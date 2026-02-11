#!/bin/bash

# Build LocalAI Host and Worker images for Caduceus-Flux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🏗️  Building LocalAI Images for Caduceus-Flux"
echo "=============================================="
echo ""

# Build Host Image
echo "📦 Building LocalAI Host Image..."
docker build -f Dockerfile.localai-host -t localai-host:latest . || {
    echo "❌ Failed to build host image"
    exit 1
}
echo "✅ Host image built: localai-host:latest"
echo ""

# Build Worker Image
echo "📦 Building LocalAI Worker Image (Smart Mode)..."
docker build -f Dockerfile.localai-worker -t localai-worker:latest . || {
    echo "❌ Failed to build worker image"
    exit 1
}
echo "✅ Worker image built: localai-worker:latest"
echo ""

echo "🎉 Build Complete!"
echo ""
echo "Images created:"
echo "  - localai-host:latest"
echo "  - localai-worker:latest"
echo ""
echo "Worker features:"
echo "  ✅ Runs with P2P token (TOKEN/LOCALAI_P2P_TOKEN)"
echo "  ✅ Backward compatible env names (P2P/LOCALAI_P2P)"
echo ""
