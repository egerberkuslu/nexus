"""
Base Controller Manager Class
Provides common interface and functionality for all SDN controllers
"""

import os
import time
import signal
import subprocess
import socket
from datetime import datetime
from collections import deque
from abc import ABC, abstractmethod

from utils.logger import setup_logger

logger = setup_logger(__name__)

class BaseControllerManager(ABC):
    """Base class for all SDN controller managers"""

    def __init__(self, name, default_port=6633):
        self.name = name
        self.controller_type = 'unknown'
        self.controller_port = default_port
        self.is_running = False
        self.start_time = None
        self.python_exe = self._get_python_executable()
        self.logs = deque(maxlen=1000)  # Store last 1000 log lines
        self.stats_data = {}
        self.process = None

    def _get_python_executable(self):
        """Get the correct Python executable"""
        # Check if we're in a conda environment
        conda_prefix = os.environ.get('CONDA_PREFIX')
        if conda_prefix:
            conda_python = os.path.join(conda_prefix, 'bin', 'python')
            if os.path.exists(conda_python):
                return conda_python

        # Check for conda environment in known locations
        possible_paths = [
            '/home/ege/anaconda3/envs/sdn-mininet/bin/python',
            '/home/ege/anaconda3/envs/sdn-mininet/bin/python3',
        ]

        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found Python at: {path}")
                return path

        # Default to system Python
        for python_cmd in ['python3', 'python2', 'python']:
            if subprocess.run(['which', python_cmd], capture_output=True).returncode == 0:
                return python_cmd

        return 'python3'

    @abstractmethod
    def check_installation(self):
        """Check if controller is properly installed"""
        pass

    @abstractmethod
    def get_controller_command(self, app, port, custom_args=None):
        """Get the command to start the controller"""
        pass

    def start_controller(self, app='default', port=6633, custom_args=None):
        """Start controller with enhanced monitoring"""
        try:
            # Check installation
            if not self.check_installation():
                logger.error(f"{self.name} is not properly installed")
                return False

            if self.is_running:
                logger.info(f"{self.name} controller already running, stopping first")
                self.stop_controller()

            self.controller_type = app
            self.controller_port = port
            self.start_time = datetime.now()
            self.logs.clear()

            logger.info(f"[BASE CONTROLLER UPDATED] Starting {self.name} controller: {app} on port {port}")

            # Get controller command
            cmd = self.get_controller_command(app, port, custom_args)
            if not cmd:
                return False

            logger.info(f"Starting {self.name} with command: {' '.join(cmd)}")

            # Start the process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                env=self._get_environment(),
                bufsize=1,
                universal_newlines=True
            )

            return self._monitor_startup()

        except Exception as e:
            logger.error(f"Error starting {self.name} controller: {e}")
            self.stop_controller()
            return False

    def _monitor_startup(self):
        """Monitor controller startup with real-time log capture"""
        try:
            startup_timeout = 15
            for i in range(startup_timeout):
                time.sleep(1)

                # Read any available output
                if self.process.stdout:
                    try:
                        import select
                        if select.select([self.process.stdout], [], [], 0)[0]:
                            line = self.process.stdout.readline()
                            if line:
                                self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
                    except:
                        pass

                # Check if process is still running
                if self.process.poll() is not None:
                    logger.error(f"[BASE CONTROLLER UPDATED] {self.name} process died during startup")
                    self._capture_final_output()
                    return False

                # Check if controller is listening
                if i >= 3 and self._verify_controller_running():
                    self.is_running = True
                    logger.info(f"{self.name} controller started successfully: {self.controller_type}")
                    return True

                if i % 3 == 0:
                    logger.info(f"Waiting for {self.name} controller startup... ({i+1}/{startup_timeout})")

            logger.error(f"{self.name} controller startup timeout")
            self._capture_final_output()
            return False

        except Exception as e:
            logger.error(f"Error monitoring {self.name} startup: {e}")
            return False

    def _capture_final_output(self):
        """Capture final output from failed process"""
        if self.process:
            try:
                stdout, stderr = self.process.communicate(timeout=2)
                if stdout:
                    for line in stdout.split('\n'):
                        if line.strip():
                            self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
                if stderr:
                    for line in stderr.split('\n'):
                        if line.strip():
                            self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} ERROR: {line.strip()}")
            except:
                pass

    def _get_environment(self):
        """Get environment variables for controller process"""
        env = os.environ.copy()

        conda_prefix = os.environ.get('CONDA_PREFIX')
        if not conda_prefix and 'anaconda3' in self.python_exe:
            conda_prefix = '/'.join(self.python_exe.split('/')[:-2])

        if conda_prefix and os.path.exists(conda_prefix):
            env['CONDA_PREFIX'] = conda_prefix
            env['PATH'] = f"{conda_prefix}/bin:{env.get('PATH', '')}"
            env['LD_LIBRARY_PATH'] = f"{conda_prefix}/lib:" + env.get('LD_LIBRARY_PATH', '')

            python_version = "python3.9"
            conda_site_packages = f"{conda_prefix}/lib/{python_version}/site-packages"
            env['PYTHONPATH'] = conda_site_packages + ":" + env.get('PYTHONPATH', '')

        return env

    def _verify_controller_running(self):
        """Verify that the controller is listening on the port"""
        if not self.process or self.process.poll() is not None:
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.controller_port))
            sock.close()

            if result == 0:
                logger.info(f"Controller verified listening on port {self.controller_port}")
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error verifying controller: {e}")
            return False

    def stop_controller(self):
        """Stop controller with proper cleanup"""
        self.is_running = False

        if self.process:
            try:
                pgid = os.getpgid(self.process.pid)

                # Send SIGTERM to process group
                os.killpg(pgid, signal.SIGTERM)

                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=5)
                    logger.info(f"{self.name} controller stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    os.killpg(pgid, signal.SIGKILL)
                    self.process.wait()
                    logger.info(f"{self.name} controller force killed")

            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping {self.name} controller: {e}")

            finally:
                self.process = None

        self.start_time = None
        return True

    def restart_controller(self):
        """Restart the controller"""
        logger.info(f"Restarting {self.name} controller")
        app = self.controller_type
        port = self.controller_port

        self.stop_controller()
        time.sleep(2)
        return self.start_controller(app, port)

    def get_status(self):
        """Get detailed controller status"""
        uptime = "00:00:00"
        if self.start_time:
            delta = datetime.now() - self.start_time
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

        return {
            'name': self.name,
            'running': self.is_running,
            'type': self.controller_type if self.is_running else None,
            'port': self.controller_port,
            'pid': self.process.pid if self.process else None,
            'uptime': uptime,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'python_executable': self.python_exe,
            'log_lines': len(self.logs)
        }

    def get_logs(self, lines=100):
        """Get recent controller logs"""
        recent_logs = list(self.logs)[-lines:] if lines else list(self.logs)

        # If controller is running, try to get more recent output
        if self.is_running and self.process:
            try:
                import select
                if self.process.stdout and select.select([self.process.stdout], [], [], 0)[0]:
                    while True:
                        line = self.process.stdout.readline()
                        if not line:
                            break
                        self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
                        recent_logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
            except:
                pass

        return {
            'logs': recent_logs,
            'total_lines': len(self.logs),
            'timestamp': datetime.now().isoformat(),
            'controller_running': self.is_running
        }

    def get_controller_stats(self):
        """Get controller statistics"""
        if not self.is_running:
            return {}

        stats = {
            'controller_name': self.name,
            'controller_type': self.controller_type,
            'uptime': self.get_status()['uptime'],
            'port': self.controller_port,
            'status': 'running',
            'connections': self._get_connection_count(),
            'memory_usage': self._get_memory_usage()
        }

        return stats

    def _get_connection_count(self):
        """Get number of OpenFlow connections"""
        try:
            if not self.process:
                return 0

            # Use netstat to count connections to the controller port
            result = subprocess.run([
                'netstat', '-an'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                count = 0
                for line in result.stdout.split('\n'):
                    if f':{self.controller_port}' in line and 'ESTABLISHED' in line:
                        count += 1
                return count
        except:
            pass
        return 0

    def _get_memory_usage(self):
        """Get memory usage of controller process"""
        try:
            if not self.process:
                return 0

            import psutil
            process = psutil.Process(self.process.pid)
            return process.memory_info().rss // 1024 // 1024  # MB
        except:
            return 0
