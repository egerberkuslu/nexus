"""
Controller Management API Routes
Full Ryu controller control via web API
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
controller_bp = Blueprint('controller', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@controller_bp.route('/status', methods=['GET'])
@log_api_request
def get_controller_status():
    """Get comprehensive Ryu controller status"""
    try:
        mininet_mgr = get_mininet_manager()
        status = mininet_mgr.get_controller_status()
        
        # Add additional status information
        if status['running']:
            controller_stats = mininet_mgr.ryu_controller.get_controller_stats()
            status.update(controller_stats)
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting controller status: {e}")
        return jsonify({'error': str(e)}), 500

@controller_bp.route('/start', methods=['POST'])
@log_api_request
def start_controller():
    """Start Ryu controller with specified configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        controller_type = data.get('type', 'simple_switch_13')
        port = int(data.get('port', 6633))
        
        # Map frontend names to Ryu app names
        app_mapping = {
            'simple_switch': 'simple_switch_13',
            'learning_switch': 'simple_switch_13',
            'l2_switch': 'simple_switch_13',
            'hub': 'hub',
            'rest_router': 'rest_router',
            'custom': data.get('custom_app', 'simple_switch_13')
        }
        
        ryu_app = app_mapping.get(controller_type, controller_type)
        
        logger.info(f"Starting controller: {ryu_app} on port {port}")
        success = mininet_mgr.ryu_controller.start_controller(ryu_app, port)
        
        message = f'Ryu controller started with {ryu_app}' if success else 'Failed to start controller'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success, 
            'message': message,
            'controller_type': ryu_app,
            'port': port,
            'status': mininet_mgr.get_controller_status()
        }), status_code
        
    except Exception as e:
        logger.error(f"Error starting controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/stop', methods=['POST'])
@log_api_request
def stop_controller():
    """Stop Ryu controller"""
    try:
        mininet_mgr = get_mininet_manager()
        success = mininet_mgr.stop_ryu_controller()
        
        message = 'Ryu controller stopped successfully' if success else 'Failed to stop controller'
        
        return jsonify({
            'success': success, 
            'message': message,
            'status': mininet_mgr.get_controller_status()
        })
        
    except Exception as e:
        logger.error(f"Error stopping controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/restart', methods=['POST'])
@log_api_request
def restart_controller():
    """Restart Ryu controller"""
    try:
        mininet_mgr = get_mininet_manager()
        success = mininet_mgr.restart_ryu_controller()
        
        message = 'Ryu controller restarted successfully' if success else 'Failed to restart controller'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success, 
            'message': message,
            'status': mininet_mgr.get_controller_status()
        }), status_code
        
    except Exception as e:
        logger.error(f"Error restarting controller: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/logs', methods=['GET'])
@log_api_request
def get_controller_logs():
    """Get controller logs"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Get number of lines from query parameter
        lines = request.args.get('lines', 100, type=int)
        
        logs = mininet_mgr.get_controller_logs()
        
        # If specific number of lines requested
        if lines and lines != 100:
            logs = mininet_mgr.ryu_controller.get_logs(lines)
        
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
        mininet_mgr.ryu_controller.logs.clear()
        
        return jsonify({
            'success': True,
            'message': 'Controller logs cleared'
        })
        
    except Exception as e:
        logger.error(f"Error clearing controller logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/apps', methods=['GET'])
@log_api_request
def get_available_apps():
    """Get list of available Ryu applications"""
    try:
        # Get the mininet manager - this was missing!
        mininet_mgr = get_mininet_manager()
        
        apps = [
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
            }
        ]
        
        return jsonify({
            'apps': apps,
            'current_app': mininet_mgr.ryu_controller.controller_type if mininet_mgr.ryu_controller.is_running else None
        })
        
    except Exception as e:
        logger.error(f"Error getting available apps: {e}")
        return jsonify({'error': str(e)}), 500
@controller_bp.route('/switch/<switch_id>', methods=['POST'])
@log_api_request
def switch_controller_app(switch_id):
    """Switch to a different controller application"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        new_app = data.get('app', 'simple_switch_13')
        
        # Stop current controller
        mininet_mgr.stop_ryu_controller()
        
        # Start with new app
        success = mininet_mgr.start_ryu_controller(new_app)
        
        message = f'Switched to {new_app}' if success else f'Failed to switch to {new_app}'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success,
            'message': message,
            'new_app': new_app,
            'status': mininet_mgr.get_controller_status()
        }), status_code
        
    except Exception as e:
        logger.error(f"Error switching controller app: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@controller_bp.route('/config', methods=['GET', 'POST'])
@log_api_request
def controller_config():
    """Get or update controller configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if request.method == 'GET':
            # Return current configuration
            config = {
                'type': mininet_mgr.ryu_controller.controller_type,
                'port': mininet_mgr.ryu_controller.controller_port,
                'python_executable': mininet_mgr.ryu_controller.python_exe,
                'running': mininet_mgr.ryu_controller.is_running
            }
            return jsonify(config)
        
        else:  # POST - Update configuration
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json() or {}
            else:
                data = request.form.to_dict() or {}
            
            # Update port if provided
            if 'port' in data:
                new_port = int(data['port'])
                mininet_mgr.ryu_controller.controller_port = new_port
            
            # Restart controller with new config if it was running
            if mininet_mgr.ryu_controller.is_running:
                success = mininet_mgr.restart_ryu_controller()
                message = 'Controller restarted with new configuration' if success else 'Failed to apply new configuration'
            else:
                success = True
                message = 'Configuration updated'
            
            return jsonify({
                'success': success,
                'message': message,
                'config': {
                    'type': mininet_mgr.ryu_controller.controller_type,
                    'port': mininet_mgr.ryu_controller.controller_port,
                    'running': mininet_mgr.ryu_controller.is_running
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
        
        controller_stats = mininet_mgr.ryu_controller.get_controller_stats()
        flow_stats = mininet_mgr.get_flow_stats()
        
        return jsonify({
            'controller': controller_stats,
            'flows': flow_stats,
            'timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None
        })
        
    except Exception as e:
        logger.error(f"Error getting controller stats: {e}")
        return jsonify({'error': str(e)}), 500