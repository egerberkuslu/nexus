"""
Configuration Manager - Business Logic for Device Configuration
Contains all the helper functions and business logic for applying device configurations.
"""

import os
import re
import subprocess
from datetime import datetime
from flask import request, current_app
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ======================= UTILITY FUNCTIONS =======================

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

def validate_request_and_setup():
    """Validate request and setup basic variables"""
    try:
        spec = request.get_json(force=True, silent=False) or {}
        validate_only = bool(spec.get('validate_only', False))
        
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return None, None, {'error': 'Network not running'}, 400
            
        return spec, validate_only, mininet_mgr, None
    except Exception as e:
        logger.error(f"Request validation error: {e}")
        return None, None, {'error': f'Invalid request: {str(e)}'}, 400

def node_exists(mininet_mgr, node_name):
    """Check if node exists in network"""
    try:
        _ = mininet_mgr.net.get(node_name)
        return True
    except Exception:
        return False

def get_node_safely(mininet_mgr, node_name):
    """Safely get a node from the network"""
    try:
        return mininet_mgr.net.get(node_name), None
    except Exception as e:
        return None, f'Failed to get node {node_name}: {e}'

# ======================= COMMAND PLANNING CLASS =======================

class CommandPlanner:
    """Manages command planning and execution queue"""
    
    def __init__(self):
        self.plan = []
        self.results = []
    
    def enqueue(self, node_name, where, cmd, ignore_error=False, description=None):
        """Add command to execution plan"""
        self.plan.append({
            'node': node_name,
            'where': where,
            'cmd': cmd,
            'ignore_error': ignore_error,
            'description': description or cmd[:50] + '...' if len(cmd) > 50 else cmd
        })
        logger.debug(f"Enqueued command for {node_name}: {cmd}")
    
    def get_plan(self):
        """Get the current execution plan"""
        return self.plan
    
    def get_results(self):
        """Get execution results"""
        return self.results
    
    def add_result(self, result):
        """Add execution result"""
        self.results.append(result)

# ======================= NODE STATE INSPECTION FUNCTIONS =======================

def get_current_interfaces(node):
    """Get current configured interfaces with their IPs"""
    interfaces = {}
    try:
        # Get all interfaces with their IPs
        result = node.cmd('ip -o -4 addr show')
        for line in result.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    ifname = parts[1]
                    ip_cidr = parts[3]
                    if ifname != 'lo:':
                        interfaces[ifname] = ip_cidr
    except Exception as e:
        logger.error(f"Error getting interfaces: {e}")
    return interfaces

def get_current_routes(node):
    """Get current routing table entries"""
    routes = []
    try:
        result = node.cmd('ip route show')
        for line in result.strip().split('\n'):
            if line.strip():
                routes.append(line.strip())
    except Exception as e:
        logger.error(f"Error getting routes: {e}")
    return routes

def get_current_nat_rules(node):
    """Get current NAT rules"""
    nat_rules = []
    try:
        result = node.cmd('iptables -t nat -L -n --line-numbers')
        for line in result.strip().split('\n'):
            if line.strip() and not line.startswith('Chain') and not line.startswith('num'):
                nat_rules.append(line.strip())
    except Exception as e:
        logger.error(f"Error getting NAT rules: {e}")
    return nat_rules

def get_current_firewall_rules(node):
    """Get current firewall rules"""
    fw_rules = []
    try:
        result = node.cmd('iptables -L -n --line-numbers')
        for line in result.strip().split('\n'):
            if line.strip() and not line.startswith('Chain') and not line.startswith('num'):
                fw_rules.append(line.strip())
    except Exception as e:
        logger.error(f"Error getting firewall rules: {e}")
    return fw_rules

def interface_exists(node, ifname):
    """Check if interface exists"""
    try:
        result = node.cmd(f'ip link show {ifname} 2>/dev/null')
        return result.strip() != ''
    except:
        return False

def check_routing_daemon_availability(node, daemon_name):
    """Check if routing daemon is available on the node"""
    try:
        result = node.cmd(f'which {daemon_name}')
        return result.strip() != ''
    except:
        return False

def get_process_status(node, process_pattern):
    """Get status of processes matching pattern"""
    try:
        result = node.cmd(f'ps aux | grep -E "{process_pattern}" | grep -v grep')
        return result.strip().split('\n') if result.strip() else []
    except:
        return []

# ======================= INTERFACE MANAGEMENT FUNCTIONS =======================

