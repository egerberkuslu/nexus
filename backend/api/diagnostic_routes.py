"""
Diagnostic API Routes for Network Troubleshooting
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
diagnostic_bp = Blueprint('diagnostic', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@diagnostic_bp.route('/connectivity', methods=['GET'])
@log_api_request
def diagnose_connectivity():
    """Diagnose network connectivity issues"""
    try:
        mininet_mgr = get_mininet_manager()
        diagnosis = mininet_mgr.diagnose_connectivity_issues()
        
        return jsonify(diagnosis)
        
    except Exception as e:
        logger.error(f"Error diagnosing connectivity: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/detailed-ping', methods=['POST'])
@log_api_request
def detailed_ping_test():
    """Run detailed ping test with specific host pairs"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get test parameters
        data = request.get_json() or {}
        source = data.get('source', 'h1')
        target = data.get('target', 'h2')
        count = data.get('count', 4)
        timeout = data.get('timeout', 2)
        
        # Validate hosts exist
        source_host = mininet_mgr.net.get(source)
        target_host = mininet_mgr.net.get(target)
        
        if not source_host:
            return jsonify({'error': f'Source host {source} not found'}), 404
        
        if not target_host:
            return jsonify({'error': f'Target host {target} not found'}), 404
        
        # Get target IP
        if target == 'r1':
            # For router, determine which interface to ping
            if source in ['h1', 'h2']:
                target_ip = '10.0.1.1'
            else:
                target_ip = '10.0.2.1'
        else:
            target_ip = target_host.IP()
        
        # Run ping command
        ping_cmd = f'ping -c {count} -W {timeout} {target_ip}'
        result = source_host.cmd(ping_cmd)
        
        # Parse results
        import re
        packet_loss_match = re.search(r'(\d+)% packet loss', result)
        packet_loss = packet_loss_match.group(1) if packet_loss_match else '100'
        
        # Extract timing info
        time_match = re.search(r'time=(\d+\.?\d*)\s*ms', result)
        avg_time = time_match.group(1) if time_match else 'N/A'
        
        success = packet_loss == '0'
        
        return jsonify({
            'source': source,
            'target': target,
            'target_ip': target_ip,
            'success': success,
            'packet_loss': packet_loss,
            'average_time_ms': avg_time,
            'full_result': result.strip(),
            'command': ping_cmd
        })
        
    except Exception as e:
        logger.error(f"Error in detailed ping test: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/arp-tables', methods=['GET'])
@log_api_request
def get_arp_tables():
    """Get ARP tables from all hosts"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        arp_tables = {}
        
        for host in mininet_mgr.net.hosts:
            try:
                arp_result = host.cmd('arp -a')
                arp_tables[host.name] = {
                    'raw': arp_result.strip(),
                    'entries': []
                }
                
                # Parse ARP entries
                lines = arp_result.strip().split('\n')
                for line in lines:
                    if line.strip() and '(' in line and ')' in line:
                        # Parse format like: gateway (10.0.1.1) at aa:bb:cc:dd:ee:ff [ether] on h1-eth0
                        import re
                        match = re.search(r'(\S+)\s+\(([^)]+)\)\s+at\s+([^\s]+)', line)
                        if match:
                            hostname, ip, mac = match.groups()
                            arp_tables[host.name]['entries'].append({
                                'hostname': hostname,
                                'ip': ip,
                                'mac': mac
                            })
                            
            except Exception as e:
                arp_tables[host.name] = {'error': str(e)}
        
        return jsonify(arp_tables)
        
    except Exception as e:
        logger.error(f"Error getting ARP tables: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/routing-tables', methods=['GET'])
@log_api_request
def get_routing_tables():
    """Get routing tables from all hosts and routers"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        routing_tables = {}
        
        for host in mininet_mgr.net.hosts:
            try:
                route_result = host.cmd('ip route show')
                routing_tables[host.name] = {
                    'raw': route_result.strip(),
                    'default_route': None,
                    'routes': []
                }
                
                # Parse routing entries
                lines = route_result.strip().split('\n')
                for line in lines:
                    if line.strip():
                        if line.startswith('default'):
                            # Extract default gateway
                            import re
                            match = re.search(r'default via ([^\s]+)', line)
                            if match:
                                routing_tables[host.name]['default_route'] = match.group(1)
                        else:
                            routing_tables[host.name]['routes'].append(line.strip())
                            
            except Exception as e:
                routing_tables[host.name] = {'error': str(e)}
        
        return jsonify(routing_tables)
        
    except Exception as e:
        logger.error(f"Error getting routing tables: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/switch-flows', methods=['GET'])
@log_api_request
def get_all_switch_flows():
    """Get flow tables from all switches"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        switch_flows = {}
        
        for switch in mininet_mgr.net.switches:
            try:
                import subprocess
                
                # Get flow table
                result = subprocess.run(
                    ['ovs-ofctl', 'dump-flows', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    flows = result.stdout.strip().split('\n')
                    # Skip the header line
                    flow_entries = [flow for flow in flows[1:] if flow.strip()]
                    
                    switch_flows[switch.name] = {
                        'flow_count': len(flow_entries),
                        'flows': flow_entries,
                        'connected': True
                    }
                else:
                    switch_flows[switch.name] = {
                        'error': f'Failed to get flows: {result.stderr}',
                        'connected': False
                    }
                
                # Also get port statistics
                port_result = subprocess.run(
                    ['ovs-ofctl', 'dump-ports', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                
                if port_result.returncode == 0:
                    switch_flows[switch.name]['port_stats'] = port_result.stdout.strip()
                    
            except subprocess.TimeoutExpired:
                switch_flows[switch.name] = {'error': 'Timeout connecting to switch'}
            except Exception as e:
                switch_flows[switch.name] = {'error': str(e)}
        
        return jsonify(switch_flows)
        
    except Exception as e:
        logger.error(f"Error getting switch flows: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/fix-common-issues', methods=['POST'])
@log_api_request
def fix_common_issues():
    """Attempt to fix common network connectivity issues"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        fixes_applied = []
        errors = []
        
        # Fix 1: Ensure controller is running
        if not mininet_mgr.ryu_controller.is_running:
            try:
                success = mininet_mgr.start_ryu_controller('simple_switch_13')
                if success:
                    fixes_applied.append("Started Ryu controller")
                    import time
                    time.sleep(2)  # Wait for controller to be ready
                else:
                    errors.append("Failed to start Ryu controller")
            except Exception as e:
                errors.append(f"Error starting controller: {e}")
        
        # Fix 2: Reconfigure router interfaces
        try:
            router = mininet_mgr.net.get('r1')
            if router:
                router.cmd('ifconfig r1-eth0 10.0.1.1/24 up')
                router.cmd('ifconfig r1-eth1 10.0.2.1/24 up')
                router.cmd('echo 1 > /proc/sys/net/ipv4/ip_forward')
                fixes_applied.append("Reconfigured router interfaces and enabled IP forwarding")
        except Exception as e:
            errors.append(f"Error configuring router: {e}")
        
        # Fix 3: Reconnect switches to controller
        try:
            for switch in mininet_mgr.net.switches:
                switch.cmd('ovs-vsctl set-controller', switch.name, 'tcp:127.0.0.1:6633')
            fixes_applied.append("Reconnected switches to controller")
        except Exception as e:
            errors.append(f"Error reconnecting switches: {e}")
        
        # Fix 4: Clear and repopulate ARP tables
        try:
            for host in mininet_mgr.net.hosts:
                if host.name.startswith('h'):
                    # Clear ARP table
                    host.cmd('arp -d -a')
                    # Ping default gateway to repopulate ARP
                    if host.name in ['h1', 'h2']:
                        host.cmd('ping -c 1 -W 1 10.0.1.1 > /dev/null 2>&1 &')
                    else:
                        host.cmd('ping -c 1 -W 1 10.0.2.1 > /dev/null 2>&1 &')
            fixes_applied.append("Cleared and repopulated ARP tables")
        except Exception as e:
            errors.append(f"Error fixing ARP tables: {e}")
        
        # Fix 5: Wait for network to stabilize
        import time
        time.sleep(3)
        
        return jsonify({
            'success': len(errors) == 0,
            'fixes_applied': fixes_applied,
            'errors': errors,
            'message': f'Applied {len(fixes_applied)} fixes with {len(errors)} errors'
        })
        
    except Exception as e:
        logger.error(f"Error fixing common issues: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/network-health', methods=['GET'])
@log_api_request
def get_network_health():
    """Get comprehensive network health status"""
    try:
        mininet_mgr = get_mininet_manager()
        
        health_status = {
            'overall_status': 'unknown',
            'network_running': mininet_mgr.is_running,
            'controller_running': mininet_mgr.ryu_controller.is_running,
            'components': {},
            'connectivity_tests': {},
            'issues': [],
            'recommendations': []
        }
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            health_status['overall_status'] = 'critical'
            health_status['issues'].append('Network is not running')
            health_status['recommendations'].append('Start the network')
            return jsonify(health_status)
        
        # Check controller status
        if mininet_mgr.ryu_controller.is_running:
            health_status['components']['controller'] = 'healthy'
        else:
            health_status['components']['controller'] = 'critical'
            health_status['issues'].append('Controller is not running')
            health_status['recommendations'].append('Start the Ryu controller')
        
        # Check switch connectivity
        switch_health = []
        for switch in mininet_mgr.net.switches:
            try:
                import subprocess
                cmd = [
                    'sudo',                          # ensure root privilege
                    'ovs-ofctl',
                    '-O', 'OpenFlow13',              # match your switch’s protocol
                    'show', switch.name
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    switch_health.append('healthy')
                else:
                    switch_health.append('warning')
                    health_status['issues'].append(f'Switch {switch.name} not responding properly')
            except:
                switch_health.append('critical')
                health_status['issues'].append(f'Switch {switch.name} unreachable')
        
        if all(status == 'healthy' for status in switch_health):
            health_status['components']['switches'] = 'healthy'
        elif any(status == 'critical' for status in switch_health):
            health_status['components']['switches'] = 'critical'
        else:
            health_status['components']['switches'] = 'warning'
        
        # Check router health
        router = mininet_mgr.net.get('r1')
        if router:
            try:
                # Check IP forwarding
                ip_forward = router.cmd('cat /proc/sys/net/ipv4/ip_forward').strip()
                interfaces = router.cmd('ip addr show')
                
                if ip_forward == '1' and '10.0.1.1' in interfaces and '10.0.2.1' in interfaces:
                    health_status['components']['router'] = 'healthy'
                else:
                    health_status['components']['router'] = 'warning'
                    if ip_forward != '1':
                        health_status['issues'].append('IP forwarding disabled on router')
                        health_status['recommendations'].append('Enable IP forwarding on router')
                    if '10.0.1.1' not in interfaces or '10.0.2.1' not in interfaces:
                        health_status['issues'].append('Router interfaces not properly configured')
                        health_status['recommendations'].append('Reconfigure router interfaces')
            except:
                health_status['components']['router'] = 'critical'
                health_status['issues'].append('Router not responding')
        else:
            health_status['components']['router'] = 'critical'
            health_status['issues'].append('Router not found')
        
        # Run quick connectivity tests
        try:
            # Test within subnet 1
            h1 = mininet_mgr.net.get('h1')
            h2 = mininet_mgr.net.get('h2')
            if h1 and h2:
                result = h1.cmd(f'ping -c 1 -W 1 {h2.IP()}')
                if '1 received' in result:
                    health_status['connectivity_tests']['intra_subnet_1'] = 'pass'
                else:
                    health_status['connectivity_tests']['intra_subnet_1'] = 'fail'
                    health_status['issues'].append('Intra-subnet connectivity failed (subnet 1)')
            
            # Test within subnet 2
            h3 = mininet_mgr.net.get('h3')
            h4 = mininet_mgr.net.get('h4')
            if h3 and h4:
                result = h3.cmd(f'ping -c 1 -W 1 {h4.IP()}')
                if '1 received' in result:
                    health_status['connectivity_tests']['intra_subnet_2'] = 'pass'
                else:
                    health_status['connectivity_tests']['intra_subnet_2'] = 'fail'
                    health_status['issues'].append('Intra-subnet connectivity failed (subnet 2)')
            
            # Test inter-subnet connectivity
            if h1 and h3:
                result = h1.cmd(f'ping -c 1 -W 2 {h3.IP()}')
                if '1 received' in result:
                    health_status['connectivity_tests']['inter_subnet'] = 'pass'
                else:
                    health_status['connectivity_tests']['inter_subnet'] = 'fail'
                    health_status['issues'].append('Inter-subnet connectivity failed')
                    health_status['recommendations'].append('Check router configuration and controller flows')
        
        except Exception as e:
            health_status['connectivity_tests']['error'] = str(e)
        
        # Determine overall status
        critical_components = [comp for comp, status in health_status['components'].items() if status == 'critical']
        warning_components = [comp for comp, status in health_status['components'].items() if status == 'warning']
        failed_tests = [test for test, result in health_status['connectivity_tests'].items() if result == 'fail']
        
        if critical_components or len(failed_tests) > 1:
            health_status['overall_status'] = 'critical'
        elif warning_components or failed_tests:
            health_status['overall_status'] = 'warning'
        else:
            health_status['overall_status'] = 'healthy'
        
        # Add general recommendations
        if health_status['overall_status'] != 'healthy':
            health_status['recommendations'].append('Run the fix-common-issues endpoint to automatically resolve common problems')
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error getting network health: {e}")
        return jsonify({'error': str(e)}), 500

@diagnostic_bp.route('/trace-route/<source>/<target>', methods=['GET'])
@log_api_request
def trace_route(source, target):
    """Trace route between two hosts"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        source_host = mininet_mgr.net.get(source)
        target_host = mininet_mgr.net.get(target)
        
        if not source_host:
            return jsonify({'error': f'Source host {source} not found'}), 404
        
        if not target_host:
            return jsonify({'error': f'Target host {target} not found'}), 404
        
        # Get target IP
        if target == 'r1':
            if source in ['h1', 'h2']:
                target_ip = '10.0.1.1'
            else:
                target_ip = '10.0.2.1'
        else:
            target_ip = target_host.IP()
        
        # Run traceroute
        traceroute_result = source_host.cmd(f'traceroute -n -w 2 {target_ip}')
        
        # Also get route information
        route_info = source_host.cmd(f'ip route get {target_ip}')
        
        return jsonify({
            'source': source,
            'target': target,
            'target_ip': target_ip,
            'traceroute': traceroute_result.strip(),
            'route_info': route_info.strip()
        })
        
    except Exception as e:
        logger.error(f"Error in trace route: {e}")
        return jsonify({'error': str(e)}), 500