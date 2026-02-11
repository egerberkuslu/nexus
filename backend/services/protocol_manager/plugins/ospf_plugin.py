"""
OSPF Protocol Plugin
Implements OSPF v2 and v3 routing protocol support
"""

import logging
from typing import Dict, Any, List, Optional
from shared.plugins.protocol_plugin import RoutingProtocolPlugin, ProtocolStatus

logger = logging.getLogger(__name__)


class OSPFPlugin(RoutingProtocolPlugin):
    """OSPF routing protocol plugin"""

    name = "ospf"
    version = "2.0"
    description = "OSPF (Open Shortest Path First) routing protocol v2/v3"
    supported_devices = ["router"]

    def __init__(self):
        self.active_configs: Dict[str, Dict[str, Any]] = {}

    def configure(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure OSPF on a router

        Config parameters:
            - router_id: Router ID (required)
            - area: OSPF area (default: 0.0.0.0)
            - networks: List of networks to advertise
            - interfaces: List of interfaces to enable OSPF on
            - cost: Interface cost (optional)
            - hello_interval: Hello packet interval (default: 10s)
            - dead_interval: Dead interval (default: 40s)
            - version: OSPF version (2 or 3, default: 2)
        """
        try:
            # Validate configuration
            validation = self.validate_config(config)
            if not validation['valid']:
                return {
                    'success': False,
                    'message': f"Invalid configuration: {validation['errors']}",
                    'config': None
                }

            # Extract parameters
            router_id = config['router_id']
            area = config.get('area', '0.0.0.0')
            networks = config.get('networks', [])
            interfaces = config.get('interfaces', [])
            version = config.get('version', 2)
            hello_interval = config.get('hello_interval', 10)
            dead_interval = config.get('dead_interval', 40)

            # Generate FRRouting OSPF configuration
            ospf_config = self._generate_frr_config(
                router_id=router_id,
                area=area,
                networks=networks,
                interfaces=interfaces,
                version=version,
                hello_interval=hello_interval,
                dead_interval=dead_interval
            )

            # Store configuration
            self.active_configs[device] = {
                'router_id': router_id,
                'area': area,
                'networks': networks,
                'interfaces': interfaces,
                'version': version,
                'config_text': ospf_config
            }

            logger.info(f"OSPF configured on {device} with router-id {router_id}")

            return {
                'success': True,
                'message': f"OSPF configured successfully on {device}",
                'config': ospf_config
            }

        except Exception as e:
            logger.error(f"Failed to configure OSPF on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'config': None
            }

    def enable(self, device: str) -> Dict[str, Any]:
        """Enable OSPF on a router"""
        try:
            if device not in self.active_configs:
                return {
                    'success': False,
                    'message': f"OSPF not configured on {device}",
                    'status': ProtocolStatus.DISABLED
                }

            # Execute commands on the device via gRPC
            logger.info(f"Enabling OSPF on {device}")
            
            from shared.utils.grpc_client import get_grpc_client
            grpc_client = get_grpc_client()

            # Command sequence to enable OSPF (FRRouting)
            commands = [
                "vtysh -c 'configure terminal'",
                f"vtysh -c 'router ospf'",
                "vtysh -c 'end'",
                "vtysh -c 'write memory'"
            ]

            # Execute via gRPC
            import asyncio
            result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))

            return {
                'success': True,
                'message': f"OSPF enabled on {device}",
                'status': ProtocolStatus.ENABLED
            }

        except Exception as e:
            logger.error(f"Failed to enable OSPF on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }

    def disable(self, device: str) -> Dict[str, Any]:
        """Disable OSPF on a router"""
        try:
            logger.info(f"Disabling OSPF on {device}")

            # Command to disable OSPF
            commands = [
                "vtysh -c 'configure terminal'",
                "vtysh -c 'no router ospf'",
                "vtysh -c 'end'",
                "vtysh -c 'write memory'"
            ]

            # In production: execute via gRPC
            # grpc_client.execute_command(device, " && ".join(commands))

            # Remove from active configs
            if device in self.active_configs:
                del self.active_configs[device]

            return {
                'success': True,
                'message': f"OSPF disabled on {device}"
            }

        except Exception as e:
            logger.error(f"Failed to disable OSPF on {device}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def get_status(self, device: str) -> Dict[str, Any]:
        """Get OSPF status"""
        try:
            if device not in self.active_configs:
                return {
                    'status': ProtocolStatus.DISABLED,
                    'details': {},
                    'version': self.version,
                    'config': {}
                }

            # Query actual status via gRPC
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            
            # Get OSPF neighbors
            neighbor_result = asyncio.run(grpc_client.execute_command(device, "vtysh -c 'show ip ospf neighbor'"))
            neighbors_output = neighbor_result.get("output", "") if neighbor_result.get("success") else ""
            
            # Get OSPF routes
            route_result = asyncio.run(grpc_client.execute_command(device, "vtysh -c 'show ip ospf route'"))
            routes_output = route_result.get("output", "") if route_result.get("success") else ""

            return {
                'status': ProtocolStatus.ENABLED,
                'details': {
                    'router_id': config['router_id'],
                    'area': config['area'],
                    'networks': config['networks'],
                    'neighbors_output': neighbors_output,
                    'routes_output': routes_output
                },
                'version': str(config['version']),
                'config': config
            }

        except Exception as e:
            logger.error(f"Failed to get OSPF status on {device}: {e}")
            return {
                'status': ProtocolStatus.ERROR,
                'details': {'error': str(e)},
                'version': self.version,
                'config': {}
            }

    def switch_from(self, device: str, to_protocol: str, preserve_config: bool = True) -> Dict[str, Any]:
        """Switch from OSPF to another protocol"""
        try:
            logger.info(f"Switching from OSPF to {to_protocol} on {device}")

            # Capture current routing table if preserving config
            preserved_state = {}
            if preserve_config:
                routing_table = self.get_routing_table(device)
                preserved_state = {
                    'routing_table': routing_table,
                    'router_id': self.active_configs.get(device, {}).get('router_id'),
                    'area': self.active_configs.get(device, {}).get('area'),
                    'networks': self.active_configs.get(device, {}).get('networks')
                }

            # Disable OSPF gracefully
            self.disable(device)

            return {
                'success': True,
                'message': f"Successfully switched from OSPF to {to_protocol}",
                'preserved_state': preserved_state
            }

        except Exception as e:
            logger.error(f"Failed to switch from OSPF on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'preserved_state': {}
            }

    def switch_to(self, device: str, from_protocol: str, preserved_state: Optional[Dict] = None) -> Dict[str, Any]:
        """Switch to OSPF from another protocol"""
        try:
            logger.info(f"Switching from {from_protocol} to OSPF on {device}")

            # Build OSPF configuration from preserved state
            if preserved_state:
                config = {
                    'router_id': preserved_state.get('router_id', '1.1.1.1'),
                    'area': preserved_state.get('area', '0.0.0.0'),
                    'networks': preserved_state.get('networks', [])
                }
            else:
                # Use default configuration
                config = self.get_default_config()

            # Configure OSPF
            result = self.configure(device, config)
            if not result['success']:
                return result

            # Enable OSPF
            enable_result = self.enable(device)

            return {
                'success': enable_result['success'],
                'message': f"Successfully switched to OSPF from {from_protocol}",
                'status': enable_result.get('status', ProtocolStatus.ENABLED)
            }

        except Exception as e:
            logger.error(f"Failed to switch to OSPF on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate OSPF configuration"""
        errors = []
        warnings = []

        # Check required fields
        if 'router_id' not in config:
            errors.append("router_id is required")
        else:
            # Validate router ID format (x.x.x.x)
            router_id = config['router_id']
            parts = str(router_id).split('.')
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                errors.append(f"Invalid router_id format: {router_id}")

        # Validate area format
        if 'area' in config:
            area = config['area']
            parts = str(area).split('.')
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                errors.append(f"Invalid area format: {area}")

        # Check if networks or interfaces provided
        if 'networks' not in config and 'interfaces' not in config:
            warnings.append("No networks or interfaces specified")

        # Validate OSPF version
        if 'version' in config:
            version = config['version']
            if version not in [2, 3]:
                errors.append(f"Invalid OSPF version: {version}. Must be 2 or 3")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def get_default_config(self) -> Dict[str, Any]:
        """Get default OSPF configuration"""
        return {
            'router_id': '1.1.1.1',
            'area': '0.0.0.0',
            'networks': [],
            'version': 2,
            'hello_interval': 10,
            'dead_interval': 40
        }

    def get_config_schema(self) -> Dict[str, Any]:
        """Get JSON schema for OSPF configuration"""
        return {
            "type": "object",
            "properties": {
                "router_id": {
                    "type": "string",
                    "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$",
                    "description": "OSPF Router ID"
                },
                "area": {
                    "type": "string",
                    "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$",
                    "default": "0.0.0.0",
                    "description": "OSPF Area"
                },
                "networks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Networks to advertise"
                },
                "interfaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Interfaces to enable OSPF on"
                },
                "version": {
                    "type": "integer",
                    "enum": [2, 3],
                    "default": 2,
                    "description": "OSPF version (2 or 3)"
                },
                "hello_interval": {
                    "type": "integer",
                    "default": 10,
                    "description": "Hello interval in seconds"
                },
                "dead_interval": {
                    "type": "integer",
                    "default": 40,
                    "description": "Dead interval in seconds"
                }
            },
            "required": ["router_id"]
        }

    # Protocol-specific methods
    def get_routing_table(self, device: str) -> List[Dict[str, Any]]:
        """Get OSPF routing table"""
        # In production: execute "vtysh -c 'show ip ospf route'" via gRPC
        return []

    def get_neighbors(self, device: str) -> List[Dict[str, Any]]:
        """Get OSPF neighbors"""
        # In production: execute "vtysh -c 'show ip ospf neighbor'" via gRPC
        return []

    def get_metrics(self, device: str) -> Dict[str, Any]:
        """Get OSPF metrics"""
        return {
            'neighbors_count': 0,
            'routes_count': 0,
            'lsa_count': 0,
            'spf_runs': 0
        }

    # Helper methods
    def _generate_frr_config(self, router_id: str, area: str, networks: List[str],
                             interfaces: List[str], version: int,
                             hello_interval: int, dead_interval: int) -> str:
        """Generate FRRouting OSPF configuration"""

        config_lines = [
            "!",
            f"router ospf",
            f"  ospf router-id {router_id}",
        ]

        # Add networks
        for network in networks:
            config_lines.append(f"  network {network} area {area}")

        # Add interfaces
        for interface in interfaces:
            config_lines.append(f"!")
            config_lines.append(f"interface {interface}")
            config_lines.append(f"  ip ospf hello-interval {hello_interval}")
            config_lines.append(f"  ip ospf dead-interval {dead_interval}")
            config_lines.append(f"  ip ospf area {area}")

        config_lines.append("!")

        return "\n".join(config_lines)
