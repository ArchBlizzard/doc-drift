"""Fetch the real-world kicker case (T032): OpenML `credit-g` (dataset 31).

A REAL, UNMODIFIED data card: the dataset's own OpenML description is saved
verbatim as datacard.md, and the CSV is downloaded as-is. Nothing is planted —
whatever DocDrift finds is genuine documentation drift. (Kaggle was the
original target but requires an API token; OpenML is public and
unauthenticated — substitution disclosed in tasks.md/PROVENANCE.)

Run: uv run python scripts/fetch_kicker.py   -> cases/demo_credit_g/
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docdrift.config import CASES_DIR

DATA_URL = "https://www.openml.org/data/get_csv/31/dataset_31_credit-g.arff"
META_URL = "https://www.openml.org/api/v1/json/data/31"
UA = {"User-Agent": "docdrift-hackathon/0.1 (one-time kicker fetch)"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main() -> int:
    out = CASES_DIR / "demo_credit_g"
    out.mkdir(parents=True, exist_ok=True)

    meta = json.loads(get(META_URL))["data_set_description"]
    (out / "datacard.md").write_text(meta["description"], encoding="utf-8", newline="\n")
    (out / "data.csv").write_bytes(get(DATA_URL))

    print(f"name: {meta['name']}  version: {meta['version']}  licence: {meta.get('licence')}")
    print(f"card: {len(meta['description'])} chars -> {out / 'datacard.md'}")
    print(f"data: {(out / 'data.csv').stat().st_size} bytes -> {out / 'data.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
