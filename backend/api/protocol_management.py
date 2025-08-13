"""
FRR Version-Compatible Protocol Management - Works with your FRR version
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import time

from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
protocol_mgmt_bp = Blueprint('protocol_management', __name__)

# Constants
FRR_BINARIES = {
    'zebra': '/usr/lib/frr/zebra',
    'ripd':  '/usr/lib/frr/ripd',
    'ospfd': '/usr/lib/frr/ospfd',
    'bgpd':  '/usr/lib/frr/bgpd',
}

VTY_PORT_MAP = {
    'zebra': '2601',
    'ripd':  '2602', 
    'ospfd': '2604',
    'bgpd':  '2605',
}

SUPPORTED_PROTOCOLS = ('zebra', 'rip', 'ospf', 'bgp')
DYNAMIC_PROTOCOLS = ('rip', 'ospf', 'bgp')

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    from flask import current_app
    return current_app.config['MININET_MANAGER']

def _base_dirs(device):
    """Returns dict with base, conf, run, log directories for the given Mininet node."""
    base = f"/tmp/frr/{device.name}"
    return {
        'base': base,
        'conf': f"{base}/conf",
        'run':  f"{base}/run",
        'log':  f"{base}/log",
        'zserv': f"{base}/run/zserv.api",
    }

def _user_exists(device, username):
    return device.cmd(f'id -u {username} >/dev/null 2>&1 && echo OK').strip() == 'OK'

def _runtime_user_group(device):
    """Return ('frr','frr') if frr user exists, else ('root','root')."""
    return ('frr', 'frr') if _user_exists(device, 'frr') else ('root', 'root')

def _ensure_dirs(device):
    """Create per-node directories with correct ownership/permissions."""
    d = _base_dirs(device)
    device.cmd(f"mkdir -p {d['conf']} {d['run']} {d['log']}")
    user, group = _runtime_user_group(device)
    device.cmd(f"chown -R {user}:{group} {d['base']} || true")
    device.cmd(f"chmod -R 775 {d['base']} || true")
    return d

def _check_host_frr_binaries(device):
    """Verify that FRR binaries exist on the host filesystem."""
    missing = []
    for name, path in FRR_BINARIES.items():
        out = device.cmd(f'test -x {path} || echo MISSING')
        if out.strip() == 'MISSING':
            missing.append(f"{name}:{path}")
    return (len(missing) == 0, missing)

def _daemon_bin_and_name(protocol):
    """Maps user protocol keys to (daemon_name, daemon_path)."""
    mapping = {
        'rip': ('ripd', FRR_BINARIES['ripd']),
        'ospf': ('ospfd', FRR_BINARIES['ospfd']),
        'bgp': ('bgpd', FRR_BINARIES['bgpd']),
        'zebra': ('zebra', FRR_BINARIES['zebra'])
    }
    if protocol in mapping:
        return mapping[protocol]
    raise ValueError(f"Unsupported protocol: {protocol}")

def _pidfile_path(device, daemon_name):
    d = _base_dirs(device)
    return f"{d['run']}/{daemon_name}.pid"

def is_daemon_running(device, daemon_name):
    """Enhanced process detection."""
    # Method 1: Check pidfile + process
    pidfile = _pidfile_path(device, daemon_name)
    pid = device.cmd(f'cat {pidfile} 2>/dev/null').strip()
    
    if pid.isdigit():
        ps_check = device.cmd(f'ps -p {pid} -o comm= 2>/dev/null').strip()
        if daemon_name in ps_check:
            return True
        else:
            device.cmd(f'rm -f {pidfile} 2>/dev/null || true')
    
    # Method 2: Check by process name
    ps_output = device.cmd(f'pgrep -f "^{daemon_name}"').strip()
    if ps_output:
        # Update pidfile with found PID
        device.cmd(f'echo {ps_output.split()[0]} > {pidfile}')
        return True
    
    return False

def is_port_listening(device, port):
    """Check if a specific port is listening."""
    methods = [
        f'ss -tlpn | grep ":{port} "',
        f'netstat -tlnp 2>/dev/null | grep ":{port} "',
        f'lsof -i :{port} 2>/dev/null'
    ]
    
    for method in methods:
        result = device.cmd(method).strip()
        if result:
            return True
    return False

def get_running_dynamic_protocols(device):
    """Get list of currently running dynamic routing protocols."""
    running = []
    for proto in DYNAMIC_PROTOCOLS:
        daemon_name, _ = _daemon_bin_and_name(proto)
        if is_daemon_running(device, daemon_name):
            running.append(proto)
    return running

def force_stop_daemon(device, daemon_name):
    """Forcefully stop a daemon using multiple methods."""
    logger.info(f"Force stopping {daemon_name} on {device.name}")
    
    # Method 1: Use pidfile
    pidfile = _pidfile_path(device, daemon_name)
    pid = device.cmd(f'cat {pidfile} 2>/dev/null').strip()
    if pid.isdigit():
        device.cmd(f'kill {pid} 2>/dev/null || true')
        time.sleep(1)
        ps_check = device.cmd(f'ps -p {pid} 2>/dev/null').strip()
        if ps_check:
            device.cmd(f'kill -9 {pid} 2>/dev/null || true')
            time.sleep(0.5)
    
    # Method 2: Kill by process name
    device.cmd(f'pkill -f "^{daemon_name}" 2>/dev/null || true')
    time.sleep(0.5)
    
    # Method 3: Kill by port
    expected_port = VTY_PORT_MAP.get(daemon_name)
    if expected_port:
        port_pids = device.cmd(f"ss -tlpn | grep ':{expected_port} ' | grep -o 'pid=[0-9]*' | cut -d= -f2").strip()
        if port_pids:
            for pid in port_pids.split('\n'):
                if pid.isdigit():
                    device.cmd(f'kill -9 {pid} 2>/dev/null || true')
    
    # Clean up files
    device.cmd(f'rm -f {pidfile} 2>/dev/null || true')
    
    time.sleep(1)
    return not is_daemon_running(device, daemon_name)

def stop_conflicting_protocols(device, target_protocol):
    """Stop all dynamic protocols except the target protocol."""
    if target_protocol == 'static':
        protocols_to_stop = list(DYNAMIC_PROTOCOLS)
    else:
        protocols_to_stop = [p for p in DYNAMIC_PROTOCOLS if p != target_protocol]
    
    results = []
    for proto in protocols_to_stop:
        daemon_name, _ = _daemon_bin_and_name(proto)
        if is_daemon_running(device, daemon_name):
            success = force_stop_daemon(device, daemon_name)
            results.append({
                'protocol': proto,
                'daemon': daemon_name,
                'stopped': success,
                'message': f"{'Successfully stopped' if success else 'Failed to stop'} {daemon_name}"
            })
    
    return results

def get_daemon_command_template(daemon_name):
    """Get the correct command template for each daemon based on actual capabilities."""
    # Based on your FRR version's help output, different daemons support different args
    
    common_args = [
        '-d',  # daemon mode
        '-i {pidfile}',  # pid file
        '-u {run_user}',  # user
        '-g {run_group}',  # group
        '-A {vty_addr}',  # VTY address
        '-P {vty_port}',  # VTY port
        '--log file:{log_file}'  # log file
    ]
    
    if daemon_name == 'zebra':
        # Zebra might support more options
        return common_args
    elif daemon_name in ['ripd', 'ospfd']:
        # RIP and OSPF need zebra socket
        return common_args + ['-z {zserv_socket}']
    elif daemon_name == 'bgpd':
        # BGP might support config file (as it worked before)
        return [
            '-d',
            '--config_file={conf_path}',  # BGP supports this
            '-i {pidfile}',
            '-A {vty_addr}',
            '-P {vty_port}',
            '-u {run_user}',
            '-g {run_group}',
            '--log file:{log_file}',
            '-z {zserv_socket}'
        ]
    else:
        return common_args

def start_daemon(device, protocol):
    """Start daemon with version-specific command arguments."""
    if protocol not in SUPPORTED_PROTOCOLS:
        return {'success': False, 'message': f"Unsupported protocol '{protocol}'"}

    daemon_name, binpath = _daemon_bin_and_name(protocol)
    
    # Check if already running
    if is_daemon_running(device, daemon_name):
        return {'success': True, 'message': f"{daemon_name} already running"}

    # Check for conflicts with OTHER dynamic protocols
    if protocol in DYNAMIC_PROTOCOLS:
        running_dynamic = get_running_dynamic_protocols(device)
        conflicting_protocols = [p for p in running_dynamic if p != protocol]
        
        if conflicting_protocols:
            logger.info(f"Stopping conflicting protocols on {device.name}: {conflicting_protocols}")
            conflict_results = stop_conflicting_protocols(device, protocol)
            time.sleep(3)
            
            still_running = [p for p in get_running_dynamic_protocols(device) if p != protocol]
            if still_running:
                return {
                    'success': False, 
                    'message': f"Cannot start {protocol}: conflicting protocols still running: {still_running}",
                    'conflict_resolution': conflict_results
                }

    # Ensure environment
    d = _ensure_dirs(device)
    ok, missing = _check_host_frr_binaries(device)
    if not ok:
        return {'success': False, 'message': f"Host FRR binaries missing: {', '.join(missing)}"}

    # Start zebra first if needed
    if protocol != 'zebra' and not is_daemon_running(device, 'zebra'):
        res_z = start_daemon(device, 'zebra')
        if not res_z.get('success'):
            return {'success': False, 'message': f"Failed to start zebra first: {res_z.get('message')}"}

    # Create configuration files in per-node directory
    conf_path = f"{d['conf']}/{daemon_name}.conf"
    
    if daemon_name == 'zebra':
        config_content = f"""!
