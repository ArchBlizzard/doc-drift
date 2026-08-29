"""Deterministic 1M-row synthetic transactions (T024) — the hard case's source.

Generated, never downloaded (research R4): numpy PCG64 with the master seed,
~25MB parquet, built by `make data` in well under a minute. The ACCURATE data
satisfies every claim in its card; case_12's violations are then planted by
the standard corruption operators, so gold stays by-construction:

- `add_category` puts 173 `XX-BAD-CODE` values into `coupon_id` only after row
  810,000 — violating the CP-##### pattern claim. coupon_id has ~2,000 heavily
  reused codes, so the bad code ranks far below any top-10 value count, and
  `describe()` unique-counts tell nothing: summary statistics provably cannot
  see it, and neither can a head sample.
- `fuzzy_coarsen` rewrites the true "Roughly 14%" coupon×express share claim
  to "Roughly 10%" — a CROSS-COLUMN share (truth 14.2%) that no per-column
  summary can compute.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from docdrift.config import MASTER_SEED

N_ROWS = 1_000_000
N_COUPON_CODES = 2_000
EXPRESS_COUPON_ROWS = 142_000  # exactly 14.2% of all rows pair coupon+express


@lru_cache(maxsize=1)
def generate() -> pd.DataFrame:
    rng = np.random.default_rng(MASTER_SEED)

    start = pd.Timestamp("2024-01-01 00:00:00")
    end = pd.Timestamp("2024-12-31 23:59:59")
    span_s = int((end - start).total_seconds())
    offsets = np.sort(rng.integers(0, span_s + 1, N_ROWS))
    offsets[0], offsets[-1] = 0, span_s  # exact coverage endpoints
    ts = start + pd.to_timedelta(offsets, unit="s")

    amount = rng.uniform(5.0, 500.0, N_ROWS).round(2)
    amount[0], amount[1] = 5.00, 500.00  # exact range endpoints

    status = rng.choice(np.array(["PLACED", "SHIPPED", "DELIVERED", "RETURNED"]),
                        N_ROWS, p=[0.2, 0.3, 0.4, 0.1])
    channel = rng.choice(np.array(["web", "app", "express"]), N_ROWS, p=[0.5, 0.3, 0.2])

    # coupons: heavy reuse over 2,000 codes; the coupon×express share is EXACT
    express_idx = np.where(channel == "express")[0]
    if len(express_idx) < EXPRESS_COUPON_ROWS:  # deterministic given the seed
        raise RuntimeError("express channel drew too few rows for the target share")
    coupon = np.full(N_ROWS, None, dtype=object)
    chosen_express = rng.choice(express_idx, EXPRESS_COUPON_ROWS, replace=False)
    coupon[chosen_express] = [f"CP-{c:05d}" for c in
                              rng.integers(0, N_COUPON_CODES, EXPRESS_COUPON_ROWS)]
    non_express = np.where(channel != "express")[0]
    with_coupon = non_express[rng.random(len(non_express)) < 0.30]
    coupon[with_coupon] = [f"CP-{c:05d}" for c in
                           rng.integers(0, N_COUPON_CODES, len(with_coupon))]

    return pd.DataFrame({
        "order_id": np.arange(1, N_ROWS + 1),
        "ts": ts,
        "amount": amount,
        "status": status,
        "channel": channel,
        "coupon_id": coupon,
    })
