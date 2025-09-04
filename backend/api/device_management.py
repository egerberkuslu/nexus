"""
Device Management API Routes
Comprehensive network device management for Mininet framework
"""

from flask import Blueprint, jsonify, request, current_app
import subprocess
import json
import re
import time
from datetime import datetime
from utils.logger import setup_logger, log_api_request
# Import all the configuration management functions
from utils.config_manager import (
    # Core utilities
    validate_request_and_setup,
    CommandPlanner,
    
    # Configuration processors
    process_router_configuration,
    process_host_configuration, 
    process_switch_configuration,
    
    # Execution functions
    execute_command_plan,
    calculate_execution_summary
)




logger = setup_logger(__name__)
device_mgmt_bp = Blueprint('device_management', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

# ======================= HOST MANAGEMENT =======================

@device_mgmt_bp.route('/hosts', methods=['GET'])
@log_api_request
def get_all_hosts():
    """Get all hosts in the network with detailed information"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        hosts_info = []
        for host in mininet_mgr.net.hosts:
            # Skip routers (they're handled separately)
            if hasattr(host, 'node_type') and host.node_type == 'router':
                continue
                
            host_info = {
                'id': host.name,
                'type': 'host',
                'ip': host.IP(),
                'mac': host.MAC(),
                'interfaces': [],
                'routes': [],
                'arp_table': [],
                'services': [],
                'status': 'active' if mininet_mgr.is_running else 'inactive'
            }
            
            # Get interface information
            for intf in host.intfList():
                if intf.name != 'lo':
                    intf_info = {
                        'name': intf.name,
                        'ip': intf.IP() if hasattr(intf, 'IP') else 'N/A',
                        'mac': intf.MAC() if hasattr(intf, 'MAC') else 'N/A',
                        'status': 'up' if intf.isUp() else 'down',
                        'mtu': getattr(intf, 'mtu', 1500)
                    }
                    host_info['interfaces'].append(intf_info)
            
            # Get routing table
            try:
                routes_output = host.cmd('ip route show')
                for line in routes_output.strip().split('\n'):
                    if line.strip():
                        host_info['routes'].append(line.strip())
            except:
                pass
            
            # Get ARP table
            try:
                arp_output = host.cmd('arp -a')
                for line in arp_output.strip().split('\n'):
                    if line.strip() and '(' in line:
                        host_info['arp_table'].append(line.strip())
            except:
                pass
            
            # Check running services
            try:
                ps_output = host.cmd('ps aux | grep -E "(ssh|http|ftp|telnet)" | grep -v grep')
                for line in ps_output.strip().split('\n'):
                    if line.strip():
                        host_info['services'].append(line.strip())
            except:
                pass
            
            hosts_info.append(host_info)
        
        return jsonify({
            'hosts': hosts_info,
            'count': len(hosts_info),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting all hosts: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/hosts/<host_id>', methods=['GET'])
@log_api_request
def get_host_details(host_id):
    """Get detailed information about a specific host"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        host = mininet_mgr.net.get(host_id)
        if not host:
            return jsonify({'error': f'Host {host_id} not found'}), 404
        
        # Comprehensive host information
        host_details = {
            'id': host.name,
            'type': 'host',
            'ip': host.IP(),
            'mac': host.MAC(),
            'interfaces': [],
            'network_config': {},
            'system_info': {},
            'performance': {},
            'security': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Interface details
        for intf in host.intfList():
            if intf.name != 'lo':
                intf_stats = _get_interface_stats(host, intf.name)
                intf_info = {
                    'name': intf.name,
                    'ip': intf.IP() if hasattr(intf, 'IP') else 'N/A',
                    'mac': intf.MAC() if hasattr(intf, 'MAC') else 'N/A',
                    'status': 'up' if intf.isUp() else 'down',
                    'mtu': getattr(intf, 'mtu', 1500),
                    'statistics': intf_stats
                }
                host_details['interfaces'].append(intf_info)
        
        # Network configuration
        host_details['network_config'] = {
            'routing_table': host.cmd('ip route show').strip().split('\n'),
            'arp_table': host.cmd('arp -a').strip(),
            'dns_config': host.cmd('cat /etc/resolv.conf 2>/dev/null || echo "No DNS config"').strip(),
            'firewall_rules': host.cmd('iptables -L 2>/dev/null || echo "No iptables"').strip().split('\n')[:10]
        }
        
        # System information
        host_details['system_info'] = {
            'hostname': host.cmd('hostname').strip(),
            'uptime': host.cmd('uptime').strip(),
            'memory': host.cmd('free -h').strip().split('\n'),
            'disk': host.cmd('df -h').strip().split('\n'),
            'processes': len(host.cmd('ps aux').strip().split('\n')) - 1
        }
        
        # Performance metrics
        host_details['performance'] = {
            'cpu_usage': _get_cpu_usage(host),
            'memory_usage': _get_memory_usage(host),
            'network_stats': _get_network_performance(host)
        }
        
        # Security status
        host_details['security'] = {
            'open_ports': _get_open_ports(host),
            'running_services': _get_running_services(host),
            'firewall_status': _get_firewall_status(host)
        }
        
        return jsonify(host_details)
        
    except Exception as e:
        logger.error(f"Error getting host details: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/hosts/<host_id>/configure', methods=['POST'])
@log_api_request
def configure_host(host_id):
    """Configure host network settings"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        host = mininet_mgr.net.get(host_id)
        if not host:
            return jsonify({'error': f'Host {host_id} not found'}), 404
        
        config = request.get_json() or {}
        results = []
        
        # Configure IP address
        if 'ip' in config:
            interface = config.get('interface', f'{host_id}-eth0')
            ip_addr = config['ip']
            try:
                result = host.cmd(f'ifconfig {interface} {ip_addr}')
                results.append({
                    'action': 'set_ip',
                    'interface': interface,
                    'ip': ip_addr,
                    'success': True,
                    'output': result.strip()
                })
            except Exception as e:
                results.append({
                    'action': 'set_ip',
                    'interface': interface,
                    'ip': ip_addr,
                    'success': False,
                    'error': str(e)
                })
        
        # Configure default gateway
        if 'gateway' in config:
            gateway = config['gateway']
            try:
                # Remove existing default route
                host.cmd('route del default 2>/dev/null')
                # Add new default route
                result = host.cmd(f'route add default gw {gateway}')
                results.append({
                    'action': 'set_gateway',
                    'gateway': gateway,
                    'success': True,
                    'output': result.strip()
                })
            except Exception as e:
                results.append({
                    'action': 'set_gateway',
                    'gateway': gateway,
                    'success': False,
                    'error': str(e)
                })
        
        # Configure DNS
        if 'dns' in config:
            dns_servers = config['dns'] if isinstance(config['dns'], list) else [config['dns']]
            try:
                dns_config = '\n'.join([f'nameserver {dns}' for dns in dns_servers])
                host.cmd(f'echo "{dns_config}" > /etc/resolv.conf')
                results.append({
                    'action': 'set_dns',
                    'dns_servers': dns_servers,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'action': 'set_dns',
                    'dns_servers': dns_servers,
                    'success': False,
                    'error': str(e)
                })
        
        # Configure hostname
        if 'hostname' in config:
            hostname = config['hostname']
            try:
                host.cmd(f'hostname {hostname}')
                host.cmd(f'echo {hostname} > /etc/hostname')
                results.append({
                    'action': 'set_hostname',
                    'hostname': hostname,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'action': 'set_hostname',
                    'hostname': hostname,
                    'success': False,
                    'error': str(e)
                })
        
        # Add static routes
        if 'routes' in config:
            for route in config['routes']:
                network = route.get('network')
                gateway = route.get('gateway')
                interface = route.get('interface')
                
                try:
                    if gateway:
                        cmd = f'ip route add {network} via {gateway}'
                    elif interface:
                        cmd = f'ip route add {network} dev {interface}'
                    else:
                        continue
                    
                    result = host.cmd(cmd)
                    results.append({
                        'action': 'add_route',
                        'network': network,
                        'gateway': gateway,
                        'interface': interface,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'add_route',
                        'network': network,
                        'success': False,
                        'error': str(e)
                    })
        
        return jsonify({
            'success': True,
            'host_id': host_id,
            'configuration_results': results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error configuring host: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/hosts/<host_id>/services', methods=['GET', 'POST'])
@log_api_request
def manage_host_services(host_id):
    """Manage services on a host"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        host = mininet_mgr.net.get(host_id)
        if not host:
            return jsonify({'error': f'Host {host_id} not found'}), 404
        
        if request.method == 'GET':
            # Get running services
            services = _get_running_services(host)
            return jsonify({
                'host_id': host_id,
                'services': services,
                'timestamp': datetime.now().isoformat()
            })
        
        else:  # POST - Start/stop services
            action = request.json.get('action')
            service_type = request.json.get('service')
            port = request.json.get('port', 8080)
            
            if action == 'start':
                if service_type == 'http':
                    result = host.cmd(f'python3 -m http.server {port} &')
                elif service_type == 'ssh':
                    result = host.cmd('/usr/sbin/sshd -D &')
                elif service_type == 'ftp':
                    result = host.cmd(f'python3 -m pyftpdlib -p {port} &')
                else:
                    return jsonify({'error': f'Unknown service: {service_type}'}), 400
                
                return jsonify({
                    'success': True,
                    'action': 'start',
                    'service': service_type,
                    'port': port,
                    'output': result.strip()
                })
            
            elif action == 'stop':
                if service_type == 'http':
                    result = host.cmd(f'pkill -f "python3 -m http.server"')
                elif service_type == 'ssh':
                    result = host.cmd('pkill sshd')
                elif service_type == 'ftp':
                    result = host.cmd('pkill -f pyftpdlib')
                else:
                    return jsonify({'error': f'Unknown service: {service_type}'}), 400
                
                return jsonify({
                    'success': True,
                    'action': 'stop',
                    'service': service_type,
                    'output': result.strip()
                })
            
            else:
                return jsonify({'error': f'Unknown action: {action}'}), 400
        
    except Exception as e:
        logger.error(f"Error managing host services: {e}")
        return jsonify({'error': str(e)}), 500

# ======================= SWITCH MANAGEMENT =======================

@device_mgmt_bp.route('/switches', methods=['GET'])
@log_api_request
def get_all_switches():
    """Get all switches with detailed OpenFlow information"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        switches_info = []
        for switch in mininet_mgr.net.switches:
            switch_info = {
                'id': switch.name,
                'type': 'switch',
                'dpid': switch.dpid,
                'ports': [],
                'flows': [],
                'controller_connection': {},
                'statistics': {},
                'status': 'active' if mininet_mgr.is_running else 'inactive'
            }
            
            # Get port information
            try:
                ports_output = subprocess.run(
                    ['ovs-ofctl', 'show', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                if ports_output.returncode == 0:
                    switch_info['ports'] = _parse_switch_ports(ports_output.stdout)
            except:
                pass
            
            # Get flow statistics
            try:
                flows_output = subprocess.run(
                    ['ovs-ofctl', 'dump-flows', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                if flows_output.returncode == 0:
                    switch_info['flows'] = _parse_flow_entries(flows_output.stdout)
            except:
                pass
            
            # Get controller connection info
            try:
                controller_output = subprocess.run(
                    ['ovs-vsctl', 'get-controller', switch.name],
                    capture_output=True, text=True, timeout=5
                )
                if controller_output.returncode == 0:
                    switch_info['controller_connection'] = {
                        'controller': controller_output.stdout.strip(),
                        'connected': True
                    }
            except:
                switch_info['controller_connection'] = {'connected': False}
            
            # Get port statistics
            try:
                stats_output = subprocess.run(
                    ['ovs-ofctl', 'dump-ports', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                if stats_output.returncode == 0:
                    switch_info['statistics'] = _parse_port_statistics(stats_output.stdout)
            except:
                pass
            
            switches_info.append(switch_info)
        
        return jsonify({
            'switches': switches_info,
            'count': len(switches_info),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting all switches: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/switches/<switch_id>/flows', methods=['GET', 'POST', 'DELETE'])
@log_api_request
def manage_switch_flows(switch_id):
    """Manage OpenFlow entries on a switch"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        switch = mininet_mgr.net.get(switch_id)
        if not switch:
            return jsonify({'error': f'Switch {switch_id} not found'}), 404
        
        if request.method == 'GET':
            # Get flow entries
            try:
                result = subprocess.run(
                    ['ovs-ofctl', 'dump-flows', switch_id, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    flows = _parse_flow_entries(result.stdout)
                    return jsonify({
                        'switch_id': switch_id,
                        'flows': flows,
                        'flow_count': len(flows),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({'error': f'Failed to get flows: {result.stderr}'}), 500
            except Exception as e:
                return jsonify({'error': f'Error getting flows: {str(e)}'}), 500
        
        elif request.method == 'POST':
            # Add flow entry
            flow_config = request.get_json() or {}
            
            # Build flow entry command
            flow_parts = []
            
            # Priority
            priority = flow_config.get('priority', 100)
            flow_parts.append(f'priority={priority}')
            
            # Match fields
            if 'in_port' in flow_config:
                flow_parts.append(f'in_port={flow_config["in_port"]}')
            if 'eth_src' in flow_config:
                flow_parts.append(f'dl_src={flow_config["eth_src"]}')
            if 'eth_dst' in flow_config:
                flow_parts.append(f'dl_dst={flow_config["eth_dst"]}')
            if 'eth_type' in flow_config:
                flow_parts.append(f'dl_type={flow_config["eth_type"]}')
            if 'ip_src' in flow_config:
                flow_parts.append(f'nw_src={flow_config["ip_src"]}')
            if 'ip_dst' in flow_config:
                flow_parts.append(f'nw_dst={flow_config["ip_dst"]}')
            if 'tcp_src' in flow_config:
                flow_parts.append(f'tp_src={flow_config["tcp_src"]}')
            if 'tcp_dst' in flow_config:
                flow_parts.append(f'tp_dst={flow_config["tcp_dst"]}')
            
            # Actions
            actions = []
            if 'output_port' in flow_config:
                actions.append(f'output:{flow_config["output_port"]}')
            if 'set_vlan' in flow_config:
                actions.append(f'mod_vlan_vid:{flow_config["set_vlan"]}')
            if 'drop' in flow_config and flow_config['drop']:
                actions.append('drop')
            
            if not actions:
                actions.append('normal')
            
            flow_parts.append(f'actions={",".join(actions)}')
            flow_entry = ','.join(flow_parts)
            
            try:
                result = subprocess.run(
                    ['ovs-ofctl', 'add-flow', switch_id, flow_entry, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    return jsonify({
                        'success': True,
                        'switch_id': switch_id,
                        'flow_entry': flow_entry,
                        'message': 'Flow added successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to add flow: {result.stderr}'
                    }), 500
            except Exception as e:
                return jsonify({'error': f'Error adding flow: {str(e)}'}), 500
        
        elif request.method == 'DELETE':
            # Delete flows
            flow_filter = request.args.get('filter', '')
            
            try:
                if flow_filter:
                    result = subprocess.run(
                        ['ovs-ofctl', 'del-flows', switch_id, flow_filter, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=10
                    )
                else:
                    result = subprocess.run(
                        ['ovs-ofctl', 'del-flows', switch_id, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=10
                    )
                
                if result.returncode == 0:
                    return jsonify({
                        'success': True,
                        'switch_id': switch_id,
                        'message': 'Flows deleted successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to delete flows: {result.stderr}'
                    }), 500
            except Exception as e:
                return jsonify({'error': f'Error deleting flows: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Error managing switch flows: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/switches/<switch_id>/ports', methods=['GET', 'POST'])
@log_api_request
def manage_switch_ports(switch_id):
    """Manage switch ports and their configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        switch = mininet_mgr.net.get(switch_id)
        if not switch:
            return jsonify({'error': f'Switch {switch_id} not found'}), 404
        
        if request.method == 'GET':
            # Get port information and statistics
            try:
                # Get port details
                show_result = subprocess.run(
                    ['ovs-ofctl', 'show', switch_id, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                
                # Get port statistics
                stats_result = subprocess.run(
                    ['ovs-ofctl', 'dump-ports', switch_id, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=5
                )
                
                ports_info = []
                if show_result.returncode == 0:
                    ports_info = _parse_switch_ports(show_result.stdout)
                
                if stats_result.returncode == 0:
                    port_stats = _parse_port_statistics(stats_result.stdout)
                    # Merge statistics with port info
                    for port in ports_info:
                        port_num = port.get('port_no')
                        if port_num in port_stats:
                            port['statistics'] = port_stats[port_num]
                
                return jsonify({
                    'switch_id': switch_id,
                    'ports': ports_info,
                    'port_count': len(ports_info),
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                return jsonify({'error': f'Error getting ports: {str(e)}'}), 500
        
        elif request.method == 'POST':
            # Configure port settings
            port_config = request.get_json() or {}
            port_no = port_config.get('port_no')
            
            if not port_no:
                return jsonify({'error': 'Port number required'}), 400
            
            results = []
            
            # Configure port state (up/down)
            if 'admin_state' in port_config:
                state = 'up' if port_config['admin_state'] else 'down'
                try:
                    config = 0 if state == 'up' else 1  # OFPPC_PORT_DOWN = 1
                    result = subprocess.run(
                        ['ovs-ofctl', 'mod-port', switch_id, str(port_no), state, '-O', 'OpenFlow13'],
                        capture_output=True, text=True, timeout=5
                    )
                    results.append({
                        'action': 'set_admin_state',
                        'port_no': port_no,
                        'state': state,
                        'success': result.returncode == 0,
                        'output': result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_admin_state',
                        'port_no': port_no,
                        'success': False,
                        'error': str(e)
                    })
            
            # Configure VLAN
            if 'vlan' in port_config:
                vlan_id = port_config['vlan']
                try:
                    result = subprocess.run(
                        ['ovs-vsctl', 'set', 'port', f'{switch_id}-eth{port_no}', f'tag={vlan_id}'],
                        capture_output=True, text=True, timeout=5
                    )
                    results.append({
                        'action': 'set_vlan',
                        'port_no': port_no,
                        'vlan_id': vlan_id,
                        'success': result.returncode == 0,
                        'output': result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_vlan',
                        'port_no': port_no,
                        'success': False,
                        'error': str(e)
                    })
            
            # Configure QoS
            if 'qos' in port_config:
                qos_config = port_config['qos']
                rate = qos_config.get('rate')  # in bps
                burst = qos_config.get('burst', rate // 10 if rate else 1000)
                
                try:
                    # Set ingress policing
                    if rate:
                        subprocess.run(
                            ['ovs-vsctl', 'set', 'interface', f'{switch_id}-eth{port_no}', 
                             f'ingress_policing_rate={rate}', f'ingress_policing_burst={burst}'],
                            capture_output=True, text=True, timeout=5
                        )
                    
                    results.append({
                        'action': 'set_qos',
                        'port_no': port_no,
                        'rate': rate,
                        'burst': burst,
                        'success': True
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_qos',
                        'port_no': port_no,
                        'success': False,
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'switch_id': switch_id,
                'port_configuration_results': results,
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error managing switch ports: {e}")
        return jsonify({'error': str(e)}), 500

# ======================= ROUTER MANAGEMENT =======================

@device_mgmt_bp.route('/routers', methods=['GET'])
@log_api_request
def get_all_routers():
    """Get all routers with detailed routing information"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        routers_info = []
        for host in mininet_mgr.net.hosts:
            # Check if this is a router
            if hasattr(host, 'node_type') and host.node_type == 'router':
                router_info = {
                    'id': host.name,
                    'type': 'router',
                    'interfaces': [],
                    'routing_table': [],
                    'arp_table': [],
                    'nat_rules': [],
                    'firewall_rules': [],
                    'performance': {},
                    'status': 'active' if mininet_mgr.is_running else 'inactive'
                }
                
                # Get interface information
                if hasattr(host, 'get_interface_info'):
                    router_info['interfaces'] = host.get_interface_info()
                else:
                    # Fallback interface detection
                    for intf in host.intfList():
                        if intf.name != 'lo':
                            intf_info = {
                                'name': intf.name,
                                'ip': intf.IP() if hasattr(intf, 'IP') else 'N/A',
                                'mac': intf.MAC() if hasattr(intf, 'MAC') else 'N/A',
                                'status': 'up' if intf.isUp() else 'down'
                            }
                            router_info['interfaces'].append(intf_info)
                
                # Get routing table
                try:
                    routes_output = host.cmd('ip route show')
                    for line in routes_output.strip().split('\n'):
                        if line.strip():
                            router_info['routing_table'].append(line.strip())
                except:
                    pass
                
                # Get ARP table
                try:
                    arp_output = host.cmd('arp -a')
                    for line in arp_output.strip().split('\n'):
                        if line.strip() and '(' in line:
                            router_info['arp_table'].append(line.strip())
                except:
                    pass
                
                # Get NAT rules
                try:
                    nat_output = host.cmd('iptables -t nat -L -n 2>/dev/null')
                    for line in nat_output.strip().split('\n'):
                        if line.strip() and not line.startswith('Chain') and not line.startswith('target'):
                            router_info['nat_rules'].append(line.strip())
                except:
                    pass
                
                # Get firewall rules
                try:
                    fw_output = host.cmd('iptables -L -n 2>/dev/null')
                    for line in fw_output.strip().split('\n')[:20]:  # Limit output
                        if line.strip() and not line.startswith('Chain') and not line.startswith('target'):
                            router_info['firewall_rules'].append(line.strip())
                except:
                    pass
                
                # Get performance metrics
                router_info['performance'] = {
                    'cpu_usage': _get_cpu_usage(host),
                    'memory_usage': _get_memory_usage(host),
                    'forwarding_enabled': _check_ip_forwarding(host)
                }
                
                routers_info.append(router_info)
        
        return jsonify({
            'routers': routers_info,
            'count': len(routers_info),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting all routers: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/routers/<router_id>/routing', methods=['GET', 'POST', 'DELETE'])
@log_api_request
def manage_router_routing(router_id):
    """Manage routing table on a router"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        router = mininet_mgr.net.get(router_id)
        if not router:
            return jsonify({'error': f'Router {router_id} not found'}), 404
        
        if request.method == 'GET':
            # Get routing table with detailed information
            routing_info = {
                'router_id': router_id,
                'routing_table': [],
                'default_route': None,
                'static_routes': [],
                'connected_routes': [],
                'forwarding_enabled': _check_ip_forwarding(router)
            }
            
            try:
                routes_output = router.cmd('ip route show')
                for line in routes_output.strip().split('\n'):
                    if line.strip():
                        route_info = _parse_route_entry(line.strip())
                        routing_info['routing_table'].append(route_info)
                        
                        if route_info['type'] == 'default':
                            routing_info['default_route'] = route_info
                        elif route_info['type'] == 'static':
                            routing_info['static_routes'].append(route_info)
                        elif route_info['type'] == 'connected':
                            routing_info['connected_routes'].append(route_info)
            except Exception as e:
                routing_info['error'] = str(e)
            
            return jsonify(routing_info)
        
        elif request.method == 'POST':
            # Add routing entries
            route_config = request.get_json() or {}
            results = []
            
            # Add static route
            if 'destination' in route_config:
                destination = route_config['destination']
                gateway = route_config.get('gateway')
                interface = route_config.get('interface')
                metric = route_config.get('metric')
                
                try:
                    cmd_parts = ['ip', 'route', 'add', destination]
                    
                    if gateway:
                        cmd_parts.extend(['via', gateway])
                    if interface:
                        cmd_parts.extend(['dev', interface])
                    if metric:
                        cmd_parts.extend(['metric', str(metric)])
                    
                    result = router.cmd(' '.join(cmd_parts))
                    results.append({
                        'action': 'add_route',
                        'destination': destination,
                        'gateway': gateway,
                        'interface': interface,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'add_route',
                        'destination': destination,
                        'success': False,
                        'error': str(e)
                    })
            
            # Set default route
            if 'default_gateway' in route_config:
                gateway = route_config['default_gateway']
                try:
                    # Remove existing default route
                    router.cmd('ip route del default 2>/dev/null')
                    # Add new default route
                    result = router.cmd(f'ip route add default via {gateway}')
                    results.append({
                        'action': 'set_default_route',
                        'gateway': gateway,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_default_route',
                        'gateway': gateway,
                        'success': False,
                        'error': str(e)
                    })
            
            # Enable/disable IP forwarding
            if 'ip_forwarding' in route_config:
                enable = route_config['ip_forwarding']
                try:
                    value = '1' if enable else '0'
                    router.cmd(f'echo {value} > /proc/sys/net/ipv4/ip_forward')
                    router.cmd(f'sysctl net.ipv4.ip_forward={value}')
                    results.append({
                        'action': 'set_ip_forwarding',
                        'enabled': enable,
                        'success': True
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_ip_forwarding',
                        'enabled': enable,
                        'success': False,
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'router_id': router_id,
                'routing_results': results,
                'timestamp': datetime.now().isoformat()
            })
        
        elif request.method == 'DELETE':
            # Delete routing entries
            destination = request.args.get('destination')
            
            if destination:
                try:
                    if destination == 'default':
                        result = router.cmd('ip route del default')
                    else:
                        result = router.cmd(f'ip route del {destination}')
                    
                    return jsonify({
                        'success': True,
                        'router_id': router_id,
                        'deleted_route': destination,
                        'output': result.strip()
                    })
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': str(e)
                    }), 500
            else:
                return jsonify({'error': 'Destination required for route deletion'}), 400
        
    except Exception as e:
        logger.error(f"Error managing router routing: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/routers/<router_id>/nat', methods=['GET', 'POST', 'DELETE'])
@log_api_request
def manage_router_nat(router_id):
    """Manage NAT rules on a router"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        router = mininet_mgr.net.get(router_id)
        if not router:
            return jsonify({'error': f'Router {router_id} not found'}), 404
        
        if request.method == 'GET':
            # Get NAT rules
            nat_info = {
                'router_id': router_id,
                'nat_rules': {
                    'PREROUTING': [],
                    'POSTROUTING': [],
                    'OUTPUT': []
                },
                'masquerade_rules': []
            }
            
            try:
                nat_output = router.cmd('iptables -t nat -L -n --line-numbers 2>/dev/null')
                current_chain = None
                
                for line in nat_output.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('Chain'):
                        current_chain = line.split()[1]
                    elif line and not line.startswith('num') and current_chain:
                        if current_chain in nat_info['nat_rules']:
                            rule_info = _parse_nat_rule(line)
                            nat_info['nat_rules'][current_chain].append(rule_info)
                            
                            if 'MASQUERADE' in line:
                                nat_info['masquerade_rules'].append(rule_info)
            except Exception as e:
                nat_info['error'] = str(e)
            
            return jsonify(nat_info)
        
        elif request.method == 'POST':
            # Add NAT rules
            nat_config = request.get_json() or {}
            results = []
            
            # Add MASQUERADE rule
            if 'masquerade' in nat_config:
                interface = nat_config['masquerade'].get('interface')
                source_network = nat_config['masquerade'].get('source_network')
                
                try:
                    cmd = 'iptables -t nat -A POSTROUTING'
                    if source_network:
                        cmd += f' -s {source_network}'
                    if interface:
                        cmd += f' -o {interface}'
                    cmd += ' -j MASQUERADE'
                    
                    result = router.cmd(cmd)
                    results.append({
                        'action': 'add_masquerade',
                        'interface': interface,
                        'source_network': source_network,
                        'success': True,
                        'command': cmd
                    })
                except Exception as e:
                    results.append({
                        'action': 'add_masquerade',
                        'success': False,
                        'error': str(e)
                    })
            
            # Add DNAT rule (port forwarding)
            if 'dnat' in nat_config:
                dnat_rule = nat_config['dnat']
                external_port = dnat_rule.get('external_port')
                internal_ip = dnat_rule.get('internal_ip')
                internal_port = dnat_rule.get('internal_port', external_port)
                protocol = dnat_rule.get('protocol', 'tcp')
                
                try:
                    cmd = f'iptables -t nat -A PREROUTING -p {protocol} --dport {external_port} -j DNAT --to-destination {internal_ip}:{internal_port}'
                    result = router.cmd(cmd)
                    results.append({
                        'action': 'add_dnat',
                        'external_port': external_port,
                        'internal_ip': internal_ip,
                        'internal_port': internal_port,
                        'protocol': protocol,
                        'success': True,
                        'command': cmd
                    })
                except Exception as e:
                    results.append({
                        'action': 'add_dnat',
                        'success': False,
                        'error': str(e)
                    })
            
            # Add SNAT rule
            if 'snat' in nat_config:
                snat_rule = nat_config['snat']
                source_network = snat_rule.get('source_network')
                to_source = snat_rule.get('to_source')
                
                try:
                    cmd = f'iptables -t nat -A POSTROUTING -s {source_network} -j SNAT --to-source {to_source}'
                    result = router.cmd(cmd)
                    results.append({
                        'action': 'add_snat',
                        'source_network': source_network,
                        'to_source': to_source,
                        'success': True,
                        'command': cmd
                    })
                except Exception as e:
                    results.append({
                        'action': 'add_snat',
                        'success': False,
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'router_id': router_id,
                'nat_results': results,
                'timestamp': datetime.now().isoformat()
            })
        
        elif request.method == 'DELETE':
            # Delete NAT rules
            chain = request.args.get('chain', 'POSTROUTING')
            rule_number = request.args.get('rule_number')
            
            try:
                if rule_number:
                    result = router.cmd(f'iptables -t nat -D {chain} {rule_number}')
                else:
                    # Flush all rules in chain
                    result = router.cmd(f'iptables -t nat -F {chain}')
                
                return jsonify({
                    'success': True,
                    'router_id': router_id,
                    'deleted_chain': chain,
                    'deleted_rule': rule_number,
                    'output': result.strip()
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
    except Exception as e:
        logger.error(f"Error managing router NAT: {e}")
        return jsonify({'error': str(e)}), 500

# ======================= CONTROLLER MANAGEMENT =======================

@device_mgmt_bp.route('/controllers', methods=['GET'])
@log_api_request
def get_all_controllers():
    """Get all controllers with detailed status"""
    try:
        mininet_mgr = get_mininet_manager()
        
        controllers_info = []
        
        # Get Ryu controller info
        ryu_status = mininet_mgr.get_controller_status()
        ryu_info = {
            'id': 'ryu_controller',
            'type': 'ryu',
            'status': ryu_status,
            'applications': [],
            'connections': [],
            'statistics': {},
            'logs': []
        }
        
        if ryu_status.get('running'):
            # Get controller statistics
            try:
                ryu_info['statistics'] = mininet_mgr.ryu_controller.get_controller_stats()
            except:
                pass
            
            # Get recent logs
            try:
                logs = mininet_mgr.get_controller_logs()
                ryu_info['logs'] = logs.get('logs', [])[-20:]  # Last 20 log entries
            except:
                pass
            
            # Get connected switches
            if mininet_mgr.net:
                for switch in mininet_mgr.net.switches:
                    try:
                        controller_output = subprocess.run(
                            ['ovs-vsctl', 'get-controller', switch.name],
                            capture_output=True, text=True, timeout=5
                        )
                        if controller_output.returncode == 0 and 'tcp:' in controller_output.stdout:
                            ryu_info['connections'].append({
                                'switch_id': switch.name,
                                'dpid': switch.dpid,
                                'controller_address': controller_output.stdout.strip(),
                                'connected': True
                            })
                    except:
                        pass
        
        controllers_info.append(ryu_info)
        
        # Get OpenFlow controllers from topology data
        mininet_mgr.update_topology_data()
        for controller in mininet_mgr.topology_data.get('controllers', []):
            if controller['id'] != 'ryu_controller':
                controllers_info.append(controller)
        
        return jsonify({
            'controllers': controllers_info,
            'count': len(controllers_info),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting all controllers: {e}")
        return jsonify({'error': str(e)}), 500

@device_mgmt_bp.route('/controllers/<controller_id>/flows', methods=['GET'])
@log_api_request
def get_controller_flows(controller_id):
    """Get flows managed by the controller across all switches"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        all_flows = {}
        flow_summary = {
            'total_flows': 0,
            'flows_by_table': {},
            'flows_by_priority': {},
            'switches': []
        }
        
        for switch in mininet_mgr.net.switches:
            try:
                result = subprocess.run(
                    ['ovs-ofctl', 'dump-flows', switch.name, '-O', 'OpenFlow13'],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    switch_flows = _parse_flow_entries(result.stdout)
                    all_flows[switch.name] = switch_flows
                    flow_summary['switches'].append(switch.name)
                    flow_summary['total_flows'] += len(switch_flows)
                    
                    # Analyze flows by table and priority
                    for flow in switch_flows:
                        table = flow.get('table', 0)
                        priority = flow.get('priority', 0)
                        
                        if table not in flow_summary['flows_by_table']:
                            flow_summary['flows_by_table'][table] = 0
                        flow_summary['flows_by_table'][table] += 1
                        
                        if priority not in flow_summary['flows_by_priority']:
                            flow_summary['flows_by_priority'][priority] = 0
                        flow_summary['flows_by_priority'][priority] += 1
                        
            except Exception as e:
                all_flows[switch.name] = {'error': str(e)}
        
        return jsonify({
            'controller_id': controller_id,
            'flows_by_switch': all_flows,
            'summary': flow_summary,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting controller flows: {e}")
        return jsonify({'error': str(e)}), 500

# ======================= UTILITY FUNCTIONS =======================

def _get_interface_stats(host, interface):
    """Get interface statistics"""
    try:
        stats_output = host.cmd(f'cat /proc/net/dev | grep {interface}')
        if stats_output.strip():
            parts = stats_output.strip().split()
            if len(parts) >= 17:
                return {
                    'rx_bytes': int(parts[1]),
                    'rx_packets': int(parts[2]),
                    'rx_errors': int(parts[3]),
                    'rx_dropped': int(parts[4]),
                    'tx_bytes': int(parts[9]),
                    'tx_packets': int(parts[10]),
                    'tx_errors': int(parts[11]),
                    'tx_dropped': int(parts[12])
                }
    except:
        pass
    return {}

def _get_cpu_usage(host):
    """Get CPU usage percentage"""
    try:
        cpu_output = host.cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        return float(cpu_output.strip().replace('us,', '')) if cpu_output.strip() else 0.0
    except:
        return 0.0

def _get_memory_usage(host):
    """Get memory usage information"""
    try:
        mem_output = host.cmd('free -m')
        lines = mem_output.strip().split('\n')
        if len(lines) >= 2:
            mem_line = lines[1].split()
            if len(mem_line) >= 3:
                total = int(mem_line[1])
                used = int(mem_line[2])
                return {
                    'total_mb': total,
                    'used_mb': used,
                    'free_mb': total - used,
                    'usage_percent': round((used / total) * 100, 2) if total > 0 else 0
                }
    except:
        pass
    return {}

def _get_network_performance(host):
    """Get network performance metrics"""
    try:
        # Simple network performance check
        return {
            'interfaces_up': len([intf for intf in host.intfList() if intf.isUp() and intf.name != 'lo']),
            'total_interfaces': len([intf for intf in host.intfList() if intf.name != 'lo'])
        }
    except:
        return {}

def _get_open_ports(host):
    """Get open ports on host"""
    try:
        netstat_output = host.cmd('netstat -tuln 2>/dev/null | grep LISTEN')
        ports = []
        for line in netstat_output.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    local_address = parts[3]
                    if ':' in local_address:
                        port = local_address.split(':')[-1]
                        protocol = parts[0]
                        ports.append({'port': port, 'protocol': protocol})
        return ports
    except:
        return []

def _get_running_services(host):
    """Get running services on host"""
    try:
        ps_output = host.cmd('ps aux | grep -E "(ssh|http|ftp|telnet|nginx|apache)" | grep -v grep')
        services = []
        for line in ps_output.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 11:
                    services.append({
                        'pid': parts[1],
                        'command': ' '.join(parts[10:]),
                        'cpu_percent': parts[2],
                        'memory_percent': parts[3]
                    })
        return services
    except:
        return []

def _get_firewall_status(host):
    """Get firewall status"""
    try:
        iptables_output = host.cmd('iptables -L -n 2>/dev/null | head -20')
        return {
            'enabled': 'Chain' in iptables_output,
            'rules_count': len(iptables_output.strip().split('\n')) - 3 if 'Chain' in iptables_output else 0
        }
    except:
        return {'enabled': False, 'rules_count': 0}
    
def _get_firewall_status(host):
    """Get firewall status and rules"""
    try:
        # Fetch all rules in a parsable format
        iptables_output = host.cmd('iptables -L -n --line-numbers 2>/dev/null')
        lines = iptables_output.strip().split('\n')

        if 'Chain' not in iptables_output:
            return {
                'enabled': False,
                'rules_count': 0,
                'rules': []
            }

        # Skip the header lines for each chain
        rules = []
        current_chain = None
        for line in lines:
            if line.startswith('Chain'):
                # Example: Chain INPUT (policy ACCEPT)
                parts = line.split()
                if len(parts) >= 2:
                    current_chain = parts[1]
            elif line.strip() and not line.lower().startswith('num'):
                # Treat the full line as a rule
                rules.append({
                    'chain': current_chain,
                    'rule': line.strip()
                })

        return {
            'enabled': True,
            'rules_count': len(rules),
            'rules': rules
        }

    except Exception:
        return {
            'enabled': False,
            'rules_count': 0,
            'rules': []
        }


def _parse_switch_ports(output):
    """Parse switch port information from ovs-ofctl show output"""
    ports = []
    for line in output.split('\n'):
        line = line.strip()
        if re.match(r'^\d+\(', line):  # Port line format: "1(s1-eth1): addr:..."
            port_match = re.match(r'^(\d+)\(([^)]+)\):\s+addr:([a-f0-9:]+)', line)
            if port_match:
                port_no, name, addr = port_match.groups()
                ports.append({
                    'port_no': int(port_no),
                    'name': name,
                    'hw_addr': addr,
                    'config': 'UP' if 'DOWN' not in line else 'DOWN',
                    'state': 'LIVE' if 'LIVE' in line else 'DOWN'
                })
    return ports

def _parse_flow_entries(output):
    """Parse flow entries from ovs-ofctl dump-flows output"""
    flows = []
    for line in output.split('\n'):
        line = line.strip()
        if 'cookie=' in line:
            flow = {'raw': line}
            
            # Extract basic flow information
            if 'priority=' in line:
                priority_match = re.search(r'priority=(\d+)', line)
                if priority_match:
                    flow['priority'] = int(priority_match.group(1))
            
            if 'table=' in line:
                table_match = re.search(r'table=(\d+)', line)
                if table_match:
                    flow['table'] = int(table_match.group(1))
            
            if 'n_packets=' in line:
                packets_match = re.search(r'n_packets=(\d+)', line)
                if packets_match:
                    flow['packet_count'] = int(packets_match.group(1))
            
            if 'n_bytes=' in line:
                bytes_match = re.search(r'n_bytes=(\d+)', line)
                if bytes_match:
                    flow['byte_count'] = int(bytes_match.group(1))
            
            # Extract match fields
            if 'in_port=' in line:
                port_match = re.search(r'in_port=(\d+)', line)
                if port_match:
                    flow['in_port'] = int(port_match.group(1))
            
            # Extract actions
            actions_match = re.search(r'actions=([^\s]+)', line)
            if actions_match:
                flow['actions'] = actions_match.group(1)
            
            flows.append(flow)
    
    return flows



def _parse_port_statistics(output):
    """Parse port statistics from ovs-ofctl dump-ports output."""
    stats = {}
    current_port = None

    for line in output.split('\n'):
        line = line.strip()

        # Detect a new port header, e.g. "port 1:" or "port LOCAL:"
        port_match = re.match(r'^port\s+(\d+|LOCAL):', line)
        if port_match:
            # Always keep the port ID as a string
            current_port = port_match.group(1)
            stats[current_port] = {}
            continue

        # If we have a current_port context, parse rx/tx stats
        if current_port is not None:
            # rx packets and bytes
            rx_match = re.search(r'rx pkts=(\d+),\s*bytes=(\d+)', line)
            if rx_match:
                stats[current_port]['rx_packets'] = int(rx_match.group(1))
                stats[current_port]['rx_bytes']   = int(rx_match.group(2))

            # tx packets and bytes
            tx_match = re.search(r'tx pkts=(\d+),\s*bytes=(\d+)', line)
            if tx_match:
                stats[current_port]['tx_packets'] = int(tx_match.group(1))
                stats[current_port]['tx_bytes']   = int(tx_match.group(2))

    return stats

def _check_ip_forwarding(router):
    """Check if IP forwarding is enabled on router"""
    try:
        result = router.cmd('cat /proc/sys/net/ipv4/ip_forward')
        return result.strip() == '1'
    except:
        return False

def _parse_route_entry(route_line):
    """Parse a single routing table entry"""
    parts = route_line.split()
    route_info = {'raw': route_line, 'type': 'unknown'}
    
    if route_line.startswith('default'):
        route_info['type'] = 'default'
        route_info['destination'] = 'default'
        if 'via' in parts:
            via_index = parts.index('via')
            if via_index + 1 < len(parts):
                route_info['gateway'] = parts[via_index + 1]
    elif '/' in parts[0]:  # Network route
        route_info['type'] = 'static' if 'via' in parts else 'connected'
        route_info['destination'] = parts[0]
        if 'via' in parts:
            via_index = parts.index('via')
            if via_index + 1 < len(parts):
                route_info['gateway'] = parts[via_index + 1]
        if 'dev' in parts:
            dev_index = parts.index('dev')
            if dev_index + 1 < len(parts):
                route_info['interface'] = parts[dev_index + 1]
    
    return route_info

def _parse_nat_rule(rule_line):
    """Parse NAT rule from iptables output"""
    parts = rule_line.split()
    rule_info = {'raw': rule_line}
    
    if len(parts) >= 4:
        rule_info['rule_number'] = parts[0] if parts[0].isdigit() else None
        rule_info['target'] = parts[1] if len(parts) > 1 else None
        rule_info['protocol'] = parts[2] if len(parts) > 2 else None
        rule_info['option'] = parts[3] if len(parts) > 3 else None
        rule_info['source'] = parts[4] if len(parts) > 4 else None
        rule_info['destination'] = parts[5] if len(parts) > 5 else None
    
    return rule_info

# ======================= BULK CONFIG APPLY =======================



# Enhanced apply_config() function with comprehensive CRUD support

# ======================= ENHANCED APPLY CONFIG =======================

@device_mgmt_bp.route('/apply-config', methods=['POST'])
@log_api_request
def apply_config():
    """
    Enhanced apply configuration endpoint with modular design.
    
    This function orchestrates the entire configuration application process
    by delegating specific tasks to specialized functions in config_manager.py.
    """
    try:
        # Phase 1: Validate request and setup
        spec, validate_only, mininet_mgr, error_response = validate_request_and_setup()
        if error_response:
            return jsonify(error_response[0]), error_response[1]
        
        logger.info(f"Starting configuration application - validate_only: {validate_only}")
        logger.info(f"Configuration spec summary: {len(spec.get('routers', {}))} routers, "
                   f"{len(spec.get('hosts', {}))} hosts, {len(spec.get('switches', {}))} switches")
        
        # Phase 2: Initialize command planner
        planner = CommandPlanner()
        configuration_errors = []
        
        # Phase 3: Process router configurations
        router_configs = spec.get('routers', {})
        logger.info(f"Processing {len(router_configs)} router configurations")
        
        for rtr_name, rtr_cfg in router_configs.items():
            logger.debug(f"Processing router {rtr_name} with config keys: {list(rtr_cfg.keys())}")
            error = process_router_configuration(planner, mininet_mgr, rtr_name, rtr_cfg)
            if error:
                configuration_errors.append(error)
                logger.warning(f"Router configuration error for {rtr_name}: {error}")
        
        # Phase 4: Process host configurations
        host_configs = spec.get('hosts', {})
        logger.info(f"Processing {len(host_configs)} host configurations")
        
        for host_name, host_cfg in host_configs.items():
            logger.debug(f"Processing host {host_name} with config keys: {list(host_cfg.keys())}")
            error = process_host_configuration(planner, mininet_mgr, host_name, host_cfg)
            if error:
                configuration_errors.append(error)
                logger.warning(f"Host configuration error for {host_name}: {error}")
        
        # Phase 5: Process switch configurations
        switch_configs = spec.get('switches', {})
        logger.info(f"Processing {len(switch_configs)} switch configurations")
        
        for sw_name, sw_cfg in switch_configs.items():
            logger.debug(f"Processing switch {sw_name} with config keys: {list(sw_cfg.keys())}")
            error = process_switch_configuration(planner, mininet_mgr, sw_name, sw_cfg)
            if error:
                configuration_errors.append(error)
                logger.warning(f"Switch configuration error for {sw_name}: {error}")
        
        # Log planning summary
        plan_size = len(planner.get_plan())
        logger.info(f"Generated execution plan with {plan_size} commands")
        
        if configuration_errors:
            logger.warning(f"Found {len(configuration_errors)} configuration errors during planning")
            for error in configuration_errors:
                logger.warning(f"  - {error}")
        
        # Phase 6: Handle validation-only mode
        if validate_only:
            logger.info("Returning validation-only plan")
            return jsonify({
                'validate_only': True,
                'plan': planner.get_plan(),
                'configuration_errors': configuration_errors,
                'plan_size': plan_size,
                'timestamp': datetime.now().isoformat()
            })
        
        # Phase 7: Execute command plan
        logger.info(f"Executing command plan with {plan_size} commands")
        if plan_size > 0:
            execute_command_plan(planner, mininet_mgr)
        else:
            logger.info("No commands to execute")
        
        # Phase 8: Calculate results and return response
        results = planner.get_results()
        summary = calculate_execution_summary(results)
        
        logger.info(f"Configuration application completed")
        logger.info(f"Execution summary: {summary}")
        
        # Log any failed commands
        failed_results = [r for r in results if not r.get('success', False)]
        if failed_results:
            logger.warning(f"Found {len(failed_results)} failed commands:")
            for result in failed_results:
                logger.warning(f"  - {result['node']}: {result.get('error', 'Unknown error')}")
        
        # Log any warnings
        warning_results = [r for r in results if r.get('warning', False)]
        if warning_results:
            logger.info(f"Found {len(warning_results)} commands with warnings:")
            for result in warning_results:
                logger.info(f"  - {result['node']}: {result.get('output', 'No output')}")
        
        # Determine overall success
        overall_success = summary['failed'] == 0 and len(configuration_errors) == 0
        
        # Track configuration application for snapshots
        try:
            mininet_mgr.track_api_operation(
                operation_type='apply_config',
                operation_data={
                    'routers': list(router_configs.keys()),
                    'hosts': list(host_configs.keys()),
                    'switches': list(switch_configs.keys()),
                    'total_commands': plan_size
                },
                result={
                    'success': overall_success,
                    'applied': summary['successful'],
                    'failed': summary['failed'],
                    'warnings': summary['warnings']
                }
            )
            
            # Track individual device configurations
            # Track router configurations
            for device_name, config_data in router_configs.items():
                device_results = [r for r in results if r.get('node') == device_name]
                mininet_mgr.track_device_configuration(
                    device_name=device_name,
                    config_type='router_config',
                    config_data=config_data,
                    result={
                        'success': all(r.get('success', False) for r in device_results),
                        'commands_applied': len(device_results),
                        'results': device_results
                    }
                )
            
            # Track host configurations
            for device_name, config_data in host_configs.items():
                device_results = [r for r in results if r.get('node') == device_name]
                mininet_mgr.track_device_configuration(
                    device_name=device_name,
                    config_type='host_config',
                    config_data=config_data,
                    result={
                        'success': all(r.get('success', False) for r in device_results),
                        'commands_applied': len(device_results),
                        'results': device_results
                    }
                )
            
            # Track switch configurations
            for device_name, config_data in switch_configs.items():
                device_results = [r for r in results if r.get('node') == device_name]
                mininet_mgr.track_device_configuration(
                    device_name=device_name,
                    config_type='switch_config',
                    config_data=config_data,
                    result={
                        'success': all(r.get('success', False) for r in device_results),
                        'commands_applied': len(device_results),
                        'results': device_results
                    }
                )
        except Exception as e:
            logger.warning(f"Error tracking configuration application: {e}")
        
        response_data = {
            'success': overall_success,
            'applied': summary['successful'],
            'failed': summary['failed'],
            'warnings': summary['warnings'],
            'ignored_errors': summary['ignored_errors'],
            'configuration_errors': configuration_errors,
            'results': results,
            'summary': summary,
            'plan': planner.get_plan() if spec.get('include_plan', False) else None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add detailed summary for logging
        logger.info(f"Final response: success={overall_success}, "
                   f"applied={summary['successful']}, failed={summary['failed']}, "
                   f"warnings={summary['warnings']}, config_errors={len(configuration_errors)}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Fatal error in apply_config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e), 
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

# Keep all other existing endpoints from the original file...
# (Include all the other endpoints from your original device_management.py file here)

# ======================= DEVICE SNAPSHOTS (READ-ONLY) =======================

@device_mgmt_bp.route('/devices/snapshots', methods=['GET'])
@log_api_request
def list_device_snapshots():
    """
    GET /api/device-management/devices/snapshots?detail=summary|full
      - Returns snapshots for ALL devices (hosts, switches, routers, controllers)
    """
    try:
        mininet_mgr = get_mininet_manager()
        detail = (request.args.get('detail') or 'summary').lower()

        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        payload = {
            'routers': [],
            'hosts': [],
            'switches': [],
            'controllers': [],
            'timestamp': datetime.now().isoformat()
        }

        # -------- Routers --------
        for r in getattr(mininet_mgr.net, 'routers', []):
            payload['routers'].append(_build_router_snapshot(r, detail))

        # Some topologies use hosts as routers; try nodes named r*
        if not payload['routers']:
            for h in mininet_mgr.net.hosts:
                if h.name.startswith('r'):
                    payload['routers'].append(_build_router_snapshot(h, detail))

        # -------- Hosts --------
        for h in mininet_mgr.net.hosts:
            if not h.name.startswith('r'):  # skip routers already captured above if they’re hosts
                payload['hosts'].append(_build_host_snapshot(h, detail))

        # -------- Switches --------
        for s in mininet_mgr.net.switches:
            payload['switches'].append(_build_switch_snapshot(s, detail))

        # -------- Controllers --------
        try:
            ryu_status = mininet_mgr.get_controller_status()
            payload['controllers'].append(_build_controller_snapshot(mininet_mgr, ryu_status, detail))
        except Exception as e:
            payload['controllers'].append({'id': 'ryu_controller', 'error': str(e)})

        return jsonify({'success': True, 'devices': payload})
    except Exception as e:
        logger.error(f"Error listing device snapshots: {e}")
        return jsonify({'error': str(e)}), 500


@device_mgmt_bp.route('/devices/<device_id>/snapshot', methods=['GET'])
@log_api_request
def get_device_snapshot(device_id):
    """
    GET /api/device-management/devices/<device_id>/snapshot?detail=summary|full
      - Returns snapshot for a SINGLE device (host/router/switch/controller)
    """
    try:
        mininet_mgr = get_mininet_manager()
        detail = (request.args.get('detail') or 'full').lower()

        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        # Try as node
        try:
            node = mininet_mgr.net.get(device_id)
        except Exception:
            node = None

        # Controller is special (not a Mininet node)
        if device_id in ('ryu', 'ryu_controller', 'controller'):
            ryu_status = mininet_mgr.get_controller_status()
            return jsonify({'success': True, 'device': _build_controller_snapshot(mininet_mgr, ryu_status, detail)})

        if not node:
            return jsonify({'error': f'Device {device_id} not found'}), 404

        # Heuristics for type
        dtype = 'host'
        if node in getattr(mininet_mgr.net, 'switches', []):
            dtype = 'switch'
        elif node in getattr(mininet_mgr.net, 'hosts', []) and node.name.startswith('r'):
            dtype = 'router'

        if dtype == 'router':
            snap = _build_router_snapshot(node, detail)
        elif dtype == 'switch':
            snap = _build_switch_snapshot(node, detail)
        else:
            snap = _build_host_snapshot(node, detail)

        return jsonify({'success': True, 'device': snap})
    except Exception as e:
        logger.error(f"Error getting device snapshot for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------- SNAPSHOT BUILDERS ----------------------

def _build_host_snapshot(host, detail='summary'):
    # Current IPs (ip addr), MAC, hostname, DNS, services, routes, interfaces
    try:
        ip_show = host.cmd('ip -o -4 addr show | awk \'{print $2,$4}\'').strip()
        addrs = []
        for line in ip_show.splitlines():
            if not line.strip():
                continue
            ifname, cidr = line.split()
            addrs.append({'interface': ifname, 'address': cidr})

        mac = host.MAC() if hasattr(host, 'MAC') else None
        hostname = host.cmd('hostname').strip()
        dns = [_ for _ in host.cmd("grep -E '^nameserver ' /etc/resolv.conf 2>/dev/null | awk '{print $2}'").split() if _]
        default_gw = host.cmd("ip route show default 2>/dev/null | awk '/default/ {print $3}'").strip() or None

        snap = {
            'id': host.name,
            'type': 'host',
            'summary': {
                'current_ip': (addrs[0]['address'] if addrs else None),
                'mac': mac,
                'gateway': default_gw,
                'dns': dns
            }
        }

        if detail == 'full':
            snap['interfaces'] = addrs
            snap['routes'] = _read_routes(host)
            snap['services'] = _get_running_services(host)
            snap['open_ports'] = _get_open_ports(host)
            snap['firewall'] = _get_firewall_status(host)
            snap['ifstats'] = _read_ifstats(host)

        return snap
    except Exception as e:
        return {'id': host.name, 'type': 'host', 'error': str(e)}


def _build_router_snapshot(router, detail='summary'):
    try:
        ip_forward = _check_ip_forwarding(router)
        nat_status = _nat_enabled(router)
        # Count configured L3 interfaces (with IPv4 addresses)
        intfs = _read_ipv4_interfaces(router)

        snap = {
            'id': router.name,
            'type': 'router',
            'summary': {
                'ip_forwarding': bool(ip_forward),
                'nat_enabled': bool(nat_status),
                'configured_interfaces': len(intfs),
                'routing_protocol': 'static'  # current system assumes static
            }
        }

        if detail == 'full':
            snap['interfaces'] = intfs
            snap['routes'] = _read_routes(router)
            snap['nat'] = _read_nat(router)
            snap['firewall'] = _get_firewall_status(router)
            firewall_info = _get_firewall_status(router)
            snap['firewall']['rules'] = firewall_info.get('rules', [])
            snap['ifstats'] = _read_ifstats(router)

        return snap
    except Exception as e:
        return {'id': router.name, 'type': 'router', 'error': str(e)}


def _build_switch_snapshot(sw, detail='summary'):
    try:
        # Controller & fail-mode
        ctrl = subprocess.run(['ovs-vsctl', 'get-controller', sw.name], capture_output=True, text=True, timeout=5)
        controller = ctrl.stdout.strip() if ctrl.returncode == 0 else ''
        failmode = subprocess.run(['ovs-vsctl', 'get-fail-mode', sw.name], capture_output=True, text=True, timeout=5)
        fail_mode = failmode.stdout.strip() if failmode.returncode == 0 else ''

        snap = {
            'id': sw.name,
            'type': 'switch',
            'summary': {
                'controller': controller or None,
                'fail_mode': fail_mode or None,
            }
        }

        if detail == 'full':
            # OF version, DPID, flows, port stats
            show = subprocess.run(['ovs-ofctl', 'show', sw.name], capture_output=True, text=True, timeout=5)
            dpid = None
            of_ver = None
            if show.returncode == 0:
                m = re.search(r'datapath\s+id:\s*([0-9a-f]+)', show.stdout, re.I)
                if m: dpid = m.group(1)
                m = re.search(r'OpenFlow\s+(\d+\.\d+)', show.stdout, re.I)
                if m: of_ver = m.group(1)

            flows_out = subprocess.run(['ovs-ofctl', 'dump-flows', sw.name, '-O', 'OpenFlow13'], capture_output=True, text=True, timeout=10)
            flows = _parse_flow_entries(flows_out.stdout) if flows_out.returncode == 0 else []

            ports_stats = subprocess.run(['ovs-ofctl', 'dump-ports', sw.name, '-O', 'OpenFlow13'], capture_output=True, text=True, timeout=10)
            port_stats = _parse_port_statistics(ports_stats.stdout) if ports_stats.returncode == 0 else {}

            snap['openflow'] = {'version': of_ver, 'dpid': dpid}
            snap['connections'] = {'controller': controller, 'status': 'connected' if controller else 'disconnected'}
            snap['flows'] = {'count': len(flows), 'entries': flows}
            snap['port_statistics'] = port_stats

        return snap
    except Exception as e:
        return {'id': sw.name, 'type': 'switch', 'error': str(e)}


def _build_controller_snapshot(mininet_mgr, ryu_status, detail='summary'):
    snap = {
        'id': 'ryu_controller',
        'type': 'controller',
        'summary': {
            'running': bool(ryu_status.get('running')),
            'controller_type': 'ryu',
            'port': ryu_status.get('port', 6633),
            'connections': 0
        }
    }

    if not ryu_status.get('running'):
        return snap

    # Count connected switches
    connections = []
    try:
        if mininet_mgr.net:
            for sw in mininet_mgr.net.switches:
                co = subprocess.run(['ovs-vsctl', 'get-controller', sw.name], capture_output=True, text=True, timeout=5)
                if co.returncode == 0 and 'tcp:' in co.stdout:
                    connections.append({'switch_id': sw.name, 'controller_address': co.stdout.strip(), 'connected': True})
    except Exception:
        pass

    snap['summary']['connections'] = len(connections)

    if detail == 'full':
        # stats & logs if available
        try:
            stats = mininet_mgr.ryu_controller.get_controller_stats()
        except Exception:
            stats = {}
        try:
            logs = mininet_mgr.get_controller_logs().get('logs', [])[-50:]
        except Exception:
            logs = []

        snap['statistics'] = stats
        snap['connections'] = connections
        snap['logs'] = logs

    return snap


# ---------------------- LOW-LEVEL READERS ----------------------

def _nat_enabled(router):
    try:
        out = router.cmd('iptables -t nat -S 2>/dev/null | grep -c MASQUERADE')
        return int(out.strip() or '0') > 0
    except:
        return False

def _read_nat(router):
    info = {'chains': {'PREROUTING': [], 'POSTROUTING': [], 'OUTPUT': []}, 'masquerade': []}
    try:
        nat_output = router.cmd('iptables -t nat -L -n --line-numbers 2>/dev/null')
        current_chain = None
        for line in nat_output.strip().split('\n'):
            line = line.strip()
            if line.startswith('Chain'):
                current_chain = line.split()[1]
            elif line and not line.startswith('num') and current_chain in info['chains']:
                rule = _parse_nat_rule(line)
                info['chains'][current_chain].append(rule)
                if 'MASQUERADE' in line:
                    info['masquerade'].append(rule)
    except Exception as e:
        info['error'] = str(e)
    return info

def _read_routes(node):
    routes = []
    try:
        out = node.cmd('ip route show')
        for ln in out.strip().split('\n'):
            ln = ln.strip()
            if ln:
                routes.append(_parse_route_entry(ln))
    except:
        pass
    return routes

def _read_ifstats(node):
    stats = []
    try:
        for intf in [i for i in node.intfList() if i.name != 'lo']:
            stats.append({'interface': intf.name, 'stats': _get_interface_stats(node, intf.name)})
    except:
        pass
    return stats

def _read_ipv4_interfaces(node):
    res = []
    try:
        out = node.cmd('ip -o -4 addr show | awk \'{print $2,$4}\'')
        for ln in out.strip().split('\n'):
            if not ln.strip():
                continue
            ifname, cidr = ln.split()
            res.append({'name': ifname, 'ip': cidr})
    except:
        pass
    return res
