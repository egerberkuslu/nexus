"""
Network Diagnostics Module
Handles network monitoring, connectivity testing, and diagnostics
"""

import os
import re
import subprocess
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from mininet.net import Mininet
from utils.logger import setup_logger

logger = setup_logger(__name__)


class NetworkDiagnostics:
    """Handles network connectivity testing and diagnostics"""

    def __init__(self):
        self.logger = logger

    def ping_test(self, net: Mininet) -> Dict[str, Any]:
        """Run ping test between all hosts"""
        if not net:
            return {'error': 'Network not running'}

        try:
            logger.info("Running ping test")
            result = net.pingAll()
            packet_loss = re.search(r'(\d+)% packet loss', str(result))
            loss_percent = packet_loss.group(1) if packet_loss else '0'

            return {
                'result': f'Ping test completed with {loss_percent}% packet loss',
                'success': True,
                'packet_loss': loss_percent
            }
        except Exception as e:
            logger.error(f"Ping test failed: {e}")
            return {'error': f'Ping test failed: {str(e)}', 'success': False}

    def execute_host_command(self, net: Mininet, host_id: str, command: str) -> Dict[str, Any]:
        """Execute command on a specific host"""
        if not net:
            return {'error': 'Network not running', 'success': False}

        host = net.get(host_id)
        if not host:
            return {'error': f'Host {host_id} not found', 'success': False}

        try:
            result = host.cmd(command)
            logger.info(f"Executed command '{command}' on {host_id}")
            return {'result': result.strip(), 'success': True}
        except Exception as e:
            logger.error(f"Command execution failed on {host_id}: {e}")
            return {'error': str(e), 'success': False}

    def diagnose_connectivity_issues(self, net: Mininet,
                                   controller_factory: Optional[Any] = None) -> Dict[str, Any]:
        """
        Diagnose connectivity issues in the network
        Returns detailed analysis of network connectivity problems
        """
        if not net:
            return {
                'status': 'error',
                'message': 'Network not running',
                'issues': ['Network is not started'],
                'recommendations': ['Start the network first']
            }

        try:
            issues = []
            recommendations = []
            detailed_results = {}

            # 1. Check controller connectivity
            controller_issues = self._check_controller_connectivity(controller_factory)
            if controller_issues['issues']:
                issues.extend(controller_issues['issues'])
                recommendations.extend(controller_issues['recommendations'])
            detailed_results['controller'] = controller_issues

            # 2. Check switch connectivity to controller
            switch_controller_issues = self._check_switch_controller_connectivity(net)
            if switch_controller_issues['issues']:
                issues.extend(switch_controller_issues['issues'])
                recommendations.extend(switch_controller_issues['recommendations'])
            detailed_results['switch_controller'] = switch_controller_issues

            # 3. Check host-to-host connectivity
            host_connectivity_issues = self._check_host_connectivity(net)
            if host_connectivity_issues['issues']:
                issues.extend(host_connectivity_issues['issues'])
                recommendations.extend(host_connectivity_issues['recommendations'])
            detailed_results['host_connectivity'] = host_connectivity_issues

            # 4. Check interface status
            interface_issues = self._check_interface_status(net)
            if interface_issues['issues']:
                issues.extend(interface_issues['issues'])
                recommendations.extend(interface_issues['recommendations'])
            detailed_results['interfaces'] = interface_issues

            # 5. Check flow table status
            flow_issues = self._check_flow_tables(net)
            if flow_issues['issues']:
                issues.extend(flow_issues['issues'])
                recommendations.extend(flow_issues['recommendations'])
            detailed_results['flows'] = flow_issues

            # 6. Check ARP tables
            arp_issues = self._check_arp_tables(net)
            if arp_issues['issues']:
                issues.extend(arp_issues['issues'])
                recommendations.extend(arp_issues['recommendations'])
            detailed_results['arp'] = arp_issues

            # 7. Check routing (for routers)
            routing_issues = self._check_routing_tables(net)
            if routing_issues['issues']:
                issues.extend(routing_issues['issues'])
                recommendations.extend(routing_issues['recommendations'])
            detailed_results['routing'] = routing_issues

            # Overall status
            if not issues:
                status = 'healthy'
                message = 'Network connectivity is healthy'
            elif len(issues) <= 3:
                status = 'warning'
                message = f'Network has {len(issues)} connectivity issues'
            else:
                status = 'critical'
                message = f'Network has {len(issues)} critical connectivity issues'

            return {
                'status': status,
                'message': message,
                'issues': issues,
                'recommendations': recommendations,
                'detailed_results': detailed_results,
                'timestamp': str(datetime.now())
            }

        except Exception as e:
            logger.error(f"Connectivity diagnosis failed: {e}")
            return {
                'status': 'error',
                'message': f'Diagnosis failed: {str(e)}',
                'issues': [f'Diagnosis error: {str(e)}'],
                'recommendations': ['Check network configuration and try again']
            }

    def _check_controller_connectivity(self, controller_factory: Optional[Any]) -> Dict[str, Any]:
        """Check if controller is running and accessible"""
        issues = []
        recommendations = []
        details = {}

        try:
            if not controller_factory:
                issues.append("No controller factory available")
                recommendations.append("Initialize controller factory")
                return {
                    'issues': issues,
                    'recommendations': recommendations,
                    'details': details
                }

            # Check if controller is running
            active_controller = controller_factory.get_active_controller()
            if not active_controller:
                issues.append("No controller is active")
                recommendations.append("Start a controller")
                details['controller_running'] = False
            else:
                controller_info = controller_factory.get_controller_info().get(active_controller, {})
                if not controller_info.get('running', False):
                    issues.append(f"{active_controller.upper()} controller is not running")
                    recommendations.append(f"Start the {active_controller} controller")
                    details['controller_running'] = False
                else:
                    details['controller_running'] = True

            # Check controller process
            if hasattr(controller_factory, 'get_controller_status'):
                controller_status = controller_factory.get_controller_status()
                details['controller_status'] = controller_status

                if controller_status.get('running', False) and active_controller:
                    # Check if controller port is accessible
                    try:
                        controller_info = controller_factory.get_controller_info().get(active_controller, {})
                        controller_port = controller_info.get('port', 6633)

                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)
                        result = sock.connect_ex(('127.0.0.1', controller_port))
                        sock.close()

                        if result != 0:
                            issues.append(f"Controller port {controller_port} is not accessible")
                            recommendations.append("Check if controller is listening on the correct port")
                            details['port_accessible'] = False
                        else:
                            details['port_accessible'] = True

                    except Exception as e:
                        issues.append(f"Cannot check controller port accessibility: {e}")
                        details['port_check_error'] = str(e)

        except Exception as e:
            issues.append(f"Controller connectivity check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_switch_controller_connectivity(self, net: Mininet) -> Dict[str, Any]:
        """Check if switches are connected to controller"""
        issues = []
        recommendations = []
        details = {}

        try:
            switches = [s for s in net.switches]
            details['switches_checked'] = len(switches)
            details['switch_details'] = {}

            for switch in switches:
                switch_details = {}

                try:
                    # Check if switch is connected to controller using ovs-vsctl
                    result = subprocess.run(
                        ['ovs-vsctl', 'get-controller', switch.name],
                        capture_output=True, text=True, timeout=5
                    )

                    if result.returncode == 0:
                        controller_info = result.stdout.strip()
                        switch_details['controller_configured'] = controller_info

                        if 'tcp:' not in controller_info:
                            issues.append(f"Switch {switch.name} has no controller configured")
                            recommendations.append(f"Configure controller for switch {switch.name}")
                    else:
                        issues.append(f"Cannot get controller info for switch {switch.name}")
                        switch_details['controller_configured'] = 'unknown'

                    # Check OpenFlow connection status
                    result = subprocess.run(
                        ['ovs-vsctl', 'show'],
                        capture_output=True, text=True, timeout=5
                    )

                    if result.returncode == 0:
                        ovs_output = result.stdout
                        if switch.name in ovs_output:
                            switch_details['ovs_configured'] = True
                        else:
                            switch_details['ovs_configured'] = False
                            issues.append(f"Switch {switch.name} not found in OVS configuration")
                            recommendations.append(f"Check OVS configuration for switch {switch.name}")

                except subprocess.TimeoutExpired:
                    issues.append(f"Timeout checking switch {switch.name}")
                    switch_details['timeout'] = True
                except Exception as e:
                    issues.append(f"Error checking switch {switch.name}: {e}")
                    switch_details['error'] = str(e)

                details['switch_details'][switch.name] = switch_details

        except Exception as e:
            issues.append(f"Switch-controller connectivity check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_host_connectivity(self, net: Mininet) -> Dict[str, Any]:
        """Check host-to-host connectivity"""
        issues = []
        recommendations = []
        details = {}

        try:
            hosts = [h for h in net.hosts]
            details['hosts_checked'] = len(hosts)
            details['connectivity_matrix'] = {}

            # Test connectivity between hosts
            for i, host1 in enumerate(hosts):
                for host2 in hosts[i+1:]:
                    try:
                        # Use ping to test connectivity
                        result = host1.cmd(f'ping -c 1 -W 1 {host2.IP()}')
                        success = '1 received' in result

                        details['connectivity_matrix'][f'{host1.name}->{host2.name}'] = success

                        if not success:
                            issues.append(f"No connectivity between {host1.name} and {host2.name}")
                            recommendations.append(f"Check network configuration and routing between {host1.name} and {host2.name}")

                    except Exception as e:
                        issues.append(f"Error testing connectivity {host1.name}->{host2.name}: {e}")
                        details['connectivity_matrix'][f'{host1.name}->{host2.name}'] = False

        except Exception as e:
            issues.append(f"Host connectivity check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_interface_status(self, net: Mininet) -> Dict[str, Any]:
        """Check interface status for all nodes"""
        issues = []
        recommendations = []
        details = {}

        try:
            all_nodes = net.hosts + net.switches
            details['nodes_checked'] = len(all_nodes)
            details['interface_details'] = {}

            for node in all_nodes:
                node_interfaces = {}
                try:
                    # Get interface information
                    intf_output = node.cmd('ip addr show')
                    node_interfaces['ip_addr_output'] = intf_output

                    # Check for UP interfaces
                    interfaces = re.findall(r'\d+: ([^:]+):', intf_output)
                    up_interfaces = []

                    for interface in interfaces:
                        if interface != 'lo':  # Skip loopback
                            intf_details = node.cmd(f'ip addr show {interface}')
                            if 'UP' in intf_details:
                                up_interfaces.append(interface)
                            else:
                                issues.append(f"Interface {interface} on {node.name} is DOWN")
                                recommendations.append(f"Bring up interface {interface} on {node.name}")

                    node_interfaces['up_interfaces'] = up_interfaces
                    node_interfaces['total_interfaces'] = len(interfaces)

                except Exception as e:
                    issues.append(f"Error checking interfaces on {node.name}: {e}")
                    node_interfaces['error'] = str(e)

                details['interface_details'][node.name] = node_interfaces

        except Exception as e:
            issues.append(f"Interface status check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_flow_tables(self, net: Mininet) -> Dict[str, Any]:
        """Check flow table status on switches"""
        issues = []
        recommendations = []
        details = {}

        try:
            switches = [s for s in net.switches]
            details['switches_checked'] = len(switches)
            details['flow_details'] = {}

            for switch in switches:
                switch_flows = {}
                try:
                    # Get flow table information
                    result = subprocess.run(
                        ['ovs-ofctl', 'dump-flows', switch.name],
                        capture_output=True, text=True, timeout=5
                    )

                    if result.returncode == 0:
                        flow_output = result.stdout
                        switch_flows['flow_dump'] = flow_output

                        # Count flows (excluding header)
                        flow_lines = [line for line in flow_output.split('\n') if line.strip() and not line.startswith('NXST')]
                        flow_count = len(flow_lines)
                        switch_flows['flow_count'] = flow_count

                        if flow_count == 0:
                            issues.append(f"Switch {switch.name} has no flows installed")
                            recommendations.append(f"Install flows on switch {switch.name}")
                        elif flow_count < 3:  # Very few flows might indicate issues
                            issues.append(f"Switch {switch.name} has very few flows ({flow_count})")
                            recommendations.append(f"Verify flow installation on switch {switch.name}")
                    else:
                        issues.append(f"Cannot dump flows for switch {switch.name}")
                        switch_flows['error'] = result.stderr

                except subprocess.TimeoutExpired:
                    issues.append(f"Timeout dumping flows for switch {switch.name}")
                    switch_flows['timeout'] = True
                except Exception as e:
                    issues.append(f"Error checking flows on switch {switch.name}: {e}")
                    switch_flows['error'] = str(e)

                details['flow_details'][switch.name] = switch_flows

        except Exception as e:
            issues.append(f"Flow table check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_arp_tables(self, net: Mininet) -> Dict[str, Any]:
        """Check ARP table status"""
        issues = []
        recommendations = []
        details = {}

        try:
            hosts = [h for h in net.hosts]
            details['hosts_checked'] = len(hosts)
            details['arp_details'] = {}

            for host in hosts:
                host_arp = {}
                try:
                    # Get ARP table
                    arp_output = host.cmd('arp -n')
                    host_arp['arp_table'] = arp_output

                    # Count ARP entries
                    arp_lines = [line for line in arp_output.split('\n') if line.strip() and not line.startswith('Address')]
                    arp_count = len(arp_lines)
                    host_arp['arp_entries'] = arp_count

                    if arp_count == 0:
                        issues.append(f"Host {host.name} has empty ARP table")
                        recommendations.append(f"Check network connectivity for {host.name}")

                except Exception as e:
                    issues.append(f"Error checking ARP table on {host.name}: {e}")
                    host_arp['error'] = str(e)

                details['arp_details'][host.name] = host_arp

        except Exception as e:
            issues.append(f"ARP table check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }

    def _check_routing_tables(self, net: Mininet) -> Dict[str, Any]:
        """Check routing table status"""
        issues = []
        recommendations = []
        details = {}

        try:
            all_nodes = net.hosts + net.switches
            details['nodes_checked'] = len(all_nodes)
            details['routing_details'] = {}

            for node in all_nodes:
                node_routing = {}
                try:
                    # Get routing table
                    route_output = node.cmd('ip route show')
                    node_routing['routing_table'] = route_output

                    # Check for default route
                    has_default = 'default' in route_output
                    node_routing['has_default_route'] = has_default

                    if not has_default and 'h' in node.name:  # Only check hosts for default route
                        issues.append(f"Host {node.name} has no default route")
                        recommendations.append(f"Configure default route for {node.name}")

                    # Count routes
                    route_lines = [line for line in route_output.split('\n') if line.strip()]
                    route_count = len(route_lines)
                    node_routing['route_count'] = route_count

                except Exception as e:
                    issues.append(f"Error checking routing table on {node.name}: {e}")
                    node_routing['error'] = str(e)

                details['routing_details'][node.name] = node_routing

        except Exception as e:
            issues.append(f"Routing table check failed: {e}")

        return {
            'issues': issues,
            'recommendations': recommendations,
            'details': details
        }
