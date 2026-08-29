"""T021 acceptance: for every claim type, the clean fixture satisfies the claim
and the mutant violates it (fast in-process asserts), plus full gate runs that
catch a vacuous check, an inverted check, and pass a discriminating one."""

import pandas as pd
import pytest

from docdrift.schemas import Claim, ClaimType, GateOutcome
from docdrift.tools.mutants import FixtureError, build_fixtures, gate_check

DF = pd.DataFrame({
    "price": [1.0, 5.5, 9.0, 3.3] * 5,
    "qty": [1, 2, 3, 4] * 5,
    "status": ["A", "B", "C", "A"] * 5,
    "year": [2007, 2008, 2009, 2008] * 5,
    "ts": pd.date_range("2024-01-01", periods=20),
    "coupon": [f"CP-{i:05d}" for i in range(20)],
})


def claim(type_, params, quoted="the claim text"):
    return Claim(id="case_99-c01", case_id="case_99", type=type_,
                 quoted_span=quoted, span_start=0, span_end=len(quoted), params=params)


def test_row_count():
    fx = build_fixtures(DF, claim(ClaimType.row_count, {"expected": 12}))
    assert len(fx.clean) == 12 and len(fx.mutant) == 19


def test_range_float_and_int():
    fx = build_fixtures(DF, claim(ClaimType.range, {"column": "price", "min": 1, "max": 9}))
    assert fx.clean["price"].min() == 1 and fx.clean["price"].max() == 9
    assert fx.mutant["price"].max() > 9
    fi = build_fixtures(DF, claim(ClaimType.range, {"column": "qty", "min": 1, "max": 4}))
    assert fi.clean["qty"].min() == 1 and fi.clean["qty"].max() == 4
    assert fi.mutant["qty"].max() > 4


def test_null_rate_modes():
    zero = build_fixtures(DF, claim(ClaimType.null_rate, {"column": "qty", "mode": "zero"}))
    assert zero.clean["qty"].isna().sum() == 0 and zero.mutant["qty"].isna().sum() == 3
    count = build_fixtures(DF, claim(ClaimType.null_rate,
                                     {"column": "coupon", "mode": "count", "value": 4}))
    assert count.clean["coupon"].isna().sum() == 4 and count.mutant["coupon"].isna().sum() == 7
    pct = build_fixtures(DF, claim(ClaimType.null_rate,
                                   {"column": "coupon", "mode": "pct", "value": 10, "tol_pp": 2}))
    assert pct.clean["coupon"].isna().mean() == pytest.approx(0.10)
    assert pct.mutant["coupon"].isna().mean() == pytest.approx(0.17)
    sent = build_fixtures(DF, claim(ClaimType.null_rate,
                                    {"column": "price", "mode": "sentinel", "sentinel": 999.9}))
    assert (sent.clean["price"] == 999.9).any() and sent.clean["price"].notna().all()
    assert sent.mutant["price"].isna().sum() == 2
    za = build_fixtures(DF, claim(ClaimType.null_rate, {"mode": "zero_all"}))
    assert int(za.clean.isna().sum().sum()) == 0 and int(za.mutant.isna().sum().sum()) == 3


def test_category_set_values_and_count():
    v = build_fixtures(DF, claim(ClaimType.category_set,
                                 {"column": "status", "values": ["A", "B", "C"]}))
    assert set(v.clean["status"]) == {"A", "B", "C"}
    assert "UNDOCUMENTED_MUTANT" in set(v.mutant["status"])
    c = build_fixtures(DF, claim(ClaimType.category_set, {"column": "status", "count": 3}))
    assert c.clean["status"].nunique() == 3 and c.mutant["status"].nunique() == 4


