"""
Metrics Collector service entrypoint.

Implementation lives in `metrics_collector_app/app.py` so `main.py` stays small.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import shared  # noqa: F401
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metrics_collector_app.app import SERVICE_PORT, app  # noqa: E402,F401


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("SERVICE_PORT", str(SERVICE_PORT))))

