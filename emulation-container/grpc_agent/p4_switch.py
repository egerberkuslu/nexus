"""
BMv2 P4Runtime switch integration for Mininet/Containernet.

This provides a simple Switch subclass that runs `simple_switch_grpc` inside the switch namespace.
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Optional

from mininet.node import Switch

logger = logging.getLogger(__name__)


class P4BMv2Switch(Switch):
    """A Mininet switch that runs BMv2 `simple_switch_grpc`."""

    def __init__(
        self,
        name: str,
        sw_path: str = "simple_switch_grpc",
        json_path: Optional[str] = None,
        p4info_path: Optional[str] = None,
        grpc_port: int = 9559,
        thrift_port: int = 9090,
        device_id: int = 0,
        log_console: bool = True,
        log_level: str = "info",
        pcap_dump: bool = False,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.sw_path = sw_path
        self.json_path = json_path
        self.p4info_path = p4info_path
        self.grpc_port = int(grpc_port)
        self.thrift_port = int(thrift_port)
        self.device_id = int(device_id)
        self.log_console = bool(log_console)
        self.log_level = str(log_level or "info")
        self.pcap_dump = bool(pcap_dump)
        self.bmv2_pid: Optional[int] = None

    def start(self, controllers):  # noqa: ARG002 - Mininet passes controllers list
        if not self.json_path:
            raise RuntimeError(f"P4 switch {self.name}: missing json_path/device_config_path")
        if not os.path.exists(self.json_path):
            raise RuntimeError(f"P4 switch {self.name}: JSON not found at {self.json_path}")

        # Map interfaces to BMv2 ports (skip loopback).
        port_args = []
        port_num = 1
        for intf in self.intfList():
            if not intf or not getattr(intf, "name", None):
                continue
            if intf.name == "lo":
                continue
            port_args.extend(["-i", f"{port_num}@{intf.name}"])
            port_num += 1

        cmd = [
            self.sw_path,
            "--device-id",
            str(self.device_id),
            "--thrift-port",
            str(self.thrift_port),
            "--grpc-server-addr",
            f"0.0.0.0:{self.grpc_port}",
            "--log-level",
            self.log_level,
        ]

        if self.log_console:
            cmd.append("--log-console")
        if self.pcap_dump:
            cmd.append("--pcap")

        cmd.extend(port_args)
        cmd.append(self.json_path)

        log_dir = os.getenv("CADUCEUS_LOG_DIR", "/var/lib/caduceus/logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = "/tmp"

        log_file = os.path.join(log_dir, f"bmv2-{self.name}.log")
        cmd_str = " ".join(shlex.quote(part) for part in cmd)

        # Run in background and capture PID.
        pid_out = self.cmd(f"sh -lc {shlex.quote(cmd_str + f' > {log_file} 2>&1 & echo $!')}")
        try:
            self.bmv2_pid = int(str(pid_out).strip().splitlines()[-1])
        except Exception:
            self.bmv2_pid = None

        logger.info(
            "Started BMv2 switch %s (pid=%s, grpc_port=%s, thrift_port=%s, json=%s)",
            self.name,
            self.bmv2_pid,
            self.grpc_port,
            self.thrift_port,
            self.json_path,
        )

    def stop(self, deleteIntfs=True):  # noqa: N803 - Mininet API uses camelCase
        if self.bmv2_pid:
            self.cmd(f"kill {int(self.bmv2_pid)} >/dev/null 2>&1 || true")
            self.bmv2_pid = None
        super().stop(deleteIntfs=deleteIntfs)

