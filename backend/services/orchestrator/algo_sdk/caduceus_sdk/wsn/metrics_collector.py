"""
WSN Metrics Collector for Network-Wide Statistics.

Collects and aggregates metrics from all WSN nodes including:
- Network lifetime metrics (FND, HND, LND)
- Energy consumption statistics
- Cluster formation metrics
- Throughput and packet delivery
- Protocol-specific metrics

This collector can run on the base station node or as a central
aggregator that processes events from all nodes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .wsn_node_base import WSNNode


@dataclass
class RoundMetrics:
    """Metrics for a single simulation round."""
    round_number: int
    alive_nodes: int = 0
    dead_nodes: int = 0
    total_energy: float = 0.0
    avg_energy: float = 0.0
    min_energy: float = float('inf')
    max_energy: float = 0.0
    energy_variance: float = 0.0
    packets_to_bs: int = 0
    cluster_count: int = 0
    ch_ids: List[int] = field(default_factory=list)
    newly_dead: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "round": self.round_number,
            "alive_nodes": self.alive_nodes,
            "dead_nodes": self.dead_nodes,
            "total_energy": self.total_energy,
            "avg_energy": self.avg_energy,
            "min_energy": self.min_energy if self.min_energy != float('inf') else 0,
            "max_energy": self.max_energy,
            "energy_variance": self.energy_variance,
            "packets_to_bs": self.packets_to_bs,
            "cluster_count": self.cluster_count,
            "ch_ids": self.ch_ids,
            "newly_dead": self.newly_dead,
        }


@dataclass
class LifetimeMetrics:
    """Network lifetime metrics."""
    fnd_round: Optional[int] = None  # First Node Dead
    hnd_round: Optional[int] = None  # Half Nodes Dead
    lnd_round: Optional[int] = None  # Last Node Dead
    stability_period: int = 0  # Rounds until FND
    total_nodes: int = 0
    total_packets_delivered: int = 0
    total_energy_consumed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fnd_round": self.fnd_round,
            "hnd_round": self.hnd_round,
            "lnd_round": self.lnd_round,
            "stability_period": self.stability_period,
            "total_nodes": self.total_nodes,
            "total_packets_delivered": self.total_packets_delivered,
            "total_energy_consumed": self.total_energy_consumed,
        }


class WSNMetricsCollector:
    """
    Collects and aggregates metrics from WSN nodes.

    Can operate in two modes:
    1. Node-local: Attached to a single node, tracks that node's metrics
    2. Network-wide: Aggregates metrics from all nodes (typically on BS)

    Attributes:
        node: The node this collector is attached to (if node-local)
        is_network_wide: Whether this is a network-wide collector
        node_states: Current state of all nodes (for network-wide mode)
        round_history: Metrics for each completed round
        lifetime: Network lifetime metrics
    """

    def __init__(
        self,
        node: Optional["WSNNode"] = None,
        total_nodes: int = 0,
        is_network_wide: bool = False
    ) -> None:
        """
        Initialize metrics collector.

        Args:
            node: WSN node this collector is attached to
            total_nodes: Total number of nodes in network (for network-wide)
            is_network_wide: Whether this is network-wide collector
        """
        self.node = node
        self.is_network_wide = is_network_wide
        self.total_nodes = total_nodes

        # Node state tracking (for network-wide mode)
        self.node_states: Dict[int, Dict[str, Any]] = {}
        self.alive_nodes: Set[int] = set()
        self.dead_nodes: Set[int] = set()

        # Round metrics history
        self.round_history: List[RoundMetrics] = []
        self.current_round: int = 0

        # Lifetime metrics
        self.lifetime = LifetimeMetrics(total_nodes=total_nodes)

        # Cumulative counters
        self._total_packets_to_bs: int = 0
        self._total_energy_consumed: float = 0.0

        # Cluster tracking
        self._current_clusters: Dict[int, List[int]] = {}  # ch_id -> member_ids

    # --- Node-Local Metrics ---

    def record_packet_sent(self, bits: int, to_bs: bool = False) -> None:
        """Record a packet transmission."""
        if to_bs:
            self._total_packets_to_bs += 1
            if self.node:
                self.node.emit({
                    "type": "metric_packet_to_bs",
                    "round": self.current_round,
                    "bits": bits,
                    "total": self._total_packets_to_bs,
                })

    def record_energy_consumed(self, energy: float, operation: str) -> None:
        """Record energy consumption."""
        self._total_energy_consumed += energy
        if self.node:
            self.node.emit({
                "type": "metric_energy",
                "round": self.current_round,
                "energy": energy,
                "operation": operation,
                "total_consumed": self._total_energy_consumed,
            })

    # --- Network-Wide Metrics ---

    def update_node_state(
        self,
        node_id: int,
        energy: float,
        is_alive: bool,
        role: str,
        cluster_id: Optional[int] = None,
        is_ch: bool = False,
        members: Optional[List[int]] = None
    ) -> None:
        """
        Update state for a node (network-wide mode).

        Args:
            node_id: Node identifier
            energy: Current energy level
            is_alive: Whether node is alive
            role: Current role
            cluster_id: Cluster this node belongs to
            is_ch: Whether node is cluster head
            members: Member IDs if node is CH
        """
        was_alive = node_id in self.alive_nodes

        self.node_states[node_id] = {
            "energy": energy,
            "is_alive": is_alive,
            "role": role,
            "cluster_id": cluster_id,
            "is_ch": is_ch,
            "members": members or [],
        }

        if is_alive:
            self.alive_nodes.add(node_id)
            self.dead_nodes.discard(node_id)
        else:
            self.alive_nodes.discard(node_id)
            self.dead_nodes.add(node_id)

            # Check for lifetime events
            if was_alive:
                self._check_lifetime_events(node_id)

        # Update cluster tracking
        if is_ch and members:
            self._current_clusters[node_id] = members

    def _check_lifetime_events(self, dead_node_id: int) -> None:
        """Check and record lifetime events (FND, HND, LND)."""
        dead_count = len(self.dead_nodes)

        # First Node Dead
        if dead_count == 1 and self.lifetime.fnd_round is None:
            self.lifetime.fnd_round = self.current_round
            self.lifetime.stability_period = self.current_round
            if self.node:
                self.node.emit({
                    "type": "fnd",
                    "round": self.current_round,
                    "dead_node_id": dead_node_id,
                })

        # Half Nodes Dead
        half_count = self.total_nodes // 2
        if dead_count >= half_count and self.lifetime.hnd_round is None:
            self.lifetime.hnd_round = self.current_round
            if self.node:
                self.node.emit({
                    "type": "hnd",
                    "round": self.current_round,
                    "dead_count": dead_count,
                })

        # Last Node Dead
        if dead_count >= self.total_nodes and self.lifetime.lnd_round is None:
            self.lifetime.lnd_round = self.current_round
            if self.node:
                self.node.emit({
                    "type": "lnd",
                    "round": self.current_round,
                })

    def complete_round(self, packets_this_round: int = 0) -> RoundMetrics:
        """
        Complete current round and calculate metrics.

        Args:
            packets_this_round: Packets delivered to BS this round

        Returns:
            Metrics for the completed round
        """
        metrics = RoundMetrics(round_number=self.current_round)

        # Count alive/dead nodes
        metrics.alive_nodes = len(self.alive_nodes)
        metrics.dead_nodes = len(self.dead_nodes)

        # Energy statistics
        energies = [
            state["energy"]
            for state in self.node_states.values()
            if state["is_alive"]
        ]

        if energies:
            metrics.total_energy = sum(energies)
            metrics.avg_energy = metrics.total_energy / len(energies)
            metrics.min_energy = min(energies)
            metrics.max_energy = max(energies)

            # Variance
            if len(energies) > 1:
                mean = metrics.avg_energy
                metrics.energy_variance = sum(
                    (e - mean) ** 2 for e in energies
                ) / len(energies)

        # Packet and cluster metrics
        metrics.packets_to_bs = packets_this_round
        self._total_packets_to_bs += packets_this_round
        self.lifetime.total_packets_delivered = self._total_packets_to_bs

        # Cluster information
        metrics.cluster_count = len(self._current_clusters)
        metrics.ch_ids = list(self._current_clusters.keys())

        # Track newly dead nodes
        if self.round_history:
            prev_dead = set()
            for state in self.round_history[-1].newly_dead:
                prev_dead.add(state)
            for nid in self.dead_nodes:
                if nid not in prev_dead:
                    metrics.newly_dead.append(nid)

        # Store in history
        self.round_history.append(metrics)
        self.current_round += 1

        # Reset cluster tracking for next round
        self._current_clusters.clear()

        # Emit round metrics
        if self.node:
            self.node.emit({
                "type": "round_metrics",
                **metrics.to_dict(),
            })

        return metrics

    def start_new_round(self, round_number: int) -> None:
        """
        Start a new round.

        Args:
            round_number: The new round number
        """
        self.current_round = round_number
        self._current_clusters.clear()

    # --- Cluster Metrics ---

    def record_cluster_formed(
        self,
        ch_id: int,
        members: List[int]
    ) -> None:
        """
        Record cluster formation.

        Args:
            ch_id: Cluster head ID
            members: List of member node IDs
        """
        self._current_clusters[ch_id] = members

        if self.node:
            self.node.emit({
                "type": "cluster_formed",
                "round": self.current_round,
                "ch_id": ch_id,
                "members": members,
                "size": len(members),
            })

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get statistics about current clusters."""
        if not self._current_clusters:
            return {
                "cluster_count": 0,
                "avg_size": 0,
                "min_size": 0,
                "max_size": 0,
                "sizes": [],
            }

        sizes = [len(members) for members in self._current_clusters.values()]
        return {
            "cluster_count": len(self._current_clusters),
            "avg_size": sum(sizes) / len(sizes) if sizes else 0,
            "min_size": min(sizes) if sizes else 0,
            "max_size": max(sizes) if sizes else 0,
            "sizes": sizes,
            "ch_ids": list(self._current_clusters.keys()),
        }

    # --- Summary and Export ---

    def get_summary(self) -> Dict[str, Any]:
        """Get complete metrics summary."""
        return {
            "lifetime": self.lifetime.to_dict(),
            "total_rounds": self.current_round,
            "total_packets_to_bs": self._total_packets_to_bs,
            "total_energy_consumed": self._total_energy_consumed,
            "final_alive_count": len(self.alive_nodes),
            "final_dead_count": len(self.dead_nodes),
            "cluster_stats": self.get_cluster_stats(),
            "round_count": len(self.round_history),
        }

    def get_round_history(
        self,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get round metrics history.

        Args:
            start_round: First round to include
            end_round: Last round to include (None for all)

        Returns:
            List of round metrics dictionaries
        """
        end = end_round if end_round is not None else len(self.round_history)
        return [
            metrics.to_dict()
            for metrics in self.round_history[start_round:end]
        ]

    def emit_final_summary(self) -> None:
        """Emit final simulation summary."""
        if self.node:
            self.node.emit({
                "type": "simulation_complete",
                "summary": self.get_summary(),
                "lifetime": self.lifetime.to_dict(),
            })

    def reset(self) -> None:
        """Reset all metrics for new simulation."""
        self.node_states.clear()
        self.alive_nodes.clear()
        self.dead_nodes.clear()
        self.round_history.clear()
        self.current_round = 0
        self._total_packets_to_bs = 0
        self._total_energy_consumed = 0.0
        self._current_clusters.clear()
        self.lifetime = LifetimeMetrics(total_nodes=self.total_nodes)
