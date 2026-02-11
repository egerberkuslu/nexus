"""
LEACH-C Protocol Example for Caduceus Flux.

This bundle is intentionally thin: the actual protocol logic lives inside
`caduceus_sdk.wsn.protocols.leach_c.LEACHCNode`.

The orchestrator loads this file, finds the exported Node class, and runs one
agent process per selected node.
"""

from caduceus_sdk.wsn.protocols.leach_c import LEACHCNode

__all__ = ["LEACHCNode"]


def select_nodes(ctx):
    """
    Optional node selector function.

    Return `[]` (or `None`) to run on all nodes.
    """
    return []
