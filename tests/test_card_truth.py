"""T007 acceptance: every holds-claim in every card manifest is true of the
committed data, and every quoted span (prose included) locates uniquely."""

import pytest

from card_truth import check_claim
from corruptions import locate_span
from docdrift.schemas import Verdict
from manifest import DATASETS, load_card, load_dataset, load_manifest


@pytest.fixture(scope="module")
def loaded():
    return {name: (load_card(name), load_dataset(name), load_manifest(name)) for name in DATASETS}


@pytest.mark.parametrize("name", list(DATASETS))
def test_every_span_locates_uniquely(loaded, name):
    card, _, claims = loaded[name]
    for claim in claims:
        start, end = locate_span(card, claim.quoted_span)
        assert card[start:end] == claim.quoted_span


@pytest.mark.parametrize("name", list(DATASETS))
def test_every_holds_claim_is_true(loaded, name):
    _, df, claims = loaded[name]
    failures = []
    for claim in claims:
        if claim.base_verdict is not Verdict.holds:
            continue
        ok, detail = check_claim(df, claim)
        if not ok:
            failures.append(f"{name}/{claim.id}: {detail}")
    assert not failures, "untrue card claims:\n" + "\n".join(failures)


@pytest.mark.parametrize("name", list(DATASETS))
def test_each_card_has_required_claim_mix(loaded, name):
    _, _, claims = loaded[name]
    holds = [c for c in claims if c.base_verdict is Verdict.holds]
    prose = [c for c in claims if c.base_verdict is Verdict.unverifiable]
    assert len(holds) >= 2, f"{name}: need >=2 checkable-true claims"
    assert len(prose) >= 1, f"{name}: need >=1 unverifiable prose claim"
