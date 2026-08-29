"""Claim extractor (T016): data card -> typed claims with exact spans.

Context discipline (FR-006): sees only the card and the profile snapshot.
Quotes that fail exact-substring location get ONE repair pass listing the bad
quotes; still-unlocatable claims are dropped with a warning (they would be
unscorable anyway). Zero-claim cards are a valid outcome (spec edge case).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from docdrift.config import MODEL_AGENT
from docdrift.llm import CallMeta, Transport, call_json
from docdrift.schemas import Claim, ClaimType

SYSTEM_PROMPT = """You extract the claims a dataset's data card (README) makes about the data \
file, as typed, machine-checkable claims.

Claim types:
- schema: a column exists / has a property of its shape or encoding
- row_count: how many rows the file has
- range: a column's minimum/maximum bounds
- null_rate: missing values (none / a count / a percentage / a sentinel encoding)
- category_set: which distinct values or how many distinct values a column has
- aggregate_stat: a stated statistic (mean, minimum, maximum, share, ...)
- temporal_coverage: the date/time span the data covers
- prose_unverifiable: provenance, collection method, people, purpose — anything that cannot be \
checked against the data file itself

Rules:
- "quoted_span" MUST be an EXACT character-for-character substring of the card that states the \
claim. Never paraphrase, re-punctuate, merge sentences, or fix typos.
- One entry per distinct assertion; a sentence can contain several claims.
- "params" carries machine-readable details; ALWAYS include "column" when the claim concerns one \
column (use the actual column name from the profile when the card names it differently).
- Extract EVERY claim, including ones you suspect are false — judging comes later.

Reply with ONLY this JSON:
{"claims": [{"type": "...", "quoted_span": "...", "params": {...}}]}"""


class ExtractedClaim(BaseModel):
    type: ClaimType
    quoted_span: str = Field(min_length=1)
    params: dict = Field(default_factory=dict)


class ExtractorReply(BaseModel):
    claims: list[ExtractedClaim]


def _locate_first(card: str, quoted: str) -> tuple[int, int] | None:
    start = card.find(quoted)
    if start < 0:
        return None
    return start, start + len(quoted)


async def extract_claims(
    case_id: str,
    card: str,
    profile_text: str,
    *,
    model: str = MODEL_AGENT,
    log_path: Path | None = None,
    transport: Transport | None = None,
) -> tuple[list[Claim], list[CallMeta], list[str]]:
    """Returns (claims in span order, call metas, warnings)."""
    user = f"DATA CARD:\n{card}\n\nDATA PROFILE:\n{profile_text}"
    reply, meta = await call_json(ExtractorReply, SYSTEM_PROMPT, user, model=model,
                                  label=f"extract:{case_id}", log_path=log_path,
                                  transport=transport)
    metas = [meta]
    warnings: list[str] = []

    located: list[tuple[ExtractedClaim, tuple[int, int]]] = []
    bad: list[ExtractedClaim] = []
    for ec in reply.claims:
        span = _locate_first(card, ec.quoted_span)
        (located if span else bad).append((ec, span) if span else ec)

    if bad:
        repair_user = (
            f"{user}\n\nThese quoted_span values were NOT exact substrings of the card:\n"
            + "\n".join(f"- {ec.quoted_span!r}" for ec in bad)
            + "\n\nRe-emit ONLY these claims with quoted_span copied character-for-character "
              "from the card. Same JSON shape."
        )
        repaired, meta2 = await call_json(ExtractorReply, SYSTEM_PROMPT, repair_user,
                                          model=model, label=f"extract-repair:{case_id}",
                                          log_path=log_path, transport=transport)
        metas.append(meta2)
        for ec in repaired.claims:
            span = _locate_first(card, ec.quoted_span)
            if span:
                located.append((ec, span))
            else:
                warnings.append(f"dropped unlocatable claim quote: {ec.quoted_span!r}")

    # de-duplicate identical spans (repair pass may re-emit an already-good claim)
    seen: set[tuple[int, int]] = set()
    unique = []
    for ec, span in located:
        if span in seen:
            continue
        seen.add(span)
        unique.append((ec, span))

    unique.sort(key=lambda pair: pair[1][0])
    claims = [
        Claim(id=f"{case_id}-c{i + 1:02d}", case_id=case_id, type=ec.type,
              quoted_span=ec.quoted_span, span_start=span[0], span_end=span[1],
              params=ec.params)
        for i, (ec, span) in enumerate(unique)
    ]
    if not claims:
        warnings.append("card yielded zero extractable claims")
    return claims, metas, warnings
