# Imagen base ligera con Python fijado (3.11: mejor compatibilidad Prophet/statsmodels).
FROM python:3.11-slim

# Evita .pyc y activa logs sin buffer (mejor para Render).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias del sistema mínimas para compilar Prophet/statsmodels si hace falta.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias primero (mejor caché de capas).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto del código.
COPY . .

# DATA_DIR por defecto dentro del contenedor (fichero local, EFÍMERO en Render free).
# En producción real usa Turso vía TURSO_DATABASE_URL para no perder el histórico.
ENV DATA_DIR=/data
RUN mkdir -p /data

# Puerto informativo; Render inyecta el real por $PORT.
EXPOSE 8501

# Streamlit escuchando en el puerto de Render, en 0.0.0.0, sin abrir navegador.
# "sh -c" es necesario para que $PORT se expanda en tiempo de ejecución.
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true"]
