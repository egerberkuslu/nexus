"""
LLM Configuration Database Service
Handles CRUD operations for LLM configurations with encrypted API key storage
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from database.connection import get_database
from database.models import LLMConfigurationModel
from utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMConfigService:
    """Service for managing LLM configurations in MongoDB"""
    
    def __init__(self):
        self.db_manager = get_database()
        # Ensure database connection is established
        if not self.db_manager.is_connected():
            self.db_manager.connect()
        self.db = self.db_manager.db
        self.collection = self.db_manager.llm_configurations
    
    def create_config(self, config_data: Dict[str, Any]) -> Optional[LLMConfigurationModel]:
        """
        Create a new LLM configuration
        
        Args:
            config_data: Configuration data including name, service_type, model_name, etc.
            
        Returns:
            Created LLMConfigurationModel or None if failed
        """
        try:
            logger.info(f"Creating LLM configuration with data: {config_data}")
            
            # Create the model instance
            config = LLMConfigurationModel(
                name=config_data['name'],
                service_type=config_data['service_type'],
                model_name=config_data['model_name'],
                base_url=config_data.get('base_url'),
                is_active=config_data.get('is_active', False),
                metadata=config_data.get('metadata', {})
            )
            
            logger.info(f"Created model instance: {config.name}")
            
            # Set API key if provided
            if 'api_key' in config_data and config_data['api_key']:
                logger.info("Setting API key...")
                config.set_api_key(config_data['api_key'])
                logger.info("API key set successfully")
            
            # Insert into database
            logger.info("Inserting into database...")
            result = self.collection.insert_one(config.to_dict())
            config._id = result.inserted_id
            
            logger.info(f"Created LLM configuration: {config.name}")
            return config
            
        except DuplicateKeyError:
            logger.error(f"LLM configuration with name '{config_data['name']}' already exists")
            return None
        except Exception as e:
            logger.error(f"Failed to create LLM configuration: {e}")
            return None
    
    def get_config(self, config_id: str) -> Optional[LLMConfigurationModel]:
        """
        Get an LLM configuration by ID
        
        Args:
            config_id: Configuration ID
            
        Returns:
            LLMConfigurationModel or None if not found
        """
        try:
            config_doc = self.collection.find_one({'_id': ObjectId(config_id)})
            if config_doc:
                return LLMConfigurationModel.from_dict(config_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get LLM configuration {config_id}: {e}")
            return None
    
    def get_config_by_name(self, name: str) -> Optional[LLMConfigurationModel]:
        """
        Get an LLM configuration by name
        
        Args:
            name: Configuration name
            
        Returns:
            LLMConfigurationModel or None if not found
        """
        try:
            config_doc = self.collection.find_one({'name': name})
            if config_doc:
                return LLMConfigurationModel.from_dict(config_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get LLM configuration by name '{name}': {e}")
            return None
    
    def get_all_configs(self) -> List[LLMConfigurationModel]:
        """
        Get all LLM configurations
        
        Returns:
            List of LLMConfigurationModel instances
        """
        try:
            configs = []
            for config_doc in self.collection.find():
                config = LLMConfigurationModel.from_dict(config_doc)
                configs.append(config)
            return configs
            
        except Exception as e:
            logger.error(f"Failed to get all LLM configurations: {e}")
            return []
    
    def get_active_config(self) -> Optional[LLMConfigurationModel]:
        """
        Get the currently active LLM configuration
        
        Returns:
            Active LLMConfigurationModel or None if no active config
        """
        try:
            config_doc = self.collection.find_one({'is_active': True})
            if config_doc:
                return LLMConfigurationModel.from_dict(config_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active LLM configuration: {e}")
            return None
    
    def update_config(self, config_id: str, update_data: Dict[str, Any]) -> Optional[LLMConfigurationModel]:
        """
        Update an LLM configuration
        
        Args:
            config_id: Configuration ID
            update_data: Data to update
            
        Returns:
            Updated LLMConfigurationModel or None if failed
        """
        try:
            # Get existing config
            existing_config = self.get_config(config_id)
            if not existing_config:
                return None
            
            # Update fields
            if 'name' in update_data:
                existing_config.name = update_data['name']
            if 'service_type' in update_data:
                existing_config.service_type = update_data['service_type']
            if 'model_name' in update_data:
                existing_config.model_name = update_data['model_name']
            if 'base_url' in update_data:
                existing_config.base_url = update_data['base_url']
            if 'is_active' in update_data:
                existing_config.is_active = update_data['is_active']
            if 'metadata' in update_data:
                existing_config.metadata = update_data['metadata']
            
            # Update API key if provided
            if 'api_key' in update_data and update_data['api_key']:
                existing_config.set_api_key(update_data['api_key'])
            
            # Update timestamp
            existing_config.updated_at = datetime.now()
            
            # Update in database
            result = self.collection.update_one(
                {'_id': ObjectId(config_id)},
                {'$set': existing_config.to_dict()}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated LLM configuration: {existing_config.name}")
                return existing_config
            else:
                logger.warning(f"No changes made to LLM configuration: {config_id}")
                return existing_config
                
        except Exception as e:
            logger.error(f"Failed to update LLM configuration {config_id}: {e}")
            return None
    
    def delete_config(self, config_id: str) -> bool:
        """
        Delete an LLM configuration
        
        Args:
            config_id: Configuration ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = self.collection.delete_one({'_id': ObjectId(config_id)})
            if result.deleted_count > 0:
                logger.info(f"Deleted LLM configuration: {config_id}")
                return True
            else:
                logger.warning(f"LLM configuration not found: {config_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete LLM configuration {config_id}: {e}")
            return False
    
    def set_active_config(self, config_id: str) -> bool:
        """
        Set a configuration as active (deactivates all others)
        
        Args:
            config_id: Configuration ID to activate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, deactivate all configurations
            self.collection.update_many(
                {'is_active': True},
                {'$set': {'is_active': False}}
            )
            
            # Then activate the specified configuration
            result = self.collection.update_one(
                {'_id': ObjectId(config_id)},
                {'$set': {'is_active': True, 'updated_at': datetime.now()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Set active LLM configuration: {config_id}")
                return True
            else:
                logger.warning(f"LLM configuration not found: {config_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set active LLM configuration {config_id}: {e}")
            return False
    
    def test_config(self, config_id: str) -> Dict[str, Any]:
        """
        Test an LLM configuration by creating a temporary service instance
        
        Args:
            config_id: Configuration ID to test
            
        Returns:
            Test result with success status and details
        """
        try:
            config = self.get_config(config_id)
            if not config:
                return {
                    'success': False,
                    'error': 'Configuration not found'
                }
            
            # Import here to avoid circular imports
            from core.llm.llm_factory import LLMFactory
            
            # Create service instance with decrypted API key
            api_key = config.get_api_key()
            
            # Prepare service kwargs based on service type
            if config.service_type == 'ollama':
                service_kwargs = {
                    'model_name': config.model_name,
                    'base_url': config.base_url or 'http://localhost:11434'
                }
            elif config.service_type in ['openai', 'gemini', 'claude']:
                service_kwargs = {
                    'model_name': config.model_name,
                    'api_key': api_key
                }
            else:
                service_kwargs = {
                    'model_name': config.model_name,
                    'base_url': config.base_url
                }
                if api_key:
                    service_kwargs['api_key'] = api_key
            
            # Create and test the service
            service = LLMFactory.create_service(config.service_type, **service_kwargs)
            is_available = service.is_available()
            
            return {
                'success': True,
                'available': is_available,
                'service_type': config.service_type,
                'model_name': config.model_name,
                'message': 'Service is available' if is_available else 'Service is not available'
            }
            
        except Exception as e:
            logger.error(f"Failed to test LLM configuration {config_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_configs_by_service_type(self, service_type: str) -> List[LLMConfigurationModel]:
        """
        Get all configurations for a specific service type
        
        Args:
            service_type: Service type (ollama, openai, gemini)
            
        Returns:
            List of LLMConfigurationModel instances
        """
        try:
            configs = []
            for config_doc in self.collection.find({'service_type': service_type}):
                config = LLMConfigurationModel.from_dict(config_doc)
                configs.append(config)
            return configs
            
        except Exception as e:
            logger.error(f"Failed to get LLM configurations for service type {service_type}: {e}")
            return []


# Global service instance
_llm_config_service = None


def get_llm_config_service() -> LLMConfigService:
    """Get the global LLM configuration service instance"""
    global _llm_config_service
    if _llm_config_service is None:
        _llm_config_service = LLMConfigService()
    return _llm_config_service
