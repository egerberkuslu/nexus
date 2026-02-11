import asyncio
import json
import logging
import os
import re
import shlex
import base64
import hashlib
import math
import time
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken

from shared.database.postgres import get_db, init_db
from shared.models.ai import AIProviderConfig
from shared.models.ai_agents import AIAgent, AIArtifact, AIMessage, AIThread, AIToolCall
from shared.models.ai_runs import AIRun, AIPinnedContext
from shared.models.ml_models import MLModel, MLModelAssignment

from fpdf import FPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Caduceus-Flux AI Gateway",
    description="LLM provider gateway + MCP request generator/executor",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str


Provider = Literal["openai", "anthropic", "gemini", "ollama"]


class ChatRequest(BaseModel):
    provider: Provider
    model: str
    prompt: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    api_key: Optional[str] = Field(default=None, description="Provider API key (not stored)")
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 1024


class ChatResponse(BaseModel):
    provider: Provider
    model: str
    content: str
    raw: Dict[str, Any]


class MCPRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str = Field(description="Must start with /api/")
    query: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None


class GenerateMCPRequestRequest(BaseModel):
    provider: Provider
    model: str
    prompt: str
    api_key: Optional[str] = None
    scope_topology_id: Optional[str] = None


class GenerateMCPRequestResponse(BaseModel):
    request: MCPRequest
    toon: str
    raw: Dict[str, Any]


class ExecuteMCPRequestRequest(BaseModel):
    request: Optional[MCPRequest] = None
    toon: Optional[str] = None
    scope_topology_id: Optional[str] = None


class ExecuteMCPRequestResponse(BaseModel):
    status_code: int
    headers: Dict[str, Any]
    body: Any
    meta: Optional[Dict[str, Any]] = None


class MCPAgentMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str


class MCPAgentRequest(BaseModel):
    provider: Provider
    model: str
    messages: List[MCPAgentMessage]
    api_key: Optional[str] = None
    scope_topology_id: Optional[str] = None
    max_steps: int = 3


class MCPAgentToolCall(BaseModel):
    toon: str
    result: ExecuteMCPRequestResponse


class MCPAgentResponse(BaseModel):
    assistant: str
    tool_calls: List[MCPAgentToolCall]
    raw_steps: List[Dict[str, Any]] = Field(default_factory=list)


class NetworkDiagnoseRequest(BaseModel):
    topology_id: str
    provider: Optional[Provider] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class NetworkDiagnoseResponse(BaseModel):
    topology_id: str
    provider: Provider
    model: str
    content: str
    heuristics: Dict[str, Any]


class NetworkTestAnalyzeRequest(BaseModel):
    topology_id: str
    run_id: str
    provider: Optional[Provider] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class NetworkTestAnalyzeResponse(BaseModel):
    topology_id: str
    run_id: str
    provider: Provider
    model: str
    content: str
    highlights: Dict[str, Any] = Field(default_factory=dict)


class NetworkDiagnosticsAnalyzeRequest(BaseModel):
    topology_id: str
    window_minutes: Optional[int] = 60
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    every_seconds: int = 5
    device: Optional[str] = None
    source: Optional[str] = None
    emulation_id: Optional[str] = None
    fields: List[str] = Field(default_factory=list)
    prompt: Optional[str] = None
    provider: Optional[Provider] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class NetworkDiagnosticsAnalyzeResponse(BaseModel):
    topology_id: str
    provider: Provider
    model: str
    content: str
    summary: Dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    scope: Literal["global", "topology", "both"] = "both"
    allowed_prefixes: List[str] = Field(default_factory=list)
    allowed_methods: List[str] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    agents: List[AgentInfo]


class ThreadInfo(BaseModel):
    id: str
    agent_id: str
    topology_id: Optional[str] = None
    title: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None


class ThreadListResponse(BaseModel):
    threads: List[ThreadInfo]


class ThreadCreateRequest(BaseModel):
    agent_id: str
    topology_id: Optional[str] = None
    title: Optional[str] = None


class ThreadMessageInfo(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content_md: str
    created_at: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class ThreadGetResponse(BaseModel):
    thread: ThreadInfo
    messages: List[ThreadMessageInfo]


class AgentChatContext(BaseModel):
    kind: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    message: str
    topology_id: Optional[str] = None
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    context: Optional[AgentChatContext] = None
    provider: Optional[Provider] = None
    model: Optional[str] = None
    max_steps: int = 4


class AgentRouteInfo(BaseModel):
    mode: Literal["fixed", "router"] = "fixed"
    selected_agent_id: str
    selected_agent_name: str
    reason: Optional[str] = None
    confidence: Optional[float] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    thread_id: str
    thread_agent_id: str
    agent_id: str
    assistant: str
    tool_calls: List[MCPAgentToolCall] = Field(default_factory=list)
    raw_steps: List[Dict[str, Any]] = Field(default_factory=list)
    memory_hits: List[Dict[str, Any]] = Field(default_factory=list)
    route: Optional[AgentRouteInfo] = None
    run: Optional[Dict[str, Any]] = None


class AgentRouteRequest(BaseModel):
    message: str
    topology_id: Optional[str] = None
    provider: Optional[Provider] = None
    model: Optional[str] = None


class AgentRouteResponse(BaseModel):
    route: AgentRouteInfo


class ReportGenerateRequest(BaseModel):
    provider: Optional[Provider] = None
    model: Optional[str] = None
    format: Literal["md", "pdf"] = "md"
    title: Optional[str] = None


class MCPCapabilityItem(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    description: str
    scope: Literal["global", "scoped", "both"] = "both"


class MCPCapabilitiesResponse(BaseModel):
    scope_topology_id: Optional[str] = None
    allowed_prefixes: List[str]
    notes: List[str]
    items: List[MCPCapabilityItem]
    examples: List[str]


DEFAULT_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "ollama": ["llama3.1", "qwen2.5", "mistral"],
}


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_BASE_URL = _env("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
GEMINI_BASE_URL = _env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
MCP_SERVER_URL = _env("MCP_SERVER_URL", "http://mcp-server:8012")
MCP_FALLBACK_GATEWAY_URL = _env("MCP_FALLBACK_GATEWAY_URL", "http://nginx")

GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_RETRY_BACKOFF_SECONDS = float(os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "2"))
GEMINI_MAX_RETRY_DELAY_SECONDS = float(os.getenv("GEMINI_MAX_RETRY_DELAY_SECONDS", "30"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

AI_GATEWAY_HTTP_CONNECT_TIMEOUT = float(os.getenv("AI_GATEWAY_HTTP_CONNECT_TIMEOUT", "10.0"))
AI_GATEWAY_HTTP_READ_TIMEOUT = float(os.getenv("AI_GATEWAY_HTTP_READ_TIMEOUT", "180.0"))
AI_GATEWAY_HTTP_WRITE_TIMEOUT = float(os.getenv("AI_GATEWAY_HTTP_WRITE_TIMEOUT", "60.0"))
AI_GATEWAY_HTTP_POOL_TIMEOUT = float(os.getenv("AI_GATEWAY_HTTP_POOL_TIMEOUT", "10.0"))

http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=AI_GATEWAY_HTTP_CONNECT_TIMEOUT,
        read=AI_GATEWAY_HTTP_READ_TIMEOUT,
        write=AI_GATEWAY_HTTP_WRITE_TIMEOUT,
        pool=AI_GATEWAY_HTTP_POOL_TIMEOUT,
    ),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0),
)


async def _safe_http_request(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    label: str = "upstream",
    attempts: int = 2,
) -> httpx.Response:
    last_exc: Optional[BaseException] = None
    attempts = max(1, int(attempts))
    for i in range(attempts):
        try:
            return await http_client.request(method=method, url=url, params=params, headers=headers, json=json_body)
        except httpx.RequestError as exc:
            last_exc = exc
            if i < attempts - 1:
                await asyncio.sleep(0.25 * (i + 1))
                continue
            logger.warning("%s network error for %s %s: %s", label, method, url, exc)
            raise HTTPException(status_code=502, detail=f"{label} network error: {exc}") from exc
        except Exception as exc:
            last_exc = exc
            logger.warning("%s unexpected error for %s %s: %s", label, method, url, exc)
            raise
    raise HTTPException(status_code=502, detail=f"{label} request failed: {last_exc}")

def _fernet() -> Fernet:
    seed = os.getenv("AI_CREDENTIALS_ENCRYPTION_KEY") or os.getenv("JWT_SECRET_KEY") or "changeme_ai_gateway_key"
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_api_key(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise HTTPException(status_code=500, detail=f"Stored credential cannot be decrypted: {e}")


def _get_or_create_provider_config(db: Session, provider: Provider) -> AIProviderConfig:
    row = db.get(AIProviderConfig, provider)
    if row:
        return row
    row = AIProviderConfig(provider=provider)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_stored_api_key(db: Session, provider: Provider) -> Optional[str]:
    if provider == "ollama":
        return None
    row = db.get(AIProviderConfig, provider)
    if not row or not row.api_key_encrypted:
        return None
    return _decrypt_api_key(row.api_key_encrypted)


def _resolve_api_key(db: Session, provider: Provider, provided: Optional[str]) -> Optional[str]:
    if provided:
        return provided
    stored = _get_stored_api_key(db, provider)
    if stored:
        return stored
    if provider == "openai":
        return OPENAI_API_KEY
    if provider == "anthropic":
        return ANTHROPIC_API_KEY
    if provider == "gemini":
        return GEMINI_API_KEY
    return None


@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()


@app.on_event("startup")
async def startup_event():
    init_db()
    # Seed built-in agent definitions (idempotent).
    try:
        from shared.database.postgres import SessionLocal

        db = SessionLocal()
        try:
            _ensure_builtin_agents(db)
            _ensure_builtin_ml_models(db)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to seed AI agents: %s", exc)


def _builtin_agents() -> List[Dict[str, Any]]:
    return [
        {
            "id": "router",
            "name": "Router (Auto)",
            "description": "Automatically routes each message to the best specialized agent and enforces tool access.",
            "scope": "both",
            "allowed_methods": ["GET"],
            "allowed_prefixes": [],
            "system_prompt": (
                "You are the Router for Caduceus-Flux.\n"
                "Your job is to pick the best specialized agent for each user message.\n"
                "You do not execute tools. You only route.\n"
            ),
        },
        {
            "id": "infra_ops",
            "name": "InfraOps Agent",
            "description": "Nginx/gateway, services, containers, topology isolated infra health and repairs.",
            "scope": "both",
            "allowed_methods": ["GET", "POST"],
            "allowed_prefixes": [
                "/api/infrastructure",
                "/api/services",
                "/api/system",
                "/api/emulation/containers",
                "/api/topologies",
                "/api/mcp",
            ],
            "system_prompt": (
                "You are InfraOps Agent for Caduceus-Flux.\n"
                "Focus on infrastructure reliability, routing, container lifecycle, and per-topology isolated infra.\n"
                "Prefer MCP tools for facts; summarize actions and risks; be precise.\n"
            ),
        },
        {
            "id": "mcp_ops",
            "name": "MCP Ops Agent",
            "description": "External MCP registry/proxy operations and cross-stack MCP checks.",
            "scope": "both",
            "allowed_methods": ["GET", "POST"],
            "allowed_prefixes": [
                "/api/mcp",
            ],
            "system_prompt": (
                "You are the MCP Ops Agent for Caduceus-Flux.\n"
                "Use /api/mcp/* to register, inspect, and proxy MCP servers safely.\n"
                "Prefer read-only calls unless the user explicitly requests writes.\n"
            ),
        },
        {
            "id": "emulation_ops",
            "name": "EmulationOps Agent",
            "description": "Start/stop emulations, device inventory, execute commands, controller connectivity.",
            "scope": "both",
            "allowed_methods": ["GET", "POST"],
            "allowed_prefixes": [
                "/api/emulation",
                "/api/controllers",
                "/api/topologies",
                "/api/infrastructure/topologies",
            ],
            "system_prompt": (
                "You are EmulationOps Agent for Caduceus-Flux.\n"
                "Operate emulations safely. Prefer deterministic steps: discover -> act -> verify.\n"
                "When running commands, keep them short and non-destructive.\n"
            ),
        },
        {
            "id": "diagnostics",
            "name": "Monitoring & Diagnostics Agent",
            "description": "Influx telemetry exploration, diagnostics queries, anomaly/bottleneck analysis, reporting.",
            "scope": "topology",
            "allowed_methods": ["GET", "POST"],
            "allowed_prefixes": [
                "/api/diagnostics",
                "/api/monitoring",
                "/api/metrics-collector",
                "/api/emulation/active",
                "/api/emulation/shell",
                "/api/topologies",
            ],
            "system_prompt": (
                "You are Monitoring & Diagnostics Agent for Caduceus-Flux.\n"
                "Explain telemetry clearly. Prefer querying Influx via /api/diagnostics and correlating with emulation state.\n"
                "Output Markdown with sections: Status, What stands out, Possible causes, Recommendations.\n"
            ),
        },
        {
            "id": "network_config",
            "name": "NetworkConfig Agent",
            "description": "Import/export/apply network configuration, validate IPs/routes/DNS, consistency checks.",
            "scope": "topology",
            "allowed_methods": ["GET", "POST", "PUT", "PATCH"],
            "allowed_prefixes": [
                "/api/network-configs",
                "/api/emulation/network-config",
                "/api/topologies",
                "/api/emulation",
            ],
            "system_prompt": (
                "You are NetworkConfig Agent for Caduceus-Flux.\n"
                "Work with network configuration documents. Validate carefully and avoid destructive changes.\n"
            ),
        },
        {
            "id": "snapshots",
            "name": "Snapshot & Restore Agent",
            "description": "Snapshots, schedules, restore verification, CRIU constraints and troubleshooting.",
            "scope": "topology",
            "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "allowed_prefixes": [
                "/api/snapshots",
                "/api/emulation",
                "/api/topologies",
            ],
            "system_prompt": (
                "You are Snapshot & Restore Agent for Caduceus-Flux.\n"
                "Focus on creating/restoring snapshots for running topology emulations.\n"
                "Be explicit about prerequisites (CRIU, privileges) and verification steps.\n"
            ),
        },
        {
            "id": "admin",
            "name": "Admin Agent",
            "description": "Cross-topology overview and safe global operations.",
            "scope": "global",
            "allowed_methods": ["GET", "POST"],
            "allowed_prefixes": [
                "/api/system",
                "/api/services",
                "/api/projects",
                "/api/topologies",
                "/api/emulation/active",
                "/api/infrastructure",
                "/api/mcp",
            ],
            "system_prompt": (
                "You are Admin Agent for Caduceus-Flux.\n"
                "Operate at global scope. Prefer read-only inspection unless user explicitly asks for changes.\n"
            ),
        },
    ]


def _ensure_builtin_agents(db: Session) -> None:
    for row in _builtin_agents():
        agent = db.get(AIAgent, row["id"])
        payload = {
            "name": row["name"],
            "description": row.get("description") or "",
            "scope": row.get("scope") or "both",
            "allowed_prefixes_json": json.dumps(row.get("allowed_prefixes") or []),
            "allowed_methods_json": json.dumps(row.get("allowed_methods") or ["GET"]),
            "system_prompt": row.get("system_prompt") or "",
            "is_builtin": True,
            "updated_at": datetime.utcnow(),
        }
        if not agent:
            agent = AIAgent(
                id=row["id"],
                created_at=datetime.utcnow(),
                **payload,
            )
            db.add(agent)
        else:
            for k, v in payload.items():
                setattr(agent, k, v)


def _builtin_ml_models() -> List[Dict[str, Any]]:
    return [
        {
            "id": "ml_builtin_anomaly_robust_zscore",
            "task": "anomaly_detection",
            "name": "Baseline: Robust Z-Score",
            "framework": "builtin",
            "algorithm": "robust_zscore",
            "description": "Simple robust z-score/MAD detector (good fallback + drift guardrail).",
        },
        {
            "id": "ml_builtin_anomaly_ewma_zscore",
            "task": "anomaly_detection",
            "name": "Baseline: EWMA Z-Score",
            "framework": "builtin",
            "algorithm": "ewma_zscore",
            "description": "EWMA mean/variance z-score detector (fast, simple, good for streaming).",
        },
        {
            "id": "ml_builtin_anomaly_cusum",
            "task": "anomaly_detection",
            "name": "Baseline: CUSUM",
            "framework": "builtin",
            "algorithm": "cusum",
            "description": "CUSUM change detector (stream-friendly, good for shifts).",
        },
        {
            "id": "ml_builtin_attack_correlation_rules",
            "task": "attack_detection",
            "name": "Baseline: Correlation Rules",
            "framework": "builtin",
            "algorithm": "correlation_rules",
            "description": "Rule-based correlation on metrics/features (placeholder until flow/pcap models are enabled).",
        },
        {
            "id": "ml_builtin_routing_noop",
            "task": "routing_policy",
            "name": "Baseline: No-Op",
            "framework": "builtin",
            "algorithm": "noop",
            "description": "Produces no routing actions (safe default).",
        },
        {
            "id": "ml_builtin_mano_noop",
            "task": "mano_policy",
            "name": "Baseline: No-Op",
            "framework": "builtin",
            "algorithm": "noop",
            "description": "Produces no MANO actions (safe default).",
        },
    ]


def _ensure_builtin_ml_models(db: Session) -> None:
    for row in _builtin_ml_models():
        model = db.get(MLModel, row["id"])
        payload = {
            "task": row["task"],
            "name": row["name"],
            "framework": row.get("framework") or "builtin",
            "algorithm": row.get("algorithm"),
            "version": row.get("version"),
            "description": row.get("description"),
            "artifact_path": None,
            "artifact_filename": None,
            "artifact_sha256": None,
            "artifact_size_bytes": None,
            "input_schema": row.get("input_schema") or {},
            "output_schema": row.get("output_schema") or {},
            "meta": {**(row.get("meta") or {}), "is_builtin": True},
            "updated_at": datetime.utcnow(),
        }
        if not model:
            model = MLModel(id=row["id"], created_at=datetime.utcnow(), **payload)
            db.add(model)
        else:
            for k, v in payload.items():
                setattr(model, k, v)

        # Ensure a default assignment exists for each task (idempotent).
        task = str(row["task"])
        if not db.get(MLModelAssignment, task):
            db.add(MLModelAssignment(task=task, model_id=str(row["id"]), updated_at=datetime.utcnow()))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/ai/providers")
async def list_providers():
    return {
        "providers": [
            {"id": "openai", "label": "OpenAI"},
            {"id": "anthropic", "label": "Anthropic"},
            {"id": "gemini", "label": "Gemini"},
            {"id": "ollama", "label": "Ollama"},
        ]
    }


@app.get("/api/ai/models")
async def list_models(provider: Provider):
    if provider == "ollama":
        try:
            r = await http_client.get(f"{OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
            payload = r.json()
            models = [m.get("name") for m in (payload.get("models") or []) if m.get("name")]
            return {"provider": provider, "models": models or DEFAULT_MODELS["ollama"]}
        except Exception:
            return {"provider": provider, "models": DEFAULT_MODELS["ollama"]}

    return {"provider": provider, "models": DEFAULT_MODELS.get(provider, [])}


class SetProviderCredentialRequest(BaseModel):
    provider: Provider
    api_key: str


@app.get("/api/ai/settings")
async def get_settings(db: Session = Depends(get_db)):
    providers = []
    for p in ["openai", "anthropic", "gemini", "ollama"]:
        provider: Provider = p  # type: ignore[assignment]
        row = db.get(AIProviderConfig, provider)
        configured = bool(row and row.api_key_encrypted) or (provider == "ollama")
        providers.append(
            {
                "provider": provider,
                "configured": configured,
                "default_model": (row.default_model if row else None),
            }
        )
    return {"providers": providers}


class UpdateDefaultModelRequest(BaseModel):
    provider: Provider
    default_model: str


@app.put("/api/ai/settings/default-model")
async def set_default_model(body: UpdateDefaultModelRequest, db: Session = Depends(get_db)):
    row = _get_or_create_provider_config(db, body.provider)
    row.default_model = body.default_model
    db.add(row)
    db.commit()
    return {"ok": True}


@app.put("/api/ai/credentials")
async def set_provider_credential(body: SetProviderCredentialRequest, db: Session = Depends(get_db)):
    if body.provider == "ollama":
        raise HTTPException(status_code=400, detail="Ollama does not require an API key")
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key is required")
    row = _get_or_create_provider_config(db, body.provider)
    row.api_key_encrypted = _encrypt_api_key(body.api_key.strip())
    db.add(row)
    db.commit()
    return {"ok": True}


@app.delete("/api/ai/credentials")
async def clear_provider_credential(provider: Provider, db: Session = Depends(get_db)):
    if provider == "ollama":
        raise HTTPException(status_code=400, detail="Ollama does not require an API key")
    row = _get_or_create_provider_config(db, provider)
    row.api_key_encrypted = None
    db.add(row)
    db.commit()
    return {"ok": True}


# ==================== Operational ML Model Registry ====================

KNOWN_ML_TASKS: List[str] = [
    "anomaly_detection",
    "attack_detection",
    "routing_policy",
    "mano_policy",
]

ALLOWED_MODEL_FRAMEWORKS: set[str] = {"builtin", "onnx", "torchscript"}
ALLOWED_MODEL_EXTS: set[str] = {".onnx", ".pt", ".pth"}


def _ml_models_storage_root() -> str:
    root = (os.getenv("ML_MODELS_STORAGE_ROOT") or "/var/lib/caduceus/ml_models").strip()
    if not root:
        root = "/var/lib/caduceus/ml_models"
    os.makedirs(root, exist_ok=True)
    return root


def _safe_filename(name: str) -> str:
    base = os.path.basename(str(name or ""))
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-")
    return (base[:128] if base else "model.bin")


def _maybe_json_dict(raw: Optional[str], *, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label} JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f"{label} must be a JSON object")
    return parsed


