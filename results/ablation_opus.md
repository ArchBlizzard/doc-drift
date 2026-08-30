# Ablation — Opus as the pipeline model (T041)

Same v3 pipeline, same 12 cases, model alias `opus` (Opus 5), isolated in
`runs_opus/`. Reproduce:
`foreach case: python run_agent.py case_NN --model opus --out runs_opus`,
then `python eval/score.py --runs-dir runs_opus --out <dir>`.

## The full model ladder

| pipeline model | macro-F1 | violations caught | false confirmations | tokens | wall s |
|---|---|---|---|---|---|
| **opus (this ablation)** | **0.936** | **39/41** | 0 | **23,452** | 886 |
| sonnet (default, [final.md](final.md)) | 0.928 | 38/41 | 0 | 55,063 | 983 |
| haiku ([ablation_haiku.md](ablation_haiku.md)) | 0.815 | 37/41 | 0 | 118,982 | 2,267 |

## Findings

1. **Stronger models are token-CHEAPER on a gated pipeline.** Opus used 57%
   fewer tokens than Sonnet and 5× fewer than Haiku for the same work,
   because its first drafts pass schema validation and the mutation gate more
   often — retries and rewrites, not verbosity, dominate the token bill.
   Capability ↑ ⇒ corrections ↓ ⇒ tokens ↓.
2. **Opus recovered one Sonnet miss:** the NOAA precipitation range claim
   (`case_06/n_prcp`) — Sonnet's v3 check applied the sentinel lesson
   over-broadly and judged it `holds`; Opus checked the claim as written and
   caught the violation. The other two misses (`a_nulls` compound-sentence
   alignment, `r_countries` gate refusal of proxy-count checks) are identical
   across all three models: **the residual misses are harness properties,
   not model properties.**
3. **Zero false confirmations at every tier** — the third model to
   demonstrate that the safety property lives in the gate + abstention
   design, not model strength.

## Decision

Per-token API pricing makes Opus roughly 2× Sonnet's billed cost per sweep
despite the smaller token count (≈$1–2 vs ≈$0.50–1), and it draws harder on
subscription usage windows. **Sonnet stays the default** as the
cost-quality sweet spot; Opus is the documented quality ceiling
(+0.008 macro-F1, +1 catch) for users who want it: `run_agent.py <case>
--model opus`.
