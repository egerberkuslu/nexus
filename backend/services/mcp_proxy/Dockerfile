# MCP Proxy Dockerfile

FROM python:3.11-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="Generic MCP HTTP proxy for upstream services"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/mcp_proxy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mcp_proxy/ /app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
