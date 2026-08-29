"""Check synthesizer (T017): one claim -> one executable pandas check.

The model's output is CODE, not an opinion (the structural beat over the
baseline). The Check contract (data-model.md): `def check(df)` returns
{"passed": bool, "computed": str, "evidence_rows": [<=5 dicts]}, and MUST
first verify every referenced column exists, returning
{"passed": False, "computed": "missing-column", "evidence_rows": []} instead
of raising — phantom-column claims score violated, never execution_error.

Source validity (compiles + defines a callable `check`) is enforced by the
pydantic reply model, so llm.call_json's retry loop repairs bad code shapes
automatically. The lessons hook (Phase 5, T026) appends accumulated pitfalls
to the system prompt.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from docdrift.config import MODEL_AGENT
from docdrift.llm import CallMeta, Transport, call_json
from docdrift.schemas import Claim

SYSTEM_PROMPT = """You write ONE self-contained pandas check function for ONE documented claim \
about a dataset.

Contract — your function is executed against the FULL data file by a harness that has already \
run `import pandas as pd` and `import numpy as np`:

def check(df):
    # returns a dict with EXACTLY these keys:
    # "passed": bool — True iff the claim holds of df
    # "computed": str — the actual measured value(s), short and human-readable
    # "evidence_rows": list of at most 5 dicts — offending rows when passed is False
    #                  (e.g. df[mask].head(5).to_dict("records")), else []

Hard rules:
1. FIRST verify every column the claim references exists in df.columns. If any is missing, \
return {"passed": False, "computed": "missing-column", "evidence_rows": []}.
2. Never raise for data-shaped reasons; compute defensively (dropna where sensible, coerce \
dtypes explicitly with pd.to_datetime / pd.to_numeric errors="coerce" when comparing).
3. Only pandas (pd), numpy (np), and the standard library — no file/network I/O, no prints.
4. Interpret the claim literally but sensibly: "no missing values" means zero nulls; a stated \
range means both min and max match the data; "roughly X%" allows the tolerance given in params.
5. Keep it under ~30 lines.

Reply with ONLY this JSON:
{"source_code": "def check(df):\\n    ..."}"""


def validate_check_source(source: str) -> None:
    """Raise ValueError unless source compiles and defines a callable check()."""
    if "def check(" not in source:
        raise ValueError("source must define check(df)")
    try:
        compiled = compile(source, "<check>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"source does not compile: {exc}") from exc
    namespace: dict = {}
    exec(compiled, namespace)  # noqa: S102 — builder-side validation of model code
    if not callable(namespace.get("check")):
        raise ValueError("source must leave a callable named check")


class SynthReply(BaseModel):
    source_code: str = Field(min_length=1)

    @field_validator("source_code")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        validate_check_source(v)
        return v


async def synthesize_check(
    claim: Claim,
    profile_text: str,
    *,
    lessons: str = "",
    feedback: str = "",
    model: str = MODEL_AGENT,
    log_path: Path | None = None,
    transport: Transport | None = None,
) -> tuple[str, CallMeta]:
    """Returns (check source, call meta). `feedback` carries a mutation-gate
    rejection diff on rewrite attempts (Phase 4)."""
    system = SYSTEM_PROMPT
    if lessons:
        system += f"\n\nAccumulated pitfalls from earlier runs — avoid repeating them:\n{lessons}"
    user = (
        f"CLAIM (type={claim.type.value}):\n{claim.quoted_span}\n\n"
        f"PARAMS: {claim.params}\n\nDATA PROFILE:\n{profile_text}"
    )
    if feedback:
        user += f"\n\nYOUR PREVIOUS CHECK WAS REJECTED:\n{feedback}\nWrite a corrected check."
    reply, meta = await call_json(SynthReply, system, user, model=model,
                                  label=f"synthesize:{claim.id}", log_path=log_path,
                                  transport=transport)
    return reply.source_code, meta
