"""
LEACH Protocol Implementation.

LEACH (Low-Energy Adaptive Clustering Hierarchy) is a hierarchical
clustering protocol for wireless sensor networks.

Key Features:
- Probabilistic cluster head election
- Self-organizing clusters each round
- Data aggregation at cluster heads
- Direct transmission from CH to BS

Algorithm Phases per Round:
1. Setup Phase:
   - CH Election: Probabilistic threshold T(n) = p / (1 - p * (r mod 1/p))
   - Advertisement: CHs broadcast ADV messages
   - Cluster Formation: Non-CHs join closest CH
   - TDMA Schedule: CH creates schedule for members

2. Steady-State Phase:
   - Data Transmission: Members transmit in TDMA slots
   - Aggregation: CH aggregates received data
   - BS Transmission: CH sends aggregated data to BS

Reference:
Heinzelman, W., Chandrakasan, A., & Balakrishnan, H. (2000).
Energy-efficient communication protocol for wireless microsensor networks.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from ..wsn_node_base import WSNNode, WSNRole, WSNNodeType
from ..metrics_collector import WSNMetricsCollector


class LEACHNode(WSNNode):
    """
    LEACH protocol node implementation.

    Attributes:
        p: Cluster head probability (default 0.05 = 5%)
        rounds_since_ch: Rounds since this node was CH
        is_ch_eligible: Whether eligible to be CH this epoch
        adv_received: ADV messages received {ch_id: distance}
        tdma_schedule: TDMA slot assignments {node_id: slot}
    """

    def __init__(self, ctx: Any) -> None:
        """Initialize LEACH node."""
        super().__init__(ctx)

        # LEACH-specific parameters
        self.p: float = float(self.params.get("p", 0.05))

        # CH eligibility tracking
        self.rounds_since_ch: int = 0
        self.is_ch_eligible: bool = True
        self._last_ch_round: int = -1

        # Cluster formation data
        self.adv_received: Dict[int, float] = {}  # ch_id -> distance
        self.tdma_schedule: Dict[int, int] = {}   # node_id -> slot
        self.my_tdma_slot: int = -1

        # Packet parameters
        self.packet_size: int = int(self.params.get("packet_size", 4000))  # bits

        # Network-wide metrics collector (for BS node)
        self._metrics_collector: Optional[WSNMetricsCollector] = None
        if self.role == WSNRole.BASE_STATION:
            total_nodes = int(self.params.get("total_nodes", len(self.neighbors) + 1))
            self._metrics_collector = WSNMetricsCollector(
                node=self,
                total_nodes=total_nodes,
                is_network_wide=True
            )

    def run(self):
        """
        Main LEACH protocol execution loop.

        Generator-based execution compatible with algo_sdk.
        """
        # Initial setup
        yield from self._discover_neighbors()

        # If this is base station, just collect data
        if self.role == WSNRole.BASE_STATION:
            yield from self._run_base_station()
            return

        # Main simulation loop
        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if not self.is_alive:
                # Dead node just waits
                yield self.mailbox.get(1.0)
                continue

            # === SETUP PHASE ===
            yield from self._ch_election_phase()
            yield from self._cluster_formation_phase()

            if self.role == WSNRole.CLUSTER_HEAD:
                yield from self._tdma_schedule_phase()

            # === STEADY-STATE PHASE ===
            yield from self._data_transmission_phase()

            # Emit round metrics
            self.emit_round_summary()
            self.emit_energy_state()

            # Reset for next round
            self._reset_round_state()

        # Simulation complete
        self.emit({
            "type": "done",
            "total_rounds": max_rounds,
            "final_energy": self.current_energy,
            "is_alive": self.is_alive,
        })

    def _discover_neighbors(self):
        """Discover network neighbors via HELLO broadcast."""
        discovery_seconds = float(self.params.get("discovery_seconds", 2.0))
        hello_interval = float(self.params.get("hello_interval", 0.5))
        start = time.time()
        next_hello = 0.0

        while time.time() - start < discovery_seconds:
            now = time.time()
            if now >= next_hello:
                # Broadcast HELLO with our position and energy
                self.broadcast({
                    "type": "HELLO",
                    "position": list(self.position),
                    "energy": self.current_energy,
                    "node_type": self.node_type.value,
                })
                next_hello = now + hello_interval

            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                if msg.get("type") == "HELLO":
                    sender = msg.get("sender")
                    if sender is not None and sender != self.id:
                        # Store neighbor info
                        self.neighbors[int(sender)] = {
                            "position": msg.get("position"),
                            "energy": msg.get("energy"),
                            "node_type": msg.get("node_type"),
                        }

        self.emit({
            "type": "neighbors_discovered",
            "count": len(self.neighbors),
            "neighbors": list(self.neighbors.keys()),
        })

    def _ch_election_phase(self):
        """
        Cluster Head election using probabilistic threshold.

        T(n) = p / (1 - p * (r mod 1/p))  for eligible nodes
        T(n) = 0  for ineligible nodes

        Node becomes CH if random() < T(n)
        """
        # Check eligibility (can't be CH twice in same epoch)
        epoch_length = int(1 / self.p) if self.p > 0 else 100
        r_mod = self.round_number % epoch_length

        # Reset eligibility at start of new epoch
        if r_mod == 0:
            self.is_ch_eligible = True

        # Calculate threshold
        if self.is_ch_eligible and self.p > 0:
            denominator = 1 - self.p * r_mod
            if denominator > 0:
                threshold = self.p / denominator
            else:
                threshold = 1.0  # Guarantee CH selection
        else:
            threshold = 0.0

        # Random election
        rand_val = random.random()

        if rand_val < threshold:
            # Become cluster head
            self.set_role(WSNRole.CLUSTER_HEAD)
            self.is_ch_eligible = False
            self._last_ch_round = self.round_number
            self.cluster_members = [self.id]

            # Broadcast ADV message multiple times for reliability
            adv_count = int(self.params.get("adv_broadcast_count", 3))
            for _ in range(adv_count):
                self.broadcast({
                    "type": "ADV",
                    "ch_id": self.id,
                    "round": self.round_number,
                    "position": list(self.position),
                    "energy": self.current_energy,
                })

                # Energy for ADV broadcast
                # Approximate: broadcast to all neighbors at max distance
                max_dist = max(
                    (self.distance_to(int(nid)) for nid in self.neighbors.keys()),
                    default=50.0
                )
                self.consume_tx_energy(100, max_dist)  # Small ADV packet

                yield self.mailbox.get(0.1)

            self.emit({
                "type": "became_ch",
                "round": self.round_number,
                "threshold": threshold,
                "random": rand_val,
            })
        else:
            # Stay as sensor, listen for ADV messages
            self.set_role(WSNRole.SENSOR)
            self.adv_received.clear()

            # Listen for ADV messages
            adv_listen_time = float(self.params.get("adv_listen_time", 1.5))
            start = time.time()

            while time.time() - start < adv_listen_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "ADV" and msg.get("round") == self.round_number:
                        ch_id = msg.get("ch_id")
                        ch_pos = msg.get("position", [0, 0])

                        # Calculate distance to this CH
                        dist = math.sqrt(
                            (self.position[0] - ch_pos[0]) ** 2 +
                            (self.position[1] - ch_pos[1]) ** 2
                        )
                        self.adv_received[ch_id] = dist

                        # Energy for receiving ADV
                        self.consume_rx_energy(100)

    def _cluster_formation_phase(self):
        """
        Non-CH nodes join the closest cluster.

        CH nodes collect JOIN_REQ messages and track members.
        """
        if self.role == WSNRole.CLUSTER_HEAD:
            # Wait for JOIN_REQ messages
            join_listen_time = float(self.params.get("join_listen_time", 1.0))
            start = time.time()

            while time.time() - start < join_listen_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "JOIN_REQ" and msg.get("ch_id") == self.id:
                        member_id = msg.get("sender")
                        if member_id is not None and member_id not in self.cluster_members:
                            self.cluster_members.append(int(member_id))

                            # Energy for receiving JOIN_REQ
                            self.consume_rx_energy(100)

            self.emit({
                "type": "cluster_formed",
                "ch_id": self.id,
                "members": self.cluster_members,
                "size": len(self.cluster_members),
            })

        else:
            # Find closest CH
            if self.adv_received:
                closest_ch = min(self.adv_received.items(), key=lambda x: x[1])
                self.cluster_head_id = closest_ch[0]
                self.cluster_id = closest_ch[0]

                # Send JOIN_REQ to chosen CH
                join_msg = {
                    "type": "JOIN_REQ",
                    "ch_id": self.cluster_head_id,
                    "round": self.round_number,
                }
                self._send_to_ch(join_msg)

                # Energy for sending JOIN_REQ
                self.consume_tx_energy(100, closest_ch[1])

                self.emit({
                    "type": "joined_cluster",
                    "ch_id": self.cluster_head_id,
                    "distance": closest_ch[1],
                })
            else:
                # No CH found - isolated node or all CHs out of range
                self.cluster_head_id = None
                self.cluster_id = None
                self.emit({
                    "type": "no_cluster",
                    "round": self.round_number,
                })

            yield self.mailbox.get(0.5)

    def _tdma_schedule_phase(self):
        """
        CH creates TDMA schedule and broadcasts to members.
        """
        if self.role != WSNRole.CLUSTER_HEAD:
            # Wait for schedule from CH
            schedule_wait = float(self.params.get("schedule_wait_time", 1.0))
            start = time.time()

            while time.time() - start < schedule_wait:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "TDMA_SCHEDULE" and msg.get("ch_id") == self.cluster_head_id:
                        schedule = msg.get("schedule", {})
                        self.my_tdma_slot = schedule.get(str(self.id), -1)
                        self.consume_rx_energy(200)

            return

        # Create TDMA schedule
        self.tdma_schedule = {}
        slot = 0
        for member_id in self.cluster_members:
            if member_id != self.id:  # CH doesn't need a slot
                self.tdma_schedule[member_id] = slot
                slot += 1

        # Broadcast schedule to cluster members
        schedule_msg = {
            "type": "TDMA_SCHEDULE",
            "ch_id": self.id,
            "round": self.round_number,
            "schedule": {str(k): v for k, v in self.tdma_schedule.items()},
        }

        # Send to each member
        for member_id in self.cluster_members:
            if member_id != self.id:
                self._send_to_node(member_id, schedule_msg)

        # Energy for broadcasting schedule
        max_dist = max(
            (self.distance_to(int(mid)) for mid in self.cluster_members if mid != self.id),
            default=10.0
        )
        self.consume_tx_energy(200, max_dist)

        yield self.mailbox.get(0.3)

    def _data_transmission_phase(self):
        """
        Steady-state data transmission.

        Members transmit in TDMA slots, CH aggregates and sends to BS.
        """
        if self.role == WSNRole.CLUSTER_HEAD:
            # Receive data from members
            received_data: List[int] = []
            frame_time = float(self.params.get("frame_time", 2.0))
            start = time.time()

            while time.time() - start < frame_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "DATA" and msg.get("ch_id") == self.id:
                        sender = msg.get("sender")
                        if sender is not None:
                            received_data.append(sender)
                            self.consume_rx_energy(self.packet_size)
                            self.record_packet_received(self.packet_size)

            # Aggregate data
            total_sources = len(received_data) + 1  # +1 for own data
            self.consume_aggregation_energy(self.packet_size * total_sources)

            # Transmit aggregated data to BS
            dist_to_bs = self.distance_to_bs()
            self.consume_tx_energy(self.packet_size, dist_to_bs)
            self.record_packet_sent(self.packet_size, to_bs=True)

            self.emit({
                "type": "ch_transmission",
                "round": self.round_number,
                "members_received": len(received_data),
                "total_aggregated": total_sources,
                "distance_to_bs": dist_to_bs,
            })

        else:
            # Member: transmit data to CH in TDMA slot
            if self.cluster_head_id is not None:
                # Wait for our slot (simplified - just small delay)
                slot_delay = float(self.my_tdma_slot * 0.1) if self.my_tdma_slot >= 0 else 0.1
                yield self.mailbox.get(slot_delay)

                # Send data to CH
                data_msg = {
                    "type": "DATA",
                    "ch_id": self.cluster_head_id,
                    "round": self.round_number,
                    "data_size": self.packet_size,
                }
                self._send_to_ch(data_msg)

                # Energy for transmission
                dist_to_ch = self.distance_to(self.cluster_head_id)
                self.consume_tx_energy(self.packet_size, dist_to_ch)
                self.record_packet_sent(self.packet_size)

                self.emit({
                    "type": "member_transmission",
                    "round": self.round_number,
                    "ch_id": self.cluster_head_id,
                    "distance": dist_to_ch,
                })
            else:
                # Direct transmission to BS (no cluster)
                dist_to_bs = self.distance_to_bs()
                self.consume_tx_energy(self.packet_size, dist_to_bs)
                self.record_packet_sent(self.packet_size, to_bs=True)

            # Wait for frame to complete
            yield self.mailbox.get(0.5)

    def _run_base_station(self):
        """
        Base station operation - collect data and track metrics.
        """
        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if self._metrics_collector:
                self._metrics_collector.start_new_round(r)

            # Listen for transmissions
            round_time = float(self.params.get("round_time", 5.0))
            packets_received = 0
            start = time.time()

            while time.time() - start < round_time:
                yield self.mailbox.get(0.5)
                for msg in self._drain_mailbox():
                    msg_type = msg.get("type")

                    if msg_type == "DATA" or msg_type == "ch_transmission":
                        packets_received += 1

                    # Track node states from events
                    if msg_type in ("energy", "round_summary") and self._metrics_collector:
                        node_id = msg.get("node_id") or msg.get("sender")
                        if node_id is not None:
                            self._metrics_collector.update_node_state(
                                node_id=int(node_id),
                                energy=msg.get("current_energy", 0),
                                is_alive=msg.get("is_alive", True),
                                role=msg.get("role", "sensor"),
                                cluster_id=msg.get("cluster_id"),
                            )

                    if msg_type == "cluster_formed" and self._metrics_collector:
                        self._metrics_collector.record_cluster_formed(
                            ch_id=msg.get("ch_id"),
                            members=msg.get("members", []),
                        )

            # Complete round metrics
            if self._metrics_collector:
                metrics = self._metrics_collector.complete_round(packets_received)
                self.emit({
                    "type": "bs_round_complete",
                    "round": r,
                    "packets_received": packets_received,
                    "alive_nodes": metrics.alive_nodes,
                    "clusters": metrics.cluster_count,
                })

                # Check if simulation should end
                if metrics.alive_nodes == 0:
                    break

        # Emit final summary
        if self._metrics_collector:
            self._metrics_collector.emit_final_summary()

        self.emit({
            "type": "done",
            "role": "base_station",
            "total_rounds": self.round_number,
        })

    def _reset_round_state(self):
        """Reset state for next round."""
        self.adv_received.clear()
        self.tdma_schedule.clear()
        self.my_tdma_slot = -1

        if self.role == WSNRole.CLUSTER_HEAD:
            self.cluster_members = []

        # Reset role to sensor (CH selection happens each round)
        if self.role != WSNRole.BASE_STATION:
            self.role = WSNRole.SENSOR
            self.cluster_id = None
            self.cluster_head_id = None

    def _send_to_ch(self, msg: Dict[str, Any]) -> None:
        """Send message to cluster head."""
        if self.cluster_head_id is None:
            return

        # Find CH address from neighbors
        ch_info = self.neighbors.get(int(self.cluster_head_id))
        if ch_info:
            ip = ch_info.get("ip")
            port = ch_info.get("port", self.ctx.listen_port)
            if ip:
                self.sendToAddr(ip, port, msg)
                return

        # Fallback: broadcast
        self.broadcast(msg)

    def _send_to_node(self, node_id: int, msg: Dict[str, Any]) -> None:
        """Send message to specific node."""
        node_info = self.neighbors.get(int(node_id))
        if node_info:
            ip = node_info.get("ip")
            port = node_info.get("port", self.ctx.listen_port)
            if ip:
                self.sendToAddr(ip, port, msg)
                return

        # Fallback: broadcast with target field
        msg["target"] = node_id
        self.broadcast(msg)

    def _drain_mailbox(self) -> List[Dict[str, Any]]:
        """Drain all messages from mailbox."""
        messages = []
        while True:
            msg = self.receiveMessage()
            if msg is None:
                break
            messages.append(msg)
        return messages
