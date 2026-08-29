import pytest
from pydantic import ValidationError

from docdrift.schemas import (
    Check,
    CheckStatus,
    Claim,
    ClaimType,
    ExecutionResult,
    GateOutcome,
    GoldClaim,
    GoldFile,
    LedgerEntry,
    MutantResult,
    OutputClaim,
    SystemOutput,
    Usage,
    Verdict,
    VerdictRecord,
)


def make_claim(**over):
    base = dict(
        id="case_01-c01", case_id="case_01", type=ClaimType.row_count,
        quoted_span="contains 344 rows", span_start=10, span_end=27,
    )
    base.update(over)
    return Claim(**base)


def test_claim_span_invariant_against_card():
    card = "The file contains 344 rows in total."
    claim = make_claim(span_start=9, span_end=26)
    claim.validate_against_card(card)  # card[9:26] == "contains 344 rows"
    bad = make_claim(span_start=0, span_end=17)
    with pytest.raises(ValueError, match="span invariant"):
        bad.validate_against_card(card)


def test_claim_rejects_inverted_span():
    with pytest.raises(ValidationError):
        make_claim(span_start=20, span_end=20)


def test_verdict_holds_requires_claimed_and_computed():
    with pytest.raises(ValidationError, match="claimed and computed"):
        VerdictRecord(claim_id="c", verdict=Verdict.holds)
    VerdictRecord(claim_id="c", verdict=Verdict.holds, claimed="344", computed="344")


def test_verdict_unverifiable_requires_reason_and_no_computed():
    with pytest.raises(ValidationError, match="requires a reason"):
        VerdictRecord(claim_id="c", verdict=Verdict.unverifiable)
    with pytest.raises(ValidationError, match="computed must be absent"):
        VerdictRecord(claim_id="c", verdict=Verdict.unverifiable, reason="prose", computed="x")
    VerdictRecord(claim_id="c", verdict=Verdict.unverifiable, reason="prose")


def test_verdict_reason_forbidden_on_holds():
    with pytest.raises(ValidationError, match="only applies to unverifiable"):
        VerdictRecord(claim_id="c", verdict=Verdict.holds, claimed="1", computed="1", reason="prose")


def test_mutant_result_consistency():
    with pytest.raises(ValidationError, match="gate_passed requires"):
        MutantResult(claim_id="c", attempt=1, clean_passed=True, mutant_failed=False,
                     outcome=GateOutcome.gate_passed, mutant_desc="null injected")
    MutantResult(claim_id="c", attempt=1, clean_passed=True, mutant_failed=True,
                 outcome=GateOutcome.gate_passed, mutant_desc="null injected")


def test_ledger_trusted_verdict_needs_executed_check():
    claim = make_claim()
    verdict = VerdictRecord(claim_id=claim.id, verdict=Verdict.violated, claimed="0", computed="3")
    with pytest.raises(ValidationError, match="require an executed check"):
        LedgerEntry(claim=claim, verdict_record=verdict, model_id="m", tokens_in=1, tokens_out=1, wall_ms=1)
    ok = LedgerEntry(
        claim=claim,
        check=Check(claim_id=claim.id, source_code="def check(df): ...", attempt=1, status=CheckStatus.gate_passed),
        execution=ExecutionResult(claim_id=claim.id, passed=False, computed="3", duration_ms=5),
        verdict_record=verdict, model_id="m", tokens_in=1, tokens_out=1, wall_ms=1,
    )
    assert ok.check.status is CheckStatus.gate_passed


def test_ledger_rejects_verdict_on_vacuous_check():
    claim = make_claim()
    verdict = VerdictRecord(claim_id=claim.id, verdict=Verdict.holds, claimed="1", computed="1")
    with pytest.raises(ValidationError, match="rejected_vacuous"):
        LedgerEntry(
            claim=claim,
            check=Check(claim_id=claim.id, source_code="x", attempt=2, status=CheckStatus.rejected_vacuous),
            execution=ExecutionResult(claim_id=claim.id, passed=True, computed="1", duration_ms=5),
            verdict_record=verdict, model_id="m", tokens_in=1, tokens_out=1, wall_ms=1,
        )


def test_gate_skipped_v1_entries_validate():
    claim = make_claim()
    entry = LedgerEntry(
        claim=claim,
        check=Check(claim_id=claim.id, source_code="x", attempt=1, status=CheckStatus.gate_skipped),
        execution=ExecutionResult(claim_id=claim.id, passed=True, computed="344", duration_ms=5),
        verdict_record=VerdictRecord(claim_id=claim.id, verdict=Verdict.holds, claimed="344", computed="344"),
        model_id="m", tokens_in=1, tokens_out=1, wall_ms=1,
    )
    assert entry.check.status is CheckStatus.gate_skipped


def test_execution_result_caps_evidence_rows():
    with pytest.raises(ValidationError):
        ExecutionResult(claim_id="c", passed=False, computed="x",
                        evidence_rows=[{}] * 6, duration_ms=1)


def test_gold_file_requires_six_claims_and_case_pattern():
    gc = GoldClaim(id="g1", span_start=0, span_end=5, quoted_span="hello",
                   type=ClaimType.schema, gold_verdict=Verdict.holds)
    with pytest.raises(ValidationError):
        GoldFile(case_id="case_1", dataset="d", seed=1, gold_claims=[gc] * 6)
    with pytest.raises(ValidationError):
        GoldFile(case_id="case_01", dataset="d", seed=1, gold_claims=[gc] * 5)
    GoldFile(case_id="case_01", dataset="d", seed=1, gold_claims=[gc] * 6)


def test_system_output_roundtrip():
    out = SystemOutput(
        case_id="case_01", system="baseline_stratified", model_id="claude-sonnet-5",
        claims=[OutputClaim(quoted_span="no nulls", verdict=Verdict.violated,
                            claimed="0", computed="3")],
        usage=Usage(input_tokens=100, output_tokens=50), wall_s=1.5,
    )
    again = SystemOutput.model_validate_json(out.model_dump_json())
    assert again.system.value == "baseline_stratified"
