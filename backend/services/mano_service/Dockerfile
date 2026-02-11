FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared code + protos
COPY shared/ /app/shared/
COPY proto/ /app/proto/

# Generate gRPC stubs (kept out of git, generated at build time like orchestrator).
RUN pip install --no-cache-dir grpcio-tools==1.59.0
RUN python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /app/proto/mano.proto

# Install service dependencies
COPY services/mano_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/mano_service/ /app/

EXPOSE 8015
EXPOSE 50052

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=10 \
    CMD curl -f http://localhost:8015/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8015"]