def configure_interface(planner, node_name, iface_config):
    """Generate commands to configure an interface"""
    ifname = iface_config.get('name')
    if not ifname:
        logger.warning(f"Interface configuration missing name: {iface_config}")
        return

    logger.info(f"Configuring interface {ifname} on {node_name}")
    
    # Handle interface deletion
    if iface_config.get('action') == 'delete':
        planner.enqueue(node_name, 'router', f'ip addr flush dev {ifname}', 
                       ignore_error=True, description=f"Flush interface {ifname}")
        planner.enqueue(node_name, 'router', f'ip link set dev {ifname} down', 
                       ignore_error=True, description=f"Bring down interface {ifname}")
        return

    # Check if we need to flush existing config
    if iface_config.get('flush', False):
        planner.enqueue(node_name, 'router', f'ip addr flush dev {ifname}', 
                       ignore_error=True, description=f"Flush interface {ifname}")

    # Configure addresses
    addresses = iface_config.get('addresses', [])
    for addr in addresses:
        if addr and addr.strip():
            # Remove any existing instance of this address first (idempotent)
            planner.enqueue(node_name, 'router', f'ip addr del {addr} dev {ifname}', 
                           ignore_error=True, description=f"Remove existing address {addr}")
            planner.enqueue(node_name, 'router', f'ip addr add {addr} dev {ifname}', 
                           description=f"Add address {addr} to {ifname}")

    # Set interface state
    state = iface_config.get('state', 'up')
    if state in ['up', 'down']:
        planner.enqueue(node_name, 'router', f'ip link set dev {ifname} {state}', 
                       description=f"Set interface {ifname} {state}")

def process_interface_configurations(planner, node_name, node, interfaces_config):
    """Process all interface configurations for a node"""
    logger.info(f"Processing interface configurations for {node_name}")
    
    current_interfaces = get_current_interfaces(node)
    logger.debug(f"Current interfaces on {node_name}: {current_interfaces}")
    
    # Track configured interfaces
    configured_interfaces = set()
    interfaces_to_delete = set()
    
    # Process each interface configuration
    for iface in interfaces_config:
        ifname = iface.get('name')
        if not ifname:
            continue
            
        action = iface.get('action', 'configure').lower()
        
        if action in ['delete', 'remove']:
            interfaces_to_delete.add(ifname)
            configure_interface(planner, node_name, iface)
        else:
            configured_interfaces.add(ifname)
            configure_interface(planner, node_name, iface)
    
    logger.info(f"Configured interfaces: {configured_interfaces}")
    logger.info(f"Deleted interfaces: {interfaces_to_delete}")

# ======================= ROUTE MANAGEMENT FUNCTIONS =======================

def process_static_route(planner, node_name, route_config, current_routes):
    """Process a single static route configuration"""
    action = route_config.get('action', 'add').lower()
    destination = route_config.get('destination', '')
    via = route_config.get('via', '')
    dev = route_config.get('dev', '')
    metric = route_config.get('metric', '')
    
    if not destination:
        logger.warning(f"Route configuration missing destination: {route_config}")
        return

    logger.debug(f"Processing route: {action} {destination} via {via} dev {dev}")

    # Build route command
    if action in ['del', 'delete']:
        # Delete route - be lenient about errors
        base_cmd = f'ip route del {destination}'
        if via:
            base_cmd += f' via {via}'
        if dev:
            base_cmd += f' dev {dev}'
        planner.enqueue(node_name, 'router', base_cmd, ignore_error=True, 
                       description=f"Delete route to {destination}")
        
    elif action == 'add':
        # Check if route already exists
        route_exists = any(destination in existing_route for existing_route in current_routes)
        
        if route_exists:
            # Delete existing route first for idempotent operation
            planner.enqueue(node_name, 'router', f'ip route del {destination}', 
                           ignore_error=True, description=f"Remove existing route to {destination}")
        
        # Add new route
        base_cmd = f'ip route add {destination}'
        if via:
            base_cmd += f' via {via}'
        if dev:
            base_cmd += f' dev {dev}'
        if metric:
            base_cmd += f' metric {metric}'
        planner.enqueue(node_name, 'router', base_cmd, 
                       description=f"Add route to {destination}")
        
    elif action == 'replace':
        # Replace route (atomic operation)
        base_cmd = f'ip route replace {destination}'
        if via:
            base_cmd += f' via {via}'
        if dev:
            base_cmd += f' dev {dev}'
        if metric:
            base_cmd += f' metric {metric}'
        planner.enqueue(node_name, 'router', base_cmd, 
                       description=f"Replace route to {destination}")

def process_route_configurations(planner, node_name, node, routes_config):
    """Process all route configurations for a node"""
    logger.info(f"Processing route configurations for {node_name}")
    
    if not routes_config:
        logger.debug(f"No route configurations for {node_name}")
        return
    
    current_routes = get_current_routes(node)
    logger.debug(f"Current routes on {node_name}: {len(current_routes)} routes")
    
    for route in routes_config:
        process_static_route(planner, node_name, route, current_routes)

# ======================= NAT MANAGEMENT FUNCTIONS =======================

