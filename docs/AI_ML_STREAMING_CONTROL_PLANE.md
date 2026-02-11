# AI/ML Streaming Control Plane (Design)

This document proposes a **shared (non-isolated)** streaming analytics + AI/ML decision architecture for Caduceus‑Flux, plus an operator workflow to **upload/select models**, run **parallel decision tasks**, and use **JupyterLab** for rapid iteration and offline evaluation (including PCAP-driven experiments).

## Goals

- **Shared pipeline**: one Kafka + one Flink cluster for all topologies (no per-topology infra).
- **Parallel tasks**: anomaly detection, attack detection, routing/TE, MANO ops run independently and concurrently.
- **Influx stores both**: raw metrics stream and processed/features stream.
- **Hot-swappable models**: upload/select models/algorithms without redeploying core services.
- **Experimentation loop**: JupyterLab for training/eval + access to artifacts (models, pcaps).

## Non-goals (for MVP)

- Perfect model governance (RBAC, approvals, signed artifacts).
- Full packet/flow telemetry everywhere (we start with metrics, then add flows/pcaps).

## High-level Architecture

```
Mininet/Containernet
  └─ gRPC StreamMetrics
      └─ metrics-collector
           └─ Kafka topic: metrics.raw
                ├─ Influx sink (raw)
                ├─ Flink Job A: feature engineering  ──> Kafka: metrics.processed
                │      └─ Influx sink (processed)
                ├─ Flink Job B: anomaly detection    ──> Kafka: alerts.anomaly
                ├─ Flink Job C: attack detection     ──> Kafka: alerts.security
                ├─ Flink Job D: routing policy/RL    ──> Kafka: actions.routing
                └─ Flink Job E: MANO policy/RL       ──> Kafka: actions.mano
                                        └─ action-executor (Config Service + Orchestrator/Controller/MANO)

Model Registry (upload/select)
  └─ decision services / Flink jobs load active model(s)

JupyterLab (Data Lab)
  ├─ reads Influx (raw+processed) + Kafka (optional) + Postgres
  ├─ reads/writes Model Registry artifacts
  └─ reads/writes PCAP artifacts
```

### Why shared (no isolated per topology)
- Lowest operational overhead (one Kafka, one Flink).
- Still supports multi-topology separation using **tags/keys**:
  - `topology_id`, `emulation_id`, `device` always present
  - Kafka key: `"{topology_id}|{device}"` to preserve per-device ordering while scaling partitions.

## Topics (shared)

### Core
- `metrics.raw`: raw device metrics (source of truth).
- `metrics.processed`: enriched metrics + engineered features.

### Alerts
- `alerts.anomaly`: per-device/per-topology anomalies.
- `alerts.security`: suspected attack indicators.

### Actions
- `actions.routing`: link-weight/path/flow rule recommendations.
- `actions.mano`: scale/heal/placement recommendations.

### Control / Metadata
- `topology.events`: topology lifecycle changes (start/stop, add/remove node/link).
- `mano.events`: NS/VNF lifecycle changes from `mano-service`.

## Message Shapes (recommended)

### `metrics.raw`
- Key: `"{topology_id}|{device}"`
- Value:
```json
{
  "timestamp": "2026-01-05T12:34:56.789Z",
  "topology_id": "uuid",
  "emulation_id": "uuid-or-string",
  "device": "h1",
  "source": "grpc",
  "metrics": {
    "bytes_sent": 1,
    "bytes_received": 2,
    "packets_sent": 3,
    "packets_received": 4,
    "errors_in": 0,
    "errors_out": 0,
    "drops_in": 0,
    "drops_out": 0,
    "cpu_percent": 12.3,
    "memory_percent": 45.6
  }
}
```

### `metrics.processed`
- Keep the same envelope; put engineered values under `features` (or merge into `metrics` if your sink expects it).
```json
{
  "timestamp": "2026-01-05T12:34:56.789Z",
  "topology_id": "uuid",
  "emulation_id": "uuid-or-string",
  "device": "h1",
  "source": "flink.features",
  "metrics": { "...raw counters/gauges..." },
  "features": {
    "tx_bps": 1234.5,
    "rx_bps": 2345.6,
    "cpu_ewma_60s": 10.2,
    "drops_rate_10s": 0.01
  }
}
```

### `alerts.*`
```json
{
  "timestamp": "2026-01-05T12:35:10.000Z",
  "topology_id": "uuid",
  "emulation_id": "uuid-or-string",
  "device": "h1",
  "kind": "anomaly|security",
  "score": 0.93,
  "severity": "low|medium|high|critical",
  "model": { "task": "anomaly_detection", "model_id": "uuid", "name": "TranAD-v1" },
  "evidence": { "feature": "drops_rate_10s", "value": 0.2, "baseline": 0.01 }
}
```

