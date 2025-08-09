import os
import re
import time
import subprocess
import logging
from datetime import datetime

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink
from mininet.topo import Topo, SingleSwitchTopo, LinearTopo
from mininet.node import RemoteController
from .ryu_controller import RyuControllerManager
from .stats_collector import NetworkStatsCollector
from .router import Router
from utils.logger import setup_logger

# Optional controller fallback
try:
    from mininet.node import OVSController
except ImportError:
    OVSController = Controller  # fallback to basic controller

# Optional switch fallback
try:
    from mininet.node import OVSSwitch
    DEFAULT_SWITCH = OVSSwitch
    print("Using OVSSwitch")
except ImportError:
    try:
        from mininet.node import Switch
        DEFAULT_SWITCH = Switch
        print("Using generic Switch")
    except ImportError:
        DEFAULT_SWITCH = None
        print("No specific switch class available")

# Optional link fallback
try:
    from mininet.link import TCLink
    DEFAULT_LINK = TCLink
    print("Using TCLink")
except ImportError:
    try:
        from mininet.link import Link
        DEFAULT_LINK = Link
        print("Using generic Link")
    except ImportError:
        DEFAULT_LINK = None
        print("No specific link class available")

logger = setup_logger(__name__)


class MininetManager:
    """Main Mininet network management class"""
    
    def __init__(self):
        self.net = None
        self.is_running = False
        self.ryu_controller = RyuControllerManager()
        self.stats_collector = NetworkStatsCollector()
        self.topology_data = {
            'nodes': [],
            'links': [],
            'controllers': [],
            'stats': {}
        }
        self.logger = logging.getLogger(__name__)
    
    def start_ryu_controller(self, controller_type='simple_switch_13'):
        """Start Ryu controller"""
        logger.info(f"Starting Ryu controller: {controller_type}")
        return self.ryu_controller.start_controller(controller_type)
    
    def stop_ryu_controller(self):
        """Stop Ryu controller"""
        logger.info("Stopping Ryu controller")
        return self.ryu_controller.stop_controller()
    
    def restart_ryu_controller(self):
        """Restart Ryu controller"""
        logger.info("Restarting Ryu controller")
        self.stop_ryu_controller()
        time.sleep(2)
        return self.start_ryu_controller(self.ryu_controller.controller_type)
    
    def get_controller_status(self):
        """Get controller status"""
        return self.ryu_controller.get_status()
    
    def get_controller_logs(self):
        """Get controller logs"""
        return self.ryu_controller.get_logs()

    def create_simple_topology(self):
        """Create the default network topology with controller visibility"""
        try:
            # Clean any existing Mininet processes
            os.system('mn -c > /dev/null 2>&1')
            
            # Create network with RemoteController
            self.net = Mininet(
                controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
                switch=OVSKernelSwitch,
                link=TCLink,
                host=Host,
                autoSetMacs=True,
                autoStaticArp=False
            )
            
            # Add controller - THIS IS NOW TRACKED
            c0 = self.net.addController('c0', controller=RemoteController, 
                                      ip='127.0.0.1', port=6633)
            
            # Add switches
            s1 = self.net.addSwitch('s1', protocols='OpenFlow13')
            s2 = self.net.addSwitch('s2', protocols='OpenFlow13')
            
            # Add router
            r1 = self.net.addHost('r1', cls=Router, ip='10.0.1.1/24')
            
            # Add hosts in different subnets
            h1 = self.net.addHost('h1', ip='10.0.1.10/24', defaultRoute='via 10.0.1.1')
            h2 = self.net.addHost('h2', ip='10.0.1.11/24', defaultRoute='via 10.0.1.1')
            h3 = self.net.addHost('h3', ip='10.0.2.10/24', defaultRoute='via 10.0.2.1')
            h4 = self.net.addHost('h4', ip='10.0.2.11/24', defaultRoute='via 10.0.2.1')
            
            # Add links
            self.net.addLink(h1, s1, bw=10)
            self.net.addLink(h2, s1, bw=10)
            self.net.addLink(r1, s1, bw=100, intfName1='r1-eth0')
            
            self.net.addLink(h3, s2, bw=10)
            self.net.addLink(h4, s2, bw=10)
            self.net.addLink(r1, s2, bw=100, intfName1='r1-eth1')
            
            logger.info("Simple topology created successfully")
            self._print_topology_info()
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating topology: {e}")
            return False

    
    def _is_valid_mac(self, mac_address):
        """Validate MAC address format"""
        if not mac_address or mac_address.lower() == 'auto':
            return False
        
        # Check if MAC address matches expected format
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(mac_pattern, mac_address))
    
    def _is_valid_dpid(self, dpid):
        """Validate DPID format"""
        if not dpid or dpid.lower() == 'auto':
            return False
        
        try:
            # DPID should be a hex string
            int(dpid, 16)
            return True
        except ValueError:
            return False
        """Validate DPID format"""
        if not dpid or dpid.lower() == 'auto':
            return False
        
        try:
            # DPID should be a hex string
            int(dpid, 16)
            return True
        except ValueError:
            return False

    def create_custom_topology(self, topology_config):
        """Create custom topology from configuration and save node positions"""
        try:
            os.system('mn -c > /dev/null 2>&1')
            topo = Topo()
            node_positions = {}
            nodes = topology_config.get('nodes', [])
            links = topology_config.get('links', [])
            
            if not nodes:
                self.logger.error("No nodes specified in topology configuration")
                return False
            
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
                        if node.get('dpid') and node['dpid'] != 'auto' and self._is_valid_dpid(node['dpid']):
                            params['dpid'] = node['dpid']
                        
                        # Only use OpenFlow if we plan to start a controller
                        # Otherwise, switches will act as learning bridges
                        if controller_nodes:
                            params['protocols'] = 'OpenFlow13'
                            self.logger.info(f"Creating OpenFlow switch {node_id} (controller will be started)")
                        else:
                            self.logger.info(f"Creating learning bridge switch {node_id} (no controller)")
                        
                        topo.addSwitch(node_id, **params)
                        
                    elif node_type == 'router':
                        params = {}
                        if node.get('ip') and node['ip'] != 'auto': 
                            params['ip'] = node['ip']
                        topo.addHost(node_id,cls=Router, **params)
                        
                    else:
                        self.logger.warning(f"Unknown node type {node_type} for {node_id}")
                        
                except Exception as e:
                    self.logger.error(f"Error adding node {node_id}: {e}")
        
            self.switch_mode = 'openflow' if controller_nodes else 'learning_bridge'
            # Filter links to exclude controller connections
            network_node_ids = [node.get('id') for node in network_nodes]
            valid_links = []
            
            for link in links:
                source = link.get('source')
                target = link.get('target')
                
                if not source or not target:
                    self.logger.error("Link missing source or target")
                    continue
                
                # Skip links involving controllers (they'll be handled separately)
                if source in [c.get('id') for c in controller_nodes] or target in [c.get('id') for c in controller_nodes]:
                    self.logger.info(f"Skipping controller link: {source} -> {target}")
                    continue
                
                # Verify both nodes exist in network nodes
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
                if params:
                    topo.addLink(source, target, **params)
                else:
                    topo.addLink(source, target)
            
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
            
            # Configure controller only if specified in topology config or controller nodes exist
            controller_config = topology_config.get('controller')
            if not controller_config and controller_nodes:
                # Use first controller node as config
                first_controller = controller_nodes[0]
                controller_config = {
                    'type': 'remote',
                    'ip': first_controller.get('ip', '127.0.0.1'),
                    'port': first_controller.get('port', 6633)
                }
            
            # Only add controller if explicitly configured
            if controller_config and controller_config.get('type') in ('remote', 'ryu'):
                ip = controller_config.get('ip', '127.0.0.1')
                port = controller_config.get('port', 6633)
                # Create controller with the same ID as the controller node if it exists
                if controller_nodes:
                    controller_name = controller_nodes[0].get('id', 'c0')
                else:
                    controller_name = 'c0'
                net_params['controller'] = lambda name: RemoteController(controller_name, ip=ip, port=port)
                self.logger.info(f"Adding remote controller {controller_name} at {ip}:{port}")
            elif controller_nodes:
                # If controller nodes exist but no explicit config, use first controller node
                first_controller = controller_nodes[0]
                ip = first_controller.get('ip', '127.0.0.1')
                port = first_controller.get('port', 6633)
                controller_name = first_controller.get('id', 'c0')
                net_params['controller'] = lambda name: RemoteController(controller_name, ip=ip, port=port)
                self.logger.info(f"Adding controller {controller_name} from topology nodes at {ip}:{port}")
            else:
                # No controller config and no controller nodes - use None to disable controller
                # Switches will operate as learning bridges
                net_params['controller'] = None
                self.logger.info("No controller specified - switches will operate as learning bridges")
            
            # Create the network
            self.net = Mininet(**net_params)
            
            self.logger.info(f"Custom topology created with {len(network_nodes)} network nodes, "
                            f"{len(controller_nodes)} controllers, {len(valid_links)} links")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating custom topology: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def update_topology_data(self):
        """Update topology data including controller information, node positions, and controller links"""
        self.topology_data = {
            'nodes': [],
            'links': [],
            'controllers': [],
            'stats': {}
        }
        if not self.net:
            return

        # Collect all controller information, prioritizing config over default
        controllers_added = set()
        
        # First, add controllers from stored config (these have positions and custom IDs)
        if hasattr(self, 'controller_config'):
            for controller_node in self.controller_config:
                controller_id = controller_node.get('id')
                
                controller_info = {
                    'id': controller_id,
                    'type': 'controller',
                    'ip': controller_node.get('ip', '127.0.0.1'),
                    'port': controller_node.get('port', 6633),
                    'status': 'active' if self.ryu_controller.is_running else 'inactive',
                    'controller_type': self.ryu_controller.controller_type,
                    'protocol': 'OpenFlow',
                    'version': '1.3'
                }
                if hasattr(self, 'node_positions') and controller_id in self.node_positions:
                    controller_info.update(self.node_positions[controller_id])
                self.topology_data['controllers'].append(controller_info)
                
                # Also add to nodes list for visualization
                node_info = {
                    'id': controller_id,
                    'type': 'controller',
                    'ip': controller_node.get('ip', '127.0.0.1'),
                    'mac': 'N/A',
                    'status': 'active' if self.ryu_controller.is_running else 'inactive'
                }
                if hasattr(self, 'node_positions') and controller_id in self.node_positions:
                    node_info.update(self.node_positions[controller_id])
                self.topology_data['nodes'].append(node_info)
                
                controllers_added.add(controller_id)
        
        # Then, add any additional controllers from Mininet that weren't in config
        if hasattr(self.net, 'controllers') and self.net.controllers:
            for controller in self.net.controllers:
                # Skip if this controller name matches any controller node ID
                if controller.name not in controllers_added:
                    # Check if this Mininet controller corresponds to a controller node
                    controller_node_match = None
                    if hasattr(self, 'controller_config'):
                        for controller_node in self.controller_config:
                            if (controller_node.get('ip', '127.0.0.1') == getattr(controller, 'ip', '127.0.0.1') and 
                                controller_node.get('port', 6633) == getattr(controller, 'port', 6633)):
                                controller_node_match = controller_node
                                break
                    
                    # If this Mininet controller matches a controller node, skip it (already added above)
                    if controller_node_match:
                        self.logger.info(f"Skipping Mininet controller {controller.name} - matches controller node {controller_node_match.get('id')}")
                        continue
                    
                    controller_info = {
                        'id': controller.name,
                        'type': 'controller',
                        'ip': getattr(controller, 'ip', '127.0.0.1'),
                        'port': getattr(controller, 'port', 6633),
                        'status': 'active' if self.ryu_controller.is_running else 'inactive',
                        'controller_type': self.ryu_controller.controller_type,
                        'protocol': 'OpenFlow',
                        'version': '1.3'
                    }
                    if hasattr(self, 'node_positions') and controller.name in self.node_positions:
                        controller_info.update(self.node_positions[controller.name])
                    self.topology_data['controllers'].append(controller_info)

                    # Also include in nodes list for visualization
                    node_info = {
                        'id': controller.name,
                        'type': 'controller',
                        'ip': getattr(controller, 'ip', '127.0.0.1'),
                        'mac': 'N/A',
                        'status': 'active' if self.ryu_controller.is_running else 'inactive'
                    }
                    if hasattr(self, 'node_positions') and controller.name in self.node_positions:
                        node_info.update(self.node_positions[controller.name])
                    self.topology_data['nodes'].append(node_info)
                    
                    controllers_added.add(controller.name)

        # Add network nodes (hosts, routers, switches)
        for node in self.net.hosts + self.net.switches:
            # Determine node type with improved router detection
            if isinstance(node, Router):
                node_type = 'router'
            elif hasattr(node, 'node_type') and node.node_type == 'router':
                node_type = 'router'
            elif hasattr(node, 'get_type') and callable(node.get_type):
                try:
                    node_type = node.get_type()
                except:
                    node_type = 'host' if isinstance(node, Host) else 'switch'
            elif isinstance(node, Host):
                node_type = 'host'
            else:
                node_type = 'switch'

            node_ip = node.IP() if hasattr(node, 'IP') and node_type in ['host', 'router'] else ''
            node_mac = getattr(node, 'MAC', lambda: 'auto')() if node_type in ['host', 'router'] else 'N/A'

            node_info = {
                'id': node.name,
                'type': node_type,
                'ip': node_ip,
                'mac': node_mac,
                'status': 'active' if self.is_running else 'inactive'
            }
            if hasattr(self, 'node_positions') and node.name in self.node_positions:
                node_info.update(self.node_positions[node.name])

            # Add interface information for routers
            if node_type == 'router':
                interfaces = []
                for intf in node.intfList():
                    if intf.name != 'lo':
                        try:
                            interfaces.append({
                                'name': intf.name,
                                'ip': intf.IP() if hasattr(intf, 'IP') else 'unknown',
                                'mac': intf.MAC() if hasattr(intf, 'MAC') else 'unknown'
                            })
                        except:
                            interfaces.append({
                                'name': intf.name,
                                'ip': 'unknown',
                                'mac': 'unknown'
                            })
                node_info['interfaces'] = interfaces

            # Add port information for switches
            elif node_type == 'switch':
                ports = []
                for intf in node.intfList():
                    if intf.name != 'lo':
                        ports.append({
                            'name': intf.name,
                            'port': getattr(intf, 'port', 'unknown'),
                            'link': getattr(intf, 'link', None) is not None
                        })
                node_info['ports'] = ports
                if self.is_running:
                    # Only set controller if one exists
                    if self.topology_data['controllers']:
                        node_info['controller'] = self.topology_data['controllers'][0]['id']
                    else:
                        node_info['controller'] = 'none'
                    node_info['openflow_version'] = '1.3'

            self.topology_data['nodes'].append(node_info)

        # Add physical links from Mininet
        for link in self.net.links:
            try:
                bw = link.intf1.params.get('bw', 'unknown')
                bw = f"{bw}Mbit" if bw != 'unknown' else bw
            except:
                bw = 'unknown'
            self.topology_data['links'].append({
                'source': link.intf1.node.name,
                'target': link.intf2.node.name,
                'type': 'physical',
                'bandwidth': bw,
                'status': 'up' if self.is_running else 'down'
            })

        # Add controller links from original topology configuration
        if hasattr(self, 'original_topology_config'):
            original_links = self.original_topology_config.get('links', [])
            controller_ids = [c['id'] for c in self.topology_data['controllers']]
            
            for link in original_links:
                source = link.get('source')
                target = link.get('target')
                
                # Check if this is a controller link
                if source in controller_ids or target in controller_ids:
                    # Verify both nodes exist in our topology
                    all_node_ids = [n['id'] for n in self.topology_data['nodes']]
                    if source in all_node_ids and target in all_node_ids:
                        self.topology_data['links'].append({
                            'source': source,
                            'target': target,
                            'type': 'control',
                            'bandwidth': 'N/A',
                            'status': 'up' if self.is_running else 'down'
                        })

        # If we don't have the original config, create default controller links to all switches
        elif self.topology_data['controllers']:
            switch_nodes = [n for n in self.topology_data['nodes'] if n['type'] == 'switch']
            
            for controller in self.topology_data['controllers']:
                for switch in switch_nodes:
                    self.topology_data['links'].append({
                        'source': controller['id'],
                        'target': switch['id'],
                        'type': 'control',
                        'bandwidth': 'N/A',
                        'status': 'up' if self.is_running else 'down'
                    })

        # Add statistics
        router_count = len([node for node in self.net.hosts if isinstance(node, Router) or 
                        (hasattr(node, 'node_type') and node.node_type == 'router')])
        host_count = len(self.net.hosts) - router_count
        self.topology_data['stats'] = {
            'hosts': host_count,
            'routers': router_count,
            'switches': len(self.net.switches),
            'controllers': len(self.topology_data['controllers']),
            'links': len(self.topology_data['links']),
            'status': 'running' if self.is_running else 'stopped',
            'controller_status': self.get_controller_status()
        }


    def _parse_frontend_topology(self, frontend_topology):
        """Parse frontend topology format to backend format"""
        try:
            # Handle both direct config and nested topology
            if 'topology' in frontend_topology:
                config = frontend_topology['topology']
            else:
                config = frontend_topology
            
            # Separate nodes by type
            parsed = {
                'name': config.get('name', 'Custom Topology'),
                'hosts': [],
                'switches': [],
                'routers': [],
                'controllers': [],
                'links': config.get('links', [])
            }
            
            # Process nodes and separate by type
            for node in config.get('nodes', []):
                node_type = node.get('type', 'host')
                node_data = {
                    'id': node['id'],
                    'ip': node.get('ip', 'auto'),
                    'type': node_type
                }
                
                # Add type-specific attributes
                if node_type == 'switch':
                    node_data['dpid'] = node.get('dpid', 'auto')
                    node_data['openflow_version'] = node.get('openflow_version', '1.3')
                    parsed['switches'].append(node_data)
                elif node_type == 'router':
                    node_data['routing_protocol'] = node.get('routing_protocol', 'static')
                    parsed['routers'].append(node_data)
                elif node_type == 'controller':
                    node_data['port'] = node.get('port', 6633)
                    parsed['controllers'].append(node_data)
                else:  # host
                    node_data['mac'] = node.get('mac', 'auto')
                    parsed['hosts'].append(node_data)
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing frontend topology: {e}")
            raise e


    def create_predefined_topology(self, topology_config):
        """Create predefined topology types"""
        try:
            topo_type = topology_config.get('type', 'simple')
            
            # Clean any existing processes
            os.system('mn -c > /dev/null 2>&1')
            
            if topo_type == 'simple':
                hosts = topology_config.get('hosts', 2)
                switches = topology_config.get('switches', 1)
                self.net = Mininet(topo=SingleSwitchTopo(k=hosts))
                
            elif topo_type == 'linear':
                hosts = topology_config.get('hosts', 4)
                switches = topology_config.get('switches', 4)
                self.net = Mininet(topo=LinearTopo(k=hosts))
                
            elif topo_type == 'tree':
                depth = topology_config.get('depth', 3)
                fanout = topology_config.get('fanout', 2)
                self.net = Mininet(topo=TreeTopo(depth=depth, fanout=fanout))
                
            elif topo_type == 'star':
                hosts = topology_config.get('hosts', 6)
                # Star topology is essentially a single switch topology
                self.net = Mininet(topo=SingleSwitchTopo(k=hosts))
                
            elif topo_type == 'mesh':
                hosts = topology_config.get('hosts', 4)
                # Create a mesh topology using custom implementation
                self.net = Mininet(topo=self._create_mesh_topology(hosts))
                
            elif topo_type == 'ring':
                hosts = topology_config.get('hosts', 6)
                # Create a ring topology
                self.net = Mininet(topo=self._create_ring_topology(hosts))
                
            elif topo_type == 'fattree':
                k = topology_config.get('k', 4)  # k-ary fat tree
                # Create fat tree topology
                self.net = Mininet(topo=self._create_fattree_topology(k))
                
            elif topo_type == 'datacenter':
                pods = topology_config.get('pods', 4)
                hosts_per_pod = topology_config.get('hosts_per_pod', 2)
                # Create datacenter-like topology
                self.net = Mininet(topo=self._create_datacenter_topology(pods, hosts_per_pod))
                
            else:
                logger.error(f"Unknown predefined topology type: {topo_type}")
                return False
            
            # Set controller if specified
            controller_config = topology_config.get('controller', {})
            if controller_config:
                controller_type = controller_config.get('type', 'ovs')
                controller_ip = controller_config.get('ip', '127.0.0.1')
                controller_port = controller_config.get('port', 6633)
                
                if controller_type == 'remote':
                    self.net.addController('c0', controller=RemoteController, 
                                         ip=controller_ip, port=controller_port)
                elif controller_type == 'ryu':
                    # Use Ryu controller
                    self.net.addController('c0', controller=RemoteController, 
                                         ip=controller_ip, port=controller_port)
            
            # Configure link parameters if specified
            link_config = topology_config.get('links', {})
            if link_config:
                bandwidth = link_config.get('bandwidth', None)
                delay = link_config.get('delay', None)
                loss = link_config.get('loss', None)
                
                # Apply link configuration to all links
                for link in self.net.links:
                    if bandwidth:
                        link.intf1.config(bw=bandwidth)
                        link.intf2.config(bw=bandwidth)
                    if delay:
                        link.intf1.config(delay=delay)
                        link.intf2.config(delay=delay)
                    if loss:
                        link.intf1.config(loss=loss)
                        link.intf2.config(loss=loss)
            
            logger.info(f"Created predefined topology: {topo_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating predefined topology: {e}")
            return False

    def _create_mesh_topology(self, num_hosts):
        """Create a mesh topology where all switches are connected"""
        from mininet.topo import Topo
        
        class MeshTopo(Topo):
            def __init__(self, hosts=4):
                Topo.__init__(self)
                
                # Add switches
                switches = []
                for i in range(hosts):
                    switch = self.addSwitch(f's{i+1}')
                    switches.append(switch)
                    
                    # Add host connected to this switch
                    host = self.addHost(f'h{i+1}')
                    self.addLink(host, switch)
                
                # Connect all switches to each other (full mesh)
                for i in range(len(switches)):
                    for j in range(i+1, len(switches)):
                        self.addLink(switches[i], switches[j])
        
        return MeshTopo(num_hosts)

    def _create_ring_topology(self, num_hosts):
        """Create a ring topology"""
        from mininet.topo import Topo
        
        class RingTopo(Topo):
            def __init__(self, hosts=6):
                Topo.__init__(self)
                
                # Add switches and hosts
                switches = []
                for i in range(hosts):
                    switch = self.addSwitch(f's{i+1}')
                    switches.append(switch)
                    
                    # Add host connected to this switch
                    host = self.addHost(f'h{i+1}')
                    self.addLink(host, switch)
                
                # Connect switches in a ring
                for i in range(len(switches)):
                    next_switch = switches[(i + 1) % len(switches)]
                    self.addLink(switches[i], next_switch)
        
        return RingTopo(num_hosts)

    def _create_fattree_topology(self, k):
        """Create a k-ary fat tree topology"""
        from mininet.topo import Topo
        
        class FatTreeTopo(Topo):
            def __init__(self, k=4):
                Topo.__init__(self)
                
                # Core switches
                core_switches = []
                for i in range((k//2)**2):
                    core = self.addSwitch(f'core{i+1}')
                    core_switches.append(core)
                
                # Pod switches and hosts
                pods = k
                for pod in range(pods):
                    # Aggregation switches in this pod
                    agg_switches = []
                    for i in range(k//2):
                        agg = self.addSwitch(f'agg{pod}_{i}')
                        agg_switches.append(agg)
                    
                    # Edge switches in this pod
                    edge_switches = []
                    for i in range(k//2):
                        edge = self.addSwitch(f'edge{pod}_{i}')
                        edge_switches.append(edge)
                        
                        # Connect hosts to edge switches
                        for j in range(k//2):
                            host = self.addHost(f'h{pod}_{i}_{j}')
                            self.addLink(host, edge)
                    
                    # Connect edge to aggregation switches
                    for edge in edge_switches:
                        for agg in agg_switches:
                            self.addLink(edge, agg)
                    
                    # Connect aggregation switches to core switches
                    for i, agg in enumerate(agg_switches):
                        for j in range(k//2):
                            core_idx = i * (k//2) + j
                            if core_idx < len(core_switches):
                                self.addLink(agg, core_switches[core_idx])
        
        return FatTreeTopo(k)

    def _create_datacenter_topology(self, pods, hosts_per_pod):
        """Create a datacenter-like topology"""
        from mininet.topo import Topo
        
        class DatacenterTopo(Topo):
            def __init__(self, pods=4, hosts_per_pod=2):
                Topo.__init__(self)
                
                # Core switch
                core = self.addSwitch('core1')
                
                # Pod switches and hosts
                for pod in range(pods):
                    # Top of rack switch for this pod
                    tor = self.addSwitch(f'tor{pod+1}')
                    self.addLink(core, tor)
                    
                    # Hosts in this pod
                    for host in range(hosts_per_pod):
                        h = self.addHost(f'h{pod+1}_{host+1}')
                        self.addLink(h, tor)
        
        return DatacenterTopo(pods, hosts_per_pod)

    def _parse_bandwidth(self, bw_string):
        """Parse bandwidth string to numeric value in Mbps"""
        try:
            if isinstance(bw_string, (int, float)):
                return bw_string
            
            bw_string = str(bw_string).upper()
            
            # Remove whitespace
            bw_string = bw_string.replace(' ', '')
            
            # Parse numeric part and unit
            import re
            match = re.match(r'(\d+(?:\.\d+)?)(.*)', bw_string)
            if not match:
                logger.warning(f"Could not parse bandwidth '{bw_string}', using default 10 Mbps")
                return 10
            
            value = float(match.group(1))
            unit = match.group(2).upper()
            
            # Convert to Mbps
            if unit in ['', 'M', 'MBPS', 'MB/S']:
                return value
            elif unit in ['K', 'KBPS', 'KB/S']:
                return value / 1000
            elif unit in ['G', 'GBPS', 'GB/S']:
                return value * 1000
            else:
                logger.warning(f"Unknown bandwidth unit '{unit}', treating as Mbps")
                return value
                
        except Exception as e:
            logger.warning(f"Error parsing bandwidth '{bw_string}': {e}, using default 10 Mbps")
            return 10
    
    def _configure_router(self, router):
        """Configure router interfaces and routing"""
        try:
            # Configure router interfaces
            router.cmd('ifconfig r1-eth0 10.0.1.1/24')
            router.cmd('ifconfig r1-eth1 10.0.2.1/24')
            
            # Add routing table entries
            router.cmd('ip route add 10.0.1.0/24 dev r1-eth0')
            router.cmd('ip route add 10.0.2.0/24 dev r1-eth1')
            
            logger.info("Router configured successfully")
            
        except Exception as e:
            logger.error(f"Error configuring router: {e}")
    
    def _print_topology_info(self):
        """Print topology information"""
        info("*** Topology Information:\n")
        info("Subnet 1 (10.0.1.0/24):\n")
        info("  - h1: 10.0.1.10/24 -> s1\n")
        info("  - h2: 10.0.1.11/24 -> s1\n")
        info("  - r1-eth0: 10.0.1.1/24 -> s1\n")
        info("Subnet 2 (10.0.2.0/24):\n")
        info("  - h3: 10.0.2.10/24 -> s2\n")
        info("  - h4: 10.0.2.11/24 -> s2\n")
        info("  - r1-eth1: 10.0.2.1/24 -> s2\n")
        info("Router: r1 (connects s1 and s2)\n")
        info("Controller: c0 (127.0.0.1:6633)\n")
    
    
    def start_network(self):
        """Start the network"""
        try:
            if not self.net:
                self.logger.error("No network to start. Create topology first.")
                return False
            
            self.logger.info("Starting Mininet network")
            self.net.start()
            
            # Wait a moment for network to stabilize
            import time
            time.sleep(2)
            
            # Test connectivity
            self.logger.info("Testing network connectivity")            
            self.is_running = True
            
            # Start statistics collection if available
            if hasattr(self, 'stats_collector'):
                self.stats_collector.start_collection()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting network: {e}")
            return False
        
    def stop_network(self):
        """Stop the Mininet network and Ryu controller"""
        try:
            # Stop statistics collection
            self.stats_collector.stop_collection()
            
            if self.net:
                self.net.stop()
                self.is_running = False
                logger.info("Mininet network stopped")
            
            self.stop_ryu_controller()
            self.net = None
            
            # Clear topology data
            self.topology_data = {
                'nodes': [],
                'links': [],
                'controllers': [],
                'stats': {}
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping network: {e}")
            return False

    def ping_test(self):
        """Run ping test between all hosts"""
        if not self.net or not self.is_running:
            return {'error': 'Network not running'}
        
        try:
            logger.info("Running ping test")
            result = self.net.pingAll()
            packet_loss = re.search(r'(\d+)% packet loss', str(result))
            loss_percent = packet_loss.group(1) if packet_loss else '0'
            
            return {
                'result': f'Ping test completed with {loss_percent}% packet loss',
                'success': True,
                'packet_loss': loss_percent
            }
        except Exception as e:
            logger.error(f"Ping test failed: {e}")
            return {'error': f'Ping test failed: {str(e)}', 'success': False}
    
    def get_flow_stats(self):
        """Get flow statistics from switches"""
        if not self.net or not self.is_running:
            return {}
        
        flow_stats = {}
        try:
            for switch in self.net.switches:
                try:
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-flows', switch.name],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        flows = result.stdout.strip().split('\n')[1:]
                        flow_stats[switch.name] = {
                            'flow_count': len(flows),
                            'flows': flows[:10]
                        }
                except subprocess.TimeoutExpired:
                    flow_stats[switch.name] = {'error': 'timeout'}
                except Exception as e:
                    flow_stats[switch.name] = {'error': str(e)}
                    
        except Exception as e:
            logger.error(f"Error getting flow stats: {e}")
            
        return flow_stats
    
    def get_network_metrics(self):
        """Get real-time network metrics"""
        if not self.is_running or not self.net:
            return {
                'uptime': '00:00:00',
                'packets_transferred': 0,
                'total_bytes': 0,
                'bandwidth_mbps': 0.0,
                'latency_ms': 0.0,
                'active_flows': 0,
                'total_interfaces': 0
            }
        
        return self.stats_collector.get_network_metrics(self.net)
    
    def execute_host_command(self, host_id, command):
        """Execute command on a specific host"""
        if not self.net or not self.is_running:
            return {'error': 'Network not running', 'success': False}
        
        host = self.net.get(host_id)
        if not host:
            return {'error': f'Host {host_id} not found', 'success': False}
        
        try:
            result = host.cmd(command)
            logger.info(f"Executed command '{command}' on {host_id}")
            return {'result': result.strip(), 'success': True}
        except Exception as e:
            logger.error(f"Command execution failed on {host_id}: {e}")
            return {'error': str(e), 'success': False}
    
    def start_cli(self):
        """Start Mininet CLI"""
        if self.net:
            logger.info("Starting CLI")
            CLI(self.net)
    def diagnose_connectivity_issues(self):
        """
        Diagnose connectivity issues in the network
        Returns detailed analysis of network connectivity problems
        """
        if not self.net or not self.is_running:
            return {
                'status': 'error',
                'message': 'Network not running',
                'issues': ['Network is not started'],
                'recommendations': ['Start the network first']
            }
        
        try:
            issues = []
            recommendations = []
            detailed_results = {}
            
            # 1. Check controller connectivity
            controller_issues = self._check_controller_connectivity()
            if controller_issues['issues']:
                issues.extend(controller_issues['issues'])
                recommendations.extend(controller_issues['recommendations'])
            detailed_results['controller'] = controller_issues
            
            # 2. Check switch connectivity to controller
            switch_controller_issues = self._check_switch_controller_connectivity()
            if switch_controller_issues['issues']:
                issues.extend(switch_controller_issues['issues'])
                recommendations.extend(switch_controller_issues['recommendations'])
            detailed_results['switch_controller'] = switch_controller_issues
            
            # 3. Check host-to-host connectivity
            host_connectivity_issues = self._check_host_connectivity()
            if host_connectivity_issues['issues']:
                issues.extend(host_connectivity_issues['issues'])
                recommendations.extend(host_connectivity_issues['recommendations'])
            detailed_results['host_connectivity'] = host_connectivity_issues
            
            # 4. Check interface status
            interface_issues = self._check_interface_status()
            if interface_issues['issues']:
                issues.extend(interface_issues['issues'])
                recommendations.extend(interface_issues['recommendations'])
            detailed_results['interfaces'] = interface_issues
            
            # 5. Check flow table status
            flow_issues = self._check_flow_tables()
            if flow_issues['issues']:
                issues.extend(flow_issues['issues'])
                recommendations.extend(flow_issues['recommendations'])
            detailed_results['flows'] = flow_issues
            
            # 6. Check ARP tables
            arp_issues = self._check_arp_tables()
            if arp_issues['issues']:
                issues.extend(arp_issues['issues'])
                recommendations.extend(arp_issues['recommendations'])
            detailed_results['arp'] = arp_issues
            
            # 7. Check routing (for routers)
            routing_issues = self._check_routing_tables()
            if routing_issues['issues']:
                issues.extend(routing_issues['issues'])
                recommendations.extend(routing_issues['recommendations'])
            detailed_results['routing'] = routing_issues
            
            # Overall status
            status = 'healthy' if not issues else 'issues_found'
            
            return {
                'status': status,
                'message': f'Found {len(issues)} connectivity issues' if issues else 'No connectivity issues detected',
                'issues': issues,
                'recommendations': recommendations,
                'detailed_results': detailed_results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during connectivity diagnosis: {e}")
            return {
                'status': 'error',
                'message': f'Diagnosis failed: {str(e)}',
                'issues': [f'Diagnostic error: {str(e)}'],
                'recommendations': ['Check system logs for more details']
            }

    def _check_controller_connectivity(self):
        """Check if controller is running and accessible"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            # Check if Ryu controller is running
            if not self.ryu_controller.is_running:
                issues.append("Ryu controller is not running")
                recommendations.append("Start the Ryu controller")
                details['controller_running'] = False
            else:
                details['controller_running'] = True
                
            # Check controller process
            controller_status = self.get_controller_status()
            details['controller_status'] = controller_status
            
            if controller_status.get('running', False):
                # Check if controller port is accessible
                import socket
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(('127.0.0.1', self.ryu_controller.controller_port))
                    sock.close()
                    
                    if result != 0:
                        issues.append(f"Controller port {self.ryu_controller.controller_port} is not accessible")
                        recommendations.append("Check if controller is listening on the correct port")
                        details['port_accessible'] = False
                    else:
                        details['port_accessible'] = True
                        
                except Exception as e:
                    issues.append(f"Cannot check controller port accessibility: {e}")
                    details['port_check_error'] = str(e)
            
        except Exception as e:
            issues.append(f"Controller connectivity check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_switch_controller_connectivity(self):
        """Check if switches are connected to controller"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            switches = [s for s in self.net.switches]
            details['switches_checked'] = len(switches)
            details['switch_details'] = {}
            
            for switch in switches:
                switch_details = {}
                
                try:
                    # Check if switch is connected to controller using ovs-vsctl
                    result = subprocess.run(
                        ['ovs-vsctl', 'get-controller', switch.name],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        controller_info = result.stdout.strip()
                        switch_details['controller_configured'] = controller_info
                        
                        if 'tcp:' not in controller_info:
                            issues.append(f"Switch {switch.name} has no controller configured")
                            recommendations.append(f"Configure controller for switch {switch.name}")
                    else:
                        issues.append(f"Cannot get controller info for switch {switch.name}")
                        switch_details['controller_configured'] = 'unknown'
                    
                    # Check OpenFlow connection status
                    result = subprocess.run(
                        ['ovs-vsctl', 'show'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        ovs_output = result.stdout
                        if switch.name in ovs_output:
                            if 'is_connected: true' in ovs_output:
                                switch_details['connected'] = True
                            else:
                                switch_details['connected'] = False
                                issues.append(f"Switch {switch.name} is not connected to controller")
                                recommendations.append(f"Check OpenFlow connection for {switch.name}")
                    
                except subprocess.TimeoutExpired:
                    issues.append(f"Timeout checking switch {switch.name}")
                    switch_details['timeout'] = True
                except Exception as e:
                    issues.append(f"Error checking switch {switch.name}: {e}")
                    switch_details['error'] = str(e)
                    
                details['switch_details'][switch.name] = switch_details
                
        except Exception as e:
            issues.append(f"Switch-controller connectivity check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_host_connectivity(self):
        """Check host-to-host connectivity"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            hosts = [h for h in self.net.hosts if not isinstance(h, Router)]
            details['hosts_checked'] = len(hosts)
            details['ping_results'] = {}
            
            if len(hosts) < 2:
                details['note'] = 'Less than 2 hosts available for connectivity testing'
                return {
                    'issues': issues,
                    'recommendations': recommendations,
                    'details': details
                }
            
            # Test connectivity between all pairs of hosts
            failed_pairs = []
            total_tests = 0
            
            for i, host1 in enumerate(hosts):
                for host2 in hosts[i+1:]:
                    total_tests += 1
                    try:
                        # Ping from host1 to host2
                        result = host1.cmd(f'ping -c 1 -W 2 {host2.IP()}')
                        
                        if '1 packets transmitted, 1 received' in result:
                            details['ping_results'][f'{host1.name}->{host2.name}'] = 'success'
                        else:
                            details['ping_results'][f'{host1.name}->{host2.name}'] = 'failed'
                            failed_pairs.append((host1.name, host2.name))
                            
                    except Exception as e:
                        details['ping_results'][f'{host1.name}->{host2.name}'] = f'error: {e}'
                        failed_pairs.append((host1.name, host2.name))
            
            details['total_tests'] = total_tests
            details['failed_tests'] = len(failed_pairs)
            
            if failed_pairs:
                issues.append(f"Connectivity failed between {len(failed_pairs)} host pairs")
                recommendations.append("Check switch flow tables and ARP resolution")
                for pair in failed_pairs:
                    issues.append(f"No connectivity: {pair[0]} -> {pair[1]}")
                    
        except Exception as e:
            issues.append(f"Host connectivity check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_interface_status(self):
        """Check interface status for all nodes"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            all_nodes = self.net.hosts + self.net.switches
            details['interfaces'] = {}
            
            for node in all_nodes:
                node_interfaces = {}
                
                try:
                    for intf in node.intfList():
                        if intf.name == 'lo':
                            continue
                            
                        intf_info = {
                            'name': intf.name,
                            'up': intf.isUp(),
                            'ip': getattr(intf, 'ip', 'N/A'),
                            'mac': getattr(intf, 'mac', 'N/A')
                        }
                        
                        if not intf.isUp():
                            issues.append(f"Interface {intf.name} on {node.name} is down")
                            recommendations.append(f"Bring up interface {intf.name} on {node.name}")
                            
                        node_interfaces[intf.name] = intf_info
                        
                except Exception as e:
                    node_interfaces['error'] = str(e)
                    issues.append(f"Cannot check interfaces on {node.name}: {e}")
                    
                details['interfaces'][node.name] = node_interfaces
                
        except Exception as e:
            issues.append(f"Interface status check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_flow_tables(self):
        """Check OpenFlow flow tables on switches"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            switches = [s for s in self.net.switches]
            details['flow_tables'] = {}
            
            for switch in switches:
                switch_flows = {}
                
                try:
                    # Get flow table using ovs-ofctl
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-flows', switch.name, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        flow_lines = result.stdout.strip().split('\n')[1:]  # Skip header
                        switch_flows['flow_count'] = len(flow_lines)
                        switch_flows['flows'] = flow_lines[:5]  # First 5 flows
                        
                        if len(flow_lines) == 0:
                            issues.append(f"No flows installed on switch {switch.name}")
                            recommendations.append(f"Check controller application and host connectivity")
                        elif len(flow_lines) < 2:
                            issues.append(f"Very few flows on switch {switch.name} (only {len(flow_lines)})")
                            recommendations.append(f"Generate some traffic to populate flow tables")
                            
                    else:
                        switch_flows['error'] = 'Cannot dump flows'
                        issues.append(f"Cannot dump flows from switch {switch.name}")
                        
                except subprocess.TimeoutExpired:
                    switch_flows['error'] = 'timeout'
                    issues.append(f"Timeout dumping flows from switch {switch.name}")
                except Exception as e:
                    switch_flows['error'] = str(e)
                    issues.append(f"Error checking flows on switch {switch.name}: {e}")
                    
                details['flow_tables'][switch.name] = switch_flows
                
        except Exception as e:
            issues.append(f"Flow table check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_arp_tables(self):
        """Check ARP tables on hosts"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            hosts = [h for h in self.net.hosts if not isinstance(h, Router)]
            details['arp_tables'] = {}
            
            for host in hosts:
                arp_info = {}
                
                try:
                    # Get ARP table
                    result = host.cmd('arp -a')
                    arp_info['arp_output'] = result.strip()
                    
                    # Count ARP entries
                    arp_lines = [line for line in result.strip().split('\n') if line and '(' in line]
                    arp_info['arp_entries'] = len(arp_lines)
                    
                    if len(arp_lines) == 0:
                        issues.append(f"Host {host.name} has empty ARP table")
                        recommendations.append(f"Generate traffic from {host.name} to populate ARP table")
                        
                except Exception as e:
                    arp_info['error'] = str(e)
                    issues.append(f"Cannot check ARP table on {host.name}: {e}")
                    
                details['arp_tables'][host.name] = arp_info
                
        except Exception as e:
            issues.append(f"ARP table check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_routing_tables(self):
        """Check routing tables on routers"""
        issues = []
        recommendations = []
        details = {}
        
        try:
            routers = [r for r in self.net.hosts if isinstance(r, Router) or 
                    (hasattr(r, 'node_type') and r.node_type == 'router')]
            details['routers_checked'] = len(routers)
            details['routing_tables'] = {}
            
            for router in routers:
                routing_info = {}
                
                try:
                    # Get routing table
                    result = router.cmd('ip route show')
                    routing_info['routes'] = result.strip()
                    
                    # Count routes
                    route_lines = [line for line in result.strip().split('\n') if line]
                    routing_info['route_count'] = len(route_lines)
                    
                    # Check for default route
                    if 'default' not in result:
                        routing_info['has_default_route'] = False
                    else:
                        routing_info['has_default_route'] = True
                    
                    # Check IP forwarding
                    forwarding_result = router.cmd('cat /proc/sys/net/ipv4/ip_forward')
                    ip_forward_enabled = forwarding_result.strip() == '1'
                    routing_info['ip_forwarding'] = ip_forward_enabled
                    
                    if not ip_forward_enabled:
                        issues.append(f"IP forwarding disabled on router {router.name}")
                        recommendations.append(f"Enable IP forwarding on router {router.name}")
                    
                except Exception as e:
                    routing_info['error'] = str(e)
                    issues.append(f"Cannot check routing on {router.name}: {e}")
                    
                details['routing_tables'][router.name] = routing_info
                
        except Exception as e:
            issues.append(f"Routing table check failed: {e}")
            
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }