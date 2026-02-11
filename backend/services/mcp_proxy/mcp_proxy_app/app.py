"""
Generic MCP HTTP proxy.

Forwards HTTP requests to an upstream URL with basic read-only controls.
"""

from __future__ import annotations

import logging
import os
import base64
from typing import Iterable, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "mcp-proxy-service")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
UPSTREAM_URL = (os.getenv("UPSTREAM_URL") or "").rstrip("/")
UPSTREAM_BASIC_AUTH = os.getenv("UPSTREAM_BASIC_AUTH")
UPSTREAM_AUTH_HEADER = os.getenv("UPSTREAM_AUTH_HEADER")
READ_ONLY = (os.getenv("READ_ONLY", "true").strip().lower() in {"1", "true", "yes", "y", "on"})
ALLOWED_METHODS = [m.strip().upper() for m in (os.getenv("ALLOWED_METHODS") or "").split(",") if m.strip()]
ALLOWED_PREFIXES = [p.strip() for p in (os.getenv("ALLOWED_PREFIXES") or "").split(",") if p.strip()]
BLOCKED_PREFIXES = [p.strip() for p in (os.getenv("BLOCKED_PREFIXES") or "").split(",") if p.strip()]
TIMEOUT_SECONDS = float(os.getenv("PROXY_TIMEOUT_SECONDS", "30"))

if not UPSTREAM_URL:
    logger.warning("UPSTREAM_URL is not set; proxy will return 503 until configured.")

app = FastAPI(
    title="Caduceus-Flux MCP Proxy",
    description="Generic HTTP proxy used as a local MCP server shim",
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
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS))
    logger.info("MCP Proxy started: %s:%s -> %s", SERVICE_NAME, SERVICE_PORT, UPSTREAM_URL or "<unset>")


@app.on_event("shutdown")
async def _shutdown() -> None:
    http: httpx.AsyncClient = app.state.http
    await http.aclose()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "upstream": UPSTREAM_URL}


def _normalize_prefixes(values: Iterable[str]) -> list[str]:
    out = []
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        if not s.startswith("/"):
            s = "/" + s
        out.append(s)
    return out


def _allowed_method(method: str) -> bool:
    if ALLOWED_METHODS:
        return method in ALLOWED_METHODS
    if READ_ONLY and method not in {"GET", "HEAD"}:
        return False
    return True


def _allowed_path(path: str) -> bool:
    blocked = _normalize_prefixes(BLOCKED_PREFIXES)
    if blocked and any(path.startswith(p) for p in blocked):
        return False
    allowed = _normalize_prefixes(ALLOWED_PREFIXES)
    if allowed and not any(path.startswith(p) for p in allowed):
        return False
    return True


def _strip_hop_headers(headers: httpx.Headers) -> dict:
    hop = {
        "connection",
        "content-encoding",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
    return {k: v for k, v in headers.items() if k.lower() not in hop}


def _maybe_apply_upstream_auth(headers: dict) -> dict:
    if UPSTREAM_AUTH_HEADER:
        headers["Authorization"] = UPSTREAM_AUTH_HEADER
        return headers
    if UPSTREAM_BASIC_AUTH:
        token = base64.b64encode(UPSTREAM_BASIC_AUTH.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    if not UPSTREAM_URL:
        raise HTTPException(status_code=503, detail="UPSTREAM_URL is not configured")

    method = request.method.upper()
    if not _allowed_method(method):
        raise HTTPException(status_code=403, detail="Method not allowed")

    req_path = "/" + (path or "")
    if not _allowed_path(req_path):
        raise HTTPException(status_code=403, detail="Path not allowed")

    url = f"{UPSTREAM_URL}{req_path}"
    query = dict(request.query_params)

    body = await request.body()
    headers = _strip_hop_headers(request.headers)
    headers = _maybe_apply_upstream_auth(headers)

    http: httpx.AsyncClient = app.state.http
    try:
        resp = await http.request(method, url, params=query, content=body or None, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_strip_hop_headers(resp.headers),
        media_type=resp.headers.get("content-type"),
    )
