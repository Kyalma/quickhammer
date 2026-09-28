# QuickHammer — single production image.
# FastAPI serves the API, uploaded pictures, and the built React app.
#
#   docker build -t <you>/quickhammer:latest .
#   docker run -p 8000:8000 -v quickhammer-data:/data -e QH_SECRET_KEY=<random> <you>/quickhammer

# --- Stage 1: build the React frontend ---------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime --------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY scripts ./scripts
COPY --from=frontend /build/dist ./static

# All persistent state (SQLite DB + uploaded pictures) lives under /data:
# map it to a host path or named volume, and back that up.
ENV QH_DATABASE_URL=sqlite:////data/quickhammer.db \
    QH_UPLOAD_DIR=/data/uploads \
    QH_STATIC_DIR=/app/static
VOLUME /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
