"""
Network Statistics Collector - Real-time network metrics
"""

import os
import re
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

from utils.logger import setup_logger

logger = setup_logger(__name__)

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
        self.previous_bytes = 0
        
    def start_collection(self):
        """Start collecting network statistics"""
        self.start_time = datetime.now()
        self.last_collection_time = datetime.now()
        logger.info("Started network statistics collection")
        
    def stop_collection(self):
        """Stop collecting network statistics"""
        self.start_time = None
        self.stats_history.clear()
        self.interface_stats.clear()
        self.flow_stats.clear()
        self.packet_counters.clear()
        self.byte_counters.clear()
        logger.info("Stopped network statistics collection")
        
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
            logger.error(f"Error collecting interface stats: {e}")
            
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
                                
                                # Extract match fields
                                if 'in_port=' in line:
                                    port_match = re.search(r'in_port=(\d+)', line)
                                    if port_match:
                                        flow_info['in_port'] = int(port_match.group(1))
                                
                                flows.append(flow_info)
                        
                        switch_stats['flows'] = flows
                        switch_stats['total_packets'] = total_packets
                        switch_stats['total_bytes'] = total_bytes
                        switch_stats['flow_count'] = len(flows)
                        
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
            logger.error(f"Error collecting OVS stats: {e}")
            
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
            hosts = [h for h in net.hosts if not hasattr(h, 'node_type') or h.node_type != 'router']
            if len(hosts) < 2:
                return 0.0
                
            host1 = hosts[0]
            host2 = hosts[1] if len(hosts) > 1 else hosts[0]
            
            if host1 == host2:
                return 0.0
            
            # Run ping with single packet and parse latency
            result = host1.cmd(f'ping -c 1 -W 1 {host2.IP()}')
            
            # Parse latency from ping output
            latency_match = re.search(r'time=(\d+\.?\d*)', result)
            if latency_match:
                return float(latency_match.group(1))
                
        except Exception as e:
            logger.error(f"Error measuring latency: {e}")
            
        return 0.0
    
    def get_network_utilization(self, interface_stats):
        """Calculate network utilization percentage"""
        if not interface_stats:
            return 0.0
        
        total_bytes = 0
        total_capacity = 0
        
        for node_name, interfaces in interface_stats.items():
            for intf_name, stats in interfaces.items():
                total_bytes += stats.get('rx_bytes', 0) + stats.get('tx_bytes', 0)
                # Assume 10Mbps per interface (can be enhanced with actual link capacity)
                total_capacity += 10 * 1024 * 1024  # 10 Mbps in bytes per second
        
        if total_capacity == 0:
            return 0.0
        
        # Calculate utilization based on time since collection started
        if self.start_time:
            time_diff = (datetime.now() - self.start_time).total_seconds()
            if time_diff > 0:
                utilization = (total_bytes / time_diff) / total_capacity * 100
                return min(utilization, 100.0)  # Cap at 100%
        
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
        
        # Add interface bytes to total
        interface_bytes = 0
        for node_stats in interface_stats.values():
            for intf_stats in node_stats.values():
                interface_bytes += intf_stats.get('rx_bytes', 0) + intf_stats.get('tx_bytes', 0)
        
        total_bytes = max(total_bytes, interface_bytes)
        
        # Calculate bandwidth if we have previous data
        bandwidth = 0.0
        if self.last_collection_time and hasattr(self, 'previous_bytes'):
            time_diff = (current_time - self.last_collection_time).total_seconds()
            bandwidth = self.calculate_bandwidth(total_bytes, self.previous_bytes, time_diff)
        
        # Store current bytes for next calculation
        self.previous_bytes = total_bytes
        self.last_collection_time = current_time
        
        # Measure latency
        #latency = self.measure_latency(net)
        
        # Calculate additional metrics
        total_interfaces = sum(len(node_stats) for node_stats in interface_stats.values())
        active_flows = sum(switch_stats.get('flow_count', 0) for switch_stats in ovs_stats.values())
        
        # Network utilization
        utilization = self.get_network_utilization(interface_stats)
        
        # Error counts
        total_errors = 0
        total_dropped = 0
        for node_stats in interface_stats.values():
            for intf_stats in node_stats.values():
                total_errors += intf_stats.get('rx_errors', 0) + intf_stats.get('tx_errors', 0)
                total_dropped += intf_stats.get('rx_dropped', 0) + intf_stats.get('tx_dropped', 0)
        
        metrics = {
            'uptime': self.get_uptime(),
            'packets_transferred': total_packets,
            'total_bytes': total_bytes,
            'bandwidth_mbps': bandwidth,
            #'latency_ms': latency,
            'active_flows': active_flows,
            'total_interfaces': total_interfaces,
            'network_utilization': round(utilization, 2),
            'total_errors': total_errors,
            'total_dropped': total_dropped,
            'interface_stats': interface_stats,
            'ovs_stats': ovs_stats,
            'timestamp': current_time.isoformat()
        }
        
        # Store in history (keep last 100 entries)
        self.stats_history['metrics'].append(metrics)
        if len(self.stats_history['metrics']) > 100:
            self.stats_history['metrics'].pop(0)
            
        return metrics
    
    def get_historical_data(self, minutes=10):
        """Get historical metrics for the last N minutes"""
        if not self.stats_history['metrics']:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        historical_data = []
        for metric in self.stats_history['metrics']:
            metric_time = datetime.fromisoformat(metric['timestamp'])
            if metric_time >= cutoff_time:
                historical_data.append({
                    'timestamp': metric['timestamp'],
                    'bandwidth_mbps': metric['bandwidth_mbps'],
                    'latency_ms': metric['latency_ms'],
                    'packets_transferred': metric['packets_transferred'],
                    'active_flows': metric['active_flows'],
                    'network_utilization': metric.get('network_utilization', 0)
                })
        
        return historical_data
    
    def reset_stats(self):
        """Reset all statistics"""
        self.stats_history.clear()
        self.interface_stats.clear()
        self.flow_stats.clear()
        self.packet_counters.clear()
        self.byte_counters.clear()
        self.previous_bytes = 0
        logger.info("Network statistics reset")