def build_nat_rule_match_criteria(nat_rule):
    """Build match criteria for NAT rule"""
    match_criteria = ''
    
    if nat_rule.get('source'):
        match_criteria += f' -s {nat_rule["source"]}'
    if nat_rule.get('destination'):
        match_criteria += f' -d {nat_rule["destination"]}'
    if nat_rule.get('in_interface'):
        match_criteria += f' -i {nat_rule["in_interface"]}'
    if nat_rule.get('out_interface'):
        match_criteria += f' -o {nat_rule["out_interface"]}'
    if nat_rule.get('protocol'):
        match_criteria += f' -p {nat_rule["protocol"]}'
    if nat_rule.get('sport'):
        match_criteria += f' --sport {nat_rule["sport"]}'
    if nat_rule.get('dport'):
        match_criteria += f' --dport {nat_rule["dport"]}'
    
    return match_criteria

def build_nat_rule_target(nat_rule):
    """Build target specification for NAT rule"""
    nat_type = nat_rule.get('type', 'masquerade').lower()
    
    if nat_type == 'snat' and nat_rule.get('to_source'):
        return f' -j SNAT --to-source {nat_rule["to_source"]}'
    elif nat_type == 'dnat' and nat_rule.get('to_destination'):
        return f' -j DNAT --to-destination {nat_rule["to_destination"]}'
    else:
        target = nat_rule.get('target', 'MASQUERADE')
        return f' -j {target}'

def process_nat_rule(planner, node_name, nat_rule):
    """Process a single NAT rule configuration"""
    action = nat_rule.get('action', 'add').lower()
    chain = nat_rule.get('chain', 'POSTROUTING')
    
    logger.debug(f"Processing NAT rule: {action} in chain {chain}")
    
    if action in ['del', 'delete']:
        # Build delete command
        cmd = f'iptables -t nat -D {chain}'
        cmd += build_nat_rule_match_criteria(nat_rule)
        cmd += build_nat_rule_target(nat_rule)
        
        planner.enqueue(node_name, 'router', cmd, ignore_error=True, 
                       description=f"Delete NAT rule from {chain}")
        
    elif action in ['add', 'append']:
        # Build idempotent add command (check first, then add if not exists)
        match_criteria = build_nat_rule_match_criteria(nat_rule)
        target_spec = build_nat_rule_target(nat_rule)
        
        check_cmd = f'iptables -t nat -C {chain}{match_criteria}{target_spec}'
        add_cmd = f'iptables -t nat -A {chain}{match_criteria}{target_spec}'
        
        # Idempotent add
        combined_cmd = f'{check_cmd} 2>/dev/null || {add_cmd}'
        planner.enqueue(node_name, 'router', combined_cmd, 
                       description=f"Add NAT rule to {chain} (idempotent)")

def process_nat_configurations(planner, node_name, node, nat_rules_config):
    """Process all NAT rule configurations for a node"""
    logger.info(f"Processing NAT configurations for {node_name}")
    
    if not nat_rules_config:
        logger.debug(f"No NAT configurations for {node_name}")
        return
    
    current_nat_rules = get_current_nat_rules(node)
    logger.debug(f"Current NAT rules on {node_name}: {len(current_nat_rules)} rules")
    
    for nat_rule in nat_rules_config:
        process_nat_rule(planner, node_name, nat_rule)

# ======================= FIREWALL MANAGEMENT FUNCTIONS =======================

def build_firewall_rule_match_criteria(fw_rule):
    """Build match criteria for firewall rule"""
    match_criteria = ''
    
    if fw_rule.get('protocol'):
        match_criteria += f' -p {fw_rule["protocol"]}'
    if fw_rule.get('source'):
        match_criteria += f' -s {fw_rule["source"]}'
    if fw_rule.get('destination'):
        match_criteria += f' -d {fw_rule["destination"]}'
    if fw_rule.get('sport'):
        match_criteria += f' --sport {fw_rule["sport"]}'
    if fw_rule.get('dport'):
        match_criteria += f' --dport {fw_rule["dport"]}'
    if fw_rule.get('in_interface'):
        match_criteria += f' -i {fw_rule["in_interface"]}'
    if fw_rule.get('out_interface'):
        match_criteria += f' -o {fw_rule["out_interface"]}'
    if fw_rule.get('state'):
        match_criteria += f' -m state --state {fw_rule["state"]}'
    
    return match_criteria

