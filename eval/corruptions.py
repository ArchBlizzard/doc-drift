"""The 8 corruption operators (T006): gold labels by construction.

Design (research R3, data-model.md GoldClaim):

Every accurate data card ships with a sidecar *manifest* listing each claim it
makes: the exact quoted sentence fragment, its ClaimType, machine-readable
params, and its base verdict (holds for checkable-true claims, unverifiable
for prose). A case applies corruption operators to either the CARD (rewrite
one claim's text so it no longer matches the data) or the DATA (mutate the
frame so a true claim becomes false). The operator knows exactly what it
changed, so it emits the violated GoldClaim itself; uncorrupted manifest
claims keep their base verdict. Spans are located by unique-substring search
in the FINAL card text, so card edits can never silently break other claims'
offsets — duplicates raise.

Operators (op name → target):
  inject_nulls        data   null_rate claim becomes violated
  add_category        data   category_set claim becomes violated
  shift_range         data   range claim becomes violated
  row_count_drift     data   row_count claim becomes violated
  stale_temporal      card   temporal_coverage text rewritten vs unchanged data
  perturb_stat        card   aggregate_stat number rewritten vs unchanged data
  phantom_column      card   inserts a schema claim about a nonexistent column
  fuzzy_coarsen       card   exact figure replaced by a wrong "roughly X%" (tests
                             the tolerance-band judgment, spec edge case)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from docdrift.schemas import ClaimType, GoldClaim, Verdict


# --- manifest --------------------------------------------------------------

class ManifestClaim(BaseModel):
    """One claim of the *accurate* card, from data_src/cards/<name>.claims.yaml."""

    id: str
    type: ClaimType
    quoted_span: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    base_verdict: Verdict  # holds (checkable, true of data_src) | unverifiable (prose)


def locate_span(card_text: str, quoted_span: str) -> tuple[int, int]:
    """Unique-substring search; the span invariant everything relies on."""
    first = card_text.find(quoted_span)
    if first < 0:
        raise ValueError(f"span not found in card: {quoted_span!r}")
    if card_text.find(quoted_span, first + 1) >= 0:
        raise ValueError(f"span not unique in card: {quoted_span!r}")
    return first, first + len(quoted_span)


# --- operator plumbing -----------------------------------------------------

@dataclass
class OpResult:
    card_text: str
    df: pd.DataFrame
    gold: GoldClaim
    # claim ids whose manifest entry this op consumed (usually one)
    consumed: list[str] = field(default_factory=list)


OpFn = Callable[[str, pd.DataFrame, ManifestClaim, np.random.Generator, dict[str, Any]], OpResult]
OP_REGISTRY: dict[str, OpFn] = {}


def _register(name: str) -> Callable[[OpFn], OpFn]:
    def deco(fn: OpFn) -> OpFn:
        OP_REGISTRY[name] = fn
        return fn
    return deco


def _violated_gold(op: str, claim: ManifestClaim, card_text: str,
                   quoted_span: str, note: str) -> GoldClaim:
    start, end = locate_span(card_text, quoted_span)
    return GoldClaim(
        id=claim.id, span_start=start, span_end=end, quoted_span=quoted_span,
        type=claim.type, gold_verdict=Verdict.violated, corruption_op=op, note=note,
    )


def _rewrite_span(card_text: str, old_span: str, new_span: str) -> str:
    start, end = locate_span(card_text, old_span)
    return card_text[:start] + new_span + card_text[end:]


# --- data-target operators -------------------------------------------------

@_register("inject_nulls")
def inject_nulls(card: str, df: pd.DataFrame, claim: ManifestClaim,
                 rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Violate a null_rate claim ('no missing values in X') by injecting nulls.

    For whole-file claims (mode zero_all, no column of their own), the target
    column comes from the op params instead.
    """
    col = params.get("column") or claim.params["column"]
    n = int(params.get("n", 3))
    df = df.copy()
    rows = rng.choice(len(df), size=n, replace=False)
    if df[col].dtype.kind in "iu":  # integer columns cannot hold None
        df[col] = df[col].astype("object")
    df.iloc[rows, df.columns.get_loc(col)] = None
    note = f"injected {n} nulls into {col!r}; card still claims none"
    return OpResult(card, df, _violated_gold("inject_nulls", claim, card, claim.quoted_span, note),
                    consumed=[claim.id])


