"""Regenerate audit.md from existing agent ledgers (T031).

Lets the reporter upgrade apply to completed sweeps without re-running the
pipeline: reads runs/<case>/agent/{ledger.jsonl, verdicts.json}, renders the
FR-007 audit (one small model call per case for the executive summary), and
verifies the checklist before overwriting.

Run: uv run python scripts/regen_audits.py [--runs-dir runs]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docdrift.agents.reporter import audit_checklist, write_audit
from docdrift.config import RUNS_DIR
from docdrift.schemas import LedgerEntry


async def regen(agent_dir: Path) -> str:
    lines = (agent_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    entries = [LedgerEntry.model_validate_json(line) for line in lines[1:]]
    verdicts = json.loads((agent_dir / "verdicts.json").read_text(encoding="utf-8"))
    audit_path = agent_dir / "audit.md"
    await write_audit(audit_path, verdicts["case_id"], verdicts["model_id"], entries,
                      datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      log_path=agent_dir / "messages.jsonl")
    failures = audit_checklist(audit_path.read_text(encoding="utf-8"), entries)
    return f"{verdicts['case_id']}: {'OK' if not failures else 'FAILED ' + '; '.join(failures)}"


async def main_async(runs_dir: Path) -> int:
    rc = 0
    for agent_dir in sorted(runs_dir.glob("case_*/agent")):
        if not (agent_dir / "ledger.jsonl").is_file():
            continue
        line = await regen(agent_dir)
        print(line, flush=True)
        if "FAILED" in line:
            rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = parser.parse_args()
    return anyio.run(lambda: main_async(args.runs_dir))


if __name__ == "__main__":
    sys.exit(main())