def test_aggregate_stats():
    mean_i = build_fixtures(DF, claim(ClaimType.aggregate_stat,
                                      {"column": "qty", "stat": "mean", "value": 2.5}))
    assert mean_i.clean["qty"].mean() == pytest.approx(2.5)
    assert mean_i.mutant["qty"].mean() != pytest.approx(2.5)
    min_f = build_fixtures(DF, claim(ClaimType.aggregate_stat,
                                     {"column": "price", "stat": "min", "value": -351.0}))
    assert min_f.clean["price"].min() == pytest.approx(-351.0)
    assert min_f.mutant["price"].min() != pytest.approx(-351.0)
    share = build_fixtures(DF, claim(ClaimType.aggregate_stat, {
        "stat": "pair_share", "column": "coupon", "condition_column": "status",
        "condition_value": "A", "value": 14, "tol_pp": 2}))
    clean_share = (share.clean["coupon"].notna() & (share.clean["status"] == "A")).mean()
    mut_share = (share.mutant["coupon"].notna() & (share.mutant["status"] == "A")).mean()
    assert clean_share == pytest.approx(0.14) and mut_share == pytest.approx(0.21)


def test_temporal_dates_and_years():
    d = build_fixtures(DF, claim(ClaimType.temporal_coverage,
                                 {"column": "ts", "min_date": "2023-01-01", "max_date": "2023-12-31"}))
    assert str(d.clean["ts"].min().date()) == "2023-01-01"
    assert str(d.clean["ts"].max().date()) == "2023-12-31"
    assert d.mutant["ts"].min() < pd.Timestamp("2023-01-01")
    y = build_fixtures(DF, claim(ClaimType.temporal_coverage,
                                 {"column": "year", "min_year": 2007, "max_year": 2009}))
    assert y.clean["year"].min() == 2007 and y.clean["year"].max() == 2009
    assert y.mutant["year"].max() == 2012


def test_schema_exists_regex_sorted():
    ph = build_fixtures(DF, claim(ClaimType.schema, {"column": "tag_id"}))
    assert "tag_id" in ph.clean.columns and "tag_id" not in ph.mutant.columns
    rx = build_fixtures(DF, claim(ClaimType.schema,
                                  {"column": "coupon", "regex": r"CP-\d{5}"}))
    import re
    assert all(re.fullmatch(r"CP-\d{5}", v) for v in rx.clean["coupon"])
    assert not all(re.fullmatch(r"CP-\d{5}", str(v)) for v in rx.mutant["coupon"])
    so = build_fixtures(DF, claim(ClaimType.schema, {"column": "ts", "sorted": True}))
    assert so.clean["ts"].is_monotonic_increasing
    assert not so.mutant["ts"].is_monotonic_increasing


@pytest.mark.parametrize("type_,params,msg", [
    (ClaimType.row_count, {}, "lacks params"),
    (ClaimType.range, {"column": "price"}, "lacks params"),
    (ClaimType.prose_unverifiable, {}, "no fixture builder"),
    (ClaimType.schema, {"column": "status", "regex": r"\d+"}, "no real values"),
    (ClaimType.category_set, {"column": "nope", "count": 2}, "not in data"),
])
def test_fixture_errors(type_, params, msg):
    with pytest.raises(FixtureError, match=msg):
        build_fixtures(DF, claim(type_, params))


GOOD_ROW_CHECK = ('def check(df):\n    n = len(df)\n    return {"passed": n == 12, '
                  '"computed": str(n), "evidence_rows": []}\n')
VACUOUS_CHECK = ('def check(df):\n    return {"passed": True, "computed": "looks fine", '
                 '"evidence_rows": []}\n')
INVERTED_CHECK = ('def check(df):\n    return {"passed": False, "computed": "always bad", '
                  '"evidence_rows": []}\n')


def test_gate_passes_discriminating_check():
    r = gate_check(GOOD_ROW_CHECK, DF, claim(ClaimType.row_count, {"expected": 12}))
    assert r.outcome is GateOutcome.gate_passed
    assert r.clean_passed and r.mutant_failed


def test_gate_catches_vacuous_check():
    r = gate_check(VACUOUS_CHECK, DF, claim(ClaimType.row_count, {"expected": 12}))
    assert r.outcome is GateOutcome.vacuous
    assert not r.mutant_failed
    assert "PASSED the mutant" in r.detail


def test_gate_catches_inverted_check():
    r = gate_check(INVERTED_CHECK, DF, claim(ClaimType.row_count, {"expected": 12}))
    assert r.outcome is GateOutcome.error
    assert "FAILED the clean fixture" in r.detail
