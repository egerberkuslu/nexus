"""
Enhanced Host Device Management API
Comprehensive host management with complete network information for Mininet framework
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import subprocess
import time
import os
import re
import json

from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
host_mgmt_bp = Blueprint('host_management', __name__)

# Service definitions
NETWORK_SERVICES = {
    'ssh': {
        'name': 'SSH Server',
        'default_port': 22,
        'process_names': ['sshd', 'ssh'],
        'config_files': ['/etc/ssh/sshd_config'],
        'start_commands': ['/usr/sbin/sshd -D'],
        'stop_commands': ['pkill sshd'],
        'test_commands': ['ssh -V']
    },
    'http': {
        'name': 'HTTP Server',
        'default_port': 80,
        'process_names': ['apache2', 'httpd', 'nginx', 'python3'],
        'config_files': ['/etc/apache2/apache2.conf', '/etc/nginx/nginx.conf'],
        'start_commands': ['python3 -m http.server 80', 'service apache2 start', 'service nginx start'],
        'stop_commands': ['pkill -f "python3 -m http.server"', 'service apache2 stop', 'service nginx stop'],
        'test_commands': ['curl -I http://localhost']
    },
    'https': {
        'name': 'HTTPS Server',
        'default_port': 443,
        'process_names': ['apache2', 'httpd', 'nginx'],
        'config_files': ['/etc/apache2/sites-available/default-ssl.conf'],
        'start_commands': ['service apache2 start', 'service nginx start'],
        'stop_commands': ['service apache2 stop', 'service nginx stop'],
        'test_commands': ['curl -I -k https://localhost']
    },
    'ftp': {
        'name': 'FTP Server',
        'default_port': 21,
        'process_names': ['vsftpd', 'proftpd', 'pure-ftpd', 'python3'],
        'config_files': ['/etc/vsftpd.conf', '/etc/proftpd/proftpd.conf'],
        'start_commands': ['python3 -m pyftpdlib -p 21', 'service vsftpd start'],
        'stop_commands': ['pkill -f pyftpdlib', 'service vsftpd stop'],
        'test_commands': ['ftp -V']
    },
    'telnet': {
        'name': 'Telnet Server',
        'default_port': 23,
        'process_names': ['telnetd', 'xinetd'],
        'config_files': ['/etc/xinetd.d/telnet'],
        'start_commands': ['service xinetd start'],
        'stop_commands': ['service xinetd stop'],
        'test_commands': ['telnet localhost 23']
    },
    'snmp': {
        'name': 'SNMP Agent',
        'default_port': 161,
        'process_names': ['snmpd'],
        'config_files': ['/etc/snmp/snmpd.conf'],
        'start_commands': ['service snmpd start'],
        'stop_commands': ['service snmpd stop'],
        'test_commands': ['snmpwalk -v2c -c public localhost']
    },
    'ntp': {
        'name': 'NTP Server',
        'default_port': 123,
        'process_names': ['ntpd', 'chronyd'],
        'config_files': ['/etc/ntp.conf', '/etc/chrony/chrony.conf'],
        'start_commands': ['service ntp start', 'service chrony start'],
        'stop_commands': ['service ntp stop', 'service chrony stop'],
        'test_commands': ['ntpq -p']
    },
    'dhcp': {
        'name': 'DHCP Server',
        'default_port': 67,
        'process_names': ['dhcpd', 'isc-dhcp-server'],
        'config_files': ['/etc/dhcp/dhcpd.conf'],
        'start_commands': ['service isc-dhcp-server start'],
        'stop_commands': ['service isc-dhcp-server stop'],
        'test_commands': ['dhcpd --version']
    },
    'dns': {
        'name': 'DNS Server',
        'default_port': 53,
        'process_names': ['named', 'bind9', 'dnsmasq'],
        'config_files': ['/etc/bind/named.conf', '/etc/dnsmasq.conf'],
        'start_commands': ['service bind9 start', 'service dnsmasq start'],
        'stop_commands': ['service bind9 stop', 'service dnsmasq stop'],
        'test_commands': ['nslookup localhost']
    }
}

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    from flask import current_app
    return current_app.config['MININET_MANAGER']

def _ensure_host_dirs(host):
    """Create host-specific directories for configuration and logs"""
    base_dir = f"/tmp/host_mgmt/{host.name}"
    dirs = {
        'base': base_dir,
        'config': f"{base_dir}/config",
        'logs': f"{base_dir}/logs",
        'services': f"{base_dir}/services",
        'dhcp': f"{base_dir}/dhcp"
    }
    
    for dir_path in dirs.values():
        host.cmd(f"mkdir -p {dir_path}")
        host.cmd(f"chmod 755 {dir_path}")
    
    return dirs

def _get_host_interfaces(host):
    """Get detailed interface information with enhanced error handling"""
    interfaces = []
    
    try:
        # Method 1: Use ip command to get interface list
        intf_output = host.cmd("ip -o link show 2>/dev/null")
        logger.debug(f"Interface list output for {host.name}: {intf_output}")
        
        if not intf_output.strip():
            # Fallback method: use ifconfig
            intf_output = host.cmd("ifconfig -a 2>/dev/null | grep '^[a-zA-Z]' | awk '{print $1}' | sed 's/:$//'")
            logger.debug(f"Fallback interface list for {host.name}: {intf_output}")
            
            # Process ifconfig output
            interface_names = [name.strip() for name in intf_output.strip().split('\n') if name.strip() and name.strip() != 'lo']
        else:
            # Process ip command output
            interface_names = []
            for line in intf_output.strip().split('\n'):
                if not line.strip() or 'lo:' in line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    intf_name = parts[1].rstrip(':')
                    if intf_name != 'lo':
                        interface_names.append(intf_name)
        
        logger.debug(f"Found interfaces for {host.name}: {interface_names}")
        
        # Get detailed information for each interface
        for intf_name in interface_names:
            interface_info = {
                'name': intf_name,
                'ip_addresses': [],
                'mac_address': 'unknown',
                'mtu': 1500,
                'state': 'unknown',
                'statistics': {},
                'primary_ip': None,
                'netmask': None,
                'broadcast': None,
                'prefix_length': None
            }
            
            try:
                # Get IP addresses using multiple methods
                ip_methods = [
                    f"ip -4 addr show {intf_name} 2>/dev/null | grep 'inet ' | awk '{{print $2}}'",
                    f"ifconfig {intf_name} 2>/dev/null | grep 'inet ' | awk '{{print $2}}'"
                ]
                
                ip_found = False
                for method in ip_methods:
                    ip_output = host.cmd(method)
                    if ip_output.strip():
                        for ip_line in ip_output.strip().split('\n'):
                            if ip_line.strip() and '/' in ip_line.strip():
                                full_ip = ip_line.strip()
                                interface_info['ip_addresses'].append(full_ip)
                                if not interface_info['primary_ip']:
                                    # Parse primary IP details
                                    if '/' in full_ip:
                                        ip_part, prefix = full_ip.split('/', 1)
                                        interface_info['primary_ip'] = ip_part
                                        interface_info['prefix_length'] = prefix
                                        # Calculate netmask from prefix
                                        try:
                                            prefix_int = int(prefix)
                                            netmask = _prefix_to_netmask(prefix_int)
                                            interface_info['netmask'] = netmask
                                        except:
                                            pass
                                ip_found = True
                        break
                
                # Get MAC address using multiple methods
                mac_methods = [
                    f"ip link show {intf_name} 2>/dev/null | grep 'link/ether' | awk '{{print $2}}'",
                    f"cat /sys/class/net/{intf_name}/address 2>/dev/null",
                    f"ifconfig {intf_name} 2>/dev/null | grep 'ether' | awk '{{print $2}}'"
                ]
                
                for method in mac_methods:
                    mac_output = host.cmd(method)
                    if mac_output.strip() and ':' in mac_output.strip():
                        interface_info['mac_address'] = mac_output.strip()
                        break
                
                # Get MTU
                mtu_methods = [
                    f"ip link show {intf_name} 2>/dev/null | grep 'mtu' | sed 's/.*mtu \\([0-9]*\\).*/\\1/'",
                    f"cat /sys/class/net/{intf_name}/mtu 2>/dev/null"
                ]
                
                for method in mtu_methods:
                    mtu_output = host.cmd(method)
                    if mtu_output.strip().isdigit():
                        interface_info['mtu'] = int(mtu_output.strip())
                        break
                
                # Get interface state
                state_methods = [
                    f"ip link show {intf_name} 2>/dev/null | grep 'state' | sed 's/.*state \\([A-Z]*\\).*/\\1/'",
                    f"cat /sys/class/net/{intf_name}/operstate 2>/dev/null"
                ]
                
                for method in state_methods:
                    state_output = host.cmd(method)
                    if state_output.strip():
                        interface_info['state'] = state_output.strip()
                        break
                
                # Get interface statistics
                try:
                    stats_output = host.cmd(f"cat /proc/net/dev 2>/dev/null | grep {intf_name}")
                    if stats_output.strip():
                        stat_parts = stats_output.strip().split()
                        if len(stat_parts) >= 17:
                            interface_info['statistics'] = {
                                'rx_bytes': int(stat_parts[1]),
                                'rx_packets': int(stat_parts[2]),
                                'rx_errors': int(stat_parts[3]),
                                'rx_dropped': int(stat_parts[4]),
                                'tx_bytes': int(stat_parts[9]),
                                'tx_packets': int(stat_parts[10]),
                                'tx_errors': int(stat_parts[11]),
                                'tx_dropped': int(stat_parts[12])
                            }
                except Exception as e:
                    logger.debug(f"Could not get statistics for {intf_name}: {e}")
                
                # Get broadcast address if available
                try:
                    bcast_output = host.cmd(f"ifconfig {intf_name} 2>/dev/null | grep 'broadcast' | awk '{{print $NF}}'")
                    if bcast_output.strip():
                        interface_info['broadcast'] = bcast_output.strip()
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Error getting details for interface {intf_name}: {e}")
                interface_info['error'] = str(e)
            
            interfaces.append(interface_info)
            
    except Exception as e:
        logger.error(f"Error getting interfaces for {host.name}: {e}")
        # Return at least basic interface info from Mininet
        try:
            for intf in host.intfList():
                if intf.name != 'lo':
                    interface_info = {
                        'name': intf.name,
                        'ip_addresses': [f"{intf.IP()}/24"] if hasattr(intf, 'IP') and intf.IP() else [],
                        'mac_address': intf.MAC() if hasattr(intf, 'MAC') else 'unknown',
                        'mtu': getattr(intf, 'mtu', 1500),
                        'state': 'up' if intf.isUp() else 'down',
                        'primary_ip': intf.IP() if hasattr(intf, 'IP') and intf.IP() else None,
                        'statistics': {}
                    }
                    interfaces.append(interface_info)
        except Exception as inner_e:
            logger.error(f"Fallback interface detection failed: {inner_e}")
    
    return interfaces

def _prefix_to_netmask(prefix_length):
    """Convert prefix length to netmask"""
    try:
        mask = (0xffffffff >> (32 - prefix_length)) << (32 - prefix_length)
        return f"{(mask >> 24) & 0xff}.{(mask >> 16) & 0xff}.{(mask >> 8) & 0xff}.{mask & 0xff}"
    except:
        return "255.255.255.0"

def _get_default_gateway(host):
    """Get the default gateway for the host"""
    try:
        # Method 1: Using ip route
        gateway_output = host.cmd("ip route show default 2>/dev/null | awk '/default/ {print $3}' | head -1")
        if gateway_output.strip():
            return gateway_output.strip()
        
        # Method 2: Using route command
        gateway_output = host.cmd("route -n 2>/dev/null | grep '^0.0.0.0' | awk '{print $2}' | head -1")
        if gateway_output.strip():
            return gateway_output.strip()
        
        # Method 3: Parse full routing table
        route_output = host.cmd("ip route show 2>/dev/null")
        for line in route_output.split('\n'):
            if 'default' in line and 'via' in line:
                parts = line.split()
                try:
                    via_index = parts.index('via')
                    if via_index + 1 < len(parts):
                        return parts[via_index + 1]
                except:
                    continue
        
        return None
    except Exception as e:
        logger.error(f"Error getting default gateway for {host.name}: {e}")
        return None

def _get_dns_config(host):
    """Get DNS configuration with enhanced reliability"""
    dns_config = {
        'nameservers': [],
        'search_domains': [],
        'resolv_conf': '',
        'dns_service_running': False
    }
    
    try:
        # Read /etc/resolv.conf
        resolv_output = host.cmd("cat /etc/resolv.conf 2>/dev/null")
        if resolv_output.strip():
            dns_config['resolv_conf'] = resolv_output.strip()
            
            for line in resolv_output.strip().split('\n'):
                line = line.strip()
                if line.startswith('nameserver'):
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_config['nameservers'].append(parts[1])
                elif line.startswith('search'):
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_config['search_domains'].extend(parts[1:])
                elif line.startswith('domain'):
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_config['search_domains'].append(parts[1])
        
        # If resolv.conf is empty or doesn't exist, try alternative methods
        if not dns_config['nameservers']:
            # Check for systemd-resolved
            systemd_dns = host.cmd("systemd-resolve --status 2>/dev/null | grep 'DNS Servers' | awk '{print $3}'")
            if systemd_dns.strip():
                dns_config['nameservers'].append(systemd_dns.strip())
        
        # Check if DNS service is running
        dns_processes = host.cmd("pgrep -f 'named|bind9|dnsmasq|systemd-resolved' 2>/dev/null")
        dns_config['dns_service_running'] = bool(dns_processes.strip())
        
    except Exception as e:
        logger.error(f"Error getting DNS config for {host.name}: {e}")
        dns_config['error'] = str(e)
    
    return dns_config

def _get_routing_table(host):
    """Get routing table information with enhanced parsing"""
    routes = []
    gateway_info = {
        'default_gateway': None,
        'gateway_interface': None
    }
    
    try:
        # Get routing table
        route_methods = [
            "ip route show 2>/dev/null",
            "route -n 2>/dev/null",
            "netstat -rn 2>/dev/null"
        ]
        
        route_output = None
        for method in route_methods:
            output = host.cmd(method)
            if output.strip():
                route_output = output
                break
        
        if not route_output:
            return routes
        
        # Parse routes
        for line in route_output.strip().split('\n'):
            if not line.strip():
                continue
            
            # Skip header lines
            if any(header in line.lower() for header in ['destination', 'kernel', 'flags', 'iface']):
                continue
            
            route_info = _parse_route_line(line.strip())
            if route_info:
                routes.append(route_info)
                
                # Track default gateway
                if route_info.get('destination') in ['default', '0.0.0.0', '0.0.0.0/0']:
                    gateway_info['default_gateway'] = route_info.get('gateway')
                    gateway_info['gateway_interface'] = route_info.get('interface')
        
        # If we didn't find default gateway in routes, try direct method
        if not gateway_info['default_gateway']:
            gateway_info['default_gateway'] = _get_default_gateway(host)
        
        # Add gateway info to the first route or as a separate entry
        if gateway_info['default_gateway'] and not any(r.get('destination') in ['default', '0.0.0.0/0'] for r in routes):
            routes.insert(0, {
                'destination': 'default',
                'gateway': gateway_info['default_gateway'],
                'interface': gateway_info['gateway_interface'],
                'metric': 0,
                'flags': 'UG',
                'type': 'default'
            })
                
    except Exception as e:
        logger.error(f"Error getting routing table for {host.name}: {e}")
    
    return routes

def _parse_route_line(route_line):
    """Parse a single route line with enhanced parsing"""
    try:
        parts = route_line.split()
        if not parts:
            return None
        
        route = {
            'destination': parts[0] if parts[0] != 'default' else '0.0.0.0/0',
            'gateway': None,
            'interface': None,
            'metric': None,
            'flags': None,
            'scope': None,
            'protocol': None,
            'type': 'static',
            'raw': route_line
        }
        
        # Determine if this is default route
        if parts[0] in ['default', '0.0.0.0', '0.0.0.0/0']:
            route['type'] = 'default'
        
        # Parse different route formats
        if 'via' in parts:
            # ip route format: dest via gateway dev interface
            i = 1
            while i < len(parts):
                if parts[i] == 'via' and i + 1 < len(parts):
                    route['gateway'] = parts[i + 1]
                    i += 2
                elif parts[i] == 'dev' and i + 1 < len(parts):
                    route['interface'] = parts[i + 1]
                    i += 2
                elif parts[i] == 'metric' and i + 1 < len(parts):
                    try:
                        route['metric'] = int(parts[i + 1])
                    except:
                        pass
                    i += 2
                elif parts[i] == 'scope' and i + 1 < len(parts):
                    route['scope'] = parts[i + 1]
                    i += 2
                elif parts[i] == 'proto' and i + 1 < len(parts):
                    route['protocol'] = parts[i + 1]
                    i += 2
                else:
                    i += 1
        elif len(parts) >= 8:
            # route -n format: Destination Gateway Genmask Flags Metric Ref Use Iface
            route['gateway'] = parts[1] if parts[1] != '0.0.0.0' else None
            route['netmask'] = parts[2] if len(parts) > 2 else None
            route['flags'] = parts[3] if len(parts) > 3 else None
            try:
                route['metric'] = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
            except:
                pass
            route['interface'] = parts[7] if len(parts) > 7 else None
        elif len(parts) >= 2:
            # Simple format: destination interface or destination gateway
            if '.' in parts[1]:  # Likely an IP address (gateway)
                route['gateway'] = parts[1]
            else:  # Likely an interface
                route['interface'] = parts[1]
        
        return route
        
    except Exception as e:
        logger.error(f"Error parsing route line '{route_line}': {e}")
        return {
            'destination': 'unknown',
            'raw': route_line,
            'error': str(e)
        }

def _get_firewall_status(host):
    """Get comprehensive firewall status"""
    firewall_status = {
        'iptables_available': False,
        'ufw_available': False,
        'active_rules': [],
        'policy': {},
        'rule_count': 0,
        'chains': []
    }
    
    try:
        # Check if iptables is available
        iptables_check = host.cmd("which iptables 2>/dev/null")
        firewall_status['iptables_available'] = bool(iptables_check.strip())
        
        if firewall_status['iptables_available']:
            # Get iptables rules
            rules_output = host.cmd("iptables -L -n --line-numbers 2>/dev/null")
            
            current_chain = None
            for line in rules_output.strip().split('\n'):
                line = line.strip()
                
                if line.startswith('Chain'):
                    # Extract chain name and policy
                    chain_match = re.match(r'Chain\s+(\w+)\s+\(policy\s+(\w+)', line)
                    if chain_match:
                        current_chain = chain_match.group(1)
                        policy = chain_match.group(2)
                        firewall_status['policy'][current_chain] = policy
                        firewall_status['chains'].append(current_chain)
                elif line and not line.startswith('num') and not line.startswith('target') and current_chain:
                    # This is a rule line
                    rule_parts = line.split()
                    if rule_parts:
                        rule_info = {
                            'chain': current_chain,
                            'line_number': rule_parts[0] if rule_parts[0].isdigit() else None,
                            'target': rule_parts[1] if len(rule_parts) > 1 else '',
                            'protocol': rule_parts[2] if len(rule_parts) > 2 else '',
                            'source': rule_parts[3] if len(rule_parts) > 3 else '',
                            'destination': rule_parts[4] if len(rule_parts) > 4 else '',
                            'raw': line
                        }
                        firewall_status['active_rules'].append(rule_info)
                        firewall_status['rule_count'] += 1
        
        # Check if UFW is available
        ufw_check = host.cmd("which ufw 2>/dev/null")
        firewall_status['ufw_available'] = ufw_check.strip()
        
        if firewall_status['ufw_available']:
            ufw_status = host.cmd("ufw status 2>/dev/null")
            firewall_status['ufw_status'] = ufw_status.strip()
        
    except Exception as e:
        logger.error(f"Error getting firewall status for {host.name}: {e}")
        firewall_status['error'] = str(e)
    
    return firewall_status

def _get_service_status(host, service_name):
    """Get detailed status of a specific service"""
    if service_name not in NETWORK_SERVICES:
        return {'error': f'Unknown service: {service_name}'}
    
    service_def = NETWORK_SERVICES[service_name]
    status = {
        'name': service_def['name'],
        'service_key': service_name,
        'running': False,
        'port_listening': False,
        'processes': [],
        'port': service_def['default_port'],
        'config_files': [],
        'start_methods': service_def['start_commands'],
        'stop_methods': service_def['stop_commands']
    }
    
    try:
        # Check for running processes
        for process_name in service_def['process_names']:
            process_output = host.cmd(f"pgrep -f {process_name}")
            if process_output.strip():
                pids = process_output.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        # Get process details
                        proc_info = host.cmd(f"ps -p {pid} -o pid,ppid,cmd --no-headers 2>/dev/null")
                        if proc_info.strip():
                            status['processes'].append({
                                'pid': pid.strip(),
                                'details': proc_info.strip()
                            })
                            status['running'] = True
        
        # Check if port is listening
        port_check = host.cmd(f"netstat -tuln 2>/dev/null | grep ':{service_def['default_port']} '")
        if not port_check.strip():
            # Try with ss if netstat is not available
            port_check = host.cmd(f"ss -tuln 2>/dev/null | grep ':{service_def['default_port']} '")
        
        status['port_listening'] = bool(port_check.strip())
        
        # Check configuration files
        for config_file in service_def['config_files']:
            file_check = host.cmd(f"test -f {config_file} && echo EXISTS")
            if file_check.strip() == 'EXISTS':
                file_size = host.cmd(f"wc -l < {config_file} 2>/dev/null")
                status['config_files'].append({
                    'path': config_file,
                    'exists': True,
                    'lines': int(file_size.strip()) if file_size.strip().isdigit() else 0
                })
            else:
                status['config_files'].append({
                    'path': config_file,
                    'exists': False
                })
        
    except Exception as e:
        logger.error(f"Error getting service status for {service_name}: {e}")
        status['error'] = str(e)
    
    return status

def _get_dhcp_status(host):
    """Get DHCP client and server status"""
    dhcp_status = {
        'client': {
            'active_leases': [],
            'dhcp_enabled_interfaces': [],
            'current_servers': []
        },
        'server': {
            'running': False,
            'config_file': None,
            'leases_file': None,
            'active_leases': [],
            'configured_pools': []
        }
    }
    
    try:
        # Check DHCP client status
        interfaces = _get_host_interfaces(host)
        for intf in interfaces:
            # Check if interface is configured via DHCP
            dhcp_check = host.cmd(f"grep -r {intf['name']} /var/lib/dhcp/ 2>/dev/null")
            if dhcp_check.strip():
                dhcp_status['client']['dhcp_enabled_interfaces'].append(intf['name'])
        
        # Check for active DHCP leases
        lease_files = ['/var/lib/dhcp/dhclient.leases', '/var/lib/dhclient/dhclient.leases']
        for lease_file in lease_files:
            lease_content = host.cmd(f"cat {lease_file} 2>/dev/null")
            if lease_content.strip():
                # Parse lease information (simplified)
                for line in lease_content.split('\n'):
                    if 'fixed-address' in line:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip_match:
                            dhcp_status['client']['active_leases'].append(ip_match.group(1))
        
        # Check DHCP server status
        dhcp_service_status = _get_service_status(host, 'dhcp')
        dhcp_status['server']['running'] = dhcp_service_status['running']
        
        # Check DHCP server configuration
        dhcp_conf_files = ['/etc/dhcp/dhcpd.conf', '/etc/dhcpd.conf']
        for conf_file in dhcp_conf_files:
            conf_check = host.cmd(f"test -f {conf_file} && echo EXISTS")
            if conf_check.strip() == 'EXISTS':
                dhcp_status['server']['config_file'] = conf_file
                
                # Parse configuration for pools (simplified)
                conf_content = host.cmd(f"cat {conf_file}")
                for line in conf_content.split('\n'):
                    if 'subnet' in line and 'netmask' in line:
                        dhcp_status['server']['configured_pools'].append(line.strip())
                break
        
        # Check DHCP server leases
        lease_files = ['/var/lib/dhcp/dhcpd.leases', '/var/lib/dhcpd/dhcpd.leases']
        for lease_file in lease_files:
            lease_check = host.cmd(f"test -f {lease_file} && echo EXISTS")
            if lease_check.strip() == 'EXISTS':
                dhcp_status['server']['leases_file'] = lease_file
                
                lease_content = host.cmd(f"cat {lease_file}")
                # Parse active leases (simplified)
                current_leases = re.findall(r'lease\s+(\d+\.\d+\.\d+\.\d+)', lease_content)
                dhcp_status['server']['active_leases'] = list(set(current_leases))
                break
                
    except Exception as e:
        logger.error(f"Error getting DHCP status for {host.name}: {e}")
        dhcp_status['error'] = str(e)
    
    return dhcp_status

def _get_system_metrics(host):
    """Get system performance metrics with better error handling"""
    metrics = {
        'cpu': {'usage_percent': 0.0, 'load_average': []},
        'memory': {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'usage_percent': 0.0},
        'disk': {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'usage_percent': 0.0},
        'network': {'total_rx_bytes': 0, 'total_tx_bytes': 0},
        'uptime': '0 days, 0:00:00',
        'processes': 0
    }
    
    try:
        # CPU usage - try multiple methods
        cpu_methods = [
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | sed 's/%us,//'",
            "sar -u 1 1 2>/dev/null | tail -1 | awk '{print $3}'",
            "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'"
        ]
        
        for method in cpu_methods:
            cpu_output = host.cmd(method)
            if cpu_output.strip():
                try:
                    # Clean up the output
                    cpu_str = cpu_output.strip().replace('us,', '').replace('%', '')
                    if cpu_str and not cpu_str.isalpha():
                        metrics['cpu']['usage_percent'] = float(cpu_str)
                        break
                except ValueError:
                    continue
        
        # Load average
        load_output = host.cmd("uptime | awk -F'load average:' '{print $2}' 2>/dev/null")
        if load_output.strip():
            try:
                load_parts = load_output.strip().split(',')
                metrics['cpu']['load_average'] = [float(x.strip()) for x in load_parts[:3] if x.strip() and x.strip().replace('.', '').isdigit()]
            except:
                pass
        
        # Memory usage
        mem_output = host.cmd("free -m 2>/dev/null | grep '^Mem:'")
        if mem_output.strip():
            try:
                mem_parts = mem_output.strip().split()
                if len(mem_parts) >= 3:
                    total = int(mem_parts[1])
                    used = int(mem_parts[2])
                    free = total - used
                    metrics['memory'] = {
                        'total_mb': total,
                        'used_mb': used,
                        'free_mb': free,
                        'usage_percent': round((used / total) * 100, 2) if total > 0 else 0
                    }
            except (ValueError, IndexError):
                pass
        
        # Disk usage
        disk_output = host.cmd("df -BG / 2>/dev/null | tail -1")
        if disk_output.strip():
            try:
                disk_parts = disk_output.strip().split()
                if len(disk_parts) >= 4:
                    total = int(disk_parts[1].replace('G', ''))
                    used = int(disk_parts[2].replace('G', ''))
                    free = int(disk_parts[3].replace('G', ''))
                    metrics['disk'] = {
                        'total_gb': total,
                        'used_gb': used,
                        'free_gb': free,
                        'usage_percent': round((used / total) * 100, 2) if total > 0 else 0
                    }
            except (ValueError, IndexError):
                pass
        
        # Network statistics
        try:
            interfaces = _get_host_interfaces(host)
            total_rx = sum(intf.get('statistics', {}).get('rx_bytes', 0) for intf in interfaces)
            total_tx = sum(intf.get('statistics', {}).get('tx_bytes', 0) for intf in interfaces)
            metrics['network'] = {
                'total_rx_bytes': total_rx,
                'total_tx_bytes': total_tx
            }
        except:
            pass
        
        # Uptime
        uptime_methods = [
            "uptime -p 2>/dev/null",
            "uptime | cut -d',' -f1 | cut -d' ' -f3-"
        ]
        
        for method in uptime_methods:
            uptime_output = host.cmd(method)
            if uptime_output.strip():
                metrics['uptime'] = uptime_output.strip()
                break
        
        # Process count
        proc_output = host.cmd("ps aux 2>/dev/null | wc -l")
        if proc_output.strip().isdigit():
            metrics['processes'] = max(0, int(proc_output.strip()) - 1)  # Subtract header line
        
    except Exception as e:
        logger.error(f"Error getting system metrics for {host.name}: {e}")
        metrics['error'] = str(e)
    
    return metrics

# API Endpoints

@host_mgmt_bp.route('/devices/<device_id>/host/status', methods=['GET'])
@log_api_request
def get_host_status(device_id):
    """Get comprehensive host status with complete network information"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        # Get hostname with fallback
        hostname = host.cmd('hostname 2>/dev/null').strip()
        if not hostname:
            hostname = device_id  # Fallback to device_id

        # Get comprehensive network information
        interfaces = _get_host_interfaces(host)
        routing_table = _get_routing_table(host)
        default_gateway = _get_default_gateway(host)
        
        # Extract primary network information
        primary_ip = None
        primary_mac = None
        primary_interface = None
        
        for intf in interfaces:
            if intf.get('primary_ip') and intf.get('name') != 'lo':
                primary_ip = intf['primary_ip']
                primary_mac = intf.get('mac_address')
                primary_interface = intf.get('name')
                break
        
        # Build comprehensive status
        status = {
            'device_id': device_id,
            'hostname': hostname,
            'primary_ip': primary_ip,
            'primary_mac': primary_mac,
            'primary_interface': primary_interface,
            'default_gateway': default_gateway,
            'interfaces': interfaces,
            'dns_config': _get_dns_config(host),
            'routing_table': routing_table,
            'firewall_status': _get_firewall_status(host),
            'dhcp_status': _get_dhcp_status(host),
            'system_metrics': _get_system_metrics(host),
            'network_services': {},
            'timestamp': datetime.now().isoformat()
        }

        # Get status of all network services
        for service_name in NETWORK_SERVICES.keys():
            status['network_services'][service_name] = _get_service_status(host, service_name)

        return jsonify({'success': True, 'data': status})

    except Exception as e:
        logger.error(f"Error getting host status for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/interfaces', methods=['GET', 'POST'])
@log_api_request
def manage_host_interfaces(device_id):
    """Manage host network interfaces"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            interfaces = _get_host_interfaces(host)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'interfaces': interfaces,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Configure interface
            config = request.get_json() or {}
            interface_name = config.get('interface')
            action = config.get('action', 'configure')

            if not interface_name:
                return jsonify({'error': 'Interface name required'}), 400

            results = []

            if action == 'configure':
                # Configure IP address
                if 'ip_address' in config:
                    ip_addr = config['ip_address']
                    try:
                        result = host.cmd(f'ip addr add {ip_addr} dev {interface_name}')
                        results.append({
                            'action': 'set_ip',
                            'interface': interface_name,
                            'ip_address': ip_addr,
                            'success': True,
                            'output': result.strip()
                        })
                    except Exception as e:
                        results.append({
                            'action': 'set_ip',
                            'interface': interface_name,
                            'success': False,
                            'error': str(e)
                        })

                # Set interface state
                if 'state' in config:
                    state = config['state']  # 'up' or 'down'
                    try:
                        result = host.cmd(f'ip link set dev {interface_name} {state}')
                        results.append({
                            'action': 'set_state',
                            'interface': interface_name,
                            'state': state,
                            'success': True,
                            'output': result.strip()
                        })
                    except Exception as e:
                        results.append({
                            'action': 'set_state',
                            'interface': interface_name,
                            'success': False,
                            'error': str(e)
                        })

                # Set MTU
                if 'mtu' in config:
                    mtu = config['mtu']
                    try:
                        result = host.cmd(f'ip link set dev {interface_name} mtu {mtu}')
                        results.append({
                            'action': 'set_mtu',
                            'interface': interface_name,
                            'mtu': mtu,
                            'success': True,
                            'output': result.strip()
                        })
                    except Exception as e:
                        results.append({
                            'action': 'set_mtu',
                            'interface': interface_name,
                            'success': False,
                            'error': str(e)
                        })

            elif action == 'flush':
                # Flush IP addresses
                try:
                    result = host.cmd(f'ip addr flush dev {interface_name}')
                    results.append({
                        'action': 'flush_ip',
                        'interface': interface_name,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'flush_ip',
                        'interface': interface_name,
                        'success': False,
                        'error': str(e)
                    })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'interface_configuration_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing interfaces for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/dns', methods=['GET', 'POST'])
@log_api_request
def manage_host_dns(device_id):
    """Manage host DNS configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            dns_config = _get_dns_config(host)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'dns_config': dns_config,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Configure DNS
            config = request.get_json() or {}
            results = []

            # Configure nameservers
            if 'nameservers' in config:
                nameservers = config['nameservers']
                if isinstance(nameservers, list):
                    try:
                        # Backup existing resolv.conf
                        host.cmd('cp /etc/resolv.conf /etc/resolv.conf.backup 2>/dev/null || true')
                        
                        # Write new resolv.conf
                        resolv_content = []
                        for ns in nameservers:
                            resolv_content.append(f'nameserver {ns}')
                        
                        if 'search_domains' in config:
                            search_domains = config['search_domains']
                            if isinstance(search_domains, list) and search_domains:
                                resolv_content.append(f"search {' '.join(search_domains)}")
                        
                        resolv_text = '\n'.join(resolv_content)
                        host.cmd(f'echo "{resolv_text}" > /etc/resolv.conf')
                        
                        results.append({
                            'action': 'configure_dns',
                            'nameservers': nameservers,
                            'success': True,
                            'message': 'DNS configuration updated'
                        })
                    except Exception as e:
                        results.append({
                            'action': 'configure_dns',
                            'success': False,
                            'error': str(e)
                        })

            # Test DNS resolution
            if 'test_resolution' in config:
                test_host = config['test_resolution']
                try:
                    result = host.cmd(f'nslookup {test_host}')
                    success = 'NXDOMAIN' not in result and 'connection timed out' not in result
                    results.append({
                        'action': 'test_dns',
                        'test_host': test_host,
                        'success': success,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'test_dns',
                        'test_host': test_host,
                        'success': False,
                        'error': str(e)
                    })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'dns_configuration_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing DNS for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/services/<service_name>', methods=['GET', 'POST'])