def process_firewall_rule(planner, node_name, fw_rule):
    """Process a single firewall rule configuration"""
    action = fw_rule.get('action', 'add').lower()
    chain = fw_rule.get('chain', 'INPUT')
    position = fw_rule.get('position')
    
    logger.debug(f"Processing firewall rule: {action} in chain {chain}")
    
    if action in ['del', 'delete']:
        # Build delete command
        cmd = f'iptables -D {chain}'
        cmd += build_firewall_rule_match_criteria(fw_rule)
        cmd += f' -j {fw_rule.get("target", "ACCEPT")}'
        
        planner.enqueue(node_name, 'router', cmd, ignore_error=True, 
                       description=f"Delete firewall rule from {chain}")
        
    elif action == 'insert':
        # Insert at specific position
        pos = position if position else 1
        cmd = f'iptables -I {chain} {pos}'
        cmd += build_firewall_rule_match_criteria(fw_rule)
        cmd += f' -j {fw_rule.get("target", "ACCEPT")}'
        
        planner.enqueue(node_name, 'router', cmd, 
                       description=f"Insert firewall rule at position {pos} in {chain}")
        
    elif action in ['add', 'append']:
        # Build idempotent add command
        match_criteria = build_firewall_rule_match_criteria(fw_rule)
        target = f' -j {fw_rule.get("target", "ACCEPT")}'
        
        check_cmd = f'iptables -C {chain}{match_criteria}{target}'
        add_cmd = f'iptables -A {chain}{match_criteria}{target}'
        
        # Idempotent add
        combined_cmd = f'{check_cmd} 2>/dev/null || {add_cmd}'
        planner.enqueue(node_name, 'router', combined_cmd, 
                       description=f"Add firewall rule to {chain} (idempotent)")

def process_firewall_configurations(planner, node_name, node, firewall_rules_config):
    """Process all firewall rule configurations for a node"""
    logger.info(f"Processing firewall configurations for {node_name}")
    
    if not firewall_rules_config:
        logger.debug(f"No firewall configurations for {node_name}")
        return
    
    current_fw_rules = get_current_firewall_rules(node)
    logger.debug(f"Current firewall rules on {node_name}: {len(current_fw_rules)} rules")
    
    for fw_rule in firewall_rules_config:
        process_firewall_rule(planner, node_name, fw_rule)

# ======================= ROUTING PROTOCOL MANAGEMENT FUNCTIONS =======================

def generate_rip_config(config):
    """Generate basic RIP configuration"""
    version = config.get('version', '2')
    rip_config = f"""# Basic RIP configuration
hostname router
password zebra
log stdout
!
router rip
 version {version}
 network 0.0.0.0/0
!
line vty
!"""
    
    return f'echo "{rip_config}" > /etc/frr/ripd.conf 2>/dev/null || echo "{rip_config}" > /etc/quagga/ripd.conf 2>/dev/null || echo "RIP config created"'

def generate_ospf_config(config):
    """Generate basic OSPF configuration"""
    area_id = config.get('area_id', '0')
    router_id = config.get('router_id', '')
    
    ospf_config = f"""# Basic OSPF configuration
hostname router
password zebra
log stdout
!
router ospf"""
    
    if router_id:
        ospf_config += f"\n router-id {router_id}"
    
    ospf_config += f"\n network 0.0.0.0/0 area {area_id}"
    ospf_config += "\n!\nline vty\n!"
    
    return f'echo "{ospf_config}" > /etc/frr/ospfd.conf 2>/dev/null || echo "{ospf_config}" > /etc/quagga/ospfd.conf 2>/dev/null || echo "OSPF config created"'

def generate_bgp_config(config):
    """Generate basic BGP configuration"""
    as_number = config.get('as_number', '65001')
    router_id = config.get('router_id', '')
    
    bgp_config = f"""# Basic BGP configuration
hostname router
password zebra
log stdout
!
router bgp {as_number}"""
    
    if router_id:
        bgp_config += f"\n bgp router-id {router_id}"
    
    bgp_config += "\n!\nline vty\n!"
    
    return f'echo "{bgp_config}" > /etc/frr/bgpd.conf 2>/dev/null || echo "{bgp_config}" > /etc/quagga/bgpd.conf 2>/dev/null || echo "BGP config created"'


def detect_routing_environment(node):
    """Detect what routing software is available on the node"""
    environment = {
        'frr_available': False,
        'quagga_available': False,
        'daemons_available': {},
        'config_paths': {},
        'recommendation': 'static'
    }
    
    # Check for FRR
    try:
        frr_check = node.cmd('ls /usr/lib/frr/ 2>/dev/null | head -1')
        if frr_check.strip():
            environment['frr_available'] = True
            environment['config_paths']['base'] = '/etc/frr'
    except:
        pass
    
    # Check for Quagga
    try:
        quagga_check = node.cmd('ls /usr/lib/quagga/ 2>/dev/null | head -1')
        if quagga_check.strip():
            environment['quagga_available'] = True
            if not environment['frr_available']:  # Prefer FRR over Quagga
                environment['config_paths']['base'] = '/etc/quagga'
    except:
        pass
    
    # Check individual daemons
    daemons = ['zebra', 'ripd', 'ospfd', 'bgpd', 'isisd', 'pimd']
    for daemon in daemons:
        try:
            result = node.cmd(f'which {daemon}')
            environment['daemons_available'][daemon] = bool(result.strip())
        except:
            environment['daemons_available'][daemon] = False
    
    # Determine recommendation
    if environment['frr_available'] or environment['quagga_available']:
        if any(environment['daemons_available'].values()):
            environment['recommendation'] = 'dynamic'
        else:
            environment['recommendation'] = 'limited'
    else:
        environment['recommendation'] = 'static'
    
    return environment

