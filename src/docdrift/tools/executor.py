"""Sandboxed check executor (T015, research R5).

Runs one synthesized `check(df)` against the FULL dataset in a fresh Python
subprocess: temp cwd, hard timeout, capped stored output. Windows-honest
sandbox (no resource-module rlimits — cap is timeout + output size, disclosed
in the README). Checks need no network by construction.

Protocol: the harness loads the data file, calls check(df), normalizes the
result (evidence capped at 5 rows, values stringified), and prints one line
`DOCDRIFT_RESULT:<json>`. Anything else on stdout is check noise and ignored.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from docdrift.config import EVIDENCE_ROWS_MAX, EXECUTOR_STDOUT_CAP, EXECUTOR_TIMEOUT_S

MARKER = "DOCDRIFT_RESULT:"

HARNESS = """\
import json, sys
import pandas as pd
import numpy as np

def _load(path):
    return pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)

{check_source}

if __name__ == "__main__":
    df = _load(sys.argv[1])
    result = check(df)
    if not isinstance(result, dict):
        raise SystemExit("check() must return a dict")
    rows = result.get("evidence_rows") or []
    result["evidence_rows"] = [
        {{str(k): str(v) for k, v in dict(r).items()}} for r in list(rows)[:{max_rows}]
    ]
    result["computed"] = str(result.get("computed", ""))
    result["passed"] = bool(result.get("passed"))
    print("{marker}" + json.dumps(result, default=str))
"""


@dataclass
class ExecutionOutcome:
    ok: bool
    passed: bool | None = None
    computed: str = ""
    evidence_rows: list[dict] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None


def _cap(text: str) -> str:
    return text[:EXECUTOR_STDOUT_CAP]


def run_check(check_source: str, data_path: Path,
              timeout_s: int = EXECUTOR_TIMEOUT_S) -> ExecutionOutcome:
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="docdrift_exec_") as tmp:
        script = Path(tmp) / "runner.py"
        script.write_text(
            HARNESS.format(check_source=check_source, max_rows=EVIDENCE_ROWS_MAX,
                           marker=MARKER),
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(script), str(data_path)],
                capture_output=True, text=True, cwd=tmp, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecutionOutcome(ok=False, error=f"timeout after {timeout_s}s",
                                    duration_ms=int((time.monotonic() - t0) * 1000))
    duration_ms = int((time.monotonic() - t0) * 1000)

    if proc.returncode != 0:
        detail = _cap(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
        return ExecutionOutcome(ok=False, error=f"check crashed: {detail}", duration_ms=duration_ms)

    marker_line = next((line for line in proc.stdout.splitlines()
                        if line.startswith(MARKER)), None)
    if marker_line is None:
        return ExecutionOutcome(ok=False, duration_ms=duration_ms,
                                error=f"no result marker in output: {_cap(proc.stdout)!r}")
    try:
        payload = json.loads(marker_line[len(MARKER):])
    except json.JSONDecodeError as exc:
        return ExecutionOutcome(ok=False, duration_ms=duration_ms,
                                error=f"unparseable result payload: {exc}")
    return ExecutionOutcome(
        ok=True, passed=bool(payload["passed"]), computed=_cap(str(payload["computed"])),
        evidence_rows=payload.get("evidence_rows", [])[:EVIDENCE_ROWS_MAX],
        duration_ms=duration_ms,
    )
