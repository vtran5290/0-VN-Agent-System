"""Shared helpers for cortex degeneracy pre-checks (S12/S14/S15/S16)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pp_backtest.cortex_book1_common import OOS_WINDOW
from pp_backtest.cortex_book2_common import OOS_SUB_WINDOW_A, OOS_SUB_WINDOW_B
from pp_backtest.p0_realism_p1_winner import _build_honest_cache
from pp_backtest.sprint2b_common import build_baseline_stack

REPO = Path(__file__).resolve().parents[1]
OOS_START = pd.Timestamp(f"{OOS_WINDOW[0]}-01-01")
OOS_END = pd.Timestamp("2026-07-03")


def load_stack():
    return build_baseline_stack()


def oos_entry_mask(df: pd.DataFrame) -> pd.Series:
    ed = pd.to_datetime(df["entry_date"])
    return (ed >= OOS_START) & (ed <= OOS_END)


def sub_window_mask(series: pd.Series, window: tuple[int, int]) -> pd.Series:
    y0, y1 = window
    return (series.dt.year >= y0) & (series.dt.year <= y1)


def build_symbol_panel(panel: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    for sym, g in p.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        dates = g["date"]
        out[str(sym)] = {
            "dates": dates,
            "date_to_i": {pd.Timestamp(d).normalize(): i for i, d in enumerate(dates)},
            "close": g["close"].astype(float).values,
            "high": g["high"].astype(float).values,
            "low": g["low"].astype(float).values,
            "open": g["open"].astype(float).values,
        }
    return out


def iter_oos_signals(panel: pd.DataFrame, cache: dict | None = None):
    """Yield (symbol, signal_date, panel_index) for A3_RS OOS signal bars."""
    if cache is None:
        cache = _build_honest_cache(panel)
    sym_panel = build_symbol_panel(panel)
    for sym, data in cache.items():
        sp = sym_panel.get(str(sym))
        if sp is None:
            continue
        d2i = sp["date_to_i"]
        for si in data["sig_idxs"]:
            sig_dt = pd.Timestamp(data["dates"][si]).normalize()
            if sig_dt < OOS_START or sig_dt > OOS_END:
                continue
            pi = d2i.get(sig_dt)
            if pi is None:
                continue
            yield str(sym), sig_dt, pi, sp


def rolling_sma(arr: np.ndarray, end_i: int, window: int) -> float:
    start = end_i - window + 1
    if start < 0:
        return float("nan")
    return float(np.mean(arr[start : end_i + 1]))


def write_precheck_outputs(
    out_md: Path,
    out_json: Path,
    title: str,
    verdict: str,
    meta: dict[str, Any],
    body_lines: list[str],
) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    meta["verdict"] = verdict
    out_json.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# {title}",
        "",
        f"**Generated:** {meta.get('date', '2026-07-05')}",
        f"**OOS window:** {OOS_START.date()} → {OOS_END.date()}",
        f"**VERDICT: {verdict}**",
        "",
        *body_lines,
        "",
        "RESEARCH_ONLY_NOT_PRODUCTION",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
