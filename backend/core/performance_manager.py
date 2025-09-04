"""
Network Performance Measurement Manager - Business Logic for Performance Testing
Contains all the helper functions and business logic for measuring network performance.
Follows the configuration manager template structure.
"""

import json
import time
import threading
import subprocess
from datetime import datetime, timedelta
from collections import deque, defaultdict
from flask import request, current_app
import numpy as np
import psutil
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ======================= UTILITY FUNCTIONS =======================

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

def validate_performance_request():
    """Validate performance testing request and setup basic variables"""
    try:
        spec = request.get_json(force=True, silent=False) or {}
        test_type = spec.get('test_type', 'comprehensive')
        validate_only = bool(spec.get('validate_only', False))
        
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return None, None, None, {'error': 'Network not running'}, 400
            
        return spec, test_type, validate_only, mininet_mgr, None
    except Exception as e:
        logger.error(f"Performance request validation error: {e}")
        return None, None, None, {'error': f'Invalid request: {str(e)}'}, 400

def get_available_hosts(mininet_mgr, host_filter=None):
    """Get available hosts for testing, excluding routers"""
    try:
        hosts = [h for h in mininet_mgr.net.hosts if not hasattr(h, 'node_type') or h.node_type != 'router']
        
        if host_filter:
            if isinstance(host_filter, list):
                hosts = [h for h in hosts if h.name in host_filter]
            elif isinstance(host_filter, str):
                hosts = [h for h in hosts if h.name == host_filter]
        
        return hosts
    except Exception as e:
        logger.error(f"Error getting available hosts: {e}")
        return []

def get_host_pairs(hosts, src_host=None, dst_host=None):
    """Generate host pairs for testing"""
    if src_host and dst_host:
        src = next((h for h in hosts if h.name == src_host), None)
        dst = next((h for h in hosts if h.name == dst_host), None)
        if src and dst:
            return [(src, dst)]
        else:
            return []
    else:
        # Generate all pairs
        return [(hosts[i], hosts[j]) for i in range(len(hosts)) 
                for j in range(i+1, len(hosts))]

def check_iperf_availability(host):
    """Check if iperf3 is available on the host"""
    try:
        result = host.cmd('which iperf3')
        return bool(result.strip())
    except:
        return False

def find_available_port(host, start_port=5201, max_attempts=10):
    """Find an available port for iperf testing"""
    for port in range(start_port, start_port + max_attempts):
        try:
            result = host.cmd(f'netstat -ln | grep :{port}')
            if not result.strip():
                return port
        except:
            continue
    return start_port  # Fallback to default

# ======================= TEST PLANNING CLASS =======================

class PerformanceTestPlanner:
    """Manages performance test planning and execution queue"""
    
    def __init__(self):
        self.test_plan = []
        self.results = []
        self.test_metadata = {}
        self.start_time = None
        self.end_time = None
    
    def enqueue_test(self, test_type, src_host, dst_host, params=None, description=None):
        """Add performance test to execution plan"""
        test_item = {
            'test_type': test_type,
            'src_host': src_host,
            'dst_host': dst_host,
            'params': params or {},
            'description': description or f"{test_type} test {src_host} -> {dst_host}"
        }
        self.test_plan.append(test_item)
        logger.debug(f"Enqueued {test_type} test: {src_host} -> {dst_host}")
    
    def get_plan(self):
        """Get the current test execution plan"""
        return self.test_plan
    
    def get_results(self):
        """Get test execution results"""
        return self.results
    
    def add_result(self, result):
        """Add test execution result"""
        result['timestamp'] = datetime.now().isoformat()
        self.results.append(result)
    
    def set_metadata(self, key, value):
        """Set test metadata"""
        self.test_metadata[key] = value
    
    def get_metadata(self):
        """Get test metadata"""
        return self.test_metadata

# ======================= NETWORK STATE INSPECTION FUNCTIONS =======================

def get_current_network_state(mininet_mgr):
    """Get current network state for baseline measurements"""
    state = {
        'hosts': [],
        'links': [],
        'interfaces': {},
        'routing_tables': {},
        'active_processes': {}
    }
    
    try:
        # Get host information
        for host in mininet_mgr.net.hosts:
            host_info = {
                'name': host.name,
                'ip': host.IP() if hasattr(host, 'IP') else 'unknown',
                'interfaces': []
            }
            
            # Get interface information
            for intf in host.intfList():
                if intf.name != 'lo':
                    intf_info = {
                        'name': intf.name,
                        'ip': getattr(intf, 'ip', 'unknown'),
                        'status': 'up' if intf.isUp() else 'down'
                    }
                    host_info['interfaces'].append(intf_info)
            
            state['hosts'].append(host_info)
        
        # Get link information
        for link in mininet_mgr.net.links:
            link_info = {
                'src': link.intf1.node.name,
                'dst': link.intf2.node.name,
                'src_intf': link.intf1.name,
                'dst_intf': link.intf2.name
            }
            state['links'].append(link_info)
            
    except Exception as e:
        logger.error(f"Error getting network state: {e}")
    
    return state

