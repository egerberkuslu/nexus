"""
IS-IS (Intermediate System to Intermediate System) Plugin
Supports IS-IS for both IPv4 and IPv6
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


class ISISPlugin:
    """IS-IS protocol plugin for FRRouting"""
    
    name = "IS-IS"
    version = "1.0"
    description = "IS-IS (Intermediate System to Intermediate System) routing protocol"
    supported_devices = ["router"]
    
    def __init__(self):
        self.active_configs = {}
    
    def configure(self, device: str, config: Dict) -> Dict:
        """
        Configure IS-IS on a device
        
        Args:
            device: Device name
            config: IS-IS configuration
                - net: Network Entity Title (NET) address
                - area: IS-IS area (Level-1, Level-2, or Level-1-2)
                - interfaces: List of interfaces to enable IS-IS on
                - metric_style: Metric style (narrow, wide, or transition)
                - is_type: IS type (level-1, level-2, level-1-2)
                - authentication: Optional authentication config
                
        Returns:
            Configuration result
        """
        try:
            # Validate configuration
            if 'net' not in config:
                return {
                    'success': False,
                    'message': "NET (Network Entity Title) is required"
                }
            
            if 'interfaces' not in config or not config['interfaces']:
                return {
                    'success': False,
                    'message': "At least one interface must be specified"
                }
            
            net = config['net']
            area = config.get('area', 'level-1-2')
            interfaces = config.get('interfaces', [])
            metric_style = config.get('metric_style', 'wide')
            is_type = config.get('is_type', 'level-1-2')
            authentication = config.get('authentication', {})
            
            # Validate IS type
            valid_is_types = ['level-1', 'level-2', 'level-1-2']
            if is_type not in valid_is_types:
                return {
                    'success': False,
                    'message': f"Invalid IS type: {is_type}. Must be one of {valid_is_types}"
                }
            
            # Validate metric style
            valid_metric_styles = ['narrow', 'wide', 'transition']
            if metric_style not in valid_metric_styles:
                return {
                    'success': False,
                    'message': f"Invalid metric style: {metric_style}. Must be one of {valid_metric_styles}"
                }
            
            # Store configuration
            self.active_configs[device] = {
                'net': net,
                'area': area,
                'interfaces': interfaces,
                'metric_style': metric_style,
                'is_type': is_type,
                'authentication': authentication
            }
            
            logger.info(f"IS-IS configured on {device}: NET={net}, type={is_type}")
            
            return {
                'success': True,
                'message': f"IS-IS configured on {device}",
                'config': self.active_configs[device]
            }
        
        except Exception as e:
            logger.error(f"Error configuring IS-IS on {device}: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def enable(self, device: str) -> Dict:
        """
        Enable IS-IS on a device
        
        Args:
            device: Device name
            
        Returns:
            Enable result with status
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': False,
                    'message': f"IS-IS not configured on {device}",
                    'status': ProtocolStatus.DISABLED
                }

            # Execute commands on the device via gRPC
            logger.info(f"Enabling IS-IS on {device}")
            
            from shared.utils.grpc_client import get_grpc_client
            grpc_client = get_grpc_client()
            
            config = self.active_configs[device]
            
            # Build command sequence
            commands = [
                "vtysh -c 'configure terminal'",
                "vtysh -c 'router isis'",
                f"vtysh -c 'net {config['net']}'",
                f"vtysh -c 'is-type {config['is_type']}'",
                f"vtysh -c 'metric-style {config['metric_style']}'"
            ]
            
            # Add authentication if configured
            if config.get('authentication'):
                auth = config['authentication']
                if 'domain_password' in auth:
                    commands.append(f"vtysh -c 'domain-password {auth['domain_password']}'")
                if 'area_password' in auth:
                    commands.append(f"vtysh -c 'area-password {auth['area_password']}'")
            
            # Enable IS-IS on interfaces
            for interface in config['interfaces']:
                commands.append(f"vtysh -c 'interface {interface}'")
                commands.append("vtysh -c 'ip router isis'")
                commands.append("vtysh -c 'ipv6 router isis'")
                commands.append("vtysh -c 'exit'")
            
            commands.append("vtysh -c 'end'")
            commands.append("vtysh -c 'write memory'")

            # Execute via gRPC
            import asyncio
            result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))

            return {
                'success': True,
                'message': f"IS-IS enabled on {device}",
                'status': ProtocolStatus.ENABLED
            }
        
        except Exception as e:
            logger.error(f"Error enabling IS-IS on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def disable(self, device: str) -> Dict:
        """
        Disable IS-IS on a device
        
        Args:
            device: Device name
            
        Returns:
            Disable result
        """
        try:
            if device not in self.active_configs:
                return {
                    'success': True,
                    'message': f"IS-IS already disabled on {device}",
                    'status': ProtocolStatus.DISABLED
                }
            
            from shared.utils.grpc_client import get_grpc_client
            import asyncio
            grpc_client = get_grpc_client()
            
            # Build disable commands
            commands = [
                "vtysh -c 'configure terminal'",
                "vtysh -c 'no router isis'",
                "vtysh -c 'end'",
                "vtysh -c 'write memory'"
            ]
            
            result = asyncio.run(grpc_client.execute_command(device, " && ".join(commands)))
            
            return {
                'success': True,
                'message': f"IS-IS disabled on {device}",
                'status': ProtocolStatus.DISABLED
            }
        
        except Exception as e:
            logger.error(f"Error disabling IS-IS on {device}: {e}")
            return {
                'success': False,
                'message': str(e),
                'status': ProtocolStatus.ERROR
            }
    
    def get_status(self, device: str) -> Dict:
        """
        Get IS-IS status on a device
        
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
            
            # Get IS-IS status
            summary_result = asyncio.run(grpc_client.execute_command(device, "vtysh -c 'show isis summary'"))
            neighbor_result = asyncio.run(grpc_client.execute_command(device, "vtysh -c 'show isis neighbor'"))
            database_result = asyncio.run(grpc_client.execute_command(device, "vtysh -c 'show isis database'"))

            return {
                'status': ProtocolStatus.ENABLED,
                'details': {
                    'net': config['net'],
                    'is_type': config['is_type'],
                    'metric_style': config['metric_style'],
                    'interfaces': config['interfaces'],
                    'summary': summary_result.get("output", "") if summary_result.get("success") else "",
                    'neighbors': neighbor_result.get("output", "") if neighbor_result.get("success") else "",
                    'database': database_result.get("output", "") if database_result.get("success") else ""
                },
                'version': self.version,
                'config': config
            }

        except Exception as e:
            logger.error(f"Error getting IS-IS status on {device}: {e}")
            return {
                'status': ProtocolStatus.ERROR,
                'details': {'error': str(e)},
                'version': self.version,
                'config': {}
            }
    
    def get_config_schema(self) -> Dict:
        """
        Get configuration schema for IS-IS
        
        Returns:
            JSON schema for configuration
        """
        return {
            "type": "object",
            "required": ["net", "interfaces"],
            "properties": {
                "net": {
                    "type": "string",
                    "pattern": "^49\\.[0-9]{4}\\.[0-9]{4}\\.[0-9]{4}\\.[0-9]{4}\\.[0-9]{2}$",
                    "description": "Network Entity Title (NET) address"
                },
                "area": {
                    "type": "string",
                    "enum": ["level-1", "level-2", "level-1-2"],
                    "default": "level-1-2",
                    "description": "IS-IS area level"
                },
                "interfaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Interfaces to enable IS-IS on"
                },
                "metric_style": {
                    "type": "string",
                    "enum": ["narrow", "wide", "transition"],
                    "default": "wide",
                    "description": "Metric style for IS-IS"
                },
                "is_type": {
                    "type": "string",
                    "enum": ["level-1", "level-2", "level-1-2"],
                    "default": "level-1-2",
                    "description": "IS type (level-1, level-2, or level-1-2)"
                },
                "authentication": {
                    "type": "object",
                    "properties": {
                        "domain_password": {"type": "string"},
                        "area_password": {"type": "string"}
                    },
                    "description": "Optional authentication configuration"
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
        if 'net' not in config:
            return False, "NET (Network Entity Title) is required"
        
        if 'interfaces' not in config or not config['interfaces']:
            return False, "At least one interface must be specified"
        
        is_type = config.get('is_type', 'level-1-2')
        if is_type not in ['level-1', 'level-2', 'level-1-2']:
            return False, f"Invalid IS type: {is_type}"
        
        metric_style = config.get('metric_style', 'wide')
        if metric_style not in ['narrow', 'wide', 'transition']:
            return False, f"Invalid metric style: {metric_style}"
        
        return True, None
    
    def get_metrics(self, device: str) -> Dict:
        """
        Get IS-IS metrics
        
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
            
            # Get neighbor count
            neighbor_cmd = "vtysh -c 'show isis neighbor' | grep -c 'Up'"
            result = asyncio.run(grpc_client.execute_command(device, neighbor_cmd))
            
            neighbor_count = 0
            if result.get("success"):
                try:
                    neighbor_count = int(result.get("output", "0").strip())
                except ValueError:
                    neighbor_count = 0
            
            return {
                'protocol': 'IS-IS',
                'is_type': self.active_configs[device]['is_type'],
                'neighbor_count': neighbor_count,
                'interface_count': len(self.active_configs[device]['interfaces']),
                'status': 'enabled'
            }
        
        except Exception as e:
            logger.error(f"Error getting IS-IS metrics for {device}: {e}")
            return {}


# Plugin instance
plugin = ISISPlugin()

