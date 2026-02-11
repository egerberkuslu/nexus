"""
Custom Mininet CLI helpers for Caduceus-Flux.

Mininet's built-in `pingall` relies on `Host.IP()` which may return None when IPs are
applied at runtime (via `ip addr ...`) rather than `host.setIP()`/`intf.setIP()`.
This CLI overrides `pingall` to discover real addresses from the namespace.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Iterable, Optional

from mininet.cli import CLI
from mininet.log import error, info


def _parse_ipv4_cidrs(text: str) -> list[str]:
    cidrs: list[str] = []
    for line in (text or "").splitlines():
        token = line.strip()
        if not token:
            continue
        cidrs.append(token)
    return cidrs


def _ipv4_network_of(ip: str, prefixlen: int) -> ipaddress.IPv4Network:
    return ipaddress.ip_network(f"{ip}/{prefixlen}", strict=False)


class CaduceusCLI(CLI):
    """CLI that provides a runtime-IP-aware `pingall`."""

    def _get_ipv4_addrs(self, host) -> list[tuple[str, int]]:
        out = host.cmd("sh -lc \"ip -4 -o addr show scope global | awk '{print $4}'\"")
        cidrs = _parse_ipv4_cidrs(out)
        addrs: list[tuple[str, int]] = []
        for cidr in cidrs:
            m = re.match(r"^([0-9.]+)/([0-9]{1,2})$", cidr.strip())
            if not m:
                continue
            ip = m.group(1)
            prefix = int(m.group(2))
            addrs.append((ip, prefix))
        return addrs

    def _select_dst_ip(self, src, dst) -> Optional[str]:
        src_addrs = self._get_ipv4_addrs(src)
        dst_addrs = self._get_ipv4_addrs(dst)
        if not dst_addrs:
            return None

        # Prefer a destination address that shares a subnet with any source address.
        for src_ip, src_prefix in src_addrs:
            try:
                src_net = _ipv4_network_of(src_ip, src_prefix)
            except Exception:
                continue
            for dst_ip, _dst_prefix in dst_addrs:
                try:
                    if ipaddress.ip_address(dst_ip) in src_net:
                        return dst_ip
                except Exception:
                    continue

        # Fallback to the first global IPv4 address.
        return dst_addrs[0][0]

    def do_pingall(self, line):  # noqa: D401 - Mininet CLI signature
        """Ping between all hosts using runtime-discovered IPv4 addresses."""
        hosts: list = list(getattr(self.mn, "hosts", []) or [])
        if not hosts:
            info("*** Ping: no hosts\n")
            return

        info("*** Ping: testing ping reachability\n")

        total = 0
        received = 0

        for src in hosts:
            info(f"{src.name} -> ")
            for dst in hosts:
                if src is dst:
                    continue
                total += 1
                dst_ip = self._select_dst_ip(src, dst)
                if not dst_ip:
                    info("X ")
                    continue
                out = src.cmd(f"ping -c 1 -W 1 {dst_ip} 2>&1")
                ok = " 0% packet loss" in out or ", 1 received" in out or " 1 received," in out
                if ok:
                    received += 1
                    info(f"{dst.name} ")
                else:
                    info("X ")
                    # Keep debug output terse; full output is often noisy.
                    if "Temporary failure in name resolution" in out:
                        error("*** ping failed due to name resolution\n")
            info("\n")

        dropped = total - received
        pct = int(round((dropped / total) * 100)) if total else 0
        info(f"*** Results: {pct}% dropped ({received}/{total} received)\n")

    def do_controllers(self, line):  # noqa: D401 - Mininet CLI signature
        """List OpenFlow controller targets for switches (controllers are not Mininet nodes)."""
        switches: list = list(getattr(self.mn, "switches", []) or [])
        if not switches:
            info("*** No switches\n")
            return

        info("*** Switch controllers:\n")
        for sw in switches:
            try:
                target = (sw.cmd(f"ovs-vsctl get-controller {sw.name} 2>/dev/null") or "").strip()
                fail_mode = (sw.cmd(f"ovs-vsctl get-fail-mode {sw.name} 2>/dev/null") or "").strip()
                if not target:
                    target = "—"
                if not fail_mode:
                    fail_mode = "—"
                info(f"{sw.name}: controller={target} fail_mode={fail_mode}\n")
            except Exception:
                info(f"{sw.name}: controller=— fail_mode=—\n")
