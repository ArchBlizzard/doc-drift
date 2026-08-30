# Coding-agent disclosure & trajectory index

Coding-agent use was required by the hackathon and is disclosed here in full.

## Tools used

- **Claude Code** (CLI/IDE, Claude Fable 5) — every line of code, spec, and
  documentation in this repository was produced in Claude Code sessions driven
  by the participant. The commit history is the faithful build log: one commit
  per task of `specs/001-docdrift/tasks.md` (Constitution VIII).
- **Claude Agent SDK (`claude-agent-sdk` Python)** — the runtime for every
  DocDrift pipeline model call (extractor, synthesizer, reporter, baselines),
  on Claude subscription auth (`sonnet` → resolved IDs recorded per run in the
  ledgers; `haiku` for the T029 ablation).
- **Multi-agent planning workflows** (Claude Code Workflow tool) — project
  selection (5 ideation agents + 3 rubric judges) and a 4-auditor
  cross-document spec review. Full journals included below.

## Trajectory index (`trajectories/`)

| path | what it shows |
|---|---|
| `agent_case_04/` | Full pipeline run on a corruption case: `ledger.jsonl` (claim → check source → mutation-gate results → execution → verdict), `messages.jsonl` (every prompt/reply verbatim), `audit.md`, `verdicts.json`. **Includes a mutation-gate rejection → rewrite episode and a two-strike abstention** (claim `r_countries`). |
| `agent_case_12/` | The 1M-row hard case run: both summary-invisible violations caught (pattern break past row 810k; cross-column share). |
| `baseline_case_04/` | One baseline transcript (`messages.jsonl`): the honest single-prompt comparison, same claims, same scorer. |
| `kaggle_kicker/` | Real-world run on an UNMODIFIED public data card (OpenML `credit-g`) — two genuine violations found in the 1994 documentation. Nothing planted; see its `PROVENANCE.md`. |
| `kaggle_iris/` | Second real-world run, via the Kaggle API on the participant's own account: `uciml/iris` (CC0). The complementary outcome — a good card *certified* with computed evidence (50/50/50 species counts, all documented columns verified), prose correctly abstained. |
| `ideation/` | The planning-stage multi-agent workflow journals: project selection (10 candidate ideas, 3-judge rubric panel) and the 68-finding spec audit. Each line is one agent's full structured return. |

Reading order for judges: start at `agent_case_04/audit.md` (the product),
then `ledger.jsonl` for the same case (how each verdict was earned), then
`messages.jsonl` (the raw model traffic behind it).

## Feedback loops captured

- Gate rejections carry the mutant diff back into the rewrite prompt — visible
  as consecutive `synthesize:<claim>` records in any `messages.jsonl` where a
  `x ... rejected by gate` event appears in the ledger's mutant_results.
- `lessons.md` (injected into every synthesis prompt) accumulates pitfalls
  across eval iterations; each entry cites the evidence that created it.
- Human checkpoints: every task landed as a reviewed commit; live sweeps were
  monitored and two mid-flight defects (SDK turn-cap handling, phantom-fixture
  semantics) were fixed and documented in CHANGELOG.md rather than papered
  over.

## Credential hygiene

Scanned 2026-08-29 (T035): `git grep` over the working tree and `git log --all -p`
over the FULL history for `sk-ant-` key material and inline
`ANTHROPIC_API_KEY=` / `CLAUDE_CODE_OAUTH_TOKEN=` assignments — **clean**, and
no `.env` file has ever been tracked. Auth enters only via environment
variables or the Claude Code login; `.env` is gitignored and `.env.example`
ships empty.
