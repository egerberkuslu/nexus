"""
Controller Management API Routes
Full SDN controller control via web API
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request
import subprocess
import os

logger = setup_logger(__name__)
controller_bp = Blueprint('controller', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@controller_bp.route('/status', methods=['GET', 'POST'])
@log_api_request
def get_controller_status():
    """Get comprehensive controller status"""
    try:
        mininet_mgr = get_mininet_manager()
        status = mininet_mgr.get_controller_status()

        # Add additional status information from active controller
        active_controller = mininet_mgr.controller_factory.get_active_controller()
        if active_controller and status['running']:
            controller_stats = mininet_mgr.controller_factory.get_controller_stats(active_controller)
            status.update(controller_stats)

        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting controller status: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/types', methods=['GET', 'POST'])
@log_api_request
def get_available_controller_types():
    """Get available controller types and their configurations"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Get available controller types from factory
        available_types = mininet_mgr.controller_factory.get_available_controllers()
        controller_info = mininet_mgr.controller_factory.get_controller_info()
        
        # Build detailed information about each controller type
        types_info = {}
        for controller_type in available_types:
            capabilities = mininet_mgr.controller_factory.get_controller_capabilities(controller_type)
            info = controller_info.get(controller_type, {})
            
            types_info[controller_type] = {
                'name': capabilities.get('name', controller_type.title()),
                'running': info.get('running', False),
                'port': capabilities.get('default_port', 6633),
                'supported_apps': capabilities.get('supported_apps', []),
                'supports_installation': capabilities.get('supports_installation', False),
                'supports_custom_apps': capabilities.get('supports_custom_apps', False),
                'current_app': info.get('current_app'),
                'status': info.get('status', {})
            }
        
        return jsonify({
            'success': True,
            'types': available_types,
            'types_info': types_info,
            'active_controller': mininet_mgr.controller_factory.get_active_controller()
        })

    except Exception as e:
        logger.error(f"Error getting controller types: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/start', methods=['POST'])
@log_api_request
def start_controller():
    """Start controller with specified configuration"""
    try:
        mininet_mgr = get_mininet_manager()

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}

        controller_framework = data.get('framework', 'ryu')  # ryu, pox, osken, opendaylight
        controller_app = data.get('app', 'simple_switch_13')
        port = int(data.get('port', 6633))

        # Map frontend names to controller-specific app names
        app_mapping = {
            'ryu': {
                'simple_switch': 'simple_switch_13',
                'learning_switch': 'simple_switch_13',
                'l2_switch': 'simple_switch_13',
                'hub': 'hub',
                'rest_router': 'rest_router',
                'custom': data.get('custom_app', 'simple_switch_13')
            },
            'pox': {
                'simple_switch': 'l2_learning',
                'learning_switch': 'l2_learning',
                'l2_switch': 'l2_learning',
                'hub': 'hub',
                'custom': data.get('custom_app', 'l2_learning')
            },
            'osken': {
                'simple_switch': 'simple_switch_13',
                'learning_switch': 'simple_switch_13',
                'l2_switch': 'simple_switch_13',
                'hub': 'hub',
                'rest_router': 'rest_router',
                'custom': data.get('custom_app', 'simple_switch_13')
            },
            'opendaylight': {
                'simple_switch': 'l2switch',
                'learning_switch': 'l2switch',
                'l2_switch': 'l2switch',
                'custom': data.get('custom_app', 'l2switch')
            }
        }

        # Get the appropriate app name for the controller framework
        framework_apps = app_mapping.get(controller_framework, app_mapping['ryu'])
        final_app = framework_apps.get(controller_app, controller_app)

        logger.info(f"Starting {controller_framework} controller: {final_app} on port {port}")
        success = mininet_mgr.start_controller(controller_framework, final_app, port)

        message = f'{controller_framework.upper()} controller started with {final_app}' if success else f'Failed to start {controller_framework} controller'
        status_code = 200 if success else 500

        return jsonify({
            'success': success,
            'message': message,
            'controller_framework': controller_framework,
            'controller_app': final_app,
            'port': port,
            'status': mininet_mgr.get_controller_status()
        }), status_code

    except Exception as e:
        logger.error(f"Error starting controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/stop', methods=['POST'])
@log_api_request
def stop_controller():
    """Stop controller"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
        
        # Get controller type to stop (if specified)
        controller_type = data.get('controller_type')
        
        if controller_type:
            # Stop specific controller type
            success = mininet_mgr.controller_factory.stop_controller(controller_type)
            controller_name = controller_type
        else:
            # Stop active controller
            success = mininet_mgr.stop_controller()
            active_controller = mininet_mgr.controller_factory.get_active_controller()
            controller_name = active_controller or 'controller'

        message = f'{controller_name.upper()} controller stopped successfully' if success else f'Failed to stop {controller_name} controller'

        return jsonify({
            'success': success,
            'message': message,
            'stopped_controller': controller_name,
            'status': mininet_mgr.get_controller_status()
        })

    except Exception as e:
        logger.error(f"Error stopping controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/restart', methods=['POST'])
@log_api_request
def restart_controller():
    """Restart controller"""
    try:
        mininet_mgr = get_mininet_manager()

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}

        # Get current controller info
        active_controller = mininet_mgr.controller_factory.get_active_controller()
        if not active_controller:
            return jsonify({
                'success': False,
                'error': 'No active controller to restart'
            }), 400

        # Get current controller config
        controller_info = mininet_mgr.controller_factory.get_controller_info().get(active_controller, {})
        current_app = controller_info.get('current_app', 'simple_switch_13')
        current_port = controller_info.get('port', 6633)

        # Override with provided parameters
        new_app = data.get('app', current_app)
        new_port = int(data.get('port', current_port))

        success = mininet_mgr.restart_controller(active_controller, new_app, new_port)

        message = f'{active_controller.upper()} controller restarted successfully' if success else f'Failed to restart {active_controller} controller'
        status_code = 200 if success else 500

        return jsonify({
            'success': success,
            'message': message,
            'restarted_controller': active_controller,
            'new_app': new_app,
            'new_port': new_port,
            'status': mininet_mgr.get_controller_status()
        }), status_code

    except Exception as e:
        logger.error(f"Error restarting controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/logs', methods=['GET', 'POST'])
@log_api_request
def get_controller_logs():
    """Get controller logs"""
    try:
        mininet_mgr = get_mininet_manager()

        # Handle both JSON and query parameters
        if request.is_json:
            data = request.get_json() or {}
            lines = data.get('lines', 100)
            controller_type = data.get('controller_type')
        else:
            lines = request.args.get('lines', 100, type=int)
            controller_type = request.args.get('controller_type')

        # Get active controller or use specified controller type
        if controller_type:
            active_controller = controller_type
        else:
            active_controller = mininet_mgr.controller_factory.get_active_controller()
            
        if not active_controller:
            return jsonify({
                'logs': [],
                'error': 'No active controller'
            }), 400

        # Get logs from controller factory
        logs = mininet_mgr.controller_factory.get_controller_logs(active_controller, lines)

        return jsonify(logs)

    except Exception as e:
        logger.error(f"Error getting controller logs: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/logs/clear', methods=['POST'])
@log_api_request
def clear_controller_logs():
    """Clear controller logs"""
    try:
        mininet_mgr = get_mininet_manager()

        # Get active controller
        active_controller = mininet_mgr.controller_factory.get_active_controller()
        if not active_controller:
            return jsonify({
                'success': False,
                'error': 'No active controller'
            }), 400

        # Clear logs through controller factory
        controller_instance = mininet_mgr.controller_factory.controllers.get(active_controller)
        if controller_instance and hasattr(controller_instance, 'logs'):
            controller_instance.logs.clear()

            return jsonify({
                'success': True,
                'message': f'{active_controller.upper()} controller logs cleared'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Controller does not support log clearing'
            }), 400

    except Exception as e:
        logger.error(f"Error clearing controller logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@controller_bp.route('/apps', methods=['GET', 'POST'])
@log_api_request
def get_available_apps():
    """Get list of available controller applications"""
    try:
        mininet_mgr = get_mininet_manager()

        # Handle both JSON and query parameters
        if request.is_json:
            data = request.get_json() or {}
            framework = data.get('framework')
        else:
            framework = request.args.get('framework')
            
        if not framework:
            framework = mininet_mgr.controller_factory.get_active_controller() or 'ryu'

        # Define applications for each controller framework
        framework_apps = {
            'ryu': [
                {
                    'id': 'simple_switch_13',
                    'name': 'Simple Switch (OpenFlow 1.3)',
                    'description': 'Basic L2 learning switch with OpenFlow 1.3',
                    'category': 'switching'
                },
                {
                    'id': 'hub',
                    'name': 'Hub',
                    'description': 'Simple hub that floods all packets',
                    'category': 'switching'
                },
                {
                    'id': 'rest_router',
                    'name': 'REST Router',
                    'description': 'L3 router with REST API',
                    'category': 'routing'
                },
                {
                    'id': 'simple_switch_lacp',
                    'name': 'LACP Switch',
                    'description': 'Switch with Link Aggregation Control Protocol',
                    'category': 'switching'
                },
                {
                    'id': 'rest_firewall',
                    'name': 'REST Firewall',
                    'description': 'Firewall with REST API',
                    'category': 'security'
                },
                {
                    'id': 'gui_topology',
                    'name': 'GUI Topology',
                    'description': 'Topology discovery with web GUI',
                    'category': 'topology'
                }
            ],
            'pox': [
                {
                    'id': 'l2_learning',
                    'name': 'L2 Learning',
                    'description': 'Basic L2 learning switch',
                    'category': 'switching'
                },
                {
                    'id': 'hub',
                    'name': 'Hub',
                    'description': 'Simple hub that floods all packets',
                    'category': 'switching'
                },
                {
                    'id': 'l3_learning',
                    'name': 'L3 Learning',
                    'description': 'Simple L3 router',
                    'category': 'routing'
                },
                {
                    'id': 'firewall',
                    'name': 'Firewall',
                    'description': 'Basic firewall functionality',
                    'category': 'security'
                }
            ],
            'osken': [
                {
                    'id': 'simple_switch_13',
                    'name': 'Simple Switch (OpenFlow 1.3)',
                    'description': 'Basic L2 learning switch with OpenFlow 1.3',
                    'category': 'switching'
                },
                {
                    'id': 'hub',
                    'name': 'Hub',
                    'description': 'Simple hub that floods all packets',
                    'category': 'switching'
                },
                {
                    'id': 'rest_router',
                    'name': 'REST Router',
                    'description': 'L3 router with REST API',
                    'category': 'routing'
                },
                {
                    'id': 'simple_switch_rest_13',
                    'name': 'REST Switch',
                    'description': 'Switch with REST API for flow management',
                    'category': 'switching'
                }
            ],
            'opendaylight': [
                {
                    'id': 'l2switch',
                    'name': 'L2 Switch',
                    'description': 'Basic L2 switching functionality',
                    'category': 'switching'
                },
                {
                    'id': 'l3vpn',
                    'name': 'L3 VPN',
                    'description': 'L3 VPN service',
                    'category': 'routing'
                },
                {
                    'id': 'odl-l3vpn',
                    'name': 'ODL L3 VPN',
                    'description': 'OpenDaylight L3 VPN implementation',
                    'category': 'routing'
                },
                {
                    'id': 'odl-netvirt-openstack',
                    'name': 'NetVirt OpenStack',
                    'description': 'OpenStack integration',
                    'category': 'integration'
                }
            ]
        }

        apps = framework_apps.get(framework, framework_apps['ryu'])

        # Get current app for the specified framework
        current_app = None
        if framework in mininet_mgr.controller_factory.controllers:
            controller_instance = mininet_mgr.controller_factory.controllers[framework]
            current_app = controller_instance.controller_type if controller_instance.is_running else None

        return jsonify({
            'apps': apps,
            'framework': framework,
            'current_app': current_app,
            'available_frameworks': list(framework_apps.keys())
        })

    except Exception as e:
        logger.error(f"Error getting available apps: {e}")
        return jsonify({'error': str(e)}), 500
@controller_bp.route('/switch/<controller_framework>', methods=['POST'])
@log_api_request
def switch_controller_app(controller_framework):
    """Switch to a different controller application"""
    try:
        mininet_mgr = get_mininet_manager()

        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}

        new_app = data.get('app', 'simple_switch_13')
        port = int(data.get('port', 6633))

        # Validate controller framework
        available_controllers = mininet_mgr.controller_factory.get_available_controllers()
        if controller_framework not in available_controllers:
            return jsonify({
                'success': False,
                'error': f'Unknown controller framework: {controller_framework}',
                'available_frameworks': available_controllers
            }), 400

        # Switch controller using factory
        success = mininet_mgr.controller_factory.start_controller(controller_framework, new_app, port)

        message = f'Switched to {controller_framework.upper()} with {new_app}' if success else f'Failed to switch to {controller_framework} with {new_app}'
        status_code = 200 if success else 500

        return jsonify({
            'success': success,
            'message': message,
            'controller_framework': controller_framework,
            'new_app': new_app,
            'port': port,
            'status': mininet_mgr.get_controller_status()
        }), status_code

    except Exception as e:
        logger.error(f"Error switching controller app: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/switch/type', methods=['POST'])
@log_api_request
def switch_controller_type():
    """Switch controller framework type (ryu, pox, osken, opendaylight)"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}
        
        new_type = data.get('type', 'ryu')
        new_app = data.get('app', 'default')
        port = data.get('port', 6633)
        
        logger.info(f"Switching controller type to {new_type} with app {new_app}")
        
        # Validate controller type
        available_types = mininet_mgr.controller_factory.get_available_controllers()
        if new_type not in available_types:
            return jsonify({
                'success': False,
                'error': f'Controller type {new_type} not available. Available types: {available_types}'
            }), 400
        
        # Use controller factory to switch controller type
        success = mininet_mgr.controller_factory.switch_controller(new_type, new_app, port)
        
        # If successful, update topology data to reflect the new controller
        if success:
            mininet_mgr.update_topology_data()
        
        message = f'Switched to {new_type} controller with {new_app}' if success else f'Failed to switch to {new_type} controller'
        status_code = 200 if success else 500
        
        # Get updated controller status
        controller_status = mininet_mgr.get_controller_status() if success else {}
        
        return jsonify({
            'success': success,
            'message': message,
            'controller_type': new_type,
            'app': new_app,
            'port': port,
            'status': controller_status
        }), status_code
        
    except Exception as e:
        logger.error(f"Error switching controller type: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/config', methods=['GET', 'POST'])
@log_api_request
def controller_config():
    """Get or update controller configuration"""
    try:
        mininet_mgr = get_mininet_manager()

        if request.method == 'GET':
            # Get controller framework from query parameter
            framework = request.args.get('framework')
            if not framework:
                framework = mininet_mgr.controller_factory.get_active_controller()

            if not framework or framework not in mininet_mgr.controller_factory.controllers:
                return jsonify({
                    'error': 'No active controller or invalid framework specified',
                    'available_frameworks': mininet_mgr.controller_factory.get_available_controllers()
                }), 400

            controller_instance = mininet_mgr.controller_factory.controllers[framework]

            # Return current configuration
            config = {
                'framework': framework,
                'type': controller_instance.controller_type,
                'port': controller_instance.controller_port,
                'python_executable': getattr(controller_instance, 'python_exe', 'system'),
                'running': controller_instance.is_running
            }
            return jsonify(config)

        else:  # POST - Update configuration
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json() or {}
            else:
                data = request.form.to_dict() or {}

            framework = data.get('framework')
            if not framework:
                framework = mininet_mgr.controller_factory.get_active_controller()

            if not framework or framework not in mininet_mgr.controller_factory.controllers:
                return jsonify({
                    'success': False,
                    'error': 'No active controller or invalid framework specified',
                    'available_frameworks': mininet_mgr.controller_factory.get_available_controllers()
                }), 400

            controller_instance = mininet_mgr.controller_factory.controllers[framework]

            # Update port if provided
            updated = False
            if 'port' in data:
                new_port = int(data['port'])
                controller_instance.controller_port = new_port
                mininet_mgr.controller_factory.port_assignments[framework] = new_port
                updated = True

            # Restart controller with new config if it was running
            if controller_instance.is_running:
                success = mininet_mgr.restart_controller(framework)
                message = f'{framework.upper()} controller restarted with new configuration' if success else f'Failed to apply new configuration to {framework}'
            else:
                success = True
                message = f'{framework.upper()} configuration updated'

            return jsonify({
                'success': success,
                'message': message,
                'config': {
                    'framework': framework,
                    'type': controller_instance.controller_type,
                    'port': controller_instance.controller_port,
                    'running': controller_instance.is_running
                }
            })

    except Exception as e:
        logger.error(f"Error with controller config: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/stats', methods=['GET'])
@log_api_request
def get_controller_stats():
    """Get detailed controller statistics"""
    try:
        mininet_mgr = get_mininet_manager()

        # Get controller framework from query parameter
        framework = request.args.get('framework')
        if not framework:
            framework = mininet_mgr.controller_factory.get_active_controller()

        if not framework:
            return jsonify({
                'error': 'No active controller',
                'available_frameworks': mininet_mgr.controller_factory.get_available_controllers()
            }), 400

        # Get controller stats from factory
        controller_stats = mininet_mgr.controller_factory.get_controller_stats(framework)
        flow_stats = mininet_mgr.get_flow_stats()

        return jsonify({
            'controller': controller_stats,
            'flows': flow_stats,
            'framework': framework,
            'timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None
        })

    except Exception as e:
        logger.error(f"Error getting controller stats: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/installations', methods=['GET'])
@log_api_request
def get_controller_installations():
    """Get installation status of all available SDN controllers"""
    try:
        installations = {}

        # Check Ryu/os-ken installation
        ryu_status = check_ryu_installation()
        installations['ryu'] = ryu_status

        # Check POX installation
        pox_status = check_pox_installation()
        installations['pox'] = pox_status

        # Check OpenDaylight installation
        odl_status = check_opendaylight_installation()
        installations['opendaylight'] = odl_status

        # Check os-ken installation
        osken_status = check_osken_installation()
        installations['osken'] = osken_status

        # Overall status
        all_installed = all(status['installed'] for status in installations.values())
        any_running = any(status.get('running', False) for status in installations.values())

        return jsonify({
            'controllers': installations,
            'summary': {
                'total_controllers': len(installations),
                'installed_count': sum(1 for status in installations.values() if status['installed']),
                'running_count': sum(1 for status in installations.values() if status.get('running', False)),
                'all_installed': all_installed,
                'any_running': any_running
            },
            'timestamp': str(current_app.config.get('START_TIME', 'unknown'))
        })

    except Exception as e:
        logger.error(f"Error checking controller installations: {e}")
        return jsonify({'error': str(e)}), 500

def check_ryu_installation():
    """Check Ryu controller installation status"""
    try:
        # Try system Python first
        result = subprocess.run([
            'python3', '-c',
            'import ryu; import ryu.cmd.manager; import ryu.app.simple_switch_13; print("OK")'
        ], capture_output=True, text=True, timeout=10)

        # If system Python fails, try conda environment
        if result.returncode != 0:
            conda_python = '/home/ege/anaconda3/envs/sdn-mininet/bin/python'
            if os.path.exists(conda_python):
                result = subprocess.run([
                    conda_python, '-c',
                    'import ryu; import ryu.cmd.manager; import ryu.app.simple_switch_13; print("OK")'
                ], capture_output=True, text=True, timeout=10)

            # Try general conda python
            if result.returncode != 0:
                conda_python = '/home/ege/anaconda3/bin/python3'
                if os.path.exists(conda_python):
                    result = subprocess.run([
                        conda_python, '-c',
                        'import ryu; import ryu.cmd.manager; import ryu.app.simple_switch_13; print("OK")'
                    ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            # Check if ryu-manager command is available
            ryu_manager_result = subprocess.run(['which', 'ryu-manager'],
                                              capture_output=True, text=True)

            # Try to get version
            try:
                if 'conda_python' in locals():
                    version_result = subprocess.run([
                        conda_python, '-c', 'import ryu; print(getattr(ryu, "__version__", "unknown"))'
                    ], capture_output=True, text=True, timeout=5)
                else:
                    version_result = subprocess.run([
                        'python3', '-c', 'import ryu; print(getattr(ryu, "__version__", "unknown"))'
                    ], capture_output=True, text=True, timeout=5)

                version = version_result.stdout.strip() if version_result.returncode == 0 else '4.34'
            except:
                version = '4.34'

            return {
                'installed': True,
                'version': version,
                'executable': ryu_manager_result.stdout.strip() if ryu_manager_result.returncode == 0 else None,
                'running': False,  # Would need to check actual running processes
                'status': 'ready',
                'environment': 'conda' if 'conda_python' in locals() and 'anaconda3' in conda_python else 'system'
            }
        else:
            return {
                'installed': False,
                'error': result.stderr.strip(),
                'status': 'not_installed'
            }
    except Exception as e:
        return {
            'installed': False,
            'error': str(e),
            'status': 'error'
        }

def check_pox_installation():
    """Check POX controller installation status"""
    try:
        pox_path = os.path.expanduser('~/pox')
        pox_py = os.path.join(pox_path, 'pox.py')

        if os.path.exists(pox_py):
            # Check if pox.py is executable
            if os.access(pox_py, os.X_OK):
                return {
                    'installed': True,
                    'path': pox_py,
                    'version': 'latest',  # POX doesn't have version info easily accessible
                    'running': False,
                    'status': 'ready'
                }
            else:
                return {
                    'installed': True,
                    'path': pox_py,
                    'status': 'not_executable',
                    'error': 'pox.py is not executable'
                }
        else:
            return {
                'installed': False,
                'status': 'not_found',
                'expected_path': pox_py
            }
    except Exception as e:
        return {
            'installed': False,
            'error': str(e),
            'status': 'error'
        }

def check_opendaylight_installation():
    """Check OpenDaylight controller installation status"""
    try:
        odl_path = os.path.expanduser('~/opendaylight')
        karaf_bin = os.path.join(odl_path, 'bin', 'karaf')

        if os.path.exists(karaf_bin):
            # Check if karaf is executable
            if os.access(karaf_bin, os.X_OK):
                return {
                    'installed': True,
                    'path': odl_path,
                    'karaf_path': karaf_bin,
                    'version': '0.18.1',  # Based on the download URL in check_controllers.py
                    'running': False,  # Would need to check running processes
                    'status': 'ready'
                }
            else:
                return {
                    'installed': True,
                    'path': odl_path,
                    'status': 'not_executable',
                    'error': 'karaf script is not executable'
                }
        else:
            return {
                'installed': False,
                'status': 'not_found',
                'expected_path': karaf_bin
            }
    except Exception as e:
        return {
            'installed': False,
            'error': str(e),
            'status': 'error'
        }

def check_osken_installation():
    """Check os-ken controller installation status"""
    try:
        # Try system Python first
        result = subprocess.run([
            'python3', '-c',
            'import os_ken; import os_ken.cmd.manager; print("OK")'
        ], capture_output=True, text=True, timeout=10)

        # If system Python fails, try conda environment
        if result.returncode != 0:
            conda_python = '/home/ege/anaconda3/envs/sdn-mininet/bin/python'
            if os.path.exists(conda_python):
                result = subprocess.run([
                    conda_python, '-c',
                    'import os_ken; import os_ken.cmd.manager; print("OK")'
                ], capture_output=True, text=True, timeout=10)

            # Try general conda python
            if result.returncode != 0:
                conda_python = '/home/ege/anaconda3/bin/python3'
                if os.path.exists(conda_python):
                    result = subprocess.run([
                        conda_python, '-c',
                        'import os_ken; import os_ken.cmd.manager; print("OK")'
                    ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            # Try to get version from conda environment
            conda_python = '/home/ege/anaconda3/envs/sdn-mininet/bin/python'
            if os.path.exists(conda_python):
                version_result = subprocess.run([
                    conda_python, '-c', 'import os_ken; print(getattr(os_ken, "__version__", "unknown"))'
                ], capture_output=True, text=True, timeout=5)
            else:
                conda_python = '/home/ege/anaconda3/bin/python3'
                version_result = subprocess.run([
                    conda_python, '-c', 'import os_ken; print(getattr(os_ken, "__version__", "unknown"))'
                ], capture_output=True, text=True, timeout=5)

            version = version_result.stdout.strip() if version_result.returncode == 0 else 'unknown'

            return {
                'installed': True,
                'version': version,
                'running': False,
                'status': 'ready',
                'note': 'os-ken is the official Ryu replacement',
                'environment': 'conda' if 'anaconda3' in conda_python else 'system'
            }
        else:
            return {
                'installed': False,
                'error': result.stderr.strip(),
                'status': 'not_installed'
            }
    except Exception as e:
        return {
            'installed': False,
            'error': str(e),
            'status': 'error'
        }

@controller_bp.route('/force_restart', methods=['POST'])
@log_api_request
def force_restart_controllers():
    """Force restart all controllers (useful for debugging)"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Force stop all controllers
        mininet_mgr.controller_factory.stop_all_controllers()
        
        # Wait a moment
        import time
        time.sleep(2)
        
        # Force reset all controller states
        mininet_mgr.controller_factory.reset_controller_states()
        
        # Get updated status
        status = mininet_mgr.get_controller_status()
        
        return jsonify({
            'success': True,
            'message': 'All controllers force restarted',
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error force restarting controllers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/install/check', methods=['GET', 'POST'])
@log_api_request
def check_controller_installation():
    """Check if a specific controller is properly installed"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and query parameters
        if request.is_json:
            data = request.get_json() or {}
            controller_type = data.get('controller_type')
        else:
            controller_type = request.args.get('controller_type')
            
        if not controller_type:
            return jsonify({
                'error': 'controller_type parameter is required',
                'available_types': mininet_mgr.controller_factory.get_available_controllers()
            }), 400
        
        # Check installation status
        installation_status = mininet_mgr.check_controller_installation(controller_type)
        
        return jsonify({
            'success': True,
            'controller_type': controller_type,
            'installed': installation_status,
            'message': f'{controller_type} is {"installed" if installation_status else "not installed"}'
        })
        
    except Exception as e:
        logger.error(f"Error checking controller installation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
