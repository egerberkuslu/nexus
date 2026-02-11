# Caduceus-Flux: Complete Software Framework Manual & Developer Guide

**Version:** 2.0
**Date:** 2026-01-28
**Type:** Comprehensive Documentation & User Manual

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Microservices Catalog](#3-microservices-catalog)
4. [Isolated Infrastructure Deep Dive](#4-isolated-infrastructure-deep-dive)
5. [Protocol Hot-Swap System](#5-protocol-hot-swap-system)
6. [Streaming Analytics Pipeline](#6-streaming-analytics-pipeline)
7. [AI/LLM Control Plane](#7-ai-llm-control-plane)
8. [MANO & NFV Integration](#8-mano--nfv-integration)
9. [Test Infrastructure](#9-test-infrastructure)
10. [Configuration Reference](#10-configuration-reference)
11. [API Reference](#11-api-reference)
12. [Deployment Guide](#12-deployment-guide)
13. [Troubleshooting](#13-troubleshooting)
14. [Best Practices](#14-best-practices)
15. [Code Evidence Index](#15-code-evidence-index)

---

## 1. Executive Summary

### 1.1 What is Caduceus-Flux?

**Caduceus-Flux** is a production-grade, microservices-based network emulation platform that extends Mininet, Containernet, and Mininet-WiFi with enterprise features including:

- **21 independently deployable microservices**
- **Per-topology isolated infrastructure** (InfluxDB, Grafana, Kafka, RabbitMQ, Consul)
- **Runtime protocol hot-swapping** without emulation restart
- **Streaming metrics pipeline** with real-time anomaly detection
- **AI/LLM-driven control** through secure MCP gateway
- **NFV MANO integration** with ETSI OSM support

### 1.2 Target Users

| User Type | Primary Use Cases |
|-----------|-------------------|
| **Network Researchers** | Protocol evaluation, SDN experiments, security research |
| **Network Engineers** | Pre-deployment testing, failure simulation, capacity planning |
| **Students** | Learning networking concepts, hands-on protocol behavior |
| **Data Scientists** | Traffic analysis, ML model training, anomaly detection |
| **SDN Developers** | Controller testing, P4 program development |

### 1.3 Key Innovations

1. **Per-Topology Isolation**: Each topology gets dedicated infrastructure containers (InfluxDB, Grafana, Kafka, etc.) with dynamic port allocation (33000-40999 range)
2. **Runtime Hot-Swap**: Change routing protocols (OSPF↔BGP) without restart, preserving state
3. **Streaming Analytics**: Kafka→Flink→InfluxDB pipeline with 3 anomaly detection algorithms
4. **AI Control**: Multi-provider LLM gateway (OpenAI, Anthropic, Gemini, Ollama) with security guardrails
5. **MANO Integration**: Both local MANO and ETSI OSM support with per-topology VIM emulator

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Frontend (React)                        │
│                         Port 3000                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                    Nginx API Gateway                           │
│                         Port 80                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼────────────────────────────────────┐
│                    MCP Server (8012)                           │
│                 (API Gateway / Service Discovery)              │
└───┬───────────┬───────────┬───────────┬───────────┬────────────┘
    │           │           │           │           │
┌───▼────┐ ┌──▼─────┐ ┌──▼─────┐ ┌──▼─────┐ ┌──▼─────┐
│Topology│ │Orchestr│ │Protocol│ │Device  │ │Snapshot│
│ :8001  │ │ :8002  │ │Manager │ │Manager │ │ :8006  │
│        │ │        │ │ :8003  │ │ :8004  │ │        │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
┌───▼────┐ ┌──▼─────┐ ┌──▼─────┐ ┌──▼─────┐ ┌──▼─────┐
│Monitor │ │AI Gate │ │Decision│ │MCP Hub │ │MANO    │
│ :8011  │ │ :8014  │ │Engine  │ │ :8018  │ │ :8015  │
│        │ │        │ │ :8017  │ │        │ │        │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Shared Infrastructure                              │
│  PostgreSQL │ MongoDB │ Redis │ InfluxDB │ Prometheus         │
│  RabbitMQ │ Kafka │ Zookeeper │ Schema Registry              │
│  Flink │ Spark │ HDFS │ Hive │ JupyterLab                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│         Per-Topology Isolated Infrastructure (Optional)         │
│  InfluxDB (36000-36999) │ Grafana (33000-33999)              │
│  Consul (35000-35999) │ RabbitMQ (37000-37999)              │
│  Kafka+Zookeeper │ Portainer (39000-40999)                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 Emulation Containers (Per Topology)             │
│           gRPC :50051+ (Mininet/Containernet/WiFi)             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Design Patterns

| Pattern | Implementation | Benefit |
|---------|----------------|---------|
| **API Gateway** | Nginx + MCP Server | Unified entry point, service aggregation |
| **Service Discovery** | Consul | Dynamic registration, health checks |
| **Publish-Subscribe** | RabbitMQ topic exchange | Loose coupling, event-driven |
| **CQRS** | Separate read/write models | Optimized queries |
| **Plugin Architecture** | Protocol plugin base class | Extensible protocol implementations |
| **Strategy Pattern** | Algorithm selection in Decision Engine | Runtime-swappable ML models |
| **Observer Pattern** | RabbitMQ event subscribers | Reactive updates |
| **Repository Pattern** | SQLAlchemy models | Data access abstraction |
| **Factory Pattern** | Container creation in Orchestrator | Dynamic instantiation |
| **Proxy Pattern** | MCP Tool Hub | Controlled external access |
| **Circuit Breaker** | Health checks, retries | Fault tolerance |
| **Saga Pattern** | Multi-service orchestration | Distributed transactions |

### 2.3 Technology Stack

**Backend:**
- Python 3.11, FastAPI, asyncio, gRPC, SQLAlchemy
- Protocol Buffers for gRPC definitions

**Frontend:**
- React 18, TypeScript, Vite, TailwindCSS
- WebSocket for real-time updates

**Emulation:**
- Mininet 2.3+, Containernet, Mininet-WiFi
- FRR/BIRD for routing protocols
- Open vSwitch for SDN

**Databases:**
- PostgreSQL 15 (pgvector extension)
- MongoDB 7 (binary snapshots)
- Redis 7 (caching, WebShell state)

**Time-Series:**
- InfluxDB 2.7 (metrics storage)
- Prometheus 2.48 (scraping)

**Streaming:**
- Kafka 7.5.0 (event streaming)
- Flink 1.18.1 (stream processing)
- Spark 3.5.1 (batch analytics)

**Big Data:**
- Hadoop 3.2.1 (HDFS)
- Hive 3.1.3 (SQL on Hadoop)
- JupyterLab (data science)

**Container:**
- Docker 24.0+, Docker Compose 2.20+

---

## 3. Microservices Catalog

### 3.1 Topology Service (Port 8001)

**File:** `backend/services/topology/topology_app/app.py` (1-1816 lines)

#### Purpose
Central repository for network topology metadata, providing CRUD operations, versioning, and JSON I/O.

#### Key Responsibilities
- Topology CRUD operations
- Node and link management
- P4 program draft storage
- Real-time WebSocket updates
- Topology versioning
- Import/Export coordination

#### Data Model

```python
class Topology:
    id: str (UUID)
    project_id: str (FK to projects)
    name: str
    description: str
    version: int (auto-increment)
    is_active: bool
    emulation_status: Enum[stopped, starting, running, stopping, error]
    topology_metadata: JSONB
    created_at: datetime
    updated_at: datetime

class Node:
    id: str (UUID)
    topology_id: str (FK)
    name: str
    device_type: Enum[host, switch, router, ap, station, container, p4switch]
    x: float (canvas position)
    y: float
    properties: JSONB

class Link:
    id: str (UUID)
    topology_id: str (FK)
    source_node_id: str (FK)
    target_node_id: str (FK)
    source_port: str
    target_port: str
    bandwidth: float (Mbps)
    delay: float (ms)
    loss: float (%)
    max_queue_size: int
    status: Enum[active, inactive]
```

#### API Endpoints

**Project Management:**
- `POST /api/projects` - Create project
- `GET /api/projects` - List projects (paginated)
- `GET /api/projects/{id}` - Get project details
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project (cascades to topologies)

**Topology CRUD:**
- `POST /api/topologies` - Create topology
- `GET /api/topologies` - List topologies (includes container status)
- `GET /api/topologies/{id}` - Get full topology (nodes, links, controllers)
- `PUT /api/topologies/{id}` - Update topology metadata
- `DELETE /api/topologies/{id}` - Delete topology
- `POST /api/topologies/{id}/apply` - Apply staged changes atomically
- `POST /api/topologies/{id}/stop` - Stop running emulation

**Node Operations:**
- `POST /api/topologies/{id}/nodes` - Add device node
- `GET /api/topologies/{id}/nodes` - List all nodes
- `GET /api/topologies/{id}/nodes/{nid}` - Get node details
- `PUT /api/topologies/{id}/nodes/{nid}` - Update node config
- `DELETE /api/topologies/{id}/nodes/{nid}` - Delete node

**Link Operations:**
- `POST /api/topologies/{id}/links` - Add link
- `GET /api/topologies/{id}/links` - List all links
- `PUT /api/topologies/{id}/links/{lid}` - Update link parameters
- `DELETE /api/topologies/{id}/links/{lid}` - Delete link

**P4 Programs:**
- `GET /api/topologies/{id}/p4/programs` - List P4 drafts
- `POST /api/topologies/{id}/p4/programs` - Create/update P4 draft
- `DELETE /api/topologies/{id}/p4/programs/{did}` - Delete P4 draft

#### Configuration

Environment variables:
```bash
SERVICE_NAME=topology-service
SERVICE_PORT=8001
POSTGRES_HOST=postgres
POSTGRES_USER=caduceus
POSTGRES_PASSWORD=changeme_postgres_password
POSTGRES_DB=caduceus_flux
RABBITMQ_HOST=rabbitmq
RABBITMQ_USER=caduceus
RABBITMQ_PASSWORD=changeme_rabbitmq_password
RABBITMQ_VHOST=/caduceus-flux
CONSUL_HOST=consul
ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8002
```

#### RabbitMQ Events Published

- `project.created`
- `project.updated`
- `project.deleted`
- `topology.created`
- `topology.updated`
- `topology.deleted`
- `topology.node.added`
- `topology.node.updated`
- `topology.node.deleted`
- `topology.link.added`
- `topology.link.updated`
- `topology.link.deleted`
- `network.config.created`
- `emulation.stopped`

#### Usage Example

```bash
# Create a new topology
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-123",
    "name": "My SDN Topology",
    "description": "OpenFlow topology with 4 switches"
  }'

# Add a host node
curl -X POST http://localhost:8001/api/topologies/{topology_id}/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "h1",
    "device_type": "host",
    "x": 100,
    "y": 200,
    "properties": {
      "ip": "10.0.0.1/24",
      "mac": "00:00:00:00:00:01"
    }
  }'

# Add a link
curl -X POST http://localhost:8001/api/topologies/{topology_id}/links \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "node-1",
    "target_node_id": "node-2",
    "bandwidth": 100,
    "delay": 10,
    "loss": 0.1
  }'
```

---

### 3.2 Orchestrator Service (Port 8002)

**File:** `backend/services/orchestrator/orchestrator_app/app.py` (5000+ lines)

#### Purpose
Manages emulation container lifecycle, coordinates infrastructure provisioning, and executes algorithm-based experiments.

#### Key Responsibilities
- Emulation container lifecycle (create, start, stop, destroy)
- Per-topology isolated infrastructure provisioning
- gRPC client management for emulation containers
- Algorithm SDK execution (WSN protocols: LEACH, PEGASIS, SEP, TEEN)
- Test suite execution (connectivity, SDN, MANO)
- PCAP capture management
- InfluxDB auth repair for isolated instances

#### Architecture

```
Orchestrator
├── Container Management
│   ├── Docker Engine API client
│   ├── Image management (pull, build)
│   ├── Container lifecycle (create, start, stop, remove)
│   └── Network management (create, connect, disconnect)
├── gRPC Client Manager
│   ├── Connection pooling
│   ├── Auto-reconnection
│   ├── Retry logic with exponential backoff
│   └── Health checking
├── Isolated Infrastructure Manager
│   ├── Dynamic port allocation (33000-40999)
│   ├── Credential generation and storage (Consul)
│   ├── Service deployment (InfluxDB, Grafana, etc.)
│   └── Auth repair mechanisms
├── Test Suite Runner
│   ├── Connectivity tests
│   ├── SDN smoke tests
│   ├── MANO smoke tests
│   └── Metrics integration (InfluxDB line protocol)
└── Algorithm SDK
    ├── WSN protocol implementations
    ├── Topology context building
    └── Result persistence
```

#### Configuration

```bash
SERVICE_NAME=orchestrator-service
SERVICE_PORT=8002
AUTO_APPLY_NETWORK_CONFIG=true
STOP_EMULATIONS_ON_SHUTDOWN=false
EMULATION_GRPC_HOST=localhost
EMULATION_GRPC_PORT=50051
P4_PROGRAMS_VOLUME=caduceus-p4-programs
TOPOLOGY_INFRA_MODE=shared|isolated  # KEY SETTING
MONITORING_URL=http://monitoring-service:8011
GRAFANA_INTERNAL_URL=http://grafana:3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=changeme_grafana_password
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=changeme_influxdb_token
INFLUXDB_ORG=caduceus-flux
PCAP_STORAGE_ROOT=/var/lib/caduceus/pcap
```

#### API Endpoints

**Emulation Control:**
- `POST /api/emulations` - Start emulation
- `GET /api/emulations` - List active emulations
- `GET /api/emulations/{id}` - Get emulation status
- `POST /api/emulations/{id}/stop` - Stop emulation
- `POST /api/emulations/{id}/command` - Execute command in device

**Infrastructure Management:**
- `POST /api/topologies/{id}/infrastructure/ensure` - Provision isolated infra
- `POST /api/topologies/{id}/infrastructure/stop` - Stop isolated infra
- `POST /api/topologies/{id}/infrastructure/restart` - Restart isolated infra
- `POST /api/topologies/{id}/infrastructure/purge` - Remove all infrastructure

**Test Execution:**
- `POST /api/topologies/{id}/tests/run` - Start test suite
- `GET /api/topologies/{id}/tests/{run_id}` - Get test status
- `POST /api/topologies/{id}/tests/{run_id}/stop` - Cancel test run

**Diagnostics:**
- `POST /api/topologies/{id}/influx/diagnostics/query` - Query isolated InfluxDB
- `GET /api/topologies/{id}/influx/diagnostics/features` - List available features

#### Isolated Infrastructure Provisioning

**Key Function:** `ensure_topology_isolated_infra(topology_id: str)` (Line 4196)

**Algorithm:**
1. Create topology-specific Docker network (`caduceus-topo-<short_id>`)
2. Check existing infrastructure in Consul KV
3. Allocate host ports from designated ranges
4. Generate or retrieve credentials
5. Create Docker volumes for each service
6. Deploy containers with version labels
7. Connect containers to both main network and topology network
8. Store infrastructure metadata in Consul
9. Return infrastructure details (URLs, credentials, ports)

**Container Names:**
- InfluxDB: `caduceus-topo-<short_id>-influxdb`
- Grafana: `caduceus-topo-<short_id>-grafana`
- Consul: `caduceus-topo-<short_id>-consul`
- RabbitMQ: `caduceus-topo-<short_id>-rabbitmq`
- Kafka: `caduceus-topo-<short_id>-kafka`
- Zookeeper: `caduceus-topo-<short_id>-zookeeper`
- Portainer: `caduceus-topo-<short_id>-portainer`

**Port Ranges:**
- Grafana: 33000-33999
- Prometheus: 34000-34999
- Consul: 35000-35999
- InfluxDB: 36000-36999
- RabbitMQ: 37000-37999
- Kafka-UI: 38000-38999
- Portainer: 39000-39999
- Portainer HTTP: 40000-40999

**Credential Storage (Consul KV):**
- `caduceus/topologies/{topology_id}/isolated_influx_token`
- `caduceus/topologies/{topology_id}/isolated_influx_org`
- `caduceus/topologies/{topology_id}/isolated_influx_bucket`
- `caduceus/topologies/{topology_id}/isolated_influx_admin_user`
- `caduceus/topologies/{topology_id}/isolated_influx_admin_password`
- `caduceus/topologies/{topology_id}/isolated_grafana_admin_user`
- `caduceus/topologies/{topology_id}/isolated_grafana_admin_password`
- `caduceus/topologies/{topology_id}/isolated_rabbitmq_user`
- `caduceus/topologies/{topology_id}/isolated_rabbitmq_password`
- `caduceus/topologies/{topology_id}/isolated_rabbitmq_vhost`
- `caduceus/topologies/{topology_id}/isolated_portainer_admin_user`
- `caduceus/topologies/{topology_id}/isolated_portainer_admin_password`

**Evidence:** orchestrator/app.py:4196-4595

#### InfluxDB Auth Repair Mechanism

**Function:** `repair_topology_isolated_influx_auth(topology_id: str)` (Line 291)

**Problem:** When InfluxDB volumes already exist from previous runs, Docker initialization environment variables (`DOCKER_INFLUXDB_INIT_*`) are ignored, causing credential mismatches.

**Solution:**
1. Stop topology's InfluxDB container (unlock boltdb)
2. Launch temporary Alpine container with influxd recovery tools
3. Mount InfluxDB volume in read-write mode
4. Execute recovery commands:
```bash
influxd recovery org create --bolt-path /var/lib/influxdb2/influxd.bolt --org <org>
influxd recovery user create --bolt-path <bolt> --username <user> --password <pass>
influxd recovery user update --bolt-path <bolt> --username <user> --password <pass>
influxd recovery auth create-operator --bolt-path <bolt> --org <org> --username <user>
```
5. Parse operator token from output (second-to-last tab-delimited column)
6. Store new token in Consul KV
7. Restart InfluxDB container
8. Re-run `ensure_topology_isolated_infra()` to update Grafana datasource

**Evidence:** orchestrator/app.py:291-385

#### Test Suites

**Connectivity Test:**
- Discovers all host-like devices (hosts, routers, stations, containers)
- Executes ping tests between all pairs
- Captures packet loss percentage and RTT statistics
- Writes results to isolated InfluxDB:
```
caduceus_test_ping,run_id=<id>,src=<src>,dst=<dst>,topology_id=<id> success=1,loss_pct=0.0,rtt_avg_ms=12.5 <timestamp_ns>
```

**SDN Smoke Test:**
- Selects a reachable host pair
- Identifies switches with configured controllers
- For each switch:
  - Sets fail-mode to `secure`
  - Deletes all flows
  - Removes controller
  - Verifies ping fails (dataplane enforced by controller)
  - Restores controller
  - Waits for flow repopulation
  - Verifies ping recovers
- Proves OpenFlow control plane is functional

**MANO Smoke Test:**
- Creates local NS (Network Service) instance
- Instantiates Docker-based VNF (default: `alpine:3.19`)
- Verifies VNF appears in device list (gRPC ListDevices)
- Executes command in VNF container
- Terminates VNF and verifies removal

**Evidence:** orchestrator/app.py:445-999

#### Usage Examples

**Start Emulation:**
```bash
curl -X POST http://localhost:8002/api/emulations \
  -H "Content-Type: application/json" \
  -d '{
    "topology_id": "topo-abc123",
    "enable_metrics": true,
    "start_isolated_infra": true
  }'
```

**Provision Isolated Infrastructure:**
```bash
curl -X POST http://localhost:8002/api/topologies/topo-abc123/infrastructure/ensure
```

**Run Test Suite:**
```bash
curl -X POST http://localhost:8002/api/topologies/topo-abc123/tests/run \
  -H "Content-Type: application/json" \
  -d '{
    "suite": "connectivity|sdn_smoke|mano_local_smoke",
    "params": {}
  }'
```

**Execute Command:**
```bash
curl -X POST http://localhost:8002/api/emulations/emu-xyz/command \
  -H "Content-Type: application/json" \
  -d '{
    "device": "h1",
    "command": "ping -c 3 10.0.0.2"
  }'
```

---

### 3.3 Protocol Manager Service (Port 8003)

**File:** `backend/services/protocol_manager/protocol_manager_app/app.py` (Line 355-453 for hot-swap)

#### Purpose
Plugin-based protocol management system enabling runtime protocol transitions without emulation restart.

#### Key Features
- Plugin architecture for routing protocols (BGP, OSPF, IS-IS, RIP, Static)
- Hot-swap capability with state preservation
- OpenFlow version selection per switch
- Wireless protocol configuration (802.11 a/b/g/n/ac/ax)
- Security mode management (Open, WPA, WPA2, WPA3)

#### Plugin Base Class

```python
class ProtocolPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Protocol identifier (e.g., 'bgp', 'ospf')"""
        pass

    @property
    @abstractmethod
    def protocol_type(self) -> ProtocolType:
        """ROUTING, OPENFLOW, WIRELESS, SECURITY, MANAGEMENT"""
        pass

    @property
    @abstractmethod
    def supported_devices(self) -> List[str]:
        """['router', 'switch', 'ap', 'station']"""
        pass

    @abstractmethod
    async def configure(self, device: str, config: dict) -> dict:
        """Apply configuration to device"""
        pass

    @abstractmethod
    async def enable(self, device: str) -> dict:
        """Enable protocol on device"""
        pass

    @abstractmethod
    async def disable(self, device: str) -> dict:
        """Disable protocol on device"""
        pass

    @abstractmethod
    async def switch_from(self, device: str, to_protocol: str, preserve_config: bool) -> dict:
        """Capture state before switching away from this protocol"""
        pass

    @abstractmethod
    async def switch_to(self, device: str, from_protocol: str, preserved_state: dict) -> dict:
        """Apply state after switching to this protocol"""
        pass

    @abstractmethod
    async def get_status(self, device: str) -> dict:
        """Get current protocol status"""
        pass
```

**Evidence:** shared/plugins/protocol_plugin.py:29-295

#### Hot-Swap Algorithm

```
INPUT: device_name, from_protocol, to_protocol, preserve_config=True
OUTPUT: success/failure, preserved_state

1. Publish RabbitMQ event: protocol.switching.started
2. Load plugins: from_plugin = get_plugin(from_protocol)
                 to_plugin = get_plugin(to_protocol)

3. IF preserve_config:
     preserved_state = from_plugin.switch_from(device, to_protocol, True)
     preserved_state.routing_table = execute_command(device, "ip route show")
     preserved_state.neighbors = parse_neighbors(device)

4. Disable current protocol:
     result = from_plugin.disable(device)
     IF result.failed:
       Publish protocol.switching.failed
       RETURN error

5. Configure new protocol:
     default_config = to_plugin.get_default_config()
     IF preserved_state:
       merged_config = merge(default_config, preserved_state)
     ELSE:
       merged_config = default_config

     to_plugin.configure(device, merged_config)
     to_plugin.switch_to(device, from_protocol, preserved_state)

6. Verify new protocol:
     status = to_plugin.get_status(device)
     IF status.is_active:
       Publish protocol.switching.completed
       RETURN success
     ELSE:
       Publish protocol.switching.failed
       # Rollback attempt
       from_plugin.enable(device)
       RETURN error
```

**Evidence:** protocol_manager/app.py:355-453

#### State Preservation

When switching protocols, the following state is preserved:

**Routing Table:**
- Destination networks
- Next-hop addresses
- Metric values
- Administrative distance

**Neighbor Adjacencies:**
- Neighbor IPs
- AS numbers (for BGP)
- State (established, idle, etc.)
- Hold times

**Interface Configuration:**
- IP addresses (v4/v6)
- MTU settings
- Bandwidth allocation

#### Supported Plugins

| Plugin | Type | Supported Devices | Config FRR/BIRD |
|--------|------|-------------------|-----------------|
| `bgp` | Routing | router | FRR/BIRD |
| `ospf` | Routing | router | FRR |
| `isis` | Routing | router | FRR |
| `rip` | Routing | router | FRR |
| `static` | Routing | router, switch | Manual routes |
| `openflow_1.0` | OpenFlow | switch | OVS |
| `openflow_1.3` | OpenFlow | switch | OVS |
| `openflow_1.4` | OpenFlow | switch | OVS |
| `openflow_1.5` | OpenFlow | switch | OVS |
| `ieee80211a` | Wireless | ap, station | mac80211_hwsim |
| `ieee80211n` | Wireless | ap, station | mac80211_hwsim |
| `ieee80211ac` | Wireless | ap, station | mac80211_hwsim |
| `ieee80211ax` | Wireless | ap, station | mac80211_hwsim |
| `wpa2` | Security | ap, station | hostapd/wpa_supplicant |
| `wpa3` | Security | ap, station | hostapd/wpa_supplicant |

#### API Endpoints

- `POST /api/protocols/switch` - Execute hot-swap
- `GET /api/protocols/{device}` - Get current protocol config
- `POST /api/protocols/{device}/configure` - Apply protocol config
- `POST /api/protocols/{device}/enable` - Enable protocol
- `POST /api/protocols/{device}/disable` - Disable protocol

#### Usage Example

```bash
# Hot-swap from OSPF to BGP
curl -X POST http://localhost:8003/api/protocols/switch \
  -H "Content-Type: application/json" \
  -d '{
    "device": "router1",
    "from_protocol": "ospf",
    "to_protocol": "bgp",
    "preserve_config": true,
    "new_config": {
      "as_number": 65001,
      "router_id": "1.1.1.1",
      "neighbors": [
        {"ip": "10.0.0.2", "remote_as": 65002}
      ]
    }
  }'

# Response
{
  "success": true,
  "preserved_state": {
    "routing_table": [...],
    "neighbors": [...],
    "interfaces": [...]
  },
  "transition_time_ms": 1250
}
```

---

(Due to character limits, I'll create a second file with the remaining services)

## [Continue to Part 2...]

---

**Note:** This manual is comprehensive and spans 15 major sections. The remaining microservices (Device Manager, Controller Manager, Snapshot, WebShell, Export/Import, Topology Generator, P4 Manager, Monitoring, MCP Server, Metrics Collector, AI Gateway, MANO, Config, Decision Engine, MCP Tool Hub, OSM Connector, VIM Emulator) will be documented in Part 2, along with configuration reference, API reference, deployment guide, troubleshooting, and best practices.

**Evidence Base:** All information extracted from actual codebase with file paths and line numbers provided throughout.
