"""
Enhanced Ryu Controller Manager with full web API control
"""

import os
import sys
import subprocess
from datetime import datetime

from utils.logger import setup_logger
from .base_controller import BaseControllerManager

logger = setup_logger(__name__)

class RyuControllerManager(BaseControllerManager):
    """Enhanced Ryu controller manager with complete web API control"""

    def __init__(self):
        super().__init__('Ryu', default_port=6633)
        self.controller_type = 'simple_switch_13'
        self.ryu_process = None  # Keep reference for Ryu-specific methods

    def check_installation(self):
        """Check if Ryu is properly installed"""
        try:
            result = subprocess.run([
                self.python_exe, '-c',
                'import ryu.cmd.manager; import ryu.app.simple_switch_13; print("Ryu OK")'
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                logger.info(f"Ryu installation verified with {self.python_exe}")
                return True
            else:
                logger.error(f"Ryu import test failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Could not verify Ryu installation: {e}")
            return False

    def get_controller_command(self, app, port, custom_args=None):
        """Get the command to start Ryu controller"""
        # Try direct ryu-manager command first
        ryu_manager_cmd = self._find_ryu_manager()
        if ryu_manager_cmd:
            cmd = [
                ryu_manager_cmd,
                f'ryu.app.{app}',
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
        """Find ryu-manager command"""
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
        """Create a temporary Ryu startup script"""
        script_content = f'''#!/usr/bin/env python3
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

# Patch eventlet for compatibility
try:
    import eventlet.wsgi
    if not hasattr(eventlet.wsgi, 'ALREADY_HANDLED'):
        eventlet.wsgi.ALREADY_HANDLED = object()
except:
    pass

# Import and run Ryu
try:
    from ryu.cmd import manager
    sys.argv = [
        'ryu-manager',
        'ryu.app.{controller_type}',
        '--ofp-tcp-listen-port', str({port}),
        '--verbose'
    ]
    print(f"Starting Ryu with: {{' '.join(sys.argv)}}", file=sys.stderr)
    manager.main()
except ImportError as e:
    print(f"Ryu import error: {{e}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Ryu controller error: {{e}}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

        script_path = '/tmp/ryu_controller.py'
        try:
            with open(script_path, 'w') as f:
                f.write(script_content.format(controller_type=controller_type, port=port))

            os.chmod(script_path, 0o755)
            return script_path
        except Exception as e:
            logger.error(f"Failed to create Ryu script: {e}")
            return None

    def _get_environment(self):
        """Get environment variables for Ryu process (override base class)"""
        env = super()._get_environment()
        env['RYU_LOG_LEVEL'] = 'INFO'
        return env

    def start_controller(self, app='simple_switch_13', port=6633, custom_args=None):
        """Start Ryu controller (override base class for Ryu-specific logic)"""
        return super().start_controller(app, port, custom_args)

    def stop_controller(self):
        """Stop Ryu controller (override base class for cleanup)"""
        result = super().stop_controller()
        self.ryu_process = None

        # Clean up temporary script
        try:
            os.remove('/tmp/ryu_controller.py')
        except:
            pass

        return result

    def _monitor_startup(self):
        """Monitor Ryu startup and set ryu_process reference"""
        result = super()._monitor_startup()
        if result and self.is_running:
            self.ryu_process = self.process
        return result