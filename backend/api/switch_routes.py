"""
Switch Management API Routes
Handles switch creation, configuration, and management
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request

logger = setup_logger(__name__)
switch_bp = Blueprint('switch', __name__)

def get_mininet_manager():
    """Get the Mininet manager from app config"""
    return current_app.config['MININET_MANAGER']


@switch_bp.route('/available', methods=['GET'])
@log_api_request
def get_available_switches():
    """Get list of available switch types"""
    try:
        mininet_mgr = get_mininet_manager()
        switches = mininet_mgr.get_available_switches()

        return jsonify({
            'success': True,
            'switches': switches
        })
    except Exception as e:
        logger.error(f"Error getting available switches: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@switch_bp.route('/types', methods=['GET'])
@log_api_request
def get_available_switch_types():
    """Get available switch types and their configurations"""
    try:
        mininet_mgr = get_mininet_manager()
        
        # Get available switch types from factory
        available_types = mininet_mgr.switch_factory.get_available_switches()
        switch_info = mininet_mgr.switch_factory.get_switch_info()
        
        # Build detailed information about each switch type
        types_info = {}
        for switch_type in available_types:
            capabilities = mininet_mgr.switch_factory.get_switch_capabilities(switch_type)
            info = switch_info.get(switch_type, {})
            
            types_info[switch_type] = {
                'name': capabilities.get('name', switch_type.title().replace('_', ' ')),
                'running': info.get('running', False),
                'switch_type': info.get('switch_type', switch_type),
                'supported_features': capabilities.get('supported_features', []),
                'supports_installation': capabilities.get('supports_installation', False),
                'supports_p4_programs': capabilities.get('supports_p4_programs', False),
                'supports_bridge_commands': capabilities.get('supports_bridge_commands', False),
                'supports_openflow': capabilities.get('supports_openflow', False),
                'standalone_operation': capabilities.get('standalone_operation', False),
                'status': info.get('status', {}),
                'capabilities': capabilities
            }
        
        return jsonify({
            'success': True,
            'types': available_types,
            'types_info': types_info
        })

    except Exception as e:
        logger.error(f"Error getting switch types: {e}")
        return jsonify({'error': str(e)}), 500


@switch_bp.route('/info', methods=['GET'])
@log_api_request
def get_switch_info():
    """Get information about all switches"""
    try:
        mininet_mgr = get_mininet_manager()
        switch_info = mininet_mgr.get_switch_info()

        return jsonify({
            'success': True,
            'switch_info': switch_info
        })
    except Exception as e:
        logger.error(f"Error getting switch info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/capabilities/<switch_type>', methods=['GET'])
@log_api_request
def get_switch_capabilities(switch_type):
    """Get capabilities of a specific switch type"""
    try:
        mininet_mgr = get_mininet_manager()
        capabilities = mininet_mgr.get_switch_capabilities(switch_type)

        return jsonify({
            'success': True,
            'capabilities': capabilities
        })
    except Exception as e:
        logger.error(f"Error getting switch capabilities: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/create', methods=['POST'])
@log_api_request
def create_switch():
    """Create a new switch instance"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}

        switch_type = data.get('switch_type', 'ovs')
        switch_id = data.get('switch_id', f's{len(mininet_mgr.get_switch_info()) + 1}')
        kwargs = data.get('config', {})

        success = mininet_mgr.create_switch(switch_type, switch_id, **kwargs)

        if success:
            return jsonify({
                'success': True,
                'message': f'Switch {switch_id} of type {switch_type} created successfully',
                'switch_id': switch_id
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to create switch {switch_id}'
            }), 400

    except Exception as e:
        logger.error(f"Error creating switch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/status/<switch_type>', methods=['GET'])
@log_api_request
def get_switch_status(switch_type):
    """Get status of a specific switch type"""
    try:
        mininet_mgr = get_mininet_manager()
        status = mininet_mgr.get_switch_status(switch_type)

        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting switch status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/stats/<switch_type>', methods=['GET'])
@log_api_request
def get_switch_stats(switch_type):
    """Get statistics for a specific switch type"""
    try:
        mininet_mgr = get_mininet_manager()
        stats = mininet_mgr.get_switch_stats(switch_type)

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting switch stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/port/<switch_id>/<port_name>', methods=['POST'])
@log_api_request
def configure_switch_port(switch_id, port_name):
    """Configure a port on a specific switch"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}

        config = data.get('config', {})

        success = mininet_mgr.configure_switch_port(switch_id, port_name, config)

        if success:
            return jsonify({
                'success': True,
                'message': f'Port {port_name} on switch {switch_id} configured successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to configure port {port_name} on switch {switch_id}'
            }), 400

    except Exception as e:
        logger.error(f"Error configuring switch port: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/port/<switch_id>/<port_name>', methods=['GET'])
@log_api_request
def get_port_config(switch_id, port_name):
    """Get configuration for a specific port"""
    try:
        mininet_mgr = get_mininet_manager()
        config = mininet_mgr.get_port_config(switch_id, port_name)

        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        logger.error(f"Error getting port config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/ports/<switch_id>', methods=['GET'])
@log_api_request
def list_switch_ports(switch_id):
    """List all ports on a specific switch"""
    try:
        mininet_mgr = get_mininet_manager()
        ports = mininet_mgr.list_switch_ports(switch_id)

        return jsonify({
            'success': True,
            'ports': ports
        })
    except Exception as e:
        logger.error(f"Error listing switch ports: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/install/<switch_type>', methods=['POST'])
@log_api_request
def install_switch(switch_type):
    """Install switch software if supported"""
    try:
        mininet_mgr = get_mininet_manager()
        success = mininet_mgr.install_switch(switch_type)

        if success:
            return jsonify({
                'success': True,
                'message': f'Switch type {switch_type} installed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to install switch type {switch_type}'
            }), 400

    except Exception as e:
        logger.error(f"Error installing switch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# P4-Specific Routes

@switch_bp.route('/p4/compile/<program_name>', methods=['POST'])
@log_api_request
def compile_p4_program(program_name):
    """Compile a P4 program"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}

        success, result = mininet_mgr.compile_p4_program(program_name)

        if success:
            return jsonify({
                'success': True,
                'message': f'P4 program {program_name} compiled successfully',
                'output_file': result
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to compile P4 program {program_name}',
                'details': result
            }), 400

    except Exception as e:
        logger.error(f"Error compiling P4 program: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/p4/table/<table_name>/entry', methods=['POST'])
@log_api_request
def add_p4_table_entry(table_name):
    """Add an entry to a P4 table"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}

        match_fields = data.get('match_fields', {})
        action_name = data.get('action_name', '')
        action_params = data.get('action_params', {})

        success = mininet_mgr.add_p4_table_entry(table_name, match_fields, action_name, action_params)

        if success:
            return jsonify({
                'success': True,
                'message': f'Entry added to P4 table {table_name}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to add entry to P4 table {table_name}'
            }), 400

    except Exception as e:
        logger.error(f"Error adding P4 table entry: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/p4/table/<table_name>/entries', methods=['GET'])
@log_api_request
def get_p4_table_entries(table_name):
    """Get entries from a P4 table"""
    try:
        mininet_mgr = get_mininet_manager()
        entries = mininet_mgr.get_p4_table_entries(table_name)

        return jsonify({
            'success': True,
            'entries': entries
        })
    except Exception as e:
        logger.error(f"Error getting P4 table entries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/p4/template/<program_name>', methods=['POST'])
@log_api_request
def create_p4_program_template(program_name):
    """Create a P4 program from template"""
    try:
        mininet_mgr = get_mininet_manager()
        data = request.get_json() or {}

        program_type = data.get('program_type', 'basic_forwarding')

        result = mininet_mgr.create_p4_program_template(program_name, program_type)

        return jsonify({
            'success': True,
            'message': f'P4 program template {program_name} created',
            'program_name': result
        })
    except Exception as e:
        logger.error(f"Error creating P4 program template: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@switch_bp.route('/p4/templates', methods=['GET'])
@log_api_request
def get_p4_templates():
    """Get list of available P4 program templates"""
    try:
        templates = [
            'basic_forwarding',
            'l2_forwarding',
            'l3_forwarding',
            'firewall',
            'load_balancer'
        ]

        return jsonify({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        logger.error(f"Error getting P4 templates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
