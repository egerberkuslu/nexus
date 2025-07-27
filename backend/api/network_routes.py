"""
Network Management API Routes
Handles network creation, start, stop, and testing
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
network_bp = Blueprint('network', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']


@network_bp.route('/create', methods=['POST'])
@log_api_request
def create_network():
    """Create a new network topology with improved error handling"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        elif request.form:
            data = request.form.to_dict() or {}
        else:
            data = {}
            
        topology_type = data.get('type', 'simple')
        
        # Stop existing network first
        stop_result = mininet_mgr.stop_network()
        if not stop_result:
            logger.warning("Failed to cleanly stop existing network, continuing anyway")
        
        success = False
        error_message = None
        
        try:
            if topology_type == 'custom':
                # Handle custom topology from frontend builder
                topology_config = data.get('topology', {})
                if not topology_config:
                    return jsonify({
                        'success': False, 
                        'error': 'No topology configuration provided for custom topology'
                    }), 400
                
                success = mininet_mgr.create_custom_topology(topology_config)
                
            elif topology_type == 'predefined':
                # Handle predefined topology types
                predefined_config = data.get('topology', {})
                if not predefined_config:
                    return jsonify({
                        'success': False, 
                        'error': 'No topology configuration provided for predefined topology'
                    }), 400
                
                success = mininet_mgr.create_predefined_topology(predefined_config)
                
            else:
                # Default simple topology
                success = mininet_mgr.create_simple_topology()
                
        except Exception as create_error:
            error_message = str(create_error)
            logger.error(f"Topology creation failed: {create_error}")
            success = False
        
        if success:
            message = 'Network topology created successfully'
            status_code = 200
            
            # Try to update topology data
            try:
                mininet_mgr.update_topology_data()
                topology_summary = mininet_mgr.topology_data.get('stats', {})
            except Exception as e:
                logger.warning(f"Could not update topology data: {e}")
                topology_summary = {}
                
        else:
            message = f'Failed to create topology: {error_message or "Unknown error"}'
            status_code = 500
            topology_summary = {}
        
        response_data = {
            'success': success,
            'message': message,
            'topology_type': topology_type
        }
        
        # Add additional info for successful creation
        if success:
            if 'topology' in data:
                response_data['config'] = data['topology']
            response_data['topology_summary'] = topology_summary
        else:
            response_data['error'] = error_message
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"Error in create_network endpoint: {e}")
        return jsonify({
            'success': False, 
            'error': f'Internal server error: {str(e)}'
        }), 500


