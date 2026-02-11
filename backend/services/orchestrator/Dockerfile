FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared code
COPY shared/ /app/shared/
COPY proto/ /app/proto/

# Generate gRPC stubs
RUN pip install --no-cache-dir grpcio-tools==1.59.0
RUN python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /app/proto/emulation.proto

# Copy service dependencies and install
COPY services/orchestrator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/orchestrator/ /app/

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=10 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run service
CMD ["python", "main.py"]
