# Quickstart: DocDrift

Written for a clean environment; this document seeds the final `REPRODUCE.md`. Runtime/cost figures marked *(to be measured)* are filled in from ledger data before submission (Constitution II).

## Prerequisites

- Git, Python 3.12, and [uv](https://docs.astral.sh/uv/) (or pip).
- The Claude Code CLI: `npm install -g @anthropic-ai/claude-code` (version pinned in REPRODUCE.md) — required by `claude-agent-sdk` under **every** auth option below.
- **Model auth — any ONE of:**
  - A) `ANTHROPIC_API_KEY` set in the environment (funded key), or
  - B) `CLAUDE_CODE_OAUTH_TOKEN` set (generate once with `claude setup-token` on any machine with a Claude subscription login), or
  - C) a machine already logged into Claude Code (`claude` → `/login`) — no env var needed.
- No other network access is required by any step.

## Setup

```bash
git clone <repo-url> docdrift && cd docdrift
uv sync                      # or: pip install -e ".[dev]"
uv run pytest                # harness self-tests must pass before anything else
```

## Build the eval cases (offline, deterministic)

```bash
uv run python eval/make_cases.py --all     # alias: make data / .\tasks.ps1 data
```

Verifies `data_src/SHA256SUMS`, then writes `cases/case_01..12` and `eval/gold/`. `case_12` synthesizes the 1M-row parquet locally (~1 min). Running it twice produces identical cards and gold files.

## Run one case (both systems)

```bash
uv run python run_baseline.py case_04            # 1 model call
uv run python run_baseline.py case_04 --plus     # stronger single-prompt variant
uv run python run_agent.py case_04               # full pipeline
```

Expected outputs: `runs/case_04/baseline*/verdicts.json`; `runs/case_04/agent/{verdicts.json, ledger.jsonl, audit.md}`. Open `audit.md` — the per-claim table with claimed-vs-computed values is the product.

## Full evaluation (the main result)

```bash
uv run python eval/run_all.py                    # all 3 systems × 12 cases; resumable
uv run python eval/score.py                      # deterministic; no model calls
```

Expected output: `results/results.md` — per-case macro-F1 table for baseline, baseline_plus, and agent — plus `results/per_claim.csv` with every verdict and every flagged fallback alignment. The committed `results/` from the submitted run is the reference; your reproduced agent macro-F1 should land within ±0.05 absolute of it with agent > both baselines preserved (SC-004 — model outputs are not bit-identical, but the scorer and cases are deterministic).

## Runtime & cost *(to be measured; targets)*

- Full agent sweep: ≤45 min wall clock (SC-003); baselines: minutes.
- Subscription auth: $0 billed, draws on the plan's usage window.
- API key: ≈$6–10 per full sweep (verified token counts will be published from the ledger).

## Troubleshooting

- **exit 2 (auth):** no credential found — set one of the three options above; `ANTHROPIC_API_KEY` takes precedence if set.
- **Usage-limit pause mid-sweep:** wait for the window reset, then re-run the same command — settled claims are skipped automatically (FR-008); pass `--fresh` only for a deliberate full re-run.
- **exit 4 on `make data`:** `data_src/` checksum mismatch — re-clone; do not substitute dataset files.
- **Windows:** all commands work in PowerShell; `.\tasks.ps1 <target>` mirrors the Makefile targets.
