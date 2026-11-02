FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# CPU-only PyTorch first (its own layer: large and rarely changes).
RUN pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "segmentation-models-pytorch>=0.4,<1.0" \
    && useradd --create-home appuser

COPY app ./app

# Package trained model weights inside the Docker image
COPY sketch_v1/checkpoints/sketch_model_v1.pth \
    /app/sketch_v1/checkpoints/sketch_model_v1.pth

# Weights are not baked in: Compose mounts ./sketch_v1/checkpoints read-only here.
ENV SEGMENTATION_MODEL_PATH=/app/sketch_v1/checkpoints/sketch_model_v1.pth

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
