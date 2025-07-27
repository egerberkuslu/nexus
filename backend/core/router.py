"""
Router Implementation for Mininet
Enhanced router node with proper type identification
"""

from mininet.node import Host
from utils.logger import setup_logger

logger = setup_logger(__name__)

class Router(Host):
    """A Router host that can route between subnets"""
    
    def __init__(self, name, **params):
        # Set node type to router for identification
        params['node_type'] = 'router'
        super(Router, self).__init__(name, **params)
        self.node_type = 'router'  # Custom attribute for type identification
        logger.info(f"Created router: {name}")
    
    def config(self, **params):
        """Configure the router with IP forwarding enabled"""
        super(Router, self).config(**params)
        
        # Enable IP forwarding
        self.cmd('sysctl net.ipv4.ip_forward=1')
        self.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
        
        # Disable ICMP redirects (optional, for better routing behavior)
        self.cmd('sysctl net.ipv4.conf.all.send_redirects=0')
        
        logger.info(f"Configured router {self.name} with IP forwarding enabled")
    
    def terminate(self):
        """Clean up router configuration on termination"""
        self.cmd('sysctl net.ipv4.ip_forward=0')
        logger.info(f"Router {self.name} terminated")
        super(Router, self).terminate()
    
    def get_type(self):
        """Return node type as router"""
        return 'router'
    
    def add_route(self, network, interface):
        """Add a route to the routing table"""
        try:
            self.cmd(f'ip route add {network} dev {interface}')
            logger.info(f"Added route {network} via {interface} on router {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add route on {self.name}: {e}")
            return False
    
    def delete_route(self, network):
        """Delete a route from the routing table"""
        try:
            self.cmd(f'ip route del {network}')
            logger.info(f"Deleted route {network} on router {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete route on {self.name}: {e}")
            return False
    
    def show_routes(self):
        """Show current routing table"""
        result = self.cmd('ip route show')
        return result.strip()
    
    def configure_interface(self, interface, ip_address):
        """Configure an interface with IP address"""
        try:
            self.cmd(f'ifconfig {interface} {ip_address}')
            logger.info(f"Configured interface {interface} with IP {ip_address} on router {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure interface {interface} on {self.name}: {e}")
            return False
    
    def get_interface_info(self):
        """Get information about all interfaces"""
        interfaces = []
        for intf in self.intfList():
            if intf.name != 'lo':
                try:
                    info = {
                        'name': intf.name,
                        'ip': intf.IP() if hasattr(intf, 'IP') else 'unknown',
                        'mac': intf.MAC() if hasattr(intf, 'MAC') else 'unknown',
                        'status': 'up' if intf.isUp() else 'down'
                    }
                    interfaces.append(info)
                except Exception as e:
                    logger.error(f"Error getting interface info for {intf.name}: {e}")
                    interfaces.append({
                        'name': intf.name,
                        'ip': 'unknown',
                        'mac': 'unknown',
                        'status': 'unknown'
                    })
        
        return interfaces