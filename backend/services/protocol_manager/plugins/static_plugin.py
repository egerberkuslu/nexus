"""
Static Routing Plugin
Manages static routes for both IPv4 and IPv6
"""

import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ProtocolStatus(Enum):
    """Protocol status enumeration"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ERROR = "error"
    UNKNOWN = "unknown"


class StaticPlugin:
    """Static routing plugin"""
    
    name = "STATIC"
    version = "1.0"
    description = "Static routing configuration for IPv4 and IPv6"
    supported_devices = ["router", "host", "switch"]
    
    def __init__(self):
        self.active_configs = {}
    
    def configure(self, device: str, config: Dict) -> Dict:
        """
        Configure static routes on a device
        
        Args:
            device: Device name
            config: Static routing configuration
                - routes: List of static routes
                    Each route:
                        - destination: Destination network (CIDR notation)
                        - gateway: Next-hop gateway (optional if interface specified)
                        - interface: Outgoing interface (optional if gateway specified)
                        - distance: Administrative distance (optional, default: 1)
                        - metric: Route metric (optional)
                - ipv6_routes: List of IPv6 static routes (same structure)
                
        Returns:
            Configuration result
        """
        try:
            # Validate configuration
            routes = config.get('routes', [])
            ipv6_routes = config.get('ipv6_routes', [])
            
            if not routes and not ipv6_routes:
                return {
                    'success': False,
                    'message': "At least one route (IPv4 or IPv6) must be specified"
                }
            
            # Validate each route
            for route in routes:
                if 'destination' not in route:
                    return {
                        'success': False,
                        'message': "Each route must have a destination"
                    }
                if 'gateway' not in route and 'interface' not in route:
                    return {
                        'success': False,
                        'message': f"Route to {route['destination']} must have either gateway or interface"
                    }
            
            for route in ipv6_routes:
                if 'destination' not in route:
                    return {
                        'success': False,
                        'message': "Each IPv6 route must have a destination"
                    }
                if 'gateway' not in route and 'interface' not in route:
                    return {
                        'success': False,
                        'message': f"IPv6 route to {route['destination']} must have either gateway or interface"
                    }
            
            # Store configuration
            self.active_configs[device] = {
                'routes': routes,
                'ipv6_routes': ipv6_routes
            }
            
            logger.info(f"Static routing configured on {device}: {len(routes)} IPv4 routes, {len(ipv6_routes)} IPv6 routes")
            
            return {
                'success': True,
                'message': f"Static routing configured on {device}",
                'config': self.active_configs[device]
            }
        
        except Exception as e:
            logger.error(f"Error configuring static routing on {device}: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def enable(self, device: str) -> Dict:
        """
        Enable static routes on a device
        
        Args:
            device: Device name
            
        Returns:
            Enable result with status
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': False,
                    'message': f"Static routing not configured on {device}",
                    'status': ProtocolStatus.DISABLED
                }

            # Execute commands on the device via gRPC
            logger.info(f"Enabling static routes on {device}")
            
            from shared.utils.grpc_client import get_grpc_client
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            commands = []
            
            # Add IPv4 static routes
            for route in config.get('routes', []):
                dest = route['destination']
                distance = route.get('distance', 1)
                
                if 'gateway' in route:
                    gateway = route['gateway']
                    if 'interface' in route:
                        # Both gateway and interface specified
                        commands.append(f"ip route add {dest} via {gateway} dev {route['interface']} metric {distance}")
                    else:
                        # Only gateway
                        commands.append(f"ip route add {dest} via {gateway} metric {distance}")
                elif 'interface' in route:
                    # Only interface (directly connected)
                    commands.append(f"ip route add {dest} dev {route['interface']} metric {distance}")
            
            # Add IPv6 static routes
            for route in config.get('ipv6_routes', []):
                dest = route['destination']
                distance = route.get('distance', 1)
                
                if 'gateway' in route:
                    gateway = route['gateway']
                    if 'interface' in route:
                        # Both gateway and interface specified
                        commands.append(f"ip -6 route add {dest} via {gateway} dev {route['interface']} metric {distance}")
                    else:
                        # Only gateway
                        commands.append(f"ip -6 route add {dest} via {gateway} metric {distance}")
                elif 'interface' in route:
                    # Only interface (directly connected)
                    commands.append(f"ip -6 route add {dest} dev {route['interface']} metric {distance}")
            
            # Execute all route additions
            import asyncio
            if commands:
                result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))
                
                if not result.get("success"):
                    return {
                        'success': False,
                        'message': f"Failed to add static routes: {result.get('error', 'Unknown error')}",
                        'status': ProtocolStatus.ERROR
                    }

            return {
                'success': True,
                'message': f"Static routes enabled on {device}",
                'status': ProtocolStatus.ENABLED
            }
        
        except Exception as e:
            logger.error(f"Error enabling static routes on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def disable(self, device: str) -> Dict:
        """
        Disable static routes on a device
        
        Args:
            device: Device name
            
        Returns:
            Disable result
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': True,
                    'message': f"Static routing already disabled on {device}",
                    'status': ProtocolStatus.DISABLED
                }
            
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            commands = []
            
            # Remove IPv4 static routes
            for route in config.get('routes', []):
                dest = route['destination']
                
                if 'gateway' in route:
                    gateway = route['gateway']
                    if 'interface' in route:
                        commands.append(f"ip route del {dest} via {gateway} dev {route['interface']}")
                    else:
                        commands.append(f"ip route del {dest} via {gateway}")
                elif 'interface' in route:
                    commands.append(f"ip route del {dest} dev {route['interface']}")
            
            # Remove IPv6 static routes
            for route in config.get('ipv6_routes', []):
                dest = route['destination']
                
                if 'gateway' in route:
                    gateway = route['gateway']
                    if 'interface' in route:
                        commands.append(f"ip -6 route del {dest} via {gateway} dev {route['interface']}")
                    else:
                        commands.append(f"ip -6 route del {dest} via {gateway}")
                elif 'interface' in route:
                    commands.append(f"ip -6 route del {dest} dev {route['interface']}")
            
            # Execute all route deletions
            if commands:
                result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))
            
            return {
                'success': True,
                'message': f"Static routes disabled on {device}",
                'status': ProtocolStatus.DISABLED
            }
        
        except Exception as e:
            logger.error(f"Error disabling static routes on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def get_status(self, device: str) -> Dict:
        """
        Get static routing status on a device
        
        Args:
            device: Device name
            
        Returns:
            Status information
        """
        try:
            if device not in self.active_configs:
                return {
                    'status': ProtocolStatus.DISABLED,
                    'details': {},
                    'version': self.version,
                    'config': {}
                }

            # Query actual routing table via gRPC
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            
            # Get IPv4 routing table
            ipv4_result = asyncio.run(grpc_client.execute_command(device, "ip route show"))
            
            # Get IPv6 routing table
            ipv6_result = asyncio.run(grpc_client.execute_command(device, "ip -6 route show"))

            return {
                'status': ProtocolStatus.ENABLED,
                'details': {
                    'ipv4_routes': config.get('routes', []),
                    'ipv6_routes': config.get('ipv6_routes', []),
                    'ipv4_route_count': len(config.get('routes', [])),
                    'ipv6_route_count': len(config.get('ipv6_routes', [])),
                    'ipv4_routing_table': ipv4_result.get("output", "") if ipv4_result.get("success") else "",
                    'ipv6_routing_table': ipv6_result.get("output", "") if ipv6_result.get("success") else ""
                },
                'version': self.version,
                'config': config
            }

        except Exception as e:
            logger.error(f"Error getting static routing status on {device}: {e}")
            return {
                'status': ProtocolStatus.ERROR,
                'details': {'error': str(e)},
                'version': self.version,
                'config': {}
            }
    
    def add_route(self, device: str, route: Dict) -> Dict:
        """
        Add a single static route
        
        Args:
            device: Device name
            route: Route configuration
            
        Returns:
            Result of route addition
        """
        try:
            if device not in self.active_configs:
                self.active_configs[device] = {'routes': [], 'ipv6_routes': []}
            
            is_ipv6 = ':' in route['destination']
            route_list = 'ipv6_routes' if is_ipv6 else 'routes'
            
            # Add to configuration
            self.active_configs[device][route_list].append(route)
            
            # Apply the route
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            dest = route['destination']
            distance = route.get('distance', 1)
            cmd_prefix = "ip -6" if is_ipv6 else "ip"
            
            if 'gateway' in route and 'interface' in route:
                cmd = f"{cmd_prefix} route add {dest} via {route['gateway']} dev {route['interface']} metric {distance}"
            elif 'gateway' in route:
                cmd = f"{cmd_prefix} route add {dest} via {route['gateway']} metric {distance}"
            else:
                cmd = f"{cmd_prefix} route add {dest} dev {route['interface']} metric {distance}"
            
            result = asyncio.run(grpc_client.execute_command(device, cmd))
            
            return {
                'success': result.get("success", False),
                'message': f"Route to {dest} added" if result.get("success") else "Failed to add route"
            }
        
        except Exception as e:
            logger.error(f"Error adding route on {device}: {e}")
            return {'success': False, 'message': str(e)}
    
    def remove_route(self, device: str, destination: str) -> Dict:
        """
        Remove a specific static route
        
        Args:
            device: Device name
            destination: Destination network to remove
            
        Returns:
            Result of route removal
        """
        try:
            if device not in self.active_configs:
                return {'success': False, 'message': f"No static routes configured on {device}"}
            
            is_ipv6 = ':' in destination
            route_list = 'ipv6_routes' if is_ipv6 else 'routes'
            
            # Find and remove from configuration
            routes = self.active_configs[device].get(route_list, [])
            route_to_remove = None
            for route in routes:
                if route['destination'] == destination:
                    route_to_remove = route
                    break
            
            if not route_to_remove:
                return {'success': False, 'message': f"Route to {destination} not found"}
            
            routes.remove(route_to_remove)
            
            # Remove the route from kernel
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            cmd_prefix = "ip -6" if is_ipv6 else "ip"
            
            if 'gateway' in route_to_remove and 'interface' in route_to_remove:
                cmd = f"{cmd_prefix} route del {destination} via {route_to_remove['gateway']} dev {route_to_remove['interface']}"
            elif 'gateway' in route_to_remove:
                cmd = f"{cmd_prefix} route del {destination} via {route_to_remove['gateway']}"
            else:
                cmd = f"{cmd_prefix} route del {destination} dev {route_to_remove['interface']}"
            
            result = asyncio.run(grpc_client.execute_command(device, cmd))
            
            return {
                'success': result.get("success", False),
                'message': f"Route to {destination} removed" if result.get("success") else "Failed to remove route"
            }
        
        except Exception as e:
            logger.error(f"Error removing route on {device}: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_config_schema(self) -> Dict:
        """
        Get configuration schema for static routing
        
        Returns:
            JSON schema for configuration
        """
        return {
            "type": "object",
            "properties": {
                "routes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["destination"],
                        "properties": {
                            "destination": {
                                "type": "string",
                                "description": "Destination network in CIDR notation"
                            },
                            "gateway": {
                                "type": "string",
                                "description": "Next-hop gateway IP address"
                            },
                            "interface": {
                                "type": "string",
                                "description": "Outgoing interface name"
                            },
                            "distance": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 255,
                                "default": 1,
                                "description": "Administrative distance"
                            },
                            "metric": {
                                "type": "integer",
                                "description": "Route metric"
                            }
                        }
                    },
                    "description": "List of IPv4 static routes"
                },
                "ipv6_routes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["destination"],
                        "properties": {
                            "destination": {
                                "type": "string",
                                "description": "IPv6 destination network in CIDR notation"
                            },
                            "gateway": {
                                "type": "string",
                                "description": "Next-hop gateway IPv6 address"
                            },
                            "interface": {
                                "type": "string",
                                "description": "Outgoing interface name"
                            },
                            "distance": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 255,
                                "default": 1,
                                "description": "Administrative distance"
                            },
                            "metric": {
                                "type": "integer",
                                "description": "Route metric"
                            }
                        }
                    },
                    "description": "List of IPv6 static routes"
                }
            }
        }
    
    def validate_config(self, config: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate configuration
        
        Args:
            config: Configuration to validate
            
        Returns:
            (is_valid, error_message)
        """
        routes = config.get('routes', [])
        ipv6_routes = config.get('ipv6_routes', [])
        
        if not routes and not ipv6_routes:
            return False, "At least one route (IPv4 or IPv6) must be specified"
        
        for route in routes:
            if 'destination' not in route:
                return False, "Each route must have a destination"
            if 'gateway' not in route and 'interface' not in route:
                return False, f"Route to {route['destination']} must have either gateway or interface"
        
        for route in ipv6_routes:
            if 'destination' not in route:
                return False, "Each IPv6 route must have a destination"
            if 'gateway' not in route and 'interface' not in route:
                return False, f"IPv6 route to {route['destination']} must have either gateway or interface"
        
        return True, None
    
    def get_metrics(self, device: str) -> Dict:
        """
        Get static routing metrics
        
        Args:
            device: Device name
            
        Returns:
            Metrics dictionary
        """
        try:
            if device not in self.active_configs:
                return {}
            
            config = self.active_configs[device]
            
            return {
                'protocol': 'STATIC',
                'ipv4_route_count': len(config.get('routes', [])),
                'ipv6_route_count': len(config.get('ipv6_routes', [])),
                'total_routes': len(config.get('routes', [])) + len(config.get('ipv6_routes', [])),
                'status': 'enabled'
            }
        
        except Exception as e:
            logger.error(f"Error getting static routing metrics for {device}: {e}")
            return {}


# Plugin instance
plugin = StaticPlugin()

