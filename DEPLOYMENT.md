# Caduceus-Flux Deployment Guide

## Current Deployment Status

**Version**: 1.0.0-alpha
**Completion**: ~45%
**Status**: Active Development

This guide covers deploying the **currently implemented components** of Caduceus-Flux.

---

## What's Available to Deploy

### ✅ Fully Functional Components

1. **Infrastructure Services** (100%)
   - PostgreSQL database
   - MongoDB document store
   - Redis cache
   - InfluxDB time-series
   - RabbitMQ message broker
   - Consul service discovery
   - Prometheus metrics
   - Grafana dashboards

2. **Microservices** (2/12 complete)
   - Topology Service (Port 8001) ✅
   - Orchestrator Service (Port 8002) ✅

3. **Emulation Container** (70%)
   - Docker image with all tools
   - gRPC server
   - Device and link management

4. **Protocol System** (30%)
   - Plugin architecture
   - OSPF and BGP plugins

---

## Prerequisites

### System Requirements

```
Minimum:
- CPU: 4 cores
- RAM: 8GB
- Disk: 30GB free space
- OS: Linux (Ubuntu 20.04+ recommended)

Recommended:
- CPU: 8+ cores
- RAM: 16GB+
- Disk: 50GB+ SSD
- OS: Ubuntu 22.04 LTS
```

### Software Requirements

```bash
# Docker
docker --version  # 24.0+
docker-compose --version  # 2.20+

# Python (for development)
python3 --version  # 3.11+

# Git
git --version  # 2.0+
```

### Installation

#### Ubuntu/Debian

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt install docker-compose-plugin

# Install development tools (optional)
sudo apt install python3-pip python3-venv git
```

#### macOS

```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop and enable Kubernetes (optional)
open /Applications/Docker.app
```

---

## Quick Deployment

### Option 1: Automated Setup (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd caduceus-flux

# Run automated setup
./quick-start.sh

# Select option 1: Full Setup
# This will:
# - Check prerequisites
# - Create .env file
# - Build all images
# - Start all services
# - Create test project
```

### Option 2: Manual Deployment

```bash
# 1. Clone and configure
git clone <repository-url>
cd caduceus-flux
cp .env.example .env

# 2. Edit configuration (optional)
nano .env

# 3. Build services
docker-compose build

# 4. Start infrastructure
docker-compose up -d postgres mongodb redis rabbitmq consul influxdb

# 5. Wait for health checks (30 seconds)
sleep 30
docker-compose ps

# 6. Start microservices
docker-compose up -d topology-service orchestrator-service

# 7. Verify deployment
docker-compose ps
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## Service-by-Service Deployment

### 1. Infrastructure Layer

#### Start Core Databases

```bash
# PostgreSQL
docker-compose up -d postgres

# Verify
docker-compose exec postgres psql -U caduceus -d caduceus_flux -c "SELECT version();"

# MongoDB
docker-compose up -d mongodb

# Verify
docker-compose exec mongodb mongosh -u caduceus -p changeme --eval "db.runCommand({ping:1})"

# Redis
docker-compose up -d redis

# Verify
docker-compose exec redis redis-cli -a changeme ping
```

#### Start Message Broker & Service Discovery

```bash
# RabbitMQ
docker-compose up -d rabbitmq

# Verify
curl http://localhost:15672  # Management UI
# Login: caduceus / changeme

# Consul
docker-compose up -d consul

# Verify
curl http://localhost:8500/v1/status/leader
```

#### Start Monitoring Stack

```bash
# Prometheus
docker-compose up -d prometheus

# Verify
curl http://localhost:9090/-/healthy

# Grafana
docker-compose up -d grafana

# Verify
curl http://localhost:3001/api/health
# Login: admin / changeme
```

### 2. Microservices Layer

#### Topology Service (Port 8001)

```bash
# Build
docker-compose build topology-service

# Start
docker-compose up -d topology-service

# Verify
curl http://localhost:8001/health

# Test API
curl http://localhost:8001/docs  # Swagger UI

# Create test project
curl -X POST http://localhost:8001/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Project","description":"Testing deployment"}'
```

#### Orchestrator Service (Port 8002)

```bash
# Build
docker-compose build orchestrator-service

# Start
docker-compose up -d orchestrator-service

# Verify
curl http://localhost:8002/health

# Check active emulations
curl http://localhost:8002/api/emulation/active
```

### 3. Emulation Container

```bash
# Build (takes 15-20 minutes first time)
docker-compose build emulation-container

# Start
docker-compose up -d emulation-container

# Verify gRPC server
# Install grpcurl if not available
# brew install grpcurl  # macOS
# apt install grpcurl    # Ubuntu

grpcurl -plaintext localhost:50051 list

# Should show: emulation.EmulationService
```

---

## Verification & Testing

### Health Check All Services

```bash
#!/bin/bash
# health-check.sh

