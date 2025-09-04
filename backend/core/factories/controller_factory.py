"""
Controller Factory for managing multiple SDN controllers
"""

import socket
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.logger import setup_logger
from ..controllers import (
    BaseControllerManager,
    RyuControllerManager,
    POXControllerManager,
    OsKenControllerManager,
    OpenDaylightControllerManager
)

logger = setup_logger(__name__)

class ControllerFactory:
    """Factory for managing multiple SDN controller types"""

    def __init__(self):
        self.controllers: Dict[str, BaseControllerManager] = {}
        self.active_controller: Optional[str] = None
        self.port_assignments: Dict[str, int] = {}
        self.controller_registry: Dict[str, type] = {
            'ryu': RyuControllerManager,
            'pox': POXControllerManager,
            'osken': OsKenControllerManager,
            'opendaylight': OpenDaylightControllerManager
        }

        # Initialize controller instances
        self._initialize_controllers()

    def _initialize_controllers(self):
        """Initialize all available controller managers"""
        for controller_type, controller_class in self.controller_registry.items():
            try:
                controller_instance = controller_class()
                self.controllers[controller_type] = controller_instance
                self.port_assignments[controller_type] = controller_instance.controller_port
                logger.info(f"Initialized {controller_type} controller manager")
            except Exception as e:
                logger.error(f"Failed to initialize {controller_type} controller: {e}")

    def get_available_controllers(self) -> List[str]:
        """Get list of available controller types"""
        return list(self.controller_registry.keys())

    def get_controller_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all controllers"""
        info = {}
        for controller_type, controller in self.controllers.items():
            info[controller_type] = {
                'name': controller.name,
                'running': controller.is_running,
                'port': controller.controller_port,
                'current_app': controller.controller_type if controller.is_running else None,
                'available_apps': self._get_available_apps(controller_type),
                'status': controller.get_status()
            }
        return info

    def _get_available_apps(self, controller_type: str) -> List[str]:
        """Get available applications for a controller type"""
        if controller_type in self.controllers:
            controller = self.controllers[controller_type]
            if hasattr(controller, 'get_available_apps'):
                return controller.get_available_apps()
        return []

    def start_controller(self, controller_type: str, app: str = 'default',
                        port: Optional[int] = None, custom_args: Optional[Any] = None) -> bool:
        """Start a specific controller type"""
        if controller_type not in self.controllers:
            logger.error(f"Unknown controller type: {controller_type}")
            return False

        # Stop currently active controller if different
        if self.active_controller and self.active_controller != controller_type:
            self.stop_controller(self.active_controller)

        controller = self.controllers[controller_type]

        # Use assigned port or specified port
        if port is None:
            port = self.port_assignments.get(controller_type, 6633)

        # Check for port conflicts
        if not self._check_port_availability(port):
            logger.error(f"Port {port} is already in use")
            return False

        # Update port assignment
        self.port_assignments[controller_type] = port
        controller.controller_port = port

        # Start the controller
        success = controller.start_controller(app, port, custom_args)
        if success:
            self.active_controller = controller_type
            logger.info(f"Started {controller_type} controller on port {port} with app {app}")
        else:
            logger.error(f"Failed to start {controller_type} controller")

        return success

    def stop_controller(self, controller_type: Optional[str] = None) -> bool:
        """Stop a specific controller or the active one"""
        if controller_type is None:
            controller_type = self.active_controller

        if not controller_type or controller_type not in self.controllers:
            logger.error(f"Controller type not found: {controller_type}")
            return False

        controller = self.controllers[controller_type]
        success = controller.stop_controller()

        if success:
            if self.active_controller == controller_type:
                self.active_controller = None
            logger.info(f"Stopped {controller_type} controller")
        else:
            logger.error(f"Failed to stop {controller_type} controller")

        return success

    def restart_controller(self, controller_type: Optional[str] = None,
                          app: Optional[str] = None, port: Optional[int] = None) -> bool:
        """Restart a specific controller or the active one"""
        if controller_type is None:
            controller_type = self.active_controller

        if not controller_type or controller_type not in self.controllers:
            logger.error(f"Controller type not found: {controller_type}")
            return False

        controller = self.controllers[controller_type]

        # Use current app if not specified
        if app is None:
            app = controller.controller_type

        # Use current port if not specified
        if port is None:
            port = controller.controller_port

        logger.info(f"Restarting {controller_type} controller...")
        return self.start_controller(controller_type, app, port)

    def switch_controller(self, controller_type: str, app: str = 'default',
                         port: Optional[int] = None) -> bool:
        """Switch from current controller to another without recreating topology"""
        logger.info(f"Switching from {self.active_controller} to {controller_type}")
        return self.start_controller(controller_type, app, port)

    def get_active_controller(self) -> Optional[str]:
        """Get the currently active controller type"""
        return self.active_controller

    def get_controller_status(self, controller_type: Optional[str] = None) -> Dict[str, Any]:
        """Get status of a specific controller or the active one"""
        if controller_type is None:
            controller_type = self.active_controller

        if not controller_type or controller_type not in self.controllers:
            return {'running': False, 'error': 'Controller not found'}

        controller = self.controllers[controller_type]
        status = controller.get_status()
        status['controller_framework'] = controller_type
        return status

    def get_controller_logs(self, controller_type: Optional[str] = None,
                           lines: int = 100) -> Dict[str, Any]:
        """Get logs from a specific controller or the active one"""
        if controller_type is None:
            controller_type = self.active_controller

        if not controller_type or controller_type not in self.controllers:
            return {'logs': [], 'error': 'Controller not found'}

        return self.controllers[controller_type].get_logs(lines)

    def get_controller_stats(self, controller_type: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics from a specific controller or the active one"""
        if controller_type is None:
            controller_type = self.active_controller

        if not controller_type or controller_type not in self.controllers:
            return {}

        return self.controllers[controller_type].get_controller_stats()

    def assign_controller_port(self, controller_type: str, port: int) -> bool:
        """Assign a specific port to a controller type"""
        if controller_type not in self.controllers:
            logger.error(f"Unknown controller type: {controller_type}")
            return False

        if not self._check_port_availability(port):
            logger.error(f"Port {port} is already in use")
            return False

        self.port_assignments[controller_type] = port
        self.controllers[controller_type].controller_port = port
        logger.info(f"Assigned port {port} to {controller_type} controller")
        return True

    def _check_port_availability(self, port: int) -> bool:
        """Check if a port is available"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result != 0  # Port is available if connection fails
        except:
            return False

    def benchmark_controllers(self, controllers: List[str], app: str = 'default',
                             duration: int = 30) -> Dict[str, Any]:
        """Benchmark multiple controllers for comparison"""
        results = {}

        for controller_type in controllers:
            if controller_type not in self.controllers:
                results[controller_type] = {'error': 'Controller not available'}
                continue

            logger.info(f"Benchmarking {controller_type} controller...")

            # Start controller
            start_time = datetime.now()
            if not self.start_controller(controller_type, app):
                results[controller_type] = {'error': 'Failed to start'}
                continue

            # Wait for it to stabilize
            import time
            time.sleep(5)

            # Collect initial stats
            initial_stats = self.get_controller_stats(controller_type)

            # Wait for benchmark duration
            time.sleep(duration)

            # Collect final stats
            final_stats = self.get_controller_stats(controller_type)
            end_time = datetime.now()

            # Calculate metrics
            results[controller_type] = {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration': duration,
                'initial_stats': initial_stats,
                'final_stats': final_stats,
                'uptime': (end_time - start_time).total_seconds()
            }

            # Stop controller
            self.stop_controller(controller_type)

        return results

    def install_controller(self, controller_type: str) -> bool:
        """Install a specific controller if supported"""
        if controller_type not in self.controllers:
            logger.error(f"Unknown controller type: {controller_type}")
            return False

        controller = self.controllers[controller_type]

        if hasattr(controller, 'install_pox'):  # POX specific
            return controller.install_pox()
        elif hasattr(controller, 'install_opendaylight'):  # OpenDaylight specific
            return controller.install_opendaylight()
        elif hasattr(controller, 'check_installation'):
            # For other controllers, just check if they're installed
            installed = controller.check_installation()
            if not installed:
                logger.warning(f"{controller_type} is not installed. Please install manually:")
                if controller_type in ['ryu', 'osken']:
                    logger.warning("  pip install ryu")
                elif controller_type == 'pox':
                    logger.warning("  git clone https://github.com/noxrepo/pox.git ~/pox")
                elif controller_type == 'opendaylight':
                    logger.warning("  Run: python install_controllers.py")
            return installed
        else:
            logger.info(f"No installation method available for {controller_type}")
            return True

    def get_controller_capabilities(self, controller_type: str) -> Dict[str, Any]:
        """Get capabilities of a specific controller"""
        if controller_type not in self.controllers:
            return {}

        controller = self.controllers[controller_type]

        capabilities = {
            'name': controller.name,
            'supported_apps': self._get_available_apps(controller_type),
            'supports_installation': hasattr(controller, 'install_pox') or hasattr(controller, 'check_installation'),
            'supports_custom_apps': hasattr(controller, 'set_custom_app'),
            'default_port': controller.controller_port
        }

        return capabilities

    def cleanup(self):
        """Cleanup all controllers"""
        for controller_type in list(self.controllers.keys()):
            try:
                self.stop_controller(controller_type)
            except Exception as e:
                logger.error(f"Error stopping {controller_type}: {e}")

        self.active_controller = None
        logger.info("Controller factory cleanup completed")
