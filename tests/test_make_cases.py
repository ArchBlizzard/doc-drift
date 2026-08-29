"""T008 acceptance: byte-identical regeneration, schema-valid gold, and — for
every data-target corruption — the claim really did flip from true to false
(guards against silent gold errors like a corruption that misses)."""

from pathlib import Path

import pandas as pd
import pytest

from card_truth import check_claim
from docdrift.schemas import Verdict
from make_cases import build_case, load_spec
from manifest import load_manifest

SPECS = sorted((Path(__file__).parents[1] / "eval" / "specs").glob("case_*.yaml"))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build every case twice into separate roots."""
    roots = []
    for run in ("a", "b"):
        root = tmp_path_factory.mktemp(f"gen_{run}")
        for spec_path in SPECS:
            build_case(load_spec(spec_path), cases_dir=root / "cases", gold_dir=root / "gold")
        roots.append(root)
    return roots


def test_specs_exist():
    assert len(SPECS) >= 6


@pytest.mark.parametrize("spec_path", SPECS, ids=[p.stem for p in SPECS])
def test_byte_identical_regeneration(built, spec_path):
    a, b = built
    case = spec_path.stem
    for rel in [f"gold/{case}_gold.json", f"cases/{case}/datacard.md"]:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"{rel} not deterministic"
    data_a = next((a / "cases" / case).glob("data.*"))
    data_b = next((b / "cases" / case).glob("data.*"))
    assert data_a.read_bytes() == data_b.read_bytes(), f"{case} data not deterministic"


@pytest.mark.parametrize("spec_path", SPECS, ids=[p.stem for p in SPECS])
def test_data_corruptions_really_flip_truth(built, spec_path):
    """For each target=data corruption, the manifest claim must be FALSE of the
    corrupted data (it was proven TRUE of the source by test_card_truth)."""
    a, _ = built
    spec = load_spec(spec_path)
    data_file = next((a / "cases" / spec.case_id).glob("data.*"))
    df = pd.read_parquet(data_file) if data_file.suffix == ".parquet" else pd.read_csv(data_file)
    man = {c.id: c for c in load_manifest(spec.dataset)}
    for cor in spec.corruptions:
        if cor.target != "data":
            continue
        ok, detail = check_claim(df, man[cor.claim])
        assert not ok, f"{spec.case_id}/{cor.claim}: corruption did not flip truth ({detail})"


@pytest.mark.parametrize("spec_path", SPECS, ids=[p.stem for p in SPECS])
def test_gold_floors(built, spec_path):
    import json
    a, _ = built
    spec = load_spec(spec_path)
    gold = json.loads((a / "gold" / f"{spec.case_id}_gold.json").read_text())
    verdicts = [g["gold_verdict"] for g in gold["gold_claims"]]
    assert len(verdicts) >= 6
    assert verdicts.count(Verdict.holds.value) >= spec.kept_true_claims
    assert verdicts.count(Verdict.unverifiable.value) >= spec.kept_unverifiable_claims
    assert verdicts.count(Verdict.violated.value) >= 3  # PLAN §5: 3-6 discrepancies per case
