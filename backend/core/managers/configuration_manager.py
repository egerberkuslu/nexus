"""
Configuration Manager
Handles configuration tracking, device configurations, and configuration management
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ConfigurationEntry:
    """Represents a configuration entry"""
    device_name: str
    config_type: str
    config_data: Dict[str, Any]
    timestamp: str
    result: Optional[Dict[str, Any]] = None
    success: bool = True


class ConfigurationManager:
    """Manages configuration tracking and device configurations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Configuration tracking system
        self.applied_configurations = {
            'device_configs': {},  # Applied device configurations from API
            'terminal_commands': {},  # Terminal commands executed on nodes
            'api_operations': [],  # List of API operations performed
            'routing_configs': {},  # Routing configurations
            'firewall_configs': {},  # Firewall configurations
            'interface_configs': {},  # Interface configurations
            'service_configs': {}  # Service configurations
        }

        # Configuration history
        self.config_history: List[ConfigurationEntry] = []

    def track_device_configuration(self, device_name: str, config_type: str,
                                  config_data: Dict[str, Any], result: Dict[str, Any] = None) -> None:
        """Track a device configuration change"""
        try:
            timestamp = datetime.now().isoformat()

            # Create configuration entry
            entry = ConfigurationEntry(
                device_name=device_name,
                config_type=config_type,
                config_data=config_data.copy(),
                timestamp=timestamp,
                result=result,
                success=result is None or result.get('success', True)
            )

            # Add to history
            self.config_history.append(entry)

            # Update applied configurations
            if device_name not in self.applied_configurations['device_configs']:
                self.applied_configurations['device_configs'][device_name] = {}

            self.applied_configurations['device_configs'][device_name][config_type] = {
                'config': config_data,
                'timestamp': timestamp,
                'result': result
            }

            self.logger.info(f"Tracked {config_type} configuration for {device_name}")

        except Exception as e:
            self.logger.error(f"Error tracking device configuration: {e}")

    def track_terminal_command(self, device_name: str, command: str,
                             result: str = None, success: bool = True) -> None:
        """Track a terminal command execution"""
        try:
            timestamp = datetime.now().isoformat()

            command_entry = {
                'device_name': device_name,
                'command': command,
                'result': result,
                'timestamp': timestamp,
                'success': success
            }

            # Update applied configurations
            if device_name not in self.applied_configurations['terminal_commands']:
                self.applied_configurations['terminal_commands'][device_name] = []

            self.applied_configurations['terminal_commands'][device_name].append(command_entry)

            self.logger.info(f"Tracked terminal command for {device_name}: {command[:50]}...")

        except Exception as e:
            self.logger.error(f"Error tracking terminal command: {e}")

    def track_api_operation(self, operation_type: str, operation_data: Dict[str, Any],
                          result: Dict[str, Any] = None) -> None:
        """Track an API operation"""
        try:
            timestamp = datetime.now().isoformat()

            operation_entry = {
                'operation_type': operation_type,
                'operation_data': operation_data,
                'result': result,
                'timestamp': timestamp,
                'success': result is None or result.get('success', True)
            }

            self.applied_configurations['api_operations'].append(operation_entry)

            self.logger.info(f"Tracked API operation: {operation_type}")

        except Exception as e:
            self.logger.error(f"Error tracking API operation: {e}")

    def get_applied_configurations(self) -> Dict[str, Any]:
        """Get all applied configurations"""
        return self.applied_configurations.copy()

    def clear_configuration_tracking(self) -> None:
        """Clear all configuration tracking data"""
        try:
            self.applied_configurations = {
                'device_configs': {},
                'terminal_commands': {},
                'api_operations': [],
                'routing_configs': {},
                'firewall_configs': {},
                'interface_configs': {},
                'service_configs': {}
            }
            self.config_history.clear()

            self.logger.info("Configuration tracking cleared")

        except Exception as e:
            self.logger.error(f"Error clearing configuration tracking: {e}")

    def debug_tracked_configurations(self) -> Dict[str, Any]:
        """Get debug information about tracked configurations"""
        try:
            debug_info = {
                'total_configurations': len(self.config_history),
                'device_configs_count': len(self.applied_configurations['device_configs']),
                'terminal_commands_count': sum(len(cmds) for cmds in self.applied_configurations['terminal_commands'].values()),
                'api_operations_count': len(self.applied_configurations['api_operations']),
                'configuration_types': {},
                'devices_with_configs': list(self.applied_configurations['device_configs'].keys()),
                'recent_configurations': []
            }

            # Count configuration types
            for entry in self.config_history[-10:]:  # Last 10 configurations
                config_type = entry.config_type
                if config_type not in debug_info['configuration_types']:
                    debug_info['configuration_types'][config_type] = 0
                debug_info['configuration_types'][config_type] += 1

                # Add to recent configurations
                debug_info['recent_configurations'].append({
                    'device': entry.device_name,
                    'type': entry.config_type,
                    'timestamp': entry.timestamp,
                    'success': entry.success
                })

            return debug_info

        except Exception as e:
            self.logger.error(f"Error getting debug configuration info: {e}")
            return {'error': str(e)}

    def get_device_configurations(self, device_name: str) -> Dict[str, Any]:
        """Get all configurations for a specific device"""
        try:
            device_configs = {}

            # Get device configs
            if device_name in self.applied_configurations['device_configs']:
                device_configs['device_configs'] = self.applied_configurations['device_configs'][device_name]

            # Get terminal commands
            if device_name in self.applied_configurations['terminal_commands']:
                device_configs['terminal_commands'] = self.applied_configurations['terminal_commands'][device_name]

            # Get related API operations
            related_operations = []
            for operation in self.applied_configurations['api_operations']:
                if operation.get('operation_data', {}).get('device_name') == device_name:
                    related_operations.append(operation)

            if related_operations:
                device_configs['related_operations'] = related_operations

            return device_configs

        except Exception as e:
            self.logger.error(f"Error getting device configurations: {e}")
            return {'error': str(e)}

    def export_configurations(self, file_path: str) -> bool:
        """Export all configurations to a JSON file"""
        try:
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'applied_configurations': self.applied_configurations,
                'config_history': [
                    {
                        'device_name': entry.device_name,
                        'config_type': entry.config_type,
                        'config_data': entry.config_data,
                        'timestamp': entry.timestamp,
                        'result': entry.result,
                        'success': entry.success
                    }
                    for entry in self.config_history
                ]
            }

            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.logger.info(f"Configurations exported to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting configurations: {e}")
            return False

    def import_configurations(self, file_path: str) -> bool:
        """Import configurations from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)

            # Restore applied configurations
            if 'applied_configurations' in import_data:
                self.applied_configurations.update(import_data['applied_configurations'])

            # Restore configuration history
            if 'config_history' in import_data:
                for entry_data in import_data['config_history']:
                    entry = ConfigurationEntry(
                        device_name=entry_data['device_name'],
                        config_type=entry_data['config_type'],
                        config_data=entry_data['config_data'],
                        timestamp=entry_data['timestamp'],
                        result=entry_data.get('result'),
                        success=entry_data.get('success', True)
                    )
                    self.config_history.append(entry)

            self.logger.info(f"Configurations imported from {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error importing configurations: {e}")
            return False

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of all configurations"""
        try:
            summary = {
                'total_devices': len(self.applied_configurations['device_configs']),
                'total_terminal_commands': sum(len(cmds) for cmds in self.applied_configurations['terminal_commands'].values()),
                'total_api_operations': len(self.applied_configurations['api_operations']),
                'configuration_types': {},
                'devices_by_config_type': {},
                'recent_activity': []
            }

            # Analyze configuration types
            for device_name, configs in self.applied_configurations['device_configs'].items():
                for config_type in configs.keys():
                    if config_type not in summary['configuration_types']:
                        summary['configuration_types'][config_type] = 0
                        summary['devices_by_config_type'][config_type] = []

                    summary['configuration_types'][config_type] += 1
                    summary['devices_by_config_type'][config_type].append(device_name)

            # Get recent activity (last 5 configurations)
            for entry in self.config_history[-5:]:
                summary['recent_activity'].append({
                    'device': entry.device_name,
                    'action': f"{entry.config_type} configuration",
                    'timestamp': entry.timestamp,
                    'success': entry.success
                })

            return summary

        except Exception as e:
            self.logger.error(f"Error getting configuration summary: {e}")
            return {'error': str(e)}

    def validate_configuration(self, device_name: str, config_type: str,
                             config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a configuration before applying"""
        try:
            validation_result = {
                'valid': True,
                'warnings': [],
                'errors': []
            }

            # Basic validation rules
            if config_type == 'interface':
                # Validate IP address format
                if 'ip' in config_data:
                    ip = config_data['ip']
                    if not self._is_valid_ip(ip) and ip != 'auto':
                        validation_result['errors'].append(f"Invalid IP address format: {ip}")

                # Validate MAC address format
                if 'mac' in config_data:
                    mac = config_data['mac']
                    if not self._is_valid_mac(mac) and mac != 'auto':
                        validation_result['errors'].append(f"Invalid MAC address format: {mac}")

            elif config_type == 'routing':
                # Validate routing configuration
                if 'routes' in config_data:
                    for route in config_data['routes']:
                        if 'destination' in route and not self._is_valid_network(route['destination']):
                            validation_result['warnings'].append(f"Potentially invalid destination network: {route['destination']}")

            # Set overall validity
            validation_result['valid'] = len(validation_result['errors']) == 0

            return validation_result

        except Exception as e:
            self.logger.error(f"Error validating configuration: {e}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}'],
                'warnings': []
            }

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$'
        return bool(re.match(ip_pattern, ip))

    def _is_valid_mac(self, mac: str) -> bool:
        """Validate MAC address format"""
        import re
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(mac_pattern, mac))

    def _is_valid_network(self, network: str) -> bool:
        """Validate network address format"""
        import re
        network_pattern = r'^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$'
        return bool(re.match(network_pattern, network))
