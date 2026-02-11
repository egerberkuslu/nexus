# OS-Ken SDN Controller Dockerfile
# OS-Ken is the successor to Ryu, actively maintained

FROM python:3.11-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="OS-Ken SDN Controller with sample applications"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    iproute2 \
    iputils-ping \
    net-tools \
    tcpdump \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install OS-Ken
RUN pip install --no-cache-dir \
    os-ken==2.8.0 \
    eventlet==0.33.3 \
    msgpack-python==0.5.6 \
    netaddr==0.10.1 \
    ovs==3.1.7 \
    routes==2.5.1 \
    webob==1.8.7

# Create application directory
WORKDIR /opt/osken

# Copy controller applications
COPY apps/ ./apps/
COPY config/ ./config/

# Create logs directory
RUN mkdir -p /var/log/osken

# Expose OpenFlow and REST API ports
EXPOSE 6653 8080

# Environment variables
ENV OSKEN_LOG_DIR=/var/log/osken
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 6653)); s.close()" || exit 1

# Default command - run simple switch with REST API
CMD ["osken-manager", \
     "--observe-links", \
     "--ofp-tcp-listen-port", "6653", \
     "/opt/osken/apps/simple_switch_13.py"]

