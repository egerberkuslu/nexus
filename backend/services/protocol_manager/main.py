"""
Protocol Manager service entrypoint.

Implementation lives in `protocol_manager_app/app.py` so `main.py` stays small.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import shared  # noqa: F401
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protocol_manager_app.app import app  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SERVICE_PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)

