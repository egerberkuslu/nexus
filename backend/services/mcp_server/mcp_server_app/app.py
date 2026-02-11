"""
MCP (Master Control Program) Server - Port 8012
Unified API gateway that aggregates all microservices
Provides single entry point for frontend and external clients
"""

import logging
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from typing import Optional, Dict, Any
import os
import json
import base64
import re
from pydantic import BaseModel

from shared.utils.consul_client import ConsulClient
from shared.messaging.rabbitmq import RabbitMQPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Caduceus-Flux MCP Server",
    description="Unified API gateway for all microservices",
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

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()

# HTTP client for service communication
http_client = httpx.AsyncClient(timeout=30.0)

# Service registry cache
service_cache = {}

_swagger_static_mounted = False
try:
    import swagger_ui_bundle  # type: ignore
except Exception:
    swagger_ui_bundle = None

if swagger_ui_bundle:
    try:
        app.mount(
            "/api/docs/static",
            StaticFiles(directory=swagger_ui_bundle.swagger_ui_3_path),
            name="swagger-ui-static",
        )
        _swagger_static_mounted = True
        logger.info("Serving Swagger UI assets from /api/docs/static (no external CDN required).")
    except Exception as exc:
        logger.warning("Failed to mount Swagger UI static assets: %s", exc)