def get_interface_statistics(host, interface):
    """Get interface statistics for performance monitoring"""
    stats = {}
    try:
        # Get RX/TX statistics
        result = host.cmd(f'cat /sys/class/net/{interface}/statistics/rx_bytes 2>/dev/null')
        if result.strip():
            stats['rx_bytes'] = int(result.strip())
        
        result = host.cmd(f'cat /sys/class/net/{interface}/statistics/tx_bytes 2>/dev/null')
        if result.strip():
            stats['tx_bytes'] = int(result.strip())
        
        result = host.cmd(f'cat /sys/class/net/{interface}/statistics/rx_packets 2>/dev/null')
        if result.strip():
            stats['rx_packets'] = int(result.strip())
        
        result = host.cmd(f'cat /sys/class/net/{interface}/statistics/tx_packets 2>/dev/null')
        if result.strip():
            stats['tx_packets'] = int(result.strip())
            
    except Exception as e:
        logger.warning(f"Error getting interface statistics for {interface}: {e}")
    
    return stats

def check_network_prerequisites(mininet_mgr):
    """Check network prerequisites for performance testing"""
    prerequisites = {
        'network_running': False,
        'hosts_available': 0,
        'iperf3_available': 0,
        'ping_available': 0,
        'issues': [],
        'recommendations': []
    }
    
    try:
        # Check if network is running
        if mininet_mgr.net and mininet_mgr.is_running:
            prerequisites['network_running'] = True
        else:
            prerequisites['issues'].append('Network is not running')
            prerequisites['recommendations'].append('Start the network before testing')
            return prerequisites
        
        # Check available hosts
        hosts = get_available_hosts(mininet_mgr)
        prerequisites['hosts_available'] = len(hosts)
        
        if len(hosts) < 2:
            prerequisites['issues'].append('Need at least 2 hosts for performance testing')
            prerequisites['recommendations'].append('Create a topology with multiple hosts')
        
        # Check tool availability
        for host in hosts:
            if check_iperf_availability(host):
                prerequisites['iperf3_available'] += 1
            
            try:
                result = host.cmd('which ping')
                if result.strip():
                    prerequisites['ping_available'] += 1
            except:
                pass
        
        # Check for missing tools
        if prerequisites['iperf3_available'] == 0:
            prerequisites['issues'].append('iperf3 not available on any host')
            prerequisites['recommendations'].append('Install iperf3: apt-get install iperf3')
        
        if prerequisites['ping_available'] == 0:
            prerequisites['issues'].append('ping not available on any host')
            prerequisites['recommendations'].append('Install ping utilities')
            
    except Exception as e:
        prerequisites['issues'].append(f'Error checking prerequisites: {e}')
    
    return prerequisites

# ======================= BANDWIDTH TESTING FUNCTIONS =======================

def process_bandwidth_test(planner, src_host, dst_host, duration=30, parallel_streams=1):
    """Generate bandwidth test configuration"""
    test_params = {
        'duration': duration,
        'parallel_streams': parallel_streams,
        'protocol': 'tcp'
    }
    
    planner.enqueue_test(
        'bandwidth',
        src_host.name,
        dst_host.name,
        test_params,
        f"Bandwidth test {src_host.name} -> {dst_host.name} ({duration}s, {parallel_streams} streams)"
    )

def execute_bandwidth_test(src_host, dst_host, params):
    """Execute bandwidth test using iperf3"""
    duration = params.get('duration', 30)
    parallel_streams = params.get('parallel_streams', 1)
    protocol = params.get('protocol', 'tcp')
    
    try:
        # Find available port
        port = find_available_port(dst_host)
        
        # Start iperf3 server
        server_cmd = f'iperf3 -s -p {port} -1 -D'
        dst_host.cmd(server_cmd)
        
        # Wait for server to start
        time.sleep(0.5)
        
        # Build client command
        client_cmd = f'iperf3 -c {dst_host.IP()} -p {port} -t {duration} -P {parallel_streams} -J'
        if protocol == 'udp':
            client_cmd += ' -u'
        
        # Execute client test
        result = src_host.cmd(client_cmd)
        
        # Kill server
        dst_host.cmd(f'pkill -f "iperf3.*-p {port}"')
        
        # Parse results
        return parse_bandwidth_results(result, params)
        
    except Exception as e:
        logger.error(f"Bandwidth test execution failed: {e}")
        return {'error': f'Bandwidth test failed: {e}'}

