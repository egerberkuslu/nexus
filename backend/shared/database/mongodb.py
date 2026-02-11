"""
MongoDB database connection and client management
For storing snapshot state data and large documents
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# MongoDB configuration from environment
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "caduceus")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "changeme_mongo_password")
MONGODB_DB = os.getenv("MONGODB_DB", "caduceus_snapshots")
MONGODB_AUTH_SOURCE = os.getenv("MONGODB_AUTH_SOURCE", "admin")

# Connection URI
if MONGODB_USER and MONGODB_PASSWORD:
    MONGODB_URI = f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}?authSource={MONGODB_AUTH_SOURCE}"
else:
    MONGODB_URI = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}"

# Override with full URI if provided
MONGODB_URI = os.getenv("MONGODB_URI", MONGODB_URI)


class MongoDBClient:
    """
    MongoDB client singleton for snapshot state storage
    """
    _instance: Optional['MongoDBClient'] = None
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._connect()

    def _connect(self):
        """Establish MongoDB connection"""
        try:
            self._client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5
            )
            # Test connection
            self._client.admin.command('ping')
            self._db = self._client[MONGODB_DB]
            logger.info(f"Connected to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @property
    def client(self) -> MongoClient:
        """Get MongoDB client"""
        if self._client is None:
            self._connect()
        return self._client

    @property
    def db(self) -> Database:
        """Get database instance"""
        if self._db is None:
            self._connect()
        return self._db

    def get_collection(self, name: str) -> Collection:
        """Get a collection by name"""
        return self.db[name]

    def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")


# Global client instance
_mongo_client: Optional[MongoDBClient] = None


def get_mongodb() -> MongoDBClient:
    """Get MongoDB client instance"""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoDBClient()
    return _mongo_client


def get_db() -> Database:
    """Get MongoDB database instance"""
    return get_mongodb().db


# Collection names
SNAPSHOT_STATES_COLLECTION = "snapshot_states"
SNAPSHOT_BLOBS_COLLECTION = "snapshot_blobs"


def get_snapshot_states_collection() -> Collection:
    """Get the snapshot states collection"""
    return get_mongodb().get_collection(SNAPSHOT_STATES_COLLECTION)


def get_snapshot_blobs_collection() -> Collection:
    """Get the snapshot blobs collection (for large data)"""
    return get_mongodb().get_collection(SNAPSHOT_BLOBS_COLLECTION)


def init_mongodb():
    """Initialize MongoDB collections and indexes"""
    try:
        mongo = get_mongodb()

        # Create snapshot_states collection indexes
        states_collection = mongo.get_collection(SNAPSHOT_STATES_COLLECTION)
        states_collection.create_index("snapshot_id", unique=True)
        states_collection.create_index("topology_id")
        states_collection.create_index("created_at")

        # Create snapshot_blobs collection indexes
        blobs_collection = mongo.get_collection(SNAPSHOT_BLOBS_COLLECTION)
        blobs_collection.create_index([("snapshot_id", 1), ("blob_type", 1)])
        blobs_collection.create_index("created_at")

        logger.info("MongoDB collections and indexes initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        raise


def health_check() -> Dict[str, Any]:
    """Check MongoDB health status"""
    try:
        mongo = get_mongodb()
        mongo.client.admin.command('ping')
        stats = mongo.db.command('dbStats')
        return {
            "status": "healthy",
            "host": MONGODB_HOST,
            "port": MONGODB_PORT,
            "database": MONGODB_DB,
            "collections": stats.get("collections", 0),
            "dataSize": stats.get("dataSize", 0),
            "storageSize": stats.get("storageSize", 0)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Export
__all__ = [
    'MongoDBClient',
    'get_mongodb',
    'get_db',
    'get_snapshot_states_collection',
    'get_snapshot_blobs_collection',
    'init_mongodb',
    'health_check',
    'MONGODB_URI',
    'MONGODB_DB',
    'SNAPSHOT_STATES_COLLECTION',
    'SNAPSHOT_BLOBS_COLLECTION',
]
