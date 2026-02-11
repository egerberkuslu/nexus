"""
VIM Emulation Service (OpenStack-like API)

Implements a minimal Keystone + Nova + Neutron subset so ETSI OSM can treat a running
Mininet/Containernet emulation as an OpenStack VIM. Runtime actions are forwarded to
the orchestrator's southbound APIs (add device/link, remove device).

Design goals:
- Good-enough compatibility for OSM RO's OpenStack VIM connector.
- Topology-scoped: one instance per topology (env TOPOLOGY_ID).
- Deterministic, debuggable behavior (simple in-memory state, verbose logs).
"""

from __future__ import annotations

import ipaddress
import asyncio
import base64
import logging
import os
import random
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.utils.consul_client import ConsulClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "vimemu-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "6001"))

TOPOLOGY_ID = (os.getenv("TOPOLOGY_ID", "") or "").strip()
ORCHESTRATOR_URL = (os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002") or "").rstrip("/")
REGION = os.getenv("OSM_REGION", os.getenv("REGION", "RegionOne")) or "RegionOne"

DEFAULT_DOCKER_IMAGE = os.getenv("VIMEMU_DEFAULT_DOCKER_IMAGE", "ubuntu:22.04")
DEFAULT_DOCKER_COMMAND = os.getenv("VIMEMU_DEFAULT_DOCKER_COMMAND", "sleep infinity")
VIMEMU_HTTP_TIMEOUT_SECONDS = float(os.getenv("VIMEMU_HTTP_TIMEOUT_SECONDS", "180"))
VIMEMU_EMULATION_START_TIMEOUT_SECONDS = float(os.getenv("VIMEMU_EMULATION_START_TIMEOUT_SECONDS", "240"))

app = FastAPI(
    title="Caduceus-Flux VIM Emulator",
    description="OpenStack-like Keystone/Nova/Neutron subset for ETSI OSM integration",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

consul_client = ConsulClient()


def _now_s() -> int:
    return int(time.time())


def _iso_utc() -> str:
    # OSM and OpenStack clients typically accept any RFC3339-ish timestamp; keep it simple.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _slug(value: str, *, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-")
    return cleaned or fallback


def _decode_user_data(user_data: Any) -> str:
    if not isinstance(user_data, str):
        return ""
    raw = user_data.strip()
    if not raw:
        return ""
    # Best-effort decode base64 user_data (Nova convention). If it's not base64, keep as-is.
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8", errors="ignore").strip()
        # Heuristic: only accept decoded payloads that look textual.
        if decoded and "\x00" not in decoded:
            return decoded
    except Exception:
        pass
    return raw


def _resolve_docker_image(image_ref: Any, metadata: Optional[dict[str, Any]] = None, *, store: Optional["MemoryStore"] = None) -> str:
    if isinstance(metadata, dict):
        meta_img = metadata.get("docker_image") or metadata.get("image")
        if isinstance(meta_img, str) and meta_img.strip():
            return meta_img.strip()
    if store is not None and isinstance(image_ref, str):
        ref = image_ref.strip()
        img = store.images.get(ref)
        if isinstance(img, dict) and isinstance(img.get("docker_image"), str) and img.get("docker_image"):
            return str(img.get("docker_image"))
        img_id = store.image_name_to_id.get(ref)
        if img_id:
            by_id = store.images.get(img_id)
            if isinstance(by_id, dict) and isinstance(by_id.get("docker_image"), str) and by_id.get("docker_image"):
                return str(by_id.get("docker_image"))
    if isinstance(image_ref, str):
        ref = image_ref.strip()
        if ref.startswith("docker://"):
            return ref[len("docker://") :].strip() or DEFAULT_DOCKER_IMAGE
        if ref.startswith("docker:"):
            return ref[len("docker:") :].strip() or DEFAULT_DOCKER_IMAGE
        # If it looks like a docker image name, accept it.
        if " " not in ref and (":" in ref or "/" in ref):
            return ref
    return DEFAULT_DOCKER_IMAGE


def _random_mac() -> str:
    # Locally administered MAC
    octets = [0x02, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
    return ":".join(f"{o:02x}" for o in octets)


def _extract_ref_id(value: Any) -> Optional[str]:
    if isinstance(value, (int, float)):
        return str(int(value))
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    # Nova sometimes sends full URLs in *Ref fields; accept the last path segment.
    if "://" in raw or "/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
    return raw or None


class MemoryStore:
    def __init__(self) -> None:
        self.tenant_id: str = os.getenv("VIMEMU_TENANT_ID", "") or "fc394f2a-b2df-4114-bde3-9905f800dc57"
        self.tenant_name: str = os.getenv("VIMEMU_TENANT_NAME", "") or "tenantName"
        self.tokens: dict[str, int] = {}  # token -> expires_at_s

        self.images: dict[str, dict[str, Any]] = {}
        self.image_name_to_id: dict[str, str] = {}

        self.networks: dict[str, dict[str, Any]] = {}
        self.subnets: dict[str, dict[str, Any]] = {}
        self.ports: dict[str, dict[str, Any]] = {}
        self.servers: dict[str, dict[str, Any]] = {}
        self.flavors: dict[str, dict[str, Any]] = {}
        self.flavor_name_to_id: dict[str, str] = {}
        self.builtin_flavor_ids: set[str] = set()

        # Emulation wiring metadata (best-effort)
        self.network_switch: dict[str, str] = {}  # network_id -> switch device name
        self.server_device: dict[str, str] = {}  # server_id -> device name in emulation

        # Per-network address allocation
        self.network_next_ip: dict[str, int] = {}  # network_id -> next host offset

        self._init_default_images()
        self._init_default_flavors()

    def issue_token(self) -> str:
        token = _new_uuid()
        self.tokens[token] = _now_s() + 60 * 60 * 24 * 365 * 10  # 10 years
        return token

    def _init_default_images(self) -> None:
        defaults = [
            ("netshoot", "nicolaka/netshoot:latest"),
            ("ubuntu-22.04", "ubuntu:22.04"),
            ("alpine-3.19", "alpine:3.19"),
        ]
        for name, docker_image in defaults:
            self._register_image(name, docker_image=docker_image)
            # Also allow using the docker image string directly as the VNFD `image`.
            self._register_image(docker_image, docker_image=docker_image)
            self._register_image(f"docker://{docker_image}", docker_image=docker_image)

    def _init_default_flavors(self) -> None:
        defaults = [
            ("m1.nano", 64, 1, 1),
            ("m1.micro", 256, 1, 1),
            ("m1.tiny", 512, 1, 1),
            ("m1.small", 2048, 1, 20),
        ]
        for name, ram_mb, vcpus, disk in defaults:
            flavor = self._register_flavor(name=name, ram=ram_mb, vcpus=vcpus, disk=disk, is_public=True)
            self.builtin_flavor_ids.add(str(flavor.get("id")))
            # Some OSM/RO builds request RAM in KB (e.g. 256MB -> 262144). Provide KB variants so
            # RO can find a matching flavor without custom OpenStack config.
            kb_name = f"{name}-kb"
            kb_flavor = self._register_flavor(name=kb_name, ram=ram_mb * 1024, vcpus=vcpus, disk=disk, is_public=True)
            self.builtin_flavor_ids.add(str(kb_flavor.get("id")))

    def _register_image(self, name: str, *, docker_image: str) -> dict[str, Any]:
        normalized = str(name or "").strip()
        if not normalized:
            normalized = docker_image
        existing_id = self.image_name_to_id.get(normalized)
        if existing_id and existing_id in self.images:
            return self.images[existing_id]

        image_id = _new_uuid()
        img = {
            "id": image_id,
            "name": normalized,
            "status": "active",
            "visibility": "public",
            "protected": False,
            "tags": [],
            "created_at": _iso_utc(),
            "updated_at": _iso_utc(),
            "size": 0,
            "min_disk": 0,
            "min_ram": 0,
            "docker_image": docker_image,
        }
        self.images[image_id] = img
        self.image_name_to_id[normalized] = image_id
        return img

    def ensure_image_by_name(self, name: str) -> dict[str, Any]:
        normalized = str(name or "").strip()
        if not normalized:
            return self._register_image(DEFAULT_DOCKER_IMAGE, docker_image=DEFAULT_DOCKER_IMAGE)

        existing_id = self.image_name_to_id.get(normalized)
        if existing_id and existing_id in self.images:
            return self.images[existing_id]

        docker_image = _resolve_docker_image(normalized, metadata=None, store=None)
        return self._register_image(normalized, docker_image=docker_image)

    def _register_flavor(
        self,
        *,
        name: str,
        ram: int,
        vcpus: int,
        disk: int,
        flavor_id: Optional[str] = None,
        is_public: bool = True,
        extra_specs: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        normalized_name = str(name or "").strip() or "flavor"
        existing_id = self.flavor_name_to_id.get(normalized_name)
        if existing_id and existing_id in self.flavors:
            return self.flavors[existing_id]

        fid = str(flavor_id or "").strip() or _new_uuid()
        obj = {
            "id": fid,
            "name": normalized_name,
            "ram": int(ram),
            "vcpus": int(vcpus),
            "disk": int(disk),
            "OS-FLV-EXT-DATA:ephemeral": 0,
            "swap": "",
            "rxtx_factor": 1.0,
            "os-flavor-access:is_public": bool(is_public),
            "extra_specs": dict(extra_specs or {}),
        }
        self.flavors[fid] = obj
        self.flavor_name_to_id[normalized_name] = fid
        return obj

    def ensure_flavor_by_name(self, name: str, *, defaults: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            normalized_name = "flavor"
        existing_id = self.flavor_name_to_id.get(normalized_name)
        if existing_id and existing_id in self.flavors:
            return self.flavors[existing_id]
        defaults = defaults or {}
        return self._register_flavor(
            name=normalized_name,
            ram=int(defaults.get("ram") or 64),
            vcpus=int(defaults.get("vcpus") or 1),
            disk=int(defaults.get("disk") or 1),
            is_public=bool(defaults.get("os-flavor-access:is_public", True)),
            extra_specs=defaults.get("extra_specs") if isinstance(defaults.get("extra_specs"), dict) else None,
        )


app.state.store = MemoryStore()


def _openstack_nova_error_payload(status_code: int, message: str) -> dict[str, Any]:
    key = {
        400: "badRequest",
        401: "unauthorized",
        403: "forbidden",
        404: "itemNotFound",
        409: "conflict",
    }.get(int(status_code), "computeFault")
    return {key: {"message": message, "code": int(status_code)}}


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Nova clients (novaclient) expect OpenStack-style error bodies where the first
    # top-level key maps to a dict containing at least a "message" field. FastAPI's
    # default `{"detail": "Not Found"}` breaks that assumption and can crash clients.
    path = request.url.path or ""
    detail = str(getattr(exc, "detail", "") or "")
    if path.startswith("/nova/"):
        return JSONResponse(status_code=exc.status_code, content=_openstack_nova_error_payload(exc.status_code, detail))
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


def _base_url(request: Request) -> str:
    host = request.headers.get("host") or f"localhost:{SERVICE_PORT}"
    scheme = "http"
    if request.url.scheme:
        scheme = request.url.scheme
    return f"{scheme}://{host}"


def _keystone_v2_service_catalog(request: Request, tenant_id: str) -> list[dict[str, Any]]:
    base = _base_url(request)
    compute_url = f"{base}/nova/v2.1/{tenant_id}"
    network_url = f"{base}/neutron"
    image_url = f"{base}/glance"

    return [
        {
            "name": "nova",
            "type": "compute",
            "endpoints": [
                {
                    "region": REGION,
                    "publicURL": compute_url,
                    "internalURL": compute_url,
                    "adminURL": compute_url,
                }
            ],
            "endpoints_links": [],
        },
        {
            "name": "neutron",
            "type": "network",
            "endpoints": [
                {
                    "region": REGION,
                    "publicURL": network_url,
                    "internalURL": network_url,
                    "adminURL": network_url,
                }
            ],
            "endpoints_links": [],
        },
        {
            "name": "glance",
            "type": "image",
            "endpoints": [
                {
                    "region": REGION,
                    "publicURL": image_url,
                    "internalURL": image_url,
                    "adminURL": image_url,
                }
            ],
            "endpoints_links": [],
        },
    ]


def _keystone_v3_catalog(request: Request, tenant_id: str) -> list[dict[str, Any]]:
    base = _base_url(request)
    return [
        {
            "type": "compute",
            "name": "nova",
            "endpoints": [
                {
                    "id": _new_uuid(),
                    "interface": "public",
                    "region": REGION,
                    "url": f"{base}/nova/v2.1/{tenant_id}",
                }
            ],
        },
        {
            "type": "network",
            "name": "neutron",
            "endpoints": [
                {
                    "id": _new_uuid(),
                    "interface": "public",
                    "region": REGION,
                    "url": f"{base}/neutron",
                }
            ],
        },
        {
            "type": "image",
            "name": "glance",
            "endpoints": [
                {
                    "id": _new_uuid(),
                    "interface": "public",
                    "region": REGION,
                    "url": f"{base}/glance",
                }
            ],
        },
    ]


async def _orch_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{ORCHESTRATOR_URL}{path}"
    http: httpx.AsyncClient = app.state.http  # type: ignore[attr-defined]
    resp = await http.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


async def _orch_delete(path: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    url = f"{ORCHESTRATOR_URL}{path}"
    http: httpx.AsyncClient = app.state.http  # type: ignore[attr-defined]
    resp = await http.delete(url, params=params or None)
    resp.raise_for_status()
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


async def _ensure_emulation_running() -> None:
    if not TOPOLOGY_ID:
        raise HTTPException(status_code=500, detail="TOPOLOGY_ID is not configured for this vimemu instance")
    http: httpx.AsyncClient = app.state.http  # type: ignore[attr-defined]
    active = await http.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
    active.raise_for_status()
    data = active.json()
    for item in (data.get("emulations") or []):
        if isinstance(item, dict) and item.get("topology_id") == TOPOLOGY_ID and str(item.get("status") or "").lower() == "running":
            return

    # Best-effort auto-start (this mirrors what the UI does).
    # Emulation startup can take >30s depending on topology and image pulls, so keep timeouts generous.
    try:
        start = await http.post(
            f"{ORCHESTRATOR_URL}/api/emulation/start",
            json={"topology_id": TOPOLOGY_ID, "options": {}},
            timeout=VIMEMU_EMULATION_START_TIMEOUT_SECONDS,
        )
        start.raise_for_status()
    except httpx.ReadTimeout:
        # Orchestrator may still be starting the emulation; fall back to polling.
        logger.warning("Timeout while waiting for orchestrator emulation/start; polling active status.")

    deadline = time.time() + VIMEMU_EMULATION_START_TIMEOUT_SECONDS
    while time.time() < deadline:
        active = await http.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
        active.raise_for_status()
        data = active.json()
        for item in (data.get("emulations") or []):
            if isinstance(item, dict) and item.get("topology_id") == TOPOLOGY_ID and str(item.get("status") or "").lower() == "running":
                return
        await asyncio.sleep(0.5)
    raise HTTPException(status_code=409, detail="Emulation is not running (failed to auto-start)")


async def _materialize_network_switch(network_id: str) -> str:
    store: MemoryStore = app.state.store
    if network_id in store.network_switch:
        return store.network_switch[network_id]

    await _ensure_emulation_running()
    switch_name = f"osm-net-{network_id[:8]}"
    try:
        await _orch_post(
            "/api/emulation/devices/add",
            {
                "topology_id": TOPOLOGY_ID,
                "name": switch_name,
                "device_type": "switch",
                "properties": {"node_id": network_id},
                "node_id": network_id,
            },
        )
        store.network_switch[network_id] = switch_name
    except Exception as exc:
        # Do not cache failures: allow subsequent retries (e.g. orchestrator not ready yet).
        logger.warning("Failed to materialize network switch for %s: %s", network_id, exc)
    return switch_name


def _allocate_ip(network_id: str) -> Optional[str]:
    store: MemoryStore = app.state.store
    # Pick the first subnet for this network (best-effort).
    subnet = None
    for s in store.subnets.values():
        if isinstance(s, dict) and s.get("network_id") == network_id:
            subnet = s
            break
    if not subnet:
        return None

    cidr = str(subnet.get("cidr") or "").strip()
    if not cidr:
        return None
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return None

    # Simple sequential allocation, skipping network/gateway.
    idx = store.network_next_ip.get(network_id, 2)
    hosts = list(net.hosts())
    if idx >= len(hosts):
        return None
    ip = str(hosts[idx])
    store.network_next_ip[network_id] = idx + 1
    return ip


async def _attach_port_to_server(port_id: str, server_id: str) -> None:
    store: MemoryStore = app.state.store
    port = store.ports.get(port_id)
    if not isinstance(port, dict):
        return
    net_id = port.get("network_id")
    if not isinstance(net_id, str) or not net_id:
        return
    device_name = store.server_device.get(server_id)
    if not device_name:
        return
    switch_name = await _materialize_network_switch(net_id)
    try:
        await _orch_post(
            "/api/emulation/links/add",
            {
                "topology_id": TOPOLOGY_ID,
                "node1": device_name,
                "node2": switch_name,
            },
        )
    except Exception as exc:
        logger.warning("Failed to attach port %s to server %s: %s", port_id, server_id, exc)


def _server_to_nova(store: MemoryStore, server: dict[str, Any], *, base: str, tenant_id: str) -> dict[str, Any]:
    server_id = str(server.get("id") or "")
    name = str(server.get("name") or "")
    status = str(server.get("status") or "ACTIVE")
    flavor_id = _extract_ref_id(server.get("flavor_id")) or _extract_ref_id(server.get("flavorRef")) or ""
    flavor = store.flavors.get(flavor_id) if flavor_id else None
    flavor_name = ""
    if isinstance(flavor, dict):
        flavor_name = str(flavor.get("name") or "")
    image_id = _extract_ref_id(server.get("image_id")) or _extract_ref_id(server.get("imageRef")) or ""
    links = [
        {"rel": "self", "href": f"{base}/nova/v2.1/{tenant_id}/servers/{server_id}"},
        {"rel": "bookmark", "href": f"{base}/nova/servers/{server_id}"},
    ]
    return {
        "id": server_id,
        "name": name,
        "status": status,
        "created": server.get("created") or _iso_utc(),
        "updated": server.get("updated") or _iso_utc(),
        "tenant_id": tenant_id,
        "user_id": server.get("user_id") or "user",
        "image": {"id": image_id} if image_id else {},
        "flavor": {"id": flavor_id, "original_name": flavor_name} if flavor_id else {"id": "", "original_name": ""},
        "metadata": server.get("metadata") if isinstance(server.get("metadata"), dict) else {},
        "links": links,
    }


def _flavor_to_nova(flavor: dict[str, Any], *, base: str, tenant_id: str, detail: bool) -> dict[str, Any]:
    flavor_id = str(flavor.get("id") or "")
    links = [
        {"rel": "self", "href": f"{base}/nova/v2.1/{tenant_id}/flavors/{flavor_id}"},
        {"rel": "bookmark", "href": f"{base}/nova/flavors/{flavor_id}"},
    ]
    if not detail:
        return {"id": flavor_id, "name": str(flavor.get("name") or ""), "links": links}
    return {
        "id": flavor_id,
        "name": str(flavor.get("name") or ""),
        "ram": int(flavor.get("ram") or 0),
        "vcpus": int(flavor.get("vcpus") or 0),
        "disk": int(flavor.get("disk") or 0),
        "OS-FLV-EXT-DATA:ephemeral": int(flavor.get("OS-FLV-EXT-DATA:ephemeral") or 0),
        "swap": str(flavor.get("swap") or ""),
        "rxtx_factor": float(flavor.get("rxtx_factor") or 1.0),
        "os-flavor-access:is_public": bool(flavor.get("os-flavor-access:is_public", True)),
        "links": links,
    }


# -----------------------
# Health/info
# -----------------------


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "topology_id": TOPOLOGY_ID or None,
        "orchestrator_url": ORCHESTRATOR_URL,
    }


# -----------------------
# Keystone (Identity)
# -----------------------


@app.get("/")
def keystone_versions(request: Request) -> dict[str, Any]:
    base = _base_url(request)
    return {
        "versions": {
            "values": [
                {"id": "v2.0", "status": "stable", "updated": "2014-04-17T00:00:00Z", "links": [{"rel": "self", "href": f"{base}/v2.0"}]},
                {"id": "v3.0", "status": "stable", "updated": "2013-03-06T00:00:00Z", "links": [{"rel": "self", "href": f"{base}/v3"}]},
            ]
        }
    }


@app.get("/v2.0")
def keystone_show_v2(request: Request) -> dict[str, Any]:
    base = _base_url(request)
    return {
        "version": {
            "id": "v2.0",
            "status": "stable",
            "updated": "2014-04-17T00:00:00Z",
            "links": [{"rel": "self", "href": f"{base}/v2.0"}],
        }
    }


@app.post("/v2.0/tokens")
async def keystone_get_token_v2(request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    auth = body.get("auth") if isinstance(body, dict) else {}
    tenant_name = None
    tenant_id = None
    if isinstance(auth, dict):
        tenant_name = auth.get("tenantName") or auth.get("tenant_name")
        tenant_id = auth.get("tenantId") or auth.get("tenant_id")

    if isinstance(tenant_id, str) and tenant_id.strip():
        store.tenant_id = tenant_id.strip()
    if isinstance(tenant_name, str) and tenant_name.strip():
        store.tenant_name = tenant_name.strip()

    token = store.issue_token()
    base = _base_url(request)

    return {
        "access": {
            "token": {
                "id": token,
                "issued_at": _iso_utc(),
                "expires": "2999-01-30T15:30:58.819Z",
                "tenant": {"id": store.tenant_id, "name": store.tenant_name},
            },
            "user": {"id": _new_uuid(), "name": "user", "roles": [{"name": "admin"}]},
            "serviceCatalog": _keystone_v2_service_catalog(request, store.tenant_id),
            "metadata": {"is_admin": 1, "roles": ["admin"]},
        }
    }


@app.get("/v3")
def keystone_show_v3(request: Request) -> dict[str, Any]:
    base = _base_url(request)
    return {
        "version": {
            "id": "v3.0",
            "status": "stable",
            "updated": "2013-03-06T00:00:00Z",
            "links": [{"rel": "self", "href": f"{base}/v3"}],
        }
    }


@app.post("/v3/auth/tokens")
async def keystone_get_token_v3(request: Request, response: Response) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    token = store.issue_token()
    response.status_code = 201
    response.headers["X-Subject-Token"] = token
    return {
        "token": {
            "expires_at": "2999-01-30T15:30:58.819Z",
            "issued_at": _iso_utc(),
            "methods": ["password"],
            "project": {"id": store.tenant_id, "name": store.tenant_name},
            "catalog": _keystone_v3_catalog(request, store.tenant_id),
        }
    }


@app.get("/v3/projects")
def keystone_list_projects() -> dict[str, Any]:
    store: MemoryStore = app.state.store
    return {"projects": [{"id": store.tenant_id, "name": store.tenant_name, "enabled": True}]}


# -----------------------
# Glance (Image) - under /glance/*
# -----------------------


@app.get("/glance/")
def glance_versions(request: Request) -> dict[str, Any]:
    base = _base_url(request)
    return {
        "versions": [
            {
                "id": "v2.0",
                "status": "CURRENT",
                "updated": "2014-04-17T00:00:00Z",
                "links": [{"rel": "self", "href": f"{base}/glance/v2"}],
            }
        ]
    }


@app.get("/glance/v2")
def glance_show_v2() -> dict[str, Any]:
    return {"version": {"id": "v2.0", "status": "CURRENT"}}


@app.get("/glance/v2/images")
def glance_list_images(
    request: Request,
    name: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    items: list[dict[str, Any]] = []

    if isinstance(name, str) and name.strip():
        img = store.ensure_image_by_name(name.strip())
        items = [img]
    else:
        items = list(store.images.values())

    if isinstance(limit, int) and limit > 0:
        items = items[:limit]

    # Keep the payload close to Glance v2 expectations; OSM mostly needs id+name.
    base = _base_url(request)
    for img in items:
        img.setdefault("self", f"{base}/glance/v2/images/{img.get('id')}")
        img.setdefault("file", f"{base}/glance/v2/images/{img.get('id')}/file")
        img.setdefault("schema", f"{base}/glance/v2/schemas/image")
    return {"images": items}


@app.get("/glance/v2/images/{image_id}")
def glance_get_image(image_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    img = store.images.get(image_id)
    if not isinstance(img, dict):
        raise HTTPException(status_code=404, detail="Image not found")
    base = _base_url(request)
    img.setdefault("self", f"{base}/glance/v2/images/{image_id}")
    img.setdefault("file", f"{base}/glance/v2/images/{image_id}/file")
    img.setdefault("schema", f"{base}/glance/v2/schemas/image")
    return img


@app.get("/glance/v2/schemas/image")
def glance_schema_image() -> dict[str, Any]:
    # Minimal schema (clients rarely need it for read-only operations).
    return {"name": "image", "properties": {"id": {}, "name": {}, "status": {}, "visibility": {}}}


# -----------------------
# Nova (Compute) - under /nova/*
# -----------------------


@app.get("/nova/")
def nova_versions() -> dict[str, Any]:
    return {
        "versions": [
            {
                "id": "v2.1",
                "status": "CURRENT",
                "version": "2.38",
                "min_version": "2.1",
                "updated": "2013-07-23T11:33:21Z",
            }
        ]
    }


@app.get("/nova/v2.1/{tenant_id}")
def nova_show_version(tenant_id: str) -> dict[str, Any]:
    return {
        "version": {
            "id": "v2.1",
            "status": "CURRENT",
            "version": "2.38",
            "min_version": "2.1",
            "updated": "2013-07-23T11:33:21Z",
        }
    }


@app.get("/nova/v2.1/{tenant_id}/os-availability-zone")
def nova_availability_zones(tenant_id: str) -> dict[str, Any]:
    return {
        "availabilityZoneInfo": [
            {
                "zoneName": "nova",
                "zoneState": {"available": True},
            }
        ]
    }


@app.get("/nova/v2.1/{tenant_id}/os-availability-zone/detail")
def nova_availability_zones_detail(tenant_id: str) -> dict[str, Any]:
    return {
        "availabilityZoneInfo": [
            {
                "zoneName": "nova",
                "zoneState": {"available": True},
                "hosts": {},
            }
        ]
    }


@app.get("/nova/v2.1/{tenant_id}/servers")
def nova_list_servers(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    base = _base_url(request)
    servers = [_server_to_nova(store, s, base=base, tenant_id=tenant_id) for s in store.servers.values()]
    return {"servers": servers}


@app.get("/nova/v2.1/{tenant_id}/servers/detail")
def nova_list_servers_detail(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    base = _base_url(request)
    servers = [_server_to_nova(store, s, base=base, tenant_id=tenant_id) for s in store.servers.values()]
    return {"servers": servers}


@app.get("/nova/v2.1/{tenant_id}/servers/{server_id}")
def nova_get_server(tenant_id: str, server_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    srv = store.servers.get(server_id)
    if not isinstance(srv, dict):
        raise HTTPException(status_code=404, detail="Server not found")
    base = _base_url(request)
    return {"server": _server_to_nova(store, srv, base=base, tenant_id=tenant_id)}


@app.post("/nova/v2.1/{tenant_id}/servers", status_code=202)
async def nova_create_server(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = await request.json()
    server_req = (body or {}).get("server") if isinstance(body, dict) else None
    if not isinstance(server_req, dict):
        raise HTTPException(status_code=400, detail="Invalid server request")

    name = str(server_req.get("name") or "").strip() or "server"
    image_ref = server_req.get("imageRef") or server_req.get("image_id")
    image_id = _extract_ref_id(image_ref) or ""
    flavor_ref = server_req.get("flavorRef") or server_req.get("flavor_id") or server_req.get("flavor")
    flavor_id = _extract_ref_id(flavor_ref) or ""
    metadata = server_req.get("metadata") if isinstance(server_req.get("metadata"), dict) else {}
    docker_image = _resolve_docker_image(image_ref, metadata=metadata, store=store)

    docker_command = metadata.get("docker_command") or metadata.get("command")
    if not docker_command:
        docker_command = _decode_user_data(server_req.get("user_data"))
    if not docker_command and DEFAULT_DOCKER_COMMAND:
        docker_command = DEFAULT_DOCKER_COMMAND
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        environment = None

    server_id = _new_uuid()
    device_name = f"{_slug(name, fallback='srv')}-{server_id[:8]}"

    # Create in emulation as a dockerized host.
    await _ensure_emulation_running()
    props: dict[str, Any] = {
        "dockerized": True,
        "docker_image": docker_image,
        "node_id": server_id,
        "openstack_server_id": server_id,
        "openstack_tenant_id": tenant_id,
    }
    if isinstance(docker_command, str) and docker_command.strip():
        props["command"] = docker_command.strip()
    if environment:
        props["environment"] = environment

    try:
        await _orch_post(
            "/api/emulation/devices/add",
            {
                "topology_id": TOPOLOGY_ID,
                "name": device_name,
                "device_type": "host",
                "properties": props,
                "node_id": server_id,
            },
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to create server in emulation: {exc.response.text}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to create server in emulation: {exc}") from exc

    store.server_device[server_id] = device_name

    # Attach requested networks (uuid or port id).
    requested_networks = server_req.get("networks")
    if isinstance(requested_networks, list):
        for n in requested_networks:
            if not isinstance(n, dict):
                continue
            port_id = n.get("port")
            net_id = n.get("uuid") or n.get("network")
            if isinstance(port_id, str) and port_id in store.ports:
                store.ports[port_id]["device_id"] = server_id
                await _attach_port_to_server(port_id, server_id)
            elif isinstance(net_id, str) and net_id:
                # Create a port and attach.
                port_obj = {
                    "id": _new_uuid(),
                    "name": "",
                    "network_id": net_id,
                    "admin_state_up": True,
                    "status": "ACTIVE",
                    "mac_address": _random_mac(),
                    "device_id": server_id,
                    "device_owner": "compute:nova",
                    "fixed_ips": [],
                }
                ip = _allocate_ip(net_id)
                if ip:
                    # Choose first subnet for this network, if any.
                    subnet_id = None
                    for s in store.subnets.values():
                        if isinstance(s, dict) and s.get("network_id") == net_id:
                            subnet_id = s.get("id")
                            break
                    if subnet_id:
                        port_obj["fixed_ips"] = [{"subnet_id": subnet_id, "ip_address": ip}]
                store.ports[str(port_obj["id"])] = port_obj
                await _attach_port_to_server(str(port_obj["id"]), server_id)

    server_obj = {
        "id": server_id,
        "name": name,
        "status": "ACTIVE",
        "created": _iso_utc(),
        "updated": _iso_utc(),
        "image_id": image_id,
        "flavor_id": flavor_id,
        "metadata": metadata,
        "docker_image": docker_image,
    }
    store.servers[server_id] = server_obj

    base = _base_url(request)
    return {"server": _server_to_nova(store, server_obj, base=base, tenant_id=tenant_id)}


@app.delete("/nova/v2.1/{tenant_id}/servers/{server_id}", status_code=204)
async def nova_delete_server(tenant_id: str, server_id: str) -> Response:
    store: MemoryStore = app.state.store
    srv = store.servers.get(server_id)
    if not isinstance(srv, dict):
        raise HTTPException(status_code=404, detail="Server not found")
    device_name = store.server_device.get(server_id)
    if device_name:
        try:
            await _orch_delete(f"/api/emulation/devices/{device_name}", params={"topology_id": TOPOLOGY_ID})
        except Exception as exc:
            logger.warning("Failed to remove server device %s: %s", device_name, exc)
    # Cleanup ports
    for pid, p in list(store.ports.items()):
        if isinstance(p, dict) and p.get("device_id") == server_id:
            store.ports.pop(pid, None)
    store.servers.pop(server_id, None)
    store.server_device.pop(server_id, None)
    return Response(status_code=204)

@app.get("/nova/v2.1/{tenant_id}/flavors")
def nova_list_flavors(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    base = _base_url(request)
    return {"flavors": [_flavor_to_nova(f, base=base, tenant_id=tenant_id, detail=False) for f in store.flavors.values()]}


@app.get("/nova/v2.1/{tenant_id}/flavors/detail")
def nova_list_flavors_detail(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    base = _base_url(request)
    return {"flavors": [_flavor_to_nova(f, base=base, tenant_id=tenant_id, detail=True) for f in store.flavors.values()]}


@app.get("/nova/v2.1/{tenant_id}/flavors/{flavor_id}")
def nova_get_flavor(tenant_id: str, flavor_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    flavor = store.flavors.get(flavor_id)
    if not isinstance(flavor, dict):
        # Some clients pass the flavor name as id; try name->id mapping.
        by_name_id = store.flavor_name_to_id.get(flavor_id)
        if by_name_id:
            flavor = store.flavors.get(by_name_id)
    if not isinstance(flavor, dict):
        raise HTTPException(status_code=404, detail="Flavor not found")
    base = _base_url(request)
    return {"flavor": _flavor_to_nova(flavor, base=base, tenant_id=tenant_id, detail=True)}


@app.post("/nova/v2.1/{tenant_id}/flavors", status_code=200)
async def nova_create_flavor(tenant_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = await request.json()
    flv_req = (body or {}).get("flavor") if isinstance(body, dict) else None
    if not isinstance(flv_req, dict):
        raise HTTPException(status_code=400, detail="Invalid flavor request")

    name = str(flv_req.get("name") or "").strip() or f"flavor-{len(store.flavors)+1}"
    ram = int(flv_req.get("ram") or 64)
    vcpus = int(flv_req.get("vcpus") or 1)
    disk = int(flv_req.get("disk") or 1)
    flavor_id = flv_req.get("id")
    fid = str(flavor_id).strip() if isinstance(flavor_id, (str, int)) and str(flavor_id).strip() else None
    is_public = bool(flv_req.get("os-flavor-access:is_public", True))

    extra_specs = flv_req.get("extra_specs") if isinstance(flv_req.get("extra_specs"), dict) else None
    flavor = store._register_flavor(name=name, ram=ram, vcpus=vcpus, disk=disk, flavor_id=fid, is_public=is_public, extra_specs=extra_specs)
    base = _base_url(request)
    return {"flavor": _flavor_to_nova(flavor, base=base, tenant_id=tenant_id, detail=True)}


@app.delete("/nova/v2.1/{tenant_id}/flavors/{flavor_id}", status_code=202)
async def nova_delete_flavor(tenant_id: str, flavor_id: str) -> Response:
    store: MemoryStore = app.state.store
    fid = flavor_id
    # Allow deletion by name as well.
    if fid not in store.flavors and flavor_id in store.flavor_name_to_id:
        fid = store.flavor_name_to_id[flavor_id]
    if fid in store.builtin_flavor_ids:
        return Response(status_code=202)
    store.flavors.pop(fid, None)
    # Clean up name map entries
    for name, mapped in list(store.flavor_name_to_id.items()):
        if mapped == fid:
            store.flavor_name_to_id.pop(name, None)
    return Response(status_code=202)


@app.get("/nova/v2.1/{tenant_id}/flavors/{flavor_id}/os-extra_specs")
def nova_get_flavor_extra_specs(tenant_id: str, flavor_id: str) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    flavor = store.flavors.get(flavor_id)
    if not isinstance(flavor, dict):
        by_name_id = store.flavor_name_to_id.get(flavor_id)
        if by_name_id:
            flavor = store.flavors.get(by_name_id)
    if not isinstance(flavor, dict):
        raise HTTPException(status_code=404, detail="Flavor not found")
    extra = flavor.get("extra_specs")
    return {"extra_specs": extra if isinstance(extra, dict) else {}}


@app.post("/nova/v2.1/{tenant_id}/flavors/{flavor_id}/os-extra_specs", status_code=200)
async def nova_set_flavor_extra_specs(tenant_id: str, flavor_id: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    flavor = store.flavors.get(flavor_id)
    if not isinstance(flavor, dict) and flavor_id in store.flavor_name_to_id:
        flavor = store.flavors.get(store.flavor_name_to_id[flavor_id])
    if not isinstance(flavor, dict):
        raise HTTPException(status_code=404, detail="Flavor not found")

    body = await request.json()
    extras = (body or {}).get("extra_specs") if isinstance(body, dict) else None
    if not isinstance(extras, dict):
        raise HTTPException(status_code=400, detail="Invalid extra_specs payload")

    current = flavor.get("extra_specs")
    if not isinstance(current, dict):
        current = {}
    for k, v in extras.items():
        if isinstance(k, str):
            current[k] = str(v)
    flavor["extra_specs"] = current
    return {"extra_specs": current}


@app.put("/nova/v2.1/{tenant_id}/flavors/{flavor_id}/os-extra_specs/{key}", status_code=200)
async def nova_put_flavor_extra_spec(tenant_id: str, flavor_id: str, key: str, request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    flavor = store.flavors.get(flavor_id)
    if not isinstance(flavor, dict) and flavor_id in store.flavor_name_to_id:
        flavor = store.flavors.get(store.flavor_name_to_id[flavor_id])
    if not isinstance(flavor, dict):
        raise HTTPException(status_code=404, detail="Flavor not found")

    body = await request.json()
    value = None
    if isinstance(body, dict) and key in body:
        value = body.get(key)
    elif isinstance(body, dict) and "extra_spec" in body and isinstance(body.get("extra_spec"), dict):
        value = body["extra_spec"].get(key)
    if value is None:
        raise HTTPException(status_code=400, detail="Invalid extra spec body")

    current = flavor.get("extra_specs")
    if not isinstance(current, dict):
        current = {}
    current[str(key)] = str(value)
    flavor["extra_specs"] = current
    return {key: str(value)}


@app.delete("/nova/v2.1/{tenant_id}/flavors/{flavor_id}/os-extra_specs/{key}", status_code=202)
async def nova_delete_flavor_extra_spec(tenant_id: str, flavor_id: str, key: str) -> Response:
    store: MemoryStore = app.state.store
    flavor = store.flavors.get(flavor_id)
    if not isinstance(flavor, dict) and flavor_id in store.flavor_name_to_id:
        flavor = store.flavors.get(store.flavor_name_to_id[flavor_id])
    if not isinstance(flavor, dict):
        raise HTTPException(status_code=404, detail="Flavor not found")

    current = flavor.get("extra_specs")
    if isinstance(current, dict):
        current.pop(str(key), None)
        flavor["extra_specs"] = current
    return Response(status_code=202)


# -----------------------
# Neutron (Network) - under /neutron/*
# -----------------------


@app.get("/neutron/")
def neutron_versions() -> dict[str, Any]:
    return {"versions": [{"id": "v2.0", "status": "CURRENT"}]}


@app.get("/neutron/v2.0")
def neutron_show() -> dict[str, Any]:
    return {"version": {"id": "v2.0", "status": "CURRENT"}}


@app.get("/neutron/v2.0/networks")
def neutron_list_networks(name: Optional[str] = None, id: Optional[str] = None) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    items = []
    for n in store.networks.values():
        if not isinstance(n, dict):
            continue
        if isinstance(id, str) and id and str(n.get("id")) != id:
            continue
        if isinstance(name, str) and name and str(n.get("name") or "") != name:
            continue
        items.append(n)
    return {"networks": items}


@app.post("/neutron/v2.0/networks", status_code=201)
async def neutron_create_network(request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = await request.json()
    net_req = (body or {}).get("network") if isinstance(body, dict) else None
    if not isinstance(net_req, dict):
        raise HTTPException(status_code=400, detail="Invalid network request")
    name = str(net_req.get("name") or "").strip() or f"net-{len(store.networks)+1}"
    network_id = _new_uuid()
    net_obj = {
        "id": network_id,
        "name": name,
        "status": "ACTIVE",
        "admin_state_up": True,
        "shared": False,
        "router:external": False,
    }
    store.networks[network_id] = net_obj
    await _materialize_network_switch(network_id)
    return {"network": net_obj}


@app.get("/neutron/v2.0/networks/{network_id}")
def neutron_get_network(network_id: str) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    n = store.networks.get(network_id)
    if not isinstance(n, dict):
        raise HTTPException(status_code=404, detail="Network not found")
    return {"network": n}


@app.delete("/neutron/v2.0/networks/{network_id}", status_code=204)
async def neutron_delete_network(network_id: str) -> Response:
    store: MemoryStore = app.state.store
    store.networks.pop(network_id, None)
    # Best-effort remove switch
    sw = store.network_switch.pop(network_id, None)
    if sw:
        try:
            await _orch_delete(f"/api/emulation/devices/{sw}", params={"topology_id": TOPOLOGY_ID})
        except Exception:
            pass
    # Cleanup ports/subnets
    for sid, s in list(store.subnets.items()):
        if isinstance(s, dict) and s.get("network_id") == network_id:
            store.subnets.pop(sid, None)
    for pid, p in list(store.ports.items()):
        if isinstance(p, dict) and p.get("network_id") == network_id:
            store.ports.pop(pid, None)
    return Response(status_code=204)


@app.get("/neutron/v2.0/subnets")
def neutron_list_subnets(network_id: Optional[str] = None) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    items = []
    for s in store.subnets.values():
        if not isinstance(s, dict):
            continue
        if network_id and s.get("network_id") != network_id:
            continue
        items.append(s)
    return {"subnets": items}


@app.post("/neutron/v2.0/subnets", status_code=201)
async def neutron_create_subnet(request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = await request.json()
    subnet_req = (body or {}).get("subnet") if isinstance(body, dict) else None
    if not isinstance(subnet_req, dict):
        raise HTTPException(status_code=400, detail="Invalid subnet request")
    net_id = str(subnet_req.get("network_id") or "").strip()
    cidr = str(subnet_req.get("cidr") or "").strip()
    if not net_id or net_id not in store.networks:
        raise HTTPException(status_code=404, detail="Network not found")
    if not cidr:
        raise HTTPException(status_code=400, detail="cidr is required")
    subnet_id = _new_uuid()
    obj = {
        "id": subnet_id,
        "network_id": net_id,
        "cidr": cidr,
        "ip_version": int(subnet_req.get("ip_version") or 4),
        "gateway_ip": subnet_req.get("gateway_ip"),
        "enable_dhcp": bool(subnet_req.get("enable_dhcp", True)),
        "name": subnet_req.get("name") or "",
    }
    store.subnets[subnet_id] = obj
    return {"subnet": obj}


@app.get("/neutron/v2.0/ports")
def neutron_list_ports(
    network_id: Optional[str] = None,
    device_id: Optional[str] = None,
    id: Optional[str] = None,
) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    items = []
    for p in store.ports.values():
        if not isinstance(p, dict):
            continue
        if id and str(p.get("id")) != id:
            continue
        if network_id and p.get("network_id") != network_id:
            continue
        if device_id and p.get("device_id") != device_id:
            continue
        items.append(p)
    return {"ports": items}


@app.post("/neutron/v2.0/ports", status_code=201)
async def neutron_create_port(request: Request) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    body = await request.json()
    port_req = (body or {}).get("port") if isinstance(body, dict) else None
    if not isinstance(port_req, dict):
        raise HTTPException(status_code=400, detail="Invalid port request")
    net_id = str(port_req.get("network_id") or "").strip()
    if not net_id or net_id not in store.networks:
        raise HTTPException(status_code=404, detail="Network not found")
    port_id = _new_uuid()
    fixed_ips = []
    ip = _allocate_ip(net_id)
    if ip:
        subnet_id = None
        for s in store.subnets.values():
            if isinstance(s, dict) and s.get("network_id") == net_id:
                subnet_id = s.get("id")
                break
        if subnet_id:
            fixed_ips = [{"subnet_id": subnet_id, "ip_address": ip}]

    device_id = port_req.get("device_id")
    obj = {
        "id": port_id,
        "name": port_req.get("name") or "",
        "network_id": net_id,
        "admin_state_up": bool(port_req.get("admin_state_up", True)),
        "status": "ACTIVE",
        "mac_address": _random_mac(),
        "device_id": device_id if isinstance(device_id, str) else "",
        "device_owner": port_req.get("device_owner") or "",
        "fixed_ips": fixed_ips,
    }
    store.ports[port_id] = obj

    if isinstance(device_id, str) and device_id in store.servers:
        await _attach_port_to_server(port_id, device_id)

    return {"port": obj}


@app.get("/neutron/v2.0/ports/{port_id}")
def neutron_get_port(port_id: str) -> dict[str, Any]:
    store: MemoryStore = app.state.store
    p = store.ports.get(port_id)
    if not isinstance(p, dict):
        raise HTTPException(status_code=404, detail="Port not found")
    return {"port": p}


@app.delete("/neutron/v2.0/ports/{port_id}", status_code=204)
async def neutron_delete_port(port_id: str) -> Response:
    store: MemoryStore = app.state.store
    store.ports.pop(port_id, None)
    return Response(status_code=204)


@app.on_event("startup")
async def startup() -> None:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(VIMEMU_HTTP_TIMEOUT_SECONDS))
    try:
        consul_client.register_service(SERVICE_NAME, SERVICE_PORT)
    except Exception as exc:
        logger.warning("Consul registration failed: %s", exc)


@app.on_event("shutdown")
async def shutdown() -> None:
    try:
        consul_client.deregister_service(SERVICE_NAME)
    except Exception:
        pass
    try:
        await app.state.http.aclose()
    except Exception:
        pass
