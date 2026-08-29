# Feature Specification: DocDrift

**Feature ID:** `001-docdrift`
**Created:** 2026-08-29
**Status:** Approved (hackathon submission target: micro1 Agentic Workflows Hackathon, deadline 2026-08-31 18:00 UTC)
**Input:** "A dataset-audit agent that verifies every claim in a data card against the actual data by writing, mutation-testing, and executing its own checks."

---

## 1. User Scenarios & Testing

### Primary user story

A data engineer inherits a dataset — a Kaggle download, a UCI classic, an internal handoff — accompanied by a data card (README) making concrete claims: "no nulls in `patient_id`", "dates cover 2015–2023", "12 product categories". Today they either trust the card or spend half an hour writing ad-hoc pandas. With DocDrift they run one command against the case directory and receive an audit report they would sign their name to: every documented claim classified as **holds**, **violated** (with the computed value and offending rows), or **unverifiable** (with the reason), plus an executive summary.

### Secondary user story (the judge)

A hackathon judge clones the repo into a clean environment, authenticates with either their own API key or their own Claude subscription login, regenerates the eval cases from committed data and seeds, runs the baseline and the agent on the same cases, scores both, and reproduces the submitted comparison.

### Acceptance scenarios

1. **Violation with evidence.** Given a case whose card claims "no missing values in `customer_id`" and whose data contains 3 nulls in that column, When `run_agent.py` completes, Then the claim's verdict is `violated`, the audit shows the computed null count (3) and up to 5 offending rows, and the ledger contains the executed check's source and result.
2. **Confirmation is computed, not asserted.** Given a card claim that is true of the data (e.g., a stated row count), When the agent runs, Then the verdict is `holds` and the audit shows the computed value alongside the claimed value — with a corresponding executed-check entry in the ledger.
3. **Calibrated abstention.** Given a prose claim that cannot be checked against the file (e.g., "collected via phone surveys in 2019"), When the agent runs, Then the verdict is `unverifiable` with reason `prose`, and no check execution is attempted for it.
4. **The hard case.** Given the 1,000,000-row case whose only category-set violation begins after row ~810,000, When the agent runs, Then that claim's verdict is `violated`; the published eval tables document whether each baseline caught or missed the same claim.
5. **Mutation gate rejects vacuous checks.** Given a synthesized check that cannot fail (e.g., a dtype-coerced comparison that is always true), When the mutation gate runs it against the violating fixture, Then the check is rejected as vacuous and rewritten; if the rewrite also fails the gate, the claim's verdict is `unverifiable` with reason `check_failed` — never a trusted `holds`.
6. **Resumable runs.** Given a sweep interrupted mid-case and re-run, When the agent restarts, Then claims already settled in the ledger (same claim hash + data and card fingerprints) are skipped and their verdicts preserved — no flag required.
7. **Auth parity.** Given a machine with no `ANTHROPIC_API_KEY` but a logged-in Claude subscription, When any documented command runs, Then it exits 0 and produces outputs that validate against the same schemas, with the resolved model ID recorded in the ledger — and vice versa with only an API key. (If the builder has no funded key, the API-key direction is verified by credential-precedence tests and disclosed as such.)

### Edge cases

- **Phantom column:** card claims a property of a column absent from the data → `violated` with evidence `missing-column`.
- **Check crash or timeout:** executor failure → one retry; on second failure the claim is `unverifiable(execution_error)`, and the error is logged in the ledger.
- **Cardless or claimless card:** a card yielding zero extractable claims produces a valid report stating so, exit code 0, with a warning.
- **Fuzzy quantity claims:** "roughly 10% missing" is judged against a stated tolerance band (default ±2 percentage points absolute, disclosed in the report); outside the band → `violated` with the computed percentage.
- **Contradictory claims:** each claim is judged independently; contradictions surface naturally as one `holds` and one `violated`.

---

## 2. Requirements

### Functional requirements — the product

