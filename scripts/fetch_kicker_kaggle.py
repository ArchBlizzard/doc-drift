"""Fetch a Kaggle real-world kicker case (T032 addendum).

Downloads a public Kaggle dataset's own description (saved VERBATIM as the
data card) and its CSV via the Kaggle API. Credentials come from
%USERPROFILE%/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY env vars —
NEVER from this repository (hackathon ground rule 08).

Default target: uciml/iris (CC0) — a claim-rich classic card (three species,
50 samples each, named columns).

Run: uv run python scripts/fetch_kicker_kaggle.py [owner/slug] [csv-name]
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docdrift.config import CASES_DIR

API = "https://www.kaggle.com/api/v1"


def credentials() -> tuple[str, str]:
    user, key = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    if not (user and key):
        cfg = Path.home() / ".kaggle" / "kaggle.json"
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            user, key = data.get("username"), data.get("key")
    if not (user and key):
        print("no Kaggle credentials (kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY)", file=sys.stderr)
        sys.exit(2)
    return user, key


def get(url: str, user: str, key: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "docdrift-hackathon/0.1 (one-time kicker fetch)",
        "Authorization": "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode(),
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "uciml/iris"
    csv_name = sys.argv[2] if len(sys.argv) > 2 else "Iris.csv"
    user, key = credentials()

    meta = json.loads(get(f"{API}/datasets/view/{ref}", user, key))
    description = meta.get("description") or ""
    if not description.strip():
        print(f"dataset {ref} has no description to audit", file=sys.stderr)
        return 4

    blob = get(f"{API}/datasets/download/{ref}", user, key)
    case_id = "demo_kaggle_" + ref.split("/")[1].replace("-", "_")
    out = CASES_DIR / case_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "datacard.md").write_text(description, encoding="utf-8", newline="\n")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
        target = csv_name if csv_name in names else next(n for n in names if n.endswith(".csv"))
        (out / "data.csv").write_bytes(zf.read(target))

    print(f"dataset: {ref}  license: {meta.get('licenseName')}  title: {meta.get('title')}")
    print(f"card: {len(description)} chars; data: {target} "
          f"({(out / 'data.csv').stat().st_size} bytes) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
