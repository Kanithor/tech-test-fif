# ── Stage 1: dependencias ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
 
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
 
# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim
 
WORKDIR /app
 
COPY --from=builder /install /usr/local
COPY main.py .
COPY src/ ./src/
 
ENV PORT=8080
 
# gunicorn: 2 workers, 4 threads — adecuado para cargas de I/O (BQ calls)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "main:app"]
 