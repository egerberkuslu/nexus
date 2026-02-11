"""
PEGASIS Protocol Implementation.

PEGASIS (Power-Efficient Gathering in Sensor Information Systems) is a
chain-based protocol where nodes form a chain and take turns being the
leader that transmits to the base station.

Key Features:
- Chain construction: greedy algorithm starting from farthest node to BS
- Each node communicates only with its nearest neighbor
- Leader rotation: leader = chain[round % n]
- Data flows along chain toward leader
- 100-300% improvement in network lifetime over LEACH

Algorithm:
1. Chain Construction (once):
   - Start from node farthest from BS
   - Greedily add nearest unvisited node
   - Form single chain

2. Per Round:
   - Leader selection: round-robin or weighted by energy
   - Data gathering: flows along chain toward leader
   - Leader transmits aggregated data to BS

Disadvantages:
- Higher latency due to chain transmission
- Chain reconstruction costly when nodes die

Reference:
Lindsey, S., & Raghavendra, C. S. (2002).
PEGASIS: Power-efficient gathering in sensor information systems.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..wsn_node_base import WSNNode, WSNRole, WSNNodeType
from ..metrics_collector import WSNMetricsCollector


class PEGASISNode(WSNNode):
    """
    PEGASIS protocol node implementation.

    Chain-based protocol with leader rotation.
    """

    def __init__(self, ctx: Any) -> None:
        """Initialize PEGASIS node."""
        super().__init__(ctx)

        # Chain structure
        self.chain_prev: Optional[int] = None  # Previous node in chain
        self.chain_next: Optional[int] = None  # Next node in chain
        self.chain_position: int = -1  # Position in chain (0 = start)
        self.chain_length: int = 0

        # Leader status
        self.is_leader: bool = False
        self.current_leader_id: Optional[int] = None

        # Packet parameters
        self.packet_size: int = int(self.params.get("packet_size", 4000))

        # Chain state
        self._chain_constructed: bool = False
        self._all_positions: Dict[int, Tuple[float, float]] = {}
        self._chain_order: List[int] = []

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
        """Main PEGASIS protocol execution loop."""
        yield from self._discover_neighbors()

        if self.role == WSNRole.BASE_STATION:
            yield from self._run_base_station()
            return

        # Chain construction (collaborative)
        yield from self._construct_chain()

        max_rounds = int(self.params.get("max_rounds", 2000))

        for r in range(1, max_rounds + 1):
            self.round_number = r

            if not self.is_alive:
                yield from self._notify_chain_death()
                yield self.mailbox.get(1.0)
                continue

            # Leader election (round-robin)
            yield from self._leader_election()

            # Data gathering along chain
            yield from self._chain_data_gathering()

            # Leader transmits to BS
            if self.is_leader:
                yield from self._transmit_to_bs()

            self.emit_round_summary()
            self.emit_energy_state()

        self.emit({"type": "done", "total_rounds": max_rounds})

    def _discover_neighbors(self):
        """Discover neighbors and collect positions."""
        discovery_seconds = float(self.params.get("discovery_seconds", 2.0))
        hello_interval = float(self.params.get("hello_interval", 0.5))
        start = time.time()
        next_hello = 0.0

        self._all_positions[self.id] = self.position

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
                    pos = msg.get("position")
                    if sender is not None and sender != self.id:
                        self.neighbors[int(sender)] = {
                            "position": pos,
                            "energy": msg.get("energy"),
                        }
                        if pos and len(pos) >= 2:
                            self._all_positions[int(sender)] = (float(pos[0]), float(pos[1]))

        self.emit({"type": "neighbors_discovered", "count": len(self.neighbors)})

    def _construct_chain(self):
        """
        Construct chain using greedy algorithm.

        Coordinated by node with lowest ID.
        """
        # Determine coordinator (lowest ID)
        all_ids = [self.id] + list(self.neighbors.keys())
        coordinator_id = min(all_ids)

        if self.id == coordinator_id:
            # Build chain
            chain = self._greedy_chain_construction()
            self._chain_order = chain

            # Broadcast chain assignments
            for _ in range(3):  # Multiple broadcasts for reliability
                self.broadcast({
                    "type": "CHAIN_ASSIGN",
                    "chain": chain,
                })
                yield self.mailbox.get(0.2)

            self._apply_chain_assignment(chain)
        else:
            # Wait for chain assignment
            wait_time = float(self.params.get("chain_wait_time", 3.0))
            start = time.time()

            while time.time() - start < wait_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "CHAIN_ASSIGN":
                        chain = msg.get("chain", [])
                        if chain:
                            self._chain_order = chain
                            self._apply_chain_assignment(chain)
                            self._chain_constructed = True
                            return

        self._chain_constructed = True
        self.emit({
            "type": "chain_constructed",
            "position": self.chain_position,
            "prev": self.chain_prev,
            "next": self.chain_next,
            "chain_length": self.chain_length,
        })

    def _greedy_chain_construction(self) -> List[int]:
        """
        Build chain using greedy algorithm.

        Start from node farthest from BS, greedily add nearest unvisited.
        """
        if not self._all_positions:
            return [self.id]

        # Find farthest node from BS
        max_dist = -1
        start_node = self.id

        for nid, pos in self._all_positions.items():
            dist = math.sqrt(
                (pos[0] - self.bs_position[0]) ** 2 +
                (pos[1] - self.bs_position[1]) ** 2
            )
            if dist > max_dist:
                max_dist = dist
                start_node = nid

        # Greedy chain construction
        chain = [start_node]
        remaining = set(self._all_positions.keys()) - {start_node}

        while remaining:
            last_pos = self._all_positions[chain[-1]]
            min_dist = float('inf')
            nearest = None

            for nid in remaining:
                pos = self._all_positions[nid]
                dist = math.sqrt(
                    (pos[0] - last_pos[0]) ** 2 +
                    (pos[1] - last_pos[1]) ** 2
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest = nid

            if nearest is not None:
                chain.append(nearest)
                remaining.remove(nearest)
            else:
                break

        return chain

    def _apply_chain_assignment(self, chain: List[int]) -> None:
        """Apply chain assignment to this node."""
        self.chain_length = len(chain)

        if self.id not in chain:
            self.chain_position = -1
            return

        self.chain_position = chain.index(self.id)

        # Set prev/next
        if self.chain_position > 0:
            self.chain_prev = chain[self.chain_position - 1]
        else:
            self.chain_prev = None

        if self.chain_position < len(chain) - 1:
            self.chain_next = chain[self.chain_position + 1]
        else:
            self.chain_next = None

    def _leader_election(self):
        """
        Select leader for this round.

        Simple round-robin: leader = chain[round % chain_length]
        """
        if not self._chain_order or self.chain_length == 0:
            return

        # Round-robin leader selection
        leader_idx = self.round_number % self.chain_length

        # Account for dead nodes
        alive_chain = [nid for nid in self._chain_order if self._is_node_alive(nid)]
        if not alive_chain:
            return

        leader_idx = self.round_number % len(alive_chain)
        self.current_leader_id = alive_chain[leader_idx]
        self.is_leader = (self.id == self.current_leader_id)

        if self.is_leader:
            self.set_role(WSNRole.CHAIN_LEADER)
            self.emit({
                "type": "became_leader",
                "round": self.round_number,
            })
        else:
            self.set_role(WSNRole.SENSOR)

        yield self.mailbox.get(0.1)

    def _is_node_alive(self, node_id: int) -> bool:
        """Check if a node is still alive."""
        if node_id == self.id:
            return self.is_alive
        # Assume alive unless we received death notification
        return True

    def _chain_data_gathering(self):
        """
        Data flows along chain toward leader.

        Each node receives from one side, aggregates, sends to other side.
        """
        if self.current_leader_id is None:
            return

        # Determine direction to leader
        if self._chain_order:
            try:
                my_idx = self._chain_order.index(self.id)
                leader_idx = self._chain_order.index(self.current_leader_id)
            except ValueError:
                return

            # Direction: -1 if leader is before us, +1 if after
            direction = 1 if leader_idx > my_idx else -1
        else:
            direction = 1

        # Wait for data from downstream (away from leader)
        if not self.is_leader:
            upstream = self.chain_next if direction > 0 else self.chain_prev
            downstream = self.chain_prev if direction > 0 else self.chain_next

            # Receive from downstream if we're not at end
            received_data = 0
            if downstream is not None:
                wait_time = float(self.params.get("chain_wait_time", 1.5))
                start = time.time()

                while time.time() - start < wait_time:
                    yield self.mailbox.get(0.2)
                    for msg in self._drain_mailbox():
                        if msg.get("type") == "CHAIN_DATA" and msg.get("round") == self.round_number:
                            received_data = msg.get("data_count", 0) + 1
                            self.consume_rx_energy(self.packet_size)
                            self.record_packet_received(self.packet_size)
                            break
                    if received_data > 0:
                        break

            # Aggregate and send upstream
            total_data = received_data + 1  # +1 for own data
            self.consume_aggregation_energy(self.packet_size)

            if upstream is not None:
                data_msg = {
                    "type": "CHAIN_DATA",
                    "round": self.round_number,
                    "data_count": total_data,
                }
                self._send_to_node(upstream, data_msg)

                dist = self.distance_to(upstream)
                self.consume_tx_energy(self.packet_size, dist)
                self.record_packet_sent(self.packet_size)

        else:
            # Leader: receive from both ends
            received_from_prev = 0
            received_from_next = 0
            wait_time = float(self.params.get("leader_wait_time", 2.0))
            start = time.time()

            while time.time() - start < wait_time:
                yield self.mailbox.get(0.2)
                for msg in self._drain_mailbox():
                    if msg.get("type") == "CHAIN_DATA" and msg.get("round") == self.round_number:
                        sender = msg.get("sender")
                        count = msg.get("data_count", 1)

                        if sender == self.chain_prev:
                            received_from_prev = count
                        elif sender == self.chain_next:
                            received_from_next = count

                        self.consume_rx_energy(self.packet_size)
                        self.record_packet_received(self.packet_size)

        yield self.mailbox.get(0.3)

    def _transmit_to_bs(self):
        """Leader transmits aggregated data to base station."""
        # Aggregate all data
        self.consume_aggregation_energy(self.packet_size * self.chain_length)

        # Transmit to BS
        dist_to_bs = self.distance_to_bs()
        self.consume_tx_energy(self.packet_size, dist_to_bs)
        self.record_packet_sent(self.packet_size, to_bs=True)

        self.emit({
            "type": "leader_transmission",
            "round": self.round_number,
            "distance_to_bs": dist_to_bs,
            "aggregated_nodes": self.chain_length,
        })

        yield self.mailbox.get(0.2)

    def _notify_chain_death(self):
        """Notify neighbors that this node has died."""
        death_msg = {
            "type": "CHAIN_DEATH",
            "dead_node": self.id,
            "chain_position": self.chain_position,
        }
        self.broadcast(death_msg)
        yield self.mailbox.get(0.1)

    def _send_to_node(self, node_id: int, msg: Dict[str, Any]) -> None:
        """Send message to specific node."""
        node_info = self.neighbors.get(int(node_id))
        if node_info:
            ip = node_info.get("ip")
            port = node_info.get("port", self.ctx.listen_port)
            if ip:
                self.sendToAddr(ip, port, msg)
                return
        msg["target"] = node_id
        self.broadcast(msg)

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
                    if msg.get("type") == "leader_transmission":
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

            if self._metrics_collector:
                metrics = self._metrics_collector.complete_round(packets_received)
                if metrics.alive_nodes == 0:
                    break

        if self._metrics_collector:
            self._metrics_collector.emit_final_summary()

        self.emit({"type": "done", "role": "base_station"})

    def _drain_mailbox(self) -> List[Dict[str, Any]]:
        """Drain all messages from mailbox."""
        messages = []
        while True:
            msg = self.receiveMessage()
            if msg is None:
                break
            messages.append(msg)
        return messages
