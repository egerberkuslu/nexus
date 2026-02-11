"""
MCP Tool Hub - Port 8018

Registry and safe proxy for external MCP servers.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from shared.utils.consul_client import ConsulClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "mcp-tool-hub-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8018"))

MCP_REGISTRY_PREFIX = os.getenv("MCP_REGISTRY_PREFIX", "caduceus/mcp/servers")
MCP_TOPOLOGY_PREFIX = os.getenv("MCP_TOPOLOGY_PREFIX", "caduceus/topologies")
HTTP_TIMEOUT_SECONDS = float(os.getenv("MCP_TOOL_HUB_HTTP_TIMEOUT_SECONDS", "30"))

consul_client = ConsulClient()

app = FastAPI(
    title="Caduceus-Flux MCP Tool Hub",
    description="Registry and safe proxy for external MCP servers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SENSITIVE_KEY_RE = re.compile(r"(password|token|secret|api[_-]?key|private[_-]?key|authorization)", re.IGNORECASE)


class MCPServerConfig(BaseModel):
    name: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    transport: Literal["http"] = "http"
    scope: Literal["shared", "topology"] = "shared"
    topology_id: Optional[str] = None
    read_only: bool = True
    allowed_methods: List[str] = Field(default_factory=list)
    allowed_path_prefixes: List[str] = Field(default_factory=list)
    blocked_path_prefixes: List[str] = Field(default_factory=list)
    allowed_write_prefixes: List[str] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)
    profile: Optional[str] = None
    notes: Optional[str] = None


class MCPProxyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    server: str = Field(..., min_length=1)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    path: str = "/"
    query: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    json_body: Optional[Any] = Field(default=None, alias="json")
    data: Optional[str] = None
    timeout_seconds: Optional[float] = None
    topology_id: Optional[str] = None


MCP_SERVER_PROFILES: Dict[str, Dict[str, Any]] = {
    "grafana": {
        "description": "Grafana API (dashboards/datasources writes are optional).",
        "allowed_write_prefixes": ["/api/dashboards", "/api/datasources", "/api/folders"],
    },
    "influxdb": {
        "description": "InfluxDB API (writes should target the topology bucket).",
        "allowed_write_prefixes": ["/api/v2/write", "/api/v2/delete"],
    },
    "consul": {
        "description": "Consul KV and service discovery (restrict writes to caduceus/ paths).",
        "allowed_write_prefixes": ["/v1/kv/caduceus", "/v1/kv/caduceus/"],
    },
    "kafka": {
        "description": "Kafka Admin API (writes should be namespace-scoped).",
        "allowed_write_prefixes": ["/admin", "/kafka"],
    },
    "rabbitmq": {
        "description": "RabbitMQ Management API (limit to topology vhost).",
        "allowed_write_prefixes": ["/api/queues", "/api/exchanges", "/api/bindings"],
    },
    "prometheus": {
        "description": "Prometheus query API (read-only).",
        "allowed_write_prefixes": [],
    },
    "onos": {
        "description": "ONOS control API (topology-scoped controller).",
        "allowed_write_prefixes": ["/onos/v1/flows", "/onos/v1/devices", "/onos/v1/links"],
    },
}


@app.on_event("startup")
async def _startup() -> None:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS))
    logger.info("MCP Tool Hub started: %s:%s", SERVICE_NAME, SERVICE_PORT)


@app.on_event("shutdown")
async def _shutdown() -> None:
    http: httpx.AsyncClient = app.state.http
    await http.aclose()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _registry_key(name: str, topology_id: Optional[str]) -> str:
    if topology_id:
        return f"{MCP_TOPOLOGY_PREFIX}/{topology_id}/mcp/servers/{name}"
    return f"{MCP_REGISTRY_PREFIX}/{name}"


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in (headers or {}).items():
        if _SENSITIVE_KEY_RE.search(str(k)):
            out[str(k)] = "*****"
        else:
            out[str(k)] = str(v)
    return out


def _redact_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(raw or {})
    headers = cfg.get("headers")
    if isinstance(headers, dict):
        cfg["headers"] = _redact_headers(headers)
    return cfg


def _parse_consul_value(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = value.decode("utf-8", errors="replace")
    else:
        raw = str(value)
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _normalize_prefixes(values: List[str]) -> List[str]:
    out: List[str] = []
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        if not s.startswith("/"):
            s = "/" + s
        out.append(s)
    return out


def _apply_profile_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    profile = cfg.get("profile")
    if not profile:
        return cfg
    defaults = MCP_SERVER_PROFILES.get(str(profile))
    if not defaults:
        return cfg
    merged = dict(cfg)
    for key, value in defaults.items():
        if key == "description":
            continue
        existing = merged.get(key)
        if existing in (None, [], "", {}):
            merged[key] = value
    if not merged.get("notes") and defaults.get("description"):
        merged["notes"] = defaults["description"]
    return merged


def _list_registry(prefix: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        _, data = consul_client.client.kv.get(prefix, recurse=True)
    except Exception as exc:
        logger.warning("Failed to list registry under %s: %s", prefix, exc)
        return out
    if not data:
        return out
    for item in data:
        key = item.get("Key")
        value = _parse_consul_value(item.get("Value"))
        if not key or not value:
            continue
        name = value.get("name")
        if not name:
            name = str(key).split("/")[-1]
            value["name"] = name
        out.append(value)
    return out


def _load_config(name: str, topology_id: Optional[str], fallback_shared: bool = True) -> Optional[Dict[str, Any]]:
    key = _registry_key(name, topology_id)
    raw = consul_client.get_config(key)
    cfg = _parse_consul_value(raw)
    if cfg:
        return _apply_profile_defaults(cfg)
    if topology_id and fallback_shared:
        raw = consul_client.get_config(_registry_key(name, None))
        cfg = _parse_consul_value(raw)
        if cfg:
            return _apply_profile_defaults(cfg)
    return None


def _allowed_methods(cfg: MCPServerConfig) -> List[str]:
    if cfg.allowed_methods:
        return [m.upper() for m in cfg.allowed_methods]
    if cfg.read_only:
        return ["GET", "HEAD"]
    return ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def _join_url(base_url: str, path: str) -> str:
    base = str(base_url).rstrip("/")
    p = str(path or "/")
    if not p.startswith("/"):
        p = "/" + p
    return base + p


def _as_server_config(name: str, payload: Dict[str, Any]) -> MCPServerConfig:
    cfg = _apply_profile_defaults(dict(payload or {}))
    cfg.setdefault("name", name)
    return MCPServerConfig(**cfg)


def _store_config(cfg: MCPServerConfig) -> None:
    resolved = _apply_profile_defaults(cfg.model_dump())
    key = _registry_key(cfg.name, cfg.topology_id if cfg.scope == "topology" else None)
    consul_client.set_config(key, json.dumps(resolved))


def _delete_config(name: str, topology_id: Optional[str]) -> None:
    key = _registry_key(name, topology_id)
    try:
        consul_client.client.kv.delete(key)
    except Exception as exc:
        logger.warning("Failed to delete %s: %s", key, exc)


@app.get("/api/mcp/servers")
async def list_servers(
    topology_id: Optional[str] = None,
    include_shared: bool = True,
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if topology_id:
        items.extend(_list_registry(_registry_key("", topology_id).rstrip("/")))
    if include_shared or not topology_id:
        items.extend(_list_registry(MCP_REGISTRY_PREFIX))

    redacted = [_redact_config(i) for i in items]
    return {"items": redacted, "total": len(redacted)}


@app.get("/api/mcp/profiles")
async def list_profiles() -> Dict[str, Any]:
    items = []
    for name, meta in MCP_SERVER_PROFILES.items():
        items.append({"name": name, **meta})
    return {"items": items, "total": len(items)}


@app.get("/api/mcp/servers/{name}")
async def get_server(name: str, topology_id: Optional[str] = None, fallback_shared: bool = True) -> Dict[str, Any]:
    cfg = _load_config(name, topology_id, fallback_shared=fallback_shared)
    if not cfg:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return _redact_config(cfg)


@app.put("/api/mcp/servers/{name}")
async def put_server(name: str, payload: MCPServerConfig) -> Dict[str, Any]:
    if payload.name != name:
        raise HTTPException(status_code=400, detail="Server name mismatch")
    if payload.scope == "topology" and not payload.topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required for topology-scoped servers")
    if payload.scope == "shared":
        payload.topology_id = None
    _store_config(payload)
    return {"ok": True, "server": _redact_config(payload.model_dump())}


@app.delete("/api/mcp/servers/{name}")
async def delete_server(name: str, topology_id: Optional[str] = None) -> Dict[str, Any]:
    _delete_config(name, topology_id)
    return {"ok": True, "deleted": name, "topology_id": topology_id}


@app.get("/api/mcp/{topology_id}/servers")
async def list_servers_scoped(topology_id: str, include_shared: bool = False) -> Dict[str, Any]:
    return await list_servers(topology_id=topology_id, include_shared=include_shared)


@app.get("/api/mcp/{topology_id}/servers/{name}")
async def get_server_scoped(topology_id: str, name: str, fallback_shared: bool = False) -> Dict[str, Any]:
    return await get_server(name=name, topology_id=topology_id, fallback_shared=fallback_shared)


@app.put("/api/mcp/{topology_id}/servers/{name}")
async def put_server_scoped(topology_id: str, name: str, payload: MCPServerConfig) -> Dict[str, Any]:
    if payload.name != name:
        raise HTTPException(status_code=400, detail="Server name mismatch")
    payload.scope = "topology"
    payload.topology_id = topology_id
    _store_config(payload)
    return {"ok": True, "server": _redact_config(payload.model_dump())}


@app.delete("/api/mcp/{topology_id}/servers/{name}")
async def delete_server_scoped(topology_id: str, name: str) -> Dict[str, Any]:
    _delete_config(name, topology_id)
    return {"ok": True, "deleted": name, "topology_id": topology_id}


@app.post("/api/mcp/proxy")
async def proxy_request(req: MCPProxyRequest) -> Dict[str, Any]:
    cfg_raw = _load_config(req.server, req.topology_id, fallback_shared=True)
    if not cfg_raw:
        raise HTTPException(status_code=404, detail="MCP server not found")

    cfg = _as_server_config(req.server, cfg_raw)
    if cfg.scope == "topology" and cfg.topology_id and req.topology_id != cfg.topology_id:
        raise HTTPException(status_code=403, detail="Topology scope mismatch")

    method = req.method.upper()
    allowed_methods = _allowed_methods(cfg)
    if method not in allowed_methods:
        raise HTTPException(status_code=403, detail=f"Method {method} is not allowed for {cfg.name}")

    req_path = "/" + str(req.path or "/").lstrip("/")
    blocked = _normalize_prefixes(cfg.blocked_path_prefixes)
    if blocked and any(req_path.startswith(p) for p in blocked):
        raise HTTPException(status_code=403, detail="Path is blocked by policy")

    allowed_write = _normalize_prefixes(cfg.allowed_write_prefixes)
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        if cfg.read_only and not cfg.allowed_methods:
            raise HTTPException(status_code=403, detail="Write operations are not allowed for this server")
        if allowed_write and not any(req_path.startswith(p) for p in allowed_write):
            raise HTTPException(status_code=403, detail="Write path is not allowed by policy")

    allowed_paths = _normalize_prefixes(cfg.allowed_path_prefixes)
    if allowed_paths and not any(req_path.startswith(p) for p in allowed_paths):
        raise HTTPException(status_code=403, detail="Path is not allowed by policy")

    url = _join_url(cfg.base_url, req_path)
    headers = dict(cfg.headers or {})
    headers.update(req.headers or {})

    http: httpx.AsyncClient = app.state.http
    timeout = req.timeout_seconds or HTTP_TIMEOUT_SECONDS

    try:
        resp = await http.request(
            method,
            url,
            params=req.query or None,
            json=req.json_body,
            content=req.data,
            headers=headers,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream MCP server timeout")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream MCP server error: {exc}")

    content_type = (resp.headers.get("content-type") or "").lower()
    if method == "HEAD":
        body: Any = None
    elif "application/json" in content_type:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    else:
        body = resp.text

    resp_headers = {k: v for k, v in resp.headers.items() if not _SENSITIVE_KEY_RE.search(k)}

    return {
        "status_code": resp.status_code,
        "headers": _redact_headers(resp_headers),
        "body": body,
        "meta": {
            "server": cfg.name,
            "url": url,
            "method": method,
            "read_only": cfg.read_only,
        },
    }


@app.post("/api/mcp/{topology_id}/proxy")
async def proxy_request_scoped(topology_id: str, req: MCPProxyRequest) -> Dict[str, Any]:
    if req.topology_id and req.topology_id != topology_id:
        raise HTTPException(status_code=403, detail="Topology scope mismatch")
    req.topology_id = topology_id
    return await proxy_request(req)
