"""
WSN Node Base Class for Distributed Sensor Network Algorithms.

Extends the base Node class with:
- Energy management (integrated with Mininet-WiFi)
- Position tracking for distance calculations
- Role management (sensor, cluster head, base station)
- Cluster membership tracking
- WSN-specific event emission

Compatible with Mininet-WiFi's energy model and propagation models.
"""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..node_base import Node
from .energy_model import (
    EnergyModel,
    MininetWiFiEnergyAdapter,
    EnergyState,
    create_energy_model,
    DEFAULT_E_ELEC,
    DEFAULT_E_AMP_FS,
    DEFAULT_D0,
)


class WSNNodeType(str, Enum):
    """Node type classification for heterogeneous networks (SEP protocol)."""
    NORMAL = "normal"
    ADVANCED = "advanced"
    BASE_STATION = "base_station"


class WSNRole(str, Enum):
    """Role of the node in the current round."""
    SENSOR = "sensor"
    CLUSTER_HEAD = "cluster_head"
    CHAIN_LEADER = "chain_leader"  # For PEGASIS
    BASE_STATION = "base_station"


# Visual overlay colors for different roles/states
ROLE_OVERLAYS = {
    WSNRole.BASE_STATION: {
        "fill": "#dc2626", "text": "#ffffff", "border": "#7f1d1d", "badge": "BS"
    },
    WSNRole.CLUSTER_HEAD: {
        "fill": "#2563eb", "text": "#ffffff", "border": "#1e40af", "badge": "CH"
    },
    WSNRole.CHAIN_LEADER: {
        "fill": "#7c3aed", "text": "#ffffff", "border": "#5b21b6", "badge": "LEADER"
    },
    WSNRole.SENSOR: {
        "fill": "#22c55e", "text": "#ffffff", "border": "#166534", "badge": "SENSOR"
    },
}

# Energy-level based overlays for sensors
ENERGY_OVERLAYS = {
    "high": {"fill": "#22c55e", "text": "#ffffff", "border": "#166534", "badge": "SENSOR"},
    "medium": {"fill": "#eab308", "text": "#000000", "border": "#854d0e", "badge": "LOW"},
    "low": {"fill": "#f97316", "text": "#ffffff", "border": "#9a3412", "badge": "CRITICAL"},
    "dead": {"fill": "#6b7280", "text": "#ffffff", "border": "#374151", "badge": "DEAD"},
}


