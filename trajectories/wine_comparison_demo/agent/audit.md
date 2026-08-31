# Data card audit — web_red_wine_quality_cortez__891a10

Run: 2026-08-31T09:15:35+00:00 · model: claude-opus-5 · claims audited: 27

## Executive summary

**1 violated · 13 hold · 13 unverifiable.** Most severe violation: **web_red_wine_quality_cortez__891a10-c24** — "to turn the 10 point scale to dichtome variable".

The one real violation is the quality column: it holds only 6 distinct values, 3 through 8, so the documented 10 point scale never shows up in the data. Any dichotomization written against a 0 to 10 scale, such as splitting at the midpoint, lands somewhere other than where the author intended, and the poor and excellent extremes the docs describe are simply not present. Fix the documentation to state the observed range of 3 to 8 and name the exact cut point used for the binary target. Everything else testable passed: all 12 columns appear in the documented order with float64 dtype and zero non-numeric cells across 1599 rows. The weak spot that remains is coverage, since 13 of 27 claims are prose the audit cannot test, including the AUC of .88 assertion, which should be backed by a reproducible script or removed.

## Per-claim verdicts

| # | claim (quoted from the card) | type | verdict | claimed | computed |
|---|---|---|---|---|---|
| 1 | The two datasets are related to red and white variants of the Portuguese "Vinho Verde" wine. | prose_unverifiable | unverifiable (prose) | — | — |
| 2 | For more details, consult the reference [Cortez et al., 2009]. | prose_unverifiable | unverifiable (prose) | — | — |
| 3 | Due to privacy and logistic issues, only physicochemical (inputs) and sensory (the output) variables are available | prose_unverifiable | unverifiable (prose) | — | — |
| 4 | there is no data about grape types, wine brand, wine selling price, etc. | prose_unverifiable | unverifiable (prose) | — | — |
| 5 | These datasets can be viewed as classification or regression tasks. | prose_unverifiable | unverifiable (prose) | — | — |
| 6 | The classes are ordered and not balanced (e.g. there are much more normal wines than excellent or poor ones). | prose_unverifiable | unverifiable (prose) | — | — |
| 7 | This dataset is also available from the UCI machine learning repository, https://archive.ics.uci.edu/ml/datasets/wine+quality , I just shared it to kaggle for convenience. | prose_unverifiable | unverifiable (prose) | — | — |
| 8 | Input variables (based on physicochemical tests): | prose_unverifiable | unverifiable (prose) | — | — |
| 9 | 1 - fixed acidity | schema | holds | 1 - fixed acidity | column 'fixed acidity' present at position 1 (1-indexed), dtype=float64, non-numeric cells=0 |
| 10 | 2 - volatile acidity | schema | holds | 2 - volatile acidity | column 'volatile acidity' present at position 2 (1-indexed) of 12; dtype=float64; non-numeric cells=0; min=0.12, max=1.58 |
| 11 | 3 - citric acid | schema | holds | 3 - citric acid | 'citric acid' at 1-based position 3 of 12 columns (dtype=float64) |
| 12 | 4 - residual sugar | schema | holds | 4 - residual sugar | column 'residual sugar' at position 4 of 12; dtype=float64; non-numeric non-null values=0 |
| 13 | 5 - chlorides | schema | holds | 5 - chlorides | 'chlorides' is attribute #5 of 12; 5th column is 'chlorides'; numeric=True, non-numeric values=0 |
| 14 | 6 - free sulfur dioxide | schema | holds | 6 - free sulfur dioxide | column 'free sulfur dioxide' at 1-based position 6 (claim says 6); dtype=float64; numeric-parseable non-null 1599/1599 rows |
| 15 | 7 - total sulfur dioxide | schema | holds | 7 - total sulfur dioxide | column 'total sulfur dioxide' is at 1-based position 7 (expected 7); dtype=float64 |
| 16 | 8 - density | schema | holds | 8 - density | column 'density' at 1-based position 8 (expected 8), dtype=float64, non-numeric cells=0, nulls=0, min=0.99007, max=1.00369 |
| 17 | 9 - pH | schema | holds | 9 - pH | column 9 = 'pH'; 'pH' found at position 9 of 12 columns; dtype=float64; rows=1599; non-numeric/null pH cells=0 |
| 18 | 10 - sulphates | schema | holds | 10 - sulphates | column 'sulphates' is at 1-indexed position 10 (stated 10); dtype=float64 |
| 19 | 11 - alcohol | schema | holds | 11 - alcohol | column 11 = 'alcohol'; 'alcohol' at 1-based position 11 |
| 20 | Output variable (based on sensory data): | prose_unverifiable | unverifiable (prose) | — | — |
| 21 | 12 - quality | schema | holds | 12 - quality | column 'quality' is at 1-based position 12 of 12 columns (claim: position 12) |
| 22 | 12 - quality (score between 0 and 10) | range | holds | 12 - quality (score between 0 and 10) | min=3, max=8, out-of-[0,10]=0, non-numeric=0 |
| 23 | Without doing any kind of feature engineering or overfitting you should be able to get an AUC of .88 (without even using random forest algorithm) | prose_unverifiable | unverifiable (prose) | — | — |
| 24 | to turn the 10 point scale to dichtome variable | category_set | violated | to turn the 10 point scale to dichtome variable | quality has 6 distinct levels: [3, 4, 5, 6, 7, 8] (min=3, max=8); stated scale = 10 points |
| 25 | I am not the owner of this dataset. | prose_unverifiable | unverifiable (prose) | — | — |
| 26 | Please include this citation if you plan to use this database | prose_unverifiable | unverifiable (prose) | — | — |
| 27 | P. Cortez, A. Cerdeira, F. Almeida, T. Matos and J. Reis. Modeling wine preferences by data mining from physicochemical properties.  | prose_unverifiable | unverifiable (prose) | — | — |

