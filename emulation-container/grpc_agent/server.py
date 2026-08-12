#!/usr/bin/env python3
"""
Caduceus-Flux gRPC Agent Server
Provides remote control interface for the unified emulation container
"""

from __future__ import annotations

import logging
import grpc
from concurrent import futures
import time
import sys
import os
import asyncio

# Add proto directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import emulation_pb2
import emulation_pb2_grpc

def _configure_docker_sdk_timeout() -> None:
    """
    Containernet uses docker-py's default timeout (60s). Under load (e.g., multiple
    topologies starting concurrently) docker container creation can legitimately take
    longer, causing `requests.exceptions.ReadTimeout` and broken topology builds.
    """
    try:
        import docker.constants as docker_constants
        import docker.client as docker_client

        timeout_raw = os.getenv("CADUCEUS_DOCKER_HTTP_TIMEOUT") or os.getenv("CADUCEUS_DOCKER_SDK_TIMEOUT")
        timeout = int(timeout_raw) if timeout_raw else 300
        if timeout <= 0:
            return

        docker_constants.DEFAULT_TIMEOUT_SECONDS = timeout
        # docker.from_env() uses docker.client.DEFAULT_TIMEOUT_SECONDS which is
        # imported at module-load time from docker.constants, so patch both.
        if hasattr(docker_client, "DEFAULT_TIMEOUT_SECONDS"):
            docker_client.DEFAULT_TIMEOUT_SECONDS = timeout
        logging.getLogger(__name__).info("Docker SDK default timeout set to %ss", timeout)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to configure Docker SDK timeout: %s", exc)


_configure_docker_sdk_timeout()

from emulation_manager import EmulationManager
from device_handler import DeviceHandler
from link_handler import LinkHandler
from protocol_handler import ProtocolHandler
from state_handler import StateHandler
from monitoring_handler import MonitoringHandler
import pty
import select
import termios
import struct
import fcntl
from custom_cli import CaduceusCLI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GRPC_SERVER_HOST = os.getenv("EMULATION_SERVER_HOST", "0.0.0.0")
GRPC_SERVER_PORT = int(os.getenv("EMULATION_SERVER_PORT", "50051"))