def check_protocol_prerequisites(node, protocol):
    """Check if prerequisites for a specific protocol are met"""
    env = detect_routing_environment(node)
    
    prerequisites = {
        'static': {'required_daemons': [], 'available': True},
        'rip': {'required_daemons': ['ripd'], 'available': False},
        'ospf': {'required_daemons': ['ospfd'], 'available': False},
        'bgp': {'required_daemons': ['bgpd'], 'available': False}
    }
    
    if protocol not in prerequisites:
        return {'available': False, 'missing': ['Unknown protocol']}
    
    prereq = prerequisites[protocol]
    missing_daemons = []
    
    for daemon in prereq['required_daemons']:
        if not env['daemons_available'].get(daemon, False):
            missing_daemons.append(daemon)
    
    prereq['available'] = len(missing_daemons) == 0
    prereq['missing'] = missing_daemons
    prereq['environment'] = env
    
    return prereq

# ======================= ENHANCED ROUTING PROTOCOL MANAGEMENT =======================

def install_routing_software_commands(node_name):
    """Generate commands to attempt installing routing software"""
    return [
        'apt-get update',
        'apt-get install -y frr frr-pythontools',
        'systemctl enable frr',
        'echo "frr installation attempted"'
    ]

def create_frr_daemons_file(protocols):
    """Create the daemons configuration file for FRR"""
    daemons_config = """# FRR daemons configuration
zebra=yes
bgpd={bgp}
ospfd={ospf}
ospf6d=no
ripd={rip}
ripngd=no
isisd=no
pimd=no
ldpd=no
nhrpd=no
eigrpd=no
babeld=no
sharpd=no
pbrd=no
bfdd=no
fabricd=no

vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
ospfd_options="  -A 127.0.0.1"
ripd_options="   -A 127.0.0.1"
""".format(
        bgp='yes' if 'bgp' in protocols else 'no',
        ospf='yes' if 'ospf' in protocols else 'no',
        rip='yes' if 'rip' in protocols else 'no'
    )
    
    return f'echo "{daemons_config}" > /etc/frr/daemons'

def enhanced_process_routing_protocol(planner, node_name, node, protocol_config):
    """Enhanced routing protocol processing with better error handling"""
    protocol = protocol_config.get('protocol', '').lower()
    action = protocol_config.get('action', 'enable').lower()
    config = protocol_config.get('config', {})
    
    logger.info(f"Processing routing protocol: {protocol}, action: {action} for {node_name}")
    
    # Check prerequisites
    prereqs = check_protocol_prerequisites(node, protocol)
    
    if protocol == 'static':
        if action == 'enable':
            # Stop all dynamic routing protocols for static-only mode
            planner.enqueue(node_name, 'router', 'killall -9 ripd ospfd bgpd zebra', 
                           ignore_error=True, description="Stop all dynamic routing protocols")
            planner.enqueue(node_name, 'router', 'echo "Static routing enabled - dynamic protocols stopped"', 
                           description="Static routing confirmation")
        return
    
    # For dynamic protocols, check if software is available
    if not prereqs['available']:
        missing_daemons = ', '.join(prereqs['missing'])
        env = prereqs['environment']
        
        # Provide detailed feedback about what's missing and how to fix it
        if not env['frr_available'] and not env['quagga_available']:
            planner.enqueue(node_name, 'router', 
                           f'echo "ERROR: No routing software (FRR/Quagga) installed for {protocol.upper()} protocol"', 
                           description=f"Missing routing software for {protocol}")
            planner.enqueue(node_name, 'router', 
                           'echo "SOLUTION: Install FRR with: apt-get update && apt-get install -y frr"', 
                           description="Installation instructions")
            planner.enqueue(node_name, 'router', 
                           f'echo "FALLBACK: Using static routing instead of {protocol.upper()}"', 
                           description="Fallback notification")
            
            # Offer to attempt installation (optional)
            planner.enqueue(node_name, 'router', 
                           'echo "Would you like to attempt automatic installation? (requires internet)"', 
                           description="Installation offer")
            
            return  # Don't proceed with protocol configuration
        else:
            planner.enqueue(node_name, 'router', 
                           f'echo "ERROR: {protocol.upper()} daemon ({missing_daemons}) not available"', 
                           description=f"Missing {protocol} daemon")
            planner.enqueue(node_name, 'router', 
                           f'echo "Available routing software detected but {missing_daemons} daemon(s) missing"', 
                           description="Partial routing software")
            return
    
    # If we get here, prerequisites are met
    base_config_path = prereqs['environment']['config_paths'].get('base', '/etc/frr')
    
    if action == 'enable':
        # Protocol-specific configuration
        if protocol == 'rip':
            configure_rip_protocol(planner, node_name, config, base_config_path)
        elif protocol == 'ospf':
            configure_ospf_protocol(planner, node_name, config, base_config_path)
        elif protocol == 'bgp':
            configure_bgp_protocol(planner, node_name, config, base_config_path)
            
    elif action == 'disable':
        # Stop specific protocol daemon
        daemon_name = f"{protocol}d"
        planner.enqueue(node_name, 'router', f'killall -9 {daemon_name}', 
                       ignore_error=True, description=f"Stop {protocol.upper()} daemon")
        planner.enqueue(node_name, 'router', f'echo "{protocol.upper()} protocol disabled"', 
                       description=f"{protocol} disable confirmation")

