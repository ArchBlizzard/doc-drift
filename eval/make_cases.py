"""Deterministic eval-case builder (T008).

`python eval/make_cases.py --all` (or `make data` / `.\\tasks.ps1 data`):
1. verifies data_src/SHA256SUMS (exit 4 on any mismatch — never build from
   tampered sources);
2. for each eval/specs/case_NN.yaml: loads the accurate card + data + manifest,
   applies the seeded corruption operators, and emits
   cases/case_NN/{data.(csv|parquet), datacard.md} + eval/gold/case_NN_gold.json;
3. relocates EVERY gold span in the FINAL card text (unique-substring search),
   so multiple card edits can never leave stale offsets.

Running twice yields byte-identical cards and gold files (T008 acceptance,
enforced by tests/test_make_cases.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import yaml

from corruptions import OP_REGISTRY, ManifestClaim, locate_span
from docdrift.config import CASES_DIR, DATA_SRC, GOLD_DIR, SPECS_DIR
from docdrift.schemas import CaseSpec, ClaimType, GoldClaim, GoldFile, Verdict
from manifest import dataset_suffix, load_card, load_dataset, load_manifest


def verify_checksums() -> None:
    sums_file = DATA_SRC / "SHA256SUMS"
    for line in sums_file.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256((DATA_SRC / name.strip()).read_bytes()).hexdigest()
        if actual != expected:
            print(f"checksum mismatch for data_src/{name.strip()}: {actual} != {expected}")
            sys.exit(4)


def load_spec(path: Path) -> CaseSpec:
    return CaseSpec(**yaml.safe_load(path.read_text(encoding="utf-8")))


def build_case(spec: CaseSpec, cases_dir: Path = CASES_DIR, gold_dir: Path = GOLD_DIR) -> GoldFile:
    card = load_card(spec.dataset)
    df = load_dataset(spec.dataset)
    man = {c.id: c for c in load_manifest(spec.dataset)}
    rng = np.random.default_rng(spec.seed)

    golds: list[GoldClaim] = []
    consumed: set[str] = set()
    for cor in spec.corruptions:
        if cor.op == "phantom_column":
            claim = ManifestClaim(
                id=cor.params["claim_id"], type=ClaimType.schema, quoted_span="template",
                params={"column": cor.params["column"]}, base_verdict=Verdict.holds,
            )
        else:
            claim = man[cor.claim]
        res = OP_REGISTRY[cor.op](card, df, claim, rng, cor.params)
        card, df = res.card_text, res.df
        golds.append(res.gold)
        consumed.update(res.consumed)

    for cid, claim in man.items():
        if cid in consumed:
            continue
        golds.append(GoldClaim(
            id=cid, span_start=0, span_end=1, quoted_span=claim.quoted_span,
            type=claim.type, gold_verdict=claim.base_verdict,
        ))

    # relocate every span in the FINAL card text
    relocated = []
    for g in golds:
        start, end = locate_span(card, g.quoted_span)
        relocated.append(g.model_copy(update={"span_start": start, "span_end": end}))
    relocated.sort(key=lambda g: g.span_start)

    gold_file = GoldFile(case_id=spec.case_id, dataset=spec.dataset,
                         seed=spec.seed, gold_claims=relocated)

    holds_n = sum(g.gold_verdict is Verdict.holds for g in relocated)
    unv_n = sum(g.gold_verdict is Verdict.unverifiable for g in relocated)
    if holds_n < spec.kept_true_claims or unv_n < spec.kept_unverifiable_claims:
        raise ValueError(
            f"{spec.case_id}: kept-claim floor not met "
            f"(holds {holds_n}/{spec.kept_true_claims}, unverifiable {unv_n}/{spec.kept_unverifiable_claims})"
        )

    case_dir = cases_dir / spec.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "datacard.md").write_text(card, encoding="utf-8", newline="\n")
    if dataset_suffix(spec.dataset) == ".parquet":
        df.to_parquet(case_dir / "data.parquet", index=False)
    else:
        df.to_csv(case_dir / "data.csv", index=False, lineterminator="\n")

    gold_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(gold_file.model_dump(mode="json", exclude_none=True), indent=2) + "\n"
    (gold_dir / f"{spec.case_id}_gold.json").write_text(payload, encoding="utf-8", newline="\n")
    return gold_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", help="case ids, e.g. case_01")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    verify_checksums()
    spec_paths = sorted(SPECS_DIR.glob("case_*.yaml"))
    if not args.all and args.cases:
        spec_paths = [p for p in spec_paths if p.stem in args.cases]
    if not spec_paths:
        print("no case specs selected (use --all or name cases)")
        return 3
    for path in spec_paths:
        spec = load_spec(path)
        gold = build_case(spec)
        counts = {v.value: sum(g.gold_verdict is v for g in gold.gold_claims) for v in Verdict}
        print(f"{spec.case_id} [{spec.dataset}] claims={len(gold.gold_claims)} {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
