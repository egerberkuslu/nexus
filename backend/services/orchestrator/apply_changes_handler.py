"""
Apply Changes Handler - Button-triggered topology changes
Applies changes to Mininet-WiFi/Containernet FIRST, then persists to database
"""

import logging
import httpx
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

TOPOLOGY_SERVICE_URL = "http://topology-service:8001"
TOPOLOGY_REQUEST_TIMEOUT = 30.0


class ApplyException(Exception):
    """Exception raised when apply operation fails"""
    pass


class ApplyChangesHandler:
    """Handles button-triggered apply operations"""

    def __init__(self, grpc_client, active_emulations, rabbitmq_publisher):
        self.grpc_client = grpc_client
        self.active_emulations = active_emulations
        self.rabbitmq_publisher = rabbitmq_publisher
        self.applied_operations = []

    async def apply_changes(self, topology_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply staged changes to running emulation, then persist to database.

        Flow:
        1. Validate all changes can be applied to Mininet-WiFi
        2. Apply changes to emulation in order:
           - Add new devices
           - Update existing devices
           - Add new links
           - Update existing links
           - Remove links
           - Remove devices
        3. If ALL successful → Save to database via Topology Service
        4. If ANY fails → Rollback changes in Mininet, return error
        5. Return detailed results
        """
        if topology_id not in self.active_emulations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active emulation for topology {topology_id}"
            )

        # Track applied changes for rollback
        self.applied_operations = []
        failed_operations = []

        try:
            logger.info(f"Starting apply changes for topology {topology_id}")
            logger.info(f"Changes summary: {self._summarize_changes(changes)}")

            # Phase 1: Add new devices
            add_devices = changes.get('add_devices', [])
            for device in add_devices:
                logger.info(f"Adding device: {device.get('name')} ({device.get('type')})")
                success = await self._add_device_to_emulation(topology_id, device)
                if success:
                    self.applied_operations.append(('add_device', device))
                else:
                    failed_operations.append(('add_device', device, "Failed to create"))
                    raise ApplyException(f"Failed to add device {device.get('name')}")

            # Phase 2: Update devices
            update_devices = changes.get('update_devices', [])
            for device in update_devices:
                logger.info(f"Updating device: {device.get('name')}")
                success = await self._update_device_in_emulation(topology_id, device)
                if success:
                    self.applied_operations.append(('update_device', device))
                else:
                    failed_operations.append(('update_device', device, "Failed to update"))
                    raise ApplyException(f"Failed to update device {device.get('name')}")

            # Phase 3: Add new links
            add_links = changes.get('add_links', [])
            for link in add_links:
                logger.info(f"Adding link: {link.get('source_node_id')} <-> {link.get('target_node_id')}")
                success = await self._add_link_to_emulation(topology_id, link)
                if success:
                    self.applied_operations.append(('add_link', link))
                else:
                    failed_operations.append(('add_link', link, "Failed to create"))
                    raise ApplyException("Failed to add link")

            # Phase 4: Update links
            update_links = changes.get('update_links', [])
            for link in update_links:
                logger.info(f"Updating link: {link.get('source_node_id')} <-> {link.get('target_node_id')}")
                success = await self._update_link_in_emulation(topology_id, link)
                if success:
                    self.applied_operations.append(('update_link', link))
                else:
                    failed_operations.append(('update_link', link, "Failed to update"))
                    raise ApplyException("Failed to update link")

            # Phase 5: Remove links (before removing devices)
            remove_links = changes.get('remove_links', [])
            for link in remove_links:
                logger.info(f"Removing link: {link.get('source_node_id')} <-> {link.get('target_node_id')}")
                success = await self._remove_link_from_emulation(topology_id, link)
                if success:
                    self.applied_operations.append(('remove_link', link))
                else:
                    # Continue on link removal failures (link might already be gone)
                    logger.warning(f"Failed to remove link, continuing: {link}")

            # Phase 6: Remove devices
            remove_devices = changes.get('remove_devices', [])
            for device in remove_devices:
                logger.info(f"Removing device: {device.get('name')}")
                success = await self._remove_device_from_emulation(
                    topology_id, device.get('name'), device.get('id')
                )
                if success:
                    self.applied_operations.append(('remove_device', device))
                else:
                    failed_operations.append(('remove_device', device, "Failed to remove"))
                    raise ApplyException(f"Failed to remove device {device.get('name')}")

            # ===== ALL MININET OPERATIONS SUCCESSFUL =====
            # Now persist to database via Topology Service

            logger.info(f"All Mininet operations successful ({len(self.applied_operations)} ops). Persisting to database...")

            db_success = await self._persist_changes_to_database(topology_id, changes)

            if not db_success:
                logger.error("Database persistence failed! Mininet and DB are now out of sync!")
                # TODO: Implement compensation logic or manual sync
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Applied to emulation but failed to save to database"
                )

            # Publish success event
            try:
                self.rabbitmq_publisher.publish("emulation.changes.applied", {
                    'topology_id': topology_id,
                    'timestamp': self._iso_now(),
                    'changes_count': len(self.applied_operations),
                    'summary': self._summarize_changes(changes)
                })
            except Exception as exc:
                logger.error(f"Failed to publish changes.applied event: {exc}")

            logger.info(f"Apply changes completed successfully for topology {topology_id}")

            return {
                "success": True,
                "message": "All changes applied successfully",
                "applied_count": len(self.applied_operations),
                "results": {
                    "devices_added": len(add_devices),
                    "devices_updated": len(update_devices),
                    "devices_removed": len(remove_devices),
                    "links_added": len(add_links),
                    "links_updated": len(update_links),
                    "links_removed": len(remove_links)
                }
            }

        except ApplyException as e:
            # Rollback applied changes in reverse order
            logger.error(f"Apply failed: {e}. Rolling back {len(self.applied_operations)} operations")

            rollback_count = await self._rollback_operations(self.applied_operations)

            return {
                "success": False,
                "message": str(e),
                "applied_count": len(self.applied_operations),
                "rolled_back_count": rollback_count,
                "failed_operations": failed_operations
            }

        except Exception as e:
            logger.error(f"Unexpected error during apply: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}"
            )

    async def _add_device_to_emulation(self, topology_id: str, device_data: Dict) -> bool:
        """Add a new device to running emulation"""
        # Import the existing add_device_to_emulation function from orchestrator main.py
        from main import add_device_to_emulation
        return await add_device_to_emulation(topology_id, device_data)

    async def _update_device_in_emulation(self, topology_id: str, device_data: Dict) -> bool:
        """Update existing device in running emulation"""
        from main import sync_device_to_emulation
        return await sync_device_to_emulation(topology_id, device_data)

    async def _add_link_to_emulation(self, topology_id: str, link_data: Dict) -> bool:
        """Add a new link to running emulation"""
        from main import add_link_to_emulation
        return await add_link_to_emulation(topology_id, link_data)

    async def _update_link_in_emulation(self, topology_id: str, link_data: Dict) -> bool:
        """Update existing link in running emulation"""
        from main import sync_link_to_emulation
        return await sync_link_to_emulation(topology_id, link_data)

    async def _remove_link_from_emulation(self, topology_id: str, link_data: Dict) -> bool:
        """Remove a link from running emulation"""
        from main import remove_link_from_emulation
        return await remove_link_from_emulation(topology_id, link_data)

    async def _remove_device_from_emulation(
        self, topology_id: str, device_name: str, device_id: Optional[str] = None
    ) -> bool:
        """Remove a device from running emulation"""
        from main import remove_device_from_emulation
        return await remove_device_from_emulation(topology_id, device_name, device_id)

    async def _persist_changes_to_database(self, topology_id: str, changes: Dict) -> bool:
        """
        Persist validated changes to database via Topology Service API.
        """
        try:
            async with httpx.AsyncClient(timeout=TOPOLOGY_REQUEST_TIMEOUT) as client:
                # POST batch update endpoint
                response = await client.post(
                    f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}/batch-update",
                    json=changes
                )

                if response.status_code == 200:
                    logger.info(f"Successfully persisted changes to database for {topology_id}")
                    return True
                else:
                    logger.error(f"Database persistence failed: {response.status_code} {response.text}")
                    return False

        except httpx.RequestError as exc:
            logger.error(f"Network error during database persistence: {exc}")
            return False
        except Exception as e:
            logger.error(f"Exception during database persistence: {e}")
            return False

    async def _rollback_operations(self, applied_operations: List[Tuple]) -> int:
        """
        Rollback applied operations in reverse order.
        Returns count of successfully rolled back operations.
        """
        rollback_count = 0

        # Reverse order: last applied, first rolled back
        for operation, data in reversed(applied_operations):
            try:
                if operation == 'add_device':
                    # Rollback: remove device
                    device_name = data.get('name')
                    device_id = data.get('id')
                    topology_id = self._extract_topology_id(data)
                    await self._remove_device_from_emulation(topology_id, device_name, device_id)
                    rollback_count += 1
                    logger.info(f"Rolled back: removed device {device_name}")

                elif operation == 'update_device':
                    # Rollback: restore original state (if we had snapshot)
                    logger.warning(f"Cannot rollback device update for {data.get('name')} (no snapshot)")

                elif operation == 'remove_device':
                    # Rollback: re-add device
                    topology_id = self._extract_topology_id(data)
                    await self._add_device_to_emulation(topology_id, data)
                    rollback_count += 1
                    logger.info(f"Rolled back: re-added device {data.get('name')}")

                elif operation == 'add_link':
                    # Rollback: remove link
                    topology_id = self._extract_topology_id(data)
                    await self._remove_link_from_emulation(topology_id, data)
                    rollback_count += 1
                    logger.info(f"Rolled back: removed link")

                elif operation == 'update_link':
                    # Rollback: restore original params (if we had snapshot)
                    logger.warning(f"Cannot rollback link update (no snapshot)")

                elif operation == 'remove_link':
                    # Rollback: re-add link
                    topology_id = self._extract_topology_id(data)
                    await self._add_link_to_emulation(topology_id, data)
                    rollback_count += 1
                    logger.info(f"Rolled back: re-added link")

            except Exception as e:
                logger.error(f"Rollback failed for operation {operation}: {e}")

        logger.info(f"Rollback completed: {rollback_count}/{len(applied_operations)} operations rolled back")
        return rollback_count

    def _extract_topology_id(self, data: Dict) -> str:
        """Extract topology_id from data dict"""
        return data.get('topology_id', '')

    def _summarize_changes(self, changes: Dict) -> Dict:
        """Create a summary of changes for logging"""
        return {
            'devices_to_add': len(changes.get('add_devices', [])),
            'devices_to_update': len(changes.get('update_devices', [])),
            'devices_to_remove': len(changes.get('remove_devices', [])),
            'links_to_add': len(changes.get('add_links', [])),
            'links_to_update': len(changes.get('update_links', [])),
            'links_to_remove': len(changes.get('remove_links', []))
        }

    def _iso_now(self) -> str:
        """Return current UTC time as ISO8601 string."""
        return datetime.now(timezone.utc).isoformat()
