"""v1 agent pipeline (T019): extract -> per-claim (synthesize -> execute) ->
verdicts -> template audit.

Deterministic Python drives control flow; the model appears only at judgment
points (Constitution IV). v1 runs checks ungated — every Check is recorded
`gate_skipped`; the mutation gate lands in Phase 4 (T022) and flips the
invariant to gate_passed-only.

Resume is default (FR-008): extraction is cached per card fingerprint in
claims.json, and settled ledger entries skip synthesis + execution entirely,
so an interrupted sweep continues with zero repeated model calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import anyio
import pandas as pd

from docdrift import __version__
from docdrift.agents.extractor import extract_claims
from docdrift.agents.synthesizer import synthesize_check
from docdrift.config import CASES_DIR, CLAIM_SEMAPHORE, MODEL_AGENT, RUNS_DIR
from docdrift.ledger import Ledger, claim_key, fingerprint_bytes, fingerprint_text
from docdrift.llm import Transport
from docdrift.schemas import (
    Check,
    CheckStatus,
    Claim,
    ClaimType,
    ExecutionResult,
    LedgerEntry,
    OutputClaim,
    SystemOutput,
    Usage,
    Verdict,
    VerdictRecord,
)
from docdrift.tools.executor import ExecutionOutcome, run_check
from docdrift.tools.profile import snapshot

EXECUTION_RETRIES = 1  # spec edge case: one retry, then unverifiable(execution_error)


class CaseNotFound(FileNotFoundError):
    pass


@dataclass
class RunStats:
    extracted: int = 0
    settled_reused: int = 0
    synth_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _say(quiet: bool, text: str) -> None:
    if not quiet:
        print(text, flush=True)


async def _settle_claim(
    claim: Claim,
    *,
    profile_text: str,
    data_path: Path,
    model: str,
    log_path: Path,
    transport: Transport | None,
    stats: RunStats,
) -> LedgerEntry:
    if claim.type is ClaimType.prose_unverifiable:
        return LedgerEntry(
            claim=claim, check=None, execution=None,
            verdict_record=VerdictRecord(claim_id=claim.id, verdict=Verdict.unverifiable,
                                         reason="prose"),
            model_id="none", tokens_in=0, tokens_out=0, wall_ms=0,
        )

    source, meta = await synthesize_check(claim, profile_text, model=model,
                                          log_path=log_path, transport=transport)
    stats.synth_calls += 1
    stats.tokens_in += meta.input_tokens
    stats.tokens_out += meta.output_tokens
    check = Check(claim_id=claim.id, source_code=source, attempt=1,
                  status=CheckStatus.gate_skipped)  # v1: gate lands in T022

    outcome: ExecutionOutcome | None = None
    for _ in range(EXECUTION_RETRIES + 1):
        outcome = await anyio.to_thread.run_sync(run_check, source, data_path)
        if outcome.ok:
            break

    if not outcome.ok:
        execution = ExecutionResult(claim_id=claim.id, passed=False, computed="",
                                    duration_ms=outcome.duration_ms, error=outcome.error)
        verdict = VerdictRecord(claim_id=claim.id, verdict=Verdict.unverifiable,
                                reason="execution_error")
    else:
        execution = ExecutionResult(claim_id=claim.id, passed=bool(outcome.passed),
                                    computed=outcome.computed,
                                    evidence_rows=outcome.evidence_rows,
                                    duration_ms=outcome.duration_ms)
        verdict = VerdictRecord(
            claim_id=claim.id,
            verdict=Verdict.holds if outcome.passed else Verdict.violated,
            claimed=claim.quoted_span, computed=outcome.computed,
        )
    return LedgerEntry(claim=claim, check=check, execution=execution,
                       verdict_record=verdict, model_id=meta.model_id,
                       tokens_in=meta.input_tokens, tokens_out=meta.output_tokens,
                       wall_ms=meta.wall_ms)


async def _get_claims(
    case_id: str, card: str, profile_text: str, out_dir: Path,
    *, model: str, fresh: bool, transport: Transport | None, stats: RunStats,
) -> tuple[list[Claim], list[str]]:
    """Extraction with card-fingerprint cache (claims.json) for cheap resume."""
    cache_path = out_dir / "claims.json"
    card_fp = fingerprint_text(card)
    if not fresh and cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("card_fingerprint") == card_fp:
            return [Claim(**c) for c in cached["claims"]], []

    claims, metas, warnings = await extract_claims(
        case_id, card, profile_text, model=model,
        log_path=out_dir / "messages.jsonl", transport=transport)
    for meta in metas:
        stats.tokens_in += meta.input_tokens
        stats.tokens_out += meta.output_tokens
    cache_path.write_text(json.dumps({
        "card_fingerprint": card_fp,
        "claims": [c.model_dump(mode="json") for c in claims],
    }, indent=2), encoding="utf-8")
    return claims, warnings


def _write_audit(out_dir: Path, case_id: str, model_id: str,
                 entries: list[LedgerEntry]) -> None:
    """v1 template audit — replaced by the reporter agent in T031 (FR-007)."""
    lines = [f"# Data card audit — {case_id}", "",
             f"Run: {_now_iso()} · model: {model_id} · claims: {len(entries)}", "",
             "| # | claim | type | verdict | computed |", "|---|---|---|---|---|"]
    for i, e in enumerate(entries, 1):
        v = e.verdict_record
        verdict = v.verdict.value + (f" ({v.reason.value})" if v.reason else "")
        quoted = e.claim.quoted_span.replace("|", "\\|")
        lines.append(f"| {i} | {quoted} | {e.claim.type.value} | {verdict} | {v.computed or ''} |")
    violated = [e for e in entries if e.verdict_record.verdict is Verdict.violated
                and e.execution and e.execution.evidence_rows]
    if violated:
        lines += ["", "## Evidence for violations (≤5 rows each)", ""]
        for e in violated:
            lines.append(f"**{e.claim.quoted_span}**")
            lines.append("```json")
            lines.append(json.dumps(e.execution.evidence_rows, indent=2))
            lines.append("```")
            lines.append("")
    (out_dir / "audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def run_case(
    case_id: str,
    *,
    model: str = MODEL_AGENT,
    fresh: bool = False,
    out_root: Path = RUNS_DIR,
    cases_root: Path = CASES_DIR,
    transport: Transport | None = None,
    quiet: bool = False,
) -> Path:
    t0 = anyio.current_time()
    case_dir = cases_root / case_id
    card_path = case_dir / "datacard.md"
    if not card_path.is_file():
        raise CaseNotFound(f"case not found: {case_dir}")
    data_path = next(case_dir.glob("data.*"))
    card = card_path.read_text(encoding="utf-8")
    df = pd.read_parquet(data_path) if data_path.suffix == ".parquet" else pd.read_csv(data_path)
    profile_text = snapshot(df)
    del df  # profile is the only data the model sees; executor reads from disk

    out_dir = out_root / case_id / "agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "messages.jsonl"
    stats = RunStats()

    ledger = Ledger.open(
        out_dir / "ledger.jsonl", case_id=case_id,
        data_fingerprint=fingerprint_bytes(data_path.read_bytes()),
        card_fingerprint=fingerprint_text(card),
        sdk_version=f"docdrift {__version__}", started=_now_iso(), fresh=fresh)
    settled = ledger.settled()

    claims, warnings = await _get_claims(case_id, card, profile_text, out_dir,
                                         model=model, fresh=fresh,
                                         transport=transport, stats=stats)
    stats.extracted = len(claims)
    for w in warnings:
        _say(quiet, f"  ! {w}")

    entries: dict[str, LedgerEntry] = {}
    append_lock = anyio.Lock()
    sem = anyio.Semaphore(CLAIM_SEMAPHORE)

    async def worker(claim: Claim) -> None:
        key = claim_key(claim)
        if key in settled:
            entries[claim.id] = settled[key]
            stats.settled_reused += 1
            _say(quiet, f"  = {claim.id} {claim.type.value}: settled (resume)")
            return
        async with sem:
            entry = await _settle_claim(claim, profile_text=profile_text,
                                        data_path=data_path, model=model,
                                        log_path=log_path, transport=transport, stats=stats)
        async with append_lock:
            ledger.append(entry)
        entries[claim.id] = entry
        v = entry.verdict_record
        tag = v.verdict.value + (f"({v.reason.value})" if v.reason else "")
        _say(quiet, f"  * {claim.id} {claim.type.value}: {tag} computed={v.computed or '-'}")

    async with anyio.create_task_group() as tg:
        for claim in claims:
            tg.start_soon(worker, claim)

    ordered = [entries[c.id] for c in claims]
    model_ids = {e.model_id for e in ordered if e.model_id != "none"}
    model_id = sorted(model_ids)[0] if model_ids else model
    out_claims = []
    for e in ordered:
        v = e.verdict_record
        out_claims.append(OutputClaim(
            quoted_span=e.claim.quoted_span, span_start=e.claim.span_start,
            span_end=e.claim.span_end, verdict=v.verdict, reason=v.reason,
            claimed=v.claimed, computed=v.computed,
            evidence_rows=(e.execution.evidence_rows or None) if e.execution else None,
        ))
    output = SystemOutput(
        case_id=case_id, system="agent", model_id=model_id, claims=out_claims,
        usage=Usage(input_tokens=stats.tokens_in, output_tokens=stats.tokens_out),
        wall_s=round(anyio.current_time() - t0, 2),
    )
    (out_dir / "verdicts.json").write_text(
        output.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
    _write_audit(out_dir, case_id, model_id, ordered)
    _say(quiet, f"  -> {stats.extracted} claims, {stats.synth_calls} checks synthesized, "
                f"{stats.settled_reused} reused")
    return out_dir / "verdicts.json"
