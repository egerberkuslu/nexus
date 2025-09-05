#!/bin/bash
# Quick test to verify Docker controller setup

echo "🧪 Quick Docker Controller Test"
echo "==============================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Build just the backend to test controller installation
echo "Building backend with controllers..."
cd /home/ege/Desktop/mininet-web-framework
docker build -f backend/Dockerfile.controllers -t mininet-controllers-test backend/

# Run a quick test container
echo "Running controller verification..."
docker run --rm -it mininet-controllers-test /verify_controllers.sh

echo ""
echo "🎯 Quick test complete!"
echo ""
echo "If controllers are installed correctly, you can run:"
echo "  ./build-and-test.sh"
echo ""
echo "To build and start the full application."