class EmulationServiceImpl(emulation_pb2_grpc.EmulationServiceServicer):
    """Implementation of EmulationService gRPC interface"""

    def __init__(self):
        logger.info("Initializing EmulationService...")
        self.emulation_manager = EmulationManager()
        self.device_handler = DeviceHandler(self.emulation_manager)
        self.link_handler = LinkHandler(self.emulation_manager)
        self.protocol_handler = ProtocolHandler(self.emulation_manager)
        self.state_handler = StateHandler(self.emulation_manager)
        self.monitoring_handler = MonitoringHandler(self.emulation_manager)
        logger.info("EmulationService initialized")

    # Lifecycle Management
    async def StartEmulation(self, request, context):
        """Start a new emulation instance"""
        logger.info(f"Starting emulation: {request.topology_id}")
        try:
            # Run blocking emulation start in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.emulation_manager.start_emulation(
                    topology_id=request.topology_id,
                    topology=request.topology,
                    options=dict(request.options)
                )
            )
            return emulation_pb2.EmulationResponse(
                success=result['success'],
                message=result['message'],
                emulation_id=result.get('emulation_id', '')
            )
        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Failed to start emulation: {error_msg}", exc_info=True)
            return emulation_pb2.EmulationResponse(
                success=False,
                message=error_msg if error_msg and error_msg != '0' else f"Network startup failed: {type(e).__name__}",
                emulation_id=''
            )

    def StopEmulation(self, request, context):
        """Stop a running emulation"""
        logger.info(f"Stopping emulation: {request.emulation_id}")
        try:
            result = self.emulation_manager.stop_emulation(
                emulation_id=request.emulation_id,
                cleanup=request.cleanup
            )
            return emulation_pb2.EmulationResponse(
                success=result['success'],
                message=result['message'],
                emulation_id=request.emulation_id
            )
        except Exception as e:
            logger.error(f"Failed to stop emulation: {e}")
            return emulation_pb2.EmulationResponse(
                success=False,
                message=str(e),
                emulation_id=request.emulation_id
            )

    def PauseEmulation(self, request, context):
        """Pause a running emulation"""
        logger.info(f"Pausing emulation: {request.emulation_id}")
        try:
            result = self.emulation_manager.pause_emulation(request.emulation_id)
            return emulation_pb2.EmulationResponse(
                success=result['success'],
                message=result['message'],
                emulation_id=request.emulation_id
            )
        except Exception as e:
            logger.error(f"Failed to pause emulation: {e}")
            return emulation_pb2.EmulationResponse(
                success=False,
                message=str(e),
                emulation_id=request.emulation_id
            )

    def ResumeEmulation(self, request, context):
        """Resume a paused emulation"""
        logger.info(f"Resuming emulation: {request.emulation_id}")
        try:
            result = self.emulation_manager.resume_emulation(request.emulation_id)
            return emulation_pb2.EmulationResponse(
                success=result['success'],
                message=result['message'],
                emulation_id=request.emulation_id
            )
        except Exception as e:
            logger.error(f"Failed to resume emulation: {e}")
            return emulation_pb2.EmulationResponse(
                success=False,
                message=str(e),
                emulation_id=request.emulation_id
            )

    def GetEmulationStatus(self, request, context):
        """Get status of an emulation"""
        try:
            status = self.emulation_manager.get_status(request.emulation_id)
            return emulation_pb2.EmulationStatusResponse(
                status=status['status'],
                uptime_seconds=status.get('uptime_seconds', 0),
                device_count=status.get('device_count', 0),
                link_count=status.get('link_count', 0),
                metadata=status.get('metadata', {})
            )
        except Exception as e:
            logger.error(f"Failed to get emulation status: {e}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(e))
            return emulation_pb2.EmulationStatusResponse()

    # Device Management
    def AddHost(self, request, context):
        """Add a host to the emulation"""
        logger.info(f"Adding host: {request.name}")
        try:
            device = self.device_handler.add_host(
                name=request.name,
                ip=request.ip,
                ip6=request.ip6,
                mac=request.mac,
                default_route=request.default_route,
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Host {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add host: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddSwitch(self, request, context):
        """Add a switch to the emulation"""
        logger.info(f"Adding switch: {request.name}")
        try:
            device = self.device_handler.add_switch(
                name=request.name,
                switch_type=request.switch_type,
                openflow_version=request.openflow_version,
                controller=request.controller,
                datapath_id=request.datapath_id,
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Switch {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add switch: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddRouter(self, request, context):
        """Add a router to the emulation"""
        logger.info(f"Adding router: {request.name}")
        try:
            device = self.device_handler.add_router(
                name=request.name,
                protocols=list(request.protocols),
                router_daemon=request.router_daemon,
                protocol_configs=dict(request.protocol_configs),
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Router {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add router: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddAccessPoint(self, request, context):
        """Add an access point to the emulation"""
        logger.info(f"Adding access point: {request.name}")
        try:
            device = self.device_handler.add_access_point(
                name=request.name,
                ssid=request.ssid,
                mode=request.mode,
                channel=request.channel,
                security=request.security,
                password=request.password,
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Access point {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add access point: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddStation(self, request, context):
        """Add a wireless station to the emulation"""
        logger.info(f"Adding station: {request.name}")
        try:
            device = self.device_handler.add_station(
                name=request.name,
                ssid=request.ssid,
                mode=request.mode,
                security=request.security,
                password=request.password,
                mobility=request.mobility,
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Station {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add station: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddDockerContainer(self, request, context):
        """Add a Docker container to the emulation"""
        logger.info(f"Adding Docker container: {request.name}")
        try:
            device = self.device_handler.add_docker_container(
                name=request.name,
                image=request.image,
                command=list(request.command),
                environment=dict(request.environment),
                volumes=list(request.volumes),
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Docker container {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add Docker container: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def AddP4Switch(self, request, context):
        """Add a P4 programmable switch to the emulation"""
        logger.info(f"Adding P4 switch: {request.name}")
        try:
            device = self.device_handler.add_p4_switch(
                name=request.name,
                p4_source=request.p4_source,
                p4info_path=request.p4info_path,
                device_config_path=request.device_config_path,
                grpc_port=request.grpc_port,
                params=dict(request.params)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"P4 switch {request.name} added successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to add P4 switch: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def RemoveDevice(self, request, context):
        """Remove a device from the emulation"""
        logger.info(f"Removing device: {request.name}")
        try:
            result = self.device_handler.remove_device(request.name)
            return emulation_pb2.DeviceResponse(
                success=result['success'],
                message=result['message']
            )
        except Exception as e:
            logger.error(f"Failed to remove device: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def UpdateDevice(self, request, context):
        """Update device properties at runtime"""
        logger.info(f"Updating device: {request.name}")
        try:
            device = self.device_handler.update_device(
                name=request.name,
                updates=dict(request.updates)
            )
            return emulation_pb2.DeviceResponse(
                success=True,
                message=f"Device {request.name} updated successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to update device: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def GetDevice(self, request, context):
        """Get device information"""
        try:
            device = self.device_handler.get_device(request.name)
            return emulation_pb2.DeviceResponse(
                success=True,
                message="Device retrieved successfully",
                device=device
            )
        except Exception as e:
            logger.error(f"Failed to get device: {e}")
            return emulation_pb2.DeviceResponse(
                success=False,
                message=str(e)
            )

    def ListDevices(self, request, context):
        """List all devices in the emulation"""
        try:
            devices = self.device_handler.list_devices(
                device_type=request.device_type if request.device_type else None
            )
            return emulation_pb2.ListDevicesResponse(devices=devices)
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.ListDevicesResponse()

    # Position Control (runtime mobility)
    def SetPosition(self, request, context):
        """Update the 3D position of a single station/access point"""
        try:
            result = self.device_handler.set_position(
                device_name=request.device_name,
                x=request.x,
                y=request.y,
                z=request.z
            )
            return emulation_pb2.SetPositionResponse(
                success=True,
                message=result['message'],
                updated_count=1
            )
        except Exception as e:
            logger.error(f"Failed to set position: {e}")
            return emulation_pb2.SetPositionResponse(
                success=False,
                message=str(e),
                updated_count=0
            )

    def SetPositionsBatch(self, request, context):
        """Update several device positions in a single round trip.

        Intended for an external physics engine pushing the whole fleet at ~10 Hz,
        so one failing device must not abort the rest of the batch.
        """
        total = len(request.positions)
        updated = 0
        errors = []

        for item in request.positions:
            try:
                self.device_handler.set_position(
                    device_name=item.device_name,
                    x=item.x,
                    y=item.y,
                    z=item.z
                )
                updated += 1
            except Exception as e:
                errors.append(f"{item.device_name}: {e}")

        message = f"Updated {updated}/{total} device positions"
        if errors:
            logger.warning("SetPositionsBatch: %s (%s)", message, '; '.join(errors))
            message = f"{message} ({'; '.join(errors)})"

        return emulation_pb2.SetPositionResponse(
            success=not errors,
            message=message,
            updated_count=updated
        )

    # Link Management
    def AddLink(self, request, context):
        """Add a link between two devices"""
        logger.info(f"Adding link: {request.node1} <-> {request.node2}")
        try:
            link = self.link_handler.add_link(
                node1=request.node1,
                node2=request.node2,
                port1=request.port1,
                port2=request.port2,
                params=request.params
            )
            return emulation_pb2.LinkResponse(
                success=True,
                message=f"Link added between {request.node1} and {request.node2}",
                link=link
            )
        except Exception as e:
            logger.error(f"Failed to add link: {e}")
            return emulation_pb2.LinkResponse(
                success=False,
                message=str(e)
            )

    def RemoveLink(self, request, context):
        """Remove a link between two devices"""
        logger.info(f"Removing link: {request.node1} <-> {request.node2}")
        try:
            result = self.link_handler.remove_link(request.node1, request.node2)
            return emulation_pb2.LinkResponse(
                success=result['success'],
                message=result['message']
            )
        except Exception as e:
            logger.error(f"Failed to remove link: {e}")
            return emulation_pb2.LinkResponse(
                success=False,
                message=str(e)
            )

    def UpdateLink(self, request, context):
        """Update link parameters at runtime"""
        logger.info(f"Updating link: {request.node1} <-> {request.node2}")
        try:
            link = self.link_handler.update_link(
                node1=request.node1,
                node2=request.node2,
                params=request.params
            )
            return emulation_pb2.LinkResponse(
                success=True,
                message=f"Link updated between {request.node1} and {request.node2}",
                link=link
            )
        except Exception as e:
            logger.error(f"Failed to update link: {e}")
            return emulation_pb2.LinkResponse(
                success=False,
                message=str(e)
            )

    def GetLink(self, request, context):
        """Get link information"""
        try:
            link = self.link_handler.get_link(request.node1, request.node2)
            return emulation_pb2.LinkResponse(
                success=True,
                message="Link retrieved successfully",
                link=link
            )
        except Exception as e:
            logger.error(f"Failed to get link: {e}")
            return emulation_pb2.LinkResponse(
                success=False,
                message=str(e)
            )

    def ListLinks(self, request, context):
        """List all links in the emulation"""
        try:
            links = self.link_handler.list_links(
                node=request.node if request.node else None
            )
            return emulation_pb2.ListLinksResponse(links=links)
        except Exception as e:
            logger.error(f"Failed to list links: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.ListLinksResponse()

    # Command Execution
    def ExecuteCommand(self, request, context):
        """Execute a command on a device"""
        logger.info(f"Executing command on {request.device}: {request.command}")
        try:
            result = self.device_handler.execute_command(
                device=request.device,
                command=request.command
            )
            return emulation_pb2.ExecuteCommandResponse(
                success=result['success'],
                stdout=result.get('stdout', ''),
                stderr=result.get('stderr', ''),
                exit_code=result.get('exit_code', -1)
            )
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return emulation_pb2.ExecuteCommandResponse(
                success=False,
                stdout='',
                stderr=str(e),
                exit_code=-1
            )

    def ExecuteCommandStream(self, request, context):
        """Execute a command on a device with streaming output"""
        logger.info(f"Executing streaming command on {request.device}: {request.command}")
        try:
            for output in self.device_handler.execute_command_stream(
                device=request.device,
                command=request.command
            ):
                yield emulation_pb2.ExecuteCommandResponse(
                    success=output['success'],
                    stdout=output.get('stdout', ''),
                    stderr=output.get('stderr', ''),
                    exit_code=output.get('exit_code', 0)
                )
        except Exception as e:
            logger.error(f"Failed to execute streaming command: {e}")
            yield emulation_pb2.ExecuteCommandResponse(
                success=False,
                stdout='',
                stderr=str(e),
                exit_code=-1
            )

    # Protocol Management
    def ConfigureProtocol(self, request, context):
        """Configure a protocol on a device"""
        logger.info(f"Configuring protocol {request.protocol} on {request.device}")
        try:
            status = self.protocol_handler.configure_protocol(
                device=request.device,
                protocol=request.protocol,
                config=dict(request.config)
            )
            return emulation_pb2.ProtocolResponse(
                success=True,
                message=f"Protocol {request.protocol} configured on {request.device}",
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to configure protocol: {e}")
            return emulation_pb2.ProtocolResponse(
                success=False,
                message=str(e)
            )

    def EnableProtocol(self, request, context):
        """Enable a protocol on a device"""
        logger.info(f"Enabling protocol {request.protocol} on {request.device}")
        try:
            status = self.protocol_handler.enable_protocol(
                device=request.device,
                protocol=request.protocol
            )
            return emulation_pb2.ProtocolResponse(
                success=True,
                message=f"Protocol {request.protocol} enabled on {request.device}",
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to enable protocol: {e}")
            return emulation_pb2.ProtocolResponse(
                success=False,
                message=str(e)
            )

    def DisableProtocol(self, request, context):
        """Disable a protocol on a device"""
        logger.info(f"Disabling protocol {request.protocol} on {request.device}")
        try:
            status = self.protocol_handler.disable_protocol(
                device=request.device,
                protocol=request.protocol
            )
            return emulation_pb2.ProtocolResponse(
                success=True,
                message=f"Protocol {request.protocol} disabled on {request.device}",
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to disable protocol: {e}")
            return emulation_pb2.ProtocolResponse(
                success=False,
                message=str(e)
            )

    def SwitchProtocol(self, request, context):
        """Switch from one protocol to another without restart"""
        logger.info(f"Switching protocol on {request.device}: {request.from_protocol} -> {request.to_protocol}")
        try:
            status = self.protocol_handler.switch_protocol(
                device=request.device,
                from_protocol=request.from_protocol,
                to_protocol=request.to_protocol,
                preserve_config=request.preserve_config
            )
            return emulation_pb2.ProtocolResponse(
                success=True,
                message=f"Protocol switched on {request.device}",
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to switch protocol: {e}")
            return emulation_pb2.ProtocolResponse(
                success=False,
                message=str(e)
            )

    def GetProtocolStatus(self, request, context):
        """Get protocol status"""
        try:
            status_response = self.protocol_handler.get_protocol_status(
                device=request.device,
                protocol=request.protocol
            )
            return status_response
        except Exception as e:
            logger.error(f"Failed to get protocol status: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.ProtocolStatusResponse()

    # State Management
    def CaptureState(self, request, context):
        """Capture complete emulation state"""
        logger.info(f"Capturing state: {request.snapshot_name}")
        try:
            response = self.state_handler.capture_state(
                snapshot_name=request.snapshot_name,
                devices=list(request.devices),
                include_routing_tables=request.include_routing_tables,
                include_flow_tables=request.include_flow_tables,
                include_arp_tables=request.include_arp_tables
            )
            return response
        except Exception as e:
            logger.error(f"Failed to capture state: {e}")
            return emulation_pb2.CaptureStateResponse(
                success=False,
                message=str(e)
            )

    def RestoreState(self, request, context):
        """Restore emulation state from snapshot"""
        logger.info(f"Restoring state: {request.snapshot_name}")
        try:
            response = self.state_handler.restore_state(
                snapshot_name=request.snapshot_name,
                state_data=request.state_data
            )
            return response
        except Exception as e:
            logger.error(f"Failed to restore state: {e}")
            return emulation_pb2.RestoreStateResponse(
                success=False,
                message=str(e)
            )

    def GetRoutingTable(self, request, context):
        """Get routing table from a device"""
        try:
            response = self.state_handler.get_routing_table(request.device)
            return response
        except Exception as e:
            logger.error(f"Failed to get routing table: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.GetRoutingTableResponse()

    def GetFlowTable(self, request, context):
        """Get flow table from a switch"""
        try:
            response = self.state_handler.get_flow_table(request.switch)
            return response
        except Exception as e:
            logger.error(f"Failed to get flow table: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.GetFlowTableResponse()

    def GetARPTable(self, request, context):
        """Get ARP table from a device"""
        try:
            response = self.state_handler.get_arp_table(request.device)
            return response
        except Exception as e:
            logger.error(f"Failed to get ARP table: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.GetARPTableResponse()

    # Monitoring
    def GetMetrics(self, request, context):
        """Get metrics from devices"""
        try:
            response = self.monitoring_handler.get_metrics(
                devices=list(request.devices),
                metrics=list(request.metrics)
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.GetMetricsResponse()

    def StreamMetrics(self, request, context):
        """Stream metrics from devices"""
        logger.info(f"Starting metric stream for devices: {request.devices}")
        try:
            for update in self.monitoring_handler.stream_metrics(
                devices=list(request.devices),
                interval_seconds=request.interval_seconds
            ):
                yield update
        except Exception as e:
            logger.error(f"Failed to stream metrics: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))

    def GetInterfaceStats(self, request, context):
        """Get interface statistics"""
        try:
            response = self.monitoring_handler.get_interface_stats(
                device=request.device,
                interface=request.interface
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get interface stats: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return emulation_pb2.GetInterfaceStatsResponse()

    # Controller Management
    def SetController(self, request, context):
        """Set controller for a switch"""
        logger.info(f"Setting controller for {request.switch}: {request.controller_ip}:{request.controller_port}")
        try:
            self.device_handler.set_controller(
                switch=request.switch,
                controller_ip=request.controller_ip,
                controller_port=request.controller_port,
                protocol=request.protocol
            )
            return emulation_pb2.ControllerResponse(
                success=True,
                message=f"Controller set for {request.switch}"
            )
        except Exception as e:
            logger.error(f"Failed to set controller: {e}")
            return emulation_pb2.ControllerResponse(
                success=False,
                message=str(e)
            )

    def RemoveController(self, request, context):
        """Remove controller from a switch"""
        logger.info(f"Removing controller from {request.switch}")
        try:
            self.device_handler.remove_controller(request.switch)
            return emulation_pb2.ControllerResponse(
                success=True,
                message=f"Controller removed from {request.switch}"
            )
        except Exception as e:
            logger.error(f"Failed to remove controller: {e}")
            return emulation_pb2.ControllerResponse(
                success=False,
                message=str(e)
            )

    async def MininetCLI(self, request_iterator, context):
        """
        Interactive Mininet/Containernet CLI over gRPC.

        We intentionally do NOT `fork()` a second Python process to run Mininet's built-in CLI:
        forking duplicates Mininet Node objects and their underlying shell pipes, which is a
        common cause of `shell died on <node>` when both processes interact with nodes.

        This is a small line-oriented CLI that supports the main commands needed by the UI.
        """
        if not self.emulation_manager.is_running() or not self.emulation_manager.net:
            yield emulation_pb2.CLIResponse(error="No active emulation running.")
            return

        net = self.emulation_manager.net
        prompt = "containernet> "
        line_buf = ""

        loop = asyncio.get_running_loop()

        async def _node_cmd(node, cmd: str) -> str:
            return await loop.run_in_executor(None, lambda: node.cmd(cmd) or "")

        def _iter_node_groups():
            # Cover Mininet/Containernet + Mininet-WiFi common collections.
            for attr in ("controllers", "hosts", "routers", "stations", "aps", "switches"):
                group = getattr(net, attr, None)
                if not group:
                    continue
                if isinstance(group, (list, tuple)):
                    yield attr, list(group)
                else:
                    try:
                        yield attr, list(group)
                    except Exception:
                        continue

        def _all_node_names():
            names = []
            for _attr, group in _iter_node_groups():
                for n in group:
                    try:
                        name = str(getattr(n, "name", "") or "")
                        if name:
                            names.append(name)
                    except Exception:
                        pass
            # Preserve deterministic ordering and de-dupe.
            out = []
            seen = set()
            for name in names:
                if name in seen:
                    continue
                seen.add(name)
                out.append(name)
            return out

        async def _exec_shell(cmd: str) -> str:
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-lc",
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            text = ""
            if out:
                text += out.decode("utf-8", "ignore")
            if err:
                text += err.decode("utf-8", "ignore")
            return text

        async def _controllers_text() -> str:
            switches = list(getattr(net, "switches", []) or [])
            import json

            controller_connected: dict[str, str] = {}
            try:
                raw = await _exec_shell("ovs-vsctl --format=json --columns=target,is_connected list Controller 2>/dev/null")
                payload = json.loads(raw) if raw else {}
                headings = payload.get("headings") or []
                data = payload.get("data") or []
                idx = {h: i for i, h in enumerate(headings)}
                for row in data:
                    try:
                        target = row[idx["target"]]
                        is_conn = row[idx["is_connected"]]
                        controller_connected[str(target)] = "true" if bool(is_conn) else "false"
                    except Exception:
                        continue
            except Exception:
                controller_connected = {}

            if not switches:
                table = await _exec_shell("ovs-vsctl --columns=target,is_connected --format=table list Controller 2>/dev/null")
                return "*** No switches\r\n" + (table.replace("\n", "\r\n") if table else "")

            lines = []
            table = await _exec_shell("ovs-vsctl --columns=target,is_connected --format=table list Controller 2>/dev/null")
            if table:
                lines.append("*** OVS controllers:\r\n")
                lines.append(table.replace("\n", "\r\n"))
                if not table.endswith("\n"):
                    lines.append("\r\n")
                lines.append("\r\n")

            lines.append("*** Switch controllers:\r\n")
            for sw in switches:
                sw_name = str(getattr(sw, "name", "") or "")
                if not sw_name:
                    continue
                controller_out = await _exec_shell(f"ovs-vsctl get-controller {sw_name} 2>/dev/null")
                fail_mode = (await _exec_shell(f"ovs-vsctl get-fail-mode {sw_name} 2>/dev/null")).strip() or "—"
                targets: list[str] = []
                try:
                    parsed = json.loads(controller_out.strip()) if controller_out.strip() else []
                    if isinstance(parsed, str):
                        targets = [parsed]
                    elif isinstance(parsed, list):
                        targets = [str(x) for x in parsed if x]
                except Exception:
                    raw = controller_out.strip()
                    if raw and raw != "[]":
                        targets = [raw]

                if not targets:
                    lines.append(f"{sw_name}: controller=— fail_mode={fail_mode}\r\n")
                    continue

                target_states = []
                for t in targets:
                    state = controller_connected.get(str(t))
                    if state is None:
                        state = "?"
                    target_states.append(f"{t} (connected={state})")

                lines.append(f"{sw_name}: controller={', '.join(target_states)} fail_mode={fail_mode}\r\n")
            return "".join(lines)

        async def _pingall_text() -> str:
            hosts = []
            for attr in ("hosts", "routers", "stations"):
                group = getattr(net, attr, None)
                if group:
                    hosts.extend(list(group))
            if not hosts:
                return "*** Ping: no hosts\r\n"

            import ipaddress

            async def _get_ipv4_addrs(h):
                # Avoid nested quoting/awk; Mininet Node.cmd often runs via shells that can
                # mangle quotes. Parse `ip -o` output directly.
                out = await _node_cmd(h, "ip -4 -o addr show scope global")
                addrs = []
                for token in (out or "").splitlines():
                    token = token.strip()
                    if not token:
                        continue
                    parts = token.split()
                    if len(parts) < 4:
                        continue
                    cidr = parts[3].strip()
                    if "/" not in cidr:
                        continue
                    ip, pre = cidr.split("/", 1)
                    try:
                        addrs.append((ip.strip(), int(pre.strip())))
                    except Exception:
                        continue
                return addrs

            async def _select_dst_ip(src, dst):
                dst_addrs = await _get_ipv4_addrs(dst)
                if not dst_addrs:
                    return None
                src_addrs = await _get_ipv4_addrs(src)
                for src_ip, src_prefix in src_addrs:
                    try:
                        src_net = ipaddress.ip_network(f"{src_ip}/{src_prefix}", strict=False)
                    except Exception:
                        continue
                    for dst_ip, _dst_prefix in dst_addrs:
                        try:
                            if ipaddress.ip_address(dst_ip) in src_net:
                                return dst_ip
                        except Exception:
                            continue
                return dst_addrs[0][0]

            def _parse_rc(output: str) -> int:
                marker = "__RC:"
                if marker not in (output or ""):
                    return 1
                try:
                    return int((output or "").rsplit(marker, 1)[1].strip().splitlines()[0])
                except Exception:
                    return 1

            lines = ["*** Ping: testing ping reachability\r\n"]
            total = 0
            received = 0

            for src in hosts:
                lines.append(f"{src.name} -> ")
                for dst in hosts:
                    if src is dst:
                        continue
                    total += 1
                    dst_ip = await _select_dst_ip(src, dst)
                    if not dst_ip:
                        lines.append("X(no-ip) ")
                        continue
                    # Use an explicit return-code marker instead of parsing ping text.
                    out = await _node_cmd(
                        src,
                        f"sh -lc 'ping -c 1 -W 1 {dst_ip} >/dev/null 2>&1; echo __RC:$?'",
                    )
                    rc = _parse_rc(out)
                    if rc == 0:
                        received += 1
                        lines.append(f"{dst.name} ")
                    else:
                        lines.append(f"X(rc={rc},ip={dst_ip}) ")
                lines.append("\r\n")

            dropped = total - received
            pct = int(round((float(dropped) / float(total)) * 100.0)) if total else 0
            lines.append(f"*** Results: {pct}% dropped ({received}/{total} received)\r\n")
            return "".join(lines)

        async def _handle_line(cmdline: str) -> str:
            cmdline = (cmdline or "").strip()
            if not cmdline:
                return ""
            if cmdline in ("exit", "quit"):
                raise StopAsyncIteration
            if cmdline == "help":
                return (
                    "Commands: nodes, dump, net, links, pingall, controllers, sh <cmd>, <node> <cmd>, exit\r\n"
                    "Tip: use `dump` for detailed device info.\r\n"
                )

            def _build_group_index():
                by_name: dict[str, str] = {}
                for attr, group in _iter_node_groups():
                    for n in group:
                        try:
                            name = str(getattr(n, "name", "") or "")
                        except Exception:
                            continue
                        if name and name not in by_name:
                            by_name[name] = attr
                return by_name

            group_by_name = _build_group_index()

            def _node_kind(name: str, node_obj) -> str:
                kind = group_by_name.get(name)
                if kind:
                    return kind
                try:
                    cls = node_obj.__class__.__name__
                    return cls or "node"
                except Exception:
                    return "node"

            def _extract_ipv4(ip_text: str) -> str:
                val = (ip_text or "").strip()
                if not val:
                    return ""
                return val.split("/", 1)[0].strip()

            def _iter_intf_rows(node_obj):
                try:
                    intfs = list(node_obj.intfList() or [])
                except Exception:
                    intfs = []
                for intf in intfs:
                    try:
                        iname = str(getattr(intf, "name", "") or "")
                        mac = str(intf.MAC() or "") if hasattr(intf, "MAC") else ""
                        ip = str(intf.IP() or "") if hasattr(intf, "IP") else ""
                        yield iname, mac, _extract_ipv4(ip)
                    except Exception:
                        continue

            async def _dump_nodes_text() -> str:
                names = _all_node_names()
                if not names:
                    return "*** No nodes\r\n"

                lines: list[str] = []
                for name in names:
                    try:
                        node_obj = net.get(name)
                    except Exception:
                        continue

                    kind = _node_kind(name, node_obj)
                    pid = getattr(node_obj, "pid", None)
                    pid_text = f" pid={pid}" if pid else ""

                    primary_ip = ""
                    try:
                        if hasattr(node_obj, "IP"):
                            primary_ip = _extract_ipv4(str(node_obj.IP() or ""))
                    except Exception:
                        primary_ip = ""

                    dpid_text = ""
                    try:
                        dpid = getattr(node_obj, "dpid", None)
                        if dpid:
                            dpid_text = f" dpid={dpid}"
                    except Exception:
                        pass

                    lines.append(f"{name} ({kind}){pid_text}{dpid_text}" + (f" ip={primary_ip}" if primary_ip else "") + "\r\n")

                    # Interface details
                    for iname, mac, ip in _iter_intf_rows(node_obj):
                        if not iname:
                            continue
                        parts = [f"  - {iname}"]
                        if mac:
                            parts.append(f"mac={mac}")
                        if ip:
                            parts.append(f"ip={ip}")
                        lines.append(" ".join(parts) + "\r\n")

                    # Switch controller details (OVS)
                    try:
                        is_switch = kind == "switches" or kind == "aps" or "switch" in str(kind).lower()
                        if is_switch:
                            ctrl_out = (await _exec_shell(f"ovs-vsctl get-controller {name} 2>/dev/null")).strip()
                            if ctrl_out:
                                lines.append(f"  - controller={ctrl_out}\r\n")
                    except Exception:
                        pass

                    lines.append("\r\n")
                return "".join(lines)

            if cmdline == "nodes":
                groups: list[str] = []
                for attr, group in _iter_node_groups():
                    node_names = []
                    for n in group:
                        try:
                            nm = str(getattr(n, "name", "") or "")
                            if nm:
                                node_names.append(nm)
                        except Exception:
                            pass
                    if node_names:
                        groups.append(f"{attr} ({len(node_names)}): " + " ".join(node_names))
                if not groups:
                    names = _all_node_names()
                    return "*** Nodes:\r\n" + (" ".join(names) if names else "—") + "\r\n"
                return "*** Nodes:\r\n" + "\r\n".join(groups) + "\r\n"

            # "nump" is a common typo in the UI; treat it as "dump".
            if cmdline in ("dump", "nump"):
                return await _dump_nodes_text()
            if cmdline in ("net", "links"):
                links = list(getattr(net, "links", []) or [])
                if not links:
                    return "*** No links\r\n"
                out_lines = []
                for lk in links:
                    try:
                        i1 = getattr(lk, "intf1", None)
                        i2 = getattr(lk, "intf2", None)
                        n1 = getattr(getattr(i1, "node", None), "name", "?")
                        n2 = getattr(getattr(i2, "node", None), "name", "?")
                        out_lines.append(f"{n1}-{getattr(i1, 'name', '?')} <-> {n2}-{getattr(i2, 'name', '?')}\r\n")
                    except Exception:
                        pass
                return "".join(out_lines)
            if cmdline == "controllers":
                return await _controllers_text()
            if cmdline == "pingall":
                return await _pingall_text()
            if cmdline.startswith("sh "):
                shell_cmd = cmdline[3:].strip()
                if not shell_cmd:
                    return ""
                out = await _exec_shell(shell_cmd)
                return out.replace("\n", "\r\n")

            parts = cmdline.split(None, 1)
            names = set(_all_node_names())
            if parts and parts[0] in names:
                node = net.get(parts[0])
                node_cmd = parts[1] if len(parts) > 1 else ""
                if not node_cmd:
                    return ""
                out = await _node_cmd(node, node_cmd)
                return out.replace("\n", "\r\n")

            return f"Unknown command: {cmdline}\r\n"

        # Banner + prompt
        yield emulation_pb2.CLIResponse(output="*** Starting CLI:\r\n\r\n" + prompt)

        try:
            async for request in request_iterator:
                if request.HasField("resize"):
                    continue
                if not request.HasField("input"):
                    continue

                data = request.input or ""
                out_chunks = []

                for ch in data:
                    # Ctrl+C
                    if ch == "\x03":
                        line_buf = ""
                        out_chunks.append("^C\r\n" + prompt)
                        continue

                    # Ignore ESC (arrows/etc) best-effort
                    if ch == "\x1b":
                        continue

                    # Backspace
                    if ch in ("\x7f", "\b"):
                        if line_buf:
                            line_buf = line_buf[:-1]
                            out_chunks.append("\b \b")
                        continue

                    # Enter
                    if ch in ("\r", "\n"):
                        out_chunks.append("\r\n")
                        cmdline = line_buf
                        line_buf = ""
                        try:
                            out_chunks.append(await _handle_line(cmdline))
                        except StopAsyncIteration:
                            return
                        out_chunks.append(prompt)
                        continue

                    # Printable chars
                    line_buf += ch
                    out_chunks.append(ch)

                for chunk in out_chunks:
                    if chunk:
                        yield emulation_pb2.CLIResponse(output=chunk)
        finally:
            return


async def serve():
    """Start the gRPC server"""
    server = grpc.aio.server(
        options=[
            ('grpc.max_send_message_length', 100 * 1024 * 1024),
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),
        ]
    )

    emulation_pb2_grpc.add_EmulationServiceServicer_to_server(
        EmulationServiceImpl(), server
    )

    bind_address = f"{GRPC_SERVER_HOST}:{GRPC_SERVER_PORT}"
    server.add_insecure_port(bind_address)

    logger.info("Starting gRPC server on %s...", bind_address)
    await server.start()
    logger.info("gRPC server started successfully")
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())
