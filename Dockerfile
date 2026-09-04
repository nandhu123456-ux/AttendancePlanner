# ---- Stage 1: build the React frontend -------------------------------
FROM node:22 AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Build WITHOUT the local .env.local so VITE_API_URL is unset and the frontend
# talks to the API via a relative (same-origin) path.
RUN rm -f .env.local .env && npm run build

# ---- Stage 2: Python backend + bundled frontend -----------------------
FROM python:3.12-slim
WORKDIR /backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/frontend/dist

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist /frontend/dist

EXPOSE 8000
# Render injects $PORT; default to 8000 when running via Docker Compose.
CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-8000}"]