def parse_bandwidth_results(iperf_output, params):
    """Parse iperf3 output for bandwidth results"""
    try:
        # Try to parse JSON output
        data = json.loads(iperf_output)
        
        result = {
            'bandwidth_mbps': data['end']['sum_received']['bits_per_second'] / 1e6,
            'throughput_mbps': data['end']['sum_sent']['bits_per_second'] / 1e6,
            'retransmissions': data['end']['sum_sent'].get('retransmits', 0),
            'parallel_streams': len(data['end']['streams']),
            'test_duration': data['end']['sum_received']['seconds'],
            'protocol': params.get('protocol', 'tcp'),
            'success': True
        }
        
        # Add CPU utilization if available
        if 'cpu_utilization_percent' in data['end']:
            result['cpu_utilization'] = {
                'local': data['end']['cpu_utilization_percent'].get('host_total', 0),
                'remote': data['end']['cpu_utilization_percent'].get('remote_total', 0)
            }
        
        return result
        
    except json.JSONDecodeError:
        # Fallback to text parsing
        try:
            lines = iperf_output.split('\n')
            for line in lines:
                if 'receiver' in line and ('Mbits/sec' in line or 'Gbits/sec' in line):
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'bits/sec' in part:
                            value = float(parts[i-1])
                            if 'Gbits/sec' in part:
                                value *= 1000
                            return {
                                'bandwidth_mbps': value,
                                'success': True,
                                'protocol': params.get('protocol', 'tcp')
                            }
            
            return {'error': 'Could not parse bandwidth result', 'success': False}
            
        except Exception as e:
            return {'error': f'Failed to parse bandwidth result: {e}', 'success': False}

# ======================= LATENCY TESTING FUNCTIONS =======================

def process_latency_test(planner, src_host, dst_host, count=100, interval=0.1):
    """Generate latency test configuration"""
    test_params = {
        'count': count,
        'interval': interval
    }
    
    planner.enqueue_test(
        'latency',
        src_host.name,
        dst_host.name,
        test_params,
        f"Latency test {src_host.name} -> {dst_host.name} ({count} packets)"
    )

def execute_latency_test(src_host, dst_host, params):
    """Execute latency test using ping"""
    count = params.get('count', 100)
    interval = params.get('interval', 0.1)
    
    try:
        # Execute ping command
        cmd = f'ping -c {count} -i {interval} {dst_host.IP()}'
        result = src_host.cmd(cmd)
        
        # Parse results
        return parse_latency_results(result, params)
        
    except Exception as e:
        logger.error(f"Latency test execution failed: {e}")
        return {'error': f'Latency test failed: {e}'}

def parse_latency_results(ping_output, params):
    """Parse ping output for latency statistics"""
    try:
        lines = ping_output.split('\n')
        latencies = []
        packet_loss = 0
        
        # Extract individual latency measurements
        for line in lines:
            if 'time=' in line:
                try:
                    time_part = line.split('time=')[1].split()[0]
                    latency = float(time_part.replace('ms', ''))
                    latencies.append(latency)
                except:
                    continue
        
        # Extract packet loss percentage
        for line in lines:
            if 'packet loss' in line:
                try:
                    loss_str = line.split(',')[2].strip()
                    packet_loss = float(loss_str.split('%')[0])
                except:
                    pass
        
        if latencies:
            latencies = np.array(latencies)
            result = {
                'min_ms': float(np.min(latencies)),
                'max_ms': float(np.max(latencies)),
                'mean_ms': float(np.mean(latencies)),
                'median_ms': float(np.median(latencies)),
                'std_dev_ms': float(np.std(latencies)),
                'percentile_95_ms': float(np.percentile(latencies, 95)),
                'percentile_99_ms': float(np.percentile(latencies, 99)),
                'packet_loss_percent': packet_loss,
                'samples': len(latencies),
                'success': True,
                'distribution': {
                    '0-1ms': int(np.sum((latencies >= 0) & (latencies < 1))),
                    '1-5ms': int(np.sum((latencies >= 1) & (latencies < 5))),
                    '5-10ms': int(np.sum((latencies >= 5) & (latencies < 10))),
                    '10ms+': int(np.sum(latencies >= 10))
                }
            }
            return result
        else:
            return {
                'error': 'No valid latency measurements',
                'packet_loss_percent': 100,
                'success': False
            }
            
    except Exception as e:
        return {'error': f'Failed to parse latency result: {e}', 'success': False}

# ======================= JITTER TESTING FUNCTIONS =======================

