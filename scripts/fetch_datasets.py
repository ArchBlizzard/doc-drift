"""One-time, builder-only fetch of the six eval source datasets (T005).

Judges never run this: the outputs are committed in data_src/ with SHA256SUMS.
Deterministic sampling = first-N rows, so re-fetching reproduces the files as
long as upstream is unchanged (checksums are the source of truth either way).

Run: uv run --with openpyxl python scripts/fetch_datasets.py
"""

from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data_src"
DATA.mkdir(exist_ok=True)

UA = {"User-Agent": "docdrift-hackathon/0.1 (dataset fetch; one-time)"}


def get(url: str) -> bytes:
    print(f"  GET {url}", flush=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def adult() -> None:
    cols = [
        "age", "workclass", "fnlwgt", "education", "education_num",
        "marital_status", "occupation", "relationship", "race", "sex",
        "capital_gain", "capital_loss", "hours_per_week", "native_country", "income",
    ]
    raw = get("https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data")
    df = pd.read_csv(io.BytesIO(raw), header=None, names=cols, skipinitialspace=True)
    df = df.dropna(how="all")
    df.to_csv(DATA / "adult.csv", index=False)
    print(f"  adult.csv: {len(df)} rows")


def penguins() -> None:
    raw = get("https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv")
    (DATA / "penguins.csv").write_bytes(raw)
    print(f"  penguins.csv: {len(pd.read_csv(io.BytesIO(raw)))} rows")


def wine() -> None:
    raw = get("https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv")
    df = pd.read_csv(io.BytesIO(raw), sep=";")
    df.to_csv(DATA / "winequality-red.csv", index=False)  # normalize to comma-separated
    print(f"  winequality-red.csv: {len(df)} rows")


def retail() -> None:
    raw = get("https://archive.ics.uci.edu/ml/machine-learning-databases/00502/online_retail_II.xlsx")
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Year 2010-2011")
    df = df.head(40_000)
    df.columns = [re.sub(r"\W+", "_", c).strip("_").lower() for c in df.columns]
    df.to_csv(DATA / "online_retail_sample.csv", index=False)
    print(f"  online_retail_sample.csv: {len(df)} rows")


def taxi() -> None:
    raw = get("https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet")
    df = pd.read_parquet(io.BytesIO(raw))
    df = df.head(50_000)
    df.to_parquet(DATA / "taxi_jan2023_50k.parquet", index=False)
    print(f"  taxi_jan2023_50k.parquet: {len(df)} rows")


def noaa() -> None:
    base = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/2023/"
    listing = get(base).decode("utf-8", errors="replace")
    names = sorted(set(re.findall(r'href="(\d{11}\.csv)"', listing)))
    if len(names) < 10:
        raise RuntimeError(f"NOAA listing yielded only {len(names)} station files")
    frames = []
    for name in names[:10]:  # deterministic: first 10 in sorted order
        frames.append(pd.read_csv(io.BytesIO(get(base + name))))
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(DATA / "noaa_gsod_sample.csv", index=False)
    print(f"  noaa_gsod_sample.csv: {len(df)} rows from {len(names[:10])} stations")


def main() -> int:
    jobs = [adult, penguins, wine, retail, taxi, noaa]
    failed: list[str] = []
    for job in jobs:
        print(f"[{job.__name__}]", flush=True)
        try:
            job()
        except Exception as exc:  # keep going; substitutions handled per T005
            print(f"  FAILED: {exc}", flush=True)
            failed.append(job.__name__)
    print(f"done. failed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
