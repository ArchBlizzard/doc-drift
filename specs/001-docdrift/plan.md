# Implementation Plan: DocDrift

**Feature:** `001-docdrift` · **Spec:** [spec.md](spec.md) · **Tasks:** [tasks.md](tasks.md)
**Operational companion:** the root [PLAN.md](../../PLAN.md) holds the hackathon-facing hour-by-hour schedule, video script outline, risk register, and idea leaderboard. This document is the *technical* how; where the two overlap, this one governs implementation.

---

## Technical Context

| dimension | choice |
|---|---|
| Language | Python 3.12 |
| Model access | `claude-agent-sdk` (pinned in lockfile). Auth: `ANTHROPIC_API_KEY` → `CLAUDE_CODE_OAUTH_TOKEN` → stored Claude Code subscription login, unbranched (research R2). Fallback if SDK misbehaves on Windows: headless `claude -p --output-format json` subprocess, same auth. |
| Models | alias `sonnet` (extractor, synthesizer, reporter, baselines); alias `haiku` (synthesizer ablation). Resolved IDs recorded per run. |
| Key libraries | pandas 2.2.x, pyarrow ≥17, numpy (seeded generation), pydantic 2.x, rapidfuzz (fallback alignment only), rich (live trajectory display), pytest, PyYAML |
| Packaging | `pyproject.toml` + `uv` lockfile; pip fallback documented |
| Platform | Windows 11 primary (builder); commands documented for PowerShell and bash |
| Performance goal | full 12-case agent sweep ≤45 min wall clock (SC-003); per-check execution ≤60s timeout |
| Constraints | offline at runtime except model auth (FR-010); raw rows never in context beyond profile + ≤5 evidence rows (FR-006); LLM retry cap 2 (Constitution IV) |
| Scale | 12 cases, ~70 gold claims; largest file 1M rows ≈ 25MB parquet |

## Constitution Check

- *Evidence over assertion* → run ledger is the single source for every published number (Article I → FR-008).
- *Reproducibility first* → committed data + seeds, unbranched auth, deterministic scorer (Article II → FR-010/011/013).
- *Verified verification* → mutation gate before any trusted verdict (Article III → FR-004/005).
- *Deterministic orchestration* → asyncio pipeline, LLM only at 4 judgment points (Article IV).
- *Context discipline* → profile tool is the only data the model sees (Article V → FR-006).
- No violations to justify; no "Complexity Tracking" entries needed.

## Project Structure (target)

```
src/docdrift/
├── config.py            # model aliases, paths, retry caps, tolerance bands
├── schemas.py           # entities per data-model.md
├── llm.py               # Agent SDK wrapper: no-tools + tools modes, validated JSON, ≤2 retries, usage capture
├── orchestrator.py      # asyncio pipeline; per-claim fan-out, Semaphore(4)
├── ledger.py            # JSONL append, fingerprints, skip-settled resume
├── lessons.py           # loads lessons.md into synthesizer system prompt (v3)
├── agents/{extractor,synthesizer,reporter}.py   # prompts + call logic per stage
└── tools/{profile,executor,mutants}.py          # snapshot, sandboxed runner, gate fixtures
run_agent.py  run_baseline.py                    # CLIs per contracts/cli-contracts.md
eval/{make_cases,corruptions,score,run_all}.py + specs/ + gold/
data_src/  cases/(generated)  runs/(generated)  results/  trajectories/
tests/                                            # pytest: schemas, corruptions, scorer, executor, ledger, mutants
```

Full annotated tree with all submission files: root PLAN.md §2.

## Architecture (six stages, one asyncio pipeline)

`orchestrator.py` drives: **extract** (one Sonnet call → typed claims with spans) → per-claim fan-out under `Semaphore(4)`: **synthesize** (check source) → **mutation-gate** (pure Python fixtures; on vacuous → one rewrite call) → **execute** (sandboxed subprocess over the full file) → verdict into **ledger** → finally **report** (one Sonnet call → audit.md). Stage-by-stage capability rationale: root PLAN.md §3 table. The model is granted no filesystem/bash tools — only profile/executor/mutant results flow through the orchestrator (Article IV/V).

Design decisions with rationale and alternatives: [research.md](research.md) R2–R8. Entity definitions: [data-model.md](data-model.md). Interfaces: [contracts/](contracts/).

## Phase Outline (detail in tasks.md)

- **Phase 0 — Setup & spikes:** scaffold, schemas, auth smoke test (S1), datasets + checksums.
- **Phase 1 — Eval foundation first:** corruption operators, case generation, gold emission, deterministic scorer with fixture tests. *Gate G1: scorer green before any model-call code.*
- **Phase 2 — Baselines (changelog v0):** llm.py wrapper, both baselines, first scored numbers. *Gate G2: span-quoting compliance ≥95% (S2).*
- **Phase 3 — Agent core (v1):** profile/executor tools, extractor, synthesizer, ledger, orchestrator, e2e run, first agent sweep.
- **Phase 4 — Mutation gate (v2):** mutant fixtures, gate loop, vacuous-rate counter, cases 07–12 incl. hard case, full sweep.
- **Phase 5 — Memory & calibration (v3):** lessons.md loop, fuzzy-claim tolerance calibration, removed-experiment + Haiku ablations, final sweep.
- **Phase 6 — Report quality & kicker:** sign-worthy audit.md, real-Kaggle-card run for the video.
- **Phase 7 — Submission package:** README, CHANGELOG, REPRODUCE (verified from clean environment), DISCLOSURE, trajectories, video, submit.

Each phase ends at a working, committed state; full sweeps run only at changelog checkpoints to respect subscription usage windows (research S3).

## Progress Tracking

- [x] Research complete (R1–R8; S1–S3 scheduled)
- [x] Spec approved · [x] Data model · [x] Contracts · [x] Quickstart
- [ ] Phase 0–7 execution → tracked per-task in [tasks.md](tasks.md)
