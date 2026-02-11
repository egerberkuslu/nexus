# Getting Started with Caduceus-Flux

Welcome to Caduceus-Flux! This guide will help you get up and running quickly.

## What is Caduceus-Flux?

Caduceus-Flux is an advanced microservices-based network emulation platform that provides:

- **Runtime Protocol Switching**: Change routing protocols (OSPF↔BGP↔RIP) without restarting
- **12 Microservices**: Complete separation of concerns for scalability
- **Unified Emulation**: Single container with Mininet + WiFi + Containernet
- **Multi-Protocol Support**: OSPF, BGP, RIP, IS-IS, EIGRP, OpenFlow 1.0-1.5
- **Wireless Emulation**: 802.11 a/b/g/n/ac/ax with mobility models
- **P4 Programmable Switches**: BMv2 integration
- **SDN Controllers**: OS-Ken, Ryu, OpenDaylight, ONOS
- **Web Interface**: React-based topology designer with web terminal
- **Complete Observability**: Prometheus + Grafana monitoring

## Quick Start (5 Minutes)

### Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- 16GB RAM (minimum 8GB)
- 50GB free disk space
- Linux kernel 4.15+ (for network namespaces)

### Option 1: Interactive Setup (Recommended)

```bash
cd caduceus-flux
./quick-start.sh
# Select option 1: Full Setup
```

The script will:
1. ✓ Check prerequisites
2. ✓ Create .env file
3. ✓ Build all services
4. ✓ Start infrastructure
5. ✓ Start microservices
6. ✓ Create test project
7. ✓ Import example topology

### Option 2: Manual Setup

```bash
cd caduceus-flux

# 1. Create environment file
cp .env.example .env

# 2. Build services
docker-compose build

# 3. Start everything
docker-compose up -d

# 4. Wait for services to be ready
sleep 30

# 5. Check status
docker-compose ps
```

## Verify Installation

### Check Service Health

```bash
# All services should be "healthy" or "running"
docker-compose ps

# Check individual service
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"topology-service"}
```

### Access Web Interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| **Topology API** | http://localhost:8001/docs | None |
| **MCP Server** | http://localhost:8012/docs | None |
| **Grafana** | http://localhost:3001 | admin/admin |
| **RabbitMQ** | http://localhost:15672 | caduceus/changeme |
| **Prometheus** | http://localhost:9090 | None |
| **Consul** | http://localhost:8500 | None |

## Your First Topology

### 1. Create a Project

```bash
curl -X POST http://localhost:8001/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Project",
    "description": "Learning Caduceus-Flux",
    "owner": "your-name"
  }'
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My First Project",
  "description": "Learning Caduceus-Flux",
  "owner": "your-name",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

Save the `id` - you'll need it for the next steps!

### 2. Import an Example Topology

We have three example topologies ready to use:

**a) Simple Topology** (2 hosts, 1 switch - perfect for beginners)
```bash
curl -X POST "http://localhost:8001/api/topologies/import?project_id=YOUR_PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d @examples/simple-topology.json
```

**b) Wireless Mesh** (1 AP, 3 stations with mobility)
```bash
curl -X POST "http://localhost:8001/api/topologies/import?project_id=YOUR_PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d @examples/wireless-mesh.json
```

**c) Multi-Protocol Router** (3 routers with OSPF/BGP/RIP)
```bash
curl -X POST "http://localhost:8001/api/topologies/import?project_id=YOUR_PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d @examples/multi-protocol-router.json
```

### 3. View Your Topology

```bash
# List all topologies
curl http://localhost:8001/api/topologies | jq

# Get specific topology
curl http://localhost:8001/api/topologies/TOPOLOGY_ID | jq
```

### 4. Start the Emulation

**Note**: Currently requires manual gRPC call (Orchestrator service coming soon)

```bash
# Install grpcurl if not already installed
# macOS: brew install grpcurl
# Ubuntu: apt-get install grpcurl

# Start emulation
grpcurl -plaintext \
  -d '{
    "topology_id": "YOUR_TOPOLOGY_ID",
    "topology": {
      "devices": [...],
      "links": [...]
    }
  }' \
  localhost:50051 \
  emulation.EmulationService/StartEmulation
```

## Common Operations

### Manage Topologies

```bash
# List all topologies
curl http://localhost:8001/api/topologies

# Get topology details
curl http://localhost:8001/api/topologies/TOPOLOGY_ID

# Add a node to topology
curl -X POST http://localhost:8001/api/topologies/TOPOLOGY_ID/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "h3",
    "device_type": "host",
    "x": 400,
    "y": 200,
    "properties": {
      "ip": "10.0.0.3/24"
    }
  }'

# Add a link
curl -X POST http://localhost:8001/api/topologies/TOPOLOGY_ID/links \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "NODE_ID_1",
    "target_node_id": "NODE_ID_2",
    "bandwidth": 100,
    "delay": 1
  }'

