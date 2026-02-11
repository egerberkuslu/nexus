#!/bin/bash
# Caduceus-Flux Startup Script
# Run this script after device restart to ensure all services are running

set -e

echo "🚀 Starting Caduceus-Flux services..."
echo ""

# Change to the project directory
cd "$(dirname "$0")"

# Clean up any previous/orphaned containers to avoid name conflicts
echo "🧹 Cleaning up old containers (including orphans)..."
docker compose down --remove-orphans || true
echo ""

# Start all services with docker-compose
echo "📦 Starting Docker Compose services..."
docker compose up -d

echo ""
echo "⏳ Waiting for infrastructure services to be healthy..."
sleep 10

# Check if key services are running
echo ""
echo "✅ Checking service status..."
docker ps --format "table {{.Names}}\t{{.Status}}" | grep caduceus | head -15

echo ""
echo "🎉 Caduceus-Flux services started!"
echo ""
echo "Access points:"
echo "  - Frontend:    http://localhost:3000"
echo "  - API Gateway: http://localhost:80"
echo "  - Grafana:     http://localhost:3001"
echo "  - Prometheus:  http://localhost:9090"
echo ""
echo "To check logs: docker logs <container-name>"
echo "To stop all:   docker compose down"
