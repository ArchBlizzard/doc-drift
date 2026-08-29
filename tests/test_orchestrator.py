"""T019 acceptance (offline, stubbed model, REAL executor subprocesses):
end-to-end verdicts, prose skip, execution-retry policy, default resume with
zero model calls, --fresh, exit 3."""

import json

import anyio
import pytest

import run_agent
from docdrift import orchestrator
from docdrift.llm import RawReply
from docdrift.schemas import CheckStatus, LedgerEntry, SystemOutput, Verdict

CARD = ("# T\n\nThe table holds 3 rows. There are no missing values in the qty column. "
        "Collected by hand.\n")

EXTRACT_REPLY = {"claims": [
    {"type": "row_count", "quoted_span": "The table holds 3 rows.", "params": {"expected": 3}},
    {"type": "null_rate", "quoted_span": "There are no missing values in the qty column.",
     "params": {"column": "qty"}},
    {"type": "prose_unverifiable", "quoted_span": "Collected by hand.", "params": {}},
]}

ROW_CHECK = ('def check(df):\n    n = len(df)\n    return {"passed": n == 3, '
             '"computed": str(n), "evidence_rows": []}\n')
NULL_CHECK = ('def check(df):\n    bad = df[df["qty"].isna()]\n    return {"passed": bad.empty, '
              '"computed": f"{len(bad)} nulls", "evidence_rows": bad.head(5).to_dict("records")}\n')
CRASH_CHECK = 'def check(df):\n    raise ValueError("kaboom")\n'


def make_transport(crash_null=False):
    calls = {"extract": 0, "synth": 0}

    async def transport(system_prompt, user_prompt, model):
        if "You extract" in system_prompt:
            calls["extract"] += 1
            return RawReply(json.dumps(EXTRACT_REPLY), "claude-test-1", 100, 50)
        calls["synth"] += 1
        if "holds 3 rows" in user_prompt:
            src = ROW_CHECK
        else:
            src = CRASH_CHECK if crash_null else NULL_CHECK
        return RawReply(json.dumps({"source_code": src}), "claude-test-1", 40, 20)

    transport.calls = calls
    return transport


@pytest.fixture
def case_root(tmp_path):
    d = tmp_path / "cases" / "case_77"
    d.mkdir(parents=True)
    (d / "datacard.md").write_text(CARD, encoding="utf-8")
    (d / "data.csv").write_text("price,qty\n1,10\n5,\n9,3\n", encoding="utf-8")
    return tmp_path / "cases"


def run(case_root, out_root, transport, fresh=False):
    return anyio.run(lambda: orchestrator.run_case(
        "case_77", cases_root=case_root, out_root=out_root,
        transport=transport, fresh=fresh, quiet=True))


def by_claim(out_root) -> dict[str, LedgerEntry]:
    from docdrift.ledger import Ledger, fingerprint_text  # noqa: F401
    lines = (out_root / "case_77" / "agent" / "ledger.jsonl").read_text().splitlines()
    entries = [LedgerEntry.model_validate_json(line) for line in lines[1:]]
    return {e.claim.quoted_span: e for e in entries}


def test_end_to_end_verdicts(case_root, tmp_path):
    transport = make_transport()
    out = run(case_root, tmp_path / "runs", transport)
    parsed = SystemOutput.model_validate_json(out.read_text())
    verdicts = {c.quoted_span: c for c in parsed.claims}
    assert verdicts["The table holds 3 rows."].verdict is Verdict.holds
    nulls = verdicts["There are no missing values in the qty column."]
    assert nulls.verdict is Verdict.violated and nulls.computed == "1 nulls"
    assert nulls.evidence_rows and nulls.evidence_rows[0]["price"] == "5"
    prose = verdicts["Collected by hand."]
    assert prose.verdict is Verdict.unverifiable and prose.reason.value == "prose"
    # spans are exact
    for c in parsed.claims:
        assert CARD[c.span_start:c.span_end] == c.quoted_span
    assert transport.calls == {"extract": 1, "synth": 2}
    assert (out.parent / "audit.md").read_text().count("|") > 10


def test_trusted_verdicts_have_executed_checks_and_prose_has_none(case_root, tmp_path):
    run(case_root, tmp_path / "runs", make_transport())
    entries = by_claim(tmp_path / "runs")
    for span in ("The table holds 3 rows.", "There are no missing values in the qty column."):
        e = entries[span]
        assert e.check is not None and e.execution is not None
        assert e.check.status is CheckStatus.gate_skipped  # v1 marker
    prose = entries["Collected by hand."]
    assert prose.check is None and prose.execution is None


def test_execution_error_after_retry(case_root, tmp_path):
    transport = make_transport(crash_null=True)
    out = run(case_root, tmp_path / "runs", transport)
    parsed = SystemOutput.model_validate_json(out.read_text())
    nulls = next(c for c in parsed.claims if "missing values" in c.quoted_span)
    assert nulls.verdict is Verdict.unverifiable and nulls.reason.value == "execution_error"
    entry = by_claim(tmp_path / "runs")["There are no missing values in the qty column."]
    assert "kaboom" in entry.execution.error


def test_resume_makes_zero_model_calls(case_root, tmp_path):
    first = make_transport()
    run(case_root, tmp_path / "runs", first)
    second = make_transport()
    out = run(case_root, tmp_path / "runs", second)
    assert second.calls == {"extract": 0, "synth": 0}
    parsed = SystemOutput.model_validate_json(out.read_text())
    assert len(parsed.claims) == 3  # verdicts fully reconstructed from the ledger


def test_fresh_reruns_everything(case_root, tmp_path):
    run(case_root, tmp_path / "runs", make_transport())
    again = make_transport()
    run(case_root, tmp_path / "runs", again, fresh=True)
    assert again.calls == {"extract": 1, "synth": 2}


def test_exit_3_on_missing_case():
    assert run_agent.main(["case_00"]) == 3
