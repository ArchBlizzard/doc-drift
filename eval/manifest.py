"""Shared loading of datasets, cards, and claim manifests (T007/T008)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from corruptions import ManifestClaim
from docdrift.config import CARDS_DIR, DATA_SRC

DATASETS: dict[str, str] = {
    "adult": "adult.csv",
    "penguins": "penguins.csv",
    "winequality-red": "winequality-red.csv",
    "online_retail_sample": "online_retail_sample.csv",
    "taxi_jan2023_50k": "taxi_jan2023_50k.parquet",
    "noaa_gsod_sample": "noaa_gsod_sample.csv",
}


def dataset_path(name: str) -> Path:
    return DATA_SRC / DATASETS[name]


def load_dataset(name: str) -> pd.DataFrame:
    path = dataset_path(name)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def load_card(name: str) -> str:
    return (CARDS_DIR / f"{name}.md").read_text(encoding="utf-8")


def load_manifest(name: str) -> list[ManifestClaim]:
    raw = yaml.safe_load((CARDS_DIR / f"{name}.claims.yaml").read_text(encoding="utf-8"))
    return [ManifestClaim(**c) for c in raw["claims"]]
