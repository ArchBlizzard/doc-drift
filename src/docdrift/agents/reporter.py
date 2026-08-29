"""Reporter (T031): ledger -> audit.md meeting FR-007's checklist (a)-(e).

Structure is DETERMINISTIC — every row, evidence block, and count is rendered
straight from the ledger, so (a), (b), (c), (e) hold by construction and
`audit_checklist` can verify them mechanically. The model contributes only
the judgment parts of (d): a short executive summary and the severity call,
with a deterministic fallback if the call fails. FR-004 stays visible: every
holds/violated row shows the claimed vs computed values its executed check
produced.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from docdrift.config import MODEL_AGENT
from docdrift.llm import Transport, call_json
from docdrift.schemas import LedgerEntry, Verdict

SYSTEM_PROMPT = """You write the executive summary of a dataset-documentation audit for the data \
engineer who must act on it. You get one line per audited claim with its verdict and computed \
value. Reply with ONLY this JSON:
{"executive_summary": "<3-5 sentences: what the audit found, leading with the most consequential \
problem and what to fix in the documentation or data>", "most_severe_claim_id": "<claim id of \
the violation with the worst practical consequences>"}
Plain prose — no markdown, no hedging boilerplate. If nothing is violated, say the documentation \
checks out and name the weakest spot instead."""


class SummaryReply(BaseModel):
    executive_summary: str = Field(min_length=20)
    most_severe_claim_id: str


def _entry_digest(entries: list[LedgerEntry]) -> str:
    lines = []
    for e in entries:
        v = e.verdict_record
        tag = v.verdict.value + (f"({v.reason.value})" if v.reason else "")
        lines.append(f"{e.claim.id} [{e.claim.type.value}] {tag} "
                     f"computed={v.computed or '-'} :: {e.claim.quoted_span}")
    return "\n".join(lines)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_audit(case_id: str, model_id: str, entries: list[LedgerEntry],
                 executive_summary: str, most_severe_id: str, generated_at: str) -> str:
    counts = {v: sum(e.verdict_record.verdict is v for e in entries) for v in Verdict}
    violated = [e for e in entries if e.verdict_record.verdict is Verdict.violated]
    severe = next((e for e in violated if e.claim.id == most_severe_id),
                  violated[0] if violated else None)

    lines = [
        f"# Data card audit — {case_id}",
        "",
        f"Run: {generated_at} · model: {model_id} · claims audited: {len(entries)}",
        "",
        "## Executive summary",
        "",
        f"**{counts[Verdict.violated]} violated · {counts[Verdict.holds]} hold · "
        f"{counts[Verdict.unverifiable]} unverifiable.**"
        + (f" Most severe violation: **{severe.claim.id}** — \"{severe.claim.quoted_span}\"."
           if severe else " No violations found."),
        "",
        executive_summary.strip(),
        "",
        "## Per-claim verdicts",
        "",
        "| # | claim (quoted from the card) | type | verdict | claimed | computed |",
        "|---|---|---|---|---|---|",
    ]
    for i, e in enumerate(entries, 1):
        v = e.verdict_record
        verdict = v.verdict.value + (f" ({v.reason.value})" if v.reason else "")
        lines.append(
            f"| {i} | {_md_escape(e.claim.quoted_span)} | {e.claim.type.value} "
            f"| {verdict} | {_md_escape(v.claimed or '—')} | {_md_escape(v.computed or '—')} |")

    if violated:
        lines += ["", "## Evidence for violations", ""]
        for e in violated:
            lines.append(f"### {e.claim.id} — {_md_escape(e.claim.quoted_span)}")
            lines.append("")
            lines.append(f"Computed: `{e.verdict_record.computed}`")
            rows = e.execution.evidence_rows if e.execution else []
            if rows:
                cols = list(rows[0].keys())
                lines.append("")
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("|" + "---|" * len(cols))
                for r in rows[:5]:
                    lines.append("| " + " | ".join(_md_escape(str(r.get(c, ""))) for c in cols) + " |")
            else:
                lines.append("")
                lines.append("*(aggregate violation — the computed value above is the evidence; "
                             "no row-level exemplars apply)*")
            lines.append("")

    unverifiable = [e for e in entries if e.verdict_record.verdict is Verdict.unverifiable]
    if unverifiable:
        lines += ["", "## Abstentions", ""]
        for e in unverifiable:
            lines.append(f"- **{e.claim.id}** ({e.verdict_record.reason.value}): "
                         f"{_md_escape(e.claim.quoted_span)}")
    lines.append("")
    return "\n".join(lines)


async def write_audit(
    out_path: Path, case_id: str, model_id: str, entries: list[LedgerEntry],
    generated_at: str, *, model: str = MODEL_AGENT,
    log_path: Path | None = None, transport: Transport | None = None,
) -> None:
    counts = {v.value: sum(e.verdict_record.verdict is v for e in entries) for v in Verdict}
    try:
        reply, _ = await call_json(
            SummaryReply, SYSTEM_PROMPT,
            f"CASE: {case_id}\nVERDICT COUNTS: {counts}\n\nCLAIMS:\n{_entry_digest(entries)}",
            model=model, label=f"report:{case_id}", log_path=log_path, transport=transport)
        summary, severe_id = reply.executive_summary, reply.most_severe_claim_id
    except Exception:  # deterministic fallback keeps the audit shippable
        violated = [e.claim.id for e in entries if e.verdict_record.verdict is Verdict.violated]
        summary = (f"The audit checked {len(entries)} documented claims against the full data "
                   f"file: {counts['violated']} are violated, {counts['holds']} hold, and "
                   f"{counts['unverifiable']} could not be verified. Review the violations "
                   f"below and correct the data card or the data.")
        severe_id = violated[0] if violated else ""
    audit = render_audit(case_id, model_id, entries, summary, severe_id, generated_at)
    out_path.write_text(audit, encoding="utf-8", newline="\n")


def audit_checklist(audit_md: str, entries: list[LedgerEntry]) -> list[str]:
    """Mechanical FR-007 verification. Returns a list of failures (empty = pass)."""
    failures = []
    # (a) one row per claim with claimed & computed for holds/violated
    for e in entries:
        if _md_escape(e.claim.quoted_span) not in audit_md:
            failures.append(f"(a) missing row for {e.claim.id}")
        v = e.verdict_record
        if v.verdict in (Verdict.holds, Verdict.violated) and v.computed:
            if _md_escape(v.computed) not in audit_md:
                failures.append(f"(a) computed value missing for {e.claim.id}")
    # (b) evidence block for every violated claim
    for e in entries:
        if e.verdict_record.verdict is Verdict.violated:
            if f"### {e.claim.id}" not in audit_md:
                failures.append(f"(b) no evidence block for violated {e.claim.id}")
    # (c) enum reason for every unverifiable claim
    for e in entries:
        v = e.verdict_record
        if v.verdict is Verdict.unverifiable:
            if f"({v.reason.value})" not in audit_md:
                failures.append(f"(c) missing reason for {e.claim.id}")
    # (d) executive summary with per-class counts and the most severe violation
    counts = {v: sum(e.verdict_record.verdict is v for e in entries) for v in Verdict}
    header = (f"**{counts[Verdict.violated]} violated · {counts[Verdict.holds]} hold · "
              f"{counts[Verdict.unverifiable]} unverifiable.**")
    if header not in audit_md:
        failures.append("(d) per-class counts line missing or wrong")
    if "## Executive summary" not in audit_md:
        failures.append("(d) executive summary section missing")
    if counts[Verdict.violated] and "Most severe violation:" not in audit_md:
        failures.append("(d) most severe violation not named")
    # (e) no verdict rows beyond the ledger — count only the per-claim table
    section = audit_md.split("## Per-claim verdicts", 1)[-1].split("\n## ", 1)[0]
    table_rows = re.findall(r"^\| \d+ \|", section, flags=re.MULTILINE)
    if len(table_rows) != len(entries):
        failures.append(f"(e) table has {len(table_rows)} rows for {len(entries)} ledger entries")
    return failures
