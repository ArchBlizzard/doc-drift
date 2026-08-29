"""Truth checkers for manifest claims (T007): gold integrity is auditable.

Every `base_verdict: holds` claim in a card manifest must be verifiably true of
the committed dataset — these checkers are the committed proof (Constitution I),
exercised by tests/test_card_truth.py on every `pytest` run.
"""

from __future__ import annotations

import pandas as pd

from corruptions import ManifestClaim
from docdrift.schemas import ClaimType


def check_claim(df: pd.DataFrame, claim: ManifestClaim) -> tuple[bool, str]:
    """Return (truth, detail) for one holds-claim against the accurate data."""
    p = claim.params
    t = claim.type

    if t is ClaimType.row_count:
        actual = len(df)
        return actual == p["expected"], f"rows={actual} expected={p['expected']}"

    if t is ClaimType.range:
        s = df[p["column"]]
        lo, hi = s.min(), s.max()
        ok = float(lo) == float(p["min"]) and float(hi) == float(p["max"])
        return ok, f"{p['column']} min={lo} max={hi} claimed=[{p['min']}, {p['max']}]"

    if t is ClaimType.category_set:
        s = df[p["column"]].dropna()
        if "values" in p:
            actual = set(map(str, s.unique()))
            ok = actual == set(map(str, p["values"]))
            return ok, f"{p['column']} actual={sorted(actual)} claimed={sorted(map(str, p['values']))}"
        actual_n = s.nunique()
        return actual_n == p["count"], f"{p['column']} nunique={actual_n} claimed={p['count']}"

    if t is ClaimType.null_rate:
        mode = p["mode"]
        if mode == "zero_all":
            n = int(df.isna().sum().sum())
            return n == 0, f"total nulls={n}"
        s = df[p["column"]]
        if mode == "count":
            n = int(s.isna().sum())
            return n == int(p["value"]), f"{p['column']} nulls={n} claimed={p['value']}"
        if mode == "pct":
            pct = 100.0 * s.isna().mean()
            ok = abs(pct - float(p["value"])) <= float(p.get("tol_pp", 2))
            return ok, f"{p['column']} null%={pct:.2f} claimed~{p['value']}±{p.get('tol_pp', 2)}"
        if mode == "sentinel":
            has_sentinel = bool((s == p["sentinel"]).any())
            no_nan = int(s.isna().sum()) == 0
            return has_sentinel and no_nan, (
                f"{p['column']} sentinel({p['sentinel']}) present={has_sentinel} nan-free={no_nan}"
            )
        raise ValueError(f"unknown null_rate mode {mode!r}")

    if t is ClaimType.aggregate_stat:
        if p.get("stat") == "pair_share":
            share = 100.0 * float((df[p["column"]].notna()
                                   & (df[p["condition_column"]] == p["condition_value"])).mean())
            tol = float(p.get("tol_pp", p.get("tolerance_pp", 2)))
            ok = abs(share - float(p["value"])) <= tol
            return ok, (f"share({p['column']} & {p['condition_column']}=="
                        f"{p['condition_value']})={share:.2f}% claimed ~{p['value']}%±{tol}")
        s = df[p["column"]]
        actual = float(getattr(s, p["stat"])())
        dec = int(p["decimals"])
        ok = round(actual, dec) == round(float(p["value"]), dec)
        return ok, f"{p['stat']}({p['column']})={actual:.4f} ~ claimed {p['value']} @{dec}dp"

    if t is ClaimType.temporal_coverage:
        s = df[p["column"]]
        if "min_year" in p:
            ok = int(s.min()) == p["min_year"] and int(s.max()) == p["max_year"]
            return ok, f"{p['column']} years [{s.min()}, {s.max()}] claimed [{p['min_year']}, {p['max_year']}]"
        dates = pd.to_datetime(s)
        lo, hi = dates.min().date(), dates.max().date()
        ok = (str(lo) == p["min_date"]) and (str(hi) == p["max_date"])
        return ok, f"{p['column']} dates [{lo}, {hi}] claimed [{p['min_date']}, {p['max_date']}]"

    if t is ClaimType.schema:
        col = p["column"]
        if "regex" in p:
            import re
            values = df[col].dropna().astype(str)
            bad = int((~values.str.fullmatch(p["regex"])).sum())
            return bad == 0, f"{bad} non-null values of {col!r} violate pattern {p['regex']!r}"
        if p.get("sorted") or "sorted_by" in p:
            sort_col = p.get("sorted_by", col)
            ok = bool(pd.Series(df[sort_col]).is_monotonic_increasing)
            return ok, f"{sort_col!r} monotonic ascending={ok}"
        return col in df.columns, f"column {col!r} present={col in df.columns}"

    raise ValueError(f"no checker for claim type {t}")
