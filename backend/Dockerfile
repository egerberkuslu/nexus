# Backend Dockerfile for Mininet Web Framework
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-venv \
    git \
    curl \
    wget \
    net-tools \
    iproute2 \
    iputils-ping \
    tcpdump \
    iperf3 \
    openvswitch-switch \
    openvswitch-common \
    openvswitch-testcontroller \
    build-essential \
    libssl-dev \
    libffi-dev \
    sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Mininet from pip to get the latest version with TreeTopo
RUN pip3 install --no-cache-dir mininet

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies and additional requirements in one step
RUN pip3 install --no-cache-dir -r requirements.txt numpy matplotlib scipy

# Try to install Ryu with compatible eventlet, but make it optional
RUN pip3 install --no-cache-dir --force-reinstall eventlet==0.30.2 || echo "Eventlet install failed"
RUN pip3 install --no-cache-dir ryu==4.34 || echo "Ryu install failed - will use fallback controller"

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /var/log/mininet-web-framework \
    && mkdir -p /var/run/openvswitch \
    && mkdir -p /etc/openvswitch \
    && chmod +x start.py \
    && chmod +x app.py \
    && chmod +x docker_start.py \
    && chmod +x test_ryu.py \
    && chmod +x patch_eventlet.py \
    && chmod +x docker_controller.py

# Apply eventlet patch for Ryu compatibility
RUN python3 patch_eventlet.py

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/status || exit 1

# Run as root (required for Mininet)
USER root

# Create startup script that initializes OVS and starts the app
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting Open vSwitch initialization..."\n\
# Load kernel modules if possible\n\
modprobe openvswitch || echo "Warning: Could not load openvswitch module"\n\
modprobe bridge || echo "Warning: Could not load bridge module"\n\
# Create OVS database if it does not exist\n\
if [ ! -f /etc/openvswitch/conf.db ]; then\n\
    echo "Creating OVS database..."\n\
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema\n\
fi\n\
# Start OVS database server\n\
echo "Starting ovsdb-server..."\n\
ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \\\n\
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \\\n\
    --pidfile --detach\n\
sleep 2\n\
# Initialize database\n\
ovs-vsctl --no-wait init || echo "Warning: OVS already initialized"\n\
# Start ovs-vswitchd\n\
echo "Starting ovs-vswitchd..."\n\
ovs-vswitchd --pidfile --detach\n\
sleep 2\n\
# Verify OVS is running\n\
echo "Verifying OVS status..."\n\
ovs-vsctl show\n\
echo "OVS initialization complete"\n\
# Test Ryu installation\n\
echo "Testing Ryu installation..."\n\
python3 test_ryu.py\n\
if [ $? -eq 0 ]; then\n\
    echo "✓ Ryu test passed"\n\
else\n\
    echo "⚠ Ryu test failed, but continuing..."\n\
fi\n\
# Start the Python application\n\
echo "Starting Mininet Web Framework..."\n\
exec python3 docker_start.py' > /start.sh && chmod +x /start.sh

# Start the application with OVS initialization
CMD ["/start.sh"]
