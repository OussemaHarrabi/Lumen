FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libgomp1 est requis par onnxruntime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Les versions sont figées dans requirements.txt, qui couvre aussi les dépendances de lumen_cv.
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install -r /app/apps/api/requirements.txt

# lumen_cv est copié puis installé sans dépendances: elles viennent du requirements ci-dessus.
COPY packages/cv /app/packages/cv
RUN pip install --no-deps /app/packages/cv

COPY apps/api /app/apps/api
COPY models/unet_endoscopie.onnx models/unet_busi.onnx models/model_info.json /app/models/

ENV LUMEN_STORAGE_DIR=/data/storage \
    LUMEN_DATABASE_URL=sqlite:////data/lumen.db \
    LUMEN_MODELS_DIR=/app/models \
    LUMEN_WORKER_THREADS=2

RUN mkdir -p /data/storage
VOLUME ["/data"]

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir apps/api"]
