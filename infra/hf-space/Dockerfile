# Image de l'API Lumen pour un Hugging Face Space (SDK Docker).
# Le Space écoute sur le port 7860, en utilisateur non root, avec un disque éphémère.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    LUMEN_MODELS_DIR=/app/models \
    LUMEN_STORAGE_DIR=/tmp/lumen/storage \
    LUMEN_DATABASE_URL=sqlite:////tmp/lumen/lumen.db \
    PYTHONPATH=/app/packages/cv:/app/apps/api

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libjpeg62-turbo libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages/cv /app/packages/cv
COPY apps/api /app/apps/api
COPY models /app/models

RUN mkdir -p /tmp/lumen/storage && chown -R 1000:1000 /tmp/lumen /app

USER 1000

WORKDIR /app/apps/api
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 7860"]
