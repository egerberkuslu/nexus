# MCP Tool Hub Dockerfile

FROM python:3.11-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="External MCP server registry + proxy"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/mcp_tool_hub/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mcp_tool_hub/ /app/

EXPOSE 8018

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8018/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