def configure_rip_protocol(planner, node_name, config, config_path):
    """Configure RIP protocol with proper error handling"""
    version = config.get('version', '2')
    
    # Create config directory
    planner.enqueue(node_name, 'router', f'mkdir -p {config_path}', 
                   description="Create FRR config directory")
    
    # Generate RIP configuration
    rip_config = f"""!
! RIP configuration
!
hostname {node_name}
password zebra
enable password zebra
log stdout
!
router rip
 version {version}
 network 0.0.0.0/0
 redistribute connected
!
line vty
!
"""
    
    planner.enqueue(node_name, 'router', f'echo "{rip_config}" > {config_path}/ripd.conf', 
                   description="Create RIP configuration")
    
    # Enable RIP in daemons file
    planner.enqueue(node_name, 'router', create_frr_daemons_file(['rip']), 
                   description="Enable RIP in daemons config")
    
    # Start zebra first (required for RIP)
    planner.enqueue(node_name, 'router', 'killall -9 zebra ripd', 
                   ignore_error=True, description="Stop existing daemons")
    planner.enqueue(node_name, 'router', f'zebra -d -f {config_path}/zebra.conf', 
                   ignore_error=True, description="Start Zebra daemon")
    planner.enqueue(node_name, 'router', f'ripd -d -f {config_path}/ripd.conf', 
                   description="Start RIP daemon")
    
    # Verify daemon started
    planner.enqueue(node_name, 'router', 'sleep 2 && ps aux | grep ripd | grep -v grep', 
                   description="Verify RIP daemon is running")

def configure_ospf_protocol(planner, node_name, config, config_path):
    """Configure OSPF protocol with proper error handling"""
    area_id = config.get('area_id', '0')
    router_id = config.get('router_id', '')
    
    # Create config directory
    planner.enqueue(node_name, 'router', f'mkdir -p {config_path}', 
                   description="Create FRR config directory")
    
    # Generate OSPF configuration
    ospf_config = f"""!
! OSPF configuration
!
hostname {node_name}
password zebra
enable password zebra
log stdout
!
router ospf"""
    
    if router_id:
        ospf_config += f"\n router-id {router_id}"
    
    ospf_config += f"""
 network 0.0.0.0/0 area {area_id}
 redistribute connected
!
line vty
!
"""
    
    planner.enqueue(node_name, 'router', f'echo "{ospf_config}" > {config_path}/ospfd.conf', 
                   description="Create OSPF configuration")
    
    # Enable OSPF in daemons file
    planner.enqueue(node_name, 'router', create_frr_daemons_file(['ospf']), 
                   description="Enable OSPF in daemons config")
    
    # Start zebra first (required for OSPF)
    planner.enqueue(node_name, 'router', 'killall -9 zebra ospfd', 
                   ignore_error=True, description="Stop existing daemons")
    planner.enqueue(node_name, 'router', f'zebra -d -f {config_path}/zebra.conf', 
                   ignore_error=True, description="Start Zebra daemon")
    planner.enqueue(node_name, 'router', f'ospfd -d -f {config_path}/ospfd.conf', 
                   description="Start OSPF daemon")
    
    # Verify daemon started
    planner.enqueue(node_name, 'router', 'sleep 2 && ps aux | grep ospfd | grep -v grep', 
                   description="Verify OSPF daemon is running")

def configure_bgp_protocol(planner, node_name, config, config_path):
    """Configure BGP protocol with proper error handling"""
    as_number = config.get('as_number', '65001')
    router_id = config.get('router_id', '')
    
    # Create config directory
    planner.enqueue(node_name, 'router', f'mkdir -p {config_path}', 
                   description="Create FRR config directory")
    
    # Generate BGP configuration
    bgp_config = f"""!
! BGP configuration
!
hostname {node_name}
password zebra
enable password zebra
log stdout
!
router bgp {as_number}"""
    
    if router_id:
        bgp_config += f"\n bgp router-id {router_id}"
    
    bgp_config += f"""
 redistribute connected
!
line vty
!
"""
    
    planner.enqueue(node_name, 'router', f'echo "{bgp_config}" > {config_path}/bgpd.conf', 
                   description="Create BGP configuration")
    
    # Enable BGP in daemons file
    planner.enqueue(node_name, 'router', create_frr_daemons_file(['bgp']), 
                   description="Enable BGP in daemons config")
    
    # Start zebra first (required for BGP)
    planner.enqueue(node_name, 'router', 'killall -9 zebra bgpd', 
                   ignore_error=True, description="Stop existing daemons")
    planner.enqueue(node_name, 'router', f'zebra -d -f {config_path}/zebra.conf', 
                   ignore_error=True, description="Start Zebra daemon")
    planner.enqueue(node_name, 'router', f'bgpd -d -f {config_path}/bgpd.conf', 
                   description="Start BGP daemon")
    
    # Verify daemon started
    planner.enqueue(node_name, 'router', 'sleep 2 && ps aux | grep bgpd | grep -v grep', 
                   description="Verify BGP daemon is running")

