# Code-execution sandbox for model-written code (backend-spec BE-R10, D-10).
# Build once:  docker build -t fme-sandbox:1 sandbox/
# Runtime limits (no network, 512 MB, 10 s, non-root, read-only FS) are applied by
# backend/app/sandbox.py on every `docker run`, not here.
FROM python:3.12-slim

RUN pip install --no-cache-dir pytest==8.3.4 \
 && rm -rf /root/.cache

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /work
USER 65534:65534
