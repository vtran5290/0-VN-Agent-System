from __future__ import annotations

"""
Example:
    python -m regime.validate_combined_regime --csv data/combined_regime_log_2012_now.csv
"""

import argparse
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


KEY_COLS = [
    "date",
    "close",
    "market_status_combined",
    "rally_day_count",
    "ftd_date",
    "ftd_valid",
    "distribution_count_20d",
    "ma50_break_flag",
    "allow_new_buys",
]

STATUS_COL = "market_status_combined"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate combined (primary+tactical) market regime log.")
    parser.add_argument("--csv", required=True, help="Path to combined_regime_log.csv")
    parser.add_argument(
        "--horizons",
        default="20,40",
        help="Comma-separated forward return horizons (e.g., '20,40')",
    )
    parser.add_argument(
        "--dd_threshold",
        type=float,
        default=-0.15,
        help="Drawdown threshold (default: -0.15 = -15%)",
    )
    parser.add_argument(
        "--timeout_days",
        type=int,
        default=120,
        help="Timeout in trading days for drawdown event (default: 120)",
    )
    return parser.parse_args()


def _find_blocks(status_series: pd.Series) -> List[Tuple[str, int, int]]:
    """Return list of (state, start_idx, end_idx) contiguous blocks."""
    blocks: List[Tuple[str, int, int]] = []
    current_state: str | None = None
    start_idx: int | None = None

    for i, s in enumerate(status_series.tolist()):
        if current_state is None:
            current_state = s
            start_idx = i
            continue
        if s != current_state:
            blocks.append((current_state, start_idx, i - 1))
            current_state = s
            start_idx = i
    if current_state is not None and start_idx is not None:
        blocks.append((current_state, start_idx, len(status_series) - 1))
    return blocks


def _head_tail(df: pd.DataFrame) -> None:
    cols = [c for c in KEY_COLS if c in df.columns]
    print("=== HEAD (3 rows) ===")
    print(df[cols].head(3).to_string(index=False))
    print("\n=== TAIL (3 rows) ===")
    print(df[cols].tail(3).to_string(index=False))


def _summary_per_state(df: pd.DataFrame) -> None:
    print("\n=== SUMMARY PER MARKET STATUS (COMBINED) ===")
    n_total = len(df)
    status_series = df[STATUS_COL].astype(str)
    blocks = _find_blocks(status_series)

    # group blocks by state
    blocks_by_state: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for state, start, end in blocks:
        blocks_by_state[state].append((start, end))

    allow = df["allow_new_buys"].astype(bool) if "allow_new_buys" in df.columns else None

    print(
        "state | n_days | pct_days | n_blocks | median_block_len | max_block_len | pct_allow_new_buys_true"
    )
    for state in sorted(status_series.unique()):
        mask = status_series == state
        n_days = int(mask.sum())
        pct_days = n_days / n_total * 100.0 if n_total else 0.0
        blocks_state = blocks_by_state.get(state, [])
        if blocks_state:
            lengths = [end - start + 1 for start, end in blocks_state]
            median_len = float(np.median(lengths))
            max_len = int(max(lengths))
        else:
            median_len = 0.0
            max_len = 0
        if allow is not None:
            pct_allow_true = allow[mask].mean() * 100.0 if n_days else 0.0
        else:
            pct_allow_true = 0.0
        print(
            f"{state:22s} | {n_days:6d} | {pct_days:8.2f} | {len(blocks_state):8d} |"
            f" {median_len:16.2f} | {max_len:12d} | {pct_allow_true:24.2f}"
        )


