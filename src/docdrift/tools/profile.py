"""Profile snapshot (T014): the ONLY raw data the agent's model ever sees.

dtypes plus head(20) — Constitution V / FR-006. The full file is touched only
by the sandboxed executor, on disk.
"""

from __future__ import annotations

import pandas as pd

HEAD_ROWS = 20


def snapshot(df: pd.DataFrame, head_rows: int = HEAD_ROWS) -> str:
    return (
        f"ROWS: not disclosed (compute via checks)\n\n"
        f"COLUMN DTYPES:\n{df.dtypes.to_string()}\n\n"
        f"FIRST {head_rows} ROWS (CSV):\n{df.head(head_rows).to_csv(index=False)}"
    )
