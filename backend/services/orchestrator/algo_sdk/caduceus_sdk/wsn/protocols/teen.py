"""
TEEN (Threshold-sensitive Energy Efficient sensor Network) Implementation.

TEEN is a reactive protocol designed for time-critical applications
where data should only be transmitted when thresholds are exceeded.

Key Features:
- Reactive protocol - transmits only when thresholds exceeded
- Hard Threshold (HT): Only transmit if sensed value > HT
- Soft Threshold (ST): Only transmit if change from last value > ST
- Uses LEACH-style clustering
- Very energy efficient in stable environments
- Ideal for event-driven, alarm-type applications

Thresholds:
- Hard Threshold: Absolute threshold for sensed attribute
- Soft Threshold: Minimum change required to trigger transmission

Advantages:
- 50-70% less energy than LEACH in stable environments
- Well-suited for time-critical applications
- Reduces unnecessary transmissions

Disadvantages:
- May never transmit in stable environments (bad for periodic monitoring)
- Threshold tuning required for different applications

Reference:
Manjeshwar, A., & Agrawal, D. P. (2001).
TEEN: A routing protocol for enhanced efficiency in wireless sensor networks.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional

from ..wsn_node_base import WSNNode, WSNRole, WSNNodeType
from ..metrics_collector import WSNMetricsCollector


class TEENNode(WSNNode):
    """
    TEEN protocol node implementation.

    Reactive protocol with hard and soft thresholds.
    """

    def __init__(self, ctx: Any) -> None:
        """Initialize TEEN node."""
        super().__init__(ctx)

        # TEEN parameters
        self.p: float = float(self.params.get("p", 0.05))

        # Thresholds
        self.hard_threshold: float = float(self.params.get("hard_threshold", 50.0))
        self.soft_threshold: float = float(self.params.get("soft_threshold", 5.0))

        # Sensed value tracking
        self.current_sensed_value: float = 0.0
        self.last_transmitted_value: float = 0.0
        self.sensed_attribute: str = self.params.get("sensed_attribute", "temperature")

        # CH eligibility
        self.is_ch_eligible: bool = True

        # Cluster data
        self.adv_received: Dict[int, float] = {}
        self.packet_size: int = int(self.params.get("packet_size", 4000))

        # Transmission tracking
        self._transmissions_this_round: int = 0
        self._threshold_hits: int = 0

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
        """Main TEEN protocol execution loop."""
        yield from self._discover_neighbors()

        if self.role == WSNRole.BASE_STATION:
            yield from self._run_base_station()
            return

        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r
            self._transmissions_this_round = 0

            if not self.is_alive:
                yield self.mailbox.get(1.0)
                continue

            # LEACH-style clustering
            yield from self._ch_election_phase()
            yield from self._cluster_formation_phase()

            # TEEN-specific: reactive sensing phase
            yield from self._reactive_sensing_phase()

            # CH aggregates and transmits
            if self.role == WSNRole.CLUSTER_HEAD:
                yield from self._ch_aggregation_phase()

            self.emit_round_summary()
            self.emit_energy_state()
            self._reset_round_state()

        self.emit({
            "type": "done",
            "total_rounds": max_rounds,
            "total_threshold_hits": self._threshold_hits,
        })

    def _discover_neighbors(self):
        """Discover neighbors."""
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
                        }

        self.emit({"type": "neighbors_discovered", "count": len(self.neighbors)})

    def _ch_election_phase(self):
        """LEACH-style CH election."""
        epoch_length = int(1 / self.p) if self.p > 0 else 100
        r_mod = self.round_number % epoch_length

        if r_mod == 0:
            self.is_ch_eligible = True

        if self.is_ch_eligible and self.p > 0:
            denominator = 1 - self.p * r_mod
            threshold = self.p / denominator if denominator > 0 else 1.0
        else:
            threshold = 0.0

        if random.random() < threshold:
            self.set_role(WSNRole.CLUSTER_HEAD)
            self.is_ch_eligible = False
            self.cluster_members = [self.id]

            # Broadcast ADV with thresholds
            for _ in range(3):
                self.broadcast({
                    "type": "ADV",
                    "ch_id": self.id,
                    "round": self.round_number,
                    "position": list(self.position),
                    "hard_threshold": self.hard_threshold,
                    "soft_threshold": self.soft_threshold,
                })

                max_dist = max(
                    (self.distance_to(int(nid)) for nid in self.neighbors.keys()),
                    default=50.0
                )
                self.consume_tx_energy(100, max_dist)
                yield self.mailbox.get(0.1)

            self.emit({"type": "became_ch_teen", "round": self.round_number})
        else:
            self.set_role(WSNRole.SENSOR)
            self.adv_received.clear()

            adv_listen_time = float(self.params.get("adv_listen_time", 1.5))
            start = time.time()

            while time.time() - start < adv_listen_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "ADV" and msg.get("round") == self.round_number:
                        ch_id = msg.get("ch_id")
                        ch_pos = msg.get("position", [0, 0])

                        # Update thresholds from CH
                        ht = msg.get("hard_threshold")
                        st = msg.get("soft_threshold")
                        if ht is not None:
                            self.hard_threshold = float(ht)
                        if st is not None:
                            self.soft_threshold = float(st)

                        dist = math.sqrt(
                            (self.position[0] - ch_pos[0]) ** 2 +
                            (self.position[1] - ch_pos[1]) ** 2
                        )
                        self.adv_received[ch_id] = dist
                        self.consume_rx_energy(100)

    def _cluster_formation_phase(self):
        """Join closest cluster."""
        if self.role == WSNRole.CLUSTER_HEAD:
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
                }
                self.broadcast(join_msg)
                self.consume_tx_energy(100, closest_ch[1])

            yield self.mailbox.get(0.5)

    def _reactive_sensing_phase(self):
        """
        TEEN reactive data transmission based on thresholds.

        Only transmit if:
        1. Sensed value exceeds hard threshold, AND
        2. Change from last transmitted value exceeds soft threshold
        """
        if self.role == WSNRole.CLUSTER_HEAD:
            # CH doesn't do reactive sensing, just collects
            yield self.mailbox.get(0.1)
            return

        # Simulate sensing
        self.current_sensed_value = self._sense_environment()

        should_transmit = False

        # Hard threshold check
        if self.current_sensed_value > self.hard_threshold:
            # Soft threshold check
            value_change = abs(self.current_sensed_value - self.last_transmitted_value)
            if value_change > self.soft_threshold:
                should_transmit = True
                self._threshold_hits += 1

        if should_transmit:
            self._transmissions_this_round += 1

            # Transmit to CH
            if self.cluster_head_id is not None:
                data_msg = {
                    "type": "THRESHOLD_DATA",
                    "ch_id": self.cluster_head_id,
                    "round": self.round_number,
                    "value": self.current_sensed_value,
                    "attribute": self.sensed_attribute,
                }
                self.broadcast(data_msg)

                dist_to_ch = self.distance_to(self.cluster_head_id)
                self.consume_tx_energy(self.packet_size, dist_to_ch)
                self.record_packet_sent(self.packet_size)

                self.last_transmitted_value = self.current_sensed_value

                self.emit({
                    "type": "threshold_transmission",
                    "round": self.round_number,
                    "sensed_value": self.current_sensed_value,
                    "hard_threshold": self.hard_threshold,
                    "soft_threshold": self.soft_threshold,
                })
            else:
                # Direct to BS
                dist_to_bs = self.distance_to_bs()
                self.consume_tx_energy(self.packet_size, dist_to_bs)
                self.record_packet_sent(self.packet_size, to_bs=True)
                self.last_transmitted_value = self.current_sensed_value
        else:
            # No transmission - log why
            self.emit({
                "type": "no_transmission",
                "round": self.round_number,
                "sensed_value": self.current_sensed_value,
                "reason": "below_threshold" if self.current_sensed_value <= self.hard_threshold else "change_too_small",
            })

        yield self.mailbox.get(0.5)

    def _sense_environment(self) -> float:
        """
        Simulate environmental sensing.

        Returns a value that sometimes exceeds thresholds for testing.
        """
        # Simulate periodic events with some variation
        base_value = 40.0  # Below hard threshold normally

        # Add random variation
        variation = random.gauss(0, 10)

        # Occasionally simulate events that exceed threshold
        event_probability = float(self.params.get("event_probability", 0.1))
        if random.random() < event_probability:
            # Event occurred - value spikes above threshold
            variation += random.uniform(15, 30)

        return base_value + variation

    def _ch_aggregation_phase(self):
        """CH receives threshold data and transmits to BS."""
        received_data: List[Dict[str, Any]] = []
        frame_time = float(self.params.get("frame_time", 2.0))
        start = time.time()

        while time.time() - start < frame_time:
            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                if msg.get("type") == "THRESHOLD_DATA" and msg.get("ch_id") == self.id:
                    received_data.append({
                        "sender": msg.get("sender"),
                        "value": msg.get("value"),
                        "attribute": msg.get("attribute"),
                    })
                    self.consume_rx_energy(self.packet_size)
                    self.record_packet_received(self.packet_size)

        if received_data:
            # Aggregate and transmit to BS
            total_sources = len(received_data) + 1  # +1 for own sensing
            self.consume_aggregation_energy(self.packet_size * total_sources)

            dist_to_bs = self.distance_to_bs()
            self.consume_tx_energy(self.packet_size, dist_to_bs)
            self.record_packet_sent(self.packet_size, to_bs=True)

            self.emit({
                "type": "ch_aggregation_teen",
                "round": self.round_number,
                "data_points": len(received_data),
                "max_value": max(d["value"] for d in received_data) if received_data else 0,
            })
        else:
            # No threshold events - may still need to report
            if random.random() < 0.1:  # Periodic keepalive
                dist_to_bs = self.distance_to_bs()
                self.consume_tx_energy(100, dist_to_bs)  # Small keepalive packet

    def _run_base_station(self):
        """Base station operation."""
        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if self._metrics_collector:
                self._metrics_collector.start_new_round(r)

            round_time = float(self.params.get("round_time", 5.0))
            packets_received = 0
            threshold_events = 0
            start = time.time()

            while time.time() - start < round_time:
                yield self.mailbox.get(0.5)
                for msg in self._drain_mailbox():
                    msg_type = msg.get("type")

                    if msg_type in ("DATA", "THRESHOLD_DATA", "ch_aggregation_teen"):
                        packets_received += 1

                    if msg_type == "threshold_transmission":
                        threshold_events += 1

                    if msg_type in ("energy", "round_summary") and self._metrics_collector:
                        node_id = msg.get("node_id") or msg.get("sender")
                        if node_id is not None:
                            self._metrics_collector.update_node_state(
                                node_id=int(node_id),
                                energy=msg.get("current_energy", 0),
                                is_alive=msg.get("is_alive", True),
                                role=msg.get("role", "sensor"),
                            )

                    if msg_type == "cluster_formed" and self._metrics_collector:
                        self._metrics_collector.record_cluster_formed(
                            ch_id=msg.get("ch_id"),
                            members=msg.get("members", []),
                        )

            self.emit({
                "type": "bs_round_teen",
                "round": r,
                "packets_received": packets_received,
                "threshold_events": threshold_events,
            })

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
