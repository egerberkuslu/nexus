"""
Statistics API Routes
Real-time network statistics and metrics
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
stats_bp = Blueprint('stats', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']

@stats_bp.route('/metrics', methods=['GET'])
@log_api_request
def get_network_metrics():
    """Get real-time network metrics"""
    try:
        mininet_mgr = get_mininet_manager()
        metrics = mininet_mgr.get_network_metrics()
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error getting network metrics: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/detailed', methods=['GET'])
@log_api_request
def get_detailed_stats():
    """Get comprehensive network statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get comprehensive statistics
        metrics = mininet_mgr.get_network_metrics()
        controller_stats = mininet_mgr.ryu_controller.get_controller_stats()
        flow_stats = mininet_mgr.get_flow_stats()
        
        # Update topology for current stats
        mininet_mgr.update_topology_data()
        topology_stats = mininet_mgr.topology_data.get('stats', {})
        
        detailed_stats = {
            'network_metrics': metrics,
            'controller_stats': controller_stats,
            'flow_stats': flow_stats,
            'topology_stats': topology_stats,
            'timestamp': metrics.get('timestamp')
        }
        
        return jsonify(detailed_stats)
        
    except Exception as e:
        logger.error(f"Error getting detailed stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/historical', methods=['GET'])
@log_api_request
def get_historical_stats():
    """Get historical network statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Get time range from query parameters
        minutes = request.args.get('minutes', 10, type=int)
        
        historical_data = mininet_mgr.stats_collector.get_historical_data(minutes)
        
        return jsonify({
            'historical_data': historical_data,
            'time_range_minutes': minutes,
            'data_points': len(historical_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting historical stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/interface/<node_id>', methods=['GET'])
@log_api_request
def get_interface_stats(node_id):
    """Get interface statistics for a specific node"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        node = mininet_mgr.net.get(node_id)
        if not node:
            return jsonify({'error': f'Node {node_id} not found'}), 404
        
        # Get current metrics to access interface stats
        metrics = mininet_mgr.get_network_metrics()
        interface_stats = metrics.get('interface_stats', {})
        
        node_stats = interface_stats.get(node_id, {})
        
        # Add real-time interface information
        enhanced_stats = {
            'node_id': node_id,
            'interface_stats': node_stats,
            'total_interfaces': len(node_stats),
            'timestamp': metrics.get('timestamp')
        }
        
        # Add additional interface details
        if hasattr(node, 'intfList'):
            interfaces = []
            for intf in node.intfList():
                if intf.name != 'lo':
                    intf_info = {
                        'name': intf.name,
                        'status': 'up' if intf.isUp() else 'down',
                        'mtu': getattr(intf, 'mtu', 'unknown')
                    }
                    
                    # Add IP and MAC for host/router interfaces
                    if hasattr(intf, 'IP'):
                        intf_info['ip'] = intf.IP()
                    if hasattr(intf, 'MAC'):
                        intf_info['mac'] = intf.MAC()
                    
                    interfaces.append(intf_info)
            
            enhanced_stats['interfaces'] = interfaces
        
        return jsonify(enhanced_stats)
        
    except Exception as e:
        logger.error(f"Error getting interface stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/flows/<switch_id>', methods=['GET'])
@log_api_request
def get_switch_flows(switch_id):
    """Get flow statistics for a specific switch"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running or not mininet_mgr.net:
            return jsonify({'error': 'Network not running'}), 400
        
        # Check if switch exists
        switch = mininet_mgr.net.get(switch_id)
        if not switch:
            return jsonify({'error': f'Switch {switch_id} not found'}), 404
        
        # Get flow statistics
        flow_stats = mininet_mgr.get_flow_stats()
        switch_flows = flow_stats.get(switch_id, {})
        
        # Get detailed flow information using OVS commands
        import subprocess
        try:
            # Get detailed flow table
            result = subprocess.run(
                ['ovs-ofctl', 'dump-flows', switch_id, '-O', 'OpenFlow13'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                detailed_flows = []
                for line in result.stdout.strip().split('\n'):
                    if 'cookie=' in line:
                        detailed_flows.append(line.strip())
                switch_flows['detailed_flows'] = detailed_flows
            
            # Get port statistics
            port_result = subprocess.run(
                ['ovs-ofctl', 'dump-ports', switch_id, '-O', 'OpenFlow13'],
                capture_output=True, text=True, timeout=5
            )
            
            if port_result.returncode == 0:
                switch_flows['port_stats'] = port_result.stdout.strip()
                
        except Exception as e:
            switch_flows['ovs_error'] = str(e)
        
        return jsonify({
            'switch_id': switch_id,
            'flows': switch_flows,
            'timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None
        })
        
    except Exception as e:
        logger.error(f"Error getting switch flows: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/bandwidth', methods=['GET'])
@log_api_request
def get_bandwidth_stats():
    """Get bandwidth utilization statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get current metrics
        metrics = mininet_mgr.get_network_metrics()
        
        # Get historical data for bandwidth trends
        historical_data = mininet_mgr.stats_collector.get_historical_data(30)
        
        # Calculate bandwidth statistics
        bandwidth_values = [data['bandwidth_mbps'] for data in historical_data if 'bandwidth_mbps' in data]
        
        bandwidth_stats = {
            'current_bandwidth_mbps': metrics.get('bandwidth_mbps', 0),
            'average_bandwidth_mbps': sum(bandwidth_values) / len(bandwidth_values) if bandwidth_values else 0,
            'max_bandwidth_mbps': max(bandwidth_values) if bandwidth_values else 0,
            'min_bandwidth_mbps': min(bandwidth_values) if bandwidth_values else 0,
            'network_utilization': metrics.get('network_utilization', 0),
            'total_bytes': metrics.get('total_bytes', 0),
            'timestamp': metrics.get('timestamp')
        }
        
        return jsonify(bandwidth_stats)
        
    except Exception as e:
        logger.error(f"Error getting bandwidth stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/latency', methods=['GET'])
@log_api_request
def get_latency_stats():
    """Get latency statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get current metrics
        metrics = mininet_mgr.get_network_metrics()
        
        # Get historical data for latency trends
        historical_data = mininet_mgr.stats_collector.get_historical_data(30)
        
        # Calculate latency statistics
        latency_values = [data['latency_ms'] for data in historical_data if 'latency_ms' in data]
        
        latency_stats = {
            'current_latency_ms': metrics.get('latency_ms', 0),
            'average_latency_ms': sum(latency_values) / len(latency_values) if latency_values else 0,
            'max_latency_ms': max(latency_values) if latency_values else 0,
            'min_latency_ms': min(latency_values) if latency_values else 0,
            'jitter_ms': max(latency_values) - min(latency_values) if len(latency_values) > 1 else 0,
            'timestamp': metrics.get('timestamp')
        }
        
        return jsonify(latency_stats)
        
    except Exception as e:
        logger.error(f"Error getting latency stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/errors', methods=['GET'])
@log_api_request
def get_error_stats():
    """Get error and dropped packet statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        
        if not mininet_mgr.is_running:
            return jsonify({'error': 'Network not running'}), 400
        
        # Get current metrics
        metrics = mininet_mgr.get_network_metrics()
        
        error_stats = {
            'total_errors': metrics.get('total_errors', 0),
            'total_dropped': metrics.get('total_dropped', 0),
            'error_rate': 0,
            'drop_rate': 0,
            'interface_details': {},
            'timestamp': metrics.get('timestamp')
        }
        
        # Calculate error rates
        total_packets = metrics.get('packets_transferred', 0)
        if total_packets > 0:
            error_stats['error_rate'] = (metrics.get('total_errors', 0) / total_packets) * 100
            error_stats['drop_rate'] = (metrics.get('total_dropped', 0) / total_packets) * 100
        
        # Add per-interface error details
        interface_stats = metrics.get('interface_stats', {})
        for node_id, interfaces in interface_stats.items():
            for intf_name, intf_stats in interfaces.items():
                error_stats['interface_details'][f"{node_id}-{intf_name}"] = {
                    'rx_errors': intf_stats.get('rx_errors', 0),
                    'tx_errors': intf_stats.get('tx_errors', 0),
                    'rx_dropped': intf_stats.get('rx_dropped', 0),
                    'tx_dropped': intf_stats.get('tx_dropped', 0)
                }
        
        return jsonify(error_stats)
        
    except Exception as e:
        logger.error(f"Error getting error stats: {e}")
        return jsonify({'error': str(e)}), 500

@stats_bp.route('/reset', methods=['POST'])
@log_api_request
def reset_statistics():
    """Reset all statistics"""
    try:
        mininet_mgr = get_mininet_manager()
        mininet_mgr.stats_collector.reset_stats()
        
        return jsonify({
            'success': True,
            'message': 'Statistics reset successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resetting statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@stats_bp.route('/export', methods=['GET'])
@log_api_request
def export_statistics():
    """Export statistics data"""
    try:
        mininet_mgr = get_mininet_manager()
        
        export_format = request.args.get('format', 'json')
        minutes = request.args.get('minutes', 60, type=int)
        
        # Get historical data
        historical_data = mininet_mgr.stats_collector.get_historical_data(minutes)
        
        # Get current detailed stats
        current_stats = mininet_mgr.get_network_metrics() if mininet_mgr.is_running else {}
        
        export_data = {
            'export_timestamp': mininet_mgr.stats_collector.last_collection_time.isoformat() if mininet_mgr.stats_collector.last_collection_time else None,
            'time_range_minutes': minutes,
            'current_stats': current_stats,
            'historical_data': historical_data,
            'network_status': {
                'running': mininet_mgr.is_running,
                'controller_running': mininet_mgr.ryu_controller.is_running,
                'uptime': mininet_mgr.stats_collector.get_uptime()
            }
        }
        
        if export_format == 'json':
            return jsonify(export_data)
        
        elif export_format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            
            if historical_data:
                fieldnames = list(historical_data[0].keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(historical_data)
            
            csv_data = output.getvalue()
            output.close()
            
            return csv_data, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=network_stats.csv'
            }
        
        else:
            return jsonify({'error': f'Unsupported format: {export_format}'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting statistics: {e}")
        return jsonify({'error': str(e)}), 500