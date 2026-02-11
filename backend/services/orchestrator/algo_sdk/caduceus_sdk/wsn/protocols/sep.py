"""
SEP (Stable Election Protocol) Implementation.

SEP is designed for heterogeneous wireless sensor networks where
nodes have different initial energy levels.

Key Features:
- Two node types: Normal and Advanced (with extra energy)
- Weighted CH election probabilities based on initial energy
- Extended stability period compared to LEACH
- 26-30% longer stability period than LEACH

Node Types:
- Normal nodes: Initial energy E0
- Advanced nodes: Initial energy E0 * (1 + alpha)

CH Election Probabilities:
- p_nrm = p / (1 + m * alpha)  for normal nodes
- p_adv = p * (1 + alpha) / (1 + m * alpha)  for advanced nodes

where:
- p: Optimal CH probability
- m: Fraction of advanced nodes
- alpha: Energy factor for advanced nodes

Reference:
Smaragdakis, G., Matta, I., & Bestavros, A. (2004).
SEP: A stable election protocol for clustered heterogeneous wireless sensor networks.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional

from ..wsn_node_base import WSNNode, WSNRole, WSNNodeType
from ..metrics_collector import WSNMetricsCollector


class SEPNode(WSNNode):
    """
    SEP protocol node implementation.

    Supports heterogeneous networks with normal and advanced nodes.
    """

    def __init__(self, ctx: Any) -> None:
        """Initialize SEP node."""
        super().__init__(ctx)

        # SEP parameters
        self.p: float = float(self.params.get("p", 0.1))  # Optimal CH probability
        self.alpha: float = float(self.params.get("alpha", 1.0))  # Advanced node energy factor
        self.m: float = float(self.params.get("m", 0.1))  # Fraction of advanced nodes

        # Calculate weighted probabilities
        self.p_nrm = self.p / (1 + self.m * self.alpha)
        self.p_adv = self.p * (1 + self.alpha) / (1 + self.m * self.alpha)

        # Effective probability for this node
        if self.node_type == WSNNodeType.ADVANCED:
            self.p_eff = self.p_adv
        else:
            self.p_eff = self.p_nrm

        # CH eligibility
        self.is_ch_eligible: bool = True
        self._last_ch_round: int = -1

        # Cluster data
        self.adv_received: Dict[int, float] = {}
        self.packet_size: int = int(self.params.get("packet_size", 4000))

        # Metrics
        self._metrics_collector: Optional[WSNMetricsCollector] = None
        if self.role == WSNRole.BASE_STATION:
            total_nodes = int(self.params.get("total_nodes", len(self.neighbors) + 1))
            self._metrics_collector = WSNMetricsCollector(
                node=self,
                total_nodes=total_nodes,
                is_network_wide=True
            )

    def run(self):
        """Main SEP protocol execution loop."""
        yield from self._discover_neighbors()

        if self.role == WSNRole.BASE_STATION:
            yield from self._run_base_station()
            return

        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if not self.is_alive:
                yield self.mailbox.get(1.0)
                continue

            # SEP weighted CH election
            yield from self._ch_election_phase()
            yield from self._cluster_formation_phase()

            if self.role == WSNRole.CLUSTER_HEAD:
                yield from self._tdma_schedule_phase()

            yield from self._data_transmission_phase()

            self.emit_round_summary()
            self.emit_energy_state()
            self._reset_round_state()

        self.emit({
            "type": "done",
            "total_rounds": max_rounds,
            "node_type": self.node_type.value,
        })

    def _discover_neighbors(self):
        """Discover neighbors with node type information."""
        discovery_seconds = float(self.params.get("discovery_seconds", 2.0))
        hello_interval = float(self.params.get("hello_interval", 0.5))
        start = time.time()
        next_hello = 0.0

        while time.time() - start < discovery_seconds:
            now = time.time()
            if now >= next_hello:
                self.broadcast({
                    "type": "HELLO",
                    "position": list(self.position),
                    "energy": self.current_energy,
                    "initial_energy": self.initial_energy,
                    "node_type": self.node_type.value,
                })
                next_hello = now + hello_interval

            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                if msg.get("type") == "HELLO":
                    sender = msg.get("sender")
                    if sender is not None and sender != self.id:
                        self.neighbors[int(sender)] = {
                            "position": msg.get("position"),
                            "energy": msg.get("energy"),
                            "initial_energy": msg.get("initial_energy"),
                            "node_type": msg.get("node_type"),
                        }

        self.emit({"type": "neighbors_discovered", "count": len(self.neighbors)})

    def _ch_election_phase(self):
        """
        SEP weighted cluster head election.

        Uses different thresholds for normal and advanced nodes.
        """
        # Calculate epoch length based on node type
        epoch_length = int(1 / self.p_eff) if self.p_eff > 0 else 100
        r_mod = self.round_number % epoch_length

        # Reset eligibility at start of new epoch
        if r_mod == 0:
            self.is_ch_eligible = True

        # Calculate threshold
        if self.is_ch_eligible and self.p_eff > 0:
            denominator = 1 - self.p_eff * r_mod
            if denominator > 0:
                threshold = self.p_eff / denominator
            else:
                threshold = 1.0
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

            # Broadcast ADV with node type info
            for _ in range(3):
                self.broadcast({
                    "type": "ADV",
                    "ch_id": self.id,
                    "round": self.round_number,
                    "position": list(self.position),
                    "energy": self.current_energy,
                    "node_type": self.node_type.value,
                })

                max_dist = max(
                    (self.distance_to(int(nid)) for nid in self.neighbors.keys()),
                    default=50.0
                )
                self.consume_tx_energy(100, max_dist)
                yield self.mailbox.get(0.1)

            self.emit({
                "type": "became_ch_sep",
                "round": self.round_number,
                "node_type": self.node_type.value,
                "p_eff": self.p_eff,
                "threshold": threshold,
            })
        else:
            self.set_role(WSNRole.SENSOR)
            self.adv_received.clear()

            # Listen for ADV
            adv_listen_time = float(self.params.get("adv_listen_time", 1.5))
            start = time.time()

            while time.time() - start < adv_listen_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "ADV" and msg.get("round") == self.round_number:
                        ch_id = msg.get("ch_id")
                        ch_pos = msg.get("position", [0, 0])
                        dist = math.sqrt(
                            (self.position[0] - ch_pos[0]) ** 2 +
                            (self.position[1] - ch_pos[1]) ** 2
                        )
                        self.adv_received[ch_id] = dist
                        self.consume_rx_energy(100)

    def _cluster_formation_phase(self):
        """Join closest cluster."""
        if self.role == WSNRole.CLUSTER_HEAD:
            # Collect JOIN_REQ
            join_listen_time = float(self.params.get("join_listen_time", 1.0))
            start = time.time()

            while time.time() - start < join_listen_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "JOIN_REQ" and msg.get("ch_id") == self.id:
                        member_id = msg.get("sender")
                        if member_id is not None and member_id not in self.cluster_members:
                            self.cluster_members.append(int(member_id))
                            self.consume_rx_energy(100)

            self.emit({
                "type": "cluster_formed",
                "ch_id": self.id,
                "members": self.cluster_members,
                "size": len(self.cluster_members),
            })
        else:
            if self.adv_received:
                closest_ch = min(self.adv_received.items(), key=lambda x: x[1])
                self.cluster_head_id = closest_ch[0]
                self.cluster_id = closest_ch[0]

                join_msg = {
                    "type": "JOIN_REQ",
                    "ch_id": self.cluster_head_id,
                    "round": self.round_number,
                    "node_type": self.node_type.value,
                }
                self.broadcast(join_msg)
                self.consume_tx_energy(100, closest_ch[1])

            yield self.mailbox.get(0.5)

    def _tdma_schedule_phase(self):
        """CH sends TDMA schedule."""
        if self.role != WSNRole.CLUSTER_HEAD:
            schedule_wait = float(self.params.get("schedule_wait_time", 1.0))
            start = time.time()

            while time.time() - start < schedule_wait:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "TDMA_SCHEDULE" and msg.get("ch_id") == self.cluster_head_id:
                        self.consume_rx_energy(200)
            return

        # Create and send schedule
        schedule = {mid: i for i, mid in enumerate(self.cluster_members) if mid != self.id}

        schedule_msg = {
            "type": "TDMA_SCHEDULE",
            "ch_id": self.id,
            "round": self.round_number,
            "schedule": {str(k): v for k, v in schedule.items()},
        }
        self.broadcast(schedule_msg)

        max_dist = max(
            (self.distance_to(int(mid)) for mid in self.cluster_members if mid != self.id),
            default=10.0
        )
        self.consume_tx_energy(200, max_dist)

        yield self.mailbox.get(0.3)

    def _data_transmission_phase(self):
        """Data transmission phase."""
        if self.role == WSNRole.CLUSTER_HEAD:
            received = 0
            frame_time = float(self.params.get("frame_time", 2.0))
            start = time.time()

            while time.time() - start < frame_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "DATA" and msg.get("ch_id") == self.id:
                        received += 1
                        self.consume_rx_energy(self.packet_size)
                        self.record_packet_received(self.packet_size)

            total_sources = received + 1
            self.consume_aggregation_energy(self.packet_size * total_sources)

            dist_to_bs = self.distance_to_bs()
            self.consume_tx_energy(self.packet_size, dist_to_bs)
            self.record_packet_sent(self.packet_size, to_bs=True)
        else:
            if self.cluster_head_id is not None:
                yield self.mailbox.get(0.1)

                data_msg = {
                    "type": "DATA",
                    "ch_id": self.cluster_head_id,
                    "round": self.round_number,
                }
                self.broadcast(data_msg)

                dist_to_ch = self.distance_to(self.cluster_head_id)
                self.consume_tx_energy(self.packet_size, dist_to_ch)
                self.record_packet_sent(self.packet_size)
            else:
                dist_to_bs = self.distance_to_bs()
                self.consume_tx_energy(self.packet_size, dist_to_bs)
                self.record_packet_sent(self.packet_size, to_bs=True)

            yield self.mailbox.get(0.5)

    def _run_base_station(self):
        """Base station operation."""
        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if self._metrics_collector:
                self._metrics_collector.start_new_round(r)

            round_time = float(self.params.get("round_time", 5.0))
            packets_received = 0
            start = time.time()

            while time.time() - start < round_time:
                yield self.mailbox.get(0.5)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "DATA":
                        packets_received += 1

                    if msg.get("type") in ("energy", "round_summary") and self._metrics_collector:
                        node_id = msg.get("node_id") or msg.get("sender")
                        if node_id is not None:
                            self._metrics_collector.update_node_state(
                                node_id=int(node_id),
                                energy=msg.get("current_energy", 0),
                                is_alive=msg.get("is_alive", True),
                                role=msg.get("role", "sensor"),
                            )

                    if msg.get("type") == "cluster_formed" and self._metrics_collector:
                        self._metrics_collector.record_cluster_formed(
                            ch_id=msg.get("ch_id"),
                            members=msg.get("members", []),
                        )

            if self._metrics_collector:
                metrics = self._metrics_collector.complete_round(packets_received)
                if metrics.alive_nodes == 0:
                    break

        if self._metrics_collector:
            self._metrics_collector.emit_final_summary()

        self.emit({"type": "done", "role": "base_station"})

    def _reset_round_state(self):
        """Reset state for next round."""
        self.adv_received.clear()
        if self.role != WSNRole.BASE_STATION:
            self.role = WSNRole.SENSOR
            self.cluster_id = None
            self.cluster_head_id = None
            self.cluster_members = []

    def _drain_mailbox(self) -> List[Dict[str, Any]]:
        """Drain all messages from mailbox."""
        messages = []
        while True:
            msg = self.receiveMessage()
            if msg is None:
                break
            messages.append(msg)
        return messages
