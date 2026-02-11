from __future__ import annotations

import time
import hashlib
import ipaddress
import subprocess
from typing import Dict, Tuple

from caduceus_sdk.node_base import Node


def _overlay_from_color(color: str) -> dict:
    c = (color or "").strip().upper()
    if c == "BLACK":
        return {"fill": "#000000", "text": "#ffffff", "border": "#111827", "badge": "BLACK"}
    if c in ("GRAY", "GREY"):
        return {"fill": "#9ca3af", "text": "#111827", "border": "#374151", "badge": "GRAY"}
    return {"fill": "#ffffff", "text": "#111827", "border": "#111827", "badge": "WHITE"}


def _stable_priority(seed: int, round_no: int, node_id: int) -> float:
    """
    Deterministic per-(seed, round, node) priority in [0, 1).
    This makes the MIS decision robust to lossy PRIORITY delivery (nodes can compute neighbor priorities).
    """
    msg = f"{int(seed)}:{int(round_no)}:{int(node_id)}".encode("utf-8", errors="ignore")
    digest = hashlib.blake2b(msg, digest_size=8).digest()
    v = int.from_bytes(digest, byteorder="big", signed=False)
    return float(v) / float(2**64)


class DistributedMISNode(Node):
    """
    Distributed MIS using a simple randomized priority rule (Luby-style), with 3 colors:
      WHITE = undecided
      BLACK = in MIS
      GRAY  = excluded (neighbor is BLACK)

    Neighbor discovery:
      Nodes do NOT use topology-provided neighbor lists.
      They broadcast HELLO and learn neighbors from incoming HELLO senders.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self.color = "WHITE"
        self.neighbors: Dict[int, Tuple[str, int]] = {}  # neighbor_id -> (ip, port)
        self.neighbor_colors: Dict[int, str] = {}
        self._local_ipv4_networks: list[ipaddress.IPv4Network] = []
        self._local_ipv4_cidrs: list[str] = []
        self._hello_acked_to: set[int] = set()
        self._decision_acked: set[str] = set()
        self._acks_by_msg_id: Dict[str, set[int]] = {}
        self._need_announce_gray: bool = False

    def _load_local_ipv4(self) -> None:
        if self._local_ipv4_networks:
            return
        try:
            out = subprocess.check_output(
                ["sh", "-lc", "ip -4 -o addr show up 2>/dev/null || true"],
                stderr=subprocess.DEVNULL,
                timeout=0.5,
            ).decode("utf-8", errors="replace")
        except Exception:
            out = ""
        nets: list[ipaddress.IPv4Network] = []
        cidrs: list[str] = []
        for line in out.splitlines():
            parts = line.strip().split()
            if "inet" not in parts:
                continue
            try:
                inet_idx = parts.index("inet")
                cidr = str(parts[inet_idx + 1] or "").strip()
            except Exception:
                continue
            if not cidr or "/" not in cidr:
                continue
            try:
                iface = ipaddress.ip_interface(cidr)
                if iface.ip.is_loopback:
                    continue
                nets.append(iface.network)
                cidrs.append(cidr)
            except Exception:
                continue
        # Prefer more specific networks first (helps pick /30 over /8).
        nets.sort(key=lambda n: int(getattr(n, "prefixlen", 0)), reverse=True)
        # Keep a short list in the HELLO payload (avoid bloating packets).
        cidrs = cidrs[:16]
        self._local_ipv4_networks = nets
        self._local_ipv4_cidrs = cidrs

    def _pick_reachable_ip(self, candidate_cidrs: list[str], fallback_ip: str) -> str:
        """
        Pick a neighbor IP that is reachable from this node based on L3 network matching.
        This avoids storing a sender's IP from the "wrong" interface in multi-homed topologies.
        """
        self._load_local_ipv4()

        best_ip = ""
        best_score = -1
        for cidr in candidate_cidrs[:32]:
            ip_s = str(cidr or "").split("/", 1)[0].strip()
            if not ip_s:
                continue
            try:
                ip = ipaddress.ip_address(ip_s)
                if ip.version != 4:
                    continue
            except Exception:
                continue
            score = -1
            for net in self._local_ipv4_networks:
                try:
                    if ip in net:
                        score = max(score, int(net.prefixlen))
                        break
                except Exception:
                    continue
            if score > best_score:
                best_score = score
                best_ip = ip_s

        return best_ip or str(fallback_ip or "").strip()

    def _set_color(self, color: str) -> None:
        c = (color or "").strip().upper()
        if c not in ("WHITE", "GRAY", "BLACK"):
            return
        if self.color == c:
            return
        self.color = c
        overlay = _overlay_from_color(self.color)
        self.write_state(
            {
                "ts": time.time(),
                "node": {"algo_id": self.id, "uuid": self.uuid, "name": self.name, "type": self.type},
                "color": self.color,
                "overlay": overlay,
            }
        )
        self.emit({"type": "overlay", "color": self.color, "overlay": overlay})

    def _drain_mailbox(self) -> list[dict]:
        out = []
        while True:
            msg = self.receiveMessage()
            if not msg:
                break
            out.append(msg)
        return out

    def _handle_control_msgs(self, msg: dict) -> None:
        typ = str(msg.get("type") or "").upper()
        sender = msg.get("sender")
        try:
            sid = int(sender)
        except Exception:
            sid = None

        if typ == "ACK" and sid is not None:
            msg_id = str(msg.get("msg_id") or "")
            if msg_id:
                self._acks_by_msg_id.setdefault(msg_id, set()).add(int(sid))
            return

        if typ == "DECISION" and sid is not None:
            # ACK decisions (deduplicated by msg_id) so the sender can reliably learn that we received it.
            msg_id = str(msg.get("msg_id") or "")
            if msg_id and msg_id not in self._decision_acked:
                self._decision_acked.add(msg_id)
                src_ip = str(msg.get("__src_ip") or "").strip()
                try:
                    port = int(msg.get("__src_port") or self.ctx.listen_port)
                except Exception:
                    port = int(self.ctx.listen_port)
                # ACK to the source address and, if known, to the stored neighbor endpoint as a fallback.
                if src_ip:
                    self.sendToAddr(src_ip, port, {"type": "ACK", "msg_id": msg_id, "ack_type": "DECISION"})
                try:
                    nb = self.neighbors.get(int(sid))
                    if nb and nb[0] and nb[0] != src_ip:
                        self.sendToAddr(nb[0], nb[1], {"type": "ACK", "msg_id": msg_id, "ack_type": "DECISION"})
                except Exception:
                    pass

            col = str(msg.get("color") or "").upper()
            if col in ("WHITE", "GRAY", "BLACK"):
                self.neighbor_colors[sid] = col
                if col == "BLACK" and self.color == "WHITE":
                    self._set_color("GRAY")
                    self._need_announce_gray = True

    def discover_neighbors(self) -> None:
        discovery_seconds = float(self.params.get("discovery_seconds", 2.0))
        hello_interval = float(self.params.get("hello_interval", 0.5))
        quiet_break_seconds = float(self.params.get("discovery_quiet_seconds", 0.6))
        start = time.time()
        next_hello = 0.0
        last_new_neighbor = 0.0
        self._load_local_ipv4()

        while time.time() - start < discovery_seconds:
            if last_new_neighbor and (time.time() - last_new_neighbor) >= quiet_break_seconds:
                break
            now = time.time()
            if now >= next_hello:
                # Broadcast HELLO; receivers will ACK back via unicast so discovery becomes symmetric
                # even when broadcast delivery is lossy.
                self.broadcast({"type": "HELLO", "cidrs": list(self._local_ipv4_cidrs)})
                next_hello = now + hello_interval

            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                typ = str(msg.get("type") or "").upper()
                if typ in ("HELLO", "HELLO_ACK"):
                    try:
                        sid = int(msg.get("sender"))
                    except Exception:
                        continue
                    if sid == self.id:
                        continue
                    src_ip = str(msg.get("__src_ip") or "").strip()
                    port = int(msg.get("__src_port") or self.ctx.listen_port)
                    candidate_cidrs = msg.get("cidrs")
                    if not isinstance(candidate_cidrs, list):
                        candidate_cidrs = []
                    ip = self._pick_reachable_ip([str(x) for x in candidate_cidrs if x], fallback_ip=src_ip)
                    if ip:
                        is_new = sid not in self.neighbors
                        self.neighbors[sid] = (ip, port)
                        self.neighbor_colors.setdefault(sid, "WHITE")
                        if typ == "HELLO":
                            # Unicast ACK once so the sender learns us even if it missed our broadcast.
                            if sid not in self._hello_acked_to:
                                self._hello_acked_to.add(int(sid))
                                self.sendToAddr(ip, port, {"type": "HELLO_ACK", "cidrs": list(self._local_ipv4_cidrs)})
                        if is_new:
                            last_new_neighbor = time.time()
                else:
                    self._handle_control_msgs(msg)

        self.emit({"type": "neighbors", "count": len(self.neighbors), "neighbors": sorted(self.neighbors.keys())})

    def _send_to_neighbors(self, payload: dict) -> None:
        for _sid, (ip, port) in list(self.neighbors.items()):
            self.sendToAddr(ip, port, payload)

    def _announce_decision(self, *, color: str, round_no: int, priority: float) -> None:
        c = str(color or "").strip().upper()
        if c not in ("BLACK", "GRAY"):
            return
        max_sends = int(self.params.get("decision_max_sends", 3))
        max_sends = max(1, min(max_sends, 10))
        ack_wait = float(self.params.get("decision_ack_wait", 0.4))
        send_interval = float(self.params.get("decision_interval", 0.25))
        reliable = bool(self.params.get("decision_reliable", True)) and c == "BLACK"

        msg_id = f"dec:{int(round_no)}:{int(self.id)}:{int(time.time()*1000)}:{c}"
        pending = set(self.neighbors.keys()) if reliable else set()

        attempts = max_sends if reliable else 1
        for attempt in range(attempts):
            targets = list(pending) if pending else list(self.neighbors.keys())
            for sid in targets:
                ip, port = self.neighbors.get(int(sid), ("", self.ctx.listen_port))
                if not ip:
                    continue
                self.sendToAddr(ip, int(port), {"type": "DECISION", "color": c, "round": int(round_no), "priority": float(priority), "msg_id": msg_id})

            if not pending:
                break

            start = time.time()
            while pending and (time.time() - start) < ack_wait:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    self._handle_control_msgs(msg)
                pending -= set(self._acks_by_msg_id.get(msg_id, set()))

            if pending and attempt < attempts - 1:
                yield self.mailbox.get(send_interval)

    def run(self):
        self._set_color("WHITE")

        # 1) Discover neighbors via HELLO broadcast
        yield from self.discover_neighbors()

        if not self.neighbors:
            # Isolated node => always in MIS
            self._set_color("BLACK")
            self.emit({"type": "done", "reason": "isolated"})
            return

        # 2) MIS rounds (low-traffic): no PRIORITY messages, only state-change announcements.
        max_rounds = int(self.params.get("max_rounds", 60))
        round_sleep = float(self.params.get("round_sleep", 0.25))
        priority_seed = int(self.params.get("priority_seed", 1))
        announce_gray = bool(self.params.get("announce_gray", True))

        for r in range(1, max_rounds + 1):
            # Process any buffered messages first.
            for msg in self._drain_mailbox():
                self._handle_control_msgs(msg)

            if self.color != "WHITE":
                break

            # If we saw a BLACK neighbor, we are GRAY (and optionally announce to speed convergence).
            if any(c == "BLACK" for c in self.neighbor_colors.values()):
                self._set_color("GRAY")
                if announce_gray:
                    yield from self._announce_decision(color="GRAY", round_no=r, priority=0.0)
                break

            priority = _stable_priority(priority_seed, r, self.id)
            best = (priority, -self.id)
            for sid in self.neighbors.keys():
                if self.neighbor_colors.get(sid, "WHITE") != "WHITE":
                    continue
                cand = (_stable_priority(priority_seed, r, sid), -sid)
                if cand > best:
                    best = cand

            if best == (priority, -self.id):
                self._set_color("BLACK")
                yield from self._announce_decision(color="BLACK", round_no=r, priority=priority)
                break

            # Wait a bit for decisions from neighbors.
            yield self.mailbox.get(round_sleep)
            for msg in self._drain_mailbox():
                self._handle_control_msgs(msg)
            if self._need_announce_gray and self.color == "GRAY" and announce_gray:
                self._need_announce_gray = False
                yield from self._announce_decision(color="GRAY", round_no=r, priority=0.0)
                break

        if self.color == "WHITE":
            # Termination fallback: if no BLACK neighbor observed, take BLACK (with reliable announce).
            if any(c == "BLACK" for c in self.neighbor_colors.values()):
                self._set_color("GRAY")
                if announce_gray:
                    yield from self._announce_decision(color="GRAY", round_no=max_rounds + 1, priority=0.0)
            else:
                self._set_color("BLACK")
                yield from self._announce_decision(color="BLACK", round_no=max_rounds + 1, priority=1.0)

        # Emit final state summary
        self.emit(
            {
                "type": "done",
                "color": self.color,
                "neighbors": sorted(self.neighbors.keys()),
                "neighbor_colors": {str(k): v for k, v in self.neighbor_colors.items()},
            }
        )
