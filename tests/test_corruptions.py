import numpy as np
import pandas as pd
import pytest

from corruptions import OP_REGISTRY, ManifestClaim, locate_span
from docdrift.schemas import ClaimType, Verdict

CARD = (
    "# Toy Transactions\n\n"
    "## Overview\n"
    "This dataset records 20 transactions, collected by our field team during a 2019 pilot study.\n\n"
    "## Schema\n"
    "The `amount` column ranges from 1 to 100. "
    "The `status` column contains exactly 3 categories: A, B and C. "
    "There are no missing values in the `customer_id` column. "
    "Records span January 2020 through December 2021. "
    "The mean of `amount` is 50.5. "
    "About 0% of `coupon` values are missing.\n"
)


def toy_df() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "customer_id": range(1, 21),
        "amount": np.linspace(1, 100, 20).round(1),
        "status": [["A", "B", "C"][i % 3] for i in range(20)],
        "ts": pd.date_range("2020-01-15", "2021-12-15", periods=20),
        "coupon": [f"CP{i:02d}" for i in range(20)],
    })


CLAIMS = {
    "c_null": ManifestClaim(id="c_null", type=ClaimType.null_rate,
                            quoted_span="There are no missing values in the `customer_id` column.",
                            params={"column": "customer_id"}, base_verdict=Verdict.holds),
    "c_cat": ManifestClaim(id="c_cat", type=ClaimType.category_set,
                           quoted_span="The `status` column contains exactly 3 categories: A, B and C.",
                           params={"column": "status"}, base_verdict=Verdict.holds),
    "c_range": ManifestClaim(id="c_range", type=ClaimType.range,
                             quoted_span="The `amount` column ranges from 1 to 100.",
                             params={"column": "amount"}, base_verdict=Verdict.holds),
    "c_rows": ManifestClaim(id="c_rows", type=ClaimType.row_count,
                            quoted_span="This dataset records 20 transactions",
                            params={"expected": 20}, base_verdict=Verdict.holds),
    "c_temporal": ManifestClaim(id="c_temporal", type=ClaimType.temporal_coverage,
                                quoted_span="Records span January 2020 through December 2021.",
                                params={"column": "ts"}, base_verdict=Verdict.holds),
    "c_stat": ManifestClaim(id="c_stat", type=ClaimType.aggregate_stat,
                            quoted_span="The mean of `amount` is 50.5.",
                            params={"column": "amount"}, base_verdict=Verdict.holds),
    "c_fuzzy": ManifestClaim(id="c_fuzzy", type=ClaimType.null_rate,
                             quoted_span="About 0% of `coupon` values are missing.",
                             params={"column": "coupon"}, base_verdict=Verdict.holds),
    "c_phantom": ManifestClaim(id="c_phantom", type=ClaimType.schema,
                               quoted_span="placeholder",  # template entry; op writes its own span
                               params={"column": "discount_code"}, base_verdict=Verdict.holds),
}


def run_op(name, claim_id, params):
    rng = np.random.default_rng(42)
    return OP_REGISTRY[name](CARD, toy_df(), CLAIMS[claim_id], rng, params)


def test_all_eight_operators_registered():
    assert sorted(OP_REGISTRY) == sorted([
        "inject_nulls", "add_category", "shift_range", "row_count_drift",
        "stale_temporal", "perturb_stat", "phantom_column", "fuzzy_coarsen",
    ])


def test_inject_nulls_flips_truth():
    assert toy_df()["customer_id"].isna().sum() == 0  # true before
    res = run_op("inject_nulls", "c_null", {"n": 3})
    assert res.df["customer_id"].isna().sum() == 3    # false after
    assert res.gold.gold_verdict is Verdict.violated
    assert res.card_text == CARD  # data op: card untouched


def test_add_category_flips_truth():
    res = run_op("add_category", "c_cat", {"new_value": "X", "n": 4})
    assert "X" in set(res.df["status"])
    assert res.gold.corruption_op == "add_category"


def test_shift_range_flips_truth():
    res = run_op("shift_range", "c_range", {"out_value": 250.0, "n": 2})
    assert res.df["amount"].max() > 100


def test_row_count_drift_drop_and_dup():
    assert len(run_op("row_count_drift", "c_rows", {"mode": "drop", "n": 5}).df) == 15
    assert len(run_op("row_count_drift", "c_rows", {"mode": "dup", "n": 5}).df) == 25


def test_stale_temporal_rewrites_card_not_data():
    new = "Records span January 2020 through December 2024."
    res = run_op("stale_temporal", "c_temporal", {"new_span": new})
    assert new in res.card_text
    assert CLAIMS["c_temporal"].quoted_span not in res.card_text
    pd.testing.assert_frame_equal(res.df, toy_df())  # card op: data untouched


def test_perturb_stat_rewrites_number():
    new = "The mean of `amount` is 61.2."
    res = run_op("perturb_stat", "c_stat", {"new_span": new})
    assert new in res.card_text


def test_phantom_column_inserts_schema_claim():
    sentence = "The `discount_code` column is always populated."
    res = run_op("phantom_column", "c_phantom",
                 {"sentence": sentence, "anchor": "The mean of `amount` is 50.5."})
    assert sentence in res.card_text
    assert "discount_code" not in res.df.columns
    assert res.gold.type is ClaimType.schema


def test_fuzzy_coarsen_sets_wrong_roughly_value():
    new = "Roughly 10% of `coupon` values are missing."
    res = run_op("fuzzy_coarsen", "c_fuzzy", {"new_span": new, "true_value": "0%"})
    assert new in res.card_text
    assert res.gold.corruption_op == "fuzzy_coarsen"


@pytest.mark.parametrize("name,claim_id,params", [
    ("inject_nulls", "c_null", {"n": 3}),
    ("add_category", "c_cat", {"new_value": "X", "n": 4}),
    ("shift_range", "c_range", {"out_value": 250.0, "n": 2}),
    ("row_count_drift", "c_rows", {"mode": "drop", "n": 5}),
    ("stale_temporal", "c_temporal", {"new_span": "Records span January 2020 through December 2024."}),
    ("perturb_stat", "c_stat", {"new_span": "The mean of `amount` is 61.2."}),
    ("phantom_column", "c_phantom", {"sentence": "The `discount_code` column is always populated.",
                                     "anchor": "The mean of `amount` is 50.5."}),
    ("fuzzy_coarsen", "c_fuzzy", {"new_span": "Roughly 10% of `coupon` values are missing.",
                                  "true_value": "0%"}),
])
def test_span_invariant_roundtrip(name, claim_id, params):
    """The gold span must slice the FINAL card text to exactly quoted_span."""
    res = run_op(name, claim_id, params)
    assert res.card_text[res.gold.span_start:res.gold.span_end] == res.gold.quoted_span
    # and be locatable uniquely
    assert locate_span(res.card_text, res.gold.quoted_span) == (res.gold.span_start, res.gold.span_end)


def test_determinism_same_seed_same_result():
    a = run_op("inject_nulls", "c_null", {"n": 3})
    b = run_op("inject_nulls", "c_null", {"n": 3})
    pd.testing.assert_frame_equal(a.df, b.df)
    assert a.gold == b.gold


def test_locate_span_rejects_missing_and_duplicate():
    with pytest.raises(ValueError, match="not found"):
        locate_span(CARD, "no such text")
    with pytest.raises(ValueError, match="not unique"):
        locate_span("abc abc", "abc")
