import os
import certifi  # <-- NUEVA LÍNEA IMPORTANTE
from passlib.hash import django_pbkdf2_sha256
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app) # Permite que tu React (localhost:5173) se comunique sin errores de CORS

# Conexión a MongoDB Atlas
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
db = client[os.getenv("DB_NAME")]

# Referencia a la colección principal
propiedades_collection = db['propiedades']
usuarios_collection = db['usuarios']
reservas_collection = db['reservas']

# -----------------------------------------
# GET /api/propiedades : Listar y Filtrar
# -----------------------------------------
@app.route('/api/propiedades', methods=['GET'])
def get_propiedades():
    # 1. Recibir parámetros de filtro desde la URL (ej. ?ciudad=Cancun)
    ciudad_filtro = request.args.get('ciudad')
    
    query = {}
    if ciudad_filtro:
        query['ubicacion.ciudad'] = {"$regex": ciudad_filtro, "$options": "i"}
        
    # 2. Ejecutar find()
    documentos = list(propiedades_collection.find(query))
    
    # 3. Mapear los datos de BD (Español) al formato de React (Inglés)
    resultados = []
    for doc in documentos:
        resultados.append({
            "id": str(doc["_id"]), # Convierte ObjectId o string a string seguro
            "title": doc.get("nombre", ""),
            "price": doc.get("precio_noche", 0),
            "location": doc.get("ubicacion", {}).get("ciudad", ""),
            "rating": doc.get("calificacion_promedio", 0),
            "reviews": doc.get("total_resenas", 0), 
            "amenities": doc.get("amenidades", []),
            "photoUrl": doc.get("fotos", [""])[0] if doc.get("fotos") else ""
        })
        
    return jsonify(resultados), 200

# -----------------------------------------
# POST /api/propiedades : Insertar documento
# -----------------------------------------
@app.route('/api/propiedades', methods=['POST'])
def create_propiedad():
    data = request.json
    
    nuevo_documento = {
        "nombre": data.get("title"),
        "tipo": "hotel",
        "descripcion": data.get("description", "Un lugar increíble para hospedarte."), # <-- LÍNEA AGREGADA
        "ubicacion": { "ciudad": data.get("location"), "estado": "", "direccion": "" },
        "precio_noche": int(data.get("price", 0)),
        "amenidades": data.get("amenities", []),
        "habitaciones": data.get("habitaciones", []),
        "fotos": [data.get("photoUrl")] if data.get("photoUrl") else [],
        "calificacion_promedio": 5.0,
        "activa": True,
        "anfitrion_id": ObjectId(data.get("anfitrion_id"))
    }
    
    try:
        resultado = propiedades_collection.insert_one(nuevo_documento)
        return jsonify({"mensaje": "Propiedad creada", "id": str(resultado.inserted_id)}), 201
    except Exception as e:
        print("Error al insertar:", e)
        return jsonify({"error": "Error al guardar en base de datos"}), 500

# -----------------------------------------
# GET /api/propiedades/<id> : Obtener UNA propiedad
# -----------------------------------------
@app.route('/api/propiedades/<id>', methods=['GET'])
def get_propiedad(id):
    try:
        query_id = ObjectId(id) if len(id) == 24 else id
        doc = propiedades_collection.find_one({"_id": query_id})
        
        if doc:
            resultado = {
                "id": str(doc["_id"]),
                "title": doc.get("nombre", ""),
                "price": doc.get("precio_noche", 0),
                "location": doc.get("ubicacion", {}).get("ciudad", ""),
                "rating": doc.get("calificacion_promedio", 0),
                "reviews": doc.get("total_resenas", 0),
                "comments": doc.get("comentarios", []),
                "amenities": doc.get("amenidades", []),
                "photoUrl": doc.get("fotos", [""])[0] if doc.get("fotos") else "",
                "anfitrion_id": str(doc.get("anfitrion_id", ""))
            }
            return jsonify(resultado), 200
            
        return jsonify({"error": "Propiedad no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": "ID inválido"}), 400

# -----------------------------------------
# PUT /api/propiedades/<id>/calificar : Actualizar calificación y comentarios
# -----------------------------------------
@app.route('/api/propiedades/<id>/calificar', methods=['PUT'])
def update_rating(id):
    data = request.json
    query_id = ObjectId(id) if len(id) == 24 else id
    
    nueva_resena = {
        "usuario": data.get("usuario"),
        "comentario": data.get("comentario"),
        "estrellas": data.get("estrellas")
    }
    
    resultado = propiedades_collection.update_one(
        {"_id": query_id},
        {
            "$set": {"calificacion_promedio": data.get("rating")},
            "$inc": {"total_resenas": 1},
            "$push": {"comentarios": nueva_resena} 
        }
    )
    
    if resultado.modified_count > 0:
        return jsonify({"mensaje": "Calificación y comentario actualizados"}), 200
    return jsonify({"error": "No se encontró la propiedad"}), 404

