# Results

| system | cases | claims | holds P/R | violated P/R | unverif P/R | macro-F1 | violations caught | fallback matches | tokens | wall s |
|---|---|---|---|---|---|---|---|---|---|---|
| agent | 12 | 98 | 0.98/0.96 | 1.00/0.93 | 0.75/1.00 | **0.928** | 38/41 | 3 | 55063 | 983 |
| baseline | 12 | 98 | 0.66/0.51 | 0.92/0.27 | 0.24/1.00 | **0.457** | 11/41 | 5 | 177538 | 1947 |
| baseline_plus | 12 | 98 | 0.96/0.98 | 1.00/0.93 | 0.86/1.00 | **0.951** | 38/41 | 5 | 70566 | 668 |
| baseline_stratified | 12 | 98 | 0.84/0.96 | 0.94/0.76 | 0.86/1.00 | **0.886** | 31/41 | 5 | 817664 | 6806 |

Full per-claim detail (including every flagged fuzzy-fallback match): `per_claim.csv`.
