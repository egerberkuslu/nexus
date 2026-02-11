#!/bin/bash
# One-command CRIU setup
# Usage: sudo bash SETUP_CRIU.sh

set -e

echo "=========================================="
echo "  CRIU Snapshot Support - Full Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo bash SETUP_CRIU.sh"
    exit 1
fi

# Step 1: Enable Docker experimental features
echo ""
echo "Step 1/3: Enabling Docker experimental features..."
cat > /etc/docker/daemon.json << 'EOF'
{
  "experimental": true
}
EOF

echo "✓ Updated /etc/docker/daemon.json"

systemctl restart docker
echo "✓ Restarted Docker daemon"

sleep 3

# Verify experimental mode
if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo "✓ Docker experimental features: ENABLED"
else
    echo "✗ Failed to enable experimental features"
    exit 1
fi

# Step 2: Restart services (run as the actual user, not root)
echo ""
echo "Step 2/3: Restarting services..."
cd "$(dirname "$0")"

# Get the actual user (not root)
ACTUAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)

if [ -n "$ACTUAL_USER" ]; then
    echo "Restarting docker-compose as user: $ACTUAL_USER"
    sudo -u $ACTUAL_USER docker-compose down
    sleep 2
    sudo -u $ACTUAL_USER docker-compose up -d
else
    docker-compose down
    sleep 2
    docker-compose up -d
fi

echo "✓ Services restarted"

# Step 3: Verify
echo ""
echo "Step 3/3: Waiting for services to start..."
sleep 10

echo ""
echo "Checking CRIU in emulation container..."
CONTAINER_NAME=$(docker ps --filter "name=emu" --format "{{.Names}}" | head -1)
if [ -n "$CONTAINER_NAME" ]; then
    if docker exec $CONTAINER_NAME criu --version 2>&1 | head -1; then
        echo "✓ CRIU is installed in emulation container"
    else
        echo "⚠ CRIU not found in container (build may still be in progress)"
    fi
else
    echo "⚠ Emulation container not running yet"
fi

echo ""
echo "Checking snapshot service..."
if curl -s http://localhost:8006/api/snapshots/types 2>/dev/null | grep -q "criu_available"; then
    CRIU_STATUS=$(curl -s http://localhost:8006/api/snapshots/types | grep -o '"criu_available":[^,}]*' | cut -d: -f2)
    DOCKER_EXP=$(curl -s http://localhost:8006/api/snapshots/types | grep -o '"docker_experimental":[^,}]*' | cut -d: -f2)
    echo "✓ Snapshot service responding"
    echo "  - CRIU available: $CRIU_STATUS"
    echo "  - Docker experimental: $DOCKER_EXP"
else
    echo "⚠ Snapshot service not responding yet (may still be starting)"
fi

echo ""
echo "=========================================="
echo "  ✓ Setup Complete!"
echo "=========================================="
echo ""
echo "CRIU snapshots should now be available."
echo "Check the frontend at: http://localhost:3000"
echo ""
echo "If CRIU shows as unavailable, wait 30 seconds"
echo "for services to fully start, then refresh."
