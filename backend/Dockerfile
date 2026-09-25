# BoloBank API / worker image.
#   docker build -t bolobank-backend ./backend
# Secrets are NOT baked in: pass them at run time (docker-compose env_file).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

WORKDIR /app

# CPU-only PyTorch first, so sentence-transformers doesn't pull the multi-GB
# CUDA build (the API runs the small embedding model on CPU).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download the multilingual embedding model at build time, so containers
# start without internet access to Hugging Face.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
ENV HF_HUB_OFFLINE=1

COPY . .
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/audio_cache \
    && chown -R app:app /app /opt/hf
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"

# One process per container by default; scale with more containers
# (docker compose ... --scale api=N). WEB_CONCURRENCY>1 runs more processes
# in one container — then also set PROMETHEUS_MULTIPROC_DIR.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips='*'"]
