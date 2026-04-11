FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la app
COPY . .

# Crear directorio para la BD persistente
RUN mkdir -p /data

# La BD vive en /data para poder montarla como volumen
ENV DB_PATH=/data/switch_selector.db
ENV PORT=5000

EXPOSE 5000

# Arrancar con gunicorn (producción) o flask (desarrollo)
CMD ["python", "app.py"]
