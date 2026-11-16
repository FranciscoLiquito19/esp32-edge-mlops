# Container image for running the ingest service in the cloud (for example
# Cloud Run with INGEST_STORAGE=gcs:<bucket>). Not needed to run it on a PC.
FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn google-cloud-storage
COPY ingest_service ./ingest_service

ENV PORT=8080
CMD ["sh", "-c", "uvicorn ingest_service.app:app --host 0.0.0.0 --port ${PORT}"]