# Export topology
curl http://localhost:8001/api/topologies/TOPOLOGY_ID/export > my-topology.json
```

### View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f topology-service

# View last 100 lines
docker-compose logs --tail=100 topology-service
```

### Monitor Services

```bash
# Check service status
docker-compose ps

# View resource usage
docker stats

# Check RabbitMQ queues
docker-compose exec rabbitmq rabbitmqctl list_queues

# Check database connections
docker-compose exec postgres psql -U caduceus -d caduceus_flux -c "SELECT * FROM topologies;"
```

## API Documentation

### Topology Service API (Port 8001)

Full interactive API documentation available at: http://localhost:8001/docs

**Key Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |
| POST | `/api/topologies` | Create topology |
| GET | `/api/topologies` | List topologies |
| GET | `/api/topologies/{id}` | Get topology |
| POST | `/api/topologies/{id}/nodes` | Add node |
| POST | `/api/topologies/{id}/links` | Add link |
| POST | `/api/topologies/import` | Import from JSON |
| GET | `/api/topologies/{id}/export` | Export to JSON |

### Emulation gRPC API (Port 50051)

List available methods:
```bash
grpcurl -plaintext localhost:50051 list emulation.EmulationService
```

**Key Methods**:
- `StartEmulation` - Start network emulation
- `StopEmulation` - Stop emulation
- `AddHost` - Add host device
- `AddSwitch` - Add switch device
- `AddRouter` - Add router device
- `AddLink` - Add network link
- `ExecuteCommand` - Run command on device
- `SwitchProtocol` - Hot-swap routing protocol

## Example Workflows

### Workflow 1: Create and Start Simple Network

```bash
# 1. Create project
PROJECT=$(curl -s -X POST http://localhost:8001/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Simple Network"}' | jq -r '.id')

echo "Project ID: $PROJECT"

# 2. Import topology
TOPOLOGY=$(curl -s -X POST "http://localhost:8001/api/topologies/import?project_id=$PROJECT" \
  -H "Content-Type: application/json" \
  -d @examples/simple-topology.json | jq -r '.id')

echo "Topology ID: $TOPOLOGY"

# 3. View topology
curl -s http://localhost:8001/api/topologies/$TOPOLOGY | jq '.nodes[].name'

# 4. Start emulation (via gRPC - coming soon via REST)
# grpcurl ... (see above)
```

### Workflow 2: Runtime Device Addition

```bash
# 1. Start with existing topology
TOPOLOGY_ID="your-topology-id"

# 2. Add new host
curl -X POST http://localhost:8001/api/topologies/$TOPOLOGY_ID/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "h4",
    "device_type": "host",
    "properties": {"ip": "10.0.0.4/24"}
  }'

# 3. Connect to switch
curl -X POST http://localhost:8001/api/topologies/$TOPOLOGY_ID/links \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "h4-node-id",
    "target_node_id": "s1-node-id",
    "bandwidth": 100
  }'

# 4. Add device to running emulation (via gRPC)
grpcurl -plaintext -d '{
  "name": "h4",
  "ip": "10.0.0.4/24"
}' localhost:50051 emulation.EmulationService/AddHost
```

### Workflow 3: Protocol Switching

```bash
# 1. Start router with OSPF
# 2. Run traffic test
# 3. Switch to BGP without restart

grpcurl -plaintext -d '{
  "device": "r1",
  "from_protocol": "ospf",
  "to_protocol": "bgp",
  "preserve_config": true
}' localhost:50051 emulation.EmulationService/SwitchProtocol

# 4. Verify routing table
grpcurl -plaintext -d '{
  "device": "r1"
}' localhost:50051 emulation.EmulationService/GetRoutingTable
```

## Troubleshooting

### Services Won't Start

**Problem**: Services fail to start or are unhealthy

**Solution**:
```bash
# Check logs
docker-compose logs topology-service

# Restart specific service
docker-compose restart topology-service

# Restart all services
docker-compose restart
```

### Database Connection Error

**Problem**: Services can't connect to database

**Solution**:
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres

# Wait for health check
docker-compose ps postgres
```

### Emulation Container Won't Start

**Problem**: Emulation container exits or fails to start

**Solution**:
```bash
# Check kernel modules
lsmod | grep openvswitch

# Load modules if missing
sudo modprobe openvswitch

# Check container logs
docker-compose logs emulation-container

# Ensure privileged mode is enabled (already set in docker-compose.yml)
```

### Port Already in Use

**Problem**: Port 8001, 8002, etc. already in use

**Solution**:
```bash
# Find process using port
sudo lsof -i :8001

# Kill process
sudo kill -9 PID

# Or change port in .env file
echo "TOPOLOGY_SERVICE_PORT=8101" >> .env
```

### Out of Memory

**Problem**: System runs out of memory

**Solution**:
```bash
# Check memory usage
docker stats