hostname {device.name}
log file {d["log"]}/zebra.log
!
line vty
!
"""
    elif daemon_name == 'ripd':
        config_content = f"""!
hostname {device.name}-rip
log file {d["log"]}/ripd.log
!
router rip
 version 2
 network 0.0.0.0/0
!
line vty
!
"""
    elif daemon_name == 'ospfd':
        config_content = f"""!
hostname {device.name}-ospf
log file {d["log"]}/ospfd.log
!
router ospf
 network 0.0.0.0/0 area 0
!
line vty
!
"""
    elif daemon_name == 'bgpd':
        config_content = f"""!
hostname {device.name}-bgp
log file {d["log"]}/bgpd.log
!
router bgp 65001
!
line vty
!
"""

    # Write config file
    device.cmd(f'cat > {conf_path} << "EOF"\n{config_content}EOF')

    # Also create a symlink to standard FRR location for daemons that expect it there
    frr_conf_dir = '/etc/frr'
    device.cmd(f'mkdir -p {frr_conf_dir}')
    device.cmd(f'ln -sf {conf_path} {frr_conf_dir}/{daemon_name}.conf 2>/dev/null || true')

    pidfile = _pidfile_path(device, daemon_name)
    device.cmd(f'rm -f {pidfile} 2>/dev/null || true')

    run_user, run_group = _runtime_user_group(device)
    device.cmd(f"chown -R {run_user}:{run_group} {d['base']} || true")

    # Build command based on daemon capabilities
    vty_port = VTY_PORT_MAP.get(daemon_name, '2601')
    vty_addr = '127.0.0.1'
    log_file = f"{d['log']}/{daemon_name}.log"
    zserv_socket = d['zserv']
    
    # Get daemon-specific command template
    cmd_template = get_daemon_command_template(daemon_name)
    
    # Format the command
    cmd_args = []
    for arg in cmd_template:
        formatted_arg = arg.format(
            pidfile=pidfile,
            run_user=run_user,
            run_group=run_group,
            vty_addr=vty_addr,
            vty_port=vty_port,
            log_file=log_file,
            zserv_socket=zserv_socket,
            conf_path=conf_path
        )
        cmd_args.append(formatted_arg)
    
    cmd = f"{binpath} {' '.join(cmd_args)} > {d['log']}/{daemon_name}_startup.log 2>&1"
    
    logger.info(f"Starting {daemon_name} with command: {cmd}")
    device.cmd(cmd)
    time.sleep(2)
    
    if is_daemon_running(device, daemon_name):
        logger.info(f"Successfully started {daemon_name}")
        return {
            'success': True, 
            'message': f"Started {daemon_name}",
            'command_used': cmd
        }
    else:
        startup_log = device.cmd(f'cat {d["log"]}/{daemon_name}_startup.log 2>/dev/null || echo "No startup log"')
        logger.error(f"Failed to start {daemon_name}")
        return {
            'success': False, 
            'message': f"Failed to start {daemon_name}",
            'startup_log': startup_log,
            'command_used': cmd
        }

def stop_daemon(device, protocol):
    """Stop daemon."""
    if protocol not in SUPPORTED_PROTOCOLS:
        return {'success': False, 'message': f"Unsupported protocol '{protocol}'"}
    
    daemon_name, _ = _daemon_bin_and_name(protocol)
    
    if not is_daemon_running(device, daemon_name):
        return {'success': True, 'message': f"{daemon_name} was not running"}
    
    success = force_stop_daemon(device, daemon_name)
    return {
        'success': success,
        'message': f"{'Successfully stopped' if success else 'Failed to stop'} {daemon_name}"
    }

def get_current_protocol_status(device):
    """Get current protocol status."""
    status = {
        'active_protocols': [],
        'running_processes': {},
        'listening_ports': {},
        'configuration_files': {},
        'routing_table_size': 0,
        'primary_protocol': 'static',
        'conflicts_detected': False,
        'conflict_details': {}
    }
    
    try:
        # Check running processes
        for protocol in SUPPORTED_PROTOCOLS:
            if protocol == 'zebra':
                daemon_name = 'zebra'
            else:
                daemon_name, _ = _daemon_bin_and_name(protocol)
            status['running_processes'][daemon_name] = is_daemon_running(device, daemon_name)

        # Check listening ports
        for daemon, port in VTY_PORT_MAP.items():
            if is_port_listening(device, port):
                status['listening_ports'][daemon] = port

        # Check config files
        d = _base_dirs(device)
        for name in ['zebra', 'ripd', 'ospfd', 'bgpd']:
            conf = f"{d['conf']}/{name}.conf"
            lines = device.cmd(f'test -f {conf} && wc -l < {conf} || echo 0').strip()
            if lines.isdigit() and int(lines) > 0:
                status['configuration_files'][f'{name}.conf'] = {'path': conf, 'lines': int(lines)}

        # Get routing table size
        rc = device.cmd('ip route show | wc -l').strip()
        status['routing_table_size'] = int(rc) if rc.isdigit() else 0

        # Determine active protocols
        if status['running_processes'].get('bgpd'):
            status['active_protocols'].append('bgp')
        if status['running_processes'].get('ospfd'):
            status['active_protocols'].append('ospf')
        if status['running_processes'].get('ripd'):
            status['active_protocols'].append('rip')

        # Conflict detection
        dynamic_running = [p for p in status['active_protocols'] if p in DYNAMIC_PROTOCOLS]
        if len(dynamic_running) > 1:
            status['conflicts_detected'] = True
            status['conflict_details'] = {
                'conflicting_protocols': dynamic_running,
                'recommendation': 'Stop all but one dynamic routing protocol',
                'primary_suggestion': dynamic_running[0]
            }

        status['primary_protocol'] = status['active_protocols'][0] if status['active_protocols'] else 'static'

    except Exception as e:
        status['error'] = str(e)
        logger.error(f"Error getting protocol status: {e}")
    
    return status

# API Endpoints

@protocol_mgmt_bp.route('/devices/<device_id>/routing-protocols/resolve-conflicts', methods=['POST'])
@log_api_request
def resolve_protocol_conflicts(device_id):
    """Resolve protocol conflicts."""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            device = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Device {device_id} not found'}), 404

        data = request.get_json() or {}
        keep_protocol = data.get('keep_protocol', 'static')

        # Get current status
        current_status = get_current_protocol_status(device)
        
        # For static routing, stop ALL dynamic protocols
        if keep_protocol == 'static':
            running_dynamic = get_running_dynamic_protocols(device)
            if not running_dynamic:
                return jsonify({
                    'success': True,
                    'message': 'Already in static routing mode',
                    'conflicts_resolved': [],
                    'active_protocols': []
                })
            
            # Stop all dynamic protocols
            conflict_results = stop_conflicting_protocols(device, 'static')
            time.sleep(3)
            
            # Verify all stopped
            updated_status = get_current_protocol_status(device)
            
            return jsonify({
                'success': len(updated_status.get('active_protocols', [])) == 0,
                'message': 'Switched to static routing',
                'conflicts_resolved': conflict_results,
                'remaining_conflicts': False,
                'active_protocols': updated_status.get('active_protocols', [])
            })
        
        # For dynamic protocols, use existing logic
        if not current_status.get('conflicts_detected'):
            return jsonify({
                'success': True,
                'message': 'No conflicts detected',
                'conflicts_resolved': [],
                'active_protocols': current_status.get('active_protocols', [])
            })

        conflict_results = stop_conflicting_protocols(device, keep_protocol)
        time.sleep(3)
        updated_status = get_current_protocol_status(device)
        
        return jsonify({
            'success': not updated_status.get('conflicts_detected', False),
            'message': 'Conflict resolution completed',
            'conflicts_resolved': conflict_results,
            'remaining_conflicts': updated_status.get('conflicts_detected', False),
            'active_protocols': updated_status.get('active_protocols', [])
        })

    except Exception as e:
        logger.error(f"Error resolving conflicts on {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@protocol_mgmt_bp.route('/devices/<device_id>/routing-protocols/<proto>/start', methods=['POST'])
@log_api_request
def start_protocol(device_id, proto):
    """Start protocol."""
    try:
        proto = proto.lower()
        if proto not in SUPPORTED_PROTOCOLS:
            return jsonify({'error': f"Unsupported protocol '{proto}'"}), 400

        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            device = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Device {device_id} not found'}), 404

        perform_routing_software_installation(device)
        res = start_daemon(device, proto)
        
        return jsonify({'success': res.get('success', False), 'result': res})
    except Exception as e:
        logger.error(f"Error starting {proto} on {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@protocol_mgmt_bp.route('/devices/<device_id>/routing-protocols/<proto>/stop', methods=['POST'])
@log_api_request
def stop_protocol(device_id, proto):
    """Stop protocol."""
    try:
        proto = proto.lower()
        if proto not in SUPPORTED_PROTOCOLS:
            return jsonify({'error': f"Unsupported protocol '{proto}'"}), 400

        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            device = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Device {device_id} not found'}), 404

        res = stop_daemon(device, proto)
        return jsonify({'success': res.get('success', False), 'result': res})
    except Exception as e:
        logger.error(f"Error stopping {proto} on {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

@protocol_mgmt_bp.route('/devices/<device_id>/routing-protocols', methods=['GET'])
@log_api_request
def get_protocol_capabilities(device_id):
    """Get protocol capabilities."""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400

        try:
            device = mininet_mgr.net.get(device_id)
        except Exception:
            return jsonify({'error': f'Device {device_id} not found'}), 404

        capabilities = check_routing_environment(device)
        current_status = get_current_protocol_status(device)
        recommendations = generate_protocol_recommendations(capabilities, current_status)

        result = {
            'device_id': device_id,
            'capabilities': capabilities,
            'current_status': current_status,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"Error getting protocol capabilities for {device_id}: {e}")
        return jsonify({'error': str(e)}), 500

# Helper functions (unchanged)
def check_routing_environment(device):
    """Check routing environment."""
    environment = {
        'frr_available': False,
        'quagga_available': False,
        'daemons_available': {},
        'config_paths': {},
        'system_info': {},
        'permissions': {},
        'recommendation': 'basic',
        'installation_method': 'host_installed'
    }

    try:
        d = _ensure_dirs(device)
        ok, missing = _check_host_frr_binaries(device)
        environment['frr_available'] = ok
        environment['config_paths'] = {
            'per_node_base': d['base'],
            'conf': d['conf'],
            'run': d['run'],
            'log': d['log'],
            'zserv': d['zserv']
        }

        def _path_perms(device, path):
            owner = device.cmd(f'stat -c %U {path} 2>/dev/null').strip()
            group = device.cmd(f'stat -c %G {path} 2>/dev/null').strip()
            writable = device.cmd(f'[ -w {path} ] && echo YES || echo NO').strip() == 'YES'
            return {'owner': owner or 'unknown', 'group': group or 'unknown', 'writable': writable}

        environment['permissions'] = {
            'conf': _path_perms(device, d['conf']),
            'run':  _path_perms(device, d['run']),
            'log':  _path_perms(device, d['log']),
        }

        for daemon in ('zebra', 'ripd', 'ospfd', 'bgpd'):
            path = FRR_BINARIES.get(daemon)
            environment['daemons_available'][daemon] = bool(path and device.cmd(f'test -x {path} && echo OK').strip() == 'OK')

        environment['system_info'] = {
            'kernel': device.cmd('uname -r').strip(),
            'architecture': device.cmd('uname -m').strip(),
            'available_space': device.cmd("df -h / | tail -1 | awk '{print $4}'").strip()
        }

        avail = sum(1 for v in environment['daemons_available'].values() if v)
        environment['recommendation'] = 'frr' if environment['frr_available'] and avail >= 3 else ('limited' if avail >= 1 else 'basic')
    except Exception as e:
        environment['error'] = str(e)

    return environment

def generate_protocol_recommendations(capabilities, current_status):
    """Generate recommendations."""
    recommendations = []

    if current_status.get('conflicts_detected'):
        conflict_details = current_status.get('conflict_details', {})
        recommendations.append({
            'type': 'conflict',
            'priority': 'high',
            'message': f"Multiple dynamic routing protocols are active: {', '.join(conflict_details.get('conflicting_protocols', []))}. This can cause routing instability.",
            'action': 'resolve_protocol_conflicts',
            'suggested_resolution': f"Keep {conflict_details.get('primary_suggestion', 'one')} and stop others"
        })

    return recommendations

def perform_routing_software_installation(device):
    """Prepare per-node FRR environment."""
    results = {
        'success': False,
        'log': [],
        'errors': [],
        'strategy_used': 'host_installed'
    }
    try:
        d = _ensure_dirs(device)
        results['log'].append(f"Ensured per-node dirs at {d['base']}")

        ok, missing = _check_host_frr_binaries(device)
        if not ok:
            msg = f"Host FRR binaries missing: {', '.join(missing)}"
            results['errors'].append(msg)
            results['log'].append(msg)
            return results

        run_user, run_group = _runtime_user_group(device)
        device.cmd(f"chown -R {run_user}:{run_group} {d['base']} || true")
        device.cmd(f"chmod -R 775 {d['base']} || true")

        results['log'].append("Prepared per-node environment")
        results['success'] = True
        return results
    except Exception as e:
        results['errors'].append(f'Preparation exception: {str(e)}')
        return results