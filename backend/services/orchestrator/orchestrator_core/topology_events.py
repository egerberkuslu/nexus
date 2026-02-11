from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import status


@dataclass(slots=True)
class TopologyEventHandlers:
    logger: Any
    topology_service_url: str
    topology_request_timeout: float
    active_emulations: Any
    rabbitmq_publisher: Any
    grpc_client_manager: Any
    require_grpc_client: Any
    remove_emulation_container: Any
    sync_topology_to_emulation: Any
    sync_device_to_emulation: Any
    sync_link_to_emulation: Any
    add_device_to_emulation: Any
    remove_device_from_emulation: Any
    add_link_to_emulation: Any
    remove_link_from_emulation: Any

    def handle_topology_created(self, message: Dict[str, Any]) -> None:
        """Handle topology created event."""
        self.logger.info("Topology created: %s", message)
        # Prepare emulation environment if needed

    def handle_topology_updated(self, message: Dict[str, Any]) -> None:
        """Handle topology updated event - full topology refresh."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")

        logger.info("Topology updated event received: %s", message)
        if not topology_id:
            logger.warning("No topology_id in message, skipping sync.")
            return

        if topology_id not in self.active_emulations:
            logger.info(
                "Topology %s was updated, but no active emulation is running. Skipping sync.",
                topology_id,
            )
            return

        logger.info("Topology is active. Triggering background sync for %s", topology_id)

        async def fetch_and_sync() -> None:
            try:
                async with httpx.AsyncClient(timeout=self.topology_request_timeout) as client:
                    response = await client.get(f"{self.topology_service_url}/api/topologies/{topology_id}")
                    if response.status_code == status.HTTP_200_OK:
                        topology_data = response.json()
                        logger.info("Successfully fetched topology %s for sync.", topology_id)
                        await self.sync_topology_to_emulation(topology_id, topology_data)
                        return
                    logger.error(
                        "Failed to fetch topology %s for sync. Status: %s, Response: %s",
                        topology_id,
                        response.status_code,
                        response.text,
                    )
            except Exception as exc:
                logger.error(
                    "An exception occurred during the fetch_and_sync process for topology %s: %s",
                    topology_id,
                    exc,
                    exc_info=True,
                )

        def run_sync_in_thread() -> None:
            logger.info("Starting new thread for topology sync: %s", topology_id)
            try:
                asyncio.run(fetch_and_sync())
                logger.info("Thread finished for topology sync: %s", topology_id)
            except Exception as exc:
                logger.error("Exception in sync thread for topology %s: %s", topology_id, exc, exc_info=True)

        sync_thread = threading.Thread(target=run_sync_in_thread, daemon=True)
        sync_thread.start()

    def handle_topology_deleted(self, message: Dict[str, Any]) -> None:
        """Handle topology deleted event."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        logger.info("Topology deleted: %s", message)

        if topology_id not in self.active_emulations:
            return

        info = self.active_emulations.get(topology_id)
        if not info:
            return

        emulation_id = info.get("emulation_id")
        container_name = info.get("container_name")

        # Stop the emulation via gRPC
        if emulation_id:
            try:
                client = self.grpc_client_manager.get_client(topology_id) or self.require_grpc_client(
                    topology_id=topology_id
                )
                client.stop_emulation(emulation_id, cleanup=True)
            except Exception as exc:
                logger.warning("Failed to stop emulation %s via gRPC: %s", emulation_id, exc)

        # Remove the Docker container
        if container_name:
            logger.info("Removing container %s for deleted topology %s", container_name, topology_id)
            self.remove_emulation_container(container_name)

        # Remove from active emulations tracking
        self.active_emulations.delete(topology_id)
        self.grpc_client_manager.remove_client(topology_id)

    def handle_project_deleted(self, message: Dict[str, Any]) -> None:
        """Handle project deleted event - best-effort logging for cleanup coordination."""
        logger = self.logger
        project_id = (message or {}).get("project_id")
        logger.info("Project deleted event received: %s", message)

        if not project_id:
            logger.warning("Project deletion message missing project_id")
            return

        logger.info("Cleaning up containers for deleted project %s", project_id)
        for topology_id, info in (self.active_emulations.get_all() or {}).items():
            try:
                container_name = (info or {}).get("container_name")
                if container_name:
                    logger.info(
                        "Found container %s for topology %s - will be cleaned up with topology deletion",
                        container_name,
                        topology_id,
                    )
            except Exception as exc:
                logger.error("Error processing emulation record during project cleanup: %s", exc)

    def handle_topology_node_updated(self, message: Dict[str, Any]) -> None:
        """Handle node updates - synchronize device changes for active emulations."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        node_id = (message or {}).get("node_id")
        logger.info("Topology node updated: %s", message)

        if not topology_id or not node_id:
            logger.warning("Node update message missing topology_id or node_id: %s", message)
            return

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping node update.", topology_id)
            return

        async def fetch_and_update_node() -> None:
            async with httpx.AsyncClient(timeout=self.topology_request_timeout) as client:
                response = await client.get(
                    f"{self.topology_service_url}/api/topologies/{topology_id}/nodes/{node_id}"
                )
                if response.status_code == status.HTTP_200_OK:
                    node_data = response.json()
                    client_instance = self.require_grpc_client(topology_id=topology_id)
                    success = await self.sync_device_to_emulation(topology_id, node_data, client=client_instance)
                    if success:
                        try:
                            self.rabbitmq_publisher.publish(
                                "emulation.device.updated",
                                {"topology_id": topology_id, "node_id": node_id, "device_name": node_data.get("name")},
                            )
                        except Exception as exc:
                            logger.error("Failed to publish emulation.device.updated event: %s", exc)
                    else:
                        logger.error("Failed to synchronize device %s in emulation.", node_id)
                    return

                logger.error(
                    "Failed to fetch node %s for topology %s: %s %s",
                    node_id,
                    topology_id,
                    response.status_code,
                    response.text,
                )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_and_update_node())
        finally:
            loop.close()

    def handle_topology_link_updated(self, message: Dict[str, Any]) -> None:
        """Handle link updates - sync link parameters in running emulation."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        link_id = (message or {}).get("link_id")
        logger.info("Topology link updated: %s", message)

        if not topology_id or not link_id:
            logger.warning("Link update message missing topology_id or link_id: %s", message)
            return

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping link update.", topology_id)
            return

        async def fetch_and_update_link() -> None:
            async with httpx.AsyncClient(timeout=self.topology_request_timeout) as client:
                response = await client.get(
                    f"{self.topology_service_url}/api/topologies/{topology_id}/links/{link_id}"
                )
                if response.status_code == status.HTTP_200_OK:
                    link_data = response.json()
                    client_instance = self.require_grpc_client(topology_id=topology_id)
                    success = await self.sync_link_to_emulation(topology_id, link_data, client=client_instance)
                    if success:
                        try:
                            self.rabbitmq_publisher.publish(
                                "emulation.link.updated", {"topology_id": topology_id, "link_id": link_id}
                            )
                        except Exception as exc:
                            logger.error("Failed to publish emulation.link.updated event: %s", exc)
                    else:
                        logger.error("Failed to synchronize link %s in emulation.", link_id)
                    return

                logger.error(
                    "Failed to fetch link %s for topology %s: %s %s",
                    link_id,
                    topology_id,
                    response.status_code,
                    response.text,
                )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_and_update_link())
        finally:
            loop.close()

    def handle_topology_node_added(self, message: Dict[str, Any]) -> None:
        """Handle node/device added event - add device to running emulation."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        node_id = (message or {}).get("node_id")
        logger.info("Topology node added: %s", message)

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping node add.", topology_id)
            return

        logger.info("Adding new device %s to running emulation for topology %s", node_id, topology_id)

        async def fetch_and_add_node() -> None:
            async with httpx.AsyncClient(timeout=self.topology_request_timeout) as client:
                response = await client.get(f"{self.topology_service_url}/api/topologies/{topology_id}/nodes/{node_id}")
                if response.status_code == status.HTTP_200_OK:
                    node_data = response.json()
                    client_instance = self.require_grpc_client(topology_id=topology_id)
                    success = await self.add_device_to_emulation(topology_id, node_data, client=client_instance)
                    if success:
                        logger.info("Successfully added device %s to emulation", node_id)
                        try:
                            self.rabbitmq_publisher.publish(
                                "emulation.device.added",
                                {"topology_id": topology_id, "node_id": node_id, "device_name": node_data.get("name")},
                            )
                        except Exception as exc:
                            logger.error("Failed to publish emulation.device.added event: %s", exc)
                        return
                    logger.error("Failed to add device %s to emulation", node_id)
                    return

                logger.error("Failed to fetch node %s: %s", node_id, response.status_code)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_and_add_node())
        finally:
            loop.close()

    def handle_topology_node_deleted(self, message: Dict[str, Any]) -> None:
        """Handle node/device deleted event - remove device from running emulation."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        node_id = (message or {}).get("node_id")
        node_name = (message or {}).get("node_name")
        logger.info("Topology node deleted: %s", message)

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping node delete.", topology_id)
            return

        device_name = node_name or node_id
        logger.info("Removing device %s from running emulation for topology %s", device_name, topology_id)

        async def remove_node() -> None:
            client_instance = self.require_grpc_client(topology_id=topology_id)
            success = await self.remove_device_from_emulation(
                topology_id, device_name, device_id=node_id, client=client_instance
            )
            if success:
                logger.info("Successfully removed device %s from emulation", device_name)
                try:
                    self.rabbitmq_publisher.publish(
                        "emulation.device.removed",
                        {"topology_id": topology_id, "node_id": node_id, "device_name": device_name},
                    )
                except Exception as exc:
                    logger.error("Failed to publish emulation.device.removed event: %s", exc)
                return
            logger.error("Failed to remove device %s from emulation", device_name)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(remove_node())
        finally:
            loop.close()

    def handle_topology_link_added(self, message: Dict[str, Any]) -> None:
        """Handle link added event - add link to running emulation."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        link_id = (message or {}).get("link_id")
        logger.info("Topology link added: %s", message)

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping link add.", topology_id)
            return

        logger.info("Adding new link %s to running emulation for topology %s", link_id, topology_id)

        async def fetch_and_add_link() -> None:
            async with httpx.AsyncClient(timeout=self.topology_request_timeout) as client:
                response = await client.get(f"{self.topology_service_url}/api/topologies/{topology_id}/links/{link_id}")
                if response.status_code == status.HTTP_200_OK:
                    link_data = response.json()
                    client_instance = self.require_grpc_client(topology_id=topology_id)
                    success = await self.add_link_to_emulation(topology_id, link_data, client=client_instance)
                    if success:
                        logger.info("Successfully added link %s to emulation", link_id)
                        try:
                            self.rabbitmq_publisher.publish(
                                "emulation.link.added", {"topology_id": topology_id, "link_id": link_id}
                            )
                        except Exception as exc:
                            logger.error("Failed to publish emulation.link.added event: %s", exc)
                        return
                    logger.error("Failed to add link %s to emulation", link_id)
                    return
                logger.error("Failed to fetch link %s: %s", link_id, response.status_code)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_and_add_link())
        finally:
            loop.close()

    def handle_topology_link_deleted(self, message: Dict[str, Any]) -> None:
        """Handle link deleted event - remove link from running emulation."""
        logger = self.logger
        topology_id = (message or {}).get("topology_id")
        link_id = (message or {}).get("link_id")
        source_node_id = (message or {}).get("source_node_id")
        target_node_id = (message or {}).get("target_node_id")
        logger.info("Topology link deleted: %s", message)

        if topology_id not in self.active_emulations:
            logger.info("Topology %s has no active emulation. Skipping link delete.", topology_id)
            return

        logger.info(
            "Removing link %s-%s from running emulation for topology %s", source_node_id, target_node_id, topology_id
        )

        async def remove_link() -> None:
            link_data = {"source_node_id": source_node_id, "target_node_id": target_node_id}
            client_instance = self.require_grpc_client(topology_id=topology_id)
            success = await self.remove_link_from_emulation(topology_id, link_data, client=client_instance)
            if success:
                logger.info("Successfully removed link %s from emulation", link_id)
                try:
                    self.rabbitmq_publisher.publish(
                        "emulation.link.removed",
                        {
                            "topology_id": topology_id,
                            "link_id": link_id,
                            "source_node_id": source_node_id,
                            "target_node_id": target_node_id,
                        },
                    )
                except Exception as exc:
                    logger.error("Failed to publish emulation.link.removed event: %s", exc)
                return
            logger.error("Failed to remove link %s from emulation", link_id)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(remove_link())
        finally:
            loop.close()