### `actions.*`
Actions should be **idempotent** and include a clear `dry_run` capability. The platform’s `config-service` is a good execution surface because it already coordinates Orchestrator/Controller/MANO actions.
```json
{
  "timestamp": "2026-01-05T12:35:20.000Z",
  "topology_id": "uuid",
  "emulation_id": "uuid-or-string",
  "action_id": "uuid",
  "task": "routing|mano",
  "model": { "task": "routing_policy", "model_id": "uuid" },
  "confidence": 0.81,
  "actions": [
    { "kind": "network_config.apply", "params": { "config": { "...": "..." } } }
  ],
  "dry_run": true
}
```

## Model Strategy (SOTA + Practical)

### Anomaly detection (metrics-first)
- Start with robust baselines (EWMA/CUSUM/MAD) for guardrails + drift detection.
- Upgrade path:
  - Multivariate time-series: `TranAD`, `Anomaly Transformer`, `USAD`, `OmniAnomaly`, `MSCRED`, `DAGMM`
  - When leveraging topology/graph structure: `GDN`, `MTAD-GAT` (graph attention), GNN-based predictors + residual anomaly scoring
  - When mixing long-range seasonality: Transformers (`Informer`-style) + reconstruction/forecast residuals
  - Practical ops: always keep a lightweight baseline model as a guardrail (drift + sanity)

### Routing/TE
- Predictive GNN: `RouteNet` family (delay/queue modeling) → enable fast what-if evaluation.
- Policy learning (online): PPO/SAC/DQN → propose link-weight or segment-routing adjustments under constraints.
- Hybrid: supervised “good policy” distillation + constrained RL fine-tuning.
- Practical ops: start with safe no-op + rule-based policies; graduate to RL after offline evaluation with replay.

### MANO operations (scale/heal)
- Forecasting: `TFT`, `PatchTST`, `N-BEATS`, `DeepAR` to predict load/latency → scale/placement decisions.
- RL for autoscaling/healing: PPO/SAC/A3C with hard safety constraints (SLO + cooldowns).
- Practical ops: keep decisions idempotent + auditable; default to dry-run until policies are validated.

### Security/attack detection
Real attack classification generally needs richer telemetry than device counters (flows/pcaps).
- Phase 1: anomaly-on-metrics + correlation across devices.
- Phase 2: add flow features and/or PCAP-derived features and train classifiers (XGBoost/LightGBM, Transformers).

## Implementation Notes (current repo)

- **Shared Flink**: `flink-jobmanager` + `flink-taskmanager` (session cluster) + `flink-metrics-feature-job` submits `metrics-feature-job` which reads `metrics.raw` and writes `metrics.processed` (feature engineering).
- **Parallel decision tasks**: `decision-engine-service` consumes `metrics.processed` once, fans out to per-task workers, and emits `alerts.*` / `actions.*` based on the active ML model assignment.
- **Influx storage**: `monitoring-service` consumes both `metrics.raw` and `metrics.processed` and stores them in one bucket with a `source` tag (raw: `grpc`, processed: `flink.features`).

## Model Registry (upload/select)

The platform should support:
- Upload model artifacts (start with **ONNX** and/or **TorchScript**).
- Register built-in algorithms (no artifact) for quick iteration.
- Assign an **active model per task** (global default; optional topology overrides later).
- Keep metadata: task, algorithm, framework, feature schema, output schema, sha256, size, created_at.

## JupyterLab (Data Lab)

JupyterLab is used to:
- Query Influx raw+processed streams for training/evaluation.
- Read/write the shared **model artifacts** volume.
- Read/write **PCAP artifacts** volume for traffic experiments.

### PyFlink (optional)
If you want the Flink jobs themselves to be written in Python:
- **PyFlink still runs on the JVM Flink cluster**; the Python code is just the job “frontend” + Python UDF workers.
- It’s great for **rapid iteration** (especially from Data Lab) but has extra operational concerns (Python deps, UDF performance, packaging).
- For this repo we keep the always-on feature-engineering job as a **Java JAR** (most stable for unattended cluster runs), and keep **AI/ML inference + policy logic in Python** (`decision-engine-service`) where model tooling already lives.

## PCAP Artifacts (workflow)

Short-term:
- Capture pcaps via orchestrator-driven tcpdump into a shared volume.
- Analyze in JupyterLab (feature extraction → training datasets).

Long-term:
- Add flow telemetry (OpenFlow/OVS port stats + flow counters) and optionally sampled packet capture.
- Add a “dataset export” pipeline for reproducible experiments.

## Rollout Plan (suggested)

1. Create shared topics + Influx sinks for raw+processed.
2. Add Flink Job A (features) + write `metrics.processed`.
3. Add Model Registry + “active model” selection.
4. Add Decision tasks (anomaly first), then routing/MANO.
5. Add PCAP capture + notebook workflows; later integrate flow telemetry.
