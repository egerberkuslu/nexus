"""
MCP Tool Hub Service entrypoint.

Implementation lives in `mcp_tool_hub_app/app.py` so `main.py` stays small.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import shared  # noqa: F401
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp_tool_hub_app.app import app  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SERVICE_PORT", "8018"))
    uvicorn.run(app, host="0.0.0.0", port=port)
