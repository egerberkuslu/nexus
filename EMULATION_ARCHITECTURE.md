# Caduceus-Flux Emulation Architecture

## System Overview

The Caduceus-Flux emulation system consists of two layers:

### 1. Emulation Layer (Standalone)
- **Technology**: Mininet + Mininet-WiFi
- **Deployment**: Native systemd service on host
- **Communication**: gRPC (port 50051)
- **Runtime**: Direct kernel access

### 2. Orchestration Layer (Docker)
- **Technology**: Docker Compose microservices
- **Deployment**: Container-based services
- **Communication**: REST API, gRPC to emulation, RabbitMQ message bus
- **Components**: Topology, Orchestrator, Device Manager, Monitoring, etc.

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Caduceus-Flux Deployment                          │
└────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │      Web Frontend (React)       │
                    │  http://localhost:3000          │
                    └────────────┬────────────────────┘
                                 │ REST/WebSocket
                    ┌────────────▼────────────────────┐
                    │    API Gateway (nginx:80)       │
                    └────────────┬────────────────────┘
                                 │ REST API
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  MCP Server      │  │  WebShell Svc    │  │  Device Mgr Svc  │
│  :8012           │  │  :8007           │  │  :8004           │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         │        ┌────────────┼─────────────────────┤
         │        │            │                     │
         │        ▼            ▼                     ▼
         │   ┌─────────────────────────────────────────────────┐
         │   │      Emulation Container (Standalone)           │
         │   │      ─────────────────────────────             │
         │   │  Systemd Service: caduceus-emulation            │
         │   │  gRPC Server: localhost:50051                   │
         │   │                                                 │
         │   │  ┌──────────────────────────────────────┐      │
         │   │  │  Mininet + Mininet-WiFi             │      │
         │   │  │  ├─ Hosts & Switches                │      │
         │   │  │  ├─ Wireless APs & Stations         │      │
         │   │  │  └─ Network Links & Emulation       │      │
         │   │  └──────────────────────────────────────┘      │
         │   │                                                 │
         │   │  ┌──────────────────────────────────────┐      │
         │   │  │  Routing Services                    │      │
         │   │  ├─ Open vSwitch (OVS)                 │      │
         │   │  ├─ FRRouting (BGP, OSPF, etc.)       │      │
         │   │  └─ BIRD (Routing daemon)             │      │
         │   │  └──────────────────────────────────────┘      │
         │   │                                                 │
         │   │  ┌──────────────────────────────────────┐      │
         │   │  │  Management & Monitoring             │      │
         │   │  ├─ Device State Tracking              │      │
         │   │  ├─ Metrics Collection                 │      │
         │   │  └─ Snapshot Management                │      │
         │   │  └──────────────────────────────────────┘      │
         │   │                                                 │
         │   └─────────────────────────────────────────────────┘
         │
         │ gRPC (localhost:50051)
         │
    ┌────▼──────────────────────────────────────────────┐
    │         Orchestration Services (Docker)           │
    ├──────────────────────────────────────────────────┤
    │                                                   │
    │  ┌────────────────────────────────────────────┐ │
    │  │  Topology Service (:8001)                  │ │
    │  │  - Store topology definitions              │ │
    │  │  - Manage topology versions                │ │
    │  └────────────────────────────────────────────┘ │
    │                                                   │
    │  ┌────────────────────────────────────────────┐ │
    │  │  Orchestrator Service (:8002)              │ │
    │  │  - Deploy topologies                       │ │
    │  │  - Manage emulation lifecycle              │ │
    │  └────────────────────────────────────────────┘ │
    │                                                   │
    │  ┌────────────────────────────────────────────┐ │
    │  │  Protocol Manager Service (:8003)          │ │
    │  │  - Configure routing protocols             │ │
    │  │  - Manage protocol parameters              │ │
    │  └────────────────────────────────────────────┘ │
    │                                                   │
    │  ┌────────────────────────────────────────────┐ │
    │  │  Metrics Collector Service (:8013)         │ │
    │  │  - Collect emulation metrics               │ │
    │  │  - Stream to InfluxDB/Kafka                │ │
    │  └────────────────────────────────────────────┘ │
    │                                                   │
    │  ┌────────────────────────────────────────────┐ │
    │  │  Infrastructure Services                   │ │
    │  │  - PostgreSQL, MongoDB, Redis              │ │
    │  │  - RabbitMQ, Kafka, InfluxDB               │ │
    │  │  - Prometheus, Grafana                     │ │
    │  └────────────────────────────────────────────┘ │
    │                                                   │
    └──────────────────────────────────────────────────┘
```

## Communication Flows

### 1. Topology Deployment Flow

```
User/Web UI
    ↓ (REST API)
API Gateway
    ↓ (POST /topologies)
MCP Server
    ↓ (gRPC CreateTopology)
Orchestrator Service
    ↓ (gRPC StartEmulation)