class ServiceRegistry:
    """Manages service discovery and routing"""

    def __init__(self):
        self.services = {
            'topology': {'port': 8001, 'prefix': '/api'},
            'orchestrator': {'port': 8002, 'prefix': '/api'},
            'protocol-manager': {'port': 8003, 'prefix': '/api'},
            'device-manager': {'port': 8004, 'prefix': '/api'},
            'controller-manager': {'port': 8005, 'prefix': '/api'},
            'snapshot': {'port': 8006, 'prefix': '/api'},
            'webshell': {'port': 8007, 'prefix': '/api'},
            'export-import': {'port': 8008, 'prefix': '/api'},
            'topology-generator': {'port': 8009, 'prefix': '/api'},
            'p4-manager': {'port': 8010, 'prefix': '/api'},
            'monitoring': {'port': 8011, 'prefix': '/api'},
            'metrics-collector': {'port': 8013, 'prefix': '/api'},
            'ai-gateway': {'port': 8014, 'prefix': '/api'},
            'mano': {'port': 8015, 'prefix': '/api'},
            'config': {'port': 8016, 'prefix': '/api'},
            'osm-connector': {'port': 8020, 'prefix': '/api'},
            'mcp-tool-hub': {'port': 8018, 'prefix': '/api'},
            'decision-engine': {'port': 8017, 'prefix': '/api'},
            'vimemu': {'port': 6001, 'prefix': '/', 'host': os.getenv("VIMEMU_HOST", "vimemu-service")},
            # Self entry to expose full control-plane inventory via /api/services.
            'mcp-server': {'port': 8012, 'prefix': '/api', 'host': os.getenv("MCP_SERVER_HOST", "mcp-server")},
            # Dynamic runtime service (container name is topology-scoped and discovered at runtime).
            'emulation-runtime': {
                'port': 50051,
                'prefix': '/grpc',
                'dynamic': True,
                'host': os.getenv("EMULATION_RUNTIME_HOST", os.getenv("EMULATION_GRPC_HOST", "localhost")),
            },
        }

    def get_service_url(self, service_name: str) -> Optional[str]:
        """Get service URL by name"""
        if service_name in self.services:
            service_info = self.services[service_name]
            env_host_key = f"{service_name.upper().replace('-', '_')}_HOST"
            host = service_info.get("host") or os.getenv(env_host_key) or f"{service_name}-service"
            port = service_info['port']
            return f"http://{host}:{port}"

        # Try Consul service discovery
        service_info = consul_client.discover_service(service_name)
        if service_info:
            return f"http://{service_info['address']}:{service_info['port']}"

        return None

    def route_path_to_service(self, path: str) -> Optional[tuple[str, str]]:
        """
        Route a path to the appropriate service

        Returns: (service_name, service_path)
        """
        # MCP-handled paths (not proxied to other services)
        mcp_paths = [
            '/api/services', '/api/microservices', '/api/docs', '/api/openapi',
            '/api/redoc', '/api/system', '/api/dashboard', '/api/workflow',
            '/api/health', '/health', '/'
        ]
        for mcp_path in mcp_paths:
            if path == mcp_path or path.startswith(mcp_path + '/'):
                return None

        # Consistent service-prefixed routing: /api/{service}/... -> that service, /api/...
        # Example: /api/topology/projects -> topology-service /api/projects
        if path.startswith("/api/"):
            parts = path.split("/", 3)  # ["", "api", "{service}", "{rest...}"]
            if len(parts) >= 3:
                svc = parts[2]
                if svc in self.services and len(parts) >= 4 and parts[3]:
                    return (svc, "/api/" + parts[3])

        # Path routing rules
        if path.startswith('/api/projects') or path.startswith('/api/topologies') or path.startswith('/api/network-configs'):
            return ('topology', path)
        elif path.startswith('/api/emulation'):
            return ('orchestrator', path)
        elif path.startswith('/api/tests') or path.startswith('/api/infrastructure'):
            return ('orchestrator', path)
        elif path.startswith('/api/pcap'):
            return ('orchestrator', path)
        elif path.startswith('/api/algorithms'):
            return ('orchestrator', path)
        elif path.startswith('/api/protocols'):
            return ('protocol-manager', path)
        elif path.startswith('/api/devices'):
            return ('device-manager', path)
        elif path.startswith('/api/controllers'):
            return ('controller-manager', path)
        elif path.startswith('/api/snapshots'):
            return ('snapshot', path)
        elif path.startswith('/api/shell') or path.startswith('/ws/shell'):
            return ('webshell', path)
        elif path.startswith('/api/export') or path.startswith('/api/import'):
            return ('export-import', path)
        elif path.startswith('/api/generate'):
            return ('topology-generator', path)
        elif path.startswith('/api/p4'):
            return ('p4-manager', path)
        elif path.startswith('/api/metrics') or path.startswith('/api/monitoring'):
            return ('monitoring', path)
        elif path.startswith('/api/ai'):
            return ('ai-gateway', path)
        elif path.startswith('/api/mano'):
            return ('mano', path)
        elif path.startswith('/api/mcp'):
            return ('mcp-tool-hub', path)
        elif path.startswith('/api/osm/'):
            # Topology-scoped OSM connector: /api/osm/{topology_id}/... -> osm-connector-{topology_id[:8]} /api/osm/...
            parts = path.split("/", 4)  # ["", "api", "osm", "{topology_id}", "{rest...}"]
            if len(parts) >= 4 and parts[3]:
                topo_id = parts[3]
                # Only treat it as topology-scoped when it looks like a UUID; otherwise it's a normal OSM endpoint
                if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", topo_id):
                    svc = f"osm-connector-{str(topo_id)[:8]}"
                    rest = parts[4] if len(parts) >= 5 else ""
                    forwarded = "/api/osm" + ("/" + rest if rest else "")
                    return (svc, forwarded)
            return ('osm-connector', path)
        elif path.startswith('/api/osm'):
            # Legacy/global connector
            return ('osm-connector', path)

        return None


service_registry = ServiceRegistry()

def _normalize_service_name(service_name: str) -> str:
    name = (service_name or "").strip()
    aliases = {
        "ai": "ai-gateway",
        "aigateway": "ai-gateway",
        "ai_gateway": "ai-gateway",
        "mano-service": "mano",
        "mano_service": "mano",
        "osm": "osm-connector",
        "osm_connector": "osm-connector",
        "osm-connector-service": "osm-connector",
        "mcp": "mcp-tool-hub",
        "mcp_tool_hub": "mcp-tool-hub",
        "snapshot-service": "snapshot",
        "topology-service": "topology",
    }
    if name in aliases:
        name = aliases[name]
    if name in service_registry.services:
        return name
    alt = name.replace("_", "-")
    if alt in service_registry.services:
        return alt
    return name



