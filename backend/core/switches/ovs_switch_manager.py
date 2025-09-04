"""
OVS Switch Manager
Enhanced Open vSwitch support with additional management capabilities
"""

import os
import subprocess
import time
from typing import Dict, List, Optional, Any

from .base_switch_manager import BaseSwitchManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class OVSSwitchManager(BaseSwitchManager):
    """Enhanced Open vSwitch manager with additional capabilities"""

    def __init__(self):
        super().__init__("Open vSwitch", "ovs")
        self.ovs_version = None
        self.bridge_name = None

    def check_installation(self) -> bool:
        """Check if Open vSwitch is properly installed"""
        try:
            # Check for ovs-vsctl command
            result = subprocess.run(['which', 'ovs-vsctl'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("ovs-vsctl not found. Installing Open vSwitch...")
                self._install_openvswitch()
                return False

            # Get OVS version
            result = subprocess.run(['ovs-vsctl', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                self.ovs_version = version_line.split()[-1]
                logger.info(f"Open vSwitch version: {self.ovs_version}")
            else:
                logger.warning("Could not determine OVS version")

            # Check if OVS service is running
            result = subprocess.run(['sudo', 'systemctl', 'is-active', 'openvswitch-switch'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Open vSwitch service not running, starting it...")
                subprocess.run(['sudo', 'systemctl', 'start', 'openvswitch-switch'], check=False)

            return True
        except Exception as e:
            logger.error(f"Error checking OVS installation: {e}")
            return False

    def _install_openvswitch(self) -> bool:
        """Install Open vSwitch"""
        try:
            logger.info("Installing Open vSwitch...")

            # Update package list
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)

            # Install Open vSwitch
            result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'openvswitch-switch'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                # Start and enable the service
                subprocess.run(['sudo', 'systemctl', 'start', 'openvswitch-switch'], check=False)
                subprocess.run(['sudo', 'systemctl', 'enable', 'openvswitch-switch'], check=False)
                logger.info("Open vSwitch installed successfully")
                return True
            else:
                logger.error(f"Failed to install Open vSwitch: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error installing Open vSwitch: {e}")
            return False

    def create_switch(self, switch_id: str, **kwargs) -> Any:
        """Create an OVS bridge"""
        try:
            self.bridge_name = f"ovs-{switch_id}"

            logger.info(f"Creating OVS bridge: {self.bridge_name}")

            # Create the bridge
            result = subprocess.run(['sudo', 'ovs-vsctl', 'add-br', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to create OVS bridge {self.bridge_name}: {result.stderr}")
                return None

            # Configure bridge parameters
            self._configure_bridge_parameters(kwargs)

            # Set protocols if specified
            protocols = kwargs.get('protocols', 'OpenFlow13')
            if protocols:
                result = subprocess.run(['sudo', 'ovs-vsctl', 'set', 'bridge', self.bridge_name,
                                       f'protocols={protocols}'], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Failed to set protocols on {self.bridge_name}: {result.stderr}")

            # Set datapath ID if specified
            dpid = kwargs.get('dpid')
            if dpid:
                result = subprocess.run(['sudo', 'ovs-vsctl', 'set', 'bridge', self.bridge_name,
                                       f'other-config:datapath-id={dpid}'], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Failed to set DPID on {self.bridge_name}: {result.stderr}")

            logger.info(f"OVS bridge {self.bridge_name} created and configured")
            return self.bridge_name

        except Exception as e:
            logger.error(f"Error creating OVS bridge: {e}")
            return None

    def _configure_bridge_parameters(self, kwargs: Dict[str, Any]):
        """Configure OVS bridge parameters"""
        try:
            # Set fail mode
            fail_mode = kwargs.get('fail_mode', 'secure')
            subprocess.run(['sudo', 'ovs-vsctl', 'set-fail-mode', self.bridge_name, fail_mode],
                         capture_output=True, check=False)

            # Configure STP if requested
            stp = kwargs.get('stp', False)
            if stp:
                subprocess.run(['sudo', 'ovs-vsctl', 'set', 'bridge', self.bridge_name, 'stp_enable=true'],
                             capture_output=True, check=False)

            # Set bridge priority
            priority = kwargs.get('priority', 32768)
            subprocess.run(['sudo', 'ovs-vsctl', 'set', 'bridge', self.bridge_name,
                          f'other-config:bridge-priority={priority}'], capture_output=True, check=False)

        except Exception as e:
            logger.warning(f"Error configuring bridge parameters: {e}")

    def add_port(self, interface_name: str, **kwargs) -> bool:
        """Add a port to the OVS bridge"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            logger.info(f"Adding port {interface_name} to OVS bridge {self.bridge_name}")

            # Add port to bridge
            result = subprocess.run(['sudo', 'ovs-vsctl', 'add-port', self.bridge_name, interface_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to add port {interface_name}: {result.stderr}")
                return False

            # Configure port parameters
            self._configure_port_parameters(interface_name, kwargs)

            logger.info(f"Port {interface_name} added to bridge {self.bridge_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding port {interface_name}: {e}")
            return False

    def _configure_port_parameters(self, port_name: str, kwargs: Dict[str, Any]):
        """Configure port-specific parameters"""
        try:
            # Set VLAN mode
            vlan_mode = kwargs.get('vlan_mode')
            if vlan_mode:
                subprocess.run(['sudo', 'ovs-vsctl', 'set', 'port', port_name,
                              f'vlan_mode={vlan_mode}'], capture_output=True, check=False)

            # Set tag
            tag = kwargs.get('tag')
            if tag:
                subprocess.run(['sudo', 'ovs-vsctl', 'set', 'port', port_name,
                              f'tag={tag}'], capture_output=True, check=False)

            # Set QoS parameters
            qos = kwargs.get('qos')
            if qos:
                subprocess.run(['sudo', 'ovs-vsctl', 'set', 'port', port_name,
                              f'qos={qos}'], capture_output=True, check=False)

        except Exception as e:
            logger.warning(f"Error configuring port parameters: {e}")

    def remove_port(self, interface_name: str) -> bool:
        """Remove a port from the OVS bridge"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            logger.info(f"Removing port {interface_name} from OVS bridge {self.bridge_name}")

            result = subprocess.run(['sudo', 'ovs-vsctl', 'del-port', self.bridge_name, interface_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to remove port {interface_name}: {result.stderr}")
                return False

            logger.info(f"Port {interface_name} removed from bridge {self.bridge_name}")
            return True

        except Exception as e:
            logger.error(f"Error removing port {interface_name}: {e}")
            return False

    def get_switch_stats(self) -> Dict[str, Any]:
        """Get OVS bridge statistics"""
        if not self.bridge_name:
            return {}

        try:
            stats = {
                'bridge_name': self.bridge_name,
                'ovs_version': self.ovs_version,
                'ports': self._get_bridge_ports(),
                'flows': self._get_flow_stats(),
                'bridge_info': self._get_bridge_info()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting OVS stats: {e}")
            return {}

    def _get_bridge_ports(self) -> List[Dict[str, Any]]:
        """Get bridge port information"""
        if not self.bridge_name:
            return []

        try:
            result = subprocess.run(['sudo', 'ovs-vsctl', 'list-ports', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return []

            ports = []
            for port_name in result.stdout.strip().split('\n'):
                if port_name.strip():
                    port_info = self._get_port_info(port_name.strip())
                    ports.append(port_info)

            return ports
        except Exception as e:
            logger.error(f"Error getting bridge ports: {e}")
            return []

    def _get_port_info(self, port_name: str) -> Dict[str, Any]:
        """Get detailed port information"""
        try:
            result = subprocess.run(['sudo', 'ovs-vsctl', 'list', 'port', port_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {'name': port_name, 'error': 'Failed to get info'}

            port_info = {'name': port_name}

            # Parse port information
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    if value:
                        port_info[key] = value

            return port_info
        except Exception as e:
            return {'name': port_name, 'error': str(e)}

    def _get_flow_stats(self) -> Dict[str, Any]:
        """Get OpenFlow flow statistics"""
        if not self.bridge_name:
            return {}

        try:
            result = subprocess.run(['sudo', 'ovs-ofctl', 'dump-flows', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {'error': 'Failed to get flow stats'}

            flows = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header

            for line in lines:
                if line.strip():
                    flow_info = self._parse_flow_line(line)
                    flows.append(flow_info)

            return {
                'total_flows': len(flows),
                'flows': flows[:100]  # Limit to first 100 flows
            }
        except Exception as e:
            logger.error(f"Error getting flow stats: {e}")
            return {'error': str(e)}

    def _parse_flow_line(self, line: str) -> Dict[str, Any]:
        """Parse a single flow line from ovs-ofctl output"""
        try:
            # Basic parsing - in a real implementation, this would be more comprehensive
            parts = line.split(',')
            flow = {}

            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    flow[key.strip()] = value.strip()

            return flow
        except:
            return {'raw': line}

    def _get_bridge_info(self) -> Dict[str, Any]:
        """Get detailed bridge information"""
        if not self.bridge_name:
            return {}

        try:
            result = subprocess.run(['sudo', 'ovs-vsctl', 'list', 'bridge', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {}

            bridge_info = {}

            # Parse bridge information
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    if value:
                        bridge_info[key] = value

            return bridge_info
        except Exception as e:
            logger.error(f"Error getting bridge info: {e}")
            return {}

    def get_bridge_status(self) -> Dict[str, Any]:
        """Get comprehensive OVS bridge status"""
        if not self.bridge_name:
            return {'status': 'not_created'}

        try:
            # Check if bridge exists
            result = subprocess.run(['sudo', 'ovs-vsctl', 'br-exists', self.bridge_name],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                return {'status': 'not_found'}

            # Get bridge status
            status = {
                'status': 'active',
                'bridge_name': self.bridge_name,
                'ports': len(self._get_bridge_ports()),
                'flows': self._get_flow_stats().get('total_flows', 0),
                'controller_connected': self._check_controller_connection()
            }

            return status
        except Exception as e:
            logger.error(f"Error getting bridge status: {e}")
            return {'status': 'error', 'error': str(e)}

    def _check_controller_connection(self) -> bool:
        """Check if controller is connected"""
        if not self.bridge_name:
            return False

        try:
            result = subprocess.run(['sudo', 'ovs-vsctl', 'get-controller', self.bridge_name],
                                  capture_output=True, text=True)
            return result.returncode == 0 and result.stdout.strip() != ''
        except:
            return False

    def add_flow(self, **kwargs) -> bool:
        """Add an OpenFlow flow"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            # Build ovs-ofctl add-flow command
            cmd = ['sudo', 'ovs-ofctl', 'add-flow', self.bridge_name]

            # Build flow string
            flow_parts = []

            # Priority
            priority = kwargs.get('priority', 100)
            flow_parts.append(f"priority={priority}")

            # Match fields
            for key, value in kwargs.items():
                if key not in ['priority', 'actions', 'table']:
                    flow_parts.append(f"{key}={value}")

            # Actions
            actions = kwargs.get('actions', 'normal')
            flow_parts.append(f"actions={actions}")

            flow_string = ','.join(flow_parts)
            cmd.append(flow_string)

            logger.info(f"Adding flow: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Flow added successfully")
                return True
            else:
                logger.error(f"Failed to add flow: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error adding flow: {e}")
            return False

    def del_flows(self, **kwargs) -> bool:
        """Delete OpenFlow flows"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            cmd = ['sudo', 'ovs-ofctl', 'del-flows', self.bridge_name]

            # Build match string if criteria provided
            if kwargs:
                flow_parts = []
                for key, value in kwargs.items():
                    flow_parts.append(f"{key}={value}")
                cmd.append(','.join(flow_parts))

            logger.info(f"Deleting flows: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Flows deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete flows: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error deleting flows: {e}")
            return False

    def cleanup(self) -> bool:
        """Clean up the OVS bridge"""
        try:
            if not self.bridge_name:
                return True

            logger.info(f"Cleaning up OVS bridge {self.bridge_name}")

            # Get all ports before deletion
            ports = self._get_bridge_ports()

            # Delete the bridge (this also removes all ports)
            result = subprocess.run(['sudo', 'ovs-vsctl', 'del-br', self.bridge_name],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"OVS bridge {self.bridge_name} deleted successfully")
                self.bridge_name = None
                return True
            else:
                logger.error(f"Failed to delete OVS bridge {self.bridge_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error cleaning up OVS bridge: {e}")
            return False
