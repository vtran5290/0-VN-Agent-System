#!/usr/bin/env python3
"""
Step 6: Single-split OOS evaluation.

Train: 2023-01-01 – 2024-12-31
Test:  2025-01-01 – latest

Selects best param per signal type on train, evaluates on test.
Computes Wilson 95% CIs for success rates.
Reports for 3 universe tracks: full / ex-VIC / ex-VIC+VHM+VRE
VPL excluded entirely.

Output:
  data/research/ema_cloud/single_split_oos_summary.csv
  data/research/ema_cloud/single_split_oos.md

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_single_split_oos.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

OUT_DIR = REPO / "data" / "research" / "ema_cloud"

TRAIN_END = "2024-12-31"
TEST_START = "2025-01-01"
MIN_TRAIN_TRADES = 30
Z95 = 1.96

UNIVERSES = {
    "full":            frozenset(),          # no exclusions beyond VPL
    "ex_VIC":          frozenset({"VIC"}),
    "ex_VIC_VHM_VRE":  frozenset({"VIC", "VHM", "VRE"}),
}


def wilson_ci(p: float, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def score_params(grp: pd.DataFrame) -> pd.Series:
    sc_col, win_col, ret_col = "trade_success_63d", "win_63d", "fwd_ret_63d"
    stats = (
        grp.groupby("param_key")
        .agg(n=(sc_col, "count"), sc=(sc_col, "mean"), wr=(win_col, "mean"), mr=(ret_col, "mean"))
        .reset_index()
    )
    stats = stats[stats["n"] >= MIN_TRAIN_TRADES]
    if stats.empty:
        return pd.Series(dtype=float)
    stats["score"] = 0.6 * stats["sc"] + 0.2 * stats["wr"] + 0.2 * stats["mr"].clip(upper=0.3)
    return stats.set_index("param_key")["score"]


def evaluate(test_sub: pd.DataFrame, param_key: str) -> dict:
    sub = test_sub[test_sub["param_key"] == param_key].copy()
    # Exclude truncated
    for h in ["63d", "126d"]:
        tc = f"is_truncated_{h}"
        if tc in sub.columns:
            sub = sub[sub[tc] == 0]
    n_all = len(sub)
    if n_all == 0:
        return {}
    r: dict = {"param_key": param_key, "n": n_all}
    for h in ["63d", "126d"]:
        ret_col = f"fwd_ret_{h}"
        sc_col = f"trade_success_{h}"
        win_col = f"win_{h}"
        if ret_col not in sub.columns:
            continue
        g = sub[ret_col].dropna()
        if len(g) == 0:
            continue
        p_success = float(sub[sc_col].mean())
        p_win = float(sub[win_col].mean())
        ci_lo, ci_hi = wilson_ci(p_success, len(g))
        r[f"n_{h}"] = len(g)
        r[f"success_rate_{h}"] = round(p_success, 4)
        r[f"success_ci95_lo_{h}"] = ci_lo
        r[f"success_ci95_hi_{h}"] = ci_hi
        r[f"win_rate_{h}"] = round(p_win, 4)
        r[f"mean_ret_{h}"] = round(float(g.mean()), 4)
        r[f"median_ret_{h}"] = round(float(g.median()), 4)
    return r


def main():
    log.info("Loading trades.csv...")
    trades = pd.read_csv(OUT_DIR / "trades.csv")
    trades["signal_date"] = pd.to_datetime(trades["signal_date"])
    trades = trades[~trades["symbol"].isin({"VPL"})].copy()

    # Exclude truncated from train scoring
    train_mask = trades["signal_date"] <= pd.Timestamp(TRAIN_END)
    test_mask = trades["signal_date"] >= pd.Timestamp(TEST_START)
    if "is_truncated_63d" in trades.columns:
        train_mask_clean = train_mask & (trades["is_truncated_63d"] == 0)
    else:
        train_mask_clean = train_mask

    train_df = trades[train_mask_clean].copy()
    test_df = trades[test_mask].copy()

    log.info(f"Train (clean, ≤{TRAIN_END}): {len(train_df):,} rows")
    log.info(f"Test  (≥{TEST_START}): {len(test_df):,} rows")

    results = []
    signal_types = ["all", "breakout", "retest", "reclaim"]

    for uname, exclude_syms in UNIVERSES.items():
        train_u = train_df[~train_df["symbol"].isin(exclude_syms)].copy()
        test_u = test_df[~test_df["symbol"].isin(exclude_syms)].copy()

        for sig_type in signal_types:
            train_sub = train_u if sig_type == "all" else train_u[train_u["signal_type"] == sig_type]
            test_sub = test_u if sig_type == "all" else test_u[test_u["signal_type"] == sig_type]

            scores = score_params(train_sub)
            if scores.empty:
                log.warning(f"  No qualifying params: {uname}/{sig_type}")
                continue
            best_key = scores.idxmax()
            ev = evaluate(test_sub, best_key)
            if not ev:
                log.warning(f"  Empty test: {uname}/{sig_type} param={best_key}")
                continue
            ev.update({
                "universe": uname,
                "signal_type": sig_type,
                "train_n": len(train_sub[train_sub["param_key"] == best_key]),
            })
            results.append(ev)
            log.info(f"  {uname}/{sig_type}: best={best_key[:30]}... n_test={ev.get('n',0)} "
                     f"success_63d={ev.get('success_rate_63d','?')}")

    out_df = pd.DataFrame(results)
    csv_path = OUT_DIR / "single_split_oos_summary.csv"
    out_df.to_csv(csv_path, index=False)
    log.info(f"Saved {csv_path}")

    # ── Markdown report ────────────────────────────────────────────────────────
    lines = [
        "# Single-Split OOS Summary",
        "",
        f"**Train:** 2023-01-01 – {TRAIN_END}  ",
        f"**Test:**  {TEST_START} – latest  ",
        "**VPL:** excluded entirely  ",
        "**CIs:** Wilson 95%  ",
        "",
        "---",
        "",
    ]
    for uname in UNIVERSES:
        lines.append(f"## Universe: {uname}")
        lines.append("")
        lines.append("| Signal | n_test | success_63d | CI 95% | win_rate_63d | mean_ret_63d | best_param |")
        lines.append("|--------|--------|-------------|--------|--------------|--------------|------------|")
        for sig_type in signal_types:
            row = next((r for r in results if r["universe"] == uname and r["signal_type"] == sig_type), None)
            if row is None:
                lines.append(f"| {sig_type} | — | — | — | — | — | — |")
                continue
            ci = f"[{row.get('success_ci95_lo_63d','?')}, {row.get('success_ci95_hi_63d','?')}]"
            pk = row.get("param_key", "?")[:40]
            lines.append(
                f"| {sig_type} | {row.get('n',0)} | {row.get('success_rate_63d','?')} | {ci} "
                f"| {row.get('win_rate_63d','?')} | {row.get('mean_ret_63d','?')} | `{pk}` |"
            )
        lines.append("")

    lines.extend([
        "## Interpretation Notes",
        "",
        "- CI width is driven by test-period n. Wide CIs = statistically underpowered.",
        "- VIC/VHM concentration effect: compare full vs ex_VIC_VHM_VRE to isolate.",
        "- Retest/reclaim counts are small — treat as directional only.",
        "",
        "## Raw data",
        f"See `single_split_oos_summary.csv`.",
    ])

    md_path = OUT_DIR / "single_split_oos.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Saved {md_path}")

    print("\n=== SINGLE-SPLIT OOS (63d) ===")
    cols = ["universe", "signal_type", "n", "success_rate_63d", "success_ci95_lo_63d",
            "success_ci95_hi_63d", "mean_ret_63d", "param_key"]
    cols = [c for c in cols if c in out_df.columns]
    print(out_df[cols].sort_values(["universe", "signal_type"]).to_string(index=False))


if __name__ == "__main__":
    main()
