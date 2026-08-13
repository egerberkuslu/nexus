"""
Decision Engine Service (Port 8017)

Consumes processed metrics from Kafka (`metrics.processed`) and runs **parallel** decision tasks:
- anomaly_detection -> alerts.anomaly
- attack_detection  -> alerts.security
- routing_policy    -> actions.routing
- mano_policy       -> actions.mano

Model selection is driven by the AI Gateway ML registry assignments.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any, Deque, Dict, Optional, Tuple

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.messaging.kafka_consumer import CaduceusKafkaConsumer
from shared.messaging.kafka_producer import CaduceusKafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8017"))

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_INPUT_TOPIC = os.getenv("KAFKA_METRICS_PROCESSED_TOPIC", "metrics.processed")
KAFKA_ALERTS_ANOMALY_TOPIC = os.getenv("KAFKA_ALERTS_ANOMALY_TOPIC", "alerts.anomaly")
KAFKA_ALERTS_SECURITY_TOPIC = os.getenv(
    "KAFKA_ALERTS_SECURITY_TOPIC", "alerts.security"
)
KAFKA_ACTIONS_ROUTING_TOPIC = os.getenv(
    "KAFKA_ACTIONS_ROUTING_TOPIC", "actions.routing"
)
KAFKA_ACTIONS_MANO_TOPIC = os.getenv("KAFKA_ACTIONS_MANO_TOPIC", "actions.mano")

AI_GATEWAY_URL = (
    os.getenv("AI_GATEWAY_URL") or "http://ai-gateway-service:8014"
).rstrip("/")
MODEL_REFRESH_SECONDS = int(os.getenv("MODEL_REFRESH_SECONDS", "20"))

ANOMALY_WINDOW_SIZE = int(os.getenv("ANOMALY_WINDOW_SIZE", "30"))
ANOMALY_MIN_BASELINE = int(os.getenv("ANOMALY_MIN_BASELINE", "10"))
ANOMALY_ZSCORE_THRESHOLD = float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "6.0"))
ANOMALY_EWMA_ALPHA = float(os.getenv("ANOMALY_EWMA_ALPHA", "0.2"))
ANOMALY_CUSUM_K = float(os.getenv("ANOMALY_CUSUM_K", "0.5"))
ANOMALY_CUSUM_H = float(os.getenv("ANOMALY_CUSUM_H", "6.0"))

# SkyFabric cyber-physical MANO policy: reposition a relay/VNF host when its
# measured wireless link (RSSI, dBm) degrades below this threshold.
MANO_RSSI_THRESHOLD_DBM = float(os.getenv("MANO_RSSI_THRESHOLD_DBM", "-78"))

EMIT_NOOP_DECISIONS = os.getenv("EMIT_NOOP_DECISIONS", "false").lower() == "true"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        return float(value)
    except Exception:
        return None


def _rssi_link_cost(rssi_dbm: float) -> float:
    """RSSI -> relative link cost for FD-DSP placement (lower is better).

    Inlined piecewise envelope matching Paper C's wifi_model.rssi_to_phy_mbps:
    strong link ~ high PHY rate ~ low cost; near the noise floor the cost blows
    up. cost = 1 / phy_mbps(rssi). Kept dependency-free so it runs in the DE
    container (the paper module is not on its path)."""
    r = float(rssi_dbm)
    if r >= -50:
        phy = 72.0
    elif r >= -60:
        phy = 65.0
    elif r >= -67:
        phy = 52.0
    elif r >= -74:
        phy = 39.0
    elif r >= -80:
        phy = 26.0
    elif r >= -86:
        phy = 13.0
    elif r >= -90:
        phy = 6.5
    else:
        phy = 1.0  # near/below noise floor -> very costly
    return 1.0 / phy


def _robust_zscore(values: list[float], x: float) -> float:
    if len(values) < 3:
        return 0.0
    med = median(values)
    abs_devs = [abs(v - med) for v in values]
    mad = median(abs_devs) if abs_devs else 0.0
    if mad <= 1e-9:
        return 0.0 if abs(x - med) <= 1e-9 else 999.0
    return abs(0.6745 * (x - med) / mad)


def _severity(score: float) -> str:
    if score >= 12:
        return "critical"
    if score >= 9:
        return "high"
    if score >= 6:
        return "medium"
    return "low"


@dataclass
class ModelInfo:
    task: str
    model_id: str
    name: str
    algorithm: str
    framework: str
    meta: Dict[str, Any]


class ModelAssignments:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_task: Dict[str, ModelInfo] = {}
        self._last_refresh: float = 0.0

    def get(self, task: str) -> Optional[ModelInfo]:
        with self._lock:
            return self._by_task.get(task)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "last_refresh": self._last_refresh,
                "assignments": {
                    task: {
                        "model_id": m.model_id,
                        "name": m.name,
                        "algorithm": m.algorithm,
                        "framework": m.framework,
                        "meta": m.meta,
                    }
                    for task, m in self._by_task.items()
                },
            }

    def refresh(self) -> None:
        url = f"{AI_GATEWAY_URL}/api/ai/ml/assignments"
        try:
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            payload = resp.json() or {}
        except Exception as exc:
            logger.warning("Failed to refresh ML assignments from %s: %s", url, exc)
            return

        models_by_id = payload.get("models_by_id") or {}
        next_by_task: Dict[str, ModelInfo] = {}
        for a in payload.get("assignments") or []:
            task = str(a.get("task") or "").strip()
            model_id = str(a.get("model_id") or "").strip()
            if not task or not model_id:
                continue
            m = models_by_id.get(model_id) or {}
            next_by_task[task] = ModelInfo(
                task=task,
                model_id=model_id,
                name=str(m.get("name") or model_id),
                algorithm=str(m.get("algorithm") or "noop"),
                framework=str(m.get("framework") or "builtin"),
                meta=dict(m.get("meta") or {}),
            )

        with self._lock:
            self._by_task = next_by_task
            self._last_refresh = time.time()


class DecisionEngine:
    def __init__(self) -> None:
        self.assignments = ModelAssignments()
        self.producer = CaduceusKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, client_id="decision-engine"
        )

        self._running = False
        self._consumer: Optional[CaduceusKafkaConsumer] = None

        self._in_queue: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=10_000)
        self._queues: Dict[str, "queue.Queue[dict[str, Any]]"] = {
            "anomaly_detection": queue.Queue(maxsize=10_000),
            "attack_detection": queue.Queue(maxsize=10_000),
            "routing_policy": queue.Queue(maxsize=10_000),
            "mano_policy": queue.Queue(maxsize=10_000),
        }

        self._threads: list[threading.Thread] = []
        self._stats_lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "received": 0,
            "dropped": 0,
            "processed": defaultdict(int),
            "emitted": defaultdict(int),
            "errors": defaultdict(int),
        }

        self._history: Dict[Tuple[str, str, str], Deque[float]] = defaultdict(
            lambda: deque(maxlen=ANOMALY_WINDOW_SIZE)
        )
        self._ewma_state: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(dict)
        self._cusum_state: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(
            dict
        )

    def _ewma_zscore(self, key: Tuple[str, str, str], x: float) -> Tuple[float, float]:
        st = self._ewma_state[key]
        n = int(st.get("n") or 0)
        mean = float(st.get("mean")) if "mean" in st else x
        var = float(st.get("var")) if "var" in st else 0.0

        score = 0.0
        if n >= ANOMALY_MIN_BASELINE:
            if var <= 1e-9:
                score = 0.0 if abs(x - mean) <= 1e-9 else 999.0
            else:
                score = abs(x - mean) / (var**0.5)

        alpha = ANOMALY_EWMA_ALPHA
        next_mean = alpha * x + (1 - alpha) * mean
        next_var = alpha * ((x - next_mean) ** 2) + (1 - alpha) * var
        st["n"] = n + 1
        st["mean"] = next_mean
        st["var"] = next_var
        return score, mean

    def _cusum_score(self, key: Tuple[str, str, str], x: float) -> Tuple[float, float]:
        z, baseline = self._ewma_zscore(key, x)
        st = self._cusum_state[key]
        s_pos = float(st.get("s_pos") or 0.0)
        s_pos = max(0.0, s_pos + (z - ANOMALY_CUSUM_K))
        st["s_pos"] = s_pos
        return s_pos, baseline

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        self.assignments.refresh()

        self._consumer = CaduceusKafkaConsumer(
            group_id="decision-engine-consumer",
            topics=[KAFKA_INPUT_TOPIC],
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        self._consumer.register_callback(KAFKA_INPUT_TOPIC, self._on_metrics)
        self._consumer.start_consuming(blocking=False)

        self._threads.append(
            threading.Thread(target=self._fanout_loop, name="fanout", daemon=True)
        )
        self._threads.append(
            threading.Thread(
                target=self._refresh_models_loop, name="model-refresh", daemon=True
            )
        )
        self._threads.append(
            threading.Thread(target=self._anomaly_loop, name="anomaly", daemon=True)
        )
        self._threads.append(
            threading.Thread(target=self._attack_loop, name="attack", daemon=True)
        )
        self._threads.append(
            threading.Thread(target=self._routing_loop, name="routing", daemon=True)
        )
        self._threads.append(
            threading.Thread(target=self._mano_loop, name="mano", daemon=True)
        )
        for t in self._threads:
            t.start()

        logger.info(
            "Decision engine started (topic=%s, bootstrap=%s)",
            KAFKA_INPUT_TOPIC,
            KAFKA_BOOTSTRAP_SERVERS,
        )

    def stop(self) -> None:
        self._running = False
        try:
            if self._consumer:
                self._consumer.disconnect()
        except Exception:
            pass
        try:
            self.producer.disconnect()
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        with self._stats_lock:
            processed = dict(self._stats["processed"])
            emitted = dict(self._stats["emitted"])
            errors = dict(self._stats["errors"])
            return {
                "running": self._running,
                "kafka_input_topic": KAFKA_INPUT_TOPIC,
                "received": int(self._stats["received"]),
                "dropped": int(self._stats["dropped"]),
                "processed": processed,
                "emitted": emitted,
                "errors": errors,
                "queue_sizes": {
                    "in": self._in_queue.qsize(),
                    **{k: q.qsize() for k, q in self._queues.items()},
                },
                "models": self.assignments.snapshot(),
            }

    def _bump(self, category: str, key: str, n: int = 1) -> None:
        with self._stats_lock:
            self._stats[category][key] += n

    def _on_metrics(self, message: Dict[str, Any]) -> None:
        with self._stats_lock:
            self._stats["received"] += 1
        try:
            self._in_queue.put_nowait(message)
        except queue.Full:
            with self._stats_lock:
                self._stats["dropped"] += 1

    def _fanout_loop(self) -> None:
        while self._running:
            try:
                msg = self._in_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            for task, q in self._queues.items():
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    self._bump("errors", f"{task}.queue_full")

    def _refresh_models_loop(self) -> None:
        while self._running:
            try:
                self.assignments.refresh()
            except Exception:
                pass
            time.sleep(max(5, MODEL_REFRESH_SECONDS))

    def _extract_ctx(
        self, message: Dict[str, Any]
    ) -> Tuple[str, str, str, Dict[str, Any], Dict[str, Any]]:
        topology_id = str(
            message.get("topology_id")
            or (message.get("metrics") or {}).get("topology_id")
            or ""
        )
        emulation_id = str(
            message.get("emulation_id")
            or (message.get("metrics") or {}).get("emulation_id")
            or ""
        )
        device = str(
            message.get("device") or (message.get("metrics") or {}).get("device") or ""
        )
        metrics = (
            message.get("metrics") if isinstance(message.get("metrics"), dict) else {}
        )
        features = (
            message.get("features") if isinstance(message.get("features"), dict) else {}
        )
        return topology_id, emulation_id, device, metrics, features

    def _anomaly_loop(self) -> None:
        while self._running:
            try:
                msg = self._queues["anomaly_detection"].get(timeout=1.0)
            except queue.Empty:
                continue

            self._bump("processed", "anomaly_detection")
            model = self.assignments.get("anomaly_detection")
            algorithm = (model.algorithm if model else "robust_zscore").strip().lower()
            if algorithm in {"noop", ""}:
                if EMIT_NOOP_DECISIONS:
                    self._emit_noop("anomaly_detection", msg)
                continue

            if algorithm not in {"robust_zscore", "ewma_zscore", "cusum"}:
                self._bump("errors", "anomaly_detection.unsupported_algorithm")
                continue

            try:
                (
                    topology_id,
                    emulation_id,
                    device,
                    metrics,
                    features,
                ) = self._extract_ctx(msg)
                if not topology_id or not device:
                    continue

                candidates = {
                    "tx_bps": _safe_float(features.get("tx_bps")),
                    "rx_bps": _safe_float(features.get("rx_bps")),
                    "drops_rate": _safe_float(features.get("drops_rate")),
                    "cpu_percent": _safe_float(metrics.get("cpu_percent")),
                }

                best: Tuple[
                    str, float, float, float
                ] | None = None  # feature, x, baseline, score
                for name, x in candidates.items():
                    if x is None:
                        continue
                    key = (topology_id, device, name)

                    if algorithm == "robust_zscore":
                        hist = self._history[key]
                        if len(hist) >= ANOMALY_MIN_BASELINE:
                            score = _robust_zscore(list(hist), x)
                            base = median(list(hist))
                            if best is None or score > best[3]:
                                best = (name, x, base, score)
                        hist.append(float(x))
                    elif algorithm == "ewma_zscore":
                        score, base = self._ewma_zscore(key, float(x))
                        if best is None or score > best[3]:
                            best = (name, float(x), float(base), float(score))
                    else:  # cusum
                        score, base = self._cusum_score(key, float(x))
                        if best is None or score > best[3]:
                            best = (name, float(x), float(base), float(score))

                if not best:
                    continue

                feature, x, baseline, score = best
                threshold = (
                    ANOMALY_ZSCORE_THRESHOLD
                    if algorithm != "cusum"
                    else ANOMALY_CUSUM_H
                )
                if score < threshold:
                    continue

                payload = {
                    "timestamp": _now_iso(),
                    "topology_id": topology_id,
                    "emulation_id": emulation_id or None,
                    "device": device,
                    "kind": "anomaly",
                    "score": float(score),
                    "severity": _severity(score),
                    "model": {
                        "task": "anomaly_detection",
                        "model_id": (model.model_id if model else "builtin"),
                        "name": (model.name if model else algorithm),
                    },
                    "evidence": {
                        "feature": feature,
                        "value": float(x),
                        "baseline": float(baseline),
                    },
                }
                ok = self.producer.send_message(
                    KAFKA_ALERTS_ANOMALY_TOPIC, payload, key=f"{topology_id}|{device}"
                )
                if ok:
                    self._bump("emitted", "alerts.anomaly")
            except Exception:
                self._bump("errors", "anomaly_detection.exception")

    def _attack_loop(self) -> None:
        while self._running:
            try:
                msg = self._queues["attack_detection"].get(timeout=1.0)
            except queue.Empty:
                continue

            self._bump("processed", "attack_detection")
            model = self.assignments.get("attack_detection")
            algorithm = (
                (model.algorithm if model else "correlation_rules").strip().lower()
            )
            if algorithm in {"noop", ""}:
                if EMIT_NOOP_DECISIONS:
                    self._emit_noop("attack_detection", msg)
                continue
            if algorithm not in {"correlation_rules"}:
                self._bump("errors", "attack_detection.unsupported_algorithm")
                continue

            try:
                (
                    topology_id,
                    emulation_id,
                    device,
                    metrics,
                    features,
                ) = self._extract_ctx(msg)
                if not topology_id or not device:
                    continue

                drops_rate = _safe_float(features.get("drops_rate")) or 0.0
                tx_bps = _safe_float(features.get("tx_bps")) or 0.0
                cpu = _safe_float(metrics.get("cpu_percent")) or 0.0

                suspicious = drops_rate > 50.0 and tx_bps > 10000.0 and cpu > 80.0
                if not suspicious:
                    continue

                payload = {
                    "timestamp": _now_iso(),
                    "topology_id": topology_id,
                    "emulation_id": emulation_id or None,
                    "device": device,
                    "kind": "security",
                    "score": float(min(1.0, (drops_rate / 200.0) + (cpu / 200.0))),
                    "severity": "high",
                    "model": {
                        "task": "attack_detection",
                        "model_id": (model.model_id if model else "builtin"),
                        "name": (model.name if model else algorithm),
                    },
                    "evidence": {
                        "drops_rate": drops_rate,
                        "tx_bps": tx_bps,
                        "cpu_percent": cpu,
                    },
                }
                ok = self.producer.send_message(
                    KAFKA_ALERTS_SECURITY_TOPIC, payload, key=f"{topology_id}|{device}"
                )
                if ok:
                    self._bump("emitted", "alerts.security")
            except Exception:
                self._bump("errors", "attack_detection.exception")

    def _emit_noop(self, task: str, msg: Dict[str, Any]) -> None:
        topology_id, emulation_id, device, _metrics, _features = self._extract_ctx(msg)
        if not topology_id:
            return
        model = self.assignments.get(task)
        payload = {
            "timestamp": _now_iso(),
            "topology_id": topology_id,
            "emulation_id": emulation_id or None,
            "device": device or None,
            "task": task,
            "model": {
                "task": task,
                "model_id": (model.model_id if model else "builtin"),
                "name": (model.name if model else "noop"),
            },
            "noop": True,
        }
        topic = {
            "routing_policy": KAFKA_ACTIONS_ROUTING_TOPIC,
            "mano_policy": KAFKA_ACTIONS_MANO_TOPIC,
        }.get(task)
        if topic:
            ok = self.producer.send_message(
                topic, payload, key=f"{topology_id}|{device or ''}"
            )
            if ok:
                self._bump("emitted", f"{task}.noop")

    def _routing_loop(self) -> None:
        while self._running:
            try:
                msg = self._queues["routing_policy"].get(timeout=1.0)
            except queue.Empty:
                continue
            self._bump("processed", "routing_policy")
            model = self.assignments.get("routing_policy")
            algorithm = (model.algorithm if model else "noop").strip().lower()
            if algorithm in {"noop", ""}:
                if EMIT_NOOP_DECISIONS:
                    self._emit_noop("routing_policy", msg)
                continue
            if algorithm != "fd_dsp":
                self._bump("errors", "routing_policy.unsupported_algorithm")
                continue
            # FD-DSP (Paper C) placement/routing: forecast-driven, link-quality
            # aware. The link half runs here on the real wmediumd RSSI carried in
            # metrics.processed -- maintain a per-worker RSSI cache and route the
            # next shard/request to the lowest-link-cost worker.
            try:
                (
                    topology_id,
                    emulation_id,
                    device,
                    metrics,
                    features,
                ) = self._extract_ctx(msg)
                if not topology_id or not device:
                    continue
                rssi = _safe_float(features.get("rssi_dbm"))
                # cache is scoped PER TOPOLOGY so workers of one emulation never
                # pollute another's routing decision.
                if not hasattr(self, "_link_rssi"):
                    self._link_rssi = {}
                topo_links = self._link_rssi.setdefault(topology_id, {})
                if rssi is not None:
                    topo_links[device] = rssi
                if not topo_links:
                    continue
                ranked = sorted(topo_links.items(), key=lambda kv: kv[1], reverse=True)
                best_dev, best_rssi = ranked[0]
                payload = {
                    "timestamp": _now_iso(),
                    "topology_id": topology_id,
                    "emulation_id": emulation_id or None,
                    "kind": "route",
                    "algorithm": "fd_dsp",
                    "target": best_dev,
                    "target_rssi_dbm": float(best_rssi),
                    "link_cost": round(_rssi_link_cost(best_rssi), 4),
                    "candidates": [
                        {
                            "device": d,
                            "rssi_dbm": float(r),
                            "link_cost": round(_rssi_link_cost(r), 4),
                        }
                        for d, r in ranked
                    ],
                    "model": {
                        "task": "routing_policy",
                        "model_id": (model.model_id if model else "builtin"),
                        "name": (model.name if model else algorithm),
                    },
                }
                ok = self.producer.send_message(
                    KAFKA_ACTIONS_ROUTING_TOPIC,
                    payload,
                    key=f"{topology_id}|route",
                )
                if ok:
                    self._bump("emitted", "actions.routing")
            except Exception:
                self._bump("errors", "routing_policy.exception")

    def _mano_loop(self) -> None:
        while self._running:
            try:
                msg = self._queues["mano_policy"].get(timeout=1.0)
            except queue.Empty:
                continue
            self._bump("processed", "mano_policy")
            model = self.assignments.get("mano_policy")
            # SkyFabric: default to the built-in cyber-physical reposition policy so
            # the closed loop works without an explicit AI-Gateway assignment
            # (mirrors anomaly_detection defaulting to robust_zscore).
            algorithm = (
                (model.algorithm if model else "rssi_reposition").strip().lower()
            )
            if algorithm in {"noop", ""}:
                if EMIT_NOOP_DECISIONS:
                    self._emit_noop("mano_policy", msg)
                continue
            if algorithm != "rssi_reposition":
                self._bump("errors", "mano_policy.unsupported_algorithm")
                continue
            try:
                (
                    topology_id,
                    emulation_id,
                    device,
                    metrics,
                    features,
                ) = self._extract_ctx(msg)
                if not topology_id or not device:
                    continue
                rssi = _safe_float(features.get("rssi_dbm"))
                if rssi is None:
                    continue
                if rssi >= MANO_RSSI_THRESHOLD_DBM:
                    # link healthy -> no action (this is what stops the loop once the
                    # commanded reposition restores the link).
                    continue
                ax = _safe_float(features.get("anchor_x"))
                ay = _safe_float(features.get("anchor_y"))
                az = _safe_float(features.get("anchor_z"))
                if ax is None or ay is None or az is None:
                    self._bump("errors", "mano_policy.no_anchor")
                    continue
                payload = {
                    "timestamp": _now_iso(),
                    "topology_id": topology_id,
                    "emulation_id": emulation_id or None,
                    "device": device,
                    "kind": "reposition",
                    "reason": "rssi_below_threshold",
                    "current_rssi_dbm": float(rssi),
                    "threshold_dbm": float(MANO_RSSI_THRESHOLD_DBM),
                    "target": {"x": float(ax), "y": float(ay), "z": float(az)},
                    "model": {
                        "task": "mano_policy",
                        "model_id": (model.model_id if model else "builtin"),
                        "name": (model.name if model else algorithm),
                    },
                }
                ok = self.producer.send_message(
                    KAFKA_ACTIONS_MANO_TOPIC, payload, key=f"{topology_id}|{device}"
                )
                if ok:
                    self._bump("emitted", "actions.mano")
            except Exception:
                self._bump("errors", "mano_policy.exception")


engine = DecisionEngine()

app = FastAPI(
    title="Caduceus-Flux Decision Engine",
    description="Parallel AI/ML decision tasks over streaming metrics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    engine.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    engine.stop()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "running": True,
        "kafka_topic": KAFKA_INPUT_TOPIC,
        "ai_gateway": AI_GATEWAY_URL,
    }


@app.get("/api/stats")
async def stats() -> Dict[str, Any]:
    return engine.stats()
