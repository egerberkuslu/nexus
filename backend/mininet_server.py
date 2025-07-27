#!/usr/bin/env python3
"""
Mininet Web Framework Backend - Enhanced with Real Network Statistics
Provides robust REST API for Mininet network management with Ryu controller
Now includes real network metrics instead of frontend simulation
UPDATED: Fixed Router type detection and classification
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch, Host, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink
from mininet.util import dumpNodeConnections

import sys
import json
import threading
import time
import subprocess
import os
import signal
import re
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

class NetworkStatsCollector:
    """Collects real network statistics from Mininet and OVS"""
    
    def __init__(self):
        self.start_time = None
        self.stats_history = defaultdict(list)
        self.interface_stats = {}
        self.flow_stats = {}
        self.packet_counters = defaultdict(int)
        self.byte_counters = defaultdict(int)
        self.last_collection_time = None
        
    def start_collection(self):
        """Start collecting network statistics"""
        self.start_time = datetime.now()
        self.last_collection_time = datetime.now()
        
    def stop_collection(self):
        """Stop collecting network statistics"""
        self.start_time = None
        self.stats_history.clear()
        self.interface_stats.clear()
        self.flow_stats.clear()
        self.packet_counters.clear()
        self.byte_counters.clear()
        
    def get_uptime(self):
        """Get network uptime"""
        if not self.start_time:
            return "00:00:00"
        
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    
    def collect_interface_stats(self, net):
        """Collect interface statistics from network devices"""
        stats = {}
        
        if not net:
            return stats
            
        try:
            for node in net.hosts + net.switches:
                node_stats = {}
                
                # Get interface information
                for intf in node.intfList():
                    if intf.name == 'lo':  # Skip loopback
                        continue
                        
                    try:
                        # Read interface statistics from /proc/net/dev
                        with open('/proc/net/dev', 'r') as f:
                            lines = f.readlines()
                            
                        for line in lines:
                            if intf.name in line:
                                parts = line.split()
                                if len(parts) >= 17:
                                    # Parse network statistics
                                    rx_bytes = int(parts[1])
                                    rx_packets = int(parts[2])
                                    rx_errors = int(parts[3])
                                    rx_dropped = int(parts[4])
                                    
                                    tx_bytes = int(parts[9])
                                    tx_packets = int(parts[10])
                                    tx_errors = int(parts[11])
                                    tx_dropped = int(parts[12])
                                    
                                    node_stats[intf.name] = {
                                        'rx_bytes': rx_bytes,
                                        'rx_packets': rx_packets,
                                        'rx_errors': rx_errors,
                                        'rx_dropped': rx_dropped,
                                        'tx_bytes': tx_bytes,
                                        'tx_packets': tx_packets,
                                        'tx_errors': tx_errors,
                                        'tx_dropped': tx_dropped
                                    }
                                break
                    except (FileNotFoundError, ValueError, IndexError) as e:
                        continue
                
                if node_stats:
                    stats[node.name] = node_stats
                    
        except Exception as e:
            error(f"Error collecting interface stats: {e}")
            
        return stats
    
    def collect_ovs_stats(self, net):
        """Collect OpenFlow statistics from OVS switches"""
        ovs_stats = {}
        
        if not net:
            return ovs_stats
            
        try:
            for switch in net.switches:
                switch_stats = {
                    'flows': [],
                    'ports': {},
                    'tables': {}
                }
                
                try:
                    # Get flow statistics
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-flows', switch.name, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        flows = []
                        total_packets = 0
                        total_bytes = 0
                        
                        for line in result.stdout.strip().split('\n'):
                            if 'cookie=' in line:
                                # Parse flow entry
                                flow_info = {}
                                
                                # Extract packet and byte counts
                                packet_match = re.search(r'n_packets=(\d+)', line)
                                byte_match = re.search(r'n_bytes=(\d+)', line)
                                
                                if packet_match:
                                    packets = int(packet_match.group(1))
                                    flow_info['packets'] = packets
                                    total_packets += packets
                                    
                                if byte_match:
                                    bytes_count = int(byte_match.group(1))
                                    flow_info['bytes'] = bytes_count
                                    total_bytes += bytes_count
                                
                                # Extract other flow information
                                priority_match = re.search(r'priority=(\d+)', line)
                                if priority_match:
                                    flow_info['priority'] = int(priority_match.group(1))
                                
                                table_match = re.search(r'table=(\d+)', line)
                                if table_match:
                                    flow_info['table'] = int(table_match.group(1))
                                
                                flows.append(flow_info)
                        
                        switch_stats['flows'] = flows
                        switch_stats['total_packets'] = total_packets
                        switch_stats['total_bytes'] = total_bytes
                        
                        # Update global counters
                        self.packet_counters[switch.name] = total_packets
                        self.byte_counters[switch.name] = total_bytes
                        
                except subprocess.TimeoutExpired:
                    switch_stats['error'] = 'timeout'
                except Exception as e:
                    switch_stats['error'] = str(e)
                
                try:
                    # Get port statistics
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-ports', switch.name, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        ports = {}
                        for line in result.stdout.strip().split('\n'):
                            if 'port' in line and 'rx' in line:
                                # Parse port statistics
                                port_match = re.search(r'port\s+(\d+|LOCAL):', line)
                                if port_match:
                                    port_num = port_match.group(1)
                                    
                                    rx_match = re.search(r'rx pkts=(\d+), bytes=(\d+)', line)
                                    tx_match = re.search(r'tx pkts=(\d+), bytes=(\d+)', line)
                                    
                                    port_info = {}
                                    if rx_match:
                                        port_info['rx_packets'] = int(rx_match.group(1))
                                        port_info['rx_bytes'] = int(rx_match.group(2))
                                    if tx_match:
                                        port_info['tx_packets'] = int(tx_match.group(1))
                                        port_info['tx_bytes'] = int(tx_match.group(2))
                                    
                                    ports[port_num] = port_info
                        
                        switch_stats['ports'] = ports
                        
                except subprocess.TimeoutExpired:
                    pass
                except Exception as e:
                    pass
                
                ovs_stats[switch.name] = switch_stats
                
        except Exception as e:
            error(f"Error collecting OVS stats: {e}")
            
        return ovs_stats
    
    def calculate_bandwidth(self, current_bytes, previous_bytes, time_diff):
        """Calculate bandwidth in Mbps"""
        if time_diff <= 0 or previous_bytes is None:
            return 0.0
            
        bytes_diff = current_bytes - previous_bytes
        if bytes_diff < 0:  # Counter reset
            bytes_diff = current_bytes
            
        # Convert to Mbps (bytes per second -> bits per second -> Mbps)
        bandwidth_bps = (bytes_diff * 8) / time_diff
        bandwidth_mbps = bandwidth_bps / (1024 * 1024)
        
        return round(bandwidth_mbps, 2)
    
    def measure_latency(self, net):
        """Measure network latency between hosts"""
        if not net or len(net.hosts) < 2:
            return 0.0
            
        try:
            # Pick two hosts for latency measurement
            host1 = net.hosts[0]
            host2 = net.hosts[1] if len(net.hosts) > 1 else net.hosts[0]
            
            if host1 == host2:
                return 0.0
            
            # Run ping with single packet and parse latency
            result = host1.cmd(f'ping -c 1 -W 1 {host2.IP()}')
            
            # Parse latency from ping output
            latency_match = re.search(r'time=(\d+\.?\d*)', result)
            if latency_match:
                return float(latency_match.group(1))
                
        except Exception as e:
            error(f"Error measuring latency: {e}")
            
        return 0.0
    
    def get_network_metrics(self, net):
        """Get comprehensive network metrics"""
        current_time = datetime.now()
        
        # Collect current statistics
        interface_stats = self.collect_interface_stats(net)
        ovs_stats = self.collect_ovs_stats(net)
        
        # Calculate total packets and bytes
        total_packets = sum(self.packet_counters.values())
        total_bytes = sum(self.byte_counters.values())
        
        # Calculate bandwidth if we have previous data
        bandwidth = 0.0
        if self.last_collection_time and hasattr(self, 'previous_bytes'):
            time_diff = (current_time - self.last_collection_time).total_seconds()
            bandwidth = self.calculate_bandwidth(total_bytes, self.previous_bytes, time_diff)
        
        # Store current bytes for next calculation
        self.previous_bytes = total_bytes
        self.last_collection_time = current_time
        
        # Measure latency
        latency = self.measure_latency(net)
        
        # Calculate additional metrics
        total_interfaces = sum(len(node_stats) for node_stats in interface_stats.values())
        active_flows = sum(len(switch_stats.get('flows', [])) for switch_stats in ovs_stats.values())
        
        metrics = {
            'uptime': self.get_uptime(),
            'packets_transferred': total_packets,
            'total_bytes': total_bytes,
            'bandwidth_mbps': bandwidth,
            'latency_ms': latency,
            'active_flows': active_flows,
            'total_interfaces': total_interfaces,
            'interface_stats': interface_stats,
            'ovs_stats': ovs_stats,
            'timestamp': current_time.isoformat()
        }
        
        # Store in history (keep last 100 entries)
        self.stats_history['metrics'].append(metrics)
        if len(self.stats_history['metrics']) > 100:
            self.stats_history['metrics'].pop(0)
            
        return metrics

class RyuControllerManager:
    """Enhanced Ryu controller manager with better process handling"""
    
    def __init__(self):
        self.ryu_process = None
        self.controller_type = 'simple_switch_13'
        self.controller_port = 6633
        self.is_running = False
        self.stats_data = {}
        self.python_exe = self._get_python_executable()
        
    def _get_python_executable(self):
        """Get the correct Python executable (preferring conda env)"""
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
                # Test if this python has ryu
                try:
                    result = subprocess.run([
                        path, '-c', 'import ryu.cmd.manager; print("OK")'
                    ], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        info(f"Found Python with Ryu at: {path}")
                        return path
                except:
                    continue
        
        # Fallback to system python3
        return 'python3'
        
    def check_ryu_installation(self):
        """Check if Ryu is properly installed"""
        try:
            # Test importing key Ryu modules with the correct Python
            result = subprocess.run([
                self.python_exe, '-c', 
                'import ryu.cmd.manager; import ryu.app.simple_switch_13; print("Ryu OK")'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                info(f"Ryu installation verified successfully with {self.python_exe}")
                return True
            else:
                error(f"Ryu import test failed: {result.stderr}")
                return False
        except Exception as e:
            error(f"Could not verify Ryu installation: {e}")
            return False
        
    def start_controller(self, controller_type='simple_switch_13', port=6633):
        """Start Ryu controller with enhanced error handling"""
        try:
            # First check if Ryu is installed
            if not self.check_ryu_installation():
                error("Ryu is not properly installed. Install with: pip install ryu")
                return False
                
            if self.is_running:
                self.stop_controller()
            
            self.controller_type = controller_type
            self.controller_port = port
            
            info(f"Starting Ryu controller with {controller_type} on port {port}")
            
            # Try direct ryu-manager command first
            if self._start_with_ryu_manager(controller_type, port):
                return True
            
            # Fallback to Python script approach
            info("Falling back to Python script approach...")
            return self._start_with_script(controller_type, port)
                
        except Exception as e:
            error(f"Error starting Ryu controller: {e}")
            self.stop_controller()
            return False
    
    def _start_with_ryu_manager(self, controller_type, port):
        """Try starting with direct ryu-manager command"""
        try:
            # Check for ryu-manager in conda environment first
            ryu_manager_paths = [
                '/home/ege/anaconda3/envs/sdn-mininet/bin/ryu-manager',
                f'{os.environ.get("CONDA_PREFIX", "")}/bin/ryu-manager' if os.environ.get("CONDA_PREFIX") else None,
            ]
            
            ryu_manager_cmd = None
            for path in ryu_manager_paths:
                if path and os.path.exists(path):
                    ryu_manager_cmd = path
                    break
            
            # Fallback to system ryu-manager
            if not ryu_manager_cmd:
                result = subprocess.run(['which', 'ryu-manager'], capture_output=True)
                if result.returncode == 0:
                    ryu_manager_cmd = 'ryu-manager'
                else:
                    info("ryu-manager command not found, trying script approach")
                    return False
            
            # Start with ryu-manager command
            cmd = [
                ryu_manager_cmd,
                f'ryu.app.{controller_type}',
                '--ofp-tcp-listen-port', str(port),
                '--verbose'
            ]
            
            info(f"Starting Ryu with command: {' '.join(cmd)}")
            
            self.ryu_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                text=True,
                env=self._get_ryu_env()
            )
            
            return self._monitor_startup()
            
        except Exception as e:
            error(f"Failed to start with ryu-manager: {e}")
            return False
    
    def _start_with_script(self, controller_type, port):
        """Start with Python script approach"""
        try:
            # Create Ryu startup script
            ryu_script = self._create_ryu_script(controller_type, port)
            if not ryu_script:
                return False
            
            info(f"Starting Ryu with script using Python: {self.python_exe}")
            
            # Start Ryu controller process with script using correct Python
            self.ryu_process = subprocess.Popen(
                [self.python_exe, ryu_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                text=True,
                env=self._get_ryu_env()
            )
            
            return self._monitor_startup()
            
        except Exception as e:
            error(f"Failed to start with script: {e}")
            return False
    
    def _monitor_startup(self):
        """Monitor controller startup process"""
        try:
            startup_timeout = 10
            for i in range(startup_timeout):
                time.sleep(1)
                
                # Check if process is still running
                if self.ryu_process.poll() is not None:
                    # Process died, get error output
                    stdout, stderr = self.ryu_process.communicate()
                    error(f"Ryu process died during startup:")
                    if stderr:
                        error(f"STDERR: {stderr}")
                    if stdout:
                        error(f"STDOUT: {stdout}")
                    return False
                
                # Check if controller is listening (start checking after 3 seconds)
                if i >= 3 and self._verify_controller_running():
                    self.is_running = True
                    info(f"Ryu controller started successfully with {self.controller_type}")
                    return True
                
                if i % 2 == 0:  # Log progress every 2 seconds
                    info(f"Waiting for controller startup... ({i+1}/{startup_timeout})")
            
            # Timeout - controller didn't start properly
            error("Ryu controller startup timeout")
            if self.ryu_process and self.ryu_process.poll() is None:
                stdout, stderr = self.ryu_process.communicate()
                if stderr:
                    error(f"Final STDERR: {stderr}")
                if stdout:
                    error(f"Final STDOUT: {stdout}")
            return False
            
        except Exception as e:
            error(f"Error monitoring startup: {e}")
            return False
    
    def _create_ryu_script(self, controller_type, port):
        """Create a temporary Ryu startup script"""
        script_content = f'''#!/usr/bin/env python3
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

# Patch eventlet to handle compatibility issues
try:
    import eventlet.wsgi
    if not hasattr(eventlet.wsgi, 'ALREADY_HANDLED'):
        eventlet.wsgi.ALREADY_HANDLED = object()
except ImportError:
    pass
except Exception as e:
    print(f"Eventlet patch warning: {{e}}", file=sys.stderr)

# Import and run Ryu
try:
    from ryu.cmd import manager
    # Set up arguments for ryu-manager
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
    print("Make sure Ryu is properly installed: pip install ryu", file=sys.stderr)
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
            error(f"Failed to create Ryu script: {e}")
            return None
    
    def _get_ryu_env(self):
        """Get environment variables for Ryu process"""
        env = os.environ.copy()
        
        # If we're using conda environment, preserve its paths
        conda_prefix = os.environ.get('CONDA_PREFIX')
        if not conda_prefix:
            # Try to detect conda environment from Python executable
            if 'anaconda3' in self.python_exe or 'conda' in self.python_exe:
                conda_prefix = '/'.join(self.python_exe.split('/')[:-2])
        
        if conda_prefix and os.path.exists(conda_prefix):
            # Set up conda environment paths
            env['CONDA_PREFIX'] = conda_prefix
            env['PATH'] = f"{conda_prefix}/bin:{env.get('PATH', '')}"
            env['LD_LIBRARY_PATH'] = f"{conda_prefix}/lib:" + env.get('LD_LIBRARY_PATH', '')
            
            # Python path for conda environment
            python_version = "python3.9"  # Adjust if needed
            conda_site_packages = f"{conda_prefix}/lib/{python_version}/site-packages"
            env['PYTHONPATH'] = conda_site_packages + ":" + env.get('PYTHONPATH', '')
        
        # Set logging level
        env['RYU_LOG_LEVEL'] = 'INFO'
        
        return env
    
    def _verify_controller_running(self):
        """Verify that the controller is actually running and listening"""
        if not self.ryu_process or self.ryu_process.poll() is not None:
            return False
        
        # Check if port is being listened on
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.controller_port))
            sock.close()
            
            if result == 0:
                info(f"Controller verified listening on port {self.controller_port}")
                return True
            else:
                info(f"Controller not yet listening on port {self.controller_port}")
                return False
        except Exception as e:
            error(f"Error verifying controller: {e}")
            return False
    
    def stop_controller(self):
        """Stop Ryu controller with proper cleanup"""
        self.is_running = False
        
        if self.ryu_process:
            try:
                # Get process group ID
                pgid = os.getpgid(self.ryu_process.pid)
                
                # Send SIGTERM to process group
                os.killpg(pgid, signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    self.ryu_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    os.killpg(pgid, signal.SIGKILL)
                    self.ryu_process.wait()
                
                info("Ryu controller stopped successfully")
                
            except ProcessLookupError:
                pass  # Process already dead
            except Exception as e:
                error(f"Error stopping controller: {e}")
                
            finally:
                self.ryu_process = None
        
        # Clean up temporary script
        try:
            os.remove('/tmp/ryu_controller.py')
        except:
            pass
        
        return True
    
    def get_status(self):
        """Get detailed controller status"""
        return {
            'running': self.is_running,
            'type': self.controller_type if self.is_running else None,
            'port': self.controller_port,
            'pid': self.ryu_process.pid if self.ryu_process else None
        }
    
    def get_controller_stats(self):
        """Get controller statistics (placeholder for now)"""
        if not self.is_running:
            return {}
        
        return {
            'controller_type': self.controller_type,
            'uptime': 'Unknown',  # Could be calculated
            'port': self.controller_port,
            'status': 'running'
        }


class Router(Host):
    """A Router host that can route between subnets."""
    
    def __init__(self, name, **params):
        # Set node type to router for identification
        params['node_type'] = 'router'
        super(Router, self).__init__(name, **params)
        self.node_type = 'router'  # Custom attribute for type identification
    
    def config(self, **params):
        super(Router, self).config(**params)
        # Enable IP forwarding
        self.cmd('sysctl net.ipv4.ip_forward=1')
        # Set up as router
        self.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
    
    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(Router, self).terminate()
    
    def get_type(self):
        """Return node type as router."""
        return 'router'

class MininetManager:
    def __init__(self):
        self.net = None
        self.is_running = False
        self.ryu_controller = RyuControllerManager()
        self.stats_collector = NetworkStatsCollector()
        self.topology_data = {
            'nodes': [],
            'links': [],
            'stats': {}
        }
    
    def start_ryu_controller(self, controller_type='simple_switch_13'):
        """Start Ryu controller"""
        return self.ryu_controller.start_controller(controller_type)
    
    def stop_ryu_controller(self):
        """Stop Ryu controller"""
        return self.ryu_controller.stop_controller()
    
    def get_controller_status(self):
        """Get controller status"""
        return self.ryu_controller.get_status()

    def create_simple_topology(self):
        """Create the network topology."""
        try:
            # Clean any existing Mininet processes
            os.system('mn -c > /dev/null 2>&1')
            
            # Create network with RemoteController for external controller (like Ryu)
            self.net = Mininet(
                controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
                switch=OVSKernelSwitch,
                link=TCLink,
                host=Host,
                autoSetMacs=True,
                autoStaticArp=False  # Disable auto ARP for manual router setup
            )
            
            # Add controller
            c0 = self.net.addController('c0', controller=RemoteController, 
                                      ip='127.0.0.1', port=6633)
            
            # Add switches
            s1 = self.net.addSwitch('s1', protocols='OpenFlow13')
            s2 = self.net.addSwitch('s2', protocols='OpenFlow13')
            
            # Add router with proper Router class - FIXED: Using cls=Router
            r1 = self.net.addHost('r1', cls=Router, ip='10.0.1.1/24')
            
            # Add hosts in different subnets
            h1 = self.net.addHost('h1', ip='10.0.1.10/24', defaultRoute='via 10.0.1.1')
            h2 = self.net.addHost('h2', ip='10.0.1.11/24', defaultRoute='via 10.0.1.1')
            h3 = self.net.addHost('h3', ip='10.0.2.10/24', defaultRoute='via 10.0.2.1')
            h4 = self.net.addHost('h4', ip='10.0.2.11/24', defaultRoute='via 10.0.2.1')
            
            # Add links
            # Subnet 1: h1, h2 connected to s1, router interface 1 to s1
            self.net.addLink(h1, s1, bw=10)
            self.net.addLink(h2, s1, bw=10)
            self.net.addLink(r1, s1, bw=100, intfName1='r1-eth0')
            
            # Subnet 2: h3, h4 connected to s2, router interface 2 to s2  
            self.net.addLink(h3, s2, bw=10)
            self.net.addLink(h4, s2, bw=10)
            self.net.addLink(r1, s2, bw=100, intfName1='r1-eth1')
            
            # Start network
            self.net.start()
            
            # Configure router interfaces
            self._configure_router(r1)
            
            info("*** Network topology created successfully!\n")
            self._print_topology_info()
            
            return True
            
        except Exception as e:
            error(f"Error creating topology: {e}\n")
            return False
    
    def _configure_router(self, router):
        """Configure router interfaces and routing."""
        try:
            # Configure router interfaces
            router.cmd('ifconfig r1-eth0 10.0.1.1/24')
            router.cmd('ifconfig r1-eth1 10.0.2.1/24')
            
            # Add routing table entries (optional, for explicit routing)
            router.cmd('ip route add 10.0.1.0/24 dev r1-eth0')
            router.cmd('ip route add 10.0.2.0/24 dev r1-eth1')
            
            info("*** Router configured successfully\n")
            
        except Exception as e:
            error(f"Error configuring router: {e}\n")
    
    def _print_topology_info(self):
        """Print topology information."""
        info("*** Topology Information:\n")
        info("Subnet 1 (10.0.1.0/24):\n")
        info("  - h1: 10.0.1.10/24 -> s1\n")
        info("  - h2: 10.0.1.11/24 -> s1\n")
        info("  - r1-eth0: 10.0.1.1/24 -> s1\n")
        info("Subnet 2 (10.0.2.0/24):\n")
        info("  - h3: 10.0.2.10/24 -> s2\n")
        info("  - h4: 10.0.2.11/24 -> s2\n")
        info("  - r1-eth1: 10.0.2.1/24 -> s2\n")
        info("Router: r1 (connects s1 and s2)\n")
        info("Controller: c0 (127.0.0.1:6633)\n")
    
    def test_connectivity(self):
        """Test connectivity between hosts."""
        if not self.net:
            error("Network not created yet!\n")
            return
        
        info("*** Testing connectivity:\n")
        
        # Test same subnet connectivity
        info("Testing same subnet (h1 -> h2):\n")
        result = self.net.get('h1').cmd('ping -c 2 10.0.1.11')
        info(f"{result}")
        
        # Test cross subnet connectivity
        info("Testing cross subnet (h1 -> h3):\n")
        result = self.net.get('h1').cmd('ping -c 2 10.0.2.10')
        info(f"{result}")
    
    def start_cli(self):
        """Start Mininet CLI."""
        if self.net:
            info("*** Starting CLI (type 'exit' to quit)\n")
            CLI(self.net)
    
    def stop(self):
        """Stop and cleanup the network."""
        if self.net:
            info("*** Stopping network\n")
            self.net.stop()

    def create_custom_topology(self, topology_config):
        """Create custom topology from configuration"""
        try:
            # Clean any existing Mininet processes
            os.system('mn -c > /dev/null 2>&1')
            
            # Create network
            self.net = Mininet(
                controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
                switch=OVSKernelSwitch,
                link=TCLink,
                autoSetMacs=True,
                autoStaticArp=True
            )
            
            # Add controller
            c0 = self.net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
            
            # Add switches
            switches = {}
            for switch_config in topology_config.get('switches', []):
                switch_id = switch_config['id']
                switches[switch_id] = self.net.addSwitch(switch_id, protocols='OpenFlow13')
            
            # Add hosts and routers
            hosts = {}
            routers = {}
            for host_config in topology_config.get('hosts', []):
                host_id = host_config['id']
                host_ip = host_config.get('ip', f'10.0.0.{len(hosts)+1}/24')
                host_type = host_config.get('type', 'host')
                
                if host_type == 'router':
                    routers[host_id] = self.net.addHost(host_id, cls=Router, ip=host_ip)
                else:
                    hosts[host_id] = self.net.addHost(host_id, ip=host_ip)
            
            # Add links
            for link_config in topology_config.get('links', []):
                node1 = link_config['source']
                node2 = link_config['target']
                bw = link_config.get('bandwidth', 10)
                
                # Get nodes (could be host, router, or switch)
                n1 = hosts.get(node1) or routers.get(node1) or switches.get(node1)
                n2 = hosts.get(node2) or routers.get(node2) or switches.get(node2)
                
                if n1 and n2:
                    self.net.addLink(n1, n2, bw=bw)
            
            self._update_topology_data()
            return True
            
        except Exception as e:
            error(f"Error creating custom topology: {e}")
            return False
    
    def start_network(self):
        """Start the Mininet network with Ryu controller"""
        if self.net is None:
            if not self.create_simple_topology():
                return False
        
        if self.is_running:
            return True
            
        try:
            # Start Ryu controller first
            if not self.start_ryu_controller():
                return False
                
            # Start Mininet network
            self.net.start()
            self.is_running = True
            
            # Start statistics collection
            self.stats_collector.start_collection()
            
            # Wait for switches to connect
            time.sleep(2)
            
            info("Network started successfully")
            self._update_topology_data()
            return True
        except Exception as e:
            error(f"Error starting network: {e}")
            self.stop_network()
            return False
    
    def stop_network(self):
        """Stop the Mininet network and Ryu controller"""
        try:
            # Stop statistics collection
            self.stats_collector.stop_collection()
            
            if self.net:
                self.net.stop()
                self.is_running = False
                info("Mininet network stopped")
            
            self.stop_ryu_controller()
            self.net = None
            return True
        except Exception as e:
            error(f"Error stopping network: {e}")
            return False
    
    def _update_topology_data(self):
        """Update topology data for visualization - FIXED ROUTER TYPE DETECTION"""
        self.topology_data = {'nodes': [], 'links': [], 'stats': {}}
        
        if not self.net:
            return
            
        # Add nodes (hosts, routers, and switches)
        for node in self.net.hosts + self.net.switches:
            # Determine node type - CHECK FOR ROUTER FIRST
            if isinstance(node, Router):
                node_type = 'router'
            elif hasattr(node, 'node_type') and node.node_type == 'router':
                node_type = 'router'
            elif hasattr(node, 'get_type') and callable(node.get_type):
                try:
                    node_type = node.get_type()
                except:
                    node_type = 'host' if isinstance(node, Host) else 'switch'
            elif isinstance(node, Host):
                node_type = 'host'
            else:
                node_type = 'switch'
            
            node_ip = node.IP() if hasattr(node, 'IP') and node_type in ['host', 'router'] else ''
            node_mac = getattr(node, 'MAC', lambda: 'auto')() if node_type in ['host', 'router'] else 'N/A'
            
            # Get additional node information
            node_info = {
                'id': node.name,
                'type': node_type,
                'ip': node_ip,
                'mac': node_mac,
                'status': 'active' if self.is_running else 'inactive'
            }
            
            # Add interface information for routers
            if node_type == 'router':
                interfaces = []
                for intf in node.intfList():
                    if intf.name != 'lo':
                        try:
                            interfaces.append({
                                'name': intf.name,
                                'ip': intf.IP() if hasattr(intf, 'IP') else 'unknown',
                                'mac': intf.MAC() if hasattr(intf, 'MAC') else 'unknown'
                            })
                        except:
                            interfaces.append({
                                'name': intf.name,
                                'ip': 'unknown',
                                'mac': 'unknown'
                            })
                node_info['interfaces'] = interfaces
            
            # Add port information for switches
            elif node_type == 'switch':
                ports = []
                for intf in node.intfList():
                    if intf.name != 'lo':
                        ports.append({
                            'name': intf.name,
                            'port': getattr(intf, 'port', 'unknown'),
                            'link': getattr(intf, 'link', None) is not None
                        })
                node_info['ports'] = ports
            
            self.topology_data['nodes'].append(node_info)
        
        # Add links
        for link in self.net.links:
            try:
                bw = link.intf1.params.get('bw', 'unknown')
                bw = f"{bw}Mbit" if bw != 'unknown' else bw
            except:
                bw = 'unknown'
                
            self.topology_data['links'].append({
                'source': link.intf1.node.name,
                'target': link.intf2.node.name,
                'bandwidth': bw,
                'status': 'up' if self.is_running else 'down'
            })
        
        # Add basic stats - COUNT ROUTERS SEPARATELY
        router_count = len([node for node in self.net.hosts if isinstance(node, Router) or 
                           (hasattr(node, 'node_type') and node.node_type == 'router')])
        host_count = len(self.net.hosts) - router_count
        
        self.topology_data['stats'] = {
            'hosts': host_count,
            'routers': router_count,  # Add router count
            'switches': len(self.net.switches),
            'links': len(self.net.links),
            'status': 'running' if self.is_running else 'stopped',
            'controller': self.get_controller_status()
        }
    
    def ping_test(self):
        """Run ping test between all hosts"""
        if not self.net or not self.is_running:
            return {'error': 'Network not running'}
        
        try:
            result = self.net.pingAll()
            packet_loss = re.search(r'(\d+)% packet loss', str(result))
            loss_percent = packet_loss.group(1) if packet_loss else '0'
            return {
                'result': f'Ping test completed with {loss_percent}% packet loss',
                'success': True,
                'packet_loss': loss_percent
            }
        except Exception as e:
            return {'error': f'Ping test failed: {str(e)}', 'success': False}
    
    def get_flow_stats(self):
        """Get flow statistics from switches using ovs-ofctl"""
        if not self.net or not self.is_running:
            return {}
        
        flow_stats = {}
        try:
            for switch in self.net.switches:
                try:
                    # Get flow table from switch
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-flows', switch.name],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        flows = result.stdout.strip().split('\n')[1:]  # Skip header
                        flow_stats[switch.name] = {
                            'flow_count': len(flows),
                            'flows': flows[:10]  # Limit to first 10 flows
                        }
                except subprocess.TimeoutExpired:
                    flow_stats[switch.name] = {'error': 'timeout'}
                except Exception as e:
                    flow_stats[switch.name] = {'error': str(e)}
                    
        except Exception as e:
            error(f"Error getting flow stats: {e}")
            
        return flow_stats
    
    def get_network_metrics(self):
        """Get real-time network metrics"""
        if not self.is_running or not self.net:
            return {
                'uptime': '00:00:00',
                'packets_transferred': 0,
                'total_bytes': 0,
                'bandwidth_mbps': 0.0,
                'latency_ms': 0.0,
                'active_flows': 0,
                'total_interfaces': 0
            }
        
        return self.stats_collector.get_network_metrics(self.net)

# Initialize Mininet manager
mininet_mgr = MininetManager()

@app.route('/api/controller/status', methods=['GET'])
def get_controller_status():
    """Get Ryu controller status"""
    status = mininet_mgr.get_controller_status()
    return jsonify(status)

@app.route('/api/controller/start', methods=['POST'])
def start_controller():
    """Start Ryu controller with specified type"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        controller_type = data.get('type', 'simple_switch_13')
        
        # Map frontend names to Ryu app names
        app_mapping = {
            'simple_switch': 'simple_switch_13',
            'learning_switch': 'simple_switch_13',
            'l2_switch': 'simple_switch_13',
            'hub': 'hub',
            'custom': 'simple_switch_13'
        }
        
        ryu_app = app_mapping.get(controller_type, controller_type)
        
        success = mininet_mgr.start_ryu_controller(ryu_app)
        return jsonify({
            'success': success, 
            'message': f'Ryu controller started with {ryu_app}' if success else 'Failed to start controller'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/controller/stop', methods=['POST'])
def stop_controller():
    """Stop Ryu controller"""
    try:
        success = mininet_mgr.stop_ryu_controller()
        return jsonify({'success': success, 'message': 'Ryu controller stopped'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/controller/stats', methods=['GET'])
def get_controller_stats():
    """Get controller statistics and flow information"""
    try:
        controller_stats = mininet_mgr.ryu_controller.get_controller_stats()
        flow_stats = mininet_mgr.get_flow_stats()
        
        return jsonify({
            'controller': controller_stats,
            'flows': flow_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current network status"""
    return jsonify({
        'running': mininet_mgr.is_running,
        'network_exists': mininet_mgr.net is not None,
        'controller': mininet_mgr.get_controller_status()
    })

@app.route('/api/topology', methods=['GET'])
def get_topology():
    """Get current topology data"""
    mininet_mgr._update_topology_data()
    return jsonify(mininet_mgr.topology_data)

@app.route('/api/network/metrics', methods=['GET'])
def get_network_metrics():
    """Get real-time network metrics"""
    try:
        metrics = mininet_mgr.get_network_metrics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/create', methods=['POST'])
def create_network():
    """Create a new network topology"""
    try:
        # Handle both JSON and form data, and allow empty requests
        if request.is_json:
            data = request.get_json() or {}
        elif request.form:
            data = request.form.to_dict() or {}
        else:
            data = {}  # Default to empty dict if no data provided
            
        topology_type = data.get('type', 'simple')
        
        mininet_mgr.stop_network()
        
        if topology_type == 'custom' and 'topology' in data:
            success = mininet_mgr.create_custom_topology(data['topology'])
        else:
            success = mininet_mgr.create_simple_topology()
            
        return jsonify({'success': success, 'message': 'Topology created'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/start', methods=['POST'])
def start_network():
    """Start the network"""
    try:
        success = mininet_mgr.start_network()
        return jsonify({'success': success, 'message': 'Network started' if success else 'Failed to start network'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network/stop', methods=['POST'])
def stop_network():
    """Stop the network"""
    try:
        success = mininet_mgr.stop_network()
        return jsonify({'success': success, 'message': 'Network stopped'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ping', methods=['POST'])
def ping_test():
    """Run ping test"""
    try:
        result = mininet_mgr.ping_test()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/host/<host_id>/cmd', methods=['POST'])
def execute_command(host_id):
    """Execute command on a specific host"""
    try:
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        command = data.get('command', '')
        
        if not command:
            return jsonify({'error': 'No command provided'}), 400
        
        host = mininet_mgr.net.get(host_id)
        if not host:
            return jsonify({'error': f'Host {host_id} not found'}), 404
        
        result = host.cmd(command)
        return jsonify({'result': result.strip(), 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/network/detailed-stats', methods=['GET'])
def get_detailed_network_stats():
    """Get detailed network statistics including interface and OVS stats"""
    try:
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get comprehensive statistics
        metrics = mininet_mgr.get_network_metrics()
        
        # Add additional detailed information
        detailed_stats = {
            'network_metrics': metrics,
            'topology_stats': mininet_mgr.topology_data.get('stats', {}),
            'controller_stats': mininet_mgr.ryu_controller.get_controller_stats(),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(detailed_stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add a simple test endpoint that doesn't require any data
@app.route('/api/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint to verify API is working"""
    return jsonify({'message': 'API is working', 'method': request.method})

def cleanup():
    """Clean up Mininet resources"""
    mininet_mgr.stop_network()
    os.system('mn -c > /dev/null 2>&1')

if __name__ == '__main__':
    import atexit
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Check if running as root
    if os.geteuid() != 0:
        print("*** ERROR: Mininet must run as root ***")
        print("Please run this script with sudo:")
        print("  sudo python mininet_server.py")
        print("  OR")
        print("  sudo /home/ege/anaconda3/envs/sdn-mininet/bin/python mininet_server.py")
        exit(1)
    
    # Check Python environment and Ryu availability
    python_info = subprocess.run(['which', 'python3'], capture_output=True, text=True)
    print(f"Using Python: {python_info.stdout.strip() if python_info.returncode == 0 else 'python3'}")
    
    # Test Ryu availability with the current Python
    ryu_test = subprocess.run([
        sys.executable, '-c', 
        'import ryu.cmd.manager; print("✓ Ryu available")'
    ], capture_output=True, text=True)
    
    if ryu_test.returncode != 0:
        print("*** WARNING: Ryu not available in current Python environment ***")
        print("Checking conda environment...")
        
        conda_python = '/home/ege/anaconda3/envs/sdn-mininet/bin/python'
        if os.path.exists(conda_python):
            conda_ryu_test = subprocess.run([
                conda_python, '-c', 
                'import ryu.cmd.manager; print("✓ Ryu found in conda env")'
            ], capture_output=True, text=True)
            
            if conda_ryu_test.returncode == 0:
                print(f"✓ Found Ryu in conda environment: {conda_python}")
                print("The server will use the conda environment for Ryu operations.")
            else:
                print("*** ERROR: Ryu not found in conda environment either ***")
                print("Please install Ryu:")
                print("  conda activate sdn-mininet")
                print("  pip install ryu")
                exit(1)
        else:
            print("*** ERROR: Conda environment not found ***")
            print("Please install Ryu in your current environment or check conda setup")
            exit(1)
    else:
        print("✓ Ryu available in current environment")
    
    print("\nStarting Enhanced Mininet Web Framework Backend...")
    print("✓ Real network statistics collection enabled")
    print("✓ Router type detection fixed")
    print("✓ Running with root privileges")
    print("API available at http://localhost:5000")
    print("New endpoints:")
    print("  - GET /api/network/metrics - Real-time network metrics")
    print("  - GET /api/network/detailed-stats - Comprehensive statistics")
    print("  - GET /api/topology - Topology with proper router classification")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        setLogLevel('info')
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        cleanup()
        print("Cleanup complete. Goodbye!")