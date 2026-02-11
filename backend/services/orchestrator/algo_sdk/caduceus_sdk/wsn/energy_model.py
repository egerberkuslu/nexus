"""
Energy Model for WSN Protocols.

Supports two modes:
1. Mininet-WiFi Native: Uses mn_wifi/energy.py state-based consumption
2. First-Order Radio Model: Fallback for non-emulation testing

Mininet-WiFi Energy Model (from mn_wifi/energy.py):
- State-specific factors: Idle=0.273, Tx=0.380, Rx=0.313, Sleep=0.033
- Formula: Energy (Wh) = (voltage × factor × 0.1) / 3600 / 1000

First-Order Radio Model (academic standard):
- E_TX = E_elec * k + E_amp * k * d^n (n=2 if d<d0, n=4 otherwise)
- E_RX = E_elec * k
- E_AGG = E_da * k

References:
- Mininet-WiFi: https://github.com/intrig-unicamp/mininet-wifi/blob/master/mn_wifi/energy.py
- Polastre et al. 2004 (BitZigBee model)
- Heinzelman et al. 2000 (LEACH energy model)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Dict

# Mininet-WiFi State Factors (from mn_wifi/energy.py)
IDLE_FACTOR = 0.273
TX_FACTOR = 0.380
RX_FACTOR = 0.313
SLEEP_FACTOR = 0.033

# BitZigBee Energy Model (Polastre et al. 2004)
BITZIGBEE_TX_ENERGY = 0.00012  # J/byte
BITZIGBEE_RX_ENERGY = 0.00009  # J/byte

# First-Order Radio Model Defaults (Heinzelman et al.)
DEFAULT_E_ELEC = 50e-9          # 50 nJ/bit - Electronics energy
DEFAULT_E_AMP_FS = 10e-12       # 10 pJ/bit/m^2 - Free-space amplifier
DEFAULT_E_AMP_MP = 0.0013e-12   # 0.0013 pJ/bit/m^4 - Multipath amplifier
DEFAULT_E_DA = 5e-9             # 5 nJ/bit/signal - Data aggregation
DEFAULT_D0 = 87.0               # Crossover distance (meters)


class EnergyState(str, Enum):
    """Energy consumption states for WSN nodes."""
    IDLE = "idle"
    TX = "tx"
    RX = "rx"
    SLEEP = "sleep"


@dataclass
class EnergyModel:
    """
    First-Order Radio Energy Model for WSN.

    This is the standard academic model used in LEACH, PEGASIS, SEP, etc.
    Used as fallback when Mininet-WiFi energy tracking is not available.

    Attributes:
        e_elec: Electronics energy per bit (J/bit)
        e_amp_fs: Free-space amplifier energy (J/bit/m^2)
        e_amp_mp: Multipath amplifier energy (J/bit/m^4)
        e_da: Data aggregation energy per bit (J/bit)
        d0: Crossover distance between free-space and multipath models (m)
    """
    e_elec: float = DEFAULT_E_ELEC
    e_amp_fs: float = DEFAULT_E_AMP_FS
    e_amp_mp: float = DEFAULT_E_AMP_MP
    e_da: float = DEFAULT_E_DA
    d0: float = DEFAULT_D0

    def __post_init__(self) -> None:
        """Calculate crossover distance if not provided."""
        if self.d0 <= 0:
            # d0 = sqrt(e_amp_fs / e_amp_mp)
            if self.e_amp_mp > 0:
                self.d0 = math.sqrt(self.e_amp_fs / self.e_amp_mp)
            else:
                self.d0 = DEFAULT_D0

    def tx_energy(self, bits: int, distance: float) -> float:
        """
        Calculate transmission energy.

        E_TX = E_elec * k + E_amp * k * d^n
        where n=2 for d < d0 (free space), n=4 for d >= d0 (multipath)

        Args:
            bits: Number of bits to transmit
            distance: Distance to receiver in meters

        Returns:
            Energy consumed in Joules
        """
        bits = max(0, int(bits))
        distance = max(0.0, float(distance))

        if distance < self.d0:
            # Free-space model (d^2)
            return (self.e_elec * bits) + (self.e_amp_fs * bits * distance ** 2)
        else:
            # Multipath model (d^4)
            return (self.e_elec * bits) + (self.e_amp_mp * bits * distance ** 4)

    def rx_energy(self, bits: int) -> float:
        """
        Calculate reception energy.

        E_RX = E_elec * k

        Args:
            bits: Number of bits received

        Returns:
            Energy consumed in Joules
        """
        bits = max(0, int(bits))
        return self.e_elec * bits

    def aggregation_energy(self, bits: int) -> float:
        """
        Calculate data aggregation energy.

        E_AGG = E_da * k

        Args:
            bits: Number of bits aggregated

        Returns:
            Energy consumed in Joules
        """
        bits = max(0, int(bits))
        return self.e_da * bits

    def total_ch_round_energy(
        self,
        bits_per_member: int,
        num_members: int,
        distance_to_bs: float,
        include_own_data: bool = True
    ) -> float:
        """
        Estimate total energy for a Cluster Head in one round.

        CH receives from all members, aggregates data, and transmits to BS.

        Args:
            bits_per_member: Data bits from each cluster member
            num_members: Number of cluster members (excluding CH)
            distance_to_bs: Distance from CH to Base Station
            include_own_data: Whether CH also has its own sensor data

        Returns:
            Total energy consumed in Joules
        """
        # Receive from all members
        rx_total = self.rx_energy(bits_per_member) * num_members

        # Aggregate data (members + own if applicable)
        data_sources = num_members + (1 if include_own_data else 0)
        agg_total = self.aggregation_energy(bits_per_member) * data_sources

        # Transmit aggregated data to BS
        tx_total = self.tx_energy(bits_per_member, distance_to_bs)

        return rx_total + agg_total + tx_total

    def total_member_round_energy(
        self,
        bits: int,
        distance_to_ch: float
    ) -> float:
        """
        Estimate total energy for a cluster member in one round.

        Member transmits its data to the Cluster Head.

        Args:
            bits: Data bits to transmit
            distance_to_ch: Distance from member to Cluster Head

        Returns:
            Total energy consumed in Joules
        """
        return self.tx_energy(bits, distance_to_ch)


@dataclass
class MininetWiFiEnergyAdapter:
    """
    Adapter for Mininet-WiFi's native energy consumption model.

    This class interfaces with Mininet-WiFi's Energy class from mn_wifi/energy.py
    to get actual consumption values from emulated wireless interfaces.

    Mininet-WiFi Formula:
        Energy (Wh) = (voltage × factor × 0.1) / 3600 / 1000

    State Factors:
        - Idle: 0.273
        - Tx: 0.380
        - Rx: 0.313
        - Sleep: 0.033

    Alternative BitZigBee Model (per-byte):
        - TX: 0.00012 J/byte
        - RX: 0.00009 J/byte
    """
    voltage: float = 3.7  # Default operating voltage
    battery_capacity: float = 0.5  # Battery capacity in Joules (for FND tracking)
    use_bitzigbee: bool = False  # Use BitZigBee model instead of state-based

    # State tracking
    _consumption: float = field(default=0.0, init=False)
    _state_history: Dict[EnergyState, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Initialize state history tracking."""
        self._state_history = {
            EnergyState.IDLE: 0.0,
            EnergyState.TX: 0.0,
            EnergyState.RX: 0.0,
            EnergyState.SLEEP: 0.0,
        }

    @staticmethod
    def get_state_factor(state: EnergyState) -> float:
        """Get the energy factor for a given state."""
        factors = {
            EnergyState.IDLE: IDLE_FACTOR,
            EnergyState.TX: TX_FACTOR,
            EnergyState.RX: RX_FACTOR,
            EnergyState.SLEEP: SLEEP_FACTOR,
        }
        return factors.get(state, IDLE_FACTOR)

    def calculate_state_energy(self, state: EnergyState, duration_seconds: float = 0.1) -> float:
        """
        Calculate energy consumed for a given state and duration.

        Formula: Energy (Wh) = (voltage × factor × duration) / 3600 / 1000
        Converted to Joules: Energy (J) = Energy (Wh) * 3600

        Args:
            state: Current energy state
            duration_seconds: Duration in state (default 0.1s)

        Returns:
            Energy consumed in Joules
        """
        factor = self.get_state_factor(state)
        # Original formula gives Wh, convert to Joules
        energy_wh = (self.voltage * factor * duration_seconds) / 3600 / 1000
        energy_j = energy_wh * 3600  # Convert Wh to J
        return energy_j

    def calculate_bitzigbee_energy(self, bytes_count: int, is_tx: bool) -> float:
        """
        Calculate energy using BitZigBee model (Polastre et al. 2004).

        Args:
            bytes_count: Number of bytes transmitted/received
            is_tx: True for transmission, False for reception

        Returns:
            Energy consumed in Joules
        """
        if is_tx:
            return BITZIGBEE_TX_ENERGY * bytes_count
        else:
            return BITZIGBEE_RX_ENERGY * bytes_count

    def tx_energy(self, bits: int, distance: float = 0.0) -> float:
        """
        Calculate transmission energy.

        Uses BitZigBee per-byte model if enabled, otherwise uses state-based.

        Args:
            bits: Number of bits to transmit
            distance: Distance (ignored for Mininet-WiFi model)

        Returns:
            Energy consumed in Joules
        """
        if self.use_bitzigbee:
            bytes_count = (bits + 7) // 8
            return self.calculate_bitzigbee_energy(bytes_count, is_tx=True)
        else:
            # Assume typical TX takes ~0.1s for a packet
            return self.calculate_state_energy(EnergyState.TX, 0.1)

    def rx_energy(self, bits: int) -> float:
        """
        Calculate reception energy.

        Args:
            bits: Number of bits received

        Returns:
            Energy consumed in Joules
        """
        if self.use_bitzigbee:
            bytes_count = (bits + 7) // 8
            return self.calculate_bitzigbee_energy(bytes_count, is_tx=False)
        else:
            return self.calculate_state_energy(EnergyState.RX, 0.1)

    def idle_energy(self, duration_seconds: float) -> float:
        """
        Calculate idle energy consumption.

        Args:
            duration_seconds: Duration in idle state

        Returns:
            Energy consumed in Joules
        """
        return self.calculate_state_energy(EnergyState.IDLE, duration_seconds)

    def sleep_energy(self, duration_seconds: float) -> float:
        """
        Calculate sleep mode energy consumption.

        Args:
            duration_seconds: Duration in sleep state

        Returns:
            Energy consumed in Joules
        """
        return self.calculate_state_energy(EnergyState.SLEEP, duration_seconds)

    def consume(self, energy: float, state: EnergyState = EnergyState.IDLE) -> float:
        """
        Record energy consumption.

        Args:
            energy: Energy consumed in Joules
            state: State during consumption

        Returns:
            Total consumption after this operation
        """
        self._consumption += energy
        self._state_history[state] = self._state_history.get(state, 0.0) + energy
        return self._consumption

    @property
    def consumption(self) -> float:
        """Total energy consumed so far in Joules."""
        return self._consumption

    @property
    def remaining_capacity(self) -> float:
        """Remaining battery capacity in Joules."""
        return max(0.0, self.battery_capacity - self._consumption)

    @property
    def remaining_ratio(self) -> float:
        """Remaining battery as ratio of initial capacity (0.0 - 1.0)."""
        if self.battery_capacity <= 0:
            return 0.0
        return self.remaining_capacity / self.battery_capacity

    @property
    def is_alive(self) -> bool:
        """Check if node still has energy."""
        return self.remaining_capacity > 0

    def get_from_mininet_wifi(self, node: Any) -> Optional[float]:
        """
        Get energy consumption from a Mininet-WiFi node.

        Args:
            node: Mininet-WiFi station/sensor node

        Returns:
            Consumption value if available, None otherwise
        """
        try:
            # Try to get consumption from wireless interface
            if hasattr(node, 'wintfs') and node.wintfs:
                intf = node.wintfs[0]
                if hasattr(intf, 'consumption'):
                    return float(intf.consumption)

            # Try node-level consumption
            if hasattr(node, 'consumption'):
                return float(node.consumption)

            return None
        except Exception:
            return None

    def sync_from_mininet_wifi(self, node: Any) -> bool:
        """
        Synchronize consumption from Mininet-WiFi node.

        Args:
            node: Mininet-WiFi station/sensor node

        Returns:
            True if sync successful, False otherwise
        """
        consumption = self.get_from_mininet_wifi(node)
        if consumption is not None:
            self._consumption = consumption
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Export energy state as dictionary."""
        return {
            "voltage": self.voltage,
            "battery_capacity": self.battery_capacity,
            "consumption": self._consumption,
            "remaining_capacity": self.remaining_capacity,
            "remaining_ratio": self.remaining_ratio,
            "is_alive": self.is_alive,
            "use_bitzigbee": self.use_bitzigbee,
            "state_history": {k.value: v for k, v in self._state_history.items()},
        }


def create_energy_model(
    mode: str = "auto",
    voltage: float = 3.7,
    battery_capacity: float = 0.5,
    **kwargs
) -> EnergyModel | MininetWiFiEnergyAdapter:
    """
    Factory function to create appropriate energy model.

    Args:
        mode: "mininet-wifi", "first-order", or "auto"
        voltage: Operating voltage (for Mininet-WiFi mode)
        battery_capacity: Initial battery capacity in Joules
        **kwargs: Additional parameters for the energy model

    Returns:
        Appropriate energy model instance
    """
    if mode == "mininet-wifi":
        return MininetWiFiEnergyAdapter(
            voltage=voltage,
            battery_capacity=battery_capacity,
            use_bitzigbee=kwargs.get("use_bitzigbee", False),
        )
    elif mode == "first-order":
        return EnergyModel(
            e_elec=kwargs.get("e_elec", DEFAULT_E_ELEC),
            e_amp_fs=kwargs.get("e_amp_fs", DEFAULT_E_AMP_FS),
            e_amp_mp=kwargs.get("e_amp_mp", DEFAULT_E_AMP_MP),
            e_da=kwargs.get("e_da", DEFAULT_E_DA),
            d0=kwargs.get("d0", DEFAULT_D0),
        )
    else:
        # Auto mode: prefer Mininet-WiFi adapter as it can fall back to calculations
        return MininetWiFiEnergyAdapter(
            voltage=voltage,
            battery_capacity=battery_capacity,
            use_bitzigbee=kwargs.get("use_bitzigbee", False),
        )
