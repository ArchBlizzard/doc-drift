"""T011 acceptance: schema-valid output on a fixture case, span location +
compliance measurement, exit 3 on missing case, exit 2 on auth error."""

import json

import anyio
import pytest

import run_baseline
from docdrift.llm import AuthError, RawReply
from docdrift.schemas import SystemOutput

CARD = (
    "# Tiny\n\nThe table holds 3 rows. Prices range from 1 to 9. "
    "Collected by hand for a pilot.\n"
)


@pytest.fixture
def case_dir(tmp_path):
    d = tmp_path / "cases" / "case_77"
    d.mkdir(parents=True)
    (d / "datacard.md").write_text(CARD, encoding="utf-8")
    (d / "data.csv").write_text("price\n1\n5\n9\n", encoding="utf-8")
    return tmp_path


def fake_transport(reply_obj):
    async def transport(system_prompt, user_prompt, model):
        return RawReply(json.dumps(reply_obj), "claude-test-1", 100, 50)
    return transport


GOOD_REPLY = {"claims": [
    {"quoted_span": "The table holds 3 rows.", "verdict": "holds",
     "claimed": "3", "computed": "3"},
    {"quoted_span": "Prices range from 1 to 9.", "verdict": "holds",
     "claimed": "[1, 9]", "computed": "[1, 9]"},
    {"quoted_span": "Collected by hand for a pilot.", "verdict": "unverifiable",
     "reason": "prose"},
]}


def test_run_case_produces_schema_valid_output(case_dir, tmp_path):
    out = anyio.run(lambda: run_baseline.run_case(
        "case_77", out_root=tmp_path / "runs", cases_root=case_dir / "cases",
        transport=fake_transport(GOOD_REPLY)))
    parsed = SystemOutput.model_validate_json(out.read_text())
    assert parsed.system.value == "baseline"
    assert len(parsed.claims) == 3
    # spans located exactly
    for claim in parsed.claims:
        assert claim.span_start is not None
        assert CARD[claim.span_start:claim.span_end] == claim.quoted_span
    meta = json.loads((out.parent / "meta.json").read_text())
    assert meta["span_compliance"] == 1.0
    assert (out.parent / "messages.jsonl").is_file()


def test_unlocatable_quote_lowers_compliance(case_dir, tmp_path):
    reply = {"claims": [
        {"quoted_span": "The table holds three rows total.",  # paraphrase — not in card
         "verdict": "holds", "claimed": "3", "computed": "3"},
        {"quoted_span": "Prices range from 1 to 9.", "verdict": "holds",
         "claimed": "x", "computed": "x"},
    ]}
    out = anyio.run(lambda: run_baseline.run_case(
        "case_77", out_root=tmp_path / "runs", cases_root=case_dir / "cases",
        transport=fake_transport(reply)))
    parsed = SystemOutput.model_validate_json(out.read_text())
    assert parsed.claims[0].span_start is None
    meta = json.loads((out.parent / "meta.json").read_text())
    assert meta["span_compliance"] == 0.5


def test_plus_prompt_adds_statistics(case_dir):
    card, df = run_baseline.load_case("case_77", case_dir / "cases")
    base = run_baseline.build_user_prompt(card, df, plus=False)
    plus = run_baseline.build_user_prompt(card, df, plus=True)
    assert "FIRST 50 ROWS" in base and "SUMMARY STATISTICS" not in base
    assert "SUMMARY STATISTICS" in plus and "TOP 10 VALUE COUNTS" in plus


def test_exit_3_on_missing_case():
    assert run_baseline.main(["case_00"]) == 3  # no such case is ever generated


def test_exit_2_on_auth_error(case_dir, monkeypatch):
    async def boom(*a, **k):
        raise AuthError("no credential")
    monkeypatch.setattr(run_baseline, "run_case", boom)
    assert run_baseline.main(["case_77"]) == 2
