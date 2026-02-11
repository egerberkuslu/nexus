"""
Orchestrator service entrypoint.

Keep this file intentionally small: the implementation lives in `orchestrator_app/`.
This makes the service easier to navigate and maintain.
"""

from __future__ import annotations

import os
import sys

# Ensure `backend/` is on the path so `shared/*` imports work when running locally.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Import the FastAPI app and re-export a few helpers used by other modules.
from orchestrator_app.app import (  # noqa: E402
    SERVICE_PORT,
    app,
    add_device_to_emulation,
    add_link_to_emulation,
    remove_device_from_emulation,
    remove_link_from_emulation,
    sync_device_to_emulation,
    sync_link_to_emulation,
)

__all__ = [
    "SERVICE_PORT",
    "app",
    "add_device_to_emulation",
    "add_link_to_emulation",
    "remove_device_from_emulation",
    "remove_link_from_emulation",
    "sync_device_to_emulation",
    "sync_link_to_emulation",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)

