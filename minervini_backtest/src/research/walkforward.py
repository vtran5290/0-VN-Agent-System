"""
Expanding walk-forward split definitions (calendar-based).

Each split k has a train window [train_start, train_end] and validation [val_start, val_end].
An event on `event_date` is tagged per split as train or oos (mutually exclusive for a given split).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import pandas as pd


@dataclass(frozen=True)
class WalkForwardSplit:
    split_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp


def default_splits() -> list[WalkForwardSplit]:
    """Fixed expanding windows per spec (validate year / YTD)."""
    return [
        WalkForwardSplit(
            "wf_2018_2021_val_2022",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2021-12-31"),
            pd.Timestamp("2022-01-01"),
            pd.Timestamp("2022-12-31"),
        ),
        WalkForwardSplit(
            "wf_2018_2022_val_2023",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2022-12-31"),
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-12-31"),
        ),
        WalkForwardSplit(
            "wf_2018_2023_val_2024",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2023-12-31"),
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-12-31"),
        ),
        WalkForwardSplit(
            "wf_2018_2024_val_2025",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2024-12-31"),
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2025-12-31"),
        ),
        WalkForwardSplit(
            "wf_2018_2025_val_2026_ytd",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2025-12-31"),
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-12-31"),
        ),
    ]


def fold_for_date(split: WalkForwardSplit, event_date: pd.Timestamp) -> str | None:
    """
    Return 'train', 'oos', or None if the date is outside both windows for this split.
    Boundaries inclusive on all ends.
    """
    d = pd.Timestamp(event_date).normalize()
    if split.train_start <= d <= split.train_end:
        return "train"
    if split.val_start <= d <= split.val_end:
        return "oos"
    return None


def iter_event_split_rows(
    splits: list[WalkForwardSplit],
    event_date: pd.Timestamp,
) -> Iterator[tuple[str, str]]:
    """Yield (split_id, fold) for every split where the event falls in train or oos."""
    d = pd.Timestamp(event_date)
    for sp in splits:
        f = fold_for_date(sp, d)
        if f is not None:
            yield sp.split_id, f
