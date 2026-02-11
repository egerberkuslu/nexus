#!/bin/bash
# Quick Fix - Run this to enable CRIU in frontend
# Usage: sudo bash RUN_THIS_NOW.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo bash RUN_THIS_NOW.sh"
    exit 1
fi

echo "================================================"
echo "  Enabling CRIU Support - Quick Fix"
echo "================================================"
echo ""

# Step 1: Enable Docker experimental
echo "Step 1: Enabling Docker experimental features..."
cat > /etc/docker/daemon.json << 'EOF'
{
  "experimental": true
}
EOF
echo "✓ Created /etc/docker/daemon.json"

systemctl restart docker
echo "✓ Restarted Docker"
sleep 3

if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo "✓ Docker experimental: ENABLED"
else
    echo "✗ Docker experimental: FAILED"
    exit 1
fi

# Step 2: Restart snapshot service (as user)
echo ""
echo "Step 2: Restarting snapshot service..."
ACTUAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)
cd "$(dirname "$0")"

if [ -n "$ACTUAL_USER" ]; then
    sudo -u $ACTUAL_USER docker-compose restart snapshot-service
else
    docker-compose restart snapshot-service
fi
echo "✓ Snapshot service restarted"

sleep 5

# Step 3: Verify
echo ""
echo "Step 3: Checking CRIU availability..."
RESPONSE=$(curl -s http://localhost:8006/api/snapshots/types 2>/dev/null || echo '{}')
CRIU=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('criu_available', 'error'))" 2>/dev/null || echo "error")
DOCKER_EXP=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('docker_experimental', 'error'))" 2>/dev/null || echo "error")

echo "API Response:"
echo "  docker_experimental: $DOCKER_EXP"
echo "  criu_available: $CRIU"

echo ""
echo "================================================"
echo "  Status Update"
echo "================================================"

if [ "$DOCKER_EXP" = "True" ] || [ "$DOCKER_EXP" = "true" ]; then
    echo "✓ Docker experimental: ENABLED"
else
    echo "✗ Docker experimental: Still false (may need time)"
fi

if [ "$CRIU" = "True" ] || [ "$CRIU" = "true" ]; then
    echo "✓ CRIU: AVAILABLE"
    echo ""
    echo "SUCCESS! CRIU snapshots are now enabled in the frontend!"
else
    echo "⚠ CRIU: Not yet available"
    echo ""
    echo "CRIU shows as unavailable because the emulation container"
    echo "is still building. This is expected."
    echo ""
    echo "The frontend will automatically enable CRIU snapshots once:"
    echo "  1. The emulation container build finishes (check with: ./CHECK_BUILD_STATUS.sh)"
    echo "  2. You start an emulation (creates a container with CRIU)"
    echo ""
    echo "For now, you can use Docker Commit snapshots."
fi

echo ""
echo "Check frontend at: http://localhost:3000"
echo "Go to Snapshots → Create Snapshot"
echo ""