def _decode_agent_policy(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Optional defense-in-depth: if ai-gateway provides a policy header, enforce it here too.

    Header format: X-Caduceus-Agent-Policy = base64url(JSON)
    """
    raw = headers.get("x-caduceus-agent-policy") or headers.get("X-Caduceus-Agent-Policy")
    if not raw:
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        data = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _enforce_agent_policy(method: str, path: str, headers: Dict[str, str]) -> None:
    policy = _decode_agent_policy(headers)
    if not policy:
        return
    allowed_methods = policy.get("allowed_methods") or []
    allowed_prefixes = policy.get("allowed_prefixes") or []
    m = (method or "").upper()
    if isinstance(allowed_methods, list) and allowed_methods:
        if m not in {str(x).upper() for x in allowed_methods}:
            raise HTTPException(status_code=403, detail="Denied by agent policy (method)")
    if isinstance(allowed_prefixes, list) and allowed_prefixes:
        if not any(str(path).startswith(str(p)) for p in allowed_prefixes):
            raise HTTPException(status_code=403, detail="Denied by agent policy (path)")


@app.on_event("startup")
async def startup_event():
    """Initialize MCP server on startup"""
    logger.info("Starting MCP Server...")

    # Register with Consul
    consul_client.register_service("mcp-server", 8012)

    # Connect to RabbitMQ
    rabbitmq_publisher.connect()

    logger.info("MCP Server started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down MCP Server...")

    await http_client.aclose()
    consul_client.deregister_service("mcp-server")
    rabbitmq_publisher.disconnect()


# ==================== MCP-Specific Endpoints ====================

@app.get("/api/services", name="list_services")
async def list_services():
    """List all available services"""
    services = []

    for service_name, service_info in service_registry.services.items():
        url = service_registry.get_service_url(service_name)

        # Check service health
        health_status = "unknown"
        if service_info.get("dynamic") and service_name == "emulation-runtime":
            # Runtime containers are topology-scoped. Consider service healthy if orchestrator is reachable.
            try:
                orchestrator_url = service_registry.get_service_url("orchestrator")
                health_response = await http_client.get(f"{orchestrator_url}/health", timeout=2.0)
                health_status = "healthy" if health_response.status_code == 200 else "unhealthy"
            except Exception:
                health_status = "unhealthy"
        else:
            try:
                health_response = await http_client.get(f"{url}/health", timeout=2.0)
                if health_response.status_code == 200:
                    health_status = "healthy"
            except Exception:
                health_status = "unhealthy"

        services.append({
            'name': service_name,
            'url': url,
            'port': service_info['port'],
            'status': health_status
        })

    return {
        'count': len(services),
        'services': services
    }


@app.get("/api/microservices")
async def list_microservices():
    """Backward-compatible alias for /api/services"""
    return await list_services()

@app.get("/api/openapi")
async def list_openapi_specs():
    """List OpenAPI spec URLs for each service (proxied by MCP)."""
    specs = []
    for service_name in service_registry.services.keys():
        specs.append(
            {
                "service": service_name,
                "openapi_url": f"/api/openapi/{service_name}",
                "swagger_url": f"/api/docs/{service_name}",
                "redoc_url": f"/api/redoc/{service_name}",
            }
        )
    return {"count": len(specs), "items": specs}


@app.get("/api/openapi/{service_name}")
async def proxy_openapi_spec(service_name: str):
    """Proxy a service's OpenAPI JSON (FastAPI: /openapi.json) through MCP."""
    service_name = _normalize_service_name(service_name)
    service_url = service_registry.get_service_url(service_name)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    try:
        r = await http_client.get(f"{service_url}/openapi.json", timeout=10.0)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch OpenAPI from {service_name}: {e}")
    # Always return as JSON to keep Swagger UI happy (some upstreams include odd content-types).
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


@app.get("/api/docs")
async def docs_index():
    """Simple HTML index for service docs."""
    services = []
    for name, meta in sorted(service_registry.services.items(), key=lambda x: x[0]):
        services.append(
            {
                "name": name,
                "port": meta.get("port"),
                "swagger": f"/api/docs/{name}",
                "redoc": f"/api/redoc/{name}",
                "openapi": f"/api/openapi/{name}",
            }
        )

    cards = []
    for s in services:
        cards.append(
            f"""
            <a class="card" href="{s["swagger"]}">
              <div class="cardHead">
                <div class="svc">{s["name"]}</div>
                <div class="pill">:{s["port"]}</div>
              </div>
              <div class="links">
                <a class="link" href="{s["swagger"]}" onclick="event.stopPropagation()">Swagger</a>
                <span class="sep">·</span>
                <a class="link" href="{s["redoc"]}" onclick="event.stopPropagation()">ReDoc</a>
                <span class="sep">·</span>
                <a class="link mono" href="{s["openapi"]}" onclick="event.stopPropagation()">OpenAPI</a>
              </div>
              <div class="hint">Open in Swagger by default</div>
            </a>
            """
        )

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Caduceus-Flux · Service Docs</title>
    <style>
      :root {{
        --bg: #0b1220;
        --card: rgba(255,255,255,.06);
        --card2: rgba(255,255,255,.08);
        --text: rgba(255,255,255,.92);
        --muted: rgba(255,255,255,.65);
        --border: rgba(255,255,255,.12);
        --accent: #7c3aed;
        --accent2: #22c55e;
        --shadow: 0 20px 60px rgba(0,0,0,.35);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
        background:
          radial-gradient(1200px 500px at 20% 10%, rgba(124,58,237,.35), transparent 55%),
          radial-gradient(900px 500px at 80% 30%, rgba(34,197,94,.25), transparent 55%),
          radial-gradient(900px 600px at 40% 80%, rgba(59,130,246,.20), transparent 55%),
          var(--bg);
        color: var(--text);
      }}
      .wrap {{ max-width: 1120px; margin: 0 auto; padding: 40px 18px 80px; }}
      .hero {{
        display: flex; gap: 18px; align-items: flex-start; justify-content: space-between;
        padding: 18px; border: 1px solid var(--border); border-radius: 22px;
        background: linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.04));
        box-shadow: var(--shadow);
      }}
      .brand {{
        display: flex; gap: 12px; align-items: center;
      }}
      .logo {{
        width: 44px; height: 44px; border-radius: 14px;
        background: linear-gradient(135deg, rgba(124,58,237,1), rgba(59,130,246,1));
        box-shadow: 0 12px 32px rgba(124,58,237,.35);
      }}
      h1 {{ margin: 0; font-size: 26px; letter-spacing: -0.02em; }}
      .sub {{ margin-top: 6px; color: var(--muted); font-size: 13.5px; line-height: 1.45; }}
      .meta {{
        display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end;
      }}
      .chip {{
        padding: 8px 10px; border: 1px solid var(--border); border-radius: 999px;
        background: rgba(255,255,255,.06); color: var(--muted); font-size: 12px;
      }}
      .chip b {{ color: var(--text); }}
      .search {{
        margin-top: 18px;
        display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap;
      }}
      input {{
        width: min(560px, 100%);
        padding: 12px 14px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(255,255,255,.06);
        color: var(--text);
        outline: none;
      }}
      input::placeholder {{ color: rgba(255,255,255,.45); }}
      .grid {{
        margin-top: 18px;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }}
      @media (max-width: 960px) {{
        .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      }}
      @media (max-width: 640px) {{
        .hero {{ flex-direction: column; }}
        .meta {{ justify-content: flex-start; }}
        .grid {{ grid-template-columns: 1fr; }}
      }}
      .card {{
        display: block;
        text-decoration: none;
        padding: 14px 14px 12px;
        border-radius: 18px;
        border: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(255,255,255,.07), rgba(255,255,255,.04));
        transition: transform .12s ease, background .12s ease, border-color .12s ease;
      }}
      .card:hover {{
        transform: translateY(-1px);
        border-color: rgba(124,58,237,.45);
        background: linear-gradient(180deg, rgba(255,255,255,.10), rgba(255,255,255,.05));
      }}
      .cardHead {{ display:flex; align-items:center; justify-content: space-between; gap: 10px; }}
      .svc {{ font-weight: 800; letter-spacing: -0.01em; }}
      .pill {{
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(0,0,0,.22);
        border: 1px solid rgba(255,255,255,.14);
        color: rgba(255,255,255,.75);
        font-size: 12px;
      }}
      .links {{
        margin-top: 10px;
        display:flex; align-items:center; gap: 8px; flex-wrap: wrap;
        color: var(--muted);
        font-size: 12.5px;
      }}
      .link {{
        color: rgba(255,255,255,.86);
        text-decoration: none;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,.12);
        background: rgba(255,255,255,.04);
      }}
      .link:hover {{ border-color: rgba(255,255,255,.22); background: rgba(255,255,255,.06); }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
      .sep {{ opacity: .5; }}
      .hint {{ margin-top: 10px; color: rgba(255,255,255,.55); font-size: 12px; }}
      .footer {{
        margin-top: 22px; color: rgba(255,255,255,.55); font-size: 12.5px;
      }}
      .footer a {{ color: rgba(255,255,255,.85); text-decoration: none; }}
      .footer a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="hero">
        <div>
          <div class="brand">
            <div class="logo" aria-hidden="true"></div>
            <div>
              <h1>Service Docs</h1>
              <div class="sub">Swagger / ReDoc / OpenAPI for each microservice, served via MCP gateway.</div>
            </div>
          </div>
          <div class="search">
            <input id="q" placeholder="Search services… (e.g. topology, snapshot, monitoring)" autocomplete="off" />
          </div>
        </div>
        <div class="meta">
          <div class="chip"><b>{len(services)}</b> services</div>
          <div class="chip">Base: <span class="mono">/api</span></div>
          <div class="chip">OpenAPI list: <a class="mono" href="/api/openapi">/api/openapi</a></div>
        </div>
      </div>

      <div id="grid" class="grid">
        {''.join(cards)}
      </div>

      <div class="footer">
        Tip: if ReDoc is blank due to blocked CDNs, use the <a href="/api/openapi">OpenAPI JSON</a> endpoints.
      </div>
    </div>
    <script>
      (function() {{
        var q = document.getElementById('q');
        var grid = document.getElementById('grid');
        function filter() {{
          var term = (q.value || '').toLowerCase().trim();
          var cards = grid.querySelectorAll('.card');
          cards.forEach(function(card) {{
            var name = (card.querySelector('.svc') || {{textContent:''}}).textContent.toLowerCase();
            card.style.display = !term || name.indexOf(term) !== -1 ? '' : 'none';
          }});
        }}
        q.addEventListener('input', filter);
      }})();
    </script>
  </body>
</html>"""
    return HTMLResponse(html)


@app.get("/api/docs/{service_name}")
async def swagger_for_service(service_name: str):
    """Swagger UI for a specific service (OpenAPI proxied via MCP)."""
    service_name = _normalize_service_name(service_name)
    if service_name not in service_registry.services:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    swagger_js_url = None
    swagger_css_url = None
    swagger_favicon_url = None
    if _swagger_static_mounted:
        swagger_js_url = "/api/docs/static/swagger-ui-bundle.js"
        swagger_css_url = "/api/docs/static/swagger-ui.css"
        swagger_favicon_url = "/api/docs/static/favicon-32x32.png"

    return get_swagger_ui_html(
        openapi_url=f"/api/openapi/{service_name}",
        title=f"{service_name} · Swagger",
        swagger_js_url=swagger_js_url,
        swagger_css_url=swagger_css_url,
        swagger_favicon_url=swagger_favicon_url or "https://fastapi.tiangolo.com/img/favicon.png",
        swagger_ui_parameters={
            "persistAuthorization": True,
        },
    )


@app.get("/api/redoc")
@app.get("/api/redoc/")
async def redoc_index():
    """Convenience redirect to the docs index (which links to ReDoc per service)."""
    return RedirectResponse(url="/api/docs", status_code=307)


@app.get("/api/redoc/{service_name}")
async def redoc_for_service(service_name: str):
    """ReDoc UI for a specific service (OpenAPI proxied via MCP)."""
    service_name = _normalize_service_name(service_name)
    if service_name not in service_registry.services:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    openapi_url = f"/api/openapi/{service_name}"
    title = f"{service_name} · ReDoc"
    # ReDoc's default CDN can be blocked in some environments; try multiple CDNs and show a friendly error.
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{ margin: 0; padding: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
      #fallback {{
        display: none;
        padding: 18px;
        background: #0b1220;
        color: rgba(255,255,255,.92);
      }}
      #fallback a {{ color: rgba(255,255,255,.95); }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
      .box {{
        margin-top: 10px;
        padding: 12px 14px;
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 12px;
        background: rgba(255,255,255,.06);
      }}
    </style>
  </head>
  <body>
    <noscript>ReDoc requires JavaScript to function. Please enable it to browse the documentation.</noscript>
    <redoc spec-url="{openapi_url}"></redoc>
    <div id="fallback">
      <b>ReDoc failed to load its JavaScript bundle.</b>
      <div class="box">
        This usually happens when your network blocks external CDNs.
        <div style="margin-top:8px">Use OpenAPI JSON instead:</div>
        <div class="mono">{openapi_url}</div>
        <div style="margin-top:8px">Or use Swagger:</div>
        <div><a href="/api/docs/{service_name}">/api/docs/{service_name}</a></div>
      </div>
    </div>
    <script>
      (function() {{
        var urls = [
          "https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js",
          "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
        ];
        function load(i) {{
          if (i >= urls.length) {{
            document.getElementById('fallback').style.display = 'block';
            return;
          }}
          var s = document.createElement('script');
          s.src = urls[i];
          s.async = true;
          s.onload = function() {{ /* ok */ }};
          s.onerror = function() {{ load(i + 1); }};
          document.body.appendChild(s);
        }}
        load(0);
      }})();
    </script>
  </body>
</html>"""
    return HTMLResponse(html)


@app.get("/api/services/{service_name}/health")
async def check_service_health(service_name: str):
    """Check health of a specific service"""
    service_name = _normalize_service_name(service_name)
    service_url = service_registry.get_service_url(service_name)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    try:
        response = await http_client.get(f"{service_url}/health", timeout=5.0)
        return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service {service_name} is not responding: {str(e)}"
        )