# Add these new routes to network_routes.py
@network_bp.route('/topologies', methods=['GET'])
@log_api_request
def get_available_topologies():
    """Get list of available predefined topologies"""
    try:
        topologies = [
            {
                'id': 'simple',
                'name': 'Simple Switch',
                'description': 'Single switch with multiple hosts',
                'parameters': [
                    {'name': 'hosts', 'type': 'number', 'default': 2, 'min': 1, 'max': 10}
                ]
            },
            {
                'id': 'linear',
                'name': 'Linear Topology',
                'description': 'Linear chain of switches with hosts',
                'parameters': [
                    {'name': 'hosts', 'type': 'number', 'default': 4, 'min': 2, 'max': 10}
                ]
            },
            {
                'id': 'tree',
                'name': 'Tree Topology',
                'description': 'Hierarchical tree structure',
                'parameters': [
                    {'name': 'depth', 'type': 'number', 'default': 3, 'min': 2, 'max': 4},
                    {'name': 'fanout', 'type': 'number', 'default': 2, 'min': 2, 'max': 4}
                ]
            },
            {
                'id': 'star',
                'name': 'Star Topology',
                'description': 'Central switch with multiple hosts',
                'parameters': [
                    {'name': 'hosts', 'type': 'number', 'default': 6, 'min': 3, 'max': 12}
                ]
            },
            {
                'id': 'mesh',
                'name': 'Mesh Topology',
                'description': 'Fully connected mesh of switches',
                'parameters': [
                    {'name': 'hosts', 'type': 'number', 'default': 4, 'min': 3, 'max': 6}
                ]
            },
            {
                'id': 'ring',
                'name': 'Ring Topology',
                'description': 'Switches connected in a ring',
                'parameters': [
                    {'name': 'hosts', 'type': 'number', 'default': 6, 'min': 3, 'max': 8}
                ]
            },
            {
                'id': 'fattree',
                'name': 'Fat Tree',
                'description': 'k-ary fat tree for data centers',
                'parameters': [
                    {'name': 'k', 'type': 'number', 'default': 4, 'min': 2, 'max': 8}
                ]
            },
            {
                'id': 'datacenter',
                'name': 'Datacenter',
                'description': 'Simple datacenter topology with ToR switches',
                'parameters': [
                    {'name': 'pods', 'type': 'number', 'default': 4, 'min': 2, 'max': 8},
                    {'name': 'hosts_per_pod', 'type': 'number', 'default': 2, 'min': 1, 'max': 4}
                ]
            }
        ]
        
        return jsonify({
            'topologies': topologies,
            'total': len(topologies)
        })
        
    except Exception as e:
        logger.error(f"Error getting available topologies: {e}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/validate', methods=['POST'])
@log_api_request
def validate_topology():
    """Validate topology configuration before creation"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        topology_type = data.get('type', 'simple')
        topology_config = data.get('topology', {})
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'estimated_resources': {}
        }
        
        # Validate based on topology type
        if topology_type == 'predefined':
            topo_type = topology_config.get('type', 'simple')
            
            if topo_type == 'simple':
                hosts = topology_config.get('hosts', 2)
                if hosts < 1 or hosts > 20:
                    validation_result['errors'].append('Number of hosts must be between 1 and 20')
                    validation_result['valid'] = False
                    
            elif topo_type == 'tree':
                depth = topology_config.get('depth', 3)
                fanout = topology_config.get('fanout', 2)
                if depth < 2 or depth > 5:
                    validation_result['errors'].append('Tree depth must be between 2 and 5')
                    validation_result['valid'] = False
                if fanout < 2 or fanout > 5:
                    validation_result['errors'].append('Tree fanout must be between 2 and 5')
                    validation_result['valid'] = False
                    
                # Estimate resource usage
                estimated_switches = sum(fanout**i for i in range(depth))
                estimated_hosts = fanout**(depth-1)
                if estimated_switches > 50:
                    validation_result['warnings'].append('Large number of switches may impact performance')
                    
            elif topo_type == 'fattree':
                k = topology_config.get('k', 4)
                if k < 2 or k > 8:
                    validation_result['errors'].append('Fat tree k parameter must be between 2 and 8')
                    validation_result['valid'] = False
                if k % 2 != 0:
                    validation_result['errors'].append('Fat tree k parameter must be even')
                    validation_result['valid'] = False
                    
                # Estimate resource usage for fat tree
                estimated_hosts = (k**3) // 4
                estimated_switches = (5 * k**2) // 4
                validation_result['estimated_resources'] = {
                    'hosts': estimated_hosts,
                    'switches': estimated_switches,
                    'links': estimated_hosts + (k**3) // 2
                }
        
        elif topology_type == 'custom':
            # Validate custom topology
            nodes = topology_config.get('nodes', [])
            links = topology_config.get('links', [])
            
            if len(nodes) == 0:
                validation_result['errors'].append('Custom topology must have at least one node')
                validation_result['valid'] = False
                
            # Check for duplicate node IDs
            node_ids = [node.get('id') for node in nodes]
            if len(node_ids) != len(set(node_ids)):
                validation_result['errors'].append('Duplicate node IDs found')
                validation_result['valid'] = False
                
            # Validate links reference existing nodes
            for link in links:
                source = link.get('source')
                target = link.get('target')
                if source not in node_ids:
                    validation_result['errors'].append(f'Link source "{source}" not found in nodes')
                    validation_result['valid'] = False
                if target not in node_ids:
                    validation_result['errors'].append(f'Link target "{target}" not found in nodes')
                    validation_result['valid'] = False
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating topology: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 500


@network_bp.route('/start', methods=['POST'])
@log_api_request
def start_network():
    """Start the network"""
    try:
        mininet_mgr = get_mininet_manager()
        success = mininet_mgr.start_network()
        
        message = 'Network started successfully' if success else 'Failed to start network'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success, 
            'message': message,
            'network_status': 'running' if success else 'stopped'
        }), status_code
        
    except Exception as e:
        logger.error(f"Error starting network: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@network_bp.route('/stop', methods=['POST'])
@log_api_request
def stop_network():
    """Stop the network"""
    try:
        mininet_mgr = get_mininet_manager()
        success = mininet_mgr.stop_network()
        
        message = 'Network stopped successfully' if success else 'Failed to stop network'
        
        return jsonify({
            'success': success, 
            'message': message,
            'network_status': 'stopped'
        })
        
    except Exception as e:
        logger.error(f"Error stopping network: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@network_bp.route('/restart', methods=['POST'])
@log_api_request
def restart_network():
    """Restart the network"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Stop the network
        stop_success = mininet_mgr.stop_network()
        if not stop_success:
            return jsonify({'success': False, 'error': 'Failed to stop network'}), 500
        
        # Wait a moment
        import time
        time.sleep(2)
        
        # Start the network
        start_success = mininet_mgr.start_network()
        
        message = 'Network restarted successfully' if start_success else 'Failed to restart network'
        status_code = 200 if start_success else 500
        
        return jsonify({
            'success': start_success, 
            'message': message,
            'network_status': 'running' if start_success else 'stopped'
        }), status_code
        
    except Exception as e:
        logger.error(f"Error restarting network: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@network_bp.route('/ping', methods=['POST'])
@log_api_request
def ping_test():
    """Run ping test between all hosts"""
    try:
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.ping_test()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error running ping test: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@network_bp.route('/ping/<source>/<target>', methods=['POST'])
@log_api_request
def ping_specific(source, target):
    """Run ping test between specific hosts"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running', 'success': False}), 400
        
        source_host = mininet_mgr.net.get(source)
        target_host = mininet_mgr.net.get(target)
        
        if not source_host:
            return jsonify({'error': f'Source host {source} not found', 'success': False}), 404
        
        if not target_host:
            return jsonify({'error': f'Target host {target} not found', 'success': False}), 404
        
        # Get number of pings from request
        data = request.get_json() or {}
        count = data.get('count', 4)
        
        # Run ping
        result = source_host.cmd(f'ping -c {count} {target_host.IP()}')
        
        # Parse result for packet loss
        import re
        packet_loss = re.search(r'(\d+)% packet loss', result)
        loss_percent = packet_loss.group(1) if packet_loss else '0'
        
        return jsonify({
            'result': result.strip(),
            'success': True,
            'source': source,
            'target': target,
            'packet_loss': loss_percent
        })
        
    except Exception as e:
        logger.error(f"Error running specific ping test: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@network_bp.route('/status', methods=['GET'])
@log_api_request
def get_network_status():
    """Get detailed network status"""
    try:
        mininet_mgr = get_mininet_manager()
        
        status = {
            'running': mininet_mgr.is_running,
            'network_exists': mininet_mgr.net is not None,
            'controller': mininet_mgr.get_controller_status(),
            'uptime': mininet_mgr.stats_collector.get_uptime() if mininet_mgr.is_running else '00:00:00'
        }
        
        if mininet_mgr.is_running and mininet_mgr.net:
            # Add topology summary
            mininet_mgr.update_topology_data()
            status['topology_summary'] = mininet_mgr.topology_data.get('stats', {})
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/hosts/<host_id>/cmd', methods=['POST'])
@log_api_request
def execute_command(host_id):
    """Execute command on a specific host"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net or not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        command = data.get('command', '')
        
        if not command:
            return jsonify({'error': 'No command provided'}), 400
        
        result = mininet_mgr.execute_host_command(host_id, command)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@network_bp.route('/flows', methods=['GET'])
@log_api_request
def get_flow_stats():
    """Get OpenFlow statistics from switches"""
    try:
        mininet_mgr = get_mininet_manager()
        flow_stats = mininet_mgr.get_flow_stats()
        
        return jsonify({
            'flows': flow_stats,
            'timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None
        })
        
    except Exception as e:
        logger.error(f"Error getting flow stats: {e}")
        return jsonify({'error': str(e)}), 500

@network_bp.route('/reset', methods=['POST'])
@log_api_request
def reset_network():
    """Reset network and clear all data"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Stop network
        mininet_mgr.stop_network()
        
        # Reset statistics
        mininet_mgr.stats_collector.reset_stats()
        
        # Clear topology data
        mininet_mgr.topology_data = {
            'nodes': [],
            'links': [],
            'controllers': [],
            'stats': {}
        }
        
        return jsonify({
            'success': True,
            'message': 'Network reset successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resetting network: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500