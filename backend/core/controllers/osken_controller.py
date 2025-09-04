"""
Enhanced os-ken Controller Manager (Ryu official replacement)
"""

import os
import sys
import subprocess

from utils.logger import setup_logger
from .base_controller import BaseControllerManager

logger = setup_logger(__name__)

class OsKenControllerManager(BaseControllerManager):
    """Enhanced os-ken controller manager (official Ryu replacement)"""

    def __init__(self):
        super().__init__('os-ken', default_port=6633)
        self.controller_app = 'simple_switch_13'

        # os-ken application mappings (compatible with Ryu apps)
        self.osken_apps = {
            'simple_switch_13': 'ryu.app.simple_switch_13',
            'simple_switch': 'ryu.app.simple_switch',
            'l2_switch': 'ryu.app.simple_switch',
            'simple_switch_rest_13': 'ryu.app.simple_switch_rest_13',
            'simple_switch_rest': 'ryu.app.simple_switch_rest',
            'rest_conf_switch': 'ryu.app.rest_conf_switch',
            'rest_router': 'ryu.app.rest_router',
            'rest_topology': 'ryu.app.rest_topology',
            'ofctl_rest': 'ryu.app.ofctl_rest',
            'gui_topology': 'ryu.app.gui_topology',
            'qos_simple_switch_13': 'ryu.app.qos_simple_switch_13',
            'simple_monitor_13': 'ryu.app.simple_monitor_13',
            'ospf_router': 'ryu.app.ospf_router',
            'bgp_router': 'ryu.app.bgp_router'
        }

    def check_installation(self):
        """Check if os-ken is properly installed"""
        try:
            # Test basic ryu import without eventlet dependencies
            result = subprocess.run([
                self.python_exe, '-c',
                '''
import warnings
warnings.filterwarnings("ignore")
try:
    import ryu.cmd.manager
    import ryu.app.simple_switch_13
    print("os-ken OK")
except Exception as e:
    print(f"os-ken import error: {e}")
    exit(1)
'''
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                logger.info(f"os-ken installation verified with {self.python_exe}")
                return True
            else:
                logger.warning(f"os-ken import test failed: {result.stderr}")
                # Try alternative check
                return self._alternative_installation_check()
        except Exception as e:
            logger.warning(f"Could not verify os-ken installation: {e}")
            return self._alternative_installation_check()

    def _alternative_installation_check(self):
        """Alternative installation check that's more lenient"""
        try:
            # Check if ryu-manager command exists
            ryu_manager = self._find_ryu_manager()
            if ryu_manager:
                logger.info(f"Found ryu-manager at: {ryu_manager}")
                return True
            
            # Check if we can import ryu at all
            result = subprocess.run([
                self.python_exe, '-c', 'import ryu; print("ryu module found")'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info("ryu module found, assuming os-ken is available")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Alternative installation check failed: {e}")
            return False

    def get_controller_command(self, app, port, custom_args=None):
        """Get the command to start os-ken controller"""
        # os-ken uses the same ryu-manager command
        ryu_manager_cmd = self._find_ryu_manager()
        if ryu_manager_cmd:
            cmd = [
                ryu_manager_cmd,
                self.osken_apps.get(app, f'ryu.app.{app}'),
                '--ofp-tcp-listen-port', str(port),
                '--verbose'
            ]
            if custom_args:
                if isinstance(custom_args, str):
                    cmd.extend(custom_args.split())
                elif isinstance(custom_args, list):
                    cmd.extend(custom_args)
            return cmd

        # Fallback to Python script approach
        logger.info("Falling back to Python script approach")
        ryu_script = self._create_ryu_script(app, port)
        if ryu_script:
            return [self.python_exe, ryu_script]

        return None

    def _find_ryu_manager(self):
        """Find ryu-manager command (os-ken uses the same command)"""
        ryu_manager_paths = [
            '/home/ege/anaconda3/envs/sdn-mininet/bin/ryu-manager',
            f'{os.environ.get("CONDA_PREFIX", "")}/bin/ryu-manager' if os.environ.get("CONDA_PREFIX") else None,
        ]

        for path in ryu_manager_paths:
            if path and os.path.exists(path):
                return path

        # Check system PATH
        result = subprocess.run(['which', 'ryu-manager'], capture_output=True)
        if result.returncode == 0:
            return 'ryu-manager'

        return None

    def _create_ryu_script(self, controller_type, port):
        """Create a temporary Ryu/os-ken startup script with eventlet workaround"""
        script_content = f'''#!/usr/bin/env python3
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

# Workaround for eventlet compatibility issues with Python 3.10+
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Try to patch eventlet for compatibility, but don't fail if it doesn't work
try:
    # Skip eventlet import entirely to avoid compatibility issues
    # os-ken can work without eventlet for basic functionality
    pass
except Exception as e:
    print(f"Eventlet patch warning: {{e}}", file=sys.stderr)

# Import and run Ryu/os-ken
try:
    from ryu.cmd import manager
    sys.argv = [
        'ryu-manager',
        'ryu.app.{controller_type}',
        '--ofp-tcp-listen-port', str({port}),
        '--verbose',
        '--no-color'
    ]
    print(f"Starting os-ken with: {{' '.join(sys.argv)}}", file=sys.stderr)
    manager.main()
except ImportError as e:
    print(f"os-ken import error: {{e}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"os-ken controller error: {{e}}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

        script_path = '/tmp/osken_controller.py'
        try:
            with open(script_path, 'w') as f:
                f.write(script_content.format(controller_type=controller_type, port=port))

            os.chmod(script_path, 0o755)
            return script_path
        except Exception as e:
            logger.error(f"Failed to create os-ken script: {e}")
            return None

    def _get_environment(self):
        """Get environment variables for os-ken process (override base class)"""
        env = super()._get_environment()
        env['RYU_LOG_LEVEL'] = 'INFO'
        return env

    def start_controller(self, app='simple_switch_13', port=6633, custom_args=None):
        """Start os-ken controller (override base class for os-ken-specific logic)"""
        return super().start_controller(app, port, custom_args)

    def get_available_apps(self):
        """Get list of available os-ken applications"""
        return list(self.osken_apps.keys())

    def set_custom_app(self, app_name, app_module):
        """Add a custom os-ken application"""
        self.osken_apps[app_name] = app_module
        logger.info(f"Added custom os-ken app: {app_name} -> {app_module}")
