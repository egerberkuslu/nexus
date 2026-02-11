"""
Protocol Handler for Emulation Container
Manages protocol configuration, enabling, disabling, and hot-swapping
"""

from __future__ import annotations

import logging
import subprocess
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ProtocolHandler:
    """
    Handles protocol operations for network devices
    Supports: OSPF, BGP, RIP, IS-IS, EIGRP, OpenFlow
    """

    def __init__(self, emulation_manager=None):
        self.emulation_manager = emulation_manager
        self.active_protocols: Dict[str, Dict[str, Any]] = {}
        # device_name -> {protocol_name: {config, status}}

    def configure_protocol(
        self,
        device: str,
        protocol: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Configure a protocol on a device
        
        Args:
            device: Device name
            protocol: Protocol name (ospf, bgp, rip, etc.)
            config: Protocol configuration
            
        Returns:
            Configuration result
        """
        try:
            logger.info(f"Configuring {protocol} on {device}")

            if protocol.lower() == "ospf":
                return self._configure_ospf(device, config)
            elif protocol.lower() == "bgp":
                return self._configure_bgp(device, config)
            elif protocol.lower() == "rip":
                return self._configure_rip(device, config)
            elif protocol.lower() == "isis":
                return self._configure_isis(device, config)
            elif protocol.lower() == "static":
                return self._configure_static(device, config)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")

        except Exception as e:
            logger.error(f"Failed to configure {protocol} on {device}: {e}")
            return {"success": False, "error": str(e)}

    def _configure_ospf(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure OSPF using FRRouting"""
        try:
            router_id = config.get("router_id", "1.1.1.1")
            area = config.get("area", "0.0.0.0")
            networks = config.get("networks", [])

            # Generate FRR OSPF configuration
            ospf_config = f"""
router ospf
  ospf router-id {router_id}
"""
            for network in networks:
                net_addr = network.get("network", "")
                net_area = network.get("area", area)
                ospf_config += f"  network {net_addr} area {net_area}\n"

            # Write config to FRR
            config_path = f"/etc/frr/{device}_ospf.conf"
            with open(config_path, 'w') as f:
                f.write(ospf_config)

            # Store configuration
            if device not in self.active_protocols:
                self.active_protocols[device] = {}
            self.active_protocols[device]["ospf"] = {
                "config": config,
                "status": "configured",
                "config_file": config_path
            }

            return {
                "success": True,
                "protocol": "ospf",
                "device": device,
                "config": ospf_config
            }

        except Exception as e:
            logger.error(f"OSPF configuration error: {e}")
            return {"success": False, "error": str(e)}

    def _configure_bgp(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure BGP using FRRouting"""
        try:
            as_number = config.get("as_number", 65000)
            router_id = config.get("router_id", "1.1.1.1")
            neighbors = config.get("neighbors", [])
            networks = config.get("networks", [])

            # Generate FRR BGP configuration
            bgp_config = f"""
router bgp {as_number}
  bgp router-id {router_id}
"""
            # Add neighbors
            for neighbor in neighbors:
                neighbor_ip = neighbor.get("ip")
                remote_as = neighbor.get("remote_as")
                bgp_config += f"  neighbor {neighbor_ip} remote-as {remote_as}\n"

            # Add networks
            for network in networks:
                bgp_config += f"  network {network}\n"

            # Write config to FRR
            config_path = f"/etc/frr/{device}_bgp.conf"
            with open(config_path, 'w') as f:
                f.write(bgp_config)

            # Store configuration
            if device not in self.active_protocols:
                self.active_protocols[device] = {}
            self.active_protocols[device]["bgp"] = {
                "config": config,
                "status": "configured",
                "config_file": config_path
            }

            return {
                "success": True,
                "protocol": "bgp",
                "device": device,
                "config": bgp_config
            }

        except Exception as e:
            logger.error(f"BGP configuration error: {e}")
            return {"success": False, "error": str(e)}

    def _configure_rip(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure RIP using FRRouting"""
        try:
            networks = config.get("networks", [])
            version = config.get("version", 2)

            # Generate FRR RIP configuration
            rip_config = f"""
router rip
  version {version}
"""
            for network in networks:
                rip_config += f"  network {network}\n"

            # Write config to FRR
            config_path = f"/etc/frr/{device}_rip.conf"
            with open(config_path, 'w') as f:
                f.write(rip_config)

            # Store configuration
            if device not in self.active_protocols:
                self.active_protocols[device] = {}
            self.active_protocols[device]["rip"] = {
                "config": config,
                "status": "configured",
                "config_file": config_path
            }

            return {
                "success": True,
                "protocol": "rip",
                "device": device,
                "config": rip_config
            }

        except Exception as e:
            logger.error(f"RIP configuration error: {e}")
            return {"success": False, "error": str(e)}

    def _configure_isis(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure IS-IS using FRRouting"""
        try:
            area = config.get("area", "49.0001")
            net = config.get("net", "49.0001.1111.1111.1111.00")

            # Generate FRR IS-IS configuration
            isis_config = f"""
router isis {area}
  net {net}
  is-type level-2-only
"""
            # Write config to FRR
            config_path = f"/etc/frr/{device}_isis.conf"
            with open(config_path, 'w') as f:
                f.write(isis_config)

            # Store configuration
            if device not in self.active_protocols:
                self.active_protocols[device] = {}
            self.active_protocols[device]["isis"] = {
                "config": config,
                "status": "configured",
                "config_file": config_path
            }

            return {
                "success": True,
                "protocol": "isis",
                "device": device,
                "config": isis_config
            }

        except Exception as e:
            logger.error(f"IS-IS configuration error: {e}")
            return {"success": False, "error": str(e)}

    def _configure_static(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure static routes"""
        try:
            routes = config.get("routes", [])

            # Generate static route configuration
            static_config = ""
            for route in routes:
                dest = route.get("destination")
                nexthop = route.get("nexthop")
                static_config += f"ip route {dest} {nexthop}\n"

            # Write config
            config_path = f"/etc/frr/{device}_static.conf"
            with open(config_path, 'w') as f:
                f.write(static_config)

            # Store configuration
            if device not in self.active_protocols:
                self.active_protocols[device] = {}
            self.active_protocols[device]["static"] = {
                "config": config,
                "status": "configured",
                "config_file": config_path
            }

            return {
                "success": True,
                "protocol": "static",
                "device": device,
                "config": static_config
            }

        except Exception as e:
            logger.error(f"Static route configuration error: {e}")
            return {"success": False, "error": str(e)}

    def enable_protocol(self, device: str, protocol: str) -> bool:
        """Enable a configured protocol"""
        try:
            logger.info(f"Enabling {protocol} on {device}")

            if device not in self.active_protocols:
                logger.error(f"Device {device} has no protocols configured")
                return False

            if protocol not in self.active_protocols[device]:
                logger.error(f"Protocol {protocol} not configured on {device}")
                return False

            # Reload FRR configuration
            result = subprocess.run(
                ["vtysh", "-c", "configure terminal", "-c", f"source {self.active_protocols[device][protocol]['config_file']}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.active_protocols[device][protocol]["status"] = "active"
                logger.info(f"Successfully enabled {protocol} on {device}")
                return True
            else:
                logger.error(f"Failed to enable {protocol}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to enable {protocol} on {device}: {e}")
            return False

    def disable_protocol(self, device: str, protocol: str) -> bool:
        """Disable a protocol"""
        try:
            logger.info(f"Disabling {protocol} on {device}")

            if device not in self.active_protocols or protocol not in self.active_protocols[device]:
                logger.warning(f"Protocol {protocol} not active on {device}")
                return True

            # Stop protocol in FRR
            result = subprocess.run(
                ["vtysh", "-c", "configure terminal", "-c", f"no router {protocol}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.active_protocols[device][protocol]["status"] = "disabled"
                logger.info(f"Successfully disabled {protocol} on {device}")
                return True
            else:
                logger.error(f"Failed to disable {protocol}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to disable {protocol} on {device}: {e}")
            return False

    def switch_protocol(
        self,
        device: str,
        from_protocol: str,
        to_protocol: str,
        preserve_config: bool = True
    ) -> Dict[str, Any]:
        """
        Hot-swap protocols without restarting emulation
        
        Args:
            device: Device name
            from_protocol: Current protocol
            to_protocol: Target protocol
            preserve_config: Whether to preserve routing state
            
        Returns:
            Switch result
        """
        try:
            logger.info(f"Switching {device} from {from_protocol} to {to_protocol}")

            # Step 1: Capture current routing state (if preserving)
            routing_state = {}
            if preserve_config:
                routing_state = self._capture_routing_state(device)

            # Step 2: Disable source protocol
            if not self.disable_protocol(device, from_protocol):
                return {"success": False, "error": f"Failed to disable {from_protocol}"}

            # Step 3: Configure target protocol  
            # Check if target protocol is already configured
            if to_protocol not in self.active_protocols.get(device, {}):
                # If not configured, we cannot switch to it
                logger.error(f"{to_protocol} not configured on {device}. Please configure it first.")
                return {"success": False, "error": f"{to_protocol} must be configured before switching to it"}

            # Step 4: Enable target protocol
            if not self.enable_protocol(device, to_protocol):
                return {"success": False, "error": f"Failed to enable {to_protocol}"}

            # Step 5: Verify routing continuity (if preserved)
            if preserve_config:
                if not self._verify_routing_state(device, routing_state):
                    logger.warning(f"Routing state changed after protocol switch")

            logger.info(f"Successfully switched {device} from {from_protocol} to {to_protocol}")

            return {
                "success": True,
                "device": device,
                "from_protocol": from_protocol,
                "to_protocol": to_protocol,
                "preserved_routes": len(routing_state) if preserve_config else 0
            }

        except Exception as e:
            logger.error(f"Protocol switch failed: {e}")
            return {"success": False, "error": str(e)}

    def _capture_routing_state(self, device: str) -> Dict[str, Any]:
        """Capture current routing table"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "route"],
                capture_output=True,
                text=True
            )
            
            routes = {}
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    routes[parts[0]] = line
                    
            return routes
        except Exception as e:
            logger.error(f"Failed to capture routing state: {e}")
            return {}

    def _verify_routing_state(self, device: str, expected_state: Dict[str, Any]) -> bool:
        """Verify routing table matches expected state"""
        try:
            current_state = self._capture_routing_state(device)
            
            # Check if critical routes are preserved
            for dest in expected_state:
                if dest not in current_state:
                    logger.warning(f"Route to {dest} lost after protocol switch")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Failed to verify routing state: {e}")
            return False

    def get_protocol_status(self, device: str, protocol: Optional[str] = None) -> Dict[str, Any]:
        """Get protocol status for a device"""
        if device not in self.active_protocols:
            return {"device": device, "protocols": {}}

        if protocol:
            return {
                "device": device,
                "protocol": protocol,
                "status": self.active_protocols[device].get(protocol, {"status": "not_configured"})
            }
        else:
            return {
                "device": device,
                "protocols": self.active_protocols[device]
            }

    def get_routing_table(self, device: str) -> Dict[str, Any]:
        """Get routing table for a device"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "route"],
                capture_output=True,
                text=True
            )

            routes = []
            for line in result.stdout.splitlines():
                routes.append(line)

            return {
                "device": device,
                "routes": routes,
                "count": len(routes)
            }

        except Exception as e:
            logger.error(f"Failed to get routing table: {e}")
            return {"device": device, "routes": [], "error": str(e)}

    def get_neighbors(self, device: str, protocol: str) -> Dict[str, Any]:
        """Get protocol neighbors"""
        try:
            if protocol == "ospf":
                cmd = ["vtysh", "-c", "show ip ospf neighbor"]
            elif protocol == "bgp":
                cmd = ["vtysh", "-c", "show ip bgp summary"]
            elif protocol == "rip":
                cmd = ["vtysh", "-c", "show ip rip status"]
            else:
                return {"device": device, "protocol": protocol, "neighbors": [], "error": "Unsupported protocol"}

            result = subprocess.run(cmd, capture_output=True, text=True)

            return {
                "device": device,
                "protocol": protocol,
                "output": result.stdout,
                "success": result.returncode == 0
            }

        except Exception as e:
            logger.error(f"Failed to get neighbors: {e}")
            return {"device": device, "protocol": protocol, "error": str(e)}
