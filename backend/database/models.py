"""
Database Models for MongoDB Collections
Defines data structures and validation for topology and configuration data
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from bson import ObjectId
from utils.logger import setup_logger

logger = setup_logger(__name__)
import json

@dataclass
class TopologyModel:
    """Model for storing network topology data"""
    name: str
    description: str
    topology_data: Dict[str, Any]  # Contains nodes, links, controllers, stats
    topology_type: str  # 'custom', 'predefined', 'simple'
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    _id: Optional[ObjectId] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopologyModel':
        """Create TopologyModel from dictionary"""
        # Handle ObjectId conversion
        if '_id' in data and isinstance(data['_id'], str):
            data['_id'] = ObjectId(data['_id'])
        
        # Handle datetime conversion
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert TopologyModel to dictionary for MongoDB storage"""
        data = asdict(self)
        
        # Handle ObjectId serialization
        if self._id:
            data['_id'] = self._id
        else:
            data.pop('_id', None)
            
        # Ensure datetime objects are properly formatted
        data['created_at'] = self.created_at
        data['updated_at'] = self.updated_at
        
        return data
    
    def to_json_dict(self) -> Dict[str, Any]:
        """Convert TopologyModel to JSON-serializable dictionary"""
        data = self.to_dict()
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in data and data['_id']:
            data['_id'] = str(data['_id'])
            
        # Convert datetime to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        
        return data

@dataclass
class SimulationSnapshotModel:
    """Model for storing complete Mininet simulation snapshots"""
    name: str
    description: str
    snapshot_data: Dict[str, Any]  # Complete simulation state
    snapshot_type: str  # 'full', 'topology_only', 'runtime_state'
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    _id: Optional[ObjectId] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimulationSnapshotModel':
        """Create SimulationSnapshotModel from dictionary"""
        # Handle ObjectId conversion
        if '_id' in data and isinstance(data['_id'], str):
            data['_id'] = ObjectId(data['_id'])
        
        # Handle datetime conversion
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SimulationSnapshotModel to dictionary for MongoDB storage"""
        data = asdict(self)
        
        # Handle ObjectId serialization
        if self._id:
            data['_id'] = self._id
        else:
            data.pop('_id', None)
            
        # Ensure datetime objects are properly formatted
        data['created_at'] = self.created_at
        data['updated_at'] = self.updated_at
        
        return data
    
    def to_json_dict(self) -> Dict[str, Any]:
        """Convert SimulationSnapshotModel to JSON-serializable dictionary"""
        data = asdict(self)
        
        # Convert ObjectId to string
        if self._id:
            data['id'] = str(self._id)
        data.pop('_id', None)
        
        # Convert datetime to ISO format
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        
        return data

@dataclass
class ConfigurationModel:
    """Model for storing device configuration data"""
    name: str
    description: str
    device_type: str  # 'host', 'switch', 'router', 'controller'
    configuration_data: Dict[str, Any]  # Device-specific configuration
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    _id: Optional[ObjectId] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationModel':
        """Create ConfigurationModel from dictionary"""
        # Handle ObjectId conversion
        if '_id' in data and isinstance(data['_id'], str):
            data['_id'] = ObjectId(data['_id'])
            
        # Handle datetime conversion
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ConfigurationModel to dictionary for MongoDB storage"""
        data = asdict(self)
        
        # Handle ObjectId serialization
        if self._id:
            data['_id'] = self._id
        else:
            data.pop('_id', None)
            
        # Ensure datetime objects are properly formatted
        data['created_at'] = self.created_at
        data['updated_at'] = self.updated_at
        
        return data
    
    def to_json_dict(self) -> Dict[str, Any]:
        """Convert ConfigurationModel to JSON-serializable dictionary"""
        data = self.to_dict()
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in data and data['_id']:
            data['_id'] = str(data['_id'])
            
        # Convert datetime to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        
        return data

