# Final results — v3 pipeline, full 12-case suite, all four systems

Per-claim detail: [final_per_claim.csv](final_per_claim.csv). Scored by the
deterministic span-anchored scorer (`eval/score.py`); every fuzzy-fallback
alignment is flagged in the CSV. Reproduce: [REPRODUCE.md](../REPRODUCE.md).

| system | macro-F1 | violations caught | false confirmations¹ | holds P/R | violated P/R | unverif P/R | tokens | wall s |
|---|---|---|---|---|---|---|---|---|
| **DocDrift agent (gated, v3)** | **0.928** | **38/41** | **0** | 0.98/0.96 | 1.00/0.93 | 0.75/1.00 | 55,063 | 983 |
| baseline_plus (summary stats) | 0.951 | 38/41 | 2 | 0.96/0.98 | 1.00/0.93 | 0.86/1.00 | 70,566 | 668 |
| baseline (card + 50 rows) | 0.457 | 11/41 | 3 | 0.66/0.51 | 0.92/0.27 | 0.24/1.00 | 177,538 | 1,947 |
| baseline_stratified (removed exp.) | 0.886 | 31/41 | 8 | 0.84/0.96 | 0.94/0.76 | 0.86/1.00 | 817,664 | 6,806 |

¹ gold-violated claims the system marked `holds` — the dangerous failure: a
wrong certificate. Rows in final_per_claim.csv (`gold == violated`,
`predicted == holds`).

## What the table means

- **The agent is the only system that never issues a false certificate.** Its
  3 misses are calibrated abstentions: one gate refusal of proxy-count checks
  (`case_04/r_countries`), one compound-sentence alignment split
  (`case_01/a_nulls` — the violated half IS in its audit), and one defensible
  sentinel-aware interpretation (`case_06/n_prcp`, discussed in CHANGELOG v3).
- **The hard case separates execution from summary-reading:** agent 9/9 with
  both deep violations caught and row-level evidence; baseline_plus confirmed
  the corrupted pattern claim as `holds` and abstained on the share;
  stratified sampling also confirmed the pattern claim (its 1,800 sampled
  rows never met row 810,001).
- **Miss quality is the story, not the F1 decimals.** baseline_plus edges the
  macro-F1 by padding easy classes, but hands out 2 false certificates;
  stratified hands out 8. Where DocDrift cannot verify, it says so.
- Cost: the agent audits all 12 datasets for 55k tokens in ~16 min — 13% fewer
  tokens than the single-prompt baseline_plus needs, and 15× fewer than
  stratified stuffing. SC-003 (sweep ≤45 min) passes with room to spare.

Checkpoint history: [v0.md](v0.md) → [v1.md](v1.md) → [v2.md](v2.md) → this.
Ablation: [ablation_haiku.md](ablation_haiku.md). Removed experiment:
[removed_stratified.md](removed_stratified.md).