# ======================= PROTOCOL STATUS CHECKING =======================

def get_routing_protocol_status(node):
    """Get detailed routing protocol status"""
    status = {
        'active_protocol': 'static',
        'running_daemons': [],
        'available_protocols': [],
        'environment': detect_routing_environment(node)
    }
    
    # Check running daemons
    try:
        processes = node.cmd('ps aux | grep -E "(ripd|ospfd|bgpd)" | grep -v grep')
        if processes.strip():
            for line in processes.strip().split('\n'):
                if 'ripd' in line:
                    status['running_daemons'].append('rip')
                    status['active_protocol'] = 'rip'
                elif 'ospfd' in line:
                    status['running_daemons'].append('ospf')
                    status['active_protocol'] = 'ospf'
                elif 'bgpd' in line:
                    status['running_daemons'].append('bgp')
                    status['active_protocol'] = 'bgp'
    except:
        pass
    
    # Determine available protocols based on environment
    env = status['environment']
    if env['recommendation'] == 'dynamic':
        for protocol in ['rip', 'ospf', 'bgp']:
            if env['daemons_available'].get(f'{protocol}d', False):
                status['available_protocols'].append(protocol)
    
    status['available_protocols'].insert(0, 'static')  # Static is always available
    
    return status

def process_routing_protocol(planner, node_name, node, protocol_config):
    """Enhanced routing protocol processing (replaces original)"""
    return enhanced_process_routing_protocol(planner, node_name, node, protocol_config)


# ======================= NODE-SPECIFIC CONFIGURATION PROCESSORS =======================

def process_router_configuration(planner, mininet_mgr, rtr_name, rtr_cfg):
    """Process complete router configuration"""
    logger.info(f"Processing router configuration for {rtr_name}")
    
    # Check if router exists
    if not node_exists(mininet_mgr, rtr_name):
        return {'node': rtr_name, 'where': 'router', 'error': 'Router not found'}

    # Get router node
    router_node, error = get_node_safely(mininet_mgr, rtr_name)
    if error:
        return {'node': rtr_name, 'where': 'router', 'error': error}

    # Process system settings (sysctl)
    sysctl_settings = rtr_cfg.get('sysctl', {})
    for key, value in sysctl_settings.items():
        planner.enqueue(rtr_name, 'router', f'sysctl -w {key}={value}', 
                       description=f"Set sysctl {key}={value}")

    # Process routing protocol configuration
    if 'routing_protocol' in rtr_cfg:
        process_routing_protocol(planner, rtr_name, router_node, rtr_cfg['routing_protocol'])

    # Process interface configuration
    if 'interfaces' in rtr_cfg:
        process_interface_configurations(planner, rtr_name, router_node, rtr_cfg['interfaces'])

    # Process static routes
    if 'static_routes' in rtr_cfg:
        process_route_configurations(planner, rtr_name, router_node, rtr_cfg['static_routes'])

    # Process NAT rules
    if 'nat_rules' in rtr_cfg:
        process_nat_configurations(planner, rtr_name, router_node, rtr_cfg['nat_rules'])

    # Process firewall rules
    if 'firewall_rules' in rtr_cfg:
        process_firewall_configurations(planner, rtr_name, router_node, rtr_cfg['firewall_rules'])

    # Process raw commands (for backward compatibility and custom operations)
    raw_commands = rtr_cfg.get('commands', [])
    for raw_cmd in raw_commands:
        planner.enqueue(rtr_name, 'router', raw_cmd, 
                       description=f"Raw command: {raw_cmd[:30]}...")

    return None  # No error

def process_host_configuration(planner, mininet_mgr, host_name, host_cfg):
    """Process complete host configuration"""
    logger.info(f"Processing host configuration for {host_name}")
    
    # Check if host exists
    if not node_exists(mininet_mgr, host_name):
        return {'node': host_name, 'where': 'host', 'error': 'Host not found'}

    # Get host node
    host_node, error = get_node_safely(mininet_mgr, host_name)
    if error:
        return {'node': host_name, 'where': 'host', 'error': error}

    # Process interface configuration
    if 'interfaces' in host_cfg:
        process_interface_configurations(planner, host_name, host_node, host_cfg['interfaces'])

    # Process routes
    if 'routes' in host_cfg:
        process_route_configurations(planner, host_name, host_node, host_cfg['routes'])

    # Process raw commands
    raw_commands = host_cfg.get('commands', [])
    for raw_cmd in raw_commands:
        planner.enqueue(host_name, 'host', raw_cmd, 
                       description=f"Raw command: {raw_cmd[:30]}...")

    return None  # No error

