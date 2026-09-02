"""
Shared filter infrastructure for Cortex Book #2: S1 (52-week high proximity) and
S2 (breakout volume filter).

Both filters apply to the A3_RS entry signal stream as selection overlays — they
reduce WHICH signals enter the system, not how those signals are sized. D3 sector
slot sizing is unchanged.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pp_backtest.cortex_book1_common import (
    IS_WINDOW,
    OOS_WINDOW,
    PANEL_END,
    PANEL_START,
    _fmt_pct,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    RESEARCH_LABEL,
    apply_size,
    assert_frozen_a3,
    prepare_trades_with_size,
    run_capital_sim,
    signal_stream,
)
from pp_backtest.p0_realism_p1_winner import _build_honest_cache
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_last_months,
    slice_equity_years,
)

REPO = Path(__file__).resolve().parents[1]

# ── Gate parameters (from pre-registrations) ─────────────────────────────────
# Both S1 and S2 use the same baseline and gate margin.
BASE_OOS_MAR = 0.8386  # confirmed from cortex_book1_sizing_meta.json
G1A_BASE_MARGIN = 0.050  # base margin before k-adjustment
K = 3  # three thresholds each
# k-adjustment: base + 0.010 * log2(k) per PROPAGATION_PROTOCOL
G1A_K_ADJ = 0.010 * np.log2(K)  # ≈ 0.016
G1A_MARGIN_ADJUSTED = G1A_BASE_MARGIN + G1A_K_ADJ  # 0.066
G1A_THRESHOLD = BASE_OOS_MAR + G1A_MARGIN_ADJUSTED  # 0.9046

G1B_FLOOR = 0.500
G1B_ADJ = G1B_FLOOR + G1A_K_ADJ  # 0.516

# OOS sub-windows (pre-committed, consistent S1 and S2)
OOS_SUB_WINDOW_A = (2020, 2022)  # 3 years
OOS_SUB_WINDOW_B = (2023, 2026)  # 4 years
N_OOS_MIN_FULL = 30
N_OOS_MIN_SUBWINDOW = 12

# ── S1 thresholds: proximity to 52-week high ─────────────────────────────────
# entry allowed when: signal_close >= 52w_high * (1 - X)
# X = 0.15 → within 15%; X = 0.20 → within 20%; X = 0.25 → within 25%
S1_PROXIMITY_THRESHOLDS = [0.85, 0.80, 0.75]  # 1 - X, so 15%/20%/25%
S1_PROXIMITY_LABELS = ["within_15pct", "within_20pct", "within_25pct"]

# ── S2 thresholds: volume multiple of 50d average ────────────────────────────
S2_VOLUME_THRESHOLDS = [1.2, 1.3, 1.4]
S2_VOLUME_LABELS = ["vol_1_2x", "vol_1_3x", "vol_1_4x"]


# ─────────────────────────────────────────────────────────────────────────────
# Signal-day filter map construction
# ─────────────────────────────────────────────────────────────────────────────

def build_signal_filter_map(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], dict]:
    """
    For every A3_RS signal event, compute filter metrics from the SIGNAL BAR (not entry bar).

    Returns:
        dict keyed by (symbol, entry_date) ->
            {
                'prox': float,    # signal_close / 52w_rolling_high  (S1)
                'vol_mult': float # signal_bar_volume / vol50d_avg   (S2)
                'n_sig_bars': int # number of bars with valid signal date in panel
            }

    Signal bar = the bar where A3_RS fires.
    Entry bar  = signal bar + 1 (T+1 next-open fill).

    Point-in-time discipline:
        - 52w high: max(high[si-251 : si+1]) — includes signal bar high.
        - vol50d_avg: mean(volume[si-50 : si]) — EXCLUDES signal bar volume to avoid look-ahead.
    """
    cache = _build_honest_cache(panel)

    # Build volume lookup from panel: (symbol, date) -> (volume, vol50d_avg_prior_50)
    vol_lookup: dict[tuple[str, pd.Timestamp], tuple[float, float]] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        sdf_dates = pd.to_datetime(sdf["date"])
        vol = sdf["volume"].astype(float)
        vol_pos = vol.where(vol > 0, np.nan)
        # shift(1) = prior 50 bars only, not today — point-in-time
        vol50 = vol_pos.rolling(50, min_periods=10).mean().shift(1)
        for i in range(len(sdf)):
            d = sdf_dates.iloc[i].normalize()
            v_today = float(vol.iloc[i]) if pd.notna(vol.iloc[i]) else 0.0
            v50 = float(vol50.iloc[i]) if pd.notna(vol50.iloc[i]) else 0.0
            vol_lookup[(str(sym), d)] = (v_today, v50)

    out: dict[tuple[str, pd.Timestamp], dict] = {}
    for sym, data in cache.items():
        dates = pd.to_datetime(data["dates"])
        close = data["close"]      # np.ndarray
        high = data["high"]        # np.ndarray

        for si in data["sig_idxs"]:
            entry_i = si + 1
            if entry_i >= len(dates):
                continue
            entry_dt = pd.Timestamp(dates[entry_i]).normalize()
            sig_dt = pd.Timestamp(dates[si]).normalize()

            # S1: proximity to 52-week rolling high (at signal bar, look-back 252 bars)
            lb_start = max(0, si - 251)
            high52w = float(np.max(high[lb_start : si + 1]))
            prox = float(close[si]) / high52w if high52w > 0 else 0.0

            # S2: volume multiple (signal bar volume vs prior 50-bar average)
            vkey = (str(sym), sig_dt)
            if vkey in vol_lookup:
                vol_today, vol50d_avg = vol_lookup[vkey]
                vol_mult = vol_today / vol50d_avg if vol50d_avg > 0 else 0.0
            else:
                vol_mult = 0.0

            out[(str(sym), entry_dt)] = {
                "prox": prox,
                "vol_mult": vol_mult,
            }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Trade filtering
# ─────────────────────────────────────────────────────────────────────────────

def apply_proximity_filter(
    trades: pd.DataFrame,
    filter_map: dict[tuple[str, pd.Timestamp], dict],
    min_prox: float,
) -> pd.DataFrame:
    """
    Keep only trades where signal bar close >= 52w_high * min_prox.

    Layman: only enter when price is already near its yearly peak, not deep in a hole.
    """
    trades = trades.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    mask = []
    for _, row in trades.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = filter_map.get(key)
        if rec is None:
            mask.append(False)
        else:
            mask.append(rec["prox"] >= min_prox)
    return trades[mask].reset_index(drop=True)


def apply_volume_filter(
    trades: pd.DataFrame,
    filter_map: dict[tuple[str, pd.Timestamp], dict],
    min_vol_mult: float,
) -> pd.DataFrame:
    """
    Keep only trades where signal bar volume >= min_vol_mult × vol50d_avg.

    Layman: only enter when today's trading activity is noticeably busier than usual.
    """
    trades = trades.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    mask = []
    for _, row in trades.iterrows():
        key = (str(row["symbol"]), pd.Timestamp(row["entry_date"]).normalize())
        rec = filter_map.get(key)
        if rec is None:
            mask.append(False)
        else:
            mask.append(rec["vol_mult"] >= min_vol_mult)
    return trades[mask].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Gate evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_gates_book2(
    m_base_oos: dict[str, float],
    m_cand_oos: dict[str, float],
    m_cand_oos_a: dict[str, float],
    m_cand_oos_b: dict[str, float],
    n_oos_full: int,
    n_oos_sub_a: int,
    n_oos_sub_b: int,
) -> tuple[list[dict], str]:
    """
    Evaluate pre-registered gates for Book 2 (S1 or S2).

    G1a: candidate OOS MAR >= baseline OOS MAR + G1A_MARGIN_ADJUSTED
    G1b: candidate OOS MAR >= G1B_ADJ (absolute floor)
    N_OOS: >= 30 full OOS, >= 12 each sub-window
    Neg-OOS cap: if both base and cand OOS MAR < 0 → CONDITIONAL-ADVANCE cap
    """
    g1a = (
        np.isfinite(m_cand_oos["mar"])
        and np.isfinite(m_base_oos["mar"])
        and m_cand_oos["mar"] >= m_base_oos["mar"] + G1A_MARGIN_ADJUSTED
    )
    g1b = np.isfinite(m_cand_oos["mar"]) and m_cand_oos["mar"] >= G1B_ADJ
    n_ok_full = n_oos_full >= N_OOS_MIN_FULL
    n_ok_a = n_oos_sub_a >= N_OOS_MIN_SUBWINDOW
    n_ok_b = n_oos_sub_b >= N_OOS_MIN_SUBWINDOW
    both_neg = (
        np.isfinite(m_base_oos["mar"])
        and np.isfinite(m_cand_oos["mar"])
        and m_base_oos["mar"] < 0
        and m_cand_oos["mar"] < 0
    )
    details = [
        {
            "id": "G1a",
            "criterion": f"OOS MAR >= baseline + {G1A_MARGIN_ADJUSTED:.3f} ({G1A_THRESHOLD:.4f})",
            "result": f"cand {m_cand_oos['mar']:.4f} vs base {m_base_oos['mar']:.4f}",
            "pass": g1a,
        },
        {
            "id": "G1b",
            "criterion": f"OOS MAR >= {G1B_ADJ:.3f} (absolute floor, k-adjusted)",
            "result": f"{m_cand_oos['mar']:.4f}",
            "pass": g1b,
        },
        {
            "id": "N_OOS_full",
            "criterion": f">= {N_OOS_MIN_FULL} trades in full OOS (2020-2026)",
            "result": str(n_oos_full),
            "pass": n_ok_full,
        },
        {
            "id": "N_OOS_sub_A",
            "criterion": f">= {N_OOS_MIN_SUBWINDOW} trades in OOS sub-window A {OOS_SUB_WINDOW_A}",
            "result": str(n_oos_sub_a),
            "pass": n_ok_a,
        },
        {
            "id": "N_OOS_sub_B",
            "criterion": f">= {N_OOS_MIN_SUBWINDOW} trades in OOS sub-window B {OOS_SUB_WINDOW_B}",
            "result": str(n_oos_sub_b),
            "pass": n_ok_b,
        },
        {
            "id": "Neg-OOS-cap",
            "criterion": "Both baseline and candidate OOS MAR positive",
            "result": "BOTH NEGATIVE" if both_neg else "OK",
            "pass": not both_neg,
        },
    ]
    if not n_ok_full or not n_ok_a or not n_ok_b:
        verdict = "VN-THIN"
    elif both_neg:
        verdict = "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    elif g1a and g1b:
        verdict = "ADVANCE"
    else:
        verdict = "FAIL"
    return details, verdict


# ─────────────────────────────────────────────────────────────────────────────
# Trade counting utilities
# ─────────────────────────────────────────────────────────────────────────────

def count_oos_trades(trades: pd.DataFrame, y0: int, y1: int) -> int:
    """Count trades with entry year in [y0, y1]."""
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    return int(((t["entry_date"].dt.year >= y0) & (t["entry_date"].dt.year <= y1)).sum())


# ─────────────────────────────────────────────────────────────────────────────
# Report writer
# ─────────────────────────────────────────────────────────────────────────────

def write_book2_report(
    out_dir: Path,
    report_filename: str,
    belief_label: str,
    filter_kind: str,       # "S1_52wk_proximity" or "S2_volume_filter"
    prereg_path: str,
    meta: dict[str, Any],
) -> None:
    """Write markdown report following Book 1 pattern."""
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Cortex Book #2 — {belief_label}",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Filter type:** {filter_kind}",
        f"**Pre-registration:** `{prereg_path}`",
        "",
        "## Window",
        "",
        f"- Panel start (actual): **{PANEL_START}**",
        f"- Panel end: **{PANEL_END}**",
        f"- Primary OOS window: **{OOS_WINDOW[0]}–{OOS_WINDOW[1]}**",
        f"- OOS sub-window A: **{OOS_SUB_WINDOW_A[0]}–{OOS_SUB_WINDOW_A[1]}**",
        f"- OOS sub-window B: **{OOS_SUB_WINDOW_B[0]}–{OOS_SUB_WINDOW_B[1]}**",
        "",
        "## Baseline (A3 P1 honest + D4 + D3 @ 1.25/0.75 slot sizing)",
        "",
        f"- Full MAR: **{meta['baseline_full']['mar']:.4f}**",
        f"- Full MaxDD: **{_fmt_pct(meta['baseline_full']['max_dd'])}**",
        f"- OOS MAR: **{meta['baseline_oos']['mar']:.4f}**",
        f"- OOS MaxDD: **{_fmt_pct(meta['baseline_oos']['max_dd'])}**",
        f"- Baseline OOS trade count: **{meta['baseline_n_oos']}**",
        "",
        "## Gate thresholds (pre-registered, locked before run)",
        "",
        f"- G1a: candidate OOS MAR >= baseline + {G1A_MARGIN_ADJUSTED:.3f} = **{G1A_THRESHOLD:.4f}**",
        f"  (base margin {G1A_BASE_MARGIN:.3f} + k={K} adj {G1A_K_ADJ:.3f})",
        f"- G1b: candidate OOS MAR >= **{G1B_ADJ:.3f}** (floor {G1B_FLOOR:.3f} + k-adj {G1A_K_ADJ:.3f})",
        f"- N_OOS (full): >= {N_OOS_MIN_FULL} | Sub-window each: >= {N_OOS_MIN_SUBWINDOW}",
        "",
    ]

    for cand in meta["candidates"]:
        lines.extend([
            f"## Candidate — {cand['label']}",
            "",
            f"**Verdict: {cand['verdict']}**",
            "",
            "| Metric | Baseline | Candidate |",
            "|--------|----------|-----------|",
            f"| Full MAR | {meta['baseline_full']['mar']:.4f} | {cand['full']['mar']:.4f} |",
            f"| Full MaxDD | {_fmt_pct(meta['baseline_full']['max_dd'])} | {_fmt_pct(cand['full']['max_dd'])} |",
            f"| Full CAGR | {_fmt_pct(meta['baseline_full']['cagr'])} | {_fmt_pct(cand['full']['cagr'])} |",
            f"| OOS MAR | {meta['baseline_oos']['mar']:.4f} | {cand['oos']['mar']:.4f} |",
            f"| OOS MaxDD | {_fmt_pct(meta['baseline_oos']['max_dd'])} | {_fmt_pct(cand['oos']['max_dd'])} |",
            f"| OOS CAGR | {_fmt_pct(meta['baseline_oos']['cagr'])} | {_fmt_pct(cand['oos']['cagr'])} |",
            f"| N trades (full) | {meta['baseline_n_full']} | {cand['n_full']} |",
            f"| N trades (OOS) | {meta['baseline_n_oos']} | {cand['n_oos']} |",
            f"| N trades (OOS sub-A) | — | {cand['n_oos_sub_a']} |",
            f"| N trades (OOS sub-B) | — | {cand['n_oos_sub_b']} |",
            "",
            "| Gate | Criterion | Pass |",
            "|------|-----------|------|",
        ])
        for g in cand["gates"]:
            lines.append(f"| {g['id']} | {g['criterion']} | {'PASS ✓' if g['pass'] else 'FAIL ✗'} |")
        lines.append("")

    lines.extend([
        "## Notes",
        "- Filter applies on SIGNAL BAR (close of bar before entry). Entry is next-open (T+1).",
        "- 52w high: rolling max of prior 252 high bars (inclusive of signal bar).",
        "- Vol 50d avg: rolling mean of prior 50 volume bars (EXCLUDING signal bar — point-in-time).",
        "- Sizing: unchanged D3 sector slot sizing (1.25x leading / 0.75x lagging).",
        "- Realism: P1 honest execution (T+2 settlement, floor/ceiling locks, ADV caps, 40bps RT costs).",
        "- RESEARCH_ONLY_NOT_PRODUCTION — does not touch live signal modules or sizing_policy.py.",
        "- Does not advance vn-trading-advisor session counter (CALIBRATION activity).",
        "",
    ])

    report_path = out_dir / report_filename
    report_path.write_text("\n".join(lines), encoding="utf-8")
    meta_path = out_dir / (report_filename.replace(".md", "_meta.json"))
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {report_path}", flush=True)
