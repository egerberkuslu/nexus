from __future__ import annotations

import json
import select
import socket
import subprocess
import ipaddress
from dataclasses import dataclass
from typing import Any, Optional, Set


@dataclass(frozen=True)
class NeighborEndpoint:
    algo_id: int
    ip: str
    port: int


class UdpTransport:
    IPV4_DISCOVERY_MULTICAST = "239.255.0.1"

    def __init__(self, listen_port: int, ip_family: str = "auto") -> None:
        self.listen_port = int(listen_port)
        self.ip_family = (ip_family or "auto").strip().lower()
        self.sock4: Optional[socket.socket] = None
        self.sock6: Optional[socket.socket] = None
        self._mcast_if4: list[str] = []

        if self.ip_family in ("auto", "ipv4", "inet", "v4"):
            try:
                s4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s4.bind(("0.0.0.0", self.listen_port))
                self.sock4 = s4
            except Exception:
                self.sock4 = None

        # Join IPv4 discovery multicast group on all up interfaces.
        # This is much more reliable than directed broadcast on point-to-point (/30) Mininet links.
        if self.sock4:
            try:
                group = socket.inet_aton(self.IPV4_DISCOVERY_MULTICAST)
            except Exception:
                group = None
            if group:
                try:
                    out = subprocess.check_output(
                        ["sh", "-lc", "ip -4 -o addr show up 2>/dev/null || true"],
                        stderr=subprocess.DEVNULL,
                        timeout=0.5,
                    ).decode("utf-8", errors="replace")
                except Exception:
                    out = ""
                for line in out.splitlines():
                    parts = line.strip().split()
                    if "inet" not in parts:
                        continue
                    try:
                        inet_idx = parts.index("inet")
                        cidr = str(parts[inet_idx + 1] or "").strip()
                        ip = (cidr.split("/", 1)[0] if cidr else "").strip()
                        if not ip or ip.startswith("127."):
                            continue
                        self._mcast_if4.append(ip)
                    except Exception:
                        continue

                try:
                    self.sock4.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                except Exception:
                    pass
                try:
                    self.sock4.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
                except Exception:
                    pass
                for ip in self._mcast_if4[:64]:
                    try:
                        mreq = group + socket.inet_aton(ip)
                        self.sock4.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                    except Exception:
                        continue

        if self.ip_family in ("auto", "ipv6", "inet6", "v6"):
            try:
                s6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                except Exception:
                    pass
                s6.bind(("::", self.listen_port))
                self.sock6 = s6
            except Exception:
                self.sock6 = None

        if not self.sock4 and not self.sock6:
            raise RuntimeError("Failed to bind UDP sockets")

    def send(self, endpoint: NeighborEndpoint, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            if ":" in str(endpoint.ip) and self.sock6:
                self.sock6.sendto(payload, (endpoint.ip, int(endpoint.port), 0, 0))
                return
            if self.sock4:
                self.sock4.sendto(payload, (endpoint.ip, int(endpoint.port)))
                return
            if self.sock6:
                self.sock6.sendto(payload, (endpoint.ip, int(endpoint.port), 0, 0))
        except Exception:
            return

    def broadcast(self, message: dict[str, Any], port: Optional[int] = None) -> None:
        """
        Best-effort L2 broadcast/multicast discovery.

        IPv4: interface broadcast addresses (fallback: 255.255.255.255)
        IPv4 multicast: 239.255.0.1 on all interfaces (preferred for Mininet point-to-point links)
        IPv6: ff02::1 (link-local all-nodes multicast, joined best-effort)
        """
        dst_port = int(port or self.listen_port)
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        if self.sock4:
            # Prefer IPv4 multicast (works on point-to-point veth links where directed broadcast is flaky).
            if self._mcast_if4:
                for ip in self._mcast_if4[:64]:
                    try:
                        self.sock4.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                        self.sock4.sendto(payload, (self.IPV4_DISCOVERY_MULTICAST, dst_port))
                    except Exception:
                        continue

            try:
                self.sock4.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                targets: Set[str] = set()
                # Prefer directed broadcast addresses per interface (more reliable inside mininet namespaces).
                try:
                    out = subprocess.check_output(
                        ["sh", "-lc", "ip -4 -o addr show up 2>/dev/null || true"],
                        stderr=subprocess.DEVNULL,
                        timeout=0.5,
                    ).decode("utf-8", errors="replace")
                    for line in out.splitlines():
                        line = line.strip()
                        # Example: "2: eth0 inet 10.0.0.1/8 brd 10.255.255.255 scope global eth0"
                        parts = line.split()
                        if "inet" not in parts:
                            continue
                        try:
                            # Compute directed broadcast from inet/prefix even if `ip` output omits the `brd` token.
                            inet_idx = parts.index("inet")
                            cidr = str(parts[inet_idx + 1] or "").strip()
                            if cidr and "/" in cidr:
                                try:
                                    iface = ipaddress.ip_interface(cidr)
                                    bcast_ip = str(getattr(iface.network, "broadcast_address", "") or "")
                                    if bcast_ip and bcast_ip.count(".") == 3 and bcast_ip != "0.0.0.0":
                                        targets.add(bcast_ip)
                                except Exception:
                                    pass

                            # Directed broadcast, if present.
                            if "brd" in parts:
                                brd_idx = parts.index("brd")
                                brd_ip = parts[brd_idx + 1]
                                if brd_ip and brd_ip.count(".") == 3 and brd_ip != "0.0.0.0":
                                    targets.add(brd_ip)

                            # Point-to-point peer, if present (common in direct host-host links).
                            if "peer" in parts:
                                peer_idx = parts.index("peer")
                                peer_raw = parts[peer_idx + 1]
                                peer_ip = (peer_raw or "").split("/", 1)[0].strip()
                                if peer_ip and peer_ip.count(".") == 3 and peer_ip != "0.0.0.0":
                                    targets.add(peer_ip)
                        except Exception:
                            continue
                except Exception:
                    targets = set()

                # Always include limited broadcast; for some point-to-point links `ip` reports `brd 0.0.0.0`
                # and directed broadcast is unavailable.
                targets.add("255.255.255.255")

                for ip in sorted(targets):
                    try:
                        self.sock4.sendto(payload, (ip, dst_port))
                    except Exception:
                        continue
            except Exception:
                pass

        if self.sock6:
            # Join ff02::1 on all interfaces best-effort, then send with scope id.
            try:
                maddr = socket.inet_pton(socket.AF_INET6, "ff02::1")
            except Exception:
                maddr = None
            if maddr:
                try:
                    for if_index, _if_name in socket.if_nameindex():
                        try:
                            mreq = maddr + int(if_index).to_bytes(4, byteorder="little", signed=False)
                            self.sock6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
                        except Exception:
                            continue
                except Exception:
                    pass
                try:
                    for if_index, _if_name in socket.if_nameindex():
                        try:
                            self.sock6.sendto(payload, ("ff02::1", dst_port, 0, int(if_index)))
                        except Exception:
                            continue
                except Exception:
                    pass

    def recv(self, timeout_seconds: float) -> Optional[dict[str, Any]]:
        socks = [s for s in (self.sock4, self.sock6) if s is not None]
        if not socks:
            return None
        try:
            r, _w, _x = select.select(socks, [], [], float(timeout_seconds))
        except Exception:
            return None
        if not r:
            return None
        try:
            data, addr = r[0].recvfrom(65535)
        except Exception:
            return None
        try:
            parsed = json.loads(data.decode("utf-8"))
            if not isinstance(parsed, dict):
                return None
            parsed.setdefault("__raw_len", int(len(data)))
            # Attach source metadata for discovery algorithms.
            try:
                if isinstance(addr, tuple) and len(addr) >= 2:
                    parsed.setdefault("__src_ip", str(addr[0]))
                    parsed.setdefault("__src_port", int(addr[1]))
            except Exception:
                pass
            return parsed
        except Exception:
            return None

    def close(self) -> None:
        try:
            if self.sock4:
                self.sock4.close()
            if self.sock6:
                self.sock6.close()
        except Exception:
            pass


class TcpTransport:
    """
    Simple TCP transport using one-message-per-connection framing (JSON line).

    This keeps the implementation minimal and works well for distributed-algo style
    message passing where reliability/ordering matter more than throughput.
    """

    def __init__(self, listen_port: int, ip_family: str = "auto") -> None:
        self.listen_port = int(listen_port)
        self.ip_family = (ip_family or "auto").strip().lower()
        self.server4: Optional[socket.socket] = None
        self.server6: Optional[socket.socket] = None
        # TCP has no broadcast; we keep a small UDP side-channel so algorithms
        # can still do HELLO-based discovery even when transport=tcp.
        self._udp_discovery: Optional[UdpTransport] = None

        if self.ip_family in ("auto", "ipv4", "inet", "v4"):
            try:
                s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s4.bind(("0.0.0.0", self.listen_port))
                s4.listen(64)
                self.server4 = s4
            except Exception:
                self.server4 = None

        if self.ip_family in ("auto", "ipv6", "inet6", "v6"):
            try:
                s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                except Exception:
                    pass
                s6.bind(("::", self.listen_port))
                s6.listen(64)
                self.server6 = s6
            except Exception:
                self.server6 = None

        if not self.server4 and not self.server6:
            raise RuntimeError("Failed to bind TCP sockets")

        try:
            self._udp_discovery = UdpTransport(listen_port=self.listen_port, ip_family=self.ip_family)
        except Exception:
            self._udp_discovery = None

    def send(self, endpoint: NeighborEndpoint, message: dict[str, Any]) -> None:
        payload = (json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        sock: Optional[socket.socket] = None
        try:
            family = socket.AF_INET6 if ":" in str(endpoint.ip) else socket.AF_INET
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            if family == socket.AF_INET6:
                sock.connect((endpoint.ip, int(endpoint.port), 0, 0))
            else:
                sock.connect((endpoint.ip, int(endpoint.port)))
            sock.sendall(payload)
        except Exception:
            return
        finally:
            try:
                if sock is not None:
                    sock.close()
            except Exception:
                pass

    def broadcast(self, message: dict[str, Any], port: Optional[int] = None) -> None:
        b = self._udp_discovery.broadcast if self._udp_discovery else None
        if callable(b):
            try:
                b(message, port=port)
            except Exception:
                pass

    def recv(self, timeout_seconds: float) -> Optional[dict[str, Any]]:
        tcp_servers = [s for s in (self.server4, self.server6) if s is not None]
        udp_socks: list[socket.socket] = []
        if self._udp_discovery:
            udp_socks = [s for s in (self._udp_discovery.sock4, self._udp_discovery.sock6) if s is not None]
        socks = tcp_servers + udp_socks
        if not socks:
            return None
        try:
            r, _w, _x = select.select(socks, [], [], float(timeout_seconds))
        except Exception:
            return None
        if not r:
            return None

        # If UDP is readable, parse it as a normal message dict.
        if self._udp_discovery and r[0] in (self._udp_discovery.sock4, self._udp_discovery.sock6):
            try:
                data, addr = r[0].recvfrom(65535)
            except Exception:
                return None
            try:
                parsed = json.loads(data.decode("utf-8"))
                if not isinstance(parsed, dict):
                    return None
                parsed.setdefault("__raw_len", int(len(data)))
                try:
                    if isinstance(addr, tuple) and len(addr) >= 2:
                        parsed.setdefault("__src_ip", str(addr[0]))
                        parsed.setdefault("__src_port", int(addr[1]))
                except Exception:
                    pass
                return parsed
            except Exception:
                return None

        conn: Optional[socket.socket] = None
        addr: Any = None
        try:
            conn, addr = r[0].accept()
            conn.settimeout(1.0)
            buf = b""
            while b"\n" not in buf and len(buf) < 1024 * 1024:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except socket.timeout:
            return None
        except Exception:
            return None
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

        try:
            line = buf.split(b"\n", 1)[0]
            if not line:
                return None
            parsed = json.loads(line.decode("utf-8"))
            if not isinstance(parsed, dict):
                return None
            parsed.setdefault("__raw_len", int(len(line)))
            try:
                if isinstance(addr, tuple) and len(addr) >= 2:
                    parsed.setdefault("__src_ip", str(addr[0]))
                    parsed.setdefault("__src_port", int(addr[1]))
            except Exception:
                pass
            return parsed
        except Exception:
            return None

    def close(self) -> None:
        try:
            if self.server4:
                self.server4.close()
            if self.server6:
                self.server6.close()
            if self._udp_discovery:
                self._udp_discovery.close()
        except Exception:
            pass
