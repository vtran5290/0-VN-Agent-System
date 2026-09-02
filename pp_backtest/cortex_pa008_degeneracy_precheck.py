#!/usr/bin/env python3
"""PA-008 degeneracy pre-check: does max-4-per-sector cap bind on S1-filtered OOS pool?

RESEARCH_ONLY_NOT_PRODUCTION
Usage: python pp_backtest/cortex_pa008_degeneracy_precheck.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_book1_common import OOS_WINDOW
from pp_backtest.cortex_book2_common import apply_proximity_filter, build_signal_filter_map
from pp_backtest.sprint2b_common import build_baseline_stack

S1_MIN_PROX = 0.85
CAP_LEVELS = (3, 4, 5)
MIN_SECTOR_SIZE = 5
OUT = REPO / "knowledge" / "backtests" / "2026-07-05_pa008_sectorcap_degeneracy.md"
META = REPO / "data" / "research" / "cortex_pa008" / "pa008_degeneracy_meta.json"


def _oos_mask(df: pd.DataFrame) -> pd.Series:
    y0, y1 = OOS_WINDOW
    ed = pd.to_datetime(df["entry_date"])
    return (ed.dt.year >= y0) & (ed.dt.year <= y1)


def _daily_open_counts(trades: pd.DataFrame, sector_map: dict[str, str]) -> list[tuple[pd.Timestamp, str, int]]:
    """For each OOS day, count open positions per sector."""
    rows: list[tuple[pd.Timestamp, str, int]] = []
    if trades.empty:
        return rows
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["exit_date"] = pd.to_datetime(t["exit_date"]).dt.normalize()
    t = t[_oos_mask(t)]
    if t.empty:
        return rows
    start = t["entry_date"].min()
    end = t["exit_date"].max()
    days = pd.bdate_range(start, end)
    for d in days:
        open_t = t[(t["entry_date"] <= d) & (t["exit_date"] >= d)]
        if open_t.empty:
            continue
        sec_counts = Counter(sector_map.get(str(s), "Unknown") for s in open_t["symbol"])
        for sec, n in sec_counts.items():
            rows.append((d, sec, n))
    return rows


def main() -> dict:
    stack = build_baseline_stack()
    sector_map = stack["sector_map"]
    fmap = build_signal_filter_map(stack["ctx"].panel)
    s1 = apply_proximity_filter(stack["base_trades"], fmap, S1_MIN_PROX)
    s1_oos = s1[_oos_mask(s1)].copy()
    s1_oos["sector"] = s1_oos["symbol"].astype(str).map(lambda s: sector_map.get(s, "Unknown"))

    # Same-day entry cohorts
    cohort_max: list[int] = []
    bind_at_cap: dict[int, int] = {c: 0 for c in CAP_LEVELS}
    cohort_days = 0
    for _, grp in s1_oos.groupby(pd.to_datetime(s1_oos["entry_date"]).dt.normalize()):
        cohort_days += 1
        sec_n = grp.groupby("sector").size()
        eligible = sec_n[sec_n.index.map(lambda s: (s1_oos["sector"] == s).sum() >= MIN_SECTOR_SIZE)]
        if eligible.empty:
            continue
        mx = int(eligible.max())
        cohort_max.append(mx)
        for cap in CAP_LEVELS:
            if (eligible > cap).any():
                bind_at_cap[cap] += 1

    daily = _daily_open_counts(s1, sector_map)
    daily_max = [n for _, _, n in daily] if daily else []
    daily_bind = {c: sum(1 for n in daily_max if n > c) for c in CAP_LEVELS}
    daily_obs = len(daily_max)

    max_same_sector = max(cohort_max) if cohort_max else 0
    bind_freq_4 = (bind_at_cap[4] / cohort_days * 100) if cohort_days else 0.0
    daily_bind_freq_4 = (daily_bind[4] / daily_obs * 100) if daily_obs else 0.0
    degenerate = bind_freq_4 < 5.0 and daily_bind_freq_4 < 5.0

    meta = {
        "s1_filter": f"prox>={S1_MIN_PROX}",
        "oos_window": list(OOS_WINDOW),
        "n_s1_oos_trades": int(len(s1_oos)),
        "n_oos_entry_cohort_days": cohort_days,
        "max_same_sector_same_day": max_same_sector,
        "cohort_cap_binding_pct": {str(c): round(bind_at_cap[c] / cohort_days * 100, 2) if cohort_days else 0 for c in CAP_LEVELS},
        "daily_open_observations": daily_obs,
        "max_open_same_sector_daily": max(daily_max) if daily_max else 0,
        "daily_cap_binding_pct": {str(c): round(daily_bind[c] / daily_obs * 100, 2) if daily_obs else 0 for c in CAP_LEVELS},
        "verdict": "DEGENERATE" if degenerate else "EXPRESSIBLE",
        "degeneracy_rule": "binding_frequency_at_cap4 < 5% on both entry-cohort and daily-open metrics",
    }
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    lines = [
        "# PA-008 Sector Cap — Degeneracy Pre-Check",
        "",
        f"**Date:** 2026-07-05",
        f"**Script:** `pp_backtest/cortex_pa008_degeneracy_precheck.py`",
        f"**Pool:** S1-filtered (prox ≥ {S1_MIN_PROX}) A3_RS OOS trades {OOS_WINDOW[0]}–{OOS_WINDOW[1]}",
        f"**VERDICT: {meta['verdict']}**",
        "",
        "## Entry-cohort (same-day new signals per sector)",
        f"- OOS trades: {meta['n_s1_oos_trades']}",
        f"- Entry cohort days: {cohort_days}",
        f"- Max same-sector signals same day: **{max_same_sector}**",
        "",
        "| Cap | Cohort-days binding (count > cap) | % of cohort days |",
        "|-----|-----------------------------------|------------------|",
    ]
    for c in CAP_LEVELS:
        pct = meta["cohort_cap_binding_pct"][str(c)]
        lines.append(f"| {c} | {bind_at_cap[c]} | {pct:.1f}% |")
    lines += [
        "",
        "## Daily open positions (holding overlap)",
        f"- Daily sector observations: {daily_obs}",
        f"- Max open same-sector positions any day: **{meta['max_open_same_sector_daily']}**",
        "",
        "| Cap | Daily obs binding (open > cap) | % of daily obs |",
        "|-----|-------------------------------|----------------|",
    ]
    for c in CAP_LEVELS:
        pct = meta["daily_cap_binding_pct"][str(c)]
        lines.append(f"| {c} | {daily_bind[c]} | {pct:.1f}% |")
    lines += [
        "",
        "## Interpretation",
        f"- Cap=4 binds on **{bind_freq_4:.1f}%** of entry cohort days (threshold: ≥5% to be EXPRESSIBLE).",
        f"- Cap=4 binds on **{daily_bind_freq_4:.1f}%** of daily open-position observations.",
        "- If DEGENERATE: skip full PA-008 harness; natural S1-filtered diversification already ≤4/sector.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return meta


if __name__ == "__main__":
    main()