- **FR-001** The system MUST accept a case directory containing one tabular data file (CSV or Parquet) and one `datacard.md`, via `run_agent.py <case_id>` and `run_baseline.py <case_id>`.
- **FR-002** The system MUST extract typed claims from the data card, each carrying the exact quoted substring (span) from the card, with type ∈ {schema, row_count, range, null_rate, category_set, aggregate_stat, temporal_coverage, prose_unverifiable} (canonical serialized identifiers — matching data-model.md and the contracts).
- **FR-003** Every claim MUST receive exactly one verdict ∈ {holds, violated, unverifiable(reason)}.
- **FR-004** A `holds` or `violated` verdict MUST be backed by an executed check run against the **full** dataset, recording the computed value; unexecuted model opinion is never a verdict (Constitution III).
- **FR-005** Every synthesized check MUST pass the mutation gate before its result counts: pass on a clean fixture satisfying the claim AND fail on a mutant fixture violating it. Gate failure → one rewrite; second failure → `unverifiable(check_failed)`.
- **FR-006** Raw dataset rows MUST NOT enter the **agent pipeline's** model context except the profile snapshot (dtypes + head(20)) and ≤5 evidence rows per finding (Constitution V, as scoped by amendment v1.0.1 — baseline and ablation systems are exempt by design: their context budget is the experimental variable, and their full prompts are published as trajectories).
- **FR-007** The agent MUST produce `audit.md` satisfying ALL of: (a) one row per extracted claim, showing claimed and computed values for every holds/violated verdict; (b) 1–5 evidence rows for every violated claim; (c) an enum reason for every unverifiable claim; (d) an executive summary stating the count per verdict class and naming the most severe violation; (e) zero verdicts absent from the ledger. This checklist is the operational meaning of "a report a practitioner would sign."
- **FR-008** The agent MUST maintain an append-only run ledger capturing claim → check source → mutation-gate result → execution result → verdict → tokens/model-id/timing; re-runs MUST skip settled claims by default, keyed on claim hash + data and card fingerprints (a `--fresh` flag forces a full re-run).
- **FR-009** The baseline MUST use the identical CLI shape and output schema: a single no-tools model call given the card, dtypes, and first 50 rows. A second variant (`--plus`) additionally receives full-column summary statistics and top-10 value counts per column (concrete realization in plan.md). Both are scored and published.
- **FR-010** No component may require network access at runtime except model authentication/inference (Constitution II).
- **FR-011** The eval harness MUST build 12 cases from committed datasets + seeded corruption specs, with gold labels emitted by construction (each gold claim anchored to a character span); score with span-IoU-primary alignment; report macro-F1 over the three verdict classes as the primary metric; and publish complete per-claim results for every system. (Contingency floor under time pressure: 10 cases per Constitution VII; any cut is disclosed in the changelog with the affected cases named.)
- **FR-012** One hard case MUST be a ~1M-row deterministic synthetic dataset whose violations are structurally invisible to BOTH a head sample AND full-column summary statistics (`describe()` + top-10 value counts — the baseline-plus information budget): (a) a value-pattern violation planted only after row ~810k inside a high-cardinality column, ranking far below any top-10 value count, and (b) a fuzzy cross-column share claim off by ≥4 points, which no per-column summary can compute. *(Amended 2026-08-29 during T024: the original "rare category + fuzzy null-rate" pair proved visible to `describe()`'s unique/count rows — v0 evidence: baseline_plus 0.984. Recorded in CHANGELOG v2.)*
- **FR-013** Auth MUST work unbranched with either `ANTHROPIC_API_KEY` or a Claude subscription login / `CLAUDE_CODE_OAUTH_TOKEN` (Constitution II).

### Submission requirements — the hackathon deliverables

- **SR-001** `CHANGELOG.md` MUST contain one entry per meaningful iteration (v0 baseline-harness → v1 split pipeline → v2 mutation gate → v3 memory/calibration → final), each linked to the results evidence that motivated the next step, including at least one removed experiment with its numbers.
- **SR-002** `REPRODUCE.md` MUST be verified from an actual clean environment before submission and state exact commands, pinned versions, measured runtime, and measured token counts (with a $-estimate for API-key users).
- **SR-003** A ≤5-minute video MUST show: problem, baseline, one live agent run on the hard case, the final comparison, the changelog highlight, and one removed experiment.
- **SR-004** `trajectories/` MUST contain representative, followable trajectories for every agent role (extractor, synthesizer, gate loop, reporter), one baseline transcript, and coding-agent (Claude Code) build-session excerpts as the tool-use disclosure.
- **SR-005** Ground-rules compliance: per-dataset licenses documented; no credentials committed; every README/CHANGELOG claim evidence-linked (Constitution I, VI).

---

## 3. Key Entities

Claim, Check, MutantResult, ExecutionResult, VerdictRecord, LedgerEntry/RunLedger, GoldClaim, CaseSpec, ScoreRow — full field definitions in [data-model.md](data-model.md).

---

## 4. Success Criteria (measurable)

- **SC-001** Agent macro-F1 exceeds **both** baselines by ≥0.15 absolute on the 12-case suite (target; the actual gap is published whatever it is — Constitution VI).
- **SC-002** The agent catches both hard-case violations; each baseline's result on them is documented in the published tables.
- **SC-003** A full 12-case agent sweep completes in ≤45 minutes wall clock on the reference machine.
- **SC-004** A clean-environment run (fresh clone, fresh venv, either auth path) reproduces the main result end-to-end using only documented commands: case generation and scoring are byte-identical, the reproduced agent macro-F1 lands within ±0.05 absolute of the committed value, and the ordering agent > both baselines is preserved.
- **SC-005** The first-draft vacuous-check rate is measured and published, with before/after macro-F1 for the mutation gate (changelog v1→v2).

---

## 5. Out of Scope

Repairing the data or the card; non-tabular or multi-file/relational datasets; streaming data; any UI beyond the CLI and markdown reports; CI/scheduling integration; languages other than English data cards.

## 6. Assumptions & Dependencies

- Datasets fit on disk and in pandas on a 16GB machine (largest case ≈ 25MB parquet).
- Data cards are markdown prose; claims are textual statements within them.
- Model access exists via the builder's Claude subscription (verified — see [research.md](research.md) R2); judges may substitute an API key.
- Reference machine for SC-003 is the builder's Windows 11 machine; its CPU/RAM and the measured sweep runtime are published in `REPRODUCE.md`.
- Temperature is not exposed through Claude Code auth, so model outputs are not bit-identical across runs; the deterministic scorer plus committed submitted-run outputs preserve verifiability (see research.md R7).
