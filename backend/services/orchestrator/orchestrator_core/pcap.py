from __future__ import annotations

import asyncio
import json
import os
import shlex
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from orchestrator_core.schemas import PcapStartRequest, PcapStopRequest


@dataclass(slots=True)
class PcapService:
    require_grpc_client: Any
    resolve_runtime_name: Any
    iso_now: Any
    storage_root: str = "/var/lib/caduceus/pcap"
    lock: threading.Lock = field(default_factory=threading.Lock)

    def ensure_root(self) -> str:
        root = (self.storage_root or "/var/lib/caduceus/pcap").strip() or "/var/lib/caduceus/pcap"
        try:
            os.makedirs(root, exist_ok=True)
        except Exception:
            pass
        return root

    def _paths(self, topology_id: str, capture_id: str) -> Tuple[str, str]:
        tid = str(topology_id or "").strip()
        cid = str(capture_id or "").strip()
        if not tid or not cid:
            raise ValueError("topology_id and capture_id are required")
        topo_dir = os.path.join(self.ensure_root(), tid)
        return (
            os.path.join(topo_dir, f"{cid}.pcap"),
            os.path.join(topo_dir, f"{cid}.json"),
        )

    def _write_json_atomic(self, path: str, payload: Dict[str, Any]) -> None:
        tmp = f"{path}.tmp"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        os.replace(tmp, path)

    def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None

    def router(self) -> APIRouter:
        router = APIRouter()

        @router.post("/api/pcap/start")
        async def start_pcap_capture(request: PcapStartRequest):
            topology_id = (request.topology_id or "").strip()
            if not topology_id:
                raise HTTPException(status_code=400, detail="topology_id is required")
            device = (request.device or "").strip()
            if not device:
                raise HTTPException(status_code=400, detail="device is required")

            capture_id = str(uuid.uuid4())
            try:
                pcap_path, meta_path = self._paths(topology_id, capture_id)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            topo_dir = os.path.dirname(pcap_path)
            os.makedirs(topo_dir, exist_ok=True)

            iface = (request.interface or "").strip() or "any"
            snaplen = int(max(64, min(65535, int(request.snaplen or 96))))
            duration = request.duration_seconds
            if duration is not None:
                duration = int(max(1, min(24 * 60 * 60, int(duration))))
            bpf = (request.bpf or "").strip() or None

            tcpdump_parts = [
                "tcpdump",
                "-n",
                "-U",
                "-s",
                str(snaplen),
                "-i",
                iface,
                "-w",
                pcap_path,
            ]
            if bpf:
                tcpdump_parts.append(bpf)

            tcpdump_cmd = " ".join(shlex.quote(p) for p in tcpdump_parts)
            if duration is not None:
                tcpdump_cmd = f"timeout {int(duration)}s {tcpdump_cmd}"

            # Run in background and return PID (best-effort).
            start_cmd = (
                f"mkdir -p {shlex.quote(topo_dir)}; "
                f"nohup {tcpdump_cmd} >/dev/null 2>&1 & echo $!"
            )

            grpc_client = await asyncio.to_thread(
                self.require_grpc_client,
                topology_id=topology_id,
                emulation_id=request.emulation_id,
            )
            runtime = self.resolve_runtime_name(None, device, grpc_client)
            result = await asyncio.to_thread(grpc_client.execute_command, runtime, start_cmd)
            if not result.get("success"):
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Failed to start tcpdump: "
                        f"{result.get('stderr') or result.get('stdout') or 'unknown error'}"
                    ),
                )

            pid: Optional[int] = None
            try:
                pid = int(str(result.get("stdout") or "").strip().splitlines()[-1])
            except Exception:
                pid = None

            meta: Dict[str, Any] = {
                "capture_id": capture_id,
                "topology_id": topology_id,
                "emulation_id": (request.emulation_id or "").strip() or None,
                "device": device,
                "runtime": runtime,
                "interface": iface,
                "bpf": bpf,
                "duration_seconds": duration,
                "snaplen": snaplen,
                "pcap_path": pcap_path,
                "meta_path": meta_path,
                "pid": pid,
                "status": "running",
                "started_at": self.iso_now(),
            }

            with self.lock:
                self._write_json_atomic(meta_path, meta)

            return {"ok": True, "capture": meta}

        @router.post("/api/pcap/stop")
        async def stop_pcap_capture(request: PcapStopRequest):
            topology_id = (request.topology_id or "").strip()
            capture_id = (request.capture_id or "").strip()
            if not topology_id or not capture_id:
                raise HTTPException(status_code=400, detail="topology_id and capture_id are required")

            try:
                pcap_path, meta_path = self._paths(topology_id, capture_id)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            meta = self._read_json(meta_path) or {}
            runtime = (meta.get("runtime") or "").strip()
            pid = meta.get("pid")
            try:
                pid = int(pid) if pid is not None else None
            except Exception:
                pid = None

            if not runtime:
                raise HTTPException(status_code=404, detail="Capture metadata missing runtime; cannot stop")

            kill_cmd = "true"
            if pid:
                kill_cmd = f"kill {int(pid)} >/dev/null 2>&1 || true"
            # Unique file path is a good fallback to target the right tcpdump process.
            kill_cmd = f"{kill_cmd}; pkill -f {shlex.quote(pcap_path)} >/dev/null 2>&1 || true; echo stopped"

            grpc_client = await asyncio.to_thread(
                self.require_grpc_client,
                topology_id=topology_id,
                emulation_id=meta.get("emulation_id"),
            )
            result = await asyncio.to_thread(grpc_client.execute_command, runtime, kill_cmd)

            meta["status"] = "stopped"
            meta["stopped_at"] = self.iso_now()
            meta["stop_result"] = {k: result.get(k) for k in ("success", "exit_code", "stderr") if k in result}

            with self.lock:
                self._write_json_atomic(meta_path, meta)

            return {"ok": True, "capture": meta}

        @router.get("/api/pcap/captures")
        async def list_pcap_captures(topology_id: Optional[str] = None):
            root = self.ensure_root()
            captures: List[Dict[str, Any]] = []

            def _scan_dir(tid: str) -> None:
                topo_dir = os.path.join(root, tid)
                if not os.path.isdir(topo_dir):
                    return
                for name in os.listdir(topo_dir):
                    if not name.endswith(".json"):
                        continue
                    meta = self._read_json(os.path.join(topo_dir, name))
                    if not meta:
                        continue
                    captures.append(meta)

            if topology_id:
                _scan_dir(str(topology_id).strip())
            else:
                try:
                    for tid in os.listdir(root):
                        if os.path.isdir(os.path.join(root, tid)):
                            _scan_dir(tid)
                except Exception:
                    pass

            captures.sort(key=lambda c: str(c.get("started_at") or ""), reverse=True)
            return {"captures": captures}

        @router.get("/api/pcap/captures/{topology_id}/{capture_id}/download")
        async def download_pcap(topology_id: str, capture_id: str):
            topology_id = (topology_id or "").strip()
            capture_id = (capture_id or "").strip()
            if not topology_id or not capture_id:
                raise HTTPException(status_code=400, detail="topology_id and capture_id are required")

            try:
                pcap_path, _ = self._paths(topology_id, capture_id)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            if not os.path.isfile(pcap_path):
                raise HTTPException(status_code=404, detail="PCAP file not found")

            filename = f"{topology_id[:8]}-{capture_id}.pcap"
            return FileResponse(pcap_path, filename=filename, media_type="application/vnd.tcpdump.pcap")

        return router

