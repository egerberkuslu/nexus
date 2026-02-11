# Ryu SDN Controller Dockerfile
# Ryu is a component-based SDN framework

FROM python:3.10-slim

LABEL maintainer="Caduceus-Flux Team"
LABEL description="Ryu SDN Controller with sample applications"

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

# Install Ryu with compatible eventlet version
RUN pip install --no-cache-dir \
    dnspython==1.16.0 \
    ryu==4.34 \
    eventlet==0.30.2 \
    greenlet==1.1.3 \
    msgpack-python==0.5.6 \
    netaddr==0.8.0 \
    ovs==2.17.12 \
    routes==2.5.1 \
    webob==1.8.7

# Create application directory
WORKDIR /opt/ryu

# Copy controller applications
COPY apps/ ./apps/
COPY config/ ./config/

# Create logs directory
RUN mkdir -p /var/log/ryu

# Expose OpenFlow and REST API ports
EXPOSE 6653 8080

# Environment variables
ENV RYU_LOG_DIR=/var/log/ryu
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 6653)); s.close()" || exit 1

# Default command - run simple switch with REST API
CMD ["ryu-manager", \
     "--observe-links", \
     "--ofp-tcp-listen-port", "6653", \
     "--wsapi-port", "8080", \
     "/opt/ryu/apps/simple_switch_13.py", \
     "/opt/ryu/apps/ofctl_rest.py"]