def _compute_forward_returns(
    df: pd.DataFrame, horizons: Iterable[int]
) -> Dict[int, Dict[str, Dict[str, float]]]:
    """Return nested dict[h][state][metric] for overlapping/non-overlap medians and excess."""
    result: Dict[int, Dict[str, Dict[str, float]]] = {}
    close = df["close"].astype(float)
    status = df[STATUS_COL].astype(str)

    blocks = _find_blocks(status)
    blocks_by_state: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for state, start, end in blocks:
        blocks_by_state[state].append((start, end))

    for h in horizons:
        fr = close.shift(-h) / close - 1.0  # overlapping forward returns
        all_mask = fr.notna()
        all_overlapping = fr[all_mask]
        all_med_overlapping = float(all_overlapping.median()) if len(all_overlapping) else np.nan

        # Non-overlap: first day of each contiguous block (regardless of state)
        global_block_starts = [start for _, start, _ in blocks]
        non_overlap_all = fr.iloc[global_block_starts]
        non_overlap_all = non_overlap_all[non_overlap_all.notna()]
        all_med_non_overlap = float(non_overlap_all.median()) if len(non_overlap_all) else np.nan

        state_metrics: Dict[str, Dict[str, float]] = {}
        for state_name in sorted(status.unique()):
            state_mask = status == state_name

            overlapping_state = fr[state_mask & fr.notna()]
            med_ovl = float(overlapping_state.median()) if len(overlapping_state) else np.nan

            # Non-overlap: first day of each block of this state
            block_starts = [start for (start, end) in blocks_by_state.get(state_name, [])]
            if block_starts:
                non_overlap_state = fr.iloc[block_starts]
                non_overlap_state = non_overlap_state[non_overlap_state.notna()]
                med_nonovl = (
                    float(non_overlap_state.median()) if len(non_overlap_state) else np.nan
                )
            else:
                med_nonovl = np.nan

            excess_ovl = med_ovl - all_med_overlapping if not np.isnan(med_ovl) else np.nan
            excess_nonovl = (
                med_nonovl - all_med_non_overlap if not np.isnan(med_nonovl) else np.nan
            )

            state_metrics[state_name] = {
                "median_overlapping": med_ovl,
                "median_non_overlap": med_nonovl,
                "excess_overlapping": excess_ovl,
                "excess_non_overlap": excess_nonovl,
            }

        result[h] = {
            "__ALL__": {
                "median_overlapping": all_med_overlapping,
                "median_non_overlap": all_med_non_overlap,
                "excess_overlapping": 0.0,
                "excess_non_overlap": 0.0,
            },
            **state_metrics,
        }
    return result


def _print_forward_returns_summary(
    metrics: Dict[int, Dict[str, Dict[str, float]]], horizons: Iterable[int]
) -> None:
    print("\n=== FORWARD RETURN VALIDATION (COMBINED) ===")
    for h in horizons:
        print(f"\n-- Horizon H={h} days --")
        print("state | med_ovl | med_nonovl | excess_ovl | excess_nonovl")
        per_state = metrics[h]
        for state in sorted(per_state.keys()):
            data = per_state[state]
            mo = data["median_overlapping"]
            mn = data["median_non_overlap"]
            eo = data["excess_overlapping"]
            en = data["excess_non_overlap"]
            print(f"{state:22s} | {mo:8.4f} | {mn:11.4f} | {eo:10.4f} | {en:13.4f}")


