FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY install-postgres-client.sh ./
RUN sh install-postgres-client.sh
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
  CMD python -c "import urllib.request, os; p=os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{p}/api/health', timeout=4)"

ENTRYPOINT ["./entrypoint.sh"]
