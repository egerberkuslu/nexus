FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    ca-certificates \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/webshell/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir grpcio-tools
RUN mkdir /app/proto
COPY proto/emulation.proto /app/proto/emulation.proto
COPY services/webshell/ /app/
RUN python3 -m grpc_tools.protoc -I/app/proto --python_out=. --grpc_python_out=. /app/proto/emulation.proto

EXPOSE 8007

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
