"""T012 acceptance: skip-completed logic, --force override, unknown-system
rejection. Runner execution is exercised live in T013/T020 sweeps."""

import run_all


def test_skip_completed_pairs(tmp_path):
    (tmp_path / "case_01" / "baseline").mkdir(parents=True)
    (tmp_path / "case_01" / "baseline" / "verdicts.json").write_text("{}")
    pairs = run_all.pairs_to_run(["case_01", "case_02"], ["baseline", "agent"], tmp_path, force=False)
    assert ("case_01", "baseline") not in pairs
    assert ("case_01", "agent") in pairs
    assert ("case_02", "baseline") in pairs
    assert len(pairs) == 3


def test_force_reruns_everything(tmp_path):
    (tmp_path / "case_01" / "baseline").mkdir(parents=True)
    (tmp_path / "case_01" / "baseline" / "verdicts.json").write_text("{}")
    pairs = run_all.pairs_to_run(["case_01"], ["baseline"], tmp_path, force=True)
    assert pairs == [("case_01", "baseline")]


def test_unknown_system_exits_4():
    assert run_all.main(["--systems", "nonsense"]) == 4


def test_all_known_systems_have_runners_or_fail_lazily():
    # baseline runners import cleanly today; agent/stratified import lazily later
    assert callable(run_all.make_runner("baseline"))
    assert callable(run_all.make_runner("baseline_plus"))
