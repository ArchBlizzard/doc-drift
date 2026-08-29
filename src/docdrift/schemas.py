"""Pydantic entities per specs/001-docdrift/data-model.md.

Validation rules encoded here (the rest live in the orchestrator):
- span invariant helpers: span_end > span_start, quoted_span non-empty;
  `Claim.validate_against_card()` checks the slice equality against card text.
- computed present <=> verdict != unverifiable; unverifiable requires a reason.
- MutantResult.outcome must be consistent with its clean/mutant booleans.
- holds/violated ledger entries must carry an executed check that was not
  rejected (gate_passed required from v2 onward — enforced by the orchestrator,
  since v1 ledgers legitimately contain gate_skipped).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# --- enums -----------------------------------------------------------------

class ClaimType(str, Enum):
    schema = "schema"
    row_count = "row_count"
    range = "range"
    null_rate = "null_rate"
    category_set = "category_set"
    aggregate_stat = "aggregate_stat"
    temporal_coverage = "temporal_coverage"
    prose_unverifiable = "prose_unverifiable"


class Verdict(str, Enum):
    holds = "holds"
    violated = "violated"
    unverifiable = "unverifiable"


class UnverifiableReason(str, Enum):
    prose = "prose"
    check_failed = "check_failed"
    execution_error = "execution_error"


class CheckStatus(str, Enum):
    draft = "draft"
    gate_passed = "gate_passed"
    gate_skipped = "gate_skipped"  # v1 ledgers only; final product never emits it
    rejected_vacuous = "rejected_vacuous"
    rejected_error = "rejected_error"


class GateOutcome(str, Enum):
    gate_passed = "gate_passed"
    gate_skipped = "gate_skipped"
    vacuous = "vacuous"
    error = "error"


class System(str, Enum):
    baseline = "baseline"
    baseline_plus = "baseline_plus"
    baseline_stratified = "baseline_stratified"
    agent = "agent"


# --- core entities ---------------------------------------------------------

class Claim(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: str
    case_id: str
    type: ClaimType
    quoted_span: str = Field(min_length=1)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _span_order(self) -> "Claim":
        if self.span_end <= self.span_start:
            raise ValueError("span_end must be > span_start")
        return self

    def validate_against_card(self, card_text: str) -> None:
        """Span invariant: card[span_start:span_end] == quoted_span."""
        actual = card_text[self.span_start:self.span_end]
        if actual != self.quoted_span:
            raise ValueError(
                f"span invariant violated for {self.id}: "
                f"card slice {actual!r} != quoted_span {self.quoted_span!r}"
            )


class Check(BaseModel):
    claim_id: str
    source_code: str = Field(min_length=1)
    attempt: int = Field(ge=1, le=2)  # Constitution IV retry cap
    status: CheckStatus = CheckStatus.draft


class MutantResult(BaseModel):
    claim_id: str
    attempt: int = Field(ge=1, le=2)
    clean_passed: bool
    mutant_failed: bool
    outcome: GateOutcome
    mutant_desc: str

    @model_validator(mode="after")
    def _consistent(self) -> "MutantResult":
        if self.outcome == GateOutcome.gate_passed and not (self.clean_passed and self.mutant_failed):
            raise ValueError("gate_passed requires clean_passed AND mutant_failed")
        if self.outcome == GateOutcome.vacuous and self.mutant_failed:
            raise ValueError("vacuous outcome contradicts mutant_failed=True")
        return self


class ExecutionResult(BaseModel):
    claim_id: str
    passed: bool
    computed: str
    evidence_rows: list[dict[str, Any]] = Field(default_factory=list, max_length=5)  # FR-006
    duration_ms: int = Field(ge=0)
    error: str | None = None


class VerdictRecord(BaseModel):
    claim_id: str
    verdict: Verdict
    reason: UnverifiableReason | None = None
    claimed: str | None = None
    computed: str | None = None

    @model_validator(mode="after")
    def _rules(self) -> "VerdictRecord":
        if self.verdict == Verdict.unverifiable:
            if self.reason is None:
                raise ValueError("unverifiable verdict requires a reason")
            if self.computed is not None:
                raise ValueError("computed must be absent for unverifiable verdicts")
        else:
            if self.reason is not None:
                raise ValueError("reason only applies to unverifiable verdicts")
            if self.claimed is None or self.computed is None:
                raise ValueError("holds/violated require both claimed and computed (FR-004)")
        return self


class LedgerEntry(BaseModel):
    claim: Claim
    check: Check | None = None
    mutant_results: list[MutantResult] = Field(default_factory=list)
    execution: ExecutionResult | None = None
    verdict_record: VerdictRecord
    model_id: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    wall_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _trusted_verdicts_are_executed(self) -> "LedgerEntry":
        if self.verdict_record.verdict in (Verdict.holds, Verdict.violated):
            if self.execution is None or self.check is None:
                raise ValueError("holds/violated require an executed check in the entry (FR-004)")
            if self.check.status in (CheckStatus.draft, CheckStatus.rejected_vacuous, CheckStatus.rejected_error):
                raise ValueError(f"holds/violated cannot rest on a {self.check.status.value} check")
        return self


class RunLedgerHeader(BaseModel):
    case_id: str
    data_fingerprint: str
    card_fingerprint: str
    sdk_version: str
    started: str


# --- eval entities ---------------------------------------------------------

class GoldClaim(BaseModel):
    id: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
    quoted_span: str = Field(min_length=1)
    type: ClaimType
    gold_verdict: Verdict
    corruption_op: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _span_order(self) -> "GoldClaim":
        if self.span_end <= self.span_start:
            raise ValueError("span_end must be > span_start")
        return self


class GoldFile(BaseModel):
    case_id: str = Field(pattern=r"^case_[0-9]{2}$")
    dataset: str
    seed: int
    gold_claims: list[GoldClaim] = Field(min_length=6)


class CorruptionSpec(BaseModel):
    op: str
    target: str = Field(pattern=r"^(card|data)$")
    claim: str | None = None  # manifest claim id; None for phantom_column (template built from params)
    params: dict[str, Any] = Field(default_factory=dict)


class CaseSpec(BaseModel):
    case_id: str = Field(pattern=r"^case_[0-9]{2}$")
    dataset: str
    seed: int
    corruptions: list[CorruptionSpec]
    kept_true_claims: int = Field(ge=2)
    kept_unverifiable_claims: int = Field(ge=1)


# --- system output (contracts/verdicts.schema.json) ------------------------

class OutputClaim(BaseModel):
    quoted_span: str = Field(min_length=1)
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=1)
    verdict: Verdict
    reason: UnverifiableReason | None = None
    claimed: str | None = None
    computed: str | None = None
    evidence_rows: list[dict[str, Any]] | None = Field(default=None, max_length=5)


class Usage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class SystemOutput(BaseModel):
    case_id: str
    system: System
    model_id: str
    claims: list[OutputClaim]
    usage: Usage
    wall_s: float = Field(ge=0)
