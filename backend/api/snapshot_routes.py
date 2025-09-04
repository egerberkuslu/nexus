"""API routes for simulation snapshot management"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from database.services import get_snapshot_service
from core.mininet_manager import MininetManager
from .storage_routes import log_api_request

logger = logging.getLogger(__name__)

# Create blueprint for snapshot routes
snapshot_bp = Blueprint('snapshots', __name__, url_prefix='/api/snapshots')

def get_mininet_manager() -> MininetManager:
    """Get the global Mininet manager instance"""
    from flask import current_app
    return current_app.config['MININET_MANAGER']

@snapshot_bp.route('/create', methods=['POST'])
@log_api_request
def create_snapshot():
    """Create a new simulation snapshot"""
    try:
        data = request.get_json() or {}
        name = data.get('name', f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        description = data.get('description', 'Simulation snapshot')
        snapshot_type = data.get('snapshot_type', 'full')
        
        # Get Mininet manager
        mininet_mgr = get_mininet_manager()
        
        # Create snapshot data
        try:
            # Check if there's topology data from the request
            topology_data = data.get('topology_data')
            if topology_data:
                logger.info(f"Setting topology configuration from request with {len(topology_data.get('nodes', []))} nodes")
                mininet_mgr.set_topology_configuration(topology_data)
            
            snapshot_data = mininet_mgr.create_simulation_snapshot()
            
            if not snapshot_data:
                raise Exception("Failed to create snapshot data")
                
            # Log snapshot content for debugging
            mininet_state = snapshot_data.get('mininet_state', {})
            topology_data = mininet_state.get('topology_data', {})
            logger.info(f"Snapshot created with {len(topology_data.get('nodes', []))} nodes and {len(topology_data.get('links', []))} links")
                
        except Exception as e:
            logger.error(f"Error creating snapshot data: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to create snapshot: {str(e)}'
            }), 500
        
        # Add metadata safely
        try:
            mininet_state = snapshot_data.get('mininet_state', {})
            topology_data = mininet_state.get('topology_data', {})
            live_configurations = mininet_state.get('live_configurations', {})
            applied_configurations = mininet_state.get('applied_configurations', {})
            controller_state = snapshot_data.get('controller_state', {})
            
            # Count different node types
            nodes = topology_data.get('nodes', [])
            hosts = [n for n in nodes if n.get('type') == 'host']
            switches = [n for n in nodes if n.get('type') == 'switch'] 
            routers = [n for n in nodes if n.get('type') == 'router']
            controllers = [n for n in nodes if n.get('type') == 'controller']
            
            metadata = {
                'created_by': 'web_interface',
                'mininet_running': mininet_mgr.is_running,
                'controller_running': mininet_mgr.ryu_controller.is_running if mininet_mgr.ryu_controller else False,
                'controller_type': controller_state.get('controller_type', 'unknown'),
                'snapshot_size': len(str(snapshot_data)),
                'node_count': len(nodes),
                'link_count': len(topology_data.get('links', [])),
                'host_count': len(hosts),
                'switch_count': len(switches),
                'router_count': len(routers),
                'controller_count': len(controllers),
                'has_live_configs': bool(live_configurations),
                'configured_hosts': len(live_configurations.get('hosts', {})),
                'configured_routers': len(live_configurations.get('routers', {})),
                'flow_tables': len(live_configurations.get('flow_tables', {})),
                'total_routes': sum(len(config.get('routes', [])) for config in live_configurations.get('hosts', {}).values()),
                'tracked_devices': len(applied_configurations.get('device_configs', {})),
                'api_operations': len(applied_configurations.get('api_operations', [])),
                'terminal_commands': sum(len(cmds) for cmds in applied_configurations.get('terminal_commands', {}).values())
            }
        except Exception as e:
            logger.warning(f"Error creating metadata: {e}")
            metadata = {
                'created_by': 'web_interface',
                'error': f'Metadata creation failed: {str(e)}'
            }
        
        # Save snapshot to database
        snapshot_service = get_snapshot_service()
        snapshot_id = snapshot_service.save_snapshot(
            name=name,
            description=description,
            snapshot_data=snapshot_data,
            snapshot_type=snapshot_type,
            metadata=metadata
        )
        
        if snapshot_id:
            return jsonify({
                'success': True,
                'message': f'Snapshot "{name}" created successfully',
                'snapshot_id': snapshot_id,
                'metadata': metadata
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save snapshot (name might already exist)'
            }), 400
            
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to create snapshot: {str(e)}'
        }), 500

@snapshot_bp.route('/', methods=['GET'])
@log_api_request
def list_snapshots():
    """List all saved snapshots"""
    try:
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        snapshot_service = get_snapshot_service()
        snapshots = snapshot_service.list_snapshots(limit=limit, skip=skip)
        
        return jsonify({
            'success': True,
            'snapshots': snapshots,
            'count': len(snapshots)
        })
        
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list snapshots: {str(e)}'
        }), 500

@snapshot_bp.route('/<snapshot_id>', methods=['GET'])
@log_api_request
def get_snapshot(snapshot_id):
    """Get a specific snapshot"""
    try:
        snapshot_service = get_snapshot_service()
        snapshot = snapshot_service.get_snapshot(snapshot_id)
        
        if not snapshot:
            return jsonify({
                'success': False,
                'error': 'Snapshot not found'
            }), 404
        
        return jsonify({
            'success': True,
            'snapshot': snapshot.to_json_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get snapshot: {str(e)}'
        }), 500

@snapshot_bp.route('/<snapshot_id>', methods=['PUT'])
@log_api_request
def update_snapshot(snapshot_id):
    """Update a snapshot"""
    try:
        data = request.get_json() or {}
        
        snapshot_service = get_snapshot_service()
        success = snapshot_service.update_snapshot(
            snapshot_id=snapshot_id,
            name=data.get('name'),
            description=data.get('description'),
            metadata=data.get('metadata')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Snapshot updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Snapshot not found or update failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error updating snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to update snapshot: {str(e)}'
        }), 500

@snapshot_bp.route('/<snapshot_id>', methods=['DELETE'])
@log_api_request
def delete_snapshot(snapshot_id):
    """Delete a snapshot"""
    try:
        snapshot_service = get_snapshot_service()
        success = snapshot_service.delete_snapshot(snapshot_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Snapshot deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Snapshot not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete snapshot: {str(e)}'
        }), 500

@snapshot_bp.route('/<snapshot_id>/restore', methods=['POST'])
@log_api_request
def restore_snapshot(snapshot_id):
    """Restore a simulation from snapshot"""
    try:
        snapshot_service = get_snapshot_service()
        snapshot = snapshot_service.get_snapshot(snapshot_id)
        
        if not snapshot:
            return jsonify({
                'success': False,
                'error': 'Snapshot not found'
            }), 404
        
        # Get Mininet manager
        mininet_mgr = get_mininet_manager()
        
        # Restore snapshot
        success = mininet_mgr.restore_simulation_snapshot(snapshot.snapshot_data)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Snapshot "{snapshot.name}" restored successfully',
                'snapshot': {
                    'id': snapshot_id,
                    'name': snapshot.name,
                    'description': snapshot.description,
                    'restored_at': datetime.utcnow().isoformat()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore simulation from snapshot'
            }), 500
            
    except Exception as e:
        logger.error(f"Error restoring snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to restore snapshot: {str(e)}'
        }), 500

@snapshot_bp.route('/compare/<snapshot1_id>/<snapshot2_id>', methods=['GET'])
@log_api_request
def compare_snapshots(snapshot1_id, snapshot2_id):
    """Compare two snapshots"""
    try:
        snapshot_service = get_snapshot_service()
        
        snapshot1 = snapshot_service.get_snapshot(snapshot1_id)
        snapshot2 = snapshot_service.get_snapshot(snapshot2_id)
        
        if not snapshot1 or not snapshot2:
            return jsonify({
                'success': False,
                'error': 'One or both snapshots not found'
            }), 404
        
        # Compare basic metadata
        comparison = {
            'snapshot1': {
                'id': snapshot1_id,
                'name': snapshot1.name,
                'created_at': snapshot1.created_at.isoformat(),
                'metadata': snapshot1.metadata
            },
            'snapshot2': {
                'id': snapshot2_id,
                'name': snapshot2.name,
                'created_at': snapshot2.created_at.isoformat(),
                'metadata': snapshot2.metadata
            },
            'differences': {}
        }
        
        # Compare topology data
        topo1 = snapshot1.snapshot_data.get('mininet_state', {}).get('topology_data', {})
        topo2 = snapshot2.snapshot_data.get('mininet_state', {}).get('topology_data', {})
        
        comparison['differences']['nodes'] = {
            'snapshot1_count': len(topo1.get('nodes', [])),
            'snapshot2_count': len(topo2.get('nodes', [])),
            'difference': len(topo1.get('nodes', [])) - len(topo2.get('nodes', []))
        }
        
        comparison['differences']['links'] = {
            'snapshot1_count': len(topo1.get('links', [])),
            'snapshot2_count': len(topo2.get('links', [])),
            'difference': len(topo1.get('links', [])) - len(topo2.get('links', []))
        }
        
        # Compare controller states
        ctrl1 = snapshot1.snapshot_data.get('controller_state', {})
        ctrl2 = snapshot2.snapshot_data.get('controller_state', {})
        
        comparison['differences']['controller'] = {
            'snapshot1_running': ctrl1.get('is_running', False),
            'snapshot2_running': ctrl2.get('is_running', False),
            'same_state': ctrl1.get('is_running', False) == ctrl2.get('is_running', False)
        }
        
        return jsonify({
            'success': True,
            'comparison': comparison
        })
        
    except Exception as e:
        logger.error(f"Error comparing snapshots: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to compare snapshots: {str(e)}'
        }), 500

@snapshot_bp.route('/debug/tracked-configs', methods=['GET'])
@log_api_request
def debug_tracked_configs():
    """Debug endpoint to show tracked configurations"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Call debug method
        mininet_mgr.debug_tracked_configurations()
        
        # Return the tracked configurations
        tracked_configs = mininet_mgr.get_applied_configurations()
        
        return jsonify({
            'success': True,
            'tracked_configurations': tracked_configs,
            'summary': {
                'device_configs': len(tracked_configs.get('device_configs', {})),
                'terminal_commands': sum(len(cmds) for cmds in tracked_configs.get('terminal_commands', {}).values()),
                'api_operations': len(tracked_configs.get('api_operations', []))
            }
        })
        
    except Exception as e:
        logger.error(f"Error in debug tracked configs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@snapshot_bp.route('/debug/test-router-restore', methods=['POST'])
@log_api_request
def test_router_restore():
    """Test endpoint to manually test router configuration restoration"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running:
            return jsonify({
                'success': False,
                'error': 'Network is not running'
            }), 400
        
        logger.info("=== MANUAL ROUTER RESTORE TEST ===")
        
        # Try to apply tracked configurations
        mininet_mgr._apply_tracked_configurations()
        
        return jsonify({
            'success': True,
            'message': 'Router configuration restoration test completed. Check logs for details.'
        })
        
    except Exception as e:
        logger.error(f"Error in test router restore: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@snapshot_bp.route('/export/<snapshot_id>', methods=['GET'])
@log_api_request
def export_snapshot(snapshot_id):
    """Export a snapshot as JSON"""
    try:
        snapshot_service = get_snapshot_service()
        snapshot = snapshot_service.get_snapshot(snapshot_id)
        
        if not snapshot:
            return jsonify({
                'success': False,
                'error': 'Snapshot not found'
            }), 404
        
        # Create export data
        export_data = {
            'export_info': {
                'exported_at': datetime.utcnow().isoformat(),
                'export_version': '1.0',
                'original_snapshot_id': snapshot_id
            },
            'snapshot': snapshot.to_json_dict()
        }
        
        return jsonify({
            'success': True,
            'export_data': export_data
        })
        
    except Exception as e:
        logger.error(f"Error exporting snapshot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to export snapshot: {str(e)}'
        }), 500
