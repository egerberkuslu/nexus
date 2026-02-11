"""
TEEN Protocol Example for Caduceus Flux.

This bundle is intentionally minimal: the protocol implementation is in
`caduceus_sdk.wsn.protocols.teen.TEENNode`.
"""

from caduceus_sdk.wsn.protocols.teen import TEENNode

__all__ = ["TEENNode"]


def select_nodes(ctx):
    """
    Optional node selector function.

    Return `[]` (or `None`) to run on all nodes.
    """
    return []
