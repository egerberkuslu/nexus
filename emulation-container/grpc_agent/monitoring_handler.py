"""
Monitoring Handler for Emulation Container
Collects and streams metrics from network devices
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
import threading
from typing import Dict, List, Any, Optional, Iterator
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

import emulation_pb2
import psutil


class MonitoringHandler:
    """
    Handles metrics collection and monitoring for network devices
    Collects: interface stats, flow table stats, protocol metrics, system metrics
    """

    def __init__(self, emulation_manager=None):
        self.emulation_manager = emulation_manager
        self.monitoring_active = False
        self.monitoring_threads: Dict[str, threading.Thread] = {}
        self.metrics_buffer: Dict[str, List[Dict]] = defaultdict(list)
        self.buffer_max_size = 1000
        self._psutil_warm: set[int] = set()

    def _node_cmd(self, device: str, command: str) -> tuple[int, str, str]:
        """
        Execute a command inside a Mininet node namespace via the EmulationManager.
        Returns (exit_code, stdout, stderr).
        """
        if not self.emulation_manager or not getattr(self.emulation_manager, "net", None):
            return (1, "", "No running emulation (net is not initialized)")
        try:
            node = self.emulation_manager.get_device(device)
        except Exception as e:
            return (1, "", f"Device not found: {e}")
        try:
            out = node.cmd(command)
            return (0, out or "", "")
        except Exception as e:
            return (1, "", str(e))

    def start_monitoring(self, device: str, interval: int = 5) -> bool:
        """
        Start monitoring a device
        
        Args:
            device: Device name
            interval: Monitoring interval in seconds
            
        Returns:
            True if monitoring started successfully
        """
        try:
            if device in self.monitoring_threads and self.monitoring_threads[device].is_alive():
                logger.warning(f"Monitoring already active for {device}")
                return True

            logger.info(f"Starting monitoring for {device} (interval: {interval}s)")

            # Create monitoring thread
            thread = threading.Thread(
                target=self._monitoring_loop,
                args=(device, interval),
                daemon=True
            )
            thread.start()

            self.monitoring_threads[device] = thread
            return True

        except Exception as e:
            logger.error(f"Failed to start monitoring for {device}: {e}")
            return False

    def stop_monitoring(self, device: str) -> bool:
        """Stop monitoring a device"""
        try:
            if device not in self.monitoring_threads:
                logger.warning(f"No monitoring active for {device}")
                return True

            logger.info(f"Stopping monitoring for {device}")

            # Thread will stop on next iteration when it checks monitoring_active
            if device in self.monitoring_threads:
                del self.monitoring_threads[device]

            return True

        except Exception as e:
            logger.error(f"Failed to stop monitoring for {device}: {e}")
            return False

    def _monitoring_loop(self, device: str, interval: int):
        """Main monitoring loop for a device"""
        logger.info(f"Monitoring loop started for {device}")

        while device in self.monitoring_threads:
            try:
                # Collect metrics
                metrics = self.collect_device_metrics(device)

                # Add to buffer
                self.metrics_buffer[device].append(metrics)

                # Trim buffer if too large
                if len(self.metrics_buffer[device]) > self.buffer_max_size:
                    self.metrics_buffer[device] = self.metrics_buffer[device][-self.buffer_max_size:]

                # Sleep until next interval
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop for {device}: {e}")
                time.sleep(interval)

        logger.info(f"Monitoring loop stopped for {device}")

    def collect_device_metrics(self, device: str) -> Dict[str, Any]:
        """
        Collect all metrics for a device
        
        Args:
            device: Device name
            
        Returns:
            Dictionary of metrics
        """
        metrics = {
            "device": device,
            "timestamp": datetime.utcnow().isoformat(),
            "interfaces": {},
            "cpu": {},
            "memory": {},
            "protocols": {}
        }

        try:
            # Collect interface metrics
            metrics["interfaces"] = self._collect_interface_metrics(device)

            # Collect CPU/Memory metrics
            metrics["cpu"], metrics["memory"] = self._collect_system_metrics(device)

            # Collect protocol metrics (if applicable)
            metrics["protocols"] = self._collect_protocol_metrics(device)

        except Exception as e:
            logger.error(f"Error collecting metrics for {device}: {e}")
            metrics["error"] = str(e)

        return metrics

    def get_metrics(self, devices: List[str], metrics: Optional[List[str]] = None) -> emulation_pb2.GetMetricsResponse:
        """
        Return gRPC GetMetricsResponse for requested devices.
        The protobuf `DeviceMetrics` is an aggregated view, so we sum interface stats.
        """
        response = emulation_pb2.GetMetricsResponse()
        metrics = metrics or []

        for dev in devices:
            m = self.collect_device_metrics(dev)
            if not isinstance(m, dict) or m.get("error"):
                continue

            interfaces = m.get("interfaces") if isinstance(m.get("interfaces"), dict) else {}
            cpu = m.get("cpu") if isinstance(m.get("cpu"), dict) else {}
            mem = m.get("memory") if isinstance(m.get("memory"), dict) else {}

            rx_bytes = 0
            tx_bytes = 0
            rx_packets = 0
            tx_packets = 0
            rx_errors = 0
            tx_errors = 0
            rx_dropped = 0
            tx_dropped = 0

            for iface_stats in interfaces.values():
                if not isinstance(iface_stats, dict):
                    continue
                rx_bytes += int(iface_stats.get("rx_bytes", 0) or 0)
                tx_bytes += int(iface_stats.get("tx_bytes", 0) or 0)
                rx_packets += int(iface_stats.get("rx_packets", 0) or 0)
                tx_packets += int(iface_stats.get("tx_packets", 0) or 0)
                rx_errors += int(iface_stats.get("rx_errors", 0) or 0)
                tx_errors += int(iface_stats.get("tx_errors", 0) or 0)
                rx_dropped += int(iface_stats.get("rx_dropped", 0) or 0)
                tx_dropped += int(iface_stats.get("tx_dropped", 0) or 0)

            cpu_percent = float(cpu.get("total_cpu_percent", 0.0) or 0.0)
            memory_percent = float(mem.get("memory_percent", 0.0) or 0.0)
            if memory_percent <= 0.0:
                total_mb = float(mem.get("total_mb", 0.0) or 0.0)
                used_mb = float(mem.get("used_mb", 0.0) or 0.0)
                memory_percent = (used_mb / total_mb) * 100.0 if total_mb > 0 else 0.0
            if memory_percent < 0.0:
                memory_percent = 0.0
            if memory_percent > 100.0:
                memory_percent = 100.0

            dm = response.device_metrics[dev]
            dm.bytes_sent = tx_bytes
            dm.bytes_received = rx_bytes
            dm.packets_sent = tx_packets
            dm.packets_received = rx_packets
            dm.errors_in = rx_errors
            dm.errors_out = tx_errors
            dm.drops_in = rx_dropped
            dm.drops_out = tx_dropped
            dm.cpu_percent = cpu_percent
            dm.memory_percent = memory_percent

        return response

    def stream_metrics(self, devices: List[str], interval_seconds: int = 5) -> Iterator[emulation_pb2.MetricsUpdate]:
        """
        Stream MetricsUpdate messages indefinitely until the caller cancels.
        """
        interval = max(1, int(interval_seconds or 5))
        while True:
            update = emulation_pb2.MetricsUpdate()
            update.timestamp = int(time.time() * 1000)
            metrics_resp = self.get_metrics(devices=devices, metrics=[])
            for dev, dm in metrics_resp.device_metrics.items():
                out = update.device_metrics[dev]
                out.bytes_sent = dm.bytes_sent
                out.bytes_received = dm.bytes_received
                out.packets_sent = dm.packets_sent
                out.packets_received = dm.packets_received
                out.errors_in = dm.errors_in
                out.errors_out = dm.errors_out
                out.drops_in = dm.drops_in
                out.drops_out = dm.drops_out
                out.cpu_percent = dm.cpu_percent
                out.memory_percent = dm.memory_percent
            yield update
            time.sleep(interval)

    def get_interface_stats(self, device: str, interface: str) -> emulation_pb2.GetInterfaceStatsResponse:
        """
        Return per-interface stats for a device.
        """
        interfaces = self._collect_interface_metrics(device)
        resp = emulation_pb2.GetInterfaceStatsResponse()
        want_all = not interface or interface in ("*", "all")
        for ifname, st in interfaces.items():
            if not want_all and ifname != interface:
                continue
            resp.stats.append(
                emulation_pb2.InterfaceStats(
                    interface=ifname,
                    rx_bytes=int(st.get("rx_bytes", 0) or 0),
                    tx_bytes=int(st.get("tx_bytes", 0) or 0),
                    rx_packets=int(st.get("rx_packets", 0) or 0),
                    tx_packets=int(st.get("tx_packets", 0) or 0),
                    rx_errors=int(st.get("rx_errors", 0) or 0),
                    tx_errors=int(st.get("tx_errors", 0) or 0),
                    rx_dropped=int(st.get("rx_dropped", 0) or 0),
                    tx_dropped=int(st.get("tx_dropped", 0) or 0),
                )
            )
        return resp

    def _collect_interface_metrics(self, device: str) -> Dict[str, Dict]:
        """Collect network interface statistics"""
        interfaces = {}

        try:
            allowed_ifaces: Optional[List[str]] = None
            in_namespace = True
            if self.emulation_manager and getattr(self.emulation_manager, "net", None):
                try:
                    node = self.emulation_manager.get_device(device)
                    ns_attr = getattr(node, "inNamespace", True)
                    in_namespace = bool(ns_attr() if callable(ns_attr) else ns_attr)
                    want = set()
                    for intf in getattr(node, "intfList", lambda: [])() or []:
                        name = getattr(intf, "name", None)
                        if name:
                            want.add(str(name))
                    node_name = getattr(node, "name", None)
                    if node_name:
                        want.add(str(node_name))
                    if in_namespace:
                        want.add("lo")
                    # Filter out empty/None-like entries.
                    want = {n for n in want if n and n != "None"}
                    if want:
                        allowed_ifaces = sorted(want)
                except Exception:
                    allowed_ifaces = None

            # If a switch runs in the root namespace, restrict to its own interfaces by prefix even if
            # Mininet object introspection fails (prevents reporting host-wide bridges/veths).
            if not in_namespace and not allowed_ifaces:
                rc, out, _err = self._node_cmd(device, f"sh -lc \"ls /sys/class/net 2>/dev/null | egrep '^{device}(-|$)' || true\"")
                if rc == 0 and out:
                    want = [ln.strip() for ln in out.splitlines() if ln.strip()]
                    if want:
                        allowed_ifaces = sorted(set(want))

            # Preferred: parse /proc/net/dev (netns-aware and reliable in our Docker+Containernet setup).
            # /sys/class/net can miss Mininet-created veths for switch-like nodes while /proc/net/dev still
            # reports them correctly (and matches `ip link` output).
            rc, out, _err = self._node_cmd(device, "cat /proc/net/dev")
            if rc == 0 and out:
                lines = (out or "").splitlines()
                data_lines = lines[2:] if len(lines) >= 3 else lines

                allow_set = set(allowed_ifaces) if allowed_ifaces else None
                if not in_namespace and not allow_set:
                    # Root-namespace switches: pick only their own interfaces by prefix.
                    allow_set = set()
                    for ln in data_lines:
                        if ":" not in ln:
                            continue
                        ifname = ln.split(":", 1)[0].strip()
                        if ifname == device or ifname.startswith(device + "-"):
                            allow_set.add(ifname)
                    allow_set.discard("lo")
                    if not allow_set:
                        allow_set = None

                for ln in data_lines:
                    if ":" not in ln:
                        continue
                    ifname, rest = ln.split(":", 1)
                    ifname = ifname.strip()
                    if allow_set is not None and ifname not in allow_set:
                        continue
                    parts = rest.strip().split()
                    if len(parts) < 16:
                        continue
                    try:
                        rx_bytes = int(parts[0])
                        rx_packets = int(parts[1])
                        rx_errors = int(parts[2])
                        rx_dropped = int(parts[3])
                        tx_bytes = int(parts[8])
                        tx_packets = int(parts[9])
                        tx_errors = int(parts[10])
                        tx_dropped = int(parts[11])
                    except Exception:
                        continue

                    interfaces[ifname] = {
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "rx_packets": rx_packets,
                        "tx_packets": tx_packets,
                        "rx_errors": rx_errors,
                        "tx_errors": tx_errors,
                        "rx_dropped": rx_dropped,
                        "tx_dropped": tx_dropped,
                    }

                if interfaces:
                    return interfaces

            # Fallback: parse `ip -s link show` (kept for compatibility).
            rc, out, _err = self._node_cmd(device, "ip -s link show")
            if rc == 0:
                current_iface = None
                rx_line = False
                tx_line = False

                for line in (out or "").splitlines():
                    line = line.strip()

                    # Interface name line
                    if line and line[0].isdigit():
                        parts = line.split(':')
                        if len(parts) >= 2:
                            current_iface = parts[1].strip().split('@', 1)[0]
                            interfaces[current_iface] = {
                                "rx_bytes": 0,
                                "rx_packets": 0,
                                "rx_errors": 0,
                                "rx_dropped": 0,
                                "tx_bytes": 0,
                                "tx_packets": 0,
                                "tx_errors": 0,
                                "tx_dropped": 0
                            }
                            rx_line = False
                            tx_line = False

                    # RX stats line
                    elif current_iface and "RX:" in line:
                        rx_line = True
                    elif current_iface and rx_line and line and line[0].isdigit():
                        parts = line.split()
                        if len(parts) >= 4:
                            interfaces[current_iface]["rx_bytes"] = int(parts[0])
                            interfaces[current_iface]["rx_packets"] = int(parts[1])
                            interfaces[current_iface]["rx_errors"] = int(parts[2])
                            interfaces[current_iface]["rx_dropped"] = int(parts[3])
                        rx_line = False

                    # TX stats line
                    elif current_iface and "TX:" in line:
                        tx_line = True
                    elif current_iface and tx_line and line and line[0].isdigit():
                        parts = line.split()
                        if len(parts) >= 4:
                            interfaces[current_iface]["tx_bytes"] = int(parts[0])
                            interfaces[current_iface]["tx_packets"] = int(parts[1])
                            interfaces[current_iface]["tx_errors"] = int(parts[2])
                            interfaces[current_iface]["tx_dropped"] = int(parts[3])
                        tx_line = False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout collecting interface metrics for {device}")
        except Exception as e:
            logger.error(f"Failed to collect interface metrics for {device}: {e}")

        return interfaces

    def _collect_system_metrics(self, device: str) -> tuple:
        """Collect CPU and memory metrics"""
        cpu_metrics = {}
        mem_metrics = {}

        try:
            pid: Optional[int] = None
            node = None
            if self.emulation_manager and getattr(self.emulation_manager, "net", None):
                try:
                    node = self.emulation_manager.get_device(device)
                except Exception:
                    node = None
            if node is None and self.emulation_manager and getattr(self.emulation_manager, "devices", None):
                try:
                    node = (self.emulation_manager.devices.get(device) or {}).get("node")
                except Exception:
                    node = None

            if node is not None:
                try:
                    pid = int(getattr(node, "pid", 0) or 0)
                except Exception:
                    pid = None

            def _cgroup_mem_limit_bytes() -> Optional[int]:
                candidates = [
                    "/sys/fs/cgroup/memory.max",  # cgroup v2
                    "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroup v1
                ]
                for path in candidates:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            raw = (f.read() or "").strip()
                        if not raw or raw == "max":
                            continue
                        value = int(raw)
                        # Some setups report "unlimited" as a very large number.
                        if value <= 0 or value >= (1 << 60):
                            continue
                        return value
                    except Exception:
                        continue
                return None

            if pid and pid > 0 and psutil.pid_exists(pid):
                # Mininet/Containernet frequently launches commands via mnexec in a way that
                # breaks simple parent/child PID accounting. Instead, aggregate by network
                # namespace: all processes attached to the node's netns count toward its usage.
                try:
                    target_netns = os.readlink(f"/proc/{pid}/ns/net")
                except Exception:
                    target_netns = None

                procs: list[psutil.Process] = []
                if target_netns:
                    for p in psutil.process_iter(["pid"]):
                        try:
                            if os.readlink(f"/proc/{p.pid}/ns/net") == target_netns:
                                procs.append(p)
                        except Exception:
                            continue
                else:
                    procs = [psutil.Process(pid)]

                total_cpu = 0.0
                total_rss = 0
                for p in procs:
                    try:
                        p_pid = p.pid
                        if p_pid not in self._psutil_warm:
                            # First sample for a PID is often 0.0; take a tiny blocking
                            # sample so the UI doesn't get stuck showing 0.0% forever.
                            total_cpu += float(p.cpu_percent(interval=0.05) or 0.0)
                            self._psutil_warm.add(p_pid)
                        else:
                            total_cpu += float(p.cpu_percent(interval=None) or 0.0)
                    except Exception:
                        pass
                    try:
                        total_rss += int(p.memory_info().rss or 0)
                    except Exception:
                        pass

                cpu_count = psutil.cpu_count() or 1
                normalized_cpu = total_cpu / float(cpu_count)
                if normalized_cpu < 0.0:
                    normalized_cpu = 0.0
                if normalized_cpu > 100.0:
                    normalized_cpu = 100.0

                mem_limit = _cgroup_mem_limit_bytes()
                vm = psutil.virtual_memory()
                total_bytes = int(mem_limit or vm.total or 0)
                total_mb = float(total_bytes) / (1024.0 * 1024.0) if total_bytes else 0.0
                used_mb = float(total_rss) / (1024.0 * 1024.0)
                free_mb = max(0.0, total_mb - used_mb) if total_mb else 0.0
                memory_percent = (float(total_rss) / float(total_bytes) * 100.0) if total_bytes > 0 else 0.0
                if memory_percent < 0.0:
                    memory_percent = 0.0
                if memory_percent > 100.0:
                    memory_percent = 100.0

                cpu_metrics = {
                    "total_cpu_percent": normalized_cpu,
                    "raw_total_cpu_percent": total_cpu,
                    "cpu_count": cpu_count,
                    "process_count": len(procs),
                    "pid": pid,
                }
                mem_metrics = {
                    "total_mb": total_mb,
                    "used_mb": used_mb,
                    "free_mb": free_mb,
                    "rss_bytes": total_rss,
                    "limit_bytes": total_bytes,
                    "memory_percent": memory_percent,
                    "pid": pid,
                }
            else:
                # Fallback (less accurate): container-wide view
                vm = psutil.virtual_memory()
                total_mb = float(vm.total) / (1024.0 * 1024.0) if vm.total else 0.0
                try:
                    cpu_pct = float(psutil.cpu_percent(interval=0.05) or 0.0)
                except Exception:
                    cpu_pct = 0.0
                cpu_metrics = {"total_cpu_percent": cpu_pct, "process_count": 0, "pid": pid or 0}
                mem_metrics = {
                    "total_mb": total_mb,
                    "used_mb": float(vm.used) / (1024.0 * 1024.0) if vm.used else 0.0,
                    "free_mb": float(vm.available) / (1024.0 * 1024.0) if vm.available else 0.0,
                    "memory_percent": (float(vm.percent) if getattr(vm, "percent", None) is not None else 0.0),
                    "pid": pid or 0,
                }

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout collecting system metrics for {device}")
        except Exception as e:
            logger.error(f"Failed to collect system metrics for {device}: {e}")

        return cpu_metrics, mem_metrics

    def _collect_protocol_metrics(self, device: str) -> Dict[str, Any]:
        """Collect routing protocol metrics"""
        protocol_metrics = {}

        try:
            # Check for OSPF
            rc, out, _err = self._node_cmd(device, 'vtysh -c "show ip ospf neighbor"')
            if rc == 0 and (out or "").strip():
                neighbor_count = len([line for line in (out or "").splitlines() if line.strip() and not line.startswith("Neighbor")])
                protocol_metrics["ospf"] = {
                    "neighbor_count": neighbor_count,
                    "status": "active"
                }

            # Check for BGP
            rc2, out2, _err2 = self._node_cmd(device, 'vtysh -c "show ip bgp summary"')
            if rc2 == 0 and (out2 or "").strip():
                # Parse BGP summary
                lines = (out2 or "").splitlines()
                neighbor_count = 0
                for line in lines:
                    if line.strip() and not any(x in line for x in ["BGP", "Neighbor", "------"]):
                        parts = line.split()
                        if len(parts) > 0 and parts[0].replace('.', '').isdigit():
                            neighbor_count += 1

                protocol_metrics["bgp"] = {
                    "neighbor_count": neighbor_count,
                    "status": "active"
                }

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout collecting protocol metrics for {device}")
        except Exception as e:
            logger.error(f"Failed to collect protocol metrics for {device}: {e}")

        return protocol_metrics

    def get_flow_table_metrics(self, switch: str) -> Dict[str, Any]:
        """Collect OpenFlow flow table statistics"""
        metrics = {
            "switch": switch,
            "timestamp": datetime.utcnow().isoformat(),
            "flows": [],
            "flow_count": 0,
            "packet_count": 0,
            "byte_count": 0
        }

        try:
            # Get flow stats from OVS
            result = subprocess.run(
                ["ovs-ofctl", "dump-flows", switch],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                flows = []
                total_packets = 0
                total_bytes = 0

                for line in result.stdout.splitlines():
                    if "cookie=" in line:
                        flow_info = {}

                        # Parse packet and byte counts
                        if "n_packets=" in line:
                            parts = line.split("n_packets=")
                            if len(parts) > 1:
                                n_packets = parts[1].split(',')[0].strip()
                                flow_info["packets"] = int(n_packets) if n_packets.isdigit() else 0
                                total_packets += flow_info["packets"]

                        if "n_bytes=" in line:
                            parts = line.split("n_bytes=")
                            if len(parts) > 1:
                                n_bytes = parts[1].split(',')[0].strip()
                                flow_info["bytes"] = int(n_bytes) if n_bytes.isdigit() else 0
                                total_bytes += flow_info["bytes"]

                        if flow_info:
                            flow_info["rule"] = line.strip()
                            flows.append(flow_info)

                metrics["flows"] = flows
                metrics["flow_count"] = len(flows)
                metrics["packet_count"] = total_packets
                metrics["byte_count"] = total_bytes

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout collecting flow table metrics for {switch}")
        except Exception as e:
            logger.error(f"Failed to collect flow table metrics for {switch}: {e}")

        return metrics

    def get_latest_metrics(self, device: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get latest metrics for a device"""
        if device not in self.metrics_buffer:
            return []

        return self.metrics_buffer[device][-count:]

    def stream_device_metrics(self, device: str, interval: int = 5) -> Iterator[Dict[str, Any]]:
        """
        Stream metrics for a device (generator)
        
        Args:
            device: Device name
            interval: Streaming interval in seconds
            
        Yields:
            Metric dictionaries
        """
        logger.info(f"Starting metric stream for {device}")

        try:
            while True:
                metrics = self.collect_device_metrics(device)
                yield metrics
                time.sleep(interval)

        except GeneratorExit:
            logger.info(f"Metric stream closed for {device}")
        except Exception as e:
            logger.error(f"Error streaming metrics for {device}: {e}")

    def get_topology_metrics(self, devices: List[str]) -> Dict[str, Any]:
        """Get aggregated metrics for entire topology"""
        topology_metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "device_count": len(devices),
            "devices": {},
            "aggregated": {
                "total_rx_bytes": 0,
                "total_tx_bytes": 0,
                "total_rx_packets": 0,
                "total_tx_packets": 0,
                "active_flows": 0
            }
        }

        for device in devices:
            try:
                device_metrics = self.collect_device_metrics(device)
                topology_metrics["devices"][device] = device_metrics

                # Aggregate interface metrics
                for iface_name, iface_stats in device_metrics.get("interfaces", {}).items():
                    topology_metrics["aggregated"]["total_rx_bytes"] += iface_stats.get("rx_bytes", 0)
                    topology_metrics["aggregated"]["total_tx_bytes"] += iface_stats.get("tx_bytes", 0)
                    topology_metrics["aggregated"]["total_rx_packets"] += iface_stats.get("rx_packets", 0)
                    topology_metrics["aggregated"]["total_tx_packets"] += iface_stats.get("tx_packets", 0)

            except Exception as e:
                logger.error(f"Error collecting metrics for {device}: {e}")
                topology_metrics["devices"][device] = {"error": str(e)}

        return topology_metrics

    def clear_metrics(self, device: Optional[str] = None):
        """Clear metrics buffer"""
        if device:
            if device in self.metrics_buffer:
                self.metrics_buffer[device].clear()
                logger.info(f"Metrics cleared for {device}")
        else:
            self.metrics_buffer.clear()
            logger.info("All metrics cleared")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get status of all monitoring threads"""
        status = {
            "active_monitoring": [],
            "total_devices": len(self.monitoring_threads)
        }

        for device, thread in self.monitoring_threads.items():
            status["active_monitoring"].append({
                "device": device,
                "thread_alive": thread.is_alive(),
                "metrics_buffered": len(self.metrics_buffer.get(device, []))
            })

        return status