def process_jitter_test(planner, src_host, dst_host, duration=30, bandwidth='10M'):
    """Generate jitter test configuration"""
    test_params = {
        'duration': duration,
        'bandwidth': bandwidth,
        'protocol': 'udp'
    }
    
    planner.enqueue_test(
        'jitter',
        src_host.name,
        dst_host.name,
        test_params,
        f"Jitter test {src_host.name} -> {dst_host.name} (UDP, {duration}s)"
    )

def execute_jitter_test(src_host, dst_host, params):
    """Execute jitter test using iperf3 UDP"""
    duration = params.get('duration', 30)
    bandwidth = params.get('bandwidth', '10M')
    
    try:
        # Find available port
        port = find_available_port(dst_host, 5210)
        
        # Start iperf3 server for UDP
        server_cmd = f'iperf3 -s -p {port} -1 -D'
        dst_host.cmd(server_cmd)
        
        # Wait for server to start
        time.sleep(0.5)
        
        # Execute UDP client test
        client_cmd = f'iperf3 -c {dst_host.IP()} -p {port} -u -t {duration} -b {bandwidth} -J'
        result = src_host.cmd(client_cmd)
        
        # Kill server
        dst_host.cmd(f'pkill -f "iperf3.*-p {port}"')
        
        # Parse results
        return parse_jitter_results(result, params)
        
    except Exception as e:
        logger.error(f"Jitter test execution failed: {e}")
        return {'error': f'Jitter test failed: {e}'}

def parse_jitter_results(iperf_output, params):
    """Parse iperf3 UDP output for jitter results"""
    try:
        data = json.loads(iperf_output)
        
        result = {
            'jitter_ms': data['end']['sum']['jitter_ms'],
            'lost_packets': data['end']['sum']['lost_packets'],
            'total_packets': data['end']['sum']['packets'],
            'lost_percent': data['end']['sum']['lost_percent'],
            'out_of_order': data['end']['sum'].get('out_of_order', 0),
            'bandwidth_mbps': data['end']['sum']['bits_per_second'] / 1e6,
            'success': True,
            'protocol': 'udp'
        }
        
        return result
        
    except json.JSONDecodeError:
        return {'error': 'Could not parse jitter result', 'success': False}
    except Exception as e:
        return {'error': f'Failed to parse jitter result: {e}', 'success': False}

# ======================= PACKET LOSS TESTING FUNCTIONS =======================

def process_packet_loss_test(planner, src_host, dst_host, test_patterns=None):
    """Generate packet loss test configuration"""
    if test_patterns is None:
        test_patterns = ['normal', 'burst', 'random']
    
    test_params = {
        'patterns': test_patterns
    }
    
    planner.enqueue_test(
        'packet_loss',
        src_host.name,
        dst_host.name,
        test_params,
        f"Packet loss test {src_host.name} -> {dst_host.name} ({len(test_patterns)} patterns)"
    )

def execute_packet_loss_test(src_host, dst_host, params):
    """Execute packet loss test with different patterns"""
    patterns = params.get('patterns', ['normal', 'burst', 'random'])
    results = {}
    
    for pattern in patterns:
        try:
            if pattern == 'normal':
                # Standard ping test
                cmd = f'ping -c 100 -i 0.1 {dst_host.IP()}'
            elif pattern == 'burst':
                # Burst ping test (flood ping for short duration)
                cmd = f'ping -c 50 -f {dst_host.IP()}'
            elif pattern == 'random':
                # Random interval ping
                cmd = f'ping -c 100 {dst_host.IP()}'
            else:
                continue
            
            result = src_host.cmd(cmd)
            
            # Parse packet loss
            loss_percent = 0
            if 'packet loss' in result:
                try:
                    loss_line = [l for l in result.split('\n') if 'packet loss' in l][0]
                    loss_percent = float(loss_line.split(',')[2].strip().split('%')[0])
                except:
                    pass
            
            results[pattern] = {
                'packet_loss_percent': loss_percent,
                'pattern': pattern,
                'success': True
            }
            
        except Exception as e:
            results[pattern] = {
                'error': f'Pattern {pattern} test failed: {e}',
                'success': False
            }
    
    return {
        'patterns': results,
        'success': len(results) > 0
    }

# ======================= COMPREHENSIVE TESTING FUNCTIONS =======================

def process_comprehensive_test(planner, src_host, dst_host, test_types=None, duration=30):
    """Generate comprehensive test configuration"""
    if test_types is None:
        test_types = ['bandwidth', 'latency', 'jitter', 'packet_loss']
    
    # Add each test type to the plan
    if 'bandwidth' in test_types:
        process_bandwidth_test(planner, src_host, dst_host, duration)
    
    if 'latency' in test_types:
        process_latency_test(planner, src_host, dst_host, count=min(1000, duration * 10))
    
    if 'jitter' in test_types:
        process_jitter_test(planner, src_host, dst_host, duration=min(30, duration))
    
    if 'packet_loss' in test_types:
        process_packet_loss_test(planner, src_host, dst_host)

