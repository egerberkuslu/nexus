"""
CRIU live snapshot engine
Uses Docker checkpoint with CRIU for live process state capture
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import SnapshotEngineBase, SnapshotResult, SnapshotType
from .docker_checkpoint import DockerCheckpointHandler, DockerCheckpointError
from .network_state import NetworkStateCapture

logger = logging.getLogger(__name__)


class CRIUSnapshotEngine(SnapshotEngineBase):
    """
    CRIU live snapshot engine

    Creates snapshots using Docker checkpoint with CRIU.
    Captures complete process state including memory.
    Containers can be restored to exact running state.
    Requires CRIU and Docker experimental features.
    """

    def __init__(self, emulation_manager):
        super().__init__(emulation_manager)
        self.checkpoint_handler = DockerCheckpointHandler()
        self.network_capture = NetworkStateCapture(emulation_manager)

    @property
    def snapshot_type(self) -> SnapshotType:
        return SnapshotType.CRIU_LIVE

    def validate_prerequisites(self) -> tuple[bool, str]:
        """Check if CRIU and Docker experimental are available"""
        if not self.checkpoint_handler.criu_available:
            return False, "CRIU is not installed or not functional"

        if not self.checkpoint_handler.docker_experimental:
            return False, "Docker experimental features not enabled"

        # Check for container devices
        container_devices = self.get_container_devices(list(self.em.devices.keys()))
        if not container_devices:
            return False, "No Docker containers in emulation"

        return True, ""

    def create_snapshot(
        self,
        snapshot_name: str,
        description: str = "",
        target_devices: Optional[List[str]] = None,
        compression: bool = True,
        include_routing: bool = True,
        include_flows: bool = True,
        include_arp: bool = True,
        leave_running: bool = True
    ) -> SnapshotResult:
        """
        Create a CRIU checkpoint snapshot

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            target_devices: List of devices to snapshot (None = all)
            compression: Not directly used (CRIU handles compression)
            include_routing: Include routing tables in network state
            include_flows: Include flow tables in network state
            include_arp: Include ARP tables in network state
            leave_running: Keep containers running after checkpoint

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
                    error_message=error,
                    criu_available=False
                )

            # Get target devices
            all_devices = self.get_target_devices(target_devices)
            container_devices = self.get_container_devices(all_devices)

            if not container_devices:
                return SnapshotResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    snapshot_type=self.snapshot_type.value,
                    error_message="No container devices to checkpoint",
                    criu_available=True
                )

            # Export topology first
            topology_data = self.export_topology()

            # Capture network state before checkpoint
            network_state = self.network_capture.capture_all(
                devices=all_devices,
                include_routing=include_routing,
                include_arp=include_arp,
                include_flows=include_flows
            )

            # Create checkpoints
            criu_checkpoints: Dict[str, Dict[str, Any]] = {}
            total_size = 0
            failed_devices = []

            for device_name in container_devices:
                try:
                    checkpoint_info = self._checkpoint_device(
                        device_name,
                        snapshot_name,
                        leave_running
                    )
                    if checkpoint_info:
                        criu_checkpoints[device_name] = checkpoint_info
                        total_size += checkpoint_info.get('size_bytes', 0)
                except Exception as e:
                    logger.error(f"Failed to checkpoint {device_name}: {e}")
                    failed_devices.append(device_name)

            duration = (datetime.utcnow() - start_time).total_seconds()

            if failed_devices and len(failed_devices) == len(container_devices):
                return SnapshotResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    snapshot_type=self.snapshot_type.value,
                    error_message=f"All checkpoints failed: {failed_devices}",
                    duration_seconds=duration,
                    criu_available=True
                )

            logger.info(
                f"Created CRIU snapshot: {snapshot_name} "
                f"({len(criu_checkpoints)} checkpoints, {total_size / 1024 / 1024:.1f} MB, {duration:.2f}s)"
            )

            return SnapshotResult(
                success=True,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                size_bytes=total_size,
                devices_captured=len(all_devices),
                containers_captured=len(criu_checkpoints),
                duration_seconds=duration,
                topology_data=topology_data,
                network_state=network_state,
                criu_checkpoints=criu_checkpoints,
                criu_available=True
            )

        except Exception as e:
            logger.error(f"CRIU snapshot failed: {e}")
            return SnapshotResult(
                success=False,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                criu_available=self.checkpoint_handler.is_available()
            )

    def _checkpoint_device(
        self,
        device_name: str,
        snapshot_name: str,
        leave_running: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create CRIU checkpoint for a device

        Args:
            device_name: Name of the device
            snapshot_name: Name of the snapshot
            leave_running: Keep container running after checkpoint

        Returns:
            Checkpoint metadata or None if failed
        """
        device_info = self.em.devices.get(device_name)
        if not device_info:
            return None

        # Get container ID
        container_id = self._get_container_id(device_name, device_info)
        if not container_id:
            logger.warning(f"Could not get container ID for {device_name}")
            return None

        # Create checkpoint name
        checkpoint_name = f"{snapshot_name}_{device_name}"

        try:
            result = self.checkpoint_handler.create_checkpoint(
                container_id=container_id,
                checkpoint_name=checkpoint_name,
                leave_running=leave_running
            )

            logger.info(
                f"Checkpointed {device_name} -> {checkpoint_name} "
                f"({result['size_bytes'] / 1024 / 1024:.1f} MB)"
            )

            return result

        except DockerCheckpointError as e:
            logger.error(f"Checkpoint failed for {device_name}: {e}")
            return None

    def _get_container_id(self, device_name: str, device_info: Dict[str, Any]) -> Optional[str]:
        """Get Docker container ID from device info"""
        # Try direct container ID
        if 'container_id' in device_info:
            return device_info['container_id']

        # Try from node
        node = device_info.get('node')
        if node:
            container_id = self.checkpoint_handler.get_container_id_from_mininet_node(node)
            if container_id:
                return container_id

        return None

    def restore_checkpoints(
        self,
        criu_checkpoints: Dict[str, Dict[str, Any]]
    ) -> tuple[bool, List[str]]:
        """
        Restore containers from CRIU checkpoints

        Args:
            criu_checkpoints: Dict mapping device names to checkpoint info

        Returns:
            (success, list of errors)
        """
        errors = []

        for device_name, checkpoint_info in criu_checkpoints.items():
            try:
                container_id = checkpoint_info.get('container_id')
                checkpoint_name = checkpoint_info.get('checkpoint_name')

                if not container_id or not checkpoint_name:
                    errors.append(f"Missing checkpoint info for {device_name}")
                    continue

                self.checkpoint_handler.restore_checkpoint(
                    container_id=container_id,
                    checkpoint_name=checkpoint_name
                )

                logger.info(f"Restored checkpoint for {device_name}")

            except DockerCheckpointError as e:
                errors.append(f"Failed to restore {device_name}: {e}")

        return len(errors) == 0, errors


# Export
__all__ = ['CRIUSnapshotEngine']
