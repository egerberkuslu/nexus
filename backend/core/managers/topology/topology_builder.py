"""
Topology Builder Module
Handles creation of various network topologies for Mininet
"""

import os
import re
from typing import Dict, List, Optional, Any, Tuple
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink
from mininet.topo import Topo, SingleSwitchTopo, LinearTopo
try:
    from mininet.topo import TreeTopo
except ImportError:
    # Create a simple TreeTopo implementation if not available
    class TreeTopo(Topo):
        def __init__(self, depth=1, fanout=2):
            super(TreeTopo, self).__init__()
            self.depth = depth
            self.fanout = fanout
            self._build_tree()

        def _build_tree(self):
            # Create switches
            switches = []
            for level in range(self.depth):
                level_switches = []
                for i in range(self.fanout ** level):
                    switch = self.addSwitch(f's{level}{i}')
                    level_switches.append(switch)
                switches.append(level_switches)

            # Create links between levels
            for level in range(self.depth - 1):
                for i, parent_switch in enumerate(switches[level]):
                    for j in range(self.fanout):
                        child_idx = i * self.fanout + j
                        if child_idx < len(switches[level + 1]):
                            child_switch = switches[level + 1][child_idx]
                            self.addLink(parent_switch, child_switch)

            # Add hosts to leaf switches
            leaf_switches = switches[-1] if switches else []
            for i, switch in enumerate(leaf_switches):
                host = self.addHost(f'h{i+1}')
                self.addLink(host, switch)
from utils.logger import setup_logger

logger = setup_logger(__name__)

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


class TopologyBuilder:
    """Handles creation of various network topologies"""

    def __init__(self):
        self.logger = logger

    def create_simple_topology(self) -> Tuple[Mininet, bool]:
        """Create the default network topology with controller visibility"""
        try:
            # Clean any existing Mininet processes
            os.system('mn -c > /dev/null 2>&1')

            # Create network with RemoteController
            net = Mininet(
                controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
                switch=OVSKernelSwitch,
                link=TCLink,
                host=Host,
                autoSetMacs=True,
                autoStaticArp=False
            )

            # Add controller - THIS IS NOW TRACKED
            c0 = net.addController('c0', controller=RemoteController,
                                  ip='127.0.0.1', port=6633)

            # Add switches
            s1 = net.addSwitch('s1', protocols='OpenFlow13')
            s2 = net.addSwitch('s2', protocols='OpenFlow13')

            # Add router
            r1 = net.addHost('r1', cls=Host, ip='10.0.1.1/24')  # Will be configured as router

            # Add hosts in different subnets
            h1 = net.addHost('h1', ip='10.0.1.10/24', defaultRoute='via 10.0.1.1')
            h2 = net.addHost('h2', ip='10.0.1.11/24', defaultRoute='via 10.0.1.1')
            h3 = net.addHost('h3', ip='10.0.2.10/24', defaultRoute='via 10.0.2.1')
            h4 = net.addHost('h4', ip='10.0.2.11/24', defaultRoute='via 10.0.2.1')

            # Add links
            net.addLink(h1, s1, bw=10)
            net.addLink(h2, s1, bw=10)
            net.addLink(r1, s1, bw=100, intfName1='r1-eth0')

            net.addLink(h3, s2, bw=10)
            net.addLink(h4, s2, bw=10)
            net.addLink(r1, s2, bw=100, intfName1='r1-eth1')

            logger.info("Simple topology created successfully")
            self._print_topology_info()

            return net, True

        except Exception as e:
            logger.error(f"Error creating topology: {e}")
            return None, False

    def create_predefined_topology(self, topology_config: Dict[str, Any]) -> Tuple[Mininet, bool]:
        """Create predefined topology types"""
        try:
            topo_type = topology_config.get('type', 'simple')

            # Clean any existing processes
            os.system('mn -c > /dev/null 2>&1')

            if topo_type == 'simple':
                hosts = topology_config.get('hosts', 2)
                switches = topology_config.get('switches', 1)
                net = Mininet(topo=SingleSwitchTopo(k=hosts))

            elif topo_type == 'linear':
                hosts = topology_config.get('hosts', 4)
                switches = topology_config.get('switches', 4)
                net = Mininet(topo=LinearTopo(k=hosts))

            elif topo_type == 'tree':
                depth = topology_config.get('depth', 3)
                fanout = topology_config.get('fanout', 2)
                net = Mininet(topo=TreeTopo(depth=depth, fanout=fanout))

            elif topo_type == 'star':
                hosts = topology_config.get('hosts', 6)
                # Star topology is essentially a single switch topology
                net = Mininet(topo=SingleSwitchTopo(k=hosts))

            elif topo_type == 'mesh':
                hosts = topology_config.get('hosts', 4)
                # Create a mesh topology using custom implementation
                net = Mininet(topo=self._create_mesh_topology(hosts))

            elif topo_type == 'ring':
                hosts = topology_config.get('hosts', 6)
                # Create a ring topology
                net = Mininet(topo=self._create_ring_topology(hosts))

            elif topo_type == 'fattree':
                k = topology_config.get('k', 4)  # k-ary fat tree
                # Create fat tree topology
                net = Mininet(topo=self._create_fattree_topology(k))

            elif topo_type == 'datacenter':
                pods = topology_config.get('pods', 4)
                hosts_per_pod = topology_config.get('hosts_per_pod', 2)
                # Create datacenter-like topology
                net = Mininet(topo=self._create_datacenter_topology(pods, hosts_per_pod))

            else:
                logger.error(f"Unknown predefined topology type: {topo_type}")
                return None, False

            # Set controller if specified
            controller_config = topology_config.get('controller', {})
            if controller_config:
                controller_type = controller_config.get('type', 'ovs')
                controller_ip = controller_config.get('ip', '127.0.0.1')
                controller_port = controller_config.get('port', 6633)

                if controller_type == 'remote':
                    net.addController('c0', controller=RemoteController,
                                     ip=controller_ip, port=controller_port)
                elif controller_type == 'ryu':
                    # Use Ryu controller
                    net.addController('c0', controller=RemoteController,
                                     ip=controller_ip, port=controller_port)

            # Configure link parameters if specified
            link_config = topology_config.get('links', {})
            if link_config:
                bandwidth = link_config.get('bandwidth', None)
                delay = link_config.get('delay', None)
                loss = link_config.get('loss', None)

                # Apply link configuration to all links
                for link in net.links:
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
            return net, True

        except Exception as e:
            logger.error(f"Error creating predefined topology: {e}")
            return None, False

    def _create_mesh_topology(self, num_hosts: int) -> Topo:
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

    def _create_ring_topology(self, num_hosts: int) -> Topo:
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

    def _create_fattree_topology(self, k: int) -> Topo:
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

    def _create_datacenter_topology(self, pods: int, hosts_per_pod: int) -> Topo:
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

    def parse_frontend_topology(self, frontend_topology: Dict[str, Any]) -> Dict[str, Any]:
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

    def parse_bandwidth(self, bw_string: Any) -> float:
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

    @staticmethod
    def is_valid_mac(mac_address: str) -> bool:
        """Validate MAC address format"""
        if not mac_address or mac_address.lower() == 'auto':
            return False

        # Check if MAC address matches expected format
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(mac_pattern, mac_address))

    @staticmethod
    def is_valid_dpid(dpid: str) -> bool:
        """Validate DPID format"""
        if not dpid or dpid.lower() == 'auto':
            return False

        try:
            # DPID should be a hex string
            int(dpid, 16)
            return True
        except ValueError:
            return False
