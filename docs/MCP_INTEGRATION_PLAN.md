# MCP Integration Plan (External MCP Servers)

## Purpose

Define how external Model Context Protocol (MCP) servers are integrated into the Caduceus-Flux control plane, including scope (shared vs topology-scoped), access policy (read-only vs write), and rollout phases.

## Scope Rules (from Container UI + isolated infra stack)

When `TOPOLOGY_INFRA_MODE=isolated`, the topology-scoped infrastructure stack includes:
- Grafana
- Prometheus
- Consul
- InfluxDB
- RabbitMQ
- Kafka (broker + Kafka UI)
- Portainer

Services that remain shared in the Container UI today:
- Flink
- Spark
- HDFS
- Hive
- Hue
- pgAdmin
- Mongo Express

OSM and SDN controller UIs are topology-scoped but are managed via their existing connectors and are not part of the shared infra stack.

## MCP Server Scope + Access Policy

| MCP Server | Scope | Default Access | Notes |
| --- | --- | --- | --- |
| Grafana (grafana/mcp-grafana) | topology-scoped when isolated; shared otherwise | read-only | allow write only for dashboards/datasources if needed |
| InfluxDB (influxdb3_mcp_server) | topology-scoped when isolated; shared otherwise | read-only | allow write only to the topology bucket |
| Consul (built-in) | topology-scoped when isolated; shared otherwise | read/write (restricted) | allow KV under `caduceus/` and `caduceus/topologies/<id>` only |
| Kafka (mcp-confluent) | topology-scoped when isolated; shared otherwise | read-only | allow topic create/produce within topology prefix; block delete |
| Prometheus (prometheus-mcp) | topology-scoped when isolated; shared otherwise | read-only | query-only |
| RabbitMQ (mcp-server-rabbitmq) | topology-scoped when isolated; shared otherwise | read-only | allow ops only within topology vhost if enabled |
| Spark History (mcp-apache-spark-history-server) | shared | read-only | history UI/metadata only |
| Flink (apache-flink-mcp-server) | shared | read-only | allow submit/cancel only if required |
| HDFS (Ambari or HDFS MCP) | shared | read-only | allow writes only to project paths if required |
| Hive (CDataSoftware) | shared | read-only | query-only |
| ONOS (onos-mcp-server) | topology-scoped (per controller) | read/write | required for flow/device control on scoped controller |

## Consul Registry (decision)

Consul is the source of truth for MCP server registry and credentials.

Proposed key layout:
- Shared servers: `caduceus/mcp/servers/<name>`
- Topology-scoped servers: `caduceus/topologies/<topology_id>/mcp/servers/<name>`

## Read-Only Policy (default)

- Default allowed methods: `GET`, `HEAD`.
- Writes must be explicitly allowlisted per server (via `read_only=false`, `allowed_methods`, and/or `allowed_write_prefixes`).
- Requests that exceed the allowlist return `403` with an audit entry.

## Rollout Phases

### Phase 0: Decisions and scope (DONE)
- Confirm shared vs topology-scoped based on Container UI and isolated infra stack.
- Default to read-only for external MCP servers.
- Use Consul KV as the registry/credentials store.

### Phase 1: MCP Tool Hub foundation (DONE)
- Add `mcp-tool-hub` microservice with:
  - Consul-backed registry endpoints.
  - Safe HTTP proxy (read-only enforcement).
  - Health endpoint.
- Register the service in MCP routing and `docker-compose.yml`.
- Document endpoints and registry schema.

### Phase 2: Topology-scoped routing (DONE)
- Support `/api/mcp/{topology_id}/...` endpoints in the MCP Tool Hub.
- Read topology-scoped server registry from Consul.
- Enforce scoped access via AI Gateway topology guards.

### Phase 3: Server adapters and write allowlists (DONE)
- Add MCP server profiles (Grafana, InfluxDB, Prometheus, Consul, Kafka, RabbitMQ, ONOS).
- Enforce per-endpoint write allowlists via `allowed_write_prefixes` and `blocked_path_prefixes`.

### Phase 4: AI Gateway integration (DONE)
- Expose MCP Tool Hub endpoints in MCP capabilities list.
- Add topology-scoped guardrails for `/api/mcp/*` calls.

### Phase 5: Tests + validation (DONE)
- Add smoke test script for registry + proxy (`scripts/mcp_tool_hub_smoke_test.sh`).
- Update service catalog and MCP integration documentation.

### Phase 6: Compose wiring + auto-registration (DONE)
- Add optional MCP server services under Docker Compose profile `mcp`.
- Add `mcp-registry-init` to auto-register MCP servers in Tool Hub.
- Provide env overrides for MCP server images and base URLs.

## Compose Wiring (how to run)

Enable the MCP server profile:

```bash
docker compose --profile mcp up -d
```

Auto-registration is performed by `mcp-registry-init`. The MCP services in compose are local proxy shims that forward to the upstream services by default. Override upstreams via environment variables:

- `MCP_GRAFANA_UPSTREAM_URL`
- `MCP_INFLUXDB_UPSTREAM_URL`
- `MCP_KAFKA_UPSTREAM_URL` (defaults to Kafka UI)
- `MCP_PROMETHEUS_UPSTREAM_URL`
- `MCP_RABBITMQ_UPSTREAM_URL`
- `MCP_RABBITMQ_BASIC_AUTH` (defaults to `RABBITMQ_USER`/`RABBITMQ_PASSWORD`)
- `MCP_FLINK_UPSTREAM_URL`
- `MCP_SPARK_HISTORY_UPSTREAM_URL`
- `MCP_HDFS_UPSTREAM_URL`
- `MCP_HIVE_UPSTREAM_URL`
- `MCP_ONOS_UPSTREAM_URL`
- `MCP_ONOS_BASIC_AUTH` (defaults to `onos:rocks`)

Registry entries are still driven by:

- `MCP_GRAFANA_URL`
- `MCP_INFLUXDB_URL`
- `MCP_CONSUL_URL` (Consul MCP is built-in; no separate container)
- `MCP_KAFKA_URL`
- `MCP_PROMETHEUS_URL`
- `MCP_RABBITMQ_URL`
- `MCP_FLINK_URL`
- `MCP_SPARK_HISTORY_URL`
- `MCP_HDFS_URL`
- `MCP_HIVE_URL`
- `MCP_ONOS_URL`

Note: If you replace the proxy shims with official MCP server images, update the corresponding `MCP_*_URL` values to point at those containers.

Proxy shims strip hop-by-hop headers and `content-encoding` to prevent double-decompression when the Tool Hub proxies responses.

## Validation Results

MCP Tool Hub proxy checks (2026-01-10):
- Consul, Grafana, InfluxDB, Kafka, Prometheus, RabbitMQ, Flink, Spark History, HDFS, Hive, ONOS: `200 OK`

AI Console MCP thread checks (2026-01-11):
- Same-thread tool calls via `/api/ai/agents/chat` (admin agent, TOON prompts) for all 11 MCP servers returned `200 OK`.

## Status Log

- 2026-01-06: Phase 0 completed. Phase 1 completed (Tool Hub + routing + compose).
- 2026-01-06: Phase 2 completed (topology-scoped MCP endpoints).
- 2026-01-06: Phase 3 completed (profiles + write allowlists).
- 2026-01-06: Phase 4 completed (AI Gateway integration).
- 2026-01-06: Phase 5 completed (smoke test + docs).
- 2026-01-06: Phase 6 completed (Compose wiring + auto-registration).
- 2026-01-10: Proxy shim fix (strip `content-encoding`), all MCP proxies validated via Tool Hub.
- 2026-01-11: Added `/api/mcp` allowlist to Admin/InfraOps agents; re-registered MCP servers; AI Console MCP thread validated.
- 2026-01-12: Added `mcp_ops` agent for MCP registry/proxy operations (AI Console).
