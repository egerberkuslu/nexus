"""
Switch Factory for managing multiple SDN switch types
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.logger import setup_logger
from .base_switch_manager import BaseSwitchManager
from .linux_bridge_switch import LinuxBridgeSwitch
from .ovs_switch_manager import OVSSwitchManager
from .p4_switch_manager import P4SwitchManager

logger = setup_logger(__name__)

class SwitchFactory:
    """Factory for managing multiple network switch types"""

    def __init__(self):
        self.switches: Dict[str, BaseSwitchManager] = {}
        self.active_switches: Dict[str, BaseSwitchManager] = {}
        self.switch_registry: Dict[str, type] = {
            'ovs': OVSSwitchManager,
            'linux_bridge': LinuxBridgeSwitch,
            'p4': P4SwitchManager
        }

        # Initialize switch instances
        self._initialize_switches()

    def _initialize_switches(self):
        """Initialize all available switch managers"""
        for switch_type, switch_class in self.switch_registry.items():
            if switch_class is not None:
                try:
                    switch_instance = switch_class()
                    self.switches[switch_type] = switch_instance
                    logger.info(f"Initialized {switch_type} switch manager")
                except Exception as e:
                    logger.error(f"Failed to initialize {switch_type} switch: {e}")

    def get_available_switches(self) -> List[str]:
        """Get list of available switch types"""
        return list(self.switch_registry.keys())

    def get_switch_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all switches"""
        info = {}
        for switch_type, switch in self.switches.items():
            if switch:
                info[switch_type] = {
                    'name': switch.name,
                    'running': switch.is_running,
                    'switch_type': switch.switch_type,
                    'status': switch.get_status(),
                    'capabilities': self._get_switch_capabilities(switch_type)
                }
        return info

    def _get_switch_capabilities(self, switch_type: str) -> Dict[str, Any]:
        """Get capabilities of a specific switch type"""
        capabilities = {
            'supports_installation': hasattr(self.switches.get(switch_type), 'check_installation'),
            'supports_p4_programs': switch_type == 'p4',
            'supports_bridge_commands': switch_type in ['linux_bridge', 'ovs'],
            'supports_openflow': switch_type in ['ovs', 'p4'],
            'standalone_operation': switch_type in ['linux_bridge']
        }

        if switch_type == 'p4':
            capabilities.update({
                'p4_programs': ['basic_forwarding', 'l2_forwarding', 'l3_forwarding', 'load_balancer', 'firewall'],
                'supports_runtime_programming': True,
                'supports_table_entries': True
            })

        return capabilities

    def create_switch(self, switch_type: str, switch_id: str, **kwargs) -> Optional[Any]:
        """Create a switch instance"""
        if switch_type not in self.switches:
            logger.error(f"Unknown switch type: {switch_type}")
            return None

        switch = self.switches[switch_type]

        try:
            result = switch.create_switch(switch_id, **kwargs)
            if result:
                self.active_switches[switch_id] = switch
                logger.info(f"Created {switch_type} switch: {switch_id}")
                return result
            else:
                logger.error(f"Failed to create {switch_type} switch: {switch_id}")
                return None
        except Exception as e:
            logger.error(f"Error creating {switch_type} switch {switch_id}: {e}")
            return None

    def get_switch_manager(self, switch_type: str) -> Optional[BaseSwitchManager]:
        """Get switch manager instance"""
        return self.switches.get(switch_type)

    def get_active_switch(self, switch_id: str) -> Optional[BaseSwitchManager]:
        """Get active switch by ID"""
        return self.active_switches.get(switch_id)

    def get_switch_status(self, switch_type: str = None, switch_id: str = None) -> Dict[str, Any]:
        """Get status of switches"""
        if switch_id:
            switch = self.active_switches.get(switch_id)
            if switch:
                return switch.get_status()
            else:
                return {'error': 'Switch not found'}

        if switch_type:
            switch = self.switches.get(switch_type)
            if switch:
                return switch.get_status()
            else:
                return {'error': 'Switch type not found'}

        # Return all switch statuses
        all_status = {}
        for switch_type, switch in self.switches.items():
            all_status[switch_type] = switch.get_status()

        return all_status

    def get_switch_stats(self, switch_type: str = None, switch_id: str = None) -> Dict[str, Any]:
        """Get statistics from switches"""
        if switch_id:
            switch = self.active_switches.get(switch_id)
            if switch:
                return switch.get_switch_stats()
            else:
                return {}

        if switch_type:
            switch = self.switches.get(switch_type)
            if switch:
                return switch.get_switch_stats()
            else:
                return {}

        # Return all switch stats
        all_stats = {}
        for switch_type, switch in self.switches.items():
            all_stats[switch_type] = switch.get_switch_stats()

        return all_stats

    def install_switch(self, switch_type: str) -> bool:
        """Install switch software if supported"""
        if switch_type not in self.switches:
            logger.error(f"Unknown switch type: {switch_type}")
            return False

        switch = self.switches[switch_type]

        if hasattr(switch, 'check_installation'):
            installed = switch.check_installation()
            if not installed:
                logger.warning(f"{switch_type} is not installed. Please install manually:")
                if switch_type == 'linux_bridge':
                    logger.warning("  sudo apt-get install bridge-utils")
                elif switch_type == 'p4':
                    logger.warning("  Run P4 switch installation scripts")
                return False
            return True
        else:
            logger.info(f"No installation method available for {switch_type}")
            return True

    def get_switch_capabilities(self, switch_type: str) -> Dict[str, Any]:
        """Get capabilities of a specific switch type"""
        if switch_type not in self.switches:
            return {}

        switch = self.switches[switch_type]
        capabilities = self._get_switch_capabilities(switch_type)

        capabilities.update({
            'name': switch.name,
            'supported_features': []
        })

        # Add specific capabilities
        if switch_type == 'linux_bridge':
            capabilities['supported_features'].extend([
                'L2 learning bridge',
                'STP support',
                'VLAN support',
                'Bridge utilities (brctl)',
                'MAC address table',
                'Port configuration'
            ])
        elif switch_type == 'p4':
            capabilities['supported_features'].extend([
                'Programmable data plane',
                'P4Runtime API',
                'Runtime program updates',
                'Table entry management',
                'Custom packet processing',
                'Multiple program templates'
            ])
        elif switch_type == 'ovs':
            capabilities['supported_features'].extend([
                'OpenFlow support',
                'OVS-specific features',
                'Flow tables',
                'QoS support',
                'NetFlow/sFlow'
            ])

        return capabilities

    def configure_switch_port(self, switch_id: str, port_name: str, config: Dict[str, Any]) -> bool:
        """Configure a port on a specific switch"""
        switch = self.active_switches.get(switch_id)
        if not switch:
            logger.error(f"Switch {switch_id} not found")
            return False

        return switch.configure_port(port_name, config)

    def get_port_config(self, switch_id: str, port_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific port"""
        switch = self.active_switches.get(switch_id)
        if not switch:
            return None

        return switch.get_port_config(port_name)

    def list_switch_ports(self, switch_id: str) -> List[str]:
        """List all ports on a specific switch"""
        switch = self.active_switches.get(switch_id)
        if not switch:
            return []

        return switch.list_ports()

    def stop_all_switches(self):
        """Stop all running switches without deleting them"""
        logger.info("Stopping all switches...")

        # Stop active switches
        for switch_id, switch in list(self.active_switches.items()):
            try:
                if hasattr(switch, 'stop_switch_process'):
                    switch.stop_switch_process()
                logger.info(f"Stopped switch {switch_id}")
            except Exception as e:
                logger.error(f"Error stopping switch {switch_id}: {e}")

        logger.info("All switches stopped")

    def cleanup_switches(self):
        """Clean up all switches"""
        logger.info("Cleaning up all switches...")

        # Clean up active switches
        for switch_id, switch in list(self.active_switches.items()):
            try:
                if hasattr(switch, 'cleanup'):
                    switch.cleanup()
                logger.info(f"Cleaned up switch {switch_id}")
            except Exception as e:
                logger.error(f"Error cleaning up switch {switch_id}: {e}")

        self.active_switches.clear()
        logger.info("Switch cleanup completed")

    # P4-specific methods
    def compile_p4_program(self, switch_type: str, program_name: str) -> tuple[bool, Optional[str]]:
        """Compile a P4 program"""
        if switch_type != 'p4':
            return False, "Not a P4 switch"

        p4_switch = self.switches.get('p4')
        if not p4_switch:
            return False, "P4 switch not available"

        return p4_switch.compile_p4_program(program_name)

    def add_p4_table_entry(self, switch_type: str, table_name: str, match_fields: Dict[str, Any],
                          action_name: str, action_params: Dict[str, Any] = None) -> bool:
        """Add entry to P4 table"""
        if switch_type != 'p4':
            return False

        p4_switch = self.switches.get('p4')
        if not p4_switch:
            return False

        return p4_switch.add_table_entry(table_name, match_fields, action_name, action_params)

    def get_p4_table_entries(self, switch_type: str, table_name: str = None) -> Dict[str, List[Dict]]:
        """Get P4 table entries"""
        if switch_type != 'p4':
            return {}

        p4_switch = self.switches.get('p4')
        if not p4_switch:
            return {}

        return p4_switch.get_table_entries(table_name)

    def create_p4_program_template(self, switch_type: str, program_name: str,
                                  program_type: str = "l2_forwarding") -> str:
        """Create P4 program template"""
        if switch_type != 'p4':
            return ""

        p4_switch = self.switches.get('p4')
        if not p4_switch:
            return ""

        return p4_switch.create_advanced_program(program_name, program_type)
