"""
Network Monitor
Handles statistics collection, monitoring, diagnostics, and network metrics
"""

import os
import time
import socket
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from utils.logger import setup_logger

logger = setup_logger(__name__)


class NetworkMonitor:
    """Monitors network statistics, diagnostics, and performance metrics"""

    def __init__(self, stats_collector=None):
        self.stats_collector = stats_collector
        self.logger = logging.getLogger(__name__)

    def get_network_metrics(self, net) -> Dict[str, Any]:
        """Get comprehensive network metrics"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'network_status': self._get_network_status(net),
                'connectivity': self._check_basic_connectivity(net),
                'performance': self._get_performance_metrics(net),
                'resources': self._get_resource_usage(net)
            }

            # Add flow statistics if available
            flow_stats = self.get_flow_stats(net)
            if flow_stats:
                metrics['flows'] = flow_stats

            return metrics

        except Exception as e:
            self.logger.error(f"Error getting network metrics: {e}")
            return {'error': str(e)}

    def _get_network_status(self, net) -> Dict[str, Any]:
        """Get overall network status"""
        try:
            status = {
                'is_running': net is not None,
                'total_hosts': len(net.hosts) if net else 0,
                'total_switches': len(net.switches) if net else 0,
                'total_links': len(net.links) if net else 0,
                'total_controllers': len(net.controllers) if net and hasattr(net, 'controllers') else 0
            }

            # Check if processes are running
            if net:
                # Safely get all nodes, filtering out None values
                all_nodes = []
                if hasattr(net, 'hosts') and net.hosts:
                    all_nodes.extend([n for n in net.hosts if n is not None])
                if hasattr(net, 'switches') and net.switches:
                    all_nodes.extend([n for n in net.switches if n is not None])
                
                status['processes_running'] = all(
                    p.poll() is None for p in [getattr(node, 'proc', None) for node in all_nodes]
                    if getattr(node, 'proc', None) is not None
                )

            return status

        except Exception as e:
            self.logger.error(f"Error getting network status: {e}")
            return {'error': str(e)}

    def _check_basic_connectivity(self, net) -> Dict[str, Any]:
        """Check basic network connectivity"""
        try:
            connectivity = {
                'ping_tests': [],
                'link_status': []
            }

            # Test ping between hosts
            if len(net.hosts) >= 2:
                for i, host1 in enumerate(net.hosts):
                    for j, host2 in enumerate(net.hosts):
                        if i < j:  # Avoid duplicate tests
                            try:
                                result = net.ping([host1, host2], timeout=1)
                                connectivity['ping_tests'].append({
                                    'source': host1.name,
                                    'target': host2.name,
                                    'success': result == 0,
                                    'packet_loss': '0%' if result == 0 else '>0%'
                                })
                            except Exception as e:
                                connectivity['ping_tests'].append({
                                    'source': host1.name,
                                    'target': host2.name,
                                    'success': False,
                                    'error': str(e)
                                })

            # Check link status
            for link in net.links:
                try:
                    intf1_up = subprocess.run(['ip', 'link', 'show', link.intf1.name],
                                            capture_output=True, text=True).returncode == 0
                    intf2_up = subprocess.run(['ip', 'link', 'show', link.intf2.name],
                                            capture_output=True, text=True).returncode == 0

                    connectivity['link_status'].append({
                        'interface1': link.intf1.name,
                        'interface2': link.intf2.name,
                        'status': 'up' if (intf1_up and intf2_up) else 'down'
                    })
                except Exception as e:
                    connectivity['link_status'].append({
                        'interface1': link.intf1.name,
                        'interface2': link.intf2.name,
                        'status': 'error',
                        'error': str(e)
                    })

            return connectivity

        except Exception as e:
            self.logger.error(f"Error checking connectivity: {e}")
            return {'error': str(e)}

    def _get_performance_metrics(self, net) -> Dict[str, Any]:
        """Get network performance metrics"""
        try:
            performance = {
                'latency': {},
                'throughput': {},
                'packet_loss': {}
            }

            # Measure latency between hosts
            if len(net.hosts) >= 2:
                for i, host1 in enumerate(net.hosts[:3]):  # Test first 3 hosts
                    for j, host2 in enumerate(net.hosts[:3]):
                        if i < j:
                            try:
                                # Simple ping test for latency
                                result = subprocess.run(
                                    ['ping', '-c', '3', '-W', '1', host2.IP()],
                                    capture_output=True, text=True, cwd=f'/proc/{host1.pid}/cwd'
                                )

                                if result.returncode == 0:
                                    # Extract average latency from ping output
                                    lines = result.stdout.split('\n')
                                    for line in lines:
                                        if 'avg' in line:
                                            parts = line.split('/')
                                            if len(parts) >= 4:
                                                performance['latency'][f'{host1.name}_{host2.name}'] = {
                                                    'avg': float(parts[-3]),
                                                    'unit': 'ms'
                                                }
                                                break
                            except Exception as e:
                                self.logger.warning(f"Error measuring latency {host1.name}->{host2.name}: {e}")

            return performance

        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {e}")
            return {'error': str(e)}

    def _get_resource_usage(self, net) -> Dict[str, Any]:
        """Get resource usage statistics"""
        try:
            resources = {
                'cpu': {},
                'memory': {},
                'network_interfaces': {}
            }

            # Get resource usage for each node
            # Safely get nodes, filtering out any None values
            all_nodes = []
            if hasattr(net, 'hosts') and net.hosts:
                all_nodes.extend([n for n in net.hosts if n is not None])
            if hasattr(net, 'switches') and net.switches:
                all_nodes.extend([n for n in net.switches if n is not None])
            
            for node in all_nodes:
                try:
                    if hasattr(node, 'pid') and node.pid:
                        # Read /proc/pid/stat for CPU and memory info
                        stat_file = f'/proc/{node.pid}/stat'
                        if os.path.exists(stat_file):
                            with open(stat_file, 'r') as f:
                                stat_data = f.read().split()

                            # CPU time (utime + stime)
                            utime = int(stat_data[13])
                            stime = int(stat_data[14])
                            total_time = utime + stime

                            # Memory usage
                            status_file = f'/proc/{node.pid}/status'
                            if os.path.exists(status_file):
                                with open(status_file, 'r') as f:
                                    for line in f:
                                        if line.startswith('VmRSS:'):
                                            mem_kb = int(line.split()[1])
                                            resources['memory'][node.name] = {
                                                'rss_kb': mem_kb,
                                                'rss_mb': mem_kb / 1024
                                            }
                                            break

                            resources['cpu'][node.name] = {
                                'total_time': total_time,
                                'unit': 'jiffies'
                            }

                except Exception as e:
                    self.logger.warning(f"Error getting resources for {node.name}: {e}")

            return resources

        except Exception as e:
            self.logger.error(f"Error getting resource usage: {e}")
            return {'error': str(e)}

    def get_flow_stats(self, net) -> Dict[str, Any]:
        """Get OpenFlow flow statistics"""
        try:
            flow_stats = {
                'total_flows': 0,
                'flows_by_switch': {},
                'timestamp': datetime.now().isoformat()
            }

            # Get flows from each switch
            for switch in net.switches:
                try:
                    switch_flows = []
                    if hasattr(switch, 'dpctl') and switch.dpctl:
                        # Use ovs-ofctl to get flows
                        result = subprocess.run(
                            ['ovs-ofctl', 'dump-flows', switch.name],
                            capture_output=True, text=True, timeout=5
                        )

                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            for line in lines[1:]:  # Skip header
                                if line.strip():
                                    flow_info = self._parse_flow_line(line)
                                    switch_flows.append(flow_info)

                    flow_stats['flows_by_switch'][switch.name] = {
                        'count': len(switch_flows),
                        'flows': switch_flows
                    }
                    flow_stats['total_flows'] += len(switch_flows)

                except Exception as e:
                    self.logger.warning(f"Error getting flows for switch {switch.name}: {e}")
                    flow_stats['flows_by_switch'][switch.name] = {
                        'count': 0,
                        'flows': [],
                        'error': str(e)
                    }

            return flow_stats

        except Exception as e:
            self.logger.error(f"Error getting flow stats: {e}")
            return {'error': str(e)}

    def _parse_flow_line(self, line: str) -> Dict[str, Any]:
        """Parse a single flow line from ovs-ofctl output"""
        try:
            # Basic parsing - in a real implementation, this would be more comprehensive
            parts = line.split(',')
            flow = {}

            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    flow[key.strip()] = value.strip()

            return flow
        except:
            return {'raw': line}

    def ping_test(self, net, source_host=None, target_host=None, count=3):
        """Perform ping test between hosts"""
        try:
            if source_host and target_host:
                # Specific host to host ping
                result = net.ping([source_host, target_host], timeout=count)
                return {
                    'source': source_host.name if hasattr(source_host, 'name') else str(source_host),
                    'target': target_host.name if hasattr(target_host, 'name') else str(target_host),
                    'success': result == 0,
                    'packet_loss': '0%' if result == 0 else '>0%'
                }
            else:
                # Ping all hosts
                results = []
                if len(net.hosts) >= 2:
                    result = net.ping(timeout=count)
                    results.append({
                        'test': 'all_hosts',
                        'success': result == 0,
                        'packet_loss': '0%' if result == 0 else '>0%'
                    })
                return results

        except Exception as e:
            self.logger.error(f"Error in ping test: {e}")
            return {'error': str(e)}

    def diagnose_connectivity_issues(self, net) -> Dict[str, Any]:
        """Diagnose connectivity issues in the network"""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check controller connectivity
            controller_issues = self._check_controller_connectivity(net)
            issues.extend(controller_issues['issues'])
            recommendations.extend(controller_issues['recommendations'])
            details.update(controller_issues['details'])

            # Check switch-controller connectivity
            switch_issues = self._check_switch_controller_connectivity(net)
            issues.extend(switch_issues['issues'])
            recommendations.extend(switch_issues['recommendations'])

            # Check host connectivity
            host_issues = self._check_host_connectivity(net)
            issues.extend(host_issues['issues'])
            recommendations.extend(host_issues['recommendations'])

            # Check interface status
            interface_issues = self._check_interface_status(net)
            issues.extend(interface_issues['issues'])
            recommendations.extend(interface_issues['recommendations'])

            # Check flow tables
            flow_issues = self._check_flow_tables(net)
            issues.extend(flow_issues['issues'])
            recommendations.extend(flow_issues['recommendations'])

            return {
                'issues': issues,
                'recommendations': recommendations,
                'details': details,
                'severity': self._calculate_severity(issues)
            }

        except Exception as e:
            self.logger.error(f"Error in connectivity diagnosis: {e}")
            return {
                'issues': [f'Diagnostic error: {str(e)}'],
                'recommendations': ['Check system logs for details'],
                'details': {},
                'severity': 'high'
            }

    def _check_controller_connectivity(self, net) -> Dict[str, Any]:
        """Check if controller is running and accessible"""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check if controller is running
            if not hasattr(net, 'controllers') or not net.controllers:
                issues.append("No controllers configured in the network")
                recommendations.append("Add a controller to the network topology")
                details['controller_running'] = False
            else:
                details['controller_running'] = True

                # Check controller process
                controller_status = self._get_controller_status(net)
                details['controller_status'] = controller_status

                if controller_status.get('running', False):
                    # Check if controller port is accessible
                    import socket
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)
                        result = sock.connect_ex(('127.0.0.1', controller_status.get('port', 6633)))
                        sock.close()

                        if result != 0:
                            issues.append(f"Controller port {controller_status.get('port', 6633)} is not accessible")
                            recommendations.append("Check if controller is listening on the correct port")
                            details['port_accessible'] = False
                        else:
                            details['port_accessible'] = True

                    except Exception as e:
                        issues.append(f"Cannot check controller port accessibility: {e}")
                        details['port_check_error'] = str(e)

        except Exception as e:
            issues.append(f"Controller connectivity check failed: {e}")
            recommendations.append("Check controller configuration and logs")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _get_controller_status(self, net) -> Dict[str, Any]:
        """Get controller status"""
        # This would be implemented based on the controller factory
        return {'running': True, 'port': 6633}  # Placeholder

    def _check_switch_controller_connectivity(self, net) -> Dict[str, Any]:
        """Check connectivity between switches and controller"""
        issues = []
        recommendations = []
        details = {}

        # Implementation would check OpenFlow connections
        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_host_connectivity(self, net) -> Dict[str, Any]:
        """Check host connectivity and IP configuration"""
        issues = []
        recommendations = []
        details = {}

        try:
            for host in net.hosts:
                # Check if host has IP address
                try:
                    ip = host.IP()
                    if ip == '127.0.0.1' or ip == '0.0.0.0':
                        issues.append(f"Host {host.name} has invalid IP address: {ip}")
                        recommendations.append(f"Configure a valid IP address for host {host.name}")
                except:
                    issues.append(f"Host {host.name} has no IP address configured")
                    recommendations.append(f"Configure IP address for host {host.name}")

        except Exception as e:
            issues.append(f"Host connectivity check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_interface_status(self, net) -> Dict[str, Any]:
        """Check network interface status"""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check interface status using ip command
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'state DOWN' in line and 'lo' not in line:
                        # Extract interface name
                        parts = line.split(':')
                        if len(parts) >= 2:
                            intf_name = parts[1].strip().split()[0]
                            issues.append(f"Interface {intf_name} is down")
                            recommendations.append(f"Bring up interface {intf_name} with 'ip link set {intf_name} up'")

        except Exception as e:
            issues.append(f"Interface status check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_flow_tables(self, net) -> Dict[str, Any]:
        """Check OpenFlow flow tables"""
        issues = []
        recommendations = []
        details = {}

        try:
            for switch in net.switches:
                # Check if switch has flows
                flow_stats = self.get_flow_stats(net)
                switch_flows = flow_stats.get('flows_by_switch', {}).get(switch.name, {})

                if switch_flows.get('count', 0) == 0:
                    issues.append(f"Switch {switch.name} has no flows installed")
                    recommendations.append(f"Install flows on switch {switch.name} or check controller connectivity")

        except Exception as e:
            issues.append(f"Flow table check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _calculate_severity(self, issues: List[str]) -> str:
        """Calculate overall severity of issues"""
        if not issues:
            return 'none'

        high_priority_keywords = ['controller', 'connection', 'port', 'interface down']
        medium_priority_keywords = ['flow', 'ip', 'address']

        high_count = sum(1 for issue in issues if any(kw in issue.lower() for kw in high_priority_keywords))
        medium_count = sum(1 for issue in issues if any(kw in issue.lower() for kw in medium_priority_keywords))

        if high_count > 0:
            return 'high'
        elif medium_count > 0:
            return 'medium'
        else:
            return 'low'
