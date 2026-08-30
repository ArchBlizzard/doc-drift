# Tasks: DocDrift

**Input:** [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/), [research.md](research.md)
**Execution rules:** one task = one commit, landed when the task completes with tests green for touched files (Constitution VIII). `[P]` = parallelizable with its neighbors (different files, no dependency). Tasks with no file changes are skipped in the commit series and noted in the session summary. **Gates** block the next phase until met. Full sweeps (marked ⚡) run only at changelog checkpoints to respect subscription usage windows (research S3).

Deadline anchors (from root PLAN.md §8): Phase 0–2 ≈ H0–H7 · Phase 3–4 ≈ H14–H23 · Phase 5–6 ≈ H23–H28 · Phase 7 ≈ H34–H44. Scope fuse: if Phase 4 isn't green by H21, cut cases 10–11 (floor 10 cases, disclosed in the changelog per FR-011), never the mutation gate (Constitution VII).

---

## Phase 0 — Setup & Spikes

- [x] **T001** Init repo + spec-kit docs (constitution, spec, research, data-model, contracts, plan, quickstart, tasks). *Done 2026-08-29.*
- [x] **T002** Scaffold project: `pyproject.toml` (deps per plan.md Technical Context, pinned; `dev` extra with pytest) + uv lockfile, `src/docdrift/__init__.py`, `src/docdrift/config.py` (model aliases, paths, retry cap=2, tolerance bands, semaphore=4), `.env.example`, `Makefile` + `tasks.ps1`, `tests/conftest.py`.
  *Accept:* `uv sync` succeeds; `uv run python -c "import docdrift"` green.
  *Commit:* `chore: scaffold python project`
- [x] **T003 [P]** `src/docdrift/schemas.py`: all entities per data-model.md incl. validation rules (span invariant, computed⟺verdict rule, gate_skipped-only-in-v1 note) + `tests/test_schemas.py`.
  *Accept:* pytest green; invalid combinations (e.g. `holds` without `computed`) rejected.
  *Commit:* `feat: core pydantic schemas with validation rules`
- [x] **T004 [P]** Spike S1 — `scripts/spike_auth.py`: one no-tools `claude-agent-sdk` call with no API key set; print resolved model ID + latency; append outcome to research.md S1.
  *Accept:* response received on subscription auth (else: activate `claude -p` fallback per R2 and record the decision).
  *Commit:* `docs: record auth spike S1 outcome`
- [x] **T005** Datasets: download the 6 sources into `data_src/` (one-time, builder-only network step), write `data_src/SHA256SUMS` + `data_src/README.md` with per-file license/provenance. Any unreachable source is substituted with a comparable licensed dataset and the substitution recorded in research.md R4.
  *Accept:* checksums verify; total committed size < 30MB.
  *Commit:* `data: add source datasets with licenses and checksums`

## Phase 1 — Eval Foundation (cases before agent)

- [x] **T006** `eval/corruptions.py`: the 8 operators (inject nulls · add/rename category · shift range · row-count drift · stale temporal coverage · perturb aggregate-stat · phantom column in card · fuzzy-% coarsening), each editing card OR data and emitting `GoldClaim` with span, per gold.schema.json + `tests/test_corruptions.py` (round-trip: applying an op then diffing reproduces its gold label/span).
  *Accept:* pytest green for `tests/test_corruptions.py`, all 8 operators covered.
  *Commit:* `feat: corruption operators with gold-by-construction`
- [x] **T007 [P]** Author 6 accurate data cards `data_src/cards/*.md` (natural prose: overview, schema table, coverage, caveats; each containing ≥2 true-checkable and ≥1 unverifiable-prose claim) + `tests/test_card_truth.py` verifying every checkable claim against `data_src/` (committed — gold integrity is auditable, Constitution I).
  *Accept:* `tests/test_card_truth.py` green.
  *Commit:* `data: author accurate data cards with committed truth tests`
- [x] **T008** `eval/make_cases.py` + `eval/specs/case_01..06.yaml`: build cases + gold; verify SHA256SUMS first (exit 4 on mismatch).
  *Accept:* two consecutive runs → byte-identical cards + gold; gold validates against gold.schema.json.
  *Commit:* `feat: deterministic case generation for cases 01-06`
