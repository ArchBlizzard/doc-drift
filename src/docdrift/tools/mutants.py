"""Mutation-gate fixtures (T021) — verification of the verifier.

For one claim, build two tiny DataFrames sharing the real data's schema:
a CLEAN fixture that satisfies the claim and a MUTANT that violates it. A
synthesized check earns trust only by passing the clean fixture AND failing
the mutant (Constitution III / FR-005); a check that passes its mutant is
vacuous — "green because it cannot fail".

Fixtures are pure, deterministic Python built from the claim's typed params
(extractor contract) with the real DataFrame as the schema/dtype donor, so
column-existence guards in checks see the true schema. Claims whose params
cannot support fixture construction raise FixtureError — an ungateable claim
is never trusted (it abstains as check_failed) and is counted in the stats.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from docdrift.schemas import Claim, ClaimType, GateOutcome
from docdrift.tools.executor import run_check

FIXTURE_ROWS = 20
SHARE_FIXTURE_ROWS = 200  # 0.5pp granularity for percentage claims


class FixtureError(ValueError):
    """Claim params cannot support deterministic fixture construction."""


@dataclass
class FixturePair:
    clean: pd.DataFrame
    mutant: pd.DataFrame
    mutant_desc: str


def _base(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(df) == 0:
        raise FixtureError("source data is empty")
    return df.iloc[np.arange(n) % len(df)].reset_index(drop=True).copy()


def _need(claim: Claim, *keys: str) -> list:
    missing = [k for k in keys if k not in claim.params]
    if missing:
        raise FixtureError(f"{claim.type.value} claim lacks params {missing}")
    return [claim.params[k] for k in keys]


def _col(claim: Claim, df: pd.DataFrame) -> str:
    (col,) = _need(claim, "column")
    if col not in df.columns and claim.type is not ClaimType.schema:
        raise FixtureError(f"param column {col!r} not in data")
    return col


def _nullable(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df[col].dtype.kind in "iu":
        df[col] = df[col].astype("float64")
    return df


def _fill_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    s = df[col]
    if s.isna().any():
        non_null = s.dropna()
        filler = non_null.iloc[0] if len(non_null) else (0 if s.dtype.kind in "iuf" else "x")
        df[col] = s.fillna(filler)
    return df


# --- per-type builders ------------------------------------------------------

def _row_count(df: pd.DataFrame, claim: Claim) -> FixturePair:
    (expected,) = _need(claim, "expected")
    expected = int(expected)
    if not 0 < expected <= 2_000_000:
        raise FixtureError(f"unbuildable expected row count {expected}")
    clean = _base(df, expected)
    mutant = _base(df, expected + 7)
    return FixturePair(clean, mutant, f"mutant has {expected + 7} rows, claim states {expected}")


def _range(df: pd.DataFrame, claim: Claim) -> FixturePair:
    col = _col(claim, df)
    lo, hi = (float(v) for v in _need(claim, "min", "max"))
    clean = _base(df, FIXTURE_ROWS)
    values = np.linspace(lo, hi, FIXTURE_ROWS)
    if df[col].dtype.kind in "iu" and float(lo).is_integer() and float(hi).is_integer():
        values = np.round(values).astype("int64")
        values[0], values[-1] = int(lo), int(hi)
        delta = max(1, int(abs(hi) * 0.1))
    else:
        values[0], values[-1] = lo, hi
        delta = max(1.0, abs(hi) * 0.1)
        clean[col] = clean[col].astype("float64")
    clean[col] = values
    mutant = clean.copy()
    mutant.iloc[7, mutant.columns.get_loc(col)] = hi + delta
    return FixturePair(clean, mutant, f"mutant contains {col}={hi + delta}, outside [{lo}, {hi}]")


def _null_rate(df: pd.DataFrame, claim: Claim) -> FixturePair:
    mode = claim.params.get("mode", "zero")
    if mode == "zero_all":
        clean = _base(df, FIXTURE_ROWS)
        for c in clean.columns:
            _fill_col(clean, c)
        mutant = clean.copy()
        target = claim.params.get("column") or clean.columns[0]
        _nullable(mutant, target)
        mutant.iloc[[2, 5, 9], mutant.columns.get_loc(target)] = None
        return FixturePair(clean, mutant, f"mutant has 3 empty cells in {target!r}")
    col = _col(claim, df)
    if mode in ("zero", "none"):
        clean = _fill_col(_base(df, FIXTURE_ROWS), col)
        mutant = _nullable(clean.copy(), col)
        mutant.iloc[[2, 5, 9], mutant.columns.get_loc(col)] = None
        return FixturePair(clean, mutant, f"mutant has 3 nulls in {col!r}, claim says none")
    if mode == "count":
        (value,) = _need(claim, "value")
        value = int(value)
        n = max(FIXTURE_ROWS, value + 9)
        clean = _nullable(_fill_col(_base(df, n), col), col)
        loc = clean.columns.get_loc(col)
        clean.iloc[:value, loc] = None
        mutant = clean.copy()
        mutant.iloc[value:value + 3, mutant.columns.get_loc(col)] = None
        return FixturePair(clean, mutant,
                           f"mutant has {value + 3} nulls in {col!r}, claim states {value}")
    if mode == "pct":
        (value,) = _need(claim, "value")
        tol = float(claim.params.get("tolerance_pp", claim.params.get("tol_pp", 2)))
        k_clean = round(float(value) * SHARE_FIXTURE_ROWS / 100)
        k_mut = round((float(value) + tol + 5) * SHARE_FIXTURE_ROWS / 100)
        clean = _nullable(_fill_col(_base(df, SHARE_FIXTURE_ROWS), col), col)
        loc = clean.columns.get_loc(col)
        clean.iloc[:k_clean, loc] = None
        mutant = _nullable(_fill_col(_base(df, SHARE_FIXTURE_ROWS), col), col)
        mutant.iloc[:k_mut, mutant.columns.get_loc(col)] = None
        return FixturePair(clean, mutant,
                           f"mutant null rate {k_mut / 2:.1f}%, claim ~{value}% (±{tol}pp)")
    if mode == "sentinel":
        (sentinel,) = _need(claim, "sentinel")
        clean = _fill_col(_base(df, FIXTURE_ROWS), col)
        clean.iloc[0, clean.columns.get_loc(col)] = sentinel
        mutant = _nullable(clean.copy(), col)
        mutant.iloc[[3, 8], mutant.columns.get_loc(col)] = None
        return FixturePair(clean, mutant, "mutant leaves cells blank instead of the sentinel")
    raise FixtureError(f"unknown null_rate mode {mode!r}")


def _category_set(df: pd.DataFrame, claim: Claim) -> FixturePair:
    col = _col(claim, df)
    numeric = df[col].dtype.kind in "iuf"
    if "values" in claim.params:
        values = list(claim.params["values"])
        if not values:
            raise FixtureError("empty category values")
        clean = _base(df, FIXTURE_ROWS)
        if not numeric:
            clean[col] = clean[col].astype("object")
        clean[col] = [values[i % len(values)] for i in range(FIXTURE_ROWS)]
        mutant = clean.copy()
        undocumented = (max(float(v) for v in values) + 1000) if numeric else "UNDOCUMENTED_MUTANT"
        mutant.iloc[5, mutant.columns.get_loc(col)] = undocumented
        return FixturePair(clean, mutant, f"mutant adds undocumented value {undocumented!r} to {col!r}")
    if "count" in claim.params:
        count = int(claim.params["count"])
        uniq = list(df[col].dropna().unique())
        if len(uniq) < count:
            uniq += ([max(map(float, uniq or [0])) + i + 1 for i in range(count - len(uniq))]
                     if numeric else [f"synthetic_{i}" for i in range(count - len(uniq))])
        pool = uniq[:count]
        clean = _base(df, max(FIXTURE_ROWS, count))
        if not numeric:
            clean[col] = clean[col].astype("object")
        clean[col] = [pool[i % count] for i in range(len(clean))]
        mutant = clean.copy()
        extra = (max(map(float, pool)) + 999) if numeric else "EXTRA_DISTINCT_MUTANT"
        mutant.iloc[3, mutant.columns.get_loc(col)] = extra
        return FixturePair(clean, mutant,
                           f"mutant has {count + 1} distinct values in {col!r}, claim states {count}")
    raise FixtureError("category_set claim lacks values/count param")


def _exact_mean_ints(value: float, n: int) -> np.ndarray:
    total = round(value * n)
    base = total // n
    rem = total - base * n
    return np.array([base + 1] * rem + [base] * (n - rem), dtype="int64")


def _aggregate_stat(df: pd.DataFrame, claim: Claim) -> FixturePair:
    stat = claim.params.get("stat")
    if stat == "pair_share":
        col, cond_col, cond_val, value = _need(
            claim, "column", "condition_column", "condition_value", "value")
        tol = float(claim.params.get("tolerance_pp", claim.params.get("tol_pp", 2)))
        n = SHARE_FIXTURE_ROWS

        def build(k: int) -> pd.DataFrame:
            fx = _base(df, n)
            fx[col] = fx[col].astype("object")
            fx[cond_col] = fx[cond_col].astype("object")
            fx.loc[:, col] = None
            fx.loc[:, cond_col] = "other_channel"
            fx.iloc[:k, fx.columns.get_loc(col)] = "TOKEN"
            fx.iloc[:k, fx.columns.get_loc(cond_col)] = cond_val
            return fx

        k_clean = round(float(value) * n / 100)
        k_mut = round((float(value) + tol + 5) * n / 100)
        return FixturePair(build(k_clean), build(k_mut),
                           f"mutant pair share {k_mut / 2:.1f}%, claim ~{value}% (±{tol}pp)")

    col = _col(claim, df)
    value = float(_need(claim, "value")[0])
    if stat not in ("mean", "min", "max"):
        raise FixtureError(f"unbuildable aggregate stat {stat!r}")
    clean = _base(df, FIXTURE_ROWS)
    int_col = df[col].dtype.kind in "iu"
    if stat == "mean":
        clean[col] = (_exact_mean_ints(value, FIXTURE_ROWS) if int_col
                      else np.full(FIXTURE_ROWS, value))
    elif stat == "min":
        spread = np.abs(np.arange(FIXTURE_ROWS, dtype="float64"))
        clean[col] = value + spread
        clean[col] = clean[col].astype("int64") if int_col and value.is_integer() else clean[col]
    else:  # max
        spread = np.abs(np.arange(FIXTURE_ROWS, dtype="float64"))
        clean[col] = value - spread
        clean[col] = clean[col].astype("int64") if int_col and value.is_integer() else clean[col]
    delta = max(1.0, abs(value) * 0.1)
    mutant = clean.copy()
    if int_col:
        mutant[col] = mutant[col] + int(np.ceil(delta))
    else:
        mutant[col] = mutant[col].astype("float64") + delta
    return FixturePair(clean, mutant, f"mutant shifts {col!r} by {delta}, {stat} no longer {value}")


def _temporal(df: pd.DataFrame, claim: Claim) -> FixturePair:
    col = _col(claim, df)
    clean = _base(df, FIXTURE_ROWS)
    if "min_year" in claim.params:
        lo, hi = int(claim.params["min_year"]), int(claim.params["max_year"])
        years = np.linspace(lo, hi, FIXTURE_ROWS).round().astype("int64")
        years[0], years[-1] = lo, hi
        clean[col] = years
        mutant = clean.copy()
        mutant.iloc[3, mutant.columns.get_loc(col)] = hi + 3
        return FixturePair(clean, mutant, f"mutant contains year {hi + 3}, outside {lo}-{hi}")
    lo_s, hi_s = _need(claim, "min_date", "max_date")
    lo, hi = pd.Timestamp(lo_s), pd.Timestamp(hi_s)
    clean[col] = pd.date_range(lo, hi, periods=FIXTURE_ROWS)
    mutant = clean.copy()
    mutant[col] = mutant[col].astype("datetime64[ns]")
    mutant.iloc[3, mutant.columns.get_loc(col)] = (lo - pd.Timedelta(days=30)).to_datetime64()
    return FixturePair(clean, mutant,
                       f"mutant contains a date 30 days before {lo_s}, outside the claimed span")


def _schema(df: pd.DataFrame, claim: Claim) -> FixturePair:
    (col,) = _need(claim, "column")
    if "regex" in claim.params:
        pattern = claim.params["regex"]
        if col not in df.columns:
            raise FixtureError(f"regex claim on missing column {col!r}")
        matching = [v for v in df[col].dropna().astype(str).head(500) if re.fullmatch(pattern, v)]
        if not matching:
            raise FixtureError(f"no real values of {col!r} match {pattern!r} to seed the clean fixture")
        bad = "ZZ_NO_MATCH_999"
        if re.fullmatch(pattern, bad):
            raise FixtureError(f"cannot construct a non-matching mutant for {pattern!r}")
        clean = _base(df, FIXTURE_ROWS)
        clean[col] = [matching[i % len(matching)] for i in range(FIXTURE_ROWS)]
        mutant = clean.copy()
        mutant.iloc[4, mutant.columns.get_loc(col)] = bad
        return FixturePair(clean, mutant, f"mutant contains {bad!r}, violating pattern {pattern!r}")
    if claim.params.get("sorted") or "sorted_by" in claim.params:
        sort_col = claim.params.get("sorted_by", col)
        if sort_col not in df.columns:
            raise FixtureError(f"sortedness claim on missing column {sort_col!r}")
        clean = _base(df, FIXTURE_ROWS).sort_values(sort_col).reset_index(drop=True)
        if clean[sort_col].nunique() < 2:
            raise FixtureError(f"cannot build unsorted mutant: {sort_col!r} has <2 distinct values")
        mutant = clean.copy()
        lo_pos = int(mutant[sort_col].values.argmin())
        hi_pos = int(mutant[sort_col].values.argmax())
        mutant.iloc[[lo_pos, hi_pos]] = mutant.iloc[[hi_pos, lo_pos]].values
        return FixturePair(clean, mutant, f"mutant swaps two rows so {sort_col!r} is not sorted")
    # default: existence claim (covers phantom columns). The clean fixture's
    # values are unique and non-null so sentences like "gives each row a
    # unique identifier" / "always populated" are satisfied too — a constant
    # filler made legitimate checks fail the clean fixture (v2 finding,
    # CHANGELOG v3).
    clean = _base(df, FIXTURE_ROWS)
    if col not in clean.columns:
        clean[col] = np.arange(1, len(clean) + 1)
    mutant = clean.drop(columns=[col])
    return FixturePair(clean, mutant, f"mutant is missing the {col!r} column entirely")


BUILDERS = {
    ClaimType.row_count: _row_count,
    ClaimType.range: _range,
    ClaimType.null_rate: _null_rate,
    ClaimType.category_set: _category_set,
    ClaimType.aggregate_stat: _aggregate_stat,
    ClaimType.temporal_coverage: _temporal,
    ClaimType.schema: _schema,
}


def build_fixtures(df: pd.DataFrame, claim: Claim) -> FixturePair:
    builder = BUILDERS.get(claim.type)
    if builder is None:
        raise FixtureError(f"no fixture builder for claim type {claim.type.value}")
    return builder(df, claim)


# --- the gate itself --------------------------------------------------------

@dataclass
class GateResult:
    outcome: GateOutcome
    clean_passed: bool
    mutant_failed: bool
    mutant_desc: str
    detail: str


def gate_check(check_source: str, df: pd.DataFrame, claim: Claim,
               timeout_s: int = 60) -> GateResult:
    """Run one check against the claim's clean and mutant fixtures.

    gate_passed  — passed clean AND failed mutant: the check discriminates.
    vacuous      — passed the mutant: green-because-it-cannot-fail.
    error        — crashed on a fixture, or failed the clean fixture
                   (over-strict/inverted). Both trigger a rewrite.
    Raises FixtureError when the claim's params cannot support fixtures.
    """
    pair = build_fixtures(df, claim)
    with tempfile.TemporaryDirectory(prefix="docdrift_gate_") as tmp:
        clean_path = Path(tmp) / "clean.parquet"
        mutant_path = Path(tmp) / "mutant.parquet"
        pair.clean.to_parquet(clean_path, index=False)
        pair.mutant.to_parquet(mutant_path, index=False)
        r_clean = run_check(check_source, clean_path, timeout_s)
        r_mutant = run_check(check_source, mutant_path, timeout_s)

    clean_passed = bool(r_clean.ok and r_clean.passed)
    mutant_failed = bool(r_mutant.ok and r_mutant.passed is False)

    if not r_clean.ok or not r_mutant.ok:
        err = r_clean.error if not r_clean.ok else r_mutant.error
        return GateResult(GateOutcome.error, clean_passed, mutant_failed, pair.mutant_desc,
                          f"check crashed on a 20-row fixture: {err}")
    if clean_passed and mutant_failed:
        return GateResult(GateOutcome.gate_passed, True, True, pair.mutant_desc, "discriminates")
    if not mutant_failed:
        return GateResult(
            GateOutcome.vacuous, clean_passed, False, pair.mutant_desc,
            f"check PASSED the mutant fixture ({pair.mutant_desc}) — it cannot detect the "
            f"violation it is supposed to guard against")
    return GateResult(
        GateOutcome.error, False, True, pair.mutant_desc,
        "check FAILED the clean fixture that satisfies the claim (over-strict or inverted "
        f"logic; clean computed: {r_clean.computed!r})")
