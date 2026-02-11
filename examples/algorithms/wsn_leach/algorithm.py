"""
LEACH Protocol Example for Caduceus Flux.

This file imports and re-exports the LEACH protocol implementation
from the WSN module for use as a standalone algorithm bundle.

Usage:
1. Deploy this algorithm bundle to the emulation
2. Configure nodes with positions, initial energy, etc.
3. One node should be designated as base_station
4. Run the simulation and observe metrics

Parameters (via manifest or params):
- p: Cluster head probability (default: 0.05)
- max_rounds: Maximum simulation rounds (default: 2000)
- packet_size: Data packet size in bits (default: 4000)
- initial_energy: Initial energy per node in Joules (default: 0.5)
- discovery_seconds: Neighbor discovery duration (default: 2.0)
- adv_listen_time: Time to listen for CH advertisements (default: 1.5)
- join_listen_time: Time for CH to collect join requests (default: 1.0)
- frame_time: Data transmission frame duration (default: 2.0)

Events Emitted:
- neighbors_discovered: After neighbor discovery phase
- became_ch: When node becomes cluster head
- joined_cluster: When node joins a cluster
- cluster_formed: When CH completes cluster formation
- ch_transmission: When CH transmits to BS
- member_transmission: When member transmits to CH
- round_summary: End of each round summary
- energy: Energy state updates
- node_death: When a node dies
- fnd/hnd/lnd: Network lifetime events (from BS)
- done: Simulation complete
"""

# Import the LEACH node implementation
from caduceus_sdk.wsn.protocols.leach import LEACHNode

# Re-export for the algo_sdk to find
__all__ = ["LEACHNode"]


def select_nodes(ctx):
    """
    Optional node selector function.

    Can be used to select a subset of nodes to run the algorithm on.
    By default, runs on all nodes.

    Args:
        ctx: Topology context with nodes, links, params, mapping

    Returns:
        List of node IDs or algo IDs to run the algorithm on.
        Empty list means run on all nodes.
    """
    # Run on all nodes by default
    return []
