# Caduceus-Flux: Advanced Microservices Network Emulation Platform

## Overview

Caduceus-Flux is a comprehensive, microservices-based network emulation platform that provides:

- **Unified Emulation Engine**: Per-topology privileged container running Mininet + Mininet-WiFi + Containernet
- **Microservices Control Plane**: Separation of concerns across topology/orchestration/monitoring/AI/MANO services
- **Protocol Agnostic**: Runtime protocol switching without restart
- **Plugin Architecture**: Extensible device, protocol, and controller plugins
- **Real-time Operations**: Add/remove devices and links without emulation restart
- **Multi-Protocol Support**: OSPF, BGP, RIP, IS-IS, EIGRP, OpenFlow 1.0-1.5
- **Wireless Standards**: 802.11 a/b/g/n/ac/ax with runtime transitions
- **SDN Controllers**: OS-Ken, Ryu, OpenDaylight, ONOS support
- **P4 Programmable Switches**: BMv2 integration with P4Runtime
- **Web Interface**: React-based topology designer with WebShell
- **Snapshot System**: Complete state capture and restoration
- **MCP Server**: Unified control interface
- **Full Observability**: Prometheus/Grafana monitoring

## Architecture

### Control Plane Services (Ports 8001+)

1. **Topology Service** (8001) - CRUD operations, JSON I/O, versioning
2. **Emulation Orchestrator** (8002) - Lifecycle management, gRPC client
3. **Protocol Manager** (8003) - Plugin system, hot-swapping
4. **Device Manager** (8004) - Runtime device operations
5. **Controller Manager** (8005) - SDN controller lifecycle
6. **Snapshot Service** (8006) - State capture/restore
7. **WebShell Service** (8007) - TTY over WebSocket
8. **Export/Import Service** (8008) - Python script generation
9. **Topology Generator** (8009) - Auto-generation algorithms
10. **P4 Manager** (8010) - P4 compilation, BMv2 management
11. **Monitoring Service** (8011) - Metrics collection
12. **MCP Server** (8012) - Unified API orchestration
13. **Metrics Collector** (8013) - gRPC metrics streaming bridge → Kafka/Influx
14. **AI Gateway** (8014) - LLM provider gateway + model registry + MCP request generation/execution
15. **MANO Service** (8015) - Local MANO core + OSM mirroring/sync (gRPC: 50052)
16. **Config Service** (8016) - Unified JSON “control config” orchestration across subsystems
17. **Decision Engine** (8017) - Streaming decisions from processed metrics → alerts/actions
18. **OSM Connector** (8020) - SOL005/NBI adapter + authenticated proxy for ETSI OSM

Notes:
- The orchestrator can spawn additional **topology-scoped** runtime containers (emulation, VIM emulator, per-topology OSM stack).
- See `docs/paper/SYSTEM_ARCHITECTURE.md` for diagrams and end-to-end flows.

### Emulation Container(s) (gRPC Port 50051)

Privileged Docker container with gRPC server including:
- Mininet 2.3+
- Mininet-WiFi
- Containernet
- Open vSwitch (multi-version OpenFlow support)
- FRRouting (OSPF, BGP, RIP, IS-IS)
- BIRD routing daemon
- BMv2 (P4 behavioral model)
- hostapd/wpa_supplicant

### Further Reading

- Single-file project overview (purpose + progress): `docs/PROJECT_OVERVIEW.md`
- System architecture (GitHub-ready): `docs/paper/SYSTEM_ARCHITECTURE.md`
- Academic paper draft (Markdown): `docs/paper/ACADEMIC_PAPER_DRAFT.md`
- Control Config (unified control plane): `docs/CONTROL_CONFIG.md`
- MANO + OSM integration: `docs/MANO_FEATURES.md`, `docs/OSM_INTEGRATION.md`
- Metrics pipeline: `METRICS_PIPELINE.md`, `docs/AI_ML_STREAMING_CONTROL_PLANE.md`

## Quick Start

### Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- 16GB RAM minimum
- 50GB disk space

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/caduceus-flux.git
cd caduceus-flux

# Start all services
docker-compose up -d

# Wait for services to be ready
./scripts/wait-for-services.sh

# Access web interface
open http://localhost:3000
```

### Basic Usage

```bash
# Create a topology
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @examples/simple-topology.json

# Start emulation
curl -X POST http://localhost:8002/api/emulation/start \
  -d '{"topology_id": "topology-id"}'

# Add device at runtime
curl -X POST http://localhost:8004/api/devices \
  -d '{"type": "host", "name": "h3", "ip": "10.0.0.3/24"}'

# Take snapshot
curl -X POST http://localhost:8006/api/snapshots \
  -d '{"name": "checkpoint-1"}'
