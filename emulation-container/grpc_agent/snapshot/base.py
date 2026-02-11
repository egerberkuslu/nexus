"""
Base classes for snapshot and restore engines
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class SnapshotType(Enum):
    """Snapshot type enumeration"""
    TOPOLOGY_ONLY = "topology_only"
    DOCKER_COMMIT = "docker_commit"
    CRIU_LIVE = "criu_live"
    HYBRID_FULL = "hybrid_full"


@dataclass
class SnapshotResult:
    """Result of a snapshot operation"""
    success: bool
    snapshot_name: str
    snapshot_type: str
    snapshot_path: Optional[str] = None
    size_bytes: int = 0
    devices_captured: int = 0
    containers_captured: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None

    # Component data
    topology_data: Optional[Dict[str, Any]] = None
    network_state: Optional[Dict[str, Any]] = None
    docker_images: Dict[str, str] = field(default_factory=dict)
    criu_checkpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Metadata
    criu_available: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RestoreResult:
    """Result of a restore operation"""
    success: bool
    snapshot_name: str
    devices_restored: int = 0
    containers_restored: int = 0
    network_state_restored: bool = False
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    rollback_performed: bool = False

    # Details
    restored_devices: List[str] = field(default_factory=list)
    failed_devices: List[str] = field(default_factory=list)


class SnapshotEngineBase(ABC):
    """Abstract base class for snapshot engines"""

    def __init__(self, emulation_manager):
        """
        Initialize snapshot engine

        Args:
            emulation_manager: Reference to EmulationManager instance
        """
        self.em = emulation_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def snapshot_type(self) -> SnapshotType:
        """Return the snapshot type this engine handles"""
        pass

    @abstractmethod
    def create_snapshot(
        self,
        snapshot_name: str,
        description: str = "",
        target_devices: Optional[List[str]] = None,
        compression: bool = True,
        include_routing: bool = True,
        include_flows: bool = True,
        include_arp: bool = True
    ) -> SnapshotResult:
        """
        Create a snapshot

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            target_devices: List of device names to snapshot (None = all)
            compression: Whether to compress the snapshot
            include_routing: Include routing tables
            include_flows: Include flow tables
            include_arp: Include ARP tables

        Returns:
            SnapshotResult with operation details
        """
        pass

    @abstractmethod
    def validate_prerequisites(self) -> tuple[bool, str]:
        """
        Check if snapshot type can be created

        Returns:
            (can_create, error_message)
        """
        pass

    def get_target_devices(self, target_devices: Optional[List[str]] = None) -> List[str]:
        """Get list of devices to snapshot"""
        if target_devices:
            # Filter to only existing devices
            existing = set(self.em.devices.keys())
            return [d for d in target_devices if d in existing]
        return list(self.em.devices.keys())

    def get_container_devices(self, devices: List[str]) -> List[str]:
        """Get devices that are Docker containers"""
        container_devices = []
        for device_name in devices:
            device_info = self.em.devices.get(device_name, {})
            if device_info.get('is_docker') or device_info.get('type') in ['docker', 'docker_host', 'docker_station']:
                container_devices.append(device_name)
        return container_devices

    def export_topology(self) -> Dict[str, Any]:
        """Export current topology structure"""
        return {
            "devices": self._export_devices(),
            "links": self._export_links(),
            "controllers": self._export_controllers(),
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "emulation_id": getattr(self.em, 'emulation_id', None),
                "status": getattr(self.em, 'status', 'unknown')
            }
        }

    def _export_devices(self) -> List[Dict[str, Any]]:
        """Export device configurations"""
        devices = []
        for name, info in self.em.devices.items():
            device_data = {
                "name": name,
                "type": info.get('type', 'unknown'),
                "is_docker": info.get('is_docker', False),
                "properties": info.get('properties', {})
            }

            # Get IP addresses if available
            node = info.get('node')
            if node:
                try:
                    ips = []
                    for intf in node.intfList():
                        if intf.IP():
                            ips.append({
                                "interface": intf.name,
                                "ip": intf.IP(),
                                "mac": intf.MAC()
                            })
                    device_data["interfaces"] = ips
                except Exception:
                    pass

            devices.append(device_data)
        return devices

    def _export_links(self) -> List[Dict[str, Any]]:
        """Export link configurations"""
        links = []
        for link_info in getattr(self.em, 'links', {}).values():
            links.append({
                "source": link_info.get('source'),
                "target": link_info.get('target'),
                "bandwidth": link_info.get('bandwidth'),
                "delay": link_info.get('delay'),
                "loss": link_info.get('loss'),
                "properties": link_info.get('properties', {})
            })
        return links

    def _export_controllers(self) -> List[Dict[str, Any]]:
        """Export controller configurations"""
        controllers = []
        for ctrl_info in getattr(self.em, 'controllers', {}).values():
            controllers.append({
                "name": ctrl_info.get('name'),
                "type": ctrl_info.get('type'),
                "ip": ctrl_info.get('ip'),
                "port": ctrl_info.get('port')
            })
        return controllers


class RestoreEngineBase(ABC):
    """Abstract base class for restore engines"""

    def __init__(self, emulation_manager):
        """
        Initialize restore engine

        Args:
            emulation_manager: Reference to EmulationManager instance
        """
        self.em = emulation_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._pre_restore_state: Optional[Dict[str, Any]] = None

    @abstractmethod
    def restore_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        target_devices: Optional[List[str]] = None,
        restore_network_state: bool = True,
        restore_docker_images: bool = True,
        restore_criu_checkpoints: bool = True
    ) -> RestoreResult:
        """
        Restore from snapshot data

        Args:
            snapshot_data: Snapshot data from MongoDB
            target_devices: Specific devices to restore (None = all)
            restore_network_state: Whether to restore network state
            restore_docker_images: Whether to restore from Docker images
            restore_criu_checkpoints: Whether to restore from CRIU checkpoints

        Returns:
            RestoreResult with operation details
        """
        pass

    @abstractmethod
    def validate_snapshot(self, snapshot_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate snapshot data before restore

        Returns:
            (is_valid, error_message)
        """
        pass

    def create_rollback_point(self) -> Dict[str, Any]:
        """Create a rollback point before restore"""
        self._pre_restore_state = {
            "devices": list(self.em.devices.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
        return self._pre_restore_state

    def rollback(self) -> bool:
        """Rollback to pre-restore state"""
        if not self._pre_restore_state:
            self.logger.warning("No rollback point available")
            return False

        try:
            # Stop current emulation
            self.em.stop_emulation()
            self.logger.info("Rollback completed - emulation stopped")
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False

    def verify_restore(self, expected_devices: List[str]) -> tuple[bool, List[str]]:
        """
        Verify restore was successful

        Returns:
            (success, missing_devices)
        """
        current_devices = set(self.em.devices.keys())
        expected = set(expected_devices)
        missing = expected - current_devices

        return len(missing) == 0, list(missing)


# Export
__all__ = [
    'SnapshotType',
    'SnapshotResult',
    'RestoreResult',
    'SnapshotEngineBase',
    'RestoreEngineBase'
]
