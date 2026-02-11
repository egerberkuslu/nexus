"""
OSM Connector Service (Port 8020)

Purpose:
- Provide an "isolated" integration point to ETSI OSM (SOL005/NBI) similar to how an SDN controller
  is managed by the platform (ONOS/ODL/etc).
- Expose stable, UX-friendly HTTP endpoints for the frontend and other services via MCP gateway.
- Keep an escape hatch: a generic authenticated proxy endpoint for any OSM NBI path.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.utils.consul_client import ConsulClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "osm-connector-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8020"))

OSM_NBI_URL = (os.getenv("OSM_NBI_URL", "") or "").rstrip("/")
OSM_USERNAME = os.getenv("OSM_USERNAME", "")
OSM_PASSWORD = os.getenv("OSM_PASSWORD", "")
OSM_PROJECT_ID = os.getenv("OSM_PROJECT_ID", "")
OSM_TOKEN = os.getenv("OSM_TOKEN", "")

TOKEN_CACHE_TTL_SECONDS = int(os.getenv("OSM_TOKEN_CACHE_TTL_SECONDS", "900"))  # 15 min

app = FastAPI(
    title="Caduceus-Flux OSM Connector",
    description="Isolated adapter/proxy to ETSI OSM NBI (SOL005) for MANO integration",
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


class OsmAuthState:
    def __init__(self) -> None:
        self.token: str = ""
        self.expires_at_s: int = 0

    def valid(self) -> bool:
        return bool(self.token) and self.expires_at_s > (_now_s() + 15)


app.state.osm_auth = OsmAuthState()


def _require_base() -> str:
    if not OSM_NBI_URL:
        raise HTTPException(status_code=500, detail="OSM_NBI_URL is not configured")
    return OSM_NBI_URL


async def _get_http() -> httpx.AsyncClient:
    return app.state.http  # type: ignore[attr-defined]


def _extract_token_from_text(text: str) -> Optional[str]:
    raw = (text or "").strip()
    if not raw:
        return None

    for key in ("id", "_id", "token"):
        m = re.search(rf'(?m)^{re.escape(key)}:\s*[\'"]?([^\s\'"]+)[\'"]?\s*$', raw)
        if m:
            return m.group(1)

    return None


async def _get_token(http: httpx.AsyncClient) -> str:
    if (OSM_TOKEN or "").strip():
        return (OSM_TOKEN or "").strip()

    auth: OsmAuthState = app.state.osm_auth
    if auth.valid():
        return auth.token

    if not (OSM_USERNAME and OSM_PASSWORD):
        raise HTTPException(status_code=500, detail="OSM auth not configured (set OSM_TOKEN or OSM_USERNAME/OSM_PASSWORD)")

    url = f"{_require_base()}/admin/v1/tokens"
    payload: Dict[str, Any] = {"username": OSM_USERNAME, "password": OSM_PASSWORD}
    if (OSM_PROJECT_ID or "").strip():
        payload["project_id"] = (OSM_PROJECT_ID or "").strip()

    resp = await http.post(url, json=payload, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data: Any = {}
    if resp.content:
        try:
            data = resp.json()
        except Exception:
            data = {}
    token = None
    if isinstance(data, dict):
        token = data.get("id") or data.get("_id") or data.get("token")
    if not token:
        token = resp.headers.get("id") or resp.headers.get("X-Subject-Token")
    if not token:
        token = _extract_token_from_text(resp.text or "")
    if not token:
        raw = (resp.text or "").strip()
        if raw and len(raw) > 12 and " " not in raw and "\n" not in raw and "\t" not in raw:
            token = raw
    if not token:
        raise HTTPException(status_code=502, detail="OSM token response did not include token id")

    auth.token = str(token)
    auth.expires_at_s = _now_s() + max(60, TOKEN_CACHE_TTL_SECONDS)
    return auth.token


async def _osm_request(
    http: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    params: Optional[dict] = None,
    json_body: Any = None,
    files: Any = None,
) -> Any:
    base = _require_base()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    token = await _get_token(http)
    headers = {"Authorization": f"Bearer {token}"}
    headers["Accept"] = "application/json"
    resp = await http.request(method.upper(), url, params=params, json=json_body, files=files, headers=headers)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _extract_location_id(location: Optional[str]) -> Optional[str]:
    if not isinstance(location, str):
        return None
    raw = location.strip()
    if not raw:
        return None
    # Location can be absolute URL or relative path.
    raw = raw.rstrip("/")
    if "/" not in raw:
        return raw
    return raw.split("/")[-1] or None


async def _osm_nslcm_action(
    http: httpx.AsyncClient,
    path: str,
    *,
    json_body: Any,
) -> Any:
    """
    Some OSM NBI endpoints return the operation id in the Location header (202 Accepted) instead of the body.
    Normalize to always return a JSON payload that includes an `id` when possible.
    """
    base = _require_base()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    token = await _get_token(http)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = await http.request("POST", url, json=json_body, headers=headers)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data: Any = {}
    if resp.content:
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

    op_id = None
    if isinstance(data, dict):
        op_id = data.get("id") or data.get("_id")
    if not op_id:
        op_id = _extract_location_id(resp.headers.get("Location") or resp.headers.get("location"))

    if op_id and isinstance(data, dict) and "id" not in data and "_id" not in data:
        return {"id": op_id, **data}
    return data


async def _osm_put_binary(
    http: httpx.AsyncClient,
    path: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> Any:
    base = _require_base()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    token = await _get_token(http)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type, "Accept": "application/json"}
    resp = await http.put(url, content=content, headers=headers)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


async def _osm_post_binary(
    http: httpx.AsyncClient,
    path: str,
    content: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> Any:
    base = _require_base()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    token = await _get_token(http)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type, "Accept": "application/json"}
    resp = await http.post(url, content=content, headers=headers)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    if not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/api/osm/info")
def info() -> Dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "osm": {
            "nbi_url": OSM_NBI_URL or None,
            "project_id": OSM_PROJECT_ID or None,
            "auth_mode": "token" if (OSM_TOKEN or "").strip() else ("userpass" if (OSM_USERNAME and OSM_PASSWORD) else "none"),
        },
    }


# -----------------------
# Convenience endpoints
# -----------------------

@app.get("/api/osm/projects")
async def list_projects(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", "/admin/v1/projects")


@app.get("/api/osm/vim-accounts")
async def list_vim_accounts(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", "/admin/v1/vim_accounts")

@app.get("/api/osm/wim-accounts")
async def list_wim_accounts(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", "/admin/v1/wim_accounts")


@app.get("/api/osm/ns-instances")
async def list_ns_instances(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", "/nslcm/v1/ns_instances")


@app.get("/api/osm/ns-instances/{ns_instance_id}")
async def get_ns_instance(ns_instance_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", f"/nslcm/v1/ns_instances/{ns_instance_id}")


class CreateNsRequest(BaseModel):
    nsd_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    vim_account_id: str = ""


@app.post("/api/osm/ns-instances")
async def create_ns_instance(payload: CreateNsRequest, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    vim_account_id = (payload.vim_account_id or "").strip()
    if not vim_account_id:
        try:
            vims = await _osm_request(http, "GET", "/admin/v1/vim_accounts")
        except Exception:
            vims = None

        if isinstance(vims, list) and vims:
            if len(vims) == 1 and isinstance(vims[0], dict):
                vim_account_id = str(vims[0].get("_id") or vims[0].get("id") or "").strip()
            if not vim_account_id:
                for v in vims:
                    if not isinstance(v, dict):
                        continue
                    if str(v.get("name") or "").startswith("mininet-"):
                        vim_account_id = str(v.get("_id") or v.get("id") or "").strip()
                        break
            if not vim_account_id:
                for v in vims:
                    if isinstance(v, dict) and (v.get("_id") or v.get("id")):
                        vim_account_id = str(v.get("_id") or v.get("id") or "").strip()
                        break

    if not vim_account_id:
        raise HTTPException(status_code=400, detail="vim_account_id is required (OSM requires vimAccountId on NS create)")

    body = {
        "nsdId": payload.nsd_id,
        "nsName": payload.name,
        "nsDescription": (payload.description or "").strip() or payload.name,
        "vimAccountId": vim_account_id,
    }
    return await _osm_request(http, "POST", "/nslcm/v1/ns_instances", json_body=body)


@app.post("/api/osm/ns-instances/{ns_instance_id}/instantiate")
async def instantiate_ns_instance(ns_instance_id: str, request: Request, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    params = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(params, dict):
        params = {}

    # OSM NBI variants: some deployments require nsName + nsdId on instantiate.
    if not params.get("nsName") or not params.get("nsdId") or not params.get("vimAccountId"):
        try:
            ns = await _osm_request(http, "GET", f"/nslcm/v1/ns_instances/{ns_instance_id}")
        except Exception:
            ns = {}

        if isinstance(ns, dict):
            inst = ns.get("instantiate_params") if isinstance(ns.get("instantiate_params"), dict) else {}
            ns_name = (
                (inst.get("nsName") if isinstance(inst, dict) else None)
                or ns.get("name")
                or ns.get("nsName")
                or ns.get("name-ref")
            )
            nsd_id = (
                (inst.get("nsdId") if isinstance(inst, dict) else None)
                or ns.get("nsd-id")
                or ns.get("nsdId")
                or ns.get("nsd-ref")
            )
            if not nsd_id and isinstance(ns.get("nsd"), dict):
                nsd_id = ns.get("nsd", {}).get("_id") or ns.get("nsd", {}).get("id")
            vim_id = (
                (inst.get("vimAccountId") if isinstance(inst, dict) else None)
                or ns.get("datacenter")
                or ns.get("vimAccountId")
            )
            ns_desc = (inst.get("nsDescription") if isinstance(inst, dict) else None) or ns.get("description") or ns_name

            if ns_name and not params.get("nsName"):
                params["nsName"] = str(ns_name)
            if nsd_id and not params.get("nsdId"):
                params["nsdId"] = str(nsd_id)
            if vim_id and not params.get("vimAccountId"):
                params["vimAccountId"] = str(vim_id)
            if ns_desc and not params.get("nsDescription"):
                params["nsDescription"] = str(ns_desc)

    return await _osm_nslcm_action(
        http,
        f"/nslcm/v1/ns_instances/{ns_instance_id}/instantiate",
        json_body=params or {},
    )


@app.post("/api/osm/ns-instances/{ns_instance_id}/terminate")
async def terminate_ns_instance(ns_instance_id: str, request: Request, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    params = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(params, dict):
        params = {}
    return await _osm_nslcm_action(
        http,
        f"/nslcm/v1/ns_instances/{ns_instance_id}/terminate",
        json_body=params or {},
    )


@app.delete("/api/osm/ns-instances/{ns_instance_id}")
async def delete_ns_instance(ns_instance_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "DELETE", f"/nslcm/v1/ns_instances/{ns_instance_id}")


@app.get("/api/osm/ns-lcm-op-occs")
async def list_ns_lcm_op_occs(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", "/nslcm/v1/ns_lcm_op_occs")


@app.get("/api/osm/ns-lcm-op-occs/{op_id}")
async def get_ns_lcm_op_occ(op_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _osm_request(http, "GET", f"/nslcm/v1/ns_lcm_op_occs/{op_id}")


# -----------------------
# Package onboarding (best-effort)
# -----------------------

async def _try_paths(
    http: httpx.AsyncClient,
    method: str,
    paths: list[str],
    *,
    params: Optional[dict] = None,
    json_body: Any = None,
    files: Any = None,
) -> Any:
    last_exc: Optional[HTTPException] = None
    for p in paths:
        try:
            return await _osm_request(http, method, p, params=params, json_body=json_body, files=files)
        except HTTPException as exc:
            last_exc = exc
            if exc.status_code not in (404, 405):
                raise
    if last_exc:
        raise last_exc
    raise HTTPException(status_code=502, detail="OSM request failed")

def _guess_package_content_type(upload: UploadFile) -> str:
    """
    OSM NBI content endpoints expect `Content-Type: application/gzip` for .tar.gz packages.
    Some clients default to application/octet-stream which can lead NBI to treat the payload as YAML.
    """
    filename = (upload.filename or "").lower()
    declared = (upload.content_type or "").lower()
    if filename.endswith((".tar.gz", ".tgz")):
        return "application/gzip"
    if filename.endswith(".zip"):
        return "application/zip"
    if declared in ("application/gzip", "application/x-gzip", "application/zip"):
        return upload.content_type or "application/gzip"
    return "application/gzip"


@app.get("/api/osm/nsd-packages")
async def list_nsd_packages(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(http, "GET", ["/nsd/v1/ns_descriptors_content", "/nsd/v1/nsd_packages", "/nsd/v1/ns_descriptors"])


@app.get("/api/osm/vnfd-packages")
async def list_vnfd_packages(http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(http, "GET", ["/vnfpkgm/v1/vnf_packages_content", "/vnfpkgm/v1/vnf_packages", "/vnfpkgm/v1/vnfd_packages"])

@app.get("/api/osm/nsd-packages/{pkg_id}")
async def get_nsd_package(pkg_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(
        http,
        "GET",
        [f"/nsd/v1/ns_descriptors_content/{pkg_id}", f"/nsd/v1/nsd_packages/{pkg_id}", f"/nsd/v1/ns_descriptors/{pkg_id}"],
    )


@app.get("/api/osm/vnfd-packages/{pkg_id}")
async def get_vnfd_package(pkg_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(
        http,
        "GET",
        [
            f"/vnfpkgm/v1/vnf_packages_content/{pkg_id}",
            f"/vnfpkgm/v1/vnf_packages/{pkg_id}",
            f"/vnfpkgm/v1/vnfd_packages/{pkg_id}",
        ],
    )


@app.delete("/api/osm/nsd-packages/{pkg_id}")
async def delete_nsd_package(pkg_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(
        http,
        "DELETE",
        [f"/nsd/v1/ns_descriptors_content/{pkg_id}", f"/nsd/v1/nsd_packages/{pkg_id}", f"/nsd/v1/ns_descriptors/{pkg_id}"],
    )


@app.delete("/api/osm/vnfd-packages/{pkg_id}")
async def delete_vnfd_package(pkg_id: str, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    return await _try_paths(
        http,
        "DELETE",
        [
            f"/vnfpkgm/v1/vnf_packages_content/{pkg_id}",
            f"/vnfpkgm/v1/vnf_packages/{pkg_id}",
            f"/vnfpkgm/v1/vnfd_packages/{pkg_id}",
        ],
    )


@app.post("/api/osm/nsd-packages/upload")
async def upload_nsd_package(package: UploadFile = File(...), http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    content = await package.read()
    content_type = _guess_package_content_type(package)
    try:
        # OSM 18+ prefers the *_content endpoints (binary body).
        return await _osm_post_binary(
            http,
            "/nsd/v1/ns_descriptors_content",
            content,
            content_type=content_type,
        )
    except HTTPException:
        # SOL005-ish flow used by recent OSM releases:
        # 1) create NS descriptor record
        info = await _osm_request(http, "POST", "/nsd/v1/ns_descriptors", json_body={})
        nsd_id = None
        if isinstance(info, dict):
            nsd_id = info.get("id") or info.get("_id")
        if not nsd_id:
            raise HTTPException(status_code=502, detail="OSM did not return an NSD package id")
        # 2) upload package content
        await _osm_put_binary(http, f"/nsd/v1/ns_descriptors/{nsd_id}/nsd_content", content, content_type=content_type)
        # 3) return onboarded descriptor
        return await _osm_request(http, "GET", f"/nsd/v1/ns_descriptors/{nsd_id}")


@app.post("/api/osm/vnfd-packages/upload")
async def upload_vnfd_package(package: UploadFile = File(...), http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    content = await package.read()
    content_type = _guess_package_content_type(package)
    try:
        # OSM 18+ prefers the *_content endpoints (binary body).
        return await _osm_post_binary(
            http,
            "/vnfpkgm/v1/vnf_packages_content",
            content,
            content_type=content_type,
        )
    except HTTPException:
        # SOL005 flow used by recent OSM releases:
        # 1) create VNF package record
        info = await _osm_request(http, "POST", "/vnfpkgm/v1/vnf_packages", json_body={})
        vnf_pkg_id = None
        if isinstance(info, dict):
            vnf_pkg_id = info.get("id") or info.get("_id")
        if not vnf_pkg_id:
            raise HTTPException(status_code=502, detail="OSM did not return a VNF package id")
        # 2) upload package content
        await _osm_put_binary(
            http,
            f"/vnfpkgm/v1/vnf_packages/{vnf_pkg_id}/package_content",
            content,
            content_type=content_type,
        )
        # 3) return onboarded package info (includes links to the VNFD descriptor)
        return await _osm_request(http, "GET", f"/vnfpkgm/v1/vnf_packages/{vnf_pkg_id}")


# -----------------------
# Escape hatch: authenticated proxy
# -----------------------

@app.api_route("/api/osm/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request, http: httpx.AsyncClient = Depends(_get_http)) -> Any:
    """
    Generic proxy to OSM NBI. Use when a convenience endpoint is missing.

    Example:
      GET /api/osm/proxy/nslcm/v1/ns_instances
    """
    method = request.method.upper()
    params = dict(request.query_params)
    body: Any = None
    content_type = request.headers.get("content-type", "")
    if method in ("POST", "PUT", "PATCH") and content_type.startswith("application/json"):
        body = await request.json()
    return await _osm_request(http, method, f"/{path}", params=params or None, json_body=body)


@app.post("/api/osm/proxy-upload/{path:path}")
async def proxy_upload(
    path: str,
    package: UploadFile = File(...),
    field_name: str = "package",
    http: httpx.AsyncClient = Depends(_get_http),
) -> Any:
    """
    Generic multipart upload proxy to OSM NBI.

    Example:
      POST /api/osm/proxy-upload/vnfpkgm/v1/vnf_packages?field_name=package
    """
    content = await package.read()
    files = {field_name: (package.filename or "package.tgz", content, package.content_type or "application/octet-stream")}
    return await _osm_request(http, "POST", f"/{path}", files=files)


@app.on_event("startup")
async def startup() -> None:
    app.state.http = httpx.AsyncClient(timeout=60.0)
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
