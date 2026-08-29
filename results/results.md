# Results

| system | cases | claims | holds P/R | violated P/R | unverif P/R | macro-F1 | violations caught | fallback matches | tokens | wall s |
|---|---|---|---|---|---|---|---|---|---|---|
| agent | 6 | 48 | 1.00/1.00 | 1.00/1.00 | 1.00/1.00 | **1.000** | 23/23 | 3 | 46754 | 370 |
| baseline | 6 | 48 | 0.62/0.42 | 1.00/0.26 | 0.21/1.00 | **0.419** | 6/23 | 2 | 91130 | 1093 |
| baseline_plus | 6 | 48 | 0.95/1.00 | 1.00/0.96 | 1.00/1.00 | **0.984** | 22/23 | 3 | 36061 | 343 |

Full per-claim detail (including every flagged fuzzy-fallback match): `per_claim.csv`.
