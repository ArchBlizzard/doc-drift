"""REMOVED-EXPERIMENT runner (T028): stratified-sample context stuffing.

The "maybe we don't need code execution" test: one no-tools model call given
the card, dtypes, and three seeded random samples drawn from the head, middle,
and tail thirds of the file — the strongest sampling-based single prompt we
could fit in context. Kept runnable so judges can reproduce the removed
experiment's numbers (`eval/run_all.py --systems baseline_stratified`).

Note vs the original sketch (PLAN §6): 3×2,000 rows blew the context budget on
wide tables, so the shipped variant uses 3×600 rows — disclosed in
results/removed_stratified.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import anyio
import numpy as np
import pandas as pd

from docdrift.config import CASES_DIR, MASTER_SEED, MODEL_AGENT, RUNS_DIR
from docdrift.llm import AuthError, Transport, call_json
from docdrift.schemas import OutputClaim, SystemOutput, Usage
from run_baseline import (
    VALID_REASONS,
    BaselineReply,
    CaseNotFound,
    SYSTEM_PROMPT,
    load_case,
    locate,
)

STRATUM_ROWS = 600
SYSTEM_NAME = "baseline_stratified"


def build_stratified_prompt(card: str, df: pd.DataFrame) -> str:
    rng = np.random.default_rng(MASTER_SEED)
    n = len(df)
    parts = ["DATA CARD:\n" + card, "COLUMN DTYPES:\n" + df.dtypes.to_string()]
    bounds = [(0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n)]
    for lo, hi in bounds:
        size = min(STRATUM_ROWS, hi - lo)
        idx = np.sort(lo + rng.choice(hi - lo, size=size, replace=False))
        parts.append(f"RANDOM SAMPLE OF {size} ROWS FROM ROWS {lo}-{hi - 1} (CSV):\n"
                     + df.iloc[idx].to_csv(index=False))
    return "\n\n".join(parts)


async def run_case(case_id: str, *, model: str = MODEL_AGENT,
                   out_root: Path = RUNS_DIR, cases_root: Path = CASES_DIR,
                   transport: Transport | None = None) -> Path:
    card, df = load_case(case_id, cases_root)
    out_dir = out_root / case_id / SYSTEM_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    reply, meta = await call_json(
        BaselineReply, SYSTEM_PROMPT, build_stratified_prompt(card, df),
        model=model, label=f"{SYSTEM_NAME}:{case_id}",
        log_path=out_dir / "messages.jsonl", transport=transport,
    )
    wall_s = time.monotonic() - t0

    claims: list[OutputClaim] = []
    located_n = 0
    for c in reply.claims:
        start, end = locate(card, c.quoted_span)
        if start is not None:
            located_n += 1
        reason = c.reason if (c.verdict == "unverifiable") else None
        if c.verdict == "unverifiable" and reason not in VALID_REASONS:
            reason = "prose"
        claims.append(OutputClaim(
            quoted_span=c.quoted_span, span_start=start, span_end=end,
            verdict=c.verdict, reason=reason,
            claimed=c.claimed if c.verdict != "unverifiable" else None,
            computed=c.computed if c.verdict != "unverifiable" else None,
        ))

    output = SystemOutput(
        case_id=case_id, system=SYSTEM_NAME, model_id=meta.model_id, claims=claims,
        usage=Usage(input_tokens=meta.input_tokens, output_tokens=meta.output_tokens),
        wall_s=round(wall_s, 2),
    )
    (out_dir / "verdicts.json").write_text(
        output.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps({
        "span_compliance": round(located_n / len(claims), 4) if claims else 1.0,
        "located": located_n, "claims": len(claims), "attempts": meta.attempts,
        "stratum_rows": STRATUM_ROWS,
    }, indent=2) + "\n", encoding="utf-8")
    return out_dir / "verdicts.json"


def run_case_sync(case_id: str, *, out_root: Path = RUNS_DIR) -> Path:
    return anyio.run(lambda: run_case(case_id, out_root=out_root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--out", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)
    try:
        path = run_case_sync(args.case_id, out_root=args.out)
    except CaseNotFound as exc:
        print(exc, file=sys.stderr)
        return 3
    except AuthError as exc:
        print(f"auth/configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
