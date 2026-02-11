"""
Pydantic schemas for network configuration import/export/apply.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class NetworkRoute(BaseModel):
    dst: str = Field(..., description="Route destination, e.g. '10.0.0.0/24' or 'default'")
    via: Optional[str] = Field(None, description="Next hop IP")
    dev: Optional[str] = Field(None, description="Interface name (optional; resolved if omitted)")
    metric: Optional[int] = None


class InterfaceAddressing(BaseModel):
    name: Optional[str] = Field(None, description="Interface name, e.g. 'host-1-eth0'. If omitted, auto-selects the first non-loopback interface.")
    mac: Optional[str] = Field(None, description="MAC address (optional)")
    mtu: Optional[int] = Field(None, description="MTU (optional)")
    up: Optional[bool] = Field(True, description="Bring interface up")
    reset_addresses: Optional[bool] = Field(True, description="Flush existing addresses on the interface before applying addresses")
    addresses: List[str] = Field(default_factory=list, description="List of CIDR addresses (v4/v6), e.g. ['10.0.0.1/24']")


class DeviceNetworkConfig(BaseModel):
    name: str = Field(..., description="Topology node name (preferred) or runtime device name")
    kind: Optional[str] = Field(None, description="Device kind hint (host/router/switch/etc.)")

    interfaces: List[InterfaceAddressing] = Field(default_factory=list)
    default_gateway: Optional[str] = Field(None, description="IPv4 default gateway")
    default_gateway6: Optional[str] = Field(None, description="IPv6 default gateway")

    routes: List[NetworkRoute] = Field(default_factory=list)
    dns_servers: List[str] = Field(default_factory=list)
    sysctls: Dict[str, str] = Field(default_factory=dict)
    commands: List[str] = Field(default_factory=list, description="Additional commands to run inside the device namespace")


class NetworkConfigDefaults(BaseModel):
    flush_routes: bool = Field(False, description="If true, flush routes before applying routes (advanced)")
    dns_servers: List[str] = Field(default_factory=list, description="Default DNS servers applied to devices without dns_servers")
    sysctls: Dict[str, str] = Field(default_factory=dict, description="Default sysctls applied to all devices (device sysctls override)")
    commands: List[str] = Field(default_factory=list, description="Default commands run on all devices (prepended before device commands)")


class NetworkConfigurationDocument(BaseModel):
    """
    Canonical network configuration format.
    Stored in DB and can be applied to a running emulation.
    """

    schema: Literal["caduceus.network-config.v1"] = "caduceus.network-config.v1"
    topology_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    defaults: NetworkConfigDefaults = Field(default_factory=NetworkConfigDefaults)
    devices: List[DeviceNetworkConfig] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NetworkConfigCreateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: NetworkConfigurationDocument


class NetworkConfigResponse(BaseModel):
    id: str
    topology_id: str
    name: str
    description: Optional[str] = None
    version: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NetworkConfigListItem(BaseModel):
    id: str
    topology_id: str
    name: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NetworkConfigApplyRequest(BaseModel):
    topology_id: str
    config: NetworkConfigurationDocument
    dry_run: bool = False


class NetworkConfigApplyResult(BaseModel):
    success: bool
    message: str
    topology_id: str
    dry_run: bool = False
    results: List[Dict[str, Any]] = Field(default_factory=list)
