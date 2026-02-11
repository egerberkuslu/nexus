FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
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

# Copy service code
COPY services/metrics_collector/ /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8013

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8013/health')"

# Run service
CMD ["python", "main.py"]
