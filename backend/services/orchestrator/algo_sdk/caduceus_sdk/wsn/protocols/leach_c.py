"""
LEACH-C (Centralized LEACH) Protocol Implementation.

LEACH-C is a centralized version of LEACH where the Base Station
has global knowledge of node positions and energy levels, and
selects optimal cluster heads.

Key Differences from LEACH:
- BS collects all node positions and energy levels
- BS computes optimal CH selection (above-average energy, well-distributed)
- BS broadcasts cluster assignments
- More uniform cluster distribution
- 20-30% improvement in FND over LEACH

Algorithm:
1. All nodes send status (position, energy) to BS
2. BS calculates average energy
3. BS selects CHs from nodes with above-average energy using simulated annealing
4. BS broadcasts cluster assignments
5. Steady-state phase same as LEACH

Reference:
Heinzelman, W., Chandrakasan, A., & Balakrishnan, H. (2002).
An application-specific protocol architecture for wireless microsensor networks.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..wsn_node_base import WSNNode, WSNRole, WSNNodeType
from ..metrics_collector import WSNMetricsCollector


class LEACHCNode(WSNNode):
    """
    LEACH-C (Centralized) protocol node implementation.

    Base Station collects global information and selects optimal CHs.
    """

    def __init__(self, ctx: Any) -> None:
        """Initialize LEACH-C node."""
        super().__init__(ctx)

        # LEACH-C parameters
        self.p: float = float(self.params.get("p", 0.05))
        self.packet_size: int = int(self.params.get("packet_size", 4000))

        # Node info collection (for BS)
        self._collected_node_info: Dict[int, Dict[str, Any]] = {}

        # Cluster assignments (from BS)
        self._cluster_assignments: Dict[int, int] = {}  # node_id -> ch_id
        self._assigned_members: List[int] = []  # If this node is CH

        # Metrics collector (for BS)
        self._metrics_collector: Optional[WSNMetricsCollector] = None
        if self.role == WSNRole.BASE_STATION:
            total_nodes = int(self.params.get("total_nodes", len(self.neighbors) + 1))
            self._metrics_collector = WSNMetricsCollector(
                node=self,
                total_nodes=total_nodes,
                is_network_wide=True
            )

    def run(self):
        """Main LEACH-C protocol execution loop."""
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

            # Phase 1: Send status to BS
            yield from self._send_status_to_bs()

            # Phase 2: Receive cluster assignment from BS
            yield from self._receive_cluster_assignment()

            # Phase 3: Data transmission (same as LEACH)
            yield from self._data_transmission_phase()

            self.emit_round_summary()
            self.emit_energy_state()
            self._reset_round_state()

        self.emit({"type": "done", "total_rounds": max_rounds})

    def _discover_neighbors(self):
        """Discover network neighbors."""
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
                            "node_type": msg.get("node_type"),
                        }

        self.emit({"type": "neighbors_discovered", "count": len(self.neighbors)})

    def _send_status_to_bs(self):
        """Send current status (position, energy) to base station."""
        status_msg = {
            "type": "STATUS",
            "round": self.round_number,
            "position": list(self.position),
            "energy": self.current_energy,
            "node_type": self.node_type.value,
        }

        # Direct transmission to BS
        dist_to_bs = self.distance_to_bs()
        self.broadcast(status_msg)  # BS will receive
        self.consume_tx_energy(200, dist_to_bs)

        yield self.mailbox.get(0.3)

    def _receive_cluster_assignment(self):
        """Receive cluster assignment from BS."""
        assignment_wait = float(self.params.get("assignment_wait_time", 3.0))
        start = time.time()

        while time.time() - start < assignment_wait:
            yield self.mailbox.get(0.2)
            for msg in self._drain_mailbox():
                if msg.get("type") == "CLUSTER_ASSIGNMENT" and msg.get("round") == self.round_number:
                    assignments = msg.get("assignments", {})
                    ch_ids = msg.get("ch_ids", [])

                    # Find our assignment
                    my_ch = assignments.get(str(self.id))

                    if self.id in ch_ids:
                        # We are a cluster head
                        self.set_role(WSNRole.CLUSTER_HEAD)
                        self.cluster_id = self.id
                        self.cluster_head_id = self.id

                        # Get our members
                        self._assigned_members = [
                            int(nid) for nid, chid in assignments.items()
                            if int(chid) == self.id
                        ]
                        self.cluster_members = self._assigned_members + [self.id]

                        self.emit({
                            "type": "became_ch_centralized",
                            "round": self.round_number,
                            "members": self.cluster_members,
                        })
                    elif my_ch is not None:
                        # We are a cluster member
                        self.set_role(WSNRole.SENSOR)
                        self.cluster_head_id = int(my_ch)
                        self.cluster_id = int(my_ch)

                        self.emit({
                            "type": "assigned_to_cluster",
                            "round": self.round_number,
                            "ch_id": self.cluster_head_id,
                        })

                    self.consume_rx_energy(500)
                    return

    def _data_transmission_phase(self):
        """Data transmission phase - same as LEACH."""
        if self.role == WSNRole.CLUSTER_HEAD:
            # Receive from members
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

            # Aggregate and send to BS
            total_sources = received + 1
            self.consume_aggregation_energy(self.packet_size * total_sources)

            dist_to_bs = self.distance_to_bs()
            self.consume_tx_energy(self.packet_size, dist_to_bs)
            self.record_packet_sent(self.packet_size, to_bs=True)

        else:
            # Member: send to CH
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
                # Direct to BS
                dist_to_bs = self.distance_to_bs()
                self.consume_tx_energy(self.packet_size, dist_to_bs)
                self.record_packet_sent(self.packet_size, to_bs=True)

            yield self.mailbox.get(0.5)

    def _run_base_station(self):
        """Base station operation - collect info and assign clusters."""
        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if self._metrics_collector:
                self._metrics_collector.start_new_round(r)

            # Collect node status
            self._collected_node_info.clear()
            collect_time = float(self.params.get("status_collect_time", 2.0))
            start = time.time()

            while time.time() - start < collect_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "STATUS" and msg.get("round") == r:
                        node_id = msg.get("sender")
                        if node_id is not None:
                            self._collected_node_info[int(node_id)] = {
                                "position": msg.get("position", [0, 0]),
                                "energy": msg.get("energy", 0),
                                "node_type": msg.get("node_type", "normal"),
                            }

            # Compute optimal clusters
            if self._collected_node_info:
                ch_ids, assignments = self._compute_optimal_clusters()

                # Broadcast assignments
                assignment_msg = {
                    "type": "CLUSTER_ASSIGNMENT",
                    "round": r,
                    "ch_ids": ch_ids,
                    "assignments": {str(k): v for k, v in assignments.items()},
                }
                self.broadcast(assignment_msg)

                # Track metrics
                if self._metrics_collector:
                    for ch_id in ch_ids:
                        members = [
                            int(nid) for nid, chid in assignments.items()
                            if int(chid) == ch_id
                        ]
                        self._metrics_collector.record_cluster_formed(ch_id, members)

            # Listen for data transmissions
            round_time = float(self.params.get("round_time", 5.0))
            packets_received = 0
            start = time.time()

            while time.time() - start < round_time:
                yield self.mailbox.get(0.5)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "DATA":
                        packets_received += 1

                    # Update node states
                    if msg.get("type") in ("energy", "round_summary") and self._metrics_collector:
                        node_id = msg.get("node_id") or msg.get("sender")
                        if node_id is not None:
                            self._metrics_collector.update_node_state(
                                node_id=int(node_id),
                                energy=msg.get("current_energy", 0),
                                is_alive=msg.get("is_alive", True),
                                role=msg.get("role", "sensor"),
                            )

            if self._metrics_collector:
                metrics = self._metrics_collector.complete_round(packets_received)
                if metrics.alive_nodes == 0:
                    break

        if self._metrics_collector:
            self._metrics_collector.emit_final_summary()

        self.emit({"type": "done", "role": "base_station"})

    def _compute_optimal_clusters(self) -> Tuple[List[int], Dict[int, int]]:
        """
        Compute optimal cluster head selection using simulated annealing.

        Returns:
            Tuple of (ch_ids, assignments)
        """
        nodes = list(self._collected_node_info.keys())
        if not nodes:
            return [], {}

        # Calculate average energy
        avg_energy = sum(
            info["energy"] for info in self._collected_node_info.values()
        ) / len(nodes)

        # Filter candidates with above-average energy
        candidates = [
            nid for nid, info in self._collected_node_info.items()
            if info["energy"] >= avg_energy
        ]

        if not candidates:
            candidates = nodes  # Fallback

        # Target number of CHs
        k = max(1, int(len(nodes) * self.p))

        # Simple selection: k nodes with highest energy, well-distributed
        ch_ids = self._select_distributed_chs(candidates, k)

        # Assign non-CH nodes to closest CH
        assignments: Dict[int, int] = {}
        for node_id in nodes:
            if node_id in ch_ids:
                assignments[node_id] = node_id
            else:
                # Find closest CH
                node_pos = self._collected_node_info[node_id].get("position", [0, 0])
                closest_ch = None
                min_dist = float('inf')

                for ch_id in ch_ids:
                    ch_pos = self._collected_node_info[ch_id].get("position", [0, 0])
                    dist = math.sqrt(
                        (node_pos[0] - ch_pos[0]) ** 2 +
                        (node_pos[1] - ch_pos[1]) ** 2
                    )
                    if dist < min_dist:
                        min_dist = dist
                        closest_ch = ch_id

                if closest_ch is not None:
                    assignments[node_id] = closest_ch

        return ch_ids, assignments

    def _select_distributed_chs(self, candidates: List[int], k: int) -> List[int]:
        """Select k well-distributed CHs from candidates."""
        if len(candidates) <= k:
            return candidates

        # Sort by energy (highest first)
        candidates.sort(
            key=lambda nid: self._collected_node_info[nid].get("energy", 0),
            reverse=True
        )

        selected: List[int] = []
        min_distance = float(self.params.get("min_ch_distance", 20.0))

        for candidate in candidates:
            if len(selected) >= k:
                break

            # Check distance to already selected CHs
            cand_pos = self._collected_node_info[candidate].get("position", [0, 0])
            too_close = False

            for sel_id in selected:
                sel_pos = self._collected_node_info[sel_id].get("position", [0, 0])
                dist = math.sqrt(
                    (cand_pos[0] - sel_pos[0]) ** 2 +
                    (cand_pos[1] - sel_pos[1]) ** 2
                )
                if dist < min_distance:
                    too_close = True
                    break

            if not too_close:
                selected.append(candidate)

        # If we didn't get enough, add remaining top candidates
        for candidate in candidates:
            if len(selected) >= k:
                break
            if candidate not in selected:
                selected.append(candidate)

        return selected

    def _reset_round_state(self):
        """Reset state for next round."""
        self._assigned_members = []
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
