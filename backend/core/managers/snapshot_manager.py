"""
Snapshot Manager
Handles simulation snapshots, state capture, and restoration functionality
"""

import os
import json
import tempfile
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger(__name__)


class SnapshotManager:
    """Manages network simulation snapshots and state restoration"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        # Try to create snapshots directory with fallback
        try:
            self.snapshots_dir = Path("/tmp/mininet_snapshots")
            self.snapshots_dir.mkdir(exist_ok=True)
        except PermissionError:
            # Fallback to current directory if /tmp is not writable
            self.snapshots_dir = Path("./mininet_snapshots")
            self.snapshots_dir.mkdir(exist_ok=True)
            self.logger.warning(f"Could not create snapshots directory in /tmp, using {self.snapshots_dir}")

    def create_snapshot(self, net, topology_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a comprehensive simulation snapshot (alias for create_simulation_snapshot)"""
        return self.create_simulation_snapshot(net, topology_data)

    def create_simulation_snapshot(self, net, topology_data: Dict[str, Any] = None, mininet_manager=None) -> Dict[str, Any]:
        """Create a comprehensive simulation snapshot"""
        try:
            # Get actual controller information from MininetManager if available
            actual_controller_type = 'ryu'  # default
            actual_controller_app = 'simple_switch_13'  # default
            actual_controller_port = 6633  # default
            actual_controller_ip = '127.0.0.1'  # default
            is_controller_running = False
            
            # First, try to get controller info from topology data
            if topology_data:
                controllers = topology_data.get('controllers', [])
                if controllers:
                    controller = controllers[0]  # Use first controller
                    actual_controller_type = controller.get('controller_type', 'ryu')
                    actual_controller_app = controller.get('app', 'simple_switch_13')
                    actual_controller_port = controller.get('port', 6633)
                    actual_controller_ip = controller.get('ip', '127.0.0.1')
                    self.logger.info(f"Using controller from topology data: {actual_controller_type} with app: {actual_controller_app}")
                else:
                    # Check nodes array for controllers
                    nodes = topology_data.get('nodes', [])
                    for node in nodes:
                        if node.get('type') == 'controller':
                            actual_controller_type = node.get('controller_type', 'ryu')
                            actual_controller_app = node.get('app', 'simple_switch_13')
                            actual_controller_port = node.get('port', 6633)
                            actual_controller_ip = node.get('ip', '127.0.0.1')
                            self.logger.info(f"Using controller from nodes: {actual_controller_type} with app: {actual_controller_app}")
                            break
            
            # If no controller found in topology data, try MininetManager
            if actual_controller_type == 'ryu' and mininet_manager and hasattr(mininet_manager, 'controller_factory'):
                active_controller = mininet_manager.controller_factory.get_active_controller()
                if active_controller:
                    actual_controller_type = active_controller
                    controller_info = mininet_manager.controller_factory.get_controller_info().get(active_controller, {})
                    actual_controller_app = controller_info.get('current_app', 'simple_switch_13')
                    actual_controller_port = controller_info.get('port', 6633)
                    is_controller_running = controller_info.get('running', False)
                    self.logger.info(f"Detected active controller: {actual_controller_type} with app: {actual_controller_app}")
            
            # Create the expected snapshot structure for database validation
            snapshot = {
                'snapshot_id': f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'timestamp': datetime.now().isoformat(),
                'mininet_state': {
                    'topology_data': topology_data or {},
                    'live_configurations': {},
                    'applied_configurations': {},
                    'network_running': net is not None
                },
                'controller_state': {
                    'is_running': is_controller_running,
                    'controller_type': actual_controller_type,
                    'app': actual_controller_app,
                    'port': actual_controller_port,
                    'ip': actual_controller_ip
                },
                'network_stats': {
                    'hosts': [],
                    'switches': [],
                    'links': [],
                    'controllers': []
                },
                'configurations': {},
                'metadata': {}
            }

            # Capture live configurations
            live_configs = self._capture_live_configurations(net)
            snapshot['mininet_state']['live_configurations'] = live_configs

            # Capture network state
            network_state = self._capture_network_state(net)
            snapshot['network_stats'] = network_state

            # Capture device states with type information
            device_states = self._capture_device_states(net)
            snapshot['configurations']['devices'] = device_states

            # Capture controller and switch type information
            controller_switch_info = self._capture_controller_switch_info(net, topology_data, mininet_manager)
            snapshot['configurations']['controller_switch_types'] = controller_switch_info

            # Capture applied configurations from MininetManager if available
            if mininet_manager and hasattr(mininet_manager, 'config_tracker'):
                applied_configs = mininet_manager.config_tracker.get_applied_configurations()
                if applied_configs:
                    snapshot['configurations']['applied_configurations'] = applied_configs
                    self.logger.info(f"Captured applied configurations: {len(applied_configs.get('device_configs', {}))} devices")

            # Capture routing state
            routing_state = self._capture_routing_state(net)
            snapshot['configurations']['routing'] = routing_state

            # Capture firewall state
            firewall_state = self._capture_firewall_state(net)
            snapshot['configurations']['firewall'] = firewall_state

            # Update controller state with actual information
            if controller_switch_info.get('controllers'):
                for controller_id, controller_info in controller_switch_info['controllers'].items():
                    snapshot['controller_state'].update({
                        'is_running': controller_info.get('running', False),
                        'controller_type': controller_info.get('controller_type', 'ryu'),
                        'app': controller_info.get('app', 'simple_switch_13'),
                        'port': controller_info.get('port', 6633),
                        'ip': controller_info.get('ip', '127.0.0.1')
                    })
                    break  # Use first controller's info

            # Add metadata
            snapshot['metadata'] = {
                'network_running': net is not None,
                'total_hosts': len(net.hosts) if net else 0,
                'total_switches': len(net.switches) if net else 0,
                'total_links': len(net.links) if net else 0,
                'snapshot_version': '1.0'
            }

            # Save snapshot to file (optional, don't fail if we can't save)
            try:
                snapshot_file = self.snapshots_dir / f"{snapshot['snapshot_id']}.json"
                with open(snapshot_file, 'w') as f:
                    json.dump(snapshot, f, indent=2)
                self.logger.info(f"Simulation snapshot saved to file: {snapshot_file}")
            except Exception as e:
                self.logger.warning(f"Could not save snapshot to file: {e}")

            self.logger.info(f"Simulation snapshot created: {snapshot['snapshot_id']}")
            return snapshot

        except Exception as e:
            self.logger.error(f"Error creating simulation snapshot: {e}")
            return {'error': str(e)}

    def restore_simulation_snapshot(self, snapshot_data: Dict[str, Any], net, mininet_manager=None) -> bool:
        """Restore simulation from snapshot"""
        try:
            self.logger.info("Starting simulation restoration...")
            print(f"snapshot_data: {snapshot_data}")
            # First, restore the topology if we have topology data
            if 'mininet_state' in snapshot_data and 'topology_data' in snapshot_data['mininet_state']:
                topology_data = snapshot_data['mininet_state']['topology_data']
                if topology_data and mininet_manager:
                    self.logger.info("Restoring topology from snapshot...")
                    
                    # Stop current network if running
                    if mininet_manager.is_running:
                        mininet_manager.stop_network()
                    
                    # Store topology configuration for UI display
                    mininet_manager.set_topology_configuration(topology_data)
                    
                    # Try to create topology from snapshot data
                    success = mininet_manager.create_custom_topology(topology_data)
                    if success:
                        self.logger.info("Topology created successfully, starting network...")
                        # Start the network after creating it
                        if mininet_manager.net:
                            mininet_manager.net.start()
                            mininet_manager.is_running = True
                            self.logger.info("Network started successfully after restoration")
                        else:
                            self.logger.warning("Network object is None after creation")
                    else:
                        self.logger.warning("Failed to create running topology, but configuration stored for UI display")
                        # Don't return False here - we still want to restore controller state

            # Restore controller state
            if 'controller_state' in snapshot_data and mininet_manager:
                controller_state = snapshot_data['controller_state']
                controller_type = controller_state.get('controller_type', 'ryu')
                controller_app = controller_state.get('app', 'simple_switch_13')
                controller_port = controller_state.get('port', 6633)
                
                self.logger.info(f"Restoring controller: {controller_type} with app: {controller_app}")
                
                # Start the controller if it was running
                if controller_state.get('is_running', False):
                    success = mininet_manager.controller_factory.start_controller(
                        controller_type, controller_app, controller_port
                    )
                    if success:
                        self.logger.info(f"Controller {controller_type} started successfully")
                    else:
                        self.logger.warning(f"Failed to start controller {controller_type}")

            # Restore applied configurations from MininetManager if available
            if mininet_manager and hasattr(mininet_manager, 'config_tracker'):
                applied_configs = snapshot_data.get('configurations', {}).get('applied_configurations', {})
                self.logger.critical(f"DEBUG: Found applied_configs: {bool(applied_configs)}")
                if applied_configs:
                    self.logger.critical(f"DEBUG: Applied configs keys: {list(applied_configs.keys())}")
                    device_configs = applied_configs.get('device_configs', {})
                    self.logger.critical(f"DEBUG: Device configs: {list(device_configs.keys())}")
                    
                    self.logger.info("Restoring applied configurations...")
                    mininet_manager.config_tracker.applied_configurations = applied_configs
                    
                    # Apply tracked configurations if network is running
                    if mininet_manager.is_running and mininet_manager.net:
                        self.logger.critical("DEBUG: Network is running, applying tracked configurations...")
                        # Write debug info to file
                        with open('/tmp/snapshot_debug.log', 'a') as f:
                            f.write(f"DEBUG: About to call _apply_tracked_configurations\n")
                        self._apply_tracked_configurations(mininet_manager)
                    else:
                        self.logger.critical(f"DEBUG: Network not running - is_running: {mininet_manager.is_running}, net: {bool(mininet_manager.net)}")
                else:
                    self.logger.critical("DEBUG: No applied configurations found in snapshot")

            # Restore live configurations
            if 'configurations' in snapshot_data and 'live' in snapshot_data['configurations']:
                live_configs = snapshot_data['configurations']['live']
                self._restore_live_configurations(net, live_configs)

            # Restore device configurations
            if 'configurations' in snapshot_data and 'devices' in snapshot_data['configurations']:
                device_configs = snapshot_data['configurations']['devices']
                self._restore_device_configurations(net, device_configs)

            # Restore routing configurations
            if 'configurations' in snapshot_data and 'routing' in snapshot_data['configurations']:
                routing_configs = snapshot_data['configurations']['routing']
                self._restore_routing_configurations(net, routing_configs)

            # Restore firewall configurations
            if 'configurations' in snapshot_data and 'firewall' in snapshot_data['configurations']:
                firewall_configs = snapshot_data['configurations']['firewall']
                self._restore_firewall_configurations(net, firewall_configs)

            # Restore controller and switch type information
            if 'configurations' in snapshot_data and 'controller_switch_types' in snapshot_data['configurations']:
                controller_switch_info = snapshot_data['configurations']['controller_switch_types']
                self._restore_controller_switch_info(net, controller_switch_info)

            self.logger.info("Simulation restoration completed")
            return True

        except Exception as e:
            self.logger.error(f"Error restoring simulation snapshot: {e}")
            return False

    def _capture_live_configurations(self, net) -> Dict[str, Any]:
        """Capture live configurations from running network"""
        try:
            live_configs = {
                'timestamp': datetime.now().isoformat(),
                'network_interfaces': {},
                'routing_tables': {},
                'arp_tables': {},
                'firewall_rules': {},
                'protocols': {}
            }

            # Only capture if network is running
            if not net:
                return live_configs

            # Capture interface configurations
            for node in net.hosts + net.switches:
                try:
                    node_config = self._capture_node_interfaces(node)
                    if node_config:
                        live_configs['network_interfaces'][node.name] = node_config
                except Exception as e:
                    self.logger.warning(f"Error capturing interfaces for {node.name}: {e}")

            # Capture routing tables
            for host in net.hosts:
                try:
                    routing_config = self._capture_host_routing(host)
                    if routing_config:
                        live_configs['routing_tables'][host.name] = routing_config
                except Exception as e:
                    self.logger.warning(f"Error capturing routing for {host.name}: {e}")

            # Capture ARP tables
            for host in net.hosts:
                try:
                    arp_config = self._capture_host_arp(host)
                    if arp_config:
                        live_configs['arp_tables'][host.name] = arp_config
                except Exception as e:
                    self.logger.warning(f"Error capturing ARP for {host.name}: {e}")

            # Capture network protocols
            protocol_config = self._capture_network_protocols(net)
            live_configs['protocols'] = protocol_config

            return live_configs

        except Exception as e:
            self.logger.error(f"Error capturing live configurations: {e}")
            return {'error': str(e)}

    def _capture_node_interfaces(self, node) -> Dict[str, Any]:
        """Capture network interfaces for a node"""
        try:
            interfaces = {}
            if hasattr(node, 'intfList'):
                for intf in node.intfList():
                    if intf.name != 'lo':  # Skip loopback
                        interfaces[intf.name] = {
                            'ip': getattr(intf, 'ip', 'N/A'),
                            'mac': getattr(intf, 'mac', 'N/A'),
                            'status': 'up' if getattr(intf, 'isUp', lambda: False)() else 'down'
                        }
            return interfaces
        except Exception as e:
            self.logger.warning(f"Error capturing node interfaces: {e}")
            return {}

    def _capture_host_routing(self, host) -> Dict[str, Any]:
        """Capture routing table for a host"""
        try:
            routing_table = []

            # Use host's cmd method to get routing table
            if hasattr(host, 'cmd'):
                route_output = host.cmd('ip route show')
                for line in route_output.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            route_entry = {
                                'destination': parts[0],
                                'gateway': parts[2] if len(parts) > 2 and parts[1] == 'via' else None,
                                'interface': parts[-1] if parts[-2] == 'dev' else None
                            }
                            routing_table.append(route_entry)

            return {'routes': routing_table}
        except Exception as e:
            self.logger.warning(f"Error capturing host routing: {e}")
            return {}

    def _capture_host_arp(self, host) -> Dict[str, Any]:
        """Capture ARP table for a host"""
        try:
            arp_table = []

            # Use host's cmd method to get ARP table
            if hasattr(host, 'cmd'):
                arp_output = host.cmd('ip neigh show')
                for line in arp_output.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
                            arp_entry = {
                                'ip': parts[0],
                                'mac': parts[4] if len(parts) > 4 else 'N/A',
                                'interface': parts[2] if len(parts) > 2 else 'N/A',
                                'state': parts[-1] if parts[-1] in ['REACHABLE', 'STALE', 'FAILED'] else 'UNKNOWN'
                            }
                            arp_table.append(arp_entry)

            return {'arp_entries': arp_table}
        except Exception as e:
            self.logger.warning(f"Error capturing host ARP: {e}")
            return {}

    def _capture_network_protocols(self, net) -> Dict[str, Any]:
        """Capture network protocol configurations"""
        try:
            protocols = {
                'ospf': {},
                'bgp': {},
                'static_routes': {},
                'dhcp': {}
            }

            # This would capture actual protocol configurations
            # For now, return placeholder structure
            return protocols

        except Exception as e:
            self.logger.error(f"Error capturing network protocols: {e}")
            return {}

    def _capture_device_states(self, net) -> Dict[str, Any]:
        """Capture comprehensive device states"""
        try:
            device_states = {}

            # Only capture if network is running
            if not net:
                return device_states

            for node in net.hosts + net.switches:
                try:
                    if hasattr(node, 'pid') and node.pid:
                        # Capture process state
                        device_states[node.name] = {
                            'pid': node.pid,
                            'running': True,
                            'interfaces': self._capture_node_interfaces(node)
                        }
                    else:
                        device_states[node.name] = {
                            'running': False,
                            'interfaces': self._capture_node_interfaces(node)
                        }
                except Exception as e:
                    self.logger.warning(f"Error capturing state for {node.name}: {e}")

            return device_states

        except Exception as e:
            self.logger.error(f"Error capturing device states: {e}")
            return {}

    def _capture_controller_switch_info(self, net, topology_data: Dict[str, Any] = None, mininet_manager=None) -> Dict[str, Any]:
        """Capture controller and switch type information"""
        try:
            controller_switch_info = {
                'controllers': {},
                'switches': {},
                'metadata': {
                    'captured_at': datetime.now().isoformat(),
                    'topology_source': 'network' if net else 'topology_data'
                }
            }

            # Get actual controller information from MininetManager if available
            actual_controller_type = 'ryu'  # default
            actual_controller_app = 'simple_switch_13'  # default
            is_controller_running = False
            
            if mininet_manager and hasattr(mininet_manager, 'controller_factory'):
                active_controller = mininet_manager.controller_factory.get_active_controller()
                if active_controller:
                    actual_controller_type = active_controller
                    controller_info = mininet_manager.controller_factory.get_controller_info().get(active_controller, {})
                    actual_controller_app = controller_info.get('current_app', 'simple_switch_13')
                    is_controller_running = controller_info.get('running', False)

            # Capture controller information
            if net and hasattr(net, 'controllers'):
                for controller in net.controllers:
                    try:
                        controller_info = {
                            'name': getattr(controller, 'name', 'unknown'),
                            'ip': getattr(controller, 'ip', '127.0.0.1'),
                            'port': getattr(controller, 'port', 6633),
                            'type': 'controller',
                            'controller_type': actual_controller_type,  # Use actual controller type
                            'app': actual_controller_app,  # Use actual app
                            'protocol': 'OpenFlow',
                            'version': '1.3',
                            'running': is_controller_running
                        }
                        controller_switch_info['controllers'][controller.name] = controller_info
                    except Exception as e:
                        self.logger.warning(f"Error capturing controller info: {e}")

            # Capture switch information
            if net and hasattr(net, 'switches'):
                for switch in net.switches:
                    try:
                        switch_info = {
                            'name': getattr(switch, 'name', 'unknown'),
                            'type': 'switch',
                            'switch_type': 'ovs',  # Default, will be updated from factory if available
                            'dpid': getattr(switch, 'dpid', 'auto'),
                            'openflow_version': '1.3',
                            'running': True,
                            'interfaces': self._capture_node_interfaces(switch)
                        }
                        controller_switch_info['switches'][switch.name] = switch_info
                    except Exception as e:
                        self.logger.warning(f"Error capturing switch info: {e}")

            # If no network but we have topology data, extract from topology
            if not net and topology_data:
                nodes = topology_data.get('nodes', [])
                for node in nodes:
                    node_type = node.get('type', 'host')
                    if node_type == 'controller':
                        controller_info = {
                            'name': node.get('id', 'unknown'),
                            'ip': node.get('ip', '127.0.0.1'),
                            'port': node.get('port', 6633),
                            'type': 'controller',
                            'controller_type': node.get('controller_type', 'ryu'),
                            'app': node.get('app', 'simple_switch_13'),
                            'protocol': node.get('protocol', 'OpenFlow'),
                            'version': node.get('version', '1.3'),
                            'running': False  # Not running if no network
                        }
                        controller_switch_info['controllers'][node['id']] = controller_info
                    elif node_type == 'switch':
                        switch_info = {
                            'name': node.get('id', 'unknown'),
                            'type': 'switch',
                            'switch_type': node.get('switch_type', 'ovs'),
                            'dpid': node.get('dpid', 'auto'),
                            'openflow_version': node.get('openflow_version', '1.3'),
                            'running': False,  # Not running if no network
                            'interfaces': {}
                        }
                        controller_switch_info['switches'][node['id']] = switch_info

            return controller_switch_info

        except Exception as e:
            self.logger.error(f"Error capturing controller/switch info: {e}")
            return {'controllers': {}, 'switches': {}, 'error': str(e)}

    def _capture_network_state(self, net) -> Dict[str, Any]:
        """Capture general network state"""
        try:
            network_state = {
                'timestamp': datetime.now().isoformat(),
                'network_running': net is not None,
                'hosts': [],
                'switches': [],
                'links': [],
                'controllers': []
            }

            if net:
                # Capture hosts
                for host in net.hosts:
                    try:
                        host_info = {
                            'name': host.name,
                            'ip': host.IP() if hasattr(host, 'IP') and callable(host.IP) else 'unknown',
                            'mac': host.MAC() if hasattr(host, 'MAC') and callable(host.MAC) else 'unknown',
                            'interfaces': self._capture_node_interfaces(host)
                        }
                        network_state['hosts'].append(host_info)
                    except Exception as e:
                        self.logger.warning(f"Error capturing host {host.name}: {e}")

                # Capture switches
                for switch in net.switches:
                    try:
                        switch_info = {
                            'name': switch.name,
                            'dpid': getattr(switch, 'dpid', 'unknown'),
                            'interfaces': self._capture_node_interfaces(switch)
                        }
                        network_state['switches'].append(switch_info)
                    except Exception as e:
                        self.logger.warning(f"Error capturing switch {switch.name}: {e}")

                # Capture links
                for link in net.links:
                    try:
                        link_info = {
                            'node1': link.intf1.node.name if hasattr(link, 'intf1') else 'unknown',
                            'node2': link.intf2.node.name if hasattr(link, 'intf2') else 'unknown',
                            'intf1': link.intf1.name if hasattr(link, 'intf1') else 'unknown',
                            'intf2': link.intf2.name if hasattr(link, 'intf2') else 'unknown'
                        }
                        network_state['links'].append(link_info)
                    except Exception as e:
                        self.logger.warning(f"Error capturing link: {e}")

                # Capture controllers
                for controller in net.controllers:
                    try:
                        controller_info = {
                            'name': controller.name,
                            'ip': getattr(controller, 'ip', '127.0.0.1'),
                            'port': getattr(controller, 'port', 6633)
                        }
                        network_state['controllers'].append(controller_info)
                    except Exception as e:
                        self.logger.warning(f"Error capturing controller: {e}")

            return network_state

        except Exception as e:
            self.logger.error(f"Error capturing network state: {e}")
            return {'error': str(e)}

    def _capture_routing_state(self, net) -> Dict[str, Any]:
        """Capture routing state from all devices"""
        try:
            routing_state = {}

            # Only capture if network is running
            if not net:
                return routing_state

            for host in net.hosts:
                try:
                    routing_state[host.name] = self._capture_host_routing(host)
                except Exception as e:
                    self.logger.warning(f"Error capturing routing state for {host.name}: {e}")

            return routing_state

        except Exception as e:
            self.logger.error(f"Error capturing routing state: {e}")
            return {}

    def _capture_firewall_state(self, net) -> Dict[str, Any]:
        """Capture firewall state from all devices"""
        try:
            firewall_state = {}

            # Only capture if network is running
            if not net:
                return firewall_state

            for host in net.hosts:
                try:
                    # Capture iptables rules
                    if hasattr(host, 'cmd'):
                        iptables_output = host.cmd('iptables -L -n')
                        firewall_state[host.name] = {
                            'iptables_rules': iptables_output,
                            'timestamp': datetime.now().isoformat()
                        }
                except Exception as e:
                    self.logger.warning(f"Error capturing firewall state for {host.name}: {e}")

            return firewall_state

        except Exception as e:
            self.logger.error(f"Error capturing firewall state: {e}")
            return {}

    def _restore_live_configurations(self, net, live_configs: Dict[str, Any]) -> None:
        """Restore live configurations to network"""
        try:
            # Restore network interfaces
            if 'network_interfaces' in live_configs:
                for node_name, interfaces in live_configs['network_interfaces'].items():
                    node = self._find_network_device(net, node_name)
                    if node:
                        self._restore_node_interfaces(node, interfaces)

            # Restore routing tables
            if 'routing_tables' in live_configs:
                for host_name, routing_config in live_configs['routing_tables'].items():
                    host = self._find_network_device(net, host_name)
                    if host and hasattr(host, 'cmd'):
                        self._restore_host_routing(host, routing_config)

        except Exception as e:
            self.logger.error(f"Error restoring live configurations: {e}")

    def _restore_device_configurations(self, net, device_configs: Dict[str, Any]) -> None:
        """Restore device configurations"""
        try:
            for device_name, config in device_configs.items():
                device = self._find_network_device(net, device_name)
                if device:
                    self._apply_device_config(device, config)
        except Exception as e:
            self.logger.error(f"Error restoring device configurations: {e}")

    def _restore_routing_configurations(self, net, routing_configs: Dict[str, Any]) -> None:
        """Restore routing configurations"""
        try:
            for device_name, routing_config in routing_configs.items():
                device = self._find_network_device(net, device_name)
                if device and hasattr(device, 'cmd'):
                    self._restore_routing_config(device, routing_config)
        except Exception as e:
            self.logger.error(f"Error restoring routing configurations: {e}")

    def _restore_firewall_configurations(self, net, firewall_configs: Dict[str, Any]) -> None:
        """Restore firewall configurations"""
        try:
            for device_name, firewall_config in firewall_configs.items():
                device = self._find_network_device(net, device_name)
                if device and hasattr(device, 'cmd'):
                    self._restore_firewall_config(device, firewall_config)
        except Exception as e:
            self.logger.error(f"Error restoring firewall configurations: {e}")

    def _find_network_device(self, net, device_name: str):
        """Find a network device by name"""
        for node in net.hosts + net.switches:
            if node.name == device_name:
                return node
        return None

    def _restore_node_interfaces(self, node, interfaces: Dict[str, Any]) -> None:
        """Restore node interfaces"""
        try:
            for intf_name, config in interfaces.items():
                if hasattr(node, 'intfList'):
                    for intf in node.intfList():
                        if intf.name == intf_name:
                            # Configure interface
                            if config.get('ip') and config['ip'] != 'N/A':
                                node.cmd(f'ip addr add {config["ip"]} dev {intf_name}')
                            break
        except Exception as e:
            self.logger.warning(f"Error restoring node interfaces: {e}")

    def _restore_host_routing(self, host, routing_config: Dict[str, Any]) -> None:
        """Restore host routing table"""
        try:
            if 'routes' in routing_config:
                for route in routing_config['routes']:
                    if route.get('destination') and route.get('gateway'):
                        host.cmd(f'ip route add {route["destination"]} via {route["gateway"]}')
                    elif route.get('destination'):
                        host.cmd(f'ip route add {route["destination"]} dev {route.get("interface", "eth0")}')
        except Exception as e:
            self.logger.warning(f"Error restoring host routing: {e}")

    def _restore_routing_config(self, device, routing_config: Dict[str, Any]) -> None:
        """Restore comprehensive routing configuration"""
        try:
            # This would implement detailed routing restoration
            # For now, just restore basic routes
            if 'routes' in routing_config:
                for route in routing_config['routes']:
                    if hasattr(device, 'cmd'):
                        if route.get('gateway'):
                            device.cmd(f'ip route add {route["destination"]} via {route["gateway"]}')
                        else:
                            device.cmd(f'ip route add {route["destination"]} dev {route.get("interface", "eth0")}')
        except Exception as e:
            self.logger.warning(f"Error restoring routing config: {e}")

    def _restore_firewall_config(self, device, firewall_config: Dict[str, Any]) -> None:
        """Restore firewall configuration"""
        try:
            # Restore iptables rules
            if 'iptables_rules' in firewall_config:
                # This is a simplified restoration
                # In practice, you'd need to parse and restore rules carefully
                self.logger.info(f"Firewall restoration for {device.name} would require iptables parsing")
        except Exception as e:
            self.logger.warning(f"Error restoring firewall config: {e}")

    def _restore_controller_switch_info(self, net, controller_switch_info: Dict[str, Any]) -> None:
        """Restore controller and switch type information"""
        try:
            # This method would restore controller and switch type configurations
            # For now, we'll log the information for debugging
            controllers = controller_switch_info.get('controllers', {})
            switches = controller_switch_info.get('switches', {})
            
            self.logger.info(f"Restoring controller/switch info: {len(controllers)} controllers, {len(switches)} switches")
            
            for controller_name, controller_info in controllers.items():
                self.logger.info(f"Controller {controller_name}: type={controller_info.get('controller_type')}, app={controller_info.get('app')}")
            
            for switch_name, switch_info in switches.items():
                self.logger.info(f"Switch {switch_name}: type={switch_info.get('switch_type')}, dpid={switch_info.get('dpid')}")
                
        except Exception as e:
            self.logger.warning(f"Error restoring controller/switch info: {e}")

    def _apply_tracked_configurations(self, mininet_manager) -> None:
        """Apply tracked configurations during snapshot restoration"""
        try:
            if not mininet_manager.net or not mininet_manager.is_running:
                self.logger.warning("Cannot apply tracked configurations: network not running")
                return
            
            self.logger.critical("=== APPLYING TRACKED CONFIGURATIONS ===")
            
            # Write debug info to file
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: _apply_tracked_configurations called\n")
            
            # Get applied configurations from the config tracker
            applied_configs = mininet_manager.config_tracker.applied_configurations
            self.logger.critical(f"DEBUG: Applied configs from tracker: {bool(applied_configs)}")
            
            # Write debug info to file
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: Applied configs from tracker: {bool(applied_configs)}\n")
                if applied_configs:
                    f.write(f"DEBUG: Applied configs keys: {list(applied_configs.keys())}\n")
            
            if not applied_configs:
                self.logger.critical("DEBUG: No applied configurations found in config tracker")
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: No applied configurations found in config tracker\n")
                return
            
            # Extract device configurations and rebuild the configuration structure
            device_configs = applied_configs.get('device_configs', {})
            self.logger.info(f"Processing {len(device_configs)} devices with configurations")
            
            # Write debug info to file
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: Processing {len(device_configs)} devices with configurations\n")
                f.write(f"DEBUG: Device configs: {list(device_configs.keys())}\n")
            
            # Rebuild the configuration structure for apply-config API
            config_structure = {
                'hosts': {},
                'routers': {}
            }
            
            for device_name, configs in device_configs.items():
                try:
                    device = self._find_network_device(mininet_manager.net, device_name)
                    if not device:
                        self.logger.warning(f"Device {device_name} not found in network")
                        continue
                    
                    # Determine device type
                    device_type = 'host'  # default
                    if hasattr(device, '__class__'):
                        class_name = str(device.__class__).lower()
                        if 'router' in class_name:
                            device_type = 'router'
                    
                    self.logger.info(f"Processing {device_type} {device_name} with {len(configs)} configurations")
                    
                    # Write debug info to file
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Processing {device_type} {device_name} with {len(configs)} configurations\n")
                    
                    # Extract the latest successful configuration
                    latest_config = None
                    for config in sorted(configs, key=lambda x: x.get('timestamp', ''), reverse=True):
                        if config.get('success', True):
                            latest_config = config
                            break
                    
                    if not latest_config:
                        self.logger.warning(f"No successful configuration found for {device_name}")
                        continue
                    
                    # Extract configuration data
                    config_data = latest_config.get('config_data', {})
                    if not config_data:
                        self.logger.warning(f"No config_data found for {device_name}")
                        continue
                    
                    # Build configuration structure based on device type
                    if device_type == 'router':
                        config_structure['routers'][device_name] = config_data
                    else:
                        config_structure['hosts'][device_name] = config_data
                    
                    self.logger.info(f"Added {device_type} {device_name} configuration: {list(config_data.keys())}")
                    
                    # Write debug info to file
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Added {device_type} {device_name} configuration: {list(config_data.keys())}\n")
                        if 'interfaces' in config_data:
                            interfaces = config_data['interfaces']
                            f.write(f"DEBUG: {device_name} interfaces: {interfaces}\n")
                    
                except Exception as e:
                    self.logger.error(f"Error processing configurations for {device_name}: {e}")
            
            # Apply the rebuilt configuration using the config manager
            if config_structure['hosts'] or config_structure['routers']:
                self.logger.info("Applying rebuilt configuration structure...")
                
                # Write debug info to file
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: About to apply configurations - hosts: {list(config_structure['hosts'].keys())}, routers: {list(config_structure['routers'].keys())}\n")
                
                self._apply_configuration_structure(mininet_manager, config_structure)
            else:
                self.logger.warning("No valid configurations to apply")
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: No valid configurations to apply\n")
            
            self.logger.info("Tracked configurations applied successfully")
            
        except Exception as e:
            self.logger.error(f"Error applying tracked configurations: {e}")

    def _apply_configuration_structure(self, mininet_manager, config_structure: Dict[str, Any]) -> None:
        """Apply configuration structure using the configuration manager"""
        try:
            if not hasattr(mininet_manager, 'config_manager') or not mininet_manager.config_manager:
                self.logger.warning("No configuration manager available, applying configurations directly")
                self._apply_configurations_directly(mininet_manager, config_structure)
                return
            
            self.logger.info("Using configuration manager to apply configurations...")
            
            # Use the configuration manager to apply the configurations
            result = mininet_manager.config_manager.apply_configuration(config_structure)
            
            if result.get('success', False):
                self.logger.info("Configurations applied successfully via config manager")
            else:
                self.logger.warning(f"Config manager failed: {result.get('error', 'Unknown error')}")
                # Fallback to direct application
                self.logger.info("Falling back to direct configuration application...")
                self._apply_configurations_directly(mininet_manager, config_structure)
                
        except Exception as e:
            self.logger.error(f"Error applying configuration structure: {e}")
            # Fallback to direct application
            self.logger.info("Falling back to direct configuration application...")
            self._apply_configurations_directly(mininet_manager, config_structure)

    def _apply_configurations_directly(self, mininet_manager, config_structure: Dict[str, Any]) -> None:
        """Apply configurations directly to network devices"""
        try:
            self.logger.info("Applying configurations directly to network devices...")
            
            # Write debug info to file
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: _apply_configurations_directly called\n")
                f.write(f"DEBUG: Hosts to apply: {list(config_structure.get('hosts', {}).keys())}\n")
                f.write(f"DEBUG: Routers to apply: {list(config_structure.get('routers', {}).keys())}\n")
            
            # Apply host configurations
            for host_name, host_config in config_structure.get('hosts', {}).items():
                try:
                    device = self._find_network_device(mininet_manager.net, host_name)
                    if not device:
                        self.logger.warning(f"Host {host_name} not found in network")
                        continue
                    
                    self.logger.info(f"Applying configuration to host {host_name}")
                    self._apply_host_config_directly(device, host_config)
                    
                except Exception as e:
                    self.logger.error(f"Error applying configuration to host {host_name}: {e}")
            
            # Apply router configurations
            for router_name, router_config in config_structure.get('routers', {}).items():
                try:
                    device = self._find_network_device(mininet_manager.net, router_name)
                    if not device:
                        self.logger.warning(f"Router {router_name} not found in network")
                        continue
                    
                    self.logger.info(f"Applying configuration to router {router_name}")
                    self._apply_router_config_directly(device, router_config)
                    
                except Exception as e:
                    self.logger.error(f"Error applying configuration to router {router_name}: {e}")
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Exception applying configuration to router {router_name}: {e}\n")
                    
        except Exception as e:
            self.logger.error(f"Error applying configurations directly: {e}")

    def _apply_host_config_directly(self, device, host_config: Dict[str, Any]) -> None:
        """Apply host configuration directly"""
        try:
            if not hasattr(device, 'cmd'):
                self.logger.warning(f"Device {device.name} does not support command execution")
                return
            
            # Apply interface configurations
            interfaces = host_config.get('interfaces', [])
            for interface in interfaces:
                interface_name = interface.get('name')
                if not interface_name:
                    continue
                
                # Flush interface if requested
                if interface.get('flush', False):
                    self.logger.info(f"Flushing interface {interface_name} on {device.name}")
                    device.cmd(f'ip addr flush dev {interface_name} 2>/dev/null || true')
                
                # Apply addresses
                addresses = interface.get('addresses', [])
                for address in addresses:
                    self.logger.info(f"Adding address {address} to {interface_name} on {device.name}")
                    device.cmd(f'ip addr add {address} dev {interface_name} 2>/dev/null || true')
                
                # Set interface state
                state = interface.get('state', 'up')
                if state == 'up':
                    self.logger.info(f"Bringing up interface {interface_name} on {device.name}")
                    device.cmd(f'ip link set dev {interface_name} up 2>/dev/null || true')
                elif state == 'down':
                    self.logger.info(f"Bringing down interface {interface_name} on {device.name}")
                    device.cmd(f'ip link set dev {interface_name} down 2>/dev/null || true')
            
            # Apply routes
            routes = host_config.get('routes', [])
            for route in routes:
                action = route.get('action', 'add')
                destination = route.get('destination')
                via = route.get('via')
                ignore_error = route.get('ignore_error', False)
                
                if not destination:
                    continue
                
                if action == 'del':
                    self.logger.info(f"Deleting route {destination} on {device.name}")
                    cmd = f'ip route del {destination}'
                    if ignore_error:
                        cmd += ' 2>/dev/null || true'
                    device.cmd(cmd)
                elif action == 'add':
                    if via:
                        self.logger.info(f"Adding route {destination} via {via} on {device.name}")
                        cmd = f'ip route add {destination} via {via}'
                        if ignore_error:
                            cmd += ' 2>/dev/null || true'
                        device.cmd(cmd)
                    else:
                        self.logger.info(f"Adding route {destination} on {device.name}")
                        cmd = f'ip route add {destination}'
                        if ignore_error:
                            cmd += ' 2>/dev/null || true'
                        device.cmd(cmd)
                        
        except Exception as e:
            self.logger.error(f"Error applying host configuration: {e}")

    def _apply_router_config_directly(self, device, router_config: Dict[str, Any]) -> None:
        """Apply router configuration directly"""
        try:
            # Write debug info to file
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: _apply_router_config_directly called for {device.name}\n")
                f.write(f"DEBUG: Router config: {list(router_config.keys())}\n")
            
            if not hasattr(device, 'cmd'):
                self.logger.warning(f"Device {device.name} does not support command execution")
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: Device {device.name} does not support command execution\n")
                return
            
            # Apply sysctl configurations
            sysctl = router_config.get('sysctl', {})
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: Applying sysctl configs: {sysctl}\n")
            for key, value in sysctl.items():
                self.logger.info(f"Setting sysctl {key}={value} on {device.name}")
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: Setting sysctl {key}={value} on {device.name}\n")
                device.cmd(f'sysctl -w {key}={value} 2>/dev/null || true')
            
            # Apply interface configurations (same as host)
            interfaces = router_config.get('interfaces', [])
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: Applying {len(interfaces)} interfaces to {device.name}\n")
            for interface in interfaces:
                interface_name = interface.get('name')
                if not interface_name:
                    continue
                
                with open('/tmp/snapshot_debug.log', 'a') as f:
                    f.write(f"DEBUG: Processing interface {interface_name} on {device.name}\n")
                
                # Flush interface if requested
                if interface.get('flush', False):
                    self.logger.info(f"Flushing interface {interface_name} on {device.name}")
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Flushing interface {interface_name} on {device.name}\n")
                    device.cmd(f'ip addr flush dev {interface_name} 2>/dev/null || true')
                
                # Apply addresses
                addresses = interface.get('addresses', [])
                for address in addresses:
                    self.logger.info(f"Adding address {address} to {interface_name} on {device.name}")
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Adding address {address} to {interface_name} on {device.name}\n")
                    # First try to delete any existing address, then add the new one
                    device.cmd(f'ip addr del {address} dev {interface_name} 2>/dev/null || true')
                    device.cmd(f'ip addr add {address} dev {interface_name} 2>/dev/null || true')
                    # Verify the address was added
                    result = device.cmd(f'ip addr show {interface_name} 2>/dev/null || echo "interface not found"')
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Interface {interface_name} after adding address: {result.strip()}\n")
                
                # Set interface state
                state = interface.get('state', 'up')
                if state == 'up':
                    self.logger.info(f"Bringing up interface {interface_name} on {device.name}")
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Bringing up interface {interface_name} on {device.name}\n")
                    device.cmd(f'ip link set dev {interface_name} up 2>/dev/null || true')
                elif state == 'down':
                    self.logger.info(f"Bringing down interface {interface_name} on {device.name}")
                    with open('/tmp/snapshot_debug.log', 'a') as f:
                        f.write(f"DEBUG: Bringing down interface {interface_name} on {device.name}\n")
                    device.cmd(f'ip link set dev {interface_name} down 2>/dev/null || true')
                    
        except Exception as e:
            self.logger.error(f"Error applying router configuration: {e}")
            with open('/tmp/snapshot_debug.log', 'a') as f:
                f.write(f"DEBUG: Exception in _apply_router_config_directly: {e}\n")

    def _apply_device_config(self, device, config: Dict[str, Any]) -> None:
        """Apply device configuration"""
        try:
            # Apply interface configurations
            if 'interfaces' in config:
                for intf_name, intf_config in config['interfaces'].items():
                    if hasattr(device, 'cmd'):
                        if intf_config.get('ip') and intf_config['ip'] != 'N/A':
                            device.cmd(f'ip addr add {intf_config["ip"]} dev {intf_name}')

            # Apply other configurations as needed
            if 'running' in config and config['running'] and hasattr(device, 'start'):
                device.start()

        except Exception as e:
            self.logger.warning(f"Error applying device config: {e}")

    def _apply_terminal_command(self, device, cmd: Dict[str, Any]) -> None:
        """Apply terminal command to device"""
        try:
            command = cmd.get('command', '')
            if command and hasattr(device, 'cmd'):
                self.logger.info(f"Executing command on {device.name}: {command}")
                result = device.cmd(command)
                self.logger.debug(f"Command result: {result}")
        except Exception as e:
            self.logger.warning(f"Error applying terminal command: {e}")

    def _apply_routing_config(self, device, routing_config: Dict[str, Any]) -> None:
        """Apply routing configuration to device"""
        try:
            if not hasattr(device, 'cmd'):
                return
            
            # Apply routes
            routes = routing_config.get('routes', [])
            for route in routes:
                if route:
                    self.logger.info(f"Adding route on {device.name}: {route}")
                    device.cmd(f'ip route add {route} 2>/dev/null || true')
            
            # Apply default gateway
            default_gateway = routing_config.get('default_gateway')
            if default_gateway:
                self.logger.info(f"Setting default gateway on {device.name}: {default_gateway}")
                device.cmd(f'ip route add default via {default_gateway} 2>/dev/null || true')
                
        except Exception as e:
            self.logger.warning(f"Error applying routing config: {e}")

    def _apply_firewall_config(self, device, firewall_config: Dict[str, Any]) -> None:
        """Apply firewall configuration to device"""
        try:
            if not hasattr(device, 'cmd'):
                return
            
            # Apply iptables rules
            rules = firewall_config.get('rules', [])
            for rule in rules:
                if rule:
                    self.logger.info(f"Applying firewall rule on {device.name}: {rule}")
                    device.cmd(f'iptables {rule} 2>/dev/null || true')
                    
        except Exception as e:
            self.logger.warning(f"Error applying firewall config: {e}")

    def _apply_interface_config(self, device, interface_config: Dict[str, Any]) -> None:
        """Apply interface configuration to device"""
        try:
            if not hasattr(device, 'cmd'):
                return
            
            # Apply interface configurations
            for interface, config in interface_config.items():
                if 'ip' in config and config['ip']:
                    self.logger.info(f"Setting IP on {device.name} interface {interface}: {config['ip']}")
                    device.cmd(f'ip addr add {config["ip"]} dev {interface} 2>/dev/null || true')
                
                if 'status' in config:
                    if config['status'] == 'up':
                        self.logger.info(f"Bringing up interface {interface} on {device.name}")
                        device.cmd(f'ip link set {interface} up 2>/dev/null || true')
                    elif config['status'] == 'down':
                        self.logger.info(f"Bringing down interface {interface} on {device.name}")
                        device.cmd(f'ip link set {interface} down 2>/dev/null || true')
                
                if 'mtu' in config:
                    self.logger.info(f"Setting MTU on {device.name} interface {interface}: {config['mtu']}")
                    device.cmd(f'ip link set {interface} mtu {config["mtu"]} 2>/dev/null || true')
                    
        except Exception as e:
            self.logger.warning(f"Error applying interface config: {e}")

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots"""
        try:
            snapshots = []
            for snapshot_file in self.snapshots_dir.glob("*.json"):
                try:
                    with open(snapshot_file, 'r') as f:
                        snapshot_data = json.load(f)

                    snapshots.append({
                        'id': snapshot_data.get('snapshot_id', snapshot_file.stem),
                        'timestamp': snapshot_data.get('timestamp', 'unknown'),
                        'file_path': str(snapshot_file),
                        'metadata': snapshot_data.get('metadata', {})
                    })
                except Exception as e:
                    self.logger.warning(f"Error reading snapshot {snapshot_file}: {e}")

            return sorted(snapshots, key=lambda x: x['timestamp'], reverse=True)

        except Exception as e:
            self.logger.error(f"Error listing snapshots: {e}")
            return []

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        try:
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            if snapshot_file.exists():
                snapshot_file.unlink()
                self.logger.info(f"Snapshot {snapshot_id} deleted")
                return True
            else:
                self.logger.warning(f"Snapshot {snapshot_id} not found")
                return False
        except Exception as e:
            self.logger.error(f"Error deleting snapshot {snapshot_id}: {e}")
            return False

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Load a snapshot from file"""
        try:
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            if snapshot_file.exists():
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                return snapshot_data
            else:
                self.logger.warning(f"Snapshot {snapshot_id} not found")
                return None
        except Exception as e:
            self.logger.error(f"Error loading snapshot {snapshot_id}: {e}")
            return None
