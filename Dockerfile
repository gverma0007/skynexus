FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/install-postgres-client.sh ./
RUN PGCLIENT_MAJOR=18 sh install-postgres-client.sh
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
COPY backend/ ./
COPY --from=ui /ui/dist ./static
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