@log_api_request
def manage_host_service(device_id, service_name):
    """Manage a specific network service"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if service_name not in NETWORK_SERVICES:
            return jsonify({'error': f'Unknown service: {service_name}'}), 400

        if request.method == 'GET':
            service_status = _get_service_status(host, service_name)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'service': service_status,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Control service
            action = request.json.get('action') if request.json else None
            port = request.json.get('port') if request.json else None

            if not action:
                return jsonify({'error': 'Action required (start/stop/restart)'}), 400

            service_def = NETWORK_SERVICES[service_name]
            results = []

            if action == 'start':
                # Use custom port if provided
                actual_port = port or service_def['default_port']
                
                # Try different start methods
                started = False
                for start_cmd in service_def['start_commands']:
                    try:
                        # Replace port in command if it contains port placeholder
                        if service_name in ['http', 'ftp'] and 'python3' in start_cmd:
                            cmd = start_cmd.replace(str(service_def['default_port']), str(actual_port))
                        else:
                            cmd = start_cmd
                        
                        result = host.cmd(f'{cmd} &')
                        time.sleep(2)
                        
                        # Check if service started
                        service_status = _get_service_status(host, service_name)
                        if service_status['running'] or service_status['port_listening']:
                            started = True
                            results.append({
                                'action': 'start',
                                'service': service_name,
                                'port': actual_port,
                                'success': True,
                                'command': cmd,
                                'output': result.strip()
                            })
                            break
                    except Exception as e:
                        results.append({
                            'action': 'start',
                            'service': service_name,
                            'command': start_cmd,
                            'success': False,
                            'error': str(e)
                        })

                if not started:
                    results.append({
                        'action': 'start',
                        'service': service_name,
                        'success': False,
                        'message': 'All start methods failed'
                    })

            elif action == 'stop':
                # Try different stop methods
                stopped = False
                for stop_cmd in service_def['stop_commands']:
                    try:
                        result = host.cmd(stop_cmd)
                        time.sleep(1)
                        
                        # Check if service stopped
                        service_status = _get_service_status(host, service_name)
                        if not service_status['running']:
                            stopped = True
                            results.append({
                                'action': 'stop',
                                'service': service_name,
                                'success': True,
                                'command': stop_cmd,
                                'output': result.strip()
                            })
                            break
                    except Exception as e:
                        results.append({
                            'action': 'stop',
                            'service': service_name,
                            'command': stop_cmd,
                            'success': False,
                            'error': str(e)
                        })

                if not stopped:
                    # Force kill if regular stop failed
                    try:
                        for process_name in service_def['process_names']:
                            host.cmd(f'pkill -9 -f {process_name}')
                        results.append({
                            'action': 'force_stop',
                            'service': service_name,
                            'success': True,
                            'message': 'Service force stopped'
                        })
                    except Exception as e:
                        results.append({
                            'action': 'force_stop',
                            'service': service_name,
                            'success': False,
                            'error': str(e)
                        })

            elif action == 'restart':
                # Stop then start
                for stop_cmd in service_def['stop_commands']:
                    try:
                        host.cmd(stop_cmd)
                    except:
                        pass
                
                time.sleep(2)
                
                # Start service
                actual_port = port or service_def['default_port']
                for start_cmd in service_def['start_commands']:
                    try:
                        if service_name in ['http', 'ftp'] and 'python3' in start_cmd:
                            cmd = start_cmd.replace(str(service_def['default_port']), str(actual_port))
                        else:
                            cmd = start_cmd
                        
                        result = host.cmd(f'{cmd} &')
                        time.sleep(2)
                        
                        service_status = _get_service_status(host, service_name)
                        if service_status['running']:
                            results.append({
                                'action': 'restart',
                                'service': service_name,
                                'port': actual_port,
                                'success': True,
                                'command': cmd
                            })
                            break
                    except Exception as e:
                        results.append({
                            'action': 'restart',
                            'service': service_name,
                            'success': False,
                            'error': str(e)
                        })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'service_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing service {service_name} for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/routes', methods=['GET', 'POST', 'DELETE'])
@log_api_request
def manage_host_routes(device_id):
    """Manage host static routes"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            routes = _get_routing_table(host)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'routes': routes,
                'timestamp': datetime.now().isoformat()
            })

        elif request.method == 'POST':
            # Add route
            route_config = request.get_json() or {}
            destination = route_config.get('destination')
            gateway = route_config.get('gateway')
            interface = route_config.get('interface')
            metric = route_config.get('metric')

            if not destination:
                return jsonify({'error': 'Destination required'}), 400

            try:
                cmd_parts = ['ip', 'route', 'add', destination]
                
                if gateway:
                    cmd_parts.extend(['via', gateway])
                if interface:
                    cmd_parts.extend(['dev', interface])
                if metric:
                    cmd_parts.extend(['metric', str(metric)])

                cmd = ' '.join(cmd_parts)
                result = host.cmd(cmd)

                return jsonify({
                    'success': True,
                    'device_id': device_id,
                    'action': 'add_route',
                    'command': cmd,
                    'output': result.strip(),
                    'timestamp': datetime.now().isoformat()
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        elif request.method == 'DELETE':
            # Delete route
            destination = request.args.get('destination')
            gateway = request.args.get('gateway')

            if not destination:
                return jsonify({'error': 'Destination required'}), 400

            try:
                cmd_parts = ['ip', 'route', 'del', destination]
                if gateway:
                    cmd_parts.extend(['via', gateway])

                cmd = ' '.join(cmd_parts)
                result = host.cmd(cmd)

                return jsonify({
                    'success': True,
                    'device_id': device_id,
                    'action': 'delete_route',
                    'command': cmd,
                    'output': result.strip(),
                    'timestamp': datetime.now().isoformat()
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

    except Exception as e:
        logger.error(f"Error managing routes for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/firewall', methods=['GET', 'POST'])
@log_api_request
def manage_host_firewall(device_id):
    """Manage host firewall rules"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            firewall_status = _get_firewall_status(host)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'firewall': firewall_status,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Add firewall rule
            rule_config = request.get_json() or {}
            action = rule_config.get('action', 'add')  # add, delete, flush
            
            results = []

            if action == 'add':
                chain = rule_config.get('chain', 'INPUT')
                target = rule_config.get('target', 'ACCEPT')
                protocol = rule_config.get('protocol')
                source = rule_config.get('source')
                destination = rule_config.get('destination')
                port = rule_config.get('port')

                try:
                    cmd_parts = ['iptables', '-A', chain]
                    
                    if protocol:
                        cmd_parts.extend(['-p', protocol])
                    if source:
                        cmd_parts.extend(['-s', source])
                    if destination:
                        cmd_parts.extend(['-d', destination])
                    if port:
                        cmd_parts.extend(['--dport', str(port)])
                    
                    cmd_parts.extend(['-j', target])
                    
                    cmd = ' '.join(cmd_parts)
                    result = host.cmd(cmd)
                    
                    results.append({
                        'action': 'add_rule',
                        'command': cmd,
                        'success': True,
                        'output': result.strip()
                    })

                except Exception as e:
                    results.append({
                        'action': 'add_rule',
                        'success': False,
                        'error': str(e)
                    })

            elif action == 'delete':
                rule_number = rule_config.get('rule_number')
                chain = rule_config.get('chain', 'INPUT')

                if rule_number:
                    try:
                        cmd = f'iptables -D {chain} {rule_number}'
                        result = host.cmd(cmd)
                        results.append({
                            'action': 'delete_rule',
                            'command': cmd,
                            'success': True,
                            'output': result.strip()
                        })
                    except Exception as e:
                        results.append({
                            'action': 'delete_rule',
                            'success': False,
                            'error': str(e)
                        })
                else:
                    results.append({
                        'action': 'delete_rule',
                        'success': False,
                        'error': 'Rule number required'
                    })

            elif action == 'flush':
                chain = rule_config.get('chain', 'INPUT')
                try:
                    cmd = f'iptables -F {chain}'
                    result = host.cmd(cmd)
                    results.append({
                        'action': 'flush_chain',
                        'chain': chain,
                        'command': cmd,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'flush_chain',
                        'success': False,
                        'error': str(e)
                    })

            elif action == 'set_policy':
                chain = rule_config.get('chain', 'INPUT')
                policy = rule_config.get('policy', 'ACCEPT')
                try:
                    cmd = f'iptables -P {chain} {policy}'
                    result = host.cmd(cmd)
                    results.append({
                        'action': 'set_policy',
                        'chain': chain,
                        'policy': policy,
                        'command': cmd,
                        'success': True,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_policy',
                        'success': False,
                        'error': str(e)
                    })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'firewall_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing firewall for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/dhcp', methods=['GET', 'POST'])
@log_api_request
def manage_host_dhcp(device_id):
    """Manage DHCP client and server configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            dhcp_status = _get_dhcp_status(host)
            return jsonify({
                'success': True,
                'device_id': device_id,
                'dhcp_status': dhcp_status,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Configure DHCP
            config = request.get_json() or {}
            action = config.get('action')  # 'enable_client', 'disable_client', 'configure_server'
            results = []

            if action == 'enable_client':
                interface = config.get('interface')
                if not interface:
                    return jsonify({'error': 'Interface required for DHCP client'}), 400

                try:
                    # Request DHCP lease
                    result = host.cmd(f'dhclient {interface}')
                    time.sleep(3)
                    
                    # Check if IP was assigned
                    ip_check = host.cmd(f'ip addr show {interface} | grep "inet "')
                    success = bool(ip_check.strip())
                    
                    results.append({
                        'action': 'enable_dhcp_client',
                        'interface': interface,
                        'success': success,
                        'output': result.strip(),
                        'ip_assigned': ip_check.strip() if success else None
                    })

                except Exception as e:
                    results.append({
                        'action': 'enable_dhcp_client',
                        'interface': interface,
                        'success': False,
                        'error': str(e)
                    })

            elif action == 'disable_client':
                interface = config.get('interface')
                if not interface:
                    return jsonify({'error': 'Interface required'}), 400

                try:
                    # Release DHCP lease
                    result = host.cmd(f'dhclient -r {interface}')
                    results.append({
                        'action': 'disable_dhcp_client',
                        'interface': interface,
                        'success': True,
                        'output': result.strip()
                    })

                except Exception as e:
                    results.append({
                        'action': 'disable_dhcp_client',
                        'interface': interface,
                        'success': False,
                        'error': str(e)
                    })

            elif action == 'configure_server':
                # Configure DHCP server
                subnet = config.get('subnet')  # e.g., "192.168.1.0"
                netmask = config.get('netmask', '255.255.255.0')
                range_start = config.get('range_start')  # e.g., "192.168.1.100"
                range_end = config.get('range_end')  # e.g., "192.168.1.200"
                gateway = config.get('gateway')
                dns_servers = config.get('dns_servers', [])

                if not all([subnet, range_start, range_end]):
                    return jsonify({'error': 'Subnet, range_start, and range_end required'}), 400

                try:
                    dirs = _ensure_host_dirs(host)
                    dhcp_conf_path = f"{dirs['dhcp']}/dhcpd.conf"
                    
                    # Create DHCP configuration
                    dhcp_config = f"""
# DHCP Server Configuration for {device_id}
ddns-update-style none;

subnet {subnet} netmask {netmask} {{
    range {range_start} {range_end};
"""
                    if gateway:
                        dhcp_config += f"    option routers {gateway};\n"
                    
                    if dns_servers:
                        dns_list = ', '.join(dns_servers)
                        dhcp_config += f"    option domain-name-servers {dns_list};\n"
                    
                    dhcp_config += f"""    default-lease-time 600;
    max-lease-time 7200;
}}
"""
                    
                    # Write configuration file
                    host.cmd(f'cat > {dhcp_conf_path} << "EOF"\n{dhcp_config}EOF')
                    
                    # Create leases file
                    leases_file = f"{dirs['dhcp']}/dhcpd.leases"
                    host.cmd(f'touch {leases_file}')
                    
                    # Start DHCP server
                    dhcp_cmd = f'dhcpd -cf {dhcp_conf_path} -lf {leases_file} -pf {dirs["dhcp"]}/dhcpd.pid'
                    result = host.cmd(f'{dhcp_cmd} 2>&1')
                    
                    # Check if server started
                    time.sleep(2)
                    dhcp_status = _get_service_status(host, 'dhcp')
                    
                    results.append({
                        'action': 'configure_dhcp_server',
                        'success': dhcp_status['running'],
                        'config_file': dhcp_conf_path,
                        'leases_file': leases_file,
                        'subnet': f"{subnet}/{netmask}",
                        'range': f"{range_start}-{range_end}",
                        'output': result.strip()
                    })

                except Exception as e:
                    results.append({
                        'action': 'configure_dhcp_server',
                        'success': False,
                        'error': str(e)
                    })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'dhcp_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing DHCP for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/test-connectivity', methods=['POST'])
@log_api_request
def test_host_connectivity(device_id):
    """Test connectivity from host to various targets"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        config = request.get_json() or {}
        targets = config.get('targets', ['8.8.8.8'])  # Default to Google DNS
        test_type = config.get('type', 'ping')  # ping, traceroute, telnet
        timeout = config.get('timeout', 5)

        results = []

        for target in targets:
            test_result = {
                'target': target,
                'test_type': test_type,
                'success': False,
                'output': '',
                'latency_ms': None
            }

            try:
                if test_type == 'ping':
                    cmd = f'ping -c 3 -W {timeout} {target}'
                    output = host.cmd(cmd)
                    test_result['output'] = output.strip()
                    
                    # Check for successful pings
                    if '3 packets transmitted, 3 received' in output:
                        test_result['success'] = True
                        # Extract average latency
                        latency_match = re.search(r'avg = ([\d.]+)', output)
                        if latency_match:
                            test_result['latency_ms'] = float(latency_match.group(1))
                    elif 'received' in output:
                        # Partial success
                        test_result['success'] = True

                elif test_type == 'traceroute':
                    cmd = f'traceroute -w {timeout} {target}'
                    output = host.cmd(cmd)
                    test_result['output'] = output.strip()
                    test_result['success'] = 'trace to' in output.lower()

                elif test_type == 'telnet':
                    port = config.get('port', 80)
                    cmd = f'timeout {timeout} telnet {target} {port}'
                    output = host.cmd(cmd)
                    test_result['output'] = output.strip()
                    test_result['success'] = 'Connected to' in output

            except Exception as e:
                test_result['error'] = str(e)

            results.append(test_result)

        return jsonify({
            'success': True,
            'device_id': device_id,
            'connectivity_tests': results,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error testing connectivity for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@host_mgmt_bp.route('/devices/<device_id>/host/system', methods=['GET', 'POST'])
@log_api_request
def manage_host_system(device_id):
    """Manage host system configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            host = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Host {device_id} not found'}), 404

        if request.method == 'GET':
            system_info = {
                'hostname': host.cmd('hostname').strip(),
                'kernel': host.cmd('uname -r').strip(),
                'architecture': host.cmd('uname -m').strip(),
                'uptime': host.cmd('uptime').strip(),
                'timezone': host.cmd('date +%Z').strip(),
                'current_time': host.cmd('date').strip(),
                'shell': host.cmd('echo $SHELL').strip(),
                'environment_variables': {},
                'system_metrics': _get_system_metrics(host)
            }

            # Get some key environment variables
            env_vars = ['PATH', 'HOME', 'USER', 'SHELL']
            for var in env_vars:
                value = host.cmd(f'echo ${var}').strip()
                if value:
                    system_info['environment_variables'][var] = value

            return jsonify({
                'success': True,
                'device_id': device_id,
                'system_info': system_info,
                'timestamp': datetime.now().isoformat()
            })

        else:  # POST - Configure system settings
            config = request.get_json() or {}
            results = []

            # Set hostname
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
                        'success': False,
                        'error': str(e)
                    })

            # Set timezone
            if 'timezone' in config:
                timezone = config['timezone']
                try:
                    result = host.cmd(f'timedatectl set-timezone {timezone} 2>&1 || echo "timedatectl not available"')
                    results.append({
                        'action': 'set_timezone',
                        'timezone': timezone,
                        'success': 'not available' not in result,
                        'output': result.strip()
                    })
                except Exception as e:
                    results.append({
                        'action': 'set_timezone',
                        'success': False,
                        'error': str(e)
                    })

            # Execute custom commands
            if 'commands' in config:
                commands = config['commands']
                if isinstance(commands, list):
                    for cmd in commands:
                        try:
                            output = host.cmd(cmd)
                            results.append({
                                'action': 'execute_command',
                                'command': cmd,
                                'success': True,
                                'output': output.strip()
                            })
                        except Exception as e:
                            results.append({
                                'action': 'execute_command',
                                'command': cmd,
                                'success': False,
                                'error': str(e)
                            })

            return jsonify({
                'success': True,
                'device_id': device_id,
                'system_configuration_results': results,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error managing system for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500
    
    """
    # Host Management API Documentation

## Overview
This API provides comprehensive management capabilities for host devices in a Mininet network environment. It includes network configuration, service management, security settings, and system monitoring.

## Base URL
All endpoints are prefixed with `/api/host-management`

## Authentication
Currently no authentication required for local Mininet management.

---

## Endpoints

### 1. Get Host Status
**Endpoint:** `GET /devices/{device_id}/host/status`

**Description:** Get comprehensive status information for a host including network interfaces, routing, services, and system metrics.

**Parameters:**
- `device_id` (string, path): Host identifier (e.g., "h1", "h2")

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "device_id": "h4",
    "hostname": "h4",
    "primary_ip": "10.0.1.10",
    "primary_mac": "00:00:00:00:00:01",
    "primary_interface": "h4-eth0",
    "default_gateway": "10.0.1.1",
    "interfaces": [
      {
        "name": "h4-eth0",
        "ip_addresses": ["10.0.1.10/24"],
        "mac_address": "00:00:00:00:00:01",
        "mtu": 1500,
        "state": "UP",
        "primary_ip": "10.0.1.10",
        "netmask": "255.255.255.0",
        "broadcast": "10.0.1.255",
        "prefix_length": "24",
        "statistics": {
          "rx_bytes": 1234,
          "rx_packets": 10,
          "rx_errors": 0,
          "rx_dropped": 0,
          "tx_bytes": 5678,
          "tx_packets": 15,
          "tx_errors": 0,
          "tx_dropped": 0
        }
      }
    ],
    "dns_config": {
      "nameservers": ["8.8.8.8", "8.8.4.4"],
      "search_domains": ["local"],
      "resolv_conf": "nameserver 8.8.8.8\nnameserver 8.8.4.4",
      "dns_service_running": false
    },
    "routing_table": [
      {
        "destination": "default",
        "gateway": "10.0.1.1",
        "interface": "h4-eth0",
        "metric": 0,
        "flags": "UG",
        "type": "default"
      },
      {
        "destination": "10.0.1.0/24",
        "interface": "h4-eth0",
        "type": "connected"
      }
    ],
    "firewall_status": {
      "iptables_available": true,
      "ufw_available": "/usr/sbin/ufw",
      "active_rules": [],
      "policy": {
        "INPUT": "ACCEPT",
        "FORWARD": "ACCEPT",
        "OUTPUT": "ACCEPT"
      },
      "rule_count": 0,
      "chains": ["INPUT", "FORWARD", "OUTPUT"]
    },
    "dhcp_status": {
      "client": {
        "active_leases": [],
        "dhcp_enabled_interfaces": [],
        "current_servers": []
      },
      "server": {
        "running": false,
        "config_file": null,
        "leases_file": null,
        "active_leases": [],
        "configured_pools": []
      }
    },
    "system_metrics": {
      "cpu": {
        "usage_percent": 2.3,
        "load_average": [0.1, 0.2, 0.15]
      },
      "memory": {
        "total_mb": 4096,
        "used_mb": 1024,
        "free_mb": 3072,
        "usage_percent": 25.0
      },
      "disk": {
        "total_gb": 50,
        "used_gb": 20,
        "free_gb": 30,
        "usage_percent": 40.0
      },
      "network": {
        "total_rx_bytes": 12345,
        "total_tx_bytes": 67890
      },
      "uptime": "up 2 days, 4 hours",
      "processes": 25
    },
    "network_services": {
      "ssh": {
        "name": "SSH Server",
        "service_key": "ssh",
        "running": false,
        "port_listening": true,
        "processes": [],
        "port": 22,
        "config_files": [
          {
            "path": "/etc/ssh/sshd_config",
            "exists": false
          }
        ],
        "start_methods": ["/usr/sbin/sshd -D"],
        "stop_methods": ["pkill sshd"]
      }
      // ... other services (http, https, ftp, telnet, snmp, ntp, dhcp, dns)
    },
    "timestamp": "2025-08-14T19:09:53.847408"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Host h4 not found"
}
```

---

### 2. Manage Interfaces
**Endpoint:** `GET|POST /devices/{device_id}/host/interfaces`

#### GET Method
**Description:** Get detailed information about all network interfaces.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "interfaces": [
    {
      "name": "h4-eth0",
      "ip_addresses": ["10.0.1.10/24"],
      "mac_address": "00:00:00:00:00:01",
      "mtu": 1500,
      "state": "UP",
      "primary_ip": "10.0.1.10",
      "netmask": "255.255.255.0",
      "broadcast": "10.0.1.255",
      "prefix_length": "24",
      "statistics": {
        "rx_bytes": 1234,
        "rx_packets": 10,
        "rx_errors": 0,
        "rx_dropped": 0,
        "tx_bytes": 5678,
        "tx_packets": 15,
        "tx_errors": 0,
        "tx_dropped": 0
      }
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Configure network interface settings.

**Request Body:**
```json
{
  "interface": "h4-eth0",
  "action": "configure",  // "configure" or "flush"
  "ip_address": "10.0.1.20/24",  // Optional
  "state": "up",  // Optional: "up" or "down"
  "mtu": 1500  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "interface_configuration_results": [
    {
      "action": "set_ip",
      "interface": "h4-eth0",
      "ip_address": "10.0.1.20/24",
      "success": true,
      "output": ""
    },
    {
      "action": "set_state",
      "interface": "h4-eth0",
      "state": "up",
      "success": true,
      "output": ""
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 3. Manage DNS
**Endpoint:** `GET|POST /devices/{device_id}/host/dns`

#### GET Method
**Description:** Get current DNS configuration.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "dns_config": {
    "nameservers": ["8.8.8.8", "8.8.4.4"],
    "search_domains": ["local"],
    "resolv_conf": "nameserver 8.8.8.8\nnameserver 8.8.4.4",
    "dns_service_running": false
  },
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Configure DNS settings.

**Request Body:**
```json
{
  "nameservers": ["8.8.8.8", "1.1.1.1"],
  "search_domains": ["example.com", "local"],  // Optional
  "test_resolution": "google.com"  // Optional: test DNS resolution
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "dns_configuration_results": [
    {
      "action": "configure_dns",
      "nameservers": ["8.8.8.8", "1.1.1.1"],
      "success": true,
      "message": "DNS configuration updated"
    },
    {
      "action": "test_dns",
      "test_host": "google.com",
      "success": true,
      "output": "Server: 8.8.8.8\nAddress: 8.8.8.8#53\n\nNon-authoritative answer:\nName: google.com\nAddress: 142.250.191.14"
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 4. Manage Services
**Endpoint:** `GET|POST /devices/{device_id}/host/services/{service_name}`

**Available Services:** ssh, http, https, ftp, telnet, snmp, ntp, dhcp, dns

#### GET Method
**Description:** Get status of a specific service.

**Parameters:**
- `device_id` (string, path): Host identifier
- `service_name` (string, path): Service name (ssh, http, https, ftp, telnet, snmp, ntp, dhcp, dns)

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "service": {
    "name": "HTTP Server",
    "service_key": "http",
    "running": true,
    "port_listening": true,
    "processes": [
      {
        "pid": "1234",
        "details": "1234  1  python3 -m http.server 80"
      }
    ],
    "port": 80,
    "config_files": [
      {
        "path": "/etc/apache2/apache2.conf",
        "exists": false
      },
      {
        "path": "/etc/nginx/nginx.conf",
        "exists": false
      }
    ],
    "start_methods": ["python3 -m http.server 80", "service apache2 start"],
    "stop_methods": ["pkill -f \"python3 -m http.server\"", "service apache2 stop"]
  },
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Control service (start/stop/restart).

**Request Body:**
```json
{
  "action": "start",  // "start", "stop", or "restart"
  "port": 8080  // Optional: custom port for applicable services
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "service_results": [
    {
      "action": "start",
      "service": "http",
      "port": 8080,
      "success": true,
      "command": "python3 -m http.server 8080",
      "output": ""
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 5. Manage Routes
**Endpoint:** `GET|POST|DELETE /devices/{device_id}/host/routes`

#### GET Method
**Description:** Get routing table.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "routes": [
    {
      "destination": "default",
      "gateway": "10.0.1.1",
      "interface": "h4-eth0",
      "metric": 0,
      "flags": "UG",
      "type": "default"
    },
    {
      "destination": "10.0.1.0/24",
      "interface": "h4-eth0",
      "type": "connected"
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Add a static route.

**Request Body:**
```json
{
  "destination": "192.168.1.0/24",
  "gateway": "10.0.1.1",  // Optional
  "interface": "h4-eth0",  // Optional
  "metric": 100  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "action": "add_route",
  "command": "ip route add 192.168.1.0/24 via 10.0.1.1 dev h4-eth0 metric 100",
  "output": "",
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### DELETE Method
**Description:** Delete a static route.

**Query Parameters:**
- `destination` (string, required): Destination network
- `gateway` (string, optional): Gateway IP

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "action": "delete_route",
  "command": "ip route del 192.168.1.0/24 via 10.0.1.1",
  "output": "",
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 6. Manage Firewall
**Endpoint:** `GET|POST /devices/{device_id}/host/firewall`

#### GET Method
**Description:** Get firewall status and rules.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "firewall": {
    "iptables_available": true,
    "ufw_available": "/usr/sbin/ufw",
    "active_rules": [
      {
        "chain": "INPUT",
        "line_number": "1",
        "target": "ACCEPT",
        "protocol": "tcp",
        "source": "0.0.0.0/0",
        "destination": "0.0.0.0/0",
        "raw": "1    ACCEPT     tcp  --  0.0.0.0/0    0.0.0.0/0    tcp dpt:22"
      }
    ],
    "policy": {
      "INPUT": "ACCEPT",
      "FORWARD": "ACCEPT",
      "OUTPUT": "ACCEPT"
    },
    "rule_count": 1,
    "chains": ["INPUT", "FORWARD", "OUTPUT"]
  },
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Manage firewall rules.

**Request Body:**
```json
{
  "action": "add",  // "add", "delete", "flush", "set_policy"
  "chain": "INPUT",  // "INPUT", "OUTPUT", "FORWARD"
  "target": "ACCEPT",  // "ACCEPT", "DROP", "REJECT"
  "protocol": "tcp",  // Optional
  "source": "192.168.1.0/24",  // Optional
  "destination": "0.0.0.0/0",  // Optional
  "port": 22,  // Optional
  "rule_number": 1,  // Required for delete action
  "policy": "DROP"  // Required for set_policy action
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "firewall_results": [
    {
      "action": "add_rule",
      "command": "iptables -A INPUT -p tcp -s 192.168.1.0/24 -d 0.0.0.0/0 --dport 22 -j ACCEPT",
      "success": true,
      "output": ""
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 7. Manage DHCP
**Endpoint:** `GET|POST /devices/{device_id}/host/dhcp`

#### GET Method
**Description:** Get DHCP client and server status.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "dhcp_status": {
    "client": {
      "active_leases": ["10.0.1.10"],
      "dhcp_enabled_interfaces": ["h4-eth0"],
      "current_servers": ["10.0.1.1"]
    },
    "server": {
      "running": false,
      "config_file": null,
      "leases_file": null,
      "active_leases": [],
      "configured_pools": []
    }
  },
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Configure DHCP client or server.

**Request Body for Client:**
```json
{
  "action": "enable_client",  // "enable_client" or "disable_client"
  "interface": "h4-eth0"
}
```

**Request Body for Server:**
```json
{
  "action": "configure_server",
  "subnet": "192.168.1.0",
  "netmask": "255.255.255.0",
  "range_start": "192.168.1.100",
  "range_end": "192.168.1.200",
  "gateway": "192.168.1.1",  // Optional
  "dns_servers": ["8.8.8.8", "8.8.4.4"]  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "dhcp_results": [
    {
      "action": "enable_dhcp_client",
      "interface": "h4-eth0",
      "success": true,
      "output": "",
      "ip_assigned": "inet 10.0.1.10/24 brd 10.0.1.255 scope global h4-eth0"
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 8. Test Connectivity
**Endpoint:** `POST /devices/{device_id}/host/test-connectivity`

**Description:** Test network connectivity to various targets.

**Request Body:**
```json
{
  "targets": ["8.8.8.8", "google.com", "10.0.1.1"],
  "type": "ping",  // "ping", "traceroute", "telnet"
  "timeout": 5,  // Optional, default 5 seconds
  "port": 80  // Optional, for telnet test
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "connectivity_tests": [
    {
      "target": "8.8.8.8",
      "test_type": "ping",
      "success": true,
      "output": "PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.\n64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=1.23 ms\n64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=1.45 ms\n64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=1.34 ms\n\n--- 8.8.8.8 ping statistics ---\n3 packets transmitted, 3 received, 0% packet loss, time 2003ms\nrtt min/avg/max/mdev = 1.234/1.340/1.456/0.091 ms",
      "latency_ms": 1.34
    },
    {
      "target": "google.com",
      "test_type": "ping",
      "success": true,
      "output": "...",
      "latency_ms": 2.45
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

### 9. Manage System
**Endpoint:** `GET|POST /devices/{device_id}/host/system`

#### GET Method
**Description:** Get system information and metrics.

**Parameters:**
- `device_id` (string, path): Host identifier

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "system_info": {
    "hostname": "h4",
    "kernel": "5.4.0-74-generic",
    "architecture": "x86_64",
    "uptime": " 09:15:23 up 2 days,  4:32,  0 users,  load average: 0.08, 0.03, 0.01",
    "timezone": "UTC",
    "current_time": "Wed Aug 14 19:15:23 UTC 2025",
    "shell": "/bin/bash",
    "environment_variables": {
      "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
      "HOME": "/root",
      "USER": "root",
      "SHELL": "/bin/bash"
    },
    "system_metrics": {
      "cpu": {
        "usage_percent": 2.3,
        "load_average": [0.08, 0.03, 0.01]
      },
      "memory": {
        "total_mb": 4096,
        "used_mb": 1024,
        "free_mb": 3072,
        "usage_percent": 25.0
      },
      "disk": {
        "total_gb": 50,
        "used_gb": 20,
        "free_gb": 30,
        "usage_percent": 40.0
      },
      "network": {
        "total_rx_bytes": 12345,
        "total_tx_bytes": 67890
      },
      "uptime": "up 2 days, 4 hours",
      "processes": 25
    }
  },
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

#### POST Method
**Description:** Configure system settings.

**Request Body:**
```json
{
  "hostname": "new-hostname",  // Optional
  "timezone": "America/New_York",  // Optional
  "commands": [  // Optional: execute custom commands
    "echo 'Hello World'",
    "ls -la /tmp"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "device_id": "h4",
  "system_configuration_results": [
    {
      "action": "set_hostname",
      "hostname": "new-hostname",
      "success": true
    },
    {
      "action": "set_timezone",
      "timezone": "America/New_York",
      "success": true,
      "output": ""
    },
    {
      "action": "execute_command",
      "command": "echo 'Hello World'",
      "success": true,
      "output": "Hello World"
    }
  ],
  "timestamp": "2025-08-14T19:09:53.847408"
}
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200 OK`: Request successful
- `400 Bad Request`: Invalid parameters or network not running
- `404 Not Found`: Host not found
- `500 Internal Server Error`: Server-side error

---

## Usage Examples

### Example 1: Get Host Status
```bash
curl -X GET http://localhost:5000/api/host-management/devices/h1/host/status
```

### Example 2: Configure Interface
```bash
curl -X POST http://localhost:5000/api/host-management/devices/h1/host/interfaces \
  -H "Content-Type: application/json" \
  -d '{
    "interface": "h1-eth0",
    "action": "configure",
    "ip_address": "10.0.1.20/24",
    "state": "up"
  }'
```

### Example 3: Start HTTP Service
```bash
curl -X POST http://localhost:5000/api/host-management/devices/h1/host/services/http \
  -H "Content-Type: application/json" \
  -d '{
    "action": "start",
    "port": 8080
  }'
```

### Example 4: Add Static Route
```bash
curl -X POST http://localhost:5000/api/host-management/devices/h1/host/routes \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "192.168.1.0/24",
    "gateway": "10.0.1.1",
    "interface": "h1-eth0"
  }'
```

### Example 5: Test Connectivity
```bash
curl -X POST http://localhost:5000/api/host-management/devices/h1/host/test-connectivity \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["8.8.8.8", "google.com"],
    "type": "ping",
    "timeout": 5
  }'
```

---

## Notes

1. **Network State**: All endpoints require the Mininet network to be running
2. **Device IDs**: Use actual Mininet host names (h1, h2, h3, etc.)
3. **Service Management**: Services are managed using multiple fallback methods for reliability
4. **Error Tolerance**: Most operations include error handling and graceful degradation
5. **Logging**: All API calls are logged for debugging purposes
6. **Real-time Data**: Status information is collected in real-time from the actual Mininet hosts

---

## Service Definitions

The following network services are supported:

| Service | Default Port | Description |
|---------|-------------|-------------|
| ssh | 22 | SSH Server |
| http | 80 | HTTP Server (Python SimpleHTTPServer, Apache, Nginx) |
| https | 443 | HTTPS Server (Apache, Nginx) |
| ftp | 21 | FTP Server (pyftpdlib, vsftpd) |
| telnet | 23 | Telnet Server |
| snmp | 161 | SNMP Agent |
| ntp | 123 | NTP Server |
| dhcp | 67 | DHCP Server |
| dns | 53 | DNS Server (BIND, dnsmasq) |

Each service supports multiple implementation methods and includes automatic process detection and port monitoring.
    """