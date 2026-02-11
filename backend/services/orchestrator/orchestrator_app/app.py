"""
Emulation Orchestrator Service - Port 8002
Manages emulation lifecycle and coordinates with emulation container via gRPC
"""

import copy
import logging
import threading
import time
import docker
import asyncio
from docker.types import Healthcheck
from datetime import datetime, timezone
from fastapi import Body, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, Tuple, List
import grpc
import os
import httpx
import re
import hashlib
import uuid
import shlex
import json
import secrets
import string
import csv
from io import StringIO
from docker.errors import APIError as DockerAPIError
from fastapi import File, Form, UploadFile

import emulation_pb2
import emulation_pb2_grpc

from shared.messaging.rabbitmq import RabbitMQPublisher, RabbitMQConsumer
from shared.utils.consul_client import ConsulClient
from shared.schemas.topology_schema import (
    EmulationStartRequest,
    EmulationControlResponse,
    EmulationStatusResponse,
    CommandExecuteRequest,
    CommandExecuteResponse,
    TopologyApplyRequest,
    TopologyChangeSet,
    NodeIdentifier,
    LinkIdentifier
)
from dataclasses import dataclass, field

from orchestrator_core.schemas import (
    AlgorithmOverlayResponse,
    AlgorithmRunStartResponse,
    AlgorithmRunStatusResponse,
    ApplyChangesResponse,
    EmulationRuntimeAddDeviceRequest,
    EmulationRuntimeAddLinkRequest,
    EmulationStopRequest,
    InfrastructureEnsureRequest,
    InfluxDiagnosticsFeaturesResponse,
    InfluxDiagnosticsQueryRequest,
    InfluxDiagnosticsQueryResponse,
    NetworkConfigApplyRequestBody,
    NetworkConfigApplyResponseBody,
    OrchestratorStartOptions,
    TestRunRequest,
    TestRunStateEnum,
    TestRunStatusResponse,
    TestRunStopRequest,
    TestRunStep,
    TestStepStateEnum,
    TopologyControllerExecRequest,
    TopologyControllerLifecycleRequest,
    TopologyInfraPurgeRequest,
    TopologyInfraRestartRequest,
    TopologyInfraStopRequest,
    TopologyOsmPurgeRequest,
    TopologyOsmStopRequest,
)
from orchestrator_core.pcap import PcapService
from orchestrator_core.topology_events import TopologyEventHandlers

from algorithm_runner import (
    build_topo_context,
    create_run_tar_bytes,
    load_bundle_to_tempdir,
    new_run_id,
    normalize_selected_nodes,
    run_selector_if_present,
)

from orchestrator_app.grpc_client import (
    gRPCClient,
    gRPCClientManager,
    parse_ip_link_interfaces as _parse_ip_link_interfaces,
    pick_default_interface as _pick_default_interface,
    resolve_runtime_name,
    runtime_device_name as _runtime_device_name,
    runtime_link_key as _runtime_link_key,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from orchestrator_app.stop_tasks import StopTaskManager

# Event handler instance used by RabbitMQ consumer callbacks (initialized on startup).
_topology_event_handlers: Optional[TopologyEventHandlers] = None
_pcap_service: Optional[PcapService] = None

# Background stop tasks (avoid long-running HTTP requests timing out in the browser/proxies).
stop_task_manager = StopTaskManager()


def _lp_escape_measurement(value: str) -> str:
    return (value or "").replace(",", "\\,").replace(" ", "\\ ")


def _lp_escape_tag(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _lp_escape_str_field(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("\"", "\\\"")


def _lp_line(measurement: str, tags: Dict[str, Any], fields: Dict[str, Any], ts_ns: int) -> str:
    m = _lp_escape_measurement(measurement)
    tag_parts = []
    for k, v in (tags or {}).items():
        if v is None:
            continue
        tag_parts.append(f"{_lp_escape_tag(str(k))}={_lp_escape_tag(str(v))}")
    field_parts = []
    for k, v in (fields or {}).items():
        if v is None:
            continue
        key = _lp_escape_tag(str(k))
        if isinstance(v, bool):
            field_parts.append(f"{key}={str(v).lower()}")
        elif isinstance(v, int):
            field_parts.append(f"{key}={v}i")
        elif isinstance(v, float):
            field_parts.append(f"{key}={v}")
        else:
            field_parts.append(f"{key}=\"{_lp_escape_str_field(str(v))}\"")
    if not field_parts:
        field_parts = ["value=1i"]
    tags_str = ("," + ",".join(tag_parts)) if tag_parts else ""
    return f"{m}{tags_str} {','.join(field_parts)} {int(ts_ns)}"


def _flux_escape_str(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _shared_influx_bucket_for_topology(topology_id: str) -> str:
    bucket = (
        _consul_get(f"caduceus/topologies/{topology_id}/influxdb_bucket")
        or os.getenv("INFLUXDB_BUCKET")
        or "metrics"
    )
    bucket = str(bucket or "").strip()
    if not bucket:
        raise HTTPException(status_code=409, detail="Shared InfluxDB bucket is not configured.")
    return bucket


def _resolve_topology_influx_target(topology_id: str) -> Dict[str, str]:
    if TOPOLOGY_INFRA_MODE == "isolated":
        influx_org = _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_org")
        influx_bucket = _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_bucket")
        influx_token = _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_token")
        if not (influx_org and influx_bucket and influx_token):
            raise HTTPException(status_code=409, detail="Topology InfluxDB credentials missing; ensure topology infra first.")
        influx_container = _topo_container_name(topology_id, "influxdb")
        base_url = f"http://{influx_container}:8086"
        return {
            "mode": "isolated",
            "base_url": base_url,
            "org": str(influx_org),
            "bucket": str(influx_bucket),
            "token": str(influx_token),
        }

    influx_org = str(os.getenv("INFLUXDB_ORG", "caduceus-flux") or "").strip()
    influx_bucket = _shared_influx_bucket_for_topology(topology_id)
    influx_token = str(os.getenv("INFLUXDB_TOKEN", "") or "").strip()
    base_url = str(os.getenv("INFLUXDB_URL", "http://influxdb:8086") or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=409, detail="INFLUXDB_URL is not configured for shared mode.")
    if not influx_org:
        raise HTTPException(status_code=409, detail="INFLUXDB_ORG is not configured for shared mode.")
    if not influx_token:
        raise HTTPException(status_code=409, detail="INFLUXDB_TOKEN is not configured for shared mode.")
    return {
        "mode": "shared",
        "base_url": base_url,
        "org": influx_org,
        "bucket": influx_bucket,
        "token": influx_token,
    }


def _shared_topology_flux_filter(topology_id: str) -> str:
    if TOPOLOGY_INFRA_MODE == "isolated":
        return ""
    tid = _flux_escape_str(topology_id)
    return f'|> filter(fn: (r) => exists r.topology_id and r.topology_id == "{tid}")'


async def _write_influx_lines_for_topology(topology_id: str, lines: List[str]) -> None:
    if not lines:
        return
    target = _resolve_topology_influx_target(topology_id)
    influx_org = target["org"]
    influx_bucket = target["bucket"]
    influx_token = target["token"]
    base_url = target["base_url"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Best-effort health check to surface infra issues early.
        try:
            health = await client.get(f"{base_url}/health")
            if health.status_code >= 400:
                raise HTTPException(status_code=409, detail=f"Topology InfluxDB unhealthy: HTTP {health.status_code}")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"Topology InfluxDB unreachable: {exc}") from exc

        url = f"{base_url}/api/v2/write"
        params = {"org": influx_org, "bucket": influx_bucket, "precision": "ns"}
        headers = {"Authorization": f"Token {influx_token}", "Content-Type": "text/plain; charset=utf-8"}
        payload = "\n".join(lines) + "\n"
        res = await client.post(url, params=params, headers=headers, content=payload)
        if res.status_code == 401 and target["mode"] == "isolated":
            # Credentials drift is common when Influx volumes already exist; attempt a best-effort repair
            # by generating a fresh operator token and syncing it back into Consul.
            try:
                await asyncio.to_thread(repair_topology_isolated_influx_auth, topology_id)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Influx auth repair failed: {exc}") from exc
            influx_token = _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_token")
            headers["Authorization"] = f"Token {influx_token}"
            res = await client.post(url, params=params, headers=headers, content=payload)
        if res.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Influx write failed: HTTP {res.status_code}: {res.text[:300]}")


def _parse_influx_annotated_csv(text: str) -> List[Dict[str, str]]:
    """
    Parse InfluxDB annotated CSV into row dicts.

    Influx returns multiple tables. Each table repeats a header row like:
      ,result,table,_start,_stop,_time,_value,_field,...
    We skip annotation lines beginning with '#'.
    """
    if not text:
        return []
    rows: List[Dict[str, str]] = []
    header: Optional[List[str]] = None

    buf = StringIO(text)
    reader = csv.reader(buf)
    for raw in reader:
        if not raw:
            header = None
            continue
        if raw[0].startswith("#"):
            continue
        if len(raw) >= 3 and raw[0] == "" and raw[1] == "result" and raw[2] == "table":
            header = raw
            continue
        if not header:
            continue
        # Row has same length as header (usually); tolerate mismatch.
        out: Dict[str, str] = {}
        for i, key in enumerate(header):
            if not key:
                continue
            out[key] = raw[i] if i < len(raw) else ""
        rows.append(out)
    return rows


def _rfc3339_to_epoch_ms(value: str) -> Optional[int]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


async def _query_influx_rows_for_topology(topology_id: str, flux_query: str) -> List[Dict[str, str]]:
    target = _resolve_topology_influx_target(topology_id)
    influx_org = target["org"]
    influx_token = target["token"]
    base_url = target["base_url"]
    url = f"{base_url}/api/v2/query"
    params = {"org": influx_org}
    headers = {"Authorization": f"Token {influx_token}", "Accept": "text/csv", "Content-Type": "application/vnd.flux"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(url, params=params, headers=headers, content=flux_query)
        if res.status_code == 401 and target["mode"] == "isolated":
            try:
                await asyncio.to_thread(repair_topology_isolated_influx_auth, topology_id)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Influx auth repair failed: {exc}") from exc
            influx_token = _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_token")
            headers["Authorization"] = f"Token {influx_token}"
            res = await client.post(url, params=params, headers=headers, content=flux_query)
        if res.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Influx query failed: HTTP {res.status_code}: {res.text[:300]}")
        return _parse_influx_annotated_csv(res.text)


def _is_safe_flux_ident(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_]+$", (value or "").strip()))


def _is_safe_flux_tag_value(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_.:\\-]+$", (value or "").strip()))


def _ms_to_rfc3339(ms: int) -> str:
    dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def repair_topology_isolated_influx_auth(topology_id: str) -> dict[str, Any]:
    """
    Repair topology-local InfluxDB credentials when volumes already exist and init env is ignored.

    Strategy:
    - Stop the topology's InfluxDB container (to unlock the boltdb file)
    - Use `influxd recovery` in a temporary container with the same volume to create/update:
      org, user password, and a fresh operator token
    - Persist that token back into Consul so other services/UI can use it
    - Restart InfluxDB and re-run `ensure_topology_isolated_infra` to refresh Grafana datasource token
    """
    if not docker_client:
        raise RuntimeError("Docker client not available")
    if TOPOLOGY_INFRA_MODE != "isolated":
        raise RuntimeError("Topology infra mode is not isolated")

    secrets_payload = _ensure_topology_isolated_infra_secrets(topology_id)
    influx_org = str(secrets_payload.get("influx_org") or "").strip()
    influx_user = str(secrets_payload.get("influx_admin_user") or "admin").strip()
    influx_password = str(secrets_payload.get("influx_admin_password") or "").strip()

    influx_container_name = _topo_container_name(topology_id, "influxdb")
    influx_volume = _topo_volume_name(topology_id, "influxdb")
    bolt_path = "/var/lib/influxdb2/influxd.bolt"

    stopped = False
    try:
        c = docker_client.containers.get(influx_container_name)
        if getattr(c, "status", "") == "running":
            c.stop(timeout=10)
            stopped = True
    except Exception:
        pass

    script = (
        "set -e\n"
        f"BOLT={shlex.quote(bolt_path)}\n"
        f"ORG={shlex.quote(influx_org)}\n"
        f"USER={shlex.quote(influx_user)}\n"
        f"PASS={shlex.quote(influx_password)}\n"
        "influxd recovery org create --bolt-path \"$BOLT\" --org \"$ORG\" >/dev/null 2>&1 || true\n"
        "influxd recovery user create --bolt-path \"$BOLT\" --username \"$USER\" --password \"$PASS\" >/dev/null 2>&1 || true\n"
        "influxd recovery user update --bolt-path \"$BOLT\" --username \"$USER\" --password \"$PASS\" >/dev/null 2>&1 || true\n"
        "influxd recovery auth create-operator --bolt-path \"$BOLT\" --org \"$ORG\" --username \"$USER\" \n"
    )

    token_out = ""
    exit_code = None
    try:
        tmp = docker_client.containers.run(
            "influxdb:2.7-alpine",
            ["sh", "-lc", script],
            detach=False,
            remove=True,
            network=MAIN_DOCKER_NETWORK,
            volumes={influx_volume: {"bind": "/var/lib/influxdb2", "mode": "rw"}},
        )
        token_out = tmp.decode("utf-8", "ignore") if isinstance(tmp, (bytes, bytearray)) else str(tmp)
        exit_code = 0
    except Exception as exc:
        token_out = str(exc)
        exit_code = 1

    # Extract token from the last row: token is the second-to-last tab-delimited column (before permissions).
    new_token = None
    try:
        lines = [ln for ln in (token_out or "").splitlines() if ln.strip()]
        last = lines[-1] if lines else ""
        cols = last.split("\t")
        if len(cols) >= 2:
            candidate = cols[-2].strip()
            # Basic sanity: must be long and not contain spaces/brackets.
            if candidate and len(candidate) >= 20 and " " not in candidate and "[" not in candidate and "]" not in candidate:
                new_token = candidate
    except Exception:
        new_token = None

    if not new_token:
        raise RuntimeError(f"Failed to recover operator token (exit={exit_code}): {token_out[:400]}")

    _consul_set(f"caduceus/topologies/{topology_id}/isolated_influx_token", new_token)

    try:
        c = docker_client.containers.get(influx_container_name)
        c.start()
    except Exception:
        pass

    # Best-effort: refresh Grafana datasource and other infra wiring to use the new token.
    try:
        ensure_topology_isolated_infra(topology_id)
    except Exception:
        pass

    return {"ok": True, "stopped": stopped, "token_updated": True}


@dataclass
class _TestRun:
    run_id: str
    topology_id: str
    suite: str
    params: Dict[str, Any]
    status: TestRunStateEnum = TestRunStateEnum.queued
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""
    steps: List[TestRunStep] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    cancel_flag: threading.Event = field(default_factory=threading.Event)


_test_runs_lock = threading.Lock()
_test_runs: Dict[str, _TestRun] = {}


def _test_log(run: _TestRun, line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    with _test_runs_lock:
        run.logs.append(text)
        if len(run.logs) > 400:
            run.logs = run.logs[-400:]


def _get_hostlike_devices(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for d in devices or []:
        dt = str(d.get("device_type") or d.get("type") or "").lower()
        if dt in ("host", "router", "station", "container"):
            out.append(d)
    return out


def _extract_ipv4_from_device(device: Dict[str, Any]) -> str:
    ip = str(device.get("ip") or "").strip()
    if ip:
        ip = ip.split("/", 1)[0].strip()
    if ip and not ip.startswith("127."):
        return ip
    for intf in (device.get("interfaces") or []):
        try:
            name = str(intf.get("name") or "")
            iip = str(intf.get("ip") or "").strip().split("/", 1)[0].strip()
            if name == "lo" or not iip or iip.startswith("127."):
                continue
            return iip
        except Exception:
            continue
    return ""


async def _run_test_suite(run: _TestRun) -> None:
    run.started_at = _iso_now()
    run.status = TestRunStateEnum.running
    suite = (run.suite or "").strip().lower()
    topology_id = run.topology_id
    ts_base = int(time.time() * 1_000_000_000)

    def _mk_step(step_id: str, name: str) -> TestRunStep:
        step = TestRunStep(step_id=step_id, name=name)
        run.steps.append(step)
        return step

    async def _write_point(measurement: str, tags: Dict[str, Any], fields: Dict[str, Any]) -> None:
        ts_ns = int(time.time() * 1_000_000_000)
        await _write_influx_lines_for_topology(topology_id, [_lp_line(measurement, tags, fields, ts_ns)])

    async def _step_start(step: TestRunStep) -> None:
        step.status = TestStepStateEnum.running
        step.started_at = _iso_now()
        await _write_point(
            "caduceus_test_step",
            {"run_id": run.run_id, "suite": suite, "step": step.step_id, "topology_id": topology_id},
            {"status": "running"},
        )

    async def _step_done(step: TestRunStep, ok: bool, message: str = "", data: Optional[Dict[str, Any]] = None) -> None:
        step.finished_at = _iso_now()
        step.status = TestStepStateEnum.completed if ok else TestStepStateEnum.failed
        step.message = message or ""
        if isinstance(data, dict):
            step.data.update(data)
        await _write_point(
            "caduceus_test_step",
            {"run_id": run.run_id, "suite": suite, "step": step.step_id, "topology_id": topology_id},
            {"status": "passed" if ok else "failed", "message": (message or "")[:240]},
        )

    async def _grpc_list_devices(grpc_client: gRPCClient) -> List[Dict[str, Any]]:
        res = await asyncio.to_thread(grpc_client.list_devices, "")
        if not res.get("success"):
            raise RuntimeError(res.get("error") or "Failed to list devices")
        return list(res.get("devices") or [])

    async def _grpc_exec(grpc_client: gRPCClient, device: str, cmd: str) -> Dict[str, Any]:
        res = await asyncio.to_thread(grpc_client.execute_command, device, cmd)
        if not res.get("success") and res.get("exit_code", 0) != 0:
            stderr = str(res.get("stderr") or "").strip()
            stdout = str(res.get("stdout") or "").strip()
            exit_code = int(res.get("exit_code") or 0)
            msg = stderr or stdout or "Command failed"
            raise RuntimeError(f"{msg} (exit_code={exit_code})")
        return res

    async def _grpc_metrics(grpc_client: gRPCClient, device_names: List[str]) -> Dict[str, Any]:
        req = emulation_pb2.GetMetricsRequest(devices=device_names, metrics=[])
        resp = await asyncio.to_thread(grpc_client.stub.GetMetrics, req, 15)
        out: Dict[str, Any] = {}
        for name, dm in (resp.device_metrics or {}).items():
            out[str(name)] = {
                "cpu_percent": float(getattr(dm, "cpu_percent", 0.0) or 0.0),
                "memory_percent": float(getattr(dm, "memory_percent", 0.0) or 0.0),
                "bytes_sent": int(getattr(dm, "bytes_sent", 0) or 0),
                "bytes_received": int(getattr(dm, "bytes_received", 0) or 0),
                "packets_sent": int(getattr(dm, "packets_sent", 0) or 0),
                "packets_received": int(getattr(dm, "packets_received", 0) or 0),
                "errors_in": int(getattr(dm, "errors_in", 0) or 0),
                "errors_out": int(getattr(dm, "errors_out", 0) or 0),
                "drops_in": int(getattr(dm, "drops_in", 0) or 0),
                "drops_out": int(getattr(dm, "drops_out", 0) or 0),
            }
        return out

    async def _write_metrics(metrics: Dict[str, Any], reason: str) -> None:
        ts_ns = int(time.time() * 1_000_000_000)
        lines: List[str] = []
        for dev, m in (metrics or {}).items():
            try:
                lines.append(
                    _lp_line(
                        "caduceus_test_metric",
                        {"run_id": run.run_id, "topology_id": topology_id, "suite": suite, "device": dev, "reason": reason},
                        m,
                        ts_ns,
                    )
                )
            except Exception:
                continue
        await _write_influx_lines_for_topology(topology_id, lines)

    async def _write_counter_deltas(
        before: Dict[str, Any],
        after: Dict[str, Any],
        reason: str,
        extra_tags: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts_ns = int(time.time() * 1_000_000_000)
        lines: List[str] = []
        for dev, a in (after or {}).items():
            b = (before or {}).get(dev) or {}
            try:
                fields = {
                    "bytes_sent_delta": int(a.get("bytes_sent", 0)) - int(b.get("bytes_sent", 0)),
                    "bytes_received_delta": int(a.get("bytes_received", 0)) - int(b.get("bytes_received", 0)),
                    "packets_sent_delta": int(a.get("packets_sent", 0)) - int(b.get("packets_sent", 0)),
                    "packets_received_delta": int(a.get("packets_received", 0)) - int(b.get("packets_received", 0)),
                    "errors_in_delta": int(a.get("errors_in", 0)) - int(b.get("errors_in", 0)),
                    "errors_out_delta": int(a.get("errors_out", 0)) - int(b.get("errors_out", 0)),
                    "drops_in_delta": int(a.get("drops_in", 0)) - int(b.get("drops_in", 0)),
                    "drops_out_delta": int(a.get("drops_out", 0)) - int(b.get("drops_out", 0)),
                }
                tags = {"run_id": run.run_id, "topology_id": topology_id, "suite": suite, "device": dev, "reason": reason}
                if isinstance(extra_tags, dict):
                    tags.update(extra_tags)
                lines.append(_lp_line("caduceus_test_counter_delta", tags, fields, ts_ns))
            except Exception:
                continue
        await _write_influx_lines_for_topology(topology_id, lines)

    try:
        # Validate emulation is running and gRPC is available (avoid stale records)
        emu_info = active_emulations.get(topology_id) or {}
        emu_id = str(emu_info.get("emulation_id") or "")
        if str(emu_info.get("status") or "").lower() not in ("running", "active") or not emu_id:
            raise HTTPException(status_code=409, detail=f"Emulation not running for topology {topology_id}; start it first.")

        grpc_client = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=None)
        status_payload = await asyncio.to_thread(grpc_client.get_status, emu_id)
        backend_status = str(status_payload.get("status") or "").lower()
        device_count = int(status_payload.get("device_count") or 0)
        if backend_status != "running" or device_count <= 0:
            update_active_emulation(emu_id, status="stopped")
            raise HTTPException(
                status_code=409,
                detail=f"Emulation backend is {backend_status or 'stopped'} (device_count={device_count}) for topology {topology_id}; start it first.",
            )

        # Step: discover devices
        step_discover = _mk_step("discover", "Discover devices")
        await _step_start(step_discover)
        devices = await _grpc_list_devices(grpc_client)
        hostlike = _get_hostlike_devices(devices)
        all_device_names = [str(d.get("runtime_name") or d.get("name") or "") for d in (devices or [])]
        all_device_names = [n for n in all_device_names if n]
        await _step_done(step_discover, True, f"Found {len(devices)} devices ({len(hostlike)} host-like).", {"device_count": len(devices)})
        _test_log(run, f"Devices: {len(devices)} total, {len(hostlike)} host-like")

        if run.cancel_flag.is_set():
            raise asyncio.CancelledError()

        async def _suite_metrics_snapshot() -> None:
            step = _mk_step("metrics_snapshot", "Metrics snapshot (all devices)")
            await _step_start(step)
            metrics = await _grpc_metrics(grpc_client, all_device_names)
            await _write_metrics(metrics, "snapshot")
            await _step_done(step, True, f"Captured snapshot for {len(metrics)} devices.", {"devices": len(metrics)})

        async def _ensure_iperf(device: str) -> None:
            await _grpc_exec(grpc_client, device, "sh -lc \"command -v iperf >/dev/null 2>&1\"")

        async def _suite_ping(src: str, dst: str, count: int) -> None:
            step = _mk_step("ping", f"Ping {src} -> {dst}")
            await _step_start(step)
            dst_dev = next((d for d in hostlike if d.get("runtime_name") == dst or d.get("name") == dst), None)
            dst_ip = _extract_ipv4_from_device(dst_dev or {})
            if not dst_ip:
                await _step_done(step, False, "Target has no IPv4 address")
                return
            cmd = f"ping -c {int(count)} -W 1 {shlex.quote(dst_ip)}"
            res = await _grpc_exec(grpc_client, src, cmd)
            out = str(res.get("stdout") or "")
            step.data["stdout"] = out[-3000:]

            loss_pct = None
            rtt_avg_ms = None
            try:
                m = re.search(r"(\d+(?:\.\d+)?)%\s*packet\s*loss", out)
                if m:
                    loss_pct = float(m.group(1))
                m2 = re.search(r"rtt\s+min/avg/max/(?:mdev|stddev)\s*=\s*([0-9.]+)/([0-9.]+)/", out)
                if m2:
                    rtt_avg_ms = float(m2.group(2))
            except Exception:
                pass

            exit_code = int(res.get("exit_code") or 0)
            ok = (exit_code == 0) and (loss_pct is None or loss_pct < 100.0)
            await _write_point(
                "caduceus_test_ping",
                {"run_id": run.run_id, "topology_id": topology_id, "suite": suite, "src": src, "dst": dst},
                {
                    "success": 1 if ok else 0,
                    "loss_pct": float(loss_pct) if loss_pct is not None else 100.0,
                    "rtt_avg_ms": float(rtt_avg_ms) if rtt_avg_ms is not None else 0.0,
                    "exit_code": exit_code,
                },
            )
            await _step_done(step, ok, "Ping completed" if ok else "Ping failed", {"loss_pct": loss_pct, "rtt_avg_ms": rtt_avg_ms})

        async def _suite_sdn_smoke() -> None:
            """
            Proof-oriented SDN check:
            - Pick a reachable host pair (src -> dst).
            - Find a switch on the dataplane path by temporarily disabling controllers in fail-mode=secure.
            - Verify ping fails without controller and recovers when controller is restored.
            """

            def _dev_type(d: Dict[str, Any]) -> str:
                return str(d.get("device_type") or d.get("type") or "").strip().lower()

            def _dev_name(d: Dict[str, Any]) -> str:
                return str(d.get("runtime_name") or d.get("name") or "").strip()

            async def _grpc_exec_allow_fail(device: str, cmd: str) -> Dict[str, Any]:
                # For proof tests we need to observe non-zero exit codes (e.g., ping failure),
                # so avoid raising on failed commands.
                return await asyncio.to_thread(grpc_client.execute_command, device, cmd)

            def _strip_cidr(ip: str) -> str:
                token = (ip or "").strip()
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", token)
                if not m:
                    return ""
                return m.group(1)

            def _score_ip(ip: str) -> int:
                if not ip:
                    return -10_000
                if ip.startswith("127."):
                    return -10_000
                if ip.startswith("10."):
                    return 100
                if ip.startswith("192.168."):
                    return 90
                if ip.startswith("172.17."):
                    return -100
                if ip.startswith("172."):
                    return 50
                return 10

            async def _best_ipv4(dev: str) -> str:
                # Prefer Mininet-like RFC1918 addresses and avoid docker-default 172.17/16 when present.
                res = await _grpc_exec_allow_fail(dev, "ip -4 -br addr")
                out = str(res.get("stdout") or "").strip()
                ips = []
                for ln in out.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    parts = ln.split()
                    if not parts:
                        continue
                    if parts[0] == "lo":
                        continue
                    if len(parts) < 3:
                        continue
                    for raw in parts[2:]:
                        ip = _strip_cidr(raw)
                        if not ip or ip.startswith("127."):
                            continue
                        ips.append(ip)
                if not ips:
                    return ""
                ips = list(dict.fromkeys(ips))
                ips.sort(key=_score_ip, reverse=True)
                return ips[0]

            async def _ping_exit_code(src: str, dst_ip: str, count: int = 1) -> int:
                res = await _grpc_exec_allow_fail(src, f"ping -c {int(count)} -W 1 {shlex.quote(dst_ip)}")
                try:
                    return int(res.get("exit_code") or 0)
                except Exception:
                    return 1

            async def _pick_reachable_pair() -> Tuple[str, str, str]:
                # Prefer "hosts" over routers for SDN dataplane proof.
                preferred = [d for d in (devices or []) if _dev_type(d) in ("host", "container", "station")]
                pool = preferred if len(preferred) >= 2 else list(hostlike or [])

                candidates: List[Tuple[str, str]] = []
                for d in pool:
                    name = _dev_name(d)
                    if not name:
                        continue
                    ip = await _best_ipv4(name)
                    if not ip:
                        continue
                    candidates.append((name, ip))

                if len(candidates) < 2:
                    raise RuntimeError("Need at least two devices with IPv4 addresses")

                for i in range(len(candidates)):
                    src, _src_ip = candidates[i]
                    for j in range(len(candidates)):
                        if j == i:
                            continue
                        dst, dst_ip = candidates[j]
                        # Ping can be flaky right after start; require at least 1 success out of a few attempts.
                        ok = False
                        for _ in range(3):
                            if run.cancel_flag.is_set():
                                break
                            if await _ping_exit_code(src, dst_ip, 1) == 0:
                                ok = True
                                break
                            await asyncio.sleep(0.5)
                        if ok:
                            return src, dst, dst_ip

                raise RuntimeError("Could not find a reachable host-to-host ping pair")

            async def _restore_switch(sw: str, controller: str, fail_mode: str) -> None:
                ctrl = (controller or "").strip()
                fm = (fail_mode or "").strip()
                if ctrl and ctrl not in ("[]", "null", "none"):
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl set-controller {sw} {ctrl}")
                else:
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl del-controller {sw}")
                if not fm or fm in ("[]", "null", "none"):
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl del-fail-mode {sw}")
                else:
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl set-fail-mode {sw} {fm}")

            step_pick = _mk_step("sdn_pick", "SDN smoke: select host pair + switches")
            await _step_start(step_pick)
            src, dst, dst_ip = await _pick_reachable_pair()
            switches = [_dev_name(d) for d in (devices or []) if _dev_type(d) == "switch" and _dev_name(d)]
            switches = list(dict.fromkeys(switches))
            if not switches:
                await _step_done(step_pick, False, "No switch devices found; SDN smoke requires OVS switches.")
                return
            await _step_done(
                step_pick,
                True,
                f"Selected {src} → {dst} and {len(switches)} switch(es).",
                {"src": src, "dst": dst, "dst_ip": dst_ip, "switches": switches},
            )

            step_enforce = _mk_step("sdn_enforce", "SDN smoke: disable controller (expect ping fail)")
            await _step_start(step_enforce)
            baseline_ok = False
            baseline_code = 1
            for _ in range(3):
                if run.cancel_flag.is_set():
                    break
                baseline_code = await _ping_exit_code(src, dst_ip, 1)
                if baseline_code == 0:
                    baseline_ok = True
                    break
                await asyncio.sleep(0.5)
            if not baseline_ok:
                await _step_done(
                    step_enforce,
                    False,
                    "Baseline ping failed; topology connectivity not stable.",
                    {"baseline_exit_code": baseline_code},
                )
                return

            selected_switch = ""
            selected_ctrl = ""
            selected_fail = ""
            ping_fail_code: Optional[int] = None
            flow_lines: Optional[int] = None

            for sw in switches:
                if run.cancel_flag.is_set():
                    raise asyncio.CancelledError()

                orig_fail = str((await _grpc_exec(grpc_client, sw, f"ovs-vsctl get-fail-mode {sw}")).get("stdout") or "").strip()
                orig_ctrl = str((await _grpc_exec(grpc_client, sw, f"ovs-vsctl get-controller {sw}")).get("stdout") or "").strip()
                if not orig_ctrl or orig_ctrl in ("[]", "null", "none"):
                    _test_log(run, f"SDN smoke: skip {sw} (no controller configured)")
                    continue

                keep_disabled = False
                try:
                    _test_log(run, f"SDN smoke: testing switch {sw} (controller={orig_ctrl}, fail_mode={orig_fail or 'unset'})")
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl set-fail-mode {sw} secure")
                    await _grpc_exec(grpc_client, sw, f"ovs-ofctl -O OpenFlow13 del-flows {sw}")
                    await _grpc_exec(grpc_client, sw, f"ovs-vsctl del-controller {sw}")
                    await asyncio.sleep(1.0)

                    code = await _ping_exit_code(src, dst_ip, 1)
                    if code == 0:
                        _test_log(run, f"SDN smoke: ping still succeeded without controller on {sw}; trying next switch.")
                        continue

                    selected_switch = sw
                    selected_ctrl = orig_ctrl
                    selected_fail = orig_fail
                    ping_fail_code = code
                    keep_disabled = True

                    try:
                        flows = await _grpc_exec(grpc_client, sw, f"ovs-ofctl -O OpenFlow13 dump-flows {sw} | wc -l")
                        raw = str(flows.get("stdout") or "").strip()
                        flow_lines = int(raw) if raw.isdigit() else None
                    except Exception:
                        flow_lines = None

                    break
                finally:
                    if not keep_disabled:
                        try:
                            await _restore_switch(sw, orig_ctrl, orig_fail)
                        except Exception:
                            pass

            if not selected_switch:
                await _step_done(
                    step_enforce,
                    False,
                    "Could not demonstrate controller enforcement with any switch (ping stayed up).",
                    {"src": src, "dst": dst, "dst_ip": dst_ip, "switches": switches},
                )
                return

            try:
                await _step_done(
                    step_enforce,
                    True,
                    f"Ping failed without controller (switch={selected_switch}, exit_code={ping_fail_code}).",
                    {"switch": selected_switch, "controller": selected_ctrl, "fail_mode": selected_fail, "ping_fail_exit_code": ping_fail_code, "flow_lines": flow_lines},
                )

                step_restore = _mk_step("sdn_restore", "SDN smoke: restore controller (expect ping success)")
                await _step_start(step_restore)
                restore_ok = False
                try:
                    await _grpc_exec(grpc_client, selected_switch, f"ovs-vsctl set-controller {selected_switch} {selected_ctrl}")
                    # Give the controller time to reconnect and re-populate flows.
                    for _ in range(30):
                        if run.cancel_flag.is_set():
                            break
                        await asyncio.sleep(1.0)
                        try:
                            if await _ping_exit_code(src, dst_ip, 1) == 0:
                                restore_ok = True
                                break
                        except Exception:
                            continue
                finally:
                    try:
                        await _restore_switch(selected_switch, selected_ctrl, selected_fail)
                    except Exception:
                        pass

                extra: Dict[str, Any] = {"switch": selected_switch, "controller": selected_ctrl, "src": src, "dst": dst, "dst_ip": dst_ip}
                if not restore_ok:
                    try:
                        info = await _grpc_exec_allow_fail(selected_switch, "ovs-vsctl list Controller")
                        extra["ovs_controller"] = str(info.get("stdout") or "")[-4000:]
                    except Exception:
                        pass
                    try:
                        flows = await _grpc_exec_allow_fail(selected_switch, f"ovs-ofctl -O OpenFlow13 dump-flows {selected_switch} | wc -l")
                        extra["flow_lines_after_restore"] = str(flows.get("stdout") or "").strip()
                    except Exception:
                        pass

                await _step_done(
                    step_restore,
                    restore_ok,
                    "Ping recovered after restoring controller." if restore_ok else "Ping did not recover after restoring controller.",
                    extra,
                )
            finally:
                try:
                    await _restore_switch(selected_switch, selected_ctrl, selected_fail)
                except Exception:
                    pass

        async def _suite_mano_local_smoke() -> None:
            """
            Proof-oriented MANO check (local NFVO/VNFM):
            - Create a local NS instance (does not require NSD).
            - Create a container VNF instance (dockerized alpine).
            - Verify the VNF appears in the emulation device list.
            - Exec a command in the VNF and verify stdout.
            - Delete the VNF and verify it disappears.

            Note: We intentionally avoid terminating the local NS by default because the current
            local NS termination maps to stopping the whole emulation (too disruptive for a smoke test).
            """

            mano_url = (os.getenv("MANO_SERVICE_URL", "http://mano-service:8015") or "").rstrip("/")
            if not mano_url:
                raise RuntimeError("MANO_SERVICE_URL is not configured")

            docker_image = str(run.params.get("docker_image") or "alpine:3.19").strip() or "alpine:3.19"
            container_cmd = str(run.params.get("command") or "sleep 36000").strip() or "sleep 36000"
            terminate_ns = bool(run.params.get("terminate_ns") or False)

            suffix = (run.run_id or uuid.uuid4().hex)[:10]
            ns_name = str(run.params.get("ns_name") or f"smoke-ns-{suffix}")
            vnf_name = str(run.params.get("vnf_name") or f"smoke-vnf-{suffix}")

            ns_id: Optional[str] = None
            vnf_id: Optional[str] = None
            vnf_device_name: Optional[str] = None

            async def _http_json(
                client: httpx.AsyncClient,
                method: str,
                url: str,
                *,
                json_body: Optional[dict] = None,
                params: Optional[dict] = None,
            ) -> dict:
                resp = await client.request(method.upper(), url, json=json_body, params=params)
                resp.raise_for_status()
                if not resp.content:
                    return {}
                try:
                    return resp.json()
                except Exception:
                    return {"raw": resp.text}

            async def _device_exists(name: str) -> bool:
                if not name:
                    return False
                latest = await _grpc_list_devices(grpc_client)
                for d in latest or []:
                    runtime = str(d.get("runtime_name") or "").strip()
                    display = str(d.get("name") or "").strip()
                    if runtime == name or display == name:
                        return True
                return False

            step_create_ns = _mk_step("mano_ns_create", "MANO smoke: create local NS instance")
            await _step_start(step_create_ns)
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                try:
                    data = await _http_json(
                        client,
                        "POST",
                        f"{mano_url}/api/ns-instances",
                        json_body={
                            "name": ns_name,
                            "topology_id": topology_id,
                            "nsd_id": None,
                            "backend": "local",
                            "dry_run": False,
                            "options": {},
                        },
                    )
                    ns_id = str(data.get("id") or "").strip() or None
                    status = str(data.get("status") or "").strip()
                    if not ns_id:
                        raise RuntimeError("mano-service did not return NS id")
                    ok = status.upper() in ("RUNNING", "CREATED", "INSTANTIATING")
                    await _step_done(
                        step_create_ns,
                        ok,
                        f"NS created (id={ns_id[:12]}, status={status or 'unknown'})",
                        {"ns_id": ns_id, "ns_status": status, "mano_url": mano_url},
                    )
                    if not ok:
                        return
                except Exception as exc:
                    await _step_done(step_create_ns, False, f"Failed to create NS: {exc}")
                    return

            step_create_vnf = _mk_step("mano_vnf_create", "MANO smoke: create VNF (container)")
            await _step_start(step_create_vnf)
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                try:
                    data = await _http_json(
                        client,
                        "POST",
                        f"{mano_url}/api/vnfm/vnf-instances",
                        json_body={
                            "ns_instance_id": ns_id,
                            "vnfd_id": None,
                            "name": vnf_name,
                            "device_type": "container",
                            "device_name": None,
                            "properties": {"dockerized": True, "docker_image": docker_image, "command": container_cmd},
                            "dry_run": False,
                        },
                    )
                    vnf_id = str(data.get("id") or "").strip() or None
                    vnf_device_name = str(data.get("device_name") or vnf_name).strip() or vnf_name
                    status = str(data.get("status") or "").strip()
                    if not vnf_id:
                        raise RuntimeError("mano-service did not return VNF id")
                    await _step_done(
                        step_create_vnf,
                        status.upper() in ("RUNNING", "CREATED"),
                        f"VNF created (id={vnf_id[:12]}, device={vnf_device_name}, status={status or 'unknown'})",
                        {"vnf_id": vnf_id, "vnf_device": vnf_device_name, "docker_image": docker_image},
                    )
                except Exception as exc:
                    await _step_done(step_create_vnf, False, f"Failed to create VNF: {exc}")
                    return

            step_verify_add = _mk_step("mano_verify_add", "MANO smoke: verify VNF appears in emulation")
            await _step_start(step_verify_add)
            appeared = False
            for _ in range(30):
                if run.cancel_flag.is_set():
                    break
                try:
                    if await _device_exists(vnf_device_name or ""):
                        appeared = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(1.0)
            await _step_done(
                step_verify_add,
                appeared,
                "VNF device present in emulation." if appeared else "VNF device not found in emulation device list.",
                {"device": vnf_device_name},
            )
            if not appeared:
                return

            step_exec = _mk_step("mano_vnf_exec", "MANO smoke: exec inside VNF")
            await _step_start(step_exec)
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                try:
                    data = await _http_json(
                        client,
                        "POST",
                        f"{mano_url}/api/vnfm/vnf-instances/{vnf_id}/exec",
                        json_body={"command": "echo smoke-ok"},
                    )
                    result = data.get("result") if isinstance(data, dict) else None
                    stdout = str((result or {}).get("stdout") or "")
                    output = str((result or {}).get("output") or "")
                    stderr = str((result or {}).get("stderr") or "")
                    combined = (stdout or output or "") + (stderr or "")
                    ok = "smoke-ok" in combined
                    await _step_done(
                        step_exec,
                        ok,
                        "Exec returned expected output." if ok else "Exec did not return expected output.",
                        {"output": combined[-2000:]},
                    )
                except Exception as exc:
                    await _step_done(step_exec, False, f"Exec failed: {exc}")
                    # Continue with cleanup.

            step_delete = _mk_step("mano_vnf_delete", "MANO smoke: delete VNF")
            await _step_start(step_delete)
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                try:
                    data = await _http_json(
                        client,
                        "DELETE",
                        f"{mano_url}/api/vnfm/vnf-instances/{vnf_id}",
                        params={"force": "true"},
                    )
                    await _step_done(step_delete, bool(data.get("ok", True)), "Delete requested", {"response": data})
                except Exception as exc:
                    await _step_done(step_delete, False, f"Delete failed: {exc}")
                    return

            step_verify_rm = _mk_step("mano_verify_remove", "MANO smoke: verify VNF disappears")
            await _step_start(step_verify_rm)
            removed = False
            for _ in range(30):
                if run.cancel_flag.is_set():
                    break
                try:
                    if not await _device_exists(vnf_device_name or ""):
                        removed = True
                        break
                except Exception:
                    removed = True
                    break
                await asyncio.sleep(1.0)
            await _step_done(
                step_verify_rm,
                removed,
                "VNF device removed from emulation." if removed else "VNF device still present after delete.",
                {"device": vnf_device_name},
            )

            if terminate_ns and ns_id:
                step_term = _mk_step("mano_ns_terminate", "MANO smoke: terminate NS (optional)")
                await _step_start(step_term)
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    try:
                        data = await _http_json(
                            client,
                            "POST",
                            f"{mano_url}/api/ns-instances/{ns_id}/terminate",
                            json_body={"reason": "mano smoke test"},
                        )
                        await _step_done(step_term, bool(data.get("ok", False)), "Terminate requested", {"response": data})
                    except Exception as exc:
                        await _step_done(step_term, False, f"Terminate failed: {exc}")

        async def _suite_iperf_tcp(src: str, dst: str, seconds: int, parallel: int) -> None:
            step = _mk_step("iperf_tcp", f"iperf TCP {src} -> {dst}")
            await _step_start(step)
            before = await _grpc_metrics(grpc_client, all_device_names)
            dst_dev = next((d for d in hostlike if d.get("runtime_name") == dst or d.get("name") == dst), None)
            dst_ip = _extract_ipv4_from_device(dst_dev or {})
            if not dst_ip:
                await _step_done(step, False, "Target has no IPv4 address")
                return
            port = int(run.params.get("port") or 5001)
            # gRPC execute_command has ~20s timeout; keep iperf runs short unless we implement async exec.
            seconds = int(max(1, min(15, seconds)))
            parallel = int(max(1, min(16, parallel)))

            try:
                await _ensure_iperf(src)
                await _ensure_iperf(dst)
            except Exception:
                await _step_done(step, False, "iperf is not installed on one or both devices")
                return

            await _grpc_exec(
                grpc_client,
                dst,
                f"sh -lc \"if [ -f /tmp/caduceus_iperf_server.pid ]; then kill -9 $(cat /tmp/caduceus_iperf_server.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_iperf_server.pid; fi; "
                f"nohup iperf -s -p {port} >/tmp/caduceus_iperf_server.log 2>&1 & echo $! > /tmp/caduceus_iperf_server.pid\"",
            )
            res = await _grpc_exec(grpc_client, src, f"iperf -c {shlex.quote(dst_ip)} -p {port} -t {seconds} -P {parallel}")
            out = str(res.get("stdout") or "")
            step.data["stdout"] = out[-4000:]

            throughput_mbps = 0.0
            try:
                lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
                for ln in reversed(lines[-12:]):
                    m = re.search(r"\s([0-9.]+)\s+([KMG])bits/sec", ln)
                    if m:
                        val = float(m.group(1))
                        unit = m.group(2)
                        if unit == "K":
                            throughput_mbps = val / 1000.0
                        elif unit == "M":
                            throughput_mbps = val
                        elif unit == "G":
                            throughput_mbps = val * 1000.0
                        break
            except Exception:
                pass

            await _write_point(
                "caduceus_test_iperf",
                {"run_id": run.run_id, "topology_id": topology_id, "suite": suite, "src": src, "dst": dst, "proto": "tcp"},
                {"throughput_mbps": float(throughput_mbps), "seconds": int(seconds), "parallel": int(parallel)},
            )
            await _grpc_exec(
                grpc_client,
                dst,
                "sh -lc \"if [ -f /tmp/caduceus_iperf_server.pid ]; then kill -9 $(cat /tmp/caduceus_iperf_server.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_iperf_server.pid; fi\"",
            )
            after = await _grpc_metrics(grpc_client, all_device_names)
            await _write_counter_deltas(before, after, "iperf_tcp", {"src": src, "dst": dst})
            ok = throughput_mbps > 0.0
            await _step_done(step, ok, "iperf completed" if ok else "iperf failed to measure throughput", {"throughput_mbps": throughput_mbps})

        async def _suite_iperf_udp(src: str, dst: str, seconds: int, bandwidth_mbps: float, packet_size: int) -> None:
            step = _mk_step("iperf_udp", f"iperf UDP {src} -> {dst}")
            await _step_start(step)
            before = await _grpc_metrics(grpc_client, all_device_names)
            dst_dev = next((d for d in hostlike if d.get("runtime_name") == dst or d.get("name") == dst), None)
            dst_ip = _extract_ipv4_from_device(dst_dev or {})
            if not dst_ip:
                await _step_done(step, False, "Target has no IPv4 address")
                return
            port = int(run.params.get("port") or 5001)
            seconds = int(max(1, min(15, seconds)))
            bandwidth_mbps = float(max(0.1, min(5000.0, bandwidth_mbps)))
            packet_size = int(max(64, min(65507, packet_size)))

            try:
                await _ensure_iperf(src)
                await _ensure_iperf(dst)
            except Exception:
                await _step_done(step, False, "iperf is not installed on one or both devices")
                return

            await _grpc_exec(
                grpc_client,
                dst,
                f"sh -lc \"if [ -f /tmp/caduceus_iperf_server.pid ]; then kill -9 $(cat /tmp/caduceus_iperf_server.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_iperf_server.pid; fi; "
                f"nohup iperf -s -u -p {port} >/tmp/caduceus_iperf_server.log 2>&1 & echo $! > /tmp/caduceus_iperf_server.pid\"",
            )
            res = await _grpc_exec(
                grpc_client,
                src,
                f"iperf -c {shlex.quote(dst_ip)} -u -p {port} -t {seconds} -b {bandwidth_mbps}M -l {packet_size}",
            )
            out = str(res.get("stdout") or "")
            step.data["stdout"] = out[-4000:]

            throughput_mbps = 0.0
            jitter_ms = 0.0
            loss_pct = 0.0
            lost = 0
            total = 0
            try:
                lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
                for ln in reversed(lines[-20:]):
                    m = re.search(
                        r"\s([0-9.]+)\s+([KMG])bits/sec\s+([0-9.]+)\s+ms\s+(\d+)\s*/\s*(\d+)\s*\((\d+(?:\.\d+)?)%\)",
                        ln,
                    )
                    if m:
                        val = float(m.group(1))
                        unit = m.group(2)
                        if unit == "K":
                            throughput_mbps = val / 1000.0
                        elif unit == "M":
                            throughput_mbps = val
                        elif unit == "G":
                            throughput_mbps = val * 1000.0
                        jitter_ms = float(m.group(3))
                        lost = int(m.group(4))
                        total = int(m.group(5))
                        loss_pct = float(m.group(6))
                        break
            except Exception:
                pass

            await _write_point(
                "caduceus_test_iperf",
                {"run_id": run.run_id, "topology_id": topology_id, "suite": suite, "src": src, "dst": dst, "proto": "udp"},
                {
                    "throughput_mbps": float(throughput_mbps),
                    "seconds": int(seconds),
                    "bandwidth_mbps": float(bandwidth_mbps),
                    "packet_size": int(packet_size),
                    "jitter_ms": float(jitter_ms),
                    "loss_pct": float(loss_pct),
                    "lost": int(lost),
                    "total": int(total),
                },
            )
            await _grpc_exec(
                grpc_client,
                dst,
                "sh -lc \"if [ -f /tmp/caduceus_iperf_server.pid ]; then kill -9 $(cat /tmp/caduceus_iperf_server.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_iperf_server.pid; fi\"",
            )
            after = await _grpc_metrics(grpc_client, all_device_names)
            await _write_counter_deltas(before, after, "iperf_udp", {"src": src, "dst": dst})
            ok = throughput_mbps > 0.0 and (total == 0 or loss_pct < 100.0)
            await _step_done(
                step,
                ok,
                "iperf UDP completed" if ok else "iperf UDP failed to measure throughput",
                {"throughput_mbps": throughput_mbps, "jitter_ms": jitter_ms, "loss_pct": loss_pct},
            )

        async def _suite_cpu_stress_all(duration_s: int, workers_per_device: int = 1, sample_interval_s: float = 1.0) -> None:
            step = _mk_step("cpu_stress", f"CPU stress (yes) for {duration_s}s")
            await _step_start(step)
            targets = [str(d.get("runtime_name") or d.get("name") or "") for d in hostlike]
            targets = [t for t in targets if t]
            if not targets:
                await _step_done(step, False, "No host-like devices found")
                return

            duration_s = int(max(3, min(120, duration_s)))
            workers_per_device = int(max(1, min(8, workers_per_device)))
            sample_interval_s = float(max(0.5, min(5.0, sample_interval_s)))
            started = 0
            try:
                for dev in targets:
                    await _grpc_exec(
                        grpc_client,
                        dev,
                        "sh -lc "
                        + shlex.quote(
                            f"rm -f /tmp/caduceus_cpustress.pids; "
                            f"for i in $(seq 1 {workers_per_device}); do nohup yes >/dev/null 2>&1 & echo $! >> /tmp/caduceus_cpustress.pids; done"
                        ),
                    )
                    started += 1
                samples = 0
                start_ts = time.time()
                while (time.time() - start_ts) < duration_s:
                    if run.cancel_flag.is_set():
                        break
                    metrics = await _grpc_metrics(grpc_client, targets)
                    await _write_metrics(metrics, "cpu_stress")
                    samples += 1
                    await asyncio.sleep(sample_interval_s)
                await _step_done(
                    step,
                    True,
                    "CPU stress completed",
                    {"duration_s": duration_s, "devices": started, "samples": samples, "workers_per_device": workers_per_device},
                )
            finally:
                for dev in targets:
                    try:
                        await _grpc_exec(
                            grpc_client,
                            dev,
                            "sh -lc \"if [ -f /tmp/caduceus_cpustress.pids ]; then xargs -r kill -9 < /tmp/caduceus_cpustress.pids >/dev/null 2>&1 || true; rm -f /tmp/caduceus_cpustress.pids; fi; pkill -9 yes >/dev/null 2>&1 || true\"",
                        )
                    except Exception:
                        pass

        async def _suite_cpu_stress_stop() -> None:
            step = _mk_step("cpu_stress_stop", "Stop CPU stress")
            await _step_start(step)
            targets = [str(d.get("runtime_name") or d.get("name") or "") for d in hostlike]
            targets = [t for t in targets if t]
            for dev in targets:
                try:
                    await _grpc_exec(
                        grpc_client,
                        dev,
                        "sh -lc \"if [ -f /tmp/caduceus_cpustress.pids ]; then xargs -r kill -9 < /tmp/caduceus_cpustress.pids >/dev/null 2>&1 || true; rm -f /tmp/caduceus_cpustress.pids; fi; pkill -9 yes >/dev/null 2>&1 || true\"",
                    )
                except Exception:
                    pass
            await _step_done(step, True, "Stopped CPU stress on devices", {"devices": len(targets)})

        async def _suite_memory_stress_all(duration_s: int, mb_per_device: int, sample_interval_s: float = 1.0) -> None:
            step = _mk_step("memory_stress", f"Memory stress for {duration_s}s")
            await _step_start(step)
            targets = [str(d.get("runtime_name") or d.get("name") or "") for d in hostlike]
            targets = [t for t in targets if t]
            if not targets:
                await _step_done(step, False, "No host-like devices found")
                return

            duration_s = int(max(3, min(120, duration_s)))
            mb_per_device = int(max(16, min(4096, mb_per_device)))
            sample_interval_s = float(max(0.5, min(5.0, sample_interval_s)))
            py = (
                "import os,time;"
                "#caduceus_memstress\n"
                "mb=int(os.getenv('MB','128'));"
                "d=int(os.getenv('DURATION','30'));"
                "a=[bytearray(1024*1024) for _ in range(mb)];"
                "time.sleep(d)"
            )

            started = 0
            try:
                for dev in targets:
                    cmd = (
                        "sh -lc "
                        + shlex.quote(
                            f"MB={mb_per_device} DURATION={duration_s} nohup python3 -c {shlex.quote(py)} >/dev/null 2>&1 & echo $! > /tmp/caduceus_memstress.pid"
                        )
                    )
                    await _grpc_exec(grpc_client, dev, cmd)
                    started += 1
                samples = 0
                start_ts = time.time()
                while (time.time() - start_ts) < duration_s:
                    if run.cancel_flag.is_set():
                        break
                    metrics = await _grpc_metrics(grpc_client, targets)
                    await _write_metrics(metrics, "memory_stress")
                    samples += 1
                    await asyncio.sleep(sample_interval_s)
                await _step_done(
                    step,
                    True,
                    "Memory stress completed",
                    {"duration_s": duration_s, "devices": started, "samples": samples, "mb_per_device": mb_per_device},
                )
            finally:
                for dev in targets:
                    try:
                        await _grpc_exec(
                            grpc_client,
                            dev,
                            "sh -lc \"if [ -f /tmp/caduceus_memstress.pid ]; then kill -9 $(cat /tmp/caduceus_memstress.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_memstress.pid; fi; pkill -f caduceus_memstress >/dev/null 2>&1 || true\"",
                        )
                    except Exception:
                        pass

        async def _suite_memory_stress_stop() -> None:
            step = _mk_step("memory_stress_stop", "Stop memory stress")
            await _step_start(step)
            targets = [str(d.get("runtime_name") or d.get("name") or "") for d in hostlike]
            targets = [t for t in targets if t]
            for dev in targets:
                try:
                    await _grpc_exec(
                        grpc_client,
                        dev,
                        "sh -lc \"if [ -f /tmp/caduceus_memstress.pid ]; then kill -9 $(cat /tmp/caduceus_memstress.pid) >/dev/null 2>&1 || true; rm -f /tmp/caduceus_memstress.pid; fi; pkill -f caduceus_memstress >/dev/null 2>&1 || true\"",
                    )
                except Exception:
                    pass
            await _step_done(step, True, "Stopped memory stress on devices", {"devices": len(targets)})

        # Suite selection
        if suite == "metrics_snapshot":
            await _suite_metrics_snapshot()
        elif suite == "ping":
            src = str(run.params.get("src") or "")
            dst = str(run.params.get("dst") or "")
            count = int(run.params.get("count") or 3)
            if not (src and dst):
                raise HTTPException(status_code=400, detail="ping suite requires params.src and params.dst")
            await _suite_ping(src, dst, count)
        elif suite == "iperf_tcp":
            src = str(run.params.get("src") or "")
            dst = str(run.params.get("dst") or "")
            seconds = int(run.params.get("seconds") or 10)
            parallel = int(run.params.get("parallel") or 1)
            if not (src and dst):
                raise HTTPException(status_code=400, detail="iperf_tcp suite requires params.src and params.dst")
            await _suite_iperf_tcp(src, dst, seconds, parallel)
        elif suite == "iperf_udp":
            src = str(run.params.get("src") or "")
            dst = str(run.params.get("dst") or "")
            seconds = int(run.params.get("seconds") or 10)
            bandwidth_mbps = float(run.params.get("bandwidth_mbps") or 10.0)
            packet_size = int(run.params.get("packet_size") or 1400)
            if not (src and dst):
                raise HTTPException(status_code=400, detail="iperf_udp suite requires params.src and params.dst")
            await _suite_iperf_udp(src, dst, seconds, bandwidth_mbps, packet_size)
        elif suite == "sdn_smoke":
            await _suite_sdn_smoke()
        elif suite == "mano_local_smoke":
            await _suite_mano_local_smoke()
        elif suite == "cpu_stress":
            duration_s = int(run.params.get("duration_s") or 10)
            workers = int(run.params.get("workers_per_device") or run.params.get("cpu_workers_per_device") or 1)
            interval_s = float(run.params.get("sample_interval_s") or 1.0)
            await _suite_cpu_stress_all(duration_s, workers_per_device=workers, sample_interval_s=interval_s)
        elif suite == "cpu_stress_stop":
            await _suite_cpu_stress_stop()
        elif suite == "memory_stress":
            duration_s = int(run.params.get("duration_s") or 10)
            mb_per_device = int(run.params.get("mb_per_device") or 256)
            interval_s = float(run.params.get("sample_interval_s") or 1.0)
            await _suite_memory_stress_all(duration_s, mb_per_device, sample_interval_s=interval_s)
        elif suite == "memory_stress_stop":
            await _suite_memory_stress_stop()
        else:
            # full suite
            step_preflight = _mk_step("preflight", "Preflight checks")
            await _step_start(step_preflight)
            if len(hostlike) < 2:
                await _step_done(step_preflight, False, "Need at least two host-like devices to run full tests.")
                raise RuntimeError("Not enough devices")
            await _step_done(step_preflight, True, "Preflight OK")

            await _suite_metrics_snapshot()

            # Ping matrix (host-like)
            step_matrix = _mk_step("ping_matrix", "Ping matrix (host-like)")
            await _step_start(step_matrix)
            successes = 0
            total = 0
            for s in hostlike:
                if run.cancel_flag.is_set():
                    break
                src = str(s.get("runtime_name") or s.get("name") or "")
                if not src:
                    continue
                for d in hostlike:
                    dst = str(d.get("runtime_name") or d.get("name") or "")
                    if not dst or dst == src:
                        continue
                    total += 1
                    try:
                        await _suite_ping(src, dst, int(run.params.get("ping_matrix_count") or 1))
                        successes += 1
                    except Exception:
                        pass
            await _step_done(step_matrix, True, f"Ping matrix done: {successes}/{max(1,total)} pairs ok", {"pairs": total, "ok": successes})

            # iperf TCP/UDP between first two devices
            first = str(hostlike[0].get("runtime_name") or hostlike[0].get("name") or "")
            second = str(hostlike[1].get("runtime_name") or hostlike[1].get("name") or "")
            await _suite_iperf_tcp(first, second, int(run.params.get("seconds") or 10), int(run.params.get("parallel") or 1))
            await _suite_iperf_udp(first, second, int(run.params.get("udp_seconds") or 10), float(run.params.get("bandwidth_mbps") or 10.0), int(run.params.get("packet_size") or 1400))

            # Stress sampling
            workers = int(run.params.get("cpu_workers_per_device") or 1)
            interval_s = float(run.params.get("sample_interval_s") or 1.0)
            await _suite_cpu_stress_all(int(run.params.get("cpu_duration_s") or 10), workers_per_device=workers, sample_interval_s=interval_s)
            await _suite_memory_stress_all(int(run.params.get("mem_duration_s") or 10), int(run.params.get("mb_per_device") or 256), sample_interval_s=interval_s)

        if run.cancel_flag.is_set():
            run.status = TestRunStateEnum.canceled
            run.message = "Canceled"
        else:
            failed_steps = [s for s in run.steps if getattr(s, "status", None) == TestStepStateEnum.failed]
            if failed_steps:
                first = failed_steps[0]
                run.status = TestRunStateEnum.failed
                run.message = (first.message or "").strip() or f"Failed at step {first.step_id}"
            else:
                run.status = TestRunStateEnum.completed
                run.message = "Completed"
        run.finished_at = _iso_now()
        await _write_influx_lines_for_topology(
            topology_id,
            [
                _lp_line(
                    "caduceus_test_run",
                    {"run_id": run.run_id, "topology_id": topology_id, "suite": suite},
                    {"status": str(run.status), "message": (run.message or "")[:240]},
                    ts_base,
                )
            ],
        )

    except asyncio.CancelledError:
        run.status = TestRunStateEnum.canceled
        run.message = "Canceled"
        run.finished_at = _iso_now()
    except HTTPException as exc:
        run.status = TestRunStateEnum.failed
        run.message = str(exc.detail)
        run.finished_at = _iso_now()
    except Exception as exc:
        run.status = TestRunStateEnum.failed
        run.message = str(exc)
        run.finished_at = _iso_now()


app = FastAPI(
    title="Caduceus-Flux Emulation Orchestrator Service",
    description="Manages emulation lifecycle and gRPC communication",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/diagnostics/{topology_id}/influx/features", response_model=InfluxDiagnosticsFeaturesResponse)
async def get_influx_diagnostics_features(topology_id: str):
    """
    Return available field keys and common tag values for topology-local InfluxDB.
    Used by the Diagnostics UI to build filters and selectors.
    """
    topology_id = (topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    influx_bucket = _resolve_topology_influx_target(topology_id)["bucket"]

    measurement = "network_metrics"
    topo_filter = _shared_topology_flux_filter(topology_id)

    def _extract_values(rows: List[Dict[str, str]]) -> List[str]:
        out: List[str] = []
        for r in rows:
            v = (r.get("_value") or r.get("value") or r.get("fieldKey") or r.get("tagValue") or "").strip()
            if v:
                out.append(v)
        out = list(dict.fromkeys(out))
        out.sort()
        return out

    fields_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        ' |> range(start: -30d)'
        f' |> filter(fn: (r) => r._measurement == "{_flux_escape_str(measurement)}")'
        f" {topo_filter}"
        ' |> keep(columns: ["_field"])'
        ' |> group()'
        ' |> distinct(column: "_field")'
        ' |> sort(columns: ["_value"])'
    )
    devices_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        ' |> range(start: -30d)'
        f' |> filter(fn: (r) => r._measurement == "{_flux_escape_str(measurement)}")'
        f" {topo_filter}"
        ' |> keep(columns: ["device"])'
        ' |> filter(fn: (r) => exists r.device)'
        ' |> group()'
        ' |> distinct(column: "device")'
        ' |> sort(columns: ["_value"])'
    )
    sources_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        ' |> range(start: -30d)'
        f' |> filter(fn: (r) => r._measurement == "{_flux_escape_str(measurement)}")'
        f" {topo_filter}"
        ' |> keep(columns: ["source"])'
        ' |> filter(fn: (r) => exists r.source)'
        ' |> group()'
        ' |> distinct(column: "source")'
        ' |> sort(columns: ["_value"])'
    )
    emu_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        ' |> range(start: -30d)'
        f' |> filter(fn: (r) => r._measurement == "{_flux_escape_str(measurement)}")'
        f" {topo_filter}"
        ' |> keep(columns: ["emulation_id"])'
        ' |> filter(fn: (r) => exists r.emulation_id)'
        ' |> group()'
        ' |> distinct(column: "emulation_id")'
        ' |> sort(columns: ["_value"])'
    )

    fields_rows = await _query_influx_rows_for_topology(topology_id, fields_flux)
    devices_rows = await _query_influx_rows_for_topology(topology_id, devices_flux)
    sources_rows = await _query_influx_rows_for_topology(topology_id, sources_flux)
    emu_rows = await _query_influx_rows_for_topology(topology_id, emu_flux)

    return InfluxDiagnosticsFeaturesResponse(
        topology_id=topology_id,
        bucket=influx_bucket,
        measurement=measurement,
        fields=_extract_values(fields_rows),
        devices=_extract_values(devices_rows),
        sources=_extract_values(sources_rows),
        emulation_ids=_extract_values(emu_rows),
    )


@app.post("/api/diagnostics/{topology_id}/influx/query", response_model=InfluxDiagnosticsQueryResponse)
async def query_influx_diagnostics(topology_id: str, req: InfluxDiagnosticsQueryRequest):
    """
    Query topology-local InfluxDB `network_metrics` with user-selected fields + time window.
    Returns a time series suitable for charting.
    """
    topology_id = (topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    influx_bucket = _resolve_topology_influx_target(topology_id)["bucket"]

    measurement = "network_metrics"

    every_seconds = int(req.every_seconds or 5)
    every_seconds = max(1, min(3600, every_seconds))

    # Validate/sanitize inputs used in Flux string interpolation.
    fields = [f.strip() for f in (req.fields or []) if str(f or "").strip()]
    if fields:
        bad = [f for f in fields if not _is_safe_flux_ident(f)]
        if bad:
            raise HTTPException(status_code=400, detail=f"Invalid field(s): {', '.join(bad[:10])}")
    else:
        fields = ["cpu_percent", "memory_percent", "bytes_sent", "bytes_received", "packets_sent", "packets_received"]

    device = (req.device or "").strip() or None
    source = (req.source or "").strip() or None
    emulation_id = (req.emulation_id or "").strip() or None
    for k, v in (("device", device), ("source", source), ("emulation_id", emulation_id)):
        if v and not _is_safe_flux_tag_value(v):
            raise HTTPException(status_code=400, detail=f"Invalid {k} filter")

    start_ms = req.start_ms
    end_ms = req.end_ms
    if (start_ms is None) != (end_ms is None):
        raise HTTPException(status_code=400, detail="Provide both start_ms and end_ms (or neither).")
    if start_ms is not None and end_ms is not None:
        if end_ms <= start_ms:
            raise HTTPException(status_code=400, detail="end_ms must be > start_ms")
        # Clamp range to 14 days max to avoid runaway queries.
        if (end_ms - start_ms) > 14 * 24 * 60 * 60 * 1000:
            raise HTTPException(status_code=400, detail="Time range too large (max 14 days)")
        range_expr = f'range(start: time(v: "{_ms_to_rfc3339(start_ms)}"), stop: time(v: "{_ms_to_rfc3339(end_ms)}"))'
    else:
        window_minutes = int(req.window_minutes or 60)
        window_minutes = int(max(5, min(14 * 24 * 60, window_minutes)))
        range_expr = f'range(start: -{window_minutes}m)'

    field_filter = " or ".join([f'r._field == "{f}"' for f in fields])
    keep_cols = ",".join(['"_time"', '"device"', '"source"', '"emulation_id"'] + [f'"{f}"' for f in fields])

    parts = [
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")',
        f"|> {range_expr}",
        f'|> filter(fn: (r) => r._measurement == "{_flux_escape_str(measurement)}")',
        f"|> filter(fn: (r) => {field_filter})",
    ]
    if TOPOLOGY_INFRA_MODE != "isolated":
        parts.append(f'|> filter(fn: (r) => exists r.topology_id and r.topology_id == "{_flux_escape_str(topology_id)}")')
    if device:
        parts.append(f'|> filter(fn: (r) => r.device == "{_flux_escape_str(device)}")')
    if source:
        parts.append(f'|> filter(fn: (r) => r.source == "{_flux_escape_str(source)}")')
    if emulation_id:
        parts.append(f'|> filter(fn: (r) => r.emulation_id == "{_flux_escape_str(emulation_id)}")')

    parts.extend(
        [
            f"|> aggregateWindow(every: {every_seconds}s, fn: mean, createEmpty: false)",
            '|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")',
            f"|> keep(columns: [{keep_cols}])",
            '|> sort(columns: ["_time"])',
            "|> limit(n: 3000)",
        ]
    )
    flux = " ".join(parts)

    rows = await _query_influx_rows_for_topology(topology_id, flux)
    points: List[Dict[str, Any]] = []

    def _to_num(val: str) -> Optional[float]:
        try:
            if val is None:
                return None
            raw = str(val).strip()
            if raw == "":
                return None
            return float(raw)
        except Exception:
            return None

    for row in rows:
        ts = _rfc3339_to_epoch_ms(row.get("_time") or "")
        if ts is None:
            continue
        p: Dict[str, Any] = {
            "t": ts,
            "device": (row.get("device") or "").strip() or None,
            "source": (row.get("source") or "").strip() or None,
            "emulation_id": (row.get("emulation_id") or "").strip() or None,
        }
        for f in fields:
            n = _to_num(row.get(f) or "")
            if n is not None:
                p[f] = n
        points.append(p)

    return InfluxDiagnosticsQueryResponse(
        topology_id=topology_id,
        bucket=influx_bucket,
        measurement=measurement,
        every_seconds=every_seconds,
        start_ms=start_ms,
        end_ms=end_ms,
        device=device,
        source=source,
        emulation_id=emulation_id,
        fields=fields,
        points=points,
    )


@app.post("/api/tests/run", response_model=TestRunStatusResponse)
async def run_tests_endpoint(request: TestRunRequest):
    topology_id = request.topology_id
    suite = (request.suite or "").strip().lower() or "full"
    emu_info = active_emulations.get(topology_id) or {}
    emu_id = str(emu_info.get("emulation_id") or "")
    if str(emu_info.get("status") or "").lower() not in ("running", "active") or not emu_id:
        raise HTTPException(status_code=409, detail=f"Emulation not running for topology {topology_id}; start it first.")

    # Cross-check with gRPC backend to avoid stale "running" records.
    try:
        grpc_client = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=None)
        status_payload = await asyncio.to_thread(grpc_client.get_status, emu_id)
        backend_status = str(status_payload.get("status") or "").lower()
        device_count = int(status_payload.get("device_count") or 0)
        if backend_status != "running" or device_count <= 0:
            update_active_emulation(emu_id, status="stopped")
            raise HTTPException(
                status_code=409,
                detail=f"Emulation backend is {backend_status or 'stopped'} (device_count={device_count}) for topology {topology_id}; start it first.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to validate emulation backend: {exc}") from exc
    run_id = f"testrun-{uuid.uuid4()}"
    run = _TestRun(run_id=run_id, topology_id=topology_id, suite=suite, params=dict(request.params or {}))

    with _test_runs_lock:
        _test_runs[run_id] = run

    asyncio.create_task(_run_test_suite(run))
    return TestRunStatusResponse(**{
        "run_id": run.run_id,
        "topology_id": run.topology_id,
        "suite": run.suite,
        "status": run.status,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "message": run.message,
        "steps": [s for s in run.steps],
        "logs": list(run.logs),
    })


@app.get("/api/tests/{run_id}", response_model=TestRunStatusResponse)
async def get_test_run_endpoint(run_id: str):
    with _test_runs_lock:
        run = _test_runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Test run not found")
        payload = {
            "run_id": run.run_id,
            "topology_id": run.topology_id,
            "suite": run.suite,
            "status": run.status,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "message": run.message,
            "steps": [s for s in run.steps],
            "logs": list(run.logs),
        }
    return TestRunStatusResponse(**payload)


@app.post("/api/tests/{run_id}/stop", response_model=TestRunStatusResponse)
async def stop_test_run_endpoint(run_id: str, request: Optional[TestRunStopRequest] = None):
    with _test_runs_lock:
        run = _test_runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Test run not found")
        if request is None or bool(request.cancel):
            run.cancel_flag.set()
            _test_log(run, "Cancel requested")
        payload = {
            "run_id": run.run_id,
            "topology_id": run.topology_id,
            "suite": run.suite,
            "status": run.status,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "message": run.message,
            "steps": [s for s in run.steps],
            "logs": list(run.logs),
        }
    return TestRunStatusResponse(**payload)


@app.get("/api/tests/{run_id}/results")
async def get_test_results_endpoint(run_id: str, topology_id: str, window_minutes: int = 120):
    """
    Fetch test results from topology-local InfluxDB for charting/analysis.
    This works even after orchestrator restarts because results are sourced from Influx, not memory.
    """
    topology_id = (topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    influx_bucket = _resolve_topology_influx_target(topology_id)["bucket"]
    shared_topology_filter = (
        f' and exists r.topology_id and r.topology_id == "{_flux_escape_str(topology_id)}"'
        if TOPOLOGY_INFRA_MODE != "isolated"
        else ""
    )
    escaped_run_id = _flux_escape_str(run_id)

    window_minutes = int(max(5, min(24 * 60, window_minutes)))
    start_range = f"-{window_minutes}m"

    def _f(value: str) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None

    def _i(value: str) -> Optional[int]:
        try:
            return int(float(value))
        except Exception:
            return None

    metrics_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        f' |> range(start: {start_range})'
        f' |> filter(fn: (r) => r._measurement == "caduceus_test_metric" and r.run_id == "{escaped_run_id}"{shared_topology_filter})'
        f' |> filter(fn: (r) => r._field == "cpu_percent" or r._field == "memory_percent")'
        f' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f' |> keep(columns: ["_time","device","reason","cpu_percent","memory_percent"])'
        f' |> sort(columns: ["_time"])'
    )
    ping_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        f' |> range(start: {start_range})'
        f' |> filter(fn: (r) => r._measurement == "caduceus_test_ping" and r.run_id == "{escaped_run_id}"{shared_topology_filter})'
        f' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f' |> keep(columns: ["_time","src","dst","success","loss_pct","rtt_avg_ms","exit_code"])'
        f' |> sort(columns: ["_time"])'
    )
    iperf_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        f' |> range(start: {start_range})'
        f' |> filter(fn: (r) => r._measurement == "caduceus_test_iperf" and r.run_id == "{escaped_run_id}"{shared_topology_filter})'
        f' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f' |> keep(columns: ["_time","src","dst","proto","throughput_mbps","seconds","parallel","bandwidth_mbps","packet_size","jitter_ms","loss_pct","lost","total"])'
        f' |> sort(columns: ["_time"])'
    )
    counter_flux = (
        f'from(bucket: "{_flux_escape_str(influx_bucket)}")'
        f' |> range(start: {start_range})'
        f' |> filter(fn: (r) => r._measurement == "caduceus_test_counter_delta" and r.run_id == "{escaped_run_id}"{shared_topology_filter})'
        f' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f' |> keep(columns: ["_time","device","reason","bytes_sent_delta","bytes_received_delta","packets_sent_delta","packets_received_delta","errors_in_delta","errors_out_delta","drops_in_delta","drops_out_delta"])'
        f' |> sort(columns: ["_time"])'
    )

    metrics_rows = await _query_influx_rows_for_topology(topology_id, metrics_flux)
    ping_rows = await _query_influx_rows_for_topology(topology_id, ping_flux)
    iperf_rows = await _query_influx_rows_for_topology(topology_id, iperf_flux)
    counter_rows = await _query_influx_rows_for_topology(topology_id, counter_flux)

    series_by_device: Dict[str, List[Dict[str, Any]]] = {}
    summary_by_device: Dict[str, Dict[str, Any]] = {}
    for row in metrics_rows:
        dev = (row.get("device") or "").strip()
        if not dev:
            continue
        ts = _rfc3339_to_epoch_ms(row.get("_time") or "")
        cpu = _f(row.get("cpu_percent") or "") or 0.0
        mem = _f(row.get("memory_percent") or "") or 0.0
        reason = (row.get("reason") or "").strip()
        series_by_device.setdefault(dev, []).append(
            {
                "t": ts,
                "cpu_percent": float(cpu),
                "memory_percent": float(mem),
                "reason": reason,
            }
        )
        s = summary_by_device.setdefault(dev, {"cpu_max": 0.0, "mem_max": 0.0, "cpu_sum": 0.0, "mem_sum": 0.0, "n": 0})
        s["cpu_max"] = float(max(float(s["cpu_max"]), float(cpu)))
        s["mem_max"] = float(max(float(s["mem_max"]), float(mem)))
        s["cpu_sum"] = float(s["cpu_sum"]) + float(cpu)
        s["mem_sum"] = float(s["mem_sum"]) + float(mem)
        s["n"] = int(s["n"]) + 1

    for dev, s in summary_by_device.items():
        n = max(1, int(s.get("n") or 0))
        s["cpu_avg"] = float(s.get("cpu_sum") or 0.0) / n
        s["mem_avg"] = float(s.get("mem_sum") or 0.0) / n
        s.pop("cpu_sum", None)
        s.pop("mem_sum", None)
        s.pop("n", None)

    ping = []
    for row in ping_rows:
        ping.append(
            {
                "t": _rfc3339_to_epoch_ms(row.get("_time") or ""),
                "src": (row.get("src") or "").strip(),
                "dst": (row.get("dst") or "").strip(),
                "success": _i(row.get("success") or "") or 0,
                "loss_pct": _f(row.get("loss_pct") or "") or 0.0,
                "rtt_avg_ms": _f(row.get("rtt_avg_ms") or "") or 0.0,
                "exit_code": _i(row.get("exit_code") or "") or 0,
            }
        )

    iperf = []
    for row in iperf_rows:
        iperf.append(
            {
                "t": _rfc3339_to_epoch_ms(row.get("_time") or ""),
                "src": (row.get("src") or "").strip(),
                "dst": (row.get("dst") or "").strip(),
                "proto": (row.get("proto") or "").strip(),
                "throughput_mbps": _f(row.get("throughput_mbps") or "") or 0.0,
                "seconds": _i(row.get("seconds") or ""),
                "parallel": _i(row.get("parallel") or ""),
                "bandwidth_mbps": _f(row.get("bandwidth_mbps") or ""),
                "packet_size": _i(row.get("packet_size") or ""),
                "jitter_ms": _f(row.get("jitter_ms") or ""),
                "loss_pct": _f(row.get("loss_pct") or ""),
                "lost": _i(row.get("lost") or ""),
                "total": _i(row.get("total") or ""),
            }
        )

    counters = []
    for row in counter_rows:
        counters.append(
            {
                "t": _rfc3339_to_epoch_ms(row.get("_time") or ""),
                "device": (row.get("device") or "").strip(),
                "reason": (row.get("reason") or "").strip(),
                "bytes_sent_delta": _i(row.get("bytes_sent_delta") or "") or 0,
                "bytes_received_delta": _i(row.get("bytes_received_delta") or "") or 0,
                "packets_sent_delta": _i(row.get("packets_sent_delta") or "") or 0,
                "packets_received_delta": _i(row.get("packets_received_delta") or "") or 0,
                "errors_in_delta": _i(row.get("errors_in_delta") or "") or 0,
                "errors_out_delta": _i(row.get("errors_out_delta") or "") or 0,
                "drops_in_delta": _i(row.get("drops_in_delta") or "") or 0,
                "drops_out_delta": _i(row.get("drops_out_delta") or "") or 0,
            }
        )

    run_meta: Optional[Dict[str, Any]] = None
    with _test_runs_lock:
        r = _test_runs.get(run_id)
        if r:
            run_meta = {
                "run_id": r.run_id,
                "topology_id": r.topology_id,
                "suite": r.suite,
                "status": str(r.status),
                "created_at": r.created_at,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "message": r.message,
                "steps": [s.model_dump() for s in r.steps],
                "logs": list(r.logs),
            }

    return {
        "run": run_meta,
        "run_id": run_id,
        "topology_id": topology_id,
        "window_minutes": window_minutes,
        "metrics": {
            "series_by_device": series_by_device,
            "summary_by_device": summary_by_device,
        },
        "ping": ping,
        "iperf": iperf,
        "counters": counters,
    }

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()
rabbitmq_consumer = None

MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring-service:8011")
GRAFANA_INTERNAL_URL = os.getenv("GRAFANA_INTERNAL_URL", "http://grafana:3000")
GRAFANA_ADMIN_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_ADMIN_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "changeme_grafana_password")
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "changeme_influxdb_token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "caduceus-flux")
TOPOLOGY_INFRA_MODE = os.getenv("TOPOLOGY_INFRA_MODE", "shared").strip().lower()  # shared | isolated

MAIN_DOCKER_NETWORK = "caduceus-flux_caduceus-network"

OSM_TOPOLOGY_MODE = os.getenv("OSM_TOPOLOGY_MODE", "isolated").strip().lower()  # isolated | disabled
OSM_AUTO_BOOTSTRAP_ISOLATED = str(os.getenv("OSM_AUTO_BOOTSTRAP_ISOLATED", "true") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)


def _rand_secret(length: int = 40) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def _rand_portainer_password(length: int = 24) -> str:
    """
    Portainer enforces password complexity. Generate a deterministic-complex password:
    at least 1 lower/upper/digit/special.
    """
    length = max(int(length), 16)
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"
    alphabet = lower + upper + digits + special

    chars = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    while len(chars) < length:
        chars.append(secrets.choice(alphabet))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)

def _consul_get(key: str) -> Optional[str]:
    try:
        return consul_client.get_config(key)
    except Exception:
        return None

def _consul_set(key: str, value: str) -> None:
    try:
        consul_client.set_config(key, value)
    except Exception:
        pass

def _shared_secrets_dir() -> str:
    return os.getenv("CADUCEUS_SHARED_SECRETS_DIR", "/run/secrets/caduceus").strip() or "/run/secrets/caduceus"

def _read_secret_line(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = f.readline().strip()
        return value or None
    except Exception:
        return None

def _shared_ui_credentials() -> dict[str, Any]:
    base = _shared_secrets_dir()
    return {
        "pgadmin": {
            "email": _read_secret_line(os.path.join(base, "pgadmin_email")) or os.getenv("PGADMIN_DEFAULT_EMAIL") or "admin@example.com",
            "password": _read_secret_line(os.path.join(base, "pgadmin_password")) or os.getenv("PGADMIN_DEFAULT_PASSWORD"),
        },
        "mongo_express": {
            "user": _read_secret_line(os.path.join(base, "mongo_express_user")) or os.getenv("MONGO_EXPRESS_USER") or "caduceus",
            "password": _read_secret_line(os.path.join(base, "mongo_express_password")) or os.getenv("MONGO_EXPRESS_PASSWORD"),
        },
        "hue": {
            "user": _read_secret_line(os.path.join(base, "hue_user")) or "hue",
            "password": _read_secret_line(os.path.join(base, "hue_password")),
        },
    }

def _sync_shared_pgadmin_login(email: Optional[str], password: Optional[str]) -> None:
    if not docker_client:
        return
    if not email or not password:
        return
    try:
        c = docker_client.containers.get("caduceus-pgadmin")
    except Exception:
        return
    try:
        c.reload()
    except Exception:
        pass
    if getattr(c, "status", "") != "running":
        return

    email_q = shlex.quote(email)
    password_q = shlex.quote(password)
    update_cmd = f"/venv/bin/python3 /pgadmin4/setup.py update-user {email_q} --password {password_q} --admin --active"
    add_cmd = f"/venv/bin/python3 /pgadmin4/setup.py add-user {email_q} {password_q} --admin --active"

    try:
        res = c.exec_run(["sh", "-lc", update_cmd], demux=True)
        exit_code = getattr(res, "exit_code", None)
        if isinstance(exit_code, int) and exit_code != 0:
            c.exec_run(["sh", "-lc", add_cmd], demux=True)
            c.exec_run(["sh", "-lc", update_cmd], demux=True)
    except Exception:
        return

def _sync_shared_hue_login(username: Optional[str], password: Optional[str]) -> None:
    if not docker_client:
        return
    if not username or not password:
        return
    try:
        c = docker_client.containers.get("caduceus-hue")
    except Exception:
        return
    try:
        c.reload()
    except Exception:
        pass
    if getattr(c, "status", "") != "running":
        return

    email = f"{username}@example.com"
    py = (
        "from django.contrib.auth import get_user_model\n"
        "User = get_user_model()\n"
        f"u, _created = User.objects.get_or_create(username={username!r}, defaults={{'email': {email!r}}})\n"
        f"u.email = {email!r}\n"
        "u.is_active = True\n"
        "u.is_staff = True\n"
        "u.is_superuser = True\n"
        f"u.set_password({password!r})\n"
        "u.save()\n"
        "print('ok')\n"
    )
    cmd = f"/usr/share/hue/build/env/bin/hue shell -c {shlex.quote(py)}"
    try:
        c.exec_run(["sh", "-lc", cmd], demux=True)
    except Exception:
        return

# Avoid blocking API responses (and DoS-ing Docker) by running shared UI login sync at most once per interval.
_shared_ui_login_sync_lock = threading.Lock()
_shared_ui_login_sync_inflight = False
_shared_ui_login_sync_last_start = 0.0
_SHARED_UI_LOGIN_SYNC_MIN_INTERVAL_SEC = float(os.getenv("CADUCEUS_SHARED_UI_LOGIN_SYNC_MIN_INTERVAL_SEC", "60") or "60")


async def _maybe_schedule_shared_ui_login_sync(credentials: dict[str, Any]) -> None:
    global _shared_ui_login_sync_inflight, _shared_ui_login_sync_last_start
    if not docker_client:
        return
    if not isinstance(credentials, dict):
        return

    pg = credentials.get("pgadmin") if isinstance(credentials.get("pgadmin"), dict) else None
    hue = credentials.get("hue") if isinstance(credentials.get("hue"), dict) else None

    pg_email = (pg or {}).get("email")
    pg_password = (pg or {}).get("password")
    hue_user = (hue or {}).get("user")
    hue_password = (hue or {}).get("password")

    # Nothing to sync yet.
    if not pg_email or not pg_password:
        return
    if not hue_user or not hue_password:
        return

    now = time.time()
    with _shared_ui_login_sync_lock:
        if _shared_ui_login_sync_inflight:
            return
        if now - _shared_ui_login_sync_last_start < _SHARED_UI_LOGIN_SYNC_MIN_INTERVAL_SEC:
            return
        _shared_ui_login_sync_inflight = True
        _shared_ui_login_sync_last_start = now

    async def _run() -> None:
        global _shared_ui_login_sync_inflight
        try:
            await asyncio.to_thread(_sync_shared_pgadmin_login, str(pg_email), str(pg_password))
            await asyncio.to_thread(_sync_shared_hue_login, str(hue_user), str(hue_password))
        finally:
            with _shared_ui_login_sync_lock:
                _shared_ui_login_sync_inflight = False

    asyncio.create_task(_run())

def _ensure_topology_isolated_infra_secrets(topology_id: str, existing_payload: Optional[dict[str, Any]] = None) -> dict[str, str]:
    """
    Ensure per-topology isolated infra credentials exist (and are non-empty) in Consul.
    Returns a dict of resolved values for container env + UI display.
    """
    prefix = f"caduceus/topologies/{topology_id}"

    # If containers already exist, prefer their configured init values (especially token) to avoid
    # Consul drift causing unauthorized errors in monitoring-service queries.
    influx_container_env: dict[str, str] = {}
    try:
        if docker_client:
            cname = _topo_container_name(topology_id, "influxdb")
            c = docker_client.containers.get(cname)
            try:
                env_list = ((c.attrs or {}).get("Config") or {}).get("Env") or []
            except Exception:
                env_list = []
            for item in env_list:
                try:
                    if not isinstance(item, str) or "=" not in item:
                        continue
                    k, v = item.split("=", 1)
                    if k:
                        influx_container_env[k] = v
                except Exception:
                    continue
    except Exception:
        influx_container_env = {}

    influx_org = (
        _consul_get(f"{prefix}/isolated_influx_org")
        or ((existing_payload or {}).get("services", {}).get("influxdb", {}) or {}).get("org")
        or influx_container_env.get("DOCKER_INFLUXDB_INIT_ORG")
        or f"topology-{topology_id[:8]}"
    )
    influx_bucket = (
        _consul_get(f"{prefix}/isolated_influx_bucket")
        or ((existing_payload or {}).get("services", {}).get("influxdb", {}) or {}).get("bucket")
        or influx_container_env.get("DOCKER_INFLUXDB_INIT_BUCKET")
        or "metrics"
    )

    consul_token = _consul_get(f"{prefix}/isolated_influx_token")
    container_token = influx_container_env.get("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN") or None
    if container_token and consul_token and container_token != consul_token:
        logger.warning(
            "Topology %s isolated Influx token drift detected; syncing Consul token to container init token.",
            topology_id,
        )
        influx_token = container_token
    else:
        influx_token = consul_token or container_token or _rand_secret(48)

    influx_admin_user = (
        _consul_get(f"{prefix}/isolated_influx_admin_user") or influx_container_env.get("DOCKER_INFLUXDB_INIT_USERNAME") or "admin"
    )
    influx_admin_password = (
        _consul_get(f"{prefix}/isolated_influx_admin_password") or influx_container_env.get("DOCKER_INFLUXDB_INIT_PASSWORD") or _rand_secret(32)
    )

    grafana_admin_user = _consul_get(f"{prefix}/isolated_grafana_admin_user") or "admin"
    grafana_admin_password = _consul_get(f"{prefix}/isolated_grafana_admin_password") or _rand_secret(24)

    rabbitmq_user = _consul_get(f"{prefix}/isolated_rabbitmq_user") or "caduceus"
    rabbitmq_password = _consul_get(f"{prefix}/isolated_rabbitmq_password") or _rand_secret(18)
    rabbitmq_vhost = _consul_get(f"{prefix}/isolated_rabbitmq_vhost") or "/caduceus-flux"

    # Portainer: avoid the 5-minute "admin init timeout" by pre-seeding an admin password
    # and letting the orchestrator auto-initialize it on startup.
    portainer_admin_user = _consul_get(f"{prefix}/isolated_portainer_admin_user") or "admin"
    portainer_admin_password = _consul_get(f"{prefix}/isolated_portainer_admin_password") or _rand_secret(20)
    portainer_view_user = _consul_get(f"{prefix}/isolated_portainer_view_user") or f"caduceus-topo-{topology_id[:8]}"
    portainer_view_password = _consul_get(f"{prefix}/isolated_portainer_view_password") or _rand_portainer_password(24)

    # Persist (idempotent)
    _consul_set(f"{prefix}/isolated_influx_org", influx_org)
    _consul_set(f"{prefix}/isolated_influx_bucket", influx_bucket)
    _consul_set(f"{prefix}/isolated_influx_token", influx_token)
    _consul_set(f"{prefix}/isolated_influx_admin_user", influx_admin_user)
    _consul_set(f"{prefix}/isolated_influx_admin_password", influx_admin_password)

    _consul_set(f"{prefix}/isolated_grafana_admin_user", grafana_admin_user)
    _consul_set(f"{prefix}/isolated_grafana_admin_password", grafana_admin_password)

    _consul_set(f"{prefix}/isolated_rabbitmq_user", rabbitmq_user)
    _consul_set(f"{prefix}/isolated_rabbitmq_password", rabbitmq_password)
    _consul_set(f"{prefix}/isolated_rabbitmq_vhost", rabbitmq_vhost)

    _consul_set(f"{prefix}/isolated_portainer_admin_user", portainer_admin_user)
    _consul_set(f"{prefix}/isolated_portainer_admin_password", portainer_admin_password)
    _consul_set(f"{prefix}/isolated_portainer_view_user", portainer_view_user)
    _consul_set(f"{prefix}/isolated_portainer_view_password", portainer_view_password)

    return {
        "influx_org": influx_org,
        "influx_bucket": influx_bucket,
        "influx_token": influx_token,
        "influx_admin_user": influx_admin_user,
        "influx_admin_password": influx_admin_password,
        "grafana_admin_user": grafana_admin_user,
        "grafana_admin_password": grafana_admin_password,
        "rabbitmq_user": rabbitmq_user,
        "rabbitmq_password": rabbitmq_password,
        "rabbitmq_vhost": rabbitmq_vhost,
        "portainer_admin_user": portainer_admin_user,
        "portainer_admin_password": portainer_admin_password,
        "portainer_view_user": portainer_view_user,
        "portainer_view_password": portainer_view_password,
    }


def _provision_portainer_topology_view(
    topology_id: str,
    *,
    portainer_base: str,
    admin_user: str,
    admin_password: str,
    view_user: str,
    view_password: str,
    docker_container_ids: list[str],
) -> None:
    """
    Create a non-admin Portainer user that can only see the containers belonging to this topology.
    This avoids Portainer showing all containers on the host Docker engine.
    """
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            auth = client.post(
                f"{portainer_base}/api/auth",
                json={"Username": str(admin_user), "Password": str(admin_password)},
            )
            if auth.status_code != 200:
                return
            jwt = (auth.json() or {}).get("jwt")
            if not jwt:
                return
            headers = {"Authorization": f"Bearer {jwt}"}

            # Ensure view user exists (Role=2 => standard user).
            user_id: Optional[int] = None
            try:
                users = client.get(f"{portainer_base}/api/users", headers=headers)
                if users.status_code == 200:
                    for u in (users.json() or []):
                        if isinstance(u, dict) and str(u.get("Username")) == str(view_user):
                            try:
                                user_id = int(u.get("Id"))
                            except Exception:
                                user_id = None
                            break
            except Exception:
                pass

            if user_id is None:
                created = client.post(
                    f"{portainer_base}/api/users",
                    headers=headers,
                    json={"Username": str(view_user), "Password": str(view_password), "Role": 2},
                )
                if created.status_code != 200:
                    return
                try:
                    user_id = int((created.json() or {}).get("Id"))
                except Exception:
                    user_id = None
            if user_id is None:
                return

            # Grant the user access to the "local" endpoint so they can log in and see their assigned resources.
            endpoint_id: Optional[int] = None
            try:
                eps = client.get(f"{portainer_base}/api/endpoints", headers=headers)
                if eps.status_code == 200:
                    for e in (eps.json() or []):
                        if not isinstance(e, dict):
                            continue
                        if str(e.get("URL", "")).startswith("unix:///"):
                            try:
                                endpoint_id = int(e.get("Id"))
                            except Exception:
                                endpoint_id = None
                            break
            except Exception:
                endpoint_id = None

            if endpoint_id is not None:
                try:
                    current = client.get(f"{portainer_base}/api/endpoints/{endpoint_id}", headers=headers)
                    cur_policies = (current.json() or {}).get("UserAccessPolicies") if current.status_code == 200 else {}
                    if not isinstance(cur_policies, dict):
                        cur_policies = {}
                except Exception:
                    cur_policies = {}
                cur_policies[str(user_id)] = {"RoleId": 1}
                try:
                    client.put(
                        f"{portainer_base}/api/endpoints/{endpoint_id}",
                        headers=headers,
                        json={"UserAccessPolicies": cur_policies},
                    )
                except Exception:
                    pass

            # Assign container-level access for just the topology containers.
            for cid in docker_container_ids:
                if not cid or len(str(cid)) < 12:
                    continue
                try:
                    rc = client.post(
                        f"{portainer_base}/api/resource_controls",
                        headers=headers,
                        json={"Type": 1, "ResourceID": str(cid), "Users": [int(user_id)], "Teams": [], "Public": False},
                    )
                    if rc.status_code in (200, 409):
                        continue
                except Exception:
                    continue
    except Exception:
        return

def _list_topology_infra_containers(topology_id: str) -> list[Any]:
    if not docker_client:
        return []
    name_prefix = f"caduceus-topo-{topology_id[:8]}-"
    try:
        containers = docker_client.containers.list(
            all=True,
            filters={"label": [f"caduceus.role=topology_infra", f"caduceus.topology_id={topology_id}"]},
        )
        items = list(containers or [])
        if items:
            return items
        # Backward-compat: older stacks may be missing labels; fall back to name prefix.
        try:
            return [
                c
                for c in docker_client.containers.list(all=True)
                if (getattr(c, "name", "") or "").startswith(name_prefix)
            ]
        except Exception:
            return []
    except Exception:
        items: list[Any] = []
        try:
            for c in docker_client.containers.list(all=True):
                labels = getattr(c, "labels", {}) or {}
                if labels.get("caduceus.role") != "topology_infra":
                    # Backward-compat: accept name prefix when labels are missing.
                    if (getattr(c, "name", "") or "").startswith(name_prefix):
                        items.append(c)
                    continue
                if labels.get("caduceus.topology_id") != topology_id:
                    continue
                items.append(c)
        except Exception:
            return []
        return items


def stop_topology_isolated_infra(topology_id: str, preserve_data: bool = True) -> dict[str, Any]:
    """
    Stop (and optionally remove) isolated infra containers for a topology.
    preserve_data=True keeps named volumes so data continues on next start.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    containers = _list_topology_infra_containers(topology_id)
    stopped: list[str] = []
    removed: list[str] = []
    for c in containers:
        try:
            c.reload()
        except Exception:
            pass
        try:
            if getattr(c, "status", "") in ("running", "restarting", "created"):
                c.stop(timeout=10)
            stopped.append(getattr(c, "name", "") or getattr(c, "id", ""))
        except Exception:
            pass

        if not preserve_data:
            try:
                c.remove(force=True)
                removed.append(getattr(c, "name", "") or getattr(c, "id", ""))
            except Exception:
                pass

    return {"topology_id": topology_id, "stopped": stopped, "removed": removed, "preserve_data": preserve_data}


def purge_topology_isolated_infra(topology_id: str) -> dict[str, Any]:
    """
    Remove isolated infra containers + network + volumes for a topology, and delete Consul config keys.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    result = stop_topology_isolated_infra(topology_id, preserve_data=False)

    # Remove topology network
    net_name = _topo_network_name(topology_id)
    try:
        docker_client.networks.get(net_name).remove()
    except Exception:
        pass

    # Remove named volumes used by the topology stack
    removed_volumes: list[str] = []
    for svc in (
        "influxdb",
        "grafana",
        "prometheus-config",
        "prometheus-tsdb",
        "consul",
        "rabbitmq",
        "kafka",
        "zookeeper",
    ):
        vname = _topo_volume_name(topology_id, svc)
        try:
            docker_client.volumes.get(vname).remove(force=True)
            removed_volumes.append(vname)
        except Exception:
            pass

    # Remove Consul keys
    keys = [
        f"caduceus/topologies/{topology_id}/isolated_infra",
        f"caduceus/topologies/{topology_id}/isolated_influx_token",
        f"caduceus/topologies/{topology_id}/isolated_influx_org",
        f"caduceus/topologies/{topology_id}/isolated_influx_bucket",
        f"caduceus/topologies/{topology_id}/isolated_influx_admin_user",
        f"caduceus/topologies/{topology_id}/isolated_influx_admin_password",
        f"caduceus/topologies/{topology_id}/isolated_grafana_admin_user",
        f"caduceus/topologies/{topology_id}/isolated_grafana_admin_password",
        f"caduceus/topologies/{topology_id}/isolated_rabbitmq_user",
        f"caduceus/topologies/{topology_id}/isolated_rabbitmq_password",
        f"caduceus/topologies/{topology_id}/isolated_rabbitmq_vhost",
        f"caduceus/topologies/{topology_id}/isolated_controllers",
    ]
    deleted: list[str] = []
    for k in keys:
        try:
            consul_client.client.kv.delete(k)
            deleted.append(k)
        except Exception:
            pass

    return {
        **result,
        "network_removed": net_name,
        "volumes_removed": removed_volumes,
        "consul_keys_deleted": deleted,
    }


def sync_topology_isolated_infra_logins(topology_id: str) -> dict[str, Any]:
    """
    Make service logins match what we publish via Consul/UI.

    Important: many images only apply env-provided passwords on the *first* boot when the data volume is empty.
    If volumes already exist, we must actively reset/update passwords.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    secrets_payload = _ensure_topology_isolated_infra_secrets(topology_id)
    grafana_user = secrets_payload["grafana_admin_user"]
    grafana_password = secrets_payload["grafana_admin_password"]
    influx_user = secrets_payload["influx_admin_user"]
    influx_password = secrets_payload["influx_admin_password"]
    influx_token = secrets_payload["influx_token"]
    rabbit_user = secrets_payload["rabbitmq_user"]
    rabbit_password = secrets_payload["rabbitmq_password"]
    rabbit_vhost = secrets_payload["rabbitmq_vhost"]

    results: dict[str, Any] = {"topology_id": topology_id, "grafana": None, "influxdb": None, "rabbitmq": None}

    # Grafana: reset admin password
    try:
        grafana = docker_client.containers.get(_topo_container_name(topology_id, "grafana"))
        script = (
            "set -e\n"
            "PW=%s\n"
            "GRAFANA_BIN=\"$(command -v grafana 2>/dev/null || true)\"\n"
            "if [ -x /usr/share/grafana/bin/grafana ]; then GRAFANA_BIN=/usr/share/grafana/bin/grafana; fi\n"
            "if [ -n \"$GRAFANA_BIN\" ]; then\n"
            "  \"$GRAFANA_BIN\" cli admin reset-admin-password \"$PW\"\n"
            "elif [ -x /usr/share/grafana/bin/grafana-cli ]; then\n"
            "  /usr/share/grafana/bin/grafana-cli admin reset-admin-password \"$PW\"\n"
            "else\n"
            "  echo \"grafana cli not found\" >&2\n"
            "  exit 127\n"
            "fi\n"
        ) % shlex.quote(str(grafana_password))
        code, out = grafana.exec_run(["sh", "-lc", script], user="root")
        results["grafana"] = {"ok": code == 0, "exit_code": code, "output": (out or b"")[:2000].decode("utf-8", "ignore")}
    except Exception as exc:
        results["grafana"] = {"ok": False, "error": str(exc)}

    # RabbitMQ: ensure vhost, user, permissions, and password
    try:
        rabbit = docker_client.containers.get(_topo_container_name(topology_id, "rabbitmq"))
        script = (
            "set -e\n"
            "export PATH=/opt/erlang/bin:/opt/rabbitmq/sbin:$PATH\n"
            f"VHOST={shlex.quote(rabbit_vhost)}\n"
            f"USER={shlex.quote(rabbit_user)}\n"
            f"PASS={shlex.quote(rabbit_password)}\n"
            "rabbitmqctl add_vhost \"$VHOST\" >/dev/null 2>&1 || true\n"
            "rabbitmqctl add_user \"$USER\" \"$PASS\" >/dev/null 2>&1 || rabbitmqctl change_password \"$USER\" \"$PASS\" >/dev/null\n"
            "rabbitmqctl set_user_tags \"$USER\" administrator >/dev/null 2>&1 || true\n"
            "rabbitmqctl set_permissions -p \"$VHOST\" \"$USER\" \".*\" \".*\" \".*\" >/dev/null\n"
        )
        code, out = rabbit.exec_run(["sh", "-lc", script])
        results["rabbitmq"] = {"ok": code == 0, "exit_code": code, "output": (out or b"")[:2000].decode("utf-8", "ignore")}
    except Exception as exc:
        results["rabbitmq"] = {"ok": False, "error": str(exc)}

    # InfluxDB: set admin password using admin token
    try:
        influx = docker_client.containers.get(_topo_container_name(topology_id, "influxdb"))
        env = {"INFLUX_TOKEN": influx_token}
        cmd = [
            "sh",
            "-lc",
            "influx user password "
            f"-n {shlex.quote(influx_user)} "
            f"-p {shlex.quote(influx_password)} "
            "--host http://localhost:8086",
        ]
        code, out = influx.exec_run(cmd, user="root", environment=env)
        results["influxdb"] = {"ok": code == 0, "exit_code": code, "output": (out or b"")[:2000].decode("utf-8", "ignore")}
    except Exception as exc:
        results["influxdb"] = {"ok": False, "error": str(exc)}

    return results


def _topo_prefix(topology_id: str) -> str:
    return f"caduceus-topo-{topology_id[:8]}"


def _topo_network_name(topology_id: str) -> str:
    return f"{_topo_prefix(topology_id)}-net"


def _topo_volume_name(topology_id: str, service: str) -> str:
    return f"{_topo_prefix(topology_id)}-{service}-data"


def _topo_container_name(topology_id: str, service: str) -> str:
    return f"{_topo_prefix(topology_id)}-{service}"


def _topology_infra_labels(topology_id: str, service_id: str) -> dict[str, str]:
    return {
        "caduceus.topology_id": topology_id,
        "caduceus.role": "topology_infra",
        "caduceus.infra_service": service_id,
    }

def _topology_osm_labels(topology_id: str, service_id: str) -> dict[str, str]:
    return {
        "caduceus.topology_id": topology_id,
        "caduceus.role": "topology_osm",
        "caduceus.osm_service": service_id,
    }

def _osm_prefix(topology_id: str) -> str:
    return f"caduceus-osm-topo-{topology_id[:8]}"

def _osm_network_name(topology_id: str) -> str:
    return f"{_osm_prefix(topology_id)}-net"

def _osm_volume_name(topology_id: str, service: str) -> str:
    return f"{_osm_prefix(topology_id)}-{service}-data"

def _osm_container_name(topology_id: str, service: str) -> str:
    return f"{_osm_prefix(topology_id)}-{service}"

def _ensure_network_internal(name: str) -> Any:
    try:
        return docker_client.networks.get(name)
    except Exception:
        return docker_client.networks.create(name, driver="bridge", internal=True)

def _list_topology_osm_containers(topology_id: str) -> list[Any]:
    if not docker_client:
        return []
    name_prefix = f"{_osm_prefix(topology_id)}-"
    try:
        containers = docker_client.containers.list(
            all=True,
            filters={"label": [f"caduceus.role=topology_osm", f"caduceus.topology_id={topology_id}"]},
        )
        items = list(containers or [])
        if items:
            return items
        # Backward-compat/fallback: name prefix
        return [
            c
            for c in docker_client.containers.list(all=True)
            if (getattr(c, "name", "") or "").startswith(name_prefix)
        ]
    except Exception:
        return []

def _remove_topology_osm_resources(topology_id: str, *, remove_volumes: bool) -> dict[str, Any]:
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    containers = _list_topology_osm_containers(topology_id)
    stopped: list[str] = []
    removed: list[str] = []
    for c in containers:
        name = getattr(c, "name", "") or getattr(c, "id", "")
        try:
            c.reload()
        except Exception:
            pass
        try:
            if getattr(c, "status", "") in ("running", "restarting", "created"):
                c.stop(timeout=10)
            stopped.append(name)
        except Exception:
            pass
        try:
            c.remove(force=True)
            removed.append(name)
        except Exception:
            pass

    removed_volumes: list[str] = []
    if remove_volumes:
        for v in [
            _osm_volume_name(topology_id, "mongo"),
            _osm_volume_name(topology_id, "mysql"),
            _osm_volume_name(topology_id, "kafka"),
            _osm_volume_name(topology_id, "zookeeper-data"),
            _osm_volume_name(topology_id, "zookeeper-log"),
            _osm_volume_name(topology_id, "nbi-storage"),
        ]:
            try:
                docker_client.volumes.get(v).remove(force=True)
                removed_volumes.append(v)
            except Exception:
                pass

    removed_network: Optional[str] = None
    try:
        net_name = _osm_network_name(topology_id)
        docker_client.networks.get(net_name).remove()
        removed_network = net_name
    except Exception:
        removed_network = None

    return {
        "stopped": stopped,
        "removed": removed,
        "removed_volumes": removed_volumes,
        "removed_network": removed_network,
    }

def stop_topology_isolated_osm(topology_id: str, preserve_data: bool = True) -> dict[str, Any]:
    """
    Stop (and optionally remove) isolated OSM containers for a topology.
    preserve_data=True keeps named volumes so data continues on next start.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    containers = _list_topology_osm_containers(topology_id)
    stopped: list[str] = []
    removed: list[str] = []
    for c in containers:
        try:
            c.reload()
        except Exception:
            pass
        try:
            if getattr(c, "status", "") in ("running", "restarting", "created"):
                c.stop(timeout=10)
            stopped.append(getattr(c, "name", "") or getattr(c, "id", ""))
        except Exception:
            pass

        if not preserve_data:
            try:
                c.remove(force=True)
                removed.append(getattr(c, "name", "") or getattr(c, "id", ""))
            except Exception:
                pass

    return {"topology_id": topology_id, "stopped": stopped, "removed": removed, "preserve_data": preserve_data}


def _ensure_network(name: str) -> Any:
    try:
        return docker_client.networks.get(name)
    except Exception:
        return docker_client.networks.create(name, driver="bridge")

def _ensure_image(image: str) -> None:
    if not docker_client or not image:
        return
    try:
        docker_client.images.get(image)
        return
    except Exception:
        pass
    try:
        docker_client.images.pull(image)
    except Exception:
        # Let container run attempt raise a more specific error if pull fails.
        pass


def _connect_to_network(container: Any, network_name: str, aliases: Optional[list[str]] = None) -> None:
    try:
        net = docker_client.networks.get(network_name)
    except Exception:
        net = docker_client.networks.create(network_name, driver="bridge")
    try:
        net.connect(container, aliases=aliases or None)
    except Exception:
        pass


def _collect_used_host_ports() -> set[int]:
    used: set[int] = set()
    if not docker_client:
        return used
    for c in docker_client.containers.list(all=True):
        try:
            ports = (getattr(c, "attrs", {}) or {}).get("NetworkSettings", {}).get("Ports", {}) or {}
            for _container_port, bindings in ports.items():
                if not bindings:
                    continue
                for b in bindings:
                    hp = b.get("HostPort")
                    if hp:
                        used.add(int(hp))
        except Exception:
            continue
    return used


def _allocate_host_port(start: int, end: int, used: set[int]) -> int:
    for _ in range(2000):
        cand = secrets.randbelow(end - start + 1) + start
        if cand not in used:
            used.add(cand)
            return cand
    for cand in range(start, end + 1):
        if cand not in used:
            used.add(cand)
            return cand
    raise RuntimeError(f"No free ports in range {start}-{end}")

# gRPC configuration
EMULATION_GRPC_HOST = os.getenv("EMULATION_GRPC_HOST", "localhost")
EMULATION_GRPC_PORT = os.getenv("EMULATION_GRPC_PORT", "50051")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8002"))
TOPOLOGY_SERVICE_URL = os.getenv("TOPOLOGY_SERVICE_URL", "http://topology-service:8001")
TOPOLOGY_REQUEST_TIMEOUT = float(os.getenv("TOPOLOGY_REQUEST_TIMEOUT", "10.0"))

import redis

from orchestrator_app.stores import ActiveEmulationStore, AlgorithmRunStore

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
ACTIVE_EMULATIONS_KEY = "active_emulations"
ALGO_RUNS_KEY = "algorithm_runs"
ALGO_LATEST_BY_TOPOLOGY_KEY = "algorithm_latest_by_topology"
MININET_NAME_MAX_LEN = 10

# Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# Active emulations tracking
active_emulations = ActiveEmulationStore(redis_client, key=ACTIVE_EMULATIONS_KEY)
algo_runs = AlgorithmRunStore(redis_client, runs_key=ALGO_RUNS_KEY, latest_key=ALGO_LATEST_BY_TOPOLOGY_KEY)

# Docker client for dynamic container spawning
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized for dynamic container spawning")
except Exception as e:
    logger.warning(f"Docker client initialization failed: {e}")
    docker_client = None

# Prevent concurrent emulation starts per topology (in-process).
_topology_start_locks: dict[str, asyncio.Lock] = {}
_topology_start_locks_guard = asyncio.Lock()


async def _get_topology_start_lock(topology_id: str) -> asyncio.Lock:
    async with _topology_start_locks_guard:
        lock = _topology_start_locks.get(topology_id)
        if lock is None:
            lock = asyncio.Lock()
            _topology_start_locks[topology_id] = lock
        return lock


# Prevent concurrent per-topology ETSI OSM ensure/reconcile operations (in-process).
_topology_osm_locks: dict[str, asyncio.Lock] = {}
_topology_osm_locks_guard = asyncio.Lock()


async def _get_topology_osm_lock(topology_id: str) -> asyncio.Lock:
    async with _topology_osm_locks_guard:
        lock = _topology_osm_locks.get(topology_id)
        if lock is None:
            lock = asyncio.Lock()
            _topology_osm_locks[topology_id] = lock
        return lock


async def _schedule_isolated_osm_reconcile(topology_id: str) -> None:
    """
    Best-effort background reconcile to keep isolated per-topology ETSI OSM in sync with
    project state (controller endpoints, VIM/WIM/SDN bootstrap).

    Skips if the topology has no isolated OSM stack yet.
    """
    if not OSM_AUTO_BOOTSTRAP_ISOLATED:
        return
    if OSM_TOPOLOGY_MODE != "isolated":
        return
    topo_id = (topology_id or "").strip()
    if not topo_id:
        return
    try:
        raw = consul_client.get_config(f"caduceus/topologies/{topo_id}/isolated_osm")
    except Exception:
        raw = None
    if not raw:
        return

    lock = await _get_topology_osm_lock(topo_id)
    if lock.locked():
        return

    async def _run() -> None:
        async with lock:
            try:
                await asyncio.to_thread(ensure_topology_isolated_osm, topo_id)
            except Exception as exc:
                logger.warning("Isolated OSM auto-reconcile failed for topology %s: %s", topo_id, exc)

    asyncio.create_task(_run())


def allocate_port() -> int:
    """
    Allocate an available port for a new emulation container.
    Port range: 50051-50150 (100 ports available)
    """
    if not docker_client:
        return 50051

    # Get all running containers (best-effort). Note: this runs inside the orchestrator container, but we
    # allocate host ports via the Docker engine; we must avoid races between concurrent start requests.
    try:
        containers = docker_client.containers.list()
        used_ports: set[int] = set()

        # Extract ports from container port mappings (for all containers, not just caduceus-emu-*).
        for container in containers:
            try:
                ports = (container.attrs or {}).get('NetworkSettings', {}).get('Ports', {}) or {}
            except Exception:
                ports = {}
            for _container_port, host_bindings in ports.items():
                if host_bindings:
                    for binding in host_bindings:
                        host_port = binding.get('HostPort')
                        if not host_port:
                            continue
                        try:
                            used_ports.add(int(host_port))
                        except Exception:
                            continue

        # Find first available port in range
        for port in range(50051, 50151):
            if port not in used_ports:
                logger.info(f"Allocated port {port} for new container")
                return port

        raise Exception("No available ports in range 50051-50150")

    except Exception as e:
        logger.error(f"Error allocating port: {e}")
        # Best-effort fallback: avoid always returning 50051 (which can repeatedly collide).
        try:
            start = int(os.getenv("EMULATION_GRPC_HOST_PORT_RANGE_START", "50051") or 50051)
            end = int(os.getenv("EMULATION_GRPC_HOST_PORT_RANGE_END", "50150") or 50150)
            if start < 1:
                start = 1
            if end > 65535:
                end = 65535
            if end < start:
                start, end = 50051, 50150
            return secrets.randbelow(end - start + 1) + start
        except Exception:
            return 50051


def _docker_container_state(container_name: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Return (exists, status, container_id) for the given container name."""
    if not docker_client or not container_name:
        return False, None, None
    try:
        c = docker_client.containers.get(container_name)
        try:
            c.reload()
        except Exception:
            pass
        return True, getattr(c, "status", None), getattr(c, "id", None)
    except docker.errors.NotFound:
        return False, None, None
    except Exception:
        return False, None, None


def _reconcile_active_emulations_with_docker() -> None:
    """Best-effort: keep Redis active emulation records consistent with Docker container state."""
    if not docker_client:
        return
    try:
        all_records = active_emulations.get_all()
    except Exception:
        return

    for topology_id, record in (all_records or {}).items():
        if not isinstance(record, dict):
            continue
        cname = record.get("container_name") or (f"caduceus-emu-{topology_id[:8]}" if topology_id else None)
        if not cname:
            continue
        exists, cstatus, cid = _docker_container_state(str(cname))
        desired_status = str(record.get("status") or "").lower()
        changed = False

        if not exists:
            # If the container is gone, the emulation can't be running.
            if desired_status == "running":
                record["status"] = "stopped"
                changed = True
            if record.get("container_id"):
                record["container_id"] = None
                changed = True
        else:
            record["container_name"] = cname
            if cid and record.get("container_id") != cid:
                record["container_id"] = cid
                changed = True
            cstatus_l = str(cstatus or "").lower()
            # Only downgrade "running" records; don't promote stopped/paused/error records based solely on
            # container state (the container can be up while Mininet is stopped).
            if cstatus_l in ("exited", "dead", "removing"):
                if desired_status == "running":
                    record["status"] = "stopped"
                    changed = True

        if changed:
            record["last_updated"] = _iso_now()
            try:
                active_emulations.set(topology_id, record)
            except Exception:
                pass


_PORT_ALLOCATION_LOCK = threading.Lock()


def _is_port_allocation_error(exc: Exception) -> bool:
    msg = str(exc or "").lower()
    return "port is already allocated" in msg or "bind for" in msg and "failed" in msg


def spawn_emulation_container(topology_id: str, force_recreate: bool = False) -> tuple[str, int, str]:
    """
    Spawn a new emulation container for a topology.
    Returns: (container_name, port, container_id)
    """
    if not docker_client:
        raise Exception("Docker client not available")

    container_name = f"caduceus-emu-{topology_id[:8]}"
    desired_image = 'caduceus-flux-emulation-container:latest'
    desired_image_id = None
    try:
        desired_image_id = docker_client.images.get(desired_image).id
    except Exception:
        desired_image_id = None

    try:
        # Check if container already exists
        try:
            existing = docker_client.containers.get(container_name)
            if force_recreate:
                logger.warning("Force recreating emulation container %s for topology %s", container_name, topology_id)
                existing.remove(force=True)
                raise docker.errors.NotFound("forced recreate")
            if existing.status == 'running':
                current_image_id = (existing.attrs or {}).get("Image")
                current_labels = (existing.labels or {})
                labeled_image_id = current_labels.get("caduceus.emulation_image_id")
                # Recreate when the container was started from a different image. Older containers may not have
                # the `caduceus.emulation_image_id` label, so compare the actual image id as well.
                if desired_image_id and current_image_id and current_image_id != desired_image_id:
                    logger.info(
                        "Emulation container %s uses old image (%s != %s); recreating",
                        container_name,
                        str(current_image_id)[:12],
                        desired_image_id[:12],
                    )
                    existing.remove(force=True)
                elif desired_image_id and labeled_image_id and labeled_image_id != desired_image_id:
                    logger.info(
                        "Emulation container %s uses old image (%s != %s); recreating",
                        container_name,
                        labeled_image_id[:12],
                        desired_image_id[:12],
                    )
                    existing.remove(force=True)
                else:
                    # Get the port from existing container
                    ports = existing.attrs.get('NetworkSettings', {}).get('Ports', {})
                    port = 50051  # Default fallback
                    for container_port, host_bindings in ports.items():
                        if host_bindings and '50051/tcp' in container_port:
                            port = int(host_bindings[0]['HostPort'])
                            break
                    logger.info(f"Container {container_name} already running on port {port}")
                    return container_name, port, existing.id
            else:
                existing.remove(force=True)
        except docker.errors.NotFound:
            pass

        p4_volume = os.getenv("P4_PROGRAMS_VOLUME", "caduceus-p4-programs")
        pcap_volume = os.getenv("PCAP_VOLUME_NAME", "caduceus-pcap-data")

        # Allocate + bind host port under a lock to avoid concurrent Start requests picking the same port.
        with _PORT_ALLOCATION_LOCK:
            last_exc: Exception | None = None
            for _attempt in range(20):
                # Allocate an available port
                port = allocate_port()
                logger.info(f"Spawning container {container_name} for topology {topology_id} on port {port}")
                try:
                    container = docker_client.containers.run(
                        desired_image,
                        name=container_name,
                        network='caduceus-flux_caduceus-network',
                        ports={'50051/tcp': port},
                        labels={
                            "caduceus.topology_id": topology_id,
                            "caduceus.role": "emulation",
                            **({"caduceus.emulation_image_id": desired_image_id} if desired_image_id else {}),
                        },
                        environment={
                            'TOPOLOGY_ID': topology_id,
                            'P4_STORAGE_ROOT': '/var/lib/caduceus/p4',
                        },
                        detach=True,
                        remove=False,
                        privileged=True,
                        volumes={
                            '/sys': {'bind': '/sys', 'mode': 'rw'},
                            '/lib/modules': {'bind': '/lib/modules', 'mode': 'ro'},
                            '/sys/kernel/debug': {'bind': '/sys/kernel/debug', 'mode': 'rw'},
                            '/var/run/netns': {'bind': '/var/run/netns', 'mode': 'rw'},
                            '/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'rw'},
                            p4_volume: {'bind': '/var/lib/caduceus/p4', 'mode': 'rw'},
                            pcap_volume: {'bind': '/var/lib/caduceus/pcap', 'mode': 'rw'},
                        },
                        pid_mode='host'
                    )
                    break
                except DockerAPIError as exc:
                    last_exc = exc
                    # If the port got grabbed between allocation and start (or by another process), retry.
                    if _is_port_allocation_error(exc):
                        try:
                            # Clean up any partially-created container with our name.
                            docker_client.containers.get(container_name).remove(force=True)
                        except Exception:
                            pass
                        continue
                    raise
                except Exception as exc:
                    last_exc = exc
                    if _is_port_allocation_error(exc):
                        try:
                            docker_client.containers.get(container_name).remove(force=True)
                        except Exception:
                            pass
                        continue
                    raise
            else:
                raise Exception(f"Failed to allocate a free gRPC port after retries: {last_exc}")

        # Wait for container to be ready
        time.sleep(2)

        logger.info(f"✅ Container {container_name} spawned successfully on port {port}, ID: {container.id[:12]}")
        return container_name, port, container.id

    except Exception as e:
        logger.error(f"Failed to spawn container: {e}")
        raise


def _is_transient_start_error(message: str) -> bool:
    msg = (message or "").lower()
    return any(
        token in msg
        for token in (
            "deadline exceeded",
            "unavailable",
            "connection refused",
            "failed to connect",
            "transport is closing",
            "socket closed",
            "timed out",
        )
    )


LOCALAI_P2P_TOKEN_PLACEHOLDER = "REPLACE_ME_SHARED_P2P_TOKEN"
LOCALAI_MODELS_VOLUME_MARKER = ".caduceus_localai_models_seeded"
_LOCALAI_MODELS_VOLUME_LOCK = threading.Lock()


def _coerce_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _looks_like_localai_node(node: dict[str, Any]) -> bool:
    props = node.get("properties")
    props = props if isinstance(props, dict) else {}
    docker_image = str(props.get("docker_image") or props.get("image") or "").lower()
    if "localai" in docker_image:
        return True
    env = _coerce_dict(props.get("docker_environment") or props.get("environment"))
    return any(k in env for k in ("LOCALAI_P2P", "LOCALAI_P2P_TOKEN", "WORKERS_MODE", "WORKER_MODE"))


def _generate_localai_p2p_token(timeout_seconds: int = 120) -> str:
    """
    Generate a valid LocalAI P2P token by starting a short-lived localai host container
    without a token and parsing the generated value from stdout.
    """
    if not docker_client:
        raise RuntimeError("Docker client not available")

    image = "localai-host:latest"
    try:
        docker_client.images.get(image)
    except Exception as exc:
        raise RuntimeError(f"Required image missing: {image}") from exc

    name = f"caduceus-localai-token-gen-{uuid.uuid4().hex[:10]}"
    container = None
    token = None
    export_pattern = re.compile(r'export\\s+TOKEN=\\"([^\\"]+)\\"')
    base64_pattern = re.compile(r"^[A-Za-z0-9+/=]{64,}$")
    saw_generated_banner = False
    started = time.time()
    try:
        # Use `local-ai run --p2p` directly (no AIO entrypoint) so token generation is fast and
        # doesn't block on backends build/model downloads.
        try:
            container = docker_client.containers.run(
                image,
                name=name,
                detach=True,
                remove=False,
                entrypoint=["local-ai"],
                command=[
                    "run",
                    "--p2p",
                    "--peer-2-peer-network-id=p2p",
                    "--models-path=/tmp/empty-models",
                    "--preload-backend-only",
                    "--disable-web-ui",
                    "--disable-gallery-endpoint",
                    "--disable-metrics-endpoint",
                    "--log-level=info",
                ],
            )
        except Exception:
            # docker-py can leave a "created" container behind if start fails; remove it so we don't
            # accumulate caduceus-localai-token-gen-* containers over time.
            try:
                docker_client.containers.get(name).remove(force=True)
            except Exception:
                pass
            raise

        for raw in container.logs(stream=True, follow=True):
            if raw is None:
                continue
            line = raw.decode(errors="ignore").strip()
            match = export_pattern.search(line)
            if match:
                token = match.group(1).strip()
                break
            if "Generated Token" in line:
                saw_generated_banner = True
                continue
            if saw_generated_banner and base64_pattern.match(line):
                token = line.strip()
                break
            if time.time() - started > timeout_seconds:
                break
    finally:
        try:
            if container is not None:
                container.stop(timeout=3)
        except Exception:
            pass
        try:
            if container is not None:
                container.remove(force=True)
        except Exception:
            pass

    if not token:
        raise RuntimeError("Failed to generate LocalAI token (timed out waiting for export TOKEN=...)")
    return token


def _ensure_localai_models_volume_seeded(volume_name: str) -> bool:
    """
    Best-effort: create + seed a shared Docker volume for LocalAI models.

    Why: LocalAI can download multi-GB models into MODELS_PATH; without a shared volume, those downloads are lost
    whenever the dockerized host is recreated, forcing a re-download and delaying readiness (/readyz).

    Seeding approach:
    - If the volume already has data (or our marker file), do nothing.
    - Otherwise, copy /models from `localai-host:latest` into the volume once.
    """
    if not docker_client:
        return False

    volume_name = (volume_name or "").strip()
    if not volume_name:
        return False

    seed_image = os.getenv("LOCALAI_MODELS_SEED_IMAGE", "localai-host:latest").strip() or "localai-host:latest"

    with _LOCALAI_MODELS_VOLUME_LOCK:
        try:
            docker_client.volumes.get(volume_name)
        except Exception:
            try:
                docker_client.volumes.create(name=volume_name)
            except Exception:
                return False

        # If we can’t access the seed image, we can still use the volume as a persistent cache (LocalAI will fill it).
        try:
            docker_client.images.get(seed_image)
        except Exception:
            return True

        def _run_capture(cmd: str) -> str:
            cname = f"caduceus-localai-models-seed-{uuid.uuid4().hex[:10]}"
            try:
                out = docker_client.containers.run(
                    seed_image,
                    name=cname,
                    # IMPORTANT: override LocalAI image ENTRYPOINT so we can run simple shell commands.
                    entrypoint=["sh", "-lc"],
                    # `sh -lc` expects the script as a single argv item; docker-py will split strings into
                    # words which breaks multi-line scripts, so wrap it in a single-element list.
                    command=[cmd],
                    detach=False,
                    remove=True,
                    volumes={volume_name: {"bind": "/seed", "mode": "rw"}},
                )
                if isinstance(out, (bytes, bytearray)):
                    return out.decode("utf-8", errors="ignore")
                return str(out or "")
            except Exception:
                return ""
            finally:
                # If the container never started, docker-py might not auto-remove it; clean up by name.
                try:
                    docker_client.containers.get(cname).remove(force=True)
                except Exception:
                    pass

        marker_path = f"/seed/{LOCALAI_MODELS_VOLUME_MARKER}"

        # Quick check: already seeded / non-empty
        out = _run_capture(f"ls -A /seed 2>/dev/null | head -n 5 || true")
        if LOCALAI_MODELS_VOLUME_MARKER in out or (out or "").strip():
            # Ensure marker exists once we consider it usable.
            _run_capture(f"touch {shlex.quote(marker_path)} || true")
            return True

        # Seed from the host image's baked /models.
        seed_cmd = (
            "set -e\n"
            f"if [ -e {shlex.quote(marker_path)} ]; then exit 0; fi\n"
            "mkdir -p /seed\n"
            # If something wrote data already, don't overwrite; just mark.
            "if [ -n \"$(ls -A /seed 2>/dev/null | head -n 1)\" ]; then\n"
            f"  touch {shlex.quote(marker_path)}\n"
            "  exit 0\n"
            "fi\n"
            "cp -a /models/. /seed/ 2>/dev/null || true\n"
            f"touch {shlex.quote(marker_path)}\n"
        )
        _run_capture(seed_cmd)
        return True


def _patch_localai_definition(topology_data: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    """
    Best-effort: ensure LocalAI dockerized nodes have a runnable docker command and a valid P2P token.
    Returns (updated_topology_data, node_property_updates).
    """
    nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
    if not isinstance(nodes, list) or not nodes:
        return topology_data, []

    localai_nodes = [n for n in nodes if isinstance(n, dict) and _looks_like_localai_node(n)]
    if not localai_nodes:
        return topology_data, []

    # Find placeholder usage + any existing non-placeholder token.
    placeholder_seen = False
    existing_token = None
    for n in localai_nodes:
        props = n.get("properties")
        props = props if isinstance(props, dict) else {}
        env = _coerce_dict(props.get("docker_environment") or props.get("environment"))
        for key in ("TOKEN", "LOCALAI_P2P_TOKEN"):
            value = env.get(key)
            if value == LOCALAI_P2P_TOKEN_PLACEHOLDER:
                placeholder_seen = True
            elif isinstance(value, str) and value.strip():
                existing_token = existing_token or value.strip()

    token = existing_token
    if placeholder_seen and not token:
        token = _generate_localai_p2p_token()

    # Shared models volume to avoid re-downloading large models across restarts/topologies.
    models_volume_name = (os.getenv("LOCALAI_MODELS_VOLUME_NAME", "localai-models") or "").strip()
    # Mount path is where the persistent volume is attached inside LocalAI containers.
    # Keep it stable (default: /models) even if the runtime MODELS_PATH is a subdirectory like /models/cache.
    models_mount_path = (os.getenv("LOCALAI_MODELS_MOUNT_PATH", "/models") or "/models").strip() or "/models"
    models_runtime_path = (
        os.getenv("LOCALAI_MODELS_RUNTIME_PATH", f"{models_mount_path}/cache") or f"{models_mount_path}/cache"
    ).strip() or f"{models_mount_path}/cache"
    models_volume_ready = False
    if models_volume_name:
        try:
            models_volume_ready = _ensure_localai_models_volume_seeded(models_volume_name)
        except Exception:
            models_volume_ready = False

    # Avoid host port conflicts when multiple LocalAI topologies run concurrently.
    used_ports = _collect_used_host_ports()

    node_updates: list[tuple[str, dict[str, Any]]] = []
    for n in localai_nodes:
        node_id = n.get("id")
        if not node_id:
            continue
        props = n.get("properties")
        props = props if isinstance(props, dict) else {}
        docker_image = str(props.get("docker_image") or props.get("image") or "")
        docker_image_l = docker_image.lower()

        changed = False

        # Containernet (mininet.node.Docker) overwrites ENTRYPOINT and defaults to /bin/bash unless we pass dcmd.
        if not props.get("docker_command") and "localai" in docker_image_l:
            if "worker" in docker_image_l:
                props["docker_command"] = "/entrypoint-worker.sh"
            else:
                props["docker_command"] = "/entrypoint-host.sh"
            changed = True

        # If the LocalAI host publishes 8080, ensure the host port isn't already taken (e.g. another topology using 32778).
        if "worker" not in docker_image_l:
            published_ports = props.get("docker_ports") or props.get("published_ports")
            if isinstance(published_ports, dict):
                container_port_key = "8080/tcp"
                desired = published_ports.get(container_port_key)
                try:
                    desired_int = int(desired) if desired is not None else None
                except Exception:
                    desired_int = None

                if desired_int is None:
                    # Default host port when none is specified in the topology.
                    desired_int = 32778
                    published_ports[container_port_key] = desired_int
                    changed = True

                if desired_int in used_ports:
                    # Allocate an alternative port and persist it into the topology so the UI can show it.
                    new_port = _allocate_host_port(32779, 32999, used_ports)
                    published_ports[container_port_key] = int(new_port)
                    props["docker_ports"] = published_ports
                    changed = True

        env = _coerce_dict(props.get("docker_environment") or props.get("environment"))

        # Prevent accidental model downloads (and huge slow startups) unless explicitly enabled by the topology.
        # LocalAI reads many CLI flags from env (e.g. $AUTOLOAD_GALLERIES), but some setups also rely on
        # container-level envs like DISABLE_AUTODOWNLOAD. We set both families only when absent.
        if env.get("DISABLE_AUTODOWNLOAD") is None and env.get("LOCALAI_DISABLE_AUTODOWNLOAD") is None:
            env["DISABLE_AUTODOWNLOAD"] = "true"
            changed = True
        if env.get("AUTOLOAD_GALLERIES") is None and env.get("LOCALAI_AUTOLOAD_GALLERIES") is None:
            env["AUTOLOAD_GALLERIES"] = "false"
            changed = True
        if env.get("AUTOLOAD_BACKEND_GALLERIES") is None and env.get("LOCALAI_AUTOLOAD_BACKEND_GALLERIES") is None:
            env["AUTOLOAD_BACKEND_GALLERIES"] = "false"
            changed = True

        # LocalAI AIO images default to loading many heavyweight model YAMLs (including vision),
        # which triggers multi‑GB downloads and keeps the web UI "loading" for a long time.
        # Provide a lightweight default model set for the host unless the user already configured it.
        if "worker" not in docker_image_l:
            default_models = (
                os.getenv("LOCALAI_HOST_MODELS", "/models/tinyllama.yaml,/models/qwen2.yaml") or ""
            ).strip()
            if default_models and not str(env.get("MODELS") or "").strip():
                env["MODELS"] = default_models
                changed = True
            if not str(env.get("PROFILE") or "").strip():
                env["PROFILE"] = "cpu"
                changed = True
            # Disable automatic gallery preloads unless explicitly configured by the topology.
            if env.get("AUTO_LOAD_MODELS") is None:
                env["AUTO_LOAD_MODELS"] = "false"
                changed = True
            if env.get("PRELOAD_MODELS") is None:
                env["PRELOAD_MODELS"] = "[]"
                changed = True
            if env.get("GALLERIES") is None:
                env["GALLERIES"] = "[]"
                changed = True

        if token:
            for key in ("TOKEN", "LOCALAI_P2P_TOKEN"):
                if env.get(key) == LOCALAI_P2P_TOKEN_PLACEHOLDER:
                    env[key] = token
                    changed = True

        # Ensure LocalAI reads/writes models under a persistent path.
        # Prefer a subdirectory to avoid LocalAI autoloading every YAML in the volume root.
        if models_runtime_path and isinstance(models_runtime_path, str):
            current_models_path = str(env.get("MODELS_PATH") or "").strip()
            if not current_models_path or current_models_path == models_mount_path:
                env["MODELS_PATH"] = models_runtime_path
                changed = True

        # Mount a shared Docker volume at `models_mount_path` so downloaded models persist across recreations.
        if models_volume_name and models_volume_ready and models_mount_path:
            existing_volumes = props.get("docker_volumes") or props.get("volumes")

            # Containernet's Docker node expects `volumes` as a list of strings:
            #   ["/host/path:/container/path:rw", "named-volume:/container/path:rw"]
            # If we get a docker-py dict style, convert it.
            volumes_list: list[str] = []
            if isinstance(existing_volumes, list):
                volumes_list = [str(v) for v in existing_volumes if str(v).strip()]
            elif isinstance(existing_volumes, str) and existing_volumes.strip():
                volumes_list = [existing_volumes.strip()]
            elif isinstance(existing_volumes, dict):
                for src, spec in existing_volumes.items():
                    if not src:
                        continue
                    if isinstance(spec, dict) and spec.get("bind"):
                        bind = str(spec.get("bind"))
                        mode = str(spec.get("mode") or "rw")
                        volumes_list.append(f"{src}:{bind}:{mode}")

            already_mounted = any(f":{models_mount_path}:" in v or v.endswith(f":{models_mount_path}") for v in volumes_list)
            desired = f"{models_volume_name}:{models_mount_path}:rw"
            if not already_mounted:
                volumes_list.append(desired)
                props["docker_volumes"] = volumes_list
                changed = True
            elif isinstance(existing_volumes, dict) and volumes_list:
                # Normalize dict->list so downstream uses the format Containernet expects.
                props["docker_volumes"] = volumes_list
                changed = True
        if changed:
            props["docker_environment"] = env
            n["properties"] = props
            node_updates.append((str(node_id), props))

    return topology_data, node_updates


def _patch_dockerized_node_ports(topology_data: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    """
    Best-effort: prevent host port collisions for dockerized Mininet nodes when multiple topologies run concurrently.

    Many dockerized nodes publish ports on the *host* Docker engine (because Containernet uses the host docker.sock),
    so fixed host ports in topology definitions can collide across concurrently running emulations.
    """
    nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
    if not isinstance(nodes, list) or not nodes:
        return topology_data, []

    used_ports = _collect_used_host_ports()
    node_updates: list[tuple[str, dict[str, Any]]] = []

    # Default range for auto-assigned dockerized node host ports (safe high ephemeral range).
    # LocalAI keeps its own range logic; this patch is for everything else.
    start_port = int(os.getenv("DOCKERIZED_NODE_PORT_RANGE_START", "33000") or 33000)
    end_port = int(os.getenv("DOCKERIZED_NODE_PORT_RANGE_END", "39999") or 39999)
    if start_port < 1024:
        start_port = 33000
    if end_port <= start_port:
        end_port = max(start_port + 1000, 39999)

    for n in nodes:
        if not isinstance(n, dict):
            continue
        node_id = n.get("id")
        if not node_id:
            continue

        props = n.get("properties")
        props = props if isinstance(props, dict) else {}

        dockerized = props.get("dockerized", False)
        if isinstance(dockerized, str):
            dockerized = dockerized.strip().lower() in ("1", "true", "yes", "y", "on")
        if not dockerized:
            continue

        published_ports = props.get("docker_ports") or props.get("published_ports")
        if not isinstance(published_ports, dict) or not published_ports:
            continue

        # Skip LocalAI nodes here; LocalAI patch already manages its own default and conflict avoidance range.
        docker_image = str(props.get("docker_image") or props.get("image") or "").lower()
        if "localai" in docker_image:
            continue

        changed = False
        for container_port, host_binding in list(published_ports.items()):
            if not container_port:
                continue
            try:
                desired_int = int(host_binding) if host_binding is not None else None
            except Exception:
                desired_int = None
            if desired_int is None:
                continue
            if desired_int in used_ports:
                new_port = _allocate_host_port(start_port, end_port, used_ports)
                published_ports[container_port] = int(new_port)
                changed = True
            else:
                used_ports.add(desired_int)

        if changed:
            props["docker_ports"] = published_ports
            n["properties"] = props
            node_updates.append((str(node_id), props))

    return topology_data, node_updates


async def _force_recreate_and_start_emulation(
    topology_id: str, topology_data: Dict[str, Any], options: Optional[Dict[str, Any]] = None
) -> tuple[Dict[str, Any], str, str]:
    """Best-effort self-repair: recreate emulation container + retry StartEmulation once."""
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    grpc_client_manager.remove_client(topology_id)
    active_emulations.delete(topology_id)

    container_name = f"caduceus-emu-{topology_id[:8]}"
    try:
        docker_client.containers.get(container_name).remove(force=True)
    except docker.errors.NotFound:
        pass
    except Exception as exc:
        logger.warning("Failed to remove emulation container %s: %s", container_name, exc)

    cname, port, container_id = spawn_emulation_container(topology_id, force_recreate=True)
    client = grpc_client_manager.create_client(topology_id, cname, port)
    result = await asyncio.to_thread(client.start_emulation, topology_id, topology_data)
    return result, container_id, cname


def _read_emulation_state_from_container(container_name: str) -> Optional[Dict[str, Any]]:
    """Read `/var/lib/caduceus/emulation_state.json` from an emulation container (best-effort)."""
    if not docker_client:
        return None
    try:
        container = docker_client.containers.get(container_name)
    except Exception:
        return None

    try:
        res = container.exec_run(["sh", "-lc", "cat /var/lib/caduceus/emulation_state.json 2>/dev/null || true"], demux=True)
        out = getattr(res, "output", None)
        stdout_b = b""
        if isinstance(out, tuple) and len(out) == 2:
            stdout_b = out[0] or b""
        elif isinstance(out, (bytes, bytearray)):
            stdout_b = bytes(out)
        raw = stdout_b.decode("utf-8", errors="replace").strip()
        if not raw:
            return None
        state = json.loads(raw)
        return state if isinstance(state, dict) else None
    except Exception:
        return None


_SENSITIVE_ENV_KEY_RE = re.compile(r"(password|token|secret|api[_-]?key|private[_-]?key)", re.IGNORECASE)


PROJECT_INFRASTRUCTURE_SERVICES: list[dict[str, Any]] = [
    {"id": "grafana", "container_name": "caduceus-grafana", "category": "monitoring", "default_port": 3000},
    {"id": "prometheus", "container_name": "caduceus-prometheus", "category": "monitoring", "default_port": 9090},
    {"id": "consul", "container_name": "caduceus-consul", "category": "discovery", "default_port": 8500},
    {"id": "influxdb", "container_name": "caduceus-influxdb", "category": "database", "default_port": 8086},
    {"id": "pgadmin", "container_name": "caduceus-pgadmin", "category": "database", "default_port": 80},
    {"id": "mongo-express", "container_name": "caduceus-mongo-express", "category": "database", "default_port": 8081},
    {"id": "rabbitmq", "container_name": "caduceus-rabbitmq", "category": "messaging", "default_port": 5672},
    {"id": "kafka", "container_name": "caduceus-kafka", "category": "messaging", "default_port": 9092},
    {"id": "zookeeper", "container_name": "caduceus-zookeeper", "category": "messaging", "default_port": 2181},
    {"id": "schema-registry", "container_name": "caduceus-schema-registry", "category": "messaging", "default_port": 8081},
    {"id": "kafka-connect", "container_name": "caduceus-kafka-connect", "category": "messaging", "default_port": 8083},
    {"id": "kafka-ui", "container_name": "caduceus-kafka-ui", "compose_service": "kafka-ui", "category": "messaging", "default_port": 8080},
    {"id": "flink", "container_name": "caduceus-flink-jobmanager", "category": "streaming", "default_port": 8081},
    {"id": "spark", "container_name": "caduceus-spark-master", "category": "analytics", "default_port": 8080},
    {"id": "hdfs", "container_name": "caduceus-hdfs-namenode", "category": "storage", "default_port": 9870},
    {"id": "hive-metastore-db", "container_name": "caduceus-hive-metastore-db", "compose_service": "hive-metastore-db", "category": "database", "default_port": 5432},
    {"id": "hive-metastore", "container_name": "caduceus-hive-metastore", "compose_service": "hive-metastore", "category": "analytics", "default_port": 9083},
    {"id": "hive", "container_name": "caduceus-hive-server2", "compose_service": "hive-server2", "category": "analytics", "default_port": 10002},
    {"id": "hue", "container_name": "caduceus-hue", "category": "analytics", "default_port": 8888},
    {"id": "postgres", "container_name": "caduceus-postgres", "category": "database", "default_port": 5432},
    {"id": "mongodb", "container_name": "caduceus-mongodb", "category": "database", "default_port": 27017},
    {"id": "redis", "container_name": "caduceus-redis", "category": "database", "default_port": 6379},
    {"id": "nginx", "container_name": "caduceus-nginx", "category": "proxy", "default_port": 80},
]


def _env_list_to_dict(env_list: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(env_list, list):
        return out
    for item in env_list:
        if not isinstance(item, str) or "=" not in item:
            continue
        k, v = item.split("=", 1)
        out[k] = v
    return out


def _redact_env(env: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for k, v in (env or {}).items():
        if _SENSITIVE_ENV_KEY_RE.search(k):
            redacted[k] = "*****"
        else:
            redacted[k] = v
    return redacted


def _extract_port_bindings(container: Any) -> list[dict[str, Any]]:
    ports = (getattr(container, "attrs", {}) or {}).get("NetworkSettings", {}).get("Ports", {}) or {}
    items: list[dict[str, Any]] = []
    for container_port, bindings in ports.items():
        if not bindings:
            items.append({"container_port": container_port, "host": None})
            continue
        for b in bindings:
            items.append(
                {
                    "container_port": container_port,
                    "host": {
                        "ip": b.get("HostIp"),
                        "port": b.get("HostPort"),
                    },
                }
            )
    return items


def _container_details(container: Any) -> dict[str, Any]:
    attrs = getattr(container, "attrs", {}) or {}
    config = (attrs.get("Config") or {}) if isinstance(attrs, dict) else {}
    env = _redact_env(_env_list_to_dict(config.get("Env")))

    return {
        "name": getattr(container, "name", ""),
        "container_id": getattr(container, "id", None),
        "status": getattr(container, "status", "unknown"),
        "image": getattr(getattr(container, "image", None), "tags", None),
        "labels": getattr(container, "labels", {}) or {},
        "ports": _extract_port_bindings(container),
        "env": env,
    }


def _index_infra_containers() -> dict[str, Any]:
    """
    Build indices for containers on the current Docker host.

    Some environments ignore `container_name` or prefix it; so we also index by:
    - compose service label (`com.docker.compose.service`)
    - suffix match (e.g. `<prefix>_<container_name>`)
    """
    containers = docker_client.containers.list(all=True) if docker_client else []
    by_name: dict[str, Any] = {}
    by_compose_service: dict[str, list[Any]] = {}
    by_suffix: dict[str, list[Any]] = {}

    for c in containers:
        name = getattr(c, "name", None)
        if name:
            by_name[name] = c
        labels = getattr(c, "labels", {}) or {}
        svc = labels.get("com.docker.compose.service")
        if svc:
            by_compose_service.setdefault(str(svc), []).append(c)
        if name and "_" in name:
            suffix = name.split("_", 1)[1]
            by_suffix.setdefault(suffix, []).append(c)

    return {
        "by_name": by_name,
        "by_compose_service": by_compose_service,
        "by_suffix": by_suffix,
    }


def _pick_best_container(candidates: list[Any]) -> Optional[Any]:
    if not candidates:
        return None
    for c in candidates:
        if getattr(c, "status", "") == "running":
            return c
    return candidates[0]


def _resolve_infrastructure_container(spec: dict[str, Any], index: dict[str, Any]) -> Optional[Any]:
    if not docker_client:
        return None

    target_name = spec.get("container_name")
    if isinstance(target_name, str) and target_name:
        found = (index.get("by_name") or {}).get(target_name)
        if found:
            return found
        suffix_matches = (index.get("by_suffix") or {}).get(target_name) or []
        if suffix_matches:
            return _pick_best_container(suffix_matches)

    compose_service = spec.get("compose_service") or spec.get("id")
    if compose_service:
        matches = (index.get("by_compose_service") or {}).get(str(compose_service)) or []
        if matches:
            return _pick_best_container(matches)

    return None


def get_infrastructure_status(include_stopped: bool = True) -> dict[str, Any]:
    if not docker_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker client not available"
        )

    items: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    idx = _index_infra_containers()

    for spec in PROJECT_INFRASTRUCTURE_SERVICES:
        container = _resolve_infrastructure_container(spec, idx)
        if not container:
            missing.append(spec)
            continue

        if include_stopped or getattr(container, "status", "") == "running":
            items.append({**spec, "container": _container_details(container)})

    return {"items": items, "missing": missing, "total": len(items), "missing_total": len(missing)}


def ensure_infrastructure_running(service_ids: Optional[list[str]] = None) -> dict[str, Any]:
    if not docker_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker client not available"
        )

    wanted = set(
        service_ids
        or [
            "grafana",
            "prometheus",
            "consul",
            "influxdb",
            "pgadmin",
            "mongo-express",
            "postgres",
            "mongodb",
            "redis",
            "kafka",
            "zookeeper",
            "schema-registry",
            "kafka-connect",
            "kafka-ui",
            "flink",
            "spark",
            "hdfs",
            "hive-metastore-db",
            "hive-metastore",
            "hive",
            "hue",
            "rabbitmq",
        ]
    )
    specs = [s for s in PROJECT_INFRASTRUCTURE_SERVICES if s["id"] in wanted]

    started: list[str] = []
    already_running: list[str] = []
    missing: list[str] = []
    failed: list[dict[str, Any]] = []
    idx = _index_infra_containers()

    for spec in specs:
        container = _resolve_infrastructure_container(spec, idx)
        if not container:
            missing.append(spec["id"])
            continue

        if getattr(container, "status", "") == "running":
            already_running.append(spec["id"])
            continue

        try:
            container.start()
            started.append(spec["id"])
        except Exception as exc:
            failed.append({"id": spec["id"], "error": str(exc)})

    return {
        "started": started,
        "already_running": already_running,
        "missing": missing,
        "failed": failed,
    }


def _get_host_port(container: Any, container_port: str) -> Optional[int]:
    ports = (getattr(container, "attrs", {}) or {}).get("NetworkSettings", {}).get("Ports", {}) or {}
    bindings = ports.get(container_port)
    if not bindings:
        return None
    try:
        return int(bindings[0].get("HostPort"))
    except Exception:
        return None


def get_topology_emulation_container(topology_id: str) -> dict[str, Any]:
    """
    Resolve emulation container details for a topology.
    Returns a stable payload even if container isn't running.
    """
    record = active_emulations.get(topology_id) or {}
    container_name = record.get("container_name") or f"caduceus-emu-{topology_id[:8]}"

    payload: dict[str, Any] = {
        "topology_id": topology_id,
        "emulation_id": record.get("emulation_id"),
        "status": record.get("status"),
        "container_name": container_name,
        "container": None,
        "grpc_host_port": None,
    }

    if not docker_client:
        return payload

    try:
        container = docker_client.containers.get(container_name)
    except docker.errors.NotFound:
        return payload
    except Exception as exc:
        payload["error"] = str(exc)
        return payload

    payload["container"] = _container_details(container)
    payload["grpc_host_port"] = _get_host_port(container, "50051/tcp")
    return payload


def sync_topology_infrastructure_to_consul(topology_id: str) -> None:
    """
    Persist a topology-scoped infrastructure snapshot to Consul KV.
    Other services can consume this to auto-configure on topology/emulation changes.
    """
    try:
        influx_bucket = None
        try:
            influx_bucket = consul_client.get_config(f"caduceus/topologies/{topology_id}/influxdb_bucket")
        except Exception:
            influx_bucket = None

        snapshot = {
            "topology_id": topology_id,
            "updated_at": _iso_now(),
            "emulation": get_topology_emulation_container(topology_id),
            "infrastructure": get_infrastructure_status(include_stopped=True),
            "topology_resources": {
                "influxdb_bucket": influx_bucket,
            },
        }
        consul_client.set_config(f"caduceus/topologies/{topology_id}/infrastructure", json.dumps(snapshot))
    except Exception as exc:
        logger.warning("Failed to sync topology %s infrastructure to Consul: %s", topology_id, exc)


async def ensure_topology_observability(topology_id: str) -> None:
    """
    Ensure topology-scoped monitoring resources exist (bucket, Grafana datasource) and persist them to Consul.
    Uses shared infrastructure containers, but isolates data/config per topology.
    """
    bucket: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{MONITORING_URL}/api/monitoring/topologies/{topology_id}/influxdb/ensure")
        if res.status_code == 200:
            payload = res.json() or {}
            if payload.get("success") and payload.get("bucket"):
                bucket = str(payload["bucket"])
    except Exception as exc:
        logger.warning("Topology %s bucket ensure failed: %s", topology_id, exc)

    grafana_datasource_name: Optional[str] = None
    grafana_datasource_uid: Optional[str] = None

    if bucket:
        try:
            consul_client.set_config(f"caduceus/topologies/{topology_id}/influxdb_bucket", bucket)
        except Exception:
            pass

    # Provision Grafana datasource (best-effort)
    if bucket:
        try:
            ds_name = f"topology_{topology_id[:8]}"
            auth = (GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD)
            datasource = {
                "name": ds_name,
                "type": "influxdb",
                "access": "proxy",
                "url": INFLUXDB_URL,
                "basicAuth": False,
                "isDefault": False,
                "jsonData": {"version": "Flux", "organization": INFLUXDB_ORG, "defaultBucket": bucket},
                "secureJsonData": {"token": INFLUXDB_TOKEN},
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                existing = await client.get(f"{GRAFANA_INTERNAL_URL}/api/datasources/name/{ds_name}", auth=auth)
                if existing.status_code == 200:
                    ds_id = (existing.json() or {}).get("id")
                    if ds_id:
                        await client.put(
                            f"{GRAFANA_INTERNAL_URL}/api/datasources/{ds_id}",
                            json={**datasource, "id": ds_id},
                            auth=auth,
                        )
                else:
                    await client.post(f"{GRAFANA_INTERNAL_URL}/api/datasources", json=datasource, auth=auth)

                final = await client.get(f"{GRAFANA_INTERNAL_URL}/api/datasources/name/{ds_name}", auth=auth)
                if final.status_code == 200:
                    final_json = final.json() or {}
                    grafana_datasource_name = ds_name
                    grafana_datasource_uid = final_json.get("uid")
        except Exception as exc:
            logger.warning("Topology %s Grafana datasource ensure failed: %s", topology_id, exc)

    if grafana_datasource_name:
        try:
            consul_client.set_config(
                f"caduceus/topologies/{topology_id}/grafana_datasource_name",
                grafana_datasource_name,
            )
        except Exception:
            pass

    if grafana_datasource_uid:
        try:
            consul_client.set_config(
                f"caduceus/topologies/{topology_id}/grafana_datasource_uid",
                str(grafana_datasource_uid),
            )
        except Exception:
            pass

    sync_topology_infrastructure_to_consul(topology_id)


def ensure_topology_isolated_infra(topology_id: str) -> dict[str, Any]:
    """
    Ensure a full isolated infra stack (InfluxDB/Grafana/Prometheus/Consul/RabbitMQ/Kafka(+UI)) exists for a topology.
    The stack is separate per topology (containers + volumes + network), and connection details are stored in Consul.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    net_name = _topo_network_name(topology_id)
    _ensure_network(net_name)

    TOPOLOGY_INFRA_STACK_VERSION = "2025-12-16"

    existing_payload: Optional[dict[str, Any]] = None
    existing_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_infra")
    if existing_raw:
        try:
            candidate = json.loads(existing_raw)
            if isinstance(candidate, dict) and candidate.get("services"):
                existing_payload = candidate
        except Exception:
            existing_payload = None

    used_ports = _collect_used_host_ports()

    def reuse_or_allocate(service: str, start: int, end: int) -> int:
        try:
            maybe = (
                (existing_payload or {})
                .get("services", {})
                .get(service, {})
                .get("host_port")
            )
            if isinstance(maybe, int) and 1 <= maybe <= 65535:
                return maybe
        except Exception:
            pass
        return _allocate_host_port(start, end, used_ports)

    host_ports: dict[str, int] = {
        "grafana": reuse_or_allocate("grafana", 33000, 33999),
        "prometheus": reuse_or_allocate("prometheus", 34000, 34999),
        "consul": reuse_or_allocate("consul", 35000, 35999),
        "influxdb": reuse_or_allocate("influxdb", 36000, 36999),
        "rabbitmq": reuse_or_allocate("rabbitmq", 37000, 37999),
        "kafka-ui": reuse_or_allocate("kafka-ui", 38000, 38999),
        "portainer": reuse_or_allocate("portainer", 39000, 39999),
        "portainer-http": reuse_or_allocate("portainer-http", 40000, 40999),
    }

    secrets_payload = _ensure_topology_isolated_infra_secrets(topology_id, existing_payload)
    influx_org = secrets_payload["influx_org"]
    influx_bucket = secrets_payload["influx_bucket"]
    influx_token = secrets_payload["influx_token"]
    influx_admin_user = secrets_payload["influx_admin_user"]
    influx_admin_password = secrets_payload["influx_admin_password"]
    grafana_admin_user = secrets_payload["grafana_admin_user"]
    grafana_admin_password = secrets_payload["grafana_admin_password"]
    rabbitmq_user = secrets_payload["rabbitmq_user"]
    rabbitmq_password = secrets_payload["rabbitmq_password"]
    rabbitmq_vhost = secrets_payload["rabbitmq_vhost"]
    portainer_admin_user = secrets_payload["portainer_admin_user"]
    portainer_admin_password = secrets_payload["portainer_admin_password"]
    portainer_view_user = secrets_payload["portainer_view_user"]
    portainer_view_password = secrets_payload["portainer_view_password"]

    # Volumes
    for svc in (
        "influxdb",
        "grafana",
        "prometheus-config",
        "prometheus-tsdb",
        "consul",
        "rabbitmq",
        "portainer",
        "kafka",
        "zookeeper",
    ):
        vname = _topo_volume_name(topology_id, svc)
        try:
            docker_client.volumes.get(vname)
        except Exception:
            try:
                docker_client.volumes.create(name=vname)
            except Exception:
                pass

    def ensure_container(service_id: str, run_kwargs: dict[str, Any]) -> Any:
        cname = _topo_container_name(topology_id, service_id)
        try:
            c = docker_client.containers.get(cname)
            try:
                c.reload()
            except Exception:
                pass

            labels = (getattr(c, "attrs", {}) or {}).get("Config", {}).get("Labels", {}) or {}
            version = labels.get("caduceus.infra_stack_version")
            if version != TOPOLOGY_INFRA_STACK_VERSION:
                try:
                    c.remove(force=True)
                except Exception:
                    pass
                try:
                    _ensure_image(str(run_kwargs.get("image") or ""))
                except Exception:
                    pass
                return docker_client.containers.run(**run_kwargs)

            # If the container is not running, recreate it (we can't reliably "start" infra containers
            # because some images initialize credentials/volumes only on first boot).
            if getattr(c, "status", "") != "running":
                try:
                    c.remove(force=True)
                except Exception:
                    pass
                try:
                    _ensure_image(str(run_kwargs.get("image") or ""))
                except Exception:
                    pass
                return docker_client.containers.run(**run_kwargs)

            # Ensure restart policy is present for already-running containers.
            try:
                desired_restart = run_kwargs.get("restart_policy")
                if isinstance(desired_restart, dict) and desired_restart.get("Name"):
                    c.update(restart_policy=desired_restart)
            except Exception:
                pass

            # If this service is supposed to be exposed on a fixed host port, make sure the binding exists.
            # If it doesn't, we must recreate the container (Docker can't add published ports to an existing container).
            expected_ports = run_kwargs.get("ports") if isinstance(run_kwargs.get("ports"), dict) else None
            if expected_ports:
                missing_binding = False
                try:
                    for container_port in expected_ports.keys():
                        if _get_host_port(c, str(container_port)) is None:
                            missing_binding = True
                            break
                except Exception:
                    missing_binding = True
                if missing_binding:
                    try:
                        c.remove(force=True)
                    except Exception:
                        pass
                    try:
                        _ensure_image(str(run_kwargs.get("image") or ""))
                    except Exception:
                        pass
                    return docker_client.containers.run(**run_kwargs)

            return c
        except Exception:
            try:
                _ensure_image(str(run_kwargs.get("image") or ""))
            except Exception:
                pass
            return docker_client.containers.run(**run_kwargs)

    def _sync_host_port(service_id: str, container: Any, container_port: str) -> None:
        try:
            container.reload()
        except Exception:
            pass
        hp = _get_host_port(container, container_port)
        if isinstance(hp, int) and 1 <= hp <= 65535:
            host_ports[service_id] = hp

    # Core services (run on MAIN network, then connect to topology network with stable aliases)
    influx = ensure_container(
        "influxdb",
        {
            "image": "influxdb:2.7-alpine",
            "name": _topo_container_name(topology_id, "influxdb"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "influxdb"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "environment": {
                "DOCKER_INFLUXDB_INIT_MODE": "setup",
                "DOCKER_INFLUXDB_INIT_USERNAME": influx_admin_user,
                "DOCKER_INFLUXDB_INIT_PASSWORD": influx_admin_password,
                "DOCKER_INFLUXDB_INIT_ORG": influx_org,
                "DOCKER_INFLUXDB_INIT_BUCKET": influx_bucket,
                "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN": influx_token,
            },
            "volumes": {
                _topo_volume_name(topology_id, "influxdb"): {"bind": "/var/lib/influxdb2", "mode": "rw"},
            },
            "ports": {"8086/tcp": host_ports["influxdb"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(influx, net_name, aliases=["influxdb"])
    _sync_host_port("influxdb", influx, "8086/tcp")

    grafana = ensure_container(
        "grafana",
        {
            "image": "grafana/grafana:10.2.2",
            "name": _topo_container_name(topology_id, "grafana"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "grafana"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "environment": {
                "GF_SECURITY_ADMIN_USER": grafana_admin_user,
                "GF_SECURITY_ADMIN_PASSWORD": grafana_admin_password,
                "GF_SECURITY_ALLOW_EMBEDDING": "true",
            },
            "volumes": {
                _topo_volume_name(topology_id, "grafana"): {"bind": "/var/lib/grafana", "mode": "rw"},
            },
            "ports": {"3000/tcp": host_ports["grafana"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(grafana, net_name, aliases=["grafana"])
    _sync_host_port("grafana", grafana, "3000/tcp")

    consul = ensure_container(
        "consul",
        {
            "image": "hashicorp/consul:latest",
            "name": _topo_container_name(topology_id, "consul"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "consul"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "command": "agent -dev -ui -client=0.0.0.0",
            "environment": {
                "CONSUL_BIND_INTERFACE": "eth0",
            },
            "volumes": {
                _topo_volume_name(topology_id, "consul"): {"bind": "/consul/data", "mode": "rw"},
            },
            "ports": {"8500/tcp": host_ports["consul"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(consul, net_name, aliases=["consul"])
    _sync_host_port("consul", consul, "8500/tcp")

    rabbit = ensure_container(
        "rabbitmq",
        {
            "image": "rabbitmq:3.12-management-alpine",
            "name": _topo_container_name(topology_id, "rabbitmq"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "rabbitmq"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "environment": {
                "RABBITMQ_DEFAULT_USER": rabbitmq_user,
                "RABBITMQ_DEFAULT_PASS": rabbitmq_password,
                "RABBITMQ_DEFAULT_VHOST": rabbitmq_vhost,
            },
            "volumes": {
                _topo_volume_name(topology_id, "rabbitmq"): {"bind": "/var/lib/rabbitmq", "mode": "rw"},
            },
            "ports": {"15672/tcp": host_ports["rabbitmq"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(rabbit, net_name, aliases=["rabbitmq"])
    _sync_host_port("rabbitmq", rabbit, "15672/tcp")

    zk = ensure_container(
        "zookeeper",
        {
            "image": "confluentinc/cp-zookeeper:7.5.0",
            "name": _topo_container_name(topology_id, "zookeeper"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "zookeeper"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "environment": {
                "ZOOKEEPER_CLIENT_PORT": "2181",
                "ZOOKEEPER_TICK_TIME": "2000",
            },
            "volumes": {
                _topo_volume_name(topology_id, "zookeeper"): {"bind": "/var/lib/zookeeper/data", "mode": "rw"},
            },
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(zk, net_name, aliases=["zookeeper"])

    zk_host = _topo_container_name(topology_id, "zookeeper")
    kafka_host = _topo_container_name(topology_id, "kafka")

    kafka_run_kwargs = {
        "image": "confluentinc/cp-kafka:7.5.0",
        "name": _topo_container_name(topology_id, "kafka"),
        "detach": True,
        "remove": False,
        "restart_policy": {"Name": "unless-stopped"},
        "labels": {**_topology_infra_labels(topology_id, "kafka"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
        "environment": {
            "KAFKA_BROKER_ID": "1",
            "KAFKA_ZOOKEEPER_CONNECT": f"{zk_host}:2181",
            "KAFKA_LISTENERS": "PLAINTEXT://0.0.0.0:9092",
            "KAFKA_ADVERTISED_LISTENERS": f"PLAINTEXT://{kafka_host}:9092",
            "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT",
            "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
            "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
        },
        "volumes": {
            _topo_volume_name(topology_id, "kafka"): {"bind": "/var/lib/kafka/data", "mode": "rw"},
        },
        "network": MAIN_DOCKER_NETWORK,
    }

    kafka = ensure_container("kafka", kafka_run_kwargs)
    _connect_to_network(kafka, net_name, aliases=["kafka"])

    # Best-effort self-heal for previously misconfigured topology Kafka volumes (cluster-id mismatch, etc).
    # Prefer patching meta.properties to match ZK cluster id (preserves data), and only wipe as a fallback.
    try:
        stable_seconds = 0
        last_restart_count: Optional[int] = None
        for _ in range(30):
            time.sleep(1)
            try:
                kafka.reload()
            except Exception:
                pass

            state = (getattr(kafka, "attrs", {}) or {}).get("State", {}) or {}
            status = state.get("Status") or getattr(kafka, "status", "")
            restarting = bool(state.get("Restarting"))
            restart_count = state.get("RestartCount")
            try:
                restart_count = int(restart_count) if restart_count is not None else None
            except Exception:
                restart_count = None

            is_stable_running = (
                status == "running"
                and not restarting
                and (restart_count is None or last_restart_count is None or restart_count == last_restart_count)
            )
            if is_stable_running:
                stable_seconds += 1
                if stable_seconds >= 5:
                    break
            else:
                stable_seconds = 0

            last_restart_count = restart_count

        if stable_seconds < 5:
            logs = ""
            try:
                raw_logs = kafka.logs(tail=400)
                logs = raw_logs.decode("utf-8", errors="ignore") if isinstance(raw_logs, (bytes, bytearray)) else str(raw_logs)
            except Exception:
                logs = ""

            def _patch_kafka_cluster_id(new_cluster_id: str) -> bool:
                if not docker_client:
                    return False
                vname = _topo_volume_name(topology_id, "kafka")
                cmd = (
                    "set -e\n"
                    "if [ ! -f /data/meta.properties ]; then exit 2; fi\n"
                    f"CID={shlex.quote(str(new_cluster_id))}\n"
                    "if grep -q '^cluster\\.id=' /data/meta.properties; then\n"
                    "  sed -i \"s/^cluster\\\\.id=.*/cluster.id=$CID/\" /data/meta.properties\n"
                    "else\n"
                    "  echo \"cluster.id=$CID\" >> /data/meta.properties\n"
                    "fi\n"
                    "cat /data/meta.properties | tail -n 20\n"
                )
                try:
                    docker_client.containers.run(
                        image="alpine:3.19",
                        command=["sh", "-lc", cmd],
                        volumes={vname: {"bind": "/data", "mode": "rw"}},
                        detach=False,
                        remove=True,
                    )
                    return True
                except Exception:
                    return False

            needs_repair = (
                "InconsistentClusterIdException" in logs
                or "join the wrong cluster" in logs
                or "NodeExistsException" in logs
            )
            if needs_repair:
                desired_cluster_id = None
                try:
                    m = re.search(r"Cluster ID = ([A-Za-z0-9_-]+)", logs)
                    if m:
                        desired_cluster_id = m.group(1)
                except Exception:
                    desired_cluster_id = None

                if desired_cluster_id:
                    logger.warning(
                        "Kafka for topology %s has cluster-id mismatch; patching meta.properties to %s",
                        topology_id,
                        desired_cluster_id,
                    )
                    try:
                        kafka.remove(force=True)
                    except Exception:
                        pass
                    if _patch_kafka_cluster_id(desired_cluster_id):
                        kafka = docker_client.containers.run(**kafka_run_kwargs)
                        _connect_to_network(kafka, net_name, aliases=["kafka"])
                    else:
                        logger.warning("Kafka for topology %s: failed to patch meta.properties; wiping kafka volume", topology_id)
                        try:
                            vname = _topo_volume_name(topology_id, "kafka")
                            docker_client.containers.run(
                                image="alpine:3.19",
                                command=["sh", "-c", "rm -rf /data/* || true"],
                                volumes={vname: {"bind": "/data", "mode": "rw"}},
                                detach=False,
                                remove=True,
                            )
                        except Exception:
                            pass
                        kafka = docker_client.containers.run(**kafka_run_kwargs)
                        _connect_to_network(kafka, net_name, aliases=["kafka"])
    except Exception:
        pass

    kafka_ui = ensure_container(
        "kafka-ui",
        {
            "image": "provectuslabs/kafka-ui:latest",
            "name": _topo_container_name(topology_id, "kafka-ui"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "kafka-ui"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "environment": {
                "KAFKA_CLUSTERS_0_NAME": f"topology-{topology_id[:8]}",
                "KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS": f"{kafka_host}:9092",
                "DYNAMIC_CONFIG_ENABLED": "true",
            },
            "ports": {"8080/tcp": host_ports["kafka-ui"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(kafka_ui, net_name, aliases=["kafka-ui"])
    _sync_host_port("kafka-ui", kafka_ui, "8080/tcp")

    portainer = ensure_container(
        "portainer",
        {
            "image": "portainer/portainer-ce:latest",
            "name": _topo_container_name(topology_id, "portainer"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "portainer"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "volumes": {
                _topo_volume_name(topology_id, "portainer"): {"bind": "/data", "mode": "rw"},
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
            },
            # 9443 = HTTPS UI; 9000 = legacy HTTP UI (use only if your client can't do HTTPS).
            "ports": {"9443/tcp": host_ports["portainer"], "9000/tcp": host_ports["portainer-http"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(portainer, net_name, aliases=["portainer"])
    _sync_host_port("portainer", portainer, "9443/tcp")
    _sync_host_port("portainer-http", portainer, "9000/tcp")

    # Portainer will redirect to /timeout.html if the admin user isn't created shortly after first boot.
    # Auto-initialize the admin account so the UI is usable even if the user doesn't complete the wizard quickly.
    try:
        cname = _topo_container_name(topology_id, "portainer")
        base = f"http://{cname}:9000"
        init_payload = {"Username": str(portainer_admin_user), "Password": str(portainer_admin_password)}

        def _wait_portainer_ready(max_seconds: int = 60) -> None:
            with httpx.Client(timeout=3.0, follow_redirects=False) as client:
                deadline = time.time() + max_seconds
                while time.time() < deadline:
                    try:
                        r = client.get(f"{base}/api/status")
                        if r.status_code in (200, 401):
                            return
                    except Exception:
                        pass
                    time.sleep(1)

        def _try_admin_init() -> tuple[Optional[int], str]:
            with httpx.Client(timeout=5.0, follow_redirects=False) as client:
                try:
                    r = client.post(f"{base}/api/users/admin/init", json=init_payload)
                    reason = str(r.headers.get("Redirect-Reason") or "")
                    return int(r.status_code), reason
                except Exception as exc:
                    return None, str(exc)

        _wait_portainer_ready(60)
        status_code, reason = _try_admin_init()
        if status_code == 303 and reason.lower() == "admininittimeout":
            try:
                portainer.restart()
            except Exception:
                pass
            _wait_portainer_ready(60)
            _try_admin_init()
    except Exception:
        pass

    # Create a restricted Portainer user that can only see this topology's containers.
    try:
        topo_container_ids: list[str] = []
        try:
            for c in docker_client.containers.list(all=True, filters={"label": f"caduceus.topology_id={topology_id}"}):
                cid = getattr(c, "id", None)
                if cid:
                    topo_container_ids.append(str(cid))
        except Exception:
            topo_container_ids = []

        # Also include dockerized hosts created by Containernet (`mn.<runtime>`). These containers typically
        # don't have our topology labels, so derive them from the topology definition.
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}")
            if r.status_code == 200:
                topo = r.json() or {}
                nodes = topo.get("nodes") or topo.get("devices") or []
                if isinstance(nodes, list):
                    for n in nodes:
                        if not isinstance(n, dict):
                            continue
                        props = n.get("properties") or {}
                        if not isinstance(props, dict):
                            continue
                        dockerized = props.get("dockerized")
                        if isinstance(dockerized, str):
                            dockerized = dockerized.strip().lower() in ("true", "1", "yes")
                        dockerized = bool(dockerized) or bool(props.get("docker_image") or props.get("image"))
                        if not dockerized:
                            continue
                        runtime = props.get("runtime_name")
                        if not runtime:
                            continue
                        try:
                            mn = docker_client.containers.get(f"mn.{runtime}")
                            if getattr(mn, "id", None):
                                topo_container_ids.append(str(mn.id))
                        except Exception:
                            continue
        except Exception:
            pass

        _provision_portainer_topology_view(
            topology_id,
            portainer_base=f"http://{_topo_container_name(topology_id, 'portainer')}:9000",
            admin_user=str(portainer_admin_user),
            admin_password=str(portainer_admin_password),
            view_user=str(portainer_view_user),
            view_password=str(portainer_view_password),
            docker_container_ids=sorted(set(topo_container_ids)),
        )
    except Exception:
        pass

    # Prometheus config (minimal)
    prom_cfg = f"""global:
  scrape_interval: 10s

scrape_configs:
  - job_name: 'orchestrator'
    static_configs:
      - targets: ['orchestrator-service:8002']
"""
    prom_cfg_vol = _topo_volume_name(topology_id, "prometheus-config")
    tmp = None
    try:
        tmp = docker_client.containers.create(
            image="alpine:3.19",
            command=["sh", "-c", "sleep 60"],
            volumes={prom_cfg_vol: {"bind": "/etc/prometheus", "mode": "rw"}},
            detach=True,
            remove=True,
        )
        tmp.start()
        import io
        import tarfile

        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            data = prom_cfg.encode("utf-8")
            info = tarfile.TarInfo(name="prometheus.yml")
            info.size = len(data)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
        tarstream.seek(0)
        docker_client.api.put_archive(tmp.id, "/etc/prometheus", tarstream.read())
    except Exception:
        pass
    finally:
        try:
            if tmp is not None:
                tmp.stop(timeout=1)
        except Exception:
            pass

    prom = ensure_container(
        "prometheus",
        {
            "image": "prom/prometheus:v2.48.0",
            "name": _topo_container_name(topology_id, "prometheus"),
            "detach": True,
            "remove": False,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_infra_labels(topology_id, "prometheus"), "caduceus.infra_stack_version": TOPOLOGY_INFRA_STACK_VERSION},
            "command": [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
            ],
            "volumes": {
                prom_cfg_vol: {"bind": "/etc/prometheus", "mode": "rw"},
                _topo_volume_name(topology_id, "prometheus-tsdb"): {"bind": "/prometheus", "mode": "rw"},
            },
            "ports": {"9090/tcp": host_ports["prometheus"]},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(prom, net_name, aliases=["prometheus"])
    _sync_host_port("prometheus", prom, "9090/tcp")

    # Ensure service logins match what we show in the UI (best-effort).
    # Many images only apply env-provided passwords on the first boot; with persistent volumes we must reset them.
    try:
        sync_topology_isolated_infra_logins(topology_id)
    except Exception:
        pass

    # Provision datasource in this topology Grafana (best-effort)
    try:
        auth = (grafana_admin_user, grafana_admin_password)
        ds_name = "influxdb"
        grafana_url = f"http://{_topo_container_name(topology_id, 'grafana')}:3000"
        datasource = {
            "name": ds_name,
            "type": "influxdb",
            "access": "proxy",
            "url": f"http://{_topo_container_name(topology_id, 'influxdb')}:8086",
            "basicAuth": False,
            "isDefault": True,
            "jsonData": {"version": "Flux", "organization": influx_org, "defaultBucket": influx_bucket},
            "secureJsonData": {"token": influx_token},
        }
        with httpx.Client(timeout=5.0) as client:
            for _ in range(30):
                try:
                    r = client.get(f"{grafana_url}/api/health")
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(1)

            existing = client.get(f"{grafana_url}/api/datasources/name/{ds_name}", auth=auth)
            if existing.status_code == 200:
                ds_id = (existing.json() or {}).get("id")
                if ds_id:
                    client.put(
                        f"{grafana_url}/api/datasources/{ds_id}",
                        json={**datasource, "id": ds_id},
                        auth=auth,
                    )
            else:
                client.post(f"{grafana_url}/api/datasources", json=datasource, auth=auth)
    except Exception:
        pass

    # Connect emulation container to topology infra network (so it can resolve service aliases)
    try:
        record = active_emulations.get(topology_id) or {}
        emu_name = record.get("container_name") or f"caduceus-emu-{topology_id[:8]}"
        emu = docker_client.containers.get(emu_name)
        _connect_to_network(emu, net_name, aliases=["emulation"])
    except Exception:
        pass

    payload: dict[str, Any] = {
        "topology_id": topology_id,
        "mode": "isolated",
        "network": net_name,
        "services": {
            "grafana": {"host_port": host_ports["grafana"]},
            "prometheus": {"host_port": host_ports["prometheus"]},
            "consul": {"host_port": host_ports["consul"]},
            "influxdb": {"host_port": host_ports["influxdb"], "org": influx_org, "bucket": influx_bucket},
            "rabbitmq": {"host_port": host_ports["rabbitmq"]},
            "kafka-ui": {"host_port": host_ports["kafka-ui"]},
            "portainer": {"host_port": host_ports["portainer"], "path": "/", "scheme": "https"},
            "portainer-http": {"host_port": host_ports["portainer-http"], "path": "/", "scheme": "http"},
        },
        "internal": {
            "influxdb_url": f"http://{_topo_container_name(topology_id, 'influxdb')}:8086",
            "grafana_url": f"http://{_topo_container_name(topology_id, 'grafana')}:3000",
        },
        "updated_at": _iso_now(),
    }

    _consul_set(f"caduceus/topologies/{topology_id}/isolated_infra", json.dumps(payload))
    # Back-compat for previous UI bits
    _consul_set(f"caduceus/topologies/{topology_id}/influxdb_bucket", influx_bucket)

    return payload


def ensure_topology_isolated_osm(topology_id: str) -> dict[str, Any]:
    """
    Ensure an ETSI OSM stack exists for a topology (isolated per topology: containers + volumes + internal network).
    A topology-scoped `osm-connector` container is created on the main project network so MCP/UI can reach it.
    """
    if OSM_TOPOLOGY_MODE != "isolated":
        return {"topology_id": topology_id, "mode": OSM_TOPOLOGY_MODE, "success": False}
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    net_name = _osm_network_name(topology_id)
    _ensure_network_internal(net_name)

    mongo_name = _osm_container_name(topology_id, "mongo")
    mysql_name = _osm_container_name(topology_id, "mysql")
    zookeeper_name = _osm_container_name(topology_id, "zookeeper")
    kafka_name = _osm_container_name(topology_id, "kafka")
    prometheus_name = _osm_container_name(topology_id, "prometheus")
    ro_name = _osm_container_name(topology_id, "ro")
    lcm_name = _osm_container_name(topology_id, "lcm")
    nbi_name = _osm_container_name(topology_id, "nbi")
    ng_ui_name = _osm_container_name(topology_id, "ng-ui")
    light_ui_name = _osm_container_name(topology_id, "light-ui")
    connector_name = _osm_container_name(topology_id, "connector")
    vimemu_name = _osm_container_name(topology_id, "vimemu")

    connector_service_name = f"osm-connector-{topology_id[:8]}"
    vimemu_service_name = f"vimemu-{topology_id[:8]}"

    def _bootstrap_osm_emulation_vim() -> dict[str, Any]:
        """
        Best-effort: create a default "emulation" VIM account in the topology's isolated OSM so
        the UI can immediately select a vimAccountId when instantiating NS.
        """
        result: dict[str, Any] = {
            "attempted": True,
            "created": False,
            "updated": False,
            "name": f"mininet-{topology_id[:8]}",
            "vim_account_id": None,
            "error": None,
        }

        connector_base = f"http://{connector_name}:8020"
        emu_container_name = f"caduceus-emu-{topology_id[:8]}"
        emu_container_id = None
        try:
            emu = docker_client.containers.get(emu_container_name)
            emu_container_id = getattr(emu, "id", None)
        except Exception:
            emu_container_id = None

        description = f"Caduceus emulation container {emu_container_name} (topology {topology_id})"
        if emu_container_id:
            description += f" id={str(emu_container_id)[:12]}"
        description += f" openstack_auth_url=http://{vimemu_name}:6001/v2.0"

        desired_name = str(result["name"])
        refreshed_at = int(time.time())
        create_payload = {
            "name": desired_name,
            # Present our emulation as an OpenStack-like VIM (vim-emu-compatible).
            # Keystone v2 endpoint is used as auth_url by OSM.
            "vim_url": f"http://{vimemu_name}:6001/v2.0",
            "vim_type": "openstack",
            # Dummy credentials (vimemu-service accepts any user/pass for dev).
            "vim_user": "username",
            "vim_password": "password",
            "vim_tenant_name": "tenantName",
            # Force a non-empty change when we "refresh" so RO re-checks connectivity.
            "description": f"{description} refreshed_at={refreshed_at}",
        }

        def _operational_state(v: dict[str, Any]) -> str:
            admin = v.get("_admin") if isinstance(v.get("_admin"), dict) else {}
            return str((admin or {}).get("operationalState") or "").strip().upper()

        def _has_failed_connectivity(vim_detail: dict[str, Any]) -> bool:
            admin = vim_detail.get("_admin") if isinstance(vim_detail.get("_admin"), dict) else {}
            ops = admin.get("operations") if isinstance(admin.get("operations"), list) else []
            for op in ops:
                if not isinstance(op, dict):
                    continue
                if str(op.get("lcmOperationType") or "").lower() != "create":
                    continue
                if str(op.get("operationState") or "").upper() != "FAILED":
                    continue
                detail = str(op.get("detailed-status") or "")
                if "Checking connectivity" in detail or "Unable to establish connection" in detail:
                    return True
            return False

        try:
            with httpx.Client(timeout=8.0) as client:
                # Wait briefly for connector+NBI to be ready.
                for _ in range(20):
                    try:
                        resp = client.get(f"{connector_base}/api/osm/vim-accounts")
                        if resp.status_code < 500:
                            break
                    except Exception:
                        pass
                    time.sleep(1.0)

                resp = client.get(f"{connector_base}/api/osm/vim-accounts")
                resp.raise_for_status()
                existing = resp.json()
                if isinstance(existing, list):
                    for v in existing:
                        if isinstance(v, dict) and str(v.get("name") or "") == desired_name:
                            vim_id = v.get("_id") or v.get("id")
                            result["vim_account_id"] = vim_id
                            # If the VIM already exists but is not configured as our openstack emulator,
                            # update it in-place so the UI doesn't show multiple "mininet-<id8>" entries.
                            if (
                                str(v.get("vim_type") or "").strip().lower() == str(create_payload.get("vim_type") or "").strip().lower()
                                and str(v.get("vim_url") or "").strip() == str(create_payload.get("vim_url") or "").strip()
                            ):
                                if vim_id:
                                    # If RO recorded a FAILED create due to an early vimemu startup, recreate when safe.
                                    try:
                                        detail = client.get(
                                            f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}"
                                        ).json()
                                    except Exception:
                                        detail = {}
                                    if isinstance(detail, dict) and _has_failed_connectivity(detail):
                                        try:
                                            ns = client.get(f"{connector_base}/api/osm/ns-instances").json()
                                        except Exception:
                                            ns = []
                                        safe_to_recreate = isinstance(ns, list) and len(ns) == 0
                                        if safe_to_recreate:
                                            try:
                                                client.delete(f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}")
                                            except Exception:
                                                pass
                                            result["vim_account_id"] = None
                                            break
                                        # Otherwise just poke with an edit to refresh status.
                                        try:
                                            upd = client.put(
                                                f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}",
                                                json=create_payload,
                                            )
                                            upd.raise_for_status()
                                            result["updated"] = True
                                        except Exception:
                                            pass
                                        return result

                                if _operational_state(v) == "ENABLED":
                                    return result
                                # RO sometimes records a FAILED create if vimemu wasn't ready yet; poke with an edit.
                                if vim_id:
                                    try:
                                        upd = client.put(
                                            f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}",
                                            json=create_payload,
                                        )
                                        upd.raise_for_status()
                                        result["updated"] = True
                                        return result
                                    except Exception:
                                        pass
                                return result
                            if vim_id:
                                try:
                                    upd = client.put(
                                        f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}",
                                        json=create_payload,
                                    )
                                    upd.raise_for_status()
                                    result["updated"] = True
                                    return result
                                except Exception:
                                    # Fallback: delete and recreate (best-effort).
                                    try:
                                        client.delete(f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts/{vim_id}")
                                    except Exception:
                                        pass
                                    break

                create = None
                for _ in range(12):
                    create = client.post(f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts", json=create_payload)
                    if create.status_code != 409:
                        break
                    time.sleep(1.0)

                if create is not None and create.status_code == 409:
                    # Name conflict race (e.g., delete is async). Re-list and return the existing id.
                    try:
                        existing = client.get(f"{connector_base}/api/osm/vim-accounts").json()
                    except Exception:
                        existing = []
                    if isinstance(existing, list):
                        for v in existing:
                            if isinstance(v, dict) and str(v.get("name") or "") == desired_name:
                                result["vim_account_id"] = v.get("_id") or v.get("id")
                                return result

                if create is None:
                    raise RuntimeError("Failed to create VIM account (no response)")
                create.raise_for_status()
                data = create.json() if create.content else {}
                if isinstance(data, dict):
                    result["vim_account_id"] = data.get("_id") or data.get("id")
                result["created"] = True
                return result
        except Exception as exc:
            result["error"] = str(exc)
            return result

    def _bootstrap_osm_sdn_wims() -> dict[str, Any]:
        """
        Best-effort: register topology controller(s) into the isolated ETSI OSM as WIM accounts so
        OSM can reference SDN controllers. We use wim_type=dummy by default so this works even when
        RO SDN plugins aren't installed.
        """
        result: dict[str, Any] = {
            "attempted": True,
            "wims": [],
            "sdns": [],
            "error": None,
        }

        controllers_raw = None
        try:
            controllers_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
        except Exception:
            controllers_raw = None

        controllers_payload = None
        if controllers_raw:
            try:
                controllers_payload = json.loads(controllers_raw)
            except Exception:
                controllers_payload = None

        controllers = (controllers_payload or {}).get("controllers") if isinstance(controllers_payload, dict) else None
        if not isinstance(controllers, dict) or not controllers:
            return result

        usable: list[tuple[str, dict[str, Any]]] = []
        for controller_id, c in controllers.items():
            if not isinstance(c, dict):
                continue
            if not c.get("ok"):
                continue
            cname = str(c.get("container_name") or "").strip()
            if not cname:
                continue
            usable.append((str(controller_id), c))

        if not usable:
            return result

        connector_base = f"http://{connector_name}:8020"

        def _guess_sdn_url(ctrl: dict[str, Any]) -> str:
            ctype = str(ctrl.get("controller_type") or "").strip().lower()
            cname = str(ctrl.get("container_name") or "").strip()
            if ctype in ("onos", "odl", "opendaylight"):
                return f"http://{cname}:8181"
            return f"http://{cname}"

        # Ensure controller containers are reachable from the OSM internal network.
        for controller_id, ctrl in usable:
            cname = str(ctrl.get("container_name") or "").strip()
            try:
                cobj = docker_client.containers.get(cname)
                # Make controller name resolvable inside the OSM network.
                _connect_to_network(cobj, net_name, aliases=[f"ctrl-{_safe_controller_id(controller_id)}", str(controller_id)])
            except Exception:
                pass

        try:
            with httpx.Client(timeout=8.0) as client:
                try:
                    existing_sdns = client.get(f"{connector_base}/api/osm/proxy/admin/v1/sdns").json()
                except Exception:
                    existing_sdns = []
                existing_sdns_by_name: dict[str, dict[str, Any]] = {}
                if isinstance(existing_sdns, list):
                    for s in existing_sdns:
                        if isinstance(s, dict) and s.get("name"):
                            existing_sdns_by_name[str(s["name"])] = s

                try:
                    existing = client.get(f"{connector_base}/api/osm/proxy/admin/v1/wim_accounts").json()
                except Exception:
                    existing = []

                existing_by_name: dict[str, dict[str, Any]] = {}
                if isinstance(existing, list):
                    for w in existing:
                        if isinstance(w, dict) and w.get("name"):
                            existing_by_name[str(w["name"])] = w

                for controller_id, ctrl in usable:
                    safe_id = _safe_controller_id(controller_id)
                    name = f"sdn-{topology_id[:8]}-{safe_id}"
                    if name in existing_by_name:
                        w = existing_by_name[name]
                        result["wims"].append(
                            {
                                "name": name,
                                "wim_account_id": w.get("_id") or w.get("id"),
                                "created": False,
                                "controller_id": controller_id,
                                "controller_type": ctrl.get("controller_type"),
                                "wim_url": w.get("wim_url"),
                                "wim_type": w.get("wim_type"),
                            }
                        )
                        continue

                    wim_url = _guess_sdn_url(ctrl)
                    ctrl_type = str(ctrl.get("controller_type") or "").strip().lower() or "controller"
                    of_port = ctrl.get("openflow_port")
                    desc = f"Caduceus topology SDN controller {controller_id} ({ctrl_type}) url={wim_url}"
                    if of_port:
                        desc += f" openflow={of_port}"
                    create_payload = {
                        "name": name,
                        "wim_url": wim_url,
                        "wim_type": "dummy",
                        "description": desc,
                    }
                    create = client.post(f"{connector_base}/api/osm/proxy/admin/v1/wim_accounts", json=create_payload)
                    create.raise_for_status()
                    data = create.json() if create.content else {}
                    result["wims"].append(
                        {
                            "name": name,
                            "wim_account_id": (data.get("_id") if isinstance(data, dict) else None)
                            or (data.get("id") if isinstance(data, dict) else None),
                            "created": True,
                            "controller_id": controller_id,
                            "controller_type": ctrl.get("controller_type"),
                            "wim_url": wim_url,
                            "wim_type": "dummy",
                        }
                    )

                # Also register SDN controllers in /admin/v1/sdns so OSM NG-UI's SDN pages work.
                # Use `type=dummy` to avoid requiring RO SDN plugins (e.g., osm_rosdn_onos).
                for controller_id, ctrl in usable:
                    safe_id = _safe_controller_id(controller_id)
                    sdn_name = f"sdn-{topology_id[:8]}-{safe_id}"
                    sdn_url = _guess_sdn_url(ctrl)
                    if sdn_name in existing_sdns_by_name:
                        s = existing_sdns_by_name[sdn_name]
                        sdn_id = s.get("_id") or s.get("id")
                        updated = False
                        if sdn_id and (str(s.get("type") or "") != "dummy" or str(s.get("url") or "") != sdn_url):
                            try:
                                upd = client.put(
                                    f"{connector_base}/api/osm/proxy/admin/v1/sdns/{sdn_id}",
                                    json={"name": sdn_name, "type": "dummy", "url": sdn_url},
                                )
                                upd.raise_for_status()
                                updated = True
                            except Exception:
                                updated = False
                        result["sdns"].append(
                            {
                                "name": sdn_name,
                                "sdn_id": sdn_id,
                                "created": False,
                                "updated": updated,
                                "controller_id": controller_id,
                                "controller_type": ctrl.get("controller_type"),
                                "url": sdn_url if updated else s.get("url"),
                                "type": "dummy" if updated else s.get("type"),
                            }
                        )
                        continue

                    sdn_payload = {
                        "name": sdn_name,
                        "type": "dummy",
                        "url": sdn_url,
                    }
                    sdn_create = client.post(f"{connector_base}/api/osm/proxy/admin/v1/sdns", json=sdn_payload)
                    sdn_create.raise_for_status()
                    sdn_data = sdn_create.json() if sdn_create.content else {}
                    result["sdns"].append(
                        {
                            "name": sdn_name,
                            "sdn_id": (sdn_data.get("_id") if isinstance(sdn_data, dict) else None)
                            or (sdn_data.get("id") if isinstance(sdn_data, dict) else None),
                            "created": True,
                            "controller_id": controller_id,
                            "controller_type": ctrl.get("controller_type"),
                            "url": sdn_url,
                            "type": "dummy",
                        }
                    )

        except Exception as exc:
            result["error"] = str(exc)

        return result

    def ensure_network_aliases(container: Any, aliases: list[str]) -> None:
        try:
            container.reload()
            networks = ((getattr(container, "attrs", {}) or {}).get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
            current = list((networks.get(net_name, {}) or {}).get("Aliases") or [])
            if all(a in current for a in aliases):
                return
        except Exception:
            current = []
        try:
            net = docker_client.networks.get(net_name)
        except Exception:
            return
        try:
            net.disconnect(container, force=True)
        except Exception:
            pass
        try:
            net.connect(container, aliases=list(dict.fromkeys([*(aliases or []), *current])))
        except Exception:
            pass

    def ensure_container(service_id: str, run_kwargs: dict[str, Any], *, force_recreate: bool = False) -> Any:
        name = str(run_kwargs.get("name") or "")
        container = None
        if name:
            try:
                container = docker_client.containers.get(name)
            except docker.errors.NotFound:
                container = None
            except Exception:
                container = None

        if container:
            try:
                container.reload()
            except Exception:
                pass

            # Recreate when our stack version changes so config fixes are applied (volumes, env, healthchecks, etc).
            if not force_recreate:
                try:
                    desired_labels = run_kwargs.get("labels") if isinstance(run_kwargs.get("labels"), dict) else {}
                    desired_version = str(desired_labels.get("caduceus.osm_stack_version") or "").strip()
                    current_labels = ((getattr(container, "attrs", {}) or {}).get("Config", {}) or {}).get("Labels", {}) or {}
                    current_version = str(current_labels.get("caduceus.osm_stack_version") or "").strip()
                    if desired_version and current_version != desired_version:
                        force_recreate = True
                except Exception:
                    pass

            # If a container is missing expected volume mounts (e.g., newly added persistent storage),
            # recreate once so the new mounts apply.
            if not force_recreate:
                expected_volumes = run_kwargs.get("volumes") if isinstance(run_kwargs.get("volumes"), dict) else None
                if expected_volumes:
                    try:
                        mounts = (getattr(container, "attrs", {}) or {}).get("Mounts") or []
                        destinations = {
                            str(m.get("Destination"))
                            for m in mounts
                            if isinstance(m, dict) and isinstance(m.get("Destination"), str)
                        }
                        for v in expected_volumes.values():
                            if not isinstance(v, dict):
                                continue
                            dest = v.get("bind")
                            if isinstance(dest, str) and dest and dest not in destinations:
                                force_recreate = True
                                break
                    except Exception:
                        pass

            # Some upstream OSM images ship healthchecks that require `curl`, but `curl` isn't
            # installed in the minimal images. If we detect that failure, recreate once so our
            # overridden healthcheck can take effect.
            if not force_recreate:
                try:
                    health = ((getattr(container, "attrs", {}) or {}).get("State", {}) or {}).get("Health") or {}
                    if isinstance(health, dict) and health.get("Status") == "unhealthy":
                        logs = health.get("Log") if isinstance(health.get("Log"), list) else []
                        last = logs[-1] if logs else {}
                        output = str((last or {}).get("Output") or "")
                        if "curl: not found" in output:
                            force_recreate = True
                except Exception:
                    pass

            if force_recreate:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
                container = None
            else:
                status_val = getattr(container, "status", "")
                if status_val not in ("running", "restarting"):
                    try:
                        container.start()
                    except Exception:
                        pass
                return container

        try:
            _ensure_image(str(run_kwargs.get("image") or ""))
        except Exception:
            pass
        return docker_client.containers.run(**run_kwargs)

    # Core DB/bus services
    ensure_container(
        "mongo",
        {
            "image": "mongo:6",
            "name": mongo_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "mongo"), "caduceus.osm_stack_version": "2025-12-27"},
            "command": ["mongod", "--bind_ip_all"],
            "volumes": {_osm_volume_name(topology_id, "mongo"): {"bind": "/data/db", "mode": "rw"}},
            "network": net_name,
        },
    )

    ensure_container(
        "mysql",
        {
            "image": "mysql:8",
            "name": mysql_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "mysql"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "MYSQL_ROOT_PASSWORD": "osmrootpw",
                "MYSQL_DATABASE": "mano_db",
                "MYSQL_USER": "mano",
                "MYSQL_PASSWORD": "manopw",
            },
            "volumes": {_osm_volume_name(topology_id, "mysql"): {"bind": "/var/lib/mysql", "mode": "rw"}},
            "network": net_name,
        },
    )

    ensure_container(
        "zookeeper",
        {
            "image": "confluentinc/cp-zookeeper:7.5.0",
            "name": zookeeper_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "zookeeper"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "ZOOKEEPER_CLIENT_PORT": "2181",
                "ZOOKEEPER_TICK_TIME": "2000",
                "ZOOKEEPER_SYNC_LIMIT": "2",
            },
            "volumes": {
                _osm_volume_name(topology_id, "zookeeper-data"): {"bind": "/var/lib/zookeeper/data", "mode": "rw"},
                _osm_volume_name(topology_id, "zookeeper-log"): {"bind": "/var/lib/zookeeper/log", "mode": "rw"},
            },
            "network": net_name,
        },
    )

    ensure_container(
        "kafka",
        {
            "image": "confluentinc/cp-kafka:7.5.0",
            "name": kafka_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "kafka"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "KAFKA_BROKER_ID": "2",
                "KAFKA_ZOOKEEPER_CONNECT": f"{zookeeper_name}:2181",
                "KAFKA_LISTENERS": "PLAINTEXT://0.0.0.0:9092",
                "KAFKA_ADVERTISED_LISTENERS": f"PLAINTEXT://{kafka_name}:9092",
                "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
                "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
                "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
                "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
            },
            "volumes": {_osm_volume_name(topology_id, "kafka"): {"bind": "/var/lib/kafka/data", "mode": "rw"}},
            "network": net_name,
        },
    )

    ensure_container(
        "prometheus",
        {
            "image": "prom/prometheus:latest",
            "name": prometheus_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "prometheus"), "caduceus.osm_stack_version": "2025-12-27"},
            "network": net_name,
        },
    )

    # OSM RO / LCM / NBI
    ensure_container(
        "ro",
        {
            "image": "opensourcemano/ro:latest",
            "name": ro_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "ro"), "caduceus.osm_stack_version": "2025-12-27"},
            # Override upstream image healthcheck (uses curl, not present in image).
            "healthcheck": Healthcheck(
                test=[
                    "CMD-SHELL",
                    "python3 -c \"import socket; s=socket.create_connection(('127.0.0.1',9090),3); "
                    "s.sendall(b'GET /ro HTTP/1.0\\\\r\\\\nHost: localhost\\\\r\\\\n\\\\r\\\\n'); "
                    "s.recv(1); s.close()\"",
                ],
                interval=10_000_000_000,
                timeout=5_000_000_000,
                start_period=130_000_000_000,
                retries=12,
            ),
            "environment": {
                "OSMRO_DATABASE_URI": f"mongodb://{mongo_name}:27017",
                "OSMRO_MESSAGE_HOST": kafka_name,
                "OSMRO_MESSAGE_PORT": "9092",
                "RO_DB_HOST": mysql_name,
                "RO_DB_OVIM_HOST": mysql_name,
                "RO_DB_ROOT_PASSWORD": "osmrootpw",
                "RO_DB_OVIM_ROOT_PASSWORD": "osmrootpw",
                "RO_DB_USER": "mano",
                "RO_DB_PASSWORD": "manopw",
                "RO_DB_OVIM_USER": "mano",
                "RO_DB_OVIM_PASSWORD": "manopw",
                "RO_DB_NAME": "mano_db",
                "RO_DB_OVIM_NAME": "mano_vim_db",
            },
            "network": net_name,
        },
    )

    # LCM needs a kubeconfig file; generate a dummy one at container start.
    kubeconfig_path = "/tmp/mgmtcluster-kubeconfig.yaml"
    lcm_bootstrap = (
        "set -e; "
        f"cat > {kubeconfig_path} <<'EOF'\n"
        "apiVersion: v1\nkind: Config\nclusters:\n- name: dummy\n  cluster:\n    server: https://127.0.0.1:6443\n    insecure-skip-tls-verify: true\ncontexts:\n- name: dummy\n  context:\n    cluster: dummy\n    user: dummy\ncurrent-context: dummy\nusers:\n- name: dummy\n  user:\n    token: dummy\n"
        "EOF\n"
        "exec /bin/bash scripts/start.sh"
    )
    ensure_container(
        "lcm",
        {
            "image": "opensourcemano/lcm:latest",
            "name": lcm_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "lcm"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "OSMLCM_DATABASE_URI": f"mongodb://{mongo_name}:27017",
                "OSMLCM_MESSAGE_HOST": kafka_name,
                "OSMLCM_MESSAGE_PORT": "9092",
                "OSMLCM_RO_HOST": ro_name,
                "OSMLCM_RO_PORT": "9090",
                "OSMLCM_RO_URI": f"http://{ro_name}:9090/",
                "OSMLCM_LOG_LEVEL": "INFO",
                "OSMLCM_MAINPOSTRENDERERPATH": "",
                "OSMLCM_PODLABELSPOSTRENDERERPATH": "",
                "OSMLCM_NODESELECTORPOSTRENDERERPATH": "",
                # Prevent opensourcemano/lcm from crashing on startup when GitOps URLs are unset.
                "OSMLCM_GITOPS_GIT_BASE_URL": "https://example.invalid",
                "OSMLCM_GITOPS_FLEET_REPO_URL": "https://example.invalid/fleet.git",
                "OSMLCM_GITOPS_SW_CATALOGS_REPO_URL": "https://example.invalid/sw-catalogs.git",
                "OSMLCM_GITOPS_MGMTCLUSTER_KUBECONFIG": kubeconfig_path,
            },
            "command": ["bash", "-lc", lcm_bootstrap],
            "network": net_name,
        },
    )

    nbi = ensure_container(
        "nbi",
        {
            "image": "opensourcemano/nbi:latest",
            "name": nbi_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "nbi"), "caduceus.osm_stack_version": "2025-12-27"},
            # Override upstream image healthcheck (uses curl + https; our NBI is http here).
            "healthcheck": Healthcheck(
                test=[
                    "CMD-SHELL",
                    "python3 -c \"import socket; s=socket.create_connection(('127.0.0.1',9999),3); "
                    "s.sendall(b'GET /osm/ HTTP/1.0\\\\r\\\\nHost: localhost\\\\r\\\\n\\\\r\\\\n'); "
                    "s.recv(1); s.close()\"",
                ],
                interval=10_000_000_000,
                timeout=5_000_000_000,
                start_period=120_000_000_000,
                retries=5,
            ),
            "environment": {
                "OSMNBI_DATABASE_URI": f"mongodb://{mongo_name}:27017",
                "OSMNBI_MESSAGE_HOST": kafka_name,
                "OSMNBI_MESSAGE_PORT": "9092",
                "OSMNBI_AUTHENTICATION_BACKEND": "internal",
                "OSMNBI_LOG_LEVEL": "INFO",
                # IMPORTANT: OSM 18.0.1's package handling expects a sync-capable storage backend.
                # With `storage.driver=local`, NBI can end up deleting the extracted package folder after upload,
                # leading to "storage exception ... cannot be opened" when NG-UI tries to fetch package_content.
                # Use mongo-backed storage (GridFS) for reliability in isolated per-topology stacks.
                "OSMNBI_STORAGE_DRIVER": "mongo",
                "OSMNBI_STORAGE_PATH": "/app/storage",
                "OSMNBI_STORAGE_URI": f"mongodb://{mongo_name}:27017",
                "OSMNBI_STORAGE_COLLECTION": "osm",
            },
            # Persist package content across container restarts/recreates. Without this, NBI can lose files
            # under /app/storage while Mongo still references them, causing "storage exception ... cannot be opened".
            "volumes": {_osm_volume_name(topology_id, "nbi-storage"): {"bind": "/app/storage", "mode": "rw"}},
            "network": net_name,
        },
    )
    ensure_network_aliases(nbi, ["nbi", "osm-nbi"])
    # Make NBI reachable from the main project network so the frontend's /infra-proxy can forward `/osm/*`
    # API calls without relying on the NG-UI container acting as a proxy.
    _connect_to_network(nbi, MAIN_DOCKER_NETWORK)

    # Per-topology ETSI OSM native UIs (reachable via frontend nginx /infra-proxy, no host ports needed).
    ng_ui = ensure_container(
        "ng-ui",
        {
            "image": "opensourcemano/ng-ui:latest",
            "name": ng_ui_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "ng-ui"), "caduceus.osm_stack_version": "2025-12-27"},
            # Override upstream image healthcheck (uses curl, not present in image).
            "healthcheck": Healthcheck(
                test=[
                    "CMD-SHELL",
                    "perl -MIO::Socket::INET -e \"exit(IO::Socket::INET->new("
                    "PeerAddr=>'127.0.0.1',PeerPort=>80,Proto=>'tcp',Timeout=>3)?0:1)\"",
                ],
                interval=10_000_000_000,
                timeout=5_000_000_000,
                start_period=130_000_000_000,
                retries=12,
            ),
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(ng_ui, net_name)

    light_ui = ensure_container(
        "light-ui",
        {
            "image": "opensourcemano/light-ui:latest",
            "name": light_ui_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "light-ui"), "caduceus.osm_stack_version": "2025-12-27"},
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(light_ui, net_name)

    # Topology-scoped connector: bridge between MCP/UI and the internal OSM network.
    connector = ensure_container(
        "connector",
        {
            "image": "caduceus-flux-osm-connector-service",
            "name": connector_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "connector"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "SERVICE_NAME": connector_service_name,
                "SERVICE_PORT": "8020",
                "CONSUL_HOST": "consul",
                "CONSUL_PORT": "8500",
                "OSM_NBI_URL": f"http://{nbi_name}:9999/osm",
                "OSM_USERNAME": "admin",
                "OSM_PASSWORD": "admin",
                "OSM_PROJECT_ID": "",
                "OSM_TOKEN": "",
            },
            "network": MAIN_DOCKER_NETWORK,
        },
    )
    _connect_to_network(connector, net_name)

    # Topology-scoped OpenStack-like VIM emulator (vim-emu compatible).
    vimemu = ensure_container(
        "vimemu",
        {
            "image": "caduceus-flux-vimemu-service",
            "name": vimemu_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {**_topology_osm_labels(topology_id, "vimemu"), "caduceus.osm_stack_version": "2025-12-27"},
            "environment": {
                "SERVICE_NAME": vimemu_service_name,
                "SERVICE_PORT": "6001",
                "TOPOLOGY_ID": topology_id,
                "ORCHESTRATOR_URL": "http://orchestrator-service:8002",
                "CONSUL_HOST": "consul",
                "CONSUL_PORT": "8500",
                "OSM_REGION": "RegionOne",
            },
            "network": MAIN_DOCKER_NETWORK,
        },
        # Do not force-recreate: vimemu keeps in-memory state that RO may reference (servers/ports IDs).
        # Recreate manually when upgrading the image to avoid breaking ongoing NS operations.
        force_recreate=False,
    )
    _connect_to_network(vimemu, net_name)

    # Best-effort wait so RO doesn't record a FAILED VIM create due to early connectivity checks.
    def _wait_vimemu_ready(max_seconds: int = 60) -> bool:
        deadline = time.time() + max(10, int(max_seconds))
        health_url = f"http://{vimemu_name}:6001/health"
        token_url = f"http://{vimemu_name}:6001/v2.0/tokens"
        with httpx.Client(timeout=6.0) as client:
            while time.time() < deadline:
                try:
                    h = client.get(health_url)
                    if h.status_code != 200:
                        time.sleep(2.0)
                        continue
                except Exception:
                    time.sleep(2.0)
                    continue

                try:
                    t = client.post(
                        token_url,
                        json={
                            "auth": {
                                "tenantName": "tenantName",
                                "passwordCredentials": {"username": "username", "password": "password"},
                            }
                        },
                    )
                    if t.status_code == 200:
                        return True
                except Exception:
                    time.sleep(1.0)
                    continue
                time.sleep(1.0)
        return False

    # Best-effort wait so bootstrap requests don't fail with 503 during OSM warmup.
    def _wait_osm_ready(max_seconds: int = 120) -> bool:
        connector_base = f"http://{connector_name}:8020"
        deadline = time.time() + max(10, int(max_seconds))
        with httpx.Client(timeout=6.0) as client:
            while time.time() < deadline:
                try:
                    h = client.get(f"{connector_base}/health")
                    if h.status_code != 200:
                        time.sleep(2.0)
                        continue
                except Exception:
                    time.sleep(2.0)
                    continue

                try:
                    r = client.get(f"{connector_base}/api/osm/projects")
                    if r.status_code == 200:
                        return True
                except Exception:
                    pass
                time.sleep(2.0)
        return False

    _wait_vimemu_ready(60)
    _wait_osm_ready(120)

    bootstrap = _bootstrap_osm_emulation_vim()
    sdn_bootstrap = _bootstrap_osm_sdn_wims()

    payload: dict[str, Any] = {
        "topology_id": topology_id,
        "mode": "isolated",
        "network": net_name,
        "ui": {
            "ng_ui_path": f"/infra-proxy/osm-ng-ui/{topology_id[:8]}/",
            "light_ui_path": f"/infra-proxy/osm-light-ui/{topology_id[:8]}/",
        },
        "bootstrap": {
            "emulation_vim": bootstrap,
            "sdn_wims": sdn_bootstrap,
        },
        "connector": {
            "service_name": connector_service_name,
            "base_path": f"/api/osm/{topology_id}",
        },
        "updated_at": _iso_now(),
    }
    _consul_set(f"caduceus/topologies/{topology_id}/isolated_osm", json.dumps(payload))
    return payload


def _topology_controller_labels(topology_id: str, controller_id: str) -> dict[str, str]:
    return {
        "caduceus.topology_id": topology_id,
        "caduceus.role": "topology_controller",
        "caduceus.controller_id": controller_id,
    }


def _safe_controller_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = "controller"

    # Keep Docker DNS labels short (<=63 chars). Our container name prefix already consumes
    # a lot of that budget, so cap controller IDs aggressively.
    max_len = 24
    if len(cleaned) > max_len:
        suffix = hashlib.sha1(cleaned.encode()).hexdigest()[:6]
        head_len = max(1, max_len - len(suffix) - 1)
        cleaned = f"{cleaned[:head_len]}-{suffix}".strip("-")

    return cleaned


def _bootstrap_osm_shared_emulation_vim(topology_id: str) -> dict[str, Any]:
    """
    Best-effort: create a default VIM account in the *shared/global* ETSI OSM for the running emulation.
    This mirrors the isolated OSM bootstrap behavior but targets the compose-level `osm-connector-service`.
    """
    result: dict[str, Any] = {
        "attempted": True,
        "created": False,
        "name": f"mininet-{topology_id[:8]}",
        "vim_account_id": None,
        "error": None,
    }
    connector_base = os.getenv("OSM_SHARED_CONNECTOR_BASE", "http://osm-connector-service:8020")
    emu_container_name = f"caduceus-emu-{topology_id[:8]}"

    description = f"Caduceus emulation container {emu_container_name} (topology {topology_id})"
    try:
        if docker_client:
            emu = docker_client.containers.get(emu_container_name)
            emu_id = getattr(emu, "id", None)
            if emu_id:
                description += f" id={str(emu_id)[:12]}"
    except Exception:
        pass

    desired_name = str(result["name"])
    create_payload = {
        "name": desired_name,
        "vim_url": f"docker://{emu_container_name}",
        "vim_type": "dummy",
        "vim_user": "caduceus",
        "vim_password": "caduceus",
        "vim_tenant_name": "default",
        "description": description,
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{connector_base}/api/osm/vim-accounts")
            resp.raise_for_status()
            existing = resp.json()
            if isinstance(existing, list):
                for v in existing:
                    if isinstance(v, dict) and str(v.get("name") or "") == desired_name:
                        result["vim_account_id"] = v.get("_id") or v.get("id")
                        return result
            create = client.post(f"{connector_base}/api/osm/proxy/admin/v1/vim_accounts", json=create_payload)
            create.raise_for_status()
            data = create.json() if create.content else {}
            if isinstance(data, dict):
                result["vim_account_id"] = data.get("_id") or data.get("id")
            result["created"] = True
            return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def _bootstrap_osm_shared_sdn_wims(topology_id: str, controllers_payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Best-effort: register topology controller(s) into the *shared/global* ETSI OSM as WIM accounts so
    OSM can reference SDN controllers.
    """
    result: dict[str, Any] = {"attempted": True, "wims": [], "error": None}

    payload = controllers_payload
    if payload is None:
        raw = None
        try:
            raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
        except Exception:
            raw = None
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = None

    controllers = (payload or {}).get("controllers") if isinstance(payload, dict) else None
    if not isinstance(controllers, dict) or not controllers:
        return result

    usable: list[tuple[str, dict[str, Any]]] = []
    for controller_id, c in controllers.items():
        if not isinstance(c, dict) or not c.get("ok"):
            continue
        cname = str(c.get("container_name") or "").strip()
        if not cname:
            continue
        usable.append((str(controller_id), c))

    if not usable:
        # Fallback: Consul controller payload can be stale/misreported; if controller containers exist,
        # still register them as WIM accounts so OSM UI shows the SDN controllers.
        if docker_client:
            try:
                containers = docker_client.containers.list(
                    all=True,
                    filters={"label": [f"caduceus.role=topology_controller", f"caduceus.topology_id={topology_id}"]},
                )
            except Exception:
                containers = []
            for c in list(containers or []):
                try:
                    c.reload()
                except Exception:
                    pass
                status_str = str(getattr(c, "status", "") or "").lower()
                if status_str not in ("running", "restarting", "created"):
                    continue
                labels = getattr(c, "labels", {}) or {}
                controller_id = str(labels.get("caduceus.controller_id") or labels.get("caduceus.controller_name") or c.name or "").strip()
                if not controller_id:
                    continue
                ctrl_type = str(labels.get("caduceus.controller_type") or "custom").strip().lower()
                usable.append(
                    (
                        controller_id,
                        {
                            "ok": True,
                            "container_name": getattr(c, "name", None),
                            "controller_type": ctrl_type,
                            "credentials": (
                                {"user": "onos", "password": "rocks"}
                                if ctrl_type == "onos"
                                else ({"user": "admin", "password": "admin"} if ctrl_type in ("opendaylight", "odl") else {})
                            ),
                            "ui": {"container_port": 8181},
                        },
                    )
                )

    if not usable:
        return result

    def _guess_sdn_url(ctrl: dict[str, Any]) -> str:
        # Prefer explicit values if present
        for k in ("wim_url", "sdn_url", "controller_url", "url"):
            v = ctrl.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        cname = str(ctrl.get("container_name") or "").strip()
        port = 8181
        ui = ctrl.get("ui") if isinstance(ctrl.get("ui"), dict) else {}
        try:
            port = int(ui.get("container_port") or port)
        except Exception:
            port = 8181
        return f"http://{cname}:{port}"

    connector_base = os.getenv("OSM_SHARED_CONNECTOR_BASE", "http://osm-connector-service:8020")
    osm_network = os.getenv("DOCKER_NETWORK", "caduceus-flux_caduceus-network")

    # Ensure controller containers are reachable from OSM network (shared OSM is on the main project network).
    for controller_id, ctrl in usable:
        cname = str(ctrl.get("container_name") or "").strip()
        if not cname:
            continue
        try:
            cobj = docker_client.containers.get(cname)
            _connect_to_network(cobj, osm_network, aliases=[f"ctrl-{_safe_controller_id(controller_id)}"])
        except Exception:
            pass

    try:
        with httpx.Client(timeout=8.0) as client:
            try:
                existing = client.get(f"{connector_base}/api/osm/wim-accounts").json()
            except Exception:
                existing = []

            existing_by_name: dict[str, dict[str, Any]] = {}
            if isinstance(existing, list):
                for w in existing:
                    if isinstance(w, dict) and w.get("name"):
                        existing_by_name[str(w["name"])] = w

            for controller_id, ctrl in usable:
                safe_id = _safe_controller_id(controller_id)
                name = f"sdn-{topology_id[:8]}-{safe_id}"
                wim_url = _guess_sdn_url(ctrl)
                ctrl_type = str(ctrl.get("controller_type") or "").strip().lower() or "controller"
                of_port = ctrl.get("openflow_port")
                desc = f"Caduceus topology SDN controller {controller_id} ({ctrl_type}) url={wim_url}"
                if of_port:
                    desc += f" openflow={of_port}"

                desired_payload: dict[str, Any] = {
                    "name": name,
                    "wim_url": wim_url,
                    # Keep dummy by default: works even when RO SDN plugins are missing.
                    "wim_type": "dummy",
                    "description": desc,
                }

                if name in existing_by_name:
                    w = existing_by_name[name]
                    wim_id = w.get("_id") or w.get("id")
                    # Best-effort update if URL changed.
                    try:
                        if wim_id and str(w.get("wim_url") or "") != wim_url:
                            client.put(
                                f"{connector_base}/api/osm/proxy/admin/v1/wim_accounts/{wim_id}",
                                json=desired_payload,
                            )
                    except Exception:
                        pass
                    result["wims"].append(
                        {
                            "name": name,
                            "wim_account_id": wim_id,
                            "created": False,
                            "controller_id": controller_id,
                            "controller_type": ctrl.get("controller_type"),
                            "wim_url": w.get("wim_url"),
                            "wim_type": w.get("wim_type"),
                        }
                    )
                    continue

                create = client.post(f"{connector_base}/api/osm/proxy/admin/v1/wim_accounts", json=desired_payload)
                create.raise_for_status()
                data = create.json() if create.content else {}
                result["wims"].append(
                    {
                        "name": name,
                        "wim_account_id": (data.get("_id") if isinstance(data, dict) else None)
                        or (data.get("id") if isinstance(data, dict) else None),
                        "created": True,
                        "controller_id": controller_id,
                        "controller_type": ctrl.get("controller_type"),
                        "wim_url": wim_url,
                        "wim_type": "dummy",
                    }
                )
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _extract_topology_controllers(topology_data: dict[str, Any]) -> list[dict[str, Any]]:
    controllers: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_ids: set[str] = set()

    # Helper: find controller nodes by name so we can enrich controllers coming from `topology_data.controllers`
    # (which may omit ids / properties and may use `type` instead of `controller_type`).
    nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
    controller_nodes_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            device_type = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if device_type not in ("controller", "sdn_controller", "sdncontroller"):
                continue
            node_name = str(node.get("name") or "").strip()
            if not node_name:
                continue
            controller_nodes_by_name.setdefault(node_name, node)

    # Preferred: topology controllers list (separate from nodes)
    topo_controllers = topology_data.get("controllers") or []
    if isinstance(topo_controllers, list):
        for c in topo_controllers:
            if not isinstance(c, dict):
                continue
            props = c.get("properties") if isinstance(c.get("properties"), dict) else {}
            controller_type = str(
                c.get("controller_type")
                or c.get("controllerType")
                or c.get("type")
                or props.get("controller_type")
                or props.get("controllerType")
                or props.get("type")
                or "custom"
            ).strip().lower()
            controller_id = str(c.get("id") or c.get("controller_id") or "").strip()
            controller_name = str(c.get("name") or "").strip()

            # If the controller list entry is missing id/properties, enrich it from a matching controller node.
            if controller_name and (not controller_id or controller_type == "custom" or not props):
                node = controller_nodes_by_name.get(controller_name)
                if isinstance(node, dict):
                    if not controller_id:
                        controller_id = str(node.get("id") or node.get("node_id") or "").strip() or controller_id
                    node_props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
                    if not props and node_props:
                        props = node_props
                    if controller_type == "custom":
                        controller_type = str(
                            node_props.get("controller_type")
                            or node_props.get("controllerType")
                            or node_props.get("type")
                            or controller_type
                        ).strip().lower()

            if controller_id and controller_id in seen_ids:
                continue
            if controller_name and controller_name in seen_names:
                continue
            controllers.append(
                {
                    "controller_id": controller_id,
                    "controller_name": controller_name,
                    "controller_type": controller_type,
                    "ip": str(c.get("ip") or ""),
                    "port": int(c.get("port") or 0),
                    "properties": props or {},
                }
            )
            if controller_id:
                seen_ids.add(controller_id)
            if controller_name:
                seen_names.add(controller_name)

    # Back-compat: some payloads model controllers as nodes
    nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            device_type = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if device_type not in ("controller", "sdn_controller", "sdncontroller"):
                continue
            node_id = str(node.get("id") or "").strip()
            node_name = str(node.get("name") or "").strip()
            # If a controller is already defined in `topology_data.controllers`, don't duplicate it via node scanning.
            if node_id and node_id in seen_ids:
                continue
            if node_name and node_name in seen_names:
                continue
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            controller_type = (
                props.get("controller_type")
                or props.get("controllerType")
                or props.get("type")
                or "osken"
            )
            controllers.append(
                {
                    "controller_id": node_id,
                    "controller_name": node_name,
                    "controller_type": str(controller_type or "osken").strip().lower(),
                    "ip": str(props.get("ip") or ""),
                    "port": int(props.get("port") or 0),
                    "properties": props or {},
                }
            )
            if node_id:
                seen_ids.add(node_id)
            if node_name:
                seen_names.add(node_name)
    return controllers


def ensure_topology_controllers(
    topology_id: str,
    topology_data: dict[str, Any],
    wait_ready: bool = True,
) -> dict[str, Any]:
    """
    Ensure topology-scoped controller containers exist (one per controller node).
    Containers run on the main docker network so the emulation container can reach them by name.

    When wait_ready is False, this function only ensures containers exist and returns controller endpoints
    quickly; controller bootstrapping (e.g. ONOS app activation) is deferred to a background warm-up step.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    controllers = _extract_topology_controllers(topology_data)
    key = f"caduceus/topologies/{topology_id}/isolated_controllers"
    if not controllers:
        try:
            consul_client.set_config(key, json.dumps({"version": "none", "controllers": {}, "updated_at": _iso_now()}))
        except Exception:
            pass
        return {"version": "none", "controllers": {}, "updated_at": _iso_now()}

    # Bump this when changing controller images/defaults so existing per-topology controller
    # containers are recreated automatically.
    TOPOLOGY_CONTROLLER_STACK_VERSION = "2025-12-20.1"
    existing_payload: Optional[dict[str, Any]] = None
    existing_raw = consul_client.get_config(key)
    if existing_raw:
        try:
            candidate = json.loads(existing_raw)
            if isinstance(candidate, dict) and isinstance(candidate.get("controllers"), dict):
                existing_payload = candidate
        except Exception:
            existing_payload = None

    used_ports = _collect_used_host_ports()

    def reuse_or_allocate(controller_id: str, start: int, end: int) -> int:
        try:
            maybe = ((existing_payload or {}).get("controllers") or {}).get(controller_id, {})
            ui = maybe.get("ui") if isinstance(maybe, dict) else None
            host_port = ui.get("host_port") if isinstance(ui, dict) else None
            if isinstance(host_port, int) and 1 <= host_port <= 65535:
                return host_port
        except Exception:
            pass
        return _allocate_host_port(start, end, used_ports)

    def ensure_container(controller_id: str, run_kwargs: dict[str, Any]) -> Any:
        cname = run_kwargs.get("name") or _topo_container_name(topology_id, f"ctrl-{controller_id}")
        try:
            c = docker_client.containers.get(cname)
            try:
                c.reload()
            except Exception:
                pass

            labels = (getattr(c, "attrs", {}) or {}).get("Config", {}).get("Labels", {}) or {}
            version = labels.get("caduceus.controller_stack_version")
            if version != TOPOLOGY_CONTROLLER_STACK_VERSION:
                try:
                    c.remove(force=True)
                except Exception:
                    pass
                try:
                    _ensure_image(str(run_kwargs.get("image") or ""))
                except Exception:
                    pass
                return docker_client.containers.run(**run_kwargs)

            if getattr(c, "status", "") != "running":
                try:
                    c.remove(force=True)
                except Exception:
                    pass
                try:
                    _ensure_image(str(run_kwargs.get("image") or ""))
                except Exception:
                    pass
                return docker_client.containers.run(**run_kwargs)

            try:
                desired_restart = run_kwargs.get("restart_policy")
                if isinstance(desired_restart, dict) and desired_restart.get("Name"):
                    c.update(restart_policy=desired_restart)
            except Exception:
                pass

            expected_ports = run_kwargs.get("ports") if isinstance(run_kwargs.get("ports"), dict) else None
            if expected_ports:
                missing_binding = False
                try:
                    for container_port in expected_ports.keys():
                        if _get_host_port(c, str(container_port)) is None:
                            missing_binding = True
                            break
                except Exception:
                    missing_binding = True
                if missing_binding:
                    try:
                        c.remove(force=True)
                    except Exception:
                        pass
                    try:
                        _ensure_image(str(run_kwargs.get("image") or ""))
                    except Exception:
                        pass
                    return docker_client.containers.run(**run_kwargs)

            return c
        except Exception:
            try:
                _ensure_image(str(run_kwargs.get("image") or ""))
            except Exception:
                pass
            return docker_client.containers.run(**run_kwargs)

    main_network = "caduceus-flux_caduceus-network"
    topo_network = _topo_network_name(topology_id)
    _ensure_network(topo_network)

    out_controllers: dict[str, Any] = {}

    for idx, ctrl in enumerate(controllers):
        node_id = ctrl.get("controller_id") or ""
        node_name = ctrl.get("controller_name") or f"controller-{idx + 1}"
        ctrl_type = str(ctrl.get("controller_type") or "osken").lower()
        props = ctrl.get("properties") or {}

        controller_id = _safe_controller_id(node_name or f"{ctrl_type}-{idx + 1}")
        if controller_id in out_controllers:
            controller_id = _safe_controller_id(f"{controller_id}-{idx + 1}")
        container_name = _topo_container_name(topology_id, f"ctrl-{controller_id}")

        # Some controllers have "expected" OpenFlow ports; we default accordingly but allow override via properties.openflow_port/port.
        requested_port = props.get("openflow_port") or props.get("port")
        if requested_port is None:
            if ctrl_type == "pox":
                requested_port = 6633
            elif ctrl_type == "onos":
                # ONOS commonly listens for OpenFlow over TCP on 6653.
                # Allow override via properties.openflow_port/port when needed.
                requested_port = 6653
            else:
                requested_port = ctrl.get("port") or 6653
        openflow_port = int(requested_port)
        ui_container_port: Optional[int] = None
        ui_path: str = "/"
        creds: Optional[dict[str, str]] = None

        image = None
        command = None
        entrypoint = None
        environment = props.get("environment") if isinstance(props.get("environment"), dict) else None

        if ctrl_type == "osken":
            image = "caduceus-flux-osken-controller:latest"
            apps: list[str] = []
            if isinstance(props.get("applications"), list):
                apps = [str(a).strip() for a in props.get("applications") if str(a).strip()]
            elif props.get("application") or props.get("app"):
                apps = [str(props.get("application") or props.get("app")).strip()]
            if not apps:
                apps = ["simple_switch_13.py"]

            app_paths = [a if a.startswith("/") else f"/opt/osken/apps/{a}" for a in apps]
            command = [
                "osken-manager",
                "--observe-links",
                "--ofp-tcp-listen-port",
                str(openflow_port),
                *app_paths,
            ]
            # OS-Ken doesn't provide a built-in web UI in our image; expose none by default.
            ui_container_port = int(props.get("ui_port") or 0) or None
            ui_path = str(props.get("ui_path") or "/")
        elif ctrl_type == "ryu":
            image = "osrg/ryu:latest"
            apps: list[str] = []
            if isinstance(props.get("applications"), list):
                apps = [str(a).strip() for a in props.get("applications") if str(a).strip()]
            elif props.get("application") or props.get("app"):
                apps = [str(props.get("application") or props.get("app")).strip()]
            if not apps:
                apps = ["ryu.app.simple_switch_13"]
            rest_api = props.get("rest_api")
            if rest_api is None:
                rest_api = True
            if rest_api and "ryu.app.ofctl_rest" not in apps:
                apps.append("ryu.app.ofctl_rest")
            apps_quoted = " ".join(shlex.quote(a) for a in apps)
            command = f"ryu-manager --ofp-tcp-listen-port {openflow_port} {apps_quoted}"
            ui_container_port = int(props.get("ui_port") or props.get("rest_port") or 8080) if rest_api else None
            ui_path = str(props.get("ui_path") or "/stats/switches")
        elif ctrl_type in ("opendaylight", "odl"):
            # Prefer a modern ODL image that can auto-install required features via env.
            # Default FEATURES includes OpenFlow plugin so OVS can connect on 6653.
            image = str(props.get("image") or "opendaylight/opendaylight:14.4.0")
            ui_container_port = int(props.get("ui_port") or 8181)
            ui_path = str(props.get("ui_path") or "/explorer/index.html")
            creds = {"user": "admin", "password": "admin"}
            if environment is None:
                environment = {}
            # Allow user override; otherwise default to a sane controller feature set.
            environment.setdefault("FEATURES", "odl-restconf-all,odl-openflowplugin-southbound")
        elif ctrl_type == "onos":
            # `latest` currently tracks ONOS development snapshots (e.g. 3.x) which are not stable for this project.
            # Pin to a known stable 2.x release by default.
            image = "onosproject/onos:2.7.0"
            ui_container_port = int(props.get("ui_port") or 8181)
            ui_path = str(props.get("ui_path") or "/onos/ui")
            creds = {"user": "onos", "password": "rocks"}
        elif ctrl_type == "floodlight":
            image = str(props.get("image") or "haidarns/floodlight:latest")
            # Floodlight images vary wildly; default to the known-good haidarns/floodlight layout.
            if not props.get("command"):
                command = ["sh", "-lc", "java -jar /home/floodlight/floodlight.jar"]
            ui_container_port = int(props.get("ui_port") or props.get("rest_port") or 8080)
            ui_path = str(props.get("ui_path") or "/ui/index.html")
        elif ctrl_type == "pox":
            # POX is typically OpenFlow 1.0 only; we'll also set OpenFlow10 on switches via endpoint injection.
            image = str(props.get("image") or "haidarns/pox:latest")
            entrypoint = ["python2"]
            pox_main = str(props.get("pox_path") or "/home/cimin/pox/pox.py")
            pox_app = str(props.get("application") or props.get("app") or "forwarding.l2_learning").strip() or "forwarding.l2_learning"
            command = [pox_main, "openflow.of_01", f"--port={openflow_port}", pox_app]
            ui_container_port = int(props.get("ui_port") or 0) or None
            ui_path = str(props.get("ui_path") or "/")
        elif ctrl_type == "custom":
            image = str(props.get("image") or "").strip() or None
            command = props.get("command")
            ui_container_port = int(props.get("ui_port") or props.get("rest_port") or 0) or None
            ui_path = str(props.get("ui_path") or "/")
            maybe_creds = props.get("credentials")
            if isinstance(maybe_creds, dict):
                creds = {k: str(v) for k, v in maybe_creds.items()}

        if not image:
            out_controllers[controller_id] = {
                "ok": False,
                "error": "Missing controller image (set properties.image or use a supported controller_type)",
                "controller_type": ctrl_type,
                "node_id": node_id,
                "node_name": node_name,
            }
            continue

        ports: dict[str, int] = {}
        ui_host_port: Optional[int] = None
        if ui_container_port:
            # Controller UI port allocations are distinct from infra ranges.
            ui_host_port = reuse_or_allocate(controller_id, 42000, 45999)
            ports[f"{ui_container_port}/tcp"] = int(ui_host_port)

        run_kwargs: dict[str, Any] = {
            "image": image,
            "name": container_name,
            "detach": True,
            "network": main_network,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {
                **_topology_controller_labels(topology_id, controller_id),
                "caduceus.controller_type": ctrl_type,
                "caduceus.controller_stack_version": TOPOLOGY_CONTROLLER_STACK_VERSION,
            },
        }
        if ports:
            run_kwargs["ports"] = ports
        if command:
            run_kwargs["command"] = command
        if entrypoint:
            run_kwargs["entrypoint"] = entrypoint
        if environment:
            run_kwargs["environment"] = {str(k): str(v) for k, v in environment.items()}

        container = ensure_container(controller_id, run_kwargs)
        try:
            _connect_to_network(container, topo_network, aliases=[f"ctrl-{controller_id}", controller_id])
        except Exception:
            pass

        if ui_container_port and ui_host_port:
            try:
                container.reload()
            except Exception:
                pass
            actual_ui_port = _get_host_port(container, f"{int(ui_container_port)}/tcp")
            if isinstance(actual_ui_port, int) and 1 <= actual_ui_port <= 65535:
                ui_host_port = actual_ui_port

        # ONOS: ensure OpenFlow provider + forwarding apps are active so the controller actually listens.
        # This can take minutes; allow deferring to background warm-up.
        if wait_ready and ctrl_type == "onos":
            try:
                user = (creds or {}).get("user") if isinstance(creds, dict) else "onos"
                password = (creds or {}).get("password") if isinstance(creds, dict) else "rocks"
                auth = (str(user), str(password))
                base = f"http://{container_name}:8181/onos/v1/applications"

                # Wait for ONOS REST to become ready (broken images can return 503 with missing services).
                last_err: Optional[str] = None
                with httpx.Client(timeout=5.0) as client:
                    for _ in range(120):  # ~4 minutes
                        try:
                            r = client.get(base, auth=auth)
                            if r.status_code == 200:
                                last_err = None
                                break
                            last_err = f"HTTP {r.status_code}: {(r.text or '')[:200]}"
                        except Exception as exc:
                            last_err = str(exc)
                        time.sleep(2)

                    if last_err:
                        logger.warning("ONOS controller %s REST not ready: %s", container_name, last_err)
                    else:
                        # Activate essential apps (best-effort).
                        for app_id in ("org.onosproject.openflow", "org.onosproject.fwd", "org.onosproject.proxyarp"):
                            try:
                                rr = client.post(f"{base}/{app_id}/active", auth=auth)
                                if rr.status_code not in (200, 204):
                                    logger.warning(
                                        "ONOS controller %s app activate %s failed: HTTP %s: %s",
                                        container_name,
                                        app_id,
                                        rr.status_code,
                                        (rr.text or "")[:200],
                                    )
                            except Exception as exc:
                                logger.warning("ONOS controller %s app activate %s failed: %s", container_name, app_id, exc)

                # Wait for the OpenFlow listener to accept connections (Mininet will try immediately).
                try:
                    import socket as _socket

                    for _ in range(60):  # ~2 minutes
                        try:
                            with _socket.create_connection((str(container_name), int(openflow_port)), timeout=1.0):
                                break
                        except Exception:
                            time.sleep(2)
                except Exception:
                    pass
            except Exception:
                pass
        elif wait_ready and ctrl_type in ("odl", "opendaylight"):
            # ODL can take a while to boot; wait for the OpenFlow listener to come up so switches don't fail-fast.
            try:
                check_cmd = f"cat < /dev/null > /dev/tcp/127.0.0.1/{int(openflow_port)}"
                for _ in range(48):  # ~4 minutes
                    try:
                        code, _out = container.exec_run(["bash", "-lc", check_cmd])
                        if int(code) == 0:
                            break
                    except Exception:
                        pass
                    time.sleep(5)
            except Exception:
                pass

        out_controllers[controller_id] = {
            "ok": True,
            "controller_type": ctrl_type,
            "node_id": node_id,
            "node_name": node_name,
            "container_name": container_name,
            "openflow_port": openflow_port,
            "ui": (
                {
                    "container_port": ui_container_port,
                    "host_port": ui_host_port,
                    "path": ui_path,
                }
                if ui_container_port and ui_host_port
                else None
            ),
            "credentials": creds,
        }

    payload = {"version": TOPOLOGY_CONTROLLER_STACK_VERSION, "controllers": out_controllers, "updated_at": _iso_now()}
    try:
        consul_client.set_config(key, json.dumps(payload))
    except Exception:
        pass
    return payload


def _inject_controller_endpoints(topology_data: dict[str, Any], controllers_payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    Mutate topology controllers so the emulation container connects to per-topology controller containers.
    Also supports legacy link-based switch binding (controller nodes linked to switches).
    """
    if not controllers_payload or not isinstance(controllers_payload, dict):
        return topology_data

    controllers = controllers_payload.get("controllers")
    if not isinstance(controllers, dict):
        return topology_data

    usable = [
        c for c in controllers.values()
        if isinstance(c, dict) and c.get("ok") and c.get("container_name") and c.get("openflow_port")
    ]
    if not usable:
        return topology_data

    def _resolve_controller_host(ctrl: dict[str, Any]) -> str:
        """
        Prefer a concrete IPv4 address for OVS controller targets.

        OVS can keep using a stale resolved IP if the controller container is recreated and
        the hostname now maps to a different address. Using the current container IP at
        emulation-start time avoids that class of 'Connection refused' failures.
        """
        container_name = str(ctrl.get("container_name") or "").strip()
        if not container_name:
            return container_name

        if not docker_client:
            return container_name

        try:
            c = docker_client.containers.get(container_name)
            try:
                c.reload()
            except Exception:
                pass
            networks = ((getattr(c, "attrs", {}) or {}).get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
            if isinstance(networks, dict):
                preferred = networks.get(MAIN_DOCKER_NETWORK)
                if isinstance(preferred, dict):
                    ip = str(preferred.get("IPAddress") or "").strip()
                    if ip:
                        return ip
                for info in networks.values():
                    if not isinstance(info, dict):
                        continue
                    ip = str(info.get("IPAddress") or "").strip()
                    if ip:
                        return ip
        except Exception:
            pass

        return container_name

    def _has_controllers_list() -> bool:
        topo_controllers = topology_data.get("controllers")
        return isinstance(topo_controllers, list) and bool(topo_controllers)

    # First: if topology defines controllers explicitly, override their ip/port to the spawned container endpoints.
    topo_controllers = topology_data.get("controllers")
    if isinstance(topo_controllers, list) and topo_controllers:
        by_name: dict[str, dict[str, Any]] = {}
        for c in usable:
            node_name = str(c.get("node_name") or "").strip()
            if node_name:
                by_name[node_name] = c
        for c in topo_controllers:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or "").strip()
            match = by_name.get(name)
            if match:
                c["ip"] = str(match["container_name"])
                c["port"] = int(match["openflow_port"])
                # POX is OpenFlow 1.0 only; set OVS switches to OpenFlow10 unless user overrode it.
                ctrl_type = str(match.get("controller_type") or "").lower()
                if ctrl_type == "pox":
                    nodes = topology_data.get("nodes") or topology_data.get("devices") or []
                    if isinstance(nodes, list):
                        for n in nodes:
                            if not isinstance(n, dict):
                                continue
                            dt = str(n.get("device_type") or n.get("type") or "").lower()
                            if dt not in ("switch", "ovsswitch", "ovs", "bridge"):
                                continue
                            props = n.get("properties")
                            if not isinstance(props, dict):
                                props = {}
                                n["properties"] = props
                            props.setdefault("openflow_version", "1.0")
                elif ctrl_type == "onos":
                    # ONOS snapshots often negotiate OF1.5 with OVS and may hit decoder bugs; pin to OpenFlow13.
                    nodes = topology_data.get("nodes") or topology_data.get("devices") or []
                    if isinstance(nodes, list):
                        for n in nodes:
                            if not isinstance(n, dict):
                                continue
                            dt = str(n.get("device_type") or n.get("type") or "").lower()
                            if dt not in ("switch", "ovsswitch", "ovs", "bridge"):
                                continue
                            props = n.get("properties")
                            if not isinstance(props, dict):
                                props = {}
                                n["properties"] = props
                            props.setdefault("openflow_version", "1.3")
                elif ctrl_type in ("odl", "opendaylight"):
                    # Keep ODL on OpenFlow13 to avoid OF1.5 negotiation surprises.
                    nodes = topology_data.get("nodes") or topology_data.get("devices") or []
                    if isinstance(nodes, list):
                        for n in nodes:
                            if not isinstance(n, dict):
                                continue
                            dt = str(n.get("device_type") or n.get("type") or "").lower()
                            if dt not in ("switch", "ovsswitch", "ovs", "bridge"):
                                continue
                            props = n.get("properties")
                            if not isinstance(props, dict):
                                props = {}
                                n["properties"] = props
                            props.setdefault("openflow_version", "1.3")
                            # ODL doesn't ship a learning-switch app by default; use OVS standalone so basic L2 works.
                            props.setdefault("fail_mode", "standalone")
                            # Add a low-priority NORMAL table-miss flow so basic L2 works even with a controller connected.
                            props.setdefault("l2_fallback", "normal")
        topology_data["controllers"] = topo_controllers
        return topology_data

    nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
    links = topology_data.get("links") or []
    if not isinstance(nodes, list) or not nodes:
        return topology_data

    def _ensure_properties(node: dict[str, Any]) -> dict[str, Any]:
        props = node.get("properties")
        if not isinstance(props, dict):
            props = {}
            node["properties"] = props
        return props

    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return True
        return bool(str(value).strip())

    def _apply_controller_defaults(props: dict[str, Any], ctrl_type: str) -> None:
        ctype = str(ctrl_type or "").strip().lower()

        # Pin OpenFlow versions where controllers are known to be picky.
        desired_of = None
        if ctype == "pox":
            desired_of = "1.0"
        elif ctype == "onos":
            desired_of = "1.3"
        elif ctype in ("odl", "opendaylight"):
            desired_of = "1.3"

        if desired_of and not _has_value(props.get("openflow_version")):
            props["openflow_version"] = desired_of

        # ODL doesn't ship a learning-switch app by default; keep the topology usable.
        if ctype in ("odl", "opendaylight"):
            if not _has_value(props.get("fail_mode") or props.get("failMode") or props.get("failmode")):
                props["fail_mode"] = "standalone"
            if not _has_value(props.get("l2_fallback") or props.get("l2Fallback") or props.get("l2_fallback_mode")):
                props["l2_fallback"] = "normal"

    nodes_by_id: dict[str, dict[str, Any]] = {}
    for n in nodes:
        if isinstance(n, dict) and n.get("id"):
            nodes_by_id[str(n["id"])] = n

    controller_by_node_id: dict[str, dict[str, Any]] = {}
    for c in usable:
        node_id = str(c.get("node_id") or "").strip()
        if node_id:
            controller_by_node_id[node_id] = c

    def _is_switch(node: dict[str, Any]) -> bool:
        dt = str(node.get("device_type") or node.get("type") or "").lower()
        return dt in ("switch", "ovsswitch", "ovs", "bridge")

    # Apply link-based bindings
    bound_switch_ids: set[str] = set()
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            a = str(link.get("source_node_id") or link.get("node1") or link.get("source") or "")
            b = str(link.get("target_node_id") or link.get("node2") or link.get("target") or "")
            if not a or not b:
                continue
            if a in controller_by_node_id and b in nodes_by_id and _is_switch(nodes_by_id[b]):
                ctrl = controller_by_node_id[a]
                props = _ensure_properties(nodes_by_id[b])
                props["controller"] = f"{_resolve_controller_host(ctrl)}:{int(ctrl['openflow_port'])}"
                _apply_controller_defaults(props, str(ctrl.get("controller_type") or ""))
                bound_switch_ids.add(b)
            elif b in controller_by_node_id and a in nodes_by_id and _is_switch(nodes_by_id[a]):
                ctrl = controller_by_node_id[b]
                props = _ensure_properties(nodes_by_id[a])
                props["controller"] = f"{_resolve_controller_host(ctrl)}:{int(ctrl['openflow_port'])}"
                _apply_controller_defaults(props, str(ctrl.get("controller_type") or ""))
                bound_switch_ids.add(a)

    # If there's exactly one usable controller, apply it globally to all switches
    # that don't already have a controller set. This matches user expectations:
    # the controller "controls the topology", not just one linked switch.
    if len(usable) == 1:
        ctrl = usable[0]
        for n in nodes_by_id.values():
            if not _is_switch(n):
                continue
            props = _ensure_properties(n)
            if not _has_value(props.get("controller") or props.get("controller_ip") or props.get("controller_port")):
                props["controller"] = f"{_resolve_controller_host(ctrl)}:{int(ctrl['openflow_port'])}"
            _apply_controller_defaults(props, str(ctrl.get("controller_type") or ""))

    # If topology doesn't have an explicit controllers list, create one so Mininet shows controllers in CLI/UI.
    if not _has_controllers_list():
        topology_data["controllers"] = [
            {
                "name": str(c.get("node_name") or c.get("controller_id") or "controller"),
                "ip": str(c.get("container_name")),
                "port": int(c.get("openflow_port") or 6653),
                "type": str(c.get("controller_type") or ""),
            }
            for c in usable
        ]

    return topology_data


def stop_topology_controllers(topology_id: str) -> dict[str, Any]:
    """Stop topology-scoped controller containers (keeps any volumes by default)."""
    if not docker_client:
        return {"success": False, "error": "Docker client not available"}

    stopped: list[str] = []
    errors: dict[str, str] = {}
    prefix = f"{_topo_prefix(topology_id)}-ctrl-"
    for c in docker_client.containers.list(all=True):
        name = getattr(c, "name", "") or ""
        labels = getattr(c, "labels", {}) or {}
        if labels.get("caduceus.role") == "topology_controller" and labels.get("caduceus.topology_id") == topology_id:
            pass
        elif name.startswith(prefix):
            pass
        else:
            continue
        try:
            if getattr(c, "status", "") == "running":
                c.stop(timeout=10)
            stopped.append(name)
        except Exception as exc:
            errors[name] = str(exc)
    return {"success": True, "stopped": stopped, "errors": errors}

def remove_emulation_container(container_name: str):
    """Remove an emulation container"""
    if not docker_client:
        return

    try:
        container = docker_client.containers.get(container_name)
        container.stop(timeout=5)
        container.remove()
        logger.info(f"Removed container {container_name}")
    except docker.errors.NotFound:
        logger.warning(f"Container {container_name} not found")
    except Exception as e:
        logger.error(f"Error removing container: {e}")

def remove_active_emulation_by_id(emulation_id: str) -> Optional[str]:
    """Remove tracking entry for an emulation ID if it exists."""
    topology_id = active_emulations.find_by_emulation_id(emulation_id)
    if topology_id:
        active_emulations.delete(topology_id)
        logger.info(
            "Cleared active emulation tracking for topology %s (emulation %s)",
            topology_id,
            emulation_id
        )
        return topology_id
    return None


def _iso_now() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def record_active_emulation(
    topology_id: str,
    emulation_id: str,
    topology_data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    status_value: str = "running",
    container_id: Optional[str] = None,
    container_name: Optional[str] = None
) -> Dict[str, Any]:
    """Persist active emulation metadata in Redis."""
    record = {
        'topology_id': topology_id,
        'topology_name': topology_data.get('name'),
        'emulation_id': emulation_id,
        'status': status_value,
        'started_at': _iso_now(),
        'last_updated': _iso_now(),
        'options': options or {},
        'node_count': len(topology_data.get('nodes', topology_data.get('devices', []))),
        'link_count': len(topology_data.get('links', []))
    }

    # Add container information if provided
    if container_id:
        record['container_id'] = container_id
    if container_name:
        record['container_name'] = container_name

    active_emulations.set(topology_id, record)
    return record


def update_active_emulation(
    emulation_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """Update existing active emulation metadata."""
    topology_id = active_emulations.find_by_emulation_id(emulation_id)
    if not topology_id:
        return None

    record = active_emulations.get(topology_id) or {}
    record.update(updates)
    record['last_updated'] = _iso_now()
    active_emulations.set(topology_id, record)
    return record


async def fetch_topology_definition(topology_id: str) -> Dict[str, Any]:
    """Fetch topology definition from the topology service."""
    try:
        async with httpx.AsyncClient(timeout=TOPOLOGY_REQUEST_TIMEOUT) as client:
            response = await client.get(f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}")
    except httpx.RequestError as exc:
        logger.error("Failed to reach topology service for %s: %s", topology_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to contact topology service: {exc}"
        ) from exc

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology {topology_id} not found"
        )

    if response.status_code != status.HTTP_200_OK:
        logger.error(
            "Unexpected response fetching topology %s: %s %s",
            topology_id, response.status_code, response.text
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch topology {topology_id}: HTTP {response.status_code}"
        )

    return response.json()


grpc_client_manager = gRPCClientManager(
    active_emulations=active_emulations,
    docker_client=docker_client,
    emulation_grpc_port=EMULATION_GRPC_PORT,
)


def require_grpc_client(topology_id: str = None, emulation_id: str = None) -> "gRPCClient":
    """Get the gRPC client for a specific emulation.

    Args:
        topology_id: Topology ID to get client for
        emulation_id: Emulation ID (will be looked up to get topology_id)
    """
    # If emulation_id provided, lookup topology_id
    if emulation_id and not topology_id:
        topology_id = active_emulations.find_by_emulation_id(emulation_id)
        if not topology_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emulation {emulation_id} is not active; start it first"
            )

    if not topology_id:
        active = active_emulations.get_all()
        if len(active) == 1:
            topology_id = next(iter(active.keys()))
        elif not active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active emulations; start one first"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple emulations running; specify topology_id or emulation_id"
            )

    # Try to get or create client
    client = grpc_client_manager.get_or_create(topology_id)

    if client is None or client.stub is None:
        # If the active record points to a missing container, treat it as stale and clear it so
        # users can "Start" again instead of being stuck in a fake-running state.
        try:
            info = active_emulations.get(topology_id) if topology_id else None
            container_name = None
            if info:
                container_name = info.get("container_name") or info.get("container")  # legacy
            if not container_name and topology_id:
                container_name = f"caduceus-emu-{topology_id[:8]}"

            if docker_client and container_name:
                try:
                    docker_client.containers.get(container_name)
                except docker.errors.NotFound:
                    if topology_id:
                        active_emulations.delete(topology_id)
                        grpc_client_manager.remove_client(topology_id)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Emulation {topology_id} is not running; start it first",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Failed to perform stale-emulation cleanup for %s: %s", topology_id, exc)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Emulation backend unavailable for topology {topology_id}"
        )

    return client


_pcap_service = PcapService(
    require_grpc_client=require_grpc_client,
    resolve_runtime_name=resolve_runtime_name,
    iso_now=_iso_now,
    storage_root=(os.getenv("PCAP_STORAGE_ROOT") or "/var/lib/caduceus/pcap").strip() or "/var/lib/caduceus/pcap",
)
app.include_router(_pcap_service.router())


@app.get("/health")
async def health_check():
    """Liveness probe for orchestrator service."""
    try:
        active = active_emulations.get_all()
        return {
            "status": "ok",
            "service": "orchestrator-service",
            "active_emulations": len(active)
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read active emulations"
        ) from exc


def _algo_run_root(run_id: str) -> str:
    return f"/tmp/caduceus_algo/{run_id}"


def _resolve_emulation_container_name(topology_id: str) -> str:
    info = active_emulations.get(topology_id) or {}
    return str(info.get("container_name") or info.get("container") or f"caduceus-emu-{topology_id[:8]}")


def _require_emulation_container(topology_id: str):
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client not available in orchestrator")
    container_name = _resolve_emulation_container_name(topology_id)
    try:
        return docker_client.containers.get(container_name)
    except docker.errors.NotFound as exc:
        raise HTTPException(status_code=404, detail=f"Emulation container not found for topology {topology_id}") from exc


def _refresh_algorithm_run_status_if_needed(run_id: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Algorithm runs are background processes inside the emulation container.
    When those processes exit, the UI should see the run as stopped even if the user never pressed Stop.
    """
    try:
        if not isinstance(rec, dict):
            return rec
        if str(rec.get("status") or "").lower() != "running":
            return rec

        topology_id = str(rec.get("topology_id") or "")
        if not topology_id:
            return rec

        started_nodes = [int(i) for i in (rec.get("started_nodes") or []) if isinstance(i, (int, str))]
        if not started_nodes:
            rec["status"] = "stopped"
            algo_runs.set(run_id, rec)
            return rec

        if not docker_client:
            return rec

        container_name = str(rec.get("container_name") or _resolve_emulation_container_name(topology_id))
        try:
            container = docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            return rec

        run_root = _algo_run_root(run_id)
        ids_arg = " ".join(str(int(i)) for i in started_nodes[:256])
        shell_script = f"""
alive=0
for i in {ids_arg}; do
  pidfile={shlex.quote(run_root)}/pids/${{i}}.pid
  if test -f "$pidfile"; then
    pid=$(cat "$pidfile" 2>/dev/null || true)
    if test -n "$pid" && kill -0 "$pid" 2>/dev/null; then
      alive=$((alive+1))
    fi
  fi
done
echo "$alive"
""".strip()
        code, out = container.exec_run(["sh", "-lc", shell_script])
        if code is None:
            return rec

        text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
        alive = int((text or "").strip() or "0")
        if alive <= 0:
            rec["status"] = "stopped"
            if not rec.get("stopped_at"):
                rec["stopped_at"] = time.time()
            algo_runs.set(run_id, rec)
        return rec
    except Exception:
        return rec


def _validate_algorithm_run_in_container(
    *,
    container,
    rec: Dict[str, Any],
    run_id: str,
    tail_n: int = 2000,
) -> Dict[str, Any]:
    topology_id = str(rec.get("topology_id") or "")
    started_nodes = [int(i) for i in (rec.get("started_nodes") or []) if isinstance(i, (int, str))]
    run_root = _algo_run_root(run_id)

    def _read_state(algo_id: int) -> Dict[str, Any]:
        state_path = f"{run_root}/states/state_{int(algo_id)}.json"
        try:
            code, out = container.exec_run(["sh", "-lc", f"cat {shlex.quote(state_path)} 2>/dev/null || true"])
            if code is None:
                return {}
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
            if not text.strip():
                return {}
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _read_events_tail(algo_id: int) -> List[Dict[str, Any]]:
        path = f"{run_root}/events/events_{int(algo_id)}.jsonl"
        try:
            code, out = container.exec_run(
                ["sh", "-lc", f"test -f {shlex.quote(path)} && tail -n {int(tail_n)} {shlex.quote(path)} || true"]
            )
            if code is None:
                return []
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
            events: List[Dict[str, Any]] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        events.append(obj)
                except Exception:
                    continue
            events.sort(key=lambda e: float(e.get("ts") or 0.0))
            return events
        except Exception:
            return []

    algo_name = str((rec.get("manifest") or {}).get("name") or "")
    algo_name_l = algo_name.strip().lower()
    is_mis = "mis" in algo_name_l

    final_color: Dict[int, str] = {}
    neighbors_by_node: Dict[int, List[int]] = {}
    done_nodes: set[int] = set()

    for algo_id in started_nodes[:512]:
        state = _read_state(algo_id)
        c = state.get("color") or (state.get("overlay") or {}).get("badge") or ""
        c = str(c).strip().upper()
        if c:
            final_color[int(algo_id)] = c

        events = _read_events_tail(algo_id)
        last_neighbors: Optional[List[int]] = None
        last_color: Optional[str] = None
        saw_done = False
        for e in events:
            typ = str(e.get("type") or "").strip().lower()
            if typ == "neighbors":
                nbs = e.get("neighbors")
                if isinstance(nbs, list):
                    try:
                        last_neighbors = [int(x) for x in nbs if isinstance(x, (int, str))]
                    except Exception:
                        last_neighbors = None
            if typ == "done":
                saw_done = True
                if isinstance(e.get("neighbors"), list):
                    try:
                        last_neighbors = [int(x) for x in e.get("neighbors") if isinstance(x, (int, str))]
                    except Exception:
                        pass
                if "color" in e:
                    last_color = str(e.get("color") or "").strip().upper()
        if last_neighbors is not None:
            neighbors_by_node[int(algo_id)] = sorted({int(x) for x in last_neighbors if int(x) != int(algo_id)})
        if last_color:
            final_color[int(algo_id)] = last_color
        if saw_done:
            done_nodes.add(int(algo_id))

    started_set = set(started_nodes)
    edges: set[tuple[int, int]] = set()
    for u, nbs in neighbors_by_node.items():
        if u not in started_set:
            continue
        for v in nbs:
            if v not in started_set or v == u:
                continue
            a, b = (u, v) if u < v else (v, u)
            edges.add((a, b))

    # If the algorithm failed to discover neighbors, fall back to the topology's edges (if available)
    # so validation still catches adjacent BLACK issues.
    used_topology_edges = False
    topo_edges = rec.get("topology_edges") or []
    if not edges and isinstance(topo_edges, list) and topo_edges:
        try:
            for e in topo_edges[:8192]:
                if not isinstance(e, dict):
                    continue
                a = int(e.get("a"))
                b = int(e.get("b"))
                if a in started_set and b in started_set and a != b:
                    edges.add((a, b) if a < b else (b, a))
            used_topology_edges = len(edges) > 0
        except Exception:
            used_topology_edges = False

    colors_ok = all(final_color.get(int(i), "").strip().upper() in ("WHITE", "GRAY", "BLACK") for i in started_nodes)
    done_coverage_ok = len(done_nodes) == len(started_nodes)

    checks: List[Dict[str, Any]] = [
        {"name": "done_coverage", "ok": done_coverage_ok, "done": len(done_nodes), "started": len(started_nodes)},
        {"name": "final_colors_present", "ok": colors_ok},
    ]

    ok = done_coverage_ok and colors_ok
    details: Dict[str, Any] = {
        "started_nodes": started_nodes,
        "edges": [{"a": a, "b": b} for (a, b) in sorted(edges)],
        "colors": {str(k): v for k, v in sorted(final_color.items())},
    }
    details["edges_source"] = "topology" if used_topology_edges else "discovered"

    if is_mis:
        black = {n for n, c in final_color.items() if str(c).upper() == "BLACK"}
        conflicts: List[Dict[str, int]] = []
        for a, b in edges:
            if a in black and b in black:
                conflicts.append({"a": int(a), "b": int(b)})
                if len(conflicts) >= 50:
                    break
        independent_ok = len(conflicts) == 0

        maximal_ok = True
        for u in started_nodes:
            if u in black:
                continue
            nbs = set(neighbors_by_node.get(int(u), []))
            if not (nbs & black):
                maximal_ok = False
                break

        no_white_ok = all(str(final_color.get(int(u), "")).upper() != "WHITE" for u in started_nodes)
        checks.extend(
            [
                {"name": "mis_independence", "ok": independent_ok, "black": sorted(black), "conflicts": conflicts},
                {"name": "mis_maximality", "ok": maximal_ok},
                {"name": "mis_no_white_left", "ok": no_white_ok},
            ]
        )
        ok = ok and independent_ok and maximal_ok and no_white_ok
        details["black_nodes"] = sorted(black)
        if conflicts:
            details["conflicts"] = conflicts

    return {
        "run_id": run_id,
        "topology_id": topology_id,
        "algorithm": algo_name,
        "ok": ok,
        "checks": checks,
        "details": details,
    }


def _extract_wsn_summary_from_events_in_container(container, *, run_root: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of WSN (Wireless Sensor Network) summary metrics from algo events.

    This intentionally does not rely on a dedicated base-station aggregator; it derives the
    network-wide metrics from per-node events written by the agents.
    """
    try:
        run_root_s = str(run_root or "").strip()
        if not run_root_s:
            return None

        py = f"""
import glob
import json
import os

run_root = {json.dumps(run_root_s)}
events_dir = os.path.join(run_root, "events")
paths = sorted(glob.glob(os.path.join(events_dir, "events_*.jsonl")))[:2048]

node_initial_energy = {{}}
node_last_energy = {{}}
node_last_packets_to_bs = {{}}
node_last_role = {{}}
death_round = {{}}

# Cluster metrics (best-effort)
cluster_ids_by_round = {{}}
cluster_sizes = []

packets_to_bs_count = 0
max_round = 0

life = {{"fnd_round": None, "hnd_round": None, "lnd_round": None}}

def _to_int(v):
    try:
        return int(v)
    except Exception:
        return None

def _to_float(v):
    try:
        return float(v)
    except Exception:
        return None

for path in paths:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if not isinstance(e, dict):
                    continue

                typ = str(e.get("type") or "").strip().lower()

                if typ == "cluster_formed":
                    sz = _to_int(e.get("size"))
                    if sz is None:
                        mem = e.get("members")
                        if isinstance(mem, list):
                            try:
                                sz = len(mem)
                            except Exception:
                                sz = None
                    if sz is not None and int(sz) > 0:
                        cluster_sizes.append(int(sz))
                    continue

                if typ == "packet_to_bs":
                    packets_to_bs_count += 1

                if typ == "simulation_complete":
                    lf = e.get("lifetime")
                    if isinstance(lf, dict):
                        for k in ("fnd_round", "hnd_round", "lnd_round"):
                            vv = _to_int(lf.get(k))
                            if vv is not None:
                                life[k] = vv
                    continue

                if typ in ("fnd", "hnd", "lnd"):
                    r = _to_int(e.get("round"))
                    if r is None:
                        continue
                    key = f"{{typ}}_round"
                    if life.get(key) is None:
                        life[key] = r
                    continue

                nid_raw = e.get("node_id")
                if nid_raw is None:
                    nid_raw = e.get("node")
                nid = _to_int(nid_raw)
                if nid is None:
                    continue

                role = str(e.get("role") or "").strip().lower()
                if role:
                    node_last_role[nid] = role

                r = _to_int(e.get("round"))
                if r is not None and r > max_round:
                    max_round = r

                if typ == "energy":
                    if nid not in node_initial_energy:
                        ie = _to_float(e.get("initial_energy"))
                        if ie is not None:
                            node_initial_energy[nid] = ie
                    ce = _to_float(e.get("current_energy"))
                    if ce is not None:
                        node_last_energy[nid] = ce
                    continue

                if typ == "round_summary":
                    ce = _to_float(e.get("current_energy"))
                    if ce is not None:
                        node_last_energy[nid] = ce
                    pbs = _to_int(e.get("packets_to_bs"))
                    if pbs is not None:
                        node_last_packets_to_bs[nid] = pbs

                    # Cluster-head tracking (derive cluster count per round)
                    if role == "cluster_head" and r is not None and int(r) > 0:
                        cid = _to_int(e.get("cluster_id"))
                        if cid is None:
                            cid = nid
                        s = cluster_ids_by_round.get(int(r))
                        if s is None:
                            s = set()
                            cluster_ids_by_round[int(r)] = s
                        try:
                            s.add(int(cid))
                        except Exception:
                            pass
                    continue

                if typ == "node_death":
                    if nid not in death_round:
                        dr = _to_int(e.get("round"))
                        if dr is not None:
                            death_round[nid] = dr
                    continue
    except Exception:
        continue

nodes = set(node_last_energy.keys()) | set(node_initial_energy.keys()) | set(node_last_packets_to_bs.keys()) | set(death_round.keys())
for nid, role in list(node_last_role.items()):
    if role == "base_station":
        nodes.discard(nid)

nodes = sorted(nodes)
total_nodes = len(nodes)

initial_total = sum(float(node_initial_energy.get(n, 0.0) or 0.0) for n in nodes)
final_total = sum(float(node_last_energy.get(n, 0.0) or 0.0) for n in nodes)
energy_spent = max(0.0, initial_total - final_total)

cluster_rounds = sorted([int(x) for x in cluster_ids_by_round.keys() if isinstance(x, int) and int(x) > 0])
cluster_counts = [len(cluster_ids_by_round.get(r) or set()) for r in cluster_rounds]

packets_to_bs_total = sum(int(node_last_packets_to_bs.get(n, 0) or 0) for n in nodes)
if packets_to_bs_total <= 0 and packets_to_bs_count > 0:
    packets_to_bs_total = packets_to_bs_count

if total_nodes > 0 and (life.get("fnd_round") is None or life.get("hnd_round") is None or life.get("lnd_round") is None):
    dr = [death_round.get(n) for n in nodes if isinstance(death_round.get(n), int)]
    dr = [int(x) for x in dr if x is not None and int(x) > 0]
    dr.sort()
    if dr:
        if life.get("fnd_round") is None:
            life["fnd_round"] = dr[0]
        half = total_nodes // 2
        if half >= 1 and life.get("hnd_round") is None and len(dr) >= half:
            life["hnd_round"] = dr[half - 1]
        if life.get("lnd_round") is None and len(dr) >= total_nodes:
            life["lnd_round"] = dr[total_nodes - 1]

out = {{
    "total_nodes": total_nodes,
    "total_rounds": int(max_round or 0),
    "fnd_round": life.get("fnd_round"),
    "hnd_round": life.get("hnd_round"),
    "lnd_round": life.get("lnd_round"),
    "packets_to_bs": int(packets_to_bs_total or 0),
}}

if cluster_counts:
    out["cluster_count_avg"] = float(sum(cluster_counts)) / float(len(cluster_counts))
    out["cluster_count_min"] = int(min(cluster_counts))
    out["cluster_count_max"] = int(max(cluster_counts))
    out["cluster_count_last"] = int(cluster_counts[-1])

if cluster_sizes:
    out["cluster_size_avg"] = float(sum(cluster_sizes)) / float(len(cluster_sizes))
    out["cluster_size_min"] = int(min(cluster_sizes))
    out["cluster_size_max"] = int(max(cluster_sizes))

if initial_total > 0:
    out["initial_total_energy_j"] = float(initial_total)
    out["final_total_energy_j"] = float(final_total)
    out["energy_spent_j"] = float(energy_spent)
    if int(max_round or 0) > 0:
        out["energy_spent_per_round_j"] = float(energy_spent) / float(int(max_round))

if int(max_round or 0) > 0:
    out["packets_to_bs_per_round"] = float(packets_to_bs_total or 0) / float(int(max_round))

print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
""".strip()

        script = "python3 - <<'PY'\n" + py + "\nPY\n"
        code, out = container.exec_run(["sh", "-lc", script])
        if code is None or int(code) != 0:
            return None
        text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
        obj = json.loads(text) if text.strip() else None
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


async def _persist_algorithm_run_results_to_monitoring(run_id: str) -> None:
    """
    Persist per-node algorithm results (state + message counts) to InfluxDB via monitoring-service.
    This enables filtering/history even after orchestrator restarts.
    """
    rec = algo_runs.get(run_id) or {}
    try:
        if not isinstance(rec, dict):
            return
        if str(rec.get("status") or "").lower() != "stopped":
            return
        if bool(rec.get("persisted_to_influx")) or bool(rec.get("persisting_to_influx")):
            return

        topology_id = str(rec.get("topology_id") or "")
        if not topology_id:
            return

        if not docker_client:
            rec["persist_error"] = "docker client not available"
            algo_runs.set(run_id, rec)
            return

        container_name = str(rec.get("container_name") or _resolve_emulation_container_name(topology_id))
        try:
            container = docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            rec["persist_error"] = "emulation container not found"
            algo_runs.set(run_id, rec)
            return

        rec["persisting_to_influx"] = True
        rec["persist_error"] = None
        algo_runs.set(run_id, rec)

        run_root = _algo_run_root(run_id)
        started_nodes = [int(i) for i in (rec.get("started_nodes") or []) if isinstance(i, (int, str))]
        manifest = rec.get("manifest") or {}
        algo_name = str(manifest.get("name") or "algorithm")
        algo_version = str(manifest.get("version") or "")

        # Capture final Mininet totals and compute delta (best effort).
        mininet_final: Optional[Dict[str, int]] = None
        mininet_delta: Optional[Dict[str, int]] = None
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                mres = await client.get(f"{MONITORING_URL}/api/monitoring/topology/{topology_id}/metrics")
                if mres.status_code == 200:
                    mj = mres.json()
                    if isinstance(mj, dict):
                        mininet_final = {
                            "total_rx_packets": int(mj.get("total_rx_packets") or 0),
                            "total_tx_packets": int(mj.get("total_tx_packets") or 0),
                            "total_rx_bytes": int(mj.get("total_rx_bytes") or 0),
                            "total_tx_bytes": int(mj.get("total_tx_bytes") or 0),
                        }
        except Exception:
            mininet_final = None

        baseline = rec.get("mininet_baseline") if isinstance(rec.get("mininet_baseline"), dict) else None
        if baseline and mininet_final:
            try:
                mininet_delta = {
                    "rx_packets": int(mininet_final["total_rx_packets"]) - int(baseline.get("total_rx_packets") or 0),
                    "tx_packets": int(mininet_final["total_tx_packets"]) - int(baseline.get("total_tx_packets") or 0),
                    "rx_bytes": int(mininet_final["total_rx_bytes"]) - int(baseline.get("total_rx_bytes") or 0),
                    "tx_bytes": int(mininet_final["total_tx_bytes"]) - int(baseline.get("total_tx_bytes") or 0),
                }
                mininet_delta["total_packets"] = int(mininet_delta["rx_packets"]) + int(mininet_delta["tx_packets"])
                mininet_delta["total_bytes"] = int(mininet_delta["rx_bytes"]) + int(mininet_delta["tx_bytes"])
            except Exception:
                mininet_delta = None

        rec["mininet_final"] = mininet_final
        rec["mininet_delta"] = mininet_delta
        algo_runs.set(run_id, rec)

        payload: List[Dict[str, Any]] = []
        totals = {
            "sent_msgs": 0,
            "sent_bytes": 0,
            "broadcast_msgs": 0,
            "broadcast_bytes": 0,
            "recv_msgs": 0,
            "recv_bytes": 0,
        }
        for algo_id in started_nodes[:256]:
            state_path = f"{run_root}/states/state_{int(algo_id)}.json"
            try:
                code, out = container.exec_run(["sh", "-lc", f"cat {shlex.quote(state_path)} 2>/dev/null || true"])
                if code is None:
                    continue
                text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
                if not text.strip():
                    continue
                obj = json.loads(text)
                if not isinstance(obj, dict):
                    continue
            except Exception:
                continue

            node_obj = obj.get("node") if isinstance(obj.get("node"), dict) else {}
            stats = obj.get("stats") if isinstance(obj.get("stats"), dict) else {}
            color = obj.get("color") or (obj.get("overlay") or {}).get("badge")
            ts_ms = None
            try:
                ts_ms = int(float(obj.get("ts") or 0.0) * 1000.0)
            except Exception:
                ts_ms = int(time.time() * 1000.0)

            payload.append(
                {
                    "topology_id": topology_id,
                    "run_id": run_id,
                    "algorithm": algo_name,
                    "version": algo_version,
                    "timestamp": ts_ms,
                    "node": node_obj or {"algo_id": int(algo_id)},
                    "result": {
                        "algo_id": int(algo_id),
                        "color": str(color or ""),
                        "sent_msgs": int(stats.get("sent_msgs") or 0),
                        "sent_bytes": int(stats.get("sent_bytes") or 0),
                        "broadcast_msgs": int(stats.get("broadcast_msgs") or 0),
                        "broadcast_bytes": int(stats.get("broadcast_bytes") or 0),
                        "recv_msgs": int(stats.get("recv_msgs") or 0),
                        "recv_bytes": int(stats.get("recv_bytes") or 0),
                    },
                }
            )
            try:
                totals["sent_msgs"] += int(stats.get("sent_msgs") or 0)
                totals["sent_bytes"] += int(stats.get("sent_bytes") or 0)
                totals["broadcast_msgs"] += int(stats.get("broadcast_msgs") or 0)
                totals["broadcast_bytes"] += int(stats.get("broadcast_bytes") or 0)
                totals["recv_msgs"] += int(stats.get("recv_msgs") or 0)
                totals["recv_bytes"] += int(stats.get("recv_bytes") or 0)
            except Exception:
                pass

        if not payload:
            rec["persisted_to_influx"] = True
            rec["persisting_to_influx"] = False
            rec["persisted_at"] = time.time()
            algo_runs.set(run_id, rec)
            return

        # Validate results (best-effort) and persist a summary document too.
        validation: Optional[Dict[str, Any]] = None
        try:
            validation = _validate_algorithm_run_in_container(container=container, rec=rec, run_id=run_id, tail_n=2000)
        except Exception:
            validation = None

        # Best-effort WSN (Wireless Sensor Network) summary extraction for protocol comparison in History.
        wsn_summary: Optional[Dict[str, Any]] = None
        try:
            algo_name_l = str(algo_name or "").strip().lower()
            manifest_obj = rec.get("manifest") if isinstance(rec.get("manifest"), dict) else {}
            is_wsn = algo_name_l.startswith("wsn-") or isinstance((manifest_obj or {}).get("wsn_config"), dict)
            if is_wsn:
                wsn_summary = _extract_wsn_summary_from_events_in_container(container, run_root=run_root)
        except Exception:
            wsn_summary = None

        stopped_at = float(rec.get("stopped_at") or time.time())
        created_at = float(rec.get("created_at") or stopped_at)
        duration_s = max(0.0, stopped_at - created_at)

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{MONITORING_URL}/api/monitoring/algorithms/ingest", json=payload)
            if res.status_code >= 400:
                raise RuntimeError(f"monitoring ingest failed: HTTP {res.status_code}: {res.text[:200]}")
            summary_payload = {
                "topology_id": topology_id,
                "run_id": run_id,
                "algorithm": algo_name,
                "version": algo_version,
                "timestamp": int(stopped_at * 1000.0),
                "created_at": created_at,
                "stopped_at": stopped_at,
                "duration_s": duration_s,
                "mininet_baseline": baseline,
                "mininet_final": mininet_final,
                "mininet_delta": mininet_delta,
                "algo_totals": totals,
                "validation_ok": bool(validation.get("ok")) if isinstance(validation, dict) else None,
                "validation": validation,
            }
            if isinstance(wsn_summary, dict) and int(wsn_summary.get("total_nodes") or 0) > 0:
                try:
                    summary_payload.update(
                        {
                            "wsn_total_nodes": int(wsn_summary.get("total_nodes") or 0),
                            "wsn_total_rounds": int(wsn_summary.get("total_rounds") or 0),
                            "wsn_fnd_round": wsn_summary.get("fnd_round"),
                            "wsn_hnd_round": wsn_summary.get("hnd_round"),
                            "wsn_lnd_round": wsn_summary.get("lnd_round"),
                            "wsn_packets_to_bs": int(wsn_summary.get("packets_to_bs") or 0),
                            "wsn_packets_to_bs_per_round": wsn_summary.get("packets_to_bs_per_round"),
                            "wsn_initial_total_energy_j": wsn_summary.get("initial_total_energy_j"),
                            "wsn_final_total_energy_j": wsn_summary.get("final_total_energy_j"),
                            "wsn_energy_spent_j": wsn_summary.get("energy_spent_j"),
                            "wsn_energy_spent_per_round_j": wsn_summary.get("energy_spent_per_round_j"),
                            "wsn_cluster_count_avg": wsn_summary.get("cluster_count_avg"),
                            "wsn_cluster_count_min": wsn_summary.get("cluster_count_min"),
                            "wsn_cluster_count_max": wsn_summary.get("cluster_count_max"),
                            "wsn_cluster_count_last": wsn_summary.get("cluster_count_last"),
                            "wsn_cluster_size_avg": wsn_summary.get("cluster_size_avg"),
                            "wsn_cluster_size_min": wsn_summary.get("cluster_size_min"),
                            "wsn_cluster_size_max": wsn_summary.get("cluster_size_max"),
                            "wsn_summary": wsn_summary,
                        }
                    )
                except Exception:
                    pass
            sres = await client.post(f"{MONITORING_URL}/api/monitoring/algorithms/ingest-summary", json=summary_payload)
            if sres.status_code >= 400:
                raise RuntimeError(f"monitoring ingest-summary failed: HTTP {sres.status_code}: {sres.text[:200]}")

        rec["persisted_to_influx"] = True
        rec["persisting_to_influx"] = False
        rec["persisted_at"] = time.time()
        rec["persist_error"] = None
        algo_runs.set(run_id, rec)
    except Exception as exc:
        try:
            rec = algo_runs.get(run_id) or rec or {}
            if isinstance(rec, dict):
                rec["persisting_to_influx"] = False
                rec["persist_error"] = str(exc)
                algo_runs.set(run_id, rec)
        except Exception:
            pass


async def _fetch_topology(topology_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TOPOLOGY_REQUEST_TIMEOUT) as client:
        resp = await client.get(f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch topology {topology_id}")
        payload = resp.json()
        return payload if isinstance(payload, dict) else {}


def _build_algo_id_maps(topology: Dict[str, Any]) -> tuple[Dict[str, int], Dict[int, str]]:
    nodes = [n for n in (topology.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    # Exclude controller placeholder nodes from algorithm graph by default.
    filtered = []
    for n in nodes:
        dt = str(n.get("device_type") or n.get("type") or "").strip().lower()
        if dt in ("controller", "sdn_controller", "sdncontroller"):
            continue
        filtered.append(n)
    filtered.sort(key=lambda n: str(n.get("id") or ""))

    node_id_to_algo: Dict[str, int] = {}
    algo_to_node_id: Dict[int, str] = {}
    next_id = 1
    for n in filtered:
        nid = str(n.get("id"))
        node_id_to_algo[nid] = next_id
        algo_to_node_id[next_id] = nid
        next_id += 1
    return node_id_to_algo, algo_to_node_id


def _build_adjacency(topology: Dict[str, Any], node_id_to_algo_id: Dict[str, int]) -> Dict[int, set[int]]:
    adj: Dict[int, set[int]] = {aid: set() for aid in node_id_to_algo_id.values()}
    for link in (topology.get("links") or []):
        if not isinstance(link, dict):
            continue
        a = str(link.get("source_node_id") or link.get("source") or link.get("node1") or "")
        b = str(link.get("target_node_id") or link.get("target") or link.get("node2") or "")
        if not a or not b:
            continue
        if a not in node_id_to_algo_id or b not in node_id_to_algo_id:
            continue
        aa = int(node_id_to_algo_id[a])
        bb = int(node_id_to_algo_id[b])
        if aa == bb:
            continue
        adj.setdefault(aa, set()).add(bb)
        adj.setdefault(bb, set()).add(aa)
    return adj


def _graph_nodes_payload(topology: Dict[str, Any], node_id_to_algo_id: Dict[str, int]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for node in (topology.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or "")
        if nid not in node_id_to_algo_id:
            continue
        props = node.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        out[int(node_id_to_algo_id[nid])] = {
            **props,
            "name": node.get("name"),
            "device_type": node.get("device_type") or node.get("type"),
            "id": nid,
        }
    return out


def _device_ips_from_grpc_devices(devices: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Returns node_id -> {ip, ip6, runtime_name, device_type}
    """
    out: Dict[str, Dict[str, str]] = {}
    for d in (devices or []):
        try:
            props = d.get("properties") or {}
            if not isinstance(props, dict):
                props = {}
            node_id = str(props.get("node_id") or "")
            if not node_id:
                continue
            out[node_id] = {
                "ip": str(d.get("ip") or props.get("ip") or ""),
                "ip6": str(props.get("ip6") or ""),
                "runtime_name": str(d.get("runtime_name") or d.get("name") or ""),
                "device_type": str(d.get("device_type") or d.get("type") or ""),
            }
        except Exception:
            continue
    return out


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)


def _is_dockerized_device(device: Dict[str, Any]) -> bool:
    try:
        if not isinstance(device, dict):
            return False
        dtype = str(device.get("device_type") or device.get("type") or "").strip().lower()
        if dtype in ("docker", "container", "docker_container"):
            return True
        props = device.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        if _truthy(props.get("dockerized")):
            return True
    except Exception:
        return False
    return False


def _docker_container_pid(container_name: str) -> Optional[int]:
    if not docker_client:
        return None
    name = str(container_name or "").strip()
    if not name:
        return None
    try:
        info = docker_client.api.inspect_container(name)
        pid = int(((info or {}).get("State") or {}).get("Pid") or 0)
        return pid if pid > 0 else None
    except docker.errors.NotFound:
        return None
    except Exception:
        return None


def _mininet_docker_pid_for_runtime(runtime_name: str) -> Optional[int]:
    """
    Containernet/Mininet-Docker containers are typically named `mn.<node_name>`.
    Try a few variants to be robust across setups.
    """
    rn = str(runtime_name or "").strip()
    if not rn:
        return None
    candidates = [rn]
    if rn.startswith("mn."):
        candidates.insert(0, rn)
    else:
        candidates.insert(0, f"mn.{rn}")
    for name in candidates:
        pid = _docker_container_pid(name)
        if pid:
            return pid
    return None


def _resolve_algo_sdk_dir() -> str:
    app_dir = os.path.dirname(__file__)
    service_dir = os.path.dirname(app_dir)
    candidates = [
        os.path.join(app_dir, "algo_sdk", "caduceus_sdk"),
        os.path.join(service_dir, "algo_sdk", "caduceus_sdk"),
        "/app/algo_sdk/caduceus_sdk",
        "/app/orchestrator_app/algo_sdk/caduceus_sdk",
    ]
    for candidate in candidates:
        init_py = os.path.join(candidate, "__init__.py")
        if os.path.isdir(candidate) and os.path.exists(init_py):
            return candidate
    raise HTTPException(
        status_code=500,
        detail="Algorithm SDK directory (caduceus_sdk) not found in orchestrator container.",
    )


@app.post("/api/algorithms/runs", response_model=AlgorithmRunStartResponse)
async def start_algorithm_run(
    topology_id: str = Form(...),
    transport: str = Form("udp"),
    listen_port: int = Form(50000),
    params_json: Optional[str] = Form(None),
    manifest_json: Optional[str] = Form(None),
    source_code: Optional[str] = Form(None),
    bundle: Optional[UploadFile] = File(None),
):
    if topology_id not in active_emulations:
        raise HTTPException(status_code=404, detail="Emulation is not running for this topology; start it first")

    params: Dict[str, Any] = {}
    if params_json and str(params_json).strip():
        try:
            parsed = json.loads(params_json)
            if isinstance(parsed, dict):
                params = parsed
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid params_json: {exc}") from exc

    bundle_bytes: Optional[bytes] = None
    if bundle is not None:
        bundle_bytes = await bundle.read()

    tmp_root = None
    try:
        algo_bundle, tmp_root = load_bundle_to_tempdir(
            bundle_zip_bytes=bundle_bytes,
            manifest_json=manifest_json,
            source_code=source_code,
        )
        ip_family = str(algo_bundle.manifest.get("ip_family") or "auto").strip().lower() or "auto"
        prefer_ipv6 = ip_family in ("ipv6", "inet6", "v6")

        topology = await _fetch_topology(topology_id)
        node_id_to_algo_id, algo_id_to_node_id = _build_algo_id_maps(topology)
        adjacency = _build_adjacency(topology, node_id_to_algo_id)
        graph_nodes = _graph_nodes_payload(topology, node_id_to_algo_id)
        sdk_dir = _resolve_algo_sdk_dir()

        topo_ctx = build_topo_context(
            topology=topology,
            node_id_to_algo_id=node_id_to_algo_id,
            algo_id_to_node_id=algo_id_to_node_id,
            params=params,
        )
        try:
            selected_raw = run_selector_if_present(
                bundle=algo_bundle,
                topo_context=topo_ctx,
                extra_sys_paths=[os.path.dirname(sdk_dir)],
            )
        except Exception as exc:
            logger.warning("Algorithm selector failed; falling back to all nodes: %s", exc)
            selected_raw = None
        selected_algo_ids = normalize_selected_nodes(
            selected_raw,
            node_id_to_algo_id=node_id_to_algo_id,
            algo_id_to_node_id=algo_id_to_node_id,
        )

        # Default fallback: if selector returns [] (or None), start everywhere.
        if not selected_algo_ids:
            selected_algo_ids = sorted(algo_id_to_node_id.keys())

        grpc_client = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=None)
        devices_resp = await asyncio.to_thread(grpc_client.list_devices, "")
        devices_list = (devices_resp or {}).get("devices") or []
        device_ips = _device_ips_from_grpc_devices(devices_list)
        dockerized_runtimes: set[str] = set()
        for d in devices_list:
            try:
                rn = str(d.get("runtime_name") or d.get("name") or "").strip()
                if rn and _is_dockerized_device(d):
                    dockerized_runtimes.add(rn)
            except Exception:
                continue

        # Optional: auto-address unnumbered point-to-point links so neighbor discovery over IP works.
        # Particularly important for host-to-host topologies where only one interface per host gets an IP by default.
        auto_addr = params.get("auto_addressing", "auto")
        try:
            if isinstance(auto_addr, bool):
                auto_addr_enabled = auto_addr
                auto_addr_mode = "on"
            else:
                v = str(auto_addr or "").strip().lower()
                auto_addr_enabled = v in ("1", "true", "yes", "y", "on", "auto")
                auto_addr_mode = "auto" if v == "auto" else "on"
        except Exception:
            auto_addr_enabled = True
            auto_addr_mode = "auto"

        if auto_addr_enabled:
            try:
                links_resp = await asyncio.to_thread(grpc_client.list_links, "")
                links_list = (links_resp or {}).get("links") or []

                runtime_by_name: Dict[str, Dict[str, Any]] = {}
                iface_ipv4_by_device: Dict[str, Dict[str, set[str]]] = {}
                for d in devices_list:
                    rn = str(d.get("runtime_name") or d.get("name") or "")
                    if not rn:
                        continue
                    runtime_by_name[rn] = d
                    iface_ipv4_by_device[rn] = {}

                def _eligible(dev: str) -> bool:
                    info = runtime_by_name.get(dev) or {}
                    dt = str(info.get("device_type") or info.get("type") or "").strip().lower()
                    return dt in ("host", "station", "router", "docker", "container")

                # Query real interface IPv4 addresses per device (gRPC's interface IP mapping can be incomplete
                # for multi-interface host-host topologies).
                devices_to_probe: set[str] = set()
                for lk in links_list[:4096]:
                    n1 = str((lk or {}).get("node1") or "")
                    n2 = str((lk or {}).get("node2") or "")
                    if n1 and _eligible(n1):
                        devices_to_probe.add(n1)
                    if n2 and _eligible(n2):
                        devices_to_probe.add(n2)

                for dev in sorted(devices_to_probe)[:256]:
                    try:
                        res = await asyncio.to_thread(grpc_client.execute_command, dev, 'sh -lc "ip -4 -o addr show up || true"')
                        out = str((res or {}).get("stdout") or "")
                    except Exception:
                        out = ""
                    iface_map: Dict[str, set[str]] = {}
                    for line in out.splitlines():
                        parts = line.strip().split()
                        if len(parts) < 4:
                            continue
                        if "inet" not in parts:
                            continue
                        ifname = str(parts[1] or "").strip()
                        if not ifname:
                            continue
                        try:
                            inet_idx = parts.index("inet")
                            cidr = parts[inet_idx + 1]
                            ip = str(cidr).split("/", 1)[0].strip()
                        except Exception:
                            continue
                        if ip and ip.count(".") == 3:
                            iface_map.setdefault(ifname, set()).add(ip)
                    iface_ipv4_by_device[dev] = iface_map

                def _has_auto_ip(dev: str, port: str) -> bool:
                    ips = (iface_ipv4_by_device.get(dev) or {}).get(port) or set()
                    return any(str(ip).startswith("10.250.") for ip in ips)

                needs = 0
                for lk in links_list[:2048]:
                    n1 = str((lk or {}).get("node1") or "")
                    n2 = str((lk or {}).get("node2") or "")
                    p1 = str((lk or {}).get("port1") or "")
                    p2 = str((lk or {}).get("port2") or "")
                    if not (n1 and n2 and p1 and p2):
                        continue
                    if not (_eligible(n1) and _eligible(n2)):
                        continue
                    if not (_has_auto_ip(n1, p1) and _has_auto_ip(n2, p2)):
                        needs += 1
                should_apply = auto_addr_mode == "on" or needs >= 1

                if should_apply:
                    # Deterministic per-link /30s in 10.250.0.0/16 (avoids clashing with Mininet's 10.0.0.0/8).
                    base_a = 10
                    base_b = 250
                    link_idx = 0
                    cmds_by_dev: Dict[str, list[str]] = {}
                    applied = 0

                    for lk in links_list[:4096]:
                        n1 = str((lk or {}).get("node1") or "")
                        n2 = str((lk or {}).get("node2") or "")
                        p1 = str((lk or {}).get("port1") or "")
                        p2 = str((lk or {}).get("port2") or "")
                        if not (n1 and n2 and p1 and p2):
                            continue
                        if not (_eligible(n1) and _eligible(n2)):
                            continue
                        # Only add if this link doesn't already have our auto-addresses.
                        if _has_auto_ip(n1, p1) and _has_auto_ip(n2, p2):
                            continue

                        c = (link_idx // 64) % 256
                        d = (link_idx % 64) * 4
                        a1 = f"{base_a}.{base_b}.{c}.{d + 1}"
                        a2 = f"{base_a}.{base_b}.{c}.{d + 2}"
                        link_idx += 1

                        for dev, port, ip in ((n1, p1, a1), (n2, p2, a2)):
                            cmds = cmds_by_dev.setdefault(dev, [])
                            qport = shlex.quote(port)
                            cmds.append(f"ip link set dev {qport} up >/dev/null 2>&1 || true")
                            cmds.append(f"ip addr add {shlex.quote(ip)}/30 dev {qport} >/dev/null 2>&1 || true")
                        applied += 1

                    for dev, lines in cmds_by_dev.items():
                        if not lines:
                            continue
                        script = "sh -lc " + shlex.quote("\n".join(lines))
                        await asyncio.to_thread(grpc_client.execute_command, dev, script)

                    if applied > 0:
                        logger.info(
                            "Auto-addressing applied for %s links on topology %s (mode=%s)",
                            applied,
                            topology_id,
                            auto_addr_mode,
                        )
            except Exception:
                pass

        # Capture Mininet totals as baseline *before* starting the agents (best-effort).
        mininet_baseline: Optional[Dict[str, int]] = None
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                mres = await client.get(f"{MONITORING_URL}/api/monitoring/topology/{topology_id}/metrics")
                if mres.status_code == 200:
                    mj = mres.json()
                    if isinstance(mj, dict):
                        mininet_baseline = {
                            "total_rx_packets": int(mj.get("total_rx_packets") or 0),
                            "total_tx_packets": int(mj.get("total_tx_packets") or 0),
                            "total_rx_bytes": int(mj.get("total_rx_bytes") or 0),
                            "total_tx_bytes": int(mj.get("total_tx_bytes") or 0),
                        }
        except Exception:
            mininet_baseline = None

        run_id = new_run_id()
        run_root = _algo_run_root(run_id)

        per_node_configs: Dict[int, Dict[str, Any]] = {}
        for algo_id, node_uuid in algo_id_to_node_id.items():
            node_obj = next((n for n in (topology.get("nodes") or []) if isinstance(n, dict) and str(n.get("id")) == node_uuid), None) or {}
            node_info = device_ips.get(node_uuid, {})
            neighbors: Dict[int, Dict[str, Any]] = {}
            for nb in sorted(adjacency.get(int(algo_id), set())):
                nb_uuid = algo_id_to_node_id.get(int(nb))
                nb_info = device_ips.get(str(nb_uuid), {}) if nb_uuid else {}
                ip = str((nb_info.get("ip6") if prefer_ipv6 else nb_info.get("ip")) or nb_info.get("ip") or nb_info.get("ip6") or "")
                if not ip:
                    continue
                neighbors[int(nb)] = {"ip": ip, "port": int(listen_port)}

            per_node_configs[int(algo_id)] = {
                "run_id": run_id,
                "run_dir": run_root,
                "transport": str(transport or "udp").strip().lower(),
                "ip_family": ip_family,
                "listen_port": int(listen_port),
                "params": params,
                "graph_nodes": graph_nodes,
                "node": {
                    "uuid": node_uuid,
                    "name": node_obj.get("name") or node_uuid,
                    "type": node_obj.get("device_type") or node_obj.get("type") or "",
                    "algo_id": int(algo_id),
                },
                "neighbors": neighbors,
                "selected": int(algo_id) in set(selected_algo_ids),
            }

        # Persist topology edges (algo_id pairs) into the run record so validation can check
        # correctness even if an algorithm's neighbor discovery fails.
        topo_edges: List[Dict[str, int]] = []
        try:
            edge_set: set[tuple[int, int]] = set()
            for u, nbs in (adjacency or {}).items():
                try:
                    uu = int(u)
                except Exception:
                    continue
                for v in (nbs or []):
                    try:
                        vv = int(v)
                    except Exception:
                        continue
                    if uu == vv:
                        continue
                    a, b = (uu, vv) if uu < vv else (vv, uu)
                    edge_set.add((a, b))
            topo_edges = [{"a": int(a), "b": int(b)} for (a, b) in sorted(edge_set)]
        except Exception:
            topo_edges = []

        tar_bytes = create_run_tar_bytes(
            run_id=run_id,
            bundle=algo_bundle,
            sdk_dir=sdk_dir,
            per_node_configs=per_node_configs,
        )

        container = await asyncio.to_thread(_require_emulation_container, topology_id)
        await asyncio.to_thread(container.put_archive, "/", tar_bytes)

        started: List[int] = []
        skipped: List[int] = []
        errors: List[str] = []

        for algo_id in selected_algo_ids:
            node_uuid = algo_id_to_node_id.get(int(algo_id))
            if not node_uuid:
                skipped.append(int(algo_id))
                continue

            node_info = device_ips.get(str(node_uuid), {})
            runtime_name = str(node_info.get("runtime_name") or "")
            ip = str((node_info.get("ip6") if prefer_ipv6 else node_info.get("ip")) or node_info.get("ip") or node_info.get("ip6") or "")
            if not runtime_name:
                skipped.append(int(algo_id))
                errors.append(f"node {node_uuid}: missing runtime_name")
                continue
            if not ip:
                skipped.append(int(algo_id))
                errors.append(f"node {node_uuid}: missing IP (cannot message neighbors)")
                continue

            cfg_path = f"{run_root}/configs/{int(algo_id)}.json"
            manifest_path = f"{run_root}/manifest.json"
            log_path = f"{run_root}/logs/{int(algo_id)}.log"
            pid_path = f"{run_root}/pids/{int(algo_id)}.pid"

            # If this is a dockerized Containernet node, don't run the agent *inside* the node container.
            # Instead, run it from the emulation container and enter the node's network namespace.
            if runtime_name in dockerized_runtimes:
                netns_pid = await asyncio.to_thread(_mininet_docker_pid_for_runtime, runtime_name)
                if not netns_pid:
                    skipped.append(int(algo_id))
                    errors.append(f"{runtime_name}: docker netns PID not found; skipped")
                    continue

                setns_py = (
                    "import os,sys;"
                    "pid=int(sys.argv[1]);"
                    "fd=os.open(f'/proc/{pid}/ns/net', os.O_RDONLY);"
                    "os.setns(fd,0);"
                    "os.close(fd);"
                    "os.execvp(sys.argv[2], sys.argv[2:])"
                )
                wrapped = (
                    "python3 -c "
                    + shlex.quote(setns_py)
                    + " "
                    + shlex.quote(str(int(netns_pid)))
                    + " "
                    + " ".join(
                        shlex.quote(arg)
                        for arg in (
                            "python3",
                            "-u",
                            "-m",
                            "caduceus_sdk.agent_main",
                            "--config",
                            cfg_path,
                            "--manifest",
                            manifest_path,
                        )
                    )
                )

                script = (
                    "mkdir -p "
                    + " ".join(shlex.quote(p) for p in (f"{run_root}/logs", f"{run_root}/pids"))
                    + " && ("
                    + f"export PYTHONPATH={shlex.quote(run_root)}:{shlex.quote(run_root + '/bundle')}; "
                    + "if command -v nohup >/dev/null 2>&1; then "
                    + f"nohup {wrapped} > {shlex.quote(log_path)} 2>&1 & "
                    + "else "
                    + f"{wrapped} > {shlex.quote(log_path)} 2>&1 & "
                    + "fi; "
                    + f"echo $! > {shlex.quote(pid_path)}"
                    + ")"
                )
                code, out = await asyncio.to_thread(container.exec_run, ["sh", "-lc", script])
                if int(code or 0) == 0:
                    started.append(int(algo_id))
                else:
                    skipped.append(int(algo_id))
                    text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
                    errors.append(f"{runtime_name}: failed to start agent (docker netns): {text}".strip())
                continue

            # Ensure a Python 3 interpreter exists inside that node namespace (mostly for non-docker Mininet nodes).
            # Some environments ship only `python` (python3) or have an incomplete PATH.
            py_cmd: Optional[str] = None
            base_path = "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

            probe_py3 = await asyncio.to_thread(
                grpc_client.execute_command,
                runtime_name,
                f"sh -lc \"{base_path}; command -v python3 >/dev/null 2>&1\"",
            )
            if (probe_py3 or {}).get("success"):
                py_cmd = "python3"
            else:
                probe_py = await asyncio.to_thread(
                    grpc_client.execute_command,
                    runtime_name,
                    f"sh -lc \"{base_path}; command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(0 if sys.version_info[0] >= 3 else 1)' >/dev/null 2>&1\"",
                )
                if (probe_py or {}).get("success"):
                    py_cmd = "python"

            if not py_cmd:
                # Some environments don't surface dockerization metadata; if python3 is missing, try docker netns.
                netns_pid = await asyncio.to_thread(_mininet_docker_pid_for_runtime, runtime_name)
                if netns_pid:
                    dockerized_runtimes.add(runtime_name)
                    # Retry once using docker netns path.
                    setns_py = (
                        "import os,sys;"
                        "pid=int(sys.argv[1]);"
                        "fd=os.open(f'/proc/{pid}/ns/net', os.O_RDONLY);"
                        "os.setns(fd,0);"
                        "os.close(fd);"
                        "os.execvp(sys.argv[2], sys.argv[2:])"
                    )
                    wrapped = (
                        "python3 -c "
                        + shlex.quote(setns_py)
                        + " "
                        + shlex.quote(str(int(netns_pid)))
                        + " "
                        + " ".join(
                            shlex.quote(arg)
                            for arg in (
                                "python3",
                                "-u",
                                "-m",
                                "caduceus_sdk.agent_main",
                                "--config",
                                cfg_path,
                                "--manifest",
                                manifest_path,
                            )
                        )
                    )
                    script = (
                        "mkdir -p "
                        + " ".join(shlex.quote(p) for p in (f"{run_root}/logs", f"{run_root}/pids"))
                        + " && ("
                        + f"export PYTHONPATH={shlex.quote(run_root)}:{shlex.quote(run_root + '/bundle')}; "
                        + "if command -v nohup >/dev/null 2>&1; then "
                        + f"nohup {wrapped} > {shlex.quote(log_path)} 2>&1 & "
                        + "else "
                        + f"{wrapped} > {shlex.quote(log_path)} 2>&1 & "
                        + "fi; "
                        + f"echo $! > {shlex.quote(pid_path)}"
                        + ")"
                    )
                    code, out = await asyncio.to_thread(container.exec_run, ["sh", "-lc", script])
                    if int(code or 0) == 0:
                        started.append(int(algo_id))
                    else:
                        skipped.append(int(algo_id))
                        text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
                        errors.append(f"{runtime_name}: failed to start agent (docker netns): {text}".strip())
                    continue

                skipped.append(int(algo_id))
                errors.append(f"{runtime_name}: python3/python not found; skipped")
                continue

            cmd = (
                "sh -lc "
                + shlex.quote(
                    "mkdir -p "
                    + " ".join(shlex.quote(p) for p in (f"{run_root}/logs", f"{run_root}/pids"))
                    + " && ("
                    + f"export PYTHONPATH={shlex.quote(run_root)}:{shlex.quote(run_root + '/bundle')}; "
                    + "if command -v nohup >/dev/null 2>&1; then "
                    + f"nohup {py_cmd} -u -m caduceus_sdk.agent_main --config {shlex.quote(cfg_path)} --manifest {shlex.quote(manifest_path)} "
                    + f"> {shlex.quote(log_path)} 2>&1 & "
                    + "else "
                    + f"{py_cmd} -u -m caduceus_sdk.agent_main --config {shlex.quote(cfg_path)} --manifest {shlex.quote(manifest_path)} "
                    + f"> {shlex.quote(log_path)} 2>&1 & "
                    + "fi; "
                    + f"echo $! > {shlex.quote(pid_path)}"
                    + ")"
                )
            )
            res = await asyncio.to_thread(grpc_client.execute_command, runtime_name, cmd)
            if (res or {}).get("success"):
                started.append(int(algo_id))
            else:
                skipped.append(int(algo_id))
                err = (res or {}).get("stderr") or (res or {}).get("stdout") or ""
                errors.append(f"{runtime_name}: failed to start agent: {err}".strip())

        record = {
            "run_id": run_id,
            "topology_id": topology_id,
            "status": "running",
            "created_at": time.time(),
            "stopped_at": None,
            "manifest": algo_bundle.manifest,
            "transport": str(transport or "udp").strip().lower(),
            "listen_port": int(listen_port),
            "node_id_to_algo_id": node_id_to_algo_id,
            "algo_id_to_node_id": {int(k): v for k, v in algo_id_to_node_id.items()},
            "started_nodes": started,
            "skipped_nodes": skipped,
            "errors": errors,
            "container_name": _resolve_emulation_container_name(topology_id),
            "topology_edges": topo_edges,
            "mininet_baseline": mininet_baseline,
            "mininet_final": None,
            "mininet_delta": None,
            "persisted_to_influx": False,
            "persisting_to_influx": False,
            "persisted_at": None,
            "persist_error": None,
        }
        algo_runs.set(run_id, record)

        return AlgorithmRunStartResponse(
            run_id=run_id,
            topology_id=topology_id,
            status="running",
            message="started",
            nodes_started=len(started),
            nodes_skipped=len(skipped),
            selected_algo_ids=selected_algo_ids,
        )
    finally:
        if tmp_root:
            try:
                import shutil

                shutil.rmtree(tmp_root, ignore_errors=True)
            except Exception:
                pass


@app.get("/api/algorithms/runs/{run_id}", response_model=AlgorithmRunStatusResponse)
async def get_algorithm_run(run_id: str):
    rec = algo_runs.get(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Algorithm run not found")
    rec = _refresh_algorithm_run_status_if_needed(run_id, rec)
    try:
        if isinstance(rec, dict) and str(rec.get("status") or "").lower() == "stopped" and not bool(rec.get("persisted_to_influx")):
            asyncio.create_task(_persist_algorithm_run_results_to_monitoring(run_id))
    except Exception:
        pass
    return AlgorithmRunStatusResponse(**rec)


@app.post("/api/algorithms/runs/{run_id}/stop", response_model=AlgorithmRunStatusResponse)
async def stop_algorithm_run(run_id: str):
    rec = algo_runs.get(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Algorithm run not found")

    topology_id = str(rec.get("topology_id") or "")
    if not topology_id:
        raise HTTPException(status_code=400, detail="Run record missing topology_id")

    errors: List[str] = []
    run_root = _algo_run_root(run_id)
    started_nodes = [int(i) for i in (rec.get("started_nodes") or []) if isinstance(i, (int, str))]
    try:
        container = await asyncio.to_thread(_require_emulation_container, topology_id)
        if not started_nodes:
            script = "true"
        else:
            ids_arg = " ".join(str(int(i)) for i in started_nodes[:512])
            script = f"""
for i in {ids_arg}; do
  pidfile={shlex.quote(run_root)}/pids/${{i}}.pid
  if test -f "$pidfile"; then
    pid=$(cat "$pidfile" 2>/dev/null || true)
    if test -n "$pid"; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  fi
done
""".strip()
        code, out = await asyncio.to_thread(container.exec_run, ["sh", "-lc", script])
        if int(code or 0) != 0:
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
            errors.append(f"failed to stop one or more agents: {text}".strip())
    except Exception as exc:
        errors.append(f"failed to stop agents: {exc}")

    rec["status"] = "stopped"
    if not rec.get("stopped_at"):
        rec["stopped_at"] = time.time()
    if errors:
        rec["errors"] = (rec.get("errors") or []) + errors
    algo_runs.set(run_id, rec)
    try:
        asyncio.create_task(_persist_algorithm_run_results_to_monitoring(run_id))
    except Exception:
        pass
    return AlgorithmRunStatusResponse(**rec)


@app.get("/api/algorithms/runs/{run_id}/events")
async def get_algorithm_run_events(run_id: str, algo_id: Optional[int] = None, tail: int = 200):
    rec = algo_runs.get(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Algorithm run not found")
    topology_id = str(rec.get("topology_id") or "")
    container_name = str(rec.get("container_name") or _resolve_emulation_container_name(topology_id))
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client not available")
    try:
        container = docker_client.containers.get(container_name)
    except docker.errors.NotFound as exc:
        raise HTTPException(status_code=404, detail="Emulation container not found") from exc

    tail_n = max(1, min(int(tail or 200), 2000))
    run_root = _algo_run_root(run_id)
    if algo_id is not None:
        paths = [f"{run_root}/events/events_{int(algo_id)}.jsonl"]
    else:
        paths = [f"{run_root}/events/events_{int(i)}.jsonl" for i in (rec.get("started_nodes") or [])]
        if not paths:
            paths = [f"{run_root}/events/events_{int(i)}.jsonl" for i in (rec.get("skipped_nodes") or [])]

    events: List[Dict[str, Any]] = []
    for path in paths[:64]:
        try:
            code, out = container.exec_run(["sh", "-lc", f"test -f {shlex.quote(path)} && tail -n {tail_n} {shlex.quote(path)} || true"])
            if code is None:
                continue
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        events.append(obj)
                except Exception:
                    continue
        except Exception:
            continue

    events.sort(key=lambda e: float(e.get("ts") or 0.0))
    return {"run_id": run_id, "events": events}


@app.get("/api/algorithms/topologies/{topology_id}/overlay", response_model=AlgorithmOverlayResponse)
async def get_topology_algorithm_overlay(topology_id: str, run_id: Optional[str] = None):
    """
    Return topology overlays for a specific algorithm run.
    If run_id is omitted, returns overlays for the latest run on this topology.
    """
    if run_id:
        run_id = str(run_id).strip()
    if not run_id:
        run_id = algo_runs.latest_for_topology(topology_id)
    if not run_id:
        return AlgorithmOverlayResponse(topology_id=topology_id, run_id=None, overlays={})
    rec = algo_runs.get(run_id)
    if not rec:
        return AlgorithmOverlayResponse(topology_id=topology_id, run_id=None, overlays={})
    if str(rec.get("topology_id") or "") != str(topology_id):
        raise HTTPException(status_code=400, detail="run_id does not belong to topology_id")

    container_name = str(rec.get("container_name") or _resolve_emulation_container_name(topology_id))
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client not available")
    try:
        container = docker_client.containers.get(container_name)
    except docker.errors.NotFound:
        return AlgorithmOverlayResponse(topology_id=topology_id, run_id=run_id, overlays={})

    run_root = _algo_run_root(run_id)
    overlays: Dict[str, Any] = {}
    algo_id_to_node_id = rec.get("algo_id_to_node_id") or {}
    for algo_id in (rec.get("started_nodes") or []):
        node_uuid = algo_id_to_node_id.get(str(int(algo_id))) or algo_id_to_node_id.get(int(algo_id))
        if not node_uuid:
            continue
        state_path = f"{run_root}/states/state_{int(algo_id)}.json"
        try:
            code, out = container.exec_run(["sh", "-lc", f"cat {shlex.quote(state_path)} 2>/dev/null || true"])
            if code is None:
                continue
            text = out.decode("utf-8", errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
            if not text.strip():
                continue
            obj = json.loads(text)
            if not isinstance(obj, dict):
                continue
            overlay = obj.get("overlay")
            if overlay is None:
                continue
            overlays[str(node_uuid)] = overlay
        except Exception:
            continue

    return AlgorithmOverlayResponse(topology_id=topology_id, run_id=run_id, overlays=overlays)


@app.get("/api/algorithms/runs/{run_id}/validate")
async def validate_algorithm_run(run_id: str):
    """
    Best-effort validation for known algorithms.

    - Always returns generic run sanity checks (done coverage, final colors present).
    - For `distributed-mis` (or algorithms whose manifest name contains `mis`),
      checks MIS properties on the *discovered neighbor graph* (from events):
        - independence: no BLACK-BLACK edge
        - maximality: every non-BLACK node has a BLACK neighbor
    """
    rec = algo_runs.get(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Algorithm run not found")

    topology_id = str(rec.get("topology_id") or "")
    container_name = str(rec.get("container_name") or _resolve_emulation_container_name(topology_id))
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker client not available")
    try:
        container = docker_client.containers.get(container_name)
    except docker.errors.NotFound as exc:
        raise HTTPException(status_code=404, detail="Emulation container not found") from exc

    return _validate_algorithm_run_in_container(container=container, rec=rec, run_id=run_id, tail_n=2000)


@app.get("/api/infrastructure/status")
async def infrastructure_status_endpoint(
    topology_id: Optional[str] = None,
    include_stopped: bool = True,
    sync_consul: bool = False,
):
    """
    Report project infrastructure container status (Grafana/Prometheus/Consul/InfluxDB/Kafka/RabbitMQ/etc).

    If topology_id is provided, includes that topology's emulation container details.
    If sync_consul is true and topology_id is provided, persists a snapshot under
    `caduceus/topologies/<topology_id>/infrastructure`.
    """
    # Keep this endpoint responsive even if Docker/Consul are slow/unavailable.
    try:
        infra = await asyncio.wait_for(
            asyncio.to_thread(get_infrastructure_status, include_stopped=include_stopped),
            timeout=4.0,
        )
    except Exception as exc:
        infra = {"items": [], "missing": [], "total": 0, "missing_total": 0, "error": str(exc)}

    if topology_id:
        try:
            emulation = await asyncio.wait_for(
                asyncio.to_thread(get_topology_emulation_container, topology_id),
                timeout=2.0,
            )
        except Exception as exc:
            emulation = {"topology_id": topology_id, "error": str(exc)}
    else:
        emulation = None

    async def _consul_get(key: str) -> Optional[str]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(consul_client.get_config, key), timeout=2.0)
        except Exception:
            return None

    topology_resources = None
    if topology_id:
        topology_resources = {
            "influxdb_bucket": await _consul_get(f"caduceus/topologies/{topology_id}/influxdb_bucket"),
            "grafana_datasource_name": await _consul_get(f"caduceus/topologies/{topology_id}/grafana_datasource_name"),
            "grafana_datasource_uid": await _consul_get(f"caduceus/topologies/{topology_id}/grafana_datasource_uid"),
        }

    if sync_consul and topology_id:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(sync_topology_infrastructure_to_consul, topology_id),
                timeout=8.0,
            )
        except Exception:
            pass

    return {"infrastructure": infra, "emulation": emulation, "topology_resources": topology_resources}


@app.get("/api/infrastructure/jupyter")
async def infrastructure_jupyter_endpoint():
    """
    Return JupyterLab access info for the UI.

    The Data Lab UI is proxied at `/jupyter/` and typically protected by a token.
    This endpoint reports the current token from the running `caduceus-jupyterlab` container
    so the frontend can auto-login.
    """
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    container = None
    try:
        container = docker_client.containers.get("caduceus-jupyterlab")
    except Exception:
        try:
            for c in docker_client.containers.list(all=True):
                labels = getattr(c, "labels", {}) or {}
                if labels.get("com.docker.compose.service") == "jupyterlab":
                    container = c
                    break
        except Exception:
            container = None

    if not container:
        return {"available": False, "error": "JupyterLab container not found", "base_url": "/jupyter/"}

    try:
        container.reload()
    except Exception:
        pass

    env = _env_list_to_dict((getattr(container, "attrs", {}) or {}).get("Config", {}).get("Env", []) or [])
    token = str(env.get("JUPYTER_TOKEN") or "").strip()
    host_port = _get_host_port(container, "8888/tcp")

    return {
        "available": True,
        "container_name": getattr(container, "name", None),
        "status": getattr(container, "status", None),
        "host_port": host_port,
        "base_url": "/jupyter/",
        "token": token,
    }


@app.post("/api/infrastructure/ensure")
async def infrastructure_ensure_endpoint(payload: InfrastructureEnsureRequest):
    """Start stopped infrastructure containers (if they exist)."""
    return ensure_infrastructure_running(payload.services)


@app.get("/api/infrastructure/topologies")
async def infrastructure_topologies_endpoint():
    """
    List active topology simulations along with topology-scoped infrastructure resources.
    Currently includes the per-topology InfluxDB bucket (if created by monitoring).
    """
    items: list[dict[str, Any]] = []
    for topology_id, info in (active_emulations.get_all() or {}).items():
        try:
            bucket = await asyncio.wait_for(
                asyncio.to_thread(consul_client.get_config, f"caduceus/topologies/{topology_id}/influxdb_bucket"),
                timeout=1.5,
            )
        except Exception:
            bucket = None
        items.append(
            {
                "topology_id": topology_id,
                "emulation_id": info.get("emulation_id"),
                "status": info.get("status"),
                "container_name": info.get("container_name"),
                "influxdb_bucket": bucket,
            }
        )
    items.sort(key=lambda r: (r.get("status") != "running", str(r.get("topology_id") or "")))
    return {"items": items}


@app.post("/api/topologies/{topology_id}/observability/ensure")
async def ensure_topology_observability_endpoint(topology_id: str):
    """Best-effort ensure of topology-scoped observability resources (bucket + Grafana datasource)."""
    await ensure_topology_observability(topology_id)
    try:
        bucket = await asyncio.wait_for(
            asyncio.to_thread(consul_client.get_config, f"caduceus/topologies/{topology_id}/influxdb_bucket"),
            timeout=1.5,
        )
    except Exception:
        bucket = None
    return {
        "success": True,
        "topology_id": topology_id,
        "influxdb_bucket": bucket,
    }


@app.post("/api/infrastructure/topologies/{topology_id}/observability/ensure")
async def ensure_topology_observability_infra_endpoint(topology_id: str):
    return await ensure_topology_observability_endpoint(topology_id)


@app.post("/api/topologies/{topology_id}/infra/ensure")
async def ensure_topology_infra_endpoint(topology_id: str, force_isolated: bool = False):
    """
    Ensure topology infrastructure is present.
    When `TOPOLOGY_INFRA_MODE=isolated`, starts a dedicated infra stack per topology and returns UI ports.
    """
    if TOPOLOGY_INFRA_MODE != "isolated" and not force_isolated:
        return {"success": True, "topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE}

    infra = await asyncio.to_thread(ensure_topology_isolated_infra, topology_id)
    controllers = None
    try:
        topology_data = await fetch_topology_definition(topology_id)
        controllers = await asyncio.to_thread(ensure_topology_controllers, topology_id, topology_data, False)
    except Exception as exc:
        logger.warning("Topology %s controller ensure via infra/ensure failed: %s", topology_id, exc)

    # Best-effort: if this topology has an isolated ETSI OSM stack, reconcile it in the background so
    # controller/VIM/WIM/SDN bootstrap stays up-to-date without manual Sync clicks.
    try:
        await _schedule_isolated_osm_reconcile(topology_id)
    except Exception:
        pass
    mode = "isolated" if (TOPOLOGY_INFRA_MODE == "isolated" or force_isolated) else TOPOLOGY_INFRA_MODE
    return {"success": True, "topology_id": topology_id, "mode": mode, "infra": infra, "controllers": controllers}


@app.post("/api/infrastructure/topologies/{topology_id}/infra/ensure")
async def ensure_topology_infra_infra_endpoint(topology_id: str, force_isolated: bool = False):
    return await ensure_topology_infra_endpoint(topology_id, force_isolated=force_isolated)


@app.post("/api/infrastructure/topologies/{topology_id}/osm/ensure")
async def ensure_topology_osm_endpoint(topology_id: str):
    """
    Ensure an isolated ETSI OSM stack exists for this topology (per-topology NFVO-like environment).
    Creates a topology-scoped osm-connector registered in Consul as `osm-connector-<topology_id[:8]>`.
    """
    if OSM_TOPOLOGY_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": OSM_TOPOLOGY_MODE}
    try:
        topology_data = await fetch_topology_definition(topology_id)
        await asyncio.to_thread(ensure_topology_controllers, topology_id, topology_data, False)
    except Exception as exc:
        logger.warning("Topology %s controller ensure via osm/ensure failed: %s", topology_id, exc)

    lock = await _get_topology_osm_lock(topology_id)
    async with lock:
        osm = await asyncio.to_thread(ensure_topology_isolated_osm, topology_id)
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "osm": osm}


@app.get("/api/infrastructure/topologies/{topology_id}/osm/status")
async def topology_osm_status_endpoint(topology_id: str):
    raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_osm")
    payload = None
    if raw:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None

    containers: list[dict[str, Any]] = []
    if OSM_TOPOLOGY_MODE == "isolated" and docker_client:
        for c in _list_topology_osm_containers(topology_id):
            try:
                c.reload()
            except Exception:
                pass
            containers.append(
                {
                    "name": getattr(c, "name", None),
                    "status": getattr(c, "status", None),
                    "image": getattr(getattr(c, "image", None), "tags", None),
                }
            )
    return {
        "topology_id": topology_id,
        "mode": OSM_TOPOLOGY_MODE,
        "osm": payload,
        "containers": containers,
    }


@app.post("/api/infrastructure/topologies/{topology_id}/osm/stop")
async def stop_topology_osm_endpoint(topology_id: str, request: Optional[TopologyOsmStopRequest] = None):
    if OSM_TOPOLOGY_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": OSM_TOPOLOGY_MODE}
    preserve_data = bool((request.preserve_data if request else True))
    lock = await _get_topology_osm_lock(topology_id)
    async with lock:
        res = await asyncio.to_thread(stop_topology_isolated_osm, topology_id, preserve_data)
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "result": res}


@app.post("/api/infrastructure/topologies/{topology_id}/osm/purge")
async def purge_topology_osm_endpoint(topology_id: str, request: TopologyOsmPurgeRequest):
    if OSM_TOPOLOGY_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": OSM_TOPOLOGY_MODE}
    if not bool(request.confirm):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true required")
    lock = await _get_topology_osm_lock(topology_id)
    async with lock:
        res = await asyncio.to_thread(_remove_topology_osm_resources, topology_id, remove_volumes=bool(request.remove_volumes))
    try:
        consul_client.client.kv.delete(f"caduceus/topologies/{topology_id}/isolated_osm")
    except Exception:
        pass
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "result": res}


@app.get("/api/topologies/{topology_id}/infra/status")
async def topology_infra_status_endpoint(topology_id: str):
    """Get topology infra status payload (if isolated infra is enabled)."""
    raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_infra")
    payload = None
    if raw:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None

    # Best-effort reconcile: if containers exist, the Docker port bindings are the source of truth.
    # This fixes cases where Consul was unavailable during an earlier `ensure_topology_isolated_infra`
    # run and the stored host ports drifted from the running containers.
    if TOPOLOGY_INFRA_MODE == "isolated" and docker_client and isinstance(payload, dict):
        try:
            services = payload.get("services")
            if isinstance(services, dict):
                port_map: dict[str, str] = {
                    "grafana": "3000/tcp",
                    "prometheus": "9090/tcp",
                    "consul": "8500/tcp",
                    "influxdb": "8086/tcp",
                    "rabbitmq": "15672/tcp",
                    "kafka-ui": "8080/tcp",
                    "portainer": "9443/tcp",
                    "portainer-http": "9000/tcp",
                }
                changed = False
                for svc, container_port in port_map.items():
                    cname = _topo_container_name(topology_id, svc)
                    try:
                        c = docker_client.containers.get(cname)
                        try:
                            c.reload()
                        except Exception:
                            pass
                        hp = _get_host_port(c, container_port)
                        if isinstance(hp, int) and 1 <= hp <= 65535:
                            svc_obj = services.get(svc)
                            if not isinstance(svc_obj, dict):
                                svc_obj = {}
                                services[svc] = svc_obj
                                changed = True
                            if svc_obj.get("host_port") != hp:
                                svc_obj["host_port"] = hp
                                changed = True
                    except Exception:
                        continue

                # Keep network name aligned with the canonical topology network.
                net_name = _topo_network_name(topology_id)
                if payload.get("network") != net_name:
                    payload["network"] = net_name
                    changed = True

                if changed:
                    payload["updated_at"] = _iso_now()
                    _consul_set(f"caduceus/topologies/{topology_id}/isolated_infra", json.dumps(payload))
        except Exception:
            pass
    controllers_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
    controllers_payload = None
    if controllers_raw:
        try:
            controllers_payload = json.loads(controllers_raw)
        except Exception:
            controllers_payload = None
    containers: list[dict[str, Any]] = []
    if (TOPOLOGY_INFRA_MODE == "isolated" or isinstance(payload, dict)) and docker_client:
        for c in _list_topology_infra_containers(topology_id):
            try:
                c.reload()
            except Exception:
                pass
            containers.append(
                {
                    "name": getattr(c, "name", None),
                    "status": getattr(c, "status", None),
                    "image": getattr(getattr(c, "image", None), "tags", None),
                }
            )
        # Also include controller containers (if any) for UI visibility.
        for c in docker_client.containers.list(all=True):
            labels = getattr(c, "labels", {}) or {}
            if labels.get("caduceus.role") != "topology_controller":
                continue
            if labels.get("caduceus.topology_id") != topology_id:
                continue
            try:
                c.reload()
            except Exception:
                pass
            containers.append(
                {
                    "name": getattr(c, "name", None),
                    "status": getattr(c, "status", None),
                    "image": getattr(getattr(c, "image", None), "tags", None),
                }
            )
    effective_mode = "isolated" if isinstance(payload, dict) else TOPOLOGY_INFRA_MODE
    return {
        "topology_id": topology_id,
        "mode": effective_mode,
        "infra": payload,
        "controllers": controllers_payload,
        "containers": containers,
    }


@app.get("/api/infrastructure/topologies/{topology_id}/infra/status")
async def topology_infra_status_infra_endpoint(topology_id: str):
    return await topology_infra_status_endpoint(topology_id)


@app.get("/api/infrastructure/topologies/{topology_id}/infra/credentials")
async def topology_infra_credentials_endpoint(topology_id: str):
    """
    Return credentials/connection details for a topology's isolated infra stack.
    This is intended for UI display (Grafana login, Influx token, etc).
    """
    raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_infra")
    infra = None
    if raw:
        try:
            infra = json.loads(raw)
        except Exception:
            infra = None

    if TOPOLOGY_INFRA_MODE != "isolated" and not isinstance(infra, dict):
        influx_token = os.getenv("INFLUXDB_TOKEN")
        credentials: dict[str, Any] = {
            "grafana": {
                "user": os.getenv("GRAFANA_ADMIN_USER", "admin"),
                "password": os.getenv("GRAFANA_ADMIN_PASSWORD"),
                "host_port": None,
            },
            "influxdb": {
                "org": os.getenv("INFLUXDB_ORG"),
                "bucket": os.getenv("INFLUXDB_BUCKET", "metrics"),
                "token": influx_token,
                # In our docker-compose Influx init, password == admin token for simplicity.
                "user": os.getenv("INFLUXDB_INIT_USERNAME", "admin"),
                "password": influx_token,
                "host_port": None,
            },
            "rabbitmq": {
                "user": os.getenv("RABBITMQ_USER", "caduceus"),
                "password": os.getenv("RABBITMQ_PASSWORD"),
                "vhost": os.getenv("RABBITMQ_VHOST", "/caduceus-flux"),
                "host_port": None,
            },
        }

        credentials.update(_shared_ui_credentials())
        try:
            await _maybe_schedule_shared_ui_login_sync(credentials)
        except Exception:
            pass

        return {"topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE, "credentials": credentials}
    controllers_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
    controllers = None
    if controllers_raw:
        try:
            controllers = json.loads(controllers_raw)
        except Exception:
            controllers = None

    # Best-effort self-heal: if any credentials are missing, generate them and
    # force-reset service logins so UI-shown credentials work.
    must_sync = False
    for k in (
        f"caduceus/topologies/{topology_id}/isolated_grafana_admin_password",
        f"caduceus/topologies/{topology_id}/isolated_influx_token",
        f"caduceus/topologies/{topology_id}/isolated_rabbitmq_password",
        f"caduceus/topologies/{topology_id}/isolated_portainer_admin_password",
    ):
        if not _consul_get(k):
            must_sync = True
            break
    if must_sync:
        try:
            _ensure_topology_isolated_infra_secrets(topology_id, infra)
            sync_topology_isolated_infra_logins(topology_id)
        except Exception:
            pass

    credentials = {
        "grafana": {
            "user": _consul_get(f"caduceus/topologies/{topology_id}/isolated_grafana_admin_user"),
            "password": _consul_get(f"caduceus/topologies/{topology_id}/isolated_grafana_admin_password"),
            "host_port": (((infra or {}).get("services") or {}).get("grafana") or {}).get("host_port"),
        },
        "influxdb": {
            "org": _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_org"),
            "bucket": _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_bucket"),
            "token": _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_token"),
            "user": _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_admin_user"),
            "password": _consul_get(f"caduceus/topologies/{topology_id}/isolated_influx_admin_password"),
            "host_port": (((infra or {}).get("services") or {}).get("influxdb") or {}).get("host_port"),
        },
        "rabbitmq": {
            "user": _consul_get(f"caduceus/topologies/{topology_id}/isolated_rabbitmq_user"),
            "password": _consul_get(f"caduceus/topologies/{topology_id}/isolated_rabbitmq_password"),
            "vhost": _consul_get(f"caduceus/topologies/{topology_id}/isolated_rabbitmq_vhost"),
            "host_port": (((infra or {}).get("services") or {}).get("rabbitmq") or {}).get("host_port"),
        },
        "portainer": {
            "user": _consul_get(f"caduceus/topologies/{topology_id}/isolated_portainer_admin_user") or "admin",
            "password": _consul_get(f"caduceus/topologies/{topology_id}/isolated_portainer_admin_password"),
            "host_port": (((infra or {}).get("services") or {}).get("portainer") or {}).get("host_port"),
        },
        "portainer_view": {
            "user": _consul_get(f"caduceus/topologies/{topology_id}/isolated_portainer_view_user"),
            "password": _consul_get(f"caduceus/topologies/{topology_id}/isolated_portainer_view_password"),
            "host_port": (((infra or {}).get("services") or {}).get("portainer") or {}).get("host_port"),
        },
        "controllers": (controllers or {}).get("controllers") if isinstance(controllers, dict) else None,
    }

    credentials.update(_shared_ui_credentials())
    try:
        await _maybe_schedule_shared_ui_login_sync(credentials)
    except Exception:
        pass

    return {"topology_id": topology_id, "mode": "isolated", "credentials": credentials}


@app.post("/api/infrastructure/topologies/{topology_id}/infra/stop")
async def stop_topology_infra_endpoint(topology_id: str, request: Optional[TopologyInfraStopRequest] = None):
    if TOPOLOGY_INFRA_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE}
    preserve = True if request is None else bool(request.preserve_data)
    res = await asyncio.to_thread(stop_topology_isolated_infra, topology_id, preserve)
    try:
        await asyncio.to_thread(stop_topology_controllers, topology_id)
    except Exception as exc:
        logger.warning("Failed to stop topology controllers for %s: %s", topology_id, exc)
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "result": res}


@app.post("/api/infrastructure/topologies/{topology_id}/infra/purge")
async def purge_topology_infra_endpoint(topology_id: str, request: Optional[TopologyInfraPurgeRequest] = None):
    if TOPOLOGY_INFRA_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE}
    if request is None or not request.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true is required to purge infra data")
    res = await asyncio.to_thread(purge_topology_isolated_infra, topology_id)
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "result": res}


@app.post("/api/infrastructure/topologies/{topology_id}/infra/sync-logins")
async def sync_topology_infra_logins_endpoint(topology_id: str):
    """
    Force-reset/update service passwords so UI-shown credentials work (Grafana/InfluxDB/RabbitMQ).
    """
    if TOPOLOGY_INFRA_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE}
    res = await asyncio.to_thread(sync_topology_isolated_infra_logins, topology_id)
    return {"success": True, "topology_id": topology_id, "mode": "isolated", "result": res}


@app.post("/api/infrastructure/topologies/{topology_id}/infra/restart")
async def restart_topology_infra_services_endpoint(topology_id: str, request: Optional[TopologyInfraRestartRequest] = None):
    """
    Restart isolated infra services and/or controller containers for a topology.
    If no service/controller_id is provided, restarts the entire topology infra stack (containers only; volumes preserved).
    """
    if TOPOLOGY_INFRA_MODE != "isolated":
        return {"success": False, "topology_id": topology_id, "mode": TOPOLOGY_INFRA_MODE}
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    service = (request.service if request else None) or None
    controller_id = (request.controller_id if request else None) or None

    restarted: list[str] = []
    errors: dict[str, str] = {}

    def _restart_container(name: str) -> None:
        try:
            c = docker_client.containers.get(name)
            c.restart(timeout=10)
            restarted.append(name)
        except Exception as exc:
            errors[name] = str(exc)

    if service:
        _restart_container(_topo_container_name(topology_id, service))
    elif controller_id:
        raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
        payload = json.loads(raw) if raw else {}
        cinfo = ((payload or {}).get("controllers") or {}).get(controller_id) if isinstance(payload, dict) else None
        cname = cinfo.get("container_name") if isinstance(cinfo, dict) else None
        if cname:
            _restart_container(str(cname))
        else:
            errors[controller_id] = "Unknown controller_id"
    else:
        for c in _list_topology_infra_containers(topology_id):
            name = getattr(c, "name", None)
            if name:
                _restart_container(str(name))
        # Best-effort: restart controller containers too
        for c in docker_client.containers.list(all=True):
            labels = getattr(c, "labels", {}) or {}
            if labels.get("caduceus.role") == "topology_controller" and labels.get("caduceus.topology_id") == topology_id:
                name = getattr(c, "name", None)
                if name:
                    _restart_container(str(name))

    return {"success": True, "topology_id": topology_id, "mode": "isolated", "restarted": restarted, "errors": errors}


@app.post("/api/infrastructure/topologies/{topology_id}/controllers/{controller_id}/exec")
async def exec_topology_controller_endpoint(topology_id: str, controller_id: str, request: TopologyControllerExecRequest):
    """
    Execute a command inside a topology controller container (best-effort "terminal").
    """
    if TOPOLOGY_INFRA_MODE != "isolated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology infra mode is not isolated")
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

    cmd = (request.command or "").strip()
    if not cmd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="command is required")

    timeout_seconds = int(getattr(request, "timeout_seconds", 15) or 15)
    if timeout_seconds < 1:
        timeout_seconds = 1
    if timeout_seconds > 300:
        timeout_seconds = 300

    raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
    payload = json.loads(raw) if raw else {}
    cinfo = ((payload or {}).get("controllers") or {}).get(controller_id) if isinstance(payload, dict) else None
    cname = cinfo.get("container_name") if isinstance(cinfo, dict) else None
    if not cname:
        # Fallback: default naming convention.
        cname = _topo_container_name(topology_id, f"ctrl-{controller_id}")

    try:
        container = docker_client.containers.get(str(cname))
    except docker.errors.NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Controller container not found: {cname}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Best-effort timeout wrapper (depends on coreutils `timeout` in the controller image).
    wrapped = (
        f"if command -v timeout >/dev/null 2>&1; then "
        f"timeout {timeout_seconds}s sh -lc {shlex.quote(cmd)}; "
        f"else sh -lc {shlex.quote(cmd)}; fi"
    )
    try:
        res = container.exec_run(["sh", "-lc", wrapped], demux=True, privileged=True)
        exit_code = int(getattr(res, "exit_code", 0) or 0)
        out = getattr(res, "output", None)
        stdout_b = b""
        stderr_b = b""
        if isinstance(out, tuple) and len(out) == 2:
            stdout_b, stderr_b = out[0] or b"", out[1] or b""
        elif isinstance(out, (bytes, bytearray)):
            stdout_b = bytes(out)
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        return {
            "success": exit_code == 0,
            "topology_id": topology_id,
            "controller_id": controller_id,
            "container_name": str(cname),
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _resolve_topology_controller_container_name(topology_id: str, controller_id: str) -> str:
    raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
    payload = json.loads(raw) if raw else {}
    cinfo = ((payload or {}).get("controllers") or {}).get(controller_id) if isinstance(payload, dict) else None
    cname = cinfo.get("container_name") if isinstance(cinfo, dict) else None
    if cname:
        return str(cname)
    return _topo_container_name(topology_id, f"ctrl-{controller_id}")


@app.post("/api/infrastructure/topologies/{topology_id}/controllers/{controller_id}/stop")
async def stop_topology_controller_endpoint(
    topology_id: str, controller_id: str, request: Optional[TopologyControllerLifecycleRequest] = None
):
    if TOPOLOGY_INFRA_MODE != "isolated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology infra mode is not isolated")
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")
    timeout_seconds = int(getattr(request, "timeout_seconds", 10) or 10)
    if timeout_seconds < 1:
        timeout_seconds = 1
    if timeout_seconds > 120:
        timeout_seconds = 120

    cname = _resolve_topology_controller_container_name(topology_id, controller_id)
    try:
        container = docker_client.containers.get(cname)
    except docker.errors.NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Controller container not found: {cname}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    try:
        container.reload()
        was = getattr(container, "status", "unknown")
        if was == "running":
            container.stop(timeout=timeout_seconds)
        container.reload()
        return {
            "success": True,
            "topology_id": topology_id,
            "controller_id": controller_id,
            "container_name": cname,
            "previous_status": was,
            "status": getattr(container, "status", "unknown"),
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.post("/api/infrastructure/topologies/{topology_id}/controllers/{controller_id}/start")
async def start_topology_controller_endpoint(
    topology_id: str, controller_id: str, request: Optional[TopologyControllerLifecycleRequest] = None
):
    if TOPOLOGY_INFRA_MODE != "isolated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology infra mode is not isolated")
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")
    timeout_seconds = int(getattr(request, "timeout_seconds", 10) or 10)
    if timeout_seconds < 1:
        timeout_seconds = 1
    if timeout_seconds > 120:
        timeout_seconds = 120

    cname = _resolve_topology_controller_container_name(topology_id, controller_id)
    container = None
    try:
        container = docker_client.containers.get(cname)
    except docker.errors.NotFound:
        # Best-effort: create missing controller containers from topology definition.
        topology_data = await fetch_topology_definition(topology_id)
        await asyncio.to_thread(ensure_topology_controllers, topology_id, topology_data, False)
        cname = _resolve_topology_controller_container_name(topology_id, controller_id)
        try:
            container = docker_client.containers.get(cname)
        except docker.errors.NotFound:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Controller container not found: {cname}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    try:
        container.reload()
        was = getattr(container, "status", "unknown")
        if was != "running":
            container.start()
        # give it a moment
        time.sleep(min(2, timeout_seconds))
        container.reload()
        try:
            await _schedule_isolated_osm_reconcile(topology_id)
        except Exception:
            pass
        return {
            "success": True,
            "topology_id": topology_id,
            "controller_id": controller_id,
            "container_name": cname,
            "previous_status": was,
            "status": getattr(container, "status", "unknown"),
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.post("/api/infrastructure/topologies/{topology_id}/controllers/{controller_id}/restart")
async def restart_topology_controller_endpoint(
    topology_id: str, controller_id: str, request: Optional[TopologyControllerLifecycleRequest] = None
):
    if TOPOLOGY_INFRA_MODE != "isolated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology infra mode is not isolated")
    if not docker_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")
    timeout_seconds = int(getattr(request, "timeout_seconds", 10) or 10)
    if timeout_seconds < 1:
        timeout_seconds = 1
    if timeout_seconds > 120:
        timeout_seconds = 120

    cname = _resolve_topology_controller_container_name(topology_id, controller_id)
    try:
        container = docker_client.containers.get(cname)
    except docker.errors.NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Controller container not found: {cname}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    try:
        container.reload()
        was = getattr(container, "status", "unknown")
        container.restart(timeout=timeout_seconds)
        container.reload()
        try:
            await _schedule_isolated_osm_reconcile(topology_id)
        except Exception:
            pass
        return {
            "success": True,
            "topology_id": topology_id,
            "controller_id": controller_id,
            "container_name": cname,
            "previous_status": was,
            "status": getattr(container, "status", "unknown"),
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.post("/api/emulation/start", response_model=EmulationControlResponse)
async def start_emulation_endpoint(payload: EmulationStartRequest):
    """Start a new emulation for a given topology."""
    topology_id = payload.topology_id
    if not topology_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topology_id is required")

    options = payload.options or {}
    topology_data = await fetch_topology_definition(topology_id)

    start_lock = await _get_topology_start_lock(topology_id)

    topology_for_start_ready = False
    controllers_payload_cache: Optional[dict[str, Any]] = None

    async def _ensure_topology_for_start() -> None:
        nonlocal topology_data, topology_for_start_ready
        nonlocal controllers_payload_cache
        if topology_for_start_ready:
            return
        try:
            topology_data, node_updates = await asyncio.to_thread(_patch_localai_definition, topology_data)
            topology_data, port_updates = await asyncio.to_thread(_patch_dockerized_node_ports, topology_data)
            all_updates = (node_updates or []) + (port_updates or [])
            if all_updates:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for node_id, props in all_updates:
                        try:
                            await client.put(
                                f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}/nodes/{node_id}",
                                json={"properties": props},
                            )
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning("Topology %s LocalAI preflight failed: %s", topology_id, exc)
        try:
            # Controller containers can take minutes to boot (e.g. ONOS/ODL); do not block start.
            controllers_payload_cache = await asyncio.to_thread(
                ensure_topology_controllers, topology_id, topology_data, False
            )
            topology_data = _inject_controller_endpoints(topology_data, controllers_payload_cache)
        except Exception as exc:
            logger.warning("Topology %s controller ensure failed: %s", topology_id, exc)
        topology_for_start_ready = True

        # Best-effort: auto-register topology's emulation + SDN controllers into the shared OSM so the
        # user sees VIM/WIM accounts in ETSI-OSM UI without manual import steps.
        if str(os.getenv("OSM_AUTO_BOOTSTRAP_SHARED", "true") or "").strip().lower() in ("1", "true", "yes", "y", "on"):
            try:
                async def _bg_shared_osm_bootstrap() -> None:
                    await asyncio.to_thread(_bootstrap_osm_shared_emulation_vim, topology_id)
                    await asyncio.to_thread(_bootstrap_osm_shared_sdn_wims, topology_id, controllers_payload_cache)

                asyncio.create_task(_bg_shared_osm_bootstrap())
            except Exception:
                pass

        # Best-effort: if the user enabled isolated per-topology OSM for this topology,
        # keep it reconciled automatically (VIM/WIM/SDN bootstrap) without requiring manual Sync clicks.
        try:
            await _schedule_isolated_osm_reconcile(topology_id)
        except Exception:
            pass

    async def _start_via_client(client: "gRPCClient") -> Dict[str, Any]:
        async with start_lock:
            await _ensure_topology_for_start()
            return await asyncio.to_thread(client.start_emulation, topology_id, topology_data)

    async def _self_repair_start(reason: str) -> tuple[Dict[str, Any], str, str]:
        logger.warning("StartEmulation self-repair for topology %s (%s)", topology_id, reason)
        async with start_lock:
            await _ensure_topology_for_start()
            return await _force_recreate_and_start_emulation(topology_id, topology_data, options=options)

    result: Dict[str, Any] = {}
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    emulation_id: Optional[str] = None
    already_running = False

    def _message_from(res: Dict[str, Any]) -> str:
        return str((res or {}).get("message") or "")

    def _ok(res: Dict[str, Any]) -> bool:
        return bool((res or {}).get("success"))

    # 1) Reuse active record if possible
    existing = active_emulations.get(topology_id)
    if existing:
        container_name = existing.get("container_name") or f"caduceus-emu-{topology_id[:8]}"
        container_id = existing.get("container_id")
        emulation_id = existing.get("emulation_id")
        if str(existing.get("status") or "").lower() == "running" and emulation_id:
            # Validate the container still exists; otherwise the active record is stale.
            stale = False
            if docker_client and container_name:
                try:
                    cobj = docker_client.containers.get(container_name)
                    try:
                        cobj.reload()
                    except Exception:
                        pass
                    cstatus = str(getattr(cobj, "status", "") or "").lower()
                    if cstatus not in ("running", "restarting", "created"):
                        stale = True
                except docker.errors.NotFound:
                    stale = True
                except Exception as exc:
                    # If Docker is flaky, don't block start; treat as stale so we can self-repair.
                    logger.warning("Docker lookup failed for %s: %s", container_name, exc)
                    stale = True

            if stale:
                logger.warning(
                    "Stale active emulation record for topology %s: container %s not found; recreating",
                    topology_id,
                    container_name,
                )
                active_emulations.delete(topology_id)
                grpc_client_manager.remove_client(topology_id)
                # Best-effort cleanup: if a dead container exists, remove it so spawn is clean.
                if docker_client and container_name:
                    try:
                        docker_client.containers.get(container_name).remove(force=True)
                    except Exception:
                        pass
                existing = None
                container_id = None
                container_name = None
                emulation_id = None
            else:
                # Validate gRPC backend state as well; the container can be up while Mininet has stopped.
                try:
                    client = grpc_client_manager.get_client(topology_id)
                    if not client:
                        client = await asyncio.to_thread(grpc_client_manager.get_or_create, topology_id)
                    if client:
                        async with start_lock:
                            status_info = await asyncio.to_thread(client.get_status, emulation_id)
                        status_str = str(status_info.get("status") or "").lower()
                        device_count = int(status_info.get("device_count") or 0)
                        if status_str == "running" and device_count > 0:
                            already_running = True
                            result = {"success": True, "message": "Emulation already running", "emulation_id": emulation_id}
                        else:
                            existing["status"] = "stopped"
                            existing["last_updated"] = _iso_now()
                            active_emulations.set(topology_id, existing)
                except Exception:
                    pass

        if not already_running:
            try:
                client = grpc_client_manager.get_client(topology_id)
                if not client:
                    client = await asyncio.to_thread(grpc_client_manager.get_or_create, topology_id)
                if client:
                    # Fast-path: if the emulation is already running, don't call StartEmulation again (it can hang).
                    if emulation_id:
                        try:
                            async with start_lock:
                                status_info = await asyncio.to_thread(client.get_status, emulation_id)
                            if str(status_info.get("status") or "").lower() == "running" and int(status_info.get("device_count") or 0) > 0:
                                already_running = True
                                result = {"success": True, "message": "Emulation already running", "emulation_id": emulation_id}
                        except Exception:
                            pass
                    if not already_running:
                        result = await _start_via_client(client)
            except Exception as exc:
                logger.warning("StartEmulation in existing record container failed for %s: %s", topology_id, exc)
                result = {"success": False, "message": str(exc)}

        msg = _message_from(result)
        if _ok(result):
            emulation_id = result.get("emulation_id") or emulation_id
        elif "already" in msg.lower():
            already_running = True
        elif msg and _is_transient_start_error(msg):
            result, container_id, container_name = await _self_repair_start(msg)
            emulation_id = result.get("emulation_id") or emulation_id
        else:
            # If record is stale, drop it and continue to other paths.
            active_emulations.delete(topology_id)
            existing = None

    # 2) No record (or stale): try inferred container
    if not existing and not _ok(result) and not already_running:
        inferred_container_name = f"caduceus-emu-{topology_id[:8]}"
        if docker_client:
            try:
                cobj = docker_client.containers.get(inferred_container_name)
                cobj.reload()
                if getattr(cobj, "status", "") in ("running", "created", "restarting"):
                    container_name = inferred_container_name
                    container_id = getattr(cobj, "id", None)
                    state = _read_emulation_state_from_container(inferred_container_name)
                    if (
                        state
                        and str(state.get("topology_id") or "") == topology_id
                        and str(state.get("status") or "").lower() == "running"
                        and state.get("emulation_id")
                    ):
                        already_running = True
                        emulation_id = str(state.get("emulation_id"))
                        result = {"success": True, "message": "Emulation already running", "emulation_id": emulation_id}
                    else:
                        client = await asyncio.to_thread(grpc_client_manager.get_or_create, topology_id)
                        if not client:
                            client = await asyncio.to_thread(
                                grpc_client_manager.create_client,
                                topology_id,
                                inferred_container_name,
                                int(EMULATION_GRPC_PORT),
                            )
                        result = await _start_via_client(client)
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                result = {"success": False, "message": f"Existing emulation container present but gRPC is not reachable: {exc}"}

        msg = _message_from(result)
        if _ok(result):
            emulation_id = result.get("emulation_id") or emulation_id
        elif "already" in msg.lower():
            already_running = True
        elif msg and _is_transient_start_error(msg):
            result, container_id, container_name = await _self_repair_start(msg)
            emulation_id = result.get("emulation_id") or emulation_id

    # 3) Spawn or reuse emulation container and start
    if not _ok(result) and not already_running:
        if not docker_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Docker client not available")

        try:
            async with start_lock:
                await _ensure_topology_for_start()
                container_name, container_port, container_id = await asyncio.to_thread(
                    spawn_emulation_container,
                    topology_id,
                )
                emulation_client = await asyncio.to_thread(
                    grpc_client_manager.create_client,
                    topology_id,
                    container_name,
                    container_port,
                )
                result = await asyncio.to_thread(emulation_client.start_emulation, topology_id, topology_data)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to spawn/start emulation container: {exc}",
            ) from exc

        msg = _message_from(result)
        if not _ok(result) and msg and _is_transient_start_error(msg):
            result, container_id, container_name = await _self_repair_start(msg)
            msg = _message_from(result)

        if not _ok(result):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg or "Failed to start emulation")

        emulation_id = result.get("emulation_id") or emulation_id

    # Finalize emulation_id and record
    if not emulation_id:
        emulation_id = f"emu-{topology_id}-{int(time.time())}"
        logger.warning("StartEmulation returned no emulation_id; generated %s", emulation_id)

    record = record_active_emulation(
        topology_id=topology_id,
        emulation_id=emulation_id,
        topology_data=topology_data,
        options=options,
        status_value="running",
        container_id=container_id,
        container_name=container_name,
    )

    # Return fast for "already running" (avoid long infra/consul calls that can hang the UI).
    if already_running:
        async def _warmup_running_controllers() -> None:
            """
            Best-effort controller warm-up for an already-running topology.

            This handles cases where the orchestrator restarts while emulations are still
            running, or when controller containers have restarted and need ONOS/ODL app
            activation again so switches can reconnect.
            """
            try:
                await _ensure_topology_for_start()
                await asyncio.to_thread(ensure_topology_controllers, topology_id, topology_data, True)
            except Exception:
                return

        async def _sync_running_controllers() -> None:
            try:
                await _ensure_topology_for_start()
                payload = controllers_payload_cache or {}
                controllers = payload.get("controllers") if isinstance(payload, dict) else None
                if not isinstance(controllers, dict):
                    return
                usable = [
                    c for c in controllers.values()
                    if isinstance(c, dict) and c.get("ok") and c.get("container_name") and c.get("openflow_port")
                ]
                if not usable:
                    return

                try:
                    grpc = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=None)
                except Exception:
                    return

                nodes = topology_data.get("nodes", topology_data.get("devices", [])) or []
                if not isinstance(nodes, list):
                    return

                for n in nodes:
                    if not isinstance(n, dict):
                        continue
                    dt = str(n.get("device_type") or n.get("type") or "").strip().lower()
                    if dt not in ("switch", "ovsswitch", "ovs", "bridge"):
                        continue
                    sw_name = str(n.get("name") or "").strip()
                    if not sw_name:
                        continue
                    props = n.get("properties")
                    props = props if isinstance(props, dict) else {}
                    endpoint = props.get("controller")
                    if not endpoint:
                        continue
                    try:
                        endpoint = str(endpoint).strip()
                        host, port_s = endpoint.rsplit(":", 1)
                        port = int(port_s)
                    except Exception:
                        continue
                    cmd = f"ovs-vsctl set-controller {sw_name} tcp:{host}:{int(port)}"
                    await asyncio.to_thread(grpc.execute_command, sw_name, cmd)
            except Exception:
                return

        asyncio.create_task(_sync_running_controllers())
        asyncio.create_task(_warmup_running_controllers())
        return EmulationControlResponse(
            success=True,
            message="Emulation already running",
            emulation_id=emulation_id,
        )

    async def _post_start_setup() -> None:
        # Best-effort post-start steps; do not block the HTTP response path.
        # Warm up controller containers (best-effort); ONOS/ODL can take minutes.
        try:
            if controllers_payload_cache and isinstance(controllers_payload_cache.get("controllers"), dict):
                await asyncio.to_thread(ensure_topology_controllers, topology_id, topology_data, True)
        except Exception as exc:
            logger.warning("Topology %s controller warm-up failed: %s", topology_id, exc)

        try:
            infra_ensure = await asyncio.to_thread(ensure_infrastructure_running)
            if isinstance(infra_ensure, dict) and infra_ensure.get("started"):
                logger.info("Started infrastructure services: %s", ", ".join(infra_ensure["started"]))
        except Exception as exc:
            logger.warning("Failed to ensure infrastructure is running: %s", exc)

        try:
            await asyncio.wait_for(
                asyncio.to_thread(sync_topology_infrastructure_to_consul, topology_id),
                timeout=10.0,
            )
        except Exception as exc:
            logger.warning("Failed to sync topology %s infrastructure to Consul: %s", topology_id, exc)

        if TOPOLOGY_INFRA_MODE == "isolated":
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(ensure_topology_isolated_infra, topology_id),
                    timeout=30.0,
                )
            except Exception as exc:
                logger.warning("Topology %s isolated infra ensure failed: %s", topology_id, exc)
        else:
            try:
                await asyncio.wait_for(ensure_topology_observability(topology_id), timeout=30.0)
            except Exception as exc:
                logger.warning("Topology %s observability ensure failed: %s", topology_id, exc)

    asyncio.create_task(_post_start_setup())

    def _as_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

    auto_apply_cfg = options.get("auto_apply_network_config")
    if auto_apply_cfg is None:
        auto_apply_cfg = os.getenv("AUTO_APPLY_NETWORK_CONFIG", "false")

    if _as_bool(auto_apply_cfg, default=False):
        try:
            cfg_url = f"{TOPOLOGY_SERVICE_URL}/api/network-configs/{topology_id}/export"
            async with httpx.AsyncClient(timeout=15.0) as client:
                cfg_res = await client.get(cfg_url)
            if cfg_res.status_code == 200:
                cfg_doc = cfg_res.json()
                async def _apply_with_retry(doc: dict[str, Any], label: str) -> None:
                    # StartEmulation can return before all nodes/interfaces are stable; retry until
                    # we get actionable results back from the apply handler.
                    last_summary: Optional[str] = None
                    for attempt in range(1, 7):
                        try:
                            resp = await apply_network_config(
                                NetworkConfigApplyRequestBody(
                                    topology_id=topology_id,
                                    emulation_id=emulation_id,
                                    config=doc,
                                    dry_run=False,
                                )
                            )
                            results = getattr(resp, "results", None)
                            ok = bool(getattr(resp, "success", False))
                            count = len(results or []) if isinstance(results, list) else 0
                            last_summary = f"success={ok} results={count}"
                            if ok and count > 0:
                                logger.info("%s latest network config for topology %s (%s)", label, topology_id, last_summary)
                                return
                        except Exception as exc:
                            last_summary = str(exc)
                        await asyncio.sleep(2)
                    logger.warning("%s network config for topology %s failed (%s)", label, topology_id, last_summary or "unknown error")

                await _apply_with_retry(cfg_doc, "Auto-applied")

                # Re-apply once more later to guard against late init overriding settings.
                async def _delayed_reapply() -> None:
                    try:
                        await asyncio.sleep(8)
                        async with httpx.AsyncClient(timeout=15.0) as delayed_client:
                            delayed_res = await delayed_client.get(cfg_url)
                        if delayed_res.status_code != 200:
                            return
                        await _apply_with_retry(delayed_res.json(), "Auto-reapplied")
                    except Exception as exc:
                        logger.warning("Auto-reapply network config failed for topology %s: %s", topology_id, exc)

                asyncio.create_task(_delayed_reapply())
            elif cfg_res.status_code != 404:
                logger.warning(
                    "Auto-apply network config skipped (HTTP %s) for topology %s",
                    cfg_res.status_code,
                    topology_id,
                )
        except Exception as exc:
            logger.warning("Auto-apply network config failed for topology %s: %s", topology_id, exc)

    # Publish event for other services
    try:
        rabbitmq_publisher.publish("emulation.started", {
            'topology_id': topology_id,
            'emulation_id': emulation_id,
            'options': record.get('options', {}),
            'node_count': record.get('node_count'),
            'link_count': record.get('link_count'),
            'started_at': record.get('started_at')
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.started event: %s", exc)

    logger.info(
        "Emulation %s started for topology %s",
        emulation_id,
        topology_id
    )

    return EmulationControlResponse(
        success=True,
        message=result.get('message', 'Emulation started successfully'),
        emulation_id=emulation_id
    )


def _resolve_emulation_id_for_topology(topology_id: str) -> Optional[str]:
    """Best-effort: resolve emulation_id for a topology_id (active store first, then container state)."""
    if not topology_id:
        return None
    info = active_emulations.get(topology_id) or {}
    emu_id = info.get("emulation_id")
    if isinstance(emu_id, str) and emu_id.strip():
        return emu_id.strip()
    if emu_id is not None:
        try:
            return str(emu_id)
        except Exception:
            pass

    inferred_container_name = f"caduceus-emu-{topology_id[:8]}"
    state = _read_emulation_state_from_container(inferred_container_name)
    if state and str(state.get("topology_id") or "") == topology_id and state.get("emulation_id"):
        try:
            return str(state.get("emulation_id")).strip() or None
        except Exception:
            return None
    return None


@app.post("/api/orchestrator/emulations/{topology_id}/start", response_model=EmulationControlResponse)
async def ui_start_emulation(topology_id: str, payload: Optional[OrchestratorStartOptions] = Body(default=None)):
    """
    UI-compatible endpoint: start an emulation by topology_id.

    Frontend calls: POST /api/orchestrator/emulations/{topology_id}/start
    """
    options = payload.options if payload is not None else {}
    return await start_emulation_endpoint(EmulationStartRequest(topology_id=topology_id, options=options or {}))


@app.post("/api/orchestrator/emulations/{topology_id}/stop", response_model=EmulationControlResponse)
async def ui_stop_emulation(
    topology_id: str, request: EmulationStopRequest = Body(default=EmulationStopRequest())
):
    """
    UI-compatible endpoint: stop an emulation by topology_id (resolves the current emulation_id automatically).

    Frontend calls: POST /api/orchestrator/emulations/{topology_id}/stop
    """
    emulation_id = _resolve_emulation_id_for_topology(topology_id)
    if not emulation_id:
        # Treat as idempotent: stopping an already-stopped emulation should succeed.
        try:
            active_emulations.delete(topology_id)
            grpc_client_manager.remove_client(topology_id)
        except Exception:
            pass
        return EmulationControlResponse(success=True, message="Emulation already stopped", emulation_id=None)
    return await stop_emulation_endpoint(emulation_id, request)


@app.post("/api/orchestrator/emulations/{topology_id}/pause", response_model=EmulationControlResponse)
async def ui_pause_emulation(topology_id: str):
    """UI-compatible endpoint: pause an emulation by topology_id."""
    emulation_id = _resolve_emulation_id_for_topology(topology_id)
    if not emulation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Topology {topology_id} has no active emulation")
    return await pause_emulation_endpoint(emulation_id)


@app.post("/api/orchestrator/emulations/{topology_id}/resume", response_model=EmulationControlResponse)
async def ui_resume_emulation(topology_id: str):
    """UI-compatible endpoint: resume an emulation by topology_id."""
    emulation_id = _resolve_emulation_id_for_topology(topology_id)
    if not emulation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Topology {topology_id} has no active emulation")
    return await resume_emulation_endpoint(emulation_id)


@app.get("/api/orchestrator/emulations/{topology_id}/status", response_model=EmulationStatusResponse)
async def ui_emulation_status(topology_id: str):
    """UI-compatible endpoint: fetch emulation status by topology_id."""
    emulation_id = _resolve_emulation_id_for_topology(topology_id)
    if not emulation_id:
        return EmulationStatusResponse(
            status="stopped",
            uptime_seconds=0,
            device_count=0,
            link_count=0,
            metadata={"topology_id": topology_id, "detail": "No active emulation"},
        )
    if stop_task_manager.is_running(emulation_id):
        return EmulationStatusResponse(
            status="stopping",
            uptime_seconds=0,
            device_count=0,
            link_count=0,
            metadata={"topology_id": topology_id, "emulation_id": emulation_id},
        )
    try:
        return await get_emulation_status(emulation_id)
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_503_SERVICE_UNAVAILABLE):
            # UI expects a stable "stopped" response instead of an exception while emulation is down/stale.
            try:
                active_emulations.delete(topology_id)
                grpc_client_manager.remove_client(topology_id)
            except Exception:
                pass
            return EmulationStatusResponse(
                status="stopped",
                uptime_seconds=0,
                device_count=0,
                link_count=0,
                metadata={"topology_id": topology_id, "detail": str(exc.detail)},
            )
        raise


@app.post("/api/topologies/{topology_id}/apply", response_model=ApplyChangesResponse)
async def apply_topology_changes_endpoint(
    topology_id: str,
    payload: TopologyApplyRequest
):
    """Apply staged topology changes: emulate first, then persist."""
    grpc_client_instance = require_grpc_client(topology_id=topology_id)
    change_set = payload.changes or TopologyChangeSet()

    if change_set.is_empty():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No changes provided"
        )

    active = active_emulations.get(topology_id)
    if not active or not active.get('emulation_id'):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Topology {topology_id} is not running; start emulation before applying changes"
        )

    if active.get('status') not in ('running', 'paused'):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Emulation must be running or paused to apply changes (current state: {active.get('status')})"
        )

    topology_snapshot = await fetch_topology_definition(topology_id)
    devices_snapshot = copy.deepcopy(
        topology_snapshot.get('nodes', topology_snapshot.get('devices', [])) or []
    )
    links_snapshot = copy.deepcopy(topology_snapshot.get('links', []))

    devices_by_id: Dict[str, Dict[str, Any]] = {}
    devices_by_name: Dict[str, Dict[str, Any]] = {}
    links_by_id: Dict[str, Dict[str, Any]] = {}

    for device in devices_snapshot:
        device_id = (
            device.get('id')
            or device.get('node_id')
            or device.get('properties', {}).get('node_id')
        )
        if not device_id:
            device_id = device.get('name') or str(uuid.uuid4())
            device['id'] = device_id
        if 'id' not in device:
            device['id'] = device_id
        device.setdefault('properties', {})
        device_type = device.get('type') or device.get('device_type')
        if not device_type:
            device_type = device['properties'].get('device_type', '')
            device['type'] = device_type
        device['device_type'] = device_type
        devices_by_id[str(device_id)] = device
        if device.get('name'):
            devices_by_name[device['name']] = device

    for link in links_snapshot:
        link_id = link.get('id') or str(uuid.uuid4())
        link['id'] = link_id
        links_by_id[str(link_id)] = link

    results = {
        'devices_added': 0,
        'devices_removed': 0,
        'devices_updated': 0,
        'links_added': 0,
        'links_removed': 0,
        'links_updated': 0
    }
    rollback_stack: List[Tuple[str, Dict[str, Any]]] = []

    async def rollback_operations():
        for action, data in reversed(rollback_stack):
            try:
                if action == 'device_added':
                    await remove_device_from_emulation(
                        topology_id,
                        data.get('name'),
                        data.get('id'),
                        client=grpc_client_instance
                    )
                elif action == 'device_removed':
                    await add_device_to_emulation(topology_id, data, client=grpc_client_instance)
                elif action == 'device_updated':
                    await sync_device_to_emulation(topology_id, data, client=grpc_client_instance)
                elif action == 'link_added':
                    await remove_link_from_emulation(topology_id, data, client=grpc_client_instance)
                elif action == 'link_removed':
                    await add_link_to_emulation(topology_id, data, client=grpc_client_instance)
                elif action == 'link_updated':
                    await sync_link_to_emulation(topology_id, data, client=grpc_client_instance)
            except Exception as exc:  # Best effort rollback
                logger.error("Rollback action %s failed: %s", action, exc)

    def resolve_device(ref: NodeIdentifier) -> Optional[Dict[str, Any]]:
        if ref.id and ref.id in devices_by_id:
            return devices_by_id[ref.id]
        if ref.name and ref.name in devices_by_name:
            return devices_by_name[ref.name]
        return None

    def resolve_link(ref: LinkIdentifier) -> Optional[Dict[str, Any]]:
        if ref.id and ref.id in links_by_id:
            return links_by_id[ref.id]
        if ref.source_node_id and ref.target_node_id:
            for link in links_by_id.values():
                if (
                    link.get('source_node_id') == ref.source_node_id
                    and link.get('target_node_id') == ref.target_node_id
                ):
                    return link
        return None

    # --- Apply staged changes to running emulation ---
    try:
        # Remove links first
        for link_ref in change_set.remove_links:
            link_data = resolve_link(link_ref)
            if not link_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unable to resolve link removal target: {link_ref}"
                )
            if not await remove_link_from_emulation(topology_id, link_data, client=grpc_client_instance):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to remove link {link_data.get('id')}"
                )
            rollback_stack.append(('link_removed', copy.deepcopy(link_data)))
            results['links_removed'] += 1
            links_by_id.pop(link_data['id'], None)

        # Remove devices
        for device_ref in change_set.remove_devices:
            device_data = resolve_device(device_ref)
            if not device_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unable to resolve device removal target: {device_ref}"
                )
            if not await remove_device_from_emulation(
                topology_id,
                device_data.get('name'),
                device_data.get('id'),
                client=grpc_client_instance
            ):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to remove device {device_data.get('id')}"
                )
            rollback_stack.append(('device_removed', copy.deepcopy(device_data)))
            results['devices_removed'] += 1
            devices_by_id.pop(device_data['id'], None)
            if device_data.get('name'):
                devices_by_name.pop(device_data['name'], None)

        # Add devices
        for node_delta in change_set.add_devices:
            device_id = node_delta.id or str(uuid.uuid4())
            if node_delta.id is None:
                node_delta.id = device_id

            device_type = (
                node_delta.device_type.value
                if hasattr(node_delta.device_type, "value")
                else node_delta.device_type
            )

            device_properties = dict(node_delta.properties or {})
            device_properties.setdefault('node_id', device_id)
            device_properties.setdefault('display_name', node_delta.name)
            node_delta.properties = device_properties

            device_payload = {
                'id': device_id,
                'name': node_delta.name,
                'type': device_type,
                'device_type': device_type,
                'properties': device_properties,
                'x': node_delta.x,
                'y': node_delta.y
            }

            if not await add_device_to_emulation(topology_id, device_payload, client=grpc_client_instance):
                await rollback_operations()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to add device {node_delta.name}"
                )

            rollback_stack.append(('device_added', copy.deepcopy(device_payload)))
            results['devices_added'] += 1
            devices_by_id[device_id] = device_payload
            if node_delta.name:
                devices_by_name[node_delta.name] = device_payload

        # Update devices
        for update in change_set.update_devices:
            existing = devices_by_id.get(update.id)
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Device not found for update: {update.id}"
                )
            before_state = copy.deepcopy(existing)
            updated = copy.deepcopy(existing)

            if update.name is not None:
                if existing.get('name') and existing['name'] in devices_by_name:
                    devices_by_name.pop(existing['name'], None)
                updated['name'] = update.name
                devices_by_name[update.name] = updated
                updated.setdefault('properties', {})['display_name'] = update.name
            if update.x is not None:
                updated['x'] = update.x
            if update.y is not None:
                updated['y'] = update.y
            if update.properties is not None:
                updated['properties'] = dict(update.properties)
                updated['properties'].setdefault('node_id', update.id)

            if not await sync_device_to_emulation(topology_id, updated, client=grpc_client_instance):
                await rollback_operations()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update device {update.id}"
                )

            rollback_stack.append(('device_updated', before_state))
            results['devices_updated'] += 1
            devices_by_id[update.id] = updated

        # Add links
        for link_delta in change_set.add_links:
            link_id = link_delta.id or str(uuid.uuid4())
            if link_delta.id is None:
                link_delta.id = link_id

            link_payload = {
                'id': link_id,
                'source_node_id': link_delta.source_node_id,
                'target_node_id': link_delta.target_node_id,
                'node1': link_delta.source_node_id,
                'node2': link_delta.target_node_id,
                'port1': link_delta.source_port,
                'port2': link_delta.target_port,
                'source_port': link_delta.source_port,
                'target_port': link_delta.target_port,
                'bandwidth': link_delta.bandwidth,
                'delay': link_delta.delay,
                'loss': link_delta.loss,
                'max_queue_size': link_delta.max_queue_size,
                'properties': dict(link_delta.properties or {})
            }

            if not await add_link_to_emulation(topology_id, link_payload, client=grpc_client_instance):
                await rollback_operations()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to add link between {link_delta.source_node_id} and {link_delta.target_node_id}"
                )

            rollback_stack.append(('link_added', copy.deepcopy(link_payload)))
            results['links_added'] += 1
            links_by_id[link_id] = link_payload

        # Update links
        for update in change_set.update_links:
            link = links_by_id.get(update.id) or resolve_link(LinkIdentifier(id=update.id))
            if not link:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Link not found for update: {update.id}"
                )
            before_state = copy.deepcopy(link)
            updated_link = copy.deepcopy(link)

            if update.source_node_id:
                updated_link['source_node_id'] = update.source_node_id
                updated_link['node1'] = update.source_node_id
            if update.target_node_id:
                updated_link['target_node_id'] = update.target_node_id
                updated_link['node2'] = update.target_node_id
            if update.bandwidth is not None:
                updated_link['bandwidth'] = update.bandwidth
            if update.delay is not None:
                updated_link['delay'] = update.delay
            if update.loss is not None:
                updated_link['loss'] = update.loss
            if update.max_queue_size is not None:
                updated_link['max_queue_size'] = update.max_queue_size
            if update.properties is not None:
                updated_link['properties'] = dict(update.properties)

            if not await sync_link_to_emulation(topology_id, updated_link):
                await rollback_operations()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update link {update.id}"
                )

            rollback_stack.append(('link_updated', before_state))
            results['links_updated'] += 1
            links_by_id[updated_link['id']] = updated_link

    except HTTPException:
        await rollback_operations()
        raise
    except Exception as exc:
        await rollback_operations()
        logger.exception("Failed to apply changes to emulation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply changes to running emulation"
        ) from exc

    # --- Persist changes to topology service ---
    try:
        payload_dict = payload.model_dump()
        async with httpx.AsyncClient(timeout=TOPOLOGY_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}/apply",
                json=payload_dict
            )
    except httpx.RequestError as exc:
        await rollback_operations()
        logger.error("Failed to reach topology service for apply: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to contact topology service"
        ) from exc

    if response.status_code >= 400:
        await rollback_operations()
        detail = response.text
        try:
            detail_json = response.json()
            detail = detail_json.get('detail', detail_json)
        except Exception:
            pass
        raise HTTPException(
            status_code=response.status_code,
            detail=detail
        )

    # Update metadata for active emulation
    update_active_emulation(
        active.get('emulation_id'),
        last_synced=_iso_now(),
        status=active.get('status', 'running')
    )

    try:
        rabbitmq_publisher.publish("emulation.apply.completed", {
            'topology_id': topology_id,
            'emulation_id': active.get('emulation_id'),
            'results': results,
            'timestamp': _iso_now()
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.apply.completed event: %s", exc)

    sync_topology_infrastructure_to_consul(topology_id)

    message = f"Applied staged changes to topology {topology_id}"
    return ApplyChangesResponse(
        success=True,
        message=message,
        applied=results,
        rollback_performed=False
    )


@app.post("/api/emulation/stop/{emulation_id}", response_model=EmulationControlResponse)
async def stop_emulation_endpoint(
    emulation_id: str,
    request: EmulationStopRequest = Body(default=EmulationStopRequest()),
):
    """
    Stop an emulation and optionally clean up resources.

    Stopping can take a while (Mininet cleanup + docker removes). To avoid frontend "Network error"
    caused by request cancellation/timeouts, we run the stop in a background task and return quickly.
    """
    task = await stop_task_manager.get_or_create(
        emulation_id,
        lambda: _stop_emulation_impl(emulation_id, request),
        task_name=f"stop-emulation:{emulation_id[:24]}",
    )
    try:
        # If it finishes quickly, return the real result.
        return await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
    except asyncio.TimeoutError:
        return EmulationControlResponse(success=True, message="Stop scheduled", emulation_id=emulation_id)


async def _stop_emulation_impl(emulation_id: str, request: EmulationStopRequest) -> EmulationControlResponse:
    """Internal stop implementation (runs in background task)."""
    topology_id = active_emulations.find_by_emulation_id(emulation_id)
    if not topology_id:
        # Best-effort recovery for orchestrator restarts: emulation_id is typically "emu-<topology_uuid>-<ts>".
        m = re.match(r"^emu-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", emulation_id or "")
        if m:
            topology_id = m.group(1)

    cleanup = request.cleanup if request is not None else True
    stop_infra = True if request is None else bool(getattr(request, "stop_infra", True))
    preserve = True if request is None else bool(getattr(request, "preserve_infra_data", True))

    # Capture container name before we potentially delete the active record.
    emu_container_name: Optional[str] = None
    if topology_id:
        info = active_emulations.get(topology_id) or {}
        emu_container_name = info.get("container_name") or info.get("container")
    if not emu_container_name and topology_id:
        emu_container_name = f"caduceus-emu-{topology_id[:8]}"

    async def _cleanup_containernet_nodes(tid: str) -> None:
        """
        Best-effort cleanup of dockerized Mininet nodes (mn.<runtime> containers) that Containernet spawns.
        Without this, a crashed emulation container can leave stale mn.* containers behind.
        """
        if not docker_client or not tid:
            return
        try:
            topo = await fetch_topology_definition(tid)
        except Exception:
            return
        nodes = topo.get("nodes", topo.get("devices", [])) or []
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            props = node.get("properties")
            props = props if isinstance(props, dict) else {}
            dockerized = props.get("dockerized", False)
            if isinstance(dockerized, str):
                dockerized = dockerized.strip().lower() in ("1", "true", "yes", "y", "on")
            if not dockerized:
                continue
            node_id = node.get("id") or node.get("node_id")
            display_name = node.get("name") or node.get("display_name")
            runtime = _runtime_device_name(str(node_id) if node_id else None, str(display_name) if display_name else None)
            cname = f"mn.{runtime}"
            try:
                c = docker_client.containers.get(cname)
                try:
                    c.stop(timeout=5)
                except Exception:
                    pass
                c.remove(force=True)
            except docker.errors.NotFound:
                continue
            except Exception:
                continue

    async def _best_effort_cleanup(reason: str) -> EmulationControlResponse:
        tid = remove_active_emulation_by_id(emulation_id) or topology_id
        if tid:
            grpc_client_manager.remove_client(tid)
        if cleanup and docker_client and tid:
            cname = emu_container_name or f"caduceus-emu-{tid[:8]}"
            try:
                container = docker_client.containers.get(cname)
                try:
                    container.stop(timeout=10)
                except Exception:
                    pass
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
            except Exception as d_exc:
                logger.warning("Best-effort docker cleanup failed for %s: %s", cname, d_exc)

            await _cleanup_containernet_nodes(tid)

        if tid and stop_infra and TOPOLOGY_INFRA_MODE == "isolated":
            await _stop_topology_sidecars(tid)

        return EmulationControlResponse(
            success=True,
            message=f"{reason}; cleaned up containers best-effort.",
            emulation_id=emulation_id,
        )

    async def _stop_topology_sidecars(tid: str) -> None:
        if not tid:
            return
        # Stop topology-scoped controllers + infra containers (best-effort).
        try:
            await asyncio.wait_for(asyncio.to_thread(stop_topology_controllers, tid), timeout=20.0)
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                asyncio.to_thread(stop_topology_isolated_infra, tid, preserve_data=preserve),
                timeout=30.0,
            )
        except Exception:
            pass

    try:
        grpc = await asyncio.to_thread(
            require_grpc_client,
            topology_id=topology_id,
            emulation_id=None if topology_id else emulation_id,
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(grpc.stop_emulation, emulation_id, cleanup=cleanup),
            timeout=45.0,
        )
    except HTTPException as exc:
        # If the backend is unavailable but the caller asked to clean up, still remove the
        # active record and container (best-effort) so the user can start again.
        if cleanup and exc.status_code in (status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_404_NOT_FOUND):
            # Treat "not running" as a cleanup request: the user wants it gone, and the container
            # might still exist even if our in-memory record is missing (e.g., orchestrator restart).
            detail = None
            try:
                detail = str(getattr(exc, "detail", "") or "")
            except Exception:
                detail = None
            reason = detail.strip() or "Emulation backend unavailable"
            return await _best_effort_cleanup(reason)
        raise
    except asyncio.TimeoutError:
        if cleanup:
            return await _best_effort_cleanup("Stop timed out")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timed out stopping emulation")
    except Exception as exc:
        if cleanup:
            return await _best_effort_cleanup(f"Stop failed ({exc})")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not result.get('success'):
        message = result.get('message', 'Failed to stop emulation')
        # If the gRPC backend reports failure but the caller requested cleanup,
        # still perform best-effort cleanup so users aren't stuck with orphaned containers.
        if cleanup:
            return await _best_effort_cleanup(f"Backend reported stop failure ({message})")

        logger.error("Failed to stop emulation %s: %s", emulation_id, message)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    topology_id = remove_active_emulation_by_id(emulation_id) or topology_id
    logger.info(f"DEBUG: After remove_active_emulation_by_id, topology_id={topology_id}")

    # Clean up gRPC client and Docker container for this emulation
    if topology_id:
        grpc_client_manager.remove_client(topology_id)
        logger.info(f"DEBUG: topology_id={topology_id}, cleanup={cleanup}, docker_client={docker_client}")

        # Stop and remove the Docker container if cleanup is requested
        if cleanup and docker_client:
            try:
                # Get the container name from topology_id
                container_name = f"caduceus-emu-{topology_id[:8]}"
                try:
                    container = docker_client.containers.get(container_name)
                    logger.info(f"Stopping Docker container {container_name}")
                    container.stop(timeout=10)
                    logger.info(f"Removing Docker container {container_name}")
                    container.remove(force=True)
                    logger.info(f"✅ Docker container {container_name} cleaned up successfully")
                except docker.errors.NotFound:
                    logger.warning(f"Container {container_name} not found during cleanup, may already be removed")
                except Exception as e:
                    logger.error(f"Failed to cleanup Docker container {container_name}: {e}")
            except Exception as e:
                logger.error(f"Error during container cleanup: {e}")

        try:
            rabbitmq_publisher.publish("emulation.stopped", {
                'topology_id': topology_id,
                'emulation_id': emulation_id,
                'cleanup': cleanup,
                'timestamp': _iso_now()
            })
        except Exception as exc:
            logger.error("Failed to publish emulation.stopped event: %s", exc)

        # Keep Consul sync best-effort and bounded.
        try:
            await asyncio.wait_for(
                asyncio.to_thread(sync_topology_infrastructure_to_consul, topology_id),
                timeout=8.0,
            )
        except Exception:
            pass

        if stop_infra and TOPOLOGY_INFRA_MODE == "isolated":
            await _stop_topology_sidecars(topology_id)

    return EmulationControlResponse(
        success=True,
        message=result.get('message', 'Emulation stopped successfully'),
        emulation_id=emulation_id
    )


@app.post("/api/emulation/pause/{emulation_id}", response_model=EmulationControlResponse)
async def pause_emulation_endpoint(emulation_id: str):
    """Pause a running emulation."""
    grpc = require_grpc_client(emulation_id=emulation_id)
    result = grpc.pause_emulation(emulation_id)

    if not result.get('success'):
        message = result.get('message', 'Failed to pause emulation')
        logger.error("Failed to pause emulation %s: %s", emulation_id, message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )

    update_active_emulation(emulation_id, status="paused")
    try:
        rabbitmq_publisher.publish("emulation.paused", {
            'emulation_id': emulation_id,
            'timestamp': _iso_now()
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.paused event: %s", exc)

    return EmulationControlResponse(
        success=True,
        message=result.get('message', 'Emulation paused successfully'),
        emulation_id=emulation_id
    )


@app.post("/api/emulation/resume/{emulation_id}", response_model=EmulationControlResponse)
async def resume_emulation_endpoint(emulation_id: str):
    """Resume a paused emulation."""
    grpc = require_grpc_client(emulation_id=emulation_id)
    result = grpc.resume_emulation(emulation_id)

    if not result.get('success'):
        message = result.get('message', 'Failed to resume emulation')
        logger.error("Failed to resume emulation %s: %s", emulation_id, message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )

    update_active_emulation(emulation_id, status="running")
    try:
        rabbitmq_publisher.publish("emulation.resumed", {
            'emulation_id': emulation_id,
            'timestamp': _iso_now()
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.resumed event: %s", exc)

    return EmulationControlResponse(
        success=True,
        message=result.get('message', 'Emulation resumed successfully'),
        emulation_id=emulation_id
    )


@app.get("/api/emulation/status/{emulation_id}", response_model=EmulationStatusResponse)
async def get_emulation_status(emulation_id: str):
    """Return status information for an emulation."""
    if stop_task_manager.is_running(emulation_id):
        return EmulationStatusResponse(
            status="stopping",
            uptime_seconds=0,
            device_count=0,
            link_count=0,
            metadata={"emulation_id": emulation_id},
        )
    try:
        grpc = await asyncio.to_thread(require_grpc_client, emulation_id=emulation_id)
        status_data = await asyncio.to_thread(grpc.get_status, emulation_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning(
                "Requested status for unknown emulation %s. Removing stale tracking entry.",
                emulation_id
            )
            remove_active_emulation_by_id(emulation_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emulation {emulation_id} is not running. Tracking entry cleared."
            ) from exc
        raise

    update_active_emulation(emulation_id, status=status_data.get('status'))
    return EmulationStatusResponse(**status_data)


@app.get("/api/emulation/shell/{emulation_id}")
async def get_emulation_shell_info(emulation_id: str):
    """Return container and device metadata for establishing shell sessions."""
    topology_id = active_emulations.find_by_emulation_id(emulation_id)
    if not topology_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emulation {emulation_id} is not active"
        )

    record = active_emulations.get(topology_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active emulation record for topology {topology_id}"
        )

    try:
        topology_data = await fetch_topology_definition(topology_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning(
                "Topology %s not found while building shell metadata. Returning container info without devices.",
                topology_id
            )
            topology_data = {'nodes': [], 'devices': []}
        else:
            raise

    nodes = topology_data.get('nodes', topology_data.get('devices', [])) or []

    # Prefer live device info (IPs/interfaces) from the emulation container via gRPC.
    # This prevents UI features (ping/iperf/tests) from failing due to missing IPs in topology definitions.
    device_entries: list[dict[str, Any]] = []
    try:
        grpc = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=emulation_id)
        # Only trust the gRPC device inventory when the emulation is actually running.
        status_info = await asyncio.to_thread(grpc.get_status, emulation_id)
        if (
            str((status_info or {}).get("status") or "").lower() == "running"
            and int((status_info or {}).get("device_count") or 0) > 0
        ):
            live = await asyncio.to_thread(grpc.list_devices, "")
            live_devices = live.get("devices") if isinstance(live, dict) and live.get("success") else None
            if isinstance(live_devices, list) and live_devices:
                for d in live_devices:
                    if not isinstance(d, dict):
                        continue
                    props = d.get("properties") if isinstance(d.get("properties"), dict) else {}
                    # Ensure a stable 'id' field so the UI can correlate devices.
                    d.setdefault("id", props.get("node_id") or props.get("id") or props.get("original_id") or None)
                    d.setdefault("device_type", d.get("type") or props.get("device_type") or "")
                    device_entries.append(d)
    except Exception:
        device_entries = []

    # Fallback: derive minimal device list from the topology definition.
    if not device_entries:
        for node in nodes:
            device_id = node.get('id') or node.get('node_id') or node.get('properties', {}).get('node_id')
            device_name = node.get('name') or node.get('properties', {}).get('display_name') or device_id
            device_type = node.get('device_type') or node.get('type') or node.get('properties', {}).get('device_type')
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            ip = str(props.get("ip") or "").strip()

            device_entries.append({
                'id': device_id,
                'name': device_name,
                'device_type': device_type,
                'runtime_name': _runtime_device_name(device_id, device_name),
                'ip': ip,
                'properties': props,
                'interfaces': [],
            })

    return {
        'topology_id': topology_id,
        'emulation_id': emulation_id,
        'status': record.get('status'),
        'container_name': record.get('container_name'),
        'container_id': record.get('container_id'),
        'devices': device_entries,
    }


@app.get("/api/emulation/active")
async def list_active_emulations():
    """List all active emulations."""
    _reconcile_active_emulations_with_docker()
    emulations = list(active_emulations.get_all().values())
    return {'emulations': emulations}


@app.get("/api/emulation/containers")
async def list_emulation_containers(
    topology_id: Optional[str] = None,
    include_stopped: bool = False
):
    """
    List emulation containers managed by the orchestrator.

    - If topology_id is provided and known, returns that topology's emulation container (if present).
    - Otherwise returns all containers matching the orchestrator naming pattern.
    """
    if not docker_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker client not available"
        )

    primary_container_name: Optional[str] = None
    if topology_id and topology_id in active_emulations:
        record = active_emulations.get(topology_id)
        if record:
            primary_container_name = record.get("container_name")

    try:
        containers = docker_client.containers.list(all=include_stopped)
    except Exception as e:
        logger.error("Failed to list Docker containers: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list Docker containers"
        )

    items: list[dict[str, Any]] = []
    for container in containers:
        name = getattr(container, "name", "")
        if not name:
            continue

        labels = getattr(container, "labels", {}) or {}
        labeled_topology_id = labels.get("caduceus.topology_id")

        # Prefer label-based selection (supports multiple related containers),
        # otherwise fall back to the emulation container naming convention.
        if topology_id:
            is_primary = primary_container_name is not None and name == primary_container_name
            is_labeled = labeled_topology_id == topology_id
            is_legacy_name = name.startswith(f"caduceus-emu-{topology_id[:8]}")
            if not (is_primary or is_labeled or is_legacy_name):
                continue
        else:
            if labeled_topology_id is None and not name.startswith("caduceus-emu-"):
                continue

        items.append({
            "name": name,
            "container_id": getattr(container, "id", None),
            "status": getattr(container, "status", "unknown"),
            "image": getattr(getattr(container, "image", None), "tags", None),
        })

    return {"items": items, "total": len(items)}


@app.post("/api/osm/shared/bootstrap/{topology_id}")
async def bootstrap_shared_osm_for_topology(topology_id: str):
    """
    Best-effort: ensure shared/global ETSI OSM has VIM+WIM accounts for this topology (emulation + controllers).
    Intended both as a debugging endpoint and a manual "sync now" trigger.
    """
    try:
        controllers_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_controllers")
    except Exception:
        controllers_raw = None
    controllers_payload = None
    if controllers_raw:
        try:
            controllers_payload = json.loads(controllers_raw)
        except Exception:
            controllers_payload = None

    vim = await asyncio.to_thread(_bootstrap_osm_shared_emulation_vim, topology_id)
    wims = await asyncio.to_thread(_bootstrap_osm_shared_sdn_wims, topology_id, controllers_payload)
    return {"success": True, "topology_id": topology_id, "shared_osm": {"vim": vim, "wims": wims}}


@app.get("/api/emulation/devices")
async def list_emulation_devices(
    device_type: Optional[str] = None,
    topology_id: Optional[str] = None,
    emulation_id: Optional[str] = None
):
    """List devices in the active emulation."""
    grpc = await asyncio.to_thread(require_grpc_client, topology_id=topology_id, emulation_id=emulation_id)
    result = await asyncio.to_thread(grpc.list_devices, device_type or '')
    if not result.get('success', False):
        logger.error("Failed to list devices: %s", result.get('error', 'Unknown error'))
    return result


@app.post("/api/emulation/devices/add")
async def add_runtime_device(payload: EmulationRuntimeAddDeviceRequest):
    """
    Add a device to a running emulation (runtime-only).

    This is the stable HTTP southbound API used by Device Manager / MANO.
    """
    topology_id = (payload.topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topology_id is required")

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")

    device_type = (payload.device_type or "").strip()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_type is required")

    properties = dict(payload.properties or {})
    node_id = (payload.node_id or properties.get("node_id") or "").strip()
    if node_id:
        properties["node_id"] = node_id

    device_payload = {
        "id": node_id or None,
        "name": name,
        "type": device_type,
        "device_type": device_type,
        "properties": properties,
    }

    grpc_client_instance = await asyncio.to_thread(require_grpc_client, topology_id=topology_id)
    runtime_name = await add_device_to_emulation(topology_id, device_payload, client=grpc_client_instance)
    if not runtime_name:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to add device to emulation")

    return {
        "success": True,
        "topology_id": topology_id,
        "name": name,
        "runtime_name": runtime_name,
        "device_type": device_type,
        "properties": properties,
    }


@app.delete("/api/emulation/devices/{device_name}")
async def remove_runtime_device(
    device_name: str,
    topology_id: str,
    node_id: Optional[str] = None,
):
    """Remove a device from a running emulation (runtime-only)."""
    topology_id = (topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topology_id is required")
    name = (device_name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_name is required")

    grpc_client_instance = await asyncio.to_thread(require_grpc_client, topology_id=topology_id)
    ok = await remove_device_from_emulation(
        topology_id=topology_id,
        device_name=name,
        device_id=(node_id or "").strip() or None,
        client=grpc_client_instance,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to remove device from emulation")
    return {"success": True, "topology_id": topology_id, "name": name}


@app.post("/api/emulation/links/add")
async def add_runtime_link(payload: EmulationRuntimeAddLinkRequest):
    """Add a link between two devices in a running emulation (runtime-only)."""
    topology_id = (payload.topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topology_id is required")

    node1 = (payload.node1 or "").strip()
    node2 = (payload.node2 or "").strip()
    if not node1 or not node2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node1 and node2 are required")

    grpc_client_instance = await asyncio.to_thread(require_grpc_client, topology_id=topology_id)
    runtime_node1 = resolve_runtime_name(None, node1, client=grpc_client_instance)
    runtime_node2 = resolve_runtime_name(None, node2, client=grpc_client_instance)

    params = emulation_pb2.LinkParams(
        bandwidth=int(payload.bandwidth or 0),
        delay=int(payload.delay or 0),
        loss=float(payload.loss or 0.0),
        max_queue_size=int(payload.max_queue_size or 1000),
    )
    request = emulation_pb2.AddLinkRequest(
        node1=runtime_node1,
        node2=runtime_node2,
        port1=str(payload.port1 or ""),
        port2=str(payload.port2 or ""),
        params=params,
    )
    response = await asyncio.to_thread(
        lambda: grpc_client_instance.stub.AddLink(request, timeout=_grpc_runtime_timeout_seconds())
    )
    if not getattr(response, "success", False):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(getattr(response, "message", "Failed to add link")))

    return {
        "success": True,
        "topology_id": topology_id,
        "node1": node1,
        "node2": node2,
        "runtime_node1": runtime_node1,
        "runtime_node2": runtime_node2,
    }


@app.post("/api/emulation/execute", response_model=CommandExecuteResponse)
async def execute_command(request: CommandExecuteRequest):
    """Execute a command on a device within the emulation."""
    if not request.device or not request.command:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device and command fields are required"
        )

    grpc = await asyncio.to_thread(
        require_grpc_client,
        topology_id=request.topology_id,
        emulation_id=request.emulation_id,
    )
    runtime = resolve_runtime_name(None, request.device, grpc)
    result = await asyncio.to_thread(grpc.execute_command, runtime, request.command)
    return CommandExecuteResponse(**result)


@app.post("/api/emulation/network-config/apply", response_model=NetworkConfigApplyResponseBody)
async def apply_network_config(payload: NetworkConfigApplyRequestBody):
    """
    Apply a JSON network configuration to a running emulation.

    This endpoint is intended for bulk configuration (interfaces, IP/MAC, routes, sysctls, etc.).
    """
    if not isinstance(payload.config, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="config must be an object")

    config = payload.config or {}
    defaults_cfg = config.get("defaults") or {}
    if not isinstance(defaults_cfg, dict):
        defaults_cfg = {}

    default_sysctls = defaults_cfg.get("sysctls") or {}
    if not isinstance(default_sysctls, dict):
        default_sysctls = {}

    default_dns = defaults_cfg.get("dns_servers") or []
    if not isinstance(default_dns, list):
        default_dns = []

    default_commands = defaults_cfg.get("commands") or []
    if not isinstance(default_commands, list):
        default_commands = []

    devices_cfg = config.get("devices", [])
    if not isinstance(devices_cfg, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="config.devices must be an array")

    grpc_client = require_grpc_client(topology_id=payload.topology_id, emulation_id=payload.emulation_id)

    results: List[Dict[str, Any]] = []
    any_errors = False

    def _resolve_iface_name(device_name: str, iface: str, known_ifaces: List[str]) -> str:
        # Mininet interface names follow the *runtime* node name (which can differ from the
        # logical device name due to dockerization, truncation, or auto-renaming).
        #
        # Allow configs to keep using logical names (`host-2-eth0`) by translating to the
        # actual interface name discovered via `ip -o link show`.
        try:
            device_name = str(device_name or "")
            iface = str(iface or "")
        except Exception:
            return iface

        if not device_name or not iface:
            return iface

        if iface in (known_ifaces or []):
            return iface

        prefix = f"{device_name}-"
        if iface.startswith(prefix):
            suffix = iface[len(device_name):]  # includes leading '-'
            for candidate in known_ifaces or []:
                if candidate.endswith(suffix):
                    return candidate

        return iface

    for device_cfg in devices_cfg:
        if not isinstance(device_cfg, dict):
            continue

        device_name = str(device_cfg.get("name") or "").strip()
        if not device_name:
            continue

        runtime = resolve_runtime_name(None, device_name, grpc_client)
        device_result: Dict[str, Any] = {
            "device": device_name,
            "runtime": runtime,
            "success": True,
            "steps": [],
        }

        interfaces: List[str] = []
        # Safe even in dry-run: needed to resolve default interfaces.
        ip_link = await asyncio.to_thread(grpc_client.execute_command, runtime, "ip -o link show")
        if ip_link.get("success"):
            interfaces = _parse_ip_link_interfaces(ip_link.get("stdout", ""))
        else:
            device_result["success"] = False
            device_result["steps"].append({
                "command": "ip -o link show",
                "success": False,
                "stderr": ip_link.get("stderr", ""),
            })

        default_iface = _pick_default_interface(interfaces)

        def record_step(cmd: str, res: Dict[str, Any]):
            ok = bool(res.get("success")) and int(res.get("exit_code", 0) or 0) == 0
            device_result["steps"].append({
                "command": cmd,
                "success": ok,
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "exit_code": res.get("exit_code", 0),
            })
            if not ok:
                device_result["success"] = False

        # Apply sysctls first (router forwarding, etc.)
        sysctls = device_cfg.get("sysctls") or {}
        if isinstance(sysctls, dict):
            sysctls = {**default_sysctls, **sysctls}
        else:
            sysctls = dict(default_sysctls)
        if isinstance(sysctls, dict):
            for key, value in sysctls.items():
                cmd = f"sysctl -w {shlex.quote(str(key))}={shlex.quote(str(value))}"
                if payload.dry_run:
                    record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                else:
                    res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                    record_step(cmd, res)

        # Apply interface configs
        iface_cfgs = device_cfg.get("interfaces") or []
        if isinstance(iface_cfgs, list):
            for iface_cfg in iface_cfgs:
                if not isinstance(iface_cfg, dict):
                    continue
                iface_name = (iface_cfg.get("name") or "").strip()
                iface = iface_name or default_iface
                if not iface:
                    device_result["success"] = False
                    device_result["steps"].append({
                        "command": "(resolve interface)",
                        "success": False,
                        "stderr": "No interface found; provide interfaces[].name or ensure the device has an interface",
                    })
                    continue
                iface = _resolve_iface_name(device_name, iface, interfaces)

                addresses = iface_cfg.get("addresses") or []
                has_addresses = isinstance(addresses, list) and any(str(a).strip() for a in addresses)
                reset_addresses = iface_cfg.get("reset_addresses", True)
                # Safety: only flush addresses when we have something to apply (unless user explicitly adds no addresses intentionally).
                if reset_addresses and has_addresses:
                    for cmd in (
                        f"ip addr flush dev {shlex.quote(iface)}",
                        f"ip -6 addr flush dev {shlex.quote(iface)}",
                    ):
                        if payload.dry_run:
                            record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                        else:
                            res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                            record_step(cmd, res)

                mac = iface_cfg.get("mac")
                if mac:
                    cmd = f"ip link set dev {shlex.quote(iface)} address {shlex.quote(str(mac))}"
                    if payload.dry_run:
                        record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                    else:
                        res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                        record_step(cmd, res)

                mtu = iface_cfg.get("mtu")
                if mtu is not None and str(mtu).strip():
                    cmd = f"ip link set dev {shlex.quote(iface)} mtu {shlex.quote(str(mtu))}"
                    if payload.dry_run:
                        record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                    else:
                        res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                        record_step(cmd, res)

                up = iface_cfg.get("up", True)
                if up:
                    cmd = f"ip link set dev {shlex.quote(iface)} up"
                    if payload.dry_run:
                        record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                    else:
                        res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                        record_step(cmd, res)

                if isinstance(addresses, list):
                    for addr in addresses:
                        if not addr:
                            continue
                        cmd = f"ip addr add {shlex.quote(str(addr))} dev {shlex.quote(iface)}"
                        if payload.dry_run:
                            record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                        else:
                            res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                            record_step(cmd, res)

                # Prefer first configured iface as default route interface
                if not default_iface:
                    default_iface = iface

        # Default gateways
        gw = device_cfg.get("default_gateway")
        if gw:
            iface = default_iface
            cmd = f"ip route replace default via {shlex.quote(str(gw))}" + (f" dev {shlex.quote(iface)}" if iface else "")
            if payload.dry_run:
                record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
            else:
                res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                record_step(cmd, res)

        gw6 = device_cfg.get("default_gateway6")
        if gw6:
            iface = default_iface
            cmd = f"ip -6 route replace default via {shlex.quote(str(gw6))}" + (f" dev {shlex.quote(iface)}" if iface else "")
            if payload.dry_run:
                record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
            else:
                res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                record_step(cmd, res)

        # Static routes
        routes = device_cfg.get("routes") or []
        if isinstance(routes, list):
            for route in routes:
                if not isinstance(route, dict):
                    continue
                dst = route.get("dst")
                if not dst:
                    continue
                via = route.get("via")
                dev = route.get("dev") or default_iface
                metric = route.get("metric")
                is_v6 = ":" in str(dst) or (via and ":" in str(via))
                ip_cmd = "ip -6 route replace" if is_v6 else "ip route replace"
                parts = [ip_cmd, str(dst)]
                if via:
                    parts += ["via", str(via)]
                if dev:
                    parts += ["dev", str(dev)]
                if metric is not None and str(metric).strip():
                    parts += ["metric", str(metric)]
                cmd = " ".join(shlex.quote(p) for p in parts)
                if payload.dry_run:
                    record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                else:
                    res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                    record_step(cmd, res)

        # DNS
        dns = device_cfg.get("dns_servers")
        if dns is None or dns == []:
            dns = default_dns
        if not isinstance(dns, list):
            dns = []
        if isinstance(dns, list) and dns:
            content = "\n".join([f"nameserver {str(x).strip()}" for x in dns if str(x).strip()]) + "\n"
            cmd = f'sh -lc "printf %s {shlex.quote(content)} > /etc/resolv.conf"'
            if payload.dry_run:
                record_step(cmd, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
            else:
                res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd)
                record_step(cmd, res)

        # Extra commands
        commands = device_cfg.get("commands")
        if commands is None:
            commands = []
        if not isinstance(commands, list):
            commands = []
        merged_commands = [*default_commands, *commands] if default_commands else commands
        commands = merged_commands
        if isinstance(commands, list):
            for cmd in commands:
                if not cmd:
                    continue
                cmd_str = str(cmd)
                if payload.dry_run:
                    record_step(cmd_str, {"success": True, "stdout": "", "stderr": "", "exit_code": 0})
                else:
                    res = await asyncio.to_thread(grpc_client.execute_command, runtime, cmd_str)
                    record_step(cmd_str, res)

        results.append(device_result)
        if not device_result.get("success"):
            any_errors = True

    return NetworkConfigApplyResponseBody(
        success=not any_errors,
        message="Network configuration applied" if not any_errors else "Network configuration applied with errors",
        topology_id=payload.topology_id,
        dry_run=payload.dry_run,
        results=results,
    )


@app.post("/api/emulation/sync/{topology_id}")
async def sync_emulation(topology_id: str):
    """
    Force synchronization of topology definition with running emulation.
    """
    if topology_id not in active_emulations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active emulation for topology {topology_id}"
        )

    topology_data = await fetch_topology_definition(topology_id)
    results = await sync_topology_to_emulation(topology_id, topology_data)

    if results is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synchronize topology {topology_id}"
        )

    info = active_emulations.get(topology_id) or {}
    info['last_synced_at'] = _iso_now()
    active_emulations.set(topology_id, info)

    try:
        rabbitmq_publisher.publish("emulation.synced", {
            'topology_id': topology_id,
            'emulation_id': info.get('emulation_id'),
            'results': results,
            'timestamp': info.get('last_synced_at')
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.synced event: %s", exc)

    message = f"Topology {topology_id} synchronized successfully"
    return {
        'success': True,
        'message': message,
        'topology_id': topology_id,
        'sync_results': results
    }


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    global rabbitmq_consumer
    global _topology_event_handlers

    logger.info("Starting Emulation Orchestrator Service...")

    # Register with Consul
    consul_client.register_service("orchestrator-service", 8002)

    # Connect to RabbitMQ
    rabbitmq_publisher.connect()

    # Ensure shared artifact roots exist (best-effort; volumes may be mounted later).
    try:
        if _pcap_service:
            _pcap_service.ensure_root()
    except Exception:
        pass

    # Enable RabbitMQ consumer for topology/project deletion events
    rabbitmq_consumer = RabbitMQConsumer("orchestrator_cleanup_queue")
    rabbitmq_consumer.connect()

    _topology_event_handlers = TopologyEventHandlers(
        logger=logger,
        topology_service_url=TOPOLOGY_SERVICE_URL,
        topology_request_timeout=TOPOLOGY_REQUEST_TIMEOUT,
        active_emulations=active_emulations,
        rabbitmq_publisher=rabbitmq_publisher,
        grpc_client_manager=grpc_client_manager,
        require_grpc_client=require_grpc_client,
        remove_emulation_container=remove_emulation_container,
        sync_topology_to_emulation=sync_topology_to_emulation,
        sync_device_to_emulation=sync_device_to_emulation,
        sync_link_to_emulation=sync_link_to_emulation,
        add_device_to_emulation=add_device_to_emulation,
        remove_device_from_emulation=remove_device_from_emulation,
        add_link_to_emulation=add_link_to_emulation,
        remove_link_from_emulation=remove_link_from_emulation,
    )

    # Bind routing keys and register callbacks for automatic container cleanup
    rabbitmq_consumer.bind_routing_key("topology.deleted")
    rabbitmq_consumer.register_callback("topology.deleted", _topology_event_handlers.handle_topology_deleted)

    rabbitmq_consumer.bind_routing_key("project.deleted")
    rabbitmq_consumer.register_callback("project.deleted", _topology_event_handlers.handle_project_deleted)

    # DISABLED: Topology lifecycle and sync events to prevent blocking
    # These events trigger sync operations that can hang the orchestrator
    # Users should manually restart emulations if they need topology changes applied

    # rabbitmq_consumer.bind_routing_key("topology.created")
    # rabbitmq_consumer.register_callback("topology.created", _topology_event_handlers.handle_topology_created)

    # rabbitmq_consumer.bind_routing_key("topology.updated")
    # rabbitmq_consumer.register_callback("topology.updated", _topology_event_handlers.handle_topology_updated)

    # Fine-grained topology change events - DISABLED
    # rabbitmq_consumer.bind_routing_key("topology.node.added")
    # rabbitmq_consumer.register_callback("topology.node.added", _topology_event_handlers.handle_topology_node_added)

    # rabbitmq_consumer.bind_routing_key("topology.node.updated")
    # rabbitmq_consumer.register_callback("topology.node.updated", _topology_event_handlers.handle_topology_node_updated)

    # rabbitmq_consumer.bind_routing_key("topology.node.deleted")
    # rabbitmq_consumer.register_callback("topology.node.deleted", _topology_event_handlers.handle_topology_node_deleted)

    # rabbitmq_consumer.bind_routing_key("topology.link.added")
    # rabbitmq_consumer.register_callback("topology.link.added", _topology_event_handlers.handle_topology_link_added)

    # rabbitmq_consumer.bind_routing_key("topology.link.updated")
    # rabbitmq_consumer.register_callback("topology.link.updated", _topology_event_handlers.handle_topology_link_updated)

    # rabbitmq_consumer.bind_routing_key("topology.link.deleted")
    # rabbitmq_consumer.register_callback("topology.link.deleted", _topology_event_handlers.handle_topology_link_deleted)

    # Start consuming in a background thread
    import threading
    consumer_thread = threading.Thread(target=rabbitmq_consumer.start_consuming, daemon=True)
    consumer_thread.start()

    logger.info("RabbitMQ consumer enabled for topology/project deletion events")

    logger.info("Emulation Orchestrator Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Emulation Orchestrator Service...")

    # By default, do NOT stop running emulations when the orchestrator restarts:
    # emulation containers should keep running and controllers should stay connected.
    stop_on_shutdown = str(os.getenv("STOP_EMULATIONS_ON_SHUTDOWN", "false")).strip().lower() in ("1", "true", "yes", "y", "on")
    if stop_on_shutdown:
        for topology_id, info in active_emulations.get_all().items():
            try:
                emulation_id = info.get("emulation_id")
                if emulation_id:
                    client = grpc_client_manager.get_client(topology_id) or grpc_client_manager.get_or_create(topology_id)
                    if client:
                        client.stop_emulation(emulation_id, cleanup=True)
            except Exception as e:
                logger.error(f"Error stopping emulation {emulation_id}: {e}")

    # Close gRPC clients
    for topology_id in list(grpc_client_manager.clients.keys()):
        grpc_client_manager.remove_client(topology_id)

    consul_client.deregister_service("orchestrator-service")
    rabbitmq_publisher.disconnect()

    if rabbitmq_consumer:
        rabbitmq_consumer.disconnect()


# ==================== Live Update Helper Functions ====================

def _grpc_runtime_timeout_seconds() -> float:
    try:
        value = float(os.getenv("CADUCEUS_GRPC_RPC_TIMEOUT_SECONDS", "15") or "15")
    except Exception:
        value = 15.0
    return max(3.0, value)

async def get_node_name_from_id(topology_id: str, node_id: str) -> str:
    """
    Get node name from node ID by fetching from topology service

    Args:
        topology_id: Topology ID
        node_id: Node UUID

    Returns:
        Node name string, or node_id if fetch fails
    """
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://topology-service:8001/api/topologies/{topology_id}/nodes/{node_id}")
            if response.status_code == 200:
                node_data = response.json()
                return node_data.get('name', node_id)
            else:
                logger.warning(f"Failed to fetch node {node_id}, using ID as fallback")
                return node_id
    except Exception as e:
        logger.error(f"Error fetching node name for {node_id}: {e}")
        return node_id


async def add_device_to_emulation(
    topology_id: str,
    device_data: Dict,
    client: Optional["gRPCClient"] = None,
) -> Optional[str]:
    """
    Add a new device to running emulation

    Args:
        topology_id: Topology ID
        device_data: Device data from database
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        device_name = device_data.get('name')
        device_type = device_data.get('type', device_data.get('device_type', ''))
        device_properties = device_data.get('properties', {})
        device_id = device_data.get('id') or device_properties.get('node_id') or device_data.get('node_id')

        logger.info(f"Adding device {device_name} (type: {device_type}) to emulation for topology {topology_id}")

        node_id_value = str(device_id) if device_id else ''
        runtime_name = resolve_runtime_name(node_id_value, device_name, client=client)
        if client:
            existing_names = set(client.node_id_to_runtime.values())
            if runtime_name in existing_names:
                suffix = hashlib.sha1(f"{node_id_value}-{device_name}".encode()).hexdigest()[:4]
                runtime_name = f"{runtime_name}-{suffix}"

        def attach_common_params(param_container):
            if node_id_value:
                param_container['node_id'] = node_id_value
            if device_name:
                param_container['display_name'] = device_name
                param_container['original_name'] = device_name

        def normalize_dpid(raw_value: Any, fallback: str) -> str:
            import hashlib
            import re

            if raw_value is None or raw_value == '':
                seed = fallback or device_name or 'switch'
                return hashlib.sha1(seed.encode()).hexdigest()[-16:]

            if isinstance(raw_value, int):
                return f"{raw_value & 0xffffffffffff:016x}"

            raw_str = str(raw_value).strip().lower()
            if raw_str.startswith('0x'):
                raw_str = raw_str[2:]
            raw_str = re.sub(r'[^0-9a-f]', '', raw_str)
            if not raw_str:
                seed = fallback or device_name or 'switch'
                return hashlib.sha1(seed.encode()).hexdigest()[-16:]
            return raw_str.zfill(16)[-16:]

        # Prepare request based on device type
        if device_type.lower() == 'host':
            request = emulation_pb2.AddHostRequest(
                name=runtime_name,
                ip=device_properties.get('ip', ''),
                ip6=device_properties.get('ip6', ''),
                mac=device_properties.get('mac', ''),
                default_route=device_properties.get('default_route', '')
            )
            # Add extra params
            for key, value in device_properties.items():
                if key not in ['ip', 'ip6', 'mac', 'default_route']:
                    request.params[key] = str(value)
            attach_common_params(request.params)

            response = client.stub.AddHost(request, timeout=grpc_rpc_timeout_s)

        elif device_type.lower() in ['switch', 'ovs', 'ovsswitch']:
            raw_dpid = (
                device_properties.get('dpid')
                or device_properties.get('datapath_id')
                or device_id
            )
            normalized_dpid = normalize_dpid(raw_dpid, node_id_value or device_name)
            try:
                # gRPC schema uses `int32` for datapath_id; keep it within signed range to
                # avoid `Value out of range` on common UUID-based dpids (0x8xxxxxxx+).
                datapath_numeric = int(normalized_dpid[-8:], 16) & 0x7FFFFFFF
                if datapath_numeric == 0:
                    datapath_numeric = 1
            except ValueError:
                datapath_numeric = 0

            request = emulation_pb2.AddSwitchRequest(
                name=runtime_name,
                switch_type=device_properties.get('switch_type', 'ovs'),
                openflow_version=device_properties.get('openflow_version', ''),
                controller=device_properties.get('controller', ''),
                datapath_id=datapath_numeric
            )
            for key, value in device_properties.items():
                if key not in ['switch_type', 'openflow_version', 'controller', 'datapath_id']:
                    request.params[key] = str(value)
            request.params['dpid'] = normalized_dpid
            attach_common_params(request.params)

            response = client.stub.AddSwitch(request, timeout=grpc_rpc_timeout_s)

        elif device_type.lower() == 'router':
            protocols = device_properties.get('protocols', [])
            if isinstance(protocols, str):
                protocols = [p.strip() for p in protocols.split(',')]

            request = emulation_pb2.AddRouterRequest(
                name=runtime_name,
                protocols=protocols,
                router_daemon=device_properties.get('router_daemon', 'frr')
            )
            for key, value in device_properties.items():
                if key not in ['protocols', 'router_daemon'] and not key.startswith('protocol_config_'):
                    request.params[key] = str(value)
                elif key.startswith('protocol_config_'):
                    proto_name = key.replace('protocol_config_', '')
                    request.protocol_configs[proto_name] = str(value)
            attach_common_params(request.params)

            response = client.stub.AddRouter(request, timeout=grpc_rpc_timeout_s)

        elif device_type.lower() == 'accesspoint':
            request = emulation_pb2.AddAccessPointRequest(
                name=runtime_name,
                ssid=device_properties.get('ssid', ''),
                mode=device_properties.get('mode', 'g'),
                channel=device_properties.get('channel', '1'),
                security=device_properties.get('security', 'open'),
                password=device_properties.get('password', '')
            )
            for key, value in device_properties.items():
                if key not in ['ssid', 'mode', 'channel', 'security', 'password']:
                    request.params[key] = str(value)
            attach_common_params(request.params)

            response = client.stub.AddAccessPoint(request, timeout=grpc_rpc_timeout_s)

        elif device_type.lower() == 'station':
            request = emulation_pb2.AddStationRequest(
                name=runtime_name,
                ssid=device_properties.get('ssid', ''),
                mode=device_properties.get('mode', 'g'),
                security=device_properties.get('security', 'open'),
                password=device_properties.get('password', '')
            )
            for key, value in device_properties.items():
                if key not in ['ssid', 'mode', 'security', 'password']:
                    request.params[key] = str(value)
            attach_common_params(request.params)

            response = client.stub.AddStation(request, timeout=grpc_rpc_timeout_s)

        elif device_type.lower() in ['docker', 'container']:
            docker_rpc_timeout_s = max(
                grpc_rpc_timeout_s,
                float(os.getenv("CADUCEUS_GRPC_DOCKER_TIMEOUT_SECONDS", "25") or "25"),
            )
            command_value = device_properties.get('command')
            if isinstance(command_value, str):
                command_list = shlex.split(command_value)
            elif isinstance(command_value, (list, tuple)):
                command_list = [str(cmd) for cmd in command_value if str(cmd).strip()]
            else:
                command_list = []

            environment = device_properties.get('environment') or device_properties.get('env') or {}
            if isinstance(environment, str):
                try:
                    environment = json.loads(environment)
                except Exception:
                    parsed_env = {}
                    for entry in environment.split(','):
                        if '=' in entry:
                            key, value = entry.split('=', 1)
                            parsed_env[key.strip()] = value.strip()
                    environment = parsed_env

            volumes = device_properties.get('volumes') or []
            if isinstance(volumes, str):
                volumes = [item.strip() for item in volumes.split(',') if item.strip()]

            request = emulation_pb2.AddDockerContainerRequest(
                name=runtime_name,
                image=device_properties.get('image') or device_properties.get('docker_image') or 'ubuntu:22.04'
            )
            if command_list:
                request.command.extend(command_list)
            for key, value in (environment or {}).items():
                request.environment[str(key)] = str(value)
            for volume in volumes:
                request.volumes.append(str(volume))
            for key, value in device_properties.items():
                if key not in ['image', 'docker_image', 'command', 'environment', 'env', 'volumes']:
                    request.params[key] = str(value)
            attach_common_params(request.params)

            try:
                response = client.stub.AddDockerContainer(request, timeout=docker_rpc_timeout_s)
            except Exception as exc:
                # Some environments (or topologies) may not support Docker container spawning reliably.
                # Fall back to a regular host so higher-level MANO flows remain functional.
                logger.warning(
                    "AddDockerContainer failed for %s (timeout=%.1fs); falling back to AddHost: %s",
                    device_name,
                    docker_rpc_timeout_s,
                    exc,
                )
                fallback = emulation_pb2.AddHostRequest(
                    name=runtime_name,
                    ip=device_properties.get('ip', ''),
                    ip6=device_properties.get('ip6', ''),
                    mac=device_properties.get('mac', ''),
                    default_route=device_properties.get('default_route', '')
                )
                for key, value in device_properties.items():
                    if key not in ['ip', 'ip6', 'mac', 'default_route']:
                        fallback.params[key] = str(value)
                fallback.params['docker_fallback'] = 'true'
                attach_common_params(fallback.params)
                response = client.stub.AddHost(fallback, timeout=grpc_rpc_timeout_s)

        else:
            # Generic host for unknown types
            logger.warning(f"Unknown device type {device_type}, adding as generic host")
            request = emulation_pb2.AddHostRequest(
                name=runtime_name,
                ip=device_properties.get('ip', ''),
                mac=device_properties.get('mac', '')
            )
            for key, value in device_properties.items():
                request.params[key] = str(value)
            attach_common_params(request.params)

            response = client.stub.AddHost(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully added device {runtime_name} (display: {device_name}) to emulation")
            if client:
                if node_id_value:
                    client.node_id_to_runtime[node_id_value] = runtime_name
                if device_name:
                    client.node_id_to_runtime[device_name] = runtime_name
                client.node_id_to_runtime[runtime_name] = runtime_name
            return runtime_name
        else:
            logger.error(f"Failed to add device {device_name}: {response.message}")
            return None

    except Exception as e:
        logger.error(f"Error adding device to emulation: {e}")
        return None


async def remove_device_from_emulation(
    topology_id: str,
    device_name: str,
    device_id: Optional[str] = None,
    client: Optional["gRPCClient"] = None
):
    """
    Remove a device from running emulation

    Args:
        topology_id: Topology ID
        device_name: Name of device to remove
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        runtime_name = None
        if device_id and client:
            runtime_name = client.node_id_to_runtime.get(device_id)
        if not runtime_name:
            runtime_name = _runtime_device_name(device_id, device_name)

        logger.info(f"Removing device {runtime_name} (display: {device_name}) from emulation for topology {topology_id}")

        request = emulation_pb2.RemoveDeviceRequest(name=runtime_name)
        response = client.stub.RemoveDevice(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully removed device {runtime_name} from emulation")
            if client:
                if device_id and device_id in client.node_id_to_runtime:
                    runtime = client.node_id_to_runtime.pop(device_id, None)
                    if runtime:
                        client.node_id_to_runtime.pop(runtime, None)
                if device_name:
                    runtime = client.node_id_to_runtime.pop(device_name, None)
                    if runtime:
                        client.node_id_to_runtime.pop(runtime, None)
            return True
        else:
            logger.error(f"Failed to remove device {device_name}: {response.message}")
            return False

    except Exception as e:
        logger.error(f"Error removing device from emulation: {e}")
        return False


async def add_link_to_emulation(topology_id: str, link_data: Dict, client: Optional["gRPCClient"] = None):
    """
    Add a new link to running emulation

    Args:
        topology_id: Topology ID
        link_data: Link data from database
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        # Get node IDs
        source_node_id = link_data.get('source_node_id') or link_data.get('node1')
        target_node_id = link_data.get('target_node_id') or link_data.get('node2')
        port1 = link_data.get('source_port', link_data.get('port1', ''))
        port2 = link_data.get('target_port', link_data.get('port2', ''))

        # Resolve node names from IDs
        node1_name = await get_node_name_from_id(topology_id, source_node_id)
        node2_name = await get_node_name_from_id(topology_id, target_node_id)
        runtime_node1 = resolve_runtime_name(source_node_id, node1_name, client=client)
        runtime_node2 = resolve_runtime_name(target_node_id, node2_name, client=client)

        logger.info(f"Adding link {runtime_node1}-{runtime_node2} to emulation for topology {topology_id}")

        # Prepare link parameters
        bandwidth = link_data.get('bandwidth', 0)
        delay = link_data.get('delay', 0)
        loss = link_data.get('loss', 0)
        max_queue = link_data.get('max_queue_size', 1000)

        params = emulation_pb2.LinkParams(
            bandwidth=int(bandwidth) if bandwidth else 0,
            delay=int(delay) if delay else 0,
            loss=float(loss) if loss else 0.0,
            max_queue_size=int(max_queue) if max_queue else 1000
        )

        # Call gRPC AddLink with device names
        request = emulation_pb2.AddLinkRequest(
            node1=runtime_node1,
            node2=runtime_node2,
            port1=str(port1) if port1 else '',
            port2=str(port2) if port2 else '',
            params=params
        )

        response = client.stub.AddLink(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully added link {node1_name}-{node2_name} to emulation")
            return True
        else:
            logger.error(f"Failed to add link {node1_name}-{node2_name}: {response.message}")
            return False

    except Exception as e:
        logger.error(f"Error adding link to emulation: {e}")
        return False


async def remove_link_from_emulation(topology_id: str, link_data: Dict, client: Optional["gRPCClient"] = None):
    """
    Remove a link from running emulation

    Args:
        topology_id: Topology ID
        link_data: Link data from database (needs node1/node2 or source/target)
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        # Get node IDs
        source_node_id = link_data.get('source_node_id') or link_data.get('node1')
        target_node_id = link_data.get('target_node_id') or link_data.get('node2')

        # Resolve node names from IDs
        node1_name = await get_node_name_from_id(topology_id, source_node_id)
        node2_name = await get_node_name_from_id(topology_id, target_node_id)

        runtime_node1 = resolve_runtime_name(source_node_id, node1_name, client=client)
        runtime_node2 = resolve_runtime_name(target_node_id, node2_name, client=client)

        logger.info(f"Removing link {runtime_node1}-{runtime_node2} from emulation for topology {topology_id}")

        request = emulation_pb2.RemoveLinkRequest(
            node1=runtime_node1,
            node2=runtime_node2
        )

        response = client.stub.RemoveLink(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully removed link {node1_name}-{node2_name} from emulation")
            return True
        else:
            logger.error(f"Failed to remove link {node1_name}-{node2_name}: {response.message}")
            return False

    except Exception as e:
        logger.error(f"Error removing link from emulation: {e}")
        return False


async def sync_device_to_emulation(topology_id: str, device_data: Dict, client: Optional["gRPCClient"] = None):
    """
    Sync a single device update to running emulation

    Args:
        topology_id: Topology ID
        device_data: Device data from database
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        device_id = device_data.get('id')
        if not device_id:
            logger.warning(f"Device in topology {topology_id} is missing an ID, skipping sync.")
            return False

        device_name = device_data.get('name')
        device_properties = device_data.get('properties', {})

        logger.info(f"Syncing device {device_name} (ID: {device_id}) to emulation for topology {topology_id}")

        runtime_name = resolve_runtime_name(device_id, device_name, client=client)
        client.node_id_to_runtime[device_id] = runtime_name
        if device_name:
            client.node_id_to_runtime[device_name] = runtime_name
        client.node_id_to_runtime[runtime_name] = runtime_name

        # Prepare update request
        updates = {
            'display_name': device_name  # Pass the potentially updated display name
        }

        # Extract other updateable properties
        if 'ip' in device_properties:
            updates['ip'] = device_properties['ip']
        if 'mac' in device_properties:
            updates['mac'] = device_properties['mac']
        if 'default_route' in device_properties:
            updates['default_route'] = device_properties['default_route']

        # Call gRPC UpdateDevice, using the immutable ID as the primary identifier
        request = emulation_pb2.UpdateDeviceRequest(
            name=device_id,  # Use ID in the 'name' field
            updates=updates
        )

        response = client.stub.UpdateDevice(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully updated device {device_name} (ID: {device_id}) in emulation")
            return True
        else:
            logger.error(f"Failed to update device {device_name} (ID: {device_id}): {response.message}")
            return False

    except Exception as e:
        logger.error(f"Error syncing device to emulation: {e}")
        return False


async def sync_link_to_emulation(topology_id: str, link_data: Dict, client: Optional["gRPCClient"] = None):
    """
    Sync a single link update to running emulation

    Args:
        topology_id: Topology ID
        link_data: Link data from database
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        grpc_rpc_timeout_s = _grpc_runtime_timeout_seconds()
        # Get node IDs
        source_node_id = link_data.get('source_node_id') or link_data.get('node1')
        target_node_id = link_data.get('target_node_id') or link_data.get('node2')

        # Resolve node names from IDs
        node1_name = await get_node_name_from_id(topology_id, source_node_id)
        node2_name = await get_node_name_from_id(topology_id, target_node_id)

        runtime_node1 = resolve_runtime_name(source_node_id, node1_name, client=client)
        runtime_node2 = resolve_runtime_name(target_node_id, node2_name, client=client)

        logger.info(f"Syncing link {runtime_node1}-{runtime_node2} to emulation for topology {topology_id}")

        # Prepare link parameters
        bandwidth = link_data.get('bandwidth', 0)
        delay = link_data.get('delay', 0)
        loss = link_data.get('loss', 0)
        max_queue = link_data.get('max_queue_size', 1000)

        params = emulation_pb2.LinkParams(
            bandwidth=int(bandwidth) if bandwidth else 0,
            delay=int(delay) if delay else 0,
            loss=float(loss) if loss else 0.0,
            max_queue_size=int(max_queue) if max_queue else 1000
        )

        # Call gRPC UpdateLink with device names (not IDs)
        request = emulation_pb2.UpdateLinkRequest(
            node1=runtime_node1,
            node2=runtime_node2,
            params=params
        )

        response = client.stub.UpdateLink(request, timeout=grpc_rpc_timeout_s)

        if response.success:
            logger.info(f"Successfully updated link {node1_name}-{node2_name} in emulation")
            return True
        else:
            logger.error(f"Failed to update link {node1_name}-{node2_name}: {response.message}")
            return False

    except Exception as e:
        logger.error(f"Error syncing link to emulation: {e}")
        return False


async def restart_emulation_with_topology(
    topology_id: str,
    topology_data: Dict,
    client: Optional["gRPCClient"] = None
) -> Optional[str]:
    """Fallback path: restart the entire emulation with the latest topology."""
    try:
        client = client or require_grpc_client(topology_id=topology_id)
    except HTTPException as exc:
        logger.error(
            "Fallback restart aborted for topology %s: %s",
            topology_id,
            exc.detail
        )
        return None

    active_record = active_emulations.get(topology_id) or {}
    previous_emulation_id = active_record.get('emulation_id')

    if previous_emulation_id:
        logger.info(
            "Stopping existing emulation %s for topology %s before restart",
            previous_emulation_id,
            topology_id
        )
        stop_result = client.stop_emulation(previous_emulation_id, cleanup=True)
        if not stop_result.get('success'):
            logger.warning(
                "Failed to stop emulation %s prior to restart: %s",
                previous_emulation_id,
                stop_result.get('message', 'unknown error')
            )

    logger.info(
        "Restarting emulation for topology %s with refreshed topology definition",
        topology_id
    )
    start_result = client.start_emulation(topology_id, topology_data)
    if not start_result.get('success'):
        logger.error(
            "Fallback restart failed for topology %s: %s",
            topology_id,
            start_result.get('message', 'unknown error')
        )
        return None

    new_emulation_id = start_result.get('emulation_id')
    record_active_emulation(
        topology_id=topology_id,
        emulation_id=new_emulation_id,
        topology_data=topology_data,
        options=active_record.get('options') or {},
        status_value="running",
        container_id=active_record.get('container_id'),
        container_name=active_record.get('container_name')
    )

    try:
        rabbitmq_publisher.publish("emulation.restarted", {
            'topology_id': topology_id,
            'previous_emulation_id': previous_emulation_id,
            'emulation_id': new_emulation_id,
            'timestamp': _iso_now()
        })
    except Exception as exc:
        logger.error("Failed to publish emulation.restarted event: %s", exc)

    return new_emulation_id


async def sync_topology_to_emulation(topology_id: str, topology_data: Dict, client: Optional["gRPCClient"] = None):
    """
    Full sync of topology to running emulation

    Args:
        topology_id: Topology ID
        topology_data: Complete topology data from database
    """
    try:
        client = client or require_grpc_client(topology_id=topology_id)
        logger.info(f"Starting full topology sync for {topology_id}")

        sync_results = {
            'devices_updated': 0,
            'devices_failed': 0,
            'links_updated': 0,
            'links_failed': 0
        }

        # Sync all devices
        devices = topology_data.get('nodes', topology_data.get('devices', []))
        for device in devices:
            if await sync_device_to_emulation(topology_id, device, client=client):
                sync_results['devices_updated'] += 1
            else:
                sync_results['devices_failed'] += 1

        # Sync all links
        links = topology_data.get('links', [])
        for link in links:
            if await sync_link_to_emulation(topology_id, link, client=client):
                sync_results['links_updated'] += 1
            else:
                sync_results['links_failed'] += 1

        fallback_executed = False
        fallback_success = False
        if sync_results['devices_failed'] or sync_results['links_failed']:
            logger.warning(
                "Incremental sync encountered errors for topology %s; attempting full restart fallback.",
                topology_id
            )
            fallback_executed = True
            new_emulation_id = await restart_emulation_with_topology(
                topology_id,
                topology_data,
                client=client
            )
            if new_emulation_id:
                fallback_success = True
                sync_results['devices_failed'] = 0
                sync_results['links_failed'] = 0
                sync_results['devices_updated'] = len(devices)
                sync_results['links_updated'] = len(links)
                logger.info(
                    "Fallback restart completed for topology %s; new emulation ID %s",
                    topology_id,
                    new_emulation_id
                )
            else:
                logger.error(
                    "Fallback restart failed for topology %s; emulation may be out of sync.",
                    topology_id
                )

        sync_results['fallback_restart'] = fallback_executed
        sync_results['fallback_success'] = fallback_success

        logger.info(f"Topology sync complete: {sync_results}")

        # Publish sync complete event
        rabbitmq_publisher.publish("emulation.synced", {
            'topology_id': topology_id,
            'results': sync_results
        })

        return sync_results

    except Exception as e:
        logger.error(f"Error syncing topology to emulation: {e}")
        return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
