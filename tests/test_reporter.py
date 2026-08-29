"""T031 acceptance: the FR-007 checklist (a)-(e) passes mechanically on
rendered audits — including evidence-less aggregate violations and the
deterministic fallback path — and catches doctored audits."""

import json

import anyio
import pytest

from docdrift.agents.reporter import audit_checklist, render_audit, write_audit
from docdrift.llm import RawReply
from docdrift.schemas import (
    Check, CheckStatus, Claim, ClaimType, ExecutionResult, LedgerEntry, Verdict, VerdictRecord,
)


def entry(cid, type_, span, verdict, *, reason=None, computed=None, rows=None):
    claim = Claim(id=cid, case_id="case_77", type=type_, quoted_span=span,
                  span_start=0, span_end=len(span))
    check = execution = None
    if verdict in ("holds", "violated"):
        check = Check(claim_id=cid, source_code="def check(df): ...", attempt=1,
                      status=CheckStatus.gate_passed)
        execution = ExecutionResult(claim_id=cid, passed=verdict == "holds",
                                    computed=computed, evidence_rows=rows or [],
                                    duration_ms=5)
    return LedgerEntry(
        claim=claim, check=check, execution=execution,
        verdict_record=VerdictRecord(claim_id=cid, verdict=verdict, reason=reason,
                                     claimed=span if verdict != "unverifiable" else None,
                                     computed=computed if verdict != "unverifiable" else None),
        model_id="m", tokens_in=1, tokens_out=1, wall_ms=1)


@pytest.fixture
def entries():
    return [
        entry("case_77-c01", ClaimType.row_count, "The table holds 3 rows.",
              "holds", computed="3"),
        entry("case_77-c02", ClaimType.null_rate, "No missing qty values.",
              "violated", computed="1 null",
              rows=[{"price": "5", "qty": ""}]),
        entry("case_77-c03", ClaimType.aggregate_stat, "The mean price is 4.0.",
              "violated", computed="mean=5.17"),  # aggregate: no row exemplars
        entry("case_77-c04", ClaimType.prose_unverifiable, "Collected by hand.",
              "unverifiable", reason="prose"),
    ]


def test_rendered_audit_passes_checklist(entries):
    audit = render_audit("case_77", "claude-test-1", entries,
                         "One null violates the card; the stated mean is also off.",
                         "case_77-c02", "2026-08-29T12:00:00")
    assert audit_checklist(audit, entries) == []
    assert "Most severe violation: **case_77-c02**" in audit
    assert "aggregate violation" in audit  # evidence-less violated claim covered


def test_checklist_catches_doctored_audit(entries):
    audit = render_audit("case_77", "claude-test-1", entries, "Summary text here.",
                         "case_77-c02", "2026-08-29T12:00:00")
    broken = audit.replace("### case_77-c03", "### removed")
    assert any("(b)" in f for f in audit_checklist(broken, entries))
    no_counts = audit.replace("**2 violated", "**9 violated")
    assert any("(d)" in f for f in audit_checklist(no_counts, entries))


def test_write_audit_llm_and_fallback_paths(entries, tmp_path):
    async def good(system_prompt, user_prompt, model):
        return RawReply(json.dumps({"executive_summary": "The qty null is the actionable "
                                    "problem; fix the card.", "most_severe_claim_id":
                                    "case_77-c02"}), "claude-test-1", 10, 5)

    out = tmp_path / "audit.md"
    anyio.run(lambda: write_audit(out, "case_77", "claude-test-1", entries,
                                  "2026-08-29T12:00:00", transport=good))
    assert audit_checklist(out.read_text(encoding="utf-8"), entries) == []

    async def broken(system_prompt, user_prompt, model):
        raise RuntimeError("no model")

    out2 = tmp_path / "audit2.md"
    anyio.run(lambda: write_audit(out2, "case_77", "claude-test-1", entries,
                                  "2026-08-29T12:00:00", transport=broken))
    text = out2.read_text(encoding="utf-8")
    assert audit_checklist(text, entries) == []  # deterministic fallback still ships
    assert "Review the violations" in text
