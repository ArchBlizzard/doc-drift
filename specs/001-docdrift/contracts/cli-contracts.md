# CLI Contracts: DocDrift

Every command below is the stable interface `quickstart.md`/`REPRODUCE.md` documents and judges run. Behavior changes here require a spec update first.

## Environment contract

- **Auth (exactly one needed, checked in this order):** `ANTHROPIC_API_KEY` env var → `CLAUDE_CODE_OAUTH_TOKEN` env var → stored Claude Code subscription login. No other network access is performed by any command (Constitution II).
- **Python:** 3.12; install via `uv sync` (lockfile committed) or `pip install -e ".[dev]"` (dev extras carry pytest for the self-tests).
- **Claude Code CLI** installed (`npm install -g @anthropic-ai/claude-code`; version pinned in REPRODUCE.md) — required by `claude-agent-sdk` under every auth option.
- All commands run from the repo root; all paths below are repo-relative.

## Commands

### `make data` (alias: `python eval/make_cases.py --all`; Windows: `.\tasks.ps1 data`)
Builds all eval cases from `data_src/` + `eval/specs/*.yaml`.
- **Inputs:** committed datasets (verified against `data_src/SHA256SUMS` first; mismatch → exit 4), case specs, seeds.
- **Outputs:** `cases/case_NN/{data.(csv|parquet), datacard.md}` and `eval/gold/case_NN_gold.json` (schema: `gold.schema.json`). `case_12` additionally generates the 1M-row synthetic parquet.
- **Determinism:** running twice yields byte-identical cards and gold JSON; data files identical per seed.
- **No model calls.** Exit 0 on success.

### `python run_baseline.py <case_id> [--plus] [--out DIR]`
One no-tools model call (two with `--plus` variant, run separately).
- **Inputs:** `cases/<case_id>/`; auth per environment contract.
- **Outputs:** `runs/<case_id>/baseline[_plus]/verdicts.json` (schema: `verdicts.schema.json`) + `prompt.txt` + raw model reply (the baseline trajectory).
- **Model:** alias `sonnet` (overridable `--model`).

### `python run_agent.py <case_id> [--fresh] [--model sonnet] [--out DIR]`
Full DocDrift pipeline: extract → per-claim (synthesize → mutation-gate → execute) → verdicts → report.
- **Outputs:** `runs/<case_id>/agent/{verdicts.json, ledger.jsonl, messages.jsonl, audit.md}`.
- **Resume is the default** (FR-008): re-runs skip claims settled in an existing ledger with matching data+card fingerprints. `--fresh` discards the ledger for a deliberate full re-run.
- **Guarantees:** every holds/violated verdict has a gate-passed executed check in the ledger (FR-004/005); process exits 0 even when claims are violated — verdicts are data, not errors.

### `python eval/run_all.py [--systems baseline,baseline_plus,agent] [--cases case_01,...]`
(`--systems` also accepts `baseline_stratified` — the removed-experiment ablation, scored by the same scorer; outputs under `runs/<case>/baseline_stratified/`.)
Runs the selected systems over the selected cases (default: all three systems, all 12 cases), then invokes scoring.
- **Outputs:** everything under `runs/`, plus `results/results.md` and `results/per_claim.csv`.
- **Resumable:** re-invocation skips completed (case, system) pairs unless `--force`.

### `python eval/score.py [--runs-dir runs] [--out results]`
Pure scoring — **no model calls, fully deterministic** (Constitution II).
- **Alignment:** span-IoU ≥ 0.5 primary; rapidfuzz ≥ 85 fallback, every fallback match flagged in `per_claim.csv` (research R3). Unmatched gold claim = miss for that system.
- **Outputs:** `results/results.md` (per-case × per-system table: per-class P/R, macro-F1, violations caught, tokens, wall time) and `results/per_claim.csv`.
- Exit 4 if gold files are missing/invalid.

### `python scripts/spike_auth.py`
Spike S1: one no-tools SDK call; prints resolved model ID and latency. Not part of the judge path.

## Exit codes (all commands)

| code | meaning |
|---|---|
| 0 | success (including "violations found" — that's a result) |
| 1 | unexpected internal error |
| 2 | auth/configuration error (no credential found, SDK cannot start) |
| 3 | case or input path not found |
| 4 | validation failure (checksum mismatch, schema-invalid file, missing gold) |