## Evidence for violations

### web_red_wine_quality_cortez__891a10-c24 — to turn the 10 point scale to dichtome variable

Computed: `quality has 6 distinct levels: [3, 4, 5, 6, 7, 8] (min=3, max=8); stated scale = 10 points`

| quality | n_rows |
|---|---|
| 3 | 10 |
| 4 | 53 |
| 5 | 681 |
| 6 | 638 |
| 7 | 199 |


## Abstentions

- **web_red_wine_quality_cortez__891a10-c01** (prose): The two datasets are related to red and white variants of the Portuguese "Vinho Verde" wine.
- **web_red_wine_quality_cortez__891a10-c02** (prose): For more details, consult the reference [Cortez et al., 2009].
- **web_red_wine_quality_cortez__891a10-c03** (prose): Due to privacy and logistic issues, only physicochemical (inputs) and sensory (the output) variables are available
- **web_red_wine_quality_cortez__891a10-c04** (prose): there is no data about grape types, wine brand, wine selling price, etc.
- **web_red_wine_quality_cortez__891a10-c05** (prose): These datasets can be viewed as classification or regression tasks.
- **web_red_wine_quality_cortez__891a10-c06** (prose): The classes are ordered and not balanced (e.g. there are much more normal wines than excellent or poor ones).
- **web_red_wine_quality_cortez__891a10-c07** (prose): This dataset is also available from the UCI machine learning repository, https://archive.ics.uci.edu/ml/datasets/wine+quality , I just shared it to kaggle for convenience.
- **web_red_wine_quality_cortez__891a10-c08** (prose): Input variables (based on physicochemical tests):
- **web_red_wine_quality_cortez__891a10-c20** (prose): Output variable (based on sensory data):
- **web_red_wine_quality_cortez__891a10-c23** (prose): Without doing any kind of feature engineering or overfitting you should be able to get an AUC of .88 (without even using random forest algorithm)
- **web_red_wine_quality_cortez__891a10-c25** (prose): I am not the owner of this dataset.
- **web_red_wine_quality_cortez__891a10-c26** (prose): Please include this citation if you plan to use this database
- **web_red_wine_quality_cortez__891a10-c27** (prose): P. Cortez, A. Cerdeira, F. Almeida, T. Matos and J. Reis. Modeling wine preferences by data mining from physicochemical properties. 
