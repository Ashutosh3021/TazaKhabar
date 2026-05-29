# Fallback when Railway root directory is the repo root (not backend/).
# Prefer setting Railway Root Directory to "backend" and using backend/Dockerfile.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p logs

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD hypercorn src.main:app --bind 0.0.0.0:${PORT:-8000}
