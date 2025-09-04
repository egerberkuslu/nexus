"""
Topology API Routes
Enhanced topology management with controller visibility
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request
import os

logger = setup_logger(__name__)
topology_bp = Blueprint('topology', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

def auto_save_topology_if_enabled(topology_data, topology_type='auto_saved'):
    """Auto-save topology if enabled in environment"""
    try:
        if os.getenv('AUTO_SAVE_TOPOLOGIES', 'false').lower() == 'true':
            from database.services import get_topology_service
            from datetime import datetime
            
            topology_service = get_topology_service()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"auto_save_{timestamp}"
            
            topology_service.save_topology(
                name=name,
                description=f"Auto-saved topology at {datetime.now().isoformat()}",
                topology_data=topology_data,
                topology_type=topology_type,
                metadata={'auto_saved': True, 'timestamp': timestamp}
            )
            logger.info(f"Auto-saved topology as '{name}'")
    except Exception as e:
        logger.warning(f"Auto-save topology failed: {e}")

def _enhance_imported_topology_config(topology_config):
    """Enhance imported topology config with default controller and switch type information"""
    try:
        enhanced_config = topology_config.copy()
        
        # Ensure nodes list exists
        if 'nodes' not in enhanced_config:
            enhanced_config['nodes'] = []
        
        # Add default type information to nodes that don't have it
        for node in enhanced_config['nodes']:
            if node.get('type') == 'controller':
                # Add default controller type information if missing
                if 'controller_type' not in node:
                    node['controller_type'] = 'ryu'
                if 'app' not in node:
                    node['app'] = 'simple_switch_13'
                if 'protocol' not in node:
                    node['protocol'] = 'OpenFlow'
                if 'version' not in node:
                    node['version'] = '1.3'
                if 'port' not in node:
                    node['port'] = 6633
            elif node.get('type') == 'switch':
                # Add default switch type information if missing
                if 'switch_type' not in node:
                    node['switch_type'] = 'ovs'
                if 'dpid' not in node:
                    node['dpid'] = 'auto'
                if 'openflow_version' not in node:
                    node['openflow_version'] = '1.3'
        
        # Ensure controllers list exists and is populated
        if 'controllers' not in enhanced_config:
            enhanced_config['controllers'] = []
        
        # Add controllers from nodes if not already in controllers list
        controller_ids = {c.get('id') for c in enhanced_config['controllers']}
        for node in enhanced_config['nodes']:
            if node.get('type') == 'controller' and node.get('id') not in controller_ids:
                enhanced_config['controllers'].append(node)
        
        return enhanced_config
        
    except Exception as e:
        logger.error(f"Error enhancing imported topology config: {e}")
        return topology_config

def _extract_controller_types(topology_config):
    """Extract unique controller types from topology config"""
    controller_types = set()
    for node in topology_config.get('nodes', []):
        if node.get('type') == 'controller':
            controller_types.add(node.get('controller_type', 'ryu'))
    return list(controller_types)

def _extract_switch_types(topology_config):
    """Extract unique switch types from topology config"""
    switch_types = set()
    for node in topology_config.get('nodes', []):
        if node.get('type') == 'switch':
            switch_types.add(node.get('switch_type', 'ovs'))
    return list(switch_types)

@topology_bp.route('/full', methods=['GET'])
@log_api_request
def get_full_topology():
    """Get complete topology including controllers, nodes, and links"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Critical logging - track API calls
        logger.critical(f"API CALL: /topology/full - about to call update_topology_data()")
        
        mininet_mgr.update_topology_data()
        
        # Critical logging - check final result
        controllers = mininet_mgr.topology_data.get('controllers', [])
        logger.critical(f"API RESPONSE: Returning {len(controllers)} controllers")
        for controller in controllers:
            logger.critical(f"API CONTROLLER: {controller.get('id')} - {controller.get('controller_type')}")

        # Auto-save topology if enabled
        auto_save_topology_if_enabled(mininet_mgr.topology_data, 'current_topology')

        return jsonify(mininet_mgr.topology_data)

    except Exception as e:
        logger.error(f"Error getting full topology: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/nodes', methods=['GET'])
@log_api_request
def get_topology_nodes():
    """Get all topology nodes (hosts, routers, switches)"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        # Filter nodes by type if requested
        node_type = request.args.get('type')
        nodes = mininet_mgr.topology_data['nodes']
        
        if node_type:
            nodes = [node for node in nodes if node['type'] == node_type]
        
        return jsonify({
            'nodes': nodes,
            'count': len(nodes),
            'types': list(set(node['type'] for node in mininet_mgr.topology_data['nodes']))
        })
        
    except Exception as e:
        logger.error(f"Error getting topology nodes: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/links', methods=['GET'])
@log_api_request
def get_topology_links():
    """Get all topology links"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        links = mininet_mgr.topology_data['links']
        
        # Add link statistics if available
        enhanced_links = []
        for link in links:
            enhanced_link = link.copy()
            
            # Add packet/byte counts if available from flow stats
            flow_stats = mininet_mgr.get_flow_stats()
            enhanced_link['stats'] = {
                'packets': 0,
                'bytes': 0,
                'errors': 0
            }
            
            enhanced_links.append(enhanced_link)
        
        return jsonify({
            'links': enhanced_links,
            'count': len(enhanced_links)
        })
        
    except Exception as e:
        logger.error(f"Error getting topology links: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/controllers', methods=['GET'])
@log_api_request
def get_topology_controllers():
    """Get all controllers in the topology - NEW FEATURE"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        controllers = mininet_mgr.topology_data['controllers']
        
        # Enhance controller data with real-time status
        enhanced_controllers = []
        for controller in controllers:
            enhanced_controller = controller.copy()
            
            # Add real-time controller status
            controller_status = mininet_mgr.get_controller_status()
            enhanced_controller.update({
                'real_time_status': controller_status,
                'connections': mininet_mgr.ryu_controller._get_connection_count() if mininet_mgr.ryu_controller.is_running else 0,
                'memory_usage': mininet_mgr.ryu_controller._get_memory_usage() if mininet_mgr.ryu_controller.is_running else 0
            })
            
            enhanced_controllers.append(enhanced_controller)
        
        return jsonify({
            'controllers': enhanced_controllers,
            'count': len(enhanced_controllers)
        })
        
    except Exception as e:
        logger.error(f"Error getting topology controllers: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/stats', methods=['GET'])
@log_api_request
def get_topology_stats():
    """Get topology statistics summary"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        stats = mininet_mgr.topology_data['stats']
        
        # Add real-time network metrics
        if mininet_mgr.is_running:
            network_metrics = mininet_mgr.get_network_metrics()
            stats['network_metrics'] = {
                'uptime': network_metrics.get('uptime', '00:00:00'),
                'bandwidth_mbps': network_metrics.get('bandwidth_mbps', 0),
                'latency_ms': network_metrics.get('latency_ms', 0),
                'active_flows': network_metrics.get('active_flows', 0),
                'total_interfaces': network_metrics.get('total_interfaces', 0)
            }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting topology stats: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/node/<node_id>', methods=['GET'])
@log_api_request
def get_node_details(node_id):
    """Get detailed information about a specific node"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.net:
            return jsonify({'error': 'Network not created'}), 400
        
        # Find the node
        node = mininet_mgr.net.get(node_id)
        if not node:
            return jsonify({'error': f'Node {node_id} not found'}), 404
        
        mininet_mgr.update_topology_data()
        
        # Find node in topology data
        node_data = None
        for n in mininet_mgr.topology_data['nodes']:
            if n['id'] == node_id:
                node_data = n
                break
        
        if not node_data:
            return jsonify({'error': f'Node {node_id} not found in topology'}), 404
        
        # Add real-time information
        enhanced_node = node_data.copy()
        
        if mininet_mgr.is_running:
            # Add interface statistics for hosts and routers
            if node_data['type'] in ['host', 'router']:
                try:
                    # Get ARP table
                    arp_result = node.cmd('arp -a')
                    enhanced_node['arp_table'] = arp_result.strip()
                    
                    # Get routing table for routers
                    if node_data['type'] == 'router':
                        route_result = node.cmd('ip route show')
                        enhanced_node['routing_table'] = route_result.strip()
                        
                        # Get interface details
                        if hasattr(node, 'get_interface_info'):
                            enhanced_node['interface_details'] = node.get_interface_info()
                    
                    # Get network statistics
                    ifconfig_result = node.cmd('ifconfig')
                    enhanced_node['interface_stats'] = ifconfig_result.strip()
                    
                except Exception as e:
                    enhanced_node['error'] = f'Could not get real-time data: {e}'
            
            # Add flow table for switches
            elif node_data['type'] == 'switch':
                try:
                    flow_stats = mininet_mgr.get_flow_stats()
                    if node_id in flow_stats:
                        enhanced_node['flow_stats'] = flow_stats[node_id]
                except Exception as e:
                    enhanced_node['flow_error'] = str(e)
        
        return jsonify(enhanced_node)
        
    except Exception as e:
        logger.error(f"Error getting node details: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/visualize', methods=['GET'])
@log_api_request
def get_visualization_data():
    """Get topology data formatted for visualization libraries"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        # Format data for D3.js or similar visualization libraries
        viz_data = {
            'nodes': [],
            'links': []
        }
        
        # Add all nodes including controllers
        node_id_map = {}
        idx = 0
        
        # Add controllers first
        for controller in mininet_mgr.topology_data['controllers']:
            node_id_map[controller['id']] = idx
            viz_data['nodes'].append({
                'id': idx,
                'name': controller['id'],
                'type': 'controller',
                'group': 0,  # Controllers get group 0
                'status': controller['status'],
                'ip': controller.get('ip', ''),
                'port': controller.get('port', '')
            })
            idx += 1
        
        # Add network nodes
        type_groups = {'host': 1, 'router': 2, 'switch': 3}
        
        for node in mininet_mgr.topology_data['nodes']:
            node_id_map[node['id']] = idx
            viz_data['nodes'].append({
                'id': idx,
                'name': node['id'],
                'type': node['type'],
                'group': type_groups.get(node['type'], 4),
                'status': node['status'],
                'ip': node.get('ip', ''),
                'mac': node.get('mac', '')
            })
            idx += 1
        
        # Add links
        for link in mininet_mgr.topology_data['links']:
            source_idx = node_id_map.get(link['source'])
            target_idx = node_id_map.get(link['target'])
            
            if source_idx is not None and target_idx is not None:
                viz_data['links'].append({
                    'source': source_idx,
                    'target': target_idx,
                    'bandwidth': link.get('bandwidth', 'unknown'),
                    'status': link.get('status', 'unknown')
                })
        
        # Add metadata
        viz_data['metadata'] = {
            'total_nodes': len(viz_data['nodes']),
            'total_links': len(viz_data['links']),
            'groups': {
                0: 'controller',
                1: 'host',
                2: 'router',
                3: 'switch'
            },
            'timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None
        }
        
        return jsonify(viz_data)
        
    except Exception as e:
        logger.error(f"Error getting visualization data: {e}")
        return jsonify({'error': str(e)}), 500

# ==============================
# Dynamic topology modifications
# ==============================
@topology_bp.route('/nodes', methods=['POST'])
@log_api_request
def add_topology_node():
    """Add a node to the running topology (host/switch/router)."""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json(force=True) or {}
        node_id = data.get('id')
        node_type = data.get('type', 'host')
        if not node_id:
            return jsonify({'success': False, 'error': 'Missing node id'}), 400

        result = mininet_mgr.add_node(
            node_id=node_id,
            node_type=node_type,
            **{k: v for k, v in data.items() if k not in ['id', 'type']}
        )
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Error adding topology node: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/nodes/<node_id>', methods=['DELETE'])
@log_api_request
def delete_topology_node(node_id):
    """Remove a node from the running topology."""
    try:
        logger.info(f"=== DELETE /nodes/<node_id> called ===")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request path: {request.path}")
        logger.info(f"Request args: {request.args}")
        logger.info(f"Request view_args: {request.view_args}")
        logger.info(f"Route parameter node_id: {repr(node_id)}")
        logger.info(f"Node ID type: {type(node_id)}")
        logger.info(f"Node ID is None: {node_id is None}")
        
        if node_id is None:
            logger.error("Node ID is None in API route")
            return jsonify({'success': False, 'error': 'Node ID is None'}), 400
            
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.remove_node(node_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Error removing topology node {node_id}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/links', methods=['POST'])
@log_api_request
def add_topology_link():
    """Add a link between two nodes while running."""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json(force=True) or {}
        source = data.get('source')
        target = data.get('target')
        if not source or not target:
            return jsonify({'success': False, 'error': 'Missing source or target'}), 400

        result = mininet_mgr.add_link(source, target, **{k: v for k, v in data.items() if k not in ['source', 'target']})
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Error adding topology link: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/links', methods=['DELETE'])
@log_api_request
def delete_topology_link():
    """Remove a link between two nodes."""
    try:
        mininet_mgr = get_mininet_manager()
        # Allow delete via JSON body: {source, target}
        data = request.get_json(force=True) or {}
        source = data.get('source')
        target = data.get('target')
        if not source or not target:
            return jsonify({'success': False, 'error': 'Missing source or target'}), 400

        result = mininet_mgr.remove_link(source, target)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Error removing topology link: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/export', methods=['GET'])
@log_api_request
def export_topology():
    """Export topology configuration with controller and switch type information"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        export_format = request.args.get('format', 'json')
        
        # Enhance topology data with controller and switch type information
        enhanced_topology_data = mininet_mgr.topology_data.copy()
        
        # Add controller and switch type information to nodes
        for node in enhanced_topology_data.get('nodes', []):
            if node.get('type') == 'controller':
                # Add controller type information
                node['controller_type'] = node.get('controller_type', 'ryu')
                node['app'] = node.get('app', 'simple_switch_13')
                node['protocol'] = node.get('protocol', 'OpenFlow')
                node['version'] = node.get('version', '1.3')
            elif node.get('type') == 'switch':
                # Add switch type information
                node['switch_type'] = node.get('switch_type', 'ovs')
                node['dpid'] = node.get('dpid', 'auto')
                node['openflow_version'] = node.get('openflow_version', '1.3')
        
        # Add metadata about supported types
        enhanced_topology_data['metadata'] = {
            'export_timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None,
            'supported_controller_types': ['ryu', 'pox', 'osken', 'opendaylight'],
            'supported_switch_types': ['ovs', 'linux_bridge', 'p4'],
            'export_version': '2.0'
        }
        
        if export_format == 'json':
            return jsonify(enhanced_topology_data)
        
        elif export_format == 'yaml':
            import yaml
            yaml_data = yaml.dump(enhanced_topology_data, default_flow_style=False)
            return yaml_data, 200, {'Content-Type': 'text/yaml'}
        
        elif export_format == 'dot':
            # Generate DOT format for Graphviz
            dot_lines = ['digraph topology {']
            dot_lines.append('  rankdir=TB;')
            dot_lines.append('  node [shape=box];')
            
            # Add nodes
            for node in enhanced_topology_data['nodes']:
                color = {
                    'host': 'lightblue',
                    'router': 'lightgreen', 
                    'switch': 'lightyellow',
                    'controller': 'lightcoral'
                }.get(node['type'], 'white')
                
                # Add type-specific labels
                label = f"{node['id']}\\n{node['type']}"
                if node.get('type') == 'controller' and node.get('controller_type'):
                    label += f"\\n({node['controller_type']})"
                elif node.get('type') == 'switch' and node.get('switch_type'):
                    label += f"\\n({node['switch_type']})"
                
                dot_lines.append(f'  "{node["id"]}" [fillcolor={color}, style=filled, label="{label}"];')
            
            # Add controllers
            for controller in enhanced_topology_data['controllers']:
                label = f"{controller['id']}\\ncontroller"
                if controller.get('controller_type'):
                    label += f"\\n({controller['controller_type']})"
                dot_lines.append(f'  "{controller["id"]}" [fillcolor=lightcoral, style=filled, label="{label}"];')
            
            # Add links
            for link in enhanced_topology_data['links']:
                dot_lines.append(f'  "{link["source"]}" -> "{link["target"]}" [label="{link.get("bandwidth", "")}"];')
            
            dot_lines.append('}')
            
            return '\n'.join(dot_lines), 200, {'Content-Type': 'text/plain'}
        
        else:
            return jsonify({'error': f'Unsupported format: {export_format}'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting topology: {e}")
        return jsonify({'error': str(e)}), 500

@topology_bp.route('/import', methods=['POST'])
@log_api_request
def import_topology():
    """Import topology configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Handle both JSON and form data
        if request.is_json:
            topology_config = request.get_json()
        else:
            # Handle file upload
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Read file content
            content = file.read().decode('utf-8')
            
            # Parse based on file extension
            if file.filename.endswith('.json'):
                import json
                topology_config = json.loads(content)
            elif file.filename.endswith('.yaml') or file.filename.endswith('.yml'):
                import yaml
                topology_config = yaml.safe_load(content)
            else:
                return jsonify({'error': 'Unsupported file format'}), 400
        
        # Validate and enhance topology config with type information
        enhanced_config = _enhance_imported_topology_config(topology_config)
        
        # Stop current network
        mininet_mgr.stop_network()
        
        # Create topology from config
        success = mininet_mgr.create_custom_topology(enhanced_config)
        
        message = 'Topology imported successfully' if success else 'Failed to import topology'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success,
            'message': message,
            'imported_config': enhanced_config,
            'controller_types_found': _extract_controller_types(enhanced_config),
            'switch_types_found': _extract_switch_types(enhanced_config)
        }), status_code
        
    except Exception as e:
        logger.error(f"Error importing topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/nodes/<node_id>/ip', methods=['PUT'])
@log_api_request
def update_node_ip(node_id):
    """Update IP address of a node"""
    try:
        data = request.get_json(force=True) or {}
        new_ip = data.get('ip')
        interface = data.get('interface')  # Optional: specific interface
        
        if not new_ip:
            return jsonify({'success': False, 'error': 'Missing IP address'}), 400
            
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.update_node_ip(node_id, new_ip, interface)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
        
    except Exception as e:
        logger.error(f"Error updating IP for node {node_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/links/bandwidth', methods=['PUT'])
@log_api_request
def update_link_bandwidth():
    """Update bandwidth of a link"""
    try:
        data = request.get_json(force=True) or {}
        source = data.get('source')
        target = data.get('target')
        bandwidth = data.get('bandwidth')
        
        if not all([source, target, bandwidth]):
            return jsonify({'success': False, 'error': 'Missing source, target, or bandwidth'}), 400
            
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.update_link_bandwidth(source, target, bandwidth)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
        
    except Exception as e:
        logger.error(f"Error updating link bandwidth: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/links/status', methods=['PUT'])
@log_api_request
def update_link_status():
    """Update status of a link (up/down)"""
    try:
        data = request.get_json(force=True) or {}
        source = data.get('source')
        target = data.get('target')
        status = data.get('status')
        
        if not all([source, target, status]):
            return jsonify({'success': False, 'error': 'Missing source, target, or status'}), 400
            
        if status not in ['up', 'down']:
            return jsonify({'success': False, 'error': 'Status must be "up" or "down"'}), 400
            
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.update_link_status(source, target, status)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error updating link status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/controllers/<controller_id>/port', methods=['PUT'])
@log_api_request
def update_controller_port(controller_id):
    """Update controller port"""
    try:
        data = request.get_json(force=True) or {}
        new_port = data.get('port')
        
        if not new_port:
            return jsonify({'success': False, 'error': 'Missing port number'}), 400
            
        try:
            new_port = int(new_port)
        except ValueError:
            return jsonify({'success': False, 'error': 'Port must be a valid number'}), 400
            
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.update_controller_port(controller_id, new_port)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
        
    except Exception as e:
        logger.error(f"Error updating controller port for {controller_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/nodes/<node_id>/interfaces', methods=['GET'])
@log_api_request
def get_node_interfaces(node_id):
    """Get detailed interface information for a node"""
    try:
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.get_node_interfaces(node_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
        
    except Exception as e:
        logger.error(f"Error getting interfaces for node {node_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/refresh', methods=['POST'])
@log_api_request
def refresh_topology():
    """Force refresh topology data from Mininet"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        return jsonify({'success': True, 'message': 'Topology data refreshed'})
    except Exception as e:
        logger.error(f"Error refreshing topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@topology_bp.route('/links/bandwidth/<source>/<target>', methods=['GET'])
@log_api_request
def get_link_bandwidth(source, target):
    """Get current bandwidth of a specific link"""
    try:
        mininet_mgr = get_mininet_manager()
        result = mininet_mgr.get_link_bandwidth(source, target)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting link bandwidth: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500