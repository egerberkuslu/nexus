"""
WSN (Wireless Sensor Network) module for Caduceus Flux algo_sdk.

Provides base classes and protocol implementations for simulating
WSN routing protocols like LEACH, LEACH-C, PEGASIS, SEP, and TEEN.

Integrates with Mininet-WiFi's native energy consumption model.
"""

from .energy_model import (
    EnergyModel,
    MininetWiFiEnergyAdapter,
    IDLE_FACTOR,
    TX_FACTOR,
    RX_FACTOR,
    SLEEP_FACTOR,
)
from .wsn_node_base import (
    WSNNode,
    WSNNodeType,
    WSNRole,
)
from .metrics_collector import WSNMetricsCollector

__all__ = [
    # Energy Model
    "EnergyModel",
    "MininetWiFiEnergyAdapter",
    "IDLE_FACTOR",
    "TX_FACTOR",
    "RX_FACTOR",
    "SLEEP_FACTOR",
    # Node Base
    "WSNNode",
    "WSNNodeType",
    "WSNRole",
    # Metrics
    "WSNMetricsCollector",
]