```

## Technology Stack

### Backend
- Python 3.11+, FastAPI, gRPC
- SQLAlchemy, Alembic
- RabbitMQ/Kafka
- Docker SDK

### Frontend
- React 18+, TypeScript
- React Flow (topology visualization)
- xterm.js (web terminal)
- Material-UI

### Databases
- PostgreSQL (metadata)
- MongoDB (state snapshots)
- Redis (caching, pub/sub)
- InfluxDB (time-series metrics)

### Infrastructure
- Docker, Docker Compose
- Consul (service discovery)
- Prometheus, Grafana
- Nginx (API gateway)

## Features

### Runtime Protocol Switching
Switch protocols without restarting emulation:
- OpenFlow versions (1.0 → 1.3 → 1.4 → 1.5)
- Routing protocols (OSPF ↔ BGP ↔ RIP ↔ IS-IS)
- Wireless standards (802.11n ↔ 802.11ac ↔ 802.11ax)
- Security modes (WPA ↔ WPA2 ↔ WPA3)

### Device Types
- **Hosts**: IPv4/IPv6, custom routes, applications
- **Switches**: OVS, Linux Bridge, P4
- **Routers**: Multi-protocol (FRR/BIRD)
- **Access Points**: Multi-standard 802.11
- **Stations**: Wireless clients with mobility
- **Docker Containers**: Full Containernet integration
- **P4 Switches**: BMv2 with P4Runtime

### Plugin System
Extensible plugin architecture for:
- Custom protocols
- Device types
- Controllers
- Monitoring collectors
- Export formats

### Snapshot System
Complete state capture including:
- Device configurations
- Routing tables
- Flow tables
- ARP/neighbor tables
- Wireless associations
- Container states
- Traffic counters

## Project Structure

```
caduceus-flux/
├── backend/
│   ├── services/          # 12 microservices
│   ├── shared/            # Common code, models, schemas
│   ├── proto/             # gRPC protocol definitions
│   └── migrations/        # Database migrations
├── emulation-container/   # Unified emulation engine
│   ├── grpc_agent/        # gRPC server implementation
│   ├── protocols/         # Protocol implementations
│   └── Dockerfile
├── controllers/           # SDN controller containers
│   ├── osken/
│   ├── ryu/
│   ├── opendaylight/
│   └── onos/
├── frontend/              # React web application
│   └── src/
├── infrastructure/        # Supporting services
│   ├── nginx/
│   ├── prometheus/
│   ├── grafana/
│   └── databases/
├── examples/              # Example topologies
├── tests/                 # Test suites
├── docs/                  # Documentation
└── docker-compose.yml     # Orchestration
```

## API Documentation

Once services are running, access API documentation:
- Unified docs index (recommended): http://localhost/api/docs
- Per-service Swagger: http://localhost/api/docs/{service}
- Per-service OpenAPI JSON: http://localhost/api/openapi/{service}

Notes:
- Swagger/ReDoc are served by the MCP server through the Nginx gateway at `/api/*`.
- If you run a microservice directly (bypassing Nginx), its built-in docs are still available at `http://localhost:PORT/docs`.

## P4 Programs (BMv2)

- Upload & compile a `.p4` program: `POST /api/p4/programs/upload` (multipart form file).
- List compiled programs: `GET /api/p4/programs`.
- Assign a program to a `p4switch` node by setting node properties:
  - `p4_program_id` (recommended), or `device_config_path`/`p4info_path` to explicit artifact paths.

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# E2E tests
pytest tests/e2e
```

### Adding Plugins

```python
# Example: Custom routing protocol plugin
from caduceus_flux.shared.plugins import ProtocolPlugin

class MyProtocol(ProtocolPlugin):
    name = "my-protocol"
    version = "1.0"

    def configure(self, device, config):
        # Implementation
        pass

    def enable(self, device):
        # Implementation
        pass
```

## Monitoring

Access Grafana dashboards at http://localhost:3001

Default credentials: admin/admin

Pre-configured dashboards:
- Network Topology Overview
- Device Metrics
- Protocol Statistics
- Flow Table Analytics
- Wireless Performance

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md)

## License

Apache 2.0 - See [LICENSE](LICENSE)

## Support

- Documentation: https://docs.caduceus-flux.io
- Issues: https://github.com/your-org/caduceus-flux/issues
- Discussions: https://github.com/your-org/caduceus-flux/discussions

## Acknowledgments

Built on top of:
- Mininet, Mininet-WiFi, Containernet
- Open vSwitch, FRRouting, BIRD
- BMv2, P4Runtime
- OS-Ken, Ryu, OpenDaylight, ONOS
