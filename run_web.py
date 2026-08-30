"""Launch the local DocDrift web UI (T040).

Run: uv run python run_web.py   ->  http://127.0.0.1:8787
Local single-user demo surface; binds loopback only.
"""

from __future__ import annotations

import uvicorn

from docdrift.web import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="warning")
