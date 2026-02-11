FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY proto/ /app/proto/
COPY services/monitoring/ /app/

# Generate gRPC stubs (needed for device telemetry via emulation container)
RUN pip install --no-cache-dir grpcio-tools==1.59.0
RUN python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /app/proto/emulation.proto

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8011

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
