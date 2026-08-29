# Tasks: DocDrift

**Input:** [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/), [research.md](research.md)
**Execution rules:** one task = one commit, landed when the task completes with tests green for touched files (Constitution VIII). `[P]` = parallelizable with its neighbors (different files, no dependency). Tasks with no file changes are skipped in the commit series and noted in the session summary. **Gates** block the next phase until met. Full sweeps (marked ⚡) run only at changelog checkpoints to respect subscription usage windows (research S3).

Deadline anchors (from root PLAN.md §8): Phase 0–2 ≈ H0–H7 · Phase 3–4 ≈ H14–H23 · Phase 5–6 ≈ H23–H28 · Phase 7 ≈ H34–H44. Scope fuse: if Phase 4 isn't green by H21, cut cases 10–11 (floor 10 cases), never the mutation gate (Constitution VII).

---

## Phase 0 — Setup & Spikes

- [x] **T001** Init repo + spec-kit docs (constitution, spec, research, data-model, contracts, plan, quickstart, tasks). *Done 2026-08-29 in commits `e7ed8cc`…*
- [ ] **T002** Scaffold project: `pyproject.toml` (deps per plan.md Technical Context, pinned) + uv lockfile, `src/docdrift/__init__.py`, `src/docdrift/config.py` (model aliases, paths, retry cap=2, tolerance bands, semaphore=4), `.env.example`, `Makefile` + `tasks.ps1`, `tests/conftest.py`.
  *Accept:* `uv sync` succeeds; `uv run python -c "import docdrift"` green.
  *Commit:* `chore: scaffold python project`
- [ ] **T003 [P]** `src/docdrift/schemas.py`: all entities per data-model.md incl. validation rules (span invariant, computed⟺verdict rule) + `tests/test_schemas.py`.
  *Accept:* pytest green; invalid combinations (e.g. `holds` without `computed`) rejected.
  *Commit:* `feat: core pydantic schemas with validation rules`
- [ ] **T004 [P]** Spike S1 — `scripts/spike_auth.py`: one no-tools `claude-agent-sdk` call with no API key set; print resolved model ID + latency; append outcome to research.md S1.
  *Accept:* response received on subscription auth (else: activate `claude -p` fallback per R2 and record the decision).
  *Commit:* `docs: record auth spike S1 outcome`
- [ ] **T005** Datasets: download the 6 sources into `data_src/` (one-time, builder-only network step), write `data_src/SHA256SUMS` + `data_src/README.md` with per-file license/provenance.
  *Accept:* checksums verify; total committed size < 30MB.
  *Commit:* `data: add source datasets with licenses and checksums`

## Phase 1 — Eval Foundation (cases before agent)

- [ ] **T006** `eval/corruptions.py`: the 8 operators (inject nulls · add/rename category · shift range · row-count drift · stale temporal coverage · perturb aggregate-stat · phantom column in card · fuzzy-% coarsening), each editing card OR data and emitting `GoldClaim` with span, per gold.schema.json + `tests/test_corruptions.py` (round-trip: applying an op then diffing reproduces its gold label/span).
  *Commit:* `feat: corruption operators with gold-by-construction`
- [ ] **T007 [P]** Author 6 accurate data cards `data_src/cards/*.md` (natural prose: overview, schema table, coverage, caveats; each containing ≥2 true-checkable and ≥1 unverifiable-prose claim).
  *Accept:* claims verified true by a throwaway pandas script (not committed).
  *Commit:* `data: author accurate data cards for all six datasets`
- [ ] **T008** `eval/make_cases.py` + `eval/specs/case_01..06.yaml`: build cases + gold; verify SHA256SUMS first (exit 4 on mismatch).
  *Accept:* two consecutive runs → byte-identical cards + gold; gold validates against gold.schema.json.
  *Commit:* `feat: deterministic case generation for cases 01-06`
- [ ] **T009** `eval/score.py`: span-IoU≥0.5 alignment, flagged rapidfuzz≥85 fallback, macro-F1 + per-class P/R, `results.md` + `per_claim.csv` writers + `tests/test_score.py` with hand-labeled fixtures incl. one tricky paraphrase and one unmatched-gold miss.
  *Accept:* pytest green; scorer is pure (no model imports). **GATE G1: scorer green before any model-call code.**
  *Commit:* `feat: deterministic span-anchored scorer`

## Phase 2 — Baselines (changelog v0)

- [ ] **T010** `src/docdrift/llm.py`: Agent SDK wrapper — no-tools mode (baselines) + tools mode (agent), pydantic-validated JSON with ≤2 retries, usage/model-id capture, auth precedence per cli-contracts.md.
  *Accept:* unit tests with stubbed transport; live smoke on one tiny prompt.
  *Commit:* `feat: model client wrapper with validated output`
- [ ] **T011** `run_baseline.py` (+`--plus`): prompts, verdicts.json per contract, prompt+reply saved as trajectory.
  *Accept:* output schema-validates on case_01.
  *Commit:* `feat: baseline and baseline-plus CLIs`
- [ ] **T012** ⚡ Run both baselines on cases 01–06, score → `results/v0.md`; measure span-quoting compliance; write CHANGELOG v0 entry with numbers.
  *Accept:* **GATE G2: span compliance ≥95%**, else add format-retry to prompts (and only as a disclosed last resort restructure cards — research S2).
  *Commit:* `eval: v0 baseline results and changelog entry`

## Phase 3 — Agent Core (changelog v1)

- [ ] **T013 [P]** `src/docdrift/tools/profile.py`: dtypes + head(20) snapshot (the only raw data the model ever sees) + test.
  *Commit:* `feat: profile snapshot tool`
- [ ] **T014 [P]** `src/docdrift/tools/executor.py`: sandboxed subprocess check runner (fresh interpreter, temp cwd, 60s timeout, 4KB stdout cap) + `tests/test_executor.py` covering timeout, crash, and evidence-row capping.
  *Commit:* `feat: sandboxed check executor`
- [ ] **T015** `src/docdrift/agents/extractor.py`: card → typed claims with exact spans; prose → `prose_unverifiable` + test against case_01's card.
  *Commit:* `feat: claim extractor agent`
- [ ] **T016** `src/docdrift/agents/synthesizer.py`: claim → self-contained `check(df)` source string (contract per data-model.md Check).
  *Commit:* `feat: check synthesizer agent`
- [ ] **T017 [P]** `src/docdrift/ledger.py`: JSONL append, data/card fingerprints, skip-settled resume + `tests/test_ledger.py`.
  *Commit:* `feat: run ledger with resume`
- [ ] **T018** `src/docdrift/orchestrator.py` + `run_agent.py`: wire extract → per-claim (synthesize → execute) → verdicts under Semaphore(4); minimal template `audit.md` (reporter agent comes in T031). *Mutation gate lands in Phase 4 — until then checks execute ungated and the ledger marks them `gate: skipped(v1)`.*
  *Accept:* `run_agent.py case_01` end-to-end green; every holds/violated verdict has an executed check in the ledger.
  *Commit:* `feat: v1 agent pipeline end-to-end`
- [ ] **T019** ⚡ v1 sweep on cases 01–06 + score; CHANGELOG v1 entry (expect: hallucinated confirmations gone, but some vacuous-green verdicts — the motivation for v2).
  *Commit:* `eval: v1 agent results and changelog entry`

## Phase 4 — Mutation Gate (changelog v2) — the submission's core

- [ ] **T020** `src/docdrift/tools/mutants.py`: per-claim-type clean + mutant fixture builders (~20 rows) + `tests/test_mutants.py` (for each claim type: a known-good check passes clean and fails mutant; a known-vacuous check is caught).
  *Commit:* `feat: mutation-gate fixture builders`
- [ ] **T021** Gate loop in orchestrator: draft → gate → (vacuous → one rewrite with mutant diff → gate) → two strikes = `unverifiable(check_failed)`; vacuous-rate counter into ledger (SC-005 evidence).
  *Accept:* acceptance scenario 5 reproduced by a seeded test.
  *Commit:* `feat: mutation gate with two-strike policy`
- [ ] **T022 [P]** `eval/specs/case_07..11.yaml` + generation (second corruption draws over the six datasets).
  *Commit:* `feat: eval cases 07-11`
- [ ] **T023** Hard case: 1M-row synthetic transactions generator (PCG64 seed 20260829; `REFUND_X` ×173 after row ~810k; coupon_id nulls 14.2% vs claimed "roughly 10%") + `eval/specs/case_12.yaml` + its card.
  *Accept:* generates in ≤1 min; violations verified by direct pandas in tests.
  *Commit:* `feat: 1M-row hard case generator`
- [ ] **T024** ⚡ Full v2 sweep — all 3 systems × 12 cases → `results/v2.md`; CHANGELOG v2 entry with measured vacuous rate + two concrete vacuous-check exhibits + v1→v2 F1 delta.
  *Commit:* `eval: v2 full-suite results and changelog entry`

## Phase 5 — Memory & Calibration (changelog v3)

- [ ] **T025** `src/docdrift/lessons.py` + `lessons.md` loop: post-eval pitfall entries injected into the synthesizer prompt; report retries-per-claim trend across case order.
  *Commit:* `feat: lessons memory for check synthesis`
- [ ] **T026** Abstention calibration: tolerance bands for fuzzy-% claims in config, extractor/synthesizer prompt updates.
  *Commit:* `feat: calibrated abstention for fuzzy claims`
- [ ] **T027 [P]** Removed experiment (SR-001): stratified-sample context-stuffing baseline variant; run on all cases; record numbers; CHANGELOG "removed" entry explaining what it taught.
  *Commit:* `eval: stratified-sampling experiment (removed) with evidence`
- [ ] **T028 [P]** Haiku-synthesizer ablation; keep as cost-optimized default if F1 holds, else write up as second removed experiment — either way a changelog entry with numbers.
  *Commit:* `eval: haiku synthesizer ablation`
- [ ] **T029** ⚡ Final sweep → `results/final.md` + per_claim.csv; CHANGELOG v3/final entry.
  *Commit:* `eval: final results`

## Phase 6 — Report Quality & Kicker

- [ ] **T030** `src/docdrift/agents/reporter.py`: ledger → sign-worthy `audit.md` (per-claim table claimed-vs-computed, evidence rows, abstention reasons, executive summary); replace T018's template.
  *Accept:* SC-review against spec FR-007 wording on two real audits.
  *Commit:* `feat: reporter agent for sign-worthy audits`
- [ ] **T031** Run DocDrift on one real, unmodified Kaggle data card + data (video kicker); save its ledger + audit under `trajectories/`.
  *Commit:* `demo: real-world kaggle data card run`

## Phase 7 — Submission Package

- [ ] **T032** `README.md`: intended user, bottleneck, why it matters (hackathon README requirements), architecture, results table, main failure mode + hot take (candidates in root PLAN.md §11 — pick the one the evidence supports).
  *Commit:* `docs: submission README`
- [ ] **T033 [P]** Finalize `CHANGELOG.md` (v0→final + removed experiments, every entry evidence-linked — SR-001).
  *Commit:* `docs: finalize improvement changelog`
- [ ] **T034** `REPRODUCE.md` from quickstart.md + **verified clean-environment run** (fresh clone, fresh venv, second Windows account or fresh shell with cleared env; either auth path); fill measured runtime + token counts from ledgers (SR-002/SC-004).
  *Commit:* `docs: verified reproduction guide`
- [ ] **T035 [P]** `DISCLOSURE.md` + curate `trajectories/`: agent runs for case_04 + case_12, one baseline transcript, Claude Code build-session excerpts (SR-004; tool-disclosure rule).
  *Commit:* `docs: agent trajectories and tool disclosure`
- [ ] **T036** Video: script per root PLAN.md §8 H37–H40 beat list; record ≤5 min. *(No repo file changes beyond `video/script.md` — commit the script only.)*
  *Commit:* `docs: video script`
- [ ] **T037** Hard buffer: fix whatever T034/T036 surfaced; ⚡ re-run final sweep only if code changed after T029.
  *Commit:* (only if changes) `fix: post-rehearsal corrections`
- [ ] **T038** Package + submit before H43. *(No file changes — noted in summary, not committed.)*

---

## Dependency notes

T002 → everything · T006 → T008 → {T012, T019, T024} · T009 gates all scoring · T010 → {T011, T015, T016, T030} · T014+T016 → T018 · T020 → T021 → T024 · T023 → T024 · T029 → {T032, T033, T034} · T030 → T031 → T036.
Parallel-friendly clusters: {T003, T004} · {T006, T007} · {T013, T014, T017} · {T022, T023} · {T027, T028} · {T033, T035}.
