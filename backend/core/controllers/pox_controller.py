"""
Enhanced POX Controller Manager with full web API control
"""

import os
import subprocess
import shutil

from utils.logger import setup_logger
from .base_controller import BaseControllerManager

logger = setup_logger(__name__)

class POXControllerManager(BaseControllerManager):
    """Enhanced POX controller manager with complete web API control"""

    def __init__(self):
        super().__init__('POX', default_port=6633)
        self.controller_app = 'l2_learning'
        # Try multiple possible POX installation paths
        possible_paths = [
            os.path.expanduser('~/pox'),  # User home directory
            '/opt/pox',                   # Docker installation path
            '/root/pox',                  # Root user home
            '/home/root/pox',             # Docker symlink location
        ]
        self.pox_path = None
        for path in possible_paths:
            if os.path.exists(path):
                self.pox_path = path
                break
        
        # If no existing installation found, default to user home
        if self.pox_path is None:
            self.pox_path = os.path.expanduser('~/pox')
        
        logger.info(f"POX controller initialized with path: {self.pox_path}")

        # POX application mappings
        self.pox_apps = {
            'l2_learning': 'forwarding.l2_learning',
            'l2_switch': 'forwarding.l2_learning',  # Map to closest equivalent
            'hub': 'forwarding.hub',
            'firewall': 'misc.firewall',
            'l3_learning': 'forwarding.l3_learning',
            'spanning_tree': 'openflow.spanning_tree',
            'discovery': 'openflow.discovery',
            'topology': 'misc.topology',
            # Map Ryu/osken app names to POX equivalents
            'simple_switch_13': 'forwarding.l2_learning',
            'simple_switch': 'forwarding.l2_learning',
            'learning_switch': 'forwarding.l2_learning'
        }

    def check_installation(self):
        """Check if POX is properly installed"""
        try:
            if not os.path.exists(self.pox_path):
                logger.warning(f"POX not found at {self.pox_path}")
                return False

            pox_py = os.path.join(self.pox_path, 'pox.py')
            if not os.path.exists(pox_py):
                logger.warning(f"pox.py not found at {pox_py}")
                return False

            # Test if POX can be executed
            result = subprocess.run([
                self.python_exe, pox_py, '--help'
            ], capture_output=True, text=True, timeout=10, cwd=self.pox_path)

            if result.returncode == 0:
                logger.info(f"POX installation verified at {self.pox_path}")
                return True
            else:
                logger.error(f"POX test failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Could not verify POX installation: {e}")
            return False

    def install_pox(self):
        """Install POX from GitHub if not present"""
        try:
            if self.check_installation():
                logger.info("POX already installed")
                return True

            logger.info("Installing POX from GitHub...")

            # Remove existing directory if it exists but is incomplete
            if os.path.exists(self.pox_path):
                shutil.rmtree(self.pox_path)

            # Clone POX from GitHub
            result = subprocess.run([
                'git', 'clone', 'https://github.com/noxrepo/pox.git', self.pox_path
            ], capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                logger.error(f"Failed to clone POX: {result.stderr}")
                return False

            # Verify installation
            if self.check_installation():
                logger.info("POX installed successfully")
                return True
            else:
                logger.error("POX installation verification failed")
                return False

        except Exception as e:
            logger.error(f"Error installing POX: {e}")
            return False

    def get_controller_command(self, app, port, custom_args=None):
        """Get the command to start POX controller"""
        # Ensure POX is installed
        if not self.check_installation():
            logger.info("POX not found, attempting to install...")
            if not self.install_pox():
                logger.error("Failed to install POX")
                return None

        # Build POX command
        pox_py = os.path.join(self.pox_path, 'pox.py')
        cmd = [self.python_exe, pox_py]

        # Add log level
        cmd.extend(['log.level', '--DEBUG'])

        # Add OpenFlow listener port
        cmd.extend(['openflow.of_01', f'--port={port}'])

        # Add the application
        pox_app = self.pox_apps.get(app, app)
        cmd.append(pox_app)

        # Add custom arguments if provided
        if custom_args:
            if isinstance(custom_args, str):
                cmd.extend(custom_args.split())
            elif isinstance(custom_args, list):
                cmd.extend(custom_args)

        return cmd

    def _get_environment(self):
        """Get environment variables for POX process (override base class)"""
        env = super()._get_environment()

        # Add POX path to PYTHONPATH
        pythonpath = env.get('PYTHONPATH', '')
        if pythonpath:
            env['PYTHONPATH'] = f"{self.pox_path}:{pythonpath}"
        else:
            env['PYTHONPATH'] = self.pox_path

        # Set POX log level
        env['POX_LOG_LEVEL'] = 'DEBUG'

        return env

    def start_controller(self, app='l2_learning', port=6633, custom_args=None):
        """Start POX controller (override base class for POX-specific logic)"""
        return super().start_controller(app, port, custom_args)

    def get_available_apps(self):
        """Get list of available POX applications"""
        return list(self.pox_apps.keys())

    def set_custom_app(self, app_name, app_module):
        """Add a custom POX application"""
        self.pox_apps[app_name] = app_module
        logger.info(f"Added custom POX app: {app_name} -> {app_module}")