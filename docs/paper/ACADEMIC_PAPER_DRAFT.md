# Academic Paper Draft (Markdown)

This file is a **paper-ready draft** you can copy into LaTeX/Word later. It is intentionally written without claiming experimental results (placeholders are provided).

## Title

**Caduceus‑Flux: A Microservices Control Plane for Per‑Topology Network Emulation with SDN, NFV/MANO, and Streaming AI/ML Automation**

## Authors

- Author 1 (Affiliation, Email)
- Author 2 (Affiliation, Email)

## Abstract

Network emulation is widely used to prototype and evaluate distributed systems, routing behavior, SDN control logic, and network security mechanisms. However, many existing emulation workflows become difficult to scale and automate when experiments require (i) frequent runtime topology changes, (ii) heterogeneous protocol stacks (routing, OpenFlow, wireless, P4), (iii) strong observability with streaming analytics, and (iv) integration with NFV management and orchestration (MANO) tooling.  
This paper presents **Caduceus‑Flux**, a microservices-based network emulation platform that separates a privileged emulation engine from a containerized control plane. The platform stores topologies as database-backed artifacts, spawns **per-topology emulation containers** on demand, and exposes unified control through an API gateway. Caduceus‑Flux integrates (a) protocol extensibility via a plugin system, (b) real-time monitoring via a gRPC→Kafka→time-series pipeline, (c) optional streaming decision tasks for anomaly/security/policy signals, and (d) hybrid MANO support through both a local MANO microservice and an ETSI OSM integration path using a topology-scoped OpenStack-like VIM emulator.  
We describe the architecture, implementation, and experiment methodology for evaluating control-plane latency, scalability under multiple topologies, and the reproducibility of network experiments through snapshotting and artifact management.

## Keywords

Network emulation; Mininet; microservices; SDN; NFV; MANO; ETSI OSM; P4; observability; streaming analytics; Kafka; gRPC; AI-assisted network control

## 1. Introduction

### 1.1 Motivation

Explain why modern network experiments need:
- rapid iteration and repeatability,
- multi-protocol behavior (routing + SDN + programmable data planes),
- automation hooks (continuous testing, diagnostics, and policy-driven actions),
- observability and analytics (for debugging and scientific reporting),
- interoperability with MANO frameworks.

### 1.2 Contributions

List concrete contributions (edit to match your emphasis):

1. A microservices control plane for network emulation with a unified API surface (gateway + request routing).
2. A per-topology emulation runtime that spawns privileged emulation containers on demand and controls them via gRPC.
3. A metrics pipeline (gRPC streaming → Kafka → InfluxDB/Prometheus) enabling real-time dashboards and offline analysis.
4. A hybrid MANO approach: local MANO workflows and ETSI OSM integration through an adapter and VIM emulator.
5. Extensibility via protocol plugins and P4 program lifecycle management.

### 1.3 Paper organization

Example: Section 2 reviews background, Section 3 gives architecture, Section 4 implementation, Section 5 evaluation methodology, Section 6 discussion, Section 7 conclusion.

## 2. Background and Related Work

### 2.1 Network emulation platforms

Discuss Mininet/Containernet/Mininet‑WiFi and common limitations when used as monolithic tools (manual wiring, limited APIs, weaker integration with modern observability/automation).

### 2.2 SDN controllers and programmable data planes

Introduce OpenFlow controllers (OS-Ken/Ryu/ODL/ONOS) and P4/BMv2 environments as part of heterogeneous experimental setups.

### 2.3 NFV/MANO and ETSI OSM

Summarize why a MANO integration is valuable even in emulation (repeatable onboarding of VNFs, NS lifecycles, placement experiments, scale/heal workflows).

### 2.4 Streaming analytics and AI in network operations

Motivate the use of Kafka/Flink-style pipelines for metrics and policy decisions and clarify that the platform supports both baseline heuristics and ML-driven workflows.

## 3. System Overview

### 3.1 Architecture summary

