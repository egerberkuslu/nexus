"""
P4 Manager Service (Port 8010)
Manages P4 program compilation and BMv2 switch deployment
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
import subprocess
import tempfile
import os
import json
from datetime import datetime
import docker
import re
import shutil
import uuid

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux P4 Manager Service",
    description="P4 program compilation and BMv2 switch management",
    version="1.0.0"
)

# CORS middleware
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
docker_client = None

SERVICE_PORT = 8010
API_PREFIX = "/api/p4"
P4_STORAGE_ROOT = os.getenv("P4_STORAGE_ROOT", "/var/lib/caduceus/p4")
P4_PROGRAMS_VOLUME = os.getenv("P4_PROGRAMS_VOLUME", "caduceus-p4-programs")

# P4 programs registry
p4_programs: Dict[str, Dict] = {}
bmv2_switches: Dict[str, Dict] = {}


# Pydantic models
class P4ProgramCompile(BaseModel):
    name: str = Field(..., description="Program name")
    source_code: str = Field(..., description="P4 source code")
    target: str = Field(default="bmv2", description="Compilation target: bmv2, tofino")
    architecture: str = Field(default="v1model", description="P4 architecture: v1model, psa")


class P4ProgramResponse(BaseModel):
    program_id: str
    name: str
    target: str
    architecture: str
    status: str
    compiled_at: Optional[datetime] = None
    source_file: Optional[str] = None
    json_file: Optional[str] = None
    p4info_file: Optional[str] = None
    error: Optional[str] = None


class BMv2SwitchCreate(BaseModel):
    name: str = Field(..., description="Switch name")
    program_id: str = Field(..., description="P4 program ID")
    device_id: int = Field(default=0, description="BMv2 device ID")
    thrift_port: int = Field(default=9090, description="Thrift port")
    log_level: str = Field(default="info", description="Log level: trace, debug, info, warn, error")
    pcap_dump: bool = Field(default=False, description="Enable pcap dump")


class BMv2SwitchResponse(BaseModel):
    switch_id: str
    name: str
    program_id: str
    device_id: int
    thrift_port: int
    status: str
    created_at: datetime
    pid: Optional[int] = None


# Helper functions
def get_docker_client():
    """Get Docker client"""
    global docker_client
    if docker_client is None:
        sock = "/var/run/docker.sock"
        # Prefer the standard unix socket when present (works reliably inside compose).
        if os.path.exists(sock):
            docker_client = docker.DockerClient(base_url=f"unix://{sock}")
        else:
            docker_client = docker.from_env()
    return docker_client


def _safe_program_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "p4-program"
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:64] or "p4-program"


def _program_dir(program_id: str) -> str:
    return os.path.join(P4_STORAGE_ROOT, program_id)

def _metadata_path(program_id: str) -> str:
    return os.path.join(_program_dir(program_id), "metadata.json")


def _load_programs_from_disk() -> None:
    """Best-effort reload of compiled programs from the shared storage volume."""
    if not os.path.isdir(P4_STORAGE_ROOT):
        return

    loaded = 0
    for entry in os.listdir(P4_STORAGE_ROOT):
        program_dir = os.path.join(P4_STORAGE_ROOT, entry)
        if not os.path.isdir(program_dir):
            continue
        meta_path = os.path.join(program_dir, "metadata.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
            program_id = str(meta.get("program_id") or entry)
            meta["program_id"] = program_id
            p4_programs[program_id] = meta
            loaded += 1
        except Exception as exc:
            logger.warning("Failed to load P4 program metadata from %s: %s", meta_path, exc)

    if loaded:
        logger.info("Loaded %s P4 programs from %s", loaded, P4_STORAGE_ROOT)


def _persist_program_metadata(program: Dict[str, Any]) -> None:
    program_id = str(program.get("program_id") or "")
    if not program_id:
        return
    try:
        os.makedirs(_program_dir(program_id), exist_ok=True)
        with open(_metadata_path(program_id), "w", encoding="utf-8") as handle:
            json.dump(program, handle, default=str, indent=2)
    except Exception as exc:
        logger.warning("Failed to persist P4 program metadata for %s: %s", program_id, exc)



def _compile_with_local_p4c(p4_file: str, json_file: str, p4info_file: str, architecture: str) -> Dict[str, Any]:
    cmd = [
        "p4c-bm2-ss",
        "--p4v", "16",
        "--arch", architecture,
        "-o", json_file,
        "--p4runtime-files", p4info_file,
        p4_file
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr or result.stdout or "p4c-bm2-ss failed"}
    return {"success": True, "stdout": result.stdout, "stderr": result.stderr}


def _compile_with_docker_p4c(program_id: str, architecture: str) -> Dict[str, Any]:
    client = get_docker_client()
    image = os.getenv("P4C_DOCKER_IMAGE", "p4lang/p4c:stable")

    # The P4 source and artifacts live in the shared docker volume mounted at P4_STORAGE_ROOT
    # (inside this container). The Docker daemon cannot mount this container's filesystem paths,
    # so we mount the *named volume* directly into the compiler container at /workspace.
    p4_basename = f"{program_id}.p4"
    json_basename = f"{program_id}.json"
    p4info_basename = f"{program_id}.p4info.txt"

    command = [
        "p4c-bm2-ss",
        "--p4v", "16",
        "--arch", architecture,
        "-o", f"/workspace/{program_id}/{json_basename}",
        "--p4runtime-files", f"/workspace/{program_id}/{p4info_basename}",
        f"/workspace/{program_id}/{p4_basename}",
    ]
    try:
        logs = client.containers.run(
            image=image,
            command=command,
            volumes={P4_PROGRAMS_VOLUME: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            remove=True,
            stdout=True,
            stderr=True,
        )
        if isinstance(logs, (bytes, bytearray)):
            logs = logs.decode(errors="replace")
        return {"success": True, "stdout": str(logs)}
    except docker.errors.ContainerError as exc:
        out = getattr(exc, "stderr", None) or getattr(exc, "stdout", None) or b""
        if isinstance(out, (bytes, bytearray)):
            out = out.decode(errors="replace")
        return {"success": False, "error": str(out) or str(exc)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def publish_event(event_type: str, data: Dict):
    """Publish P4 event"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"p4_manager.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


