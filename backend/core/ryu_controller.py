"""
Enhanced Ryu Controller Manager with full web API control
"""

import os
import sys
import time
import signal
import subprocess
import socket
from datetime import datetime
from collections import deque

from utils.logger import setup_logger

logger = setup_logger(__name__)

class RyuControllerManager:
    """Enhanced Ryu controller manager with complete web API control"""
    
    def __init__(self):
        self.ryu_process = None
        self.controller_type = 'simple_switch_13'
        self.controller_port = 6633
        self.is_running = False
        self.start_time = None
        self.python_exe = self._get_python_executable()
        self.logs = deque(maxlen=1000)  # Store last 1000 log lines
        self.stats_data = {}
        
    def _get_python_executable(self):
        """Get the correct Python executable for Ryu"""
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
                try:
                    result = subprocess.run([
                        path, '-c', 'import ryu.cmd.manager; print("OK")'
                    ], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        logger.info(f"Found Python with Ryu at: {path}")
                        return path
                except:
                    continue
        
        return 'python3'
        
    def check_ryu_installation(self):
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
        
    def start_controller(self, controller_type='simple_switch_13', port=6633):
        """Start Ryu controller with enhanced monitoring"""
        try:
            if not self.check_ryu_installation():
                logger.error("Ryu is not properly installed")
                return False
                
            if self.is_running:
                logger.info("Controller already running, stopping first")
                self.stop_controller()
            
            self.controller_type = controller_type
            self.controller_port = port
            self.start_time = datetime.now()
            self.logs.clear()
            
            logger.info(f"Starting Ryu controller: {controller_type} on port {port}")
            
            # Try direct ryu-manager command first
            if self._start_with_ryu_manager(controller_type, port):
                return True
            
            # Fallback to Python script approach
            logger.info("Falling back to Python script approach")
            return self._start_with_script(controller_type, port)
                
        except Exception as e:
            logger.error(f"Error starting Ryu controller: {e}")
            self.stop_controller()
            return False
    
    def _start_with_ryu_manager(self, controller_type, port):
        """Start with direct ryu-manager command"""
        try:
            # Find ryu-manager command
            ryu_manager_paths = [
                '/home/ege/anaconda3/envs/sdn-mininet/bin/ryu-manager',
                f'{os.environ.get("CONDA_PREFIX", "")}/bin/ryu-manager' if os.environ.get("CONDA_PREFIX") else None,
            ]
            
            ryu_manager_cmd = None
            for path in ryu_manager_paths:
                if path and os.path.exists(path):
                    ryu_manager_cmd = path
                    break
            
            if not ryu_manager_cmd:
                result = subprocess.run(['which', 'ryu-manager'], capture_output=True)
                if result.returncode == 0:
                    ryu_manager_cmd = 'ryu-manager'
                else:
                    logger.info("ryu-manager command not found")
                    return False
            
            # Start with ryu-manager command
            cmd = [
                ryu_manager_cmd,
                f'ryu.app.{controller_type}',
                '--ofp-tcp-listen-port', str(port),
                '--verbose'
            ]
            
            logger.info(f"Starting Ryu with command: {' '.join(cmd)}")
            
            self.ryu_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                env=self._get_ryu_env(),
                bufsize=1,
                universal_newlines=True
            )
            
            return self._monitor_startup()
            
        except Exception as e:
            logger.error(f"Failed to start with ryu-manager: {e}")
            return False
    
    def _start_with_script(self, controller_type, port):
        """Start with Python script approach"""
        try:
            ryu_script = self._create_ryu_script(controller_type, port)
            if not ryu_script:
                return False
            
            logger.info(f"Starting Ryu with script using Python: {self.python_exe}")
            
            self.ryu_process = subprocess.Popen(
                [self.python_exe, ryu_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                env=self._get_ryu_env(),
                bufsize=1,
                universal_newlines=True
            )
            
            return self._monitor_startup()
            
        except Exception as e:
            logger.error(f"Failed to start with script: {e}")
            return False
    
    def _monitor_startup(self):
        """Monitor controller startup with real-time log capture"""
        try:
            startup_timeout = 15
            for i in range(startup_timeout):
                time.sleep(1)
                
                # Read any available output
                if self.ryu_process.stdout:
                    try:
                        import select
                        if select.select([self.ryu_process.stdout], [], [], 0)[0]:
                            line = self.ryu_process.stdout.readline()
                            if line:
                                self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
                    except:
                        pass
                
                # Check if process is still running
                if self.ryu_process.poll() is not None:
                    logger.error("Ryu process died during startup")
                    self._capture_final_output()
                    return False
                
                # Check if controller is listening
                if i >= 3 and self._verify_controller_running():
                    self.is_running = True
                    logger.info(f"Ryu controller started successfully: {self.controller_type}")
                    return True
                
                if i % 3 == 0:
                    logger.info(f"Waiting for controller startup... ({i+1}/{startup_timeout})")
            
            logger.error("Ryu controller startup timeout")
            self._capture_final_output()
            return False
            
        except Exception as e:
            logger.error(f"Error monitoring startup: {e}")
            return False
    
    def _capture_final_output(self):
        """Capture final output from failed process"""
        if self.ryu_process:
            try:
                stdout, stderr = self.ryu_process.communicate(timeout=2)
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
    
    def _get_ryu_env(self):
        """Get environment variables for Ryu process"""
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
        
        env['RYU_LOG_LEVEL'] = 'INFO'
        return env
    
    def _verify_controller_running(self):
        """Verify that the controller is listening on the port"""
        if not self.ryu_process or self.ryu_process.poll() is not None:
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
        """Stop Ryu controller with proper cleanup"""
        self.is_running = False
        
        if self.ryu_process:
            try:
                pgid = os.getpgid(self.ryu_process.pid)
                
                # Send SIGTERM to process group
                os.killpg(pgid, signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    self.ryu_process.wait(timeout=5)
                    logger.info("Ryu controller stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    os.killpg(pgid, signal.SIGKILL)
                    self.ryu_process.wait()
                    logger.info("Ryu controller force killed")
                
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping controller: {e}")
                
            finally:
                self.ryu_process = None
        
        # Clean up temporary script
        try:
            os.remove('/tmp/ryu_controller.py')
        except:
            pass
        
        self.start_time = None
        return True
    
    def restart_controller(self):
        """Restart the controller"""
        logger.info("Restarting Ryu controller")
        controller_type = self.controller_type
        port = self.controller_port
        
        self.stop_controller()
        time.sleep(2)
        return self.start_controller(controller_type, port)
    
    def get_status(self):
        """Get detailed controller status"""
        uptime = "00:00:00"
        if self.start_time:
            delta = datetime.now() - self.start_time
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        return {
            'running': self.is_running,
            'type': self.controller_type if self.is_running else None,
            'port': self.controller_port,
            'pid': self.ryu_process.pid if self.ryu_process else None,
            'uptime': uptime,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'python_executable': self.python_exe,
            'log_lines': len(self.logs)
        }
    
    def get_logs(self, lines=100):
        """Get recent controller logs"""
        recent_logs = list(self.logs)[-lines:] if lines else list(self.logs)
        
        # If controller is running, try to get more recent output
        if self.is_running and self.ryu_process:
            try:
                import select
                if self.ryu_process.stdout and select.select([self.ryu_process.stdout], [], [], 0)[0]:
                    while True:
                        line = self.ryu_process.stdout.readline()
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
            if not self.ryu_process:
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
            if not self.ryu_process:
                return 0
            
            import psutil
            process = psutil.Process(self.ryu_process.pid)
            return process.memory_info().rss // 1024 // 1024  # MB
        except:
            return 0