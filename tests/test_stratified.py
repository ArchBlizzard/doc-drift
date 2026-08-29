"""T028 acceptance (offline): the stratified prompt reaches beyond the head,
covers all three thirds, is seeded-deterministic, and the runner emits
schema-valid baseline_stratified output."""

import json

import anyio
import pandas as pd

import run_stratified
from docdrift.llm import RawReply
from docdrift.schemas import SystemOutput

CARD = "# Tiny\n\nThe table holds 900 rows. Deep values stay small.\n"


def make_case(tmp_path):
    d = tmp_path / "cases" / "case_88"
    d.mkdir(parents=True)
    (d / "datacard.md").write_text(CARD, encoding="utf-8")
    pd.DataFrame({"row_tag": [f"tag{i:04d}" for i in range(900)]}).to_csv(
        d / "data.csv", index=False)
    return tmp_path / "cases"


def test_prompt_covers_all_thirds_and_is_deterministic(tmp_path):
    cases = make_case(tmp_path)
    card, df = run_stratified.load_case("case_88", cases)
    p1 = run_stratified.build_stratified_prompt(card, df)
    p2 = run_stratified.build_stratified_prompt(card, df)
    assert p1 == p2  # seeded
    assert "FROM ROWS 0-299" in p1 and "FROM ROWS 300-599" in p1 and "FROM ROWS 600-899" in p1
    assert any(f"tag0{i}" in p1 for i in range(600, 900))  # tail rows really present


def test_runner_emits_schema_valid_output(tmp_path):
    cases = make_case(tmp_path)

    async def transport(system_prompt, user_prompt, model):
        reply = {"claims": [{"quoted_span": "The table holds 900 rows.",
                             "verdict": "holds", "claimed": "900", "computed": "900"}]}
        return RawReply(json.dumps(reply), "claude-test-1", 50, 25)

    out = anyio.run(lambda: run_stratified.run_case(
        "case_88", out_root=tmp_path / "runs", cases_root=cases, transport=transport))
    parsed = SystemOutput.model_validate_json(out.read_text())
    assert parsed.system.value == "baseline_stratified"
    meta = json.loads((out.parent / "meta.json").read_text())
    assert meta["span_compliance"] == 1.0 and meta["stratum_rows"] == 600
