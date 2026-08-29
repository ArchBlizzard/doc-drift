import pandas as pd

from docdrift.tools.profile import snapshot


def test_snapshot_caps_rows_and_lists_dtypes():
    df = pd.DataFrame({"a": range(100), "b": ["x"] * 100})
    snap = snapshot(df)
    assert "a" in snap and "b" in snap and "int64" in snap
    # header line + 20 data rows in the CSV block, never the full frame
    csv_block = snap.split("ROWS (CSV):\n")[1]
    assert len(csv_block.strip().splitlines()) == 21
    assert "99" not in csv_block  # row 99 must not leak


def test_snapshot_never_discloses_row_count():
    df = pd.DataFrame({"a": range(37)})
    assert "37" not in snapshot(df).split("ROWS (CSV):\n")[0]
