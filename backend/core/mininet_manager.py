"""
Mininet Manager (Refactored)
Main orchestration class that coordinates all Mininet components
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from mininet.net import Mininet
from mininet.cli import CLI

from utils.logger import setup_logger
from .factories.controller_factory import ControllerFactory
from .switches.switch_factory import SwitchFactory
from .managers.network_topology_manager import NetworkTopologyManager
from .managers.network_monitor import NetworkMonitor
from .managers.configuration_manager import ConfigurationManager
from .managers.snapshot_manager import SnapshotManager
from .managers.flow_manager import FlowManager
from .stats_collector import NetworkStatsCollector
from .router import Router

# Import our new modular components
from .managers.topology.topology_builder import TopologyBuilder
from .managers.network.network_diagnostics import NetworkDiagnostics
from .managers.devices.device_manager import DeviceManager
from .managers.configuration.configuration_tracker import ConfigurationTracker

logger = setup_logger(__name__)


class MininetManager:
    """Main orchestration class for Mininet network management"""

    def __init__(self):
        self.net = None
        self.is_running = False
        self.logger = logger

        # Initialize core factories and managers
        self.controller_factory = ControllerFactory()
        self.switch_factory = SwitchFactory()
        self.stats_collector = NetworkStatsCollector()

        # Initialize existing managers
        self.topology_manager = NetworkTopologyManager(self.controller_factory, self.switch_factory)
        self.network_monitor = NetworkMonitor(self.stats_collector)
        self.config_manager = ConfigurationManager()
        self.snapshot_manager = SnapshotManager(self.config_manager)
        self.flow_manager = FlowManager()

        # Initialize new modular components
        self.topology_builder = TopologyBuilder()
        self.network_diagnostics = NetworkDiagnostics()
        self.device_manager = DeviceManager()
        self.config_tracker = ConfigurationTracker()

        # Initialize topology data for backward compatibility
        self.topology_data = {
            'nodes': [],
            'links': [],
            'controllers': [],
            'stats': {}
        }

        # Legacy properties for backward compatibility
        self.node_positions = {}
        self.controller_config = []

    @property
    def ryu_controller(self):
        """Get active controller for backward compatibility"""
        active_controller_name = self.controller_factory.get_active_controller()
        if active_controller_name and active_controller_name in self.controller_factory.controllers:
            return self.controller_factory.controllers[active_controller_name]
        return None

    # ================================
    # Network Lifecycle Management
    # ================================

    def create_simple_topology(self) -> bool:
        """Create the default network topology"""
        net, success = self.topology_builder.create_simple_topology()
        if success and net:
            self.net = net
            self.is_running = True
            self._update_topology_data()
            return True
        return False

    def create_custom_topology(self, topology_config: Dict[str, Any],
                              controller_type: Optional[str] = None,
                              controller_app: Optional[str] = None,
                              controller_port: Optional[int] = None,
                              switch_type: str = 'ovs') -> bool:
        """Create custom topology from configuration"""
        net, success = self.topology_manager.create_custom_topology(
            topology_config, controller_type, controller_app, controller_port, switch_type
        )
        if success and net:
            self.net = net
            self.is_running = True
            self._update_topology_data()
            return True
        return False

    def create_predefined_topology(self, topology_config: Dict[str, Any]) -> bool:
        """Create predefined topology types"""
        net, success = self.topology_builder.create_predefined_topology(topology_config)
        if success and net:
            self.net = net
            self.is_running = True
            self._update_topology_data()
            return True
        return False

    def start_network(self) -> bool:
        """Start the network with proper initialization"""
        try:
            if not self.net:
                self.logger.error("No network to start. Create topology first.")
                return False

            self.logger.info("Starting Mininet network...")

            # Start the network
            self.net.start()
            self.is_running = True

            # Wait a moment for network to initialize
            import time
            time.sleep(2)

            # Update topology data
            self._update_topology_data()

            # Ensure controllers are running
            if hasattr(self.net, 'controllers') and self.net.controllers:
                running_controllers = 0
                for controller in self.net.controllers:
                    if hasattr(controller, 'is_running') and controller.is_running:
                        running_controllers += 1

                self.logger.info(f"Network started with {running_controllers} controllers running")

                # If no controllers are running, the network will operate as learning switches
                if running_controllers == 0:
                    self.logger.warning("No controllers running - network will operate as learning bridges")
            else:
                self.logger.info("Network started without controllers - switches will operate as learning bridges")

            # Wait a bit more for switches to learn MAC addresses
            time.sleep(3)

            self.logger.info("Network started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error starting network: {e}")
            # Try to clean up if start failed
            try:
                if self.net:
                    self.net.stop()
                self.is_running = False
            except:
                pass
            return False

    def stop_network(self) -> bool:
        """Stop the network with proper cleanup"""
        try:
            if self.net:
                self.logger.info("Stopping Mininet network...")
                
                # Stop the network first
                self.net.stop()
                self.is_running = False
                
                # Clean up network object
                self.net = None
                
                # Force cleanup of any remaining processes
                import os
                os.system('mn -c > /dev/null 2>&1')
                
                # Stop all controllers
                try:
                    self.controller_factory.cleanup()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up controllers: {e}")

                # Stop all switches
                try:
                    self.switch_factory.cleanup_switches()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up switches: {e}")

                # Clear device manager
                try:
                    self.device_manager.cleanup()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up devices: {e}")

                self.logger.info("Network stopped and cleaned up successfully")
            else:
                # Even if no network, ensure cleanup
                import os
                os.system('mn -c > /dev/null 2>&1')
                self.is_running = False
                
            return True
        except Exception as e:
            self.logger.error(f"Error stopping network: {e}")
            # Force cleanup even if there were errors
            try:
                import os
                os.system('mn -c > /dev/null 2>&1')
                self.net = None
                self.is_running = False
                self.logger.info("Forced network cleanup after error")
            except:
                pass
            return False

    def delete_network(self) -> bool:
        """Delete the network topology completely (clear all data)"""
        try:
            self.logger.info("Deleting network topology...")
            
            # Stop network if running
            if self.is_running:
                self.stop_network()
            
            # Clear all topology data
            self.topology_data = {
                'nodes': [],
                'links': [],
                'controllers': [],
                'stats': {}
            }
            
            # Clear topology manager data
            if hasattr(self, 'topology_manager'):
                self.topology_manager.topology_data = {
                    'nodes': [],
                    'links': [],
                    'controllers': [],
                    'stats': {}
                }
                self.topology_manager.controller_config = []
                self.topology_manager.custom_configs = {}
                self.topology_manager.node_types = {}
                self.topology_manager.node_positions = {}
                self.topology_manager.controller_links = set()
            
            # Clear configuration tracker
            if hasattr(self, 'config_tracker'):
                self.config_tracker.applied_configurations = {
                    'device_configs': {},
                    'terminal_commands': {},
                    'api_operations': [],
                    'routing_configs': {},
                    'firewall_configs': {},
                    'interface_configs': {},
                    'service_configs': {}
                }
            
            # Force cleanup of any remaining processes
            import os
            os.system('mn -c > /dev/null 2>&1')
            
            self.logger.info("Network topology deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting network: {e}")
            return False

    # ================================
    # Controller Management
    # ================================

    def start_controller(self, controller_type: str = 'ryu', app: str = 'simple_switch_13',
                        port: Optional[int] = None, custom_args: Optional[Any] = None) -> bool:
        """Start a controller"""
        return self.controller_factory.start_controller(controller_type, app, port, custom_args)

    def stop_controller(self, controller_type: Optional[str] = None) -> bool:
        """Stop a controller"""
        return self.controller_factory.stop_controller(controller_type)

    def restart_controller(self, controller_type: Optional[str] = None,
                          app: Optional[str] = None, port: Optional[int] = None) -> bool:
        """Restart a controller"""
        return self.controller_factory.restart_controller(controller_type, app, port)

    def get_controller_status(self, controller_type: Optional[str] = None) -> Dict[str, Any]:
        """Get controller status"""
        return self.controller_factory.get_controller_status(controller_type)

    def get_controller_logs(self, controller_type: Optional[str] = None,
                           lines: int = 100) -> Dict[str, Any]:
        """Get controller logs"""
        return self.controller_factory.get_controller_logs(controller_type, lines)

    def get_available_controllers(self) -> List[str]:
        """Get available controller types"""
        return self.controller_factory.get_available_controllers()

    # ================================
    # Switch Management
    # ================================

    def get_available_switches(self) -> List[str]:
        """Get available switch types"""
        return self.switch_factory.get_available_switches()

    def get_switch_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all switches"""
        return self.switch_factory.get_switch_info()

    def get_switch_status(self, switch_type: Optional[str] = None,
                         switch_id: Optional[str] = None) -> Dict[str, Any]:
        """Get switch status"""
        return self.switch_factory.get_switch_status(switch_type, switch_id)

    def get_switch_stats(self, switch_type: Optional[str] = None,
                        switch_id: Optional[str] = None) -> Dict[str, Any]:
        """Get switch statistics"""
        return self.switch_factory.get_switch_stats(switch_type, switch_id)

    # ================================
    # Device Management
    # ================================

    def add_node(self, node_id: str, node_type: str = 'host', **kwargs) -> Dict[str, Any]:
        """Add a node to running topology"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        logger.info(f"Adding node: {node_id}, type: {node_type}, kwargs: {kwargs}")
        node = self.device_manager.add_node(self.net, node_id, node_type, **kwargs)
        logger.info(f"Node addition result: {node}")
        success = node is not None

        if success:
            logger.info(f"Node {node_id} added successfully, updating topology data")
            self._update_topology_data()
            # Track the operation
            self.config_tracker.track_api_operation(
                'add_node',
                {'node_id': node_id, 'node_type': node_type, **kwargs},
                {'success': True}
            )

        return {'success': success, 'node': node}

    def remove_node(self, node_id: str) -> Dict[str, Any]:
        """Remove a node from running topology"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        success = self.device_manager.remove_node(self.net, node_id)

        if success:
            self._update_topology_data()
            # Track the operation
            self.config_tracker.track_api_operation(
                'remove_node',
                {'node_id': node_id},
                {'success': True}
            )

        return {'success': success}

    def add_link(self, source_id: str, target_id: str, **kwargs) -> Dict[str, Any]:
        """Add a link between two nodes"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        success = self.device_manager.add_link(self.net, source_id, target_id, **kwargs)

        if success:
            self._update_topology_data()
            # Track controller-link explicitly to avoid duplicate inferred links
            try:
                if hasattr(self.topology_manager, 'controller_links'):
                    if source_id.startswith('c') and any(n.get('id') == target_id and n.get('type') == 'switch' for n in self.topology_data.get('nodes', [])):
                        self.topology_manager.controller_links.add((source_id, target_id))
                    if target_id.startswith('c') and any(n.get('id') == source_id and n.get('type') == 'switch' for n in self.topology_data.get('nodes', [])):
                        self.topology_manager.controller_links.add((target_id, source_id))
            except Exception:
                pass
            # Track the operation
            self.config_tracker.track_api_operation(
                'add_link',
                {'source_id': source_id, 'target_id': target_id, **kwargs},
                {'success': True}
            )

        return {'success': success}

    def remove_link(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """Remove link between two nodes"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        success = self.device_manager.remove_link(self.net, source_id, target_id)

        if success:
            self._update_topology_data()
            # Track the operation
            self.config_tracker.track_api_operation(
                'remove_link',
                {'source_id': source_id, 'target_id': target_id},
                {'success': True}
            )

        return {'success': success}

    def update_node_ip(self, node_id: str, new_ip: str, interface: Optional[str] = None) -> Dict[str, Any]:
        """Update IP address of a node"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        result = self.device_manager.update_node_ip(self.net, node_id, new_ip, interface)

        if result.get('success'):
            self._update_topology_data()
            # Track the operation
            self.config_tracker.track_api_operation(
                'update_node_ip',
                {'node_id': node_id, 'new_ip': new_ip, 'interface': interface},
                result
            )

        return result

    def update_link_bandwidth(self, source_id: str, target_id: str, new_bandwidth: Any) -> Dict[str, Any]:
        """Update bandwidth of a link"""
        if not self.net:
            return {'success': False, 'error': 'Network not initialized'}

        result = self.device_manager.update_link_bandwidth(self.net, source_id, target_id, new_bandwidth)

        if result.get('success'):
            # Track the operation
            self.config_tracker.track_api_operation(
                'update_link_bandwidth',
                {'source_id': source_id, 'target_id': target_id, 'new_bandwidth': new_bandwidth},
                result
            )

        return result

    def get_node_interfaces(self, node_id: str) -> Dict[str, Any]:
        """Get interface information for a specific node"""
        if not self.net:
            return {'error': 'Network not initialized'}

        return self.device_manager.get_node_interfaces(self.net, node_id)

    # ================================
    # Network Monitoring & Diagnostics
    # ================================

    def ping_test(self) -> Dict[str, Any]:
        """Run ping test between all hosts with better error handling"""
        if not self.net or not self.is_running:
            return {'error': 'Network not running', 'success': False}

        try:
            # Wait a moment for network to stabilize
            import time
            time.sleep(1)

            # Ensure controller is running if we have one
            if hasattr(self.net, 'controllers') and self.net.controllers:
                controller_running = any(hasattr(c, 'is_running') and c.is_running for c in self.net.controllers)
                if not controller_running:
                    self.logger.warning("Controller not running, ping test may fail")

            # Run the ping test
            result = self.network_diagnostics.ping_test(self.net)
            self.logger.info(f"Ping test result: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Error running ping test: {e}")
            return {'error': f'Ping test failed: {str(e)}', 'success': False}

    def execute_host_command(self, host_id: str, command: str) -> Dict[str, Any]:
        """Execute command on a specific host"""
        if not self.net or not self.is_running:
            return {'error': 'Network not running', 'success': False}

        result = self.network_diagnostics.execute_host_command(self.net, host_id, command)

        # Track the command
        self.config_tracker.track_terminal_command(
            host_id, command, result.get('result', ''), result.get('success', False)
        )

        return result

    def get_network_metrics(self) -> Dict[str, Any]:
        """Get real-time network metrics"""
        return self.network_monitor.get_network_metrics(self.net)

    def diagnose_connectivity_issues(self) -> Dict[str, Any]:
        """Diagnose connectivity issues in the network"""
        return self.network_diagnostics.diagnose_connectivity_issues(self.net, self.controller_factory)

    def get_flow_stats(self) -> Dict[str, Any]:
        """Get flow statistics from switches"""
        return self.flow_manager.get_flow_stats(self.net)

    # ================================
    # Configuration Tracking
    # ================================

    def track_device_configuration(self, device_name: str, config_type: str,
                                  config_data: Dict[str, Any], result: Optional[Dict[str, Any]] = None):
        """Track applied device configuration"""
        self.config_tracker.track_device_configuration(device_name, config_type, config_data, result)

    def track_terminal_command(self, device_name: str, command: str,
                              result: Optional[str] = None, success: bool = True):
        """Track terminal command executed on device"""
        self.config_tracker.track_terminal_command(device_name, command, result, success)

    def track_api_operation(self, operation_type: str, operation_data: Dict[str, Any],
                           result: Optional[Dict[str, Any]] = None):
        """Track API operation performed"""
        self.config_tracker.track_api_operation(operation_type, operation_data, result)

    def get_applied_configurations(self) -> Dict[str, Any]:
        """Get all tracked configurations"""
        return self.config_tracker.get_applied_configurations()

    def clear_configuration_tracking(self):
        """Clear all tracked configurations"""
        self.config_tracker.clear_configuration_tracking()

    # ================================
    # Topology Data Management
    # ================================

    def update_topology_data(self):
        """Update topology data including controller information"""
        self.topology_manager.update_topology_data(self.net)
        self.topology_data = self.topology_manager.topology_data
        
        # Critical logging - track controller data after update
        controllers = self.topology_data.get('controllers', [])
        logger.critical(f"TOPOLOGY DATA UPDATED: {len(controllers)} controllers in final topology_data")
        for controller in controllers:
            logger.critical(f"FINAL CONTROLLER: {controller.get('id')} - {controller.get('controller_type')}")

    def get_topology_data(self) -> Dict[str, Any]:
        """Get current topology data"""
        self.update_topology_data()
        return self.topology_data

    def set_topology_configuration(self, topology_config: Dict[str, Any]):
        """Set topology configuration for snapshots when network is not running"""
        try:
            # Get controllers from both nodes array and controllers array
            controllers_from_nodes = [node for node in topology_config.get('nodes', []) if node.get('type') == 'controller']
            controllers_from_controllers = topology_config.get('controllers', [])
            
            # Combine and remove duplicates based on controller ID
            combined_controllers = controllers_from_nodes + controllers_from_controllers
            all_controllers = []
            seen_ids = set()
            
            for controller in combined_controllers:
                controller_id = controller.get('id')
                if controller_id and controller_id not in seen_ids:
                    all_controllers.append(controller)
                    seen_ids.add(controller_id)
                elif controller_id:
                    logger.debug(f"Skipping duplicate controller: {controller_id}")
            
            logger.info(f"Processed {len(combined_controllers)} controllers, kept {len(all_controllers)} unique controllers")
            

            

            
            # Store topology data in topology manager
            self.topology_manager.topology_data = {
                'nodes': topology_config.get('nodes', []),
                'links': topology_config.get('links', []),
                'controllers': all_controllers,
                'stats': {}
            }
            
            # Critical logging - track when controllers are set
            if all_controllers:
                logger.critical(f"CONTROLLERS SET: {len(all_controllers)} controllers stored in topology_data")
                for controller in all_controllers:
                    logger.critical(f"CONTROLLER STORED: {controller.get('id')} - {controller.get('controller_type')}")
            else:
                logger.critical("CONTROLLERS SET: No controllers stored - this might be the issue!")
            

            
            # Store node positions
            self.topology_manager.node_positions = {}
            for node in topology_config.get('nodes', []):
                if node.get('id') and node.get('x') is not None and node.get('y') is not None:
                    self.topology_manager.node_positions[node['id']] = {'x': node['x'], 'y': node['y']}
            
            # Store controller config (use all controllers found)
            self.topology_manager.controller_config = all_controllers
            
            # Store custom configs for all nodes and controllers
            self.topology_manager.custom_configs = {}
            for node in topology_config.get('nodes', []):
                if node.get('id'):
                    self.topology_manager.custom_configs[node['id']] = node
            for controller in all_controllers:
                if controller.get('id'):
                    self.topology_manager.custom_configs[controller['id']] = controller
            
            # Store node types for controller/switch type information
            self.topology_manager.node_types = {}
            for node in topology_config.get('nodes', []):
                if node.get('id'):
                    node_types = {}
                    if node.get('type') == 'controller':
                        node_types['controller_type'] = node.get('controller_type', 'ryu')
                        node_types['app'] = node.get('app', 'simple_switch_13')
                    elif node.get('type') == 'switch':
                        node_types['switch_type'] = node.get('switch_type', 'ovs')
                        node_types['dpid'] = node.get('dpid', 'auto')
                    self.topology_manager.node_types[node['id']] = node_types
            
            # Also store controller types from controllers array
            for controller in all_controllers:
                if controller.get('id'):
                    node_types = {}
                    node_types['controller_type'] = controller.get('controller_type', 'ryu')
                    node_types['app'] = controller.get('app', 'simple_switch_13')
                    self.topology_manager.node_types[controller['id']] = node_types
            
            logger.info(f"Stored topology configuration with {len(topology_config.get('nodes', []))} nodes and {len(topology_config.get('links', []))} links")
            
        except Exception as e:
            logger.error(f"Error setting topology configuration: {e}")

    # ================================
    # Snapshot Management
    # ================================

    def create_simulation_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the current simulation state"""
        return self.snapshot_manager.create_simulation_snapshot(self.net, self.topology_data, self)

    def restore_simulation_snapshot(self, snapshot_data: Dict[str, Any]) -> bool:
        """Restore simulation from snapshot"""
        success = self.snapshot_manager.restore_simulation_snapshot(snapshot_data, self.net, self)
        if success:
            self.logger.info("Snapshot restoration completed successfully")
        return success

    # ================================
    # CLI and Utilities
    # ================================

    def start_cli(self):
        """Start Mininet CLI"""
        if self.net:
            logger.info("Starting CLI")
            CLI(self.net)

    # ================================
    # Private Helper Methods
    # ================================

    def _update_topology_data(self):
        """Update topology data from current network state"""
        if self.net:
            self.update_topology_data()

    # ================================
    # Legacy Methods for Backward Compatibility
    # ================================

    def parse_frontend_topology(self, frontend_topology: Dict[str, Any]) -> Dict[str, Any]:
        """Parse frontend topology format (legacy method)"""
        return self.topology_builder.parse_frontend_topology(frontend_topology)

    def _is_valid_mac(self, mac_address: str) -> bool:
        """Validate MAC address format (legacy method)"""
        return self.topology_builder.is_valid_mac(mac_address)

    def _is_valid_dpid(self, dpid: str) -> bool:
        """Validate DPID format (legacy method)"""
        return self.topology_builder.is_valid_dpid(dpid)

    def _parse_bandwidth(self, bw_string: Any) -> float:
        """Parse bandwidth string (legacy method)"""
        return self.topology_builder.parse_bandwidth(bw_string)

    def _print_topology_info(self):
        """Print topology information (legacy method)"""
        self.topology_builder._print_topology_info()

    # ================================
    # Legacy Controller Methods (Deprecated)
    # ================================

    def start_ryu_controller(self, app='simple_switch_13', port=None):
        """Start Ryu controller (deprecated: use start_controller)"""
        logger.warning("start_ryu_controller is deprecated. Use start_controller('ryu', app, port) instead")
        return self.start_controller('ryu', app, port)

    def stop_ryu_controller(self):
        """Stop Ryu controller (deprecated: use stop_controller)"""
        logger.warning("stop_ryu_controller is deprecated. Use stop_controller('ryu') instead")
        return self.stop_controller('ryu')

    def restart_ryu_controller(self, app=None, port=None):
        """Restart Ryu controller (deprecated: use restart_controller)"""
        logger.warning("restart_ryu_controller is deprecated. Use restart_controller('ryu', app, port) instead")
        if app is None:
            # Get current app from factory
            controller_info = self.controller_factory.get_controller_info().get('ryu', {})
            app = controller_info.get('current_app', 'simple_switch_13')
        return self.restart_controller('ryu', app, port)
