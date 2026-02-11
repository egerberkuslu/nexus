"""
MCP Proxy Service entrypoint.

Implementation lives in `mcp_proxy_app/app.py` so `main.py` stays small.
"""

from __future__ import annotations

import os

from mcp_proxy_app.app import app  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SERVICE_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