Emulation Container
    ↓ (Mininet API)
Physical/Virtual Network
```

### 2. Device Management Flow

```
Web UI / API
    ↓
Device Manager Service
    ↓ (gRPC AddHost/AddSwitch)
Emulation Container
    ↓ (Mininet API)
Mininet Topology
    ↓
Create host/switch objects
```

### 3. Metrics Collection Flow

```
Emulation Container
    ↓ (gRPC StreamMetrics)
Metrics Collector Service
    ↓ (Kafka Producer)
Kafka Broker
    ↓ (Subscribe)
InfluxDB / Prometheus
    ↓ (Query)
Grafana Dashboards
```

## Technology Stack

### Emulation Engine
| Component | Version | Purpose |
|-----------|---------|---------|
| Mininet | 2.3.0 | Core network emulation |
| Mininet-WiFi | Latest | Wireless/WiFi support |
| Open vSwitch | Latest | Software switching |
| FRRouting | Latest | Routing protocols (BGP, OSPF, etc.) |
| BIRD | Latest | BGP routing daemon |
| Python 3 | 3.10+ | gRPC server runtime |

### Orchestration Stack
| Component | Version | Purpose |
|-----------|---------|---------|
| Docker | Latest | Container runtime |
| Docker Compose | Latest | Service orchestration |
| Python | 3.10+ | Service implementation |
| PostgreSQL | 15 | Topology database |
| MongoDB | 7 | Snapshot storage |
| Redis | 7 | Caching layer |

### Message Queue & Streaming
| Component | Version | Purpose |
|-----------|---------|---------|
| RabbitMQ | 3.12 | Service messaging |
| Kafka | 7.5 | Metrics streaming |
| Schema Registry | 7.5 | Data schema management |

### Monitoring & Observability
| Component | Version | Purpose |
|-----------|---------|---------|
| Prometheus | 2.48 | Metrics collection |
| InfluxDB | 2.7 | Time-series database |
| Grafana | 10.2 | Visualization |

### Service Discovery & Configuration
| Component | Version | Purpose |
|-----------|---------|---------|
| Consul | Latest | Service discovery |
| Nginx | 1.25 | Reverse proxy |

## Data Flow Paths

### 1. Topology Persistence

```
Web UI / API
    ↓ (Create topology)
PostgreSQL (Topology Service)
    ↓ (Store definition)
Topology DB
```

### 2. Snapshot Management

```
Emulation State
    ↓ (CaptureState gRPC)
Emulation Container
    ↓ (Serialize state)
MongoDB (Snapshot Service)
    ↓ (Store snapshot)
File System (/var/lib/caduceus-flux/snapshots)
```

### 3. Command Execution

```
Web Shell UI
    ↓ (WebSocket)
WebShell Service
    ↓ (ExecuteCommand gRPC)
Emulation Container
    ↓ (Execute in mininet node)
Device (Host/Router/etc.)
    ↓ (Command output)
WebShell Service
    ↓ (Return result)
Web UI
```

## API Interfaces

### gRPC Interface (Emulation Container)

```protobuf
service EmulationService {
  // Lifecycle
  rpc StartEmulation(StartEmulationRequest) returns (EmulationResponse);
  rpc StopEmulation(StopEmulationRequest) returns (EmulationResponse);
  rpc PauseEmulation(PauseEmulationRequest) returns (EmulationResponse);
  rpc ResumeEmulation(ResumeEmulationRequest) returns (EmulationResponse);

  // Devices
  rpc AddHost(AddHostRequest) returns (DeviceResponse);
  rpc AddSwitch(AddSwitchRequest) returns (DeviceResponse);
  rpc AddRouter(AddRouterRequest) returns (DeviceResponse);
  rpc AddAccessPoint(AddAccessPointRequest) returns (DeviceResponse);
  rpc RemoveDevice(RemoveDeviceRequest) returns (DeviceResponse);
  rpc ListDevices(ListDevicesRequest) returns (ListDevicesResponse);

  // Links
  rpc AddLink(AddLinkRequest) returns (LinkResponse);
  rpc RemoveLink(RemoveLinkRequest) returns (LinkResponse);
  rpc UpdateLink(UpdateLinkRequest) returns (LinkResponse);
  rpc ListLinks(ListLinksRequest) returns (ListLinksResponse);

  // Commands
  rpc ExecuteCommand(ExecuteCommandRequest) returns (ExecuteCommandResponse);
  rpc ExecuteCommandStream(stream ExecuteCommandRequest) returns (stream ExecuteCommandResponse);

  // Monitoring
  rpc GetMetrics(GetMetricsRequest) returns (GetMetricsResponse);
  rpc StreamMetrics(StreamMetricsRequest) returns (stream MetricsUpdate);

  // State
  rpc CaptureState(CaptureStateRequest) returns (CaptureStateResponse);
  rpc RestoreState(RestoreStateRequest) returns (RestoreStateResponse);
}
```

### REST API (MCP Server)

```
POST   /api/topologies                    - Create topology
GET    /api/topologies                    - List topologies
GET    /api/topologies/{id}               - Get topology
PUT    /api/topologies/{id}               - Update topology
DELETE /api/topologies/{id}               - Delete topology

