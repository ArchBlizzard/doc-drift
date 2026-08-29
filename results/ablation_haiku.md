# Ablation — Haiku as the synthesizer/pipeline model (T029)

Same v3 pipeline, same 12 cases, model alias `haiku` (Haiku 4.5) instead of
`sonnet`, isolated in its own runs directory. Reproduce:
`foreach case: python run_agent.py case_NN --model haiku --out runs_haiku`,
then `python eval/score.py --runs-dir runs_haiku --out <dir>`.

| pipeline model | macro-F1 | violations caught | holds P/R | violated P/R | unverif P/R | tokens | wall s |
|---|---|---|---|---|---|---|---|
| sonnet (default, [final.md](final.md)) | **0.928** | 38/41 | 1.00/0.96 | 1.00/0.93 | 0.71/1.00 | 52,515 | 969 |
| haiku (this ablation) | **0.815** | 37/41 | 1.00/0.87 | 0.95/0.90 | 0.53/0.67 | 118,982 | 2,267 |

## Findings

1. **The safety property survived the model downgrade.** Zero gold-violated
   claims were confirmed as `holds` — the mutation gate and abstention
   discipline, not model strength, carry the no-false-confirmations guarantee.
   Haiku's losses are almost all extra `check_failed` abstentions (weaker
   first-draft checks the gate refused to trust).
2. **The cheaper model was more expensive end-to-end:** 2.3× the tokens and
   2.3× the wall clock, because schema-validation retries and gate rewrites
   multiplied the number of calls. Per-token price would need to be ~2.5×
   lower before Haiku breaks even on this workload — before accounting for
   the 0.11 macro-F1 loss.

## Decision (per T029 acceptance)

F1 does not hold within tolerance → **Sonnet remains the default**; recorded
here as an informative ablation rather than a removed default. The
architectural lesson stands on its own: quality gates convert a weaker model
into more abstentions and more retries — never into wrong confirmations.
