"""
LLM API Routes
Handles LLM-based topology generation and network management
"""

from flask import Blueprint, jsonify, request, current_app
from utils.logger import setup_logger, log_api_request
from core.llm import LLMFactory, LLMManager, TopologyLLMService

logger = setup_logger(__name__)
llm_bp = Blueprint('llm', __name__)

# Global LLM service instance
_llm_service = None
_topology_llm_service = None


def get_llm_service():
    """Get or create the LLM service instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMManager()
    return _llm_service


def get_topology_llm_service():
    """Get or create the topology LLM service instance"""
    global _topology_llm_service
    if _topology_llm_service is None:
        _topology_llm_service = TopologyLLMService(get_llm_service())
    return _topology_llm_service


@llm_bp.route('/status', methods=['GET'])
@log_api_request
def get_llm_status():
    """Get LLM service status and availability"""
    try:
        llm_service = get_llm_service()
        topology_service = get_topology_llm_service()
        
        # Check available services
        available_services = LLMFactory.get_available_services()
        
        status = {
            "llm_service": llm_service.get_service_info(),
            "topology_service": topology_service.get_service_status(),
            "available_services": available_services,
            "templates": topology_service.get_available_templates()
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        return jsonify({'error': str(e)}), 500


@llm_bp.route('/switch-service', methods=['POST'])
@log_api_request
def switch_llm_service():
    """Switch to a different LLM service"""
    try:
        data = request.get_json() or {}
        service_type = data.get('service_type', 'ollama')
        service_kwargs = data.get('service_kwargs', {})
        
        llm_service = get_llm_service()
        success = llm_service.switch_service(service_type, **service_kwargs)
        
        if success:
            # Update the topology service with the new LLM service
            global _topology_llm_service
            _topology_llm_service = TopologyLLMService(llm_service)
            
            return jsonify({
                'success': True,
                'message': f'Switched to {service_type} service',
                'service_info': llm_service.get_service_info()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to switch to {service_type} service'
            }), 400
            
    except Exception as e:
        logger.error(f"Error switching LLM service: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/generate-topology', methods=['POST'])
@log_api_request
def generate_topology():
    """Generate network topology from natural language description"""
    try:
        data = request.get_json() or {}
        description = data.get('description', '')
        
        if not description:
            return jsonify({
                'success': False,
                'error': 'No description provided'
            }), 400
        
        # Get additional parameters
        parameters = data.get('parameters', {})
        
        topology_service = get_topology_llm_service()
        result = topology_service.generate_topology_from_description(description, **parameters)
        
        if result.get('success', False):
            # If successful, also create the network using the existing API
            try:
                mininet_mgr = current_app.config.get('MININET_MANAGER')
                if mininet_mgr:
                    # Stop existing network
                    mininet_mgr.stop_network()
                    
                    # Create the new topology
                    topology_config = result.get('topology_config', {})
                    create_success = mininet_mgr.create_custom_topology(topology_config.get('topology', {}))
                    
                    if create_success:
                        # Auto-start the network
                        start_success = mininet_mgr.start_network()
                        result['network_created'] = True
                        result['network_started'] = start_success
                        
                        # Update topology data
                        mininet_mgr.update_topology_data()
                        result['topology_summary'] = mininet_mgr.topology_data.get('stats', {})
                    else:
                        result['network_created'] = False
                        result['network_error'] = 'Failed to create network topology'
                        
            except Exception as network_error:
                logger.warning(f"Failed to create network from generated topology: {network_error}")
                result['network_created'] = False
                result['network_error'] = str(network_error)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error generating topology: {e}")
        return jsonify({
            'success': False,
            'error': f'Topology generation failed: {str(e)}'
        }), 500


@llm_bp.route('/generate-from-template', methods=['POST'])
@log_api_request
def generate_from_template():
    """Generate topology from a predefined template"""
    try:
        data = request.get_json() or {}
        template_name = data.get('template_name', '')
        parameters = data.get('parameters', {})
        
        if not template_name:
            return jsonify({
                'success': False,
                'error': 'No template name provided'
            }), 400
        
        topology_service = get_topology_llm_service()
        result = topology_service.generate_topology_from_template(template_name, parameters)
        
        if result.get('success', False):
            # Create the network using the existing API
            try:
                mininet_mgr = current_app.config.get('MININET_MANAGER')
                if mininet_mgr:
                    mininet_mgr.stop_network()
                    
                    topology_config = result.get('topology_config', {})
                    create_success = mininet_mgr.create_custom_topology(topology_config.get('topology', {}))
                    
                    if create_success:
                        start_success = mininet_mgr.start_network()
                        result['network_created'] = True
                        result['network_started'] = start_success
                        
                        mininet_mgr.update_topology_data()
                        result['topology_summary'] = mininet_mgr.topology_data.get('stats', {})
                    else:
                        result['network_created'] = False
                        result['network_error'] = 'Failed to create network topology'
                        
            except Exception as network_error:
                logger.warning(f"Failed to create network from template: {network_error}")
                result['network_created'] = False
                result['network_error'] = str(network_error)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error generating from template: {e}")
        return jsonify({
            'success': False,
            'error': f'Template generation failed: {str(e)}'
        }), 500


@llm_bp.route('/suggest-improvements', methods=['POST'])
@log_api_request
def suggest_improvements():
    """Suggest improvements for an existing topology"""
    try:
        data = request.get_json() or {}
        topology_config = data.get('topology_config', {})
        
        if not topology_config:
            return jsonify({
                'success': False,
                'error': 'No topology configuration provided'
            }), 400
        
        topology_service = get_topology_llm_service()
        result = topology_service.suggest_topology_improvements(topology_config)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error suggesting improvements: {e}")
        return jsonify({
            'success': False,
            'error': f'Improvement suggestions failed: {str(e)}'
        }), 500


@llm_bp.route('/chat', methods=['POST'])
@log_api_request
def chat_with_llm():
    """Chat with the LLM for general network-related questions"""
    try:
        data = request.get_json() or {}
        message = data.get('message', '')
        use_history = data.get('use_history', True)
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'No message provided'
            }), 400
        
        llm_service = get_llm_service()
        result = llm_service.generate_response(message, use_history=use_history)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in LLM chat: {e}")
        return jsonify({
            'success': False,
            'error': f'Chat failed: {str(e)}'
        }), 500


@llm_bp.route('/clear-history', methods=['POST'])
@log_api_request
def clear_chat_history():
    """Clear the LLM conversation history"""
    try:
        llm_service = get_llm_service()
        llm_service.clear_history()
        
        return jsonify({
            'success': True,
            'message': 'Chat history cleared successfully'
        })
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to clear history: {str(e)}'
        }), 500


@llm_bp.route('/history', methods=['GET'])
@log_api_request
def get_chat_history():
    """Get the LLM conversation history"""
    try:
        llm_service = get_llm_service()
        history = llm_service.get_history()
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get history: {str(e)}'
        }), 500


@llm_bp.route('/templates', methods=['GET'])
@log_api_request
def get_available_templates():
    """Get available topology templates"""
    try:
        topology_service = get_topology_llm_service()
        templates = topology_service.get_available_templates()
        
        return jsonify({
            'success': True,
            'templates': templates,
            'count': len(templates)
        })
        
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get templates: {str(e)}'
        }), 500


@llm_bp.route('/validate-topology', methods=['POST'])
@log_api_request
def validate_generated_topology():
    """Validate a generated topology configuration"""
    try:
        data = request.get_json() or {}
        topology_config = data.get('topology_config', {})
        
        if not topology_config:
            return jsonify({
                'success': False,
                'error': 'No topology configuration provided'
            }), 400
        
        # Use the LLM manager's validation
        llm_service = get_llm_service()
        validation_result = llm_service._validate_topology_config(topology_config)
        
        return jsonify({
            'success': True,
            'validation': validation_result
        })
        
    except Exception as e:
        logger.error(f"Error validating topology: {e}")
        return jsonify({
            'success': False,
            'error': f'Validation failed: {str(e)}'
        }), 500