Caduceus‑Flux separates the system into:

- **Frontend/UI** (topology designer and operations console)
- **API gateway** (Nginx) and **API aggregator** (MCP Server)
- **Control-plane microservices** (topology, orchestrator, monitoring, etc.)
- **Emulation plane** (per-topology privileged emulation containers)
- **Persistence and messaging** (Postgres/Mongo/Redis, RabbitMQ/Kafka, Influx/Prometheus)

See: `docs/paper/SYSTEM_ARCHITECTURE.md`.

### 3.2 Control-plane responsibilities

Key control-plane duties:
- topology authoring, validation, versioning, import/export,
- orchestration of side effects (spawning containers, applying runtime changes),
- service discovery and request routing,
- metrics ingestion, storage, and dashboards,
- MANO interactions (local and ETSI OSM).

### 3.3 Emulation-plane responsibilities

The emulation plane:
- instantiates topology objects (hosts/switches/routers/APs/stations/containers/P4 switches),
- provides gRPC endpoints for lifecycle and runtime operations,
- exports periodic metrics via gRPC streaming,
- supports snapshot capture/restore paths (where available).

## 4. Design and Architecture

### 4.1 Data model

Primary persistent objects (stored in PostgreSQL):
- Projects and topologies
- Nodes and links
- Runtime device inventory (for operations and reconciliation)
- MANO catalog and NS/VNF instances
- AI/ML registry (models, assignments, agent threads/tool calls)

Snapshot payloads are stored using a hybrid approach (Postgres metadata + MongoDB documents + snapshot volume).

### 4.2 Service decomposition

Summarize the main services and why they are separated:

- **Topology service**: durable topology state + live editor updates.
- **Orchestrator**: the only service that interacts with Docker Engine to spawn privileged runtimes and infra.
- **MCP server**: single `/api/*` surface + discovery/routing.
- **Monitoring + metrics collector**: metrics ingestion and storage.
- **Controller manager**: SDN controller lifecycle.
- **MANO + OSM connector + VIM emulator**: hybrid NFV workflows.
- **Config service**: “multi-step action plan” executor with `dry_run`.
- **AI gateway + decision engine**: model registry and automation hooks.

### 4.3 Per-topology runtime isolation

Describe the per-topology container model:

- Emulations are created per `topology_id`.
- The orchestrator spawns `caduceus-emu-<id8>` containers from an emulation image.
- gRPC port `50051` is mapped to a host port chosen at runtime.
- The container is privileged and mounts required host paths for namespace operations.

Discuss isolation tradeoffs:
- strong experiment separation (each topology has its own runtime),
- additional resource cost and container startup overhead.

### 4.4 Observability pipeline

Describe:
- gRPC `StreamMetrics` from emulation containers,
- batching and publish to Kafka `metrics.raw`,
- time-series persistence in InfluxDB,
- Prometheus exporter for standard dashboards/alerts,
- optional streaming feature engineering (`metrics.processed`) and decision tasks.

### 4.5 MANO integration design

Explain hybrid MANO:

1. **Local MANO** for direct emulation workflows (catalog + NS/VNF lifecycle).
2. **ETSI OSM integration** via:
   - `osm-connector-service` (authenticated adapter/proxy for SOL005/NBI),
   - a per-topology **VIM emulator** that exposes an OpenStack-like API and materializes resources into the running emulation,
   - optional “mirror” of OSM resources into Postgres for consistent querying and UI presentation.

## 5. Implementation

### 5.1 Technologies

- Control plane: Python/FastAPI microservices
- Emulation plane: containerized Mininet/Containernet + FRR/OVS/BMv2
- Interconnect: gRPC (protobuf), HTTP/JSON, WebSockets
- Persistence: PostgreSQL, MongoDB, Redis
- Messaging/streaming: RabbitMQ (events), Kafka (metrics/analytics)
- Observability: InfluxDB, Prometheus, Grafana

### 5.2 Interfaces

Include the concrete interfaces used:

