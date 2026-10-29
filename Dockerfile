FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render asigna el puerto mediante la variable de entorno PORT (por defecto suele ser 10000)
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]