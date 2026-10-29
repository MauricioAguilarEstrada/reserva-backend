from passlib.hash import django_pbkdf2_sha256

usuarios = [
    ("Ana Lopez", "WvH7kocVwcD_wA"),
    ("Luis Gomez", "1YSiBarMBd3QrQ"),
    ("Maria Torres", "OadfID_fsDz-mA"),
    ("Carlos Perez", "U1tnvPT56jIWHQ"),
    ("Anfitrion de ejemplo", "FJwTFM7BSFjelg")
]

print("--- HASHES PARA MONGODB ATLAS ---\n")
for nombre, pwd in usuarios:
    hash_generado = django_pbkdf2_sha256.hash(pwd)
    print(f"Usuario: {nombre}")
    print(f"contrasena_hash: '{hash_generado}'\n")