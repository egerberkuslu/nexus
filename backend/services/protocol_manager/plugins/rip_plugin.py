"""
RIP (Routing Information Protocol) Plugin
Supports RIPv1, RIPv2, and RIPng (for IPv6)
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


class RIPPlugin:
    """RIP protocol plugin for FRRouting"""
    
    name = "RIP"
    version = "2.0"
    description = "RIP (Routing Information Protocol) v1/v2/ng"
    supported_devices = ["router", "host"]
    
    def __init__(self):
        self.active_configs = {}
    
    def configure(self, device: str, config: Dict) -> Dict:
        """
        Configure RIP on a device
        
        Args:
            device: Device name
            config: RIP configuration
                - version: RIP version (1, 2, or ng for IPv6)
                - networks: List of networks to advertise
                - interfaces: List of interfaces to enable RIP on
                - passive_interfaces: List of passive interfaces
                - default_metric: Default metric value
                - timers: Dict with update, timeout, garbage timers
                
        Returns:
            Configuration result
        """
        try:
            # Validate configuration
            if 'networks' not in config:
                return {
                    'success': False,
                    'message': "networks parameter is required"
                }
            
            rip_version = config.get('version', 2)
            if rip_version not in [1, 2, 'ng']:
                return {
                    'success': False,
                    'message': f"Invalid RIP version: {rip_version}. Must be 1, 2, or 'ng'"
                }
            
            networks = config.get('networks', [])
            interfaces = config.get('interfaces', [])
            passive_interfaces = config.get('passive_interfaces', [])
            default_metric = config.get('default_metric', 1)
            timers = config.get('timers', {
                'update': 30,
                'timeout': 180,
                'garbage': 120
            })
            
            # Store configuration
            self.active_configs[device] = {
                'version': rip_version,
                'networks': networks,
                'interfaces': interfaces,
                'passive_interfaces': passive_interfaces,
                'default_metric': default_metric,
                'timers': timers
            }
            
            logger.info(f"RIP configured on {device}: version={rip_version}, networks={networks}")
            
            return {
                'success': True,
                'message': f"RIP v{rip_version} configured on {device}",
                'config': self.active_configs[device]
            }
        
        except Exception as e:
            logger.error(f"Error configuring RIP on {device}: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def enable(self, device: str) -> Dict:
        """
        Enable RIP on a device
        
        Args:
            device: Device name
            
        Returns:
            Enable result with status
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': False,
                    'message': f"RIP not configured on {device}",
                    'status': ProtocolStatus.DISABLED
                }

            # Execute commands on the device via gRPC
            logger.info(f"Enabling RIP on {device}")
            
            from shared.utils.grpc_client import get_grpc_client
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            rip_version = config['version']
            
            # Build command sequence based on RIP version
            if rip_version == 'ng':
                # RIPng for IPv6
                commands = ["vtysh -c 'configure terminal'"]
                commands.append("vtysh -c 'router ripng'")
                
                for network in config['networks']:
                    commands.append(f"vtysh -c 'network {network}'")
                
                for interface in config['passive_interfaces']:
                    commands.append(f"vtysh -c 'passive-interface {interface}'")
                
            else:
                # RIPv1 or RIPv2
                commands = ["vtysh -c 'configure terminal'"]
                commands.append("vtysh -c 'router rip'")
                
                if rip_version == 2:
                    commands.append("vtysh -c 'version 2'")
                else:
                    commands.append("vtysh -c 'version 1'")
                
                for network in config['networks']:
                    commands.append(f"vtysh -c 'network {network}'")
                
                for interface in config['passive_interfaces']:
                    commands.append(f"vtysh -c 'passive-interface {interface}'")
                
                # Set timers
                timers = config['timers']
                commands.append(
                    f"vtysh -c 'timers basic {timers['update']} {timers['timeout']} {timers['garbage']}'"
                )
                
                # Set default metric
                commands.append(f"vtysh -c 'default-metric {config['default_metric']}'")
            
            commands.append("vtysh -c 'end'")
            commands.append("vtysh -c 'write memory'")

            # Execute via gRPC
            import asyncio
            result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))

            return {
                'success': True,
                'message': f"RIP v{rip_version} enabled on {device}",
                'status': ProtocolStatus.ENABLED
            }
        
        except Exception as e:
            logger.error(f"Error enabling RIP on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def disable(self, device: str) -> Dict:
        """
        Disable RIP on a device
        
        Args:
            device: Device name
            
        Returns:
            Disable result
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': True,
                    'message': f"RIP already disabled on {device}",
                    'status': ProtocolStatus.DISABLED
                }
            
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            rip_version = self.active_configs[device]['version']
            
            # Build disable commands
            if rip_version == 'ng':
                commands = [
                    "vtysh -c 'configure terminal'",
                    "vtysh -c 'no router ripng'",
                    "vtysh -c 'end'",
                    "vtysh -c 'write memory'"
                ]
            else:
                commands = [
                    "vtysh -c 'configure terminal'",
                    "vtysh -c 'no router rip'",
                    "vtysh -c 'end'",
                    "vtysh -c 'write memory'"
                ]
            
            result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))
            
            return {
                'success': True,
                'message': f"RIP disabled on {device}",
                'status': ProtocolStatus.DISABLED
            }
        
        except Exception as e:
            logger.error(f"Error disabling RIP on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def get_status(self, device: str) -> Dict:
        """
        Get RIP status on a device
        
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

            # Query actual status via gRPC
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            rip_version = config['version']
            
            # Get RIP status
            if rip_version == 'ng':
                status_cmd = "vtysh -c 'show ipv6 ripng status'"
                routes_cmd = "vtysh -c 'show ipv6 ripng'"
            else:
                status_cmd = "vtysh -c 'show ip rip status'"
                routes_cmd = "vtysh -c 'show ip rip'"
            
            status_result = asyncio.run(grpc_client.execute_command(device, status_cmd))
            routes_result = asyncio.run(grpc_client.execute_command(device, routes_cmd))

            return {
                'status': ProtocolStatus.ENABLED,
                'details': {
                    'version': rip_version,
                    'networks': config['networks'],
                    'interfaces': config['interfaces'],
                    'passive_interfaces': config['passive_interfaces'],
                    'default_metric': config['default_metric'],
                    'timers': config['timers'],
                    'status_output': status_result.get("output", "") if status_result.get("success") else "",
                    'routes_output': routes_result.get("output", "") if routes_result.get("success") else ""
                },
                'version': str(rip_version),
                'config': config
            }

        except Exception as e:
            logger.error(f"Error getting RIP status on {device}: {e}")
            return {
                'status': ProtocolStatus.ERROR,
                'details': {'error': str(e)},
                'version': self.version,
                'config': {}
            }
    
    def get_config_schema(self) -> Dict:
        """
        Get configuration schema for RIP
        
        Returns:
            JSON schema for configuration
        """
        return {
            "type": "object",
            "required": ["networks"],
            "properties": {
                "version": {
                    "type": ["integer", "string"],
                    "enum": [1, 2, "ng"],
                    "default": 2,
                    "description": "RIP version (1, 2, or 'ng' for IPv6)"
                },
                "networks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Networks to advertise"
                },
                "interfaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Interfaces to enable RIP on"
                },
                "passive_interfaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Passive interfaces (no RIP updates sent)"
                },
                "default_metric": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16,
                    "default": 1,
                    "description": "Default route metric"
                },
                "timers": {
                    "type": "object",
                    "properties": {
                        "update": {"type": "integer", "default": 30},
                        "timeout": {"type": "integer", "default": 180},
                        "garbage": {"type": "integer", "default": 120}
                    },
                    "description": "RIP timers in seconds"
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
        if 'networks' not in config or not config['networks']:
            return False, "At least one network must be specified"
        
        rip_version = config.get('version', 2)
        if rip_version not in [1, 2, 'ng']:
            return False, f"Invalid RIP version: {rip_version}"
        
        default_metric = config.get('default_metric', 1)
        if not (1 <= default_metric <= 16):
            return False, f"Default metric must be between 1 and 16"
        
        return True, None
    
    def get_metrics(self, device: str) -> Dict:
        """
        Get RIP metrics
        
        Args:
            device: Device name
            
        Returns:
            Metrics dictionary
        """
        try:
            if device not in self.active_configs:
                return {}
            
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            rip_version = self.active_configs[device]['version']
            
            # Get route count
            if rip_version == 'ng':
                cmd = "vtysh -c 'show ipv6 ripng' | grep -c 'R'"
            else:
                cmd = "vtysh -c 'show ip rip' | grep -c 'R'"
            
            result = asyncio.run(grpc_client.execute_command(device, cmd))
            
            route_count = 0
            if result.get("success"):
                try:
                    route_count = int(result.get("output", "0").strip())
                except ValueError:
                    route_count = 0
            
            return {
                'protocol': 'RIP',
                'version': rip_version,
                'route_count': route_count,
                'network_count': len(self.active_configs[device]['networks']),
                'status': 'enabled'
            }
        
        except Exception as e:
            logger.error(f"Error getting RIP metrics for {device}: {e}")
            return {}


# Plugin instance
plugin = RIPPlugin()

