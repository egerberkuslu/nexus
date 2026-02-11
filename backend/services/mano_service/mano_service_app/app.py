"""
MANO Service (OSM-like) - HTTP Port 8015 + gRPC Port 50052

- HTTP endpoints are consumed via MCP gateway (/api/mano/*).
- gRPC endpoints allow low-latency, strongly-typed control.

Implements a minimal OSM-like core:
- Catalog: VNFD/NSD store (JSON descriptors)
- NFVO-ish: NS instance lifecycle backed by DB
- Southbound: can call other services via MCP gateway or direct HTTP
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
import grpc
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Literal

from shared.database.postgres import SessionLocal, get_db, init_db
from shared.models.mano import ManoNSD, ManoNSInstance, ManoOperation, ManoVNFD
from shared.models.mano_external import ManoExternalResource
from shared.models.mano_vnfm import ManoVNFInstance
from shared.utils.consul_client import ConsulClient

import mano_pb2  # generated in Docker build
import mano_pb2_grpc  # generated in Docker build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8015"))
GRPC_PORT = int(os.getenv("MANO_GRPC_PORT", "50052"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "mano-service")

MCP_SERVER_URL = (os.getenv("MCP_SERVER_URL", "http://mcp-server:8012") or "").rstrip("/")
ORCHESTRATOR_URL = (os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002") or "").rstrip("/")
DEVICE_MANAGER_URL = (os.getenv("DEVICE_MANAGER_URL", "http://device-manager-service:8004") or "").rstrip("/")
SOUTHBOUND_MODE = (os.getenv("MANO_SOUTHBOUND_MODE", "mcp") or "mcp").strip().lower()
NFVO_BACKEND_DEFAULT = (os.getenv("MANO_NFVO_BACKEND", "local") or "local").strip().lower()

OSM_NBI_URL = (os.getenv("OSM_NBI_URL", "") or "").rstrip("/")
OSM_USERNAME = os.getenv("OSM_USERNAME", "")
OSM_PASSWORD = os.getenv("OSM_PASSWORD", "")
OSM_PROJECT_ID = os.getenv("OSM_PROJECT_ID", "")  # optional
OSM_TOKEN = os.getenv("OSM_TOKEN", "")
OSM_CONNECTOR_URL = (os.getenv("OSM_CONNECTOR_URL", "http://osm-connector-service:8020") or "").rstrip("/")
OSM_MODE = (os.getenv("MANO_OSM_MODE", "connector") or "connector").strip().lower()  # connector|direct

OSM_MIRROR_ENABLED = (os.getenv("MANO_OSM_MIRROR_ENABLED", "true") or "true").strip().lower() in ("1", "true", "yes", "y", "on")
OSM_MIRROR_INTERVAL_SECONDS = int(os.getenv("MANO_OSM_MIRROR_INTERVAL_SECONDS", "30") or "30")
OSM_MIRROR_MAX_TOPOLOGIES = int(os.getenv("MANO_OSM_MIRROR_MAX_TOPOLOGIES", "50") or "50")

app = FastAPI(
    title="Caduceus-Flux MANO Service",
    description="OSM-like MANO microservice (catalog + NS lifecycle + southbound adapters)",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

consul_client = ConsulClient()

_osm_mirror_task: Optional[asyncio.Task] = None
_osm_mirror_lock: Optional[asyncio.Lock] = None


def _now_ms() -> int:
    return int(time.time() * 1000)

def _dt_to_ms(value: Optional[datetime]) -> int:
    if not value:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _db_session() -> Session:
    return SessionLocal()


def _json_checksum(value: Any) -> str:
    import hashlib

    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    except Exception:
        raw = json.dumps(str(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _osm_epoch_to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        ts = float(value)
    except Exception:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _pick_first_str(obj: Any, keys: List[str]) -> str:
    if not isinstance(obj, dict):
        return ""
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


async def _mcp_get_json(http: httpx.AsyncClient, path: str, *, params: Optional[dict] = None) -> Any:
    url = f"{MCP_SERVER_URL}{path}"
    resp = await http.get(url, params=params or None)
    resp.raise_for_status()
    if not resp.content:
        return None
    return resp.json()


async def _mcp_post_json(http: httpx.AsyncClient, path: str, payload: Any) -> Any:
    url = f"{MCP_SERVER_URL}{path}"
    resp = await http.post(url, json=payload)
    resp.raise_for_status()
    if not resp.content:
        return None
    return resp.json()


def _mirror_upsert(
    db: Session,
    *,
    topology_id: str,
    resource_type: str,
    external_id: str,
    name: str,
    payload: Any,
    now: datetime,
) -> Tuple[str, bool]:
    """
    Upsert a mirrored OSM resource into mano_external_resource.

    Returns (row_id, changed).
    """
    backend = "osm"
    checksum = _json_checksum(payload)
    row = (
        db.query(ManoExternalResource)
        .filter(
            ManoExternalResource.backend == backend,
            ManoExternalResource.topology_id == topology_id,
            ManoExternalResource.resource_type == resource_type,
            ManoExternalResource.external_id == external_id,
        )
        .one_or_none()
    )
    if row is None:
        row = ManoExternalResource(
            id=uuid.uuid4().hex,
            backend=backend,
            topology_id=topology_id,
            resource_type=resource_type,
            external_id=external_id,
            name=name or None,
            payload=payload or {},
            checksum=checksum,
            deleted=False,
            first_seen_at=now,
            last_seen_at=now,
            updated_at=now,
        )
        db.add(row)
        return row.id, True

    changed = False
    if (row.checksum or "") != checksum:
        row.payload = payload or {}
        row.checksum = checksum
        changed = True
    if (row.name or "") != (name or ""):
        row.name = name or None
        changed = True
    if bool(getattr(row, "deleted", False)):
        row.deleted = False
        changed = True
    row.last_seen_at = now
    if changed:
        row.updated_at = now
    return row.id, changed


def _mirror_mark_deleted(
    db: Session,
    *,
    topology_id: str,
    resource_type: str,
    keep_external_ids: List[str],
    now: datetime,
) -> int:
    backend = "osm"
    q = db.query(ManoExternalResource).filter(
        ManoExternalResource.backend == backend,
        ManoExternalResource.topology_id == topology_id,
        ManoExternalResource.resource_type == resource_type,
        ManoExternalResource.deleted.is_(False),
    )
    if keep_external_ids:
        q = q.filter(~ManoExternalResource.external_id.in_(keep_external_ids))
    rows = q.all()
    for r in rows:
        r.deleted = True
        r.updated_at = now
    return len(rows)


async def _sync_osm_topology(
    *,
    topology_id: str,
    resources: List[str],
    mark_deleted: bool,
) -> Dict[str, Any]:
    """
    Pull OSM state via MCP (/api/osm/{topology_id}/...) and mirror it into Postgres.
    Also upserts core MANO tables (VNFD/NSD/NS) to make the project-side view consistent.
    """
    http: httpx.AsyncClient = app.state.http
    now = datetime.utcnow()
    db = _db_session()
    try:
        summary: Dict[str, Any] = {"topology_id": topology_id, "backend": "osm", "synced": {}, "errors": []}

        async def _fetch_list(path: str) -> Optional[list]:
            try:
                data = await _mcp_get_json(http, f"/api/osm/{topology_id}{path}")
                return data if isinstance(data, list) else None
            except Exception as exc:
                summary["errors"].append({"path": path, "error": str(exc)})
                return None

        # Resource fetchers (name + id extraction differs per type)
        fetch_plan = {
            "projects": ("/projects", "osm_project", ["_id", "id"], ["name"]),
            "vim_accounts": ("/vim-accounts", "vim_account", ["_id", "id"], ["name"]),
            "wim_accounts": ("/wim-accounts", "wim_account", ["_id", "id"], ["name"]),
            "sdns": ("/proxy/admin/v1/sdns", "sdn_controller", ["_id", "id"], ["name"]),
            "vnfd_packages": ("/vnfd-packages", "vnfd_package", ["_id", "id"], ["name", "id", "product-name"]),
            "nsd_packages": ("/nsd-packages", "nsd_package", ["_id", "id"], ["name", "id"]),
            "ns_instances": ("/ns-instances", "ns_instance", ["_id", "id"], ["name", "nsName"]),
            "ns_lcm_op_occs": ("/ns-lcm-op-occs", "ns_lcm_op_occ", ["id", "_id"], ["lcmOperationType", "operationState"]),
        }

        requested = [r for r in (resources or []) if r in fetch_plan]
        if not requested:
            requested = ["projects", "vim_accounts", "wim_accounts", "sdns", "vnfd_packages", "nsd_packages", "ns_instances"]

        for key in requested:
            path, rtype, id_keys, name_keys = fetch_plan[key]
            items = await _fetch_list(path)
            if items is None:
                continue

            seen: List[str] = []
            created = 0
            updated = 0

            for item in items:
                if not isinstance(item, dict):
                    continue
                external_id = _pick_first_str(item, id_keys)
                if not external_id:
                    continue
                name = _pick_first_str(item, name_keys)
                _, changed = _mirror_upsert(
                    db,
                    topology_id=topology_id,
                    resource_type=rtype,
                    external_id=external_id,
                    name=name,
                    payload=item,
                    now=now,
                )
                seen.append(external_id)
                if changed:
                    # Best-effort: count create vs update by checking if we just inserted.
                    # (changed=True for inserts too; we can distinguish by querying once, but keep simple.)
                    updated += 1

            deleted_count = 0
            if mark_deleted:
                deleted_count = _mirror_mark_deleted(db, topology_id=topology_id, resource_type=rtype, keep_external_ids=seen, now=now)

            summary["synced"][key] = {
                "resource_type": rtype,
                "seen": len(seen),
                "updated": updated,
                "marked_deleted": deleted_count,
            }

            # Optional: also upsert into core MANO tables for unified project-side listing.
            if key == "vnfd_packages":
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pkg_id = _pick_first_str(item, ["_id", "id"])
                    if not pkg_id:
                        continue
                    row = db.get(ManoVNFD, pkg_id)
                    if row is None:
                        row = ManoVNFD(id=pkg_id, created_at=now)
                        db.add(row)
                    row.name = _pick_first_str(item, ["name", "id", "product-name"]) or pkg_id
                    row.version = _pick_first_str(item, ["version"]) or "1.0"
                    row.provider = _pick_first_str(item, ["provider", "designer"]) or "osm"
                    row.descriptor = item
                    row.updated_at = now

            if key == "nsd_packages":
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    pkg_id = _pick_first_str(item, ["_id", "id"])
                    if not pkg_id:
                        continue
                    row = db.get(ManoNSD, pkg_id)
                    if row is None:
                        row = ManoNSD(id=pkg_id, created_at=now)
                        db.add(row)
                    row.name = _pick_first_str(item, ["name", "id"]) or pkg_id
                    row.version = _pick_first_str(item, ["version"]) or "1.0"
                    row.provider = _pick_first_str(item, ["provider", "designer"]) or "osm"
                    row.descriptor = item
                    row.updated_at = now

            if key == "ns_instances":
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    ns_id = _pick_first_str(item, ["_id", "id"])
                    if not ns_id:
                        continue
                    row = db.get(ManoNSInstance, ns_id)
                    if row is None:
                        row = ManoNSInstance(id=ns_id, created_at=now)
                        db.add(row)
                    row.name = _pick_first_str(item, ["name", "nsName"]) or ns_id
                    row.topology_id = topology_id
                    row.backend = "osm"
                    row.external_id = ns_id
                    row.external_ref = {"osm": item}
                    row.nsd_id = _pick_first_str(item, ["nsd-ref", "nsd-id", "nsdId"]) or None
                    row.status = _pick_first_str(item, ["nsState", "operational-status", "admin-status"]) or "UNKNOWN"
                    row.message = _pick_first_str(item, ["detailed-status", "errorDescription", "errorDetail"]) or None
                    created_at = _osm_epoch_to_dt(item.get("create-time")) or now
                    row.created_at = row.created_at or created_at
                    row.updated_at = now

            if key == "ns_lcm_op_occs":
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    op_id = _pick_first_str(item, ["id", "_id"])
                    if not op_id:
                        continue
                    row = db.get(ManoOperation, op_id)
                    if row is None:
                        row = ManoOperation(id=op_id, created_at=now)
                        db.add(row)
                    row.ns_instance_id = _pick_first_str(item, ["nsInstanceId"]) or None
                    row.kind = (_pick_first_str(item, ["lcmOperationType"]) or "osm").upper()
                    row.status = (_pick_first_str(item, ["operationState"]) or "UNKNOWN").upper()
                    row.message = _pick_first_str(item, ["error", "detailedStatus"]) or None
                    row.request = item.get("operationParams") if isinstance(item.get("operationParams"), dict) else {}
                    row.result = item
                    row.started_at = _osm_epoch_to_dt(item.get("startTime")) or row.started_at or now
                    row.finished_at = _osm_epoch_to_dt(item.get("endTime")) or row.finished_at
                    row.created_at = row.created_at or now

        db.commit()
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class OsmMirrorSyncRequest(BaseModel):
    topology_id: str = Field(..., min_length=1)
    resources: List[str] = Field(default_factory=list)
    mark_deleted: bool = True


class OsmReconcileRequest(BaseModel):
    topology_id: str = Field(..., min_length=1)
    ensure_osm_stack: bool = True
    sync_after: bool = True
    resources: List[str] = Field(default_factory=list)
    mark_deleted: bool = True


@app.post("/api/osm/reconcile")
@app.post("/api/mano/osm/reconcile")
async def osm_reconcile(payload: OsmReconcileRequest) -> Dict[str, Any]:
    topo_id = (payload.topology_id or "").strip()
    if not topo_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    http: httpx.AsyncClient = app.state.http
    out: Dict[str, Any] = {"topology_id": topo_id, "ensure": None, "sync": None, "errors": []}

    if payload.ensure_osm_stack:
        try:
            out["ensure"] = await _mcp_post_json(http, f"/api/infrastructure/topologies/{topo_id}/osm/ensure", {})
        except Exception as exc:
            out["errors"].append({"step": "ensure_osm_stack", "error": str(exc)})

    if payload.sync_after:
        global _osm_mirror_lock
        if _osm_mirror_lock is None:
            _osm_mirror_lock = asyncio.Lock()
        async with _osm_mirror_lock:
            try:
                out["sync"] = await _sync_osm_topology(
                    topology_id=topo_id,
                    resources=payload.resources,
                    mark_deleted=bool(payload.mark_deleted),
                )
            except Exception as exc:
                out["errors"].append({"step": "sync_after", "error": str(exc)})

    return out


@app.post("/api/osm/sync")
@app.post("/api/mano/osm/sync")
async def osm_mirror_sync(payload: OsmMirrorSyncRequest) -> Dict[str, Any]:
    topo_id = (payload.topology_id or "").strip()
    if not topo_id:
        raise HTTPException(status_code=400, detail="topology_id is required")
    global _osm_mirror_lock
    if _osm_mirror_lock is None:
        _osm_mirror_lock = asyncio.Lock()
    async with _osm_mirror_lock:
        return await _sync_osm_topology(topology_id=topo_id, resources=payload.resources, mark_deleted=bool(payload.mark_deleted))


@app.get("/api/osm/mirror/stats")
@app.get("/api/mano/osm/mirror/stats")
async def osm_mirror_stats(topology_id: Optional[str] = None, include_deleted: bool = False, db: Session = Depends(get_db)) -> Dict[str, Any]:
    q = db.query(ManoExternalResource.backend, ManoExternalResource.resource_type, ManoExternalResource.deleted)
    if topology_id:
        q = q.filter(ManoExternalResource.topology_id == topology_id)
    if not include_deleted:
        q = q.filter(ManoExternalResource.deleted.is_(False))
    rows = q.all()
    counts: Dict[str, int] = {}
    for backend, rtype, deleted in rows:
        key = f"{backend}:{rtype}" + (":deleted" if deleted else "")
        counts[key] = counts.get(key, 0) + 1
    return {"topology_id": topology_id, "include_deleted": include_deleted, "counts": counts}


@app.get("/api/osm/mirror/resources")
@app.get("/api/mano/osm/mirror/resources")
async def osm_mirror_resources(
    topology_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    backend: str = "osm",
    include_deleted: bool = False,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(ManoExternalResource).filter(ManoExternalResource.backend == backend)
    if topology_id:
        q = q.filter(ManoExternalResource.topology_id == topology_id)
    if resource_type:
        q = q.filter(ManoExternalResource.resource_type == resource_type)
    if not include_deleted:
        q = q.filter(ManoExternalResource.deleted.is_(False))
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    rows = q.order_by(ManoExternalResource.updated_at.desc()).offset(offset).limit(limit).all()
    items = [
        {
            "id": r.id,
            "backend": r.backend,
            "topology_id": r.topology_id,
            "resource_type": r.resource_type,
            "external_id": r.external_id,
            "name": r.name,
            "deleted": bool(r.deleted),
            "checksum": r.checksum,
            "first_seen_at_ms": _dt_to_ms(r.first_seen_at),
            "last_seen_at_ms": _dt_to_ms(r.last_seen_at),
            "updated_at_ms": _dt_to_ms(r.updated_at),
            "payload": r.payload,
        }
        for r in rows
    ]
    return {"items": items, "limit": limit, "offset": offset}


class SouthboundClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def emulation_start(self, topology_id: str, options: Optional[dict] = None) -> dict:
        payload = {"topology_id": topology_id, "options": options or {}}
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/start"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/start"
        resp = await self.http.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def emulation_stop(self, emulation_id: str, payload: Optional[dict] = None) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/stop/{emulation_id}"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/stop/{emulation_id}"
        resp = await self.http.post(url, json=payload or {})
        resp.raise_for_status()
        return resp.json()

    async def device_add(self, *, name: str, device_type: str, properties: dict, topology_id: Optional[str] = None) -> dict:
        payload = {"name": name, "device_type": device_type, "properties": properties or {}}
        if SOUTHBOUND_MODE == "direct":
            url = f"{DEVICE_MANAGER_URL}/api/devices"
        else:
            url = f"{MCP_SERVER_URL}/api/devices"
        params = {"topology_id": topology_id} if topology_id else None
        resp = await self.http.post(url, json=payload, params=params)
        resp.raise_for_status()
        return resp.json()

    async def device_exec(self, device_name: str, command: str) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{DEVICE_MANAGER_URL}/api/devices/{device_name}/execute"
        else:
            url = f"{MCP_SERVER_URL}/api/devices/{device_name}/execute"
        resp = await self.http.post(url, params={"command": command})
        resp.raise_for_status()
        return resp.json()

    async def device_remove(self, device_name: str) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{DEVICE_MANAGER_URL}/api/devices/{device_name}"
        else:
            url = f"{MCP_SERVER_URL}/api/devices/{device_name}"
        resp = await self.http.delete(url)
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}

    async def link_add(self, *, topology_id: str, node1: str, node2: str, properties: Optional[dict] = None) -> dict:
        payload = {"topology_id": topology_id, "node1": node1, "node2": node2}
        if properties:
            payload.update(properties)
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/links/add"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/links/add"
        resp = await self.http.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def emulation_active(self) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/active"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/active"
        resp = await self.http.get(url)
        resp.raise_for_status()
        return resp.json()

    async def emulation_list_devices(self, *, topology_id: Optional[str] = None, emulation_id: Optional[str] = None) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/devices"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/devices"
        params: Dict[str, Any] = {}
        if topology_id:
            params["topology_id"] = topology_id
        if emulation_id:
            params["emulation_id"] = emulation_id
        resp = await self.http.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def emulation_list_containers(self, *, topology_id: Optional[str] = None, include_stopped: bool = False) -> dict:
        if SOUTHBOUND_MODE == "direct":
            url = f"{ORCHESTRATOR_URL}/api/emulation/containers"
        else:
            url = f"{MCP_SERVER_URL}/api/emulation/containers"
        params: Dict[str, Any] = {"include_stopped": bool(include_stopped)}
        if topology_id:
            params["topology_id"] = topology_id
        resp = await self.http.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


class OsmClient:
    """
    Minimal ETSI OSM client.

    Supports two execution modes:
    - topology-scoped via MCP: /api/osm/{topology_id}/... (preferred for isolated per-topology OSM)
    - global connector: OSM_CONNECTOR_URL (/api/osm/...)
    - direct NBI: OSM_NBI_URL (SOL005 paths)
    """

    def __init__(self, http: httpx.AsyncClient, *, topology_id: Optional[str] = None):
        self.http = http
        self.topology_id = (topology_id or "").strip() or None

    def _use_topology_scope(self) -> bool:
        return bool(self.topology_id)

    def _use_connector(self) -> bool:
        if OSM_MODE != "connector":
            return False
        # If topology_id is provided, we can always route via MCP to the per-topology connector.
        if self._use_topology_scope():
            return True
        return bool(OSM_CONNECTOR_URL)

    def _base_direct(self) -> str:
        if not OSM_NBI_URL:
            raise RuntimeError("OSM_NBI_URL is not configured")
        return OSM_NBI_URL

    def _base_connector(self) -> str:
        if self._use_topology_scope():
            # Route through MCP so we automatically hit the correct per-topology connector.
            return f"{MCP_SERVER_URL}/api/osm/{self.topology_id}"
        if not OSM_CONNECTOR_URL:
            raise RuntimeError("OSM_CONNECTOR_URL is not configured")
        return f"{OSM_CONNECTOR_URL}/api/osm"

    async def _token(self) -> str:
        if self._use_connector():
            return ""
        if (OSM_TOKEN or "").strip():
            return (OSM_TOKEN or "").strip()
        if not (OSM_USERNAME and OSM_PASSWORD):
            raise RuntimeError("OSM token missing (set OSM_TOKEN or OSM_USERNAME/OSM_PASSWORD)")
        url = f"{self._base_direct()}/admin/v1/tokens"
        payload: Dict[str, Any] = {"username": OSM_USERNAME, "password": OSM_PASSWORD}
        if (OSM_PROJECT_ID or "").strip():
            payload["project_id"] = (OSM_PROJECT_ID or "").strip()
        resp = await self.http.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        token = (
            (data.get("id") if isinstance(data, dict) else None)
            or (data.get("_id") if isinstance(data, dict) else None)
            or (data.get("token") if isinstance(data, dict) else None)
            or resp.headers.get("id")
            or resp.headers.get("X-Subject-Token")
        )
        if not token:
            raise RuntimeError("OSM token response did not include token id")
        return str(token)

    async def _request_direct(self, method: str, path: str, *, json_body: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        base = self._base_direct()
        url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
        token = await self._token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = await self.http.request(method.upper(), url, json=json_body, params=params, headers=headers)
        resp.raise_for_status()
        if not resp.content:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    async def _request_connector(self, method: str, path: str, *, json_body: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        base = self._base_connector()
        url_path = path if path.startswith("/") else f"/{path}"
        url = f"{base}{url_path}"
        resp = await self.http.request(method.upper(), url, json=json_body, params=params)
        resp.raise_for_status()
        if not resp.content:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    async def create_ns(self, *, ns_name: str, nsd_id: str, description: str = "") -> str:
        if self._use_connector():
            body = {"nsd_id": nsd_id, "name": ns_name, "description": description}
            data = await self._request_connector("POST", "/ns-instances", json_body=body)
            external_id = (data.get("id") if isinstance(data, dict) else None) or (data.get("_id") if isinstance(data, dict) else None)
        else:
            body = {"nsdId": nsd_id, "nsName": ns_name, "nsDescription": description}
            data = await self._request_direct("POST", "/nslcm/v1/ns_instances", json_body=body)
            external_id = (data.get("id") if isinstance(data, dict) else None) or (data.get("_id") if isinstance(data, dict) else None)
        if not external_id:
            raise RuntimeError("OSM create ns_instances did not return id")
        return str(external_id)

    async def instantiate_ns(self, *, ns_instance_id: str, params: Optional[dict] = None) -> dict:
        if self._use_connector():
            return await self._request_connector("POST", f"/ns-instances/{ns_instance_id}/instantiate", json_body=params or {})
        return await self._request_direct("POST", f"/nslcm/v1/ns_instances/{ns_instance_id}/instantiate", json_body=params or {})

    async def terminate_ns(self, *, ns_instance_id: str, params: Optional[dict] = None) -> dict:
        if self._use_connector():
            return await self._request_connector("POST", f"/ns-instances/{ns_instance_id}/terminate", json_body=params or {})
        return await self._request_direct("POST", f"/nslcm/v1/ns_instances/{ns_instance_id}/terminate", json_body=params or {})

    async def get_ns(self, *, ns_instance_id: str) -> dict:
        if self._use_connector():
            return await self._request_connector("GET", f"/ns-instances/{ns_instance_id}")
        return await self._request_direct("GET", f"/nslcm/v1/ns_instances/{ns_instance_id}")


class NsInstanceCreateHttp(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    nsd_id: Optional[str] = None
    topology_id: Optional[str] = Field(default=None, max_length=64)
    options: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    backend: Optional[Literal["local", "osm"]] = None


class NsInstanceHttp(BaseModel):
    id: str
    name: str
    topology_id: Optional[str] = None
    nsd_id: Optional[str] = None
    emulation_id: Optional[str] = None
    backend: str = "local"
    external_id: Optional[str] = None
    status: str
    created_at_ms: int
    updated_at_ms: int
    message: str = ""


class TerminateHttp(BaseModel):
    reason: str = ""


class VnfInstanceCreateHttp(BaseModel):
    ns_instance_id: str = Field(..., min_length=1, max_length=64)
    vnfd_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(default="container", min_length=1, max_length=32)
    device_name: Optional[str] = Field(default=None, max_length=255)
    properties: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class VnfInstanceHttp(BaseModel):
    id: str
    ns_instance_id: Optional[str] = None
    vnfd_id: Optional[str] = None
    name: str
    device_type: str
    device_name: Optional[str] = None
    status: str
    created_at_ms: int
    updated_at_ms: int
    message: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExecHttp(BaseModel):
    command: str = Field(..., min_length=1)


class DescriptorUpsert(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(default="1.0", min_length=1, max_length=64)
    provider: Optional[str] = Field(default=None, max_length=255)
    descriptor: Dict[str, Any] = Field(default_factory=dict)


def _ns_to_http(ns: ManoNSInstance) -> NsInstanceHttp:
    return NsInstanceHttp(
        id=ns.id,
        name=ns.name,
        topology_id=ns.topology_id,
        nsd_id=ns.nsd_id,
        emulation_id=ns.emulation_id,
        backend=getattr(ns, "backend", None) or "local",
        external_id=getattr(ns, "external_id", None),
        status=ns.status,
        created_at_ms=_dt_to_ms(ns.created_at),
        updated_at_ms=_dt_to_ms(ns.updated_at),
        message=ns.message or "",
    )


def _ns_to_proto(ns: ManoNSInstance) -> mano_pb2.NsInstance:
    return mano_pb2.NsInstance(
        id=ns.id,
        name=ns.name,
        topology_id=ns.topology_id or "",
        status=ns.status,
        created_at_ms=_dt_to_ms(ns.created_at),
        updated_at_ms=_dt_to_ms(ns.updated_at),
        message=ns.message or "",
        nsd_id=ns.nsd_id or "",
        emulation_id=ns.emulation_id or "",
    )


def _vnf_to_http(vnf: ManoVNFInstance) -> "VnfInstanceHttp":
    return VnfInstanceHttp(
        id=vnf.id,
        ns_instance_id=vnf.ns_instance_id,
        vnfd_id=vnf.vnfd_id,
        name=vnf.name,
        device_type=vnf.device_type,
        device_name=vnf.device_name,
        status=vnf.status,
        created_at_ms=_dt_to_ms(vnf.created_at),
        updated_at_ms=_dt_to_ms(vnf.updated_at),
        message=vnf.message or "",
        properties=vnf.properties or {},
    )


def _vnf_to_proto(vnf: ManoVNFInstance) -> mano_pb2.VnfInstance:
    return mano_pb2.VnfInstance(
        id=vnf.id,
        ns_instance_id=vnf.ns_instance_id or "",
        vnfd_id=vnf.vnfd_id or "",
        name=vnf.name,
        device_type=vnf.device_type,
        device_name=vnf.device_name or "",
        status=vnf.status,
        message=vnf.message or "",
        created_at_ms=_dt_to_ms(vnf.created_at),
        updated_at_ms=_dt_to_ms(vnf.updated_at),
    )


async def _instantiate_ns_local(
    *,
    db: Session,
    sb: SouthboundClient,
    name: str,
    topology_id: Optional[str],
    nsd_id: Optional[str],
    options: Optional[dict],
    dry_run: bool,
) -> ManoNSInstance:
    now = datetime.utcnow()
    ns = ManoNSInstance(
        id=uuid.uuid4().hex,
        name=name,
        topology_id=topology_id,
        nsd_id=nsd_id,
        backend="local",
        status="INSTANTIATING",
        message="Queued.",
        created_at=now,
        updated_at=now,
    )
    op = ManoOperation(
        id=uuid.uuid4().hex,
        ns_instance_id=ns.id,
        kind="INSTANTIATE",
        status="RUNNING",
        message="Starting.",
        request={"topology_id": topology_id, "nsd_id": nsd_id, "options": options or {}, "dry_run": dry_run},
        result={},
        started_at=now,
        created_at=now,
    )
    db.add(ns)
    db.add(op)
    db.commit()

    if dry_run:
        ns.status = "CREATED"
        ns.message = "Created (dry_run=true)."
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS"
        op.message = "Dry-run; no southbound calls executed."
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns

    if not topology_id:
        ns.status = "ERROR"
        ns.message = "topology_id is required for instantiate (or use dry_run)."
        ns.updated_at = datetime.utcnow()
        op.status = "ERROR"
        op.message = "Missing topology_id."
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns

    try:
        result = await sb.emulation_start(topology_id=topology_id, options=options or {})
        ns.emulation_id = result.get("emulation_id")
        ns.status = "RUNNING" if result.get("success") else "ERROR"
        ns.message = result.get("message") or ("Started." if ns.status == "RUNNING" else "Start failed.")
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS" if ns.status == "RUNNING" else "ERROR"
        op.message = ns.message
        op.result = result
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        # Post-instantiate actions: if NSD declares runtime VNFs/links, apply them best-effort.
        if ns.status == "RUNNING":
            try:
                post = await _apply_nsd_runtime(db=db, sb=sb, ns=ns)
                if isinstance(op.result, dict):
                    op.result["post_tasks"] = post
                else:
                    op.result = {"start": op.result, "post_tasks": post}
                if isinstance(post, dict) and post.get("errors"):
                    ns.message = f"{(ns.message or '').strip()} (post_tasks had errors)".strip()
                    ns.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(ns)
            except Exception as exc:
                if isinstance(op.result, dict):
                    op.result["post_tasks_error"] = str(exc)
                ns.message = f"{(ns.message or '').strip()} (post_tasks failed: {exc})".strip()
                ns.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(ns)
        return ns
    except Exception as exc:
        ns.status = "ERROR"
        ns.message = f"Instantiate failed: {exc}"
        ns.updated_at = datetime.utcnow()
        op.status = "ERROR"
        op.message = ns.message
        op.result = {"error": str(exc)}
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns


def _resolve_topology_from_nsd(db: Session, nsd_id: Optional[str]) -> Tuple[Optional[str], Dict[str, Any]]:
    if not nsd_id:
        return None, {}
    row = db.get(ManoNSD, nsd_id)
    if row is None or not isinstance(row.descriptor, dict):
        return None, {}
    topo = row.descriptor.get("topology_id")
    opts = row.descriptor.get("options") if isinstance(row.descriptor.get("options"), dict) else {}
    topo_str = str(topo).strip() if topo else None
    return topo_str, (opts or {})


async def _apply_nsd_runtime(
    *,
    db: Session,
    sb: SouthboundClient,
    ns: ManoNSInstance,
) -> Dict[str, Any]:
    """
    Best-effort post-instantiate actions driven by NSD descriptor.

    Supported descriptor fields (local backend):
      - vnfs: [{name, device_type, properties, vnfd_id?}]
      - links: [{node1, node2, port1?, port2?, bandwidth?, delay?, loss?, max_queue_size?}]
    """
    if not ns.nsd_id:
        return {"skipped": True, "reason": "no nsd_id"}
    row = db.get(ManoNSD, ns.nsd_id)
    if row is None or not isinstance(row.descriptor, dict):
        return {"skipped": True, "reason": "nsd not found"}
    if not ns.topology_id:
        return {"skipped": True, "reason": "no topology_id"}

    descriptor = row.descriptor or {}
    vnfs = descriptor.get("vnfs") if isinstance(descriptor.get("vnfs"), list) else []
    links = descriptor.get("links") if isinstance(descriptor.get("links"), list) else []

    results: Dict[str, Any] = {"vnfs_created": [], "links_created": [], "errors": []}

    for spec in vnfs:
        if not isinstance(spec, dict):
            continue
        vnf_name = str(spec.get("name") or "").strip()
        if not vnf_name:
            continue
        device_type = str(spec.get("device_type") or "container").strip() or "container"
        properties = spec.get("properties") if isinstance(spec.get("properties"), dict) else {}
        vnfd_id = str(spec.get("vnfd_id") or "").strip() or None

        now = datetime.utcnow()
        vnf_id = uuid.uuid4().hex
        vnf = ManoVNFInstance(
            id=vnf_id,
            ns_instance_id=ns.id,
            vnfd_id=vnfd_id,
            name=vnf_name,
            device_type=device_type,
            device_name=None,
            status="CREATING",
            message="Created from NSD.",
            properties=properties or {},
            created_at=now,
            updated_at=now,
        )
        db.add(vnf)
        db.commit()
        db.refresh(vnf)
        try:
            res = await sb.device_add(
                name=vnf_name,
                device_type=device_type,
                properties=properties or {},
                topology_id=ns.topology_id,
            )
            vnf.device_name = res.get("name") or vnf_name
            vnf.status = "RUNNING"
            vnf.message = "Created from NSD."
            results["vnfs_created"].append({"id": vnf.id, "name": vnf.name, "device_name": vnf.device_name})
        except Exception as exc:
            vnf.status = "ERROR"
            vnf.message = f"Create from NSD failed: {exc}"
            results["errors"].append({"component": "vnf", "name": vnf_name, "error": str(exc)})
        vnf.updated_at = datetime.utcnow()
        db.commit()

    for spec in links:
        if not isinstance(spec, dict):
            continue
        node1 = str(spec.get("node1") or "").strip()
        node2 = str(spec.get("node2") or "").strip()
        if not node1 or not node2:
            continue
        props = {k: v for k, v in spec.items() if k not in ("node1", "node2")}
        try:
            res = await sb.link_add(topology_id=ns.topology_id, node1=node1, node2=node2, properties=props)
            results["links_created"].append({"node1": node1, "node2": node2, "result": res})
        except Exception as exc:
            results["errors"].append({"component": "link", "node1": node1, "node2": node2, "error": str(exc)})

    return results


async def _instantiate_ns_osm(
    *,
    db: Session,
    osm: OsmClient,
    name: str,
    topology_id: Optional[str],
    nsd_id: str,
    options: Optional[dict],
    dry_run: bool,
) -> ManoNSInstance:
    now = datetime.utcnow()
    if dry_run:
        ns_id = uuid.uuid4().hex
        ns = ManoNSInstance(
            id=ns_id,
            name=name,
            topology_id=topology_id,
            nsd_id=nsd_id,
            backend="osm",
            status="CREATED",
            message="Created (dry_run=true, OSM backend).",
            created_at=now,
            updated_at=now,
            external_ref={"options": options or {}},
        )
        op = ManoOperation(
            id=uuid.uuid4().hex,
            ns_instance_id=ns_id,
            kind="INSTANTIATE",
            status="SUCCESS",
            message="Dry-run; no OSM calls executed.",
            request={"backend": "osm", "nsd_id": nsd_id, "options": options or {}, "dry_run": True},
            result={},
            started_at=now,
            finished_at=now,
            created_at=now,
        )
        db.add(ns)
        db.add(op)
        db.commit()
        db.refresh(ns)
        return ns

    try:
        external_id = await osm.create_ns(ns_name=name, nsd_id=nsd_id, description="")
        ns = ManoNSInstance(
            id=external_id,
            name=name,
            topology_id=topology_id,
            nsd_id=nsd_id,
            backend="osm",
            external_id=external_id,
            status="INSTANTIATING",
            message="Creating (OSM).",
            created_at=now,
            updated_at=now,
            external_ref={"options": options or {}},
        )
        op = ManoOperation(
            id=uuid.uuid4().hex,
            ns_instance_id=external_id,
            kind="INSTANTIATE",
            status="RUNNING",
            message="Starting (OSM).",
            request={"backend": "osm", "nsd_id": nsd_id, "options": options or {}, "dry_run": False},
            result={"create_id": external_id},
            started_at=now,
            created_at=now,
        )
        db.add(ns)
        db.add(op)
        db.commit()

        inst_params: dict = {}
        if isinstance(options, dict):
            inst_params = dict(options.get("instantiate_params") or options.get("instantiate") or {})
            # Accept common shortcuts
            vim_id = options.get("vim_account_id") or options.get("vimAccountId")
            if vim_id and "vimAccountId" not in inst_params:
                inst_params["vimAccountId"] = vim_id
        # OSM NBI variants: some deployments require nsName + nsdId on instantiate.
        inst_params.setdefault("nsName", name)
        inst_params.setdefault("nsdId", nsd_id)
        inst_result = await osm.instantiate_ns(ns_instance_id=external_id, params=inst_params)
        ns.status = "RUNNING"
        ns.message = "Instantiated via OSM."
        ns.updated_at = datetime.utcnow()

        op.status = "SUCCESS"
        op.message = ns.message
        if isinstance(op.result, dict):
            op.result["instantiate"] = inst_result
        else:
            op.result = {"create_id": external_id, "instantiate": inst_result}
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns
    except Exception as exc:
        # If the NS row doesn't exist yet (create failed), keep an op record for debugging.
        if "ns" not in locals() or not isinstance(locals().get("ns"), ManoNSInstance):
            op = ManoOperation(
                id=uuid.uuid4().hex,
                ns_instance_id=None,
                kind="INSTANTIATE",
                status="ERROR",
                message=f"OSM create failed: {exc}",
                request={"backend": "osm", "nsd_id": nsd_id, "options": options or {}, "dry_run": False},
                result={"error": str(exc)},
                started_at=now,
                finished_at=datetime.utcnow(),
                created_at=now,
            )
            db.add(op)
            db.commit()
            raise
        ns.status = "ERROR"
        ns.message = f"OSM instantiate failed: {exc}"
        ns.updated_at = datetime.utcnow()
        op.status = "ERROR"
        op.message = ns.message
        op.result = {"error": str(exc)}
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns


async def _refresh_ns_osm(*, db: Session, osm: OsmClient, ns: ManoNSInstance) -> ManoNSInstance:
    if not ns.external_id:
        return ns
    try:
        data = await osm.get_ns(ns_instance_id=ns.external_id)
        state = None
        if isinstance(data, dict):
            state = data.get("nsState") or data.get("operationalStatus") or data.get("status")
        if state:
            ns.status = str(state).upper()
        ns.external_ref = {"last_get": data, **(ns.external_ref or {})}
        ns.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
    except Exception as exc:
        ns.message = f"{(ns.message or '').strip()} (OSM refresh failed: {exc})".strip()
        ns.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
    return ns

async def _terminate_ns_local(*, db: Session, sb: SouthboundClient, ns: ManoNSInstance, reason: str) -> ManoNSInstance:
    now = datetime.utcnow()
    op = ManoOperation(
        id=uuid.uuid4().hex,
        ns_instance_id=ns.id,
        kind="TERMINATE",
        status="RUNNING",
        message="Stopping.",
        request={"reason": reason},
        result={},
        started_at=now,
        created_at=now,
    )
    ns.status = "TERMINATING"
    ns.message = "Stopping."
    ns.updated_at = now
    db.add(op)
    db.commit()

    if not ns.emulation_id:
        ns.status = "TERMINATED"
        ns.message = "Terminated (no emulation_id recorded)."
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS"
        op.message = ns.message
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns

    try:
        result = await sb.emulation_stop(emulation_id=ns.emulation_id, payload={})
        ns.status = "TERMINATED" if result.get("success") else "ERROR"
        ns.message = result.get("message") or ("Stopped." if ns.status == "TERMINATED" else "Stop failed.")
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS" if ns.status == "TERMINATED" else "ERROR"
        op.message = ns.message
        op.result = result
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns
    except Exception as exc:
        ns.status = "ERROR"
        ns.message = f"Terminate failed: {exc}"
        ns.updated_at = datetime.utcnow()
        op.status = "ERROR"
        op.message = ns.message
        op.result = {"error": str(exc)}
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns


async def _terminate_ns_osm(*, db: Session, osm: OsmClient, ns: ManoNSInstance, reason: str) -> ManoNSInstance:
    now = datetime.utcnow()
    op = ManoOperation(
        id=uuid.uuid4().hex,
        ns_instance_id=ns.id,
        kind="TERMINATE",
        status="RUNNING",
        message="Stopping (OSM).",
        request={"backend": "osm", "reason": reason},
        result={},
        started_at=now,
        created_at=now,
    )
    ns.status = "TERMINATING"
    ns.message = "Stopping (OSM)."
    ns.updated_at = now
    db.add(op)
    db.commit()

    if not ns.external_id:
        ns.status = "TERMINATED"
        ns.message = "Terminated (no external_id recorded)."
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS"
        op.message = ns.message
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns

    try:
        result = await osm.terminate_ns(ns_instance_id=ns.external_id, params={})
        ns.status = "TERMINATED"
        ns.message = "Terminate requested via OSM."
        ns.updated_at = datetime.utcnow()
        op.status = "SUCCESS"
        op.message = ns.message
        op.result = result
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns
    except Exception as exc:
        ns.status = "ERROR"
        ns.message = f"OSM terminate failed: {exc}"
        ns.updated_at = datetime.utcnow()
        op.status = "ERROR"
        op.message = ns.message
        op.result = {"error": str(exc)}
        op.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(ns)
        return ns


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/info")
@app.get("/api/mano/info")
def info() -> Dict[str, object]:
    return {
        "service": SERVICE_NAME,
        "http_port": SERVICE_PORT,
        "grpc_port": GRPC_PORT,
        "features": {
            "http_via_mcp": True,
            "grpc": True,
            "catalog": True,
            "nfvo": "basic",
            "vnfm": "basic",
            "vim": "basic",
            "southbound_mode": SOUTHBOUND_MODE,
            "nfvo_backend_default": NFVO_BACKEND_DEFAULT,
            "osm": {"enabled": bool(OSM_NBI_URL), "nbi_url": OSM_NBI_URL or None},
        },
    }

# -----------------------
# Catalog (VNFD/NSD)
# -----------------------

@app.post("/api/catalog/vnfds", response_model=Dict[str, str])
@app.post("/api/mano/catalog/vnfds", response_model=Dict[str, str])
async def upsert_vnfd(req: DescriptorUpsert, db: Session = Depends(get_db)) -> Dict[str, str]:
    vnfd_id = req.id or uuid.uuid4().hex
    now = datetime.utcnow()
    row = db.get(ManoVNFD, vnfd_id)
    if row is None:
        row = ManoVNFD(id=vnfd_id, created_at=now)
        db.add(row)
    row.name = req.name
    row.version = req.version
    row.provider = req.provider
    row.descriptor = req.descriptor or {}
    row.updated_at = now
    db.commit()
    return {"id": vnfd_id}


@app.get("/api/catalog/vnfds", response_model=List[Dict[str, Any]])
@app.get("/api/mano/catalog/vnfds", response_model=List[Dict[str, Any]])
async def list_vnfds(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = db.query(ManoVNFD).order_by(ManoVNFD.updated_at.desc()).limit(500).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "version": r.version,
            "provider": r.provider,
            "updated_at_ms": _dt_to_ms(r.updated_at),
        }
        for r in rows
    ]


@app.post("/api/catalog/nsds", response_model=Dict[str, str])
@app.post("/api/mano/catalog/nsds", response_model=Dict[str, str])
async def upsert_nsd(req: DescriptorUpsert, db: Session = Depends(get_db)) -> Dict[str, str]:
    nsd_id = req.id or uuid.uuid4().hex
    now = datetime.utcnow()
    row = db.get(ManoNSD, nsd_id)
    if row is None:
        row = ManoNSD(id=nsd_id, created_at=now)
        db.add(row)
    row.name = req.name
    row.version = req.version
    row.provider = req.provider
    row.descriptor = req.descriptor or {}
    row.updated_at = now
    db.commit()
    return {"id": nsd_id}


@app.get("/api/catalog/nsds", response_model=List[Dict[str, Any]])
@app.get("/api/mano/catalog/nsds", response_model=List[Dict[str, Any]])
async def list_nsds(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = db.query(ManoNSD).order_by(ManoNSD.updated_at.desc()).limit(500).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "version": r.version,
            "provider": r.provider,
            "updated_at_ms": _dt_to_ms(r.updated_at),
        }
        for r in rows
    ]


# -----------------------
# VNFM-ish (VNF instances)
# -----------------------

@app.post("/api/vnfm/vnf-instances", response_model=VnfInstanceHttp)
@app.post("/api/mano/vnfm/vnf-instances", response_model=VnfInstanceHttp)
async def create_vnf_instance(req: VnfInstanceCreateHttp, db: Session = Depends(get_db)) -> VnfInstanceHttp:
    ns = db.get(ManoNSInstance, req.ns_instance_id)
    if ns is None:
        raise HTTPException(status_code=404, detail="NS instance not found")
    if ns.status != "RUNNING" and not req.dry_run:
        raise HTTPException(status_code=409, detail=f"NS instance is not RUNNING (status={ns.status})")
    if (getattr(ns, "backend", None) or "local") != "local" and not req.dry_run:
        raise HTTPException(status_code=409, detail=f"VNFM runtime ops only supported for local backend (backend={getattr(ns, 'backend', None)})")

    now = datetime.utcnow()
    vnf_id = uuid.uuid4().hex
    vnf = ManoVNFInstance(
        id=vnf_id,
        ns_instance_id=req.ns_instance_id,
        vnfd_id=req.vnfd_id,
        name=req.name,
        device_type=req.device_type,
        device_name=req.device_name,
        status="CREATING",
        message="Queued.",
        properties=req.properties or {},
        created_at=now,
        updated_at=now,
    )
    db.add(vnf)
    db.commit()
    db.refresh(vnf)

    if req.dry_run:
        vnf.status = "CREATED"
        vnf.message = "Created (dry_run=true)."
        vnf.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(vnf)
        return _vnf_to_http(vnf)

    device_name = (vnf.device_name or "").strip() or vnf.name
    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    try:
        result = await sb.device_add(
            name=device_name,
            device_type=vnf.device_type,
            properties=vnf.properties or {},
            topology_id=ns.topology_id,
        )
        vnf.device_name = result.get("name") or device_name
        vnf.status = "RUNNING"
        vnf.message = "Created."
    except Exception as exc:
        vnf.status = "ERROR"
        vnf.message = f"Create failed: {exc}"
    vnf.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(vnf)
    return _vnf_to_http(vnf)


@app.get("/api/vnfm/vnf-instances", response_model=List[VnfInstanceHttp])
@app.get("/api/mano/vnfm/vnf-instances", response_model=List[VnfInstanceHttp])
async def list_vnf_instances(ns_instance_id: Optional[str] = None, db: Session = Depends(get_db)) -> List[VnfInstanceHttp]:
    q = db.query(ManoVNFInstance).order_by(ManoVNFInstance.updated_at.desc())
    if ns_instance_id:
        q = q.filter(ManoVNFInstance.ns_instance_id == ns_instance_id)
    rows = q.limit(500).all()
    return [_vnf_to_http(r) for r in rows]

@app.delete("/api/vnfm/vnf-instances/{vnf_id}")
@app.delete("/api/mano/vnfm/vnf-instances/{vnf_id}")
async def delete_vnf_instance(vnf_id: str, force: bool = False, db: Session = Depends(get_db)) -> Dict[str, Any]:
    vnf = db.get(ManoVNFInstance, vnf_id)
    if vnf is None:
        raise HTTPException(status_code=404, detail="VNF instance not found")

    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    removed_device = False
    remove_error: Optional[str] = None

    if vnf.device_name:
        try:
            await sb.device_remove(vnf.device_name)
            removed_device = True
        except Exception as exc:
            remove_error = str(exc)
            if not force:
                raise HTTPException(status_code=502, detail=f"Failed to remove runtime device '{vnf.device_name}': {exc}")

    try:
        db.delete(vnf)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok": True, "vnf_instance_id": vnf_id, "removed_device": removed_device, "remove_error": remove_error}


@app.post("/api/vnfm/vnf-instances/{vnf_id}/exec")
@app.post("/api/mano/vnfm/vnf-instances/{vnf_id}/exec")
async def exec_vnf_command(vnf_id: str, req: ExecHttp, db: Session = Depends(get_db)) -> Dict[str, Any]:
    vnf = db.get(ManoVNFInstance, vnf_id)
    if vnf is None:
        raise HTTPException(status_code=404, detail="VNF instance not found")
    if not vnf.device_name:
        raise HTTPException(status_code=409, detail="VNF instance has no device_name")
    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    result = await sb.device_exec(device_name=vnf.device_name, command=req.command)
    return {"ok": True, "vnf_instance_id": vnf_id, "device": vnf.device_name, "result": result}


# -----------------------
# VIM-ish (inventory)
# -----------------------

@app.get("/api/vim/inventory")
@app.get("/api/mano/vim/inventory")
async def vim_inventory(db: Session = Depends(get_db), ns_instance_id: Optional[str] = None) -> Dict[str, Any]:
    emulation_id: Optional[str] = None
    topology_id: Optional[str] = None
    if ns_instance_id:
        ns = db.get(ManoNSInstance, ns_instance_id)
        if ns is None:
            raise HTTPException(status_code=404, detail="NS instance not found")
        emulation_id = ns.emulation_id
        topology_id = ns.topology_id
    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    active = await sb.emulation_active()
    # If no NS scope is provided, pick the first running emulation (best-effort).
    if not topology_id and isinstance(active, dict):
        for item in (active.get("emulations") or []):
            if isinstance(item, dict) and item.get("status") == "running":
                topology_id = item.get("topology_id")
                emulation_id = emulation_id or item.get("emulation_id")
                break

    errors: List[Dict[str, Any]] = []

    async def _safe(label: str, coro):
        try:
            return await coro
        except Exception as exc:
            errors.append({"component": label, "error": str(exc)})
            return None

    devices = await _safe("emulation_devices", sb.emulation_list_devices(topology_id=topology_id, emulation_id=emulation_id))
    containers = await _safe("emulation_containers", sb.emulation_list_containers(topology_id=topology_id, include_stopped=True))
    return {
        "scope": {"ns_instance_id": ns_instance_id, "emulation_id": emulation_id, "topology_id": topology_id},
        "active": active,
        "devices": devices,
        "containers": containers,
        "errors": errors,
    }


# -----------------------
# Operations (observability)
# -----------------------

@app.get("/api/operations")
@app.get("/api/mano/operations")
async def list_operations(
    db: Session = Depends(get_db),
    ns_instance_id: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    q = db.query(ManoOperation).order_by(ManoOperation.created_at.desc())
    if ns_instance_id:
        q = q.filter(ManoOperation.ns_instance_id == ns_instance_id)
    if kind:
        q = q.filter(ManoOperation.kind == kind)
    if status:
        q = q.filter(ManoOperation.status == status)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    rows = q.offset(offset).limit(limit).all()
    items = [
        {
            "id": r.id,
            "ns_instance_id": r.ns_instance_id,
            "kind": r.kind,
            "status": r.status,
            "message": r.message,
            "request": r.request,
            "result": r.result,
            "started_at_ms": _dt_to_ms(r.started_at),
            "finished_at_ms": _dt_to_ms(r.finished_at),
            "created_at_ms": _dt_to_ms(r.created_at),
        }
        for r in rows
    ]
    return {"items": items, "limit": limit, "offset": offset}


@app.get("/api/operations/{op_id}")
@app.get("/api/mano/operations/{op_id}")
async def get_operation(op_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    r = db.get(ManoOperation, op_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Operation not found")
    return {
        "id": r.id,
        "ns_instance_id": r.ns_instance_id,
        "kind": r.kind,
        "status": r.status,
        "message": r.message,
        "request": r.request,
        "result": r.result,
        "started_at_ms": _dt_to_ms(r.started_at),
        "finished_at_ms": _dt_to_ms(r.finished_at),
        "created_at_ms": _dt_to_ms(r.created_at),
    }


# -----------------------
# NS Lifecycle (NFVO-ish)
# -----------------------

@app.post("/api/ns-instances", response_model=NsInstanceHttp)
@app.post("/api/mano/ns-instances", response_model=NsInstanceHttp)
async def create_ns_instance(req: NsInstanceCreateHttp, db: Session = Depends(get_db)) -> NsInstanceHttp:
    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    topology_id = req.topology_id
    merged_options = dict(req.options or {})
    backend = (req.backend or NFVO_BACKEND_DEFAULT or "local").strip().lower()
    if backend == "local":
        if not topology_id and req.nsd_id:
            topo_from_nsd, opts_from_nsd = _resolve_topology_from_nsd(db, req.nsd_id)
            topology_id = topo_from_nsd or topology_id
            for k, v in (opts_from_nsd or {}).items():
                merged_options.setdefault(k, v)
        ns = await _instantiate_ns_local(
            db=db,
            sb=sb,
            name=req.name,
            topology_id=topology_id,
            nsd_id=req.nsd_id,
            options=merged_options,
            dry_run=req.dry_run,
        )
    elif backend == "osm":
        osm_topology_id = str(merged_options.get("osm_topology_id") or topology_id or "").strip() or None
        osm = OsmClient(http=http, topology_id=osm_topology_id)
        # For OSM, nsd_id is the OSM nsd_id (or can be provided in options.osm_nsd_id)
        osm_nsd_id = str(merged_options.get("osm_nsd_id") or req.nsd_id or "").strip()
        if not osm_nsd_id:
            raise HTTPException(status_code=400, detail="nsd_id (OSM nsd_id) is required when backend=osm")
        ns = await _instantiate_ns_osm(
            db=db,
            osm=osm,
            name=req.name,
            topology_id=osm_topology_id,
            nsd_id=osm_nsd_id,
            options=merged_options,
            dry_run=req.dry_run,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported backend: {backend}")
    return _ns_to_http(ns)


@app.get("/api/ns-instances", response_model=List[NsInstanceHttp])
@app.get("/api/mano/ns-instances", response_model=List[NsInstanceHttp])
async def list_ns_instances(topology_id: Optional[str] = None, db: Session = Depends(get_db)) -> List[NsInstanceHttp]:
    q = db.query(ManoNSInstance).order_by(ManoNSInstance.updated_at.desc())
    if topology_id:
        q = q.filter(ManoNSInstance.topology_id == topology_id)
    rows = q.limit(500).all()
    return [_ns_to_http(r) for r in rows]


@app.get("/api/ns-instances/{ns_id}", response_model=NsInstanceHttp)
@app.get("/api/mano/ns-instances/{ns_id}", response_model=NsInstanceHttp)
async def get_ns_instance(ns_id: str, refresh: bool = False, db: Session = Depends(get_db)) -> NsInstanceHttp:
    ns = db.get(ManoNSInstance, ns_id)
    if ns is None:
        raise HTTPException(status_code=404, detail="NS instance not found")
    if refresh and (getattr(ns, "backend", None) or "local") == "osm" and ns.external_id:
        http: httpx.AsyncClient = app.state.http
        osm = OsmClient(http=http, topology_id=ns.topology_id)
        ns = await _refresh_ns_osm(db=db, osm=osm, ns=ns)
    return _ns_to_http(ns)


@app.post("/api/ns-instances/{ns_id}/terminate")
@app.post("/api/mano/ns-instances/{ns_id}/terminate")
async def terminate_ns_instance(ns_id: str, req: TerminateHttp, db: Session = Depends(get_db)) -> Dict[str, object]:
    ns = db.get(ManoNSInstance, ns_id)
    if ns is None:
        raise HTTPException(status_code=404, detail="NS instance not found")
    http: httpx.AsyncClient = app.state.http
    sb = SouthboundClient(http=http)
    if (getattr(ns, "backend", None) or "local") == "osm":
        osm = OsmClient(http=http, topology_id=ns.topology_id)
        ns = await _terminate_ns_osm(db=db, osm=osm, ns=ns, reason=req.reason or "")
    else:
        ns = await _terminate_ns_local(db=db, sb=sb, ns=ns, reason=req.reason or "")
    return {"ok": ns.status == "TERMINATED", "id": ns_id, "status": ns.status, "message": ns.message or ""}


class ManoGrpcServicer(mano_pb2_grpc.ManoServiceServicer):
    async def Ping(self, request: mano_pb2.PingRequest, context: grpc.aio.ServicerContext) -> mano_pb2.PingResponse:
        msg = request.message or "pong"
        return mano_pb2.PingResponse(message=msg, server_time_ms=_now_ms())

    async def CreateNsInstance(
        self, request: mano_pb2.CreateNsInstanceRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.NsInstance:
        if not (request.name or "").strip():
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("name is required")
            return mano_pb2.NsInstance()
        topo_in = (request.topology_id or "").strip()
        db = _db_session()
        try:
            http: httpx.AsyncClient = app.state.http
            sb = SouthboundClient(http=http)
            nsd_id = (request.nsd_id or "").strip() or None
            topology_id = topo_in
            opts: Dict[str, Any] = {}
            if not topology_id and nsd_id:
                topology_id, opts = _resolve_topology_from_nsd(db, nsd_id)
            if not topology_id:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("topology_id is required (or nsd_id with descriptor.topology_id)")
                return mano_pb2.NsInstance()
            ns = await _instantiate_ns_local(
                db=db,
                sb=sb,
                name=request.name.strip(),
                topology_id=topology_id,
                nsd_id=nsd_id,
                options=opts,
                dry_run=False,
            )
            return _ns_to_proto(ns)
        finally:
            db.close()

    async def CreateVnfInstance(
        self, request: mano_pb2.CreateVnfInstanceRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.VnfInstance:
        ns_instance_id = (request.ns_instance_id or "").strip()
        if not ns_instance_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("ns_instance_id is required")
            return mano_pb2.VnfInstance()
        name = (request.name or "").strip()
        if not name:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("name is required")
            return mano_pb2.VnfInstance()

        props: Dict[str, Any] = {}
        if (request.properties_json or "").strip():
            try:
                obj = json.loads(request.properties_json)
                if isinstance(obj, dict):
                    props = obj
            except Exception:
                props = {}

        db = _db_session()
        try:
            ns = db.get(ManoNSInstance, ns_instance_id)
            if ns is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("NS instance not found")
                return mano_pb2.VnfInstance()
            if ns.status != "RUNNING" and not bool(getattr(request, "dry_run", False)):
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details(f"NS instance is not RUNNING (status={ns.status})")
                return mano_pb2.VnfInstance()

            now = datetime.utcnow()
            vnf = ManoVNFInstance(
                id=uuid.uuid4().hex,
                ns_instance_id=ns_instance_id,
                vnfd_id=(request.vnfd_id or "").strip() or None,
                name=name,
                device_type=(request.device_type or "").strip() or "container",
                device_name=(request.device_name or "").strip() or None,
                status="CREATING",
                message="Queued.",
                properties=props,
                created_at=now,
                updated_at=now,
            )
            db.add(vnf)
            db.commit()

            if bool(getattr(request, "dry_run", False)):
                vnf.status = "CREATED"
                vnf.message = "Created (dry_run=true)."
                vnf.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(vnf)
                return _vnf_to_proto(vnf)

            http: httpx.AsyncClient = app.state.http
            sb = SouthboundClient(http=http)
            device_name = vnf.device_name or vnf.name
            try:
                result = await sb.device_add(name=device_name, device_type=vnf.device_type, properties=vnf.properties or {})
                vnf.device_name = result.get("name") or device_name
                vnf.status = "RUNNING"
                vnf.message = "Created."
            except Exception as exc:
                vnf.status = "ERROR"
                vnf.message = f"Create failed: {exc}"
            vnf.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(vnf)
            return _vnf_to_proto(vnf)
        finally:
            db.close()

    async def ListVnfInstances(
        self, request: mano_pb2.ListVnfInstancesRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.ListVnfInstancesResponse:
        db = _db_session()
        try:
            q = db.query(ManoVNFInstance).order_by(ManoVNFInstance.updated_at.desc())
            if (request.ns_instance_id or "").strip():
                q = q.filter(ManoVNFInstance.ns_instance_id == request.ns_instance_id.strip())
            items = q.all()
        finally:
            db.close()
        offset = max(int(request.offset), 0)
        limit = int(request.limit) if int(request.limit) > 0 else 200
        items = items[offset : offset + limit]
        return mano_pb2.ListVnfInstancesResponse(items=[_vnf_to_proto(x) for x in items])

    async def ExecVnfCommand(
        self, request: mano_pb2.ExecVnfCommandRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.ExecVnfCommandResponse:
        vnf_id = (request.vnf_instance_id or "").strip()
        if not vnf_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("vnf_instance_id is required")
            return mano_pb2.ExecVnfCommandResponse(ok=False, message="missing vnf_instance_id")
        command = (request.command or "").strip()
        if not command:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("command is required")
            return mano_pb2.ExecVnfCommandResponse(ok=False, message="missing command")

        db = _db_session()
        try:
            vnf = db.get(ManoVNFInstance, vnf_id)
        finally:
            db.close()
        if vnf is None or not vnf.device_name:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("VNF instance not found")
            return mano_pb2.ExecVnfCommandResponse(ok=False, message="not found")

        http: httpx.AsyncClient = app.state.http
        sb = SouthboundClient(http=http)
        try:
            result = await sb.device_exec(device_name=vnf.device_name, command=command)
            out = result.get("output") or ""
            code = int(result.get("exit_code") or 0)
            return mano_pb2.ExecVnfCommandResponse(ok=True, stdout=out, stderr="", exit_code=code, message="ok")
        except Exception as exc:
            return mano_pb2.ExecVnfCommandResponse(ok=False, stdout="", stderr=str(exc), exit_code=1, message="error")

    async def GetNsInstance(
        self, request: mano_pb2.GetNsInstanceRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.NsInstance:
        db = _db_session()
        try:
            ns = db.get(ManoNSInstance, request.id)
        finally:
            db.close()
        if ns is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("NS instance not found")
            return mano_pb2.NsInstance()
        return _ns_to_proto(ns)

    async def ListNsInstances(
        self, request: mano_pb2.ListNsInstancesRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.ListNsInstancesResponse:
        db = _db_session()
        try:
            q = db.query(ManoNSInstance).order_by(ManoNSInstance.updated_at.desc())
            if (request.topology_id or "").strip():
                q = q.filter(ManoNSInstance.topology_id == request.topology_id.strip())
            items = q.all()
        finally:
            db.close()
        offset = max(int(request.offset), 0)
        limit = int(request.limit) if int(request.limit) > 0 else 200
        items = items[offset : offset + limit]
        return mano_pb2.ListNsInstancesResponse(items=[_ns_to_proto(x) for x in items])

    async def TerminateNsInstance(
        self, request: mano_pb2.TerminateNsInstanceRequest, context: grpc.aio.ServicerContext
    ) -> mano_pb2.OperationStatus:
        db = _db_session()
        try:
            ns = db.get(ManoNSInstance, request.id)
            if ns is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("NS instance not found")
                return mano_pb2.OperationStatus(ok=False, message="Not found")
            http: httpx.AsyncClient = app.state.http
            sb = SouthboundClient(http=http)
            if (getattr(ns, "backend", None) or "local") == "osm":
                osm = OsmClient(http=http)
                ns = await _terminate_ns_osm(db=db, osm=osm, ns=ns, reason=(request.reason or "").strip())
            else:
                ns = await _terminate_ns_local(db=db, sb=sb, ns=ns, reason=(request.reason or "").strip())
            return mano_pb2.OperationStatus(ok=ns.status == "TERMINATED", message=ns.message or "")
        finally:
            db.close()


_grpc_server: Optional[grpc.aio.Server] = None
_grpc_task: Optional[asyncio.Task] = None


async def _serve_grpc() -> None:
    global _grpc_server
    server = grpc.aio.server()
    mano_pb2_grpc.add_ManoServiceServicer_to_server(ManoGrpcServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    _grpc_server = server
    await server.start()
    logger.info("✅ MANO gRPC server listening on %s", GRPC_PORT)
    await server.wait_for_termination()

async def _osm_mirror_loop() -> None:
    # Background mirror: pull OSM state for topologies that have isolated_osm in Consul.
    await asyncio.sleep(8.0)
    global _osm_mirror_lock
    if _osm_mirror_lock is None:
        _osm_mirror_lock = asyncio.Lock()

    while True:
        if not OSM_MIRROR_ENABLED:
            await asyncio.sleep(max(5, int(OSM_MIRROR_INTERVAL_SECONDS)))
            continue

        http: httpx.AsyncClient = app.state.http
        try:
            topologies = await _mcp_get_json(http, "/api/topologies")
        except Exception as exc:
            logger.warning("OSM mirror: failed to list topologies via MCP: %s", exc)
            await asyncio.sleep(max(5, int(OSM_MIRROR_INTERVAL_SECONDS)))
            continue

        topo_ids: List[str] = []
        if isinstance(topologies, list):
            for t in topologies:
                if isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"].strip():
                    topo_ids.append(t["id"].strip())

        if not topo_ids:
            await asyncio.sleep(max(5, int(OSM_MIRROR_INTERVAL_SECONDS)))
            continue

        # Only mirror topologies that have an isolated OSM stack configured.
        enabled_topos: List[str] = []
        for tid in topo_ids:
            if len(enabled_topos) >= max(1, int(OSM_MIRROR_MAX_TOPOLOGIES)):
                break
            raw = consul_client.get_config(f"caduceus/topologies/{tid}/isolated_osm")
            if raw:
                enabled_topos.append(tid)

        if not enabled_topos:
            await asyncio.sleep(max(5, int(OSM_MIRROR_INTERVAL_SECONDS)))
            continue

        async with _osm_mirror_lock:
            for tid in enabled_topos:
                try:
                    await _sync_osm_topology(topology_id=tid, resources=[], mark_deleted=True)
                except Exception as exc:
                    logger.warning("OSM mirror: sync failed for topology %s: %s", tid, exc)
        await asyncio.sleep(max(5, int(OSM_MIRROR_INTERVAL_SECONDS)))


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Starting MANO Service (HTTP %s, gRPC %s)...", SERVICE_PORT, GRPC_PORT)
    init_db()
    app.state.http = httpx.AsyncClient(timeout=30.0)
    try:
        consul_client.register_service(SERVICE_NAME, SERVICE_PORT)
    except Exception as exc:
        logger.warning("Consul registration failed: %s", exc)
    global _grpc_task
    _grpc_task = asyncio.create_task(_serve_grpc(), name="mano-grpc-server")
    global _osm_mirror_task
    if OSM_MIRROR_ENABLED:
        _osm_mirror_task = asyncio.create_task(_osm_mirror_loop(), name="osm-mirror-loop")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _grpc_task, _grpc_server, _osm_mirror_task
    http: Optional[httpx.AsyncClient] = getattr(app.state, "http", None)
    if http is not None:
        try:
            await http.aclose()
        except Exception:
            pass
    if _grpc_server is not None:
        try:
            await _grpc_server.stop(grace=None)
        except Exception:
            pass
    if _grpc_task is not None:
        _grpc_task.cancel()
    if _osm_mirror_task is not None:
        _osm_mirror_task.cancel()
    try:
        consul_client.deregister_service(SERVICE_NAME)
    except Exception:
        pass
