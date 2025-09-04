"""
Network Topology Manager
Handles topology creation, node/link management, and topology data operations
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from mininet.topo import Topo
from mininet.node import RemoteController

from utils.logger import setup_logger

logger = setup_logger(__name__)


class NetworkTopologyManager:
    """Manages network topology creation and manipulation"""

    def __init__(self, controller_factory=None, switch_factory=None):
        self.controller_factory = controller_factory
        self.switch_factory = switch_factory
        self.topology_data = {
            'nodes': [],
            'links': [],
            'controllers': [],
            'stats': {}
        }
        self.node_positions = {}  # Node positions for UI
        self.controller_config = []  # Controller configurations
        self.custom_configs = {}  # Custom node configurations
        self.node_types = {}  # Store node type information (controller_type, switch_type, etc.)
        self.logger = logger
        self.switch_mode = 'learning_bridge'  # Default switch mode
        # Explicit controller→switch links tracked from API operations
        self.controller_links = set()  # set of tuples (controller_id, switch_id)

    def create_simple_topology(self, controller_factory=None, switch_factory=None):
        """Create the default network topology with controller visibility"""
        try:
            from mininet.net import Mininet
            from mininet.node import OVSKernelSwitch, Host
            from mininet.link import TCLink
            from mininet.node import RemoteController

            # Use provided factories or fallbacks
            ctrl_factory = controller_factory or self.controller_factory
            sw_factory = switch_factory or self.switch_factory

            # Create network with RemoteController
            net = Mininet(
                controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
                switch=OVSKernelSwitch,
                link=TCLink,
                host=Host,
                autoSetMacs=True,
                autoStaticArp=False
            )

            # Add default topology (2 hosts, 1 switch)
            h1 = net.addHost('h1', ip='10.0.0.1')
            h2 = net.addHost('h2', ip='10.0.0.2')
            s1 = net.addSwitch('s1')
            net.addLink(h1, s1)
            net.addLink(h2, s1)

            # Start network
            net.start()

            # Update topology data
            self.update_topology_data(net)

            self.logger.info("Simple topology created successfully")
            return net

        except Exception as e:
            self.logger.error(f"Error creating simple topology: {e}")
            return None

    def create_custom_topology(self, topology_config: Dict[str, Any], controller_type: str = None,
                              controller_app: str = None, controller_port: int = None,
                              switch_type: str = 'ovs', controller_factory=None, switch_factory=None) -> Tuple[Optional[Any], bool]:
        """Create custom topology from configuration with optional controller specification"""
        try:
            from mininet.net import Mininet
            from mininet.link import TCLink

            os.system('mn -c > /dev/null 2>&1')
            topo = Topo()
            node_positions = {}
            nodes = topology_config.get('nodes', [])
            links = topology_config.get('links', [])

            if not nodes:
                self.logger.error("No nodes specified in topology configuration")
                return None, False

            # Separate controllers from other nodes
            network_nodes = []
            controller_nodes = []

            for node in nodes:
                node_id = node.get('id')
                node_type = node.get('type', 'host')
                x, y = node.get('x'), node.get('y')

                if node_id and x is not None and y is not None:
                    node_positions[node_id] = {'x': x, 'y': y}

                if node_type == 'controller':
                    controller_nodes.append(node)
                else:
                    network_nodes.append(node)

            # Reset explicit controller link tracking for fresh topology
            if hasattr(self, 'controller_links'):
                self.controller_links = set()

            # Add network nodes (hosts, switches, routers) to topology
            for node in network_nodes:
                node_id = node.get('id')
                node_type = node.get('type', 'host')

                try:
                    if node_type == 'host':
                        params = {}
                        if node.get('ip') and node['ip'] != 'auto':
                            params['ip'] = node['ip']
                        if node.get('mac') and node['mac'] != 'auto' and self._is_valid_mac(node['mac']):
                            params['mac'] = node['mac']
                        topo.addHost(node_id, **params)

                    elif node_type == 'switch':
                        params = {}

                        # Get switch type from node config or use default
                        node_switch_type = node.get('switch_type', switch_type)
                        self.logger.info(f"Creating switch {node_id} of type: {node_switch_type}")

                        # Handle different switch types
                        if node_switch_type == 'linux_bridge':
                            # Use Mininet's built-in LinuxBridge class
                            try:
                                from mininet.node import LinuxBridge
                                switch_class = LinuxBridge
                                self.logger.info(f"Creating Linux Bridge switch {node_id}")
                            except ImportError:
                                self.logger.warning("LinuxBridge not available, falling back to default switch")
                                switch_class = None
                        elif node_switch_type == 'p4':
                            # P4 switches require special handling
                            self.logger.info(f"Creating P4 switch {node_id}")
                            # Create P4 switch using our factory
                            sw_factory = switch_factory or self.switch_factory
                            if sw_factory:
                                p4_switch = sw_factory.create_switch('p4', node_id,
                                                                   program_name=node.get('p4_program', 'basic_forwarding'))
                                if p4_switch:
                                    # For P4 switches, we'll handle them separately
                                    switch_class = None
                                    # Mark this node as P4 for later processing
                                    params['p4_program'] = node.get('p4_program', 'basic_forwarding')
                                    params['switch_type'] = 'p4'
                                else:
                                    self.logger.error(f"Failed to create P4 switch {node_id}")
                                    self.logger.info(f"Falling back to OVS switch for {node_id}")
                                    # Fallback to OVS switch
                                    node_switch_type = 'ovs'
                                    switch_class = None
                                    params['switch_type'] = 'ovs'
                        else:  # Default to OVS
                            switch_class = None  # Use default Mininet switch
                            if node.get('dpid') and node['dpid'] != 'auto' and self._is_valid_dpid(node['dpid']):
                                params['dpid'] = node['dpid']

                            # Only use OpenFlow if we plan to start a controller
                            if controller_nodes or node_switch_type == 'ovs':
                                params['protocols'] = 'OpenFlow13'
                                self.logger.info(f"Creating OpenFlow OVS switch {node_id} (controller will be started)")
                            else:
                                self.logger.info(f"Creating learning bridge OVS switch {node_id} (no controller)")

                        # Add switch to topology
                        if switch_class:
                            topo.addSwitch(node_id, cls=switch_class, **params)
                        elif node_switch_type != 'p4':  # P4 switches are handled separately
                            topo.addSwitch(node_id, **params)

                        # Store switch type for later reference
                        if 'switch_type' not in params:
                            params['switch_type'] = node_switch_type

                    elif node_type == 'router':
                        params = {}
                        if node.get('ip') and node['ip'] != 'auto':
                            params['ip'] = node['ip']
                        if node.get('mac') and node['mac'] != 'auto' and self._is_valid_mac(node['mac']):
                            params['mac'] = node['mac']

                        # Create a proper router node
                        try:
                            from core.router import Router
                            topo.addHost(node_id, cls=Router, **params)
                            # Store node type information for later retrieval
                            if hasattr(self, 'node_types'):
                                self.node_types[node_id] = {
                                    'node_type': 'router',
                                    'controller_type': None,
                                    'switch_type': None
                                }
                            self.logger.info(f"Added router {node_id} with IP {params.get('ip', 'auto')}")
                        except Exception as e:
                            self.logger.warning(f"Could not create router node, falling back to host: {e}")
                            topo.addHost(node_id, **params)
                            # Store as host type if router creation failed
                            if hasattr(self, 'node_types'):
                                self.node_types[node_id] = {
                                    'node_type': 'host',
                                    'controller_type': None,
                                    'switch_type': None
                                }

                    else:
                        self.logger.warning(f"Unknown node type {node_type} for {node_id}")

                except Exception as e:
                    self.logger.error(f"Error adding node {node_id}: {e}")

            self.switch_mode = 'openflow' if controller_nodes else 'learning_bridge'

            # Process links: separate controller links and network links
            controller_ids = set(c.get('id') for c in controller_nodes)
            network_node_ids = [node.get('id') for node in network_nodes]
            valid_links = []

            for link in links:
                source = link.get('source')
                target = link.get('target')

                if not source or not target:
                    self.logger.error("Link missing source or target")
                    continue

                # Handle controller links - preserve explicit ones, skip auto-generated ones
                if source in controller_ids or target in controller_ids:
                    # Record explicit controller links for preservation (but don't add to Mininet topo)
                    try:
                        if hasattr(self, 'controller_links'):
                            if source in controller_ids:
                                self.controller_links.add((source, target))
                            elif target in controller_ids:
                                self.controller_links.add((target, source))
                        self.logger.info(f"Recorded explicit controller link: {source} -> {target}")
                    except Exception:
                        pass
                    # Do not add controller links to Mininet topo; controllers are external
                    continue

                # From here, treat as a regular network link
                if source not in network_node_ids or target not in network_node_ids:
                    self.logger.warning(f"Link references unknown node: {source} -> {target}")
                    continue

                valid_links.append(link)

            # Add valid links to topology
            for link in valid_links:
                source = link.get('source')
                target = link.get('target')

                params = {}

                # Handle bandwidth
                bw = link.get('bandwidth')
                if bw:
                    num = re.sub(r'[^\d.]', '', str(bw))
                    try:
                        num = float(num)
                        if num > 0:
                            params['bw'] = num
                    except:
                        self.logger.warning(f"Bad bandwidth {bw}")

                # Handle delay
                delay = link.get('delay')
                if delay and delay != 'auto':
                    if isinstance(delay, (int, float)):
                        params['delay'] = f"{delay}ms"
                    else:
                        delay_str = str(delay)
                        if not delay_str.endswith(('ms', 's', 'us')):
                            params['delay'] = f"{delay_str}ms"
                        else:
                            params['delay'] = delay_str

                # Handle loss
                loss = link.get('loss')
                if loss is not None:
                    try:
                        loss_val = float(loss)
                        if 0 <= loss_val <= 100:
                            params['loss'] = loss_val
                    except:
                        self.logger.warning(f"Bad loss {loss}")

                # Add link with or without parameters
                try:
                    if params:
                        topo.addLink(source, target, **params)
                        self.logger.info(f"Added link {source} -> {target} with params: {params}")
                    else:
                        topo.addLink(source, target)
                        self.logger.info(f"Added link {source} -> {target}")
                except Exception as e:
                    self.logger.error(f"Failed to add link {source} -> {target}: {e}")
                    # Don't fail the entire topology creation for link errors
                    continue

            # Store node positions, controller info, and original config
            self.node_positions = node_positions
            self.controller_config = controller_nodes
            self.original_topology_config = topology_config

            # Set up network parameters
            net_params = {
                'topo': topo,
                'link': TCLink,
                'autoSetMacs': True,
                'autoStaticArp': True
            }

            # Configure controller based on parameters or topology config
            controller_config = topology_config.get('controller')

            # Override controller config if parameters are provided
            if controller_type:
                if not controller_config:
                    controller_config = {}
                controller_config['type'] = 'remote'
                controller_config['framework'] = controller_type
                controller_config['app'] = controller_app or ('simple_switch_13' if controller_type != 'pox' else 'l2_learning')
                controller_config['port'] = controller_port or 6633
                controller_config['ip'] = '127.0.0.1'

            if not controller_config and controller_nodes:
                # Use first controller node as config
                first_controller = controller_nodes[0]
                controller_config = {
                    'type': 'remote',
                    'framework': first_controller.get('controller_type', 'ryu'),
                    'app': first_controller.get('app', 'simple_switch_13'),
                    'ip': first_controller.get('ip', '127.0.0.1'),
                    'port': first_controller.get('port', 6633)
                }

            # Only add controller if explicitly configured
            if controller_config and controller_config.get('type') in ('remote', 'ryu', 'pox', 'osken', 'opendaylight'):
                ip = controller_config.get('ip', '127.0.0.1')
                port = controller_config.get('port', 6633)
                controller_framework = controller_config.get('framework', 'ryu')  # Default to ryu for backward compatibility

                ctrl_factory = controller_factory or self.controller_factory
                if ctrl_factory:
                    # Validate controller framework
                    if controller_framework.lower() not in ctrl_factory.get_available_controllers():
                        self.logger.warning(f"Unknown controller framework {controller_framework}, defaulting to ryu")
                        controller_framework = 'ryu'

                    # Start the appropriate controller
                    controller_app = controller_config.get('app', 'simple_switch_13')
                    if controller_framework.lower() == 'pox':
                        controller_app = controller_config.get('app', 'l2_learning')
                    elif controller_framework.lower() == 'opendaylight':
                        controller_app = controller_config.get('app', 'l2switch')
                        # Use default REST port for ODL
                        port = controller_config.get('port', 8181)

                    success = ctrl_factory.start_controller(
                        controller_framework.lower(),
                        controller_app,
                        port
                    )

                    if not success:
                        self.logger.error(f"Failed to start {controller_framework} controller")
                        # Fall back to no controller
                        net_params['controller'] = None
                        self.logger.info("No controller will be used - switches will operate as learning bridges")
                    else:
                        # Create controller with the same ID as the controller node if it exists
                        if controller_nodes:
                            controller_name = controller_nodes[0].get('id', 'c0')
                        else:
                            controller_name = 'c0'
                        net_params['controller'] = lambda name: RemoteController(controller_name, ip=ip, port=port)
                        self.logger.info(f"Adding remote controller {controller_name} at {ip}:{port} (framework: {controller_framework})")
                else:
                    net_params['controller'] = None
                    self.logger.info("No controller factory available - switches will operate as learning bridges")
            elif controller_nodes:
                # If controller nodes exist but no explicit config, use first controller node
                first_controller = controller_nodes[0]
                ip = first_controller.get('ip', '127.0.0.1')
                port = first_controller.get('port', 6633)
                controller_name = first_controller.get('id', 'c0')
                controller_type_from_node = first_controller.get('controller_type', 'ryu')
                
                # Try to start the controller based on node configuration
                ctrl_factory = controller_factory or self.controller_factory
                if ctrl_factory:
                    controller_app = first_controller.get('app', 'simple_switch_13')
                    if controller_type_from_node.lower() == 'pox':
                        controller_app = first_controller.get('app', 'l2_learning')
                    elif controller_type_from_node.lower() == 'opendaylight':
                        controller_app = first_controller.get('app', 'l2switch')
                        port = first_controller.get('port', 8181)
                    
                    success = ctrl_factory.start_controller(
                        controller_type_from_node.lower(),
                        controller_app,
                        port
                    )
                    
                    if success:
                        self.logger.info(f"Started {controller_type_from_node} controller for topology")
                
                net_params['controller'] = lambda name: RemoteController(controller_name, ip=ip, port=port)
                self.logger.info(f"Adding controller {controller_name} from topology nodes at {ip}:{port} (type: {controller_type_from_node})")
            else:
                # No controller config and no controller nodes - use None to disable controller
                # Switches will operate as learning bridges
                net_params['controller'] = None
                self.logger.info("No controller specified - switches will operate as learning bridges")

            # Create the network
            net = Mininet(**net_params)

            # Store the original topology configuration for snapshots
            self._stored_topology = {
                'nodes': topology_config.get('nodes', []),
                'links': topology_config.get('links', []),
                'controllers': controller_nodes,
                'stats': {}
            }

            # Store node positions and controller config
            self.node_positions = node_positions
            self.controller_config = controller_nodes



            self.logger.info(f"Custom topology created with {len(network_nodes)} network nodes, "
                            f"{len(controller_nodes)} controllers, {len(valid_links)} links")
            return net, True

        except Exception as e:
            self.logger.error(f"Error creating custom topology: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None, False

    def _is_valid_mac(self, mac_address: str) -> bool:
        """Validate MAC address format"""
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(mac_pattern.match(mac_address))

    def _is_valid_dpid(self, dpid: str) -> bool:
        """Validate DPID format"""
        try:
            # DPID can be in various formats (hex, decimal)
            if dpid.startswith('0x'):
                int(dpid, 16)
            else:
                int(dpid)
            return True
        except ValueError:
            return False

    def _populate_from_stored_config(self):
        """Populate topology data from stored configuration when no network is running"""
        try:
            # Initialize topology data structure if not already set
            if not hasattr(self, 'topology_data') or not self.topology_data:
                self.topology_data = {
                    'nodes': [],
                    'links': [],
                    'controllers': [],
                    'stats': {}
                }
            
            # If topology_data already has controllers from set_topology_configuration, use them
            if self.topology_data.get('controllers'):
                self.logger.info(f"Using existing controllers from topology_data: {len(self.topology_data['controllers'])}")
                return
            
            # Add controllers from stored config
            if hasattr(self, 'controller_config') and self.controller_config:
                for controller_node in self.controller_config:
                    controller_id = controller_node.get('id')
                    
                    # Get controller status from factory
                    active_controller = 'ryu'  # default
                    is_running = False
                    controller_app = 'simple_switch_13'  # default
                    
                    if self.controller_factory:
                        active_controller = self.controller_factory.get_active_controller() or 'ryu'
                        controller_info = self.controller_factory.get_controller_info().get(active_controller, {})
                        is_running = controller_info.get('running', False)
                        controller_app = controller_info.get('current_app', 'simple_switch_13')
                    
                    # Override with stored app if available
                    if hasattr(self, 'node_types') and controller_id in self.node_types:
                        stored_app = self.node_types[controller_id].get('app')
                        if stored_app:
                            controller_app = stored_app
                    
                    # Get controller type from stored node types or config
                    controller_type = active_controller
                    if hasattr(self, 'node_types') and controller_id in self.node_types:
                        stored_type = self.node_types[controller_id].get('controller_type')
                        if stored_type:
                            controller_type = stored_type
                    
                    controller_info = {
                        'id': controller_id,
                        'type': 'controller',
                        'ip': controller_node.get('ip', '127.0.0.1'),
                        'port': controller_node.get('port', 6633),
                        'status': 'active' if is_running else 'inactive',
                        'controller_type': controller_type,
                        'app': controller_app,
                        'protocol': 'OpenFlow',
                        'version': '1.3'
                    }
                    
                    # Add position if available
                    if hasattr(self, 'node_positions') and controller_id in self.node_positions:
                        controller_info.update(self.node_positions[controller_id])
                    
                    self.topology_data['controllers'].append(controller_info)
            
            # Add nodes from stored config
            if hasattr(self, 'custom_configs') and self.custom_configs:
                for node_id, node_config in self.custom_configs.items():
                    node_type = node_config.get('type', 'host')
                    
                    node_info = {
                        'id': node_id,
                        'type': node_type,
                        'ip': node_config.get('ip', 'auto'),
                        'status': 'inactive'  # Not running if no network
                    }
                    
                    # Add type-specific attributes
                    if node_type == 'switch':
                        node_info.update({
                            'switch_type': node_config.get('switch_type', 'ovs'),
                            'dpid': node_config.get('dpid', 'auto'),
                            'openflow_version': node_config.get('openflow_version', '1.3')
                        })
                    elif node_type == 'router':
                        node_info.update({
                            'routing_protocol': node_config.get('routing_protocol', 'static')
                        })
                    elif node_type == 'controller':
                        node_info.update({
                            'controller_type': node_config.get('controller_type', 'ryu'),
                            'app': node_config.get('app', 'simple_switch_13'),
                            'port': node_config.get('port', 6633)
                        })
                    
                    # Add position if available
                    if hasattr(self, 'node_positions') and node_id in self.node_positions:
                        node_info.update(self.node_positions[node_id])
                    
                    self.topology_data['nodes'].append(node_info)
            
            # Preserve explicit controller links from stored config
            if hasattr(self, 'controller_links') and self.controller_links:
                self.logger.info(f"Preserving {len(self.controller_links)} explicit controller links from stored config")
                for controller_id, switch_id in self.controller_links:
                    link_info = {
                        'source': controller_id,
                        'target': switch_id,
                        'type': 'controller-link',
                        'status': 'inactive'
                    }
                    self.topology_data['links'].append(link_info)
                    self.logger.info(f"Preserved controller link: {controller_id} -> {switch_id}")
            else:
                self.logger.info("No explicit controller links found in stored config")
            
            self.logger.info(f"Populated topology from stored config: {len(self.topology_data['nodes'])} nodes, {len(self.topology_data['controllers'])} controllers, {len(self.topology_data['links'])} links")
            
        except Exception as e:
            self.logger.error(f"Error populating from stored config: {e}")

    def update_topology_data(self, net=None):
        """Update topology data including controller information, node positions, and controller links"""
        # If no network is running, try to populate from stored configuration
        if not net:
            # Check if topology_data already has been set from set_topology_configuration
            if (hasattr(self, 'topology_data') and 
                isinstance(self.topology_data, dict) and 
                ('controllers' in self.topology_data or 'nodes' in self.topology_data)):
                
                controllers = self.topology_data.get('controllers', [])
                nodes = self.topology_data.get('nodes', [])
                links = self.topology_data.get('links', [])
                
                self.logger.critical(f"PRESERVING TOPOLOGY DATA: {len(controllers)} controllers, {len(nodes)} nodes, {len(links)} links")
                
                if controllers:
                    for controller in controllers:
                        self.logger.critical(f"PRESERVED CONTROLLER: {controller.get('id')} - {controller.get('controller_type')}")
                else:
                    self.logger.critical("No controllers to preserve, but topology data exists")
                
                # Ensure stats are initialized
                if 'stats' not in self.topology_data:
                    self.topology_data['stats'] = {
                        'hosts': len([n for n in nodes if n.get('type') == 'host']),
                        'routers': len([n for n in nodes if n.get('type') == 'router']),
                        'switches': len([n for n in nodes if n.get('type') == 'switch']),
                        'total_controllers': len(controllers),
                        'total_nodes': len(nodes),
                        'total_links': len(links)
                    }
                
                return
            
            # Fallback to populate from stored config
            self._populate_from_stored_config()
            return
        
        # Reset topology data for live network, but preserve stored controllers and links if they exist
        stored_controllers = []
        stored_links = []
        if (hasattr(self, 'topology_data') and 
            isinstance(self.topology_data, dict)):
            if self.topology_data.get('controllers'):
                stored_controllers = self.topology_data['controllers']
                self.logger.critical(f"PRESERVING {len(stored_controllers)} stored controllers during live network update")
            if self.topology_data.get('links'):
                stored_links = self.topology_data['links']
                self.logger.critical(f"PRESERVING {len(stored_links)} stored links during live network update")
                # Debug: show what links are being preserved
                for i, link in enumerate(stored_links):
                    self.logger.critical(f"STORED LINK {i+1}: {link.get('source')} -> {link.get('target')} (type: {link.get('type')})")
        
        self.topology_data = {
            'nodes': [],
            'links': stored_links,  # Preserve stored links
            'controllers': stored_controllers,  # Preserve stored controllers
            'stats': {}
        }

        # Collect all controller information, prioritizing stored config over live network
        controllers_added = set()
        
        # Define all_links early to avoid reference errors
        all_links = stored_links + self.topology_data['links']
        
        # Track stored controller IDs to avoid duplicates
        for stored_controller in stored_controllers:
            controllers_added.add(stored_controller.get('id'))

        # Add controllers from Mininet network (only if not already in stored controllers)
        if hasattr(net, 'controllers') and net.controllers:
            for controller in net.controllers:
                controller_id = controller.name
                
                # Skip if controller already exists in stored controllers OR already processed from live network
                if controller_id in controllers_added:
                    self.logger.critical(f"SKIPPING duplicate controller from live network: {controller_id}")
                    continue
                
                # Add to controllers_added set immediately to prevent duplicates within the same live network
                controllers_added.add(controller_id)
                
                # Get active controller information from factory
                active_controller_type = 'ryu'  # default
                controller_app = 'simple_switch_13'  # default
                controller_status = 'active'
                
                if self.controller_factory:
                    active_controller_type = self.controller_factory.get_active_controller() or 'ryu'
                    controller_info_data = self.controller_factory.get_controller_info().get(active_controller_type, {})
                    controller_status = 'active' if controller_info_data.get('running', False) else 'inactive'
                    controller_app = controller_info_data.get('current_app', 'simple_switch_13')
                
                controller_info = {
                    'id': controller_id,
                    'type': 'controller',
                    'ip': getattr(controller, 'ip', '127.0.0.1'),
                    'port': getattr(controller, 'port', 6633),
                    'status': controller_status,
                    'controller_type': active_controller_type,  # Framework type (ryu, pox, osken, opendaylight)
                    'app': controller_app,  # Application name (simple_switch_13, l2_learning, etc.)
                    'protocol': 'OpenFlow',
                    'version': '1.3'
                }

                # Add position if available
                if hasattr(self, 'node_positions') and controller_id in self.node_positions:
                    controller_info.update(self.node_positions[controller_id])

                self.topology_data['controllers'].append(controller_info)

        # Then, add controllers from stored config (these have positions and custom IDs)
        # BUT ONLY if they haven't already been added from the live network
        if hasattr(self, 'controller_config'):
            for controller_node in self.controller_config:
                controller_id = controller_node.get('id')
                
                # Skip if controller already exists in stored controllers OR already processed from live network
                if controller_id in controllers_added:
                    self.logger.critical(f"SKIPPING duplicate controller from stored config: {controller_id}")
                    continue

                # Get controller status from factory
                if self.controller_factory:
                    active_controller = self.controller_factory.get_active_controller()
                    if active_controller:
                        controller_info = self.controller_factory.get_controller_info().get(active_controller, {})
                        is_running = controller_info.get('running', False)
                        controller_app = controller_info.get('current_app', 'unknown')
                    else:
                        is_running = False
                        controller_app = 'unknown'
                else:
                    is_running = False
                    controller_app = 'unknown'

                # Get controller type from stored node types or config
                controller_type = active_controller or 'ryu'
                if hasattr(self, 'node_types') and controller_id in self.node_types:
                    stored_type = self.node_types[controller_id].get('controller_type')
                    if stored_type:
                        controller_type = stored_type

                node_controller_info = {
                    'id': controller_id,
                    'type': 'controller',
                    'ip': controller_node.get('ip', '127.0.0.1'),
                    'port': controller_node.get('port', 6633),
                    'status': 'active' if is_running else 'inactive',
                    'controller_type': controller_type,  # Framework type (ryu, pox, osken, opendaylight)
                    'app': controller_app,      # Application name (simple_switch_13, l2_learning, etc.)
                    'protocol': 'OpenFlow',
                    'version': '1.3'
                }
                if hasattr(self, 'node_positions') and controller_id in self.node_positions:
                    node_controller_info.update(self.node_positions[controller_id])
                self.topology_data['controllers'].append(node_controller_info)
                controllers_added.add(controller_id)

        # Controllers from live network are already added above - skip duplicate section

        # Add network nodes (hosts, routers, switches)
        # First, add switches
        for node in net.switches:
            try:
                node_type = 'switch'
                
                # Determine switch type from node class or stored information
                switch_type = 'ovs'  # default
                if hasattr(self, 'node_types') and node.name in self.node_types:
                    stored_switch_type = self.node_types[node.name].get('switch_type')
                    if stored_switch_type:
                        switch_type = stored_switch_type
                else:
                    # Try to determine from class name
                    class_name = str(node.__class__.__name__).lower()
                    if 'linuxbridge' in class_name or 'bridge' in class_name:
                        switch_type = 'linux_bridge'
                    elif 'p4' in class_name:
                        switch_type = 'p4'
                    elif 'ovs' in class_name or 'openvswitch' in class_name:
                        switch_type = 'ovs'
                
                # Safely get IP and MAC addresses
                try:
                    if hasattr(node, 'IP') and callable(node.IP):
                        ip_addr = node.IP()
                    elif hasattr(node, 'IP'):
                        ip_addr = str(node.IP)
                    else:
                        ip_addr = 'N/A'
                except:
                    ip_addr = 'N/A'

                try:
                    if hasattr(node, 'MAC') and callable(node.MAC):
                        mac_addr = node.MAC()
                    elif hasattr(node, 'MAC'):
                        mac_addr = str(node.MAC)
                    else:
                        mac_addr = 'N/A'
                except:
                    mac_addr = 'N/A'

                node_info = {
                    'id': node.name,
                    'type': node_type,
                    'switch_type': switch_type,
                    'ip': ip_addr,
                    'mac': mac_addr,
                    'status': 'active'
                }

                # Add DPID for OpenFlow switches
                if hasattr(node, 'dpid'):
                    node_info['dpid'] = node.dpid

                # Add position if available
                if hasattr(self, 'node_positions') and node.name in self.node_positions:
                    node_info.update(self.node_positions[node.name])

                # Add additional node type information if available
                if hasattr(self, 'node_types') and node.name in self.node_types:
                    node_type_info = self.node_types[node.name]
                    if node_type_info.get('controller_type'):
                        node_info['controller_type'] = node_type_info['controller_type']

                # Add port information for switches
                if node_type == 'switch':
                    ports = []
                    if hasattr(node, 'intfList'):
                        for intf in node.intfList():
                            if intf.name != 'lo':
                                ports.append({
                                    'name': intf.name,
                                    'ip': getattr(intf, 'ip', 'N/A'),
                                    'mac': getattr(intf, 'mac', 'N/A')
                                })
                    node_info['ports'] = ports

                self.topology_data['nodes'].append(node_info)

            except Exception as e:
                node_name = getattr(node, 'name', 'unknown') if 'node' in locals() else 'unknown'
                self.logger.warning(f"Error capturing switch {node_name}: {e}")

        # Then, add hosts and routers
        for node in net.hosts:
            try:
                # Check node type from stored information first
                node_type = 'host'
                if hasattr(self, 'node_types') and node.name in self.node_types:
                    stored_type = self.node_types[node.name].get('node_type')
                    if stored_type:
                        node_type = stored_type
                else:
                    # Fallback: check class name for router detection
                    if hasattr(node, '__class__') and ('Router' in str(node.__class__) or 'router' in str(node.__class__).lower()):
                        node_type = 'router'

                # Safely get IP and MAC addresses for hosts/routers
                try:
                    if hasattr(node, 'IP') and callable(node.IP):
                        ip_addr = node.IP()
                    elif hasattr(node, 'IP'):
                        ip_addr = str(node.IP)
                    else:
                        ip_addr = 'N/A'
                except:
                    ip_addr = 'N/A'

                try:
                    if hasattr(node, 'MAC') and callable(node.MAC):
                        mac_addr = node.MAC()
                    elif hasattr(node, 'MAC'):
                        mac_addr = str(node.MAC)
                    else:
                        mac_addr = 'N/A'
                except:
                    mac_addr = 'N/A'

                node_info = {
                    'id': node.name,
                    'type': node_type,
                    'ip': ip_addr,
                    'mac': mac_addr,
                    'status': 'active'
                }

                # Add position if available
                if hasattr(self, 'node_positions') and node.name in self.node_positions:
                    node_info.update(self.node_positions[node.name])

                self.topology_data['nodes'].append(node_info)

            except Exception as e:
                node_name = getattr(node, 'name', 'unknown') if 'node' in locals() else 'unknown'
                self.logger.warning(f"Error capturing host/router {node_name}: {e}")

        # Extract links from the actual Mininet network (only if not already in stored links)
        if hasattr(net, 'links') and net.links:
            self.logger.info(f"Extracting {len(net.links)} links from Mininet network")
            for link in net.links:
                try:
                    source_node = link.intf1.node.name
                    target_node = link.intf2.node.name

                    # Check if this link already exists in stored links
                    link_exists = any(
                        l for l in stored_links 
                        if l.get('source') == source_node and l.get('target') == target_node and l.get('type') == 'network-link'
                    )
                    
                    if link_exists:
                        self.logger.critical(f"SKIPPING duplicate network link: {source_node} -> {target_node}")
                        continue

                    # Extract link parameters
                    link_info = {
                        'source': source_node,
                        'target': target_node,
                        'type': 'network-link'
                    }

                    # Add bandwidth if available
                    if hasattr(link, 'bw') and link.bw:
                        link_info['bandwidth'] = f"{link.bw}Mbps" if isinstance(link.bw, (int, float)) else str(link.bw)

                    # Add delay if available
                    if hasattr(link, 'delay') and link.delay:
                        link_info['delay'] = str(link.delay)

                    # Add loss if available
                    if hasattr(link, 'loss') and link.loss:
                        link_info['loss'] = link.loss

                    self.logger.info(f"Adding link: {source_node} -> {target_node}")
                    self.topology_data['links'].append(link_info)

                except Exception as e:
                    self.logger.warning(f"Error processing link {link}: {e}")
        else:
            self.logger.info("No links found in Mininet network")

        # Create controller-switch links in this priority order:
        # 1) Use explicitly tracked links from controller_links set (no duplicates)
        # 2) Fallback to creating links between every controller and switch only if there are no explicit controller links
        switch_nodes = [n for n in self.topology_data['nodes'] if n['type'] == 'switch']
        controllers = self.topology_data['controllers']

        # Add controller links from stored_links and controller_links set
        explicit_controller_links = [l for l in stored_links if l.get('type') == 'controller-link']
        
        # Also add controller links from the controller_links set (added via API)
        if hasattr(self, 'controller_links') and self.controller_links:
            self.logger.info(f"Found {len(self.controller_links)} controller links from API operations")
            for controller_id, target_id in self.controller_links:
                # Check if this link is not already in stored_links
                if not any(l.get('source') == controller_id and l.get('target') == target_id for l in stored_links):
                    controller_link = {
                        'source': controller_id,
                        'target': target_id,
                        'type': 'controller-link',
                        'status': 'active'
                    }
                    self.topology_data['links'].append(controller_link)
                    self.logger.info(f"Added API controller link: {controller_id} -> {target_id}")
        
        if explicit_controller_links:
            self.logger.info(f"Found {len(explicit_controller_links)} explicit controller links in stored data (already preserved)")
            for link in explicit_controller_links:
                self.logger.info(f"Preserved controller link: {link.get('source')} -> {link.get('target')}")
        else:
            self.logger.info("No explicit controller links found in stored data")

        # Store topology statistics
        self.topology_data['stats'] = {
            'total_nodes': len(self.topology_data['nodes']),
            'total_links': len(self.topology_data['links']),
            'total_controllers': len(self.topology_data['controllers']),
            'hosts': len([n for n in self.topology_data['nodes'] if n['type'] == 'host']),
            'switches': len([n for n in self.topology_data['nodes'] if n['type'] == 'switch']),
            'routers': len([n for n in self.topology_data['nodes'] if n['type'] == 'router'])
        }

        self.logger.info(f"Final topology data: {len(self.topology_data['nodes'])} nodes, {len(self.topology_data['controllers'])} controllers, {len(self.topology_data['links'])} links")
        self.logger.info(f"Links: {self.topology_data['links']}")



    def add_node(self, net, node_id: str, node_type: str = 'host', **kwargs):
        """Add a node to the running network"""
        try:
            if node_type == 'host':
                node = net.addHost(node_id, **kwargs)
            elif node_type == 'switch':
                node = net.addSwitch(node_id, **kwargs)
            elif node_type == 'router':
                # For now, treat routers as regular hosts with routing capabilities
                # TODO: Implement proper router functionality
                node = net.addHost(node_id, **kwargs)
            else:
                raise ValueError(f"Unknown node type: {node_type}")

            # Store node type information for later retrieval
            if hasattr(self, 'node_types'):
                self.node_types[node_id] = {
                    'node_type': node_type,
                    'controller_type': kwargs.get('controller_type'),
                    'switch_type': kwargs.get('switch_type')
                }

            # Update topology data
            self.update_topology_data(net)

            self.logger.info(f"Added {node_type} node: {node_id}")
            return node

        except Exception as e:
            self.logger.error(f"Error adding node {node_id}: {e}")
            return None

    def remove_node(self, net, node_id: str):
        """Remove a node from the running network"""
        try:
            # Find the node
            node = None
            for n in net.hosts:
                if n.name == node_id:
                    node = n
                    break

            if not node:
                raise ValueError(f"Node {node_id} not found")

            # Remove the node
            net.removeNode(node)

            # Update topology data
            self.update_topology_data(net)

            self.logger.info(f"Removed node: {node_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error removing node {node_id}: {e}")
            return False

    def add_link(self, net, source_id: str, target_id: str, **kwargs):
        """Add a link between two nodes"""
        try:
            # Find source and target nodes
            source_node = None
            target_node = None

            for node in net.hosts:
                if node.name == source_id:
                    source_node = node
                elif node.name == target_id:
                    target_node = node

            if not source_node or not target_node:
                raise ValueError(f"Source or target node not found: {source_id} -> {target_id}")

            # Add the link
            net.addLink(source_node, target_node, **kwargs)

            # Update topology data
            self.update_topology_data(net)

            self.logger.info(f"Added link: {source_id} <-> {target_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error adding link {source_id} -> {target_id}: {e}")
            return False

    def remove_link(self, net, source_id: str, target_id: str):
        """Remove a link between two nodes"""
        try:
            # Find the link
            link_to_remove = None
            for link in net.links:
                if ((hasattr(link.intf1, 'node') and link.intf1.node.name == source_id and
                     hasattr(link.intf2, 'node') and link.intf2.node.name == target_id) or
                    (hasattr(link.intf1, 'node') and link.intf1.node.name == target_id and
                     hasattr(link.intf2, 'node') and link.intf2.node.name == source_id)):
                    link_to_remove = link
                    break

            if not link_to_remove:
                raise ValueError(f"Link not found: {source_id} <-> {target_id}")

            # Remove the link
            net.removeLink(link_to_remove)

            # Update topology data
            self.update_topology_data(net)

            self.logger.info(f"Removed link: {source_id} <-> {target_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error removing link {source_id} <-> {target_id}: {e}")
            return False
