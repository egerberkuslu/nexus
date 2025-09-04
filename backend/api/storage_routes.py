"""
Storage API Routes
Handles saving and loading of topologies and configurations
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request
from database.services import get_topology_service, get_configuration_service

logger = setup_logger(__name__)
storage_bp = Blueprint('storage', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@storage_bp.route('/test', methods=['GET'])
def test_storage_api():
    """Test endpoint to verify storage API is working"""
    return jsonify({
        'success': True,
        'message': 'Storage API is working',
        'endpoints': {
            'POST /topologies': 'Save topology',
            'GET /topologies': 'List topologies',
            'GET /topologies/<id>': 'Get topology',
            'DELETE /topologies/<id>': 'Delete topology'
        }
    })

# =============================
# TOPOLOGY STORAGE ENDPOINTS
# =============================

@storage_bp.route('/topologies', methods=['POST'])
@log_api_request
def save_topology():
    """Save current topology to database"""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Topology name is required'}), 400
        
        # Get topology data - either from request or from running network
        topology_data = data.get('topology_data')
        
        if not topology_data:
            # If no topology_data provided, try to get from running network
            mininet_mgr = get_mininet_manager()
            if not mininet_mgr.is_running:
                return jsonify({'success': False, 'error': 'No topology data provided and no active topology running'}), 400
            
            # Update and get current topology data
            mininet_mgr.update_topology_data()
            topology_data = mininet_mgr.topology_data
        
        # Ensure controllers are properly extracted from nodes array to controllers array
        if topology_data:
            nodes = topology_data.get('nodes', [])
            existing_controllers = topology_data.get('controllers', [])
            
            # Extract controllers from nodes array
            controller_nodes = [node for node in nodes if node.get('type') == 'controller']
            
            # Combine existing controllers with controllers from nodes
            all_controllers = existing_controllers + controller_nodes
            
            # Remove duplicates based on controller ID
            unique_controllers = []
            seen_ids = set()
            for controller in all_controllers:
                controller_id = controller.get('id')
                if controller_id and controller_id not in seen_ids:
                    unique_controllers.append(controller)
                    seen_ids.add(controller_id)
            
            # Update topology data with properly extracted controllers
            topology_data['controllers'] = unique_controllers
            
            logger.info(f"Enhanced topology data: {len(unique_controllers)} controllers extracted")
        
        if not topology_data:
            return jsonify({'success': False, 'error': 'No topology data available'}), 400
        
        # Determine topology type
        topology_type = data.get('topology_type', 'custom')
        
        # Add metadata
        metadata = {
            'node_count': len(topology_data.get('nodes', [])),
            'link_count': len(topology_data.get('links', [])),
            'controller_count': len(topology_data.get('controllers', [])),
            'saved_from_api': True
        }
        metadata.update(data.get('metadata', {}))
        
        # Save to database
        try:
            topology_service = get_topology_service()
            
            # Check if database is connected
            if not topology_service or not topology_service.db_manager.is_connected():
                return jsonify({
                    'success': False,
                    'error': 'Database connection not available. Please check MongoDB setup.'
                }), 500
            
            # Check if topology name already exists
            existing_topology = topology_service.get_topology_by_name(name)
            if existing_topology:
                return jsonify({
                    'success': False,
                    'error': f'Topology with name "{name}" already exists. Please use a different name.'
                }), 409
            
            topology_id = topology_service.save_topology(
                name=name,
                description=description,
                topology_data=topology_data,
                topology_type=topology_type,
                metadata=metadata
            )
            
            if topology_id:
                return jsonify({
                    'success': True,
                    'message': f'Topology "{name}" saved successfully',
                    'topology_id': topology_id,
                    'metadata': metadata
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save topology due to database error. Check server logs for details.'
                }), 500
                
        except Exception as e:
            logger.error(f"Unexpected error saving topology: {e}")
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error saving topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/topologies', methods=['GET'])
@log_api_request
def list_topologies():
    """List all saved topologies"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        skip = request.args.get('skip', 0, type=int)
        
        topology_service = get_topology_service()
        topologies = topology_service.list_topologies(limit=limit, skip=skip)
        
        return jsonify({
            'success': True,
            'topologies': topologies,
            'count': len(topologies),
            'limit': limit,
            'skip': skip
        })
        
    except Exception as e:
        logger.error(f"Error listing topologies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/topologies/<topology_id>', methods=['GET'])
@log_api_request
def get_topology(topology_id):
    """Get a specific topology by ID"""
    try:
        topology_service = get_topology_service()
        topology = topology_service.get_topology(topology_id)
        
        if topology:
            return jsonify({
                'success': True,
                'topology': topology.to_json_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Topology not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/topologies/<topology_id>/load', methods=['POST'])
@log_api_request
def load_topology(topology_id):
    """Load a saved topology and create it in Mininet"""
    try:
        topology_service = get_topology_service()
        topology = topology_service.get_topology(topology_id)
        
        if not topology:
            return jsonify({
                'success': False,
                'error': 'Topology not found'
            }), 404
        
        # Get Mininet manager
        mininet_mgr = get_mininet_manager()
        
        # Stop current network
        mininet_mgr.stop_network()
        
        # Load the saved topology
        success = mininet_mgr.create_custom_topology(topology.topology_data)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Topology "{topology.name}" loaded successfully',
                'topology': {
                    'id': str(topology._id),
                    'name': topology.name,
                    'description': topology.description,
                    'topology_type': topology.topology_type
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create topology in Mininet'
            }), 500
            
    except Exception as e:
        logger.error(f"Error loading topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/topologies/<topology_id>', methods=['PUT'])
@log_api_request
def update_topology(topology_id):
    """Update a saved topology"""
    try:
        data = request.get_json() or {}
        
        topology_service = get_topology_service()
        success = topology_service.update_topology(
            topology_id=topology_id,
            name=data.get('name'),
            description=data.get('description'),
            topology_data=data.get('topology_data'),
            metadata=data.get('metadata')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Topology updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Topology not found or update failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error updating topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/topologies/<topology_id>', methods=['DELETE'])
@log_api_request
def delete_topology(topology_id):
    """Delete a saved topology"""
    try:
        topology_service = get_topology_service()
        success = topology_service.delete_topology(topology_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Topology deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Topology not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================
# CONFIGURATION STORAGE ENDPOINTS
# =============================

@storage_bp.route('/configurations', methods=['POST'])
@log_api_request
def save_configuration():
    """Save device configuration to database"""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description', '')
        device_type = data.get('device_type')
        configuration_data = data.get('configuration_data')
        
        if not all([name, device_type, configuration_data]):
            return jsonify({
                'success': False,
                'error': 'Name, device_type, and configuration_data are required'
            }), 400
        
        if device_type not in ['host', 'switch', 'router', 'controller']:
            return jsonify({
                'success': False,
                'error': 'Invalid device_type. Must be: host, switch, router, or controller'
            }), 400
        
        # Add metadata
        metadata = {
            'device_type': device_type,
            'saved_from_api': True
        }
        metadata.update(data.get('metadata', {}))
        
        # Save to database
        config_service = get_configuration_service()
        config_id = config_service.save_configuration(
            name=name,
            description=description,
            device_type=device_type,
            configuration_data=configuration_data,
            metadata=metadata
        )
        
        if config_id:
            return jsonify({
                'success': True,
                'message': f'Configuration "{name}" saved successfully',
                'configuration_id': config_id,
                'device_type': device_type
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration (name might already exist)'
            }), 400
            
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/configurations', methods=['GET'])
@log_api_request
def list_configurations():
    """List all saved configurations"""
    try:
        # Get query parameters
        device_type = request.args.get('device_type')
        limit = request.args.get('limit', 50, type=int)
        skip = request.args.get('skip', 0, type=int)
        
        config_service = get_configuration_service()
        configurations = config_service.list_configurations(
            device_type=device_type,
            limit=limit,
            skip=skip
        )
        
        return jsonify({
            'success': True,
            'configurations': configurations,
            'count': len(configurations),
            'device_type_filter': device_type,
            'limit': limit,
            'skip': skip
        })
        
    except Exception as e:
        logger.error(f"Error listing configurations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/configurations/<config_id>', methods=['GET'])
@log_api_request
def get_configuration(config_id):
    """Get a specific configuration by ID"""
    try:
        config_service = get_configuration_service()
        configuration = config_service.get_configuration(config_id)
        
        if configuration:
            return jsonify({
                'success': True,
                'configuration': configuration.to_json_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/configurations/<config_id>', methods=['PUT'])
@log_api_request
def update_configuration(config_id):
    """Update a saved configuration"""
    try:
        data = request.get_json() or {}
        
        config_service = get_configuration_service()
        success = config_service.update_configuration(
            config_id=config_id,
            name=data.get('name'),
            description=data.get('description'),
            configuration_data=data.get('configuration_data'),
            metadata=data.get('metadata')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found or update failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/configurations/<config_id>', methods=['DELETE'])
@log_api_request
def delete_configuration(config_id):
    """Delete a saved configuration"""
    try:
        config_service = get_configuration_service()
        success = config_service.delete_configuration(config_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================
# UTILITY ENDPOINTS
# =============================

@storage_bp.route('/export/topology/<topology_id>', methods=['GET'])
@log_api_request
def export_topology(topology_id):
    """Export topology as downloadable file"""
    try:
        topology_service = get_topology_service()
        topology = topology_service.get_topology(topology_id)
        
        if not topology:
            return jsonify({
                'success': False,
                'error': 'Topology not found'
            }), 404
        
        export_format = request.args.get('format', 'json')
        
        if export_format == 'json':
            return jsonify(topology.to_json_dict())
        
        elif export_format == 'yaml':
            import yaml
            yaml_data = yaml.dump(topology.to_json_dict(), default_flow_style=False)
            return yaml_data, 200, {'Content-Type': 'text/yaml'}
        
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported export format: {export_format}'
            }), 400
            
    except Exception as e:
        logger.error(f"Error exporting topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/export/configuration/<config_id>', methods=['GET'])
@log_api_request
def export_configuration(config_id):
    """Export configuration as downloadable file"""
    try:
        config_service = get_configuration_service()
        configuration = config_service.get_configuration(config_id)
        
        if not configuration:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
        
        export_format = request.args.get('format', 'json')
        
        if export_format == 'json':
            return jsonify(configuration.to_json_dict())
        
        elif export_format == 'yaml':
            import yaml
            yaml_data = yaml.dump(configuration.to_json_dict(), default_flow_style=False)
            return yaml_data, 200, {'Content-Type': 'text/yaml'}
        
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported export format: {export_format}'
            }), 400
            
    except Exception as e:
        logger.error(f"Error exporting configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@storage_bp.route('/stats', methods=['GET'])
@log_api_request
def get_storage_stats():
    """Get storage statistics"""
    try:
        topology_service = get_topology_service()
        config_service = get_configuration_service()
        
        # Get counts for each type
        all_topologies = topology_service.list_topologies(limit=1000)
        all_configs = config_service.list_configurations(limit=1000)
        
        # Count by device type
        config_counts = {}
        for config in all_configs:
            device_type = config['device_type']
            config_counts[device_type] = config_counts.get(device_type, 0) + 1
        
        # Count by topology type
        topology_counts = {}
        for topology in all_topologies:
            topo_type = topology.get('topology_type', 'unknown')
            topology_counts[topo_type] = topology_counts.get(topo_type, 0) + 1
        
        stats = {
            'topologies': {
                'total': len(all_topologies),
                'by_type': topology_counts
            },
            'configurations': {
                'total': len(all_configs),
                'by_device_type': config_counts
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
