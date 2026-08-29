# Research & Spike Findings: DocDrift

Decisions recorded in spec-kit format: **Decision / Rationale / Alternatives considered**. Findings R1–R8 are settled; S1–S3 are open spikes scheduled as tasks.

---

## R1 — Project selection (multi-agent judge panel)

**Decision:** Build DocDrift — a dataset-audit agent that verifies data-card claims by writing, mutation-testing, and executing its own checks.

**Rationale:** Chosen by a 9-agent workflow on 2026-08-29: 5 ideation agents generated 10 candidate projects; a 3-judge panel scored each against the official micro1 rubric as a 48-hour solo build. DocDrift won (80.3/100 expected) because (a) the baseline gap is structural — a one-shot prompt physically cannot verify a 1M-row file, (b) mutation-testing LLM-written verifiers is a novel verification story aimed at the 30-point engineering row, and (c) a fully offline eval makes the 15-point reproducibility row nearly free.

**Alternatives considered:** DeFlake (flaky-test fixer with bug-twin harness, 79.3) and RefGuard (citation forensics, 79.0) — both strong; DeFlake risks synthetic flakes behaving differently on judges' machines; RefGuard depends on third-party registry APIs at runtime. Full leaderboard in [PLAN.md](../../PLAN.md) appendix.

## R2 — Authentication without API credits

**Decision:** All model calls go through `claude-agent-sdk` (Python), which reuses the local Claude Code subscription OAuth automatically when `ANTHROPIC_API_KEY` is unset. `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` is the portable variant. Judges may set an API key instead; precedence is API key > OAuth, same code path, no branch.

**Rationale:** The builder has a Claude subscription but no funded API key. Verified against official docs (code.claude.com: `authentication.md`, `agent-sdk/python.md`, `headless.md`): credential precedence rank #7 is stored subscription OAuth; `--bare` mode is the one mode that ignores OAuth (do not use it). Anthropic's restriction on subscription auth targets third parties reselling claude.ai login, not personal use of one's own subscription.

**Alternatives considered:** Raw `anthropic` SDK (rejected: requires funded key); headless `claude -p --output-format json` subprocess calls (kept as the documented fallback if the SDK misbehaves on Windows — same auth).

## R3 — Claim-to-gold alignment (the judges' predicted objection)

**Decision:** Gold claims are **character spans** in the data card, emitted by the corruption generator. Both systems must output the exact quoted substring per claim; primary alignment is span-overlap IoU ≥ 0.5 (deterministic). `rapidfuzz` token-set ratio ≥ 85 is a fallback only, and every fallback match is flagged in published results.

**Rationale:** The judge panel's top criticism of DocDrift was "fuzzy claim matching could get mushy." Span anchoring makes the primary path auditable, while cards stay natural prose (no numbered-statement lab conditioning).

**Alternatives considered:** Pure fuzzy text matching (rejected: unauditable); numbered-statement cards (rejected: makes eval look rigged; kept as a disclosed last-resort fallback if span-quoting compliance is low — see S2).

## R4 — Eval datasets & licensing

**Decision:** Commit six small real datasets in `data_src/` with per-file license notes and `SHA256SUMS`: UCI Adult (CC BY 4.0), Palmer Penguins (CC0), UCI Wine Quality red, UCI Online Retail II 40k-row sample, NYC Yellow Taxi Jan-2023 50k-row parquet sample (public domain), NOAA GSOD 2023 10-station sample. The 1M-row hard case is generated deterministically (numpy PCG64, seed 20260829) — never downloaded.

**Rationale:** Hackathon ground rule 07 (shareable public data) plus Constitution II (judge path needs no downloads). Small committed samples keep the clone lightweight; the only large file is generated locally in under a minute.

**Alternatives considered:** Download-on-demand scripts (rejected: clean-clone friction, link rot risk); fully synthetic everything (rejected: real datasets make the story credible and enable the real-Kaggle-card video kicker).

## R5 — Windows-honest sandboxing

**Decision:** The check executor is a fresh `subprocess` Python interpreter with temp cwd, 60s timeout, and 4KB-capped stdout. No `resource`-module rlimits (unavailable on Windows) — disclosed in README. Checks require no network by construction.

**Rationale:** Ground rule 04 (consequential actions sandboxed) at a level achievable on the builder's Windows 11 machine without container tooling; the checks are read-only pandas over local files, so the threat model is runaway execution, not exfiltration.

**Alternatives considered:** Docker (rejected: setup burden for judges and builder within 44h); in-process `exec` (rejected: no isolation, a crashing check would kill the run).

## R6 — Baseline fairness

**Decision:** Two published baselines: (1) card + dtypes + first 50 rows in one no-tools model call; (2) "baseline-plus" adding `describe(include='all')` + per-column top-10 value counts. The agent must beat both.

**Rationale:** Preempts the "strawman baseline" objection — baseline-plus is the best honest single-prompt attempt that fits context. Both share the agent's CLI shape, output schema, and scorer (spec FR-009).

**Alternatives considered:** Manual-process baseline (human with pandas — rejected: not reproducible by judges); tool-equipped single agent as baseline (rejected as *primary* since it blurs the comparison; the changelog's v0 checkpoint is the harness + both baselines, per SR-001).

## R7 — Determinism under subscription auth

**Decision:** Accept non-bit-identical model outputs (temperature is not exposed via Claude Code auth). Mitigate: deterministic scorer, seeded case generation, committed complete outputs of the submitted runs, resolved model IDs + token counts recorded per run.

**Rationale:** Reproducibility for judges means "reach the main result," not bit-identical transcripts; the brief's own examples assume this. Disclosed in spec Assumptions.

**Alternatives considered:** Raw API with temperature=0 (rejected: requires credits, and still not fully deterministic across API versions).

## R8 — Mutation gate policy

**Decision:** Per claim: build a ~20-row clean fixture (satisfies claim) and a mutant fixture (violates it). A check must pass clean AND fail mutant. Gate failure → one rewrite with the mutant diff in context; second failure → `unverifiable(check-failed)`. Vacuous-rate counter published.

**Rationale:** Kills the "green because the check can't fail" failure mode — the project's central insight and hot-take source (SC-005). Two strikes bounds cost and latency (Constitution IV's retry cap).

**Alternatives considered:** N mutants per claim (rejected for v2: one well-chosen mutant per claim type suffices; revisit only if vacuous checks survive the gate in practice); skipping the gate for "simple" claim types (rejected: the measured vacuous rate on simple types is part of the evidence).

---

## Open spikes (scheduled in tasks.md)

- **S1 — SDK auth smoke test on this machine** (T004): one no-tools `claude-agent-sdk` call with no API key set; record resolved model ID and latency here. *Risk if it fails:* fall back to `claude -p` subprocess per R2.
- **S2 — Span-quoting compliance** (gate G2, end of Phase 2): measure how often each system quotes exact card substrings. ≥95% → keep natural cards; below → add a one-line format-retry, and only as last resort restructure cards (disclosed).
- **S3 — Subscription usage-window pacing** (observed during Phase 3+ sweeps): record how much of a usage window one full sweep consumes; schedule the two heaviest sweeps immediately after window resets accordingly.