def compile_p4_program(program_id: str, source_code: str, target: str, architecture: str) -> Dict:
    """Compile P4 program using p4c compiler"""
    try:
        compiled_dir = _program_dir(program_id)
        os.makedirs(compiled_dir, exist_ok=True)

        p4_file = os.path.join(compiled_dir, f"{program_id}.p4")
        json_file = os.path.join(compiled_dir, f"{program_id}.json")
        p4info_file = os.path.join(compiled_dir, f"{program_id}.p4info.txt")

        # Write P4 source code into the shared storage volume so the Docker-based compiler can see it.
        with open(p4_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        if target != "bmv2":
            return {"success": False, "error": f"Unsupported target: {target}"}

        # Prefer local p4c if present; fall back to running p4c inside a Docker container.
        try:
            result = _compile_with_local_p4c(p4_file, json_file, p4info_file, architecture)
        except FileNotFoundError:
            result = {"success": False, "error": "p4c-bm2-ss not found"}

        if not result.get("success"):
            logger.warning(
                "Local P4 compilation unavailable/failed (%s); trying Docker-based p4c.",
                result.get("error")
            )
            result = _compile_with_docker_p4c(program_id, architecture)

        if not result.get("success"):
            logger.error("P4 compilation failed: %s", result.get("error", "unknown error"))
            return {"success": False, "error": result.get("error", "Compilation failed")}

        return {
            "success": True,
            "source_file": p4_file,
            "json_file": json_file if os.path.exists(json_file) else None,
            "p4info_file": p4info_file if os.path.exists(p4info_file) else None,
            "compiler_output": result.get("stdout", ""),
        }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Compilation timeout"
        }
    except Exception as e:
        logger.error(f"Compilation error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def start_bmv2_switch(switch_id: str, config: Dict) -> Dict:
    """Start BMv2 simple_switch process"""
    try:
        program_id = config["program_id"]
        if program_id not in p4_programs:
            return {"success": False, "error": f"Program {program_id} not found"}
        
        program = p4_programs[program_id]
        if program["status"] != "compiled":
            return {"success": False, "error": f"Program {program_id} not compiled"}
        
        # BMv2 command
        cmd = [
            "simple_switch",
            "-i", "0@veth0",  # Interface specification
            "-i", "1@veth1",
            "--thrift-port", str(config["thrift_port"]),
            "--device-id", str(config["device_id"]),
            "--log-level", config["log_level"]
        ]
        
        if config.get("pcap_dump"):
            cmd.extend(["--pcap"])
        
        # Add JSON file
        cmd.append(program["json_file"])
        
        # Start BMv2 process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Started BMv2 switch {switch_id} (PID: {process.pid})")
        
        return {
            "success": True,
            "pid": process.pid,
            "process": process
        }
    
    except Exception as e:
        logger.error(f"Failed to start BMv2 switch: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting P4 Manager Service...")
    try:
        # Create P4 storage directory
        os.makedirs(P4_STORAGE_ROOT, exist_ok=True)
        _load_programs_from_disk()
        
        # Register with Consul
        consul_client.register_service("p4-manager", SERVICE_PORT)
        rabbitmq_publisher.connect()
        
        logger.info("P4 Manager Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down P4 Manager Service...")
    
    # Stop all BMv2 switches
    for switch_id, switch_info in list(bmv2_switches.items()):
        try:
            if switch_info.get("process"):
                switch_info["process"].terminate()
                switch_info["process"].wait(timeout=5)
                logger.info(f"Stopped BMv2 switch: {switch_id}")
        except Exception as e:
            logger.error(f"Error stopping switch {switch_id}: {e}")
    
    consul_client.deregister_service("p4-manager")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "p4-manager",
        "p4_programs": len(p4_programs),
        "bmv2_switches": len(bmv2_switches),
        "storage_root": P4_STORAGE_ROOT,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post(f"{API_PREFIX}/programs/compile", response_model=P4ProgramResponse)
async def compile_program(program: P4ProgramCompile):
    """Compile P4 program"""
    try:
        logger.info(f"Compiling P4 program: {program.name}")
        
        safe_name = _safe_program_name(program.name)
        program_id = f"{safe_name}-{uuid.uuid4().hex[:10]}"
        
        # Compile program
        result = compile_p4_program(
            program_id,
            program.source_code,
            program.target,
            program.architecture
        )
        
        if not result["success"]:
            program_data = {
                "program_id": program_id,
                "name": program.name,
                "target": program.target,
                "architecture": program.architecture,
                "status": "failed",
                "error": result["error"]
            }
            p4_programs[program_id] = program_data
            
            return P4ProgramResponse(**program_data)
        
        # Store program info
        program_data = {
            "program_id": program_id,
            "name": program.name,
            "target": program.target,
            "architecture": program.architecture,
            "status": "compiled",
            "compiled_at": datetime.utcnow(),
            "source_file": result.get("source_file"),
            "json_file": result["json_file"],
            "p4info_file": result["p4info_file"],
            "compiler_output": result.get("compiler_output", "")
        }
        
        p4_programs[program_id] = program_data
        _persist_program_metadata(program_data)
        
        # Publish event
        publish_event("compiled", {
            "program_id": program_id,
            "name": program.name
        })
        
        return P4ProgramResponse(**program_data)
    
    except Exception as e:
        logger.error(f"Error compiling program: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(f"{API_PREFIX}/programs/upload", response_model=P4ProgramResponse)
async def upload_and_compile_program(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    target: str = Form("bmv2"),
    architecture: str = Form("v1model"),
):
    """Upload a .p4 file and compile it."""
    filename = file.filename or "program.p4"
    if not filename.lower().endswith(".p4"):
        raise HTTPException(status_code=400, detail="Only .p4 files are supported")

    try:
        source_bytes = await file.read()
        source_code = source_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    program_name = name or os.path.splitext(os.path.basename(filename))[0]
    payload = P4ProgramCompile(
        name=program_name,
        source_code=source_code,
        target=target,
        architecture=architecture,
    )
    return await compile_program(payload)


@app.get(f"{API_PREFIX}/programs", response_model=List[P4ProgramResponse])
async def list_programs():
    """List all P4 programs"""
    return [P4ProgramResponse(**p) for p in p4_programs.values()]


@app.get(f"{API_PREFIX}/programs/{{program_id}}", response_model=P4ProgramResponse)
async def get_program(program_id: str):
    """Get P4 program details"""
    if program_id not in p4_programs:
        raise HTTPException(status_code=404, detail=f"Program {program_id} not found")
    
    return P4ProgramResponse(**p4_programs[program_id])


@app.delete(f"{API_PREFIX}/programs/{{program_id}}", status_code=204)
async def delete_program(program_id: str):
    """Delete P4 program"""
    if program_id not in p4_programs:
        raise HTTPException(status_code=404, detail=f"Program {program_id} not found")
    
    # Check if program is used by any switch
    for switch in bmv2_switches.values():
        if switch["program_id"] == program_id:
            raise HTTPException(
                status_code=400,
                detail=f"Program is in use by switch {switch['name']}"
            )
    
    # Delete compiled files
    program = p4_programs[program_id]
    if program.get("json_file"):
        compiled_dir = os.path.dirname(program["json_file"])
        if os.path.exists(compiled_dir):
            shutil.rmtree(compiled_dir, ignore_errors=True)
    
    del p4_programs[program_id]
    
    # Publish event
    publish_event("deleted", {"program_id": program_id})
    
    return None


@app.post(f"{API_PREFIX}/switches", response_model=BMv2SwitchResponse, status_code=201)
async def create_switch(switch: BMv2SwitchCreate):
    """Create and start BMv2 switch"""
    try:
        logger.info(f"Creating BMv2 switch: {switch.name}")
        
        switch_id = f"{_safe_program_name(switch.name)}-{uuid.uuid4().hex[:10]}"

        if switch.program_id not in p4_programs:
            raise HTTPException(status_code=404, detail=f"Program {switch.program_id} not found")
        
        # Start BMv2 switch
        result = start_bmv2_switch(switch_id, {
            "program_id": switch.program_id,
            "device_id": switch.device_id,
            "thrift_port": switch.thrift_port,
            "log_level": switch.log_level,
            "pcap_dump": switch.pcap_dump
        })
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Store switch info
        switch_data = {
            "switch_id": switch_id,
            "name": switch.name,
            "program_id": switch.program_id,
            "device_id": switch.device_id,
            "thrift_port": switch.thrift_port,
            "status": "running",
            "created_at": datetime.utcnow(),
            "pid": result["pid"],
            "process": result.get("process")
        }
        
        bmv2_switches[switch_id] = switch_data
        
        # Publish event
        publish_event("switch_created", {
            "switch_id": switch_id,
            "name": switch.name
        })
        
        return BMv2SwitchResponse(**{k: v for k, v in switch_data.items() if k != "process"})
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{API_PREFIX}/switches", response_model=List[BMv2SwitchResponse])
async def list_switches():
    """List all BMv2 switches"""
    return [
        BMv2SwitchResponse(**{k: v for k, v in s.items() if k != "process"})
        for s in bmv2_switches.values()
    ]


@app.get(f"{API_PREFIX}/switches/{{switch_id}}", response_model=BMv2SwitchResponse)
async def get_switch(switch_id: str):
    """Get BMv2 switch details"""
    if switch_id not in bmv2_switches:
        raise HTTPException(status_code=404, detail=f"Switch {switch_id} not found")
    
    switch_data = bmv2_switches[switch_id]
    return BMv2SwitchResponse(**{k: v for k, v in switch_data.items() if k != "process"})


@app.delete(f"{API_PREFIX}/switches/{{switch_id}}", status_code=204)
async def delete_switch(switch_id: str):
    """Stop and delete BMv2 switch"""
    if switch_id not in bmv2_switches:
        raise HTTPException(status_code=404, detail=f"Switch {switch_id} not found")
    
    switch = bmv2_switches[switch_id]
    
    # Stop BMv2 process
    if switch.get("process"):
        try:
            switch["process"].terminate()
            switch["process"].wait(timeout=5)
            logger.info(f"Stopped BMv2 switch: {switch_id}")
        except Exception as e:
            logger.error(f"Error stopping switch: {e}")
    
    del bmv2_switches[switch_id]
    
    # Publish event
    publish_event("switch_deleted", {"switch_id": switch_id})
    
    return None


@app.post(f"{API_PREFIX}/switches/{{switch_id}}/table-entry")
async def add_table_entry(switch_id: str, entry: Dict[str, Any]):
    """Add table entry to BMv2 switch via runtime CLI"""
    if switch_id not in bmv2_switches:
        raise HTTPException(status_code=404, detail=f"Switch {switch_id} not found")
    
    switch = bmv2_switches[switch_id]
    
    try:
        # Use simple_switch_CLI to add table entry
        cmd = [
            "simple_switch_CLI",
            "--thrift-port", str(switch["thrift_port"]),
        ]
        
        # Format table entry command
        table_name = entry.get("table_name")
        action_name = entry.get("action_name")
        match_key = entry.get("match_key", [])
        action_params = entry.get("action_params", [])
        
        cli_cmd = f"table_add {table_name} {action_name} {' '.join(map(str, match_key))} => {' '.join(map(str, action_params))}"
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=cli_cmd + "\n", timeout=5)
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to add table entry: {stderr}")
        
        return {
            "success": True,
            "switch_id": switch_id,
            "table_name": table_name,
            "output": stdout
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timeout")
    except Exception as e:
        logger.error(f"Error adding table entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{API_PREFIX}/examples")
async def get_p4_examples():
    """Get example P4 programs"""
    return {
        "examples": [
            {
                "name": "basic_forwarding",
                "description": "Basic L2 forwarding",
                "source": """
/* Basic L2 Forwarding */
#include <core.p4>
#include <v1model.p4>

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

struct headers {
    ethernet_t ethernet;
}

struct metadata { }

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {
    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    
    action forward(bit<9> port) {
        standard_metadata.egress_spec = port;
    }
    
    action drop() {
        mark_to_drop(standard_metadata);
    }
    
    table dmac {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            forward;
            drop;
        }
        default_action = drop();
    }
    
    apply {
        dmac.apply();
    }
}

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
"""
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
