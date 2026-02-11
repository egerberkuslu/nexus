"""
Hybrid snapshot engine
Combines Docker commit and CRIU checkpoint for comprehensive snapshots
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import SnapshotEngineBase, SnapshotResult, SnapshotType
from .docker_checkpoint import DockerCheckpointHandler
from .network_state import NetworkStateCapture
from .docker_engine import DockerSnapshotEngine
from .criu_engine import CRIUSnapshotEngine

logger = logging.getLogger(__name__)


class HybridSnapshotEngine(SnapshotEngineBase):
    """
    Hybrid snapshot engine

    Creates comprehensive snapshots combining:
    - Topology structure
    - Network state (routing, ARP, flows)
    - Docker commit (filesystem)
    - CRIU checkpoint (process state) - if available

    This provides the most complete snapshot but takes longest.
    """

    def __init__(self, emulation_manager):
        super().__init__(emulation_manager)
        self.checkpoint_handler = DockerCheckpointHandler()
        self.network_capture = NetworkStateCapture(emulation_manager)
        self.docker_engine = DockerSnapshotEngine(emulation_manager)
        self.criu_engine = CRIUSnapshotEngine(emulation_manager)

    @property
    def snapshot_type(self) -> SnapshotType:
        return SnapshotType.HYBRID_FULL

    def validate_prerequisites(self) -> tuple[bool, str]:
        """
        Check prerequisites for hybrid snapshot
        CRIU is optional - will use Docker commit only if unavailable
        """
        # Check for devices
        if not hasattr(self.em, 'devices') or not self.em.devices:
            return False, "No devices in emulation"

        # Check for container devices
        container_devices = self.get_container_devices(list(self.em.devices.keys()))
        if not container_devices:
            # Can still do topology + network state
            logger.info("No container devices - hybrid snapshot will be limited")

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
        Create a hybrid snapshot combining all available methods

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            target_devices: List of devices to snapshot (None = all)
            compression: Whether to compress data
            include_routing: Include routing tables
            include_flows: Include flow tables
            include_arp: Include ARP tables
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
                    error_message=error
                )

            # Get target devices
            all_devices = self.get_target_devices(target_devices)
            container_devices = self.get_container_devices(all_devices)

            # 1. Export topology
            logger.info(f"[1/4] Exporting topology for {snapshot_name}")
            topology_data = self.export_topology()

            # 2. Capture network state
            logger.info(f"[2/4] Capturing network state for {snapshot_name}")
            network_state = self.network_capture.capture_all(
                devices=all_devices,
                include_routing=include_routing,
                include_arp=include_arp,
                include_flows=include_flows
            )

            docker_images: Dict[str, str] = {}
            criu_checkpoints: Dict[str, Dict[str, Any]] = {}
            total_size = 0
            criu_available = self.checkpoint_handler.is_available()

            if container_devices:
                # 3. Docker commit (filesystem snapshot)
                logger.info(f"[3/4] Creating Docker commits for {snapshot_name}")
                for device_name in container_devices:
                    try:
                        image_info = self.docker_engine._commit_container(
                            device_name,
                            snapshot_name
                        )
                        if image_info:
                            docker_images[device_name] = image_info['image_tag']
                            total_size += image_info.get('size_bytes', 0)
                    except Exception as e:
                        logger.warning(f"Docker commit failed for {device_name}: {e}")

                # 4. CRIU checkpoint (process state) - if available
                if criu_available:
                    logger.info(f"[4/4] Creating CRIU checkpoints for {snapshot_name}")
                    for device_name in container_devices:
                        try:
                            checkpoint_info = self.criu_engine._checkpoint_device(
                                device_name,
                                snapshot_name,
                                leave_running
                            )
                            if checkpoint_info:
                                criu_checkpoints[device_name] = checkpoint_info
                                total_size += checkpoint_info.get('size_bytes', 0)
                        except Exception as e:
                            logger.warning(f"CRIU checkpoint failed for {device_name}: {e}")
                else:
                    logger.info(f"[4/4] Skipping CRIU checkpoints (not available)")
            else:
                logger.info(f"[3/4] No containers to snapshot")
                logger.info(f"[4/4] No containers to checkpoint")

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Build result
            result = SnapshotResult(
                success=True,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                size_bytes=total_size,
                devices_captured=len(all_devices),
                containers_captured=len(docker_images),
                duration_seconds=duration,
                topology_data=topology_data,
                network_state=network_state,
                docker_images=docker_images,
                criu_checkpoints=criu_checkpoints,
                criu_available=criu_available
            )

            logger.info(
                f"Created hybrid snapshot: {snapshot_name} "
                f"({len(all_devices)} devices, {len(docker_images)} commits, "
                f"{len(criu_checkpoints)} checkpoints, "
                f"{total_size / 1024 / 1024:.1f} MB, {duration:.2f}s)"
            )

            return result

        except Exception as e:
            logger.error(f"Hybrid snapshot failed: {e}")
            return SnapshotResult(
                success=False,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                criu_available=self.checkpoint_handler.is_available()
            )

    def get_available_components(self) -> Dict[str, bool]:
        """
        Get which components are available for hybrid snapshot

        Returns:
            Dict with availability flags
        """
        return {
            "topology": True,
            "network_state": True,
            "docker_commit": True,  # Always available if containers exist
            "criu_checkpoint": self.checkpoint_handler.is_available()
        }


# Export
__all__ = ['HybridSnapshotEngine']
