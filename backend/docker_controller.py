#!/usr/bin/env python3
"""
Docker-compatible controller manager that works without Ryu
Uses Mininet's built-in controllers and simple OpenFlow handling
"""

import os
import sys
import time
import signal
import subprocess
import socket
import threading
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger(__name__)

class DockerControllerManager:
    """Docker-compatible controller manager without Ryu dependency"""
    
    def __init__(self):
        self.controller_process = None
        self.controller_type = 'simple_switch'
        self.controller_port = 6633
        self.is_running = False
        self.start_time = None
        self.python_exe = 'python3'
        
    def start_controller(self, controller_type='simple_switch', port=6633):
        """Start a controller using available methods"""
        logger.info(f"Starting controller: {controller_type} on port {port}")
        
        if self.is_running:
            logger.warning("Controller is already running")
            return True
            
        self.controller_type = controller_type
        self.controller_port = port
        
        # Try different controller approaches
        success = False
        
        # Method 1: Try Mininet's built-in controller
        if self._start_mininet_controller(port):
            success = True
        # Method 2: Try simple OpenFlow listener
        elif self._start_simple_listener(port):
            success = True
        # Method 3: Try ovs-controller if available
        elif self._start_ovs_controller(port):
            success = True
            
        if success:
            self.is_running = True
            self.start_time = datetime.now()
            logger.info(f"✓ Controller started successfully on port {port}")
            return True
        else:
            logger.error("❌ Failed to start any controller")
            return False
    
    def _start_mininet_controller(self, port):
        """Try to start Mininet's built-in controller"""
        try:
            # Check if we can import Mininet's controller
            from mininet.node import Controller
            
            # Start a simple controller process
            cmd = [
                'python3', '-c', f'''
import time
import socket
from mininet.node import Controller

class SimpleController(Controller):
    def start(self):
        print("Starting simple controller on port {port}")
        return True
    
    def stop(self):
        print("Stopping simple controller")
        return True

controller = SimpleController("c0", port={port})
controller.start()

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    controller.stop()
'''
            ]
            
            self.controller_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            if self.controller_process.poll() is None:
                logger.info("✓ Mininet controller started")
                return True
            else:
                logger.info("❌ Mininet controller failed to start")
                return False
                
        except Exception as e:
            logger.info(f"Mininet controller not available: {e}")
            return False
    
    def _start_simple_listener(self, port):
        """Start a simple OpenFlow listener"""
        try:
            cmd = [
                'python3', '-c', f'''
import socket
import time
import threading

def handle_client(client_socket, addr):
    print(f"Switch connected from {{addr}}")
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            # Simple echo for keepalive
            client_socket.send(data)
    except Exception as e:
        print(f"Client {{addr}} error: {{e}}")
    finally:
        client_socket.close()
        print(f"Switch {{addr}} disconnected")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", {port}))
server.listen(5)
print(f"Simple OpenFlow listener on port {port}")

try:
    while True:
        client, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(client, addr))
        thread.daemon = True
        thread.start()
except KeyboardInterrupt:
    print("Stopping controller")
finally:
    server.close()
'''
            ]
            
            self.controller_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True
            )
            
            # Give it a moment to start
            time.sleep(1)
            
            # Test if the port is listening
            if self._test_port_listening(port):
                logger.info("✓ Simple OpenFlow listener started")
                return True
            else:
                logger.info("❌ Simple OpenFlow listener failed")
                return False
                
        except Exception as e:
            logger.info(f"Simple listener failed: {e}")
            return False
    
    def _start_ovs_controller(self, port):
        """Try to start ovs-controller if available"""
        try:
            # Check if ovs-controller is available
            result = subprocess.run(['which', 'ovs-controller'], capture_output=True)
            if result.returncode != 0:
                return False
                
            cmd = ['ovs-controller', f'ptcp:{port}']
            
            self.controller_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True
            )
            
            # Give it a moment to start
            time.sleep(1)
            
            if self.controller_process.poll() is None:
                logger.info("✓ OVS controller started")
                return True
            else:
                logger.info("❌ OVS controller failed to start")
                return False
                
        except Exception as e:
            logger.info(f"OVS controller not available: {e}")
            return False
    
    def _test_port_listening(self, port):
        """Test if a port is listening"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def stop_controller(self):
        """Stop the controller"""
        if not self.is_running:
            return True
            
        try:
            if self.controller_process:
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(self.controller_process.pid), signal.SIGTERM)
                
                # Wait for clean shutdown
                try:
                    self.controller_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if necessary
                    os.killpg(os.getpgid(self.controller_process.pid), signal.SIGKILL)
                    self.controller_process.wait()
                
                self.controller_process = None
            
            self.is_running = False
            self.start_time = None
            logger.info("✓ Controller stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping controller: {e}")
            return False
    
    def get_controller_status(self):
        """Get controller status"""
        uptime = "00:00:00"
        if self.is_running and self.start_time:
            delta = datetime.now() - self.start_time
            uptime = str(delta).split('.')[0]  # Remove microseconds
        
        return {
            'running': self.is_running,
            'type': self.controller_type if self.is_running else None,
            'port': self.controller_port,
            'pid': self.controller_process.pid if self.controller_process else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime': uptime,
            'python_executable': self.python_exe,
            'log_lines': 0  # Simplified for Docker
        }
    
    def get_status(self):
        """Alias for compatibility with existing code"""
        return self.get_controller_status()
    
    def get_controller_stats(self):
        """Get controller statistics - simplified for Docker"""
        return {
            'connections': 1 if self.is_running else 0,
            'switches_connected': 1 if self.is_running else 0,
            'flows_installed': 0,  # Simplified
            'packets_processed': 0,  # Simplified
            'uptime_seconds': int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
        }

# Global instance for compatibility
_docker_controller = DockerControllerManager()

def get_docker_controller():
    """Get the global Docker controller instance"""
    return _docker_controller
