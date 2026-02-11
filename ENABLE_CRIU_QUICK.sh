#!/bin/bash
# Quick CRIU Enable Script - Run this to enable CRIU snapshots

echo "=============================================="
echo "  CRIU Snapshot Support - Quick Setup"
echo "=============================================="
echo ""

# Step 1: Enable Docker Experimental Features
echo "Step 1: Enabling Docker experimental features..."
echo "You need to run this command manually with sudo:"
echo ""
echo "  sudo ./enable-docker-experimental.sh"
echo ""
read -p "Press Enter after running the command above..."

# Step 2: Rebuild emulation container
echo ""
echo "Step 2: Rebuilding emulation container with CRIU..."
docker-compose build emulation-container

# Step 3: Restart services
echo ""
echo "Step 3: Restarting services..."
docker-compose down
docker-compose up -d

# Step 4: Verify
echo ""
echo "Step 4: Verification..."
echo ""

echo "Checking Docker experimental mode:"
docker version --format '{{.Server.Experimental}}'

echo ""
echo "Waiting for containers to start..."
sleep 10

echo ""
echo "Checking CRIU in emulation container:"
CONTAINER_NAME=$(docker ps --filter "name=emu" --format "{{.Names}}" | head -1)
if [ -n "$CONTAINER_NAME" ]; then
    docker exec $CONTAINER_NAME criu --version || echo "CRIU not found in container"
else
    echo "Emulation container not running"
fi

echo ""
echo "Checking snapshot types API:"
curl -s http://localhost:8006/api/snapshots/types | python3 -m json.tool | grep -E "(criu_available|docker_experimental)" || echo "Snapshot service not responding"

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "CRIU snapshots should now be available."
echo "Check the frontend Snapshots page to verify."