class WSNNode(Node):
    """
    Extended Node base class for WSN protocols with energy management.

    Integrates with Mininet-WiFi's energy model (mn_wifi/energy.py) for
    realistic energy consumption tracking, or falls back to first-order
    radio model for simulation-only mode.

    Attributes:
        position: (x, y) coordinates for distance calculations
        initial_energy: Starting energy in Joules
        current_energy: Remaining energy in Joules
        is_alive: Whether node has energy remaining
        node_type: NORMAL, ADVANCED (SEP), or BASE_STATION
        role: Current role (SENSOR, CLUSTER_HEAD, etc.)
        cluster_id: ID of the cluster this node belongs to
        cluster_head_id: ID of the cluster head for this node
        cluster_members: List of member IDs (if this node is CH)
        bs_position: Position of the base station
        round_number: Current simulation round
    """

    def __init__(self, ctx: Any) -> None:
        """
        Initialize WSN node with energy and position.

        Args:
            ctx: AgentContext from algo_sdk
        """
        super().__init__(ctx)

        # Position from node properties or graph
        self.position: Tuple[float, float] = self._init_position()

        # Energy configuration
        self.initial_energy: float = float(
            self.params.get("initial_energy", 0.5)
        )

        # Node classification (for SEP protocol heterogeneity)
        self.node_type: WSNNodeType = self._init_node_type()

        # Adjust energy for advanced nodes (SEP)
        if self.node_type == WSNNodeType.ADVANCED:
            alpha = float(self.params.get("alpha", 1.0))
            self.initial_energy *= (1 + alpha)

        self.current_energy: float = self.initial_energy
        self.is_alive: bool = True

        # Role management
        self.role: WSNRole = self._init_role()

        # Cluster information
        self.cluster_id: Optional[int] = None
        self.cluster_head_id: Optional[int] = None
        self.cluster_members: List[int] = []

        # Base station location
        self.bs_position: Tuple[float, float] = self._init_bs_position()
        self.bs_id: Optional[int] = self._find_bs_id()

        # Energy model (supports both Mininet-WiFi and first-order radio)
        self._energy_adapter = self._init_energy_model()

        # Round tracking
        self.round_number: int = 0

        # Statistics
        self._packets_sent: int = 0
        self._packets_received: int = 0
        self._packets_to_bs: int = 0
        self._times_as_ch: int = 0
        self._energy_consumed: float = 0.0

    def _init_position(self) -> Tuple[float, float]:
        """Initialize position from node properties or graph."""
        # Try params first
        pos = self.params.get("position")
        if pos:
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return (float(pos[0]), float(pos[1]))
            elif isinstance(pos, str):
                parts = pos.replace(",", " ").split()
                if len(parts) >= 2:
                    return (float(parts[0]), float(parts[1]))

        # Try graph node attributes
        node_attrs = self.G.nodes[self.id]
        if node_attrs:
            x = node_attrs.get("x", node_attrs.get("pos_x", 0))
            y = node_attrs.get("y", node_attrs.get("pos_y", 0))
            return (float(x), float(y))

        # Random position within field
        import random
        field_size = self.params.get("field_size", (100, 100))
        if isinstance(field_size, (list, tuple)) and len(field_size) >= 2:
            return (
                random.uniform(0, float(field_size[0])),
                random.uniform(0, float(field_size[1]))
            )
        return (random.uniform(0, 100), random.uniform(0, 100))

    def _init_node_type(self) -> WSNNodeType:
        """Initialize node type from properties."""
        node_attrs = self.G.nodes[self.id] or {}

        def _norm(v: Any) -> str:
            return str(v or "").strip().lower().replace("-", "_")

        # Prefer per-node attributes from topology properties.
        node_type_str = _norm(node_attrs.get("node_type") or node_attrs.get("wsn_node_type") or "")
        role_str = _norm(node_attrs.get("role") or "")

        # Base station can be expressed as either role or node_type.
        if role_str in ("base_station", "bs") or node_type_str in ("base_station", "bs"):
            return WSNNodeType.BASE_STATION

        # Heterogeneous node types (SEP).
        if node_type_str in ("advanced", "adv"):
            return WSNNodeType.ADVANCED

        # Fall back to run-wide params.
        node_type_str = _norm(self.params.get("node_type", "normal"))

        if node_type_str == "advanced":
            return WSNNodeType.ADVANCED
        elif node_type_str == "base_station" or node_type_str == "bs":
            return WSNNodeType.BASE_STATION
        return WSNNodeType.NORMAL

    def _init_role(self) -> WSNRole:
        """Initialize role from properties."""
        if self.node_type == WSNNodeType.BASE_STATION:
            return WSNRole.BASE_STATION

        node_attrs = self.G.nodes[self.id] or {}
        role_str = str(node_attrs.get("role") or "").lower().strip().replace("-", "_")
        if role_str == "cluster_head" or role_str == "ch":
            return WSNRole.CLUSTER_HEAD
        elif role_str == "chain_leader" or role_str == "leader":
            return WSNRole.CHAIN_LEADER
        elif role_str == "base_station" or role_str == "bs":
            return WSNRole.BASE_STATION

        role_str = str(self.params.get("role", "sensor")).lower().strip()
        if role_str == "cluster_head" or role_str == "ch":
            return WSNRole.CLUSTER_HEAD
        elif role_str == "chain_leader" or role_str == "leader":
            return WSNRole.CHAIN_LEADER
        elif role_str == "base_station" or role_str == "bs":
            return WSNRole.BASE_STATION
        return WSNRole.SENSOR

    def _init_bs_position(self) -> Tuple[float, float]:
        """Initialize base station position."""
        bs_pos = self.params.get("bs_position")
        if bs_pos:
            if isinstance(bs_pos, (list, tuple)) and len(bs_pos) >= 2:
                return (float(bs_pos[0]), float(bs_pos[1]))

        # Default: outside field at (50, 175) for 100x100 field
        field_size = self.params.get("field_size", (100, 100))
        if isinstance(field_size, (list, tuple)) and len(field_size) >= 2:
            return (float(field_size[0]) / 2, float(field_size[1]) * 1.75)
        return (50.0, 175.0)

    def _find_bs_id(self) -> Optional[int]:
        """Find base station ID from graph."""
        bs_id = self.params.get("bs_id")
        if bs_id is not None:
            return int(bs_id)

        # Search in graph nodes
        for nid, attrs in (self.ctx.graph_nodes or {}).items():
            role = str(attrs.get("role") or "").lower().strip().replace("-", "_")
            node_type = str(attrs.get("node_type") or "").lower().strip().replace("-", "_")
            if role in ("base_station", "bs") or node_type in ("base_station", "bs"):
                return int(nid)
        return None

    def _init_energy_model(self) -> MininetWiFiEnergyAdapter:
        """Initialize energy model adapter."""
        mode = str(self.params.get("energy_mode", "auto")).lower()
        voltage = float(self.params.get("voltage", 3.7))
        use_bitzigbee = bool(self.params.get("use_bitzigbee", False))

        return MininetWiFiEnergyAdapter(
            voltage=voltage,
            battery_capacity=self.initial_energy,
            use_bitzigbee=use_bitzigbee,
        )

    # --- Distance Calculations ---

    def distance_to(self, other_id: int) -> float:
        """
        Calculate Euclidean distance to another node.

        Args:
            other_id: ID of the other node

        Returns:
            Distance in meters
        """
        other_pos = self._get_node_position(other_id)
        return math.sqrt(
            (self.position[0] - other_pos[0]) ** 2 +
            (self.position[1] - other_pos[1]) ** 2
        )

    def distance_to_bs(self) -> float:
        """
        Calculate distance to base station.

        Returns:
            Distance in meters
        """
        return math.sqrt(
            (self.position[0] - self.bs_position[0]) ** 2 +
            (self.position[1] - self.bs_position[1]) ** 2
        )

    def _get_node_position(self, node_id: int) -> Tuple[float, float]:
        """Get position of another node from graph."""
        node_attrs = self.G.nodes[node_id]
        if node_attrs:
            # Try various position formats
            pos = node_attrs.get("position")
            if pos:
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return (float(pos[0]), float(pos[1]))
                elif isinstance(pos, str):
                    parts = pos.replace(",", " ").split()
                    if len(parts) >= 2:
                        return (float(parts[0]), float(parts[1]))

            x = node_attrs.get("x", node_attrs.get("pos_x", 0))
            y = node_attrs.get("y", node_attrs.get("pos_y", 0))
            return (float(x), float(y))

        # If node is a neighbor, estimate from neighbor info
        neighbor_info = self.neighbors.get(int(node_id), {})
        if isinstance(neighbor_info, dict):
            pos = neighbor_info.get("position")
            if pos and isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return (float(pos[0]), float(pos[1]))

        return (0.0, 0.0)

    # --- Energy Management ---

    def consume_tx_energy(self, bits: int, distance: float) -> bool:
        """
        Consume transmission energy.

        Args:
            bits: Number of bits to transmit
            distance: Distance to receiver in meters

        Returns:
            True if node still alive, False if node died
        """
        if not self.is_alive:
            return False

        energy = self._energy_adapter.tx_energy(bits, distance)
        return self._consume_energy(energy, EnergyState.TX)

    def consume_rx_energy(self, bits: int) -> bool:
        """
        Consume reception energy.

        Args:
            bits: Number of bits received

        Returns:
            True if node still alive, False if node died
        """
        if not self.is_alive:
            return False

        energy = self._energy_adapter.rx_energy(bits)
        return self._consume_energy(energy, EnergyState.RX)

    def consume_aggregation_energy(self, bits: int) -> bool:
        """
        Consume data aggregation energy.

        Args:
            bits: Number of bits aggregated

        Returns:
            True if node still alive, False if node died
        """
        if not self.is_alive:
            return False

        # Use first-order radio model for aggregation
        e_da = float(self.params.get("e_da", 5e-9))
        energy = e_da * bits
        return self._consume_energy(energy, EnergyState.IDLE)

    def consume_idle_energy(self, duration_seconds: float) -> bool:
        """
        Consume idle energy for a duration.

        Args:
            duration_seconds: Time spent in idle state

        Returns:
            True if node still alive, False if node died
        """
        if not self.is_alive:
            return False

        energy = self._energy_adapter.idle_energy(duration_seconds)
        return self._consume_energy(energy, EnergyState.IDLE)

    def _consume_energy(self, energy: float, state: EnergyState) -> bool:
        """
        Deduct energy and check if node dies.

        Args:
            energy: Energy to consume in Joules
            state: Current energy state

        Returns:
            True if node still alive, False if node died
        """
        if not self.is_alive:
            return False

        self.current_energy -= energy
        self._energy_consumed += energy
        self._energy_adapter.consume(energy, state)

        if self.current_energy <= 0:
            self.current_energy = 0
            self.is_alive = False
            self._emit_death_event()
            return False

        return True

    def _emit_death_event(self) -> None:
        """Emit node death event."""
        overlay = ENERGY_OVERLAYS["dead"]
        self.write_state({
            "ts": time.time(),
            "node": {
                "algo_id": self.id,
                "uuid": self.uuid,
                "name": self.name,
                "type": self.type
            },
            "is_alive": False,
            "final_energy": 0,
            "overlay": overlay,
        })
        self.emit({
            "type": "node_death",
            "round": self.round_number,
            "node_id": self.id,
            "total_packets_sent": self._packets_sent,
            "total_energy_consumed": self._energy_consumed,
            "times_as_ch": self._times_as_ch,
        })

    # --- Role Management ---

    def set_role(self, new_role: WSNRole) -> None:
        """
        Change node role and emit event.

        Args:
            new_role: New role for this node
        """
        if new_role == self.role:
            return

        old_role = self.role
        self.role = new_role

        if new_role == WSNRole.CLUSTER_HEAD:
            self._times_as_ch += 1
            self.cluster_id = self.id
            self.cluster_head_id = self.id

        overlay = self._get_role_overlay()
        self.write_state({
            "ts": time.time(),
            "node": {
                "algo_id": self.id,
                "uuid": self.uuid,
                "name": self.name,
                "type": self.type
            },
            "role": new_role.value,
            "energy": self.current_energy,
            "overlay": overlay,
        })
        self.emit({
            "type": "role_change",
            "round": self.round_number,
            "old_role": old_role.value,
            "new_role": new_role.value,
            "cluster_id": self.cluster_id,
        })

    def _get_role_overlay(self) -> Dict[str, str]:
        """Get visual overlay based on current role and energy level."""
        if not self.is_alive:
            return ENERGY_OVERLAYS["dead"]

        if self.role in (WSNRole.BASE_STATION, WSNRole.CLUSTER_HEAD, WSNRole.CHAIN_LEADER):
            return ROLE_OVERLAYS.get(self.role, ROLE_OVERLAYS[WSNRole.SENSOR])

        # For sensors, color by energy level
        energy_ratio = self.current_energy / self.initial_energy if self.initial_energy > 0 else 0

        if energy_ratio > 0.5:
            return ENERGY_OVERLAYS["high"]
        elif energy_ratio > 0.2:
            return ENERGY_OVERLAYS["medium"]
        else:
            return ENERGY_OVERLAYS["low"]

    # --- Event Emission ---

    def emit_energy_state(self) -> None:
        """Emit current energy state."""
        self.emit({
            "type": "energy",
            "round": self.round_number,
            "node_id": self.id,
            "current_energy": self.current_energy,
            "initial_energy": self.initial_energy,
            "residual_ratio": self.current_energy / self.initial_energy if self.initial_energy > 0 else 0,
            "is_alive": self.is_alive,
            "role": self.role.value,
            "position": list(self.position),
        })

    def emit_cluster_info(self) -> None:
        """Emit cluster membership information."""
        self.emit({
            "type": "cluster_info",
            "round": self.round_number,
            "node_id": self.id,
            "role": self.role.value,
            "cluster_id": self.cluster_id,
            "cluster_head_id": self.cluster_head_id,
            "is_ch": self.role == WSNRole.CLUSTER_HEAD,
            "members": self.cluster_members if self.role == WSNRole.CLUSTER_HEAD else [],
        })

    def emit_round_summary(self) -> None:
        """Emit end-of-round summary."""
        self.emit({
            "type": "round_summary",
            "round": self.round_number,
            "node_id": self.id,
            "is_alive": self.is_alive,
            "current_energy": self.current_energy,
            "energy_consumed": self._energy_consumed,
            "role": self.role.value,
            "cluster_id": self.cluster_id,
            "packets_sent": self._packets_sent,
            "packets_received": self._packets_received,
            "packets_to_bs": self._packets_to_bs,
        })

    # --- Packet Tracking ---

    def record_packet_sent(self, bits: int, to_bs: bool = False) -> None:
        """Record a packet transmission."""
        self._packets_sent += 1
        if to_bs:
            self._packets_to_bs += 1
            self.emit({
                "type": "packet_to_bs",
                "round": self.round_number,
                "node_id": self.id,
                "bits": bits,
                "total_packets_to_bs": self._packets_to_bs,
            })

    def record_packet_received(self, bits: int) -> None:
        """Record a packet reception."""
        self._packets_received += 1

    # --- Utility Methods ---

    def get_signal_strength(self, other_id: int) -> float:
        """
        Get signal strength to another node.

        Uses Mininet-WiFi propagation model if available,
        otherwise uses log-distance approximation.

        Args:
            other_id: ID of the other node

        Returns:
            Signal strength in dBm (negative values)
        """
        dist = self.distance_to(other_id)
        if dist <= 0:
            return 0.0

        # Log-distance model approximation
        # RSSI = -10 * n * log10(d) + A
        # where n is path loss exponent, A is reference RSSI at 1m
        exponent = float(self.params.get("propagation_exp", 4))
        ref_rssi = float(self.params.get("ref_rssi", -30))

        return ref_rssi - 10 * exponent * math.log10(dist)

    def find_closest_node(
        self,
        node_ids: List[int],
        exclude_self: bool = True
    ) -> Optional[int]:
        """
        Find the closest node from a list.

        Args:
            node_ids: List of node IDs to search
            exclude_self: Whether to exclude this node from search

        Returns:
            ID of closest node, or None if empty
        """
        min_dist = float('inf')
        closest_id = None

        for nid in node_ids:
            if exclude_self and nid == self.id:
                continue
            dist = self.distance_to(nid)
            if dist < min_dist:
                min_dist = dist
                closest_id = nid

        return closest_id

    def get_neighbors_in_range(self, max_range: float) -> List[int]:
        """
        Get neighbor IDs within a certain range.

        Args:
            max_range: Maximum distance in meters

        Returns:
            List of neighbor IDs within range
        """
        in_range = []
        for nid in self.neighbors.keys():
            if self.distance_to(int(nid)) <= max_range:
                in_range.append(int(nid))
        return in_range

    def to_dict(self) -> Dict[str, Any]:
        """Export node state as dictionary."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "position": list(self.position),
            "node_type": self.node_type.value,
            "role": self.role.value,
            "initial_energy": self.initial_energy,
            "current_energy": self.current_energy,
            "is_alive": self.is_alive,
            "cluster_id": self.cluster_id,
            "cluster_head_id": self.cluster_head_id,
            "round_number": self.round_number,
            "packets_sent": self._packets_sent,
            "packets_received": self._packets_received,
            "packets_to_bs": self._packets_to_bs,
            "times_as_ch": self._times_as_ch,
            "energy_consumed": self._energy_consumed,
        }
