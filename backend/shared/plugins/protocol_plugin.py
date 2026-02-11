"""
Base Protocol Plugin System
Provides abstract interface for all protocol implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum


class ProtocolType(str, Enum):
    """Protocol types"""
    ROUTING = "routing"
    OPENFLOW = "openflow"
    WIRELESS = "wireless"
    SECURITY = "security"
    MANAGEMENT = "management"


class ProtocolStatus(str, Enum):
    """Protocol status"""
    DISABLED = "disabled"
    CONFIGURING = "configuring"
    ENABLED = "enabled"
    ERROR = "error"
    SWITCHING = "switching"


class ProtocolPlugin(ABC):
    """
    Base class for all protocol plugins

    All protocol implementations must inherit from this class
    and implement the required methods.
    """

    # Plugin metadata
    name: str = ""
    version: str = "1.0"
    protocol_type: ProtocolType = ProtocolType.ROUTING
    description: str = ""
    supported_devices: List[str] = []  # host, switch, router, ap, sta

    @abstractmethod
    def configure(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure protocol on a device

        Args:
            device: Device name
            config: Protocol configuration parameters

        Returns:
            Dict with keys:
                - success: bool
                - message: str
                - config: generated configuration
        """
        pass

    @abstractmethod
    def enable(self, device: str) -> Dict[str, Any]:
        """
        Enable protocol on a device

        Args:
            device: Device name

        Returns:
            Dict with keys:
                - success: bool
                - message: str
                - status: ProtocolStatus
        """
        pass

    @abstractmethod
    def disable(self, device: str) -> Dict[str, Any]:
        """
        Disable protocol on a device

        Args:
            device: Device name

        Returns:
            Dict with keys:
                - success: bool
                - message: str
        """
        pass

    @abstractmethod
    def get_status(self, device: str) -> Dict[str, Any]:
        """
        Get protocol status on a device

        Args:
            device: Device name

        Returns:
            Dict with keys:
                - status: ProtocolStatus
                - details: Dict (neighbors, routes, etc.)
                - version: str
                - config: Dict
        """
        pass

    @abstractmethod
    def switch_from(self, device: str, to_protocol: str, preserve_config: bool = True) -> Dict[str, Any]:
        """
        Switch from this protocol to another protocol

        Args:
            device: Device name
            to_protocol: Target protocol name
            preserve_config: Whether to preserve configuration

        Returns:
            Dict with keys:
                - success: bool
                - message: str
                - preserved_state: Dict (routing table, etc.)
        """
        pass

    @abstractmethod
    def switch_to(self, device: str, from_protocol: str, preserved_state: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Switch to this protocol from another protocol

        Args:
            device: Device name
            from_protocol: Source protocol name
            preserved_state: State from previous protocol

        Returns:
            Dict with keys:
                - success: bool
                - message: str
                - status: ProtocolStatus
        """
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate protocol configuration

        Args:
            config: Configuration to validate

        Returns:
            Dict with keys:
                - valid: bool
                - errors: List[str]
                - warnings: List[str]
        """
        pass

    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration for this protocol

        Returns:
            Default configuration dict
        """
        return {}

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for configuration validation

        Returns:
            JSON schema dict
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    def supports_device_type(self, device_type: str) -> bool:
        """
        Check if protocol supports a device type

        Args:
            device_type: Device type (host, switch, router, etc.)

        Returns:
            True if supported
        """
        return device_type in self.supported_devices


class RoutingProtocolPlugin(ProtocolPlugin):
    """Base class for routing protocols"""

    protocol_type = ProtocolType.ROUTING
    supported_devices = ["router"]

    @abstractmethod
    def get_routing_table(self, device: str) -> List[Dict[str, Any]]:
        """Get routing table from device"""
        pass

    @abstractmethod
    def get_neighbors(self, device: str) -> List[Dict[str, Any]]:
        """Get protocol neighbors"""
        pass

    @abstractmethod
    def get_metrics(self, device: str) -> Dict[str, Any]:
        """Get protocol metrics"""
        pass


class OpenFlowProtocolPlugin(ProtocolPlugin):
    """Base class for OpenFlow versions"""

    protocol_type = ProtocolType.OPENFLOW
    supported_devices = ["switch"]

    @abstractmethod
    def get_flow_table(self, device: str) -> List[Dict[str, Any]]:
        """Get flow table from switch"""
        pass

    @abstractmethod
    def add_flow(self, device: str, flow: Dict[str, Any]) -> Dict[str, Any]:
        """Add flow entry"""
        pass

    @abstractmethod
    def delete_flow(self, device: str, flow_id: str) -> Dict[str, Any]:
        """Delete flow entry"""
        pass


class WirelessProtocolPlugin(ProtocolPlugin):
    """Base class for wireless protocols"""

    protocol_type = ProtocolType.WIRELESS
    supported_devices = ["ap", "sta"]

    @abstractmethod
    def get_associations(self, device: str) -> List[Dict[str, Any]]:
        """Get wireless associations"""
        pass

    @abstractmethod
    def get_signal_strength(self, device: str) -> Dict[str, Any]:
        """Get signal strength metrics"""
        pass


class PluginRegistry:
    """Registry for managing protocol plugins"""

    def __init__(self):
        self._plugins: Dict[str, ProtocolPlugin] = {}

    def register(self, plugin: ProtocolPlugin):
        """Register a protocol plugin"""
        self._plugins[plugin.name] = plugin

    def unregister(self, plugin_name: str):
        """Unregister a protocol plugin"""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]

    def get(self, plugin_name: str) -> Optional[ProtocolPlugin]:
        """Get a protocol plugin by name"""
        return self._plugins.get(plugin_name)

    def list_plugins(self, protocol_type: Optional[ProtocolType] = None) -> List[str]:
        """List all registered plugins, optionally filtered by type"""
        if protocol_type:
            return [
                name for name, plugin in self._plugins.items()
                if plugin.protocol_type == protocol_type
            ]
        return list(self._plugins.keys())

    def get_plugins_for_device(self, device_type: str) -> List[str]:
        """Get plugins that support a device type"""
        return [
            name for name, plugin in self._plugins.items()
            if plugin.supports_device_type(device_type)
        ]


# Global plugin registry
plugin_registry = PluginRegistry()
