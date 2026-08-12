"""
Device Handler - Manages device operations in the emulation
Handles creation, deletion, and runtime modification of all device types
"""

from __future__ import annotations

import logging
import os
import sys
import json
import hashlib
import shlex
import shutil
import subprocess
import tempfile

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
        # Avoid shadowing pip-installed Containernet/Mininet modules.
        sys.path.append(module_path)

logger = logging.getLogger(__name__)

from mininet.node import Host, OVSKernelSwitch, RemoteController
from mininet.link import TCLink
# Containernet may expose Docker nodes either under `mininet.node` (forked installs)
# or under `containernet.node` (pip/standalone installs).
try:
    from mininet.node import Docker  # type: ignore
except Exception:  # pragma: no cover
    from containernet.node import Docker  # type: ignore

try:
    from mininet.node import DockerSta  # type: ignore
except Exception:  # pragma: no cover
    try:
        from containernet.node import DockerSta  # type: ignore
    except Exception:  # pragma: no cover
        DockerSta = Docker  # type: ignore
import emulation_pb2


class DeviceHandler:
    """Handles all device-related operations"""

    def __init__(self, emulation_manager):
        self.emulation_manager = emulation_manager

    def _register_mapping(self, params, device_name):
        """Register node ID mapping from params with the emulation manager."""
        node_id = None
        if isinstance(params, dict):
            node_id = params.get('node_id') or params.get('id')
        self.emulation_manager.register_node_mapping(node_id, device_name)

        if isinstance(params, dict):
            display_alias = params.get('display_name') or params.get('name')
            if display_alias and display_alias != device_name:
                self.emulation_manager.register_node_mapping(display_alias, device_name)

    def add_host(self, name, ip, ip6, mac, default_route, params):
        """Add a host to the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            # Add host
            host = net.addHost(
                name,
                ip=ip if ip else None,
                mac=mac if mac else None,
                defaultRoute=default_route if default_route else None
            )

            # Configure IPv6 if provided
            if ip6:
                host.cmd(f'ip -6 addr add {ip6} dev {name}-eth0')

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'host',
                'node': host,
                'properties': params
            }
            self._register_mapping(params, name)

            logger.info(f"Added host: {name}")

            # Return device info
            return emulation_pb2.Device(
                name=name,
                type='host',
                properties=params,
                interfaces=[
                    emulation_pb2.Interface(
                        name=intf.name,
                        mac=intf.MAC(),
                        ip=intf.IP() if intf.IP() else '',
                        status='up'
                    )
                    for intf in host.intfList()
                ],
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add host {name}: {e}")
            raise

    def add_switch(self, name, switch_type, openflow_version, controller, datapath_id, params):
        """Add a switch to the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            # Determine switch class
            if switch_type == 'ovs' or not switch_type:
                switch_cls = OVSKernelSwitch
            else:
                raise ValueError(f"Unsupported switch type: {switch_type}")

            # Add switch
            dpid = f"{datapath_id:016x}" if datapath_id is not None else None
            switch = net.addSwitch(
                name,
                cls=switch_cls,
                dpid=dpid,
                protocols=openflow_version if openflow_version else 'OpenFlow13'
            )

            # Set controller if provided
            if controller:
                ctrl_parts = controller.split(':')
                ctrl_ip = ctrl_parts[0]
                ctrl_port = int(ctrl_parts[1]) if len(ctrl_parts) > 1 else 6653
                self.set_controller(name, ctrl_ip, ctrl_port, 'tcp')

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'switch',
                'node': switch,
                'properties': {
                    'switch_type': switch_type,
                    'openflow_version': openflow_version,
                    'dpid': dpid,
                    **params
                }
            }
            self._register_mapping(params, name)

            logger.info(f"Added switch: {name}")

            return emulation_pb2.Device(
                name=name,
                type='switch',
                properties={
                    'switch_type': switch_type,
                    'openflow_version': openflow_version or 'OpenFlow13',
                    'dpid': dpid or '',
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add switch {name}: {e}")
            raise

    def add_router(self, name, protocols, router_daemon, protocol_configs, params):
        """Add a router to the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            # Add router as a host with IP forwarding enabled
            router = net.addHost(name, cls=Host)

            # Enable IP forwarding
            router.cmd('sysctl -w net.ipv4.ip_forward=1')
            router.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'router',
                'node': router,
                'properties': {
                    'protocols': protocols,
                    'router_daemon': router_daemon or 'frr',
                    'protocol_configs': protocol_configs,
                    **params
                }
            }
            self._register_mapping(params, name)

            # Configure routing protocols
            if router_daemon == 'frr' or not router_daemon:
                self._configure_frr_router(router, protocols, protocol_configs)
            elif router_daemon == 'bird':
                self._configure_bird_router(router, protocols, protocol_configs)

            logger.info(f"Added router: {name} with protocols: {protocols}")

            return emulation_pb2.Device(
                name=name,
                type='router',
                properties={
                    'protocols': ','.join(protocols),
                    'router_daemon': router_daemon or 'frr',
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add router {name}: {e}")
            raise

    def add_access_point(self, name, ssid, mode, channel, security, password, params):
        """Add a wireless access point to the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            if not self.emulation_manager.is_wifi_enabled:
                raise RuntimeError("WiFi not enabled in this emulation")

            net = self.emulation_manager.net

            ap_kwargs = {
                'ssid': ssid,
                'mode': mode or 'g',
                'channel': channel or '1'
            }

            if security and security != 'open' and password:
                ap_kwargs['encrypt'] = security
                ap_kwargs['passwd'] = password

            mac_address = params.get('mac')
            if mac_address:
                ap_kwargs['mac'] = mac_address

            ap = net.addAccessPoint(name, **ap_kwargs)

            position = params.get('position') or params.get('coordinates')
            if position:
                try:
                    if isinstance(position, str):
                        coords = [float(coord.strip()) for coord in position.split(',')]
                    else:
                        coords = [float(value) for value in position]
                    if len(coords) == 3:
                        ap.setPosition(','.join(str(coord) for coord in coords))
                except Exception as exc:
                    logger.warning(f"Failed to set access point position for {name}: {exc}")

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'ap',
                'node': ap,
                'properties': {
                    'ssid': ssid,
                    'mode': mode,
                    'channel': channel,
                    'security': security,
                    **params
                }
            }
            self._register_mapping(params, name)

            logger.info(f"Added access point: {name} with SSID: {ssid}")

            return emulation_pb2.Device(
                name=name,
                type='ap',
                properties={
                    'ssid': ssid,
                    'mode': mode or 'g',
                    'channel': channel or '1',
                    'security': security or 'open',
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add access point {name}: {e}")
            raise

    def add_station(self, name, ssid, mode, security, password, mobility, params):
        """Add a wireless station to the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            if not self.emulation_manager.is_wifi_enabled:
                raise RuntimeError("WiFi not enabled in this emulation")

            net = self.emulation_manager.net

            station_kwargs = {}

            if security and security != 'open':
                station_kwargs['passwd'] = password
                station_kwargs['encrypt'] = security

            station_ip = params.get('ip')
            if station_ip:
                station_kwargs['ip'] = station_ip

            station_mac = params.get('mac')
            if station_mac:
                station_kwargs['mac'] = station_mac

            docker_image = (
                params.get('docker_image') or
                params.get('image') or
                'ubuntu:22.04'
            )

            command = params.get('command')
            if command:
                if isinstance(command, (list, tuple)):
                    station_kwargs['dcmd'] = ' '.join(str(part) for part in command)
                else:
                    station_kwargs['dcmd'] = str(command)

            environment = params.get('environment')
            if environment:
                station_kwargs['environment'] = environment

            volumes = params.get('volumes')
            if volumes:
                station_kwargs['volumes'] = volumes

            sta = net.addStation(
                name,
                cls=DockerSta,
                dimage=docker_image,
                **station_kwargs
            )

            position = params.get('position') or params.get('coordinates')
            if position:
                try:
                    if isinstance(position, str):
                        coords = [float(coord.strip()) for coord in position.split(',')]
                    else:
                        coords = [float(value) for value in position]
                    if len(coords) == 3:
                        sta.setPosition(','.join(str(c) for c in coords))
                except Exception as exc:
                    logger.warning(f"Failed to set station position for {name}: {exc}")

            # Configure mobility if provided
            if mobility and hasattr(mobility, 'model'):
                self._configure_mobility(sta, mobility)

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'station',
                'node': sta,
                'properties': {
                    'ssid': ssid,
                    'mode': mode,
                    'security': security,
                    'mobility': mobility,
                    'docker_image': docker_image,
                    **params
                }
            }
            self._register_mapping(params, name)

            logger.info(f"Added station: {name}")

            return emulation_pb2.Device(
                name=name,
                type='station',
                properties={
                    'ssid': ssid or '',
                    'mode': mode or 'g',
                    'security': security or 'open',
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add station {name}: {e}")
            raise

    def add_docker_container(self, name, image, command, environment, volumes, params):
        """Add a Docker container to the emulation (Containernet)"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            docker_kwargs = {
                'cls': Docker,
                'dimage': image
            }

            if command:
                if isinstance(command, (list, tuple)):
                    docker_kwargs['dcmd'] = ' '.join(str(part) for part in command)
                else:
                    docker_kwargs['dcmd'] = str(command)

            if environment:
                docker_kwargs['environment'] = environment

            if volumes:
                docker_kwargs['volumes'] = volumes

            cpu_quota = params.get('cpu_quota')
            cpu_period = params.get('cpu_period')
            mem_limit = params.get('mem_limit')

            if cpu_quota is not None:
                docker_kwargs['cpu_quota'] = int(cpu_quota)
            if cpu_period is not None:
                docker_kwargs['cpu_period'] = int(cpu_period)
            if mem_limit is not None:
                docker_kwargs['mem_limit'] = str(mem_limit)

            if hasattr(self.emulation_manager, "_add_docker_node"):
                container = self.emulation_manager._add_docker_node(name, docker_kwargs)
            else:
                container = net.addDocker(name, **docker_kwargs)

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'docker',
                'node': container,
                'properties': {
                    'image': image,
                    'command': command,
                    **params
                }
            }
            self._register_mapping(params, name)

            logger.info(f"Added Docker container: {name} with image: {image}")

            return emulation_pb2.Device(
                name=name,
                type='docker',
                properties={
                    'image': image,
                    'command': ','.join(command) if command else '',
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add Docker container {name}: {e}")
            raise

    def add_p4_switch(self, name, p4_source, p4info_path, device_config_path, grpc_port, params):
        """Add a P4 programmable switch (BMv2)"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            net = self.emulation_manager.net

            params = params or {}

            program_id = params.get('p4_program_id') or params.get('program_id')
            if (not device_config_path or str(device_config_path).strip() in ('', 'None')) and program_id:
                storage_root = os.getenv("P4_STORAGE_ROOT", "/var/lib/caduceus/p4")
                device_config_path = os.path.join(storage_root, str(program_id), f"{program_id}.json")
            if (not p4info_path or str(p4info_path).strip() in ('', 'None')) and program_id:
                storage_root = os.getenv("P4_STORAGE_ROOT", "/var/lib/caduceus/p4")
                p4info_path = os.path.join(storage_root, str(program_id), f"{program_id}.p4info.txt")

            # Compile P4 program if needed (best-effort; requires p4c installed in the emulation container).
            if p4_source and (not device_config_path or not p4info_path):
                p4info_path, device_config_path = self._compile_p4_program(p4_source)

            # Add P4 switch
            from p4_switch import P4BMv2Switch

            p4switch = net.addSwitch(
                name,
                cls=P4BMv2Switch,
                sw_path='simple_switch_grpc',
                json_path=device_config_path,
                p4info_path=p4info_path,
                log_console=True,
                grpc_port=int(grpc_port or 9559)
            )

            # Store device reference
            self.emulation_manager.devices[name] = {
                'type': 'p4switch',
                'node': p4switch,
                'properties': {
                    'p4_source': p4_source,
                    'p4info_path': p4info_path,
                    'device_config_path': device_config_path,
                    'grpc_port': grpc_port,
                    **params
                }
            }
            self._register_mapping(params, name)

            logger.info(f"Added P4 switch: {name}")

            return emulation_pb2.Device(
                name=name,
                type='p4switch',
                properties={
                    'p4_source': p4_source or '',
                    'grpc_port': str(grpc_port or 9559),
                    **params
                },
                status='active'
            )

        except Exception as e:
            logger.error(f"Failed to add P4 switch {name}: {e}")
            raise

    def remove_device(self, name):
        """Remove a device from the emulation"""
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            if name not in self.emulation_manager.devices:
                raise ValueError(f"Device {name} not found")

            device_info = self.emulation_manager.devices[name]
            node = device_info['node']

            net = self.emulation_manager.net

            # Remove all links connected to this device
            for link in list(node.intfList()):
                if link.link:
                    net.delLink(link.link)

            # Remove the device
            net.delNode(node)

            # Remove from tracking
            del self.emulation_manager.devices[name]
            self.emulation_manager.unregister_node_mapping(name)

            logger.info(f"Removed device: {name}")

            return {'success': True, 'message': f"Device {name} removed"}

        except Exception as e:
            logger.error(f"Failed to remove device {name}: {e}")
            return {'success': False, 'message': str(e)}

    def update_device(self, name, updates):
        """Update device properties at runtime, using immutable ID for lookup."""
        try:
            device_id = name  # The 'name' parameter is now the immutable device ID
            logger.info(f"UpdateDevice called for ID: '{device_id}' with updates: {updates}")

            # Find the current Mininet name using the database ID
            mininet_name = self.emulation_manager.node_id_to_name.get(device_id)

            if not mininet_name or mininet_name not in self.emulation_manager.devices:
                raise ValueError(f"Device with ID {device_id} not found in running emulation.")

            logger.info(f"Found device '{mininet_name}' for ID '{device_id}'")
            device_info = self.emulation_manager.devices[mininet_name]
            node = device_info['node']

            # Handle potential rename (display name update)
            new_name = updates.pop('display_name', None) or updates.pop('name', None)
            if new_name:
                current_display = device_info['properties'].get('display_name') or device_info['properties'].get('name') or mininet_name
                if new_name != current_display:
                    logger.info(
                        "Updating display name for device ID %s: '%s' -> '%s'",
                        device_id,
                        current_display,
                        new_name
                    )
                    if current_display and current_display != mininet_name:
                        self.emulation_manager.unregister_node_mapping(current_display)
                    device_info['properties']['display_name'] = new_name
                    device_info['properties']['name'] = new_name
                    self.emulation_manager.register_node_mapping(new_name, mininet_name)

            # Update IP address if provided
            if 'ip' in updates:
                intf = node.defaultIntf()
                if intf:
                    logger.info(f"Updating IP for {mininet_name} to {updates['ip']}")
                    intf.setIP(updates['ip'])

            # Update MAC address if provided
            if 'mac' in updates:
                intf = node.defaultIntf()
                if intf:
                    logger.info(f"Updating MAC for {mininet_name} to {updates['mac']}")
                    intf.setMAC(updates['mac'])

            # Update default route if provided
            if 'default_route' in updates:
                logger.info(f"Updating default route for {mininet_name}")
                node.setDefaultRoute(updates['default_route'])

            # Update other properties
            device_info['properties'].update(updates)

            logger.info(f"Successfully processed updates for device ID {device_id}")

            # Return updated device information (still referenced by Mininet name)
            return self.get_device(mininet_name)

        except Exception as e:
            logger.error(f"Failed to update device with ID {name}: {e}", exc_info=True)
            raise

    def set_position(self, device_name, x, y, z):
        """Move a station or access point at runtime.

        Coordinates stay floating point end to end (mininet-wifi parses the
        "x,y,z" string with float()), so an external physics engine such as
        Gazebo can stream sub-metre updates at ~10 Hz without being quantised.
        """
        try:
            if not self.emulation_manager.is_running():
                raise RuntimeError("Emulation is not running")

            # Callers may pass either the runtime Mininet name or the immutable
            # device ID, so mirror the lookup used by update_device().
            mininet_name = device_name if device_name in self.emulation_manager.devices else None
            if mininet_name is None:
                name_map = getattr(self.emulation_manager, 'node_id_to_name', None) or {}
                mininet_name = name_map.get(device_name)

            if not mininet_name or mininet_name not in self.emulation_manager.devices:
                known = ', '.join(sorted(self.emulation_manager.devices.keys())) or '<none>'
                raise ValueError(
                    f"Device {device_name} not found in running emulation. Known devices: {known}"
                )

            device_info = self.emulation_manager.devices[mininet_name]
            node = device_info['node']

            if not hasattr(node, 'setPosition'):
                raise ValueError(
                    f"Device {mininet_name} (type={device_info.get('type')}) does not support "
                    f"positioning; setPosition is only available on mininet-wifi nodes "
                    f"such as stations and access points"
                )

            position = "%.3f,%.3f,%.3f" % (float(x), float(y), float(z))
            node.setPosition(position)

            # Keep tracked properties in sync so GetDevice/ListDevices report the move.
            properties = device_info.setdefault('properties', {})
            properties['position'] = position

            logger.debug("Set position of %s to %s", mininet_name, position)

            return {
                'success': True,
                'message': f"Position of {mininet_name} set to {position}",
                'name': mininet_name,
                'position': position
            }

        except Exception as e:
            logger.error(f"Failed to set position for {device_name}: {e}")
            raise

    def get_device(self, name):
        """Get device information"""
        if name not in self.emulation_manager.devices:
            raise ValueError(f"Device {name} not found")

        device_info = self.emulation_manager.devices[name]
        node = device_info['node']
        
        # Get interfaces safely
        interfaces = []
        try:
            for intf in node.intfList():
                if intf and intf.name:  # Check if interface is valid
                    try:
                        interfaces.append(emulation_pb2.Interface(
                            name=intf.name,
                            mac=intf.MAC() if intf.MAC() else '',
                            ip=intf.IP() if intf.IP() else '',
                            status='up' if intf.isUp() else 'down'
                        ))
                    except Exception as e:
                        logger.debug(f"Could not get interface info for {intf.name}: {e}")
        except Exception as e:
            logger.debug(f"Could not list interfaces for device {name}: {e}")

        # Convert properties dict to string map for protobuf
        props = {}
        if 'properties' in device_info and isinstance(device_info['properties'], dict):
            props = {k: str(v) for k, v in device_info['properties'].items()}

        # Ensure callers can reliably discover a device IPv4 without having to inspect interfaces.
        # Prefer explicit properties['ip'], otherwise derive from the first non-loopback interface.
        if not str(props.get("ip") or "").strip():
            for iface in interfaces:
                try:
                    iface_name = str(getattr(iface, "name", "") or "")
                    ip = str(getattr(iface, "ip", "") or "").strip()
                    if not ip:
                        continue
                    if iface_name == "lo" or ip.startswith("127."):
                        continue
                    props["ip"] = ip
                    break
                except Exception:
                    continue

        if not str(props.get("ip") or "").strip():
            try:
                ip = str(getattr(node, "IP")() or "").strip()
                if ip and not ip.startswith("127."):
                    props["ip"] = ip
            except Exception:
                pass

        # Best-effort IPv6 discovery (useful for 6LoWPAN / IPv6-only algorithms).
        if not str(props.get("ip6") or "").strip():
            try:
                out = node.cmd("ip -o -6 addr show scope global | awk '{print $4}' | head -n 1") or ""
                ip6 = (out or "").strip()
                if ip6:
                    props["ip6"] = ip6
            except Exception:
                pass

        return emulation_pb2.Device(
            name=name,
            type=device_info['type'],
            properties=props,
            interfaces=interfaces,
            status='active'
        )

    def list_devices(self, device_type=None):
        """List all devices, optionally filtered by type"""
        devices = []

        for name, device_info in self.emulation_manager.devices.items():
            if device_type and device_info['type'] != device_type:
                continue

            devices.append(self.get_device(name))

        return devices

    def execute_command(self, device, command):
        """Execute a command on a device"""
        try:
            if device not in self.emulation_manager.devices:
                raise ValueError(f"Device {device} not found")

            node = self.emulation_manager.devices[device]['node']

            timeout_seconds = 15
            marker = "__CADUCEUS_EXIT_CODE__:"
            wrapped = f"timeout {timeout_seconds}s /bin/bash -lc {shlex.quote(command)}; echo {marker}$?"
            out = node.cmd(wrapped) or ""

            exit_code = 0
            stdout = out
            if marker in out:
                before, after = out.rsplit(marker, 1)
                stdout = before
                try:
                    exit_code = int((after or "").strip().splitlines()[0])
                except Exception:
                    exit_code = 0

            stderr = ""
            if exit_code == 124:
                stderr = f"Command timed out after {timeout_seconds}s"

            return {
                'success': exit_code == 0,
                'stdout': stdout,
                'stderr': stderr,
                'exit_code': exit_code
            }

        except Exception as e:
            logger.error(f"Failed to execute command on {device}: {e}")
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1
            }

    def execute_command_stream(self, device, command):
        """Execute a command with streaming output"""
        # TODO: Implement streaming command execution
        # This would use pexpect or similar to stream output
        yield self.execute_command(device, command)

    def set_controller(self, switch, controller_ip, controller_port, protocol):
        """Set controller for a switch"""
        try:
            if switch not in self.emulation_manager.devices:
                raise ValueError(f"Switch {switch} not found")

            device_info = self.emulation_manager.devices[switch]
            if device_info['type'] != 'switch':
                raise ValueError(f"{switch} is not a switch")

            node = device_info['node']

            # Set controller
            node.cmd(f'ovs-vsctl set-controller {switch} tcp:{controller_ip}:{controller_port}')

            logger.info(f"Set controller for {switch}: {controller_ip}:{controller_port}")

        except Exception as e:
            logger.error(f"Failed to set controller for {switch}: {e}")
            raise

    def remove_controller(self, switch):
        """Remove controller from a switch"""
        try:
            if switch not in self.emulation_manager.devices:
                raise ValueError(f"Switch {switch} not found")

            device_info = self.emulation_manager.devices[switch]
            if device_info['type'] != 'switch':
                raise ValueError(f"{switch} is not a switch")

            node = device_info['node']

            # Remove controller
            node.cmd(f'ovs-vsctl del-controller {switch}')

            logger.info(f"Removed controller from {switch}")

        except Exception as e:
            logger.error(f"Failed to remove controller from {switch}: {e}")
            raise

    # Helper methods

    def _configure_frr_router(self, router, protocols, protocol_configs):
        """Configure FRRouting on a router"""
        # Start FRR daemons
        router.cmd('/usr/lib/frr/zebra -d')

        for protocol in protocols:
            if protocol == 'ospf':
                router.cmd('/usr/lib/frr/ospfd -d')
            elif protocol == 'bgp':
                router.cmd('/usr/lib/frr/bgpd -d')
            elif protocol == 'rip':
                router.cmd('/usr/lib/frr/ripd -d')
            elif protocol == 'isis':
                router.cmd('/usr/lib/frr/isisd -d')

        logger.info(f"Configured FRR with protocols: {protocols}")

    def _configure_bird_router(self, router, protocols, protocol_configs):
        """Configure BIRD on a router"""
        # TODO: Implement BIRD configuration
        logger.info(f"Configured BIRD with protocols: {protocols}")

    def _configure_mobility(self, station, mobility):
        """Configure mobility model for a station"""
        # TODO: Implement mobility configuration
        logger.info(f"Configured mobility for station: {station.name}")

    def _compile_p4_program(self, p4_source):
        """Compile P4 program to JSON and P4Info"""
        logger.info(f"Compiling P4 program for BMv2: {p4_source}")

        storage_root = os.getenv("P4_STORAGE_ROOT", "/var/lib/caduceus/p4")
        os.makedirs(storage_root, exist_ok=True)

        # If p4_source is a path, use it; otherwise treat as source code.
        source_path = None
        if isinstance(p4_source, str) and os.path.isfile(p4_source):
            source_path = p4_source

        program_id = hashlib.sha1(str(p4_source).encode()).hexdigest()[:12]
        program_dir = os.path.join(storage_root, f"runtime-{program_id}")
        os.makedirs(program_dir, exist_ok=True)

        p4_file = os.path.join(program_dir, "program.p4")
        json_file = os.path.join(program_dir, "program.json")
        p4info_file = os.path.join(program_dir, "program.p4info.txt")

        if source_path:
            shutil.copyfile(source_path, p4_file)
        else:
            with open(p4_file, "w", encoding="utf-8") as handle:
                handle.write(str(p4_source))

        cmd = [
            "p4c-bm2-ss",
            "--p4v",
            "16",
            "--arch",
            "v1model",
            "-o",
            json_file,
            "--p4runtime-files",
            p4info_file,
            p4_file,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise RuntimeError("p4c-bm2-ss not found in emulation container; compile using P4 Manager instead") from exc

        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "P4 compilation failed")

        return p4info_file, json_file
