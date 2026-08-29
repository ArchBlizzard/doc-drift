"""Baseline CLIs (T011): the honest "just paste it into Claude" comparison.

`python run_baseline.py case_NN [--plus]` — ONE no-tools model call given the
data card, the column dtypes, and the first 50 rows as CSV text. `--plus`
additionally supplies full-column summary statistics and top-10 value counts
per column (the best single-prompt attempt that still fits context, FR-009).

Output: runs/<case>/<system>/verdicts.json (contracts/verdicts.schema.json),
messages.jsonl (full prompt + reply — the baseline trajectory), and meta.json
with the span-quoting compliance rate (gate G2 evidence). Span offsets are
located deterministically by exact-substring search over the card, exactly as
the agent does it — quotes that do not appear verbatim keep span=None and fall
to the scorer's flagged fuzzy path.

Exit codes: 0 ok · 2 auth (AuthError) · 3 case not found.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import anyio
import pandas as pd
from pydantic import BaseModel, Field

from docdrift.config import CASES_DIR, MODEL_AGENT, RUNS_DIR
from docdrift.llm import AuthError, Transport, call_json
from docdrift.schemas import OutputClaim, SystemOutput, Usage

SYSTEM_PROMPT = """You are auditing a dataset's documentation. You get a data card (README) and \
information about the actual data file. Identify every claim the card makes about the data and \
judge each one against the information provided.

Verdicts:
- "holds" — the claim is true of the data.
- "violated" — the claim is false.
- "unverifiable" — the claim cannot be checked against the data file (set "reason": "prose" \
for provenance/method/people statements).

Rules:
- "quoted_span" MUST be an EXACT character-for-character substring of the data card stating the \
claim. Never paraphrase, re-punctuate, or merge sentences.
- For holds/violated include "claimed" (the documented value) and "computed" (the value you \
determined from the data information provided).
- Cover every distinct claim; one output entry per claim.

Reply with ONLY this JSON:
{"claims": [{"quoted_span": "...", "verdict": "holds|violated|unverifiable", "reason": "prose", \
"claimed": "...", "computed": "..."}]}
(omit "reason" unless unverifiable; omit claimed/computed for unverifiable claims)"""


class BaselineClaim(BaseModel):
    quoted_span: str = Field(min_length=1)
    verdict: str = Field(pattern=r"^(holds|violated|unverifiable)$")
    reason: str | None = None
    claimed: str | None = None
    computed: str | None = None


class BaselineReply(BaseModel):
    claims: list[BaselineClaim]


class CaseNotFound(FileNotFoundError):
    pass


def load_case(case_id: str, cases_root: Path = CASES_DIR) -> tuple[str, pd.DataFrame]:
    case_dir = cases_root / case_id
    card_path = case_dir / "datacard.md"
    if not card_path.is_file():
        raise CaseNotFound(f"case not found: {case_dir}")
    data_path = next(case_dir.glob("data.*"))
    df = pd.read_parquet(data_path) if data_path.suffix == ".parquet" else pd.read_csv(data_path)
    return card_path.read_text(encoding="utf-8"), df


def build_user_prompt(card: str, df: pd.DataFrame, plus: bool) -> str:
    parts = [
        "DATA CARD:\n" + card,
        "COLUMN DTYPES:\n" + df.dtypes.to_string(),
        "FIRST 50 ROWS (CSV):\n" + df.head(50).to_csv(index=False),
    ]
    if plus:
        parts.append("FULL-COLUMN SUMMARY STATISTICS:\n" + df.describe(include="all").to_string())
        counts = "\n\n".join(
            f"{col}:\n{df[col].value_counts(dropna=True).head(10).to_string()}"
            for col in df.columns
        )
        parts.append("TOP 10 VALUE COUNTS PER COLUMN:\n" + counts)
    return "\n\n".join(parts)


def locate(card: str, quoted: str) -> tuple[int | None, int | None]:
    start = card.find(quoted)
    if start < 0:
        return None, None
    return start, start + len(quoted)


VALID_REASONS = {"prose", "check_failed", "execution_error"}


async def run_case(
    case_id: str,
    *,
    plus: bool = False,
    model: str = MODEL_AGENT,
    out_root: Path = RUNS_DIR,
    cases_root: Path = CASES_DIR,
    transport: Transport | None = None,
) -> Path:
    card, df = load_case(case_id, cases_root)
    system_name = "baseline_plus" if plus else "baseline"
    out_dir = out_root / case_id / system_name
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    reply, meta = await call_json(
        BaselineReply, SYSTEM_PROMPT, build_user_prompt(card, df, plus),
        model=model, label=f"{system_name}:{case_id}",
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
        case_id=case_id, system=system_name, model_id=meta.model_id, claims=claims,
        usage=Usage(input_tokens=meta.input_tokens, output_tokens=meta.output_tokens),
        wall_s=round(wall_s, 2),
    )
    (out_dir / "verdicts.json").write_text(
        output.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
    compliance = located_n / len(claims) if claims else 1.0
    (out_dir / "meta.json").write_text(json.dumps({
        "span_compliance": round(compliance, 4), "located": located_n,
        "claims": len(claims), "attempts": meta.attempts,
    }, indent=2) + "\n", encoding="utf-8")
    return out_dir / "verdicts.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--plus", action="store_true")
    parser.add_argument("--model", default=MODEL_AGENT)
    parser.add_argument("--out", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)
    try:
        path = anyio.run(lambda: run_case(args.case_id, plus=args.plus,
                                          model=args.model, out_root=args.out))
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
