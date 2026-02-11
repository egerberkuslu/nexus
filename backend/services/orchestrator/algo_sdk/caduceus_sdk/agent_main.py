from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from typing import Any, Optional, Callable

from .node_base import Node as BaseNode
from .protocol import WaitRequest
from .state import append_jsonl, write_json_atomic
from .transport import NeighborEndpoint, TcpTransport, UdpTransport


def _load_symbol(spec: str) -> Any:
    """
    spec: "module.sub:Symbol"
    """
    if ":" not in spec:
        raise ValueError("Invalid symbol spec (expected module:Symbol)")
    mod_name, sym_name = spec.split(":", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, sym_name)


def _default_overlay_from_color(color: str) -> Optional[dict[str, Any]]:
    c = (color or "").strip().upper()
    if c == "BLACK":
        return {"fill": "#000000", "text": "#ffffff", "border": "#111827", "badge": "BLACK"}
    if c == "GRAY" or c == "GREY":
        return {"fill": "#9ca3af", "text": "#111827", "border": "#374151", "badge": "GRAY"}
    if c == "WHITE":
        return {"fill": "#ffffff", "text": "#111827", "border": "#111827", "badge": "WHITE"}
    return None


class AgentContext:
    def __init__(
        self,
        run_id: str,
        node: dict[str, Any],
        neighbors: dict[int, dict[str, Any]],
        params: dict[str, Any],
        graph_nodes: dict[int, dict[str, Any]],
        listen_port: int,
        transport: str,
        ip_family: str,
        events_path: str,
        state_path: str,
    ) -> None:
        self.run_id = run_id
        self.node = node
        self.neighbors = neighbors
        self.params = params
        self.graph_nodes = graph_nodes
        self.listen_port = int(listen_port)
        self.transport = str(transport or "udp").strip().lower() or "udp"
        self.ip_family = str(ip_family or "auto").strip().lower() or "auto"
        self.events_path = events_path
        self.state_path = state_path
        self._trace_messages = self._parse_bool(params.get("trace_messages", False))
        self._trace_payload = self._parse_bool(params.get("trace_payload", False))
        self._stats = {
            "sent_msgs": 0,
            "sent_bytes": 0,
            "recv_msgs": 0,
            "recv_bytes": 0,
            "broadcast_msgs": 0,
            "broadcast_bytes": 0,
        }

        if self.transport == "tcp":
            self._transport = TcpTransport(listen_port=self.listen_port, ip_family=self.ip_family)
        else:
            self._transport = UdpTransport(listen_port=self.listen_port, ip_family=self.ip_family)
        self._neighbor_endpoints: dict[int, NeighborEndpoint] = {}
        for nid, info in neighbors.items():
            ip = str(info.get("ip") or "")
            port = int(info.get("port") or self.listen_port)
            if ip:
                self._neighbor_endpoints[int(nid)] = NeighborEndpoint(algo_id=int(nid), ip=ip, port=port)

    @staticmethod
    def _parse_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v or "").strip().lower()
        return s in ("1", "true", "yes", "y", "on", "enabled")

    def _emit_trace(self, event: dict[str, Any]) -> None:
        if not self._trace_messages:
            return
        try:
            e = dict(event)
            e.setdefault("type", "net")
            self.emit(e)
        except Exception:
            return

    def send(self, neighbor_id: int, msg: dict[str, Any]) -> None:
        if not isinstance(msg, dict):
            return
        payload = dict(msg)
        payload.setdefault("sender", int(self.node["algo_id"]))
        endpoint = self._neighbor_endpoints.get(int(neighbor_id))
        if not endpoint:
            return
        try:
            raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self._stats["sent_msgs"] += 1
            self._stats["sent_bytes"] += int(len(raw))
            if self._trace_messages:
                ev: dict[str, Any] = {
                    "type": "net_tx",
                    "to": int(neighbor_id),
                    "dst_ip": str(endpoint.ip),
                    "dst_port": int(endpoint.port),
                    "msg_type": payload.get("type"),
                    "bytes": int(len(raw)),
                }
                if self._trace_payload:
                    ev["payload"] = payload
                self._emit_trace(ev)
        except Exception:
            pass
        self._transport.send(endpoint, payload)

    def send_addr(self, ip: str, port: int, msg: dict[str, Any]) -> None:
        if not isinstance(msg, dict):
            return
        ip_s = str(ip or "").strip()
        if not ip_s:
            return
        payload = dict(msg)
        payload.setdefault("sender", int(self.node["algo_id"]))
        try:
            endpoint = NeighborEndpoint(algo_id=-1, ip=ip_s, port=int(port))
            try:
                raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                self._stats["sent_msgs"] += 1
                self._stats["sent_bytes"] += int(len(raw))
                if self._trace_messages:
                    ev: dict[str, Any] = {
                        "type": "net_tx",
                        "to": None,
                        "dst_ip": str(endpoint.ip),
                        "dst_port": int(endpoint.port),
                        "msg_type": payload.get("type"),
                        "bytes": int(len(raw)),
                        "addr_mode": True,
                    }
                    if self._trace_payload:
                        ev["payload"] = payload
                    self._emit_trace(ev)
            except Exception:
                pass
            self._transport.send(endpoint, payload)
        except Exception:
            return

    def broadcast(self, msg: dict[str, Any], port: Optional[int] = None) -> None:
        if not isinstance(msg, dict):
            return
        payload = dict(msg)
        payload.setdefault("sender", int(self.node["algo_id"]))
        try:
            raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self._stats["broadcast_msgs"] += 1
            self._stats["broadcast_bytes"] += int(len(raw))
            if self._trace_messages:
                ev: dict[str, Any] = {
                    "type": "net_bcast",
                    "dst_port": int(port or self.listen_port),
                    "msg_type": payload.get("type"),
                    "bytes": int(len(raw)),
                }
                if self._trace_payload:
                    ev["payload"] = payload
                self._emit_trace(ev)
        except Exception:
            pass
        bcast = getattr(self._transport, "broadcast", None)
        if callable(bcast):
            try:
                bcast(payload, port=port)
            except Exception:
                pass

    def recv(self, timeout_seconds: float) -> Optional[dict[str, Any]]:
        msg = self._transport.recv(timeout_seconds)
        if not msg:
            return None
        try:
            self._stats["recv_msgs"] += 1
            raw_len = msg.get("__raw_len")
            if raw_len is not None:
                self._stats["recv_bytes"] += int(raw_len)
            else:
                self._stats["recv_bytes"] += int(len(json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")))
            if self._trace_messages:
                raw_sz = int(raw_len) if raw_len is not None else None
                ev: dict[str, Any] = {
                    "type": "net_rx",
                    "from": msg.get("sender"),
                    "src_ip": msg.get("__src_ip"),
                    "src_port": msg.get("__src_port"),
                    "msg_type": msg.get("type"),
                    "bytes": raw_sz,
                }
                if self._trace_payload:
                    # keep payload small-ish; full msg is still useful for debugging but can be large
                    ev["payload"] = {k: v for k, v in msg.items() if not str(k).startswith("__")}
                self._emit_trace(ev)
        except Exception:
            pass
        return msg

    def emit(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        e = dict(event)
        e.setdefault("ts", time.time())
        e.setdefault("node", int(self.node["algo_id"]))
        append_jsonl(self.events_path, e)

    def write_state(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, payload)

    def stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def close(self) -> None:
        self._transport.close()


def _run_generator(node: BaseNode, ctx: AgentContext) -> None:
    gen = node.run()
    if gen is None:
        return
    if not hasattr(gen, "__iter__"):
        return

    while True:
        try:
            yielded = next(gen)
        except StopIteration:
            return
        except Exception as exc:
            ctx.emit({"type": "error", "error": str(exc)})
            return

        if isinstance(yielded, WaitRequest):
            msg = ctx.recv(yielded.timeout_seconds)
            if msg:
                node.mailbox.put(msg)
            continue

        # If code yields something else, just keep stepping.
        continue


def run_agent(config_path: str, manifest_path: str) -> None:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    run_id = str(cfg.get("run_id") or "")
    node = cfg.get("node") or {}
    neighbors = cfg.get("neighbors") or {}
    params = cfg.get("params") or {}
    graph_nodes = cfg.get("graph_nodes") or {}
    listen_port = int(cfg.get("listen_port") or manifest.get("listen_port") or 50000)
    transport = str(cfg.get("transport") or manifest.get("transport") or "udp").strip().lower() or "udp"
    ip_family = str(cfg.get("ip_family") or manifest.get("ip_family") or "auto").strip().lower() or "auto"

    algo_id = int(node.get("algo_id"))
    base_dir = str(cfg.get("run_dir") or os.path.dirname(os.path.dirname(config_path)))
    events_path = os.path.join(base_dir, "events", f"events_{algo_id}.jsonl")
    state_path = os.path.join(base_dir, "states", f"state_{algo_id}.json")

    ctx = AgentContext(
        run_id=run_id,
        node=node,
        neighbors={int(k): v for k, v in neighbors.items()},
        params=params,
        graph_nodes={int(k): v for k, v in graph_nodes.items()},
        listen_port=listen_port,
        transport=transport,
        ip_family=ip_family,
        events_path=events_path,
        state_path=state_path,
    )

    ctx.emit(
        {
            "type": "started",
            "manifest": {"name": manifest.get("name"), "version": manifest.get("version")},
            "transport": transport,
            "ip_family": ip_family,
            "listen_port": listen_port,
        }
    )

    try:
        entry = manifest.get("node_class") or manifest.get("entrypoint")
        main_fn = manifest.get("main")

        if entry:
            klass = _load_symbol(str(entry))
            node_obj = klass(ctx)  # must be compatible with BaseNode signature
            if not isinstance(node_obj, BaseNode):
                # Allow non-subclass nodes if they implement required fields.
                # Wrap by injecting mailbox/send/receive methods not supported.
                raise TypeError("entrypoint must subclass caduceus_sdk.node_base.Node")
            _run_generator(node_obj, ctx)

            # Best-effort: infer overlay from `color` attribute if present.
            color = getattr(node_obj, "color", None)
            overlay = _default_overlay_from_color(str(color)) if color else None
            final_state = {
                "ts": time.time(),
                "run_id": run_id,
                "node": node,
                "done": True,
                "color": color,
                "overlay": overlay,
                "stats": ctx.stats(),
            }
            ctx.write_state(final_state)
            if overlay:
                ctx.emit({"type": "overlay", "overlay": overlay, "color": color})
            ctx.emit({"type": "done", "stats": ctx.stats(), "color": color})
            return

        if main_fn:
            fn: Callable[[AgentContext], Any] = _load_symbol(str(main_fn))
            fn(ctx)
            ctx.write_state({"ts": time.time(), "run_id": run_id, "node": node, "done": True, "stats": ctx.stats()})
            ctx.emit({"type": "done", "stats": ctx.stats()})
            return

        raise ValueError("manifest must include 'node_class' (or 'entrypoint') or 'main'")
    except Exception as exc:
        # Surface import/runtime failures that happen outside the node generator loop.
        try:
            ctx.emit({"type": "error", "error": str(exc)})
        except Exception:
            pass
        try:
            ctx.write_state({"ts": time.time(), "run_id": run_id, "node": node, "done": True, "error": str(exc), "stats": ctx.stats()})
        except Exception:
            pass
        return
    finally:
        ctx.close()


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    run_agent(args.config, args.manifest)


if __name__ == "__main__":
    _main()
