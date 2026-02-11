#!/bin/bash
# Complete CRIU Setup - Does everything in one script
# Usage: sudo bash COMPLETE_CRIU_SETUP.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "  CRIU Snapshot Support - Complete Setup"
echo "==========================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run with sudo: sudo bash COMPLETE_CRIU_SETUP.sh${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=$(logname 2>/dev/null || echo $SUDO_USER)
if [ -z "$ACTUAL_USER" ]; then
    echo -e "${RED}Error: Could not determine actual user${NC}"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ============================================
# Step 1: Enable Docker Experimental Features
# ============================================
echo -e "\n${YELLOW}Step 1/5: Enabling Docker experimental features...${NC}"

# Backup existing daemon.json
if [ -f /etc/docker/daemon.json ]; then
    echo "Backing up existing daemon.json..."
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
fi

# Create daemon.json with experimental features
cat > /etc/docker/daemon.json << 'EOF'
{
  "experimental": true
}
EOF

echo -e "${GREEN}✓ Created /etc/docker/daemon.json${NC}"

# Restart Docker
echo "Restarting Docker daemon..."
systemctl restart docker
sleep 5

# Verify experimental mode
if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo -e "${GREEN}✓ Docker experimental features: ENABLED${NC}"
else
    echo -e "${RED}✗ Failed to enable experimental features${NC}"
    echo "Check Docker logs: journalctl -u docker -n 50"
    exit 1
fi

# ============================================
# Step 2: Build Emulation Container with CRIU
# ============================================
echo -e "\n${YELLOW}Step 2/5: Building emulation container with CRIU support...${NC}"
echo "This may take 5-10 minutes..."

cd "$PROJECT_DIR/emulation-container"

# Build as actual user (Docker group membership)
sudo -u $ACTUAL_USER docker build -f Dockerfile.simple -t caduceus-flux-emulation-container:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Emulation container built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build emulation container${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# ============================================
# Step 3: Rebuild Snapshot Service
# ============================================
echo -e "\n${YELLOW}Step 3/5: Rebuilding snapshot service...${NC}"

sudo -u $ACTUAL_USER docker-compose build snapshot-service

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Snapshot service rebuilt${NC}"
else
    echo -e "${YELLOW}⚠ Snapshot service rebuild had issues (may be OK)${NC}"
fi

# ============================================
# Step 4: Restart Services
# ============================================
echo -e "\n${YELLOW}Step 4/5: Restarting services...${NC}"

sudo -u $ACTUAL_USER docker-compose down
sleep 3
sudo -u $ACTUAL_USER docker-compose up -d

echo -e "${GREEN}✓ Services restarted${NC}"

# ============================================
# Step 5: Verification
# ============================================
echo -e "\n${YELLOW}Step 5/5: Verifying CRIU support...${NC}"
echo "Waiting for services to start (30 seconds)..."
sleep 30

# Check if emulation container has CRIU
echo -e "\nChecking emulation container image..."
if docker run --rm caduceus-flux-emulation-container:latest criu --version 2>&1 | head -1; then
    echo -e "${GREEN}✓ CRIU is installed in emulation container${NC}"
else
    echo -e "${RED}✗ CRIU not found in emulation container${NC}"
    exit 1
fi

# Check snapshot service API
echo -e "\nChecking snapshot service API..."
if curl -s http://localhost:8006/health 2>/dev/null | grep -q "healthy"; then
    echo -e "${GREEN}✓ Snapshot service is healthy${NC}"

    # Check CRIU availability
    RESPONSE=$(curl -s http://localhost:8006/api/snapshots/types 2>/dev/null)
    if echo "$RESPONSE" | grep -q '"criu_available"'; then
        CRIU_STATUS=$(echo "$RESPONSE" | grep -o '"criu_available":[^,}]*' | cut -d: -f2)
        DOCKER_EXP=$(echo "$RESPONSE" | grep -o '"docker_experimental":[^,}]*' | cut -d: -f2)

        echo "  - CRIU available: $CRIU_STATUS"
        echo "  - Docker experimental: $DOCKER_EXP"

        if echo "$CRIU_STATUS" | grep -q "true"; then
            echo -e "${GREEN}✓ CRIU snapshots are ENABLED${NC}"
        else
            echo -e "${YELLOW}⚠ CRIU still showing as unavailable${NC}"
            echo "  This might resolve after starting an emulation"
        fi
    else
        echo -e "${YELLOW}⚠ Could not parse snapshot types response${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Snapshot service not responding yet${NC}"
    echo "  It may still be starting. Try checking in a minute."
fi

# Final summary
echo -e "\n${BLUE}=========================================="
echo "  ✓ Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Access the frontend: http://localhost:3000"
echo "  2. Create/start a topology"
echo "  3. Go to Snapshots page"
echo "  4. Create a snapshot - CRIU types should now be available!"
echo ""
echo "Available snapshot types:"
echo "  • Topology Only (Quick, ~1KB)"
echo "  • Docker Commit (Filesystem, ~100-500MB)"
echo "  • CRIU Live (Live state, ~300MB) ← NEW!"
echo "  • Hybrid Full (Complete, ~700MB) ← NEW!"
echo ""
echo "If CRIU still shows unavailable, check logs:"
echo "  docker-compose logs snapshot-service | grep -i criu"
echo ""
