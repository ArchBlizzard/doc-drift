"""T024 acceptance: generation speed + both planted hard-case violations
verified by direct pandas, and their invisibility to summary statistics."""

import time

import pandas as pd
import pytest

from synth_transactions import EXPRESS_COUPON_ROWS, N_ROWS, generate


@pytest.fixture(scope="module")
def df():
    t0 = time.monotonic()
    frame = generate()
    generate.cache_clear()  # measure a real second generation for the speed bound
    t0 = time.monotonic()
    frame = generate()
    assert time.monotonic() - t0 <= 60, "hard-case generation must stay under a minute"
    return frame


def test_shape_and_true_claims(df):
    assert len(df) == N_ROWS
    assert df["ts"].is_monotonic_increasing
    assert str(df["ts"].min().date()) == "2024-01-01"
    assert str(df["ts"].max().date()) == "2024-12-31"
    assert df["amount"].min() == 5.00 and df["amount"].max() == 500.00
    assert set(df["status"]) == {"PLACED", "SHIPPED", "DELIVERED", "RETURNED"}
    assert set(df["channel"]) == {"web", "app", "express"}


def test_pair_share_is_exactly_14_2_pct(df):
    share = (df["coupon_id"].notna() & (df["channel"] == "express")).mean()
    assert share == pytest.approx(EXPRESS_COUPON_ROWS / N_ROWS)
    assert share == pytest.approx(0.142)


def test_accurate_coupons_all_match_pattern(df):
    values = df["coupon_id"].dropna().astype(str)
    assert values.str.fullmatch(r"CP-\d{5}").all()


def test_corrupted_case_violations_are_deep_and_summary_invisible(tmp_path):
    """Build case_12 and verify: the 173 bad codes sit only past row 810k AND
    rank far below any top-10 value count (invisible to baseline_plus's
    information budget); the pair share is 14.2% vs the card's 'roughly 10%'."""
    from make_cases import build_case, load_spec
    from pathlib import Path

    spec = load_spec(Path(__file__).parents[1] / "eval" / "specs" / "case_12.yaml")
    build_case(spec, cases_dir=tmp_path / "cases", gold_dir=tmp_path / "gold")
    df = pd.read_parquet(tmp_path / "cases" / "case_12" / "data.parquet")

    bad = df.index[df["coupon_id"] == "XX-BAD-CODE"]
    assert len(bad) == 173 and bad.min() >= 810_000
    head = df.head(50)
    assert not (head["coupon_id"] == "XX-BAD-CODE").any()  # head sample blind
    top10 = df["coupon_id"].value_counts().head(10)
    assert "XX-BAD-CODE" not in top10.index  # top-10 value counts blind
    assert top10.min() > 173  # and by a comfortable margin

    card = (tmp_path / "cases" / "case_12" / "datacard.md").read_text(encoding="utf-8")
    assert "Roughly 10% of orders pair a coupon" in card
    share = 100 * (df["coupon_id"].notna() & (df["channel"] == "express")).mean()
    assert share == pytest.approx(14.2, abs=0.05)  # truth, outside 10±2
