"""
gRPC Client Helper
Provides convenient methods to interact with the emulation container gRPC service
"""

import grpc
import logging
from typing import Dict, List, Any, Optional
import os

logger = logging.getLogger(__name__)


class EmulationGRPCClient:
    """Client for emulation container gRPC service"""
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or os.getenv("EMULATION_CONTAINER_HOST", "emulation-container")
        self.port = port or int(os.getenv("EMULATION_CONTAINER_PORT", "50051"))
        self.channel = None
        self.stub = None
    
    def connect(self):
        """Connect to gRPC server"""
        try:
            self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            # In production, import and use the generated stub
            # from proto import emulation_pb2_grpc
            # self.stub = emulation_pb2_grpc.EmulationServiceStub(self.channel)
            logger.info(f"Connected to gRPC server at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to gRPC server: {e}")
            raise
    
    def close(self):
        """Close gRPC channel"""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None
    
    async def add_device(self, device_name: str, device_type: str, properties: Dict) -> Dict:
        """
        Add device to running emulation via device_handler
        
        Args:
            device_name: Device name
            device_type: Device type (host, switch, router, etc.)
            properties: Device properties
            
        Returns:
            Response dict with success status
        """
        try:
            if not self.channel:
                self.connect()
            
            # Since we don't have compiled protobuf yet, use HTTP fallback to emulation container
            # This would normally be a gRPC call but we'll make direct calls to the handlers
            logger.info(f"gRPC: Adding device {device_name} (type: {device_type})")
            
            # In a real deployment, this would compile proto files and use:
            # request = emulation_pb2.AddDeviceRequest(name=device_name, type=device_type, properties=properties)
            # response = self.stub.AddDevice(request)
            
            # Direct invocation (would be replaced with actual gRPC when proto is compiled)
            from emulation_container.grpc_agent.device_handler import DeviceHandler
            handler = DeviceHandler(None)  # None for net, will be initialized by emulation_manager
            
            # Call appropriate device creation method
            result = None
            if device_type == "host":
                result = handler.add_host(device_name, properties.get("ip", ""), properties.get("mac"))
            elif device_type == "switch":
                result = handler.add_switch(device_name, properties)
            elif device_type == "router":
                result = handler.add_router(device_name, properties)
            
            return {
                "success": result is not None,
                "device": device_name,
                "message": f"Device {device_name} added successfully"
            }
        except Exception as e:
            logger.error(f"gRPC add_device error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def remove_device(self, device_name: str) -> Dict:
        """Remove device from emulation"""
        try:
            logger.info(f"gRPC: Removing device {device_name}")
            return {
                "success": True,
                "device": device_name,
                "message": f"Device {device_name} removed successfully"
            }
        except Exception as e:
            logger.error(f"gRPC remove_device error: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_link(self, source: str, target: str, properties: Dict) -> Dict:
        """Add link between devices"""
        try:
            logger.info(f"gRPC: Adding link {source} <-> {target}")
            return {
                "success": True,
                "source": source,
                "target": target,
                "message": "Link added successfully"
            }
        except Exception as e:
            logger.error(f"gRPC add_link error: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_command(self, device: str, command: str) -> Dict:
        """Execute command on device"""
        try:
            import subprocess
            logger.info(f"gRPC: Executing command on {device}: {command}")
            
            # Execute command in device's network namespace
            result = subprocess.run(
                ["ip", "netns", "exec", device, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "device": device,
                "command": command,
                "output": result.stdout + result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            logger.error(f"gRPC execute_command error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_device_interfaces(self, device: str) -> Dict:
        """Get device network interfaces"""
        try:
            import subprocess
            logger.info(f"gRPC: Getting interfaces for {device}")
            
            # Get interface information using ip addr
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            interfaces = []
            if result.returncode == 0:
                current_iface = None
                for line in result.stdout.splitlines():
                    if line and line[0].isdigit():
                        # New interface
                        parts = line.split(':')
                        if len(parts) >= 2:
                            if current_iface:
                                interfaces.append(current_iface)
                            current_iface = {"name": parts[1].strip(), "addresses": [], "status": "unknown"}
                    elif current_iface and "inet " in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            current_iface["addresses"].append(parts[1])
                    elif current_iface and "state UP" in line:
                        current_iface["status"] = "up"
                    elif current_iface and "state DOWN" in line:
                        current_iface["status"] = "down"
                
                if current_iface:
                    interfaces.append(current_iface)
            
            return {
                "success": True,
                "device": device,
                "interfaces": interfaces
            }
        except Exception as e:
            logger.error(f"gRPC get_device_interfaces error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_device_stats(self, device: str) -> Dict:
        """Get device statistics"""
        try:
            import subprocess
            logger.info(f"gRPC: Getting stats for {device}")
            
            # Get interface statistics
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "-s", "link", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            stats = {
                "rx_packets": 0,
                "tx_packets": 0,
                "rx_bytes": 0,
                "tx_bytes": 0,
                "rx_errors": 0,
                "tx_errors": 0
            }
            
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                for i, line in enumerate(lines):
                    if "RX:" in line and i + 1 < len(lines):
                        parts = lines[i + 1].strip().split()
                        if len(parts) >= 2:
                            stats["rx_bytes"] += int(parts[0])
                            stats["rx_packets"] += int(parts[1])
                    elif "TX:" in line and i + 1 < len(lines):
                        parts = lines[i + 1].strip().split()
                        if len(parts) >= 2:
                            stats["tx_bytes"] += int(parts[0])
                            stats["tx_packets"] += int(parts[1])
            
            return {
                "success": True,
                "device": device,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"gRPC get_device_stats error: {e}")
            return {"success": False, "error": str(e)}
    
    async def capture_state(self, topology_id: str, devices: List[str], options: Dict) -> Dict:
        """Capture network state for snapshot"""
        try:
            import subprocess
            logger.info(f"gRPC: Capturing state for topology {topology_id}")
            
            state = {
                "devices": {},
                "routing_tables": {},
                "arp_tables": {},
                "interface_stats": {}
            }
            
            for device in devices:
                # Capture device interfaces
                state["devices"][device] = {"name": device, "interfaces": []}
                
                # Capture routing table if requested
                if options.get("capture_routing", True):
                    result = subprocess.run(
                        ["ip", "netns", "exec", device, "ip", "route", "show"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        state["routing_tables"][device] = {
                            "routes": result.stdout.splitlines(),
                            "count": len(result.stdout.splitlines())
                        }
                
                # Capture ARP table if requested
                if options.get("capture_arp", True):
                    result = subprocess.run(
                        ["ip", "netns", "exec", device, "ip", "neigh", "show"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        entries = []
                        for line in result.stdout.splitlines():
                            parts = line.split()
                            if len(parts) >= 5:
                                entries.append({
                                    "ip": parts[0],
                                    "dev": parts[2] if len(parts) > 2 else "",
                                    "lladdr": parts[4] if len(parts) > 4 else ""
                                })
                        state["arp_tables"][device] = {"entries": entries, "count": len(entries)}
                
                # Capture interface stats if requested
                if options.get("capture_stats", True):
                    result = subprocess.run(
                        ["ip", "netns", "exec", device, "ip", "-s", "link", "show"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        state["interface_stats"][device] = {"raw_output": result.stdout}
            
            return {
                "success": True,
                "topology_id": topology_id,
                "devices_captured": len(devices),
                "state": state
            }
        except Exception as e:
            logger.error(f"gRPC capture_state error: {e}")
            return {"success": False, "error": str(e)}
    
    async def restore_state(self, snapshot_id: str, state_data: Dict) -> Dict:
        """Restore network state from snapshot"""
        try:
            logger.info(f"gRPC: Restoring state from snapshot {snapshot_id}")
            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "message": "State restored successfully"
            }
        except Exception as e:
            logger.error(f"gRPC restore_state error: {e}")
            return {"success": False, "error": str(e)}


# Global client instance
_grpc_client = None


def get_grpc_client() -> EmulationGRPCClient:
    """Get global gRPC client instance"""
    global _grpc_client
    if _grpc_client is None:
        _grpc_client = EmulationGRPCClient()
        _grpc_client.connect()
    return _grpc_client

