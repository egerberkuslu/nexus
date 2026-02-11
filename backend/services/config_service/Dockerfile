# Config Service Dockerfile

FROM python:3.11-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="Unified control/config orchestration service"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/config_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/config_service/ /app/

EXPOSE 8016

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8016/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8016"]
