"""
Config Service - Port 8016

Unified JSON-based control plane that can orchestrate actions across:
- Emulation/orchestrator (infra, emulation lifecycle, network config)
- SDN controllers (per-topology controller lifecycle + exec)
- MANO (NS/VNF lifecycle)
- Generic MCP proxied requests

The frontend uses MCP routing: `/api/config/*` -> config-service `/api/*`.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "config-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8016"))

MCP_SERVER_URL = (os.getenv("MCP_SERVER_URL") or "http://mcp-server:8012").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("CONFIG_HTTP_TIMEOUT_SECONDS", "60"))

SUPPORTED_SCHEMA = "caduceus.control-config.v1"

app = FastAPI(
    title="Caduceus-Flux Config Service",
    description="Unified control/config orchestration service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ControlAction(BaseModel):
    id: Optional[str] = Field(default=None, description="Optional action id for correlation")
    kind: str = Field(..., min_length=1, description="Action kind (e.g. emulation.start, mano.vnf.create)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    dry_run: Optional[bool] = Field(default=None, description="Per-action dry run override")


class ControlConfig(BaseModel):
    schema: str = Field(default=SUPPORTED_SCHEMA)
    topology_id: Optional[str] = None
    dry_run: bool = False
    actions: List[ControlAction] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    ok: bool
    schema: str
    errors: List[str] = Field(default_factory=list)
    plan: List[Dict[str, Any]] = Field(default_factory=list)


class ApplyResponse(BaseModel):
    ok: bool
    schema: str
    results: List[Dict[str, Any]] = Field(default_factory=list)


@app.on_event("startup")
async def _startup() -> None:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS))
    logger.info("Config service started: %s:%s (MCP=%s)", SERVICE_NAME, SERVICE_PORT, MCP_SERVER_URL)


@app.on_event("shutdown")
async def _shutdown() -> None:
    http: httpx.AsyncClient = app.state.http
    await http.aclose()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _effective_topology_id(cfg: ControlConfig, action: ControlAction) -> Optional[str]:
    topo = action.params.get("topology_id")
    if isinstance(topo, str) and topo.strip():
        return topo.strip()
    if cfg.topology_id and cfg.topology_id.strip():
        return cfg.topology_id.strip()
    return None


def _effective_dry_run(cfg: ControlConfig, action: ControlAction) -> bool:
    if action.dry_run is None:
        return bool(cfg.dry_run)
    return bool(action.dry_run)


async def _mcp_request(
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
    path: str,
    *,
    json_body: Any = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not path.startswith("/"):
        path = "/" + path
    url = MCP_SERVER_URL + path
    http: httpx.AsyncClient = app.state.http
    resp = await http.request(method, url, json=json_body, params=params)
    content_type = (resp.headers.get("content-type") or "").lower()
    data: Any
    if "application/json" in content_type:
        try:
            data = resp.json()
        except Exception:
            data = resp.text
    else:
        data = resp.text
    return {"status_code": resp.status_code, "data": data}


def _build_result(
    *,
    action: ControlAction,
    dry_run: bool,
    request: Dict[str, Any],
    response: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    status = "skipped" if dry_run else "success"
    if error:
        status = "error"
    elif response and int(response.get("status_code") or 0) >= 400:
        status = "error"
    return {
        "id": action.id,
        "kind": action.kind,
        "dry_run": dry_run,
        "status": status,
        "request": request,
        "response": response,
        "error": error,
    }


def _require_topology_id(cfg: ControlConfig, action: ControlAction) -> str:
    topo = _effective_topology_id(cfg, action)
    if not topo:
        raise HTTPException(status_code=400, detail=f"Action '{action.kind}' requires topology_id (top-level or action.params.topology_id)")
    return topo


def _as_str(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected non-empty string")
    return value.strip()


async def _handle_emulation_start(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    options = action.params.get("options")
    req = {"method": "POST", "path": "/api/orchestrator/emulation/start", "json": {"topology_id": topo, "options": options}}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_emulation_stop(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    emulation_id = _as_str(action.params.get("emulation_id"))
    payload = {
        "cleanup": bool(action.params.get("cleanup", True)),
        "stop_infra": bool(action.params.get("stop_infra", True)),
        "preserve_infra_data": bool(action.params.get("preserve_infra_data", True)),
    }
    req = {"method": "POST", "path": f"/api/orchestrator/emulation/stop/{emulation_id}", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_network_config_apply(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    config = action.params.get("config")
    if config is None:
        raise HTTPException(status_code=400, detail="network_config.apply requires params.config")
    payload = {
        "topology_id": topo,
        "emulation_id": action.params.get("emulation_id"),
        "config": config,
        "dry_run": bool(action.params.get("dry_run", dry_run)),
    }
    req = {"method": "POST", "path": "/api/orchestrator/emulation/network-config/apply", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_device_exec(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    device = _as_str(action.params.get("device"))
    command = _as_str(action.params.get("command"))
    payload = {"topology_id": topo, "emulation_id": action.params.get("emulation_id"), "device": device, "command": command}
    req = {"method": "POST", "path": "/api/orchestrator/emulation/execute", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_topology_infra_ensure(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    req = {"method": "POST", "path": f"/api/orchestrator/infrastructure/topologies/{topo}/infra/ensure", "json": {}}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_topology_osm_ensure(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    req = {"method": "POST", "path": f"/api/orchestrator/infrastructure/topologies/{topo}/osm/ensure", "json": {}}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_controller_op(cfg: ControlConfig, action: ControlAction, op: Literal["start", "stop", "restart"]) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    controller_id = _as_str(action.params.get("controller_id"))
    req = {
        "method": "POST",
        "path": f"/api/orchestrator/infrastructure/topologies/{topo}/controllers/{controller_id}/{op}",
        "json": {},
    }
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_controller_exec(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _require_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    controller_id = _as_str(action.params.get("controller_id"))
    command = _as_str(action.params.get("command"))
    req = {
        "method": "POST",
        "path": f"/api/orchestrator/infrastructure/topologies/{topo}/controllers/{controller_id}/exec",
        "json": {"command": command},
    }
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mano_ns_create(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    topo = _effective_topology_id(cfg, action)
    dry_run = _effective_dry_run(cfg, action)
    name = _as_str(action.params.get("name"))
    payload = {
        "name": name,
        "nsd_id": action.params.get("nsd_id"),
        "topology_id": topo,
        "options": action.params.get("options") or {},
        "dry_run": bool(action.params.get("dry_run", dry_run)),
        "backend": action.params.get("backend"),
    }
    req = {"method": "POST", "path": "/api/mano/ns-instances", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mano_ns_terminate(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    ns_id = _as_str(action.params.get("ns_instance_id") or action.params.get("ns_id"))
    payload = {"reason": str(action.params.get("reason") or "")}
    req = {"method": "POST", "path": f"/api/mano/ns-instances/{ns_id}/terminate", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mano_vnf_create(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    name = _as_str(action.params.get("name"))
    ns_instance_id = _as_str(action.params.get("ns_instance_id"))
    payload = {
        "ns_instance_id": ns_instance_id,
        "vnfd_id": action.params.get("vnfd_id"),
        "name": name,
        "device_type": action.params.get("device_type", "container"),
        "device_name": action.params.get("device_name"),
        "properties": action.params.get("properties") or {},
        "dry_run": bool(action.params.get("dry_run", dry_run)),
    }
    req = {"method": "POST", "path": "/api/mano/vnfm/vnf-instances", "json": payload}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mano_vnf_delete(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    vnf_id = _as_str(action.params.get("vnf_instance_id") or action.params.get("vnf_id"))
    params = {"force": bool(action.params.get("force", False))}
    req = {"method": "DELETE", "path": f"/api/mano/vnfm/vnf-instances/{vnf_id}", "params": params}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("DELETE", req["path"], params=req["params"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mano_vnf_exec(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    vnf_id = _as_str(action.params.get("vnf_instance_id") or action.params.get("vnf_id"))
    command = _as_str(action.params.get("command"))
    req = {"method": "POST", "path": f"/api/mano/vnfm/vnf-instances/{vnf_id}/exec", "json": {"command": command}}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request("POST", req["path"], json_body=req["json"])
    return _build_result(action=action, dry_run=False, request=req, response=resp)


async def _handle_mcp_request_action(cfg: ControlConfig, action: ControlAction) -> Dict[str, Any]:
    dry_run = _effective_dry_run(cfg, action)
    method = str(action.params.get("method") or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise HTTPException(status_code=400, detail="mcp.request params.method must be one of GET/POST/PUT/PATCH/DELETE")
    path = str(action.params.get("path") or "")
    if not path.startswith("/api/"):
        raise HTTPException(status_code=400, detail="mcp.request params.path must start with /api/")
    req = {"method": method, "path": path, "json": action.params.get("json"), "params": action.params.get("params")}
    if dry_run:
        return _build_result(action=action, dry_run=True, request=req)
    resp = await _mcp_request(method, path, json_body=req.get("json"), params=req.get("params"))
    return _build_result(action=action, dry_run=False, request=req, response=resp)


HANDLERS = {
    "emulation.start": _handle_emulation_start,
    "emulation.stop": _handle_emulation_stop,
    "network_config.apply": _handle_network_config_apply,
    "device.exec": _handle_device_exec,
    "topology.infra.ensure": _handle_topology_infra_ensure,
    "topology.osm.ensure": _handle_topology_osm_ensure,
    "sdn.controller.start": lambda cfg, a: _handle_controller_op(cfg, a, "start"),
    "sdn.controller.stop": lambda cfg, a: _handle_controller_op(cfg, a, "stop"),
    "sdn.controller.restart": lambda cfg, a: _handle_controller_op(cfg, a, "restart"),
    "sdn.controller.exec": _handle_controller_exec,
    "mano.ns.create": _handle_mano_ns_create,
    "mano.ns.terminate": _handle_mano_ns_terminate,
    "mano.vnf.create": _handle_mano_vnf_create,
    "mano.vnf.delete": _handle_mano_vnf_delete,
    "mano.vnf.exec": _handle_mano_vnf_exec,
    "mcp.request": _handle_mcp_request_action,
}


def _template_config(topology_id: Optional[str]) -> Dict[str, Any]:
    return {
        "schema": SUPPORTED_SCHEMA,
        "topology_id": topology_id or "",
        "dry_run": True,
        "actions": [
            {"id": "ensure-infra", "kind": "topology.infra.ensure", "params": {}},
            {"id": "start-emulation", "kind": "emulation.start", "params": {"options": {}}},
            {
                "id": "apply-network-config",
                "kind": "network_config.apply",
                "params": {
                    "config": {
                        "defaults": {
                            "sysctls": {},
                            "dns_servers": [],
                            "commands": [],
                        },
                        "devices": [],
                    },
                    "dry_run": True,
                },
            },
            {"id": "restart-controller", "kind": "sdn.controller.restart", "params": {"controller_id": "controller-1"}},
            {
                "id": "test-sdn-smoke",
                "kind": "mcp.request",
                "params": {
                    "method": "POST",
                    "path": "/api/orchestrator/tests/run",
                    "json": {"topology_id": topology_id or "", "suite": "sdn_smoke", "params": {}},
                },
            },
            {
                "id": "test-mano-smoke",
                "kind": "mcp.request",
                "params": {
                    "method": "POST",
                    "path": "/api/orchestrator/tests/run",
                    "json": {"topology_id": topology_id or "", "suite": "mano_local_smoke", "params": {}},
                },
            },
            {
                "id": "create-ns",
                "kind": "mano.ns.create",
                "params": {"name": "demo-ns", "backend": "local", "options": {}, "dry_run": True},
            },
        ],
        "meta": {"ui": {"name": "Control Config Template"}},
    }


@app.get("/api/template")
async def get_template(topology_id: Optional[str] = None) -> Dict[str, Any]:
    return _template_config(topology_id)


@app.post("/api/validate", response_model=ValidateResponse)
async def validate_config(request: Request) -> ValidateResponse:
    raw = await request.json()
    try:
        cfg = ControlConfig.model_validate(raw)
    except Exception as exc:
        return ValidateResponse(ok=False, schema=str(raw.get("schema") or ""), errors=[str(exc)], plan=[])

    errors: List[str] = []
    if cfg.schema != SUPPORTED_SCHEMA:
        errors.append(f"Unsupported schema '{cfg.schema}' (expected '{SUPPORTED_SCHEMA}')")

    plan: List[Dict[str, Any]] = []
    for idx, action in enumerate(cfg.actions):
        handler = HANDLERS.get(action.kind)
        if not handler:
            errors.append(f"Unknown action kind '{action.kind}' at actions[{idx}]")
            continue
        try:
            # Always build a plan entry (dry-run).
            planned = await handler(cfg.model_copy(update={"dry_run": True}), action.model_copy(update={"dry_run": True}))
            plan.append(planned.get("request") or {"kind": action.kind})
        except Exception as exc:
            errors.append(f"Invalid action '{action.kind}' at actions[{idx}]: {exc}")

    return ValidateResponse(ok=len(errors) == 0, schema=cfg.schema, errors=errors, plan=plan)


@app.post("/api/apply", response_model=ApplyResponse)
async def apply_config(cfg: ControlConfig) -> ApplyResponse:
    errors: List[str] = []
    if cfg.schema != SUPPORTED_SCHEMA:
        raise HTTPException(status_code=400, detail=f"Unsupported schema '{cfg.schema}' (expected '{SUPPORTED_SCHEMA}')")

    results: List[Dict[str, Any]] = []
    for idx, action in enumerate(cfg.actions):
        handler = HANDLERS.get(action.kind)
        if not handler:
            errors.append(f"Unknown action kind '{action.kind}' at actions[{idx}]")
            results.append(_build_result(action=action, dry_run=_effective_dry_run(cfg, action), request={"kind": action.kind}, error=errors[-1]))
            continue
        try:
            results.append(await handler(cfg, action))
        except HTTPException as exc:
            results.append(_build_result(action=action, dry_run=_effective_dry_run(cfg, action), request={"kind": action.kind}, error=str(exc.detail)))
        except Exception as exc:
            results.append(_build_result(action=action, dry_run=_effective_dry_run(cfg, action), request={"kind": action.kind}, error=str(exc)))

    ok = all(r.get("status") in {"success", "skipped"} for r in results)
    return ApplyResponse(ok=ok, schema=cfg.schema, results=results)
