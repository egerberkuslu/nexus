FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    ca-certificates \
    docker.io \
    criu \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/snapshot/ /app/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8006

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
