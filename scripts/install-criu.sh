#!/bin/bash
###############################################################################
# CRIU Installation Script for Caduceus-Flux
# Installs and configures CRIU for container checkpointing
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/caduceus-criu-install.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root"
        exit 1
    fi
}

check_kernel() {
    log "Checking kernel configuration..."

    KERNEL_VERSION=$(uname -r | cut -d. -f1)
    KERNEL_MINOR=$(uname -r | cut -d. -f2)

    log "Kernel version: $(uname -r)"

    if [ "$KERNEL_VERSION" -lt 5 ]; then
        warn "Kernel 5.0+ is recommended for full CRIU support"
        warn "Current kernel: $(uname -r)"
        warn "Some features may not work correctly"
    else
        log "Kernel version is compatible"
    fi

    # Check for CONFIG_CHECKPOINT_RESTORE
    if [ -f "/boot/config-$(uname -r)" ]; then
        if grep -q "CONFIG_CHECKPOINT_RESTORE=y" "/boot/config-$(uname -r)"; then
            log "CONFIG_CHECKPOINT_RESTORE is enabled"
        else
            error "CONFIG_CHECKPOINT_RESTORE is not enabled in kernel"
            error "CRIU will not work without this kernel feature"
            exit 1
        fi
    else
        warn "Could not check kernel config. Proceeding anyway..."
    fi
}

install_dependencies() {
    log "Installing CRIU dependencies..."

    apt-get update
    apt-get install -y \
        build-essential \
        pkg-config \
        libprotobuf-dev \
        libprotobuf-c-dev \
        protobuf-c-compiler \
        protobuf-compiler \
        python3-protobuf \
        libnet-dev \
        libnl-3-dev \
        libcap-dev \
        asciidoc \
        xmlto \
        python3-pip \
        iptables \
        iproute2

    log "Dependencies installed successfully"
}

install_criu() {
    log "Installing CRIU..."

    # Try to install from package manager first
    if apt-get install -y criu; then
        log "CRIU installed from package manager"
    else
        warn "Package manager installation failed, building from source..."
        build_criu_from_source
    fi
}

build_criu_from_source() {
    log "Building CRIU from source..."

    CRIU_VERSION="3.18"
    BUILD_DIR="/tmp/criu-build"

    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"

    # Download CRIU
    wget "https://github.com/checkpoint-restore/criu/archive/v${CRIU_VERSION}.tar.gz" \
        -O criu.tar.gz

    tar -xzf criu.tar.gz
    cd "criu-${CRIU_VERSION}"

    # Build and install
    make
    make install

    # Clean up
    cd /
    rm -rf "$BUILD_DIR"

    log "CRIU built and installed from source"
}

configure_docker() {
    log "Configuring Docker for CRIU support..."

    DOCKER_DAEMON_JSON="/etc/docker/daemon.json"

    # Backup existing config
    if [ -f "$DOCKER_DAEMON_JSON" ]; then
        cp "$DOCKER_DAEMON_JSON" "${DOCKER_DAEMON_JSON}.backup"
        log "Backed up existing Docker config"
    fi

    # Create or update daemon.json
    if [ -f "$DOCKER_DAEMON_JSON" ]; then
        # Update existing config
        python3 -c "
import json
import sys

try:
    with open('$DOCKER_DAEMON_JSON', 'r') as f:
        config = json.load(f)
except:
    config = {}

config['experimental'] = True
config['live-restore'] = True

with open('$DOCKER_DAEMON_JSON', 'w') as f:
    json.dump(config, f, indent=2)

print('Docker configuration updated')
"
    else
        # Create new config
        cat > "$DOCKER_DAEMON_JSON" <<EOF
{
  "experimental": true,
  "live-restore": true,
  "storage-driver": "overlay2"
}
EOF
        log "Created new Docker daemon configuration"
    fi

    # Restart Docker
    log "Restarting Docker daemon..."
    systemctl restart docker

    # Wait for Docker to be ready
    sleep 5

    if systemctl is-active --quiet docker; then
        log "Docker restarted successfully"
    else
        error "Docker failed to restart"
        exit 1
    fi
}