# Validation functions
def validate_topology_data(topology_data: Dict[str, Any]) -> bool:
    """Validate topology data structure including controller and switch type attributes"""
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
    
    # Required fields - stats and controllers are optional
    required_fields = ['nodes', 'links']
    
    for field in required_fields:
        if field not in topology_data:
            logger.error(f"Missing required field: {field}")
            return False
    
    # Validate nodes structure
    if not isinstance(topology_data['nodes'], list):
        logger.error("Nodes must be a list")
        return False
    
    for i, node in enumerate(topology_data['nodes']):
        if not isinstance(node, dict):
            logger.error(f"Node {i} must be a dictionary")
            return False
        if 'id' not in node:
            logger.error(f"Node {i} missing 'id' field")
            return False
        if 'type' not in node:
            logger.error(f"Node {i} missing 'type' field")
            return False
        
        # Validate controller-specific attributes
        if node.get('type') == 'controller':
            controller_type = node.get('controller_type')
            if controller_type and controller_type not in ['ryu', 'pox', 'osken', 'opendaylight']:
                logger.warning(f"Node {i} has unsupported controller_type: {controller_type}")
        
        # Validate switch-specific attributes
        elif node.get('type') == 'switch':
            switch_type = node.get('switch_type')
            if switch_type and switch_type not in ['ovs', 'linux_bridge', 'p4']:
                logger.warning(f"Node {i} has unsupported switch_type: {switch_type}")
    
    # Validate links structure
    if not isinstance(topology_data['links'], list):
        logger.error("Links must be a list")
        return False
    
    for i, link in enumerate(topology_data['links']):
        if not isinstance(link, dict):
            logger.error(f"Link {i} must be a dictionary")
            return False
        if 'source' not in link:
            logger.error(f"Link {i} missing 'source' field")
            return False
        if 'target' not in link:
            logger.error(f"Link {i} missing 'target' field")
            return False
    
    # Optional fields validation
    if 'controllers' in topology_data and not isinstance(topology_data['controllers'], list):
        logger.error("Controllers must be a list")
        return False
    
    if 'stats' in topology_data and not isinstance(topology_data['stats'], dict):
        logger.error("Stats must be a dictionary")
        return False
    
    # Validate metadata for controller/switch type information
    if 'metadata' in topology_data:
        metadata = topology_data['metadata']
        if 'supported_controller_types' in metadata:
            logger.info(f"Topology includes controller type metadata: {metadata['supported_controller_types']}")
        if 'supported_switch_types' in metadata:
            logger.info(f"Topology includes switch type metadata: {metadata['supported_switch_types']}")
    
    logger.info("Topology data validation passed")
    return True

def validate_configuration_data(device_type: str, config_data: Dict[str, Any]) -> bool:
    """Validate configuration data based on device type"""
    
    if device_type == 'host':
        # Host configuration validation
        return True  # Basic validation - could be expanded
    
    elif device_type == 'switch':
        # Switch configuration validation
        required_fields = ['openflow_version', 'controller_ip', 'controller_port']
        return all(field in config_data for field in required_fields)
    
    elif device_type == 'router':
        # Router configuration validation
        required_fields = ['interfaces', 'routing_protocol']
        return all(field in config_data for field in required_fields)
    
    elif device_type == 'controller':
        # Controller configuration validation
        required_fields = ['type', 'port', 'ip']
        return all(field in config_data for field in required_fields)
    
    return False

