"""
PEGASIS Protocol Example for Caduceus Flux.

This bundle is intentionally minimal: the protocol implementation is in
`caduceus_sdk.wsn.protocols.pegasis.PEGASISNode`.
"""

from caduceus_sdk.wsn.protocols.pegasis import PEGASISNode

__all__ = ["PEGASISNode"]


def select_nodes(ctx):
    """
    Optional node selector function.

    Return `[]` (or `None`) to run on all nodes.
    """
    return []