def process_switch_configuration(planner, mininet_mgr, sw_name, sw_cfg):
    """Process complete switch configuration"""
    logger.info(f"Processing switch configuration for {sw_name}")
    
    # Check if switch exists
    if not node_exists(mininet_mgr, sw_name):
        return {'node': sw_name, 'where': 'switch', 'error': 'Switch not found'}

    # Get switch node
    switch_node, error = get_node_safely(mininet_mgr, sw_name)
    if error:
        return {'node': sw_name, 'where': 'switch', 'error': error}

    # Process OVS configuration
    ovs_config = sw_cfg.get('ovs', {})
    
    if 'set-controller' in ovs_config and ovs_config['set-controller']:
        ctrl = ovs_config['set-controller']
        planner.enqueue(sw_name, 'switch', f'ovs-vsctl set-controller {sw_name} {ctrl}', 
                       description=f"Set controller to {ctrl}")

    if 'fail-mode' in ovs_config and ovs_config['fail-mode']:
        fm = ovs_config['fail-mode']
        planner.enqueue(sw_name, 'switch', f'ovs-vsctl set-fail-mode {sw_name} {fm}', 
                       description=f"Set fail-mode to {fm}")

    # Process other OVS configurations
    other_cfg = ovs_config.get('other_cfg', [])
    for cfg_cmd in other_cfg:
        planner.enqueue(sw_name, 'switch', cfg_cmd, 
                       description=f"OVS config: {cfg_cmd[:30]}...")

    # Process raw commands
    raw_commands = sw_cfg.get('commands', [])
    for raw_cmd in raw_commands:
        planner.enqueue(sw_name, 'switch', raw_cmd, 
                       description=f"Raw command: {raw_cmd[:30]}...")

    return None  # No error

# ======================= COMMAND EXECUTION FUNCTIONS =======================

def execute_command_plan(planner, mininet_mgr):
    """Execute all commands in the plan"""
    logger.info(f"Executing command plan with {len(planner.get_plan())} commands")
    
    for item in planner.get_plan():
        node_name = item['node']
        
        # Get the node
        node, error = get_node_safely(mininet_mgr, node_name)
        if error:
            planner.add_result({
                'node': node_name,
                'where': item['where'],
                'cmd': item['cmd'],
                'success': False,
                'error': error,
                'description': item.get('description', 'Unknown command')
            })
            continue

        # Execute the command
        try:
            logger.debug(f"Executing on {node_name}: {item['cmd']}")
            output = node.cmd(item['cmd'])
            
            # Enhanced error detection
            error_indicators = ['error:', 'invalid', 'not found', 'cannot', 'failed']
            warning_indicators = ['warning:', 'may not be available', 'daemon start attempted']
            
            failed = any(indicator in output.lower() for indicator in error_indicators)
            is_warning = any(indicator in output.lower() for indicator in warning_indicators)
            
            # Override failure if we're ignoring errors or if it's just a warning
            if (failed and item.get('ignore_error', False)) or (failed and is_warning):
                failed = False

            planner.add_result({
                'node': node_name,
                'where': item['where'],
                'cmd': item['cmd'],
                'success': not failed,
                'output': output.strip() if output else '',
                'ignored_error': item.get('ignore_error', False),
                'warning': is_warning,
                'description': item.get('description', 'Unknown command')
            })
            
        except Exception as e:
            if item.get('ignore_error', False):
                planner.add_result({
                    'node': node_name,
                    'where': item['where'],
                    'cmd': item['cmd'],
                    'success': True,
                    'output': '',
                    'ignored_error': True,
                    'note': f'Exception suppressed: {e}',
                    'description': item.get('description', 'Unknown command')
                })
            else:
                planner.add_result({
                    'node': node_name,
                    'where': item['where'],
                    'cmd': item['cmd'],
                    'success': False,
                    'error': str(e),
                    'description': item.get('description', 'Unknown command')
                })

def calculate_execution_summary(results):
    """Calculate execution summary statistics"""
    successful = len([r for r in results if r.get('success', False)])
    failed = len([r for r in results if not r.get('success', False)])
    warnings = len([r for r in results if r.get('warning', False)])
    ignored_errors = len([r for r in results if r.get('ignored_error', False)])
    
    return {
        'total': len(results),
        'successful': successful,
        'failed': failed,
        'warnings': warnings,
        'ignored_errors': ignored_errors
    }