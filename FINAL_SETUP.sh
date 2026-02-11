#!/bin/bash
# Final CRIU Setup - Run this to complete everything
# Usage: sudo bash FINAL_SETUP.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo: sudo bash FINAL_SETUP.sh"
    exit 1
fi

echo "================================================"
echo "  Final CRIU Setup - Completing Installation"
echo "================================================"
echo ""

# Get actual user
ACTUAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Step 1: Enable Docker experimental
echo "Step 1/3: Enabling Docker experimental features..."
cat > /etc/docker/daemon.json << 'EOF'
{
  "experimental": true
}
EOF
echo "✓ Created /etc/docker/daemon.json"

systemctl restart docker
echo "✓ Restarted Docker daemon"
sleep 5

if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo "✓ Docker experimental: ENABLED"
else
    echo "✗ Docker experimental: FAILED"
    exit 1
fi

# Step 2: Verify emulation container has CRIU
echo ""
echo "Step 2/3: Verifying CRIU installation..."
if docker run --rm --entrypoint bash caduceus-flux-emulation-container:latest -c "dpkg -l | grep -q criu"; then
    CRIU_VERSION=$(docker run --rm --entrypoint bash caduceus-flux-emulation-container:latest -c "dpkg -l | grep criu | awk '{print \$3}'")
    echo "✓ CRIU installed: version $CRIU_VERSION"
else
    echo "✗ CRIU not found in container image"
    echo "  Run: cd emulation-container && docker build -f Dockerfile.simple -t caduceus-flux-emulation-container:latest ."
    exit 1
fi

# Step 3: Restart services
echo ""
echo "Step 3/3: Restarting services..."
cd "$PROJECT_DIR"

if [ -n "$ACTUAL_USER" ]; then
    sudo -u $ACTUAL_USER docker-compose restart snapshot-service
else
    docker-compose restart snapshot-service
fi

echo "✓ Snapshot service restarted"
sleep 10

# Verify API
echo ""
echo "================================================"
echo "  Verification"
echo "================================================"

RESPONSE=$(curl -s http://localhost:8006/api/snapshots/types 2>/dev/null || echo '{}')
CRIU_AVAIL=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('criu_available', False))" 2>/dev/null || echo "false")
DOCKER_EXP=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('docker_experimental', False))" 2>/dev/null || echo "false")

echo ""
echo "API Status:"
echo "  Docker Experimental: $DOCKER_EXP"
echo "  CRIU Available: $CRIU_AVAIL"
echo ""

if [ "$DOCKER_EXP" = "True" ] || [ "$DOCKER_EXP" = "true" ]; then
    echo "✅ Docker experimental features: WORKING"
else
    echo "⚠️  Docker experimental: Not detected by API yet"
fi

if [ "$CRIU_AVAIL" = "True" ] || [ "$CRIU_AVAIL" = "true" ]; then
    echo "✅ CRIU snapshots: AVAILABLE"
    echo ""
    echo "================================================"
    echo "  ✅ SUCCESS! CRIU is fully enabled!"
    echo "================================================"
    echo ""
    echo "CRIU Live and Hybrid Full snapshots are now available!"
else
    echo "⚠️  CRIU: Not showing as available yet"
    echo ""
    echo "This is normal. CRIU will become available when:"
    echo "  1. You start an emulation (creates container with CRIU)"
    echo "  2. The API detects CRIU in the running container"
    echo ""
    echo "To test:"
    echo "  1. Go to: http://localhost:3000"
    echo "  2. Create and start a topology"
    echo "  3. Go to Snapshots → Create Snapshot"
    echo "  4. CRIU types should now be selectable"
fi

echo ""
echo "Next steps:"
echo "  1. Open: http://localhost:3000"
echo "  2. Create/start a topology"
echo "  3. Try creating a CRIU Live snapshot"
echo ""