- [x] **T009** `eval/score.py`: span-IoU≥0.5 alignment, flagged rapidfuzz≥85 fallback, macro-F1 + per-class P/R, `results.md` + `per_claim.csv` writers + `tests/test_score.py` with hand-labeled fixtures incl. one tricky paraphrase and one unmatched-gold miss; exit 4 on missing/invalid gold (tested).
  *Accept:* pytest green; scorer is pure (no model imports). **GATE G1: scorer green before any model-call code.**
  *Commit:* `feat: deterministic span-anchored scorer`

## Phase 2 — Baselines (changelog v0)

- [x] **T010** `src/docdrift/llm.py`: Agent SDK wrapper — no-tools mode (baselines) + tools mode (agent), pydantic-validated JSON with ≤2 retries, usage/model-id capture, **full message-stream logging to `runs/<case>/<system>/messages.jsonl`** (system prompt, user content, raw reply per call — feeds SR-004), auth precedence per cli-contracts.md.
  *Accept:* unit tests with stubbed transport incl. credential-precedence test (`ANTHROPIC_API_KEY` > `CLAUDE_CODE_OAUTH_TOKEN` > stored login) and no-credential → exit 2; live smoke on one tiny prompt.
  *Commit:* `feat: model client wrapper with validated output and message logging`
- [x] **T011** `run_baseline.py` (+`--plus`): prompts, verdicts.json per contract, prompt+reply saved as trajectory; missing case dir → exit 3 (tested).
  *Accept:* output schema-validates on case_01; exit-3 test green.
  *Commit:* `feat: baseline and baseline-plus CLIs`
- [x] **T012** `eval/run_all.py` per cli-contracts.md: default all systems × all cases, `--systems` (incl. `baseline_stratified`)/`--cases`/`--force`, skips completed (case, system) pairs, invokes scorer at the end + test for the skip logic.
  *Accept:* pytest green; `run_all.py --systems baseline --cases case_01` produces `runs/` + `results/`.
  *Commit:* `feat: eval sweep runner`
- [x] **T013** ⚡ Run both baselines on cases 01–06 via run_all, score → `results/v0.md`; measure span-quoting compliance; write CHANGELOG v0 entry (harness + baselines) with numbers.
  *Accept:* `results/v0.md` committed with per-claim rows for both baselines; CHANGELOG entry links to it. **GATE G2: span compliance ≥95%**, else add format-retry to prompts (and only as a disclosed last resort restructure cards — research S2).
  *Commit:* `eval: v0 baseline results and changelog entry`

## Phase 3 — Agent Core (changelog v1)

