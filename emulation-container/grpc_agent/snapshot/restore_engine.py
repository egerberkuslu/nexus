"""
Restore engine for snapshot restoration
Handles restoration with validation and rollback support
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import RestoreEngineBase, RestoreResult
from .docker_checkpoint import DockerCheckpointHandler, DockerCheckpointError
from .network_state import NetworkStateCapture

logger = logging.getLogger(__name__)


class RestoreEngine(RestoreEngineBase):
    """
    Unified restore engine for all snapshot types

    Handles restoration of:
    - Topology structure
    - Network state (routing, ARP, flows)
    - Docker images (docker commit)
    - CRIU checkpoints (live process state)
    """

    def __init__(self, emulation_manager):
        super().__init__(emulation_manager)
        self.checkpoint_handler = DockerCheckpointHandler()
        self.network_capture = NetworkStateCapture(emulation_manager)

    def validate_snapshot(self, snapshot_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate snapshot data before restore

        Args:
            snapshot_data: Snapshot data from MongoDB

        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        if not snapshot_data.get('topology'):
            return False, "Missing topology data"

        # Check topology has devices
        if not snapshot_data['topology'].get('devices'):
            return False, "No devices in topology"

        # If has CRIU checkpoints, verify CRIU is available
        if snapshot_data.get('criu_checkpoints'):
            if not self.checkpoint_handler.is_available():
                return False, "Snapshot has CRIU checkpoints but CRIU is not available"

        return True, ""

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
        start_time = datetime.utcnow()
        snapshot_name = snapshot_data.get('snapshot_id', 'unknown')
        warnings: List[str] = []
        restored_devices: List[str] = []
        failed_devices: List[str] = []

        try:
            # Validate
            valid, error = self.validate_snapshot(snapshot_data)
            if not valid:
                return RestoreResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    error_message=error
                )

            # Create rollback point
            self.create_rollback_point()

            # Get target devices from topology
            all_devices = [d['name'] for d in snapshot_data['topology'].get('devices', [])]
            if target_devices:
                all_devices = [d for d in all_devices if d in target_devices]

            containers_restored = 0

            # 1. Restore CRIU checkpoints first (if available and requested)
            if restore_criu_checkpoints and snapshot_data.get('criu_checkpoints'):
                logger.info("Restoring from CRIU checkpoints...")
                criu_result = self._restore_criu_checkpoints(
                    snapshot_data['criu_checkpoints'],
                    target_devices
                )

                if criu_result['success']:
                    restored_devices.extend(criu_result['restored'])
                    containers_restored += len(criu_result['restored'])
                else:
                    warnings.extend(criu_result['errors'])
                    # Fall back to Docker images if CRIU fails
                    logger.warning("CRIU restore failed, will try Docker images")

            # 2. Restore Docker images for devices not restored by CRIU
            if restore_docker_images and snapshot_data.get('docker_snapshots'):
                remaining_devices = [d for d in all_devices if d not in restored_devices]
                docker_devices = {
                    k: v for k, v in snapshot_data['docker_snapshots'].items()
                    if k in remaining_devices
                }

                if docker_devices:
                    logger.info(f"Restoring Docker images for {len(docker_devices)} devices...")
                    docker_result = self._restore_docker_images(docker_devices)

                    if docker_result['success']:
                        restored_devices.extend(docker_result['restored'])
                        containers_restored += len(docker_result['restored'])
                    else:
                        warnings.extend(docker_result['errors'])
                        failed_devices.extend(docker_result['failed'])

            # 3. Restore network state
            network_restored = False
            if restore_network_state and snapshot_data.get('network_state'):
                logger.info("Restoring network state...")
                try:
                    errors = self.network_capture.restore_all(
                        snapshot_data['network_state'],
                        devices=restored_devices if restored_devices else None
                    )
                    if errors:
                        warnings.extend([f"{e['device']}/{e['component']}: {e['error']}" for e in errors])
                    else:
                        network_restored = True
                except Exception as e:
                    warnings.append(f"Network state restore failed: {e}")

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Determine overall success
            success = len(restored_devices) > 0 or len(failed_devices) == 0

            if not success and failed_devices:
                # Attempt rollback
                logger.warning("Restore partially failed, attempting rollback...")
                rollback_success = self.rollback()

                return RestoreResult(
                    success=False,
                    snapshot_name=snapshot_name,
                    devices_restored=len(restored_devices),
                    containers_restored=containers_restored,
                    network_state_restored=network_restored,
                    duration_seconds=duration,
                    error_message=f"Failed to restore: {failed_devices}",
                    warnings=warnings,
                    rollback_performed=rollback_success,
                    restored_devices=restored_devices,
                    failed_devices=failed_devices
                )

            logger.info(
                f"Restore completed: {len(restored_devices)} devices, "
                f"{containers_restored} containers, network={network_restored}, "
                f"{duration:.2f}s"
            )

            return RestoreResult(
                success=True,
                snapshot_name=snapshot_name,
                devices_restored=len(restored_devices),
                containers_restored=containers_restored,
                network_state_restored=network_restored,
                duration_seconds=duration,
                warnings=warnings,
                restored_devices=restored_devices,
                failed_devices=failed_devices
            )

        except Exception as e:
            logger.error(f"Restore failed: {e}")

            # Attempt rollback
            rollback_success = self.rollback()

            return RestoreResult(
                success=False,
                snapshot_name=snapshot_name,
                error_message=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                rollback_performed=rollback_success
            )

    def _restore_criu_checkpoints(
        self,
        criu_checkpoints: Dict[str, Dict[str, Any]],
        target_devices: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Restore containers from CRIU checkpoints

        Returns:
            Dict with 'success', 'restored', 'errors'
        """
        restored = []
        errors = []

        checkpoints_to_restore = criu_checkpoints
        if target_devices:
            checkpoints_to_restore = {
                k: v for k, v in criu_checkpoints.items()
                if k in target_devices
            }

        for device_name, checkpoint_info in checkpoints_to_restore.items():
            try:
                container_id = checkpoint_info.get('container_id')
                checkpoint_name = checkpoint_info.get('checkpoint_name')

                if not container_id or not checkpoint_name:
                    errors.append(f"{device_name}: Missing checkpoint info")
                    continue

                self.checkpoint_handler.restore_checkpoint(
                    container_id=container_id,
                    checkpoint_name=checkpoint_name
                )

                restored.append(device_name)
                logger.info(f"Restored CRIU checkpoint for {device_name}")

            except DockerCheckpointError as e:
                errors.append(f"{device_name}: {e}")
            except Exception as e:
                errors.append(f"{device_name}: Unexpected error - {e}")

        return {
            'success': len(errors) == 0,
            'restored': restored,
            'errors': errors
        }

    def _restore_docker_images(
        self,
        docker_snapshots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare Docker images for restoration

        Note: Actual container creation is done by EmulationManager.
        This method verifies images exist and logs info.

        Returns:
            Dict with 'success', 'restored', 'failed', 'errors'
        """
        restored = []
        failed = []
        errors = []

        for device_name, snapshot_info in docker_snapshots.items():
            try:
                # Handle both dict format and string format
                if isinstance(snapshot_info, dict):
                    image_tag = snapshot_info.get('image_tag')
                else:
                    image_tag = snapshot_info

                if not image_tag:
                    errors.append(f"{device_name}: No image tag")
                    failed.append(device_name)
                    continue

                # Verify image exists
                import subprocess
                result = subprocess.run(
                    ['docker', 'image', 'inspect', image_tag],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode != 0:
                    errors.append(f"{device_name}: Image {image_tag} not found")
                    failed.append(device_name)
                    continue

                restored.append(device_name)
                logger.info(f"Docker image ready for {device_name}: {image_tag}")

            except Exception as e:
                errors.append(f"{device_name}: {e}")
                failed.append(device_name)

        return {
            'success': len(failed) == 0,
            'restored': restored,
            'failed': failed,
            'errors': errors
        }

    def verify_restore(self, expected_devices: List[str]) -> tuple[bool, List[str]]:
        """
        Verify restore was successful by checking devices exist

        Returns:
            (success, missing_devices)
        """
        current_devices = set(self.em.devices.keys()) if hasattr(self.em, 'devices') else set()
        expected = set(expected_devices)
        missing = expected - current_devices

        return len(missing) == 0, list(missing)


# Export
__all__ = ['RestoreEngine']
