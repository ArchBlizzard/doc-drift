"""Launch the DocDrift web UI.

Local use:  uv run python run_web.py   then open http://127.0.0.1:8787
Deployed:   set HOST=0.0.0.0 (Render sets PORT itself), and set
            DOCDRIFT_ACCESS_CODE so strangers cannot start audits.
"""

from __future__ import annotations

import os

import uvicorn

from docdrift.web import app

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    uvicorn.run(app, host=host, port=port, log_level="warning")
