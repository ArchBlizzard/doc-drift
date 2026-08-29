# DocDrift Constitution

Core principles governing every artifact in this repository. Plans, tasks, and code MUST comply; where a document conflicts with the constitution, the constitution wins.

## Article I — Evidence Over Assertion

Every reported verdict, metric, and changelog claim MUST trace to a committed artifact: a ledger entry, a results table, or an executor log. No number appears in `README.md` or `CHANGELOG.md` without a repository path to its evidence. This mirrors the hackathon's ground rule "connect every claim about your results to the evidence you submit."

## Article II — Reproducibility First

- The judge's path requires **zero network beyond dependency installation and model authentication/inference**. All eval data is either committed in-repo (with licenses and SHA256 checksums) or generated deterministically from a committed seed.
- Both auth paths — a funded `ANTHROPIC_API_KEY` or a Claude subscription login (`claude` CLI OAuth / `CLAUDE_CODE_OAUTH_TOKEN`) — MUST work through the same code path, with no branch.
- Every sweep records the resolved model IDs and token counts into the run ledger; `REPRODUCE.md` cites measured numbers, never estimates presented as measurements.

## Article III — Verified Verification (the core mechanism)

No synthesized check is trusted until it **passes the clean fixture AND fails its mutant fixture**. A check that fails the mutation gate twice yields `unverifiable(check_failed)` — never a trusted verdict. A `holds` or `violated` verdict MUST be backed by an executed check result on the full dataset; the model's unexecuted opinion is never a verdict.

## Article IV — Deterministic Orchestration

Control flow is plain Python. LLM calls occur only at defined judgment points (extract, synthesize, rewrite-on-gate-failure, report), each with pydantic-validated output and a hard cap of 2 retries. The model never drives control flow.

## Article V — Context Discipline

Raw dataset rows never enter the **agent pipeline's** model context, with exactly two exceptions: the profile snapshot (dtypes + `head(20)`) and up to 5 evidence rows per finding. The full dataset is touched only by the sandboxed executor, on disk. Baseline and ablation systems run for evaluation are exempt by design — their context budget is the experimental variable under test — and their full prompts are published as trajectories.

## Article VI — Honest Reporting

Failures, removed experiments, and unfavourable ablations are published with the same prominence as wins. Complete per-claim results for **both** baselines and the agent ship in `results/`. The Improvement Changelog includes at least one removed experiment with its numbers.

## Article VII — Scope Discipline

The mutation gate is the submission. Under time pressure, cut eval cases (floor: 10 of 12), never the gate. Feature freeze at H43 (one hour before the Aug 31 18:00 UTC deadline); after that, only packaging.

## Article VIII — Commit Per Task

One `tasks.md` task = one commit, landed the moment the task completes, with its tests green for the touched files. Tasks producing no file changes are skipped in the commit series and noted in the session summary. Never `git push` without explicit approval. (Mirrors the repository owner's standing workflow rule.)

## Governance

Amendments are edits to this file with a dated rationale appended below. `spec.md`, `plan.md`, and `tasks.md` must be re-checked against the constitution after any amendment.

**Version 1.0.1 — ratified 2026-08-29.**

**Amendment 2026-08-29 (v1.0.0 → v1.0.1), rationale from the cross-document audit:** Article V scoped to the agent pipeline (baselines/ablations are exempt — their context budget is the variable under test; without this, the constitution outlawed the baselines FR-009 mandates). Article II reworded to permit dependency installation. Article III's reason token normalized to the canonical snake_case `check_failed` used by the machine contracts.
