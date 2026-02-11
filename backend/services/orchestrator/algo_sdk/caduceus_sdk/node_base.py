from __future__ import annotations

from typing import Any, Optional

from .protocol import Mailbox


class GraphView:
    def __init__(self, nodes: dict[int, dict[str, Any]]) -> None:
        self.nodes = _NodeAttrView(nodes)


class _NodeAttrView:
    def __init__(self, nodes: dict[int, dict[str, Any]]) -> None:
        self._nodes = nodes

    def __getitem__(self, key: Any) -> dict[str, Any]:
        try:
            kid = int(key)
        except Exception:
            return {}
        return self._nodes.get(kid, {})


class Node:
    """
    Compatibility base class for generator-style distributed algorithms.

    Algorithms can subclass this Node and implement `run()` either as:
    - a generator yielding `self.mailbox.get(timeout_seconds)`, or
    - a normal function (blocking is OK).
    """

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self.id: int = int(ctx.node["algo_id"])
        self.uuid: str = str(ctx.node["uuid"])
        self.name: str = str(ctx.node.get("name") or self.uuid)
        self.type: str = str(ctx.node.get("type") or "")
        self.params: dict[str, Any] = dict(ctx.params or {})
        self.neighbors: dict[int, dict[str, Any]] = dict(ctx.neighbors or {})
        self.mailbox = Mailbox()
        self.G = GraphView(ctx.graph_nodes or {})

    def sendMessageTo(self, neighbor_id: Any, msgdict: dict[str, Any]) -> None:
        try:
            nid = int(neighbor_id)
        except Exception:
            return
        self.ctx.send(nid, msgdict)

    def receiveMessage(self) -> Optional[dict[str, Any]]:
        return self.mailbox.pop()

    def emit(self, event: dict[str, Any]) -> None:
        self.ctx.emit(event)

    def write_state(self, payload: dict[str, Any]) -> None:
        self.ctx.write_state(payload)

    def sendToAddr(self, ip: str, port: int, msgdict: dict[str, Any]) -> None:
        self.ctx.send_addr(ip, port, msgdict)

    def broadcast(self, msgdict: dict[str, Any], port: Optional[int] = None) -> None:
        self.ctx.broadcast(msgdict, port=port)