def _detect_drawdown_events(
    df: pd.DataFrame, dd_threshold: float, timeout_days: int
) -> List[Dict[str, object]]:
    """Deterministic major drawdown event detection."""
    closes = df["close"].astype(float).values
    dates = pd.to_datetime(df["date"]).dt.date.values
    states = df[STATUS_COL].astype(str).values

    events: List[Dict[str, object]] = []

    rolling_peak = None
    rolling_peak_idx = None
    event_active = False
    event_start_idx = None
    trough_idx = None
    trough_price = None

    for i, close in enumerate(closes):
        if rolling_peak is None or close > rolling_peak:
            rolling_peak = close
            rolling_peak_idx = i

        if not event_active:
            if rolling_peak is None:
                continue
            dd = close / rolling_peak - 1.0
            if dd <= dd_threshold:
                event_active = True
                event_start_idx = i
                trough_idx = i
                trough_price = close
        else:
            # update trough
            if trough_price is None or close < trough_price:
                trough_price = close
                trough_idx = i

            # check end conditions
            dd = close / rolling_peak - 1.0
            duration = i - event_start_idx  # inclusive-ish; lag style
            end_due_to_new_high = close > rolling_peak
            end_due_to_timeout = duration >= timeout_days

            if end_due_to_new_high or end_due_to_timeout or i == len(closes) - 1:
                if rolling_peak_idx is not None and trough_idx is not None:
                    peak_date = dates[rolling_peak_idx]
                    trough_date = dates[trough_idx]
                    dd_pct = float(trough_price / rolling_peak - 1.0) if rolling_peak else 0.0
                    state_at_peak = states[rolling_peak_idx]
                    events.append(
                        {
                            "peak_idx": rolling_peak_idx,
                            "peak_date": peak_date,
                            "trough_date": trough_date,
                            "dd_pct": dd_pct,
                            "market_status_at_peak": state_at_peak,
                        }
                    )
                event_active = False
                event_start_idx = None
                trough_idx = None
                trough_price = None
                # reset rolling_peak after event
                rolling_peak = close
                rolling_peak_idx = i

    return events


def _drawdown_summary_and_lag(
    df: pd.DataFrame,
    events: List[Dict[str, object]],
) -> None:
    print("\n=== MAJOR DRAWDOWN EVENTS (COMBINED) ===")
    n_events = len(events)
    print(f"Number of events: {n_events}")
    if not events:
        return

    # starting state distribution
    start_states = [e["market_status_at_peak"] for e in events]
    dist = Counter(start_states)
    print("Starting state distribution (count):")
    for state, cnt in dist.items():
        print(f"  {state}: {cnt}")

    # drawdown stats for confirmed_uptrend
    dd_confirmed = [
        e["dd_pct"] for e in events if e["market_status_at_peak"] == "confirmed_uptrend"
    ]
    if dd_confirmed:
        max_dd = min(dd_confirmed)
        med_dd = float(np.median(dd_confirmed))
    else:
        max_dd = np.nan
        med_dd = np.nan
    print(f"max_dd_starting_in_confirmed: {max_dd:.4f}")
    print(f"median_dd_starting_in_confirmed: {med_dd:.4f}")

    # Defensive transition lag
    print("\n=== DEFENSIVE TRANSITION LAG (COMBINED) ===")
    status = df[STATUS_COL].astype(str).values
    lags: List[int] = []
    slow_confirmed_count = 0
    defensive_set = {"correction", "downtrend"}

    for e in events:
        peak_idx = int(e["peak_idx"])
        peak_state = str(e["market_status_at_peak"])

        lag = None
        for j in range(peak_idx, len(status)):
            if status[j] in defensive_set:
                lag = j - peak_idx
                break
        if lag is not None:
            lags.append(lag)
            if peak_state == "confirmed_uptrend" and lag > 10:
                slow_confirmed_count += 1

    if lags:
        median_lag = float(np.median(lags))
        max_lag = int(max(lags))
    else:
        median_lag = np.nan
        max_lag = np.nan

    print(f"median_defensive_transition_lag_days: {median_lag}")
    print(f"max_defensive_transition_lag_days: {max_lag}")
    print(
        "count_events_start_confirmed_with_lag_gt_10: "
        f"{slow_confirmed_count}"
    )


def main() -> None:
    args = parse_args()
    horizons = [int(x) for x in args.horizons.split(",") if x.strip()]

    df = pd.read_csv(args.csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    _head_tail(df)
    _summary_per_state(df)

    fr_metrics = _compute_forward_returns(df, horizons)
    _print_forward_returns_summary(fr_metrics, horizons)

    events = _detect_drawdown_events(df, args.dd_threshold, args.timeout_days)
    _drawdown_summary_and_lag(df, events)


if __name__ == "__main__":
    main()