class MLModelInfo(BaseModel):
    id: str
    task: str
    name: str
    algorithm: Optional[str] = None
    framework: str
    version: Optional[str] = None
    description: Optional[str] = None
    artifact_filename: Optional[str] = None
    artifact_sha256: Optional[str] = None
    artifact_size_bytes: Optional[int] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MLModelListResponse(BaseModel):
    models: List[MLModelInfo]


class MLModelAssignmentInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    task: str
    model_id: str


class MLModelAssignmentsResponse(BaseModel):
    tasks: List[str]
    assignments: List[MLModelAssignmentInfo]
    models_by_id: Dict[str, MLModelInfo]


class SetMLModelAssignmentRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    task: str
    model_id: str


@app.get("/api/ai/ml/models", response_model=MLModelListResponse)
async def list_ml_models(
    task: Optional[str] = None,
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(MLModel)
    if task:
        q = q.filter(MLModel.task == str(task))
    if framework:
        q = q.filter(MLModel.framework == str(framework))
    rows: List[MLModel] = q.order_by(MLModel.created_at.desc()).all()

    def _row(r: MLModel) -> MLModelInfo:
        return MLModelInfo(
            id=r.id,
            task=r.task,
            name=r.name,
            algorithm=r.algorithm,
            framework=r.framework,
            version=r.version,
            description=r.description,
            artifact_filename=r.artifact_filename,
            artifact_sha256=r.artifact_sha256,
            artifact_size_bytes=r.artifact_size_bytes,
            input_schema=r.input_schema or {},
            output_schema=r.output_schema or {},
            meta=r.meta or {},
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )

    return MLModelListResponse(models=[_row(r) for r in rows])


@app.get("/api/ai/ml/assignments", response_model=MLModelAssignmentsResponse)
async def get_ml_model_assignments(db: Session = Depends(get_db)):
    assigns: List[MLModelAssignment] = db.query(MLModelAssignment).all()
    model_ids = [a.model_id for a in assigns]
    models: List[MLModel] = []
    if model_ids:
        models = db.query(MLModel).filter(MLModel.id.in_(model_ids)).all()
    models_by_id = {m.id: m for m in models}

    models_payload: Dict[str, MLModelInfo] = {}
    for mid, m in models_by_id.items():
        models_payload[mid] = MLModelInfo(
            id=m.id,
            task=m.task,
            name=m.name,
            algorithm=m.algorithm,
            framework=m.framework,
            version=m.version,
            description=m.description,
            artifact_filename=m.artifact_filename,
            artifact_sha256=m.artifact_sha256,
            artifact_size_bytes=m.artifact_size_bytes,
            input_schema=m.input_schema or {},
            output_schema=m.output_schema or {},
            meta=m.meta or {},
            created_at=m.created_at.isoformat() if m.created_at else None,
            updated_at=m.updated_at.isoformat() if m.updated_at else None,
        )

    return MLModelAssignmentsResponse(
        tasks=list(KNOWN_ML_TASKS),
        assignments=[MLModelAssignmentInfo(task=a.task, model_id=a.model_id) for a in assigns],
        models_by_id=models_payload,
    )


@app.put("/api/ai/ml/assignments")
async def set_ml_model_assignment(body: SetMLModelAssignmentRequest, db: Session = Depends(get_db)):
    task = str(body.task or "").strip()
    if not task:
        raise HTTPException(status_code=400, detail="task is required")
    model_id = str(body.model_id or "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")

    model = db.get(MLModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if str(model.task) != task:
        raise HTTPException(status_code=400, detail=f"Model task mismatch: model.task={model.task} but requested task={task}")

    row = db.get(MLModelAssignment, task)
    if not row:
        row = MLModelAssignment(task=task, model_id=model_id, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.model_id = model_id
        row.updated_at = datetime.utcnow()
        db.add(row)
    db.commit()
    return {"ok": True, "task": task, "model_id": model_id}


@app.get("/api/ai/ml/models/{model_id}", response_model=MLModelInfo)
async def get_ml_model(model_id: str, db: Session = Depends(get_db)):
    row = db.get(MLModel, str(model_id))
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return MLModelInfo(
        id=row.id,
        task=row.task,
        name=row.name,
        algorithm=row.algorithm,
        framework=row.framework,
        version=row.version,
        description=row.description,
        artifact_filename=row.artifact_filename,
        artifact_sha256=row.artifact_sha256,
        artifact_size_bytes=row.artifact_size_bytes,
        input_schema=row.input_schema or {},
        output_schema=row.output_schema or {},
        meta=row.meta or {},
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@app.get("/api/ai/ml/models/{model_id}/download")
async def download_ml_model_artifact(model_id: str, db: Session = Depends(get_db)):
    row = db.get(MLModel, str(model_id))
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    if not row.artifact_path or not row.artifact_filename:
        raise HTTPException(status_code=404, detail="Model has no artifact (builtin or missing file)")
    path = str(row.artifact_path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")
    return FileResponse(path, filename=row.artifact_filename, media_type="application/octet-stream")


@app.post("/api/ai/ml/models/upload", response_model=MLModelInfo)
async def upload_ml_model(
    task: str = Form(...),
    name: str = Form(...),
    framework: str = Form("onnx"),
    algorithm: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    input_schema_json: Optional[str] = Form(None),
    output_schema_json: Optional[str] = Form(None),
    meta_json: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    task = str(task or "").strip()
    if not task:
        raise HTTPException(status_code=400, detail="task is required")
    if task not in KNOWN_ML_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task '{task}'. Known: {', '.join(KNOWN_ML_TASKS)}")

    framework = str(framework or "").strip().lower() or "onnx"
    if framework not in ALLOWED_MODEL_FRAMEWORKS:
        raise HTTPException(status_code=400, detail=f"Unsupported framework '{framework}'. Supported: {', '.join(sorted(ALLOWED_MODEL_FRAMEWORKS))}")
    if framework == "builtin":
        raise HTTPException(status_code=400, detail="Use builtin models via seeding/registration; upload requires a file-backed framework")

    if not name or not str(name).strip():
        raise HTTPException(status_code=400, detail="name is required")

    original_name = file.filename or "model.bin"
    safe_name = _safe_filename(original_name)
    _, ext = os.path.splitext(safe_name)
    ext = ext.lower()
    if ext not in ALLOWED_MODEL_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_MODEL_EXTS))}")

    input_schema = _maybe_json_dict(input_schema_json, label="input_schema_json")
    output_schema = _maybe_json_dict(output_schema_json, label="output_schema_json")
    meta = _maybe_json_dict(meta_json, label="meta_json")

    model_id = str(uuid.uuid4())
    root = _ml_models_storage_root()
    model_dir = os.path.join(root, model_id)
    os.makedirs(model_dir, exist_ok=True)
    artifact_path = os.path.join(model_dir, safe_name)

    hasher = hashlib.sha256()
    size = 0
    try:
        with open(artifact_path, "wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                hasher.update(chunk)
                handle.write(chunk)
    except Exception as exc:
        try:
            if os.path.isfile(artifact_path):
                os.remove(artifact_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to store artifact: {exc}") from exc

    row = MLModel(
        id=model_id,
        task=task,
        name=str(name).strip(),
        algorithm=(str(algorithm).strip() if algorithm else None),
        framework=framework,
        version=(str(version).strip() if version else None),
        description=(str(description).strip() if description else None),
        artifact_path=artifact_path,
        artifact_filename=safe_name,
        artifact_sha256=hasher.hexdigest(),
        artifact_size_bytes=int(size),
        input_schema=input_schema,
        output_schema=output_schema,
        meta=meta,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()

    return MLModelInfo(
        id=row.id,
        task=row.task,
        name=row.name,
        algorithm=row.algorithm,
        framework=row.framework,
        version=row.version,
        description=row.description,
        artifact_filename=row.artifact_filename,
        artifact_sha256=row.artifact_sha256,
        artifact_size_bytes=row.artifact_size_bytes,
        input_schema=row.input_schema or {},
        output_schema=row.output_schema or {},
        meta=row.meta or {},
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@app.delete("/api/ai/ml/models/{model_id}")
async def delete_ml_model(model_id: str, db: Session = Depends(get_db)):
    model_id = str(model_id or "").strip()
    row = db.get(MLModel, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    if (row.meta or {}).get("is_builtin"):
        raise HTTPException(status_code=400, detail="Builtin models cannot be deleted")

    # Block delete if currently assigned.
    assigned = db.query(MLModelAssignment).filter(MLModelAssignment.model_id == model_id).count()
    if assigned:
        raise HTTPException(status_code=409, detail="Model is active for at least one task; reassign before deleting")

    artifact_path = str(row.artifact_path or "")
    artifact_dir = os.path.dirname(artifact_path) if artifact_path else ""
    db.delete(row)
    db.commit()

    # Best-effort cleanup on disk.
    try:
        if artifact_path and os.path.isfile(artifact_path):
            os.remove(artifact_path)
    except Exception:
        pass
    try:
        root = _ml_models_storage_root()
        if artifact_dir and os.path.isdir(artifact_dir) and os.path.commonpath([root, artifact_dir]) == root:
            # remove directory if empty
            if not os.listdir(artifact_dir):
                os.rmdir(artifact_dir)
    except Exception:
        pass

    return {"ok": True}


def _normalize_messages(req: ChatRequest) -> List[ChatMessage]:
    if req.messages and len(req.messages) > 0:
        return req.messages
    if req.prompt is None:
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'messages' is required")
    return [ChatMessage(role="user", content=req.prompt)]


async def _chat_openai(req: ChatRequest) -> ChatResponse:
    if not req.api_key:
        raise HTTPException(status_code=400, detail="OpenAI api_key is required")
    payload = {
        "model": req.model,
        "messages": [m.model_dump() for m in _normalize_messages(req)],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    r = await http_client.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {req.api_key}"},
        json=payload,
    )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.json()
    content = (
        (((raw.get("choices") or [None])[0] or {}).get("message") or {}).get("content")
        or ""
    )
    return ChatResponse(provider=req.provider, model=req.model, content=content, raw=raw)


async def _chat_anthropic(req: ChatRequest) -> ChatResponse:
    if not req.api_key:
        raise HTTPException(status_code=400, detail="Anthropic api_key is required")

    messages = _normalize_messages(req)
    system_texts = [m.content for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]

    payload: Dict[str, Any] = {
        "model": req.model,
        "max_tokens": req.max_tokens,
        "messages": [{"role": m.role, "content": m.content} for m in non_system],
    }
    if system_texts:
        payload["system"] = "\n".join(system_texts)

    r = await http_client.post(
        f"{ANTHROPIC_BASE_URL}/messages",
        headers={
            "x-api-key": req.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
    )
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.json()
    content_parts = raw.get("content") or []
    content = ""
    if isinstance(content_parts, list) and content_parts:
        content = (content_parts[0] or {}).get("text") or ""
    return ChatResponse(provider=req.provider, model=req.model, content=content, raw=raw)


async def _chat_gemini(req: ChatRequest) -> ChatResponse:
    if not req.api_key:
        raise HTTPException(status_code=400, detail="Gemini api_key is required")

    messages = _normalize_messages(req)
    contents = []
    for m in messages:
        if m.role == "system":
            contents.append({"role": "user", "parts": [{"text": f"[system]\n{m.content}"}]})
        elif m.role == "assistant":
            contents.append({"role": "model", "parts": [{"text": m.content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": m.content}]})

    url = f"{GEMINI_BASE_URL}/models/{req.model}:generateContent"
    def _retry_delay_seconds(resp: httpx.Response) -> Optional[float]:
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        try:
            payload = resp.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            msg = ((payload.get("error") or {}).get("message") or "")
            match = re.search(r"retry in ([0-9.]+)s", msg)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
            for detail in (payload.get("error") or {}).get("details") or []:
                if isinstance(detail, dict) and detail.get("@type", "").endswith("RetryInfo"):
                    delay = detail.get("retryDelay") or ""
                    if isinstance(delay, str) and delay.endswith("s"):
                        try:
                            return float(delay[:-1])
                        except ValueError:
                            pass
        return None

    r: httpx.Response
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        r = await http_client.post(url, params={"key": req.api_key}, json={"contents": contents})
        if r.status_code != 429 or attempt >= GEMINI_MAX_RETRIES:
            break
        delay = _retry_delay_seconds(r)
        if delay is None:
            delay = GEMINI_RETRY_BACKOFF_SECONDS * (2**attempt)
        delay = min(delay, GEMINI_MAX_RETRY_DELAY_SECONDS)
        if delay > 0:
            await asyncio.sleep(delay)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.json()
    candidate = ((raw.get("candidates") or [None])[0] or {})
    parts = (((candidate.get("content") or {}).get("parts") or []) or [])
    content = ""
    if parts:
        content = (parts[0] or {}).get("text") or ""
    return ChatResponse(provider=req.provider, model=req.model, content=content, raw=raw)


async def _chat_ollama(req: ChatRequest) -> ChatResponse:
    messages = _normalize_messages(req)
    payload = {
        "model": req.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False,
        "options": {"temperature": req.temperature},
    }
    r = await http_client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.json()
    content = ((raw.get("message") or {}).get("content")) or ""
    return ChatResponse(provider=req.provider, model=req.model, content=content, raw=raw)

async def _chat_dispatch(req: ChatRequest) -> ChatResponse:
    if req.provider == "openai":
        return await _chat_openai(req)
    if req.provider == "anthropic":
        return await _chat_anthropic(req)
    if req.provider == "gemini":
        return await _chat_gemini(req)
    if req.provider == "ollama":
        return await _chat_ollama(req)
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {req.provider}")


@app.post("/api/ai/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, db: Session = Depends(get_db)):
    req.api_key = _resolve_api_key(db, req.provider, req.api_key)
    if req.provider in ("openai", "anthropic", "gemini") and not req.api_key:
        raise HTTPException(status_code=400, detail=f"{req.provider} is not configured. Set API key in AI Settings.")
    return await _chat_dispatch(req)


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in output")

    depth = 0
    in_str = False
    esc = False
    end: Optional[int] = None
    for i, ch in enumerate(text[start:], start=start):
        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
            continue

    if end is None or end <= start:
        raise ValueError("No complete JSON object found in output")
    return json.loads(text[start : end + 1])

_TOON_KV_RE = re.compile(r"^([^=:\s]+)\s*(=|:)\s*(.+)$")


def _parse_toon_value(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and ((raw[0] == raw[-1] == '"') or (raw[0] == raw[-1] == "'")):
        inner = raw[1:-1]
        return inner.replace(r"\\", "\\").replace(r"\"", '"').replace(r"\'", "'")
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        pass
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw


def _set_nested(target: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = [p for p in dotted_key.split(".") if p]
    if not parts:
        return
    cursor: Dict[str, Any] = target
    for part in parts[:-1]:
        next_val = cursor.get(part)
        if not isinstance(next_val, dict):
            next_val = {}
            cursor[part] = next_val
        cursor = next_val
    cursor[parts[-1]] = value


def _flatten(prefix: str, value: Any, out: Dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            _flatten(key, v, out)
        return
    out[prefix] = value


def _format_toon_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    text = str(value)
    if any(ch.isspace() for ch in text) or any(ch in text for ch in ['"', "'", "=", ":"]):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f"\"{escaped}\""
    return text


def request_to_toon(req: MCPRequest) -> str:
    lines: List[str] = [f"{req.method} {req.path}"]

    if req.query:
        tokens = []
        for k, v in req.query.items():
            tokens.append(f"{k}={_format_toon_value(v)}")
        lines.append("query " + " ".join(tokens))

    if req.headers:
        tokens = []
        for k, v in req.headers.items():
            tokens.append(f"{k}={_format_toon_value(v)}")
        lines.append("headers " + " ".join(tokens))

    if req.body is not None:
        if isinstance(req.body, dict):
            flat: Dict[str, Any] = {}
            _flatten("", req.body, flat)
            tokens = [f"{k}={_format_toon_value(v)}" for k, v in flat.items() if k]
            if tokens:
                lines.append("body " + " ".join(tokens))
            else:
                lines.append("body " + _format_toon_value(req.body))
        else:
            lines.append("body " + _format_toon_value(req.body))

    return "\n".join(lines) + "\n"


def _capabilities_text(scope_topology_id: Optional[str]) -> str:
    items = [i for i in _MCP_CAPABILITIES if (not scope_topology_id or i.scope in ("scoped", "both"))]
    lines = [
        "Available MCP endpoints (curated):",
    ]
    if scope_topology_id:
        lines.append("Scoped mode: /api/services and /api/openapi are NOT allowed.")
    else:
        lines.append("NOTE: microservices list is GET /api/services (alias /api/microservices).")
    for it in items:
        lines.append(f"- {it.method} {it.path} — {it.description}")
    if scope_topology_id:
        lines.append(f"Scoped mode: ONLY operate on topology_id={scope_topology_id}.")
        lines.append("Allowed groups: /api/emulation*, /api/snapshots*, /api/topologies/{id}*, /api/monitoring*, /api/network-configs/{id}*.")
        lines.append("Blocked: /api/topologies listing, /api/services, /api/openapi, and unrelated /api/* routes.")
    return "\n".join(lines)


def toon_to_request(text: str) -> MCPRequest:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty TOON")

    if raw.startswith("{"):
        return MCPRequest(**json.loads(raw))

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise ValueError("Empty TOON")

    first = lines[0]
    try:
        parts = shlex.split(first)
    except ValueError:
        # Be resilient to malformed quotes; fall back to whitespace splitting.
        parts = first.split()
    if len(parts) < 2:
        raise ValueError("First line must be: <METHOD> <PATH>")
    # Models sometimes return '/GET' or similar; normalize to letters only.
    method = re.sub(r"[^A-Z]", "", parts[0].upper())
    path = parts[1]
    query: Dict[str, Any] = {}
    headers: Dict[str, str] = {}
    body_obj: Dict[str, Any] = {}
    body_set = False

    for ln in lines[1:]:
        try:
            tokens = shlex.split(ln)
        except ValueError:
            tokens = ln.split()
        if not tokens:
            continue
        section = tokens[0].rstrip(":").lower()
        kv_tokens = tokens[1:]

        for token in kv_tokens:
            m = _TOON_KV_RE.match(token)
            if not m:
                continue
            key = m.group(1)
            value = _parse_toon_value(m.group(3))

            if section in ("query", "q"):
                _set_nested(query, key, value)
            elif section in ("headers", "header", "h"):
                headers[key] = str(value) if value is not None else ""
            elif section in ("body", "b"):
                _set_nested(body_obj, key, value)
                body_set = True
            else:
                # Unknown section; ignore
                continue

    return MCPRequest(
        method=method,  # type: ignore[arg-type]
        path=path,
        query=query or None,
        headers=headers or None,
        body=body_obj if body_set else None,
    )


@app.post("/api/ai/mcp/generate", response_model=GenerateMCPRequestResponse)
async def generate_mcp_request(req: GenerateMCPRequestRequest, request: Request, db: Session = Depends(get_db)):
    system = (
        "You generate ONE HTTP request in TOON (Token-Oriented Object Notation) for the Caduceus-Flux API.\n"
        "Return ONLY TOON text (no markdown).\n"
        "\n"
        "TOON format:\n"
        "<METHOD> <PATH>\n"
        "query key=value key2=value2\n"
        "headers Header=value\n"
        "body key=value nested.key=value\n"
        "\n"
        "Rules:\n"
        "- PATH MUST start with /api/\n"
        "- METHOD must be GET/POST/PUT/PATCH/DELETE\n"
        "- Only include query/headers/body lines if needed\n"
        "- Quote values that contain spaces\n"
        "\n"
        "Endpoint discovery (do not invent endpoints):\n"
        "- GET /api/services (alias /api/microservices) to see available microservices\n"
        "- GET /api/openapi to see docs/spec links\n"
        "- GET /api/openapi/{service_name} to fetch the OpenAPI spec and pick the exact method/path\n"
        "\n"
        "Common API groups (examples):\n"
        "- /api/topologies*, /api/projects*\n"
        "- /api/emulation*\n"
        "- /api/snapshots*\n"
        "- /api/devices*, /api/protocols*, /api/controllers*\n"
        "- /api/monitoring*, /api/metrics*\n"
        "- /api/export, /api/import\n"
        "- /api/generate\n"
    )
    if req.scope_topology_id:
        system += (
            "\n"
            f"Scope: ONLY operate on topology_id={req.scope_topology_id}.\n"
            "Always include topology_id in query/body when relevant.\n"
            "Never reference other topology ids.\n"
        )
    chat_req = ChatRequest(
        provider=req.provider,
        model=req.model,
        api_key=_resolve_api_key(db, req.provider, req.api_key),
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=req.prompt),
        ],
        temperature=0.0,
        max_tokens=512,
    )
    resp = await _chat_dispatch(chat_req)
    try:
        mcp_req = toon_to_request(resp.content)
    except Exception as e:
        # Fallback to JSON output if model ignored TOON instruction
        try:
            obj = _extract_json_object(resp.content)
            mcp_req = MCPRequest(**obj)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail=f"Model did not return a valid TOON/JSON MCP request: {e}",
            )
    mcp_req = _apply_known_path_aliases(mcp_req)
    if req.scope_topology_id:
        mcp_req = _apply_topology_scope(mcp_req, req.scope_topology_id)
    return GenerateMCPRequestResponse(request=mcp_req, toon=request_to_toon(mcp_req), raw=resp.raw)


def _validate_mcp_path(path: str) -> None:
    if not path.startswith("/api/"):
        raise HTTPException(status_code=400, detail="MCP request path must start with /api/")

_TOPOLOGY_ID_KEYS = {"topology_id", "topologyId"}

_MCP_PATH_ALIASES: Dict[str, str] = {
    "/api/microservices": "/api/services",
    "/api/topologies/list": "/api/topologies",
}


def _apply_known_path_aliases(req: MCPRequest) -> MCPRequest:
    alias = _MCP_PATH_ALIASES.get(req.path)
    if alias:
        req.path = alias
    return req


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


def _looks_like_uuid(value: Any) -> bool:
    if not value:
        return False
    return bool(_UUID_RE.match(str(value).strip()))


def _normalize_topology_id_fields(obj: Any) -> Any:
    if not isinstance(obj, dict):
        return obj
    out = dict(obj)
    if "topology_id" not in out and "topologyId" in out:
        out["topology_id"] = out.get("topologyId")
    if "topology_id" not in out and "topology" in out:
        out["topology_id"] = out.get("topology")
    return out


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


async def _resolve_topology_id_by_hint(hint_text: str) -> str:
    term = (hint_text or "").strip()
    if not term:
        raise HTTPException(status_code=422, detail="topology_id is required")
    try:
        r = await http_client.get(f"{MCP_SERVER_URL}/api/topologies")
        r.raise_for_status()
        items = r.json() if r.content else []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to resolve topology name: {e}")
    if not isinstance(items, list):
        raise HTTPException(status_code=502, detail="Unexpected response when resolving topology name")

    term_lower = term.lower()
    term_tokens = set(_tokens(term))
    if not term_tokens:
        term_tokens = {term_lower}

    scored: List[Dict[str, Any]] = []
    for t in items:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        name = t.get("name") or ""
        if not tid or not name:
            continue
        name_str = str(name)
        name_lower = name_str.lower()
        name_tokens = set(_tokens(name_str))

        score = 0
        if term_lower in name_lower or name_lower in term_lower:
            score += 5
        score += sum(1 for tok in term_tokens if tok and tok in name_tokens)

        if score > 0:
            scored.append({"id": tid, "name": name_str, "score": score})

    if not scored:
        raise HTTPException(status_code=422, detail=f"No topology matched: {term}")

    scored.sort(key=lambda x: (-x["score"], x["name"]))
    best = scored[0]
    ties = [s for s in scored if s["score"] == best["score"]]
    if len(ties) > 1:
        preview = [{"id": s["id"], "name": s["name"]} for s in ties[:8]]
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Multiple topologies matched. Be more specific.",
                "matches": preview,
            },
        )
    return str(best["id"])


async def _normalize_mcp_request_for_execution(req: MCPRequest, scope_topology_id: Optional[str]) -> MCPRequest:
    """
    Make tool calls robust:
    - Apply known path aliases
    - Drop bodies for GET/DELETE
    - Normalize topology_id field naming
    - For emulation start: accept topology name fragments in global scope and resolve to id
    """
    req = _apply_known_path_aliases(req)

    if req.method in ("GET", "DELETE"):
        req.body = None

    req.query = _normalize_topology_id_fields(req.query or {}) if req.query else None
    req.body = _normalize_topology_id_fields(req.body) if req.body else None

    if req.path == "/api/emulation/start":
        if scope_topology_id:
            if isinstance(req.body, dict):
                b = dict(req.body)
                b["topology_id"] = scope_topology_id
                req.body = b
            return req

        if isinstance(req.body, dict):
            b = dict(req.body)
            topo = b.get("topology_id")
            if topo and not _looks_like_uuid(topo):
                b["topology_id"] = await _resolve_topology_id_by_hint(str(topo))
                req.body = b
        elif req.body is None:
            req.body = None
        return req

    if req.path == "/api/emulation/containers":
        if req.query:
            q = dict(req.query)
            if "topology_id" in q and q.get("topology_id") and not _looks_like_uuid(q.get("topology_id")):
                q["topology_id"] = await _resolve_topology_id_by_hint(str(q["topology_id"]))
            req.query = q

    if req.path.startswith("/api/snapshots") and isinstance(req.body, dict):
        req.body = _normalize_topology_id_fields(req.body)

    return req

_MCP_CAPABILITIES: List[MCPCapabilityItem] = [
    MCPCapabilityItem(
        method="GET",
        path="/api/system/status",
        description="Overall platform health (all services)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/services",
        description="List microservices registered in MCP",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/openapi",
        description="List per-service Swagger/ReDoc/OpenAPI URLs",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/openapi/{service_name}",
        description="Fetch a microservice OpenAPI spec (JSON) via MCP",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/docs",
        description="Docs index (HTML) for all microservices (via MCP)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/docs/{service_name}",
        description="Swagger UI (HTML) for a microservice (via MCP)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/redoc/{service_name}",
        description="ReDoc UI (HTML) for a microservice (via MCP)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/mcp/servers",
        description="List external MCP servers (registry)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/mcp/servers/{name}",
        description="Get external MCP server config (registry)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="PUT",
        path="/api/mcp/servers/{name}",
        description="Register/update an external MCP server (registry)",
        scope="global",
    ),
    MCPCapabilityItem(
        method="DELETE",
        path="/api/mcp/servers/{name}",
        description="Delete an external MCP server (registry)",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/mcp/profiles",
        description="List MCP server policy profiles",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/mcp/proxy",
        description="Proxy a request to an external MCP server",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/mcp/{topology_id}/servers",
        description="List topology-scoped MCP servers",
        scope="scoped",
    ),
    MCPCapabilityItem(
        method="PUT",
        path="/api/mcp/{topology_id}/servers/{name}",
        description="Register/update a topology-scoped MCP server",
        scope="scoped",
    ),
    MCPCapabilityItem(
        method="DELETE",
        path="/api/mcp/{topology_id}/servers/{name}",
        description="Delete a topology-scoped MCP server",
        scope="scoped",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/mcp/{topology_id}/proxy",
        description="Proxy a request to a topology-scoped MCP server",
        scope="scoped",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/projects",
        description="List projects",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/topologies",
        description="List topologies (blocked in scoped mode)",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/topologies/{topology_id}",
        description="Get a specific topology",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/network-configs/{topology_id}/template",
        description="Generate a network configuration template from the topology",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/network-configs/{topology_id}",
        description="Get latest saved network configuration for a topology",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/network-configs/{topology_id}",
        description="Save a new version of the network configuration for a topology",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/emulation/active",
        description="List active emulations (auto-filtered in scoped mode)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/emulation/containers",
        description="List containers for a topology (requires topology_id query; auto-injected in scoped mode)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/emulation/start",
        description="Start emulation for topology_id (topology_id injected in scoped mode)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/emulation/stop/{emulation_id}",
        description="Stop emulation by emulation_id (validated against scope topology)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/emulation/status/{emulation_id}",
        description="Get emulation status by emulation_id (validated against scope topology)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/devices",
        description="List devices",
        scope="global",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/devices/{device}/execute",
        description="Execute a command on a device",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/protocols",
        description="List supported protocols",
        scope="global",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/protocols/configure",
        description="Configure a protocol on a device",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/controllers",
        description="List controllers",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/monitoring/topology/{topology_id}/metrics",
        description="Get topology metrics",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/export",
        description="Export a topology",
        scope="global",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/import",
        description="Import a topology",
        scope="global",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/generate",
        description="Generate a topology via generator service",
        scope="global",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/snapshots",
        description="List snapshots (filtered by topology_id in scoped mode)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/snapshots",
        description="Create snapshot (topology_id injected in scoped mode if missing)",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/snapshots/{snapshot_id}/restore",
        description="Restore snapshot",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/snapshots/schedules",
        description="List snapshot schedules",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/snapshots/schedules/presets",
        description="List schedule presets",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/snapshots/schedules",
        description="Create snapshot schedule",
        scope="both",
    ),
    MCPCapabilityItem(
        method="GET",
        path="/api/snapshots/schedules/{schedule_id}",
        description="Get schedule details",
        scope="both",
    ),
    MCPCapabilityItem(
        method="PUT",
        path="/api/snapshots/schedules/{schedule_id}",
        description="Update schedule",
        scope="both",
    ),
    MCPCapabilityItem(
        method="DELETE",
        path="/api/snapshots/schedules/{schedule_id}",
        description="Delete schedule",
        scope="both",
    ),
    MCPCapabilityItem(
        method="POST",
        path="/api/snapshots/schedules/{schedule_id}/trigger",
        description="Trigger a schedule immediately",
        scope="both",
    ),
]


def _find_values_for_keys(value: Any, keys: set[str]) -> List[Any]:
    found: List[Any] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in keys:
                found.append(v)
            found.extend(_find_values_for_keys(v, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_values_for_keys(item, keys))
    return found


def _extract_topology_id_from_path(path: str) -> Optional[str]:
    m = re.match(r"^/api/topologies/([^/?#]+)", path)
    if m:
        return m.group(1)
    m = re.match(r"^/api/infrastructure/topologies/([^/?#]+)", path)
    if m:
        return m.group(1)
    m = re.match(r"^/api/network-configs/([^/?#]+)", path)
    if m:
        return m.group(1)
    m = re.match(r"^/api/emulation/sync/([^/?#]+)", path)
    if m:
        return m.group(1)
    m = re.match(r"^/api/monitoring/topology/([^/?#]+)/metrics", path)
    if m:
        return m.group(1)
    return None


def _extract_emulation_id_from_path(path: str) -> Optional[str]:
    m = re.match(r"^/api/emulation/(status|stop|pause|resume|shell)/([^/?#]+)", path)
    if m:
        return m.group(2)
    return None


async def _ensure_emulation_belongs_to_topology(emulation_id: str, topology_id: str) -> None:
    r = await http_client.get(f"{MCP_SERVER_URL}/api/emulation/active")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to validate emulation scope")
    payload = r.json() if r.content else {}
    emulations = payload.get("emulations") or []
    match = next((e for e in emulations if e.get("emulation_id") == emulation_id), None)
    if not match:
        raise HTTPException(status_code=403, detail="Emulation not found for scope validation")
    if match.get("topology_id") != topology_id:
        raise HTTPException(status_code=403, detail="Emulation is outside the current topology scope")


async def _resolve_emulation_id_for_topology(topology_id: str) -> Optional[str]:
    r = await http_client.get(f"{MCP_SERVER_URL}/api/emulation/active")
    if r.status_code != 200:
        return None
    payload = r.json() if r.content else {}
    emulations = payload.get("emulations") or []
    if not isinstance(emulations, list):
        return None

    def _is_running(row: Any) -> bool:
        return isinstance(row, dict) and str(row.get("status") or "").lower() == "running"

    match = next((e for e in emulations if isinstance(e, dict) and e.get("topology_id") == topology_id and _is_running(e)), None)
    if not match:
        match = next((e for e in emulations if isinstance(e, dict) and e.get("topology_id") == topology_id), None)
    if isinstance(match, dict):
        emu_id = match.get("emulation_id")
        return str(emu_id) if emu_id else None
    return None


async def _ensure_monitoring_device_belongs_to_topology(device: str, topology_id: str) -> None:
    r = await http_client.get(f"{MCP_SERVER_URL}/api/emulation/active")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to validate monitoring device scope")
    payload = r.json() if r.content else {}
    emulations = payload.get("emulations") or []
    match = next((e for e in emulations if e.get("topology_id") == topology_id), None)
    if not match or not match.get("emulation_id"):
        raise HTTPException(status_code=403, detail="No running emulation for this topology (cannot validate device)")
    emu_id = match.get("emulation_id")
    r2 = await http_client.get(f"{MCP_SERVER_URL}/api/emulation/shell/{emu_id}")
    if r2.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch emulation shell info for device validation")
    shell = r2.json() if r2.content else {}
    devices = shell.get("devices") or []
    allow: set[str] = set()
    for d in devices:
        if not isinstance(d, dict):
            continue
        allow.add(str(d.get("runtime_name") or "").strip())
        allow.add(str(d.get("name") or "").strip())
        props = d.get("properties") if isinstance(d.get("properties"), dict) else {}
        allow.add(str(props.get("node_id") or "").strip())
    allow = {a for a in allow if a}
    if device not in allow:
        raise HTTPException(status_code=403, detail="Device is outside the current topology scope")


def _apply_topology_scope(req: MCPRequest, topology_id: str) -> MCPRequest:
    if not req.path.startswith(
        (
            "/api/emulation",
            "/api/snapshots",
            "/api/topologies",
            "/api/monitoring",
            "/api/network-configs",
            "/api/infrastructure/topologies",
            "/api/mcp",
        )
    ):
        raise HTTPException(status_code=403, detail="Request is outside the allowed scope for this topology")

    path_topology_id = _extract_topology_id_from_path(req.path)
    if path_topology_id and path_topology_id != topology_id:
        raise HTTPException(status_code=403, detail="Topology id in path does not match scope")

    # Reject mismatched topology ids in query/body if present
    for v in _find_values_for_keys(req.query or {}, _TOPOLOGY_ID_KEYS):
        if v is not None and str(v) != topology_id:
            raise HTTPException(status_code=403, detail="Topology id in query does not match scope")
    for v in _find_values_for_keys(req.body or {}, _TOPOLOGY_ID_KEYS):
        if v is not None and str(v) != topology_id:
            raise HTTPException(status_code=403, detail="Topology id in body does not match scope")

    # Inject topology_id where safe/expected
    if req.path.startswith("/api/emulation/containers"):
        q = dict(req.query or {})
        q.setdefault("topology_id", topology_id)
        req.query = q
        return req

    if req.path == "/api/emulation/active":
        return req

    if req.path.startswith("/api/emulation/start"):
        if isinstance(req.body, dict):
            b = dict(req.body)
            b.setdefault("topology_id", topology_id)
            req.body = b
        return req

    if req.path.startswith("/api/snapshots") and req.method == "GET":
        q = dict(req.query or {})
        q.setdefault("topology_id", topology_id)
        req.query = q
        return req

    if req.path.startswith("/api/snapshots") and req.method != "GET":
        if isinstance(req.body, dict):
            b = dict(req.body)
            b.setdefault("topology_id", topology_id)
            req.body = b
        return req

    if req.path.startswith("/api/topologies/"):
        return req

    if req.path.startswith("/api/infrastructure/topologies/"):
        return req

    if req.path.startswith("/api/monitoring/topology/"):
        return req

    if req.path.startswith("/api/monitoring/devices/"):
        return req

    if req.path.startswith("/api/network-configs/"):
        # For creation, auto-inject topology_id into the config payload if present.
        if req.method in ("POST", "PUT", "PATCH") and isinstance(req.body, dict):
            b = dict(req.body)
            cfg = b.get("config")
            if isinstance(cfg, dict):
                cfg = dict(cfg)
                cfg.setdefault("topology_id", topology_id)
                b["config"] = cfg
                req.body = b
        return req

    if req.path.startswith("/api/mcp/"):
        parts = req.path.split("/", 4)  # ["", "api", "mcp", "{maybe}", "{rest...}"]
        if len(parts) >= 4 and _looks_like_uuid(parts[3]):
            if parts[3] != topology_id:
                raise HTTPException(status_code=403, detail="Topology id in path does not match scope")
            return req

        if req.path.startswith("/api/mcp/proxy"):
            if isinstance(req.body, dict):
                b = dict(req.body)
                topo = b.get("topology_id")
                if topo and str(topo) != topology_id:
                    raise HTTPException(status_code=403, detail="Topology id in body does not match scope")
                b.setdefault("topology_id", topology_id)
                req.body = b
            return req

        if req.path.startswith("/api/mcp/servers"):
            q = dict(req.query or {})
            topo = q.get("topology_id")
            if topo and str(topo) != topology_id:
                raise HTTPException(status_code=403, detail="Topology id in query does not match scope")
            q.setdefault("topology_id", topology_id)
            q.setdefault("include_shared", False)
            req.query = q
            return req

        if req.path.startswith("/api/mcp/profiles"):
            return req

    # Block broad listing
    if req.path == "/api/topologies":
        raise HTTPException(status_code=403, detail="Listing topologies is not allowed in scoped mode")

    return req


@app.get("/api/ai/mcp/capabilities", response_model=MCPCapabilitiesResponse)
async def mcp_capabilities(scope_topology_id: Optional[str] = None):
    """
    Human-friendly description of common MCP APIs that the MCP console can access.
    This is intentionally a curated list (not a full OpenAPI dump).
    """
    allowed_prefixes = ["/api/"]
    notes: List[str] = [
        "All requests must start with /api/.",
        "The MCP console generates TOON and executes the resulting HTTP call through MCP.",
        "Microservices list endpoint is /api/services (alias: /api/microservices).",
        "Docs discovery: /api/openapi (list), /api/openapi/{service} (spec), /api/docs/{service} (Swagger), /api/redoc/{service} (ReDoc).",
        "External MCP registry/proxy endpoints live under /api/mcp/*.",
    ]

    if scope_topology_id:
        notes.append(f"Scoped mode: ONLY operate on topology_id={scope_topology_id}.")
        notes.append("Scoped allowlist: /api/emulation*, /api/snapshots*, /api/topologies/{id}, /api/network-configs/{id}*, /api/mcp/*.")
        notes.append("Blocked in scoped mode: /api/topologies (broad listing) and any unrelated /api/* routes.")
    else:
        notes.append("Global mode: any /api/* route reachable through MCP server is allowed.")

    def _include(item: MCPCapabilityItem) -> bool:
        if not scope_topology_id:
            return True
        return item.scope in ("scoped", "both")

    items = [i for i in _MCP_CAPABILITIES if _include(i)]

    examples: List[str] = [
        "GET /api/system/status",
        "GET /api/services",
        "GET /api/emulation/active",
    ]
    if scope_topology_id:
        examples.extend(
            [
                "GET /api/emulation/containers\nquery topology_id=\"<auto>\"",
                "GET /api/snapshots\nquery topology_id=\"<auto>\"",
                "POST /api/snapshots\nbody name=\"my-snap\" snapshot_type=\"criu_live\" topology_id=\"<auto>\"",
                "POST /api/mcp/{topology_id}/proxy\nbody server=\"grafana\" method=\"GET\" path=\"/api/health\"",
            ]
        )
    else:
        examples.extend(
            [
                "GET /api/topologies",
                "POST /api/emulation/start\nbody topology_id=\"<topology_id>\"",
                "POST /api/mcp/proxy\nbody server=\"grafana\" method=\"GET\" path=\"/api/health\"",
            ]
        )

    return MCPCapabilitiesResponse(
        scope_topology_id=scope_topology_id,
        allowed_prefixes=allowed_prefixes,
        notes=notes,
        items=items,
        examples=examples,
    )


def _trim_text(value: str, limit: int = 8000) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n…(truncated)…\n" + text[-20:]


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        # drop first fence
        lines = lines[1:]
        # drop last fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _summarize_tool_call(toon: str, result: ExecuteMCPRequestResponse) -> str:
    first = next((ln.strip() for ln in (toon or "").splitlines() if ln.strip()), "")
    path = ""
    parts = first.split()
    if len(parts) >= 2:
        path = parts[1]
    body = result.body

    if path == "/api/emulation/start" and isinstance(body, dict):
        emu_id = body.get("emulation_id")
        msg = body.get("message")
        if emu_id:
            return f"Emulation started: {emu_id}"
        if msg:
            return str(msg)
        return "Emulation start requested"

    if path.startswith("/api/emulation/stop/") and isinstance(body, dict):
        msg = body.get("message")
        if msg:
            return str(msg)
        ok = body.get("success")
        if ok is True:
            return "Emulation stopped"
        return "Emulation stop requested"

    if path == "/api/services" and isinstance(body, dict):
        services = body.get("services")
        if isinstance(services, list):
            names = [s.get("name") for s in services if isinstance(s, dict) and s.get("name")]
            if names:
                return f"Microservices ({len(names)}): " + ", ".join(names)

    if path == "/api/openapi" and isinstance(body, dict):
        items = body.get("items")
        if isinstance(items, list):
            names = []
            for it in items[:20]:
                if isinstance(it, dict) and it.get("service"):
                    names.append(str(it["service"]))
            if names:
                more = "" if len(items) <= 20 else f"\n…and {len(items) - 20} more"
                return (
                    f"OpenAPI specs ({len(items)}): " + ", ".join(names) + more +
                    "\nTip: open `/api/docs/<service>` for Swagger or call `GET /api/openapi/<service>` for JSON."
                )

    if path.startswith("/api/openapi/") and isinstance(body, dict):
        info = body.get("info") if isinstance(body.get("info"), dict) else {}
        title = info.get("title") or path.replace("/api/openapi/", "")
        version = info.get("version")
        paths = body.get("paths") if isinstance(body.get("paths"), dict) else {}
        num_paths = len(paths) if isinstance(paths, dict) else 0
        return f"{title} OpenAPI" + (f" v{version}" if version else "") + f" · paths={num_paths}"
    if path == "/api/emulation/active" and isinstance(body, dict):
        emus = body.get("emulations")
        if isinstance(emus, list):
            running = [e for e in emus if isinstance(e, dict) and e.get("status") == "running"]
            return f"Active emulations: {len(emus)} (running: {len(running)})"
    if path == "/api/emulation/containers" and isinstance(body, dict):
        items = body.get("items")
        if isinstance(items, list):
            running = [c for c in items if isinstance(c, dict) and c.get("status") == "running"]
            return f"Containers: {len(items)} (running: {len(running)})"
    if path.startswith("/api/snapshots") and isinstance(body, dict):
        total = body.get("total")
        if isinstance(total, int):
            return f"Snapshots total: {total}"
        items = body.get("items")
        if isinstance(items, list):
            return f"Snapshots: {len(items)}"

    if path == "/api/topologies":
        if isinstance(body, list):
            items = [b for b in body if isinstance(b, dict)]
            names = []
            for t in items[:15]:
                name = t.get("name") or t.get("id")
                tid = t.get("id")
                status = t.get("emulation_status") or ("active" if t.get("is_active") else None)
                nodes = t.get("nodes")
                links = t.get("links")
                node_count = len(nodes) if isinstance(nodes, list) else t.get("node_count")
                link_count = len(links) if isinstance(links, list) else t.get("link_count")
                container_name = t.get("container_name")
                project_id = t.get("project_id")
                if name and tid:
                    suffix = f" (id={tid})"
                    if status:
                        suffix += f", status={status}"
                    if isinstance(node_count, int) and isinstance(link_count, int):
                        suffix += f", nodes={node_count}, links={link_count}"
                    if container_name:
                        suffix += f", container={container_name}"
                    if project_id:
                        suffix += f", project={project_id}"
                    names.append(f"{name}{suffix}")
            if names:
                more = "" if len(items) <= 15 else f"\n…and {len(items) - 15} more"
                return (
                    f"Topologies ({len(items)}):\n- "
                    + "\n- ".join(names)
                    + more
                    + "\n\nMeaning: these are saved network designs; `status=running` means an emulation is currently running for that topology."
                    + "\nNext: say `Run <topology name>` to start one, or `List active emulations` to see running ones."
                )
            return f"Topologies: {len(items)}"

    return f"status_code={result.status_code}"


def _extract_method_path_from_toon(toon: str) -> tuple[str, str]:
    first = next((ln.strip() for ln in (toon or "").splitlines() if ln.strip()), "")
    parts = first.split()
    if len(parts) >= 2:
        return parts[0].upper(), parts[1]
    return "", ""


def _capability_methods_for_path(path: str) -> List[str]:
    methods: List[str] = []
    for cap in _MCP_CAPABILITIES:
        pattern = cap.path
        if "{" in pattern:
            prefix = pattern.split("{", 1)[0]
            if path.startswith(prefix):
                methods.append(cap.method)
        elif pattern == path:
            methods.append(cap.method)
    return sorted(set(methods))


def _infer_method_for_path_only(path: str) -> str:
    methods = _capability_methods_for_path(path)
    if len(methods) == 1:
        return methods[0]
    return "GET"


def _user_asked_for_services(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in ["service", "services", "microservice", "microservices"])


def _user_asked_for_containers(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in ["container", "containers"])


def _pick_best_summary(tool_calls: List[Any], last_user: str) -> str:
    if not tool_calls:
        return "I couldn't complete the request."

    preferred_paths: List[str] = [
        "/api/emulation/start",
        "/api/emulation/stop/",
        "/api/emulation/containers",
        "/api/emulation/active",
        "/api/snapshots",
        "/api/topologies",
        "/api/services",
        "/api/system/status",
    ]

    last_user_wants_services = _user_asked_for_services(last_user)

    scored: List[tuple[int, int, MCPAgentToolCall]] = []
    for idx, tc in enumerate(tool_calls):
        _, path = _extract_method_path_from_toon(tc.toon)
        rank = len(preferred_paths) + 5
        for pidx, p in enumerate(preferred_paths):
            if p.endswith("/") and path.startswith(p):
                rank = pidx
                break
            if path == p:
                rank = pidx
                break

        if path == "/api/services" and not last_user_wants_services:
            rank += 10
        scored.append((rank, idx, tc))

    scored.sort(key=lambda x: (x[0], -x[1]))
    best = scored[0][2]
    return _summarize_tool_call(best.toon, best.result)


def _should_autofinalize_after(tool_call_toon: str, result: ExecuteMCPRequestResponse, last_user: str) -> bool:
    if not (200 <= result.status_code < 300):
        return False
    method, path = _extract_method_path_from_toon(tool_call_toon)
    if not method or not path:
        return False

    if path not in {"/api/emulation/start"} and not path.startswith("/api/emulation/stop/"):
        return False

    t = (last_user or "").lower()
    if any(w in t for w in [" and ", " then ", " also ", "container", "containers", "snapshot", "schedule"]):
        return False
    return True


async def _generate_mcp_from_prompt(
    provider: Provider,
    model: str,
    prompt: str,
    db: Session,
    scope_topology_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> MCPRequest:
    system = (
        "You generate ONE HTTP request in TOON (Token-Oriented Object Notation) for the Caduceus-Flux API.\n"
        "Return ONLY TOON text (no markdown).\n"
        "\n"
        "TOON format:\n"
        "<METHOD> <PATH>\n"
        "query key=value key2=value2\n"
        "headers Header=value\n"
        "body key=value nested.key=value\n"
        "\n"
        "Rules:\n"
        "- PATH MUST start with /api/\n"
        "- METHOD must be GET/POST/PUT/PATCH/DELETE\n"
        "- Only include query/headers/body lines if needed\n"
        "- Quote values that contain spaces\n"
        "\n"
        "Endpoint discovery (do not invent endpoints):\n"
        "- GET /api/services (alias /api/microservices) to see available microservices\n"
        "- GET /api/openapi to see docs/spec links\n"
        "- GET /api/openapi/{service_name} to fetch the OpenAPI spec and pick the exact method/path\n"
        "\n"
        "Common API groups (examples):\n"
        "- /api/topologies*, /api/projects*\n"
        "- /api/emulation*\n"
        "- /api/snapshots*\n"
        "- /api/devices*, /api/protocols*, /api/controllers*\n"
        "- /api/monitoring*, /api/metrics*\n"
        "- /api/export, /api/import\n"
        "- /api/generate\n"
    )
    if scope_topology_id:
        system += (
            "\n"
            f"Scope: ONLY operate on topology_id={scope_topology_id}.\n"
            "Always include topology_id in query/body when relevant.\n"
            "Never reference other topology ids.\n"
        )
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=_resolve_api_key(db, provider, api_key),
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.0,
        max_tokens=512,
    )
    resp = await _chat_dispatch(chat_req)
    try:
        mcp_req = toon_to_request(resp.content)
    except Exception as first_err:
        # Fallback to JSON output if model ignored TOON instruction
        try:
            obj = _extract_json_object(resp.content)
            mcp_req = MCPRequest(**obj)
        except Exception:
            # Last chance: ask model to repair into valid TOON
            repaired = await _repair_toon_output(
                provider=provider,
                model=model,
                db=db,
                api_key=api_key,
                scope_topology_id=scope_topology_id,
                prompt=prompt,
                bad_output=resp.content or "",
                error_hint=str(first_err),
            )
            mcp_req = toon_to_request(repaired)
    mcp_req = _apply_known_path_aliases(mcp_req)
    if scope_topology_id:
        mcp_req = _apply_topology_scope(mcp_req, scope_topology_id)
    return mcp_req


def _coerce_agent_action_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Turn a model response into an agent action:
    - Prefer JSON object {action:tool|final,...}
    - Fallback to raw TOON in plaintext
    """
    content_text = (text or "").strip()
    if not content_text:
        return None
    try:
        obj = _extract_json_object(content_text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Fallback: TOON directly
    maybe = _strip_code_fences(content_text)
    try:
        toon_to_request(maybe)
        return {"action": "tool", "toon": maybe, "reason": "tool call (TOON)"}
    except Exception:
        return None


async def _repair_agent_output(
    provider: Provider,
    model: str,
    db: Session,
    api_key: Optional[str],
    scope_topology_id: Optional[str],
    bad_output: str,
    error_hint: str,
) -> Dict[str, Any]:
    """
    Ask the model to reformat its previous output into the strict agent JSON schema.
    This mirrors the "Claude Desktop + MCP" tool-call contract (structured tool choice).
    """
    system = (
        "You are repairing the previous assistant output.\n"
        "Return ONLY a single JSON object (no markdown), and nothing else.\n"
        "\n"
        "Schema:\n"
        '{"action":"tool","toon":"<TOON request>","reason":"<short>"}\n'
        '{"action":"final","content":"<assistant reply>"}\n'
        "\n"
        "TOON rules:\n"
        "- First line MUST be: <METHOD> <PATH>\n"
        "- PATH MUST start with /api/\n"
        "- METHOD must be GET/POST/PUT/PATCH/DELETE\n"
        "- Use GET /api/services (NOT /api/microservices)\n"
        "\n"
        + _capabilities_text(scope_topology_id)
    )
    user = (
        f"Error: {error_hint}\n"
        "Fix the output to match the schema.\n"
        "Bad output:\n"
        + _trim_text(bad_output, 6000)
    )
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=_resolve_api_key(db, provider, api_key),
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        temperature=0.0,
        max_tokens=400,
    )
    resp = await _chat_dispatch(chat_req)
    obj = _extract_json_object(resp.content)
    if not isinstance(obj, dict):
        raise HTTPException(status_code=422, detail="Repair step did not return a JSON object")
    return obj


async def _repair_toon_output(
    provider: Provider,
    model: str,
    db: Session,
    api_key: Optional[str],
    scope_topology_id: Optional[str],
    prompt: str,
    bad_output: str,
    error_hint: str,
) -> str:
    """
    Ask the model to output valid TOON only.
    """
    system = (
        "You are repairing a broken MCP tool request.\n"
        "Return ONLY valid TOON text (no markdown).\n"
        "\n"
        "TOON format:\n"
        "<METHOD> <PATH>\n"
        "query key=value\n"
        "headers Header=value\n"
        "body key=value nested.key=value\n"
        "\n"
        "Rules:\n"
        "- First line MUST be: <METHOD> <PATH>\n"
        "- PATH MUST start with /api/\n"
        "- METHOD must be GET/POST/PUT/PATCH/DELETE\n"
        "- Use GET /api/services (NOT /api/microservices)\n"
        "- Only include query/headers/body lines if needed\n"
        "\n"
        + _capabilities_text(scope_topology_id)
    )
    user = (
        f"User intent:\n{prompt}\n\n"
        f"Error:\n{error_hint}\n\n"
        "Broken output:\n"
        + _trim_text(bad_output, 6000)
    )
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=_resolve_api_key(db, provider, api_key),
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        temperature=0.0,
        max_tokens=400,
    )
    resp = await _chat_dispatch(chat_req)
    toon = _strip_code_fences(resp.content or "")
    if not toon.strip():
        raise HTTPException(status_code=422, detail="Failed to repair TOON (empty)")
    return toon


async def _execute_mcp_request_scoped(
    mcp_req: MCPRequest,
    scope_topology_id: Optional[str],
    *,
    agent: Optional[AIAgent] = None,
    request_id: Optional[str] = None,
) -> ExecuteMCPRequestResponse:
    mcp_req = await _normalize_mcp_request_for_execution(mcp_req, scope_topology_id)
    if scope_topology_id:
        mcp_req = _apply_topology_scope(mcp_req, scope_topology_id)
        emu_id = _extract_emulation_id_from_path(mcp_req.path)
        if emu_id:
            await _ensure_emulation_belongs_to_topology(emu_id, scope_topology_id)
        if mcp_req.path.startswith("/api/monitoring/devices/"):
            device = mcp_req.path.split("/api/monitoring/devices/", 1)[1].split("?", 1)[0]
            if device:
                await _ensure_monitoring_device_belongs_to_topology(device, scope_topology_id)
    _validate_mcp_path(mcp_req.path)

    url = f"{MCP_SERVER_URL}{mcp_req.path}"
    query = mcp_req.query or {}
    headers = dict(mcp_req.headers or {})
    if request_id:
        headers.setdefault("X-Request-ID", request_id)
    if agent:
        headers.setdefault("X-Caduceus-Agent-Id", agent.id)
        headers.setdefault("X-Caduceus-Agent-Policy", _encode_agent_policy_header(agent))
    body = mcp_req.body

    started = time.perf_counter()
    try:
        r = await http_client.request(
            method=mcp_req.method,
            url=url,
            params=query,
            headers=headers,
            json=body,
        )
    except Exception:
        url = f"{MCP_FALLBACK_GATEWAY_URL}{mcp_req.path}"
        r = await http_client.request(
            method=mcp_req.method,
            url=url,
            params=query,
            headers=headers,
            json=body,
        )
    duration_ms = int((time.perf_counter() - started) * 1000)

    try:
        response_body: Any = r.json()
    except Exception:
        response_body = r.text

    if scope_topology_id and mcp_req.path == "/api/emulation/active" and isinstance(response_body, dict):
        emulations = response_body.get("emulations")
        if isinstance(emulations, list):
            response_body = {
                **response_body,
                "emulations": [e for e in emulations if e.get("topology_id") == scope_topology_id],
            }
    if scope_topology_id and mcp_req.path.startswith("/api/snapshots") and isinstance(response_body, dict):
        items = response_body.get("items")
        if isinstance(items, list):
            filtered = [s for s in items if s.get("topology_id") == scope_topology_id]
            response_body = {**response_body, "items": filtered, "total": len(filtered)}

    return ExecuteMCPRequestResponse(
        status_code=r.status_code,
        headers=dict(r.headers),
        body=response_body,
        meta={
            "duration_ms": duration_ms,
            "method": mcp_req.method,
            "path": mcp_req.path,
        },
    )


@app.post("/api/ai/mcp/agent", response_model=MCPAgentResponse)
async def mcp_agent(req: MCPAgentRequest, db: Session = Depends(get_db)):
    """
    MCP-first chat agent:
    The model decides whether to call MCP tools (TOON) and can chain multiple calls.
    """
    if req.max_steps < 1 or req.max_steps > 8:
        raise HTTPException(status_code=400, detail="max_steps must be between 1 and 8")

    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")

    system = (
        "You are an MCP-first assistant for Caduceus-Flux.\n"
        "You can either call an MCP tool (by returning TOON) or reply to the user.\n"
        "\n"
        "You MUST respond with a single JSON object (no markdown) in one of these forms:\n"
        '{"action":"tool","toon":"<TOON request>","reason":"<short>"}\n'
        '{"action":"final","content":"<assistant reply>"}\n'
        "\n"
        "Common workflows (pick the minimal steps):\n"
        "- Start/run an emulation by topology name:\n"
        "  1) GET /api/topologies\n"
        "  2) POST /api/emulation/start with body topology_id=<matched topology id>\n"
        "  3) action=final confirming started emulation_id\n"
        "- Stop an emulation:\n"
        "  1) GET /api/emulation/active\n"
        "  2) POST /api/emulation/stop/{emulation_id}\n"
        "- API documentation for a microservice:\n"
        "  1) GET /api/openapi  (list services)\n"
        "  2) GET /api/openapi/{service_name}  (OpenAPI JSON)\n"
        "  3) action=final with key endpoints, or point to /api/docs/{service_name}\n"
        "\n"
        "Rules for action=tool:\n"
        "- toon must be valid TOON\n"
        "- PATH must start with /api/\n"
        "- Prefer using tools whenever the user asks to inspect or change system state\n"
        "- Do NOT call /api/services unless the user explicitly asks about services\n"
        "- Do NOT invent endpoints; discover them via OpenAPI when needed:\n"
        "  - GET /api/openapi (list specs)\n"
        "  - GET /api/openapi/{service_name} (read spec, then pick exact method/path)\n"
        "- Use GET /api/services (NOT /api/microservices)\n"
        "\n"
        + _capabilities_text(req.scope_topology_id)
    )

    llm_messages: List[ChatMessage] = [ChatMessage(role="system", content=system)]
    for m in req.messages:
        llm_messages.append(ChatMessage(role=m.role, content=m.content))

    tool_calls: List[MCPAgentToolCall] = []
    raw_steps: List[Dict[str, Any]] = []

    for step in range(req.max_steps):
        chat_req = ChatRequest(
            provider=req.provider,
            model=req.model,
            api_key=_resolve_api_key(db, req.provider, req.api_key),
            messages=llm_messages,
            temperature=0.0,
            max_tokens=700,
        )
        resp = await _chat_dispatch(chat_req)
        raw_steps.append(resp.raw)

        action_obj = _coerce_agent_action_from_text(resp.content)
        if action_obj is None:
            if tool_calls:
                return MCPAgentResponse(
                    assistant=_pick_best_summary(tool_calls, last_user),
                    tool_calls=tool_calls,
                    raw_steps=raw_steps,
                )
            # Repair once, then fallback to TOON generation if still invalid.
            try:
                action_obj = await _repair_agent_output(
                    provider=req.provider,
                    model=req.model,
                    db=db,
                    api_key=req.api_key,
                    scope_topology_id=req.scope_topology_id,
                    bad_output=resp.content or "",
                    error_hint="Output was not valid agent JSON and not valid TOON",
                )
            except Exception:
                mcp_req = await _generate_mcp_from_prompt(
                    provider=req.provider,
                    model=req.model,
                    prompt=last_user or "Show system status",
                    db=db,
                    scope_topology_id=req.scope_topology_id,
                    api_key=req.api_key,
                )
                exec_res = await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)
                toon = request_to_toon(mcp_req).strip()
                tool_calls.append(MCPAgentToolCall(toon=toon, result=exec_res))
                summary = _summarize_tool_call(toon, exec_res)
                return MCPAgentResponse(assistant=summary, tool_calls=tool_calls, raw_steps=raw_steps)

        action = str(action_obj.get("action") or "").lower().strip()
        if action == "final":
            content = str(action_obj.get("content") or "").strip()
            return MCPAgentResponse(assistant=content, tool_calls=tool_calls, raw_steps=raw_steps)

        if action != "tool":
            # Repair once, else fallback to TOON generation.
            try:
                action_obj = await _repair_agent_output(
                    provider=req.provider,
                    model=req.model,
                    db=db,
                    api_key=req.api_key,
                    scope_topology_id=req.scope_topology_id,
                    bad_output=json.dumps(action_obj),
                    error_hint="Invalid action; must be 'tool' or 'final'",
                )
                action = str(action_obj.get("action") or "").lower().strip()
                if action == "final":
                    content = str(action_obj.get("content") or "").strip()
                    return MCPAgentResponse(assistant=content, tool_calls=tool_calls, raw_steps=raw_steps)
                if action != "tool":
                    raise ValueError("still not tool/final")
            except Exception:
                mcp_req = await _generate_mcp_from_prompt(
                    provider=req.provider,
                    model=req.model,
                    prompt=last_user or "Show system status",
                    db=db,
                    scope_topology_id=req.scope_topology_id,
                    api_key=req.api_key,
                )
                exec_res = await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)
                toon = request_to_toon(mcp_req).strip()
                tool_calls.append(MCPAgentToolCall(toon=toon, result=exec_res))
                summary = _summarize_tool_call(toon, exec_res)
                return MCPAgentResponse(assistant=summary, tool_calls=tool_calls, raw_steps=raw_steps)

        toon = str(action_obj.get("toon") or "").strip()
        toon = _strip_code_fences(toon)
        if not toon:
            if tool_calls:
                return MCPAgentResponse(
                    assistant=_pick_best_summary(tool_calls, last_user),
                    tool_calls=tool_calls,
                    raw_steps=raw_steps,
                )
            try:
                action_obj = await _repair_agent_output(
                    provider=req.provider,
                    model=req.model,
                    db=db,
                    api_key=req.api_key,
                    scope_topology_id=req.scope_topology_id,
                    bad_output=resp.content or "",
                    error_hint="action=tool but toon was empty",
                )
                toon = str(action_obj.get("toon") or "").strip()
                toon = _strip_code_fences(toon)
            except Exception:
                mcp_req = await _generate_mcp_from_prompt(
                    provider=req.provider,
                    model=req.model,
                    prompt=last_user or "Show system status",
                    db=db,
                    scope_topology_id=req.scope_topology_id,
                    api_key=req.api_key,
                )
                exec_res = await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)
                toon = request_to_toon(mcp_req).strip()
                tool_calls.append(MCPAgentToolCall(toon=toon, result=exec_res))
                summary = _summarize_tool_call(toon, exec_res)
                return MCPAgentResponse(assistant=summary, tool_calls=tool_calls, raw_steps=raw_steps)

        # Normalize method tokens like '/GET ...' (but do not break '/api/...').
        first_line = next((ln.strip() for ln in toon.splitlines() if ln.strip()), "")
        first_token = (first_line.split() or [""])[0]
        if first_token.startswith("/") and first_token[1:].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            toon = first_line.lstrip("/") + "\n" + "\n".join([ln for ln in toon.splitlines()[1:]])

        # Common model shortcut: returns only the path (infer method from capabilities)
        first_line = next((ln.strip() for ln in toon.splitlines() if ln.strip()), "")
        if (" " not in first_line) and (first_line.startswith("/api/") or first_line.startswith("api/")):
            path_only = first_line if first_line.startswith("/api/") else ("/" + first_line)
            method = _infer_method_for_path_only(path_only)
            toon = f"{method} {path_only}\n" + "\n".join([ln for ln in toon.splitlines()[1:]])

        try:
            mcp_req = toon_to_request(toon)
        except Exception as e:
            try:
                action_obj = await _repair_agent_output(
                    provider=req.provider,
                    model=req.model,
                    db=db,
                    api_key=req.api_key,
                    scope_topology_id=req.scope_topology_id,
                    bad_output=toon,
                    error_hint=f"Invalid TOON: {e}",
                )
                toon = str(action_obj.get("toon") or "").strip()
                toon = _strip_code_fences(toon)
                first_line = next((ln.strip() for ln in toon.splitlines() if ln.strip()), "")
                if first_line.startswith("/api/") and " " not in first_line:
                    toon = "GET " + first_line + "\n" + "\n".join([ln for ln in toon.splitlines()[1:]])
                mcp_req = toon_to_request(toon)
            except Exception:
                mcp_req = await _generate_mcp_from_prompt(
                    provider=req.provider,
                    model=req.model,
                    prompt=last_user or "Show system status",
                    db=db,
                    scope_topology_id=req.scope_topology_id,
                    api_key=req.api_key,
                )
                exec_res = await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)
                toon2 = request_to_toon(mcp_req).strip()
                tool_calls.append(MCPAgentToolCall(toon=toon2, result=exec_res))
                summary = _summarize_tool_call(toon2, exec_res)
                return MCPAgentResponse(assistant=summary, tool_calls=tool_calls, raw_steps=raw_steps)

        # Normalize/alias + show the effective request TOON
        mcp_req = _apply_known_path_aliases(mcp_req)
        if req.scope_topology_id:
            mcp_req = _apply_topology_scope(mcp_req, req.scope_topology_id)

        if mcp_req.path == "/api/services" and not _user_asked_for_services(last_user):
            llm_messages.append(
                ChatMessage(
                    role="system",
                    content="Tool call GET /api/services is only allowed when the user explicitly asks about services. Choose another tool or answer with action=final.",
                )
            )
            continue

        # If model forgot the topology_id for start, infer from the user's message by matching known topology names.
        if mcp_req.path == "/api/emulation/start" and not req.scope_topology_id:
            if not isinstance(mcp_req.body, dict):
                mcp_req.body = {}
            body_dict = dict(mcp_req.body)
            topo = body_dict.get("topology_id")
            if not topo or not str(topo).strip() or str(topo).strip().lower() in {"selected_topology_id", "null", "none"}:
                body_dict["topology_id"] = await _resolve_topology_id_by_hint(last_user or "")
                mcp_req.body = body_dict

        exec_res = await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)
        effective_toon = request_to_toon(mcp_req).strip()
        tool_calls.append(MCPAgentToolCall(toon=effective_toon, result=exec_res))

        # If user explicitly asked for containers as part of a "run/start" request,
        # complete it deterministically (model sometimes stops early after a successful start).
        if mcp_req.path == "/api/emulation/start" and _user_asked_for_containers(last_user):
            topo_id: Optional[str] = req.scope_topology_id
            if topo_id is None and isinstance(mcp_req.body, dict):
                topo_id = str(mcp_req.body.get("topology_id") or "").strip() or None
            containers_req = MCPRequest(
                method="GET",
                path="/api/emulation/containers",
                query={"topology_id": topo_id} if topo_id else None,
            )
            containers_res = await _execute_mcp_request_scoped(containers_req, req.scope_topology_id)
            containers_toon = request_to_toon(containers_req).strip()
            tool_calls.append(MCPAgentToolCall(toon=containers_toon, result=containers_res))
            assistant = _summarize_tool_call(effective_toon, exec_res) + "\n" + _summarize_tool_call(containers_toon, containers_res)
            return MCPAgentResponse(assistant=assistant, tool_calls=tool_calls, raw_steps=raw_steps)

        if _should_autofinalize_after(effective_toon, exec_res, last_user):
            return MCPAgentResponse(
                assistant=_summarize_tool_call(effective_toon, exec_res),
                tool_calls=tool_calls,
                raw_steps=raw_steps,
            )

        # Feed tool result back into the model for the next step
        result_text = _trim_text(
            json.dumps({"status_code": exec_res.status_code, "body": exec_res.body}, ensure_ascii=False),
            limit=8000,
        )
        llm_messages.append(ChatMessage(role="assistant", content=json.dumps({"action": "tool", "toon": effective_toon})))
        llm_messages.append(ChatMessage(role="system", content=f"Tool result:\n{result_text}"))
        llm_messages.append(
            ChatMessage(
                role="system",
                content="If the user goal is satisfied, respond with action=final. Otherwise call another tool.",
            )
        )

    # Fallback: no final after max_steps
    if tool_calls:
        fallback = f"Executed {len(tool_calls)} tool call(s). {_pick_best_summary(tool_calls, last_user)}"
    else:
        fallback = "I couldn't complete the request."
    return MCPAgentResponse(assistant=fallback, tool_calls=tool_calls, raw_steps=raw_steps)


@app.post("/api/ai/mcp/execute", response_model=ExecuteMCPRequestResponse)
async def execute_mcp_request(req: ExecuteMCPRequestRequest):
    mcp_req: Optional[MCPRequest] = req.request
    if req.toon:
        try:
            mcp_req = toon_to_request(req.toon)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid TOON: {e}")
    if mcp_req is None:
        raise HTTPException(status_code=400, detail="Provide either 'request' or 'toon'")
    return await _execute_mcp_request_scoped(mcp_req, req.scope_topology_id)


async def _mcp_get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    last_status: Optional[int] = None
    last_text: str = ""
    for base in (MCP_SERVER_URL, MCP_FALLBACK_GATEWAY_URL):
        url = f"{base}{path}"
        try:
            r = await http_client.get(url, params=params)
        except Exception as exc:
            last_text = str(exc)
            continue
        last_status = r.status_code
        last_text = r.text
        # Many endpoints are not implemented by the MCP server itself; fall back to the gateway.
        if base == MCP_SERVER_URL and r.status_code in (404, 502, 503):
            continue
        if r.status_code >= 400:
            break
        try:
            return r.json()
        except Exception:
            return r.text
    if last_status and 400 <= int(last_status) < 600:
        raise HTTPException(status_code=int(last_status), detail=f"Failed to fetch {path}: {last_text[:300]}")
    raise HTTPException(status_code=502, detail=f"Failed to fetch {path} (HTTP {last_status or '—'}): {last_text[:200]}")


async def _mcp_post_json(path: str, json_body: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Any:
    last_status: Optional[int] = None
    last_text: str = ""
    for base in (MCP_SERVER_URL, MCP_FALLBACK_GATEWAY_URL):
        url = f"{base}{path}"
        try:
            r = await http_client.post(url, params=params, json=json_body)
        except Exception as exc:
            last_text = str(exc)
            continue
        last_status = r.status_code
        last_text = r.text
        if base == MCP_SERVER_URL and r.status_code in (404, 502, 503):
            continue
        if r.status_code >= 400:
            break
        try:
            return r.json()
        except Exception:
            return r.text
    if last_status and 400 <= int(last_status) < 600:
        raise HTTPException(status_code=int(last_status), detail=f"Failed to fetch {path}: {last_text[:300]}")
    raise HTTPException(status_code=502, detail=f"Failed to fetch {path} (HTTP {last_status or '—'}): {last_text[:200]}")


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _device_display_name(d: Dict[str, Any]) -> str:
    props = d.get("properties") if isinstance(d.get("properties"), dict) else {}
    return (
        str(d.get("runtime_name") or "").strip()
        or str(props.get("node_id") or "").strip()
        or str(d.get("name") or "").strip()
    )


async def _pick_default_model(db: Session, provider: Provider) -> str:
    if provider == "ollama":
        try:
            r = await http_client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code == 200:
                payload = r.json()
                models = [m.get("name") for m in (payload.get("models") or []) if m.get("name")]
                if models:
                    return str(models[0])
        except Exception:
            pass
        return "llama3.1:8b"

    row = db.get(AIProviderConfig, provider)
    if row and row.default_model:
        return row.default_model
    defaults = DEFAULT_MODELS.get(provider) or []
    if defaults:
        return str(defaults[0])
    raise HTTPException(status_code=400, detail=f"No default model for provider: {provider}")


def _pick_default_provider(db: Session) -> Provider:
    # Prefer configured cloud providers if present, otherwise fall back to Ollama.
    for p in ("openai", "anthropic", "gemini"):
        row = db.get(AIProviderConfig, p)
        if row and row.api_key_encrypted:
            return p  # type: ignore[return-value]
    return "ollama"  # type: ignore[return-value]


@app.post("/api/ai/network/diagnose", response_model=NetworkDiagnoseResponse)
async def diagnose_network(req: NetworkDiagnoseRequest, db: Session = Depends(get_db)):
    topology_id = (req.topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    provider: Provider = (req.provider or "ollama")  # type: ignore[assignment]
    model = (req.model or "").strip() or await _pick_default_model(db, provider)

    api_key = _resolve_api_key(db, provider, req.api_key)
    if provider in ("openai", "anthropic", "gemini") and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} is not configured. Set API key in AI Settings.")

    # Gather context from the running system.
    fetch_errors: Dict[str, str] = {}
    try:
        topology = await _mcp_get_json(f"/api/topologies/{topology_id}")
    except Exception as exc:
        topology = {}
        fetch_errors["topology"] = str(getattr(exc, "detail", str(exc)))
    try:
        active = await _mcp_get_json("/api/emulation/active")
    except Exception as exc:
        active = {}
        fetch_errors["active"] = str(getattr(exc, "detail", str(exc)))
    emulations = active.get("emulations") if isinstance(active, dict) else []
    emu = next((e for e in (emulations or []) if isinstance(e, dict) and e.get("topology_id") == topology_id), None)
    emulation_id = emu.get("emulation_id") if isinstance(emu, dict) else None
    emulation_status = emu.get("status") if isinstance(emu, dict) else None

    shell: Optional[Dict[str, Any]] = None
    if emulation_id:
        try:
            shell_raw = await _mcp_get_json(f"/api/emulation/shell/{emulation_id}")
            shell = shell_raw if isinstance(shell_raw, dict) else None
        except Exception:
            shell = None

    topology_metrics: Any = None
    try:
        topology_metrics = await _mcp_get_json(f"/api/monitoring/topology/{topology_id}/metrics")
    except Exception:
        topology_metrics = None

    device_entries = (shell or {}).get("devices") if isinstance(shell, dict) else []
    device_entries = device_entries if isinstance(device_entries, list) else []
    device_names = [_device_display_name(d) for d in device_entries if isinstance(d, dict)]
    device_names = [d for d in device_names if d][:30]

    device_metrics: Dict[str, Any] = {}
    device_errors: Dict[str, str] = {}
    for name in device_names:
        try:
            device_metrics[name] = await _mcp_get_json(
                f"/api/monitoring/devices/{name}",
                params={"topology_id": topology_id},
            )
        except Exception as e:
            device_errors[name] = str(getattr(e, "detail", str(e)))

    # Heuristics (fast, deterministic)
    rows = []
    hot = []
    down = list(device_errors.keys())
    talkers = []
    for name, met in device_metrics.items():
        if not isinstance(met, dict):
            continue
        cpu = (met.get("cpu") or {}).get("total_cpu_percent") if isinstance(met.get("cpu"), dict) else None
        mem = met.get("memory") if isinstance(met.get("memory"), dict) else {}
        mem_used = float(mem.get("used_mb") or 0)
        mem_total = float(mem.get("total_mb") or 0)
        mem_pct = _safe_ratio(mem_used, mem_total) * 100.0
        stats = met.get("stats") if isinstance(met.get("stats"), dict) else {}
        rx = float(stats.get("rx_bytes") or 0)
        tx = float(stats.get("tx_bytes") or 0)
        errors = 0
        if isinstance(met.get("interfaces"), dict):
            for v in met["interfaces"].values():
                if isinstance(v, dict):
                    errors += int(v.get("rx_errors") or 0) + int(v.get("tx_errors") or 0)

        row = {
            "device": name,
            "cpu_percent": float(cpu or 0),
            "memory_percent": float(mem_pct),
            "rx_bytes": rx,
            "tx_bytes": tx,
            "errors": errors,
        }
        rows.append(row)
        if row["cpu_percent"] >= 85 or row["memory_percent"] >= 85 or errors > 0:
            hot.append(row)
        talkers.append({"device": name, "bytes": rx + tx})

    talkers.sort(key=lambda x: x["bytes"], reverse=True)
    hot.sort(key=lambda x: (-(x["cpu_percent"]), -(x["memory_percent"]), -x["errors"]))

    heuristics = {
        "topology_id": topology_id,
        "fetch_errors": fetch_errors,
        "topology": topology if isinstance(topology, dict) else {},
        "emulation": {
            "emulation_id": emulation_id,
            "status": emulation_status,
        },
        "devices": {
            "total": len(device_names),
            "with_metrics": len(device_metrics),
            "down": down,
            "hot": hot[:10],
            "top_talkers": talkers[:10],
        },
        "topology_metrics": topology_metrics,
    }

    # Ask the model for a human-friendly diagnosis.
    system = (
        "You are a network operations assistant for a network emulation platform.\n"
        "Given telemetry + topology context, produce a concise diagnosis for the user.\n"
        "Do NOT invent metrics that aren't provided.\n"
        "Output format:\n"
        "Status: <one line>\n"
        "Issues:\n- ...\n"
        "Bottlenecks:\n- ...\n"
        "Recommendations:\n- ...\n"
    )
    user = "Context JSON:\n" + _trim_text(json.dumps(heuristics, ensure_ascii=False), 12000)
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=api_key,
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.2,
        max_tokens=700,
    )
    resp = await _chat_dispatch(chat_req)
    return NetworkDiagnoseResponse(
        topology_id=topology_id,
        provider=provider,
        model=model,
        content=(resp.content or "").strip(),
        heuristics=heuristics,
    )


@app.post("/api/ai/network/tests/analyze", response_model=NetworkTestAnalyzeResponse)
async def analyze_network_tests(req: NetworkTestAnalyzeRequest, db: Session = Depends(get_db)):
    topology_id = (req.topology_id or "").strip()
    run_id = (req.run_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    provider: Provider = (req.provider or _pick_default_provider(db))  # type: ignore[assignment]
    model = (req.model or "").strip() or await _pick_default_model(db, provider)
    api_key = _resolve_api_key(db, provider, req.api_key)
    if provider in ("openai", "anthropic", "gemini") and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} is not configured. Set API key in AI Settings.")

    fetch_errors: Dict[str, str] = {}
    try:
        test_status = await _mcp_get_json(f"/api/tests/{run_id}")
    except Exception as exc:
        test_status = {}
        fetch_errors["status"] = str(getattr(exc, "detail", str(exc)))
    try:
        test_results = await _mcp_get_json(
            f"/api/tests/{run_id}/results",
            params={"topology_id": topology_id, "window_minutes": 240},
        )
    except Exception as exc:
        test_results = {}
        fetch_errors["results"] = str(getattr(exc, "detail", str(exc)))

    highlights: Dict[str, Any] = {"run_id": run_id}
    if fetch_errors:
        highlights["fetch_errors"] = fetch_errors
    try:
        iperf = test_results.get("iperf") if isinstance(test_results, dict) else None
        ping = test_results.get("ping") if isinstance(test_results, dict) else None
        metrics = ((test_results or {}).get("metrics") if isinstance(test_results, dict) else None) or {}
        summary = metrics.get("summary_by_device") if isinstance(metrics, dict) else {}

        if isinstance(ping, list) and ping:
            losses = [float(p.get("loss_pct") or 0.0) for p in ping if isinstance(p, dict)]
            rtts = [float(p.get("rtt_avg_ms") or 0.0) for p in ping if isinstance(p, dict)]
            highlights["ping"] = {
                "count": len(ping),
                "loss_max_pct": max(losses) if losses else 0.0,
                "rtt_max_ms": max(rtts) if rtts else 0.0,
            }
        if isinstance(iperf, list) and iperf:
            tcp = [float(x.get("throughput_mbps") or 0.0) for x in iperf if isinstance(x, dict) and x.get("proto") == "tcp"]
            udp = [float(x.get("throughput_mbps") or 0.0) for x in iperf if isinstance(x, dict) and x.get("proto") == "udp"]
            highlights["iperf"] = {
                "tcp_max_mbps": max(tcp) if tcp else 0.0,
                "udp_max_mbps": max(udp) if udp else 0.0,
            }
        if isinstance(summary, dict) and summary:
            cpu_top = max(((k, float(v.get("cpu_max") or 0.0)) for k, v in summary.items() if isinstance(v, dict)), key=lambda x: x[1], default=("", 0.0))
            mem_top = max(((k, float(v.get("mem_max") or 0.0)) for k, v in summary.items() if isinstance(v, dict)), key=lambda x: x[1], default=("", 0.0))
            highlights["load"] = {
                "cpu_top_device": cpu_top[0],
                "cpu_max_pct": cpu_top[1],
                "mem_top_device": mem_top[0],
                "mem_max_pct": mem_top[1],
                "devices": len(summary),
            }
    except Exception:
        pass

    system = (
        "You are a network emulation test analyst.\n"
        "Analyze the test results and explain what they mean in plain language.\n"
        "Output format:\n"
        "1) Summary (2-4 bullets)\n"
        "2) Findings (issues, anomalies, bottlenecks)\n"
        "3) Likely causes\n"
        "4) Recommendations (concrete actions + which tests to rerun)\n"
        "Be precise; reference metrics (loss, RTT, throughput, CPU/mem) and name the devices involved.\n"
    )
    user = (
        "Topology ID: "
        + topology_id
        + "\n"
        + "Test Run Status (JSON):\n"
        + _trim_text(json.dumps(test_status, ensure_ascii=False), 8000)
        + "\n\n"
        + "Test Results (JSON):\n"
        + _trim_text(json.dumps(test_results, ensure_ascii=False), 12000)
    )
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=api_key,
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.2,
        max_tokens=900,
    )
    resp = await _chat_dispatch(chat_req)
    return NetworkTestAnalyzeResponse(
        topology_id=topology_id,
        run_id=run_id,
        provider=provider,
        model=model,
        content=(resp.content or "").strip(),
        highlights=highlights,
    )


@app.post("/api/ai/network/diagnostics/analyze", response_model=NetworkDiagnosticsAnalyzeResponse)
async def analyze_network_diagnostics(req: NetworkDiagnosticsAnalyzeRequest, db: Session = Depends(get_db)):
    topology_id = (req.topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    provider: Provider = (req.provider or _pick_default_provider(db))  # type: ignore[assignment]
    model = (req.model or "").strip() or await _pick_default_model(db, provider)
    api_key = _resolve_api_key(db, provider, req.api_key)
    if provider in ("openai", "anthropic", "gemini") and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} is not configured. Set API key in AI Settings.")

    query_payload: Dict[str, Any] = {
        "window_minutes": req.window_minutes,
        "start_ms": req.start_ms,
        "end_ms": req.end_ms,
        "every_seconds": req.every_seconds,
        "device": req.device,
        "source": req.source,
        "emulation_id": req.emulation_id,
        "fields": req.fields,
    }
    query_payload = {k: v for k, v in query_payload.items() if v is not None}

    fetch_errors: Dict[str, str] = {}
    try:
        series = await _mcp_post_json(f"/api/diagnostics/{topology_id}/influx/query", query_payload)
    except Exception as exc:
        series = {}
        fetch_errors["series"] = str(getattr(exc, "detail", str(exc)))
    points = series.get("points") if isinstance(series, dict) else None
    points = points if isinstance(points, list) else []
    fields = series.get("fields") if isinstance(series, dict) and isinstance(series.get("fields"), list) else list(req.fields or [])

    def _num(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    # Summarize the selected series so the LLM can reason without huge payloads.
    stats: Dict[str, Dict[str, Any]] = {}
    for f in fields:
        vals = [_num(p.get(f)) for p in points if isinstance(p, dict)]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        stats[f] = {
            "min": float(min(vals)),
            "max": float(max(vals)),
            "avg": float(sum(vals) / max(1, len(vals))),
            "last": float(vals[-1]),
            "count": len(vals),
        }

    # Downsample raw points for context (keep endpoints).
    sample: List[Dict[str, Any]] = []
    try:
        if points:
            n = len(points)
            stride = max(1, n // 80)
            sample = [p for i, p in enumerate(points) if i % stride == 0]
            if sample and sample[-1] is not points[-1]:
                sample.append(points[-1])
    except Exception:
        sample = []

    summary = {
        "topology_id": topology_id,
        "query": {k: series.get(k) for k in ("bucket", "measurement", "every_seconds", "start_ms", "end_ms", "device", "source", "emulation_id", "fields") if isinstance(series, dict)},
        "stats": stats,
        "sample_points": sample[:120],
    }
    if fetch_errors:
        summary["fetch_errors"] = fetch_errors

    system = (
        "You are a network diagnostics assistant for a network emulation platform.\n"
        "You will receive timeseries metrics from InfluxDB and must explain what they mean.\n"
        "Do NOT invent numbers.\n"
        "Output in Markdown with this structure:\n"
        "## Status\n"
        "## What stands out\n"
        "## Possible causes\n"
        "## Recommendations\n"
        "Keep it concise and actionable.\n"
    )
    user_prompt = (req.prompt or "").strip() or "Analyze the selected telemetry window and explain anomalies, bottlenecks, and risks."
    user = (
        f"User request: {user_prompt}\n\n"
        "Diagnostics context (JSON):\n"
        + _trim_text(json.dumps(summary, ensure_ascii=False), 12000)
    )
    chat_req = ChatRequest(
        provider=provider,
        model=model,
        api_key=api_key,
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.2,
        max_tokens=900,
    )
    resp = await _chat_dispatch(chat_req)
    return NetworkDiagnosticsAnalyzeResponse(
        topology_id=topology_id,
        provider=provider,
        model=model,
        content=(resp.content or "").strip(),
        summary=summary,
    )


OLLAMA_EMBED_MODEL = _env("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_EMBED_ENDPOINT: Optional[str] = "/api/embeddings"
AI_MEMORY_MAX_CANDIDATES = int(os.getenv("AI_MEMORY_MAX_CANDIDATES", "250"))
AI_MEMORY_MAX_HITS = int(os.getenv("AI_MEMORY_MAX_HITS", "6"))
AI_EMBED_DIM = int(os.getenv("AI_EMBED_DIM", "768"))


def _fix_embedding_dim(vec: Optional[List[float]]) -> Optional[List[float]]:
    if not vec:
        return None
    if AI_EMBED_DIM <= 0:
        return vec
    if len(vec) == AI_EMBED_DIM:
        return vec
    if len(vec) > AI_EMBED_DIM:
        return vec[:AI_EMBED_DIM]
    return vec + [0.0] * (AI_EMBED_DIM - len(vec))


def _encode_agent_policy_header(agent: AIAgent) -> str:
    payload = {
        "agent_id": agent.id,
        "allowed_methods": _agent_allowed_methods(agent),
        "allowed_prefixes": _agent_allowed_prefixes(agent),
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _extract_usage_from_raw_steps(raw_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize token/usage counters across providers where possible.
    """
    usage: Dict[str, Any] = {}
    if not raw_steps:
        return usage
    # Ollama-style responses carry prompt_eval_count / eval_count.
    last = raw_steps[-1] if isinstance(raw_steps[-1], dict) else {}
    if isinstance(last, dict):
        p = last.get("prompt_eval_count")
        c = last.get("eval_count")
        if isinstance(p, int):
            usage["prompt_tokens"] = p
        if isinstance(c, int):
            usage["completion_tokens"] = c
        if isinstance(p, int) and isinstance(c, int):
            usage["total_tokens"] = p + c
    return usage


def _pinned_context_text(row: Optional[AIPinnedContext]) -> str:
    if not row:
        return ""
    lines = ["Pinned topology context:"]
    lines.append(f"- topology_id: {row.topology_id}")
    if row.emulation_id:
        lines.append(f"- emulation_id: {row.emulation_id}")
    if row.container_name or row.container_id:
        lines.append(f"- container: {row.container_name or ''} {row.container_id or ''}".strip())
    if row.updated_at:
        lines.append(f"- updated_at: {row.updated_at.isoformat()}")
    if row.content_md:
        lines.append("")
        lines.append(_trim_text(row.content_md, 2000))
    return "\n".join(lines).strip()


PINNED_CONTEXT_TTL_SECONDS = int(os.getenv("AI_PINNED_CONTEXT_TTL_SECONDS", "30"))


async def _refresh_pinned_context(db: Session, topology_id: str, request_id: Optional[str] = None) -> Optional[AIPinnedContext]:
    """
    Keep a small, always-present per-topology context record so agents stop guessing.
    """
    if not topology_id:
        return None
    row = db.get(AIPinnedContext, topology_id)
    if row and row.updated_at and (datetime.utcnow() - row.updated_at).total_seconds() < PINNED_CONTEXT_TTL_SECONDS:
        return row

    emulation_id: Optional[str] = None
    status: Optional[str] = None
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    context: Dict[str, Any] = {"topology_id": topology_id}

    try:
        active_req = MCPRequest(method="GET", path="/api/emulation/active")
        active_res = await _execute_mcp_request_scoped(active_req, topology_id, request_id=request_id)
        body = active_res.body if isinstance(active_res.body, dict) else {}
        emulations = body.get("emulations") if isinstance(body, dict) else []
        if isinstance(emulations, list):
            match = next((e for e in emulations if isinstance(e, dict) and e.get("topology_id") == topology_id and str(e.get("status") or "").lower() == "running"), None)
            if not match:
                match = next((e for e in emulations if isinstance(e, dict) and e.get("topology_id") == topology_id), None)
            if isinstance(match, dict):
                emulation_id = str(match.get("emulation_id") or "") or None
                status = str(match.get("status") or "") or None
                container_id = str(match.get("container_id") or "") or None
                container_name = str(match.get("container_name") or "") or None
        context["active_emulation"] = match if "match" in locals() else None
    except Exception as e:
        context["active_emulation_error"] = str(e)

    try:
        containers_req = MCPRequest(method="GET", path="/api/emulation/containers", query={"topology_id": topology_id})
        containers_res = await _execute_mcp_request_scoped(containers_req, topology_id, request_id=request_id)
        context["containers"] = containers_res.body
    except Exception as e:
        context["containers_error"] = str(e)

    try:
        infra_req = MCPRequest(method="GET", path=f"/api/infrastructure/topologies/{topology_id}/infra/status")
        infra_res = await _execute_mcp_request_scoped(infra_req, topology_id, request_id=request_id)
        context["infra_status"] = infra_res.body
    except Exception as e:
        context["infra_status_error"] = str(e)

    summary_lines = [f"topology_id={topology_id}"]
    if emulation_id:
        summary_lines.append(f"emulation_id={emulation_id} status={status or 'unknown'}")
    if container_name or container_id:
        summary_lines.append(f"container={container_name or ''} {container_id or ''}".strip())
    try:
        infra = context.get("infra_status")
        if isinstance(infra, dict):
            state = str(infra.get("status") or infra.get("state") or "").strip()
            if state:
                summary_lines.append(f"infra_status={state}")
    except Exception:
        pass
    content_md = "\n".join(summary_lines)

    if not row:
        row = AIPinnedContext(topology_id=topology_id)
        db.add(row)
    row.emulation_id = emulation_id
    row.container_id = container_id
    row.container_name = container_name
    row.content_md = content_md
    row.content_json = json.dumps(context, ensure_ascii=False)
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return row


def _safe_json_loads(text: Optional[str], default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _agent_allowed_prefixes(agent: AIAgent) -> List[str]:
    prefixes = _safe_json_loads(agent.allowed_prefixes_json, [])
    if isinstance(prefixes, list):
        return [str(p) for p in prefixes if str(p)]
    return []


def _agent_allowed_methods(agent: AIAgent) -> List[str]:
    methods = _safe_json_loads(agent.allowed_methods_json, ["GET"])
    if isinstance(methods, list):
        out: List[str] = []
        for m in methods:
            mm = re.sub(r"[^A-Z]", "", str(m).upper())
            if mm:
                out.append(mm)
        return out or ["GET"]
    return ["GET"]


def _agent_allows(agent: AIAgent, req: MCPRequest) -> Optional[str]:
    method = re.sub(r"[^A-Z]", "", str(req.method).upper())
    path = str(req.path or "").strip()
    if not path.startswith("/api/"):
        return "PATH must start with /api/"
    if method not in set(_agent_allowed_methods(agent)):
        return f"Method {method} is not allowed for this agent"
    prefixes = _agent_allowed_prefixes(agent)
    if prefixes and not any(path.startswith(p) for p in prefixes):
        return f"Path {path} is not allowed for this agent"
    return None


class ToolDeniedError(Exception):
    def __init__(self, mcp_req: MCPRequest, reason: str):
        super().__init__(reason)
        self.mcp_req = mcp_req
        self.reason = reason


def _is_dangerous_mcp(req: MCPRequest) -> bool:
    method = re.sub(r"[^A-Z]", "", str(req.method).upper())
    path = str(req.path or "").strip()
    if method == "DELETE":
        return True
    # Infrastructure destructive ops
    if method != "GET" and path.startswith("/api/infrastructure") and any(tok in path for tok in ("/purge", "/stop", "/restart")):
        return True
    # Emulation stop/cleanup can destroy runtime state
    if method != "GET" and (path.startswith("/api/emulation/stop/") or path.startswith("/api/emulation/purge")):
        return True
    if path.startswith("/api/projects") and method in ("DELETE", "POST"):
        # project creation is OK, but be conservative with non-GET here
        return path.endswith("/delete") or method == "DELETE"
    return False


def _pick_agent_for_mcp_request(db: Session, mcp_req: MCPRequest, topology_id: Optional[str]) -> Optional[AIAgent]:
    method = re.sub(r"[^A-Z]", "", str(mcp_req.method).upper())
    path = str(mcp_req.path or "").strip()
    best: Optional[AIAgent] = None
    best_len = -1
    for a in _routing_candidates(db, topology_id):
        if method not in set(_agent_allowed_methods(a)):
            continue
        prefixes = _agent_allowed_prefixes(a)
        if prefixes:
            matches = [p for p in prefixes if path.startswith(p)]
            if not matches:
                continue
            longest = max(len(p) for p in matches)
        else:
            longest = 0
        if longest > best_len:
            best = a
            best_len = longest
    return best


async def _maybe_embed_text(text: str) -> Optional[List[float]]:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    global OLLAMA_EMBED_ENDPOINT
    if OLLAMA_EMBED_ENDPOINT is None:
        return None
    try:
        if OLLAMA_EMBED_ENDPOINT == "/api/embeddings":
            r = await http_client.post(
                f"{OLLAMA_BASE_URL}{OLLAMA_EMBED_ENDPOINT}",
                json={"model": OLLAMA_EMBED_MODEL, "prompt": cleaned[:8000]},
            )
            if r.status_code == 404:
                OLLAMA_EMBED_ENDPOINT = "/api/embed"
                return await _maybe_embed_text(cleaned)
            if r.status_code >= 400:
                return None
            payload = r.json()
            vec = payload.get("embedding")
            if isinstance(vec, list):
                return _fix_embedding_dim([float(x) for x in vec if isinstance(x, (int, float))])
            return None

        r2 = await http_client.post(
            f"{OLLAMA_BASE_URL}{OLLAMA_EMBED_ENDPOINT}",
            json={"model": OLLAMA_EMBED_MODEL, "input": cleaned[:8000]},
        )
        if r2.status_code == 404:
            OLLAMA_EMBED_ENDPOINT = None
            return None
        if r2.status_code >= 400:
            return None
        payload = r2.json()
        emb = payload.get("embeddings")
        if isinstance(emb, list) and emb and isinstance(emb[0], list):
            vec = emb[0]
            return _fix_embedding_dim([float(x) for x in vec if isinstance(x, (int, float))])
        return None
    except Exception:
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n <= 8:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        na += av * av
        nb += bv * bv
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _trim_for_memory(text: str, max_len: int = 420) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _thread_to_info(thread: AIThread) -> ThreadInfo:
    return ThreadInfo(
        id=thread.id,
        agent_id=thread.agent_id,
        topology_id=thread.topology_id,
        title=thread.title,
        updated_at=thread.updated_at.isoformat() if thread.updated_at else None,
        created_at=thread.created_at.isoformat() if thread.created_at else None,
    )


def _route_fallback(topology_id: Optional[str]) -> str:
    return "diagnostics" if topology_id else "admin"


def _routing_candidates(db: Session, topology_id: Optional[str]) -> List[AIAgent]:
    agents = db.query(AIAgent).order_by(AIAgent.id.asc()).all()
    out = []
    for a in agents:
        if a.id == "router":
            continue
        scope = (a.scope or "both").lower()
        if topology_id:
            if scope in ("both", "topology"):
                out.append(a)
        else:
            if scope in ("both", "global"):
                out.append(a)
    return out


def _route_agent_rules(message: str, topology_id: Optional[str]) -> Optional[AgentRouteInfo]:
    t = (message or "").lower()
    # Keep this minimal and only for very obvious cases.
    def has_any(words: List[str]) -> bool:
        return any(w in t for w in words)

    if has_any(["snapshot", "restore", "criu", "schedule"]):
        agent_id = "snapshots"
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name="Snapshot & Restore Agent",
            reason="rule: snapshot/restore",
            confidence=1.0,
        )
    if has_any(["influx", "metrics", "monitoring", "diagnostic", "bottleneck", "telemetry"]):
        agent_id = "diagnostics" if topology_id else "admin"
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name="Monitoring & Diagnostics Agent" if agent_id == "diagnostics" else "Admin Agent",
            reason="rule: monitoring/metrics",
            confidence=1.0,
        )
    if has_any(["nginx", "gateway", "routing", "reverse proxy", "502", "503", "bad gateway"]):
        agent_id = "infra_ops"
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name="InfraOps Agent",
            reason="rule: infra/nginx",
            confidence=1.0,
        )
    if has_any(["emulation", "mininet", "controller", "onos", "ryu", "osken", "openflow", "start", "stop"]):
        agent_id = "emulation_ops" if topology_id else "admin"
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name="EmulationOps Agent" if agent_id == "emulation_ops" else "Admin Agent",
            reason="rule: emulation/control",
            confidence=0.9,
        )
    if has_any(["network config", "ip", "ipv4", "ipv6", "mac", "gateway", "interface", "routes", "dns"]):
        agent_id = "network_config" if topology_id else "admin"
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name="NetworkConfig Agent" if agent_id == "network_config" else "Admin Agent",
            reason="rule: network config",
            confidence=0.9,
        )
    return None


async def _route_agent_decision_via_llm(
    db: Session,
    message: str,
    topology_id: Optional[str],
    provider: Provider,
    model: str,
) -> AgentRouteInfo:
    rule = _route_agent_rules(message, topology_id)
    if rule and db.get(AIAgent, rule.selected_agent_id):
        # Fill the name from DB to avoid drift.
        a = db.get(AIAgent, rule.selected_agent_id)
        if a:
            rule.selected_agent_name = a.name
        return rule
    candidates = _routing_candidates(db, topology_id)
    if not candidates:
        agent_id = _route_fallback(topology_id)
        agent = db.get(AIAgent, agent_id)
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name=(agent.name if agent else agent_id),
            reason="fallback",
            confidence=0.0,
        )

    catalog = [
        {"id": a.id, "name": a.name, "scope": a.scope, "description": a.description or ""} for a in candidates
    ]
    system = (
        "You are a router for a multi-agent system.\n"
        "Pick the single best agent_id for the user's message.\n"
        "Return ONLY JSON (no markdown): {\"agent_id\":\"...\",\"confidence\":0.0-1.0,\"reason\":\"...\"}\n"
        "Rules:\n"
        "- Choose ONLY from the provided agents list.\n"
        "- If topology_id is null, avoid topology-scoped agents.\n"
        "- Prefer more specific agents when clearly applicable.\n"
    )
    user = json.dumps({"topology_id": topology_id, "message": (message or "").strip(), "agents": catalog}, ensure_ascii=False)
    api_key = _resolve_api_key(db, provider, None)
    if provider in ("openai", "anthropic", "gemini") and not api_key:
        agent_id = _route_fallback(topology_id)
        agent = db.get(AIAgent, agent_id)
        return AgentRouteInfo(
            mode="router",
            selected_agent_id=agent_id,
            selected_agent_name=(agent.name if agent else agent_id),
            reason="fallback (no provider key)",
            confidence=0.0,
        )

    resp = await _chat_dispatch(
        ChatRequest(
            provider=provider,
            model=model,
            api_key=api_key,
            messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
            temperature=0.0,
            max_tokens=220,
        )
    )
    obj = _safe_json_loads(resp.content or "", {})
    agent_id = str(obj.get("agent_id") or "").strip()
    reason = str(obj.get("reason") or "").strip() or None
    try:
        confidence = float(obj.get("confidence")) if obj.get("confidence") is not None else None
    except Exception:
        confidence = None
    if not agent_id or not db.get(AIAgent, agent_id):
        agent_id = _route_fallback(topology_id)
        reason = reason or "fallback"
        confidence = confidence if confidence is not None else 0.0
    agent = db.get(AIAgent, agent_id)
    return AgentRouteInfo(
        mode="router",
        selected_agent_id=agent_id,
        selected_agent_name=(agent.name if agent else agent_id),
        reason=reason,
        confidence=confidence,
    )


async def _route_agent_id_via_llm(
    db: Session,
    message: str,
    topology_id: Optional[str],
    provider: Provider,
    model: str,
) -> str:
    decision = await _route_agent_decision_via_llm(db, message, topology_id, provider, model)
    return decision.selected_agent_id


async def _memory_hits_for_topology(
    db: Session,
    topology_id: str,
    query_embedding: Optional[List[float]],
    query_text: str,
) -> List[Dict[str, Any]]:
    if not topology_id:
        return []

    thread_ids = [t.id for t in db.query(AIThread).filter(AIThread.topology_id == topology_id).all()]
    if not thread_ids:
        return []

    candidates: List[Dict[str, Any]] = []

    qt = (query_text or "").strip()
    q_tokens = set(re.findall(r"[a-zA-Z0-9_]+", qt.lower())) if qt else set()

    def lexical_score(text: str) -> float:
        if not q_tokens:
            return 0.0
        t_tokens = set(re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()))
        return (len(q_tokens & t_tokens) / max(1, len(q_tokens))) if q_tokens else 0.0

    def normalize_vec(value: Any) -> Optional[List[float]]:
        if not isinstance(value, list):
            return None
        try:
            vec = [float(x) for x in value if isinstance(x, (int, float))]
        except Exception:
            return None
        return vec if vec else None

    # Messages: use pgvector if we have a query embedding; otherwise lexical over recent messages.
    msgs: List[AIMessage] = []
    if query_embedding:
        try:
            # cosine_distance: smaller is better; convert to similarity-ish score.
            rows = (
                db.query(AIMessage, AIMessage.embedding_vec.cosine_distance(query_embedding).label("dist"))
                .filter(AIMessage.thread_id.in_(thread_ids))
                .filter(AIMessage.role != "system")
                .filter(AIMessage.embedding_vec.isnot(None))
                .order_by("dist")
                .limit(min(AI_MEMORY_MAX_CANDIDATES, AI_MEMORY_MAX_HITS * 25))
                .all()
            )
            for m, dist in rows:
                sim = 1.0 - float(dist) if dist is not None else 0.0
                if sim <= 0.05:
                    continue
                candidates.append(
                    {
                        "type": "message",
                        "id": m.id,
                        "role": m.role,
                        "created_at": m.created_at.isoformat(),
                        "score": round(float(sim), 4),
                        "excerpt": _trim_for_memory(m.content_md, 520),
                    }
                )
        except Exception:
            # Fall back to Python similarity below.
            msgs = (
                db.query(AIMessage)
                .filter(AIMessage.thread_id.in_(thread_ids))
                .filter(AIMessage.role != "system")
                .order_by(AIMessage.created_at.desc())
                .limit(AI_MEMORY_MAX_CANDIDATES)
                .all()
            )
    else:
        msgs = (
            db.query(AIMessage)
            .filter(AIMessage.thread_id.in_(thread_ids))
            .filter(AIMessage.role != "system")
            .order_by(AIMessage.created_at.desc())
            .limit(AI_MEMORY_MAX_CANDIDATES)
            .all()
        )

    if msgs:
        for m in msgs:
            score = 0.0
            if query_embedding:
                vec = normalize_vec(_safe_json_loads(m.embedding_json, None))
                if vec:
                    score = _cosine_similarity(query_embedding, vec)
            if score <= 0.0:
                score = lexical_score(m.content_md or "")
            if score <= 0.05:
                continue
            candidates.append(
                {
                    "type": "message",
                    "id": m.id,
                    "role": m.role,
                    "created_at": m.created_at.isoformat(),
                    "score": round(float(score), 4),
                    "excerpt": _trim_for_memory(m.content_md, 520),
                }
            )

    # Artifacts: pgvector first (if query_embedding), else lexical over recent artifacts.
    if query_embedding:
        try:
            rows2 = (
                db.query(AIArtifact, AIArtifact.embedding_vec.cosine_distance(query_embedding).label("dist"))
                .filter(AIArtifact.thread_id.in_(thread_ids))
                .filter(AIArtifact.embedding_vec.isnot(None))
                .order_by("dist")
                .limit(80)
                .all()
            )
            for a, dist in rows2:
                sim = 1.0 - float(dist) if dist is not None else 0.0
                if sim <= 0.08:
                    continue
                candidates.append(
                    {
                        "type": "artifact",
                        "id": a.id,
                        "artifact_type": a.type,
                        "title": a.title,
                        "created_at": a.created_at.isoformat(),
                        "score": round(float(sim), 4),
                        "excerpt": _trim_for_memory(a.content_md or "", 520),
                    }
                )
        except Exception:
            pass

    # Lexical artifact fallback (or additional signals when embeddings are missing).
    arts = (
        db.query(AIArtifact)
        .filter(AIArtifact.thread_id.in_(thread_ids))
        .order_by(AIArtifact.created_at.desc())
        .limit(80)
        .all()
    )
    for a in arts:
        if not (a.content_md or "").strip():
            continue
        score = lexical_score(a.content_md or "")
        if score <= 0.10:
            continue
        candidates.append(
            {
                "type": "artifact",
                "id": a.id,
                "artifact_type": a.type,
                "title": a.title,
                "created_at": a.created_at.isoformat(),
                "score": round(float(score), 4),
                "excerpt": _trim_for_memory(a.content_md or "", 520),
            }
        )

    # De-dupe by (type,id) and sort by score.
    uniq: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        key = f"{c.get('type')}:{c.get('id')}"
        prev = uniq.get(key)
        if not prev or float(c.get("score") or 0.0) > float(prev.get("score") or 0.0):
            uniq[key] = c

    out = list(uniq.values())
    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out[:AI_MEMORY_MAX_HITS]


def _markdown_to_plain(text: str) -> str:
    s = (text or "").replace("\r\n", "\n")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"^#+\\s*", "", s, flags=re.M)
    s = re.sub(r"\\[(.*?)\\]\\((.*?)\\)", r"\\1 (\\2)", s)
    s = re.sub(r"\\*\\*(.*?)\\*\\*", r"\\1", s)
    s = re.sub(r"\\*(.*?)\\*", r"\\1", s)
    s = re.sub(r"_([^_]+)_", r"\\1", s)
    s = re.sub(r"\\n{3,}", "\\n\\n", s)
    return s.strip()


THREAD_SUMMARY_MIN_MESSAGES = int(os.getenv("AI_THREAD_SUMMARY_MIN_MESSAGES", "18"))
THREAD_SUMMARY_TTL_SECONDS = int(os.getenv("AI_THREAD_SUMMARY_TTL_SECONDS", "600"))


async def _maybe_write_thread_summary(db: Session, thread_id: str) -> None:
    """
    Lightweight, deterministic summarizer to reduce retrieval noise.

    Stores as an artifact so pgvector memory can retrieve it cheaply.
    """
    msgs = (
        db.query(AIMessage)
        .filter(AIMessage.thread_id == thread_id)
        .filter(AIMessage.role.in_(("user", "assistant")))
        .order_by(AIMessage.created_at.asc())
        .all()
    )
    if len(msgs) < THREAD_SUMMARY_MIN_MESSAGES:
        return

    last = (
        db.query(AIArtifact)
        .filter(AIArtifact.thread_id == thread_id)
        .filter(AIArtifact.type == "thread_summary")
        .order_by(AIArtifact.created_at.desc())
        .first()
    )
    if last and last.created_at and (datetime.utcnow() - last.created_at).total_seconds() < THREAD_SUMMARY_TTL_SECONDS:
        return

    tail = msgs[-18:]
    lines: List[str] = ["## Thread Summary", ""]
    for m in tail:
        role = "User" if m.role == "user" else "Assistant"
        content = _trim_text(m.content_md or "", 400).strip()
        if not content:
            continue
        lines.append(f"- **{role}**: {content}")
    md = "\n".join(lines).strip() + "\n"
    emb = await _maybe_embed_text(md)
    db.add(
        AIArtifact(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            type="thread_summary",
            title="Auto summary",
            content_md=md,
            content_json=None,
            embedding_vec=emb,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()


def _pdf_from_text(title: str, text: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    for block in (text or "").split("\\n\\n"):
        pdf.multi_cell(0, 6, block.strip())
        pdf.ln(1)
    out = pdf.output(dest="S")
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return out.encode("latin-1", errors="ignore")


@app.get("/api/ai/agents", response_model=AgentListResponse)
async def list_agents(db: Session = Depends(get_db)):
    agents = db.query(AIAgent).order_by(AIAgent.is_builtin.desc(), AIAgent.id.asc()).all()
    out = []
    for a in agents:
        out.append(
            AgentInfo(
                id=a.id,
                name=a.name,
                description=a.description or "",
                scope=(a.scope or "both"),  # type: ignore[arg-type]
                allowed_prefixes=_agent_allowed_prefixes(a),
                allowed_methods=_agent_allowed_methods(a),
            )
        )
    return AgentListResponse(agents=out)


@app.post("/api/ai/agents/router", response_model=AgentRouteResponse)
async def route_agent(req: AgentRouteRequest, db: Session = Depends(get_db)):
    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")
    provider: Provider = (req.provider or _pick_default_provider(db))  # type: ignore[assignment]
    model = (req.model or "").strip() or await _pick_default_model(db, provider)
    decision = await _route_agent_decision_via_llm(db, text, (req.topology_id or "").strip() or None, provider, model)
    return AgentRouteResponse(route=decision)


@app.get("/api/ai/threads", response_model=ThreadListResponse)
async def list_threads(agent_id: str, topology_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(AIThread).filter(AIThread.agent_id == agent_id)
    if topology_id:
        q = q.filter(AIThread.topology_id == topology_id)
    else:
        q = q.filter(AIThread.topology_id.is_(None))
    threads = q.order_by(AIThread.updated_at.desc()).limit(60).all()
    return ThreadListResponse(threads=[_thread_to_info(t) for t in threads])


@app.delete("/api/ai/threads", status_code=204)
async def delete_threads(agent_id: str, topology_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Bulk delete threads for a given agent (+ optional topology scope).
    """
    q = db.query(AIThread).filter(AIThread.agent_id == agent_id)
    if topology_id:
        q = q.filter(AIThread.topology_id == topology_id)
    else:
        q = q.filter(AIThread.topology_id.is_(None))
    threads = q.all()
    if not threads:
        return Response(status_code=204)

    thread_ids = [t.id for t in threads]
    msg_ids = [row[0] for row in db.query(AIMessage.id).filter(AIMessage.thread_id.in_(thread_ids)).all()]
    if msg_ids:
        db.query(AIToolCall).filter(AIToolCall.message_id.in_(msg_ids)).delete(synchronize_session=False)
        db.query(AIMessage).filter(AIMessage.id.in_(msg_ids)).delete(synchronize_session=False)
    db.query(AIArtifact).filter(AIArtifact.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    db.query(AIRun).filter(AIRun.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    db.query(AIThread).filter(AIThread.id.in_(thread_ids)).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=204)


@app.post("/api/ai/threads", response_model=ThreadInfo)
async def create_thread(body: ThreadCreateRequest, db: Session = Depends(get_db)):
    agent = db.get(AIAgent, body.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent_id")
    topology_id = (body.topology_id or "").strip() or None
    if (agent.scope or "both") == "global" and topology_id:
        raise HTTPException(status_code=400, detail="This agent is global-only")
    if (agent.scope or "both") == "topology" and not topology_id:
        raise HTTPException(status_code=400, detail="This agent requires topology_id")

    thread = AIThread(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        topology_id=topology_id,
        title=(body.title or "").strip() or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(thread)
    db.flush()
    sys_content = (agent.system_prompt or "").strip()
    if sys_content:
        emb = await _maybe_embed_text(sys_content)
        db.add(
            AIMessage(
                id=str(uuid.uuid4()),
                thread_id=thread.id,
                role="system",
                content_md=sys_content,
                embedding_json=json.dumps(emb) if emb else None,
                embedding_vec=emb,
                created_at=datetime.utcnow(),
            )
        )
    db.commit()
    db.refresh(thread)
    return _thread_to_info(thread)


@app.delete("/api/ai/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, db: Session = Depends(get_db)):
    """
    Hard-delete a thread and all associated messages, tool calls, and artifacts.
    """
    thread = db.get(AIThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    msg_ids = [row[0] for row in db.query(AIMessage.id).filter(AIMessage.thread_id == thread_id).all()]
    if msg_ids:
        db.query(AIToolCall).filter(AIToolCall.message_id.in_(msg_ids)).delete(synchronize_session=False)
        db.query(AIMessage).filter(AIMessage.id.in_(msg_ids)).delete(synchronize_session=False)
    db.query(AIArtifact).filter(AIArtifact.thread_id == thread_id).delete(synchronize_session=False)
    db.query(AIRun).filter(AIRun.thread_id == thread_id).delete(synchronize_session=False)
    db.delete(thread)
    db.commit()
    return Response(status_code=204)


@app.get("/api/ai/threads/{thread_id}", response_model=ThreadGetResponse)
async def get_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.get(AIThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    msgs = db.query(AIMessage).filter(AIMessage.thread_id == thread.id).order_by(AIMessage.created_at.asc()).all()
    msg_ids = [m.id for m in msgs]
    tool_calls = (
        db.query(AIToolCall)
        .filter(AIToolCall.message_id.in_(msg_ids))
        .order_by(AIToolCall.created_at.asc())
        .all()
        if msg_ids
        else []
    )
    tool_by_msg: Dict[str, List[Dict[str, Any]]] = {}
    for tc in tool_calls:
        tool_by_msg.setdefault(tc.message_id, []).append(
            {
                "id": tc.id,
                "toon": tc.toon,
                "status": tc.status,
                "duration_ms": tc.duration_ms,
                "result": _safe_json_loads(tc.result_json, None),
                "created_at": tc.created_at.isoformat(),
            }
        )

    out_msgs: List[ThreadMessageInfo] = []
    for m in msgs:
        out_msgs.append(
            ThreadMessageInfo(
                id=m.id,
                role=m.role,  # type: ignore[arg-type]
                content_md=m.content_md,
                created_at=m.created_at.isoformat(),
                meta=_safe_json_loads(m.meta_json, {}) if isinstance(m.meta_json, str) else {},
                tool_calls=tool_by_msg.get(m.id, []),
            )
        )
    return ThreadGetResponse(thread=_thread_to_info(thread), messages=out_msgs)


@app.post("/api/ai/tool-calls/{tool_call_id}/execute", response_model=ExecuteMCPRequestResponse)
async def execute_saved_tool_call(tool_call_id: str, db: Session = Depends(get_db)):
    tc = db.get(AIToolCall, tool_call_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Tool call not found")
    if (tc.status or "").lower() not in ("pending", "generated"):
        raise HTTPException(status_code=400, detail="Tool call is not pending")
    msg = db.get(AIMessage, tc.message_id)
    if not msg:
        raise HTTPException(status_code=500, detail="Tool call message missing")
    thread = db.get(AIThread, msg.thread_id)
    if not thread:
        raise HTTPException(status_code=500, detail="Tool call thread missing")

    try:
        mcp_req = toon_to_request(tc.toon)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid stored TOON: {exc}")

    mcp_req = _apply_known_path_aliases(mcp_req)

    # If an LLM planned an emulation action using a topology id, resolve the emulation id deterministically.
    if thread.topology_id:
        m = re.match(r"^/api/emulation/(status|stop|pause|resume|shell)/([^/?#]+)$", str(mcp_req.path or ""))
        if m and m.group(2) == thread.topology_id:
            emu_id = await _resolve_emulation_id_for_topology(thread.topology_id)
            if emu_id:
                mcp_req.path = f"/api/emulation/{m.group(1)}/{emu_id}"
                tc.toon = request_to_toon(mcp_req).strip()
                db.add(tc)
                db.commit()

    if thread.topology_id:
        try:
            mcp_req = _apply_topology_scope(mcp_req, thread.topology_id)
        except HTTPException as exc:
            tc.status = "error"
            tc.result_json = json.dumps(
                ExecuteMCPRequestResponse(
                    status_code=int(exc.status_code),
                    headers={},
                    body={"detail": exc.detail},
                    meta={"error": True},
                ).model_dump(),
                ensure_ascii=False,
            )
            db.add(tc)
            db.commit()
            return ExecuteMCPRequestResponse(
                status_code=int(exc.status_code),
                headers={},
                body={"detail": exc.detail},
                meta={"error": True},
            )

    # Enforce the agent allowlist that produced this message, if present.
    meta = _safe_json_loads(msg.meta_json, {}) if isinstance(msg.meta_json, str) else {}
    route = meta.get("route") if isinstance(meta, dict) else None
    selected_agent_id = None
    if isinstance(route, dict):
        selected_agent_id = route.get("selected_agent_id")
    agent_for_policy: Optional[AIAgent] = None
    if isinstance(selected_agent_id, str) and selected_agent_id:
        agent_for_policy = db.get(AIAgent, selected_agent_id)
        if agent_for_policy:
            deny = _agent_allows(agent_for_policy, mcp_req)
            if deny:
                raise HTTPException(status_code=403, detail=f"Denied by agent policy: {deny}")

    tc.status = "running"
    db.add(tc)
    db.commit()

    try:
        exec_res = await _execute_mcp_request_scoped(mcp_req, thread.topology_id, agent=agent_for_policy)
    except HTTPException as exc:
        tc.status = "error"
        tc.result_json = json.dumps(
            ExecuteMCPRequestResponse(
                status_code=int(exc.status_code),
                headers={},
                body={"detail": exc.detail},
                meta={"error": True},
            ).model_dump(),
            ensure_ascii=False,
        )
        db.add(tc)
        db.commit()
        return ExecuteMCPRequestResponse(
            status_code=int(exc.status_code),
            headers={},
            body={"detail": exc.detail},
            meta={"error": True},
        )
    except Exception as exc:
        tc.status = "error"
        tc.result_json = json.dumps(
            ExecuteMCPRequestResponse(
                status_code=500,
                headers={},
                body={"detail": str(exc)},
                meta={"error": True},
            ).model_dump(),
            ensure_ascii=False,
        )
        db.add(tc)
        db.commit()
        return ExecuteMCPRequestResponse(status_code=500, headers={}, body={"detail": str(exc)}, meta={"error": True})

    tc.status = "success" if exec_res.status_code < 400 else "error"
    tc.result_json = json.dumps(exec_res.model_dump(), ensure_ascii=False)
    try:
        tc.duration_ms = int((exec_res.meta or {}).get("duration_ms")) if exec_res.meta else None
    except Exception:
        tc.duration_ms = None
    db.add(tc)
    db.commit()
    return exec_res


async def _agent_chat_loop(
    db: Session,
    agent: AIAgent,
    thread: AIThread,
    provider: Provider,
    model: str,
    user_text: str,
    max_steps: int,
    memory_hits: List[Dict[str, Any]],
    router_mode: bool = False,
    request_id: Optional[str] = None,
) -> AgentChatResponse:
    scope_topology_id = thread.topology_id

    base_system = (
        f"{(agent.system_prompt or '').strip()}\n\n"
        "You are an MCP-first agent.\n"
        "You can either call a tool (TOON) or reply to the user.\n"
        "Return ONLY JSON (no markdown) in one of these forms:\n"
        '{"action":"tool","toon":"<TOON request>","reason":"<short>"}\n'
        '{"action":"final","content":"<assistant reply in Markdown>"}\n'
        "\n"
        "Rules for tool calls:\n"
        "- PATH must start with /api/\n"
        "- Use only the allowed method/path groups for this agent\n"
        "- When scoped, operate ONLY on the thread topology\n"
    ).strip()

    allowed = {
        "allowed_methods": _agent_allowed_methods(agent),
        "allowed_prefixes": _agent_allowed_prefixes(agent),
        "scope": agent.scope or "both",
        "topology_id": scope_topology_id,
    }
    system_parts = [
        base_system,
        "Agent policy (JSON):\n" + json.dumps(allowed, ensure_ascii=False),
        _capabilities_text(scope_topology_id),
    ]
    if scope_topology_id:
        pinned = db.get(AIPinnedContext, scope_topology_id)
        pinned_text = _pinned_context_text(pinned)
        if pinned_text:
            system_parts.append(pinned_text)
    if memory_hits:
        mem_text = "\\n".join([f"- ({h.get('type')}) score={h.get('score')}: {h.get('excerpt')}" for h in memory_hits])
        system_parts.append("Relevant memory:\\n" + mem_text)
    system = "\\n\\n".join([p for p in system_parts if p.strip()])

    history_msgs = db.query(AIMessage).filter(AIMessage.thread_id == thread.id).order_by(AIMessage.created_at.asc()).all()

    llm_messages: List[ChatMessage] = [ChatMessage(role="system", content=system)]
    for m in history_msgs[-24:]:
        if m.role in ("user", "assistant"):
            llm_messages.append(ChatMessage(role=m.role, content=m.content_md))

    llm_messages.append(ChatMessage(role="user", content=user_text))

    tool_calls: List[MCPAgentToolCall] = []
    raw_steps: List[Dict[str, Any]] = []
    denied_tools = 0

    last_user = user_text
    for _step in range(max_steps):
        chat_req = ChatRequest(
            provider=provider,
            model=model,
            api_key=_resolve_api_key(db, provider, None),
            messages=llm_messages,
            temperature=0.0,
            max_tokens=900,
        )
        resp = await _chat_dispatch(chat_req)
        raw_steps.append(resp.raw)

        action_obj = _coerce_agent_action_from_text(resp.content)
        if action_obj is None:
            action_obj = await _repair_agent_output(
                provider=provider,
                model=model,
                db=db,
                api_key=None,
                scope_topology_id=scope_topology_id,
                bad_output=resp.content or "",
                error_hint="Output was not valid agent JSON and not valid TOON",
            )

        action = str(action_obj.get("action") or "").lower().strip()
        if action == "final":
            content = str(action_obj.get("content") or "").strip()
            return AgentChatResponse(
                thread_id=thread.id,
                thread_agent_id=thread.agent_id,
                agent_id=agent.id,
                assistant=content,
                tool_calls=tool_calls,
                raw_steps=raw_steps,
                memory_hits=memory_hits,
            )

        if action != "tool":
            llm_messages.append(ChatMessage(role="system", content="Invalid action. Use {action:tool|final} JSON."))
            continue

        toon = _strip_code_fences(str(action_obj.get("toon") or "")).strip()
        if not toon:
            llm_messages.append(ChatMessage(role="system", content="Tool call missing toon. Try again."))
            continue

        first_line = next((ln.strip() for ln in toon.splitlines() if ln.strip()), "")
        first_token = (first_line.split() or [""])[0]
        if first_token.startswith("/") and first_token[1:].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            toon = first_line.lstrip("/") + "\n" + "\n".join([ln for ln in toon.splitlines()[1:]])
        # Common model shortcut: returns only the path (infer method from capabilities)
        first_line = next((ln.strip() for ln in toon.splitlines() if ln.strip()), "")
        if (" " not in first_line) and (first_line.startswith("/api/") or first_line.startswith("api/")):
            path_only = first_line if first_line.startswith("/api/") else "/" + first_line
            method = _infer_method_for_path_only(path_only)
            toon = f"{method} {path_only}\n" + "\n".join([ln for ln in toon.splitlines()[1:]])

        try:
            mcp_req = toon_to_request(toon)
        except Exception as e:
            llm_messages.append(ChatMessage(role="system", content=f"Invalid TOON: {e}. Try again."))
            continue

        mcp_req = _apply_known_path_aliases(mcp_req)
        if scope_topology_id:
            try:
                mcp_req = _apply_topology_scope(mcp_req, scope_topology_id)
            except HTTPException as exc:
                denied_tools += 1
                if router_mode and denied_tools >= 2:
                    raise ToolDeniedError(mcp_req=mcp_req, reason=str(exc.detail))
                llm_messages.append(ChatMessage(role="system", content=f"Tool call denied by scope: {exc.detail}"))
                continue

        deny_reason = _agent_allows(agent, mcp_req)
        if deny_reason:
            denied_tools += 1
            if router_mode and denied_tools >= 2:
                raise ToolDeniedError(mcp_req=mcp_req, reason=deny_reason)
            llm_messages.append(ChatMessage(role="system", content=f"Tool call denied: {deny_reason}"))
            continue
        if mcp_req.path == "/api/services" and not _user_asked_for_services(last_user):
            llm_messages.append(
                ChatMessage(
                    role="system",
                    content="Tool call GET /api/services is only allowed when the user explicitly asks about services/microservices. Use a different tool (e.g. /api/topologies) or reply with action=final.",
                )
            )
            continue

        # Resolve common placeholders deterministically (before confirmation gating).
        if scope_topology_id:
            m = re.match(r"^/api/emulation/(status|stop|pause|resume|shell)/([^/?#]+)$", str(mcp_req.path or ""))
            if m and m.group(2) == scope_topology_id:
                emu_id = await _resolve_emulation_id_for_topology(scope_topology_id)
                if emu_id:
                    mcp_req.path = f"/api/emulation/{m.group(1)}/{emu_id}"

        if isinstance(mcp_req.path, str) and "{emulation_id}" in mcp_req.path and mcp_req.path.startswith("/api/emulation/stop"):
            active_req = MCPRequest(method="GET", path="/api/emulation/active")
            active_res = await _execute_mcp_request_scoped(active_req, scope_topology_id, agent=agent, request_id=request_id)
            tool_calls.append(MCPAgentToolCall(toon=request_to_toon(active_req).strip(), result=active_res))
            active_body = active_res.body
            emulations = (active_body or {}).get("emulations") if isinstance(active_body, dict) else []
            emulations = emulations if isinstance(emulations, list) else []
            picked = next((e for e in emulations if isinstance(e, dict) and e.get("status") == "running"), None)
            emu_id = picked.get("emulation_id") if isinstance(picked, dict) else None
            if not emu_id:
                return AgentChatResponse(
                    thread_id=thread.id,
                    thread_agent_id=thread.agent_id,
                    agent_id=agent.id,
                    assistant="No running emulation found to stop.",
                    tool_calls=[],
                    raw_steps=raw_steps,
                    memory_hits=memory_hits,
                )
            mcp_req.path = mcp_req.path.replace("{emulation_id}", str(emu_id))

        if _is_dangerous_mcp(mcp_req):
            effective_toon = request_to_toon(mcp_req).strip()
            planned = ExecuteMCPRequestResponse(
                status_code=0,
                headers={},
                body=None,
                meta={
                    "planned": True,
                    "requires_confirmation": True,
                    "method": mcp_req.method,
                    "path": mcp_req.path,
                },
            )
            tool_calls.append(MCPAgentToolCall(toon=effective_toon, result=planned))
            return AgentChatResponse(
                thread_id=thread.id,
                thread_agent_id=thread.agent_id,
                agent_id=agent.id,
                assistant=(
                    "This action is marked as potentially destructive and requires confirmation.\n\n"
                    "Review the MCP Tool Call below and click **Execute** to run it."
                ),
                tool_calls=tool_calls,
                raw_steps=raw_steps,
                memory_hits=memory_hits,
            )

        exec_res = await _execute_mcp_request_scoped(mcp_req, scope_topology_id, agent=agent, request_id=request_id)
        effective_toon = request_to_toon(mcp_req).strip()
        tool_calls.append(MCPAgentToolCall(toon=effective_toon, result=exec_res))

        summary = _summarize_tool_call(effective_toon, exec_res)
        llm_messages.append(ChatMessage(role="system", content=summary))

        if exec_res.status_code >= 400:
            llm_messages.append(
                ChatMessage(
                    role="system",
                    content=f"Tool returned HTTP {exec_res.status_code}. Debug with another tool or reply with action=final explaining the failure.",
                )
            )

    summary = _pick_best_summary(tool_calls, last_user) if tool_calls else "I couldn't complete that within the step limit."
    return AgentChatResponse(
        thread_id=thread.id,
        thread_agent_id=thread.agent_id,
        agent_id=agent.id,
        assistant=summary,
        tool_calls=tool_calls,
        raw_steps=raw_steps,
        memory_hits=memory_hits,
    )


@app.post("/api/ai/agents/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest, db: Session = Depends(get_db)):
    started_perf = time.perf_counter()
    run_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    run_started_at = datetime.utcnow()
    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")
    if req.max_steps < 1 or req.max_steps > 10:
        raise HTTPException(status_code=400, detail="max_steps must be between 1 and 10")

    provider: Provider = (req.provider or _pick_default_provider(db))  # type: ignore[assignment]
    model = (req.model or "").strip() or await _pick_default_model(db, provider)

    thread: Optional[AIThread] = None
    thread_agent: Optional[AIAgent] = None
    selected_agent: Optional[AIAgent] = None
    route_info: Optional[AgentRouteInfo] = None
    if req.thread_id:
        thread = db.get(AIThread, req.thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread_agent = db.get(AIAgent, thread.agent_id)
        if not thread_agent:
            raise HTTPException(status_code=500, detail="Thread agent missing")
    else:
        topology_id = (req.topology_id or "").strip() or None
        requested_agent_id = (req.agent_id or "").strip()
        if requested_agent_id:
            thread_agent = db.get(AIAgent, requested_agent_id)
            if not thread_agent:
                raise HTTPException(status_code=404, detail="Unknown agent_id")
        else:
            decision = await _route_agent_decision_via_llm(db, text, topology_id, provider, model)
            thread_agent = db.get(AIAgent, decision.selected_agent_id)
            if not thread_agent:
                raise HTTPException(status_code=404, detail="Unknown agent_id")
            route_info = AgentRouteInfo(mode="fixed", **decision.model_dump(exclude={"mode"}))

        if (thread_agent.scope or "both") == "global" and topology_id:
            topology_id = None
        if (thread_agent.scope or "both") == "topology" and not topology_id:
            raise HTTPException(status_code=400, detail="This agent requires topology_id")

        thread = AIThread(
            id=str(uuid.uuid4()),
            agent_id=thread_agent.id,
            topology_id=topology_id,
            title=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(thread)
        db.flush()
        sys_content = (thread_agent.system_prompt or "").strip()
        if sys_content:
            emb = await _maybe_embed_text(sys_content)
            db.add(
                AIMessage(
                    id=str(uuid.uuid4()),
                    thread_id=thread.id,
                    role="system",
                    content_md=sys_content,
                    embedding_json=json.dumps(emb) if emb else None,
                    embedding_vec=emb,
                    created_at=datetime.utcnow(),
                )
            )
        db.commit()
        db.refresh(thread)

    assert thread is not None and thread_agent is not None

    # Router-mode: a thread can be bound to the router and dynamically choose a specialized agent per message.
    if thread_agent.id == "router":
        decision = await _route_agent_decision_via_llm(db, text, thread.topology_id, provider, model)
        selected_agent = db.get(AIAgent, decision.selected_agent_id)
        if not selected_agent:
            raise HTTPException(status_code=404, detail="Routed agent not found")
        route_info = decision
    else:
        selected_agent = thread_agent
        if route_info is None:
            route_info = AgentRouteInfo(
                mode="fixed",
                selected_agent_id=selected_agent.id,
                selected_agent_name=selected_agent.name,
            )

    # Keep per-topology pinned context fresh (best-effort).
    if thread.topology_id:
        try:
            await _refresh_pinned_context(db, thread.topology_id, request_id=request_id)
        except Exception:
            pass

    user_embedding = await _maybe_embed_text(text)
    # Compute memory before inserting this user message, so the current message doesn't "hit itself".
    memory_hits = await _memory_hits_for_topology(db, thread.topology_id, user_embedding, text) if thread.topology_id else []

    db.add(
        AIMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="user",
            content_md=text,
            embedding_json=json.dumps(user_embedding) if user_embedding else None,
            embedding_vec=user_embedding,
            created_at=datetime.utcnow(),
        )
    )
    thread.updated_at = datetime.utcnow()
    db.add(thread)
    db.commit()

    assert selected_agent is not None and route_info is not None

    router_mode = thread_agent.id == "router"
    route_trace: List[Dict[str, Any]] = list(route_info.trace or [])

    response: Optional[AgentChatResponse] = None
    usage: Dict[str, Any] = {}
    status = "success"
    error_json: Optional[Dict[str, Any]] = None
    duration_ms = int((time.perf_counter() - started_perf) * 1000)

    try:
        if router_mode:
            # If a tool is denied by one agent, re-route once using tool/path affinity.
            attempts = 0
            current_agent = selected_agent
            current_route = route_info
            while True:
                try:
                    response = await _agent_chat_loop(
                        db=db,
                        agent=current_agent,
                        thread=thread,
                        provider=provider,
                        model=model,
                        user_text=text,
                        max_steps=req.max_steps,
                        memory_hits=memory_hits,
                        router_mode=True,
                        request_id=request_id,
                    )
                    current_route.trace = route_trace
                    response.route = current_route
                    break
                except ToolDeniedError as err:
                    attempts += 1
                    route_trace.append(
                        {
                            "event": "tool_denied",
                            "reason": err.reason,
                            "attempted_agent_id": current_agent.id,
                            "method": str(err.mcp_req.method),
                            "path": str(err.mcp_req.path),
                        }
                    )
                    if attempts >= 2:
                        response = AgentChatResponse(
                            thread_id=thread.id,
                            thread_agent_id=thread.agent_id,
                            agent_id=current_agent.id,
                            assistant=f"Tool call denied by agent policy: {err.reason}",
                            tool_calls=[],
                            raw_steps=[],
                            memory_hits=memory_hits,
                            route=current_route,
                        )
                        break
                    alt = _pick_agent_for_mcp_request(db, err.mcp_req, thread.topology_id)
                    if not alt or alt.id == current_agent.id:
                        # Fallback to re-routing from the original message
                        decision2 = await _route_agent_decision_via_llm(db, text, thread.topology_id, provider, model)
                        alt = db.get(AIAgent, decision2.selected_agent_id) or alt
                        if alt:
                            current_route = decision2
                    if not alt:
                        response = AgentChatResponse(
                            thread_id=thread.id,
                            thread_agent_id=thread.agent_id,
                            agent_id=current_agent.id,
                            assistant=f"Tool call denied and no alternative agent could be selected: {err.reason}",
                            tool_calls=[],
                            raw_steps=[],
                            memory_hits=memory_hits,
                            route=current_route,
                        )
                        break
                    route_trace.append({"event": "reroute", "selected_agent_id": alt.id, "selected_agent_name": alt.name})
                    current_agent = alt
                    current_route.selected_agent_id = alt.id
                    current_route.selected_agent_name = alt.name
                    continue
        else:
            response = await _agent_chat_loop(
                db=db,
                agent=selected_agent,
                thread=thread,
                provider=provider,
                model=model,
                user_text=text,
                max_steps=req.max_steps,
                memory_hits=memory_hits,
                router_mode=False,
                request_id=request_id,
            )
            response.route = route_info

        assert response is not None

        assistant_text = (response.assistant or "").strip()
        assistant_embedding = await _maybe_embed_text(assistant_text)
        assistant_meta: Dict[str, Any] = {"route": (response.route.model_dump() if response.route else None)}
        if response.raw_steps:
            assistant_meta["raw_steps"] = response.raw_steps
        duration_ms = int((time.perf_counter() - started_perf) * 1000)
        usage = _extract_usage_from_raw_steps(response.raw_steps or [])
        assistant_meta["run"] = {
            "run_id": run_id,
            "request_id": request_id,
            "provider": provider,
            "model": model,
            "thread_agent_id": thread_agent.id,
            "agent_id": response.agent_id,
            "topology_id": thread.topology_id,
            "duration_ms": duration_ms,
            "tool_calls": len(response.tool_calls or []),
            "usage": usage,
        }
        assistant_msg = AIMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            role="assistant",
            content_md=assistant_text,
            meta_json=json.dumps(assistant_meta, ensure_ascii=False),
            embedding_json=json.dumps(assistant_embedding) if assistant_embedding else None,
            embedding_vec=assistant_embedding,
            created_at=datetime.utcnow(),
        )
        db.add(assistant_msg)

        for tc in response.tool_calls:
            tool_duration_ms = None
            try:
                tool_duration_ms = int((tc.result.meta or {}).get("duration_ms")) if tc.result and tc.result.meta else None
            except Exception:
                tool_duration_ms = None
            requires_confirmation = bool((tc.result.meta or {}).get("requires_confirmation")) if tc.result and tc.result.meta else False
            db.add(
                AIToolCall(
                    id=str(uuid.uuid4()),
                    message_id=assistant_msg.id,
                    toon=tc.toon,
                    status=(
                        "pending"
                        if requires_confirmation
                        else ("success" if tc.result and tc.result.status_code < 400 else "error")
                    ),
                    result_json=json.dumps(tc.result.model_dump(), ensure_ascii=False) if tc.result else None,
                    duration_ms=tool_duration_ms,
                    created_at=datetime.utcnow(),
                )
            )

        thread.updated_at = datetime.utcnow()
        db.add(thread)
        db.commit()

        response.run = assistant_meta.get("run")
        try:
            await _maybe_write_thread_summary(db, thread.id)
        except Exception:
            db.rollback()

        return response
    except Exception as exc:
        status = "error"
        error_json = {"type": type(exc).__name__, "message": str(exc)[:800]}
        raise
    finally:
        finished_at = datetime.utcnow()
        agent_id = None
        try:
            if response and response.agent_id:
                agent_id = response.agent_id
            elif selected_agent:
                agent_id = selected_agent.id
        except Exception:
            agent_id = None
        try:
            db.rollback()
        except Exception:
            pass
        try:
            if thread and agent_id:
                db.add(
                    AIRun(
                        id=run_id,
                        thread_id=thread.id,
                        topology_id=thread.topology_id,
                        thread_agent_id=thread_agent.id,
                        agent_id=agent_id,
                        provider=provider,
                        model=model,
                        request_id=request_id,
                        route_json=json.dumps((response.route.model_dump() if response and response.route else (route_info.model_dump() if route_info else None)), ensure_ascii=False),
                        usage_json=json.dumps(usage, ensure_ascii=False) if usage else None,
                        status=status,
                        error_json=json.dumps(error_json, ensure_ascii=False) if error_json else None,
                        started_at=run_started_at,
                        finished_at=finished_at,
                        duration_ms=int((time.perf_counter() - started_perf) * 1000),
                        created_at=finished_at,
                    )
                )
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass


@app.post("/api/ai/reports/thread/{thread_id}")
async def generate_thread_report(thread_id: str, body: ReportGenerateRequest, db: Session = Depends(get_db)):
    thread = db.get(AIThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    agent = db.get(AIAgent, thread.agent_id)
    if not agent:
        raise HTTPException(status_code=500, detail="Thread agent missing")

    provider: Provider = (body.provider or _pick_default_provider(db))  # type: ignore[assignment]
    model = (body.model or "").strip() or await _pick_default_model(db, provider)
    api_key = _resolve_api_key(db, provider, None)
    if provider in ("openai", "anthropic", "gemini") and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} is not configured. Set API key in AI Settings.")

    msgs = db.query(AIMessage).filter(AIMessage.thread_id == thread.id).order_by(AIMessage.created_at.asc()).all()
    msg_ids = [m.id for m in msgs]
    tool_calls = (
        db.query(AIToolCall)
        .filter(AIToolCall.message_id.in_(msg_ids))
        .order_by(AIToolCall.created_at.asc())
        .all()
        if msg_ids
        else []
    )

    timeline = []
    for m in msgs:
        if m.role == "system":
            continue
        timeline.append({"role": m.role, "content": m.content_md, "created_at": m.created_at.isoformat()})
    tools = []
    for tc in tool_calls:
        tools.append(
            {
                "toon": tc.toon,
                "status": tc.status,
                "duration_ms": tc.duration_ms,
                "result": _safe_json_loads(tc.result_json, None),
                "created_at": tc.created_at.isoformat(),
            }
        )

    report_title = (body.title or "").strip() or (thread.title or "").strip() or f"{agent.name} Report"

    baseline_lines: List[str] = [
        f"# {report_title}",
        "",
        f"- Thread: `{thread.id}`",
        f"- Agent: `{thread.agent_id}`",
        f"- Topology: `{thread.topology_id or 'global'}`",
        "",
        "## Summary",
        "Auto-generated report from the agent conversation and tool calls.",
        "",
        "## Conversation Highlights",
    ]
    for item in timeline[-12:]:
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        baseline_lines.append(f"**{role}**: {content}")
        baseline_lines.append("")
    baseline_lines.extend(["## Tool Calls", ""])
    if tools:
        for t in tools[-20:]:
            toon = str(t.get("toon") or "").strip()
            status = str(t.get("status") or "")
            duration_ms = t.get("duration_ms")
            baseline_lines.append(f"- `{status}` {toon} ({duration_ms}ms)")
    else:
        baseline_lines.append("- (none)")
    baseline_lines.extend(["", "## Findings", "", "- (fill in)", "", "## Risks", "", "- (fill in)", "", "## Recommendations", "", "- (fill in)", "", "## Next Steps", "", "- (fill in)"])
    baseline_md = "\n".join(baseline_lines).strip() + "\n"

    system = (
        "You are a report writer for a network emulation platform.\n"
        "Rewrite the provided draft report into a clean, concise Markdown report.\n"
        "Rules:\n"
        "- Output ONLY Markdown.\n"
        "- Keep the same facts; do NOT invent IDs, statuses, metrics, or events.\n"
        "- Do NOT describe API schemas or explain JSON structure.\n"
        "- Use headings: Summary, Actions Taken, Findings, Risks, Recommendations, Next Steps.\n"
    )
    user = json.dumps(
        {
            "thread": {"id": thread.id, "agent_id": thread.agent_id, "topology_id": thread.topology_id, "title": thread.title},
            "draft_report_md": baseline_md,
            "tool_calls": tools,
        },
        ensure_ascii=False,
    )

    md = baseline_md
    try:
        resp = await _chat_dispatch(
            ChatRequest(
                provider=provider,
                model=model,
                api_key=api_key,
                messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
                temperature=0.1,
                max_tokens=1200,
            )
        )
        candidate = (resp.content or "").strip()
        if "## Summary" in candidate and len(candidate) > 200:
            md = candidate
    except Exception:
        md = baseline_md

    art_embedding = await _maybe_embed_text(md)
    db.add(
        AIArtifact(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            type="report",
            title=report_title,
            content_md=md,
            content_json=json.dumps({"embedding": art_embedding}, ensure_ascii=False) if art_embedding else None,
            embedding_vec=art_embedding,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    if body.format == "pdf":
        plain = _markdown_to_plain(md)
        pdf_bytes = _pdf_from_text(report_title, plain)
        filename = f"report-{thread.id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    filename = f"report-{thread.id}.md"
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
