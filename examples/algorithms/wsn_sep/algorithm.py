"""
SEP Protocol Example for Caduceus Flux.

This bundle is intentionally minimal: the protocol implementation is in
`caduceus_sdk.wsn.protocols.sep.SEPNode`.
"""

from caduceus_sdk.wsn.protocols.sep import SEPNode

__all__ = ["SEPNode"]


def select_nodes(ctx):
    """
    Optional node selector function.

    Return `[]` (or `None`) to run on all nodes.
    """
    return []
