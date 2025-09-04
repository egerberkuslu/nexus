"""
Base Switch Manager Class
Provides common interface and functionality for all network switches
"""

import os
import time
import signal
import subprocess
import socket
from datetime import datetime
from collections import deque
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from utils.logger import setup_logger

logger = setup_logger(__name__)

class BaseSwitchManager(ABC):
    """Base class for all network switch managers"""

    def __init__(self, name: str, switch_type: str = 'unknown'):
        self.name = name
        self.switch_type = switch_type
        self.is_running = False
        self.start_time = None
        self.logs = deque(maxlen=1000)  # Store last 1000 log lines
        self.stats_data = {}
        self.process = None
        self.switch_ports = {}  # Track port assignments
        self.bridge_name = None
        self.dpid = None  # For OpenFlow switches

    @abstractmethod
    def check_installation(self) -> bool:
        """Check if switch software is properly installed"""
        pass

    @abstractmethod
    def create_switch(self, switch_id: str, **kwargs) -> Any:
        """Create a switch instance with specific configuration"""
        pass

    @abstractmethod
    def get_switch_stats(self) -> Dict[str, Any]:
        """Get switch-specific statistics"""
        pass

    @abstractmethod
    def get_bridge_status(self) -> Dict[str, Any]:
        """Get bridge status and configuration"""
        pass

    def start_switch_process(self, cmd: List[str], env: Optional[Dict[str, str]] = None) -> bool:
        """Start a switch process with monitoring"""
        try:
            if self.is_running:
                logger.info(f"{self.name} switch already running, stopping first")
                self.stop_switch_process()

            self.start_time = datetime.now()
            self.logs.clear()

            logger.info(f"Starting {self.name} switch with command: {' '.join(cmd)}")

            # Start the process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                env=env or os.environ.copy(),
                bufsize=1,
                universal_newlines=True
            )

            return self._monitor_startup()

        except Exception as e:
            logger.error(f"Error starting {self.name} switch process: {e}")
            self.stop_switch_process()
            return False

    def _monitor_startup(self, timeout: int = 15) -> bool:
        """Monitor switch startup with real-time log capture"""
        try:
            for i in range(timeout):
                time.sleep(1)

                # Read any available output
                if self.process and self.process.stdout:
                    try:
                        import select
                        if select.select([self.process.stdout], [], [], 0)[0]:
                            line = self.process.stdout.readline()
                            if line:
                                self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line.strip()}")
                    except:
                        pass

                # Check if process is still running
                if self.process and self.process.poll() is not None:
                    logger.error(f"{self.name} process died during startup")
                    self._capture_final_output()
                    return False

                # Check if switch is ready (implementation-specific)
                if i >= 3 and self._verify_switch_running():
                    self.is_running = True
                    logger.info(f"{self.name} switch started successfully")
                    return True

                if i % 3 == 0:
                    logger.info(f"Waiting for {self.name} switch startup... ({i+1}/{timeout})")

            logger.error(f"{self.name} switch startup timeout")
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

    def _verify_switch_running(self) -> bool:
        """Verify that the switch is running (implementation-specific)"""
        if not self.process or self.process.poll() is not None:
            return False
        return True

    def stop_switch_process(self) -> bool:
        """Stop switch process with proper cleanup"""
        self.is_running = False

        if self.process:
            try:
                pgid = os.getpgid(self.process.pid)

                # Send SIGTERM to process group
                os.killpg(pgid, signal.SIGTERM)

                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=5)
                    logger.info(f"{self.name} switch stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    os.killpg(pgid, signal.SIGKILL)
                    self.process.wait()
                    logger.info(f"{self.name} switch force killed")

            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping {self.name} switch: {e}")

            finally:
                self.process = None

        self.start_time = None
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get detailed switch status"""
        uptime = "00:00:00"
        if self.start_time:
            delta = datetime.now() - self.start_time
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = "02d"

        return {
            'name': self.name,
            'switch_type': self.switch_type,
            'running': self.is_running,
            'bridge_name': self.bridge_name,
            'dpid': self.dpid,
            'port_count': len(self.switch_ports),
            'uptime': uptime,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'pid': self.process.pid if self.process else None,
            'log_lines': len(self.logs)
        }

    def get_logs(self, lines: int = 100) -> Dict[str, Any]:
        """Get recent switch logs"""
        recent_logs = list(self.logs)[-lines:] if lines else list(self.logs)

        # If switch is running, try to get more recent output
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
            'switch_running': self.is_running
        }

    def get_memory_usage(self) -> int:
        """Get memory usage of switch process"""
        try:
            if not self.process:
                return 0

            import psutil
            process = psutil.Process(self.process.pid)
            return process.memory_info().rss // 1024 // 1024  # MB
        except:
            return 0

    def configure_port(self, port_name: str, config: Dict[str, Any]) -> bool:
        """Configure a specific port (implementation-specific)"""
        logger.info(f"Configuring port {port_name} with config: {config}")
        self.switch_ports[port_name] = config
        return True

    def get_port_config(self, port_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific port"""
        return self.switch_ports.get(port_name)

    def list_ports(self) -> List[str]:
        """List all configured ports"""
        return list(self.switch_ports.keys())
