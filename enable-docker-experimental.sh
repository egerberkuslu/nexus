#!/bin/bash
# Enable Docker Experimental Features for CRIU Support
# This script configures Docker daemon to enable checkpoint/restore functionality

set -e

echo "=== Enabling Docker Experimental Features for CRIU ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Backup existing daemon.json if it exists
DAEMON_JSON="/etc/docker/daemon.json"
if [ -f "$DAEMON_JSON" ]; then
    echo "Backing up existing daemon.json..."
    cp "$DAEMON_JSON" "${DAEMON_JSON}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Create or update daemon.json
echo "Configuring Docker daemon for experimental features..."

# Read existing config or create new one
if [ -f "$DAEMON_JSON" ]; then
    # Update existing config
    python3 -c "
import json
import sys

try:
    with open('$DAEMON_JSON', 'r') as f:
        config = json.load(f)
except:
    config = {}

# Enable experimental features
config['experimental'] = True

# Write back
with open('$DAEMON_JSON', 'w') as f:
    json.dump(config, f, indent=2)

print('Updated existing daemon.json')
"
else
    # Create new config
    cat > "$DAEMON_JSON" << 'EOF'
{
  "experimental": true
}
EOF
    echo "Created new daemon.json with experimental features enabled"
fi

echo "Docker daemon.json configuration:"
cat "$DAEMON_JSON"

# Restart Docker to apply changes
echo ""
echo "Restarting Docker daemon to apply changes..."
systemctl restart docker

# Wait for Docker to be ready
echo "Waiting for Docker to be ready..."
sleep 3

# Verify experimental mode is enabled
echo ""
echo "Verifying experimental features..."
if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo "✓ Docker experimental features are now ENABLED"
else
    echo "✗ Docker experimental features are NOT enabled"
    echo "Please check Docker daemon logs: journalctl -u docker -n 50"
    exit 1
fi

# Check if CRIU is installed on the host
echo ""
echo "Checking CRIU installation..."
if command -v criu &> /dev/null; then
    echo "✓ CRIU is installed on host: $(criu --version | head -1)"
else
    echo "⚠ CRIU is not installed on host"
    echo "To install CRIU on Ubuntu/Debian:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y criu"
fi

echo ""
echo "=== Docker Configuration Complete ==="
echo ""
echo "Next steps:"
echo "1. Rebuild the emulation container with CRIU support:"
echo "   docker-compose build emulation-container"
echo ""
echo "2. Restart your services:"
echo "   docker-compose restart"
echo ""
echo "3. Test CRIU snapshots via the snapshot service API"