# Helper functions for data transformation
def sanitize_topology_for_storage(topology_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize topology data for MongoDB storage while preserving controller and switch type attributes"""
    # Remove any non-serializable objects and clean up data
    sanitized = {}
    
    for key, value in topology_data.items():
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            sanitized[key] = value
        else:
            # Convert to string representation for non-standard types
            sanitized[key] = str(value)
    
    # Add default values for optional fields if missing
    if 'controllers' not in sanitized:
        sanitized['controllers'] = []
    
    if 'stats' not in sanitized:
        sanitized['stats'] = {}
    
    # Ensure controller and switch type attributes are preserved in nodes
    if 'nodes' in sanitized:
        for node in sanitized['nodes']:
            if node.get('type') == 'controller':
                # Ensure controller type attributes are present
                if 'controller_type' not in node:
                    node['controller_type'] = 'ryu'  # Default
                if 'app' not in node:
                    node['app'] = 'simple_switch_13'  # Default
                if 'protocol' not in node:
                    node['protocol'] = 'OpenFlow'  # Default
                if 'version' not in node:
                    node['version'] = '1.3'  # Default
                if 'port' not in node:
                    node['port'] = 6633  # Default
            elif node.get('type') == 'switch':
                # Ensure switch type attributes are present
                if 'switch_type' not in node:
                    node['switch_type'] = 'ovs'  # Default
                if 'dpid' not in node:
                    node['dpid'] = 'auto'  # Default
                if 'openflow_version' not in node:
                    node['openflow_version'] = '1.3'  # Default
    
    # Ensure metadata includes controller and switch type information
    if 'metadata' not in sanitized:
        sanitized['metadata'] = {}
    
    # Add supported types to metadata if not present
    if 'supported_controller_types' not in sanitized['metadata']:
        sanitized['metadata']['supported_controller_types'] = ['ryu', 'pox', 'osken', 'opendaylight']
    if 'supported_switch_types' not in sanitized['metadata']:
        sanitized['metadata']['supported_switch_types'] = ['ovs', 'linux_bridge', 'p4']
    
    return sanitized

def validate_snapshot_data(snapshot_data: Dict[str, Any]) -> bool:
    """Validate simulation snapshot data structure"""
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
    
    # Required top-level fields
    required_fields = ['mininet_state', 'controller_state', 'network_stats']
    
    for field in required_fields:
        if field not in snapshot_data:
            logger.error(f"Missing required snapshot field: {field}")
            return False
    
    # Validate mininet_state structure
    mininet_state = snapshot_data['mininet_state']
    if not isinstance(mininet_state, dict):
        logger.error("mininet_state must be a dictionary")
        return False
    
    required_mininet_fields = ['topology_data', 'is_running', 'node_positions']
    for field in required_mininet_fields:
        if field not in mininet_state:
            logger.error(f"Missing required mininet_state field: {field}")
            return False
    
    # Validate topology_data within mininet_state
    topology_data = mininet_state['topology_data']
    if not validate_topology_data(topology_data):
        logger.error("Invalid topology_data in mininet_state")
        return False
    
    logger.info("Snapshot data validation passed")
    return True

def sanitize_snapshot_for_storage(snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize simulation snapshot data for MongoDB storage"""
    sanitized = {}
    
    # Recursively sanitize nested dictionaries and lists
    def sanitize_value(value):
        if isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize_value(item) for item in value]
        elif isinstance(value, (str, int, float, bool, type(None))):
            return value
        else:
            # Convert non-serializable objects to string representation
            return str(value)
    
    for key, value in snapshot_data.items():
        sanitized[key] = sanitize_value(value)
    
    # Ensure required structure exists
    if 'mininet_state' not in sanitized:
        sanitized['mininet_state'] = {}
    if 'controller_state' not in sanitized:
        sanitized['controller_state'] = {}
    if 'network_stats' not in sanitized:
        sanitized['network_stats'] = {}
    
    return sanitized

def sanitize_configuration_for_storage(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize configuration data for MongoDB storage"""
    # Remove any non-serializable objects and clean up data
    sanitized = {}
    
    for key, value in config_data.items():
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            sanitized[key] = value
        else:
            # Convert to string representation for non-standard types
            sanitized[key] = str(value)
    
    return sanitized

def sanitize_snapshot_for_storage(snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize snapshot data for MongoDB storage by converting integer keys to strings"""
    def convert_keys_to_strings(obj):
        """Recursively convert integer keys to strings in dictionaries"""
        if isinstance(obj, dict):
            # Convert integer keys to strings
            new_dict = {}
            for key, value in obj.items():
                # Convert integer keys to strings
                str_key = str(key) if isinstance(key, int) else key
                # Recursively process the value
                new_dict[str_key] = convert_keys_to_strings(value)
            return new_dict
        elif isinstance(obj, list):
            # Process each item in the list
            return [convert_keys_to_strings(item) for item in obj]
        else:
            # Return the value as-is for non-dict, non-list types
            return obj
    
    return convert_keys_to_strings(snapshot_data)

def validate_snapshot_data(snapshot_data: Dict[str, Any]) -> bool:
    """Validate snapshot data structure"""
    try:
        # Check for required top-level keys
        required_keys = ['mininet_state', 'controller_state', 'network_stats']
        
        for key in required_keys:
            if key not in snapshot_data:
                logger.warning(f"Missing required key: {key}")
                return False
        
        # Validate mininet_state structure
        mininet_state = snapshot_data.get('mininet_state', {})
        if not isinstance(mininet_state, dict):
            logger.error("mininet_state must be a dictionary")
            return False
        
        # Check for topology_data
        topology_data = mininet_state.get('topology_data', {})
        if not isinstance(topology_data, dict):
            logger.warning("topology_data should be a dictionary")
        
        # Validate that nodes and links are lists
        if 'nodes' in topology_data and not isinstance(topology_data['nodes'], list):
            logger.error("topology_data.nodes must be a list")
            return False
            
        if 'links' in topology_data and not isinstance(topology_data['links'], list):
            logger.error("topology_data.links must be a list")
            return False
        
        logger.info("Snapshot data validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Error validating snapshot data: {e}")
        return False
