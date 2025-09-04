"""
Linux Bridge Switch Manager
Provides Linux Bridge switch support with brctl commands and L2 learning
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Any

from .base_switch_manager import BaseSwitchManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class LinuxBridgeSwitch(BaseSwitchManager):
    """Linux Bridge switch implementation using built-in Linux bridging"""

    def __init__(self):
        super().__init__("Linux Bridge", "linux_bridge")
        self.bridge_name = None
        self.bridge_interfaces = []

    def check_installation(self) -> bool:
        """Check if bridge utilities are available"""
        try:
            result = subprocess.run(['which', 'brctl'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("brctl not found. Installing bridge-utils...")
                self._install_bridge_utils()
                return False

            # Check if bridge module is loaded
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'bridge' not in result.stdout:
                logger.info("Loading bridge kernel module...")
                subprocess.run(['sudo', 'modprobe', 'bridge'], check=True)

            return True
        except Exception as e:
            logger.error(f"Error checking bridge installation: {e}")
            return False

    def _install_bridge_utils(self) -> bool:
        """Install bridge utilities"""
        try:
            logger.info("Installing bridge-utils package...")
            result = subprocess.run(['sudo', 'apt-get', 'update'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("Failed to update package list")
                return False

            result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'bridge-utils'],
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error installing bridge-utils: {e}")
            return False

    def create_switch(self, switch_id: str, **kwargs) -> Any:
        """Create a Linux bridge switch"""
        try:
            self.bridge_name = f"br-{switch_id}"

            logger.info(f"Creating Linux bridge switch: {self.bridge_name}")

            # Create the bridge
            result = subprocess.run(['sudo', 'brctl', 'addbr', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to create bridge {self.bridge_name}: {result.stderr}")
                return None

            # Set bridge parameters for better performance
            self._configure_bridge_parameters()

            # Bring up the bridge
            result = subprocess.run(['sudo', 'ip', 'link', 'set', self.bridge_name, 'up'],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to bring up bridge {self.bridge_name}: {result.stderr}")
                return None

            logger.info(f"Linux bridge {self.bridge_name} created and configured")
            return self.bridge_name

        except Exception as e:
            logger.error(f"Error creating Linux bridge switch: {e}")
            return None

    def _configure_bridge_parameters(self):
        """Configure bridge parameters for optimal performance"""
        try:
            # Set forwarding delay to 0 for faster convergence
            subprocess.run(['sudo', 'brctl', 'setfd', self.bridge_name, '0'],
                         capture_output=True, check=False)

            # Set hello time
            subprocess.run(['sudo', 'brctl', 'sethello', self.bridge_name, '1'],
                         capture_output=True, check=False)

            # Enable STP if requested (default: disabled for simplicity)
            stp_enabled = os.environ.get('BRIDGE_STP', '0')
            subprocess.run(['sudo', 'brctl', 'stp', self.bridge_name, stp_enabled],
                         capture_output=True, check=False)

        except Exception as e:
            logger.warning(f"Error configuring bridge parameters: {e}")

    def add_interface(self, interface_name: str) -> bool:
        """Add an interface to the bridge"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            logger.info(f"Adding interface {interface_name} to bridge {self.bridge_name}")

            # Bring interface down first
            subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'down'],
                         capture_output=True, check=False)

            # Add interface to bridge
            result = subprocess.run(['sudo', 'brctl', 'addif', self.bridge_name, interface_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to add interface {interface_name}: {result.stderr}")
                return False

            # Bring interface up
            subprocess.run(['sudo', 'ip', 'link', 'set', interface_name, 'up'],
                         capture_output=True, check=False)

            self.bridge_interfaces.append(interface_name)
            logger.info(f"Interface {interface_name} added to bridge {self.bridge_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding interface {interface_name}: {e}")
            return False

    def remove_interface(self, interface_name: str) -> bool:
        """Remove an interface from the bridge"""
        if not self.bridge_name:
            logger.error("Bridge not created yet")
            return False

        try:
            logger.info(f"Removing interface {interface_name} from bridge {self.bridge_name}")

            result = subprocess.run(['sudo', 'brctl', 'delif', self.bridge_name, interface_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to remove interface {interface_name}: {result.stderr}")
                return False

            if interface_name in self.bridge_interfaces:
                self.bridge_interfaces.remove(interface_name)

            logger.info(f"Interface {interface_name} removed from bridge {self.bridge_name}")
            return True

        except Exception as e:
            logger.error(f"Error removing interface {interface_name}: {e}")
            return False

    def get_switch_stats(self) -> Dict[str, Any]:
        """Get bridge statistics"""
        if not self.bridge_name:
            return {}

        try:
            stats = {
                'bridge_name': self.bridge_name,
                'interface_count': len(self.bridge_interfaces),
                'interfaces': self.bridge_interfaces.copy(),
                'mac_table': self._get_mac_table(),
                'bridge_info': self._get_bridge_info()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting bridge stats: {e}")
            return {}

    def _get_mac_table(self) -> List[Dict[str, str]]:
        """Get bridge MAC address table"""
        if not self.bridge_name:
            return []

        try:
            result = subprocess.run(['sudo', 'brctl', 'showmacs', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return []

            mac_entries = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header

            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    mac_entries.append({
                        'port': parts[0],
                        'mac': parts[1],
                        'local': parts[2],
                        'ageing': parts[3]
                    })

            return mac_entries
        except Exception as e:
            logger.error(f"Error getting MAC table: {e}")
            return []

    def _get_bridge_info(self) -> Dict[str, Any]:
        """Get detailed bridge information"""
        if not self.bridge_name:
            return {}

        try:
            result = subprocess.run(['sudo', 'brctl', 'show', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return {}

            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return {
                        'bridge': parts[0],
                        'id': parts[1],
                        'stp': parts[2],
                        'interfaces': parts[3:]
                    }
            return {}
        except Exception as e:
            logger.error(f"Error getting bridge info: {e}")
            return {}

    def get_bridge_status(self) -> Dict[str, Any]:
        """Get comprehensive bridge status"""
        if not self.bridge_name:
            return {'status': 'not_created'}

        try:
            # Check if bridge exists and is up
            result = subprocess.run(['ip', 'link', 'show', self.bridge_name],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                return {'status': 'not_found'}

            # Parse interface status
            status_line = result.stdout.strip().split('\n')[0]
            is_up = 'UP' in status_line and 'LOWER_UP' in status_line

            status = {
                'status': 'up' if is_up else 'down',
                'bridge_name': self.bridge_name,
                'interfaces': self.bridge_interfaces,
                'mac_table_size': len(self._get_mac_table()),
                'stp_enabled': self._get_stp_status(),
                'mtu': self._get_bridge_mtu()
            }

            return status
        except Exception as e:
            logger.error(f"Error getting bridge status: {e}")
            return {'status': 'error', 'error': str(e)}

    def _get_stp_status(self) -> bool:
        """Get STP status"""
        if not self.bridge_name:
            return False

        try:
            result = subprocess.run(['sudo', 'brctl', 'showstp', self.bridge_name],
                                  capture_output=True, text=True)
            return 'yes' in result.stdout.lower()
        except:
            return False

    def _get_bridge_mtu(self) -> int:
        """Get bridge MTU"""
        if not self.bridge_name:
            return 1500

        try:
            result = subprocess.run(['ip', 'link', 'show', self.bridge_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Extract MTU from output like: "... mtu 1500 ..."
                match = re.search(r'mtu (\d+)', result.stdout)
                if match:
                    return int(match.group(1))
            return 1500
        except:
            return 1500

    def configure_vlan(self, interface: str, vlan_id: int, tagged: bool = False) -> bool:
        """Configure VLAN on an interface (if supported)"""
        try:
            logger.info(f"Configuring VLAN {vlan_id} on interface {interface}")

            # Note: Basic bridge utilities don't support VLAN tagging
            # For VLAN support, would need to use ip link commands or external tools
            logger.warning("VLAN configuration requires external tools (e.g., vconfig) or kernel 3.9+ with ip link")

            # For now, just log the configuration
            self.switch_ports[interface] = {
                'vlan_id': vlan_id,
                'tagged': tagged
            }

            return True
        except Exception as e:
            logger.error(f"Error configuring VLAN: {e}")
            return False

    def cleanup(self) -> bool:
        """Clean up the bridge and its resources"""
        try:
            if not self.bridge_name:
                return True

            logger.info(f"Cleaning up Linux bridge {self.bridge_name}")

            # Remove all interfaces from bridge
            for interface in self.bridge_interfaces[:]:  # Copy list to avoid modification during iteration
                self.remove_interface(interface)

            # Bring bridge down
            subprocess.run(['sudo', 'ip', 'link', 'set', self.bridge_name, 'down'],
                         capture_output=True, check=False)

            # Delete the bridge
            result = subprocess.run(['sudo', 'brctl', 'delbr', self.bridge_name],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Bridge {self.bridge_name} deleted successfully")
                self.bridge_name = None
                self.bridge_interfaces.clear()
                return True
            else:
                logger.error(f"Failed to delete bridge {self.bridge_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error cleaning up bridge: {e}")
            return False
