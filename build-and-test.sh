#!/bin/bash
# Build and Test SDN Controllers in Docker

set -e

echo "🐳 Building Mininet Web Framework with All SDN Controllers"
echo "=========================================================="

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose -f docker-compose.controllers.yml down --remove-orphans || true
docker-compose down --remove-orphans || true

# Build the enhanced backend with all controllers
echo "Building backend with all SDN controllers..."
docker-compose -f docker-compose.controllers.yml build backend --no-cache

# Start the services
echo "Starting services..."
docker-compose -f docker-compose.controllers.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Check service health
echo "Checking service health..."
docker-compose -f docker-compose.controllers.yml ps

# Test controller installations inside the container
echo "Testing controller installations..."
docker-compose -f docker-compose.controllers.yml exec -T backend python3 docker_controller_test.py

# Show logs for troubleshooting
echo "Recent backend logs:"
docker-compose -f docker-compose.controllers.yml logs --tail=20 backend

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "Services available at:"
echo "  🌐 Web Interface: http://localhost:3000"
echo "  🔧 API Endpoint:  http://localhost:5000"
echo "  📊 MongoDB:       localhost:27017"
echo "  🎛️  OpenFlow:      localhost:6633"
echo "  🌍 OpenDaylight:  http://localhost:8181"
echo ""
echo "To test controllers:"
echo "  docker-compose -f docker-compose.controllers.yml exec backend python3 docker_controller_test.py"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.controllers.yml logs -f backend"
echo ""
echo "To stop services:"
echo "  docker-compose -f docker-compose.controllers.yml down"
