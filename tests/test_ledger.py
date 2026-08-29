"""T018 acceptance: append/load roundtrip, fingerprint-keyed resume,
fresh-start, mismatch invalidation."""

from docdrift.ledger import Ledger, claim_key, fingerprint_text
from docdrift.schemas import (
    Check, CheckStatus, Claim, ClaimType, ExecutionResult, LedgerEntry, Verdict, VerdictRecord,
)


def make_claim(span="holds 3 rows"):
    return Claim(id="case_77-c01", case_id="case_77", type=ClaimType.row_count,
                 quoted_span=span, span_start=0, span_end=len(span), params={})


def make_entry(claim):
    return LedgerEntry(
        claim=claim,
        check=Check(claim_id=claim.id, source_code="def check(df): ...",
                    attempt=1, status=CheckStatus.gate_skipped),
        execution=ExecutionResult(claim_id=claim.id, passed=True, computed="3", duration_ms=5),
        verdict_record=VerdictRecord(claim_id=claim.id, verdict=Verdict.holds,
                                     claimed="3", computed="3"),
        model_id="m", tokens_in=10, tokens_out=5, wall_ms=100,
    )


def open_ledger(path, data_fp="d1", card_fp="c1", sdk="test", fresh=False):
    return Ledger.open(path, case_id="case_77", data_fingerprint=data_fp,
                       card_fingerprint=card_fp, sdk_version=sdk,
                       started="2026-08-29T12:00:00", fresh=fresh)


def test_roundtrip_and_resume(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    claim = make_claim()
    ledger.append(make_entry(claim))

    again = open_ledger(path)  # same fingerprints -> settled
    settled = again.settled()
    assert claim_key(claim) in settled
    assert settled[claim_key(claim)].verdict_record.verdict is Verdict.holds
    assert again.stats() == {"entries": 1, "tokens_in": 10, "tokens_out": 5,
                             "vacuous_rejections": 0}


def test_changed_card_fingerprint_invalidates(tmp_path):
    path = tmp_path / "ledger.jsonl"
    open_ledger(path).append(make_entry(make_claim()))
    assert open_ledger(path, card_fp="OTHER").settled() == {}


def test_changed_data_fingerprint_invalidates(tmp_path):
    path = tmp_path / "ledger.jsonl"
    open_ledger(path).append(make_entry(make_claim()))
    assert open_ledger(path, data_fp="OTHER").settled() == {}


def test_version_bump_invalidates_and_rotates(tmp_path):
    """A pipeline version bump must never reuse older-generation entries; the
    old ledger is preserved as .old for the trajectory archive."""
    path = tmp_path / "ledger.jsonl"
    open_ledger(path, sdk="docdrift 0.1.0").append(make_entry(make_claim()))
    bumped = open_ledger(path, sdk="docdrift 0.2.0")
    assert bumped.settled() == {}
    assert (tmp_path / "ledger.jsonl.old").exists()
    # and entries appended under the new header resume normally
    bumped.append(make_entry(make_claim()))
    assert len(open_ledger(path, sdk="docdrift 0.2.0").settled()) == 1


def test_fresh_discards(tmp_path):
    path = tmp_path / "ledger.jsonl"
    open_ledger(path).append(make_entry(make_claim()))
    assert open_ledger(path, fresh=True).settled() == {}


def test_claim_key_is_content_addressed():
    a, b = make_claim(), make_claim()
    b2 = make_claim("holds 4 rows")
    assert claim_key(a) == claim_key(b)
    assert claim_key(a) != claim_key(b2)
    assert fingerprint_text("x") != fingerprint_text("y")