# ======================= STRESS TESTING FUNCTIONS =======================

def process_stress_test(planner, hosts, concurrent_flows=10, duration=300, flow_size='100M'):
    """Generate stress test configuration"""
    if len(hosts) < 2:
        logger.warning("Need at least 2 hosts for stress testing")
        return
    
    # Create multiple concurrent flows
    for i in range(concurrent_flows):
        src = hosts[i % len(hosts)]
        dst = hosts[(i + 1) % len(hosts)]
        
        test_params = {
            'duration': duration,
            'flow_size': flow_size,
            'concurrent_id': i,
            'total_flows': concurrent_flows
        }
        
        planner.enqueue_test(
            'stress_flow',
            src.name,
            dst.name,
            test_params,
            f"Stress flow {i+1}/{concurrent_flows}: {src.name} -> {dst.name}"
        )

def execute_stress_flow(src_host, dst_host, params):
    """Execute individual stress test flow"""
    duration = params.get('duration', 300)
    flow_size = params.get('flow_size', '100M')
    concurrent_id = params.get('concurrent_id', 0)
    
    try:
        # Use unique port for each flow
        port = 5220 + concurrent_id
        
        # Start iperf3 server with specific port
        server_cmd = f'iperf3 -s -p {port} -1 -D'
        dst_host.cmd(server_cmd)
        
        # Wait for server to start
        time.sleep(0.1)
        
        # Execute client test
        client_cmd = f'iperf3 -c {dst_host.IP()} -p {port} -t {duration} -J'
        result = src_host.cmd(client_cmd)
        
        # Parse results
        try:
            data = json.loads(result)
            return {
                'bandwidth_mbps': data['end']['sum_received']['bits_per_second'] / 1e6,
                'bytes_transferred': data['end']['sum_received']['bytes'],
                'retransmissions': data['end']['sum_sent'].get('retransmits', 0),
                'test_duration': data['end']['sum_received']['seconds'],
                'concurrent_id': concurrent_id,
                'success': True
            }
        except json.JSONDecodeError:
            return {
                'error': 'Failed to parse stress flow output',
                'concurrent_id': concurrent_id,
                'success': False
            }
            
    except Exception as e:
        return {
            'error': f'Stress flow failed: {e}',
            'concurrent_id': concurrent_id,
            'success': False
        }
    finally:
        # Cleanup server process
        try:
            dst_host.cmd(f'pkill -f "iperf3.*-p {port}"')
        except:
            pass

# ======================= TEST EXECUTION FUNCTIONS =======================

def execute_test_plan(planner, mininet_mgr):
    """Execute all tests in the plan"""
    logger.info(f"Executing test plan with {len(planner.get_plan())} tests")
    
    planner.start_time = datetime.now()
    
    for test_item in planner.get_plan():
        test_type = test_item['test_type']
        src_name = test_item['src_host']
        dst_name = test_item['dst_host']
        params = test_item['params']
        
        # Get host objects
        try:
            src_host = mininet_mgr.net.get(src_name)
            dst_host = mininet_mgr.net.get(dst_name)
        except Exception as e:
            planner.add_result({
                'test_type': test_type,
                'src_host': src_name,
                'dst_host': dst_name,
                'success': False,
                'error': f'Failed to get host objects: {e}',
                'description': test_item.get('description', 'Unknown test')
            })
            continue
        
        # Execute the appropriate test
        try:
            logger.debug(f"Executing {test_type} test: {src_name} -> {dst_name}")
            
            if test_type == 'bandwidth':
                result = execute_bandwidth_test(src_host, dst_host, params)
            elif test_type == 'latency':
                result = execute_latency_test(src_host, dst_host, params)
            elif test_type == 'jitter':
                result = execute_jitter_test(src_host, dst_host, params)
            elif test_type == 'packet_loss':
                result = execute_packet_loss_test(src_host, dst_host, params)
            elif test_type == 'stress_flow':
                result = execute_stress_flow(src_host, dst_host, params)
            else:
                result = {'error': f'Unknown test type: {test_type}', 'success': False}
            
            # Add test metadata to result
            result.update({
                'test_type': test_type,
                'src_host': src_name,
                'dst_host': dst_name,
                'description': test_item.get('description', 'Unknown test')
            })
            
            planner.add_result(result)
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            planner.add_result({
                'test_type': test_type,
                'src_host': src_name,
                'dst_host': dst_name,
                'success': False,
                'error': str(e),
                'description': test_item.get('description', 'Unknown test')
            })
    
    planner.end_time = datetime.now()

