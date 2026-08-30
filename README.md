# DocDrift

**A dataset-audit agent that verifies every claim in a data card against the actual data — by writing, mutation-testing, and executing its own checks.**

Built solo for the micro1 Agentic Workflows Hackathon (Aug 2026). Repo layout, specs, and the full task-by-task build history live in [`specs/001-docdrift/`](specs/001-docdrift/) and the commit log (one commit per task).

---

## Who has this problem, and why it matters

Data engineers and ML practitioners inherit datasets constantly — a Kaggle download, a UCI classic, an internal handoff — accompanied by a data card that asserts things: *"no missing values in `customer_id`"*, *"dates cover 2015–2023"*, *"12 categories"*. Documentation drifts from data constantly, and today the check is either skipped or a half-hour of ad-hoc pandas per dataset. The failure mode when it's skipped is silent: a pipeline filters on a documented label that no longer exists, a model trains on a category the card never mentioned, an analysis trusts a stated rate that's off by half.

It isn't hypothetical. Run on the **real, unmodified 1994 German Credit card** ([trajectories/kaggle_kicker/](trajectories/kaggle_kicker/)), DocDrift found that the documentation says `Telephone (yes,no)` while the data encodes `none`/`yes` — any filter written against the documented `no` label silently matches zero rows — plus 41 values outside the documented guarantor categories. Thirty years of users, and the card still lies.

Asking an LLM to check is worse than nothing: a data file doesn't fit in context, so a one-shot answer over the card plus a sample is guessing — and it guesses *confidently*. In our measured baseline, the model "verified" a wine dataset's row count because it "matches the known UCI Red Wine Quality dataset size" — memorized world knowledge substituting for the file, which actually held 1,611 rows ([results/final_per_claim.csv](results/final_per_claim.csv), row `case_03,baseline,w_rows`).

## What DocDrift does

One command per dataset: `python run_agent.py <case>`. The pipeline (deterministic Python orchestration; the model appears only at four no-tools judgment points):

1. **Extract** — the card becomes typed claims, each quoting its exact card text, with machine-readable params. Provenance prose is marked unverifiable up front: calibrated abstention is a verdict, not a failure.
2. **Synthesize** — one pandas check function per claim. The model's output is *code*, not an opinion.
3. **Mutation-gate** (the core) — before any check is trusted, it must pass a tiny fixture that *satisfies* the claim and **fail** a mutant fixture that *violates* it. A check that passes its mutant is green-because-it-cannot-fail; it gets one rewrite carrying the mutant diff, and two strikes mean the claim abstains rather than trust an unverified verifier.
4. **Execute** — the gated check runs against the **full file** in a sandboxed subprocess. Raw data never enters model context (the model sees dtypes + 20 head rows + ≤5 evidence rows, nothing more).
5. **Report** — an audit a person signs: per-claim claimed-vs-computed, offending rows for every violation, reasons for every abstention ([example](trajectories/agent_case_12/audit.md)). Every verdict traces to an append-only ledger holding the check source, gate results, and execution evidence.

Memory (`lessons.md`, injected into every synthesis) accumulates check-writing pitfalls across eval iterations; a fingerprinted ledger makes every run resumable by default.

**Use it from your browser:** `uv run python run_web.py` → http://127.0.0.1:8787 — upload any CSV/parquet plus its README (or give a Kaggle `owner/slug`, fetched with your own local Kaggle credentials), watch the claims settle live, and read the audit with per-claim verdicts and downloadable ledger. Local single-user demo surface; the pipeline underneath is unchanged.

## Measured results (12 cases, 98 gold claims, 41 planted violations)

Fair fight: same cases, same scorer, same model. `baseline` = the card + dtypes + 50 rows in one prompt (what people actually do). `baseline_plus` = the strongest single prompt we could build — full-column summary statistics + top-10 value counts.

| system | macro-F1 | violations caught | false confirmations of violated claims |
|---|---|---|---|
| **DocDrift (agent)** | **0.928** | **38/41** | **0** |
| baseline_plus | 0.951 | 38/41 | **2** |
| baseline | 0.457 | 11/41 | 3 |

Two numbers matter more than the headline F1 ([results/final.md](results/final.md) has the full tables):

- **The hard case.** A 1M-row file whose two violations are structurally invisible to head samples *and* full-column statistics: 173 pattern-breaking coupon codes planted after row 810,000 (below any top-10 value count), and a cross-column share claim ("roughly 10%", truth 14.2%) no per-column summary can compute. **DocDrift: 9/9 claims correct, both violations caught with row-level evidence. baseline_plus: missed both — and confirmed one as `holds`.**
- **Miss quality.** Where DocDrift misses, it *abstains* (`could not verify`); where the baselines miss, they *confirm* (`verified`, wrongly). An auditor that never lies about what it checked is the product; the F1 gap between agent and baseline_plus is two false certificates the baseline handed out.

Cost: full 12-case audit sweep ≈ 55k tokens / ~16 min — 13% fewer tokens than the single-prompt baseline_plus needs; $0 billed on a Claude subscription (≈$0.50–1 per sweep if run on a billed API key). Details and exact commands: [REPRODUCE.md](REPRODUCE.md).

## Improvement Changelog

**Clearly labelled and evidence-linked in [CHANGELOG.md](CHANGELOG.md)** — v0 (harness + baselines) → v1 (execution pipeline) → v2 (mutation gate, hard-case redesign after v0 proved `describe()` sees too much) → v3 (memory + calibration + fixture fixes), plus the removed stratified-sampling experiment and two model ablations: Haiku 4.5 ([results/ablation_haiku.md](results/ablation_haiku.md)) and Opus 5 ([results/ablation_opus.md](results/ablation_opus.md)). The ladder — Haiku 0.815/119k tokens, Sonnet 0.928/55k, Opus 0.936/23k — surfaced a counterintuitive finding: **stronger models are token-cheaper on a gated pipeline**, because retries and gate rewrites dominate the bill, and every tier held zero false confirmations: the safety property is the gate's, not the model's.

## Main failure mode

**Hallucinated confirmation** — a model marking a claim `verified` on evidence that cannot verify it: a 50-row sample, a memorized dataset size, a top-10 value count that hides row 810,001. Every design choice here exists to make that impossible: verdicts require executed checks (FR-004), checks require passed mutants (FR-005), and anything unverifiable says so out loud. The residual failure mode is the mirror image: over-abstention — our gate refused two claims whose checks tested a proxy instead of the exact count, trading two catches for the guarantee. We consider that trade correct, and the changelog measures it.

## Hot take

**A verifier you haven't tried to fool is just another generator.** 7.5% of our agent's first-draft checks were rejected by their own mutants — checks that would have returned green while being unable to detect the violation they guarded ([results/v2.md](results/v2.md)). Mutation-testing the *checks* — not the code under test — is what turned "an LLM that writes pandas" into an auditor whose worst behavior is saying "I couldn't verify this," while the strongest prompt-only baseline was confidently certifying violated claims from world knowledge. And a second lesson we didn't expect: agent memory is not free — one lesson we taught it (sentinel awareness) regressed a previously-caught violation a version later. Memory entries need regression evals, exactly like code.

---

*Spec-driven build: [constitution](.specify/memory/constitution.md) · [spec](specs/001-docdrift/spec.md) · [plan](specs/001-docdrift/plan.md) · [tasks](specs/001-docdrift/tasks.md) · [research log](specs/001-docdrift/research.md). Agent trajectories for every agent role: [trajectories/](trajectories/) with index in [DISCLOSURE.md](DISCLOSURE.md).*