@app.get("/api/system/status")
async def system_status():
    """Get overall system status"""
    try:
        # Check all services
        service_statuses = {}

        for service_name in service_registry.services.keys():
            try:
                service_url = service_registry.get_service_url(service_name)
                if service_url:
                    if service_name == "emulation-runtime":
                        # Runtime containers are created per topology; use orchestrator health as proxy.
                        orchestrator_url = service_registry.get_service_url("orchestrator")
                        response = await http_client.get(f"{orchestrator_url}/health", timeout=2.0)
                    else:
                        response = await http_client.get(f"{service_url}/health", timeout=2.0)
                    service_statuses[service_name] = {
                        'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                        'url': service_url
                    }
                else:
                    service_statuses[service_name] = {'status': 'not_found', 'url': None}
            except:
                service_statuses[service_name] = {'status': 'unreachable', 'url': service_url}

        # Calculate overall health
        healthy_count = sum(1 for s in service_statuses.values() if s['status'] == 'healthy')
        total_count = len(service_statuses)

        overall_status = 'healthy' if healthy_count == total_count else 'degraded' if healthy_count > 0 else 'unhealthy'

        return {
            'overall_status': overall_status,
            'healthy_services': healthy_count,
            'total_services': total_count,
            'services': service_statuses
        }

    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/reload")
