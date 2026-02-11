#!/bin/bash
# Check Docker build status

echo "Checking Docker build status..."
echo ""

if ps aux | grep -E "docker build.*Dockerfile.simple" | grep -v grep > /dev/null; then
    echo "✓ Build is RUNNING"
    echo ""
    echo "Docker build process:"
    ps aux | grep -E "docker build.*Dockerfile.simple" | grep -v grep
    echo ""
    echo "The build typically takes 5-10 minutes."
    echo "You can continue waiting or check back later."
else
    echo "✗ Build is NOT running"
    echo ""
    echo "Checking if image was built..."
    if docker images | grep -q "caduceus-flux-emulation-container.*latest"; then
        echo "✓ Image exists:"
        docker images | grep "caduceus-flux-emulation-container"
        echo ""
        echo "Build may have completed! Run the setup script:"
        echo "  sudo bash COMPLETE_CRIU_SETUP.sh"
    else
        echo "✗ Image not found. Build may have failed or not started."
        echo ""
        echo "To start the build manually:"
        echo "  cd emulation-container"
        echo "  docker build -f Dockerfile.simple -t caduceus-flux-emulation-container:latest ."
    fi
fi
