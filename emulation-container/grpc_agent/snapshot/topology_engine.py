"""
Topology-only snapshot engine
Fastest snapshot type - captures only topology structure
"""

from __future__ import annotations

import json
import gzip
import os
import logging
from typing import Optional, List
from datetime import datetime

from .base import SnapshotEngineBase, SnapshotResult, SnapshotType

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "/var/lib/caduceus/snapshots"


class TopologySnapshotEngine(SnapshotEngineBase):
    """
    Topology-only snapshot engine

    This is the fastest and smallest snapshot type.
    Captures only the topology structure (devices, links, controllers).
    Does not capture runtime state like routing tables or process state.
    """

    @property
    def snapshot_type(self) -> SnapshotType:
        return SnapshotType.TOPOLOGY_ONLY

    def validate_prerequisites(self) -> tuple[bool, str]:
        """Topology snapshots have no special requirements"""
        # Check if emulation manager has devices
        if not hasattr(self.em, 'devices') or not self.em.devices:
            return False, "No devices in emulation"
        return True, ""

    def create_snapshot(
        self,
        snapshot_name: str,
        description: str = "",
        target_devices: Optional[List[str]] = None,
        compression: bool = True,
        include_routing: bool = False,  # Ignored for topology_only
        include_flows: bool = False,     # Ignored for topology_only
        include_arp: bool = False        # Ignored for topology_only
    ) -> SnapshotResult:
        """
        Create a topology-only snapshot

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            target_devices: List of devices to include (None = all)
            compression: Whether to compress the snapshot file

        Returns:
            SnapshotResult with operation details
        """
        start_time = datetime.utcnow()

        try:
            # Validate
            valid, error = self.validate_prerequisites()
            if not valid:
                return SnapshotResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    snapshot_type=self.snapshot_type.value,
                    error_message=error
                )

            # Get target devices
            devices = self.get_target_devices(target_devices)

            # Export topology
            topology_data = self.export_topology()

            # Filter to target devices if specified
            if target_devices:
                topology_data["devices"] = [
                    d for d in topology_data["devices"]
                    if d["name"] in devices
                ]
                # Filter links to only include those between target devices
                device_set = set(devices)
                topology_data["links"] = [
                    l for l in topology_data["links"]
                    if l.get("source") in device_set and l.get("target") in device_set
                ]

            # Add metadata
            topology_data["metadata"]["snapshot_name"] = snapshot_name
            topology_data["metadata"]["description"] = description
            topology_data["metadata"]["snapshot_type"] = self.snapshot_type.value
            topology_data["metadata"]["device_count"] = len(topology_data["devices"])
            topology_data["metadata"]["link_count"] = len(topology_data["links"])

            # Save to file
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)

            if compression:
                snapshot_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_name}.json.gz")
                with gzip.open(snapshot_path, 'wt', encoding='utf-8') as f:
                    json.dump(topology_data, f, indent=2, default=str)
            else:
                snapshot_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_name}.json")
                with open(snapshot_path, 'w', encoding='utf-8') as f:
                    json.dump(topology_data, f, indent=2, default=str)

            # Calculate size
            size_bytes = os.path.getsize(snapshot_path)
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Created topology snapshot: {snapshot_name} "
                f"({size_bytes / 1024:.1f} KB, {duration:.2f}s)"
            )

            return SnapshotResult(
                success=True,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                snapshot_path=snapshot_path,
                size_bytes=size_bytes,
                devices_captured=len(topology_data["devices"]),
                containers_captured=0,
                duration_seconds=duration,
                topology_data=topology_data,
                criu_available=False
            )

        except Exception as e:
            logger.error(f"Topology snapshot failed: {e}")
            return SnapshotResult(
                success=False,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )


# Export
__all__ = ['TopologySnapshotEngine']
