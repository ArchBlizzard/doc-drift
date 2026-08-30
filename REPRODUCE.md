# Reproduction guide

Written for a clean environment. Every command below was rehearsed from a
fresh clone before submission (see the verification block at the end).
`TODO-MEASURED` markers are filled from the rehearsal ledgers before final
packaging (Constitution I: measured, not estimated).

## Prerequisites

| requirement | version used | install |
|---|---|---|
| Git | any recent | — |
| Python | 3.12+ (rehearsed on 3.13.3) | python.org |
| uv | 0.6.14 | `pip install uv` or see docs.astral.sh/uv |
| Node.js | 22.14.0 | nodejs.org |
| Claude Code CLI | 2.1.193 (rehearsed) | `npm install -g @anthropic-ai/claude-code` — required by `claude-agent-sdk` under **every** auth option |

**Model auth — any ONE of:**
- A) `ANTHROPIC_API_KEY` set in the environment (funded key), or
- B) `CLAUDE_CODE_OAUTH_TOKEN` set (generate once with `claude setup-token` on a machine with a Claude subscription login), or
- C) a machine already logged into Claude Code (`claude` → `/login`) — no env var needed.

No other network access is required by any judge-path step: all six real
datasets are committed with SHA256 checksums, and the 1M-row hard case is
generated deterministically from a committed seed.

## Setup (≈2 minutes + downloads)

```bash
git clone https://github.com/ArchBlizzard/doc-drift.git && cd doc-drift
uv sync                  # 9s measured (fresh venv, cached wheels)
uv run pytest            # 177 tests, ~85s measured; includes proof that every
                         # accurate-card claim is true of the committed data
```

## Build the eval cases (offline, deterministic, ~8s measured)

```bash
uv run python eval/make_cases.py --all      # alias: make data / .\tasks.ps1 data
```

Verifies `data_src/SHA256SUMS`, writes `cases/case_01..12` + `eval/gold/`.
Byte-identical on every run (tested by `tests/test_make_cases.py`).

## One case, all systems (the quick look, ≈3–5 min measured)

```bash
uv run python run_baseline.py case_04            # 1 no-tools model call
uv run python run_baseline.py case_04 --plus     # + summary statistics
uv run python run_agent.py case_04               # full gated pipeline
```

Outputs land under `runs/case_04/`. Open `runs/case_04/agent/audit.md` — the
per-claim table with claimed-vs-computed values and evidence rows is the
product. `ledger.jsonl` holds every check's source, mutation-gate result, and
execution evidence; `messages.jsonl` holds every model call verbatim.

## Full evaluation (the main result)

```bash
uv run python eval/run_all.py                    # 3 systems × 12 cases; resumable
uv run python eval/score.py                      # deterministic; no model calls
```

- Interrupted by a usage-limit pause? Re-run the same command — completed
  (case, system) pairs and settled claims are skipped automatically.
- The removed experiment reproduces with
  `uv run python eval/run_all.py --systems baseline_stratified`; the Haiku
  ablation with `run_agent.py case_NN --model haiku --out runs_haiku` per case.

**Expected result (SC-004):** case generation and scoring are byte-identical;
your reproduced agent macro-F1 lands within ±0.05 absolute of the committed
`results/final.md` value with the ordering agent > both baselines preserved
(model outputs vary run to run — the submitted runs' complete outputs are
committed under `results/`).

## Measured runtime and cost (reference machine: AMD Ryzen 9 6900HS, 16GB RAM, Windows 11)

| step | wall clock | model tokens (in+out) | $ if billed via API |
|---|---|---|---|
| `pytest` (177 tests) | ~85s | 0 | 0 |
| `make data` (12 cases incl. 1M-row synth) | ~8s | 0 | 0 |
| agent sweep, 12 cases (`results/final.md`) | ~16 min | 55,063 | ≈ $0.50–1 |
| baseline sweep, 12 cases | ~32 min | 177,538 | ≈ $1–2 |
| baseline_plus sweep, 12 cases | ~11 min | 70,566 | ≈ $0.50–1 |
| single case, baseline + agent (clean clone) | 74s + 105s | in the runs' ledgers | — |

On subscription auth the billed cost is $0 — calls draw on the plan's usage
window (disclosed: temperature is not exposed on this path; determinism lives
in the harness, not the transcripts).

## Clean-environment verification (T035, executed 2026-08-29)

Rehearsed on the reference machine from an actual fresh clone into an empty
directory with a fresh venv (no env vars set; auth = stored Claude Code
subscription login, option C):

1. `git clone` (1s) → `uv sync` (9s) → `uv run pytest` → **177 passed** (~85s).
2. `make data` → all 12 cases + gold generated in ~8s; committed gold
   byte-identical to the regeneration.
3. `run_baseline.py case_04` (74s) and `run_agent.py case_04` (105s) live from
   the clean clone: all four planted violations caught, one gate
   rejection→rewrite and one two-strike abstention fired identically to the
   committed run.
4. The API-key auth direction is verified by the credential-precedence unit
   tests in `tests/test_llm.py` (no funded key was available to the builder —
   disclosed per spec acceptance scenario 7).

The rehearsal caught one real defect before submission: Windows `autocrlf`
rewrote a committed CSV's line endings on fresh checkout, breaking its SHA256
gate. Fixed with a repo-wide `.gitattributes` `-text` rule and checksums
recomputed from committed blob bytes (commits `1d92005`, `8155f1d`) — a fresh
clone now reproduces byte-exactly on any platform. Credential scan (tree +
full history): clean — see DISCLOSURE.md.
