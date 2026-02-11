"""
MongoDB storage layer for snapshot state data
Stores large state data like network state, Docker images, CRIU checkpoints
"""

import logging
import gzip
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId

from pymongo.collection import Collection

from shared.database.mongodb import (
    get_snapshot_states_collection,
    get_snapshot_blobs_collection
)

logger = logging.getLogger(__name__)


class MongoSnapshotStorage:
    """
    MongoDB storage operations for snapshot state data
    """

    def __init__(self):
        self._states_collection: Optional[Collection] = None
        self._blobs_collection: Optional[Collection] = None

    @property
    def states(self) -> Collection:
        """Get snapshot states collection"""
        if self._states_collection is None:
            self._states_collection = get_snapshot_states_collection()
        return self._states_collection

    @property
    def blobs(self) -> Collection:
        """Get snapshot blobs collection"""
        if self._blobs_collection is None:
            self._blobs_collection = get_snapshot_blobs_collection()
        return self._blobs_collection

    # ==================== State Document Operations ====================

    def create_state(
        self,
        snapshot_id: str,
        topology_id: str,
        topology_data: Dict[str, Any],
        network_state: Optional[Dict[str, Any]] = None,
        docker_snapshots: Optional[Dict[str, Any]] = None,
        criu_checkpoints: Optional[Dict[str, Any]] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
        compress: bool = True
    ) -> str:
        """
        Create a new snapshot state document

        Args:
            snapshot_id: Reference to PostgreSQL snapshot record
            topology_id: Topology this snapshot belongs to
            topology_data: Topology structure (devices, links, controllers)
            network_state: Captured network state (routing, ARP, flows)
            docker_snapshots: Docker commit image references
            criu_checkpoints: CRIU checkpoint references
            runtime_config: Runtime configuration at snapshot time
            compress: Whether to compress large data fields

        Returns:
            MongoDB document ID
        """
        # Prepare document
        document = {
            "snapshot_id": snapshot_id,
            "topology_id": topology_id,
            "created_at": datetime.utcnow(),

            # Topology structure (always present)
            "topology": topology_data,

            # Optional state data
            "network_state": network_state or {},
            "docker_snapshots": docker_snapshots or {},
            "criu_checkpoints": criu_checkpoints or {},
            "runtime_config": runtime_config or {},

            # Metadata
            "compressed": compress,
            "version": "2.0"  # Schema version
        }

        # Optionally compress large fields
        if compress:
            document = self._compress_document(document)

        result = self.states.insert_one(document)
        doc_id = str(result.inserted_id)

        logger.info(f"Created state document: {doc_id} for snapshot {snapshot_id}")
        return doc_id

    def get_state(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Get state document by snapshot ID"""
        document = self.states.find_one({"snapshot_id": snapshot_id})

        if document:
            # Decompress if needed
            if document.get("compressed"):
                document = self._decompress_document(document)

            # Convert ObjectId to string
            document["_id"] = str(document["_id"])

        return document

    def get_state_by_mongo_id(self, mongo_id: str) -> Optional[Dict[str, Any]]:
        """Get state document by MongoDB ObjectId"""
        try:
            document = self.states.find_one({"_id": ObjectId(mongo_id)})

            if document:
                if document.get("compressed"):
                    document = self._decompress_document(document)
                document["_id"] = str(document["_id"])

            return document
        except Exception as e:
            logger.error(f"Failed to get state by ID {mongo_id}: {e}")
            return None

    def update_state(
        self,
        snapshot_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update state document fields"""
        result = self.states.update_one(
            {"snapshot_id": snapshot_id},
            {"$set": updates}
        )
        return result.modified_count > 0

    def delete_state(self, snapshot_id: str) -> bool:
        """Delete state document and associated blobs"""
        # Delete blobs first
        self.blobs.delete_many({"snapshot_id": snapshot_id})

        # Delete state document
        result = self.states.delete_one({"snapshot_id": snapshot_id})

        if result.deleted_count > 0:
            logger.info(f"Deleted state document for snapshot {snapshot_id}")
            return True
        return False

    # ==================== Network State Operations ====================

    def update_network_state(
        self,
        snapshot_id: str,
        network_state: Dict[str, Any]
    ) -> bool:
        """Update network state in existing document"""
        return self.update_state(snapshot_id, {"network_state": network_state})

    def get_network_state(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Get only network state from document"""
        document = self.states.find_one(
            {"snapshot_id": snapshot_id},
            {"network_state": 1, "compressed": 1}
        )

        if document:
            if document.get("compressed") and "network_state" in document:
                return self._decompress_field(document["network_state"])
            return document.get("network_state", {})

        return None

    # ==================== Docker Snapshot Operations ====================

    def update_docker_snapshots(
        self,
        snapshot_id: str,
        docker_snapshots: Dict[str, Any]
    ) -> bool:
        """Update Docker snapshot references"""
        return self.update_state(snapshot_id, {"docker_snapshots": docker_snapshots})

    def add_docker_snapshot(
        self,
        snapshot_id: str,
        device_name: str,
        container_id: str,
        image_tag: str,
        size_bytes: int
    ) -> bool:
        """Add a single Docker snapshot reference"""
        result = self.states.update_one(
            {"snapshot_id": snapshot_id},
            {
                "$set": {
                    f"docker_snapshots.{device_name}": {
                        "container_id": container_id,
                        "image_tag": image_tag,
                        "size_bytes": size_bytes,
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
            }
        )
        return result.modified_count > 0

    # ==================== CRIU Checkpoint Operations ====================

    def update_criu_checkpoints(
        self,
        snapshot_id: str,
        criu_checkpoints: Dict[str, Any]
    ) -> bool:
        """Update CRIU checkpoint references"""
        return self.update_state(snapshot_id, {"criu_checkpoints": criu_checkpoints})

    def add_criu_checkpoint(
        self,
        snapshot_id: str,
        device_name: str,
        container_id: str,
        checkpoint_name: str,
        checkpoint_path: str,
        size_bytes: int
    ) -> bool:
        """Add a single CRIU checkpoint reference"""
        result = self.states.update_one(
            {"snapshot_id": snapshot_id},
            {
                "$set": {
                    f"criu_checkpoints.{device_name}": {
                        "container_id": container_id,
                        "checkpoint_name": checkpoint_name,
                        "checkpoint_path": checkpoint_path,
                        "size_bytes": size_bytes,
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
            }
        )
        return result.modified_count > 0

    # ==================== Blob Operations (for large data) ====================

    def store_blob(
        self,
        snapshot_id: str,
        blob_type: str,
        device_name: str,
        data: bytes
    ) -> str:
        """Store large binary data as a separate blob document"""
        document = {
            "snapshot_id": snapshot_id,
            "blob_type": blob_type,  # "criu_dump", "docker_layer", "flow_table"
            "device_name": device_name,
            "data": data,
            "size_bytes": len(data),
            "created_at": datetime.utcnow()
        }

        result = self.blobs.insert_one(document)
        blob_id = str(result.inserted_id)

        logger.info(f"Stored blob: {blob_id} ({blob_type} for {device_name})")
        return blob_id

    def get_blob(
        self,
        snapshot_id: str,
        blob_type: str,
        device_name: str
    ) -> Optional[bytes]:
        """Retrieve blob data"""
        document = self.blobs.find_one({
            "snapshot_id": snapshot_id,
            "blob_type": blob_type,
            "device_name": device_name
        })

        return document.get("data") if document else None

    def delete_blobs(self, snapshot_id: str) -> int:
        """Delete all blobs for a snapshot"""
        result = self.blobs.delete_many({"snapshot_id": snapshot_id})
        return result.deleted_count

    # ==================== Compression Utilities ====================

    def _compress_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Compress large fields in document"""
        compressed = document.copy()

        # Fields to compress
        compress_fields = ["network_state", "topology"]

        for field in compress_fields:
            if field in compressed and compressed[field]:
                try:
                    json_str = json.dumps(compressed[field])
                    compressed_data = gzip.compress(json_str.encode('utf-8'))
                    compressed[field] = {
                        "_compressed": True,
                        "_data": compressed_data,
                        "_original_size": len(json_str)
                    }
                except Exception as e:
                    logger.warning(f"Failed to compress {field}: {e}")

        return compressed

    def _decompress_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Decompress compressed fields in document"""
        decompressed = document.copy()

        for field, value in decompressed.items():
            if isinstance(value, dict) and value.get("_compressed"):
                decompressed[field] = self._decompress_field(value)

        return decompressed

    def _decompress_field(self, field_data: Any) -> Any:
        """Decompress a single field"""
        if isinstance(field_data, dict) and field_data.get("_compressed"):
            try:
                decompressed = gzip.decompress(field_data["_data"])
                return json.loads(decompressed.decode('utf-8'))
            except Exception as e:
                logger.error(f"Failed to decompress field: {e}")
                return {}
        return field_data

    # ==================== Query Utilities ====================

    def list_states(
        self,
        topology_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """List state documents"""
        query = {}
        if topology_id:
            query["topology_id"] = topology_id

        cursor = self.states.find(
            query,
            {"topology": 0, "network_state": 0}  # Exclude large fields
        ).sort("created_at", -1).skip(skip).limit(limit)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)

        return results

    def get_state_size(self, snapshot_id: str) -> int:
        """Get total size of state data for a snapshot"""
        # Get state document size
        state = self.states.find_one(
            {"snapshot_id": snapshot_id},
            {"_id": 1}
        )

        if not state:
            return 0

        # Get state document size using bson
        from bson import encode
        state_full = self.states.find_one({"snapshot_id": snapshot_id})
        state_size = len(encode(state_full)) if state_full else 0

        # Get blob sizes
        blob_cursor = self.blobs.find(
            {"snapshot_id": snapshot_id},
            {"size_bytes": 1}
        )
        blob_size = sum(doc.get("size_bytes", 0) for doc in blob_cursor)

        return state_size + blob_size


# Export
__all__ = ['MongoSnapshotStorage']