POST   /api/emulations                    - Start emulation
GET    /api/emulations                    - List emulations
GET    /api/emulations/{id}               - Get emulation status
PUT    /api/emulations/{id}/pause         - Pause emulation
PUT    /api/emulations/{id}/resume        - Resume emulation
DELETE /api/emulations/{id}               - Stop emulation

POST   /api/devices                       - Add device
GET    /api/devices                       - List devices
POST   /api/devices/{name}/commands       - Execute command

POST   /api/snapshots                     - Create snapshot
GET    /api/snapshots                     - List snapshots
POST   /api/snapshots/{id}/restore        - Restore snapshot

GET    /api/metrics                       - Get metrics
WS     /api/metrics/stream                - Stream metrics
```

## Deployment Modes

### Development (All on Single Host)
```
Host Machine:
├─ Emulation Container (systemd service)
├─ Docker Compose (microservices)
└─ Frontend (React)
```

### Production (Distributed)
```
Emulation Host:
└─ Emulation Container (systemd service)

Orchestration Host:
└─ Docker Compose (microservices)

Frontend Host:
└─ Frontend (Nginx/React)
```

## Security Architecture

### Network Isolation
- Docker services on internal network (caduceus-network)
- Emulation container on host network
- Nginx reverse proxy for external access
- Firewall rules for port access

### Authentication & Authorization
- JWT tokens for REST API (MCP Server)
- Service-to-service communication (RabbitMQ, Kafka)
- Database authentication (PostgreSQL, MongoDB)

### Data Protection
- Encrypted passwords in configurations
- Snapshot data in secured directories
- Container volume permissions

## Scaling Considerations

### Single Emulation Instance (Current)
- Single gRPC server on port 50051
- Services connect directly
- Suitable for: Development, testing, small deployments

### Multiple Emulation Instances
- Multiple systemd services (50051, 50052, 50053, ...)
- Service routing to appropriate instance
- Suitable for: Parallel experiments, large deployments

### Load Balancing
- Nginx load balancer for REST API
- Service discovery via Consul
- Suitable for: Production deployments

## Monitoring and Observability

### Logs
- Systemd journal: `journalctl -u caduceus-emulation`
- Application logs: `/var/lib/caduceus-flux/logs/`
- Container logs: `docker logs <container>`

### Metrics
- Prometheus scrapes service metrics
- InfluxDB stores timeseries data
- Grafana visualizes metrics
- Kafka topic: `caduceus-flux.metrics.raw`

### Health Checks
- Systemd service status monitoring
- gRPC service health check (port 50051)
- HTTP health endpoints on microservices
- Consul service health tracking

## Performance Characteristics

### Emulation Capacity
- ~100 nodes per emulation
- ~1000 links per emulation
- CPU bound by host system
- Memory: ~100MB per node

### API Performance
- gRPC: <10ms latency
- REST: 10-50ms latency (including serialization)
- Metrics streaming: <100ms update interval

### Throughput
- Command execution: 100-1000 commands/sec
- Metrics collection: 1000s metrics/sec
- Topology changes: Near real-time

## Failure Handling

### Emulation Container Failure
- Systemd auto-restart on failure
- Snapshot restoration on recovery
- Service reconnection with exponential backoff

### Microservice Failure
- Docker restart policy (unless-stopped)
- RabbitMQ message queuing for resilience
- Service discovery deregistration

### Network Partition
- Graceful degradation
- Message buffering in queues
- Client reconnection logic

## Backup and Disaster Recovery

### Data to Backup
1. Snapshots: `/var/lib/caduceus-flux/snapshots/`
2. Configurations: `/etc/caduceus-flux/`
3. Databases: PostgreSQL, MongoDB volumes
4. Custom topologies: Git repository

### Recovery Process
1. Restore configuration files
2. Restore database volumes
3. Restart services
4. Restore snapshots
5. Verify connectivity

## Future Enhancements

### Planned Improvements
- [ ] Distributed emulation (multiple hosts)
- [ ] Kubernetes support
- [ ] Advanced visualization
- [ ] Real-time packet capture integration
- [ ] Machine learning-based anomaly detection
- [ ] Multi-domain federation

### Experimental Features
- [ ] P4 programmable switches
- [ ] 5G network simulation
- [ ] Cloud integration (AWS/GCP)

---

For more information:
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migration from Docker
- [emulation-container/DEPLOYMENT.md](emulation-container/DEPLOYMENT.md) - Deployment details
- [emulation-container/QUICK_START.md](emulation-container/QUICK_START.md) - Quick start guide
