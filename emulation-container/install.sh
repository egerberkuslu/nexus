#!/bin/bash
# Caduceus-Flux Emulation Container Standalone Installation Script
# This script installs Mininet, Mininet-WiFi, and related dependencies on the host system
# Run with: sudo bash install.sh

set -e

echo "========================================="
echo "Caduceus-Flux Emulation Container Setup"
echo "========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use: sudo bash install.sh)"
   exit 1
fi

# Determine the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Project root: $PROJECT_ROOT"
echo "Emulation container dir: $SCRIPT_DIR"

# Update system packages
echo ""
echo "=== Updating system packages ==="
apt-get update

# Install minimal base dependencies
echo ""
echo "=== Installing base dependencies ==="
apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    sudo \
    lsb-release \
    ca-certificates \
    gnupg

# Upgrade pip
echo ""
echo "=== Upgrading pip ==="
python3 -m pip install --upgrade pip

# Install Mininet from source
echo ""
echo "=== Installing Mininet ==="
cd /opt || mkdir -p /opt && cd /opt
if [ ! -d "mininet" ]; then
    git clone https://github.com/mininet/mininet.git
fi
cd mininet
git checkout 2.3.0 2>/dev/null || git pull origin 2.3.0
PYTHON=python3 util/install.sh -nv

# Install wireless tools for Mininet-WiFi
echo ""
echo "=== Installing wireless tools ==="
apt-get install -y --no-install-recommends \
    wireless-tools \
    wpasupplicant \
    hostapd \
    rfkill \
    iw

# Install Mininet-WiFi
echo ""
echo "=== Installing Mininet-WiFi ==="
export PIP_BREAK_SYSTEM_PACKAGES=1
pip3 install --no-cache-dir numpy==1.23.5 matplotlib==3.5.3
cd /opt || mkdir -p /opt && cd /opt
if [ ! -d "mininet-wifi" ]; then
    git clone https://github.com/intrig-unicamp/mininet-wifi.git
fi
cd mininet-wifi
git checkout master 2>/dev/null || git pull origin master
PYTHON=python3 util/install.sh -Wlnfv

# Install FRRouting (for routing protocols)
echo ""
echo "=== Installing FRRouting ==="
apt-get install -y --no-install-recommends \
    frr \
    frr-doc

# Install BIRD (BGP/routing daemon)
echo ""
echo "=== Installing BIRD ==="
apt-get install -y --no-install-recommends \
    bird \
    bird2

# Install gRPC dependencies and Python requirements
echo ""
echo "=== Installing Python gRPC dependencies ==="
pip3 install --no-cache-dir \
    grpcio==1.59.0 \
    grpcio-tools==1.59.0 \
    protobuf==4.25.0 \
    pyyaml==6.0.1 \
    psutil==5.9.6 \
    netifaces==0.11.0 \
    docker==6.1.3

# Create necessary directories
echo ""
echo "=== Creating system directories ==="
mkdir -p /var/lib/caduceus-flux/{snapshots,configs,logs}
mkdir -p /var/run/openvswitch
mkdir -p /etc/openvswitch
mkdir -p /var/log/openvswitch
mkdir -p /var/run/frr
mkdir -p /var/run/bird

# Compile gRPC stubs
echo ""
echo "=== Compiling gRPC stubs ==="
if [ -f "$PROJECT_ROOT/backend/proto/emulation.proto" ]; then
    cd "$SCRIPT_DIR/grpc_agent"
    python3 -m grpc_tools.protoc \
        -I"$PROJECT_ROOT/backend/proto" \
        --python_out=. \
        --grpc_python_out=. \
        "$PROJECT_ROOT/backend/proto/emulation.proto"
    echo "gRPC stubs compiled successfully"
else
    echo "Warning: emulation.proto not found at $PROJECT_ROOT/backend/proto/emulation.proto"
fi

# Set up permissions
echo ""
echo "=== Setting up permissions ==="
chown -R $SUDO_USER:$SUDO_USER "$SCRIPT_DIR" 2>/dev/null || true
chown -R $SUDO_USER:$SUDO_USER /var/lib/caduceus-flux 2>/dev/null || true

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Copy the configuration file: cp config.yaml.example config.yaml"
echo "2. Edit the configuration: vi config.yaml"
echo "3. Start the service: sudo systemctl start caduceus-emulation"
echo "4. Check status: sudo systemctl status caduceus-emulation"
echo ""
