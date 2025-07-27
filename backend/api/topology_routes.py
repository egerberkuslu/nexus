"""
Topology API Routes
Enhanced topology management with controller visibility
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
topology_bp = Blueprint('topology', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@topology_bp.route('/full', methods=['GET'])
@log_api_request
def get_full_topology():
    """Get complete topology including controllers, nodes, and links"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
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

@topology_bp.route('/export', methods=['GET'])
@log_api_request
def export_topology():
    """Export topology configuration"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.update_topology_data()
        
        export_format = request.args.get('format', 'json')
        
        if export_format == 'json':
            return jsonify(mininet_mgr.topology_data)
        
        elif export_format == 'yaml':
            import yaml
            yaml_data = yaml.dump(mininet_mgr.topology_data, default_flow_style=False)
            return yaml_data, 200, {'Content-Type': 'text/yaml'}
        
        elif export_format == 'dot':
            # Generate DOT format for Graphviz
            dot_lines = ['digraph topology {']
            dot_lines.append('  rankdir=TB;')
            dot_lines.append('  node [shape=box];')
            
            # Add nodes
            for node in mininet_mgr.topology_data['nodes']:
                color = {
                    'host': 'lightblue',
                    'router': 'lightgreen', 
                    'switch': 'lightyellow',
                    'controller': 'lightcoral'
                }.get(node['type'], 'white')
                
                dot_lines.append(f'  "{node["id"]}" [fillcolor={color}, style=filled, label="{node["id"]}\\n{node["type"]}"];')
            
            # Add controllers
            for controller in mininet_mgr.topology_data['controllers']:
                dot_lines.append(f'  "{controller["id"]}" [fillcolor=lightcoral, style=filled, label="{controller["id"]}\\ncontroller"];')
            
            # Add links
            for link in mininet_mgr.topology_data['links']:
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
        
        # Stop current network
        mininet_mgr.stop_network()
        
        # Create topology from config
        success = mininet_mgr.create_custom_topology(topology_config)
        
        message = 'Topology imported successfully' if success else 'Failed to import topology'
        status_code = 200 if success else 500
        
        return jsonify({
            'success': success,
            'message': message,
            'imported_config': topology_config
        }), status_code
        
    except Exception as e:
        logger.error(f"Error importing topology: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500