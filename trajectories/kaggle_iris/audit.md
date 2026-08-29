# Data card audit — demo_kaggle_iris

Run: 2026-08-29T08:57:37+00:00 · model: claude-sonnet-5 · claims audited: 10

## Executive summary

**0 violated · 8 hold · 2 unverifiable.** No violations found.

The audit confirms the Iris documentation checks out: all 8 verifiable claims hold, including the 150-row count with exactly 50 samples per species, three clean species categories, and fully populated, correctly-typed schema columns (Id, SepalLengthCm, SepalWidthCm, PetalLengthCm, PetalWidthCm, Species) with zero nulls or type mismatches. The two remaining claims (provenance citation to Fisher's 1936 paper and the linear-separability description of one species vs. the other two) are prose assertions that cannot be mechanically verified against the data and should be treated as trusted background rather than audited facts. No action is required on the data or schema; if anything, the weakest spot is that the separability claim (c04) is a substantive analytical assertion left unverified, so a data engineer relying on it for modeling assumptions should validate it independently before depending on it.

## Per-claim verdicts

| # | claim (quoted from the card) | type | verdict | claimed | computed |
|---|---|---|---|---|---|
| 1 | The Iris dataset was used in R.A. Fisher's classic 1936 paper, [The Use of Multiple Measurements in Taxonomic Problems](http://rcs.chemometrics.ru/Tutorials/classification/Fisher.pdf), and can also be found on the [UCI Machine Learning Repository][1]. | prose_unverifiable | unverifiable (prose) | — | — |
| 2 | three iris species | category_set | holds | three iris species | 3 unique species: ['Iris-setosa', 'Iris-versicolor', 'Iris-virginica'] |
| 3 | three iris species with 50 samples each | row_count | holds | three iris species with 50 samples each | total_rows=150, species_counts={'Iris-setosa': 50, 'Iris-versicolor': 50, 'Iris-virginica': 50} |
| 4 | One flower species is linearly separable from the other two, but the other two are not linearly separable from each other. | prose_unverifiable | unverifiable (prose) | — | — |
| 5 | Id | schema | holds | Id | rows=150, nulls=0, unique=150, int_like=True |
| 6 | SepalLengthCm | schema | holds | SepalLengthCm | dtype=float64, non_numeric_count=0, n=150 |
| 7 | SepalWidthCm | schema | holds | SepalWidthCm | dtype=float64, non_numeric_count=0 |
| 8 | PetalLengthCm | schema | holds | PetalLengthCm | dtype=float64, non-null numeric count=150/150, nulls=0 |
| 9 | PetalWidthCm | schema | holds | PetalWidthCm | column 'PetalWidthCm' present=True, dtype=float64, numeric_non_null=150/150 |
| 10 | Species | schema | holds | Species | dtype=object, non-null=150, non-string-values=0 |

## Abstentions

- **demo_kaggle_iris-c01** (prose): The Iris dataset was used in R.A. Fisher's classic 1936 paper, [The Use of Multiple Measurements in Taxonomic Problems](http://rcs.chemometrics.ru/Tutorials/classification/Fisher.pdf), and can also be found on the [UCI Machine Learning Repository][1].
- **demo_kaggle_iris-c04** (prose): One flower species is linearly separable from the other two, but the other two are not linearly separable from each other.
