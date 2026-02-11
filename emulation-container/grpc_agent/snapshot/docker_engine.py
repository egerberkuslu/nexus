"""
Docker commit snapshot engine
Captures container filesystem state using docker commit
"""

from __future__ import annotations

import subprocess
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import SnapshotEngineBase, SnapshotResult, SnapshotType
from .network_state import NetworkStateCapture

logger = logging.getLogger(__name__)


class DockerSnapshotEngine(SnapshotEngineBase):
    """
    Docker commit snapshot engine

    Creates snapshots using `docker commit` for each container.
    Captures filesystem state but not process state.
    Faster than CRIU but doesn't preserve running processes.
    """

    def __init__(self, emulation_manager):
        super().__init__(emulation_manager)
        self.network_capture = NetworkStateCapture(emulation_manager)

    @property
    def snapshot_type(self) -> SnapshotType:
        return SnapshotType.DOCKER_COMMIT

    def validate_prerequisites(self) -> tuple[bool, str]:
        """Check if Docker is available"""
        try:
            result = subprocess.run(
                ['docker', 'version'],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                return False, "Docker not available"

            # Check for container devices
            container_devices = self.get_container_devices(list(self.em.devices.keys()))
            if not container_devices:
                return False, "No Docker containers in emulation"

            return True, ""
        except Exception as e:
            return False, f"Docker check failed: {e}"

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
        Create a Docker commit snapshot

        Args:
            snapshot_name: Name for the snapshot
            description: Optional description
            target_devices: List of devices to snapshot (None = all)
            compression: Not used for docker commit
            include_routing: Include routing tables in network state
            include_flows: Include flow tables in network state
            include_arp: Include ARP tables in network state

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

            if not container_devices:
                return SnapshotResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    snapshot_type=self.snapshot_type.value,
                    error_message="No container devices to snapshot"
                )

            # Export topology
            topology_data = self.export_topology()

            # Capture network state
            network_state = self.network_capture.capture_all(
                devices=all_devices,
                include_routing=include_routing,
                include_arp=include_arp,
                include_flows=include_flows
            )

            # Commit each container
            docker_images: Dict[str, str] = {}
            total_size = 0
            failed_devices = []

            for device_name in container_devices:
                try:
                    image_info = self._commit_container(device_name, snapshot_name)
                    if image_info:
                        docker_images[device_name] = image_info['image_tag']
                        total_size += image_info.get('size_bytes', 0)
                except Exception as e:
                    logger.error(f"Failed to commit {device_name}: {e}")
                    failed_devices.append(device_name)

            duration = (datetime.utcnow() - start_time).total_seconds()

            if failed_devices and len(failed_devices) == len(container_devices):
                return SnapshotResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    snapshot_type=self.snapshot_type.value,
                    error_message=f"All container commits failed: {failed_devices}",
                    duration_seconds=duration
                )

            logger.info(
                f"Created Docker snapshot: {snapshot_name} "
                f"({len(docker_images)} containers, {total_size / 1024 / 1024:.1f} MB, {duration:.2f}s)"
            )

            return SnapshotResult(
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
                criu_available=False
            )

        except Exception as e:
            logger.error(f"Docker snapshot failed: {e}")
            return SnapshotResult(
                success=False,
                snapshot_name=snapshot_name,
                snapshot_type=self.snapshot_type.value,
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )

    def _commit_container(
        self,
        device_name: str,
        snapshot_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Commit a container's filesystem

        Args:
            device_name: Name of the device
            snapshot_name: Name of the snapshot

        Returns:
            Dict with image tag and size, or None if failed
        """
        device_info = self.em.devices.get(device_name)
        if not device_info:
            return None

        # Get container ID
        container_id = self._get_container_id(device_name, device_info)
        if not container_id:
            logger.warning(f"Could not get container ID for {device_name}")
            return None

        # Create image tag
        image_tag = f"caduceus-snapshot:{snapshot_name}-{device_name}"

        try:
            # Docker commit
            result = subprocess.run(
                ['docker', 'commit', container_id, image_tag],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"Docker commit failed for {device_name}: {result.stderr}")
                return None

            # Get image size
            size_result = subprocess.run(
                ['docker', 'image', 'inspect', image_tag, '--format', '{{.Size}}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            size_bytes = int(size_result.stdout.strip()) if size_result.returncode == 0 else 0

            logger.info(f"Committed {device_name} -> {image_tag} ({size_bytes / 1024 / 1024:.1f} MB)")

            return {
                'container_id': container_id,
                'image_tag': image_tag,
                'size_bytes': size_bytes,
                'committed_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Container commit failed: {e}")
            return None

    def _get_container_id(self, device_name: str, device_info: Dict[str, Any]) -> Optional[str]:
        """Get Docker container ID from device info or node"""
        # Try direct container ID
        if 'container_id' in device_info:
            return device_info['container_id']

        # Try from node
        node = device_info.get('node')
        if node:
            # Containernet Docker node
            if hasattr(node, 'dc') and hasattr(node.dc, 'id'):
                return node.dc.id

            # Alternative attributes
            if hasattr(node, 'container') and hasattr(node.container, 'id'):
                return node.container.id

            # Try to find by name
            try:
                result = subprocess.run(
                    ['docker', 'ps', '-q', '--filter', f'name=mn.{device_name}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split('\n')[0]
            except Exception:
                pass

        return None

    def restore_from_images(
        self,
        docker_images: Dict[str, str],
        network_state: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, List[str]]:
        """
        Restore containers from committed images

        This is a helper method - actual restore logic is in RestoreEngine

        Args:
            docker_images: Dict mapping device names to image tags
            network_state: Optional network state to restore

        Returns:
            (success, list of errors)
        """
        errors = []

        for device_name, image_tag in docker_images.items():
            try:
                # Check if image exists
                result = subprocess.run(
                    ['docker', 'image', 'inspect', image_tag],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode != 0:
                    errors.append(f"Image {image_tag} not found for {device_name}")
                    continue

                # The actual container creation would be done by EmulationManager
                # using the committed image instead of the original
                logger.info(f"Image {image_tag} ready for {device_name}")

            except Exception as e:
                errors.append(f"Failed to check image for {device_name}: {e}")

        return len(errors) == 0, errors


# Export
__all__ = ['DockerSnapshotEngine']
