FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY proto/ /app/proto/
COPY services/device_manager/ /app/

RUN pip install --no-cache-dir -r requirements.txt

# Generate gRPC stubs (needed for runtime position updates via emulation container)
RUN python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /app/proto/emulation.proto

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
