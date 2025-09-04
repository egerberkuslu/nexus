"""
Database Services for MongoDB Operations
Provides high-level CRUD operations for topologies and configurations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from .connection import get_database
from .models import TopologyModel, ConfigurationModel, SimulationSnapshotModel
from .models import validate_topology_data, validate_configuration_data, validate_snapshot_data
from .models import sanitize_topology_for_storage, sanitize_configuration_for_storage, sanitize_snapshot_for_storage
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TopologyService:
    """Service class for topology CRUD operations"""
    
    def __init__(self):
        self.db_manager = get_database()
        self.collection_name = 'topologies'
    
    def save_topology(self, name: str, description: str, topology_data: Dict[str, Any], 
                     topology_type: str = 'custom', metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Save a topology to the database
        
        Args:
            name: Unique name for the topology
            description: Description of the topology
            topology_data: Complete topology data from API
            topology_type: Type of topology ('custom', 'predefined', 'simple')
            metadata: Additional metadata
            
        Returns:
            str: ID of saved topology or None if failed
        """
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            # Validate topology data
            if not validate_topology_data(topology_data):
                logger.error("Invalid topology data structure")
                return None
            
            # Sanitize data for storage
            sanitized_data = sanitize_topology_for_storage(topology_data)
            
            # Create topology model
            now = datetime.utcnow()
            topology = TopologyModel(
                name=name,
                description=description,
                topology_data=sanitized_data,
                topology_type=topology_type,
                metadata=metadata or {},
                created_at=now,
                updated_at=now
            )
            
            # Insert into database
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.insert_one(topology.to_dict())
            
            logger.info(f"Topology '{name}' saved successfully with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except DuplicateKeyError:
            logger.error(f"Topology with name '{name}' already exists")
            return None
        except Exception as e:
            logger.error(f"Error saving topology: {e}")
            return None
    
    def get_topology(self, topology_id: str) -> Optional[TopologyModel]:
        """Get a topology by ID"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"_id": ObjectId(topology_id)})
            
            if result:
                return TopologyModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting topology: {e}")
            return None
    
    def get_topology_by_name(self, name: str) -> Optional[TopologyModel]:
        """Get a topology by name"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"name": name})
            
            if result:
                return TopologyModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting topology by name: {e}")
            return None
    
    def list_topologies(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """List all saved topologies with pagination"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return []
            
            collection = self.db_manager.get_collection(self.collection_name)
            cursor = collection.find({}, {
                'name': 1, 
                'description': 1, 
                'topology_type': 1,
                'created_at': 1,
                'updated_at': 1,
                'metadata': 1
            }).sort('updated_at', -1).skip(skip).limit(limit)
            
            topologies = []
            for doc in cursor:
                topology_summary = {
                    'id': str(doc['_id']),
                    'name': doc['name'],
                    'description': doc['description'],
                    'topology_type': doc['topology_type'],
                    'created_at': doc['created_at'].isoformat(),
                    'updated_at': doc['updated_at'].isoformat(),
                    'metadata': doc.get('metadata', {})
                }
                topologies.append(topology_summary)
            
            return topologies
            
        except Exception as e:
            logger.error(f"Error listing topologies: {e}")
            return []
    
    def update_topology(self, topology_id: str, name: str = None, description: str = None,
                       topology_data: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing topology"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            update_data = {'updated_at': datetime.utcnow()}
            
            if name is not None:
                update_data['name'] = name
            if description is not None:
                update_data['description'] = description
            if topology_data is not None:
                if not validate_topology_data(topology_data):
                    logger.error("Invalid topology data structure")
                    return False
                update_data['topology_data'] = sanitize_topology_for_storage(topology_data)
            if metadata is not None:
                update_data['metadata'] = metadata
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(topology_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Topology {topology_id} updated successfully")
                return True
            else:
                logger.warning(f"No topology found with ID {topology_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating topology: {e}")
            return False
    
    def delete_topology(self, topology_id: str) -> bool:
        """Delete a topology by ID"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.delete_one({"_id": ObjectId(topology_id)})
            
            if result.deleted_count > 0:
                logger.info(f"Topology {topology_id} deleted successfully")
                return True
            else:
                logger.warning(f"No topology found with ID {topology_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting topology: {e}")
            return False

class ConfigurationService:
    """Service class for configuration CRUD operations"""
    
    def __init__(self):
        self.db_manager = get_database()
        self.collection_name = 'configurations'
    
    def save_configuration(self, name: str, description: str, device_type: str,
                          configuration_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Save a device configuration to the database
        
        Args:
            name: Unique name for the configuration
            description: Description of the configuration
            device_type: Type of device ('host', 'switch', 'router', 'controller')
            configuration_data: Configuration data
            metadata: Additional metadata
            
        Returns:
            str: ID of saved configuration or None if failed
        """
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            # Validate configuration data
            if not validate_configuration_data(device_type, configuration_data):
                logger.warning(f"Configuration validation failed for {device_type}")
                # Continue anyway - validation might be too strict
            
            # Sanitize data for storage
            sanitized_data = sanitize_configuration_for_storage(configuration_data)
            
            # Create configuration model
            now = datetime.utcnow()
            configuration = ConfigurationModel(
                name=name,
                description=description,
                device_type=device_type,
                configuration_data=sanitized_data,
                metadata=metadata or {},
                created_at=now,
                updated_at=now
            )
            
            # Insert into database
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.insert_one(configuration.to_dict())
            
            logger.info(f"Configuration '{name}' saved successfully with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except DuplicateKeyError:
            logger.error(f"Configuration with name '{name}' already exists")
            return None
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return None
    
    def get_configuration(self, config_id: str) -> Optional[ConfigurationModel]:
        """Get a configuration by ID"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"_id": ObjectId(config_id)})
            
            if result:
                return ConfigurationModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            return None
    
    def get_configuration_by_name(self, name: str) -> Optional[ConfigurationModel]:
        """Get a configuration by name"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"name": name})
            
            if result:
                return ConfigurationModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting configuration by name: {e}")
            return None
    
    def list_configurations(self, device_type: str = None, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """List configurations with optional device type filter"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return []
            
            # Build query filter
            query = {}
            if device_type:
                query['device_type'] = device_type
            
            collection = self.db_manager.get_collection(self.collection_name)
            cursor = collection.find(query, {
                'name': 1,
                'description': 1,
                'device_type': 1,
                'created_at': 1,
                'updated_at': 1,
                'metadata': 1
            }).sort('updated_at', -1).skip(skip).limit(limit)
            
            configurations = []
            for doc in cursor:
                config_summary = {
                    'id': str(doc['_id']),
                    'name': doc['name'],
                    'description': doc['description'],
                    'device_type': doc['device_type'],
                    'created_at': doc['created_at'].isoformat(),
                    'updated_at': doc['updated_at'].isoformat(),
                    'metadata': doc.get('metadata', {})
                }
                configurations.append(config_summary)
            
            return configurations
            
        except Exception as e:
            logger.error(f"Error listing configurations: {e}")
            return []
    
    def update_configuration(self, config_id: str, name: str = None, description: str = None,
                           configuration_data: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing configuration"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            update_data = {'updated_at': datetime.utcnow()}
            
            if name is not None:
                update_data['name'] = name
            if description is not None:
                update_data['description'] = description
            if configuration_data is not None:
                update_data['configuration_data'] = sanitize_configuration_for_storage(configuration_data)
            if metadata is not None:
                update_data['metadata'] = metadata
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(config_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Configuration {config_id} updated successfully")
                return True
            else:
                logger.warning(f"No configuration found with ID {config_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def delete_configuration(self, config_id: str) -> bool:
        """Delete a configuration by ID"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.delete_one({"_id": ObjectId(config_id)})
            
            if result.deleted_count > 0:
                logger.info(f"Configuration {config_id} deleted successfully")
                return True
            else:
                logger.warning(f"No configuration found with ID {config_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting configuration: {e}")
            return False

# Global service instances
topology_service = TopologyService()
configuration_service = ConfigurationService()

def get_topology_service() -> TopologyService:
    """Get the topology service instance"""
    return topology_service

def get_configuration_service() -> ConfigurationService:
    """Get the configuration service instance"""
    return configuration_service

class SimulationSnapshotService:
    """Service class for simulation snapshot CRUD operations"""
    
    def __init__(self):
        self.db_manager = get_database()
        self.collection_name = 'simulation_snapshots'
    
    def save_snapshot(self, name: str, description: str, snapshot_data: Dict[str, Any], 
                     snapshot_type: str = 'full', metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Save a simulation snapshot to the database
        
        Args:
            name: Unique name for the snapshot
            description: Description of the snapshot
            snapshot_data: Complete simulation state data
            snapshot_type: Type of snapshot ('full', 'topology_only', 'runtime_state')
            metadata: Additional metadata
            
        Returns:
            str: ID of saved snapshot or None if failed
        """
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            # Validate snapshot data
            if not validate_snapshot_data(snapshot_data):
                logger.error("Invalid snapshot data structure")
                return None
            
            # Sanitize data for storage
            sanitized_data = sanitize_snapshot_for_storage(snapshot_data)
            
            # Create snapshot model
            now = datetime.utcnow()
            snapshot = SimulationSnapshotModel(
                name=name,
                description=description,
                snapshot_data=sanitized_data,
                snapshot_type=snapshot_type,
                metadata=metadata or {},
                created_at=now,
                updated_at=now
            )
            
            # Insert into database
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.insert_one(snapshot.to_dict())
            
            logger.info(f"Simulation snapshot '{name}' saved successfully with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except DuplicateKeyError:
            logger.error(f"Snapshot with name '{name}' already exists")
            return None
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
            return None
    
    def get_snapshot(self, snapshot_id: str) -> Optional[SimulationSnapshotModel]:
        """Get a snapshot by ID"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"_id": ObjectId(snapshot_id)})
            
            if result:
                return SimulationSnapshotModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting snapshot: {e}")
            return None
    
    def get_snapshot_by_name(self, name: str) -> Optional[SimulationSnapshotModel]:
        """Get a snapshot by name"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return None
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.find_one({"name": name})
            
            if result:
                return SimulationSnapshotModel.from_dict(result)
            return None
            
        except Exception as e:
            logger.error(f"Error getting snapshot by name: {e}")
            return None
    
    def list_snapshots(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """List all saved snapshots with pagination"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return []
            
            collection = self.db_manager.get_collection(self.collection_name)
            cursor = collection.find({}, {
                'name': 1, 
                'description': 1, 
                'snapshot_type': 1,
                'created_at': 1,
                'updated_at': 1,
                'metadata': 1
            }).sort('updated_at', -1).skip(skip).limit(limit)
            
            snapshots = []
            for doc in cursor:
                snapshot_summary = {
                    'id': str(doc['_id']),
                    'name': doc['name'],
                    'description': doc['description'],
                    'snapshot_type': doc['snapshot_type'],
                    'created_at': doc['created_at'].isoformat(),
                    'updated_at': doc['updated_at'].isoformat(),
                    'metadata': doc.get('metadata', {})
                }
                snapshots.append(snapshot_summary)
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Error listing snapshots: {e}")
            return []
    
    def update_snapshot(self, snapshot_id: str, name: str = None, description: str = None, 
                       snapshot_data: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> bool:
        """Update a snapshot"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            update_data = {'updated_at': datetime.utcnow()}
            
            if name is not None:
                update_data['name'] = name
            if description is not None:
                update_data['description'] = description
            if metadata is not None:
                update_data['metadata'] = metadata
            if snapshot_data is not None:
                if validate_snapshot_data(snapshot_data):
                    update_data['snapshot_data'] = sanitize_snapshot_for_storage(snapshot_data)
                else:
                    logger.error("Invalid snapshot data for update")
                    return False
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(snapshot_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating snapshot: {e}")
            return False
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        try:
            if not self.db_manager.is_connected():
                logger.error("Database not connected")
                return False
            
            collection = self.db_manager.get_collection(self.collection_name)
            result = collection.delete_one({"_id": ObjectId(snapshot_id)})
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting snapshot: {e}")
            return False

# Global service instances
topology_service = TopologyService()
configuration_service = ConfigurationService()
snapshot_service = SimulationSnapshotService()

def get_snapshot_service() -> SimulationSnapshotService:
    """Get the simulation snapshot service instance"""
    return snapshot_service
