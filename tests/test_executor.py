"""T015 acceptance: pass/fail checks, crash, timeout, evidence capping, and
noise-tolerant result parsing — each in a real subprocess."""

import pytest

from docdrift.tools.executor import run_check


@pytest.fixture(scope="module")
def data_csv(tmp_path_factory):
    p = tmp_path_factory.mktemp("data") / "d.csv"
    p.write_text("price,qty\n1,10\n5,0\n9,3\n", encoding="utf-8")
    return p


PASSING = """
def check(df):
    ok = df["price"].max() <= 9
    return {"passed": bool(ok), "computed": f"max={df['price'].max()}", "evidence_rows": []}
"""

FAILING_WITH_EVIDENCE = """
def check(df):
    bad = df[df["qty"] == 0]
    return {"passed": bad.empty, "computed": f"{len(bad)} zero-qty rows",
            "evidence_rows": bad.head(5).to_dict("records")}
"""


def test_passing_check(data_csv):
    out = run_check(PASSING, data_csv)
    assert out.ok and out.passed is True
    assert out.computed == "max=9"


def test_failing_check_with_evidence(data_csv):
    out = run_check(FAILING_WITH_EVIDENCE, data_csv)
    assert out.ok and out.passed is False
    assert out.computed == "1 zero-qty rows"
    assert out.evidence_rows == [{"price": "5", "qty": "0"}]


def test_crash_reports_error(data_csv):
    out = run_check("def check(df):\n    raise ValueError('boom')\n", data_csv)
    assert not out.ok and out.passed is None
    assert "boom" in out.error


def test_timeout(data_csv):
    src = "import time\ndef check(df):\n    time.sleep(30)\n    return {'passed': True}\n"
    out = run_check(src, data_csv, timeout_s=2)
    assert not out.ok and "timeout" in out.error


def test_evidence_rows_capped_at_5(data_csv):
    src = """
def check(df):
    rows = [{"i": i} for i in range(12)]
    return {"passed": False, "computed": "12", "evidence_rows": rows}
"""
    out = run_check(src, data_csv)
    assert out.ok and len(out.evidence_rows) == 5


def test_noise_before_marker_is_tolerated(data_csv):
    src = """
def check(df):
    print("debugging noise " * 50)
    return {"passed": True, "computed": "ok", "evidence_rows": []}
"""
    out = run_check(src, data_csv)
    assert out.ok and out.passed is True


def test_non_dict_result_is_crash(data_csv):
    out = run_check("def check(df):\n    return 42\n", data_csv)
    assert not out.ok and "must return a dict" in out.error
