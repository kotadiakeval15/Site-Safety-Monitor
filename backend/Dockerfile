# Backend image includes the ai-repo package so multiprocessing camera workers
# can import ai_repo directly. Build context is the repository root.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System libraries required by OpenCV / ultralytics + curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (backend + AI stack). Requirements are copied and
# installed BEFORE any source so that editing application/AI code does not
# invalidate the (very heavy) torch/ultralytics install layer.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install the CPU-only torch build first (inference runs on CPU). This avoids
# ultralytics pulling the multi-GB CUDA wheels, cutting build time and size.
RUN pip install torch==2.6.0 torchvision==0.21.0 \
    --index-url https://download.pytorch.org/whl/cpu

COPY ai-repo/requirements.txt /app/ai-repo/requirements.txt
RUN pip install -r /app/ai-repo/requirements.txt

# AI package source (installed editable; only re-runs when ai-repo changes).
COPY ai-repo/ /app/ai-repo/
RUN pip install -e /app/ai-repo

# Application source.
COPY backend/ /app/

# Create shared data directories.
RUN mkdir -p /data/screenshots /data/uploads /data/logs /data/live

EXPOSE 8000

# Run migrations then start the API server.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
