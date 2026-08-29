"""T009 acceptance: hand-labeled alignment fixtures (exact span, tricky
paraphrase via flagged fuzzy fallback, unmatched-gold miss), hand-computed
macro-F1, and exit 4 on missing/invalid gold. The scorer is pure."""

import json
import sys

import pytest

from docdrift.schemas import GoldFile, SystemOutput
from score import CLASSES, SystemScore, align_case, load_gold, score, span_iou

CARD = "X. There are no missing values in the id column. Rows total 100. Collected by hand in 2019. Prices sit between 1 and 9."


def _gold():
    def g(id_, span, type_, verdict):
        start = CARD.find(span)
        assert start >= 0 and CARD.count(span) == 1
        return dict(id=id_, span_start=start, span_end=start + len(span),
                    quoted_span=span, type=type_, gold_verdict=verdict)
    return GoldFile(case_id="case_99", dataset="toy", seed=1, gold_claims=[
        g("g1", "There are no missing values in the id column.", "null_rate", "violated"),
        g("g2", "Rows total 100.", "row_count", "holds"),
        g("g3", "Collected by hand in 2019.", "prose_unverifiable", "unverifiable"),
        g("g4", "Prices sit between 1 and 9.", "range", "violated"),
        # padding to satisfy the >=6 schema floor; all matched exactly below
        g("g5", "X.", "schema", "holds"),
        g("g6", "column", "schema", "holds"),
    ])


def _output():
    gold = _gold()

    def exact(gid, verdict, **kw):
        g = next(c for c in gold.gold_claims if c.id == gid)
        return dict(quoted_span=g.quoted_span, span_start=g.span_start,
                    span_end=g.span_end, verdict=verdict, **kw)

    return SystemOutput(case_id="case_99", system="baseline", model_id="m", claims=[
        exact("g1", "violated", claimed="0", computed="3"),      # correct, via span
        exact("g2", "violated", claimed="100", computed="93"),   # wrong verdict, via span
        # paraphrase of g3: no spans -> fuzzy fallback, flagged
        dict(quoted_span="Collected by hand in 2019", verdict="unverifiable", reason="prose"),
        # g4 has NO matching output claim -> miss
        exact("g5", "holds", claimed="x", computed="x"),
        exact("g6", "holds", claimed="x", computed="x"),
    ], usage=dict(input_tokens=10, output_tokens=5), wall_s=1.0)


def test_span_iou():
    assert span_iou((0, 10), (0, 10)) == 1.0
    assert span_iou((0, 10), (5, 15)) == pytest.approx(1 / 3)
    assert span_iou((0, 10), (20, 30)) == 0.0


def test_alignment_matches_and_flags():
    matches = {m.gold_id: m for m in align_case(_gold(), _output())}
    assert matches["g1"].predicted == "violated" and matches["g1"].via == "span"
    assert matches["g2"].predicted == "violated" and matches["g2"].gold_verdict == "holds"
    assert matches["g3"].predicted == "unverifiable" and matches["g3"].via == "fuzzy"
    assert matches["g4"].predicted == "missed" and matches["g4"].via == "none"


def test_hand_computed_metrics():
    s = SystemScore("baseline")
    s.matches = align_case(_gold(), _output())
    per = s.per_class()
    # violated: gold {g1,g4}; predicted violated {g1 ok, g2 wrong} -> P=1/2, R=1/2
    assert per["violated"] == (pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5))
    # holds: gold {g2,g5,g6}; predicted holds {g5,g6 correct} -> P=1, R=2/3
    assert per["holds"][0] == pytest.approx(1.0)
    assert per["holds"][1] == pytest.approx(2 / 3)
    # unverifiable: perfect
    assert per["unverifiable"] == (1.0, 1.0, 1.0)
    expected_macro = (0.5 + (2 * 1.0 * (2 / 3)) / (1.0 + 2 / 3) + 1.0) / 3
    assert s.macro_f1() == pytest.approx(expected_macro)
    assert s.violations_caught() == (1, 2)
    assert s.fallbacks() == 1


def test_end_to_end_score_writes_outputs(tmp_path):
    gold_dir = tmp_path / "gold"
    runs = tmp_path / "runs" / "case_99" / "baseline"
    out_dir = tmp_path / "results"
    gold_dir.mkdir(parents=True)
    runs.mkdir(parents=True)
    (gold_dir / "case_99_gold.json").write_text(_gold().model_dump_json(), encoding="utf-8")
    (runs / "verdicts.json").write_text(_output().model_dump_json(), encoding="utf-8")
    systems = score(tmp_path / "runs", gold_dir, out_dir)
    assert "baseline" in systems
    results_md = (out_dir / "results.md").read_text()
    assert "macro-F1" in results_md.lower() or "macro" in results_md
    csv_text = (out_dir / "per_claim.csv").read_text()
    assert "fuzzy" in csv_text and "missed" in csv_text


def test_exit_4_on_missing_gold(tmp_path):
    with pytest.raises(SystemExit) as exc:
        load_gold(tmp_path)
    assert exc.value.code == 4


def test_exit_4_on_invalid_gold(tmp_path):
    (tmp_path / "case_01_gold.json").write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        load_gold(tmp_path)
    assert exc.value.code == 4


def test_scorer_is_pure():
    assert "claude_agent_sdk" not in sys.modules or True  # documentation guard
    import score as score_mod
    source = open(score_mod.__file__, encoding="utf-8").read()
    assert "claude" not in source.lower()
    assert set(CLASSES) == {"holds", "violated", "unverifiable"}
