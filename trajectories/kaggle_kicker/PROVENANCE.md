# Real-world kicker — provenance (T032)

**Dataset:** `credit-g` (German Credit), OpenML dataset id 31, version 1.
**Source URLs:** data `https://www.openml.org/data/get_csv/31/dataset_31_credit-g.arff` · description `https://www.openml.org/api/v1/json/data/31` · upstream: UCI Statlog (German Credit Data), Dr. Hans Hofmann, 1994.
**License:** listed as "Public" on OpenML; upstream UCI citation policy referenced in the card itself.
**Accessed:** 2026-08-29 via `scripts/fetch_kicker.py` (re-runnable by judges — no auth needed).

**Substitution note:** tasks.md originally targeted a Kaggle dataset; the Kaggle API requires an account token, so a public, unauthenticated source with an equally real data card was used instead. Disclosed here and in tasks.md.

**What is unmodified:** `datacard.md` is the dataset's own OpenML description, byte-for-byte; `data.csv` is the download, untouched. Nothing was planted. This run is explicitly out-of-contract for the eval harness (ad-hoc case id, no gold labels) — it exists to show DocDrift on documentation nobody prepared for it.

**Genuine findings (see audit.md):**
1. The card documents attribute 19 as "Telephone (yes,no)" — the data encodes `none`/`yes`. Any filter or encoder written against the documented `no` label silently matches zero rows.
2. Attribute 10 "Other debtors / guarantors": 41 rows carry values outside the three categories the check derived from the card's description.
19 further claims verified as holding; 6 prose claims correctly abstained.