verify_criu() {
    log "Verifying CRIU installation..."

    # Check if CRIU is in PATH
    if ! command -v criu &> /dev/null; then
        error "CRIU command not found"
        exit 1
    fi

    # Check CRIU version
    CRIU_VERSION=$(criu --version | grep -oP 'Version: \K[0-9.]+' || echo "unknown")
    log "CRIU version: $CRIU_VERSION"

    # Run CRIU check
    log "Running CRIU capability check..."
    if criu check 2>&1 | tee -a "$LOG_FILE"; then
        log "CRIU check passed successfully"
    else
        warn "CRIU check reported some issues"
        warn "Some features may not work. Check the output above."
    fi

    # Test CRIU with Docker
    log "Testing CRIU with Docker..."
    test_criu_docker
}

test_criu_docker() {
    log "Running Docker checkpoint test..."

    # Create a simple test container
    TEST_CONTAINER="criu-test-$$"

    docker run -d --name "$TEST_CONTAINER" \
        --security-opt seccomp=unconfined \
        alpine sleep 3600 &>/dev/null || true

    sleep 2

    # Try to checkpoint it
    if docker checkpoint create "$TEST_CONTAINER" test-checkpoint 2>&1 | tee -a "$LOG_FILE"; then
        log "Docker checkpoint test PASSED"

        # List the checkpoint
        if docker checkpoint ls "$TEST_CONTAINER" | grep -q "test-checkpoint"; then
            log "Checkpoint verification PASSED"
        fi
    else
        warn "Docker checkpoint test FAILED"
        warn "This might be due to:"
        warn "  - Docker experimental features not enabled"
        warn "  - Missing kernel features"
        warn "  - Security restrictions"
    fi

    # Cleanup
    docker rm -f "$TEST_CONTAINER" &>/dev/null || true
}

create_checkpoint_directory() {
    log "Creating CRIU checkpoint directories..."

    mkdir -p /var/lib/caduceus/criu
    mkdir -p /var/lib/caduceus/snapshots

    chmod 755 /var/lib/caduceus/criu
    chmod 755 /var/lib/caduceus/snapshots

    log "Checkpoint directories created"
}

install_python_criu() {
    log "Installing Python CRIU bindings..."

    pip3 install pycriu || warn "Python CRIU bindings installation failed"
}

generate_report() {
    log "Generating installation report..."

    REPORT_FILE="/var/lib/caduceus/criu-installation-report.txt"

    cat > "$REPORT_FILE" <<EOF
CRIU Installation Report
========================
Date: $(date)
Hostname: $(hostname)

System Information:
-------------------
Kernel: $(uname -r)
OS: $(lsb_release -d | cut -f2)
Architecture: $(uname -m)

CRIU Installation:
------------------
CRIU Version: $(criu --version 2>/dev/null || echo "Not available")
CRIU Path: $(which criu 2>/dev/null || echo "Not found")

Docker Configuration:
---------------------
Docker Version: $(docker --version)
Experimental Features: $(docker version --format '{{.Server.Experimental}}')

Kernel Features:
----------------
CONFIG_CHECKPOINT_RESTORE: $(grep CONFIG_CHECKPOINT_RESTORE /boot/config-$(uname -r) 2>/dev/null || echo "Unknown")

CRIU Check Results:
-------------------
$(criu check 2>&1 || echo "CRIU check failed")

Installation Status:
--------------------
✓ CRIU installed
✓ Dependencies installed
✓ Docker configured
✓ Checkpoint directories created

Next Steps:
-----------
1. Review this report for any warnings
2. Test CRIU with: /scripts/test-criu.sh
3. Restart emulation-container to use CRIU features

For more information:
- CRIU documentation: https://criu.org/
- Caduceus-Flux CRIU guide: /docs/CRIU_USAGE.md
EOF

    log "Installation report saved to: $REPORT_FILE"
    cat "$REPORT_FILE"
}

main() {
    log "========================================="
    log "CRIU Installation for Caduceus-Flux"
    log "========================================="

    check_root
    check_kernel
    install_dependencies
    install_criu
    configure_docker
    create_checkpoint_directory
    install_python_criu
    verify_criu
    generate_report

    log "========================================="
    log "CRIU Installation Complete!"
    log "========================================="
    log ""
    log "Next steps:"
    log "  1. Review the installation report at /var/lib/caduceus/criu-installation-report.txt"
    log "  2. Run tests: ./scripts/test-criu.sh"
    log "  3. Restart emulation services"
    log ""
    log "To use CRIU snapshots, see documentation at docs/CRIU_USAGE.md"
}

# Run main function
main "$@"