@_register("add_category")
def add_category(card: str, df: pd.DataFrame, claim: ManifestClaim,
                 rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Violate a category_set claim by introducing an undocumented category."""
    col = claim.params["column"]
    new_value = params["new_value"]
    n = int(params.get("n", 5))
    df = df.copy()
    rows = rng.choice(len(df), size=n, replace=False)
    df[col] = df[col].astype("object")
    df.iloc[rows, df.columns.get_loc(col)] = new_value
    note = f"introduced undocumented category {new_value!r} into {col!r} ({n} rows)"
    return OpResult(card, df, _violated_gold("add_category", claim, card, claim.quoted_span, note),
                    consumed=[claim.id])


@_register("shift_range")
def shift_range(card: str, df: pd.DataFrame, claim: ManifestClaim,
                rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Violate a range claim by pushing values outside the documented bounds."""
    col = claim.params["column"]
    n = int(params.get("n", 4))
    out_value = params["out_value"]
    df = df.copy()
    rows = rng.choice(len(df), size=n, replace=False)
    df.iloc[rows, df.columns.get_loc(col)] = out_value
    note = f"set {n} values of {col!r} to {out_value!r}, outside the documented range"
    return OpResult(card, df, _violated_gold("shift_range", claim, card, claim.quoted_span, note),
                    consumed=[claim.id])


@_register("row_count_drift")
def row_count_drift(card: str, df: pd.DataFrame, claim: ManifestClaim,
                    rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Violate a row_count claim by dropping or duplicating rows."""
    mode = params.get("mode", "drop")
    n = int(params.get("n", 7))
    df = df.copy()
    if mode == "drop":
        df = df.iloc[:-n]
        note = f"dropped last {n} rows; card still states the original count"
    else:
        df = pd.concat([df, df.iloc[:n]], ignore_index=True)
        note = f"duplicated first {n} rows; card still states the original count"
    return OpResult(card, df, _violated_gold("row_count_drift", claim, card, claim.quoted_span, note),
                    consumed=[claim.id])


# --- card-target operators -------------------------------------------------

@_register("stale_temporal")
def stale_temporal(card: str, df: pd.DataFrame, claim: ManifestClaim,
                   rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Rewrite the claimed date coverage so it no longer matches the data."""
    new_span = params["new_span"]
    card = _rewrite_span(card, claim.quoted_span, new_span)
    note = f"card coverage rewritten to {new_span!r}; data unchanged"
    return OpResult(card, df, _violated_gold("stale_temporal", claim, card, new_span, note),
                    consumed=[claim.id])


@_register("perturb_stat")
def perturb_stat(card: str, df: pd.DataFrame, claim: ManifestClaim,
                 rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Rewrite a claimed aggregate figure to a wrong value."""
    new_span = params["new_span"]
    card = _rewrite_span(card, claim.quoted_span, new_span)
    note = f"claimed statistic rewritten to {new_span!r}; data unchanged"
    return OpResult(card, df, _violated_gold("perturb_stat", claim, card, new_span, note),
                    consumed=[claim.id])


@_register("phantom_column")
def phantom_column(card: str, df: pd.DataFrame, claim: ManifestClaim,
                   rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Insert a claim about a column that does not exist in the data.

    `claim` here is a template manifest entry (base_verdict is ignored); the
    sentence in params becomes a brand-new schema claim, gold = violated.
    """
    sentence = params["sentence"]
    anchor = params["anchor"]
    _, end = locate_span(card, anchor)
    card = card[:end] + " " + sentence + card[end:]
    start, stop = locate_span(card, sentence)  # uniqueness enforced
    note = f"phantom column {claim.params.get('column')!r}: sentence inserted, column absent from data"
    gold = GoldClaim(
        id=claim.id, type=ClaimType.schema, gold_verdict=Verdict.violated,
        corruption_op="phantom_column", note=note,
        quoted_span=sentence, span_start=start, span_end=stop,
    )
    return OpResult(card, df, gold, consumed=[claim.id])


@_register("fuzzy_coarsen")
def fuzzy_coarsen(card: str, df: pd.DataFrame, claim: ManifestClaim,
                  rng: np.random.Generator, params: dict[str, Any]) -> OpResult:
    """Replace an exact figure with a wrong 'roughly X%' (tolerance-band test)."""
    new_span = params["new_span"]
    true_value = params.get("true_value", "?")
    card = _rewrite_span(card, claim.quoted_span, new_span)
    note = f"coarsened to {new_span!r}; true value {true_value} is outside the ±2pp band"
    return OpResult(card, df, _violated_gold("fuzzy_coarsen", claim, card, new_span, note),
                    consumed=[claim.id])