- gRPC: `backend/proto/emulation.proto` (emulation control + metrics)
- gRPC: `backend/proto/mano.proto` (MANO control, when enabled)
- HTTP: unified gateway routes via MCP server (single `/api/*` surface)

### 5.3 Orchestration details (container spawn)

Explain how the orchestrator:
- creates/reuses containers per topology,
- attaches them to the platform Docker network,
- records runtime state (Redis + database),
- retries on transient port allocation failures,
- routes topology-scoped infra resources (optional isolated mode).

### 5.4 Snapshotting and experiment artifacts

Discuss:
- snapshot create/restore and scheduling,
- Docker checkpoint/restore integration when available,
- shared volumes for P4 artifacts and PCAPs.

## 6. Evaluation Methodology (Fill With Your Results)

This section is structured so you can run experiments and insert numbers later.

### 6.1 Research questions

Example RQs:

- **RQ1 (latency):** What is the control-plane latency for topology start/stop and runtime add/remove operations?
- **RQ2 (scalability):** How does the system behave as the number of concurrent topologies increases?
- **RQ3 (observability overhead):** What overhead does metrics collection introduce on CPU/memory and emulation performance?
- **RQ4 (reproducibility):** Can snapshots and artifact management reproduce experiments consistently?
- **RQ5 (MANO integration):** What is the end-to-end time and reliability of onboarding/instantiating NS packages through ETSI OSM integration?

### 6.2 Metrics to report

- Startup time for per-topology emulation container (p50/p95)
- Time to apply topology (nodes+links) after container start
- Time to add/remove a device at runtime
- Time to add/remove a link at runtime
- gRPC request latency (p50/p95) for common operations
- Metrics pipeline throughput (messages/sec) and end-to-end lag (gRPC → Influx)
- CPU/memory overhead per topology and per service

### 6.3 Experimental setup

Fill in:

- Host machine specs (CPU, RAM, OS, kernel)
- Docker/Compose versions
- Number of topologies and their sizes (nodes/links)
- Metrics collection interval and pipeline configuration
- SDN controller choice (if tested)
- OSM stack version (if tested)

### 6.4 Workloads

Suggested workloads:

1. **Baseline**: single topology, 10–50 nodes, no metrics pipeline.
2. **Runtime churn**: repeatedly add/remove nodes and links while traffic runs.
3. **Metrics stress**: high-frequency metrics collection and multiple topologies.
4. **MANO workflow**: onboard VNFD/NSD, instantiate NS, terminate, verify emulation state changes.
5. **P4 workflow**: compile + deploy BMv2 pipelines (if applicable).

### 6.5 Threats to validity

- emulation vs. real network fidelity,
- privileged container dependency,
- single-host Docker environment limitations,
- variability from background load and container scheduling.

## 7. Discussion

Discuss architectural tradeoffs:

- microservices overhead vs. clarity and extensibility,
- per-topology runtime separation vs. resource cost,
- shared vs. isolated infrastructure modes,
- integration complexity of MANO/OSM in an emulation environment.

## 8. Reproducibility and Artifact Availability

Provide an “artifact appendix” style checklist:

- `docker-compose.yml` orchestrates the control plane and infrastructure.
- `docs/paper/SYSTEM_ARCHITECTURE.md` describes components and flows.
- `METRICS_PIPELINE.md` documents the metrics pipeline.
- `docs/OSM_INTEGRATION.md` documents OSM integration and smoke tests.

Add your paper’s artifact URL/revision info here:
- Repository URL: `<fill>`
- Commit hash / release tag: `<fill>`
- Dataset links (pcaps, traces): `<fill>`

## 9. Conclusion

Summarize the problem, design, and what your evaluation shows (once filled in).

## References (placeholders)

Add citations here (BibTeX keys or numbered refs):

1. Mininet
2. Containernet
3. Mininet‑WiFi
4. ETSI NFV / SOL005
5. ETSI OSM
6. P4 / BMv2
7. Kafka / Flink streaming analytics
