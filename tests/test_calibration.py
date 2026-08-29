"""T027 acceptance: the ±tolerance_pp band semantics are reproducible end to
end — a canned band-honoring check judges 11.5% as within roughly-10 (holds)
and 14.2% as outside it (violated) — and both prompts carry the calibration."""

import pandas as pd
import pytest

from docdrift.agents.extractor import SYSTEM_PROMPT as EXTRACTOR_PROMPT
from docdrift.agents.synthesizer import SYSTEM_PROMPT as SYNTH_PROMPT
from docdrift.config import FUZZY_TOLERANCE_PP
from docdrift.tools.executor import run_check

BAND_CHECK = """
def check(df):
    share = 100.0 * (df["coupon_id"].notna() & (df["channel"] == "express")).mean()
    ok = abs(share - 10.0) <= 2.0
    return {"passed": bool(ok), "computed": f"{share:.2f}%", "evidence_rows": []}
"""


def frame(share_pct: float, n: int = 1000) -> pd.DataFrame:
    k = round(share_pct * n / 100)
    return pd.DataFrame({
        "coupon_id": ["CP-00001"] * k + [None] * (n - k),
        "channel": ["express"] * k + ["web"] * (n - k),
    })


@pytest.mark.parametrize("share,expected_pass", [(11.5, True), (14.2, False), (10.0, True)])
def test_band_semantics_end_to_end(tmp_path, share, expected_pass):
    path = tmp_path / f"d_{share}.parquet"
    frame(share).to_parquet(path, index=False)
    out = run_check(BAND_CHECK, path)
    assert out.ok and out.passed is expected_pass, out.computed


def test_prompts_carry_the_calibration():
    assert "tolerance_pp" in EXTRACTOR_PROMPT
    assert "tolerance_pp" in SYNTH_PROMPT
    assert "HOLDS iff |computed - stated| <= tolerance_pp" in SYNTH_PROMPT
    assert FUZZY_TOLERANCE_PP == 2.0