async def reload_services():
    """Reload service registry from Consul"""
    try:
        # Clear cache
        service_cache.clear()

        # Query Consul for all services
        # This would update the service registry

        return {'success': True, 'message': 'Service registry reloaded'}

    except Exception as e:
        logger.error(f"Failed to reload services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Aggregated Endpoints ====================

@app.get("/api/dashboard")
async def get_dashboard():
    """
    Aggregated dashboard endpoint

    Combines data from multiple services for frontend dashboard
    """
    try:
        dashboard_data = {
            'timestamp': None,
            'projects': [],
            'active_emulations': [],
            'system_health': {},
            'recent_events': []
        }

        # Get projects from Topology Service
        try:
            topology_url = service_registry.get_service_url('topology')
            if topology_url:
                response = await http_client.get(f"{topology_url}/api/projects", timeout=5.0)
                if response.status_code == 200:
                    dashboard_data['projects'] = response.json()
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")

        # Get active emulations from Orchestrator
        try:
            orchestrator_url = service_registry.get_service_url('orchestrator')
            if orchestrator_url:
                response = await http_client.get(f"{orchestrator_url}/api/emulation/active", timeout=5.0)
                if response.status_code == 200:
                    dashboard_data['active_emulations'] = response.json()
        except Exception as e:
            logger.error(f"Failed to get active emulations: {e}")

        # Get system health
        try:
            dashboard_data['system_health'] = await system_status()
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")

        return dashboard_data

    except Exception as e:
        logger.error(f"Failed to get dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflow/create-and-start")
async def create_and_start_workflow(project_name: str, topology_file: str):
    """
    Workflow endpoint: Create project, import topology, and start emulation

    This demonstrates how MCP can orchestrate multi-service workflows
    """
    try:
        workflow_result = {
            'project_id': None,
            'topology_id': None,
            'emulation_id': None,
            'steps': []
        }

        # Step 1: Create project
        try:
            topology_url = service_registry.get_service_url('topology')
            response = await http_client.post(
                f"{topology_url}/api/projects",
                json={'name': project_name, 'description': 'Created via workflow'}
            )

            if response.status_code == 201:
                project_data = response.json()
                workflow_result['project_id'] = project_data['id']
                workflow_result['steps'].append({'step': 'create_project', 'status': 'success'})
            else:
                raise Exception(f"Failed to create project: {response.text}")

        except Exception as e:
            workflow_result['steps'].append({'step': 'create_project', 'status': 'failed', 'error': str(e)})
            return workflow_result

        # Step 2: Import topology
        # (Would need topology file content)

        # Step 3: Start emulation
        # (Would call orchestrator)

        return workflow_result

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """MCP Server health check"""
    return {
        "status": "healthy",
        "service": "mcp-server",
        "version": "1.0.0"
    }

@app.get("/api/health")
async def api_health_check():
    """Convenience alias for /health (useful behind /api/* gateways)."""
    return await health_check()


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Caduceus-Flux MCP Server",
        "version": "1.0.0",
        "description": "Unified API gateway for all microservices",
        "documentation": "/docs",
        "services": list(service_registry.services.keys())
    }


# ==================== Service Proxy ====================

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
async def proxy_request(request: Request, full_path: str):
    """
    Proxy all requests to appropriate microservices

    This is the magic that makes MCP a unified gateway
    """
    try:
        # Get the full path
        path = f"/{full_path}"

        # Enforce agent policy header (defense in depth).
        _enforce_agent_policy(request.method, path, dict(request.headers))

        # Route to service (returns None for MCP-handled paths)
        routing = service_registry.route_path_to_service(path)
        if not routing:
            # This path is either handled by MCP or doesn't exist
            # Let FastAPI handle it (404 if not found)
            raise HTTPException(status_code=404, detail=f"No service found for path: {path}")

        service_name, service_path = routing

        # Get service URL
        service_url = service_registry.get_service_url(service_name)
        if not service_url:
            raise HTTPException(
                status_code=503,
                detail=f"Service {service_name} is not available"
            )

        # Build target URL
        target_url = f"{service_url}{service_path}"

        # Get query parameters
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Get request body
        body = await request.body()

        # Forward request to service
        logger.debug(f"Proxying {request.method} {path} -> {target_url}")

        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']},
            content=body
        )

        # Return response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