# -----------------------------------------
# DELETE /api/propiedades/<id> : Eliminar
# -----------------------------------------
@app.route('/api/propiedades/<id>', methods=['DELETE'])
def delete_propiedad(id):
    query_id = ObjectId(id) if len(id) == 24 else id
    
    resultado = propiedades_collection.delete_one({"_id": query_id})
    
    if resultado.deleted_count > 0:
        return jsonify({"mensaje": "Documento eliminado correctamente"}), 200
    return jsonify({"error": "Documento no encontrado"}), 404

# -----------------------------------------
# POST /api/login : Iniciar sesión
# -----------------------------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    nombre = data.get("nombre")
    password = data.get("password")
    
    usuario = usuarios_collection.find_one({"nombre": nombre})
    
    if usuario:
        # VERIFICACIÓN REAL ÚNICAMENTE
        if django_pbkdf2_sha256.verify(password, usuario["contrasena_hash"]):
            return jsonify({
                "id": str(usuario["_id"]),
                "nombre": usuario["nombre"]
            }), 200
            
    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

from datetime import datetime  # <-- NUEVA IMPORTACIÓN NECESARIA

# -----------------------------------------
# POST /api/reservas : Crear una reserva
# -----------------------------------------
@app.route('/api/reservas', methods=['POST'])
def create_reserva():
    data = request.json
    
    try:
        # Convertimos los textos ("YYYY-MM-DD") a objetos de Fecha nativos
        fecha_entrada = datetime.strptime(data.get("fecha_ingreso"), "%Y-%m-%d")
        fecha_salida = datetime.strptime(data.get("fecha_salida"), "%Y-%m-%d")
        
        nueva_reserva = {
            "propiedad_id": str(data.get("propiedad_id")),
            "huesped": str(data.get("usuario_id")),
            "entrada": fecha_entrada,                   # Guardado como Date
            "salida": fecha_salida,                     # Guardado como Date
            "personas": int(data.get("huespedes", 1)),
            "precio_total": float(data.get("precio_total", 0)),
            "estado": "confirmada"
        }
    
        resultado = reservas_collection.insert_one(nueva_reserva)
        return jsonify({"mensaje": "Reserva confirmada exitosamente", "id": str(resultado.inserted_id)}), 201
    except Exception as e:
        print("Error al crear reserva:", e)
        return jsonify({"error": "Error al procesar la reserva en la base de datos"}), 500

# -----------------------------------------
# GET /api/reservas/usuario/<id> : Obtener viajes de un usuario
# -----------------------------------------
@app.route('/api/reservas/usuario/<id>', methods=['GET'])
def get_reservas_usuario(id):
    try:
        documentos = list(reservas_collection.find({"huesped": str(id)}))
        
        resultados = []
        for doc in documentos:
            propiedad_id_str = str(doc.get("propiedad_id", ""))
            
            # PROTECCIÓN: Verificamos si el ID cumple con los 24 caracteres para ser ObjectId
            try:
                if len(propiedad_id_str) == 24:
                    query_id_prop = ObjectId(propiedad_id_str)
                else:
                    query_id_prop = propiedad_id_str # Lo buscamos como texto simple si es 'prop_003'
                    
                propiedad = propiedades_collection.find_one({"_id": query_id_prop})
            except:
                propiedad = None

            nombre_propiedad = propiedad.get("nombre", "Propiedad no disponible") if propiedad else "Propiedad no encontrada"
            
            entrada_db = doc.get("entrada")
            salida_db = doc.get("salida")
            
            str_entrada = entrada_db.strftime("%Y-%m-%d") if isinstance(entrada_db, datetime) else str(entrada_db)
            str_salida = salida_db.strftime("%Y-%m-%d") if isinstance(salida_db, datetime) else str(salida_db)
            
            resultados.append({
                "id": str(doc["_id"]),
                "propiedad_id": propiedad_id_str,
                "propiedad_nombre": nombre_propiedad,
                "fecha_ingreso": str_entrada,
                "fecha_salida": str_salida,
                "precio_total": doc.get("precio_total", 0),
                "estado": doc.get("estado", "")
            })
            
        return jsonify(resultados), 200
    except Exception as e:
        print("Error en get_reservas:", e)
        return jsonify({"error": "Error al obtener el historial de reservas"}), 400
# -----------------------------------------
# PUT /api/reservas/<id>/cancelar : Cancelar reserva
# -----------------------------------------
@app.route('/api/reservas/<id>/cancelar', methods=['PUT'])
def cancelar_reserva(id):
    try:
        query_id = ObjectId(id) if len(id) == 24 else id
        
        # Actualizamos el estado de la reserva a "cancelada"
        resultado = reservas_collection.update_one(
            {"_id": query_id},
            {"$set": {"estado": "cancelada"}}
        )
        
        if resultado.modified_count > 0:
            return jsonify({"mensaje": "Reserva cancelada correctamente"}), 200
        return jsonify({"error": "No se encontró la reserva"}), 404
    except Exception as e:
        return jsonify({"error": "ID de reserva inválido"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)