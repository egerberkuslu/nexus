"""
Emulation Manager - Core emulation lifecycle management
Handles Mininet + Mininet-WiFi + Containernet integration
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shlex
import time
import hashlib
import sys
import ipaddress
import socket
import threading
from typing import Dict
import fcntl
from types import SimpleNamespace

REQUIRED_MODULE_PATHS = [
    '/mininet',
    '/mininet/mininet',
    '/mininet/mininet-wifi',
    '/mininet-wifi',
    '/mininet-wifi/mininet',
    '/mininet-wifi/mn_wifi',
    '/mininet-wifi/custom',
    '/mininet-wifi/custom/containernet',
    '/home/mininet/mininet',
    '/home/mininet/mininet-wifi',
    '/home/mininet/containernet',
    '/home/ege/mininet',
    '/home/ege/mininet-wifi',
    '/home/ege/containernet',
    '/opt/mininet',
    '/opt/mininet-wifi',
    '/opt/containernet'
]

for module_path in REQUIRED_MODULE_PATHS:
    if os.path.isdir(module_path) and module_path not in sys.path:
        # Do not prepend these paths; we prefer the pip-installed Containernet/Mininet
        # packages when available (they expose `Containernet` under `mininet.*`).
        sys.path.append(module_path)

def _configure_docker_sdk_timeout() -> None:
    """
    Containernet's Docker node uses docker-py's default timeout (60s). When multiple
    topologies start concurrently, docker image pulls/container creation can exceed
    this timeout and leave the topology in a partially-created state (missing nodes
    causing link creation failures).
    """
    try:
        import docker.constants as docker_constants
        import docker.client as docker_client

        timeout_raw = os.getenv("CADUCEUS_DOCKER_HTTP_TIMEOUT") or os.getenv("CADUCEUS_DOCKER_SDK_TIMEOUT")
        timeout = int(timeout_raw) if timeout_raw else 300
        if timeout <= 0:
            return

        docker_constants.DEFAULT_TIMEOUT_SECONDS = timeout
        if hasattr(docker_client, "DEFAULT_TIMEOUT_SECONDS"):
            docker_client.DEFAULT_TIMEOUT_SECONDS = timeout
        logger = logging.getLogger(__name__)
        logger.info("Docker SDK default timeout set to %ss", timeout)
    except Exception:
        # Avoid crashing startup if docker isn't importable in this environment.
        pass


_configure_docker_sdk_timeout()

from mininet.node import Controller, RemoteController, OVSKernelSwitch, Node as MininetNode
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.clean import cleanup
try:
    # Some builds expose Containernet under the `mininet.*` namespace.
    from mininet.net import Containernet  # type: ignore
except Exception:
    # Fallback: Containernet is installed as its own package.
    from containernet.net import Containernet  # type: ignore
from mininet.link import Link

# Containernet is packaged as a Mininet fork in the official repo; the Python import
# namespace is still `mininet.*` (not `containernet.*`) in many builds.
#
# Some optional classes (e.g., DockerSta/DockerP4AP) may not exist depending on the
# Containernet/Mininet-WiFi build; provide safe fallbacks so the gRPC server can boot.
try:
    from mininet.node import Docker  # type: ignore
except Exception:
    from containernet.node import Docker  # type: ignore

try:
    from mininet.node import DockerSta  # type: ignore
except Exception:
    try:
        from containernet.node import DockerSta  # type: ignore
    except Exception:
        DockerSta = Docker  # type: ignore

try:
    from mininet.node import DockerP4AP  # type: ignore
except Exception:
    try:
        from containernet.node import DockerP4AP  # type: ignore
    except Exception:
        DockerP4AP = Docker  # type: ignore

ContainernetCLI = CLI
from mn_wifi.link import WirelessLink

from device_handler import DeviceHandler

# Import snapshot managers
try:
    from snapshot_manager import HybridSnapshotManager, SnapshotType
    SNAPSHOT_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Snapshot manager not available")
    SNAPSHOT_AVAILABLE = False

logger = logging.getLogger(__name__)

STATE_DIR = "/var/lib/caduceus"
STATE_FILE = os.path.join(STATE_DIR, "emulation_state.json")
MININET_NAME_MAX_LEN = 10


def _patch_mininet_cmd_with_file_lock(lock_path: str = "/tmp/caduceus_mininet_cmd.lock") -> None:
    """
    Serialize Mininet/Containernet `Node.cmd()` across processes.

    The gRPC MininetCLI session runs a CLI in a forked child process while the parent
    keeps serving gRPC calls (ExecuteCommand, metrics, etc). `Node.cmd()` is not safe
    to call concurrently: the interactive shell channel can get corrupted and Mininet
    reports `shell died on <node>`.

    Using an OS-level flock makes it safe across both processes.
    """
    if getattr(MininetNode, "_caduceus_cmd_lock_patched", False):
        return

    original_cmd = MininetNode.cmd

    def locked_cmd(self, *args, **kwargs):  # type: ignore[no-redef]
        fd = None
        try:
            fd = open(lock_path, "a+")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            return original_cmd(self, *args, **kwargs)
        finally:
            try:
                if fd is not None:
                    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                    fd.close()
            except Exception:
                pass

    MininetNode.cmd = locked_cmd  # type: ignore[assignment]
    setattr(MininetNode, "_caduceus_cmd_lock_patched", True)


class EmulationManager:
    """Manages the lifecycle of network emulations"""

    def __init__(self):
        self.net = None
        self.net_wifi = None
        self.is_wifi_enabled = False
        self.emulation_id = None
        self.topology_id = None
        self.start_time = None
        self.status = 'stopped'
        self.devices = {}
        self.links = {}
        self.pending_links = []
        self.tc_capable_cache = {}
        env_passthrough = os.getenv("DOCKER_ENV_PASSTHROUGH", "TOKEN")
        if env_passthrough:
            self.docker_env_passthrough = [
                item.strip()
                for item in env_passthrough.split(',')
                if item.strip()
            ]
        else:
            self.docker_env_passthrough = []
        self.host_docker_env = {
            name: os.environ[name]
            for name in self.docker_env_passthrough
            if name in os.environ
        }
        if self.host_docker_env:
            logger.info(
                "Passthrough Docker env configured: %s",
                ", ".join(f"{k}=***" for k in self.host_docker_env)
            )

        # Set log level
        setLogLevel('info')

        # Make Mininet `Node.cmd()` safe across forked CLI sessions.
        try:
            lock_file = os.getenv("CADUCEUS_MININET_CMD_LOCK_FILE", "/tmp/caduceus_mininet_cmd.lock")
            _patch_mininet_cmd_with_file_lock(lock_file)
        except Exception as exc:
            logger.warning(f"Failed to patch Mininet Node.cmd lock: {exc}")

        # Initialize snapshot manager
        if SNAPSHOT_AVAILABLE:
            try:
                self.snapshot_manager = HybridSnapshotManager(self)
                logger.info("Snapshot manager initialized")
            except Exception as e:
                logger.warning(f"Snapshot manager initialization failed: {e}")
                self.snapshot_manager = None
        else:
            self.snapshot_manager = None

        # Serialize lifecycle operations (start/stop). UI/API retries can call
        # StartEmulation multiple times while a start is still running; concurrent
        # starts corrupt Mininet state and cause Docker container name conflicts.
        self._lifecycle_lock = threading.RLock()

        logger.info("EmulationManager initialized")

    def _is_transient_docker_error(self, exc: Exception) -> bool:
        """Return True for docker create errors that are likely temporary under load."""
        try:
            import requests  # type: ignore

            if isinstance(exc, requests.exceptions.ReadTimeout):
                return True
        except Exception:
            pass

        try:
            import urllib3  # type: ignore

            if isinstance(exc, getattr(urllib3.exceptions, "ReadTimeoutError", ())):
                return True
        except Exception:
            pass

        message = str(exc).lower()
        if "read timed out" in message or "readtimeout" in message:
            return True

        # Starting multiple topologies concurrently can also surface name conflicts
        # from stale containers left behind by previous failed starts.
        if "already in use" in message and "container name" in message:
            return True
        if "409" in message and "conflict" in message:
            return True

        return False

    def _docker_namespace(self) -> str:
        seed = self.topology_id or self.emulation_id or "caduceus"
        return hashlib.sha1(seed.encode()).hexdigest()[:4]

    def _allocate_docker_runtime_name(self, original_name: str, kind: str = "d") -> str:
        """
        Allocate a deterministic, Mininet-safe (<=10 chars) runtime name for nodes
        that become Docker containers on the *host* via Containernet.

        Docker container names are global on the host (Containernet uses `mn.<name>`),
        so multiple concurrent topologies must not reuse the same node names.
        """
        return self._allocate_docker_runtime_name_internal(original_name, kind=kind, ensure_unique=True)

    def _allocate_docker_runtime_name_internal(
        self,
        original_name: str,
        kind: str = "d",
        *,
        ensure_unique: bool,
    ) -> str:
        # Deterministic, per-topology namespace: keep names <= 10 chars but avoid
        # collisions across concurrently-running topologies by hashing the full
        # topology identifier into the name.
        kind_char = (kind or "d")[0].lower()
        topo_seed = self.topology_id or self.emulation_id or "caduceus"
        digest = hashlib.sha1(f"{topo_seed}:{original_name}:{kind_char}".encode()).hexdigest()[:9]
        return f"{kind_char}{digest}"[:MININET_NAME_MAX_LEN]

    def _legacy_docker_runtime_names(self, original_name: str, kind: str = "d") -> list[str]:
        """Generate previous runtime-name variants for cleanup/backward compatibility."""
        kind_char = (kind or "d")[0].lower()
        topo_ns = self._docker_namespace()
        base_seed = f"{topo_ns}:{original_name}:{kind_char}"
        names: list[str] = []
        for attempt in range(0, 4):
            node_hash = hashlib.sha1(f"{base_seed}:{attempt}".encode()).hexdigest()[:5]
            names.append(f"{kind_char}{topo_ns}{node_hash}"[:MININET_NAME_MAX_LEN])
        return names

    def _cleanup_docker_containers_for_topology(self, topology) -> None:
        """Remove only the mn.* containers that belong to this topology."""
        try:
            import subprocess

            docker_names: list[str] = []
            for device in getattr(topology, "devices", []) or []:
                props = dict(getattr(device, "properties", {}) or {})
                dockerized = props.get("dockerized", False)
                if isinstance(dockerized, str):
                    dockerized = dockerized.strip().lower() in ("true", "1", "yes")

                dtype = str(getattr(device, "type", "") or "").lower()
                if not dockerized and dtype not in ("docker",):
                    continue

                kind = "d"
                if dtype in ("host", "h"):
                    kind = "h"
                elif dtype in ("station", "sta"):
                    kind = "w"
                elif dtype in ("ap", "accesspoint"):
                    kind = "a"
                elif dtype in ("docker",):
                    kind = "c"

                runtime_name = self._allocate_docker_runtime_name_internal(
                    str(getattr(device, "name", "") or ""),
                    kind=kind,
                    ensure_unique=False,
                )
                docker_names.append(f"mn.{runtime_name}")
                for legacy in self._legacy_docker_runtime_names(str(getattr(device, "name", "") or ""), kind=kind):
                    docker_names.append(f"mn.{legacy}")

            docker_names = sorted(set([name for name in docker_names if name]))
            if not docker_names:
                return

            subprocess.run(["docker", "rm", "-f", *docker_names], timeout=60, capture_output=True, text=True)
            logger.info("Removed %s stale mn.* containers for topology %s", len(docker_names), self.topology_id)
        except Exception as exc:
            logger.warning("Failed to cleanup topology-scoped Docker containers: %s", exc)

    def _cleanup_docker_container_for_node(self, name: str) -> None:
        """
        Best-effort cleanup for a Containernet Docker node.

        If docker-py timed out while waiting for the daemon response, the container
        may still have been created. Subsequent retries can fail with name conflicts.
        """
        container_name = f"mn.{name}"
        try:
            import docker  # type: ignore

            docker.from_env().api.remove_container(container=container_name, force=True)
            return
        except Exception:
            try:
                import subprocess

                subprocess.run(["docker", "rm", "-f", container_name], timeout=30, capture_output=True, text=True)
            except Exception:
                pass

    def _add_docker_node(self, name: str, docker_kwargs: Dict) -> object:
        """
        Wrapper around `Containernet.addDocker()` that tolerates slower Docker daemon
        responses when multiple topologies start concurrently.
        """
        retries = int(os.getenv("CADUCEUS_DOCKER_CREATE_RETRIES", "2"))
        backoff_seconds = float(os.getenv("CADUCEUS_DOCKER_CREATE_BACKOFF_SECONDS", "2.0"))
        lock_file = os.getenv("CADUCEUS_DOCKER_CREATE_LOCK_FILE", "/tmp/caduceus_docker_create.lock")

        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            fd = None
            try:
                if lock_file:
                    fd = open(lock_file, "a+")
                    fcntl.flock(fd.fileno(), fcntl.LOCK_EX)

                return self.net.addDocker(name, **docker_kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= retries or not self._is_transient_docker_error(exc):
                    raise

                delay = min(backoff_seconds * (2**attempt), 30.0)
                logger.warning(
                    "Docker node create timed out for %s (attempt %s/%s); retrying in %.1fs: %s",
                    name,
                    attempt + 1,
                    retries + 1,
                    delay,
                    exc,
                )
                self._cleanup_docker_container_for_node(name)
                time.sleep(delay)
            finally:
                try:
                    if fd is not None:
                        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                        fd.close()
                except Exception:
                    pass

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed to create docker node {name}")

    def _normalize_dpid(self, value, fallback: str = '') -> str:
        """Normalize datapath IDs to 16-character hex strings."""
        if isinstance(value, int) and value >= 0:
            return f"{value & 0xffffffffffff:016x}"

        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned.startswith('0x'):
                cleaned = cleaned[2:]
            cleaned = re.sub(r'[^0-9a-f]', '', cleaned)
            if cleaned:
                try:
                    numeric = int(cleaned, 16)
                    return f"{numeric & 0xffffffffffff:016x}"
                except ValueError:
                    pass

        # Fallback to deterministic hash if nothing usable
        seed = fallback or str(value) or 'switch'
        hashed = hashlib.sha1(seed.encode()).hexdigest()
        return hashed[-16:]

    def register_node_mapping(self, identifier: str, mininet_name: str):
        """Register an identifier (node_id or alias) to resolve to the Mininet name."""
        if not mininet_name:
            return

        # Always ensure the actual Mininet name maps to itself
        self.node_id_to_name[mininet_name] = mininet_name

        if identifier:
            self.node_id_to_name[str(identifier)] = mininet_name

    def unregister_node_mapping(self, identifier: str):
        """Remove identifier and any aliases associated with the same Mininet device."""
        if not identifier:
            return

        target = self.node_id_to_name.get(identifier, identifier)
        keys_to_remove = [
            key for key, value in self.node_id_to_name.items()
            if key == target or value == target
        ]
        for key in keys_to_remove:
            self.node_id_to_name.pop(key, None)

    def _name_exists(self, candidate: str) -> bool:
        """Check whether a runtime name is already in use."""
        if not candidate:
            return False

        if candidate in self.devices:
            return True

        try:
            if self.net and getattr(self.net, 'nameToNode', None):
                return candidate in self.net.nameToNode
        except Exception:
            pass

        return False

    def _allocate_docker_ap_name(self, base_name: str) -> str:
        """Generate a Mininet-safe name for DockerP4AP instances that require numeric suffixes."""
        if not base_name:
            base_name = 'ap'

        if any(char.isdigit() for char in base_name):
            return base_name[:MININET_NAME_MAX_LEN]

        sanitized = re.sub(r'[^a-zA-Z0-9]', '', base_name.lower()) or 'ap'
        seed = int(hashlib.sha1(base_name.encode()).hexdigest(), 16)

        for attempt in range(0, 100):
            suffix = str((seed + attempt) % 10000).zfill(2)
            prefix_len = max(1, MININET_NAME_MAX_LEN - len(suffix))
            prefix = sanitized[:prefix_len] or 'ap'
            candidate = f"{prefix}{suffix}"
            candidate = candidate[:MININET_NAME_MAX_LEN]

            if not self._name_exists(candidate):
                return candidate

        raise RuntimeError(f"Unable to allocate runtime name for dockerized AP '{base_name}' after multiple attempts")

    def _get_device_info(self, identifier: str):
        """Retrieve device metadata by original or runtime identifier."""
        if not identifier:
            return None

        info = self.devices.get(identifier)
        if info:
            return info

        for device_info in self.devices.values():
            props = device_info.get('properties', {}) or {}
            runtime_name = props.get('runtime_name')
            aliases = props.get('aliases', [])
            if runtime_name == identifier or identifier in aliases:
                return device_info

        return None
    def _collect_device_state(self):
        """Gather lightweight device metadata for external consumers."""
        devices_state = {}
        if not self.devices:
            return devices_state

        for name, info in self.devices.items():
            node = info.get('node')
            pid = None
            if node is not None:
                try:
                    pid = getattr(node, 'pid', None)
                except Exception as exc:
                    logger.debug(f"Unable to read PID for device {name}: {exc}")

            devices_state[name] = {
                'type': info.get('type', 'unknown'),
                'pid': pid,
                'properties': info.get('properties', {})
            }

        return devices_state

    def _persist_state(self):
        """Persist current emulation summary to a shared state file."""
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            state = {
                'status': self.status,
                'emulation_id': self.emulation_id,
                'topology_id': self.topology_id,
                'timestamp': time.time(),
                'devices': self._collect_device_state()
            }

            tmp_path = f"{STATE_FILE}.tmp"
            with open(tmp_path, 'w') as handle:
                json.dump(state, handle, indent=2)
            os.replace(tmp_path, STATE_FILE)
        except Exception as exc:
            logger.warning(f"Failed to persist emulation state: {exc}")

    def start_emulation(self, topology_id, topology, options):
        """Start a new emulation instance (serialized)."""
        with self._lifecycle_lock:
            if self.status == "starting":
                return {
                    'success': False,
                    'message': 'Emulation start already in progress',
                    'emulation_id': self.emulation_id or ''
                }
            if self.status == "running" and self.net is not None:
                return {
                    'success': True,
                    'message': 'Emulation already running',
                    'emulation_id': self.emulation_id or ''
                }

            self.status = "starting"
            self._persist_state()
            return self._start_emulation_locked(topology_id, topology, options)

    def _start_emulation_locked(self, topology_id, topology, options):
        """Start a new emulation instance (callers must hold `_lifecycle_lock`)."""
        try:
            # Clean up any previous Mininet state before starting a new one
            logger.info("Running Mininet cleanup to ensure a clean environment...")
            cleanup()

            self.topology_id = topology_id
            self.emulation_id = f"emu-{topology_id}-{int(time.time())}"

            # IMPORTANT: never delete all `mn.*` containers globally; that breaks other
            # concurrently-running topologies. Only remove containers derived from
            # this topology's dockerized node runtime names.
            self._cleanup_docker_containers_for_topology(topology)

            logger.info("Mininet cleanup complete.")

            # Ensure devices without an explicit IP get a deterministic default.
            # Mininet assigns IPs automatically for regular hosts, but dockerized nodes
            # (Docker/DockerSta/DockerAP) often end up without L3 config unless we set it.
            try:
                self._auto_assign_missing_ips(topology)
            except Exception as exc:
                logger.warning(f"Auto IP assignment failed: {exc}")

            # Check if wireless devices are present
            self.is_wifi_enabled = self._has_wireless_devices(topology)

            logger.info(
                "Initializing Containernet (WiFi enabled: %s)",
                "yes" if self.is_wifi_enabled else "no"
            )

            # Use Containernet for the emulation container. Some environments ship a Containernet build
            # without Mininet-WiFi extensions (no addStation/addAccessPoint/configureWifiNodes). In that
            # case, we transparently fall back to a wired emulation (AP->switch, STA->host) so the
            # topology still starts instead of failing mid-build.
            self.net = Containernet(
                topo=None,
                build=False,
                controller=None,
                autoSetMacs=True,
                autoStaticArp=True
            )

            if self.is_wifi_enabled:
                required = ("addAccessPoint", "addStation", "configureWifiNodes", "setPropagationModel")
                missing = [m for m in required if not hasattr(self.net, m)]
                if missing:
                    logger.warning(
                        "WiFi devices detected but this Containernet build lacks WiFi support (%s). "
                        "Falling back to wired emulation for AP/STA nodes.",
                        ", ".join(missing),
                    )
                    self.is_wifi_enabled = False

            self.net_wifi = self.net if self.is_wifi_enabled else None

            # Build topology from definition
            self._build_topology(topology)

            # Mininet-WiFi topologies often omit explicit STA<->AP links and rely on association logic.
            # If WiFi support is missing/partial, stations can end up with no interfaces and the build
            # can fail. Auto-create STA<->AP links when absent to keep these topologies functional.
            try:
                self._auto_link_stations_to_access_points(topology)
            except Exception as exc:
                logger.warning("Auto-linking stations to APs failed: %s", exc)

            # Configure WiFi if enabled
            if self.is_wifi_enabled:
                logger.info("Configuring WiFi network...")
                try:
                    self.net.configureWifiNodes()
                    # Set propagation model
                    self.net.setPropagationModel(model="logDistance", exp=4)
                    logger.info("WiFi propagation model configured")
                except Exception as e:
                    logger.warning(f"Could not set propagation model: {e}")

            # Create queued links now that devices (and WiFi) are initialized
            self._apply_pending_links()

            # Start the network
            # Build network without static ARP to avoid issues with devices that have no interfaces
            try:
                self.net.build()
            except AttributeError as e:
                if "'NoneType' object has no attribute 'IP'" in str(e):
                    logger.warning(f"Some devices have no interfaces, retrying build without static ARP: {e}")
                    if getattr(self.net, 'autoStaticArp', True):
                        self.net.autoStaticArp = False
                        try:
                            self.net.build()
                        except Exception as retry_exc:
                            logger.error(f"Retrying network build without static ARP failed: {retry_exc}")
                            raise
                    else:
                        raise
                else:
                    raise

            # Add controllers if defined
            for controller in topology.controllers:
                self._add_controller(controller)

            self.net.start()
            
            # Post-start WiFi configuration
            if self.is_wifi_enabled:
                logger.info("Applying post-start WiFi configuration...")
                try:
                    # Plot graph if available (optional, may fail in headless)
                    # self.net.plotGraph(max_x=500, max_y=500)
                    pass
                except Exception as e:
                    logger.debug(f"Could not plot WiFi graph: {e}")

            # Apply device-level configuration now that the network is up
            self._apply_post_start_configuration()

            self.start_time = time.time()
            self.status = 'running'
            self._persist_state()

            logger.info(f"Emulation {self.emulation_id} started successfully")

            return {
                'success': True,
                'message': 'Emulation started successfully',
                'emulation_id': self.emulation_id
            }

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Failed to start emulation: {error_msg}", exc_info=True)
            # Best-effort cleanup: avoid leaving host Docker containers behind when
            # topology build fails mid-way (common when resources are tight or a node
            # creation errors out). Without this, subsequent restarts may fail with
            # container name/port conflicts.
            try:
                if self.net is not None:
                    try:
                        self.net.stop()
                    except Exception as stop_exc:
                        logger.warning("Failed to stop partial network after start failure: %s", stop_exc)
            finally:
                try:
                    self._cleanup_docker_containers_for_topology(topology)
                except Exception:
                    pass
                try:
                    from mininet.clean import cleanup as mn_cleanup

                    mn_cleanup()
                except Exception:
                    pass
                self.net = None
                self.net_wifi = None
                self.devices.clear()
                self.links.clear()
            self.status = 'error'
            self._persist_state()
            return {
                'success': False,
                'message': error_msg if error_msg and error_msg != '0' else f"Network startup failed: {type(e).__name__}",
                'emulation_id': ''
            }

    def _auto_assign_missing_ips(self, topology) -> None:
        """
        Assign IPv4 addresses to L3-capable nodes when missing.
        Uses 10.0.0.0/8 to stay compatible with Mininet defaults.
        """
        try:
            devices = list(getattr(topology, "devices", []) or [])
        except Exception:
            return

        used: set[str] = set()
        for dev in devices:
            try:
                props = getattr(dev, "properties", None)
                if not props:
                    continue
                ip_raw = props.get("ip") or ""
                ip = str(ip_raw).strip()
                if not ip:
                    continue
                used.add(ip.split("/", 1)[0])
            except Exception:
                continue

        def _needs_ip(dev) -> bool:
            try:
                dt = str(getattr(dev, "type", "") or "").strip().lower()
            except Exception:
                return False
            return dt in ("host", "h", "router", "r", "station", "sta", "docker", "container")

        next_octet = 1
        for dev in devices:
            if not _needs_ip(dev):
                continue
            props = getattr(dev, "properties", None)
            if props is None:
                continue
            existing = str((props.get("ip") or "")).strip()
            if existing:
                continue

            while next_octet < 255 and f"10.0.0.{next_octet}" in used:
                next_octet += 1
            if next_octet >= 255:
                break
            addr = f"10.0.0.{next_octet}"
            props["ip"] = f"{addr}/8"
            used.add(addr)
            next_octet += 1

    def stop_emulation(self, emulation_id, cleanup=True):
        """Stop the running emulation (serialized)."""
        with self._lifecycle_lock:
            return self._stop_emulation_locked(emulation_id, cleanup=cleanup)

    def _stop_emulation_locked(self, emulation_id, cleanup=True):
        """Stop the running emulation (callers must hold `_lifecycle_lock`)."""
        try:
            if self.net is None:
                return {
                    'success': False,
                    'message': 'No emulation is running'
                }

            if emulation_id != self.emulation_id:
                return {
                    'success': False,
                    'message': f'Emulation ID mismatch: {emulation_id} != {self.emulation_id}'
                }

            logger.info(f"Stopping emulation {self.emulation_id}")

            # Stop the network
            self.net.stop()

            if cleanup:
                logger.info("Performing thorough cleanup...")

                # Ensure dockerized nodes created via Containernet are removed from the host.
                # (Containernet's cleanup is not always reliable under errors/timeouts.)
                try:
                    import subprocess

                    docker_names: list[str] = []
                    for device_info in (self.devices or {}).values():
                        props = device_info.get("properties", {}) or {}
                        runtime_name = props.get("runtime_name")
                        if not runtime_name:
                            continue

                        dockerized = props.get("dockerized", False)
                        if isinstance(dockerized, str):
                            dockerized = dockerized.strip().lower() in ("true", "1", "yes")

                        if dockerized or props.get("docker_image") or props.get("image"):
                            docker_names.append(f"mn.{runtime_name}")

                    docker_names = sorted(set([name for name in docker_names if name]))
                    if docker_names:
                        subprocess.run(
                            ["docker", "rm", "-f", *docker_names],
                            timeout=120,
                            capture_output=True,
                            text=True,
                        )
                        logger.info("Removed %s dockerized mn.* containers during stop", len(docker_names))
                except Exception as exc:
                    logger.warning("Failed to cleanup dockerized node containers during stop: %s", exc)

                # Use Mininet's cleanup utility to remove leftover interfaces
                # This is equivalent to running 'mn -c'
                try:
                    from mininet.clean import cleanup as mn_cleanup
                    logger.info("Running Mininet cleanup to remove leftover interfaces...")
                    mn_cleanup()
                    logger.info("Mininet cleanup completed")
                except Exception as cleanup_err:
                    logger.warning(f"Mininet cleanup encountered an issue: {cleanup_err}")

                self.net = None
                self.net_wifi = None
                self.devices.clear()
                self.links.clear()

            self.status = 'stopped'
            self._persist_state()

            logger.info(f"Emulation {self.emulation_id} stopped successfully")

            return {
                'success': True,
                'message': 'Emulation stopped successfully'
            }

        except Exception as e:
            logger.error(f"Failed to stop emulation: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def pause_emulation(self, emulation_id):
        """Pause the emulation"""
        try:
            if self.status != 'running':
                return {
                    'success': False,
                    'message': f'Cannot pause emulation in state: {self.status}'
                }

            # Pause by disabling all interfaces
            for device_name in self.devices:
                device = self.net.get(device_name)
                if device:
                    for intf in device.intfList():
                        device.cmd(f'ip link set {intf.name} down')

            self.status = 'paused'
            self._persist_state()
            logger.info(f"Emulation {self.emulation_id} paused")

            return {
                'success': True,
                'message': 'Emulation paused successfully'
            }

        except Exception as e:
            logger.error(f"Failed to pause emulation: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def resume_emulation(self, emulation_id):
        """Resume a paused emulation"""
        try:
            if self.status != 'paused':
                return {
                    'success': False,
                    'message': f'Cannot resume emulation in state: {self.status}'
                }

            # Resume by enabling all interfaces
            for device_name in self.devices:
                device = self.net.get(device_name)
                if device:
                    for intf in device.intfList():
                        device.cmd(f'ip link set {intf.name} up')

            self.status = 'running'
            self._persist_state()
            logger.info(f"Emulation {self.emulation_id} resumed")

            return {
                'success': True,
                'message': 'Emulation resumed successfully'
            }

        except Exception as e:
            logger.error(f"Failed to resume emulation: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def get_status(self, emulation_id):
        """Get emulation status"""
        if emulation_id != self.emulation_id:
            raise ValueError(f'Emulation ID mismatch: {emulation_id} != {self.emulation_id}')

        uptime = 0
        if self.start_time and self.status == 'running':
            uptime = int(time.time() - self.start_time)

        return {
            'status': self.status,
            'uptime_seconds': uptime,
            'device_count': len(self.devices),
            'link_count': len(self.links),
            'metadata': {
                'topology_id': self.topology_id or '',
                'emulation_id': self.emulation_id or '',
                'wifi_enabled': str(self.is_wifi_enabled)
            }
        }

    def _has_wireless_devices(self, topology):
        """Check if topology contains wireless devices"""
        for device in topology.devices:
            device_type = device.type.lower()
            if device_type in ['ap', 'sta', 'accesspoint', 'station']:
                logger.info(f"Detected WiFi device: {device.name} (type: {device_type})")
                return True
        return False

    def _build_topology(self, topology):
        """Build topology from definition"""
        logger.info(f"Building topology with {len(topology.devices)} devices and {len(topology.links)} links")

        # Create a mapping from node IDs to device names
        # This handles cases where frontend uses node IDs but we need device names
        self.node_id_to_name = {}
        
        # Add devices first and build the mapping
        for device in topology.devices:
            # Extract node ID from properties if it exists
            node_identifier = (
                device.properties.get('node_id')
                or device.properties.get('id')
                or getattr(device, 'id', '')
            )
            if node_identifier:
                self.register_node_mapping(node_identifier, device.name)
            else:
                # Ensure device name maps to itself even if no identifier is supplied
                self.register_node_mapping(device.name, device.name)

            logger.info(f"Processing device: name={device.name}, type={device.type}, properties={dict(device.properties)}")
            self._add_device(device)

        logger.info(f"Node ID to Name mapping created: {json.dumps(self.node_id_to_name, indent=2)}")

        # Store links to be processed after wireless configuration (if any)
        self.pending_links = list(topology.links)
        for link in self.pending_links:
            logger.info(f"Queued link for creation after device initialization: {link.node1} <-> {link.node2}")

    def _auto_link_stations_to_access_points(self, topology) -> None:
        """
        Ensure STA nodes are connected to an AP when the topology definition doesn't include explicit
        STA<->AP links (common in Mininet-WiFi examples). In wired fallback mode this becomes a normal
        link; in WiFi mode it becomes a WirelessLink via `_add_link()`.
        """
        if not getattr(self, "pending_links", None):
            self.pending_links = []

        aps = []
        stations = []
        for device in getattr(topology, "devices", []):
            dtype = str(getattr(device, "type", "") or "").lower()
            if dtype in ("ap", "accesspoint"):
                aps.append(device)
            elif dtype in ("station", "sta"):
                stations.append(device)

        if not aps or not stations:
            return

        def _resolve(node_id_or_name: str) -> str:
            try:
                return self.node_id_to_name.get(node_id_or_name, node_id_or_name)
            except Exception:
                return node_id_or_name

        existing_pairs = set()
        stations_with_links = set()
        for link in list(self.pending_links):
            n1_raw = getattr(link, "node1", None)
            n2_raw = getattr(link, "node2", None)
            if not n1_raw or not n2_raw:
                continue
            n1 = _resolve(str(n1_raw))
            n2 = _resolve(str(n2_raw))
            existing_pairs.add(tuple(sorted((n1, n2))))
            stations_with_links.add(n1)
            stations_with_links.add(n2)

        ap_by_ssid: Dict[str, object] = {}
        for ap in aps:
            props = getattr(ap, "properties", {}) or {}
            ssid = None
            try:
                ssid = props.get("ssid")
            except Exception:
                ssid = None
            if ssid:
                ap_by_ssid.setdefault(str(ssid), ap)

        for sta in stations:
            sta_name = str(getattr(sta, "name", "") or "")
            if not sta_name:
                continue

            if sta_name in stations_with_links:
                continue

            props = getattr(sta, "properties", {}) or {}

            preferred_ap = None
            try:
                explicit_ap = props.get("ap") or props.get("access_point") or props.get("connect_to")
            except Exception:
                explicit_ap = None

            if explicit_ap:
                explicit_ap = str(explicit_ap)
                for candidate in aps:
                    if str(getattr(candidate, "name", "") or "") == explicit_ap:
                        preferred_ap = candidate
                        break

            if preferred_ap is None:
                try:
                    ssid = props.get("ssid")
                except Exception:
                    ssid = None
                if ssid:
                    preferred_ap = ap_by_ssid.get(str(ssid))

            if preferred_ap is None:
                preferred_ap = aps[0]

            ap_name = str(getattr(preferred_ap, "name", "") or "")
            if not ap_name:
                continue

            pair_key = tuple(sorted((_resolve(sta_name), _resolve(ap_name))))
            if pair_key in existing_pairs:
                continue

            self.pending_links.append(
                SimpleNamespace(
                    node1=sta_name,
                    node2=ap_name,
                    params=SimpleNamespace(bandwidth=0, delay=0, loss=0),
                    properties={},
                )
            )
            existing_pairs.add(pair_key)
            stations_with_links.add(sta_name)
            logger.info("Auto-added STA<->AP link: %s <-> %s", sta_name, ap_name)

    def _add_device(self, device):
        """Add a device to the network based on its type"""
        try:
            device_type = device.type.lower()
            name = device.name
            logger.info(f"Adding device in _add_device: {name} of type {device_type}")

            raw_properties = dict(device.properties)
            properties = {}
            for key, value in raw_properties.items():
                if isinstance(value, str):
                    parsed_value = None
                    try:
                        parsed_value = json.loads(value)
                    except json.JSONDecodeError:
                        list_like = value.strip()
                        if list_like.startswith('[') and list_like.endswith(']'):
                            items = [
                                item.strip().strip('\"\'')
                                for item in list_like[1:-1].split(',')
                            ]
                            parsed_value = [item for item in items if item]
                    properties[key] = parsed_value if parsed_value is not None else value
                else:
                    properties[key] = value

            logger.info(f"Adding device: {name} of type: {device_type} with properties={properties}")

            # Check if device should be dockerized
            is_dockerized = properties.get('dockerized', False)
            if isinstance(is_dockerized, str):
                is_dockerized = is_dockerized.lower() in ['true', '1', 'yes']

            if device_type in ['host', 'h']:
                if is_dockerized:
                    # Use Docker container for host
                    docker_image = properties.get('docker_image') or properties.get('image') or 'ubuntu:22.04'
                    runtime_name = self._allocate_docker_runtime_name(name, kind="h")
                    docker_kwargs = {
                        'cls': Docker,
                        'dimage': docker_image,
                        # Ensure we can restart even if a previous attempt crashed and left mn.<name> behind.
                        'rm': True,
                    }
                    publish_all_ports = properties.get('docker_publish_all_ports')
                    if publish_all_ports is None:
                        publish_all_ports = properties.get('publish_all_ports')
                    if isinstance(publish_all_ports, str):
                        publish_all_ports = publish_all_ports.strip().lower() in ('true', '1', 'yes')
                    docker_kwargs['publish_all_ports'] = bool(publish_all_ports) if publish_all_ports is not None else False
                    ip_value = properties.get('ip')
                    if ip_value:
                        docker_kwargs['ip'] = ip_value
                    mac_value = properties.get('mac')
                    if mac_value:
                        docker_kwargs['mac'] = mac_value
                    command = properties.get('docker_command') or properties.get('command')
                    if command:
                        if isinstance(command, str):
                            docker_kwargs['dcmd'] = command
                        elif isinstance(command, (list, tuple)):
                            docker_kwargs['dcmd'] = ' '.join(str(part) for part in command)

                    environment = self._normalize_environment(
                        properties.get('docker_environment') or properties.get('environment'),
                        name
                    )
                    if docker_image and 'localai' in str(docker_image).lower():
                        if not environment:
                            environment = {}
                        environment.setdefault('DISABLE_AUTODOWNLOAD', 'true')
                    if environment:
                        docker_kwargs['environment'] = environment

                    # Label dockerized nodes so Portainer/ops can associate them with this topology.
                    try:
                        labels = docker_kwargs.get('labels')
                        if not isinstance(labels, dict):
                            labels = {}
                        labels.setdefault("caduceus.topology_id", str(self.topology_id))
                        labels.setdefault("caduceus.role", "emulation_device")
                        labels.setdefault("caduceus.device_name", str(name))
                        labels.setdefault("caduceus.runtime_name", str(runtime_name))
                        docker_kwargs['labels'] = labels
                    except Exception:
                        pass

                    volumes = properties.get('docker_volumes') or properties.get('volumes')
                    if volumes:
                        docker_kwargs['volumes'] = volumes

                    published_ports = properties.get('docker_ports') or properties.get('published_ports')
                    if published_ports:
                        # Containernet's Docker host expects:
                        # - `ports`: list of container ports to expose (e.g., ["8080/tcp"])
                        # - `port_bindings`: mapping container_port -> host_port (e.g., {"8080/tcp": 32778})
                        # Passing docker-py's `ports={...}` shape breaks because it is forwarded to the low-level
                        # API as `ExposedPorts` (nat.PortSet) which expects `{ "8080/tcp": {} }`.
                        if isinstance(published_ports, dict):
                            ports_list = []
                            port_bindings = {}
                            for container_port, host_binding in published_ports.items():
                                if not container_port:
                                    continue
                                ports_list.append(container_port)
                                port_bindings[container_port] = host_binding
                            if ports_list:
                                docker_kwargs['ports'] = ports_list
                                docker_kwargs['port_bindings'] = port_bindings
                                docker_kwargs['publish_all_ports'] = False
                        elif isinstance(published_ports, (list, tuple)):
                            docker_kwargs['ports'] = list(published_ports)

                    logger.info("Creating dockerized host %s (runtime: %s) with kwargs: %s", name, runtime_name, docker_kwargs)
                    host = self._add_docker_node(runtime_name, docker_kwargs)

                    if runtime_name != name:
                        self.register_node_mapping(name, runtime_name)
                        node_identifier = properties.get('node_id') or properties.get('id')
                        device_identifier = getattr(device, 'id', None)
                        for identifier in (node_identifier, device_identifier):
                            if identifier:
                                self.register_node_mapping(identifier, runtime_name)

                    augmented_properties = {**properties, 'runtime_name': runtime_name}
                    self.devices[name] = {'type': 'host', 'node': host, 'properties': augmented_properties}
                    logger.info("Added dockerized host: %s (runtime: %s, image: %s)", name, runtime_name, docker_image)
                else:
                    # Regular host
                    default_route = properties.get('default_route') or properties.get('defaultRoute')
                    # Important: do NOT pass ip=None explicitly; it disables Mininet's auto IP assignment.
                    host_kwargs = {}
                    ip_value = properties.get('ip')
                    if ip_value:
                        host_kwargs['ip'] = ip_value
                    mac_value = properties.get('mac')
                    if mac_value:
                        host_kwargs['mac'] = mac_value
                    if default_route:
                        host_kwargs['defaultRoute'] = default_route
                    host = self.net.addHost(name, **host_kwargs)
                    self.devices[name] = {'type': 'host', 'node': host, 'properties': properties}
                    logger.info(f"Added host: {name}")

            elif device_type in ['switch', 's', 'ovs', 'ovsswitch']:
                dpid_value = properties.get('dpid') or properties.get('datapath_id')
                normalized_dpid = self._normalize_dpid(dpid_value, properties.get('node_id') or name)
                switch = self.net.addSwitch(
                    name,
                    cls=OVSKernelSwitch,
                    dpid=normalized_dpid
                )
                properties['dpid'] = normalized_dpid
                self.devices[name] = {'type': 'switch', 'node': switch, 'properties': properties}
                logger.info(f"Added switch: {name}")

            elif device_type in ['router', 'r']:
                # Routers are L3-capable hosts; ensure we apply IP/MAC/defaultRoute if provided/auto-assigned.
                # Important: do NOT pass ip=None explicitly; it disables Mininet's auto IP assignment.
                router_kwargs = {}
                ip_value = properties.get('ip')
                if ip_value:
                    router_kwargs['ip'] = ip_value
                mac_value = properties.get('mac')
                if mac_value:
                    router_kwargs['mac'] = mac_value
                default_route = properties.get('default_route') or properties.get('defaultRoute')
                if default_route:
                    router_kwargs['defaultRoute'] = default_route
                router = self.net.addHost(name, **router_kwargs)
                properties['protocols'] = self._split_property_list(properties.get('protocols', []))
                self.devices[name] = {'type': 'router', 'node': router, 'properties': properties}
                logger.info(f"Added router: {name}")

            elif device_type in ['ap', 'accesspoint']:
                if not self.is_wifi_enabled:
                    logger.warning(f"WiFi device '{name}' found but WiFi not enabled, adding as switch")

                    # Preserve deterministic datapath IDs so controllers (e.g. ONOS) don't collapse
                    # multiple switches into a single device due to duplicate/random DPIDs.
                    dpid_value = properties.get('dpid') or properties.get('datapath_id')
                    normalized_dpid = self._normalize_dpid(dpid_value, properties.get('node_id') or name)
                    properties['dpid'] = normalized_dpid

                    # Most controller setups in this project expect OF1.3 by default.
                    properties.setdefault('openflow_version', '1.3')

                    switch = self.net.addSwitch(name, cls=OVSKernelSwitch, dpid=normalized_dpid)
                    self.devices[name] = {'type': 'switch', 'node': switch, 'properties': properties}
                    return

                ssid = properties.get('ssid', name)
                channel = properties.get('channel', '1')
                mode = properties.get('mode', 'g')

                ap_kwargs = {
                    'ssid': ssid,
                    'mode': mode,
                    'channel': channel
                }

                mac_address = properties.get('mac')
                if mac_address:
                    ap_kwargs['mac'] = mac_address

                passwd = properties.get('password') or properties.get('passwd') or properties.get('psk')
                security = properties.get('security')
                if security and security.lower() != 'open' and passwd:
                    ap_kwargs['encrypt'] = security
                    ap_kwargs['passwd'] = passwd

                position = properties.get('position') or properties.get('coordinates')
                if position:
                    try:
                        if isinstance(position, str):
                            coords = [float(coord.strip()) for coord in position.split(',')]
                        else:
                            coords = [float(value) for value in position]
                        if len(coords) == 3:
                            ap_kwargs['position'] = ','.join(str(coord) for coord in coords)
                    except Exception as exc:
                        logger.warning(f"Failed to parse position for AP {name}: {exc}")

                dpid_input = properties.get('dpid') or properties.get('datapath_id')
                normalized_dpid = self._normalize_dpid(dpid_input, properties.get('node_id') or name)
                ap_kwargs['dpid'] = normalized_dpid
                properties['dpid'] = normalized_dpid

                if is_dockerized:
                    # Note: DockerP4AP has compatibility issues with controlIntf
                    # Using regular dockerized host instead for AP functionality
                    logger.warning(f"Dockerized AP '{name}' will be created as a Docker host (DockerP4AP not fully supported)")
                    docker_image = properties.get('docker_image') or properties.get('image') or 'ubuntu:22.04'

                    docker_kwargs = {
                        'cls': Docker,
                        'dimage': docker_image,
                        'rm': True,
                    }
                    ip_value = properties.get('ip')
                    if ip_value:
                        docker_kwargs['ip'] = ip_value
                    mac_value = properties.get('mac') or mac_address
                    if mac_value:
                        docker_kwargs['mac'] = mac_value

                    docker_command = properties.get('docker_command') or properties.get('command')
                    if docker_command:
                        if isinstance(docker_command, (list, tuple)):
                            docker_kwargs['dcmd'] = ' '.join(str(part) for part in docker_command)
                        else:
                            docker_kwargs['dcmd'] = str(docker_command)

                    environment = self._normalize_environment(
                        properties.get('docker_environment') or properties.get('environment'),
                        name
                    )
                    if docker_image and 'localai' in str(docker_image).lower():
                        if not environment:
                            environment = {}
                        environment.setdefault('DISABLE_AUTODOWNLOAD', 'true')
                    if environment:
                        docker_kwargs['environment'] = environment

                    volumes = properties.get('docker_volumes') or properties.get('volumes')
                    if volumes:
                        docker_kwargs['volumes'] = volumes

                    # Create as Docker host instead of DockerP4AP
                    runtime_name = self._allocate_docker_runtime_name(name, kind="a")
                    ap = self._add_docker_node(runtime_name, docker_kwargs)

                    if runtime_name != name:
                        self.register_node_mapping(name, runtime_name)
                        node_identifier = properties.get('node_id') or properties.get('id')
                        device_identifier = getattr(device, 'id', None)
                        for identifier in (node_identifier, device_identifier):
                            if identifier:
                                self.register_node_mapping(identifier, runtime_name)

                    augmented_properties = {
                        **properties,
                        'docker_image': docker_image,
                        'runtime_name': runtime_name
                    }
                    self.devices[name] = {'type': 'ap', 'node': ap, 'properties': augmented_properties}
                    logger.info(f"Added dockerized AP: {name} (runtime: {runtime_name}, SSID: {ssid}, Mode: {mode}, Channel: {channel}, Image: {docker_image})")
                else:
                    # Regular AP
                    ap = self.net.addAccessPoint(name, **ap_kwargs)
                    self.devices[name] = {'type': 'ap', 'node': ap, 'properties': {**properties, 'runtime_name': name}}
                    logger.info(f"Added AP: {name} (SSID: {ssid}, Mode: {mode}, Channel: {channel})")

            elif device_type in ['station', 'sta']:
                if not self.is_wifi_enabled:
                    logger.warning(f"WiFi device '{name}' found but WiFi not enabled, adding as host")
                    host_kwargs = {}
                    station_ip = properties.get('ip')
                    if station_ip:
                        host_kwargs['ip'] = station_ip
                    station_mac = properties.get('mac')
                    if station_mac:
                        host_kwargs['mac'] = station_mac
                    default_route = properties.get('default_route') or properties.get('defaultRoute')
                    if default_route:
                        host_kwargs['defaultRoute'] = default_route

                    host = self.net.addHost(name, **host_kwargs)
                    self.devices[name] = {'type': 'host', 'node': host, 'properties': properties}
                    logger.info(
                        "Added station-as-host: %s%s",
                        name,
                        f" (IP: {station_ip})" if station_ip else "",
                    )
                    return

                station_kwargs = {}

                station_ip = properties.get('ip')
                if station_ip:
                    station_kwargs['ip'] = station_ip

                station_mac = properties.get('mac')
                if station_mac:
                    station_kwargs['mac'] = station_mac

                passwd = properties.get('password') or properties.get('passwd') or properties.get('psk')
                security = properties.get('security')
                if security and security.lower() != 'open' and passwd:
                    station_kwargs['encrypt'] = security
                    station_kwargs['passwd'] = passwd

                if is_dockerized:
                    # Use DockerSta for dockerized station
                    docker_image = (
                        properties.get('docker_image')
                        or properties.get('image')
                        or 'ubuntu:22.04'
                    )
                    runtime_name = self._allocate_docker_runtime_name(name, kind="w")

                    docker_command = properties.get('docker_command') or properties.get('command')
                    if docker_command:
                        if isinstance(docker_command, (list, tuple)):
                            station_kwargs['dcmd'] = ' '.join(str(part) for part in docker_command)
                        else:
                            station_kwargs['dcmd'] = str(docker_command)

                    environment = self._normalize_environment(
                        properties.get('docker_environment') or properties.get('environment'),
                        name
                    )
                    if docker_image and 'localai' in str(docker_image).lower():
                        if not environment:
                            environment = {}
                        environment.setdefault('DISABLE_AUTODOWNLOAD', 'true')
                    if environment:
                        station_kwargs['environment'] = environment

                    volumes = properties.get('docker_volumes') or properties.get('volumes')
                    if volumes:
                        station_kwargs['volumes'] = volumes

                    station_kwargs.setdefault('rm', True)

                    station = self.net.addStation(
                        runtime_name,
                        cls=DockerSta,
                        dimage=docker_image,
                        **station_kwargs
                    )

                    position = properties.get('position') or properties.get('coordinates')
                    if position:
                        try:
                            if isinstance(position, str):
                                coords = [float(coord.strip()) for coord in position.split(',')]
                            else:
                                coords = [float(value) for value in position]
                            if len(coords) == 3:
                                station.setPosition(','.join(str(coord) for coord in coords))
                        except Exception as exc:
                            logger.warning(f"Failed to set station position for {name}: {exc}")

                    self.devices[name] = {
                        'type': 'station',
                        'node': station,
                        'properties': {**properties, 'docker_image': docker_image, 'runtime_name': runtime_name}
                    }
                    if runtime_name != name:
                        self.register_node_mapping(name, runtime_name)
                        node_identifier = properties.get('node_id') or properties.get('id')
                        device_identifier = getattr(device, 'id', None)
                        for identifier in (node_identifier, device_identifier):
                            if identifier:
                                self.register_node_mapping(identifier, runtime_name)
                    logger.info(
                        f"Added dockerized station: {name}"
                        + (f" (IP: {station_ip})" if station_ip else "")
                        + f" (image: {docker_image})"
                    )
                else:
                    # Use regular Station
                    station = self.net.addStation(name, **station_kwargs)

                    position = properties.get('position') or properties.get('coordinates')
                    if position:
                        try:
                            if isinstance(position, str):
                                coords = [float(coord.strip()) for coord in position.split(',')]
                            else:
                                coords = [float(value) for value in position]
                            if len(coords) == 3:
                                station.setPosition(','.join(str(coord) for coord in coords))
                        except Exception as exc:
                            logger.warning(f"Failed to set station position for {name}: {exc}")

                    self.devices[name] = {'type': 'station', 'node': station, 'properties': properties}
                    logger.info(f"Added station: {name}" + (f" (IP: {station_ip})" if station_ip else ""))

            elif device_type in ['p4switch', 'bmv2']:
                from p4_switch import P4BMv2Switch

                def _as_int(value, default):
                    try:
                        if value is None:
                            return default
                        if isinstance(value, bool):
                            return int(value)
                        return int(str(value).strip())
                    except Exception:
                        return default

                program_id = properties.get('p4_program_id') or properties.get('program_id')
                json_path = (
                    properties.get('device_config_path')
                    or properties.get('json_path')
                    or properties.get('bmv2_json')
                )
                p4info_path = properties.get('p4info_path') or properties.get('p4info_file')

                if not json_path and program_id:
                    storage_root = os.getenv("P4_STORAGE_ROOT", "/var/lib/caduceus/p4")
                    json_path = os.path.join(storage_root, str(program_id), f"{program_id}.json")
                    p4info_path = os.path.join(storage_root, str(program_id), f"{program_id}.p4info.txt")
                    properties['device_config_path'] = json_path
                    properties['p4info_path'] = p4info_path

                seed = int(hashlib.sha1(name.encode()).hexdigest()[:8], 16)
                device_id = _as_int(properties.get('device_id') or properties.get('bmv2_device_id'), seed % 1024)
                grpc_port = _as_int(properties.get('grpc_port'), 9559 + (seed % 1000))
                thrift_port = _as_int(properties.get('thrift_port'), 9090 + (seed % 1000))

                switch = self.net.addSwitch(
                    name,
                    cls=P4BMv2Switch,
                    json_path=json_path,
                    p4info_path=p4info_path,
                    grpc_port=grpc_port,
                    thrift_port=thrift_port,
                    device_id=device_id,
                )
                properties['device_id'] = device_id
                properties['grpc_port'] = grpc_port
                properties['thrift_port'] = thrift_port
                self.devices[name] = {'type': 'p4switch', 'node': switch, 'properties': properties}
                logger.info("Added P4 switch: %s (grpc=%s thrift=%s program=%s)", name, grpc_port, thrift_port, program_id)

            elif device_type in ['controller']:
                # Controller nodes are modeled in the topology/UI, but they are not data-plane Mininet nodes.
                # Store as a placeholder so link creation can safely ignore controller links.
                self.devices[name] = {'type': 'controller', 'node': None, 'properties': {**properties, 'runtime_name': name}}
                logger.info("Registered controller placeholder device %s (no Mininet node created)", name)
                return

            else:
                logger.warning(f"Unsupported device type '{device_type}' for device '{name}', adding as host")
                host = self.net.addHost(name)
                self.devices[name] = {'type': 'host', 'node': host, 'properties': properties}

        except Exception as e:
            import traceback
            logger.error(f"Failed to add device {device.name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _split_property_list(self, value):
        """Normalize property values that may be stored as JSON strings."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in re.split(r'[\n,;]+', value) if item.strip()]
        return []

    def _normalize_docker_command(self, command):
        """Allow Dockerfile-style ENTRYPOINT/CMD syntax or raw lists."""
        if not command:
            return None

        def join_parts(parts):
            return ' '.join(str(part).strip() for part in parts if str(part).strip())

        if isinstance(command, (list, tuple)):
            return join_parts(command)

        if isinstance(command, str):
            cmd = command.strip()
            if not cmd:
                return None

            match = re.match(r'^(ENTRYPOINT|CMD)\s+(.*)$', cmd, flags=re.IGNORECASE)
            if match:
                cmd = match.group(2).strip()

            if cmd.startswith('[') and cmd.endswith(']'):
                try:
                    try:
                        parsed = json.loads(cmd)
                    except json.JSONDecodeError:
                        parsed = ast.literal_eval(cmd)
                    if isinstance(parsed, (list, tuple)):
                        return join_parts(parsed)
                except Exception as exc:
                    logger.warning(f"Failed to parse docker command list {cmd}: {exc}")
            return cmd

        return str(command)

    def _normalize_environment(self, environment, device_name):
        """Parse environment definitions supplied as dicts, strings, or lists."""
        merged_env = dict(self.host_docker_env) if self.host_docker_env else {}

        if not environment:
            return merged_env or None

        if isinstance(environment, dict):
            merged_env.update({str(key): str(value) for key, value in environment.items()})
            return merged_env

        parsed_env = None

        if isinstance(environment, str):
            candidate = environment.strip()
            if not candidate:
                return None
            # Try JSON object
            try:
                parsed_env = json.loads(candidate)
            except Exception:
                # Try Python literal or KEY=VALUE pairs
                try:
                    parsed_env = ast.literal_eval(candidate)
                except Exception:
                    kv_pairs = {}
                    for line in candidate.splitlines():
                        if '=' in line:
                            key, val = line.split('=', 1)
                            kv_pairs[key.strip()] = val.strip().strip('"').strip("'")
                    parsed_env = kv_pairs or None
        elif isinstance(environment, (list, tuple)):
            kv_pairs = {}
            for item in environment:
                if isinstance(item, str) and '=' in item:
                    key, val = item.split('=', 1)
                    kv_pairs[key.strip()] = val.strip()
            if kv_pairs:
                parsed_env = kv_pairs

        if isinstance(parsed_env, dict):
            # Ensure all values are strings for Docker
            merged_env.update({str(key): str(value) for key, value in parsed_env.items()})
            return merged_env

        logger.warning(
            "Environment for %s could not be parsed into a dict (type: %s, value: %s)",
            device_name,
            type(environment),
            environment
        )
        return merged_env or None

    def _node_supports_tc(self, node, device_info):
        """Check whether a node's namespace has the tc binary available."""
        if not node:
            return False

        node_name = getattr(node, 'name', None) or str(node)
        if node_name in self.tc_capable_cache:
            return self.tc_capable_cache[node_name]

        supports_tc = False
        try:
            cmd = getattr(node, 'cmd', None)
            if callable(cmd):
                sentinel = '__tc_present__'
                probe = f'command -v tc >/dev/null 2>&1 && echo {sentinel}'
                output = cmd(probe).strip()
                supports_tc = sentinel in output
        except Exception as exc:
            logger.debug("Failed to probe tc availability for %s: %s", node_name, exc)

        if not supports_tc:
            logger.warning(
                "tc binary not found inside %s (type=%s); link shaping will be disabled for its links",
                node_name,
                (device_info or {}).get('type', 'unknown')
            )

        self.tc_capable_cache[node_name] = supports_tc
        return supports_tc

    def _add_link(self, link):
        """Add a link between two devices"""
        try:
            # Resolve node IDs to device names using the mapping
            node1_id = link.node1
            node2_id = link.node2
            
            # Try to resolve using the mapping, fall back to original if not found
            node1_name = self.node_id_to_name.get(node1_id, node1_id)
            node2_name = self.node_id_to_name.get(node2_id, node2_id)
            
            logger.info(f"Resolving link: {node1_id} -> {node1_name}, {node2_id} -> {node2_name}")

            # Check if self.net exists
            if not self.net:
                logger.error("self.net is None in _add_link!")
                return False

            # Controller nodes are placeholders (no Mininet node). Ignore controller links.
            node1_info = self._get_device_info(node1_name) or self._get_device_info(node1_id)
            node2_info = self._get_device_info(node2_name) or self._get_device_info(node2_id)
            if ((node1_info and str(node1_info.get('type') or '').lower() == 'controller') or
                    (node2_info and str(node2_info.get('type') or '').lower() == 'controller')):
                logger.info("Skipping link involving controller placeholder: %s <-> %s", node1_name, node2_name)
                return True

            # Get nodes from Mininet
            logger.info(f"Getting node1: {node1_name} from self.net")
            try:
                node1 = self.net.get(node1_name)
            except Exception:
                node1 = None
            logger.info(f"Getting node2: {node2_name} from self.net")
            try:
                node2 = self.net.get(node2_name)
            except Exception:
                node2 = None

            # Fallback: some Containernet/Mininet versions can fail `net.get()` lookups for dockerized nodes
            # even though we have a valid node object reference stored in `self.devices`.
            if not node1:
                try:
                    node1 = (self.devices.get(node1_name) or {}).get('node')
                except Exception:
                    node1 = None
            if not node2:
                try:
                    node2 = (self.devices.get(node2_name) or {}).get('node')
                except Exception:
                    node2 = None
            
            logger.info(f"node1 result: {node1}, node2 result: {node2}")

            if not node1:
                logger.error(f"Cannot create link: node1='{node1_name}' (from ID '{node1_id}') not found in Mininet")
                logger.error(f"Available devices: {list(self.devices.keys())}")
                return False
                
            if not node2:
                logger.error(f"Cannot create link: node2='{node2_name}' (from ID '{node2_id}') not found in Mininet")
                logger.error(f"Available devices: {list(self.devices.keys())}")
                return False

            # Add link with parameters (handle None params gracefully)
            bandwidth = None
            delay = None
            loss = None

            params = getattr(link, "params", None)
            if params:
                try:
                    bandwidth_value = getattr(params, "bandwidth", 0) or 0
                    delay_value = getattr(params, "delay", 0) or 0
                    loss_value = getattr(params, "loss", 0) or 0
                    bandwidth = bandwidth_value if bandwidth_value > 0 else None
                    delay = f"{delay_value}ms" if delay_value > 0 else None
                    loss = loss_value if loss_value > 0 else None
                except Exception:
                    pass
            else:
                # Some callers may provide link-like objects without a `params` submessage.
                try:
                    bandwidth_value = float(getattr(link, "bandwidth", 0) or 0)
                    delay_value = float(getattr(link, "delay", 0) or 0)
                    loss_value = float(getattr(link, "loss", 0) or 0)
                    bandwidth = bandwidth_value if bandwidth_value > 0 else None
                    delay = f"{int(delay_value)}ms" if delay_value > 0 else None
                    loss = loss_value if loss_value > 0 else None
                except Exception:
                    pass
            
            node1_info = self._get_device_info(node1_name) or self._get_device_info(node1_id)
            node2_info = self._get_device_info(node2_name) or self._get_device_info(node2_id)

            wifi_types = {'ap', 'station', 'sta', 'accesspoint'}
            node1_is_wifi = bool(node1_info and node1_info.get('type') in wifi_types)
            node2_is_wifi = bool(node2_info and node2_info.get('type') in wifi_types)
            is_wireless_link = bool(node1_is_wifi and node2_is_wifi)
            if is_wireless_link:
                if bandwidth or delay or loss:
                    logger.info(
                        "Suppressing link shaping parameters for WiFi link %s <-> %s (bw=%s, delay=%s, loss=%s)",
                        node1_name,
                        node2_name,
                        bandwidth,
                        delay,
                        loss
                    )
                bandwidth = None
                delay = None
                loss = None
            
            logger.info(f"Creating link between {node1_name} and {node2_name} with params: bw={bandwidth}, delay={delay}, loss={loss}")
            
            # Check if self.net and addLink method exist
            if not self.net:
                logger.error("self.net is None!")
                return False
            if not hasattr(self.net, 'addLink'):
                logger.error("self.net.addLink method not found!")
                return False

            link_params = {}
            if bandwidth is not None:
                link_params['bw'] = bandwidth
            if delay is not None:
                link_params['delay'] = delay
            if loss is not None:
                link_params['loss'] = loss

            if is_wireless_link:
                link_obj = self.net.addLink(node1, node2, cls=WirelessLink)
            else:
                node1_has_tc = self._node_supports_tc(node1, node1_info)
                node2_has_tc = self._node_supports_tc(node2, node2_info)
                wired_link_cls = None

                if link_params and not (node1_has_tc and node2_has_tc):
                    missing = [name for has_tc, name in (
                        (node1_has_tc, node1_name),
                        (node2_has_tc, node2_name)
                    ) if not has_tc]
                    logger.info(
                        "Skipping bw/delay/loss parameters for link %s <-> %s because tc is unavailable on %s",
                        node1_name,
                        node2_name,
                        ', '.join(missing)
                    )
                    link_params = {}

                if not (node1_has_tc and node2_has_tc):
                    wired_link_cls = Link

                if link_params or wired_link_cls:
                    link_kwargs = dict(link_params)
                    if wired_link_cls:
                        link_kwargs['cls'] = wired_link_cls
                    link_obj = self.net.addLink(node1, node2, **link_kwargs)
                else:
                    link_obj = self.net.addLink(node1, node2)

            link_id = f"{node1_name}-{node2_name}"
            # Persist interface/port names so APIs like ListLinks can be used by orchestrator features
            # (e.g. auto-addressing for point-to-point discovery).
            try:
                port1 = getattr(getattr(link_obj, "intf1", None), "name", "") or ""
                port2 = getattr(getattr(link_obj, "intf2", None), "name", "") or ""
            except Exception:
                port1 = ""
                port2 = ""
            self.links[link_id] = {
                'node1': node1_name,
                'node2': node2_name,
                'port1': port1,
                'port2': port2,
                'link': link_obj,
                'params': link.params if hasattr(link, "params") else None,
            }
            logger.info(f"Added link: {node1_name} <-> {node2_name}")
            return True

        except Exception as e:
            logger.warning(
                f"Failed to add link {link.node1} <-> {link.node2}: {e} (allowing emulation to continue)",
                exc_info=True
            )
            return True  # Return True to allow emulation to proceed despite link failures

    def _apply_pending_links(self):
        """Instantiate any deferred links after device configuration is complete."""
        if not self.pending_links:
            return

        def _link_priority(link) -> tuple[int, str, str]:
            try:
                n1 = self.node_id_to_name.get(getattr(link, 'node1', None), getattr(link, 'node1', '')) if getattr(self, 'node_id_to_name', None) else getattr(link, 'node1', '')
                n2 = self.node_id_to_name.get(getattr(link, 'node2', None), getattr(link, 'node2', '')) if getattr(self, 'node_id_to_name', None) else getattr(link, 'node2', '')
            except Exception:
                n1 = getattr(link, 'node1', '') or ''
                n2 = getattr(link, 'node2', '') or ''

            t1 = (self.devices.get(n1, {}) or {}).get('type', '') if isinstance(self.devices, dict) else ''
            t2 = (self.devices.get(n2, {}) or {}).get('type', '') if isinstance(self.devices, dict) else ''
            t1 = str(t1 or '').lower()
            t2 = str(t2 or '').lower()

            l2_types = {'switch', 'p4switch', 'ap', 'accesspoint', 'station'}
            is_router_link = ('router' in (t1, t2)) and not (t1 in l2_types or t2 in l2_types)
            if is_router_link:
                return (0, n1, n2)
            return (1, n1, n2)

        ordered_links = sorted(list(self.pending_links), key=_link_priority)

        logger.info("Creating %d queued links", len(ordered_links))
        for link in ordered_links:
            logger.info(f"Processing deferred link: {link.node1} <-> {link.node2}")
            if not self._add_link(link):
                logger.error(
                    "Failed to create link between %s and %s (continuing)",
                    getattr(link, "node1", "?"),
                    getattr(link, "node2", "?"),
                )

        self.pending_links.clear()

    def _apply_post_start_configuration(self):
        """Apply device-specific settings that require an active network."""
        for name, info in self.devices.items():
            node = info.get('node')
            if not node:
                continue

            properties = info.get('properties', {}) or {}
            device_type = info.get('type')

            if device_type in ('host', 'station', 'docker'):
                self._configure_host_device(node, properties)
            elif device_type == 'switch':
                self._configure_switch_device(name, node, properties)
            elif device_type == 'router':
                self._configure_router_device(node, properties)

        # Best-effort fixups for direct (host/router) links:
        # Containernet/Mininet can auto-assign IPs to multi-homed nodes in a way that
        # doesn't match link wiring (e.g., a /30 ends up on the interface connected to a switch).
        # When this happens, ARP never reaches the peer and pingall shows "Destination Host Unreachable".
        try:
            self._fixup_direct_link_ips()
        except Exception as exc:
            logger.warning(f"Failed to fixup direct-link IPs: {exc}")

    def _fixup_direct_link_ips(self) -> None:
        """Ensure host/router-to-host/router links have compatible IPs on the *connected* interfaces."""
        if not self.net:
            return

        def _dtype(name: str) -> str:
            try:
                return str((self.devices.get(name, {}) or {}).get('type') or '').lower()
            except Exception:
                return ''

        def _iface_ipv4_cidr(node, ifname: str) -> str:
            out = node.cmd(f"ip -o -4 addr show dev {shlex.quote(ifname)} | awk '{{print $4}}' | head -n 1")
            return (out or '').strip()

        def _all_ifaces_ipv4(node) -> Dict[str, str]:
            out = node.cmd("ip -o -4 addr show | awk '{print $2\" \"$4}'")
            mapping: Dict[str, str] = {}
            for line in (out or '').splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) != 2:
                    continue
                mapping[parts[0]] = parts[1]
            return mapping

        def _same_subnet(a: str, b: str) -> bool:
            try:
                ia = ipaddress.ip_interface(a)
                ib = ipaddress.ip_interface(b)
                return ia.network == ib.network
            except Exception:
                return False

        for link in (self.links or {}).values():
            a = str(link.get('node1') or '')
            b = str(link.get('node2') or '')
            if not a or not b:
                continue

            ta = _dtype(a)
            tb = _dtype(b)
            if ta not in ('host', 'router') or tb not in ('host', 'router'):
                continue

            try:
                na = self.net.get(a)
                nb = self.net.get(b)
            except Exception:
                continue

            try:
                conns = na.connectionsTo(nb)  # list[(intfA, intfB)]
            except Exception:
                conns = []
            if not conns:
                continue

            all_a = _all_ifaces_ipv4(na)
            all_b = _all_ifaces_ipv4(nb)

            for intf_a, intf_b in conns:
                ifname_a = getattr(intf_a, 'name', '') or ''
                ifname_b = getattr(intf_b, 'name', '') or ''
                if not ifname_a or not ifname_b:
                    continue

                cidr_a = _iface_ipv4_cidr(na, ifname_a)
                cidr_b = _iface_ipv4_cidr(nb, ifname_b)
                if cidr_a and cidr_b and _same_subnet(cidr_a, cidr_b):
                    continue

                # If one side has a subnet, and the other side has that subnet on a different interface, swap.
                target_subnet = None
                if cidr_b:
                    try:
                        target_subnet = ipaddress.ip_interface(cidr_b).network
                    except Exception:
                        target_subnet = None

                if target_subnet:
                    alt_a_if = None
                    alt_a_cidr = None
                    for k, v in all_a.items():
                        if k == ifname_a:
                            continue
                        try:
                            if ipaddress.ip_interface(v).network == target_subnet:
                                alt_a_if, alt_a_cidr = k, v
                                break
                        except Exception:
                            continue

                    if alt_a_if and alt_a_cidr:
                        # Swap addresses between ifname_a and alt_a_if (preserve both networks).
                        if cidr_a:
                            na.cmd(f"ip addr del {shlex.quote(cidr_a)} dev {shlex.quote(ifname_a)} || true")
                        na.cmd(f"ip addr del {shlex.quote(alt_a_cidr)} dev {shlex.quote(alt_a_if)} || true")
                        na.cmd(f"ip addr add {shlex.quote(alt_a_cidr)} dev {shlex.quote(ifname_a)} || true")
                        if cidr_a:
                            na.cmd(f"ip addr add {shlex.quote(cidr_a)} dev {shlex.quote(alt_a_if)} || true")
                        logger.info(f"Fixed direct-link IP wiring for {a}<->{b}: moved {alt_a_cidr} onto {ifname_a}")
                        # refresh
                        all_a = _all_ifaces_ipv4(na)
                        cidr_a = _iface_ipv4_cidr(na, ifname_a)

                # Repeat the same check in the other direction (if A has subnet, but B has it on a different iface)
                target_subnet = None
                if cidr_a:
                    try:
                        target_subnet = ipaddress.ip_interface(cidr_a).network
                    except Exception:
                        target_subnet = None

                if target_subnet:
                    alt_b_if = None
                    alt_b_cidr = None
                    for k, v in all_b.items():
                        if k == ifname_b:
                            continue
                        try:
                            if ipaddress.ip_interface(v).network == target_subnet:
                                alt_b_if, alt_b_cidr = k, v
                                break
                        except Exception:
                            continue

                    if alt_b_if and alt_b_cidr:
                        if cidr_b:
                            nb.cmd(f"ip addr del {shlex.quote(cidr_b)} dev {shlex.quote(ifname_b)} || true")
                        nb.cmd(f"ip addr del {shlex.quote(alt_b_cidr)} dev {shlex.quote(alt_b_if)} || true")
                        nb.cmd(f"ip addr add {shlex.quote(alt_b_cidr)} dev {shlex.quote(ifname_b)} || true")
                        if cidr_b:
                            nb.cmd(f"ip addr add {shlex.quote(cidr_b)} dev {shlex.quote(alt_b_if)} || true")
                        logger.info(f"Fixed direct-link IP wiring for {a}<->{b}: moved {alt_b_cidr} onto {ifname_b}")
                        all_b = _all_ifaces_ipv4(nb)
                        cidr_b = _iface_ipv4_cidr(nb, ifname_b)

                # If still mismatched, nothing else we can do without explicit config.

    def _configure_host_device(self, host, properties):
        """Configure host-level settings such as IP, routes, and DNS."""
        try:
            intf = None
            try:
                intf = host.defaultIntf()
            except Exception:
                intf = None

            if not intf:
                logger.debug(f"Host {getattr(host, 'name', host)} has no default interface to configure")
                return

            intf_name = intf.name

            ip_address = properties.get('ip')
            if ip_address:
                host.cmd(f'ip addr flush dev {intf_name}')
                host.cmd(f'ip addr add {ip_address} dev {intf_name}')

            ipv6_address = properties.get('ip6')
            if ipv6_address:
                host.cmd(f'ip -6 addr flush dev {intf_name}')
                host.cmd(f'ip -6 addr add {ipv6_address} dev {intf_name}')

            mac_address = properties.get('mac')
            if mac_address:
                host.cmd(f'ip link set dev {intf_name} address {mac_address}')

            mtu_value = properties.get('mtu')
            if mtu_value:
                try:
                    mtu_int = int(str(mtu_value))
                    host.cmd(f'ip link set dev {intf_name} mtu {mtu_int}')
                except ValueError:
                    logger.warning(f"Invalid MTU value '{mtu_value}' for host {getattr(host, 'name', host)}")

            default_route = properties.get('default_route') or properties.get('defaultRoute')
            if default_route:
                host.cmd('ip route del default || true')
                route_spec = str(default_route).strip()
                if route_spec:
                    if ' ' in route_spec:
                        host.cmd(f'ip route add default {route_spec}')
                    else:
                        host.cmd(f'ip route add default via {route_spec}')

            for route in self._split_property_list(properties.get('static_routes', [])):
                host.cmd(f'ip route add {route} || true')

            dns_entries = self._split_property_list(properties.get('dns_servers', []))
            if dns_entries:
                host.cmd('cat /dev/null > /etc/resolv.conf')
                for entry in dns_entries:
                    nameserver_entry = f"nameserver {entry}"
                    host.cmd(f'echo {shlex.quote(nameserver_entry)} >> /etc/resolv.conf')

            startup_commands = properties.get('startup_commands')
            if startup_commands:
                if isinstance(startup_commands, list):
                    commands = [str(cmd).strip() for cmd in startup_commands if str(cmd).strip()]
                else:
                    commands = [cmd.strip() for cmd in str(startup_commands).splitlines() if cmd.strip()]
                for command in commands:
                    host.cmd(command)

        except Exception as exc:
            logger.warning(f"Failed to apply host configuration for {getattr(host, 'name', host)}: {exc}")

    def _configure_switch_device(self, name, switch, properties):
        """Apply controller and OpenFlow settings for switches."""
        try:
            controller_value = properties.get('controller')
            controller_ip = properties.get('controller_ip')
            controller_port = properties.get('controller_port')

            controller_endpoint = None
            if controller_value:
                controller_value = str(controller_value).strip()
                if controller_value:
                    controller_endpoint = controller_value
            elif controller_ip:
                controller_endpoint = f"{controller_ip}:{controller_port or 6653}"

            if controller_endpoint:
                parts = controller_endpoint.split(':')
                ctrl_ip = parts[0]
                ctrl_port = int(parts[1]) if len(parts) > 1 else 6653
                resolved_ip = ctrl_ip
                try:
                    ipaddress.ip_address(ctrl_ip)
                except ValueError:
                    try:
                        infos = socket.getaddrinfo(ctrl_ip, None)
                        for _family, _socktype, _proto, _canonname, sockaddr in infos:
                            candidate = sockaddr[0]
                            if candidate:
                                resolved_ip = candidate
                                break
                    except Exception as exc:
                        logger.warning("Failed to resolve controller host %s for switch %s: %s", ctrl_ip, name, exc)

                switch.cmd(f'ovs-vsctl set-controller {name} tcp:{resolved_ip}:{ctrl_port}')
                if resolved_ip != ctrl_ip:
                    logger.info(f"Configured controller for {name}: {ctrl_ip}:{ctrl_port} (resolved to {resolved_ip})")
                else:
                    logger.info(f"Configured controller for {name}: {ctrl_ip}:{ctrl_port}")

            # Default behavior: keep basic connectivity even without a controller configuration.
            #
            # OVS + OpenFlow defaults can drop all traffic unless a controller installs flows.
            # Users expect pingall to work by default, so we enable L2 forwarding unless
            # explicitly disabled via properties.
            if not (properties.get('fail_mode') or properties.get('failMode') or properties.get('failmode')):
                properties.setdefault('fail_mode', 'standalone')
            if not (properties.get('l2_fallback') or properties.get('l2Fallback') or properties.get('l2_fallback_mode')):
                properties.setdefault('l2_fallback', 'normal')

            fail_mode = properties.get('fail_mode') or properties.get('failMode') or properties.get('failmode')
            if fail_mode:
                mode = str(fail_mode).strip().lower()
                if mode in ('standalone', 'secure'):
                    switch.cmd(f'ovs-vsctl set-fail-mode {name} {mode}')
                    logger.info(f"Configured OVS fail-mode {mode} for {name}")

            openflow_version = properties.get('openflow_version')
            protocol = None
            if openflow_version:
                version_str = str(openflow_version).strip()
                if version_str:
                    protocol = version_str if version_str.lower().startswith('openflow') else f"OpenFlow{version_str.replace('.', '')}"
                    switch.cmd(f'ovs-vsctl set bridge {name} protocols={protocol}')
                    logger.info(f"Configured OpenFlow protocol {protocol} for {name}")

            l2_fallback = properties.get('l2_fallback') or properties.get('l2Fallback') or properties.get('l2_fallback_mode')
            if l2_fallback:
                mode = str(l2_fallback).strip().lower()
                if mode in ('normal', 'learning', 'l2', 'true', '1', 'yes'):
                    proto_flag = f"-O {protocol}" if protocol else ""
                    actions = "NORMAL"
                    if controller_endpoint:
                        # Keep network usable while still allowing controller apps to observe traffic.
                        actions = "NORMAL,CONTROLLER:65535"
                    # Use priority=1 so we override the default table-miss-to-controller rule.
                    flow = f"priority=1,actions={actions}"
                    cmd = f"ovs-ofctl {proto_flag} add-flow {name} {shlex.quote(flow)} || true"
                    switch.cmd(cmd)
                    logger.info(f"Configured L2 fallback flow for {name}: {flow}")

        except Exception as exc:
            logger.warning(f"Failed to apply switch configuration for {name}: {exc}")

    def _configure_router_device(self, router, properties):
        """Apply routing configuration, including protocol setups."""
        try:
            self._configure_host_device(router, properties)

            protocols = self._split_property_list(properties.get('protocols', []))
            if not protocols:
                return

            protocol_configs = properties.get('protocol_configs') or {}
            if isinstance(protocol_configs, str):
                try:
                    protocol_configs = json.loads(protocol_configs)
                except json.JSONDecodeError:
                    protocol_configs = {}

            handler = DeviceHandler(self)
            daemon = str(properties.get('router_daemon', 'frr')).lower()

            if daemon in ('frr', ''):
                handler._configure_frr_router(router, protocols, protocol_configs)
            elif daemon == 'bird':
                handler._configure_bird_router(router, protocols, protocol_configs)

        except Exception as exc:
            logger.warning(f"Failed to apply router configuration for {getattr(router, 'name', router)}: {exc}")

    def _add_controller(self, controller):
        """Add a controller to the network"""
        try:
            ctrl = self.net.addController(
                name=controller.name,
                controller=RemoteController,
                ip=controller.ip,
                port=controller.port
            )
            logger.info(f"Added controller: {controller.name} at {controller.ip}:{controller.port}")
        except Exception as e:
            logger.error(f"Failed to add controller: {e}")

    def get_device(self, name):
        """Get a device from the network"""
        if self.net is None:
            raise RuntimeError("No emulation is running")

        return self.net.get(name)

    def is_running(self):
        """Check if emulation is running"""
        return self.status == 'running'

    # Snapshot methods

    def create_snapshot(
        self,
        snapshot_name: str,
        snapshot_type: str = "hybrid_full",
        description: str = ""
    ) -> Dict:
        """
        Create a snapshot of the current emulation

        Args:
            snapshot_name: Unique name for the snapshot
            snapshot_type: Type of snapshot (topology_only, docker_commit, criu_live, hybrid_full)
            description: Optional description

        Returns:
            Dict with snapshot creation results
        """
        if not self.snapshot_manager:
            return {
                'success': False,
                'message': 'Snapshot manager not available'
            }

        try:
            # Map string to enum
            type_map = {
                'topology_only': SnapshotType.TOPOLOGY_ONLY,
                'docker_commit': SnapshotType.DOCKER_COMMIT,
                'criu_live': SnapshotType.CRIU_LIVE,
                'hybrid_full': SnapshotType.HYBRID_FULL
            }

            snap_type = type_map.get(snapshot_type.lower(), SnapshotType.HYBRID_FULL)

            logger.info(f"Creating snapshot: {snapshot_name} (type: {snapshot_type})")

            result = self.snapshot_manager.create_snapshot(
                snapshot_name=snapshot_name,
                snapshot_type=snap_type,
                description=description,
                compression=True
            )

            if result.get('success'):
                logger.info(f"Snapshot created successfully: {snapshot_name}")
                return {
                    'success': True,
                    'message': f'Snapshot {snapshot_name} created successfully',
                    'snapshot': result
                }
            else:
                return {
                    'success': False,
                    'message': result.get('error', 'Snapshot creation failed'),
                    'details': result
                }

        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }

    def list_snapshots(self) -> Dict:
        """List all available snapshots"""
        if not self.snapshot_manager:
            return {
                'success': False,
                'message': 'Snapshot manager not available',
                'snapshots': []
            }

        try:
            snapshots = self.snapshot_manager.list_snapshots()
            return {
                'success': True,
                'count': len(snapshots),
                'snapshots': snapshots
            }
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return {
                'success': False,
                'message': str(e),
                'snapshots': []
            }

    def delete_snapshot(self, snapshot_name: str) -> Dict:
        """Delete a snapshot"""
        if not self.snapshot_manager:
            return {
                'success': False,
                'message': 'Snapshot manager not available'
            }

        try:
            result = self.snapshot_manager.delete_snapshot(snapshot_name)
            if result:
                return {
                    'success': True,
                    'message': f'Snapshot {snapshot_name} deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to delete snapshot {snapshot_name}'
                }
        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return {
                'success': False,
                'message': str(e)
            }
