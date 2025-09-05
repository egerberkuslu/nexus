"""
MongoDB Database Connection Manager
Handles connection to MongoDB database
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from utils.logger import setup_logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)

class DatabaseManager:
    """MongoDB connection and management"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.connection_string = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.database_name = os.getenv('DATABASE_NAME', 'mininet_web_framework')
        
        # Collection references (will be set after connection)
        self.topologies = None
        self.configurations = None
        self.llm_configurations = None
        
    def connect(self):
        """Establish connection to MongoDB"""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,         # 10 second connection timeout
                socketTimeoutMS=20000           # 20 second socket timeout
            )
            
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            
            # Initialize collection references
            self.topologies = self.db['topologies']
            self.configurations = self.db['configurations']
            self.llm_configurations = self.db['llm_configurations']
            
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client is not None:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_collection(self, collection_name):
        """Get a MongoDB collection"""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]
    
    def is_connected(self):
        """Check if database is connected"""
        try:
            if self.client is not None:
                self.client.admin.command('ping')
                return True
        except Exception:
            pass
        return False
    
    def create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Topology collection indexes
            topologies = self.get_collection('topologies')
            topologies.create_index([("name", 1)], unique=True)
            topologies.create_index([("created_at", -1)])
            topologies.create_index([("updated_at", -1)])
            
            # Configuration collection indexes
            configurations = self.get_collection('configurations')
            configurations.create_index([("name", 1)], unique=True)
            configurations.create_index([("device_type", 1)])
            configurations.create_index([("created_at", -1)])
            configurations.create_index([("updated_at", -1)])
            
            # LLM Configuration collection indexes
            llm_configurations = self.get_collection('llm_configurations')
            llm_configurations.create_index([("name", 1)], unique=True)
            llm_configurations.create_index([("service_type", 1)])
            llm_configurations.create_index([("is_active", 1)])
            llm_configurations.create_index([("created_at", -1)])
            llm_configurations.create_index([("updated_at", -1)])
            
            logger.info("Database indexes created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating database indexes: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()

def get_database():
    """Get the database manager instance"""
    return db_manager

def init_database():
    """Initialize database connection and indexes"""
    if db_manager.connect():
        db_manager.create_indexes()
        return True
    return False