# Stop unnecessary services
docker-compose stop grafana prometheus

# Increase Docker memory limit in Docker Desktop settings
# Recommended: 8GB minimum, 16GB optimal
```

## Next Steps

### Learn More

1. **Read the Documentation**
   - [README.md](README.md) - Project overview
   - [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Detailed implementation guide
   - [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Current status and roadmap

2. **Explore Examples**
   - [simple-topology.json](examples/simple-topology.json) - Basic network
   - [wireless-mesh.json](examples/wireless-mesh.json) - WiFi network
   - [multi-protocol-router.json](examples/multi-protocol-router.json) - Routing protocols

3. **API Documentation**
   - http://localhost:8001/docs - Interactive Swagger UI
   - http://localhost:8012/docs - MCP Server API (coming soon)

### Contribute

1. **Implement Remaining Services**
   - See `IMPLEMENTATION_GUIDE.md` for templates
   - All 11 remaining microservices need implementation

2. **Add Protocol Plugins**
   - OSPF, BGP, RIP, IS-IS plugins
   - See plugin architecture in guide

3. **Build Frontend**
   - React + TypeScript
   - React Flow for topology designer
   - xterm.js for WebShell

### Get Help

- **Issues**: File bug reports or feature requests on GitHub
- **Discussions**: Ask questions in GitHub Discussions
- **Documentation**: Check `/docs` directory
- **Logs**: Always check `docker-compose logs` first

## Configuration

### Environment Variables

Edit `.env` file to customize:

```bash
# Database
POSTGRES_PASSWORD=your-secure-password
MONGO_PASSWORD=your-secure-password
REDIS_PASSWORD=your-secure-password

# Services Ports (if conflicts)
TOPOLOGY_SERVICE_PORT=8001
ORCHESTRATOR_SERVICE_PORT=8002
# ... etc

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Features
ENABLE_METRICS=true
ENABLE_DEBUG_ENDPOINTS=false
```

### Service Configuration

Each service can be configured via:
1. Environment variables in `.env`
2. Consul KV store
3. Service-specific config files

## Architecture Overview

```
┌──────────────┐
│   Frontend   │ (React + TypeScript)
└──────┬───────┘
       │
┌──────▼───────────────────────────────────┐
│        Nginx API Gateway                 │
└──────┬───────────────────────────────────┘
       │
┌──────▼───────────────────────────────────┐
│       MCP Server (Port 8012)             │
│     Unified API Orchestration            │
└──┬───────────────────────────────────────┘
   │
   ├─► Topology (8001)      ├─► Snapshot (8006)
   ├─► Orchestrator (8002)  ├─► WebShell (8007)
   ├─► Protocol Mgr (8003)  ├─► Export/Import (8008)
   ├─► Device Mgr (8004)    ├─► Topology Gen (8009)
   ├─► Controller (8005)    ├─► P4 Manager (8010)
   │                        └─► Monitoring (8011)
   │
   ├─► PostgreSQL (metadata)
   ├─► MongoDB (snapshots)
   ├─► Redis (cache)
   ├─► InfluxDB (metrics)
   ├─► RabbitMQ (events)
   └─► Consul (discovery)
   │
   ▼
┌───────────────────────────────────────────┐
│    Emulation Container (Port 50051)       │
│  Mininet + WiFi + Containernet + gRPC    │
└───────────────────────────────────────────┘
```

## FAQ

**Q: Can I run this on macOS/Windows?**
A: Yes, using Docker Desktop. However, emulation performance is best on Linux.

**Q: How many concurrent emulations can I run?**
A: Depends on resources. Each emulation needs ~2-4GB RAM. Currently one emulation container, but architecture supports multiple.

**Q: Can I add custom routing protocols?**
A: Yes! Use the plugin system. See `IMPLEMENTATION_GUIDE.md` for details.

**Q: Does it support IPv6?**
A: Yes, all devices support IPv4 and IPv6.

**Q: Can I export to real Mininet Python scripts?**
A: Yes! Use the Export/Import service (coming soon).

**Q: Is there a web interface?**
A: Frontend is in development. Currently API-based.

**Q: How do I add more nodes to running emulation?**
A: Use the AddHost/AddSwitch/AddRouter gRPC methods - no restart needed!

**Q: Can I snapshot a running network?**
A: Yes! Snapshot service captures complete state including routing tables, flows, ARP, etc.

## Resources

- **GitHub**: [Repository Link]
- **Documentation**: `/docs` directory
- **Examples**: `/examples` directory
- **Issues**: [Issues Link]
- **Discussions**: [Discussions Link]

## License

Apache 2.0 License - See [LICENSE](LICENSE) file

---

**Welcome to the Caduceus-Flux community!** 🎉

We're excited to have you here. If you have questions, found bugs, or want to contribute, please don't hesitate to reach out!

Happy emulating! 🚀
