"""DocDrift agent CLI (T019), per contracts/cli-contracts.md.

`python run_agent.py case_NN [--fresh] [--model sonnet] [--out DIR]`
Outputs: runs/<case>/agent/{verdicts.json, ledger.jsonl, messages.jsonl, audit.md}.
Resume is the default; `--fresh` discards the ledger and extraction cache.
Exit codes: 0 ok · 2 auth · 3 case not found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anyio

from docdrift import orchestrator
from docdrift.config import MODEL_AGENT, RUNS_DIR
from docdrift.llm import AuthError


def run_case_sync(case_id: str, *, out_root: Path = RUNS_DIR,
                  model: str = MODEL_AGENT, fresh: bool = False) -> Path:
    return anyio.run(lambda: orchestrator.run_case(
        case_id, model=model, fresh=fresh, out_root=out_root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--fresh", action="store_true",
                        help="discard the ledger and re-run every claim")
    parser.add_argument("--model", default=MODEL_AGENT)
    parser.add_argument("--out", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)
    try:
        path = run_case_sync(args.case_id, out_root=args.out,
                             model=args.model, fresh=args.fresh)
    except orchestrator.CaseNotFound as exc:
        print(exc, file=sys.stderr)
        return 3
    except AuthError as exc:
        print(f"auth/configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
