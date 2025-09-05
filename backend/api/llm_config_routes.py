"""
LLM Configuration API Routes
Handles CRUD operations for LLM configurations and active LLM selection
"""

from flask import Blueprint, jsonify, request
from utils.logger import setup_logger, log_api_request
from database.llm_config_service import get_llm_config_service
from database.models import LLMConfigurationModel
from core.llm.llm_factory import LLMFactory

logger = setup_logger(__name__)
llm_config_bp = Blueprint('llm_config', __name__)


@llm_config_bp.route('/configurations', methods=['GET'])
@log_api_request
def get_all_configurations():
    """Get all LLM configurations"""
    try:
        service = get_llm_config_service()
        configs = service.get_all_configs()
        
        return jsonify({
            'success': True,
            'configurations': [config.to_json_dict() for config in configs],
            'count': len(configs)
        })
        
    except Exception as e:
        logger.error(f"Error getting LLM configurations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations/<config_id>', methods=['GET'])
@log_api_request
def get_configuration(config_id):
    """Get a specific LLM configuration by ID"""
    try:
        service = get_llm_config_service()
        config = service.get_config(config_id)
        
        if config:
            return jsonify({
                'success': True,
                'configuration': config.to_json_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting LLM configuration {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations', methods=['POST'])
@log_api_request
def create_configuration():
    """Create a new LLM configuration"""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['name', 'service_type', 'model_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate service type
        valid_service_types = ['ollama', 'openai', 'gemini', 'claude']
        if data['service_type'] not in valid_service_types:
            return jsonify({
                'success': False,
                'error': f'Invalid service type. Must be one of: {valid_service_types}'
            }), 400
        
        service = get_llm_config_service()
        config = service.create_config(data)
        
        if config:
            return jsonify({
                'success': True,
                'configuration': config.to_json_dict(),
                'message': 'Configuration created successfully'
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create configuration'
            }), 400
            
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations/<config_id>', methods=['PUT'])
@log_api_request
def update_configuration(config_id):
    """Update an LLM configuration"""
    try:
        data = request.get_json() or {}
        
        # Validate service type if provided
        if 'service_type' in data:
            valid_service_types = ['ollama', 'openai', 'gemini', 'claude']
            if data['service_type'] not in valid_service_types:
                return jsonify({
                    'success': False,
                    'error': f'Invalid service type. Must be one of: {valid_service_types}'
                }), 400
        
        service = get_llm_config_service()
        config = service.update_config(config_id, data)
        
        if config:
            return jsonify({
                'success': True,
                'configuration': config.to_json_dict(),
                'message': 'Configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found or update failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error updating LLM configuration {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations/<config_id>', methods=['DELETE'])
@log_api_request
def delete_configuration(config_id):
    """Delete an LLM configuration"""
    try:
        service = get_llm_config_service()
        success = service.delete_config(config_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Configuration deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found or deletion failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting LLM configuration {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations/<config_id>/test', methods=['POST'])
@log_api_request
def test_configuration(config_id):
    """Test an LLM configuration"""
    try:
        service = get_llm_config_service()
        result = service.test_config(config_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error testing LLM configuration {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/active', methods=['GET'])
@log_api_request
def get_active_configuration():
    """Get the currently active LLM configuration"""
    try:
        service = get_llm_config_service()
        config = service.get_active_config()
        
        if config:
            return jsonify({
                'success': True,
                'configuration': config.to_json_dict()
            })
        else:
            return jsonify({
                'success': True,
                'configuration': None,
                'message': 'No active configuration found'
            })
            
    except Exception as e:
        logger.error(f"Error getting active LLM configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/active', methods=['POST'])
@log_api_request
def set_active_configuration():
    """Set the active LLM configuration"""
    try:
        data = request.get_json() or {}
        config_id = data.get('config_id')
        
        if not config_id:
            return jsonify({
                'success': False,
                'error': 'config_id is required'
            }), 400
        
        service = get_llm_config_service()
        success = service.set_active_config(config_id)
        
        if success:
            # Get the updated configuration
            config = service.get_config(config_id)
            return jsonify({
                'success': True,
                'configuration': config.to_json_dict() if config else None,
                'message': 'Active configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Configuration not found or activation failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error setting active LLM configuration: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/service-types', methods=['GET'])
@log_api_request
def get_service_types():
    """Get available LLM service types and their availability"""
    try:
        # Get available services from factory
        available_services = LLMFactory.get_available_services()
        
        # Get service type information
        service_types = {
            'ollama': {
                'name': 'Ollama',
                'description': 'Local Ollama service for running models locally',
                'requires_api_key': False,
                'available': available_services.get('ollama', False)
            },
            'openai': {
                'name': 'OpenAI',
                'description': 'OpenAI API service (GPT models)',
                'requires_api_key': True,
                'available': available_services.get('openai', False)
            },
            'gemini': {
                'name': 'Google Gemini',
                'description': 'Google Gemini API service',
                'requires_api_key': True,
                'available': available_services.get('gemini', False)
            },
            'claude': {
                'name': 'Anthropic Claude',
                'description': 'Anthropic Claude API service',
                'requires_api_key': True,
                'available': available_services.get('claude', False)
            }
        }
        
        return jsonify({
            'success': True,
            'service_types': service_types
        })
        
    except Exception as e:
        logger.error(f"Error getting service types: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_config_bp.route('/configurations/by-service/<service_type>', methods=['GET'])
@log_api_request
def get_configurations_by_service_type(service_type):
    """Get all configurations for a specific service type"""
    try:
        service = get_llm_config_service()
        configs = service.get_configs_by_service_type(service_type)
        
        return jsonify({
            'success': True,
            'configurations': [config.to_json_dict() for config in configs],
            'count': len(configs),
            'service_type': service_type
        })
        
    except Exception as e:
        logger.error(f"Error getting LLM configurations for service type {service_type}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
