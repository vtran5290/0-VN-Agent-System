"""De-clustered event study (non-overlapping events)."""
from __future__ import annotations

import pandas as pd

EVENT_SPECS = [
    ("dist25_ge4", lambda r: r["dist_count_25d"] >= 4),
    ("dist25_ge5", lambda r: r["dist_count_25d"] >= 5),
    ("dist10_ge3", lambda r: r["dist_count_10d"] >= 3),
    (
        "dist25_ge4_below_ema20",
        lambda r: (r["dist_count_25d"] >= 4) & (r.get("close_above_ema20", 1) < 1),
    ),
    (
        "dist25_ge5_below_ema50",
        lambda r: (r["dist_count_25d"] >= 5) & (r.get("close_above_ema50", 1) < 1),
    ),
]


def run_event_study(df: pd.DataFrame, *, index_view: str, skip_days: int = 25) -> pd.DataFrame:
    rows = []
    i = 0
    while i < len(df):
        row = df.iloc[i]
        fired = False
        for etype, pred in EVENT_SPECS:
            try:
                hit = bool(pred(row))
            except Exception:
                hit = False
            if not hit:
                continue
            if fired:
                continue
            rec = {
                "event_date": row["date"],
                "index_view": index_view,
                "event_type": etype,
                "dist_count_10d": row.get("dist_count_10d"),
                "dist_count_25d": row.get("dist_count_25d"),
                "dist_count_50d": row.get("dist_count_50d"),
                "close_above_ema20": row.get("close_above_ema20"),
                "close_above_ema50": row.get("close_above_ema50"),
            }
            for h in (5, 10, 25, 75, 100):
                rc = f"fwd_ret_{h}d"
                dc = f"max_dd_{h}d"
                if rc in row.index:
                    rec[rc] = row[rc]
                if dc in row.index:
                    rec[dc] = row[dc]
            rows.append(rec)
            fired = True
        i += skip_days if fired else 1
    return pd.DataFrame(rows)