echo "Checking service health..."

services=(
    "postgres:5432"
    "mongodb:27017"
    "redis:6379"
    "rabbitmq:5672"
    "consul:8500"
    "topology-service:8001"
    "orchestrator-service:8002"
)

for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"

    if nc -z localhost $port 2>/dev/null; then
        echo "✅ $name (port $port) - UP"
    else
        echo "❌ $name (port $port) - DOWN"
    fi
done

# HTTP health checks
echo ""
echo "HTTP Health Checks:"
curl -s http://localhost:8001/health | jq '.status' 2>/dev/null && echo "✅ Topology Service" || echo "❌ Topology Service"
curl -s http://localhost:8002/health | jq '.status' 2>/dev/null && echo "✅ Orchestrator Service" || echo "❌ Orchestrator Service"
```

### Test Complete Workflow

```bash
#!/bin/bash
# test-workflow.sh

echo "Testing Caduceus-Flux workflow..."

# 1. Create project
echo "1. Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8001/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Workflow","description":"Automated test"}')

PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
echo "   Project ID: $PROJECT_ID"

# 2. Import topology
echo "2. Importing topology..."
TOPOLOGY_RESPONSE=$(curl -s -X POST "http://localhost:8001/api/topologies/import?project_id=$PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d @examples/simple-topology.json)

TOPOLOGY_ID=$(echo $TOPOLOGY_RESPONSE | jq -r '.id')
echo "   Topology ID: $TOPOLOGY_ID"

# 3. List nodes
echo "3. Listing nodes..."
curl -s "http://localhost:8001/api/topologies/$TOPOLOGY_ID/nodes" | jq '.[] | .name'

# 4. Check orchestrator
echo "4. Checking orchestrator..."
curl -s http://localhost:8002/api/emulation/active | jq

echo "✅ Workflow test complete!"
```

---

## Configuration

### Environment Variables

Edit `.env` file for customization:

```bash
# Database Passwords
POSTGRES_PASSWORD=your_secure_password
MONGO_PASSWORD=your_secure_password
REDIS_PASSWORD=your_secure_password

# Service Ports (change if conflicts)
TOPOLOGY_SERVICE_PORT=8001
ORCHESTRATOR_SERVICE_PORT=8002

# Logging
LOG_LEVEL=INFO  # DEBUG for development

# Features
ENABLE_METRICS=true
ENABLE_DEBUG_ENDPOINTS=false
```

### Database Initialization

```bash
# PostgreSQL - Run migrations (if any)
docker-compose exec topology-service alembic upgrade head

# MongoDB - Create indexes
docker-compose exec mongodb mongosh -u caduceus -p changeme caduceus_flux --eval '
  db.snapshot_states.createIndex({snapshot_id: 1})
  db.snapshot_states.createIndex({topology_id: 1})
  db.snapshot_states.createIndex({timestamp: -1})
'

# Redis - Configure persistence
docker-compose exec redis redis-cli -a changeme CONFIG SET save "900 1 300 10"
```

---

## Monitoring & Observability

### Prometheus

Access: http://localhost:9090

```yaml
# Custom queries
# Check service health
up{job="topology-service"}

# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### Grafana

Access: http://localhost:3001
Login: admin / changeme

```bash
# Import pre-configured dashboard
curl -X POST http://localhost:3001/api/dashboards/import \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(cat .grafana-token)" \
  -d @infrastructure/grafana/dashboards/topology-overview.json
```

### Logs

```bash
# View logs
docker-compose logs -f topology-service
docker-compose logs -f orchestrator-service

# Filter errors
docker-compose logs topology-service 2>&1 | grep ERROR

# Export logs
docker-compose logs --no-color > caduceus-flux-logs.txt
```

---

## Scaling

### Horizontal Scaling

```bash
# Scale topology service to 3 instances
docker-compose up -d --scale topology-service=3

# Verify
docker-compose ps topology-service
```

### Resource Limits

Edit `docker-compose.yml`:

```yaml
services:
  topology-service:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

---

## Backup & Restore

### Database Backup

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# PostgreSQL
docker-compose exec -T postgres pg_dump -U caduceus caduceus_flux > "$BACKUP_DIR/postgres.sql"

# MongoDB
docker-compose exec -T mongodb mongodump --username=caduceus --password=changeme --out=/dump
docker-compose cp mongodb:/dump "$BACKUP_DIR/mongodb"

# Redis
docker-compose exec redis redis-cli -a changeme SAVE
docker-compose cp redis:/data/dump.rdb "$BACKUP_DIR/redis.rdb"

echo "Backup completed: $BACKUP_DIR"
```

### Restore

```bash
#!/bin/bash
# restore.sh

BACKUP_DIR=$1

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: ./restore.sh <backup_directory>"
    exit 1
fi

# PostgreSQL
docker-compose exec -T postgres psql -U caduceus caduceus_flux < "$BACKUP_DIR/postgres.sql"

# MongoDB
docker-compose cp "$BACKUP_DIR/mongodb" mongodb:/dump
docker-compose exec mongodb mongorestore --username=caduceus --password=changeme /dump

# Redis
docker-compose stop redis
docker-compose cp "$BACKUP_DIR/redis.rdb" redis:/data/dump.rdb
docker-compose start redis

echo "Restore completed from: $BACKUP_DIR"
```

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Find process using port
sudo lsof -i :8001

# Kill process
sudo kill -9 <PID>

# Or change port in .env
echo "TOPOLOGY_SERVICE_PORT=8101" >> .env
```

#### 2. Services Won't Start

```bash
# Check logs
docker-compose logs topology-service

# Rebuild
docker-compose build --no-cache topology-service

# Restart
docker-compose restart topology-service
```

#### 3. Database Connection Errors

```bash
# Check if database is ready
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U caduceus -d caduceus_flux -c "SELECT 1;"

# Restart database
docker-compose restart postgres
```

#### 4. gRPC Connection Failed

```bash
# Check if emulation container is running
docker-compose ps emulation-container

# Check gRPC server
grpcurl -plaintext localhost:50051 list

# View logs
docker-compose logs emulation-container

# Restart container
docker-compose restart emulation-container
```

#### 5. Out of Memory

```bash
# Check Docker memory
docker stats

# Increase Docker memory in Docker Desktop settings
# Or stop unnecessary services
docker-compose stop grafana prometheus
```

---

## Security Hardening

### Production Checklist

- [ ] Change all default passwords in `.env`
- [ ] Enable HTTPS/TLS for all services
- [ ] Configure firewall rules
- [ ] Enable authentication on APIs
- [ ] Set up VPN for remote access
- [ ] Configure log rotation
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Backup encryption
- [ ] API rate limiting

### Enable TLS

```bash
# Generate certificates
./scripts/generate-certs.sh

# Update docker-compose.yml
# Add SSL certificates to nginx configuration
```

---

## Performance Tuning

### Database Optimization

```bash
# PostgreSQL
docker-compose exec postgres psql -U caduceus caduceus_flux <<EOF
  ALTER SYSTEM SET shared_buffers = '2GB';
  ALTER SYSTEM SET effective_cache_size = '6GB';
  ALTER SYSTEM SET maintenance_work_mem = '512MB';
  ALTER SYSTEM SET work_mem = '32MB';
EOF

# Restart
docker-compose restart postgres
```

### Redis Optimization

```bash
docker-compose exec redis redis-cli -a changeme <<EOF
  CONFIG SET maxmemory 2gb
  CONFIG SET maxmemory-policy allkeys-lru
  CONFIG REWRITE
EOF
```

---

## Maintenance

### Regular Tasks

```bash
# Daily
./scripts/health-check.sh
./scripts/backup.sh

# Weekly
docker system prune -f
docker volume prune -f

# Monthly
docker-compose pull  # Update images
docker-compose up -d  # Restart with new images
```

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild changed services
docker-compose build

# Rolling update (no downtime)
docker-compose up -d --no-deps --build topology-service
```

---

## Uninstallation

### Stop Services

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

### Complete Cleanup

```bash
# Remove everything
docker-compose down -v --rmi all --remove-orphans

# Remove project directory
cd ..
rm -rf caduceus-flux

# Remove Docker networks
docker network prune -f

# Remove unused volumes
docker volume prune -f
```

---

## Next Steps

Once deployed and verified:

1. **Explore the API**
   - http://localhost:8001/docs (Topology Service)
   - http://localhost:8002/docs (Orchestrator Service)

2. **Create Your First Topology**
   - Use provided examples
   - Design custom networks

3. **Monitor Performance**
   - Grafana dashboards
   - Prometheus metrics

4. **Provide Feedback**
   - Report issues
   - Suggest improvements

---

## Support

### Getting Help

- **Documentation**: See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- **Issues**: Create GitHub issue with deployment logs
- **Logs**: Always include `docker-compose logs` output

### Useful Commands

```bash
# Service status
docker-compose ps

# View logs
docker-compose logs -f <service>

# Restart service
docker-compose restart <service>

# Enter container
docker-compose exec <service> /bin/bash

# Check resources
docker stats
```

---

## Roadmap

**Current**: Alpha release (45% complete)
**Next**: Complete all microservices (70% complete)
**Future**: Full production release (100% complete)

See [PROGRESS_REPORT.md](PROGRESS_REPORT.md) for detailed status.

---

**Deployment Status**: ✅ Ready for Development/Testing
**Production Ready**: ❌ Not Yet (Target: 90%+ completion)
**Last Updated**: Current Session