- [x] **T014 [P]** `src/docdrift/tools/profile.py`: dtypes + head(20) snapshot (the only raw data the agent's model ever sees) + `tests/test_profile.py`.
  *Accept:* pytest green.
  *Commit:* `feat: profile snapshot tool`
- [x] **T015 [P]** `src/docdrift/tools/executor.py`: sandboxed subprocess check runner (fresh interpreter, temp cwd, 60s timeout, 4KB stdout cap) + `tests/test_executor.py` covering timeout, crash, and evidence-row capping.
  *Accept:* pytest green.
  *Commit:* `feat: sandboxed check executor`
- [x] **T016** `src/docdrift/agents/extractor.py`: card → typed claims with exact spans; prose → `prose_unverifiable`; + tests against case_01's card AND a claimless-card fixture (valid empty result, warning, exit 0 path).
  *Accept:* both tests green.
  *Commit:* `feat: claim extractor agent`
- [x] **T017** `src/docdrift/agents/synthesizer.py`: claim → self-contained `check(df)` source string honoring the Check contract (verify referenced columns exist → `passed=False, computed="missing-column"` instead of raising).
  *Accept:* on 3 fixture claims (row_count, null_rate, category_set) the emitted source compiles and `check(df)` returns a valid CheckOutput on a toy frame; phantom-column fixture returns missing-column, not an exception.
  *Commit:* `feat: check synthesizer agent`
- [x] **T018 [P]** `src/docdrift/ledger.py`: JSONL append, data+card fingerprints, skip-settled-by-default resume + `tests/test_ledger.py`.
  *Accept:* pytest green.
  *Commit:* `feat: run ledger with default resume`
- [x] **T019** `src/docdrift/orchestrator.py` + `run_agent.py`: wire extract → per-claim (synthesize → execute) → verdicts under Semaphore(4); minimal template `audit.md` (reporter agent comes in T031); rich live-progress display (the video's visual); executor crash/timeout retried once → `unverifiable(execution_error)` (tested); prose claims skip synthesis entirely (ledger holds no Check entries for them — tested); v1 checks recorded as `gate_skipped`; missing case dir → exit 3; `--fresh` flag.
  *Accept:* `run_agent.py case_01` end-to-end green; every holds/violated verdict has an executed check in the ledger; retry/prose/exit-3 tests green.
  *Commit:* `feat: v1 agent pipeline end-to-end`
- [x] **T020** ⚡ v1 sweep on cases 01–06 + score; CHANGELOG v1 entry.
  *Accept:* `results/v1.md` committed with per-claim rows for all systems run; CHANGELOG entry links to it.
  *Commit:* `eval: v1 agent results and changelog entry`

## Phase 4 — Mutation Gate (changelog v2) — the submission's core

- [x] **T021** `src/docdrift/tools/mutants.py`: per-claim-type clean + mutant fixture builders (~20 rows) + `tests/test_mutants.py` (for each claim type incl. schema/phantom-column: a known-good check passes clean and fails mutant; a known-vacuous check is caught).
  *Accept:* pytest green, every claim type covered.
  *Commit:* `feat: mutation-gate fixture builders`
- [x] **T022** Gate loop in orchestrator: draft → gate → (vacuous → one rewrite with mutant diff → gate) → two strikes = `unverifiable(check_failed)`; vacuous-rate counter into ledger (SC-005 evidence); from here on, holds/violated verdicts require `gate_passed`.
  *Accept:* acceptance scenario 5 reproduced by a seeded test.
  *Commit:* `feat: mutation gate with two-strike policy`
- [x] **T023 [P]** `eval/specs/case_07..11.yaml` only (second corruption draws over five datasets; runs the existing generator — no generator-code changes, keeping [P] with T024 file-disjoint).
  *Accept:* `make_cases` twice yields byte-identical case_07..11 + gold, validating against gold.schema.json.
  *Commit:* `feat: eval cases 07-11`
- [x] **T024 [P]** Hard case: `eval/synth_transactions.py` (1M-row generator, PCG64 seed 20260829), invoked by make_cases for case_12 + `eval/specs/case_12.yaml` + its card. Violations per amended FR-012: 173 pattern-breaking coupon codes only after row ~810k (below top-10 value counts in a ~2,000-code column) + a fuzzy cross-column share claim (truth 14.2% vs "roughly 10%") that per-column summaries cannot compute.
  *Accept:* generates in ≤1 min; both violations verified by direct pandas in tests, including their invisibility to head samples and top-10 value counts.
  *Commit:* `feat: 1M-row hard case generator`
- [x] **T025** ⚡ Full v2 sweep — all 3 systems × 12 cases via run_all → `results/v2.md`; CHANGELOG v2 entry with measured vacuous rate + two concrete vacuous-check exhibits + v1→v2 F1 delta.
  *Accept:* `results/v2.md` + per_claim.csv committed for all three systems; vacuous rate recorded in the entry.
  *Commit:* `eval: v2 full-suite results and changelog entry`

## Phase 5 — Memory & Calibration (changelog v3)

- [x] **T026** `src/docdrift/lessons.py` + `lessons.md` loop: post-eval pitfall entries injected into the synthesizer prompt.
  *Accept:* retries-per-claim reported for first vs last case in the sweep output.
  *Commit:* `feat: lessons memory for check synthesis`
- [x] **T027** Abstention calibration: tolerance bands for fuzzy-% claims in config, extractor/synthesizer prompt updates.
  *Accept:* the fuzzy-claim edge case (±2pp band; 14.2% vs "roughly 10%" → violated) reproduced by test.
  *Commit:* `feat: calibrated abstention for fuzzy claims`
- [x] **T028 [P]** Removed experiment (SR-001): `baseline_stratified` context-stuffing variant; run on all cases via run_all; numbers into `results/removed_stratified.md` (changelog entry lands in T034 — keeps this file-disjoint from T029).
  *Accept:* numbers recorded under results/.
  *Commit:* `eval: stratified-sampling experiment (removed) with evidence`
- [x] **T029 [P]** Haiku-synthesizer ablation; numbers into `results/ablation_haiku.md`; keep as cost-optimized default only if F1 holds (changelog entry in T034).
  *Accept:* numbers recorded under results/.
  *Commit:* `eval: haiku synthesizer ablation`
- [x] **T030** ⚡ Final sweep → `results/final.md` + per_claim.csv.
  *Accept:* committed for all three systems; CHANGELOG v3/final entry links to it.
  *Commit:* `eval: final results`

## Phase 6 — Report Quality & Kicker

- [x] **T031** `src/docdrift/agents/reporter.py`: ledger → `audit.md` meeting FR-007's checklist (a)–(e); replace T019's template.
  *Accept:* checklist (a)–(e) passes on two real audits (scripted structural check).
  *Commit:* `feat: reporter agent meeting FR-007 checklist`
- [x] **T032** Run DocDrift on one real, unmodified public data card + data (video kicker) — dataset MUST have a permissive license; save ledger + audit + `PROVENANCE.md` (license, URL, access date) under `trajectories/kaggle_kicker/`. This demo run is explicitly out-of-contract (ad-hoc case id; no gold). *Executed against OpenML `credit-g` (Kaggle requires an API token; substitution disclosed in PROVENANCE.md). Found two genuine violations in the 1994 card: "Telephone (yes,no)" vs actual `none`/`yes` encoding, and 41 non-conforming guarantor values.*
  *Accept:* artifacts + provenance committed. ✓
  *Commit:* `demo: real-world data card run (openml credit-g)`

## Phase 7 — Submission Package

- [x] **T033** `README.md`: intended user, bottleneck, why it matters (hackathon README requirements), architecture, results table, main failure mode + hot take (candidates in root PLAN.md §11 — pick the one the evidence supports).
  *Accept:* every numeric claim has an adjacent repo-relative evidence link (Constitution I walk).
  *Commit:* `docs: submission README`
- [x] **T034** Finalize `CHANGELOG.md` (v0→final + removed stratified experiment + haiku ablation, every entry evidence-linked — SR-001).
  *Accept:* zero unlinked numbers across README + CHANGELOG (walk recorded in the commit message).
  *Commit:* `docs: finalize improvement changelog`
- [x] **T035** `REPRODUCE.md` from quickstart.md + **verified clean-environment run** (fresh clone, fresh venv, cleared env vars; both auth paths, or precedence-tests + disclosure for the API-key direction per scenario 7); fill measured runtime + token counts from ledgers; pin Claude Code CLI version; credential scan of tree AND history (gitleaks or grep for key patterns) with the clean result recorded.
  *Accept:* SC-004 tolerances stated; scan clean; measured numbers in place.
  *Commit:* `docs: verified reproduction guide`
- [x] **T036 [P]** `DISCLOSURE.md` + curate `trajectories/`: agent runs for case_04 + case_12 (ledger + messages.jsonl for extractor, synthesizer, gate loop, reporter), one baseline transcript, Claude Code build-session excerpts, and `trajectories/ideation/` (project-selection + audit workflow transcripts from the planning sessions) — SR-004.
  *Accept:* all four agent roles + baseline + coding-agent + ideation present; at least one mutation-gate rejection → rewrite episode included (swap in another case's run or a targeted single-claim run if the defaults contain none).
  *Commit:* `docs: agent trajectories and tool disclosure`
- [x] **T037** Video: script per root PLAN.md §8 H37–H40 (spec SR-003's six elements are authoritative); record.
  *Accept:* recorded video ≤5:00 containing all six SR-003 elements; only `video/script.md` is committed.
  *Commit:* `docs: video script`
- [ ] **T038** Hard buffer: fix whatever T035/T037 surfaced; ⚡ re-run final sweep only if code changed after T030.
  *Accept:* clean-clone rehearsal issues closed.
  *Commit:* (only if changes) `fix: post-rehearsal corrections`
- [ ] **T039** Feature freeze at H43; package, link-check, and submit during H43–H44 (nothing new after H43 — Constitution VII). *(No file changes — noted in summary, not committed.)*

---

## Dependency notes

T002 → everything · T003 → T006 · T005 → T007 · T006+T007 → T008 → {T013, T020, T025} · T009 gates all scoring · T010 → {T011, T016, T017, T031} · T011+T012 → T013 · T014+T015+T016+T017+T018 → T019 · T021 → T022 → T025 · T023+T024 → T025 · T030 → {T033, T034, T035} · T031 → T032 → T037.
Parallel-friendly clusters: {T003, T004} · {T006, T007} · {T014, T015, T018} · {T023, T024} · {T028, T029} · {T035→T036 overlap only in docs; T036 [P] with T037 prep}.
