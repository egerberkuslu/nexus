"""
Configuration Tracking Module
Handles tracking of device configurations, terminal commands, and API operations
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from mininet.net import Mininet
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ConfigurationTracker:
    """Tracks applied configurations, terminal commands, and API operations"""

    def __init__(self):
        self.logger = logger
        self.applied_configurations = {
            'device_configs': {},
            'terminal_commands': {},
            'api_operations': [],
            'routing_configs': {},
            'firewall_configs': {},
            'interface_configs': {},
            'service_configs': {}
        }

    def track_device_configuration(self, device_name: str, config_type: str,
                                  config_data: Dict[str, Any], result: Optional[Dict[str, Any]] = None):
        """Track applied device configuration with enhanced interface tracking"""
        try:
            timestamp = datetime.now().isoformat()

            if device_name not in self.applied_configurations['device_configs']:
                self.applied_configurations['device_configs'][device_name] = []

            # Enhanced configuration data with current device state
            enhanced_config_data = config_data.copy()

            config_entry = {
                'timestamp': timestamp,
                'config_type': config_type,
                'config_data': enhanced_config_data,
                'result': result or {},
                'success': result.get('success', True) if result else True
            }

            self.applied_configurations['device_configs'][device_name].append(config_entry)

            # Also track interface-specific configurations separately
            if config_type == 'router_config':
                self._track_router_interface_configs(device_name, enhanced_config_data, timestamp)

            logger.info(f"Tracked {config_type} configuration for {device_name}")

        except Exception as e:
            logger.warning(f"Error tracking device configuration: {e}")

    def track_terminal_command(self, device_name: str, command: str,
                              result: Optional[str] = None, success: bool = True):
        """Track terminal command executed on device"""
        try:
            timestamp = datetime.now().isoformat()

            if device_name not in self.applied_configurations['terminal_commands']:
                self.applied_configurations['terminal_commands'][device_name] = []

            command_entry = {
                'timestamp': timestamp,
                'command': command,
                'result': result or '',
                'success': success
            }

            self.applied_configurations['terminal_commands'][device_name].append(command_entry)
            logger.debug(f"Tracked terminal command for {device_name}: {command}")

        except Exception as e:
            logger.warning(f"Error tracking terminal command: {e}")

    def track_api_operation(self, operation_type: str, operation_data: Dict[str, Any],
                           result: Optional[Dict[str, Any]] = None):
        """Track API operation performed"""
        try:
            timestamp = datetime.now().isoformat()

            operation_entry = {
                'timestamp': timestamp,
                'operation_type': operation_type,
                'operation_data': operation_data,
                'result': result or {},
                'success': result.get('success', True) if result else True
            }

            self.applied_configurations['api_operations'].append(operation_entry)
            logger.info(f"Tracked API operation: {operation_type}")

        except Exception as e:
            logger.warning(f"Error tracking API operation: {e}")

    def track_routing_config(self, device_name: str, routing_data: Dict[str, Any],
                           result: Optional[Dict[str, Any]] = None):
        """Track routing configuration"""
        try:
            timestamp = datetime.now().isoformat()

            if device_name not in self.applied_configurations['routing_configs']:
                self.applied_configurations['routing_configs'][device_name] = []

            routing_entry = {
                'timestamp': timestamp,
                'routing_data': routing_data,
                'result': result or {},
                'success': result.get('success', True) if result else True
            }

            self.applied_configurations['routing_configs'][device_name].append(routing_entry)
            logger.info(f"Tracked routing configuration for {device_name}")

        except Exception as e:
            logger.warning(f"Error tracking routing configuration: {e}")

    def track_firewall_config(self, device_name: str, firewall_data: Dict[str, Any],
                             result: Optional[Dict[str, Any]] = None):
        """Track firewall configuration"""
        try:
            timestamp = datetime.now().isoformat()

            if device_name not in self.applied_configurations['firewall_configs']:
                self.applied_configurations['firewall_configs'][device_name] = []

            firewall_entry = {
                'timestamp': timestamp,
                'firewall_data': firewall_data,
                'result': result or {},
                'success': result.get('success', True) if result else True
            }

            self.applied_configurations['firewall_configs'][device_name].append(firewall_entry)
            logger.info(f"Tracked firewall configuration for {device_name}")

        except Exception as e:
            logger.warning(f"Error tracking firewall configuration: {e}")

    def track_interface_config(self, device_name: str, interface_name: str,
                              settings: Dict[str, Any], result: Optional[Dict[str, Any]] = None):
        """Track interface configuration"""
        try:
            timestamp = datetime.now().isoformat()

            if device_name not in self.applied_configurations['interface_configs']:
                self.applied_configurations['interface_configs'][device_name] = []

            interface_entry = {
                'timestamp': timestamp,
                'interface_name': interface_name,
                'settings': settings,
                'result': result or {},
                'success': result.get('success', True) if result else True
            }

            self.applied_configurations['interface_configs'][device_name].append(interface_entry)
            logger.info(f"Tracked interface configuration for {device_name}:{interface_name}")

        except Exception as e:
            logger.warning(f"Error tracking interface configuration: {e}")

    def get_applied_configurations(self) -> Dict[str, Any]:
        """Get all tracked configurations"""
        return self.applied_configurations.copy()

    def get_device_configurations(self, device_name: Optional[str] = None) -> Dict[str, Any]:
        """Get configurations for a specific device or all devices"""
        if device_name:
            return {
                'device_configs': {device_name: self.applied_configurations['device_configs'].get(device_name, [])},
                'terminal_commands': {device_name: self.applied_configurations['terminal_commands'].get(device_name, [])},
                'routing_configs': {device_name: self.applied_configurations['routing_configs'].get(device_name, [])},
                'firewall_configs': {device_name: self.applied_configurations['firewall_configs'].get(device_name, [])},
                'interface_configs': {device_name: self.applied_configurations['interface_configs'].get(device_name, [])},
            }
        return self.applied_configurations

    def clear_configuration_tracking(self):
        """Clear all tracked configurations"""
        self.applied_configurations = {
            'device_configs': {},
            'terminal_commands': {},
            'api_operations': [],
            'routing_configs': {},
            'firewall_configs': {},
            'interface_configs': {},
            'service_configs': {}
        }
        logger.info("Configuration tracking cleared")

    def debug_tracked_configurations(self):
        """Debug method to log all tracked configurations"""
        try:
            logger.info("=== TRACKED CONFIGURATIONS DEBUG ===")

            # Debug device configs
            device_configs = self.applied_configurations.get('device_configs', {})
            logger.info(f"Device configs tracked: {len(device_configs)} devices")
            for device_name, configs in device_configs.items():
                logger.info(f"  {device_name}: {len(configs)} configurations")
                for i, config in enumerate(configs):
                    config_type = config.get('config_type', 'unknown')
                    timestamp = config.get('timestamp', 'unknown')
                    success = config.get('success', False)
                    logger.info(f"    [{i+1}] {config_type} at {timestamp} - {'SUCCESS' if success else 'FAILED'}")

            # Debug terminal commands
            terminal_commands = self.applied_configurations.get('terminal_commands', {})
            logger.info(f"Terminal commands tracked: {sum(len(cmds) for cmds in terminal_commands.values())} total")
            for device_name, commands in terminal_commands.items():
                logger.info(f"  {device_name}: {len(commands)} commands")

            # Debug API operations
            api_operations = self.applied_configurations.get('api_operations', [])
            logger.info(f"API operations tracked: {len(api_operations)}")
            for i, op in enumerate(api_operations):
                op_type = op.get('operation_type', 'unknown')
                timestamp = op.get('timestamp', 'unknown')
                success = op.get('result', {}).get('success', False)
                logger.info(f"  [{i+1}] {op_type} at {timestamp} - {'SUCCESS' if success else 'FAILED'}")

            # Debug interface configurations
            interface_configs = self.applied_configurations.get('interface_configs', {})
            logger.info(f"Interface configs tracked: {sum(len(interfaces) for interfaces in interface_configs.values())} total")
            for device_name, interfaces in interface_configs.items():
                logger.info(f"  {device_name}: {len(interfaces)} interface configurations")
                for i, interface in enumerate(interfaces):
                    interface_name = interface.get('interface_name', 'unknown')
                    timestamp = interface.get('timestamp', 'unknown')
                    settings = interface.get('settings', {})
                    logger.info(f"    [{i+1}] {interface_name} at {timestamp} - {len(settings)} settings")

            # Debug routing configurations
            routing_configs = self.applied_configurations.get('routing_configs', {})
            logger.info(f"Routing configs tracked: {sum(len(routes) for routes in routing_configs.values())} total")

            # Debug firewall configurations
            firewall_configs = self.applied_configurations.get('firewall_configs', {})
            logger.info(f"Firewall configs tracked: {sum(len(rules) for rules in firewall_configs.values())} total")

            logger.info("=== END TRACKED CONFIGURATIONS DEBUG ===")

        except Exception as e:
            logger.error(f"Error in debug_tracked_configurations: {e}")

    def export_configurations(self, file_path: str) -> bool:
        """Export all tracked configurations to a JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.applied_configurations, f, indent=2, default=str)
            logger.info(f"Configurations exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting configurations: {e}")
            return False

    def import_configurations(self, file_path: str) -> bool:
        """Import configurations from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                self.applied_configurations = json.load(f)
            logger.info(f"Configurations imported from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error importing configurations: {e}")
            return False

    def _track_router_interface_configs(self, device_name: str, config_data: Dict[str, Any], timestamp: str):
        """Track router interface configurations separately"""
        try:
            # Extract interface configurations from router config
            interfaces = config_data.get('interfaces', {})

            for interface_name, interface_config in interfaces.items():
                self.track_interface_config(
                    device_name=device_name,
                    interface_name=interface_name,
                    settings=interface_config,
                    result={'success': True, 'timestamp': timestamp}
                )

        except Exception as e:
            logger.warning(f"Error tracking router interface configs: {e}")

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of all tracked configurations"""
        try:
            summary = {
                'total_devices': len(self.applied_configurations['device_configs']),
                'total_terminal_commands': sum(len(cmds) for cmds in self.applied_configurations['terminal_commands'].values()),
                'total_api_operations': len(self.applied_configurations['api_operations']),
                'total_routing_configs': sum(len(routes) for routes in self.applied_configurations['routing_configs'].values()),
                'total_firewall_configs': sum(len(rules) for rules in self.applied_configurations['firewall_configs'].values()),
                'total_interface_configs': sum(len(interfaces) for interfaces in self.applied_configurations['interface_configs'].values()),
                'last_updated': datetime.now().isoformat()
            }

            # Get most recent timestamps
            recent_timestamps = []
            for device_configs in self.applied_configurations['device_configs'].values():
                for config in device_configs:
                    recent_timestamps.append(config.get('timestamp', ''))

            for api_ops in self.applied_configurations['api_operations']:
                recent_timestamps.append(api_ops.get('timestamp', ''))

            if recent_timestamps:
                summary['most_recent'] = max(recent_timestamps)

            return summary

        except Exception as e:
            logger.error(f"Error generating configuration summary: {e}")
            return {'error': str(e)}
