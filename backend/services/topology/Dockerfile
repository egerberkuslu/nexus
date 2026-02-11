# Topology Service Dockerfile

FROM python:3.11-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="Topology Management Service"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared modules first
COPY shared/ /app/shared/

# Copy service requirements
COPY services/topology/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/topology/ /app/

# Expose port
EXPOSE 8001

# Health check with longer start period to allow for dependency connections
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=10 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

