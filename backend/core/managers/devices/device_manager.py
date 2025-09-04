"""
Device Manager Module
Handles dynamic node and link management in running Mininet networks
"""

import os
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch, Host, OVSSwitch
from mininet.link import TCLink
from mininet.node import RemoteController
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DeviceManager:
    """Handles dynamic device management in Mininet networks"""

    def __init__(self):
        self.logger = logger

    def add_node(self, net: Mininet, node_id: str, node_type: str = 'host', **kwargs) -> Optional[Any]:
        """Add a node (host/switch/router) to running topology without restart."""
        if not net:
            logger.error("Network not initialized")
            return None

        try:
            # Check if network exists and is properly initialized
            if not net:
                logger.error("Network not initialized")
                return None

            # Prevent duplicate node creation
            try:
                existing = net.get(node_id)
                if existing is not None:
                    logger.info(f"Node {node_id} already exists; skipping creation")
                    return existing
            except Exception as e:
                logger.debug(f"Error checking existing node {node_id}: {e}")
                existing = None

            # Add node based on type
            if node_type == 'host':
                params = {}
                if 'ip' in kwargs and kwargs['ip'] and kwargs['ip'] != 'auto':
                    params['ip'] = kwargs['ip']
                if 'mac' in kwargs and kwargs['mac'] and kwargs['mac'] != 'auto' and self._is_valid_mac(kwargs['mac']):
                    params['mac'] = kwargs['mac']
                try:
                    # Check if addHost method exists
                    if hasattr(net, 'addHost'):
                        host = net.addHost(node_id, **params)
                        logger.info(f"Successfully added host {node_id}")
                        return host
                    else:
                        logger.warning("addHost method not available on network object")
                        # Try alternative approach - add to hosts collection directly
                        try:
                            from mininet.node import Host
                            host = Host(node_id, **params)
                            net.hosts.append(host)
                            logger.info(f"Added host {node_id} to hosts collection")
                            return host
                        except Exception as e2:
                            logger.error(f"Could not add host {node_id} using alternative method: {e2}")
                            return None
                except Exception as e:
                    logger.error(f"Failed to add host {node_id}: {e}")
                    return None

            elif node_type == 'router':
                params = {}
                if 'ip' in kwargs and kwargs['ip'] and kwargs['ip'] != 'auto':
                    params['ip'] = kwargs['ip']
                try:
                    # Import the custom Router class
                    from core.router import Router
                    # Check if addHost method exists
                    if hasattr(net, 'addHost'):
                        router = net.addHost(node_id, cls=Router, **params)
                        logger.info(f"Successfully added router {node_id}")
                        return router
                    else:
                        logger.warning("addHost method not available on network object")
                        # Try alternative approach - add to hosts collection directly
                        try:
                            router = Router(node_id, **params)
                            net.hosts.append(router)
                            logger.info(f"Added router {node_id} to hosts collection")
                            return router
                        except Exception as e2:
                            logger.error(f"Could not add router {node_id} using alternative method: {e2}")
                            return None
                except Exception as e:
                    logger.error(f"Failed to add router {node_id}: {e}")
                    return None

            elif node_type == 'switch':
                params = {}
                switch_type = kwargs.get('switch_type', 'ovs')

                if 'dpid' in kwargs and kwargs['dpid'] and kwargs['dpid'] != 'auto' and self._is_valid_dpid(kwargs['dpid']):
                    params['dpid'] = kwargs['dpid']

                try:
                    # Determine switch class based on type
                    switch_class = self._get_switch_class(switch_type)

                    # Check if addSwitch method exists
                    if hasattr(net, 'addSwitch'):
                        sw = net.addSwitch(node_id, cls=switch_class, **params)
                        # Ensure switch is in the switches collection
                        if sw not in net.switches:
                            net.switches.append(sw)
                        self._maybe_apply_controller_to_switch(net, sw)
                        logger.info(f"Successfully added {switch_type} switch {node_id}")
                        return sw
                    else:
                        logger.warning("addSwitch method not available on network object")
                        # Try alternative approach - add to switches collection directly
                        try:
                            sw = switch_class(node_id, **params)
                            net.switches.append(sw)
                            logger.info(f"Added {switch_type} switch {node_id} to switches collection")
                            return sw
                        except Exception as e2:
                            logger.error(f"Could not add {switch_type} switch {node_id} using alternative method: {e2}")
                            return None
                except Exception as e:
                    logger.error(f"Failed to add {switch_type} switch {node_id}: {e}")
                    return None

            elif node_type == 'controller':
                controller_type = kwargs.get('controller_type', 'ryu')
                logger.info(f"Adding controller {node_id} of type {controller_type}")

                # Get controller configuration based on type
                controller_config = self._get_controller_config(controller_type, **kwargs)
                logger.info(f"Controller config: {controller_config}")

                try:
                    # Try to add controller to Mininet network
                    if hasattr(net, 'addController'):
                        controller_class = self._get_controller_class(controller_type)
                        logger.info(f"Adding controller with class: {controller_class}")
                        controller = net.addController(node_id, controller=controller_class, **controller_config)
                        logger.info(f"Successfully added {controller_type} controller {node_id} to network: {controller}")
                        # Ensure controller is in the controllers collection
                        if hasattr(net, 'controllers') and controller not in net.controllers:
                            net.controllers.append(controller)
                        return controller
                    else:
                        logger.warning("addController method not available, treating as external entity")
                        # Return controller info for tracking purposes
                        return {
                            'id': node_id,
                            'type': controller_type,
                            'config': controller_config,
                            'external': True
                        }
                except Exception as e:
                    logger.error(f"Failed to add controller {node_id}: {e}")
                    # Return controller info for tracking purposes
                    return {
                        'id': node_id,
                        'type': controller_type,
                        'config': controller_config,
                        'external': True
                    }

            else:
                logger.error(f'Unsupported node type {node_type}')
                return None

        except Exception as e:
            logger.error(f"Error adding node {node_id}: {e}")
            return None

    def _get_switch_class(self, switch_type: str):
        """Get the appropriate switch class based on type"""
        try:
            if switch_type == 'ovs':
                from mininet.node import OVSSwitch
                return OVSSwitch
            elif switch_type == 'linux_bridge':
                from mininet.node import LinuxBridge
                return LinuxBridge
            elif switch_type == 'p4':
                # For P4 switches, we'll use a custom implementation or fallback
                try:
                    from mininet.node import UserSwitch
                    return UserSwitch
                except ImportError:
                    logger.warning("P4 switch not available, falling back to OVSSwitch")
                    from mininet.node import OVSSwitch
                    return OVSSwitch
            else:
                logger.warning(f"Unknown switch type '{switch_type}', falling back to OVSSwitch")
                from mininet.node import OVSSwitch
                return OVSSwitch
        except ImportError as e:
            logger.warning(f"Switch class not available: {e}, falling back to OVSSwitch")
            from mininet.node import OVSSwitch
            return OVSSwitch

    def _get_controller_config(self, controller_type: str, **kwargs):
        """Get controller configuration based on type"""
        base_config = {
            'ip': kwargs.get('ip', '127.0.0.1'),
            'port': kwargs.get('port', 6633),
            'protocol': 'OpenFlow'
        }

        if controller_type == 'ryu':
            base_config.update({
                'default_port': 6633,
                'rest_api_enabled': True,
                'rest_api_port': 8080
            })
        elif controller_type == 'pox':
            base_config.update({
                'default_port': 6633,
                'scripting_enabled': True
            })
        elif controller_type == 'osken':
            base_config.update({
                'default_port': 6633,
                'rest_api_enabled': True,
                'rest_api_port': 8080
            })
        elif controller_type == 'opendaylight':
            base_config.update({
                'default_port': 8181,
                'web_ui_enabled': True,
                'web_ui_port': 8181,
                'rest_api_enabled': True,
                'rest_api_port': 8181
            })

        return base_config

    def remove_node(self, net: Mininet, node_id: str) -> bool:
        """Remove a node and related links from running topology."""
        if not net:
            logger.error("Network not initialized")
            return False

        try:
            # Check if network exists
            if not net:
                logger.error("Network not initialized")
                return False

            logger.info(f"Attempting to remove node {node_id}")

            if node_id is None:
                logger.error("Node ID is None - cannot proceed with removal")
                return False

            # Find the node
            node = None
            try:
                # Try to get node from network
                node = net.get(node_id)
            except Exception as e:
                logger.debug(f"Could not get node {node_id} from net.get(): {e}")

            # If not found, search manually
            if not node:
                # Search in hosts
                if hasattr(net, 'hosts'):
                    for host in net.hosts:
                        if hasattr(host, 'name') and host.name == node_id:
                            node = host
                            logger.info(f"Found node {node_id} in hosts collection")
                            break

                # Search in switches
                if not node and hasattr(net, 'switches'):
                    for switch in net.switches:
                        if hasattr(switch, 'name') and switch.name == node_id:
                            node = switch
                            logger.info(f"Found node {node_id} in switches collection")
                            break

            if not node:
                logger.error(f"Node {node_id} not found")
                return False

            # Find and remove all links connected to this node
            links_to_remove = []
            if hasattr(net, 'links'):
                for link in list(net.links):
                    try:
                        if (hasattr(link, 'intf1') and hasattr(link, 'intf2') and
                            link.intf1 and link.intf2 and
                            hasattr(link.intf1, 'node') and hasattr(link.intf2, 'node') and
                            link.intf1.node and link.intf2.node):

                            if link.intf1.node == node or link.intf2.node == node:
                                links_to_remove.append(link)
                    except Exception as e:
                        logger.debug(f"Error checking link {link}: {e}")
                        continue

            # Remove the links
            for link in links_to_remove:
                try:
                    if link in net.links:
                        net.links.remove(link)
                        logger.info(f"Removed link connected to {node_id}")
                except Exception as e:
                    logger.warning(f"Error removing link: {e}")

            # Remove the node from its collection
            try:
                if hasattr(node, 'terminate'):
                    node.terminate()
                    logger.info(f"Terminated node {node_id}")

                if node in net.hosts:
                    net.hosts.remove(node)
                    logger.info(f"Removed {node_id} from hosts collection")
                elif node in net.switches:
                    net.switches.remove(node)
                    logger.info(f"Removed {node_id} from switches collection")

                # Try to delete the node object
                try:
                    del node
                    logger.info(f"Deleted node object {node_id}")
                except:
                    pass  # Node might still be referenced elsewhere

            except Exception as e:
                logger.warning(f"Error during node cleanup: {e}")

            logger.info(f"Successfully removed node {node_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing node {node_id}: {e}")
            return False

    def add_link(self, net: Mininet, source_id: str, target_id: str, **kwargs) -> bool:
        """Add a link between two nodes while running."""
        if not net:
            logger.error("Network not initialized")
            return False

        try:
            # Check if network exists and is properly initialized
            if not net:
                logger.error("Network not initialized")
                return False

            logger.info(f"Adding link between {source_id} and {target_id}")

            try:
                n1 = net.get(source_id)
            except Exception as e:
                logger.error(f"Error getting source node {source_id}: {e}")
                n1 = None
            try:
                n2 = net.get(target_id)
            except Exception as e:
                logger.error(f"Error getting target node {target_id}: {e}")
                n2 = None
            if n1 is None or n2 is None:
                logger.error("Source or target not found")
                return False

            # Prevent duplicate link creation
            for l in list(net.links):
                try:
                    if (l.intf1.node == n1 and l.intf2.node == n2) or (l.intf1.node == n2 and l.intf2.node == n1):
                        logger.info(f"Link {source_id}-{target_id} already exists; skipping creation")
                        return True
                except Exception:
                    continue

            # Special handling for controller links
            # Controllers are external entities, so we just track the connection
            if source_id.startswith('c') or target_id.startswith('c'):
                logger.info(f"Controller link {source_id}-{target_id} registered (external connection)")
                return True

            params = {}
            if 'bandwidth' in kwargs and kwargs['bandwidth']:
                try:
                    bw = self._parse_bandwidth(kwargs['bandwidth'])
                    params['bw'] = bw
                except Exception:
                    pass
            if 'delay' in kwargs and kwargs['delay']:
                params['delay'] = kwargs['delay']
            if 'loss' in kwargs and kwargs['loss'] is not None:
                params['loss'] = kwargs['loss']

            # Add link
            try:
                # Check if addLink method exists
                if hasattr(net, 'addLink'):
                    if params:
                        net.addLink(n1, n2, cls=TCLink, **params)
                    else:
                        net.addLink(n1, n2)
                    logger.info(f"Successfully added link between {source_id} and {target_id}")
                    return True
                else:
                    logger.warning("addLink method not available on network object")
                    # Try alternative approach - create link object and add to links collection
                    try:
                        if params:
                            link = TCLink(n1, n2, **params)
                        else:
                            link = TCLink(n1, n2)
                        net.links.append(link)
                        logger.info(f"Added link between {source_id} and {target_id} to links collection")
                        return True
                    except Exception as e2:
                        logger.error(f"Could not add link using alternative method: {e2}")
                        return False
            except Exception as e:
                logger.error(f"Failed to add link between {source_id} and {target_id}: {e}")
                return False

        except Exception as e:
            logger.error(f"Error adding link {source_id}-{target_id}: {e}")
            return False

    def remove_link(self, net: Mininet, source_id: str, target_id: str) -> bool:
        """Remove link between given nodes."""
        if not net:
            logger.error("Network not initialized")
            return False

        try:
            # Check if network exists
            if not net:
                logger.error("Network not initialized")
                return False

            logger.info(f"Removing link between {source_id} and {target_id}")

            # Find the link
            link_to_remove = None
            for link in list(net.links):
                try:
                    if (hasattr(link, 'intf1') and hasattr(link, 'intf2') and
                        link.intf1 and link.intf2 and
                        hasattr(link.intf1, 'node') and hasattr(link.intf2, 'node') and
                        link.intf1.node and link.intf2.node):

                        if ((link.intf1.node.name == source_id and link.intf2.node.name == target_id) or
                            (link.intf1.node.name == target_id and link.intf2.node.name == source_id)):
                            link_to_remove = link
                            break
                except Exception as e:
                    logger.debug(f"Error checking link {link}: {e}")
                    continue

            if not link_to_remove:
                logger.error(f"Link {source_id}-{target_id} not found")
                return False

            # Remove the link
            try:
                if link_to_remove in net.links:
                    net.links.remove(link_to_remove)
                    logger.info(f"Removed link {source_id}-{target_id}")
                    return True
                else:
                    logger.error(f"Link {source_id}-{target_id} not in links collection")
                    return False
            except Exception as e:
                logger.error(f"Error removing link {source_id}-{target_id}: {e}")
                return False

        except Exception as e:
            logger.error(f"Error removing link {source_id}-{target_id}: {e}")
            return False

    def update_node_ip(self, net: Mininet, node_id: str, new_ip: str, interface: Optional[str] = None) -> Dict[str, Any]:
        """Update IP address of a node"""
        try:
            if not net:
                return {'success': False, 'error': 'Network not initialized'}

            # Find the node
            node = None
            if hasattr(net, 'hosts'):
                for host in net.hosts:
                    if hasattr(host, 'name') and host.name == node_id:
                        node = host
                        break

            if not node and hasattr(net, 'switches'):
                for switch in net.switches:
                    if hasattr(switch, 'name') and switch.name == node_id:
                        node = switch
                        break

            if not node:
                return {'success': False, 'error': f'Node {node_id} not found'}

            # Update IP address
            if interface:
                # Update specific interface
                if hasattr(node, 'intfs') and interface in node.intfs:
                    node.intfs[interface].setIP(new_ip)
                    logger.info(f"Updated IP of interface {interface} on {node_id} to {new_ip}")
                else:
                    return {'success': False, 'error': f'Interface {interface} not found on {node_id}'}
            else:
                # Update default interface
                if hasattr(node, 'defaultIntf') and node.defaultIntf():
                    node.defaultIntf().setIP(new_ip)
                    logger.info(f"Updated default IP of {node_id} to {new_ip}")
                else:
                    return {'success': False, 'error': f'No default interface found on {node_id}'}

            return {'success': True, 'message': f'IP updated to {new_ip}'}

        except Exception as e:
            logger.error(f"Error updating IP for {node_id}: {e}")
            return {'success': False, 'error': str(e)}

    def update_link_bandwidth(self, net: Mininet, source_id: str, target_id: str, new_bandwidth: Any) -> Dict[str, Any]:
        """Update bandwidth of a link"""
        try:
            if not net:
                return {'success': False, 'error': 'Network not initialized'}

            # Validate node IDs
            if not source_id or not target_id:
                return {'success': False, 'error': 'Invalid node IDs provided'}

            logger.info(f"Bandwidth update request: {source_id} -> {target_id} = {new_bandwidth}")

            # Parse and convert bandwidth to Mbps
            bandwidth_mbps = self._parse_bandwidth(new_bandwidth)
            logger.info(f"Parsed bandwidth '{new_bandwidth}' to {bandwidth_mbps} Mbps")

            # Find the link
            link_to_update = None
            for link in net.links:
                try:
                    if (hasattr(link, 'intf1') and hasattr(link, 'intf2') and
                        link.intf1 and link.intf2 and
                        hasattr(link.intf1, 'node') and hasattr(link.intf2, 'node') and
                        link.intf1.node and link.intf2.node):

                        if ((link.intf1.node.name == source_id and link.intf2.node.name == target_id) or
                            (link.intf1.node.name == target_id and link.intf2.node.name == source_id)):
                            link_to_update = link
                            break
                except Exception as e:
                    logger.debug(f"Error checking link {link}: {e}")
                    continue

            if not link_to_update:
                return {'success': False, 'error': f'Link {source_id}-{target_id} not found'}

            # Update bandwidth
            try:
                if hasattr(link_to_update, 'intf1') and link_to_update.intf1:
                    # Check if bandwidth is within Mininet's supported range
                    if bandwidth_mbps > 1000:
                        logger.warning(f"Mininet limitation: Cannot set bandwidth {bandwidth_mbps} Mbps (>1000 Mbps)")
                        bandwidth_mbps = 1000

                    # Apply the bandwidth update
                    link_to_update.intf1.config(bw=bandwidth_mbps)
                    logger.info(f"Updated bandwidth of {source_id}-{target_id} to {bandwidth_mbps} Mbps")

                    return {'success': True, 'message': f'Bandwidth updated to {bandwidth_mbps} Mbps'}
                else:
                    return {'success': False, 'error': 'Link interface not accessible'}
            except Exception as e:
                logger.error(f"Error updating bandwidth for {source_id}-{target_id}: {e}")
                return {'success': False, 'error': str(e)}

        except Exception as e:
            logger.error(f"Error updating link bandwidth {source_id}-{target_id}: {e}")
            return {'success': False, 'error': str(e)}

    def update_link_status(self, net: Mininet, source_id: str, target_id: str, new_status: str) -> Dict[str, Any]:
        """Update status of a link (up/down)"""
        try:
            if not net:
                return {'success': False, 'error': 'Network not initialized'}

            logger.info(f"Link status update request: {source_id} -> {target_id} = {new_status}")

            # Find the link
            link_to_update = None
            for link in net.links:
                try:
                    if (hasattr(link, 'intf1') and hasattr(link, 'intf2') and
                        link.intf1 and link.intf2 and
                        hasattr(link.intf1, 'node') and hasattr(link.intf2, 'node') and
                        link.intf1.node and link.intf2.node):

                        if ((link.intf1.node.name == source_id and link.intf2.node.name == target_id) or
                            (link.intf1.node.name == target_id and link.intf2.node.name == source_id)):
                            link_to_update = link
                            break
                except Exception as e:
                    logger.debug(f"Error checking link {link}: {e}")
                    continue

            if not link_to_update:
                return {'success': False, 'error': f'Link {source_id}-{target_id} not found'}

            # Update link status
            try:
                if new_status.lower() == 'up':
                    link_to_update.intf1.ifconfig('up')
                    link_to_update.intf2.ifconfig('up')
                    logger.info(f"Set link {source_id}-{target_id} to UP")
                elif new_status.lower() == 'down':
                    link_to_update.intf1.ifconfig('down')
                    link_to_update.intf2.ifconfig('down')
                    logger.info(f"Set link {source_id}-{target_id} to DOWN")
                else:
                    return {'success': False, 'error': f'Invalid status: {new_status}'}

                return {'success': True, 'message': f'Link status updated to {new_status.upper()}'}

            except Exception as e:
                logger.error(f"Error updating link status for {source_id}-{target_id}: {e}")
                return {'success': False, 'error': str(e)}

        except Exception as e:
            logger.error(f"Error updating link status {source_id}-{target_id}: {e}")
            return {'success': False, 'error': str(e)}

    def get_node_interfaces(self, net: Mininet, node_id: str) -> Dict[str, Any]:
        """Get interface information for a specific node"""
        try:
            if not net:
                return {'error': 'Network not initialized'}

            # Find the node
            node = None
            if hasattr(net, 'hosts'):
                for host in net.hosts:
                    if hasattr(host, 'name') and host.name == node_id:
                        node = host
                        break

            if not node and hasattr(net, 'switches'):
                for switch in net.switches:
                    if hasattr(switch, 'name') and switch.name == node_id:
                        node = switch
                        break

            if not node:
                return {'error': f'Node {node_id} not found'}

            # Get interface information
            interfaces = {}
            if hasattr(node, 'intfs'):
                for intf_name, intf in node.intfs.items():
                    interfaces[intf_name] = {
                        'ip': getattr(intf, 'ip', None),
                        'mac': getattr(intf, 'mac', None),
                        'status': 'up' if intf.isUp() else 'down'
                    }

            return {
                'node_id': node_id,
                'interfaces': interfaces
            }

        except Exception as e:
            logger.error(f"Error getting interfaces for {node_id}: {e}")
            return {'error': str(e)}

    def _maybe_apply_controller_to_switch(self, net: Mininet, switch_obj: Any):
        """If a controller is configured/running, point the switch to it and set OF version."""
        try:
            # This would need access to controller configuration
            # For now, just set OpenFlow13 if controller exists
            if hasattr(net, 'controllers') and net.controllers:
                switch_obj.cmd('ovs-vsctl set bridge %s protocols=OpenFlow13' % switch_obj.name)
        except Exception as e:
            logger.warning(f"Could not configure controller for {switch_obj.name}: {e}")

    def cleanup(self):
        """Clean up device manager resources"""
        try:
            logger.info("Cleaning up device manager...")
            # Clear any cached data or resources
            # This method can be expanded as needed
            logger.info("Device manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during device manager cleanup: {e}")

    @staticmethod
    def _get_controller_class(controller_type: str):
        """Get the appropriate controller class based on type"""
        try:
            # For now, use RemoteController for all types since they are typically external
            from mininet.node import RemoteController
            return RemoteController
        except ImportError as e:
            logger.warning(f"Controller class not available: {e}")
            return None

    @staticmethod
    def _is_valid_mac(mac_address: str) -> bool:
        """Validate MAC address format"""
        if not mac_address or mac_address.lower() == 'auto':
            return False

        # Check if MAC address matches expected format
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(mac_pattern, mac_address))

    @staticmethod
    def _is_valid_dpid(dpid: str) -> bool:
        """Validate DPID format"""
        if not dpid or dpid.lower() == 'auto':
            return False

        try:
            # DPID should be a hex string
            int(dpid, 16)
            return True
        except ValueError:
            return False

    def _parse_bandwidth(self, bandwidth_str: Any) -> int:
        """Parse bandwidth string with units and convert to Mbps"""
        try:
            if isinstance(bandwidth_str, (int, float)):
                return int(bandwidth_str)

            bandwidth_str = str(bandwidth_str).strip().upper()

            # Remove any existing 'Mbit' or 'Gbit' suffix
            if bandwidth_str.endswith('MBIT') or bandwidth_str.endswith('M'):
                bandwidth_str = bandwidth_str.replace('MBIT', '').replace('M', '')
                multiplier = 1
            elif bandwidth_str.endswith('GBIT') or bandwidth_str.endswith('G'):
                bandwidth_str = bandwidth_str.replace('GBIT', '').replace('G', '')
                multiplier = 1000  # Convert Gbps to Mbps
            elif bandwidth_str.endswith('KBIT') or bandwidth_str.endswith('K'):
                bandwidth_str = bandwidth_str.replace('KBIT', '').replace('K', '')
                multiplier = 0.001  # Convert Kbps to Mbps
            else:
                # Assume Mbps if no unit specified
                multiplier = 1

            # Parse the numeric value
            numeric_value = float(bandwidth_str)
            bandwidth_mbps = int(numeric_value * multiplier)

            # Check Mininet's bandwidth limits
            if bandwidth_mbps > 1000:
                logger.warning(f"Requested bandwidth {bandwidth_mbps} Mbps exceeds Mininet's limit of 1000 Mbps")
                logger.warning("Mininet will ignore this value and keep the original bandwidth")
                logger.warning("For high-bandwidth simulation, consider using multiple links or custom topology")

            return bandwidth_mbps

        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing bandwidth '{bandwidth_str}': {e}, using default 10 Mbps")
            return 10
