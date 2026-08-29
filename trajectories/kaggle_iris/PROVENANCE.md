# Kaggle real-world run — provenance (T032 addendum)

**Dataset:** `uciml/iris` (Iris Species), Kaggle.
**License:** CC0: Public Domain (per the Kaggle API dataset metadata).
**Accessed:** 2026-08-29 via `scripts/fetch_kicker_kaggle.py` — Kaggle API v1, authenticated with the participant's own account credentials (stored locally in `~/.kaggle/kaggle.json`, never in this repository).

**What is unmodified:** `datacard.md` is the dataset's own Kaggle description, byte-for-byte; `data.csv` is `Iris.csv` from the official download, untouched. Out-of-contract demo run (ad-hoc case id, no gold labels).

**Result (see audit.md):** the complementary demo to the credit-g run — a card that survives the audit. All checkable claims verified against the full file: exactly three species with 50 samples each (computed 50/50/50), all six documented columns present with expected types, 150 rows. The two prose claims (Fisher 1936 provenance, linear-separability remark) correctly abstained. 8 checks gated, zero rejections. DocDrift certifies good documentation with computed evidence — it does not only find fault.