def calculate_test_summary(planner):
    """Calculate test execution summary statistics"""
    results = planner.get_results()
    
    successful = len([r for r in results if r.get('success', False)])
    failed = len([r for r in results if not r.get('success', False)])
    
    # Calculate type-specific statistics
    type_stats = {}
    for result in results:
        test_type = result.get('test_type', 'unknown')
        if test_type not in type_stats:
            type_stats[test_type] = {'total': 0, 'successful': 0, 'failed': 0}
        
        type_stats[test_type]['total'] += 1
        if result.get('success', False):
            type_stats[test_type]['successful'] += 1
        else:
            type_stats[test_type]['failed'] += 1
    
    # Calculate duration
    duration = 0
    if planner.start_time and planner.end_time:
        duration = (planner.end_time - planner.start_time).total_seconds()
    
    return {
        'total_tests': len(results),
        'successful': successful,
        'failed': failed,
        'duration_seconds': duration,
        'type_statistics': type_stats,
        'start_time': planner.start_time.isoformat() if planner.start_time else None,
        'end_time': planner.end_time.isoformat() if planner.end_time else None
    }

# ======================= REAL-TIME MONITORING FUNCTIONS =======================

class RealTimeMonitor:
    """Real-time network performance monitoring"""
    
    def __init__(self, mininet_mgr):
        self.mininet_mgr = mininet_mgr
        self.monitoring_active = False
        self.performance_history = defaultdict(deque)
        self.monitoring_thread = None
        self.monitor_interval = 30
    
    def start_monitoring(self, interval=30, hosts=None):
        """Start real-time monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return False
        
        self.monitor_interval = interval
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(hosts,),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"Started real-time monitoring with {interval}s interval")
        return True
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Stopped real-time monitoring")
    
    def _monitoring_loop(self, hosts):
        """Real-time monitoring loop"""
        if not hosts:
            hosts = [h.name for h in get_available_hosts(self.mininet_mgr)]
        
        while self.monitoring_active:
            try:
                timestamp = datetime.now()
                
                # Monitor key metrics for each host pair
                for i, src_name in enumerate(hosts):
                    for dst_name in hosts[i+1:]:
                        try:
                            src = self.mininet_mgr.net.get(src_name)
                            dst = self.mininet_mgr.net.get(dst_name)
                            
                            if src and dst:
                                # Quick measurements
                                metrics = {
                                    'timestamp': timestamp.isoformat(),
                                    'latency_ms': self._quick_latency_check(src, dst),
                                    'connectivity': self._connectivity_check(src, dst)
                                }
                                
                                # Store in history
                                pair_key = f"{src_name}->{dst_name}"
                                self.performance_history[pair_key].append(metrics)
                                
                                # Keep only last 100 measurements
                                if len(self.performance_history[pair_key]) > 100:
                                    self.performance_history[pair_key].popleft()
                        
                        except Exception as e:
                            logger.warning(f"Monitoring error for {src_name}->{dst_name}: {e}")
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitor_interval)
    
    def _quick_latency_check(self, src, dst):
        """Quick latency measurement"""
        try:
            result = src.cmd(f'ping -c 1 -W 1 {dst.IP()}')
            if 'time=' in result:
                time_part = result.split('time=')[1].split()[0]
                return float(time_part.replace('ms', ''))
        except:
            pass
        return None
    
    def _connectivity_check(self, src, dst):
        """Check basic connectivity"""
        try:
            result = src.cmd(f'ping -c 1 -W 1 {dst.IP()}')
            return '1 received' in result
        except:
            return False
    
    def get_current_metrics(self):
        """Get current real-time metrics"""
        if not self.monitoring_active:
            return {'error': 'Real-time monitoring not active'}
        
        latest_metrics = {}
        for pair_key, history in self.performance_history.items():
            if history:
                latest_metrics[pair_key] = history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'monitoring_active': self.monitoring_active,
            'monitor_interval': self.monitor_interval,
            'metrics': latest_metrics
        }
    
    def get_history(self, pair_key=None, limit=None):
        """Get historical monitoring data"""
        if pair_key:
            history = list(self.performance_history.get(pair_key, []))
            if limit:
                history = history[-limit:]
            return {pair_key: history}
        else:
            result = {}
            for key, history in self.performance_history.items():
                history_list = list(history)
                if limit:
                    history_list = history_list[-limit:]
                result[key] = history_list
            return result

# ======================= REPORT GENERATION FUNCTIONS =======================

def generate_performance_report(test_results, format='json', include_analysis=True):
    """Generate comprehensive performance report"""
    try:
        if not test_results:
            return {'message': 'No performance data available', 'data': []}
        
        # Organize results by test type and host pairs
        organized_results = {}
        for result in test_results:
            test_type = result.get('test_type', 'unknown')
            pair_key = f"{result.get('src_host', 'unknown')}->{result.get('dst_host', 'unknown')}"
            
            if pair_key not in organized_results:
                organized_results[pair_key] = {}
            
            organized_results[pair_key][test_type] = result
        
        # Generate summary statistics
        summary = {
            'total_tests': len(test_results),
            'successful_tests': len([r for r in test_results if r.get('success', False)]),
            'failed_tests': len([r for r in test_results if not r.get('success', False)]),
            'host_pairs_tested': len(organized_results),
            'test_types': list(set(r.get('test_type', 'unknown') for r in test_results))
        }
        
        report = {
            'summary': summary,
            'detailed_results': organized_results,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add analysis if requested
        if include_analysis:
            analysis = analyze_performance_results(test_results)
            report['analysis'] = analysis
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        return {'error': f'Report generation failed: {e}'}

def analyze_performance_results(test_results):
    """Analyze performance test results for insights"""
    analysis = {
        'performance_issues': [],
        'recommendations': [],
        'statistics': {}
    }
    
    try:
        # Analyze bandwidth results
        bandwidth_results = [r for r in test_results if r.get('test_type') == 'bandwidth' and r.get('success')]
        if bandwidth_results:
            bandwidths = [r.get('bandwidth_mbps', 0) for r in bandwidth_results]
            analysis['statistics']['bandwidth'] = {
                'mean': np.mean(bandwidths),
                'min': np.min(bandwidths),
                'max': np.max(bandwidths),
                'std': np.std(bandwidths)
            }
            
            # Check for low bandwidth
            if np.mean(bandwidths) < 1:
                analysis['performance_issues'].append('Low average bandwidth detected')
                analysis['recommendations'].append('Check link capacity and network congestion')
        
        # Analyze latency results
        latency_results = [r for r in test_results if r.get('test_type') == 'latency' and r.get('success')]
        if latency_results:
            mean_latencies = [r.get('mean_ms', 0) for r in latency_results]
            analysis['statistics']['latency'] = {
                'mean': np.mean(mean_latencies),
                'min': np.min(mean_latencies),
                'max': np.max(mean_latencies),
                'std': np.std(mean_latencies)
            }
            
            # Check for high latency
            if np.mean(mean_latencies) > 100:
                analysis['performance_issues'].append('High average latency detected')
                analysis['recommendations'].append('Check routing paths and network delays')
        
        # Analyze packet loss
        loss_results = [r for r in test_results if r.get('test_type') == 'packet_loss' and r.get('success')]
        if loss_results:
            loss_rates = []
            for result in loss_results:
                patterns = result.get('patterns', {})
                for pattern_data in patterns.values():
                    if pattern_data.get('success'):
                        loss_rates.append(pattern_data.get('packet_loss_percent', 0))
            
            if loss_rates:
                analysis['statistics']['packet_loss'] = {
                    'mean': np.mean(loss_rates),
                    'max': np.max(loss_rates)
                }
                
                # Check for packet loss issues
                if np.max(loss_rates) > 5:
                    analysis['performance_issues'].append('High packet loss detected')
                    analysis['recommendations'].append('Investigate network congestion and errors')
        
        # General recommendations based on overall results
        failed_tests = len([r for r in test_results if not r.get('success', False)])
        if failed_tests > 0:
            analysis['performance_issues'].append(f'{failed_tests} tests failed to execute')
            analysis['recommendations'].append('Check network configuration and tool availability')
    
    except Exception as e:
        logger.error(f"Error analyzing performance results: {e}")
        analysis['analysis_error'] = str(e)
    
    return analysis

# ======================= MAIN PERFORMANCE MANAGER CLASS =======================

class NetworkPerformanceManager:
    """Main class for managing network performance testing"""
    
    def __init__(self, mininet_mgr):
        self.mininet_mgr = mininet_mgr
        self.real_time_monitor = RealTimeMonitor(mininet_mgr)
        self.test_history = deque(maxlen=100)  # Keep last 100 test sessions
        self.logger = logger
    
    def run_comprehensive_test(self, src_host=None, dst_host=None, duration=30, test_types=None):
        """Run comprehensive performance test"""
        planner = PerformanceTestPlanner()
        
        try:
            # Check prerequisites
            prereqs = check_network_prerequisites(self.mininet_mgr)
            if prereqs['issues']:
                return {
                    'error': 'Prerequisites not met',
                    'issues': prereqs['issues'],
                    'recommendations': prereqs['recommendations']
                }
            
            # Get hosts for testing
            hosts = get_available_hosts(self.mininet_mgr)
            host_pairs = get_host_pairs(hosts, src_host, dst_host)
            
            if not host_pairs:
                return {'error': 'No valid host pairs for testing'}
            
            # Set test metadata
            planner.set_metadata('test_session_id', f"session_{int(time.time())}")
            planner.set_metadata('duration', duration)
            planner.set_metadata('test_types', test_types or ['bandwidth', 'latency', 'jitter', 'packet_loss'])
            
            # Generate test plan
            for src, dst in host_pairs:
                process_comprehensive_test(planner, src, dst, test_types, duration)
            
            # Execute tests
            execute_test_plan(planner, self.mininet_mgr)
            
            # Generate summary
            summary = calculate_test_summary(planner)
            
            # Store in history
            test_session = {
                'metadata': planner.get_metadata(),
                'results': planner.get_results(),
                'summary': summary
            }
            self.test_history.append(test_session)
            
            return {
                'success': True,
                'metadata': planner.get_metadata(),
                'results': planner.get_results(),
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"Comprehensive test failed: {e}")
            return {'error': f'Comprehensive test failed: {e}'}
    
    def run_stress_test(self, duration=300, concurrent_flows=10, flow_size='100M'):
        """Run network stress test"""
        planner = PerformanceTestPlanner()
        
        try:
            # Check prerequisites
            prereqs = check_network_prerequisites(self.mininet_mgr)
            if prereqs['issues']:
                return {
                    'error': 'Prerequisites not met',
                    'issues': prereqs['issues'],
                    'recommendations': prereqs['recommendations']
                }
            
            # Get hosts for testing
            hosts = get_available_hosts(self.mininet_mgr)
            if len(hosts) < 2:
                return {'error': 'Need at least 2 hosts for stress testing'}
            
            # Set test metadata
            planner.set_metadata('test_type', 'stress_test')
            planner.set_metadata('concurrent_flows', concurrent_flows)
            planner.set_metadata('duration', duration)
            planner.set_metadata('flow_size', flow_size)
            
            # Generate stress test plan
            process_stress_test(planner, hosts, concurrent_flows, duration, flow_size)
            
            # Execute tests
            execute_test_plan(planner, self.mininet_mgr)
            
            # Calculate aggregate statistics
            results = planner.get_results()
            successful_flows = [r for r in results if r.get('success', False)]
            
            aggregate_stats = {}
            if successful_flows:
                total_bandwidth = sum(r.get('bandwidth_mbps', 0) for r in successful_flows)
                total_retransmissions = sum(r.get('retransmissions', 0) for r in successful_flows)
                
                aggregate_stats = {
                    'total_bandwidth_mbps': total_bandwidth,
                    'average_bandwidth_mbps': total_bandwidth / len(successful_flows),
                    'total_retransmissions': total_retransmissions,
                    'successful_flows': len(successful_flows),
                    'failed_flows': len(results) - len(successful_flows)
                }
            
            # Generate summary
            summary = calculate_test_summary(planner)
            summary['aggregate_stats'] = aggregate_stats
            
            # Store in history
            test_session = {
                'metadata': planner.get_metadata(),
                'results': results,
                'summary': summary
            }
            self.test_history.append(test_session)
            
            return {
                'success': True,
                'metadata': planner.get_metadata(),
                'results': results,
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"Stress test failed: {e}")
            return {'error': f'Stress test failed: {e}'}
    
    def start_real_time_monitoring(self, interval=30, hosts=None):
        """Start real-time monitoring"""
        return self.real_time_monitor.start_monitoring(interval, hosts)
    
    def stop_real_time_monitoring(self):
        """Stop real-time monitoring"""
        return self.real_time_monitor.stop_monitoring()
    
    def get_real_time_metrics(self):
        """Get current real-time metrics"""
        return self.real_time_monitor.get_current_metrics()
    
    def get_test_history(self, limit=None):
        """Get test history"""
        history = list(self.test_history)
        if limit:
            history = history[-limit:]
        return history
    
    def generate_report(self, session_id=None, format='json', include_analysis=True):
        """Generate performance report"""
        try:
            if session_id:
                # Find specific session
                session = next((s for s in self.test_history if s['metadata'].get('test_session_id') == session_id), None)
                if not session:
                    return {'error': f'Session {session_id} not found'}
                test_results = session['results']
            else:
                # Use latest session
                if not self.test_history:
                    return {'error': 'No test history available'}
                test_results = self.test_history[-1]['results']
            
            return generate_performance_report(test_results, format, include_analysis)
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return {'error': f'Report generation failed: {e}'}
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_real_time_monitoring()