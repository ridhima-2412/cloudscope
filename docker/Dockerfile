# Dockerfile
# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# Install deps into an isolated prefix so we can copy only them later
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.10-slim AS runtime

# Keeps Python from writing .pyc files and enables stdout/stderr logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Pull only the installed packages from the builder — nothing else
COPY --from=builder /install /usr/local

# Copy application code (cache-friendly: deps layer above won't rebuild on code changes)
COPY . .

# ── Security: run as non-root ─────────────────────────────────────────────────
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# ── Health check — Docker restarts the container if this fails 3× ─────────────
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
