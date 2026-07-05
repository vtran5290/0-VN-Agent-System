#!/usr/bin/env python3
"""
Batch degeneracy pre-check: S17 (FireAnt buy/sell flow) + S18 (sector breadth/persistence)
+ S19 (co-sector cohort / VIN leader stability).

RESEARCH_ONLY_NOT_PRODUCTION
Usage: python pp_backtest/cortex_schwager_s17_s18_s19_precheck_batch.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_book1_common import IS_WINDOW, OOS_WINDOW, PANEL_END, PANEL_START
from pp_backtest.d3_sector_rs_validation import load_sector_map
from pp_backtest.sprint2b_common import build_baseline_stack
from src.data.fireant_client import RESTV2_BASE, _BROWSER_HEADERS, _load_token

OUT_MD = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s17_s18_s19_precheck_batch.md"
OUT_META = REPO / "data" / "research" / "cortex_schwager" / "s17_s18_s19_precheck_meta.json"
SCHEMA = REPO / "data" / "config" / "signal_data_schema.md"

VIN_SYMBOLS = {"VIC", "VHM", "VRE"}
MIN_SECTOR_MEMBERS = 10
MIN_COSECTOR_DAYS = 30
LEADER_DEGEN_PCT = 80.0
RATIO_DEGEN_STD = 0.10
RATIO_NEAR_ONE_PCT = 70.0
FIREANT_DELAY = 0.12
PROBE_SYMBOLS = ("VNM", "ACB", "AAA")


def _year_mask(series: pd.Series, window: tuple[int, int]) -> pd.Series:
    y0, y1 = window
    return (series.dt.year >= y0) & (series.dt.year <= y1)


def _fetch_buy_sell_raw(
    symbol: str,
    start: str,
    end: str,
    headers: dict[str, str],
) -> pd.DataFrame:
    url = f"{RESTV2_BASE}/symbols/{symbol}/historical-quotes"
    params = {"startDate": start, "endDate": end, "offset": 0, "limit": 5000}
    r = requests.get(url, headers=headers, params=params, timeout=60)
    if r.status_code != 200:
        return pd.DataFrame()
    data = r.json()
    if not isinstance(data, list):
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for item in data:
        d = item.get("date") or item.get("Date")
        if not d:
            continue
        bq = item.get("buyQuantity")
        sq = item.get("sellQuantity")
        pt = item.get("putthroughVolume")
        if bq is None or sq is None:
            continue
        try:
            bq, sq = float(bq), float(sq)
        except (TypeError, ValueError):
            continue
        if bq <= 0 and sq <= 0:
            continue
        rows.append(
            {
                "date": pd.Timestamp(str(d)[:10]).normalize(),
                "buy_quantity": bq,
                "sell_quantity": sq,
                "putthrough_volume": float(pt) if pt is not None else np.nan,
                "deal_volume": float(item.get("dealVolume") or item.get("totalVolume") or 0),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("date").drop_duplicates("date")


def _rolling_ratio(df: pd.DataFrame, window: int) -> pd.Series:
    b = df["buy_quantity"].rolling(window, min_periods=window).sum()
    s = df["sell_quantity"].rolling(window, min_periods=window).sum()
    return b / s.replace(0, np.nan)


def _sector_daily_returns(panel: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p["sector"] = p["symbol"].map(sector_map).fillna("Unknown")
    p = p[p["sector"] != "Unknown"]
    p["ret"] = p.groupby("symbol")["close"].pct_change()
    p = p.dropna(subset=["ret"])
    return p.groupby(["date", "sector"], as_index=False)["ret"].mean()


def _compute_s18(sector_rets: pd.DataFrame, window: tuple[int, int]) -> dict[str, Any]:
    sr = sector_rets.copy()
    sr = sr[_year_mask(sr["date"], window)]
    if sr.empty:
        return {"n_sector_days": 0}

    out: dict[str, Any] = {"window": list(window), "sectors": {}}
    qualifying: list[str] = []
    fire_rates: dict[str, dict[str, float]] = {}
    cont_rates: dict[str, float] = {}

    for sec, g in sr.groupby("sector"):
        g = g.sort_values("date").set_index("date")
        if len(g) < 60:
            continue
        members = sector_rets[sector_rets["sector"] == sec]["date"].nunique()
        # member count from panel at OOS — approximate via unique symbols in sector_rets source
        out["sectors"][sec] = {"n_days": len(g)}
        std20 = g["ret"].rolling(20, min_periods=15).std()
        for k in (1.0, 0.75):
            flag = g["ret"] > k * std20
            rate = float(flag.mean()) if len(flag) else 0.0
            fire_rates.setdefault(sec, {})[str(k)] = rate
        # continuation on k=1.0 upside days only
        up = g["ret"] > 1.0 * std20
        n_up = int(up.sum())
        if n_up >= 5:
            nxt = g["ret"].shift(-1)
            cont = float((nxt[up] > 0).mean())
            cont_rates[sec] = cont
        if n_up >= 5:  # proxy for activity
            qualifying.append(sec)

    agg_fire_100 = np.mean([v.get("1.0", 0) for v in fire_rates.values()]) if fire_rates else 0.0
    agg_fire_075 = np.mean([v.get("0.75", 0) for v in fire_rates.values()]) if fire_rates else 0.0
    agg_cont = float(np.mean(list(cont_rates.values()))) if cont_rates else np.nan

    if len(qualifying) < 3:
        verdict = "DEGENERATE"
    elif agg_fire_100 < 0.05 and agg_fire_075 < 0.10:
        verdict = "VN-THIN"
    elif np.isfinite(agg_cont) and agg_cont >= 0.58:
        verdict = "EXPRESSIBLE"
    elif np.isfinite(agg_cont) and agg_cont >= 0.52:
        verdict = "EXPRESSIBLE"
    else:
        verdict = "VN-THIN"

    return {
        "qualifying_sectors": sorted(set(qualifying)),
        "n_qualifying_sectors": len(set(qualifying)),
        "fire_rate_k1_mean": agg_fire_100,
        "fire_rate_k075_mean": agg_fire_075,
        "is_continuation_rate_mean": agg_cont,
        "sector_continuation": cont_rates,
        "sector_fire_rates": fire_rates,
        "verdict": verdict,
    }


def _compute_s19(trades: pd.DataFrame, sector_map: dict[str, str]) -> dict[str, Any]:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t = t[_year_mask(t["entry_date"], OOS_WINDOW)]
    t["sector"] = t["symbol"].astype(str).map(lambda s: sector_map.get(s, "Unknown"))
    t = t[t["sector"] != "Unknown"]

    cohort_days = 0
    leader_dom: dict[str, list[str]] = defaultdict(list)

    for (ed, sec), grp in t.groupby(["entry_date", "sector"]):
        if len(grp) < 2:
            continue
        cohort_days += 1
        top = grp.sort_values("rs_score", ascending=False).iloc[0]
        leader_dom[sec].append(str(top["symbol"]))

    stability: dict[str, float] = {}
    for sec, leaders in leader_dom.items():
        if not leaders:
            continue
        top1 = Counter(leaders).most_common(1)[0]
        stability[sec] = 100.0 * top1[1] / len(leaders)

    vin_secs = {}
    for sym in VIN_SYMBOLS:
        sec = sector_map.get(sym)
        if sec and sec in stability:
            vin_secs[sym] = {"sector": sec, "leader_stability_pct": stability[sec]}

    if cohort_days < MIN_COSECTOR_DAYS:
        verdict = "VN-THIN"
    elif sum(1 for v in stability.values() if v <= LEADER_DEGEN_PCT) >= 2:
        verdict = "EXPRESSIBLE"
    elif all(v > LEADER_DEGEN_PCT for v in stability.values() if v):
        verdict = "DEGENERATE"
    else:
        verdict = "VN-THIN"

    return {
        "cosector_cohort_days_oos": cohort_days,
        "leader_stability_by_sector": stability,
        "vin_leader_check": vin_secs,
        "verdict": verdict,
    }


def main() -> dict[str, Any]:
    OUT_META.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA.parent.mkdir(parents=True, exist_ok=True)

    print("Building A3 baseline stack...", flush=True)
    stack = build_baseline_stack()
    sector_map, _ = load_sector_map()
    panel = stack["ctx"].panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    trades = stack["base_trades"]
    oos_trades = trades[_year_mask(pd.to_datetime(trades["entry_date"]), OOS_WINDOW)].copy()

    # ── S17 FireAnt discovery ───────────────────────────────────────────────
    token = _load_token(None)
    s17: dict[str, Any] = {"token_present": bool(token)}
    buy_sell_frames: dict[str, pd.DataFrame] = {}

    if token:
        headers = {**_BROWSER_HEADERS, "Authorization": f"Bearer {token}"}
        # API field probe
        r = requests.get(
            f"{RESTV2_BASE}/symbols/VNM/historical-quotes",
            headers=headers,
            params={"startDate": "2025-06-01", "endDate": "2025-06-05", "offset": 0, "limit": 3},
            timeout=45,
        )
        if r.status_code == 200 and r.json():
            s17["api_fields"] = list(r.json()[0].keys())
            s17["buy_field"] = "buyQuantity"
            s17["sell_field"] = "sellQuantity"
            s17["putthrough_field"] = "putthroughVolume"

        # Historical depth probe
        depth: dict[str, str] = {}
        for sym in PROBE_SYMBOLS:
            df = _fetch_buy_sell_raw(sym, PANEL_START, PANEL_END, headers)
            depth[sym] = str(df["date"].min())[:10] if not df.empty else "NONE"
            time.sleep(FIREANT_DELAY)
        s17["earliest_buy_sell_date_probe"] = depth

        syms = sorted(oos_trades["symbol"].astype(str).unique())
        print(f"S17: fetching buy/sell for {len(syms)} OOS symbols...", flush=True)
        ok, fail = 0, 0
        for i, sym in enumerate(syms):
            df = _fetch_buy_sell_raw(sym, f"{OOS_WINDOW[0]}-01-01", PANEL_END, headers)
            if df.empty:
                fail += 1
            else:
                buy_sell_frames[sym] = df
                ok += 1
            if (i + 1) % 25 == 0:
                print(f"  ... {i+1}/{len(syms)}", flush=True)
            time.sleep(FIREANT_DELAY)
        s17["symbols_fetched_ok"] = ok
        s17["symbols_fetch_fail"] = fail

        # Ratio stats on OOS signal days (entry_date proxy)
        ratios_1d: list[float] = []
        ratios_5d: list[float] = []
        ratios_20d: list[float] = []
        matched = 0
        for _, row in oos_trades.iterrows():
            sym = str(row["symbol"])
            df = buy_sell_frames.get(sym)
            if df is None or df.empty:
                continue
            ed = pd.Timestamp(row["entry_date"]).normalize()
            sub = df.set_index("date")
            if ed not in sub.index:
                continue
            matched += 1
            r1 = sub.loc[ed, "buy_quantity"] / max(sub.loc[ed, "sell_quantity"], 1e-9)
            ratios_1d.append(float(r1))
            hist = sub.loc[:ed]
            if len(hist) >= 5:
                b5 = hist["buy_quantity"].tail(5).sum()
                s5 = hist["sell_quantity"].tail(5).sum()
                if s5 > 0:
                    ratios_5d.append(b5 / s5)
            if len(hist) >= 20:
                b20 = hist["buy_quantity"].tail(20).sum()
                s20 = hist["sell_quantity"].tail(20).sum()
                if s20 > 0:
                    ratios_20d.append(b20 / s20)

        def _ratio_stats(vals: list[float]) -> dict[str, float]:
            if not vals:
                return {"n": 0, "std": np.nan, "pct_near_one": np.nan}
            a = np.array(vals)
            near = float(((a >= 0.95) & (a <= 1.05)).mean() * 100)
            return {"n": len(vals), "std": float(np.std(a)), "pct_near_one": near, "mean": float(np.mean(a))}

        rs1, rs5, rs20 = _ratio_stats(ratios_1d), _ratio_stats(ratios_5d), _ratio_stats(ratios_20d)
        s17.update(
            {
                "signal_days_matched": matched,
                "signal_day_match_pct": 100.0 * matched / max(len(oos_trades), 1),
                "ratio_1d": rs1,
                "ratio_5d": rs5,
                "ratio_20d": rs20,
                "Q1_classification_basis": "FireAnt REST buyQuantity/sellQuantity — HOSE/HNX matched-order buy vs sell counts (not aggressor tick)",
                "Q2_putthrough_excluded": "PARTIAL — putthroughVolume reported separately; buyQuantity/sellQuantity are deal-matched fields (verify HOSE spec)",
                "Q3_historical_coverage": f"OOS {OOS_WINDOW[0]}-{OOS_WINDOW[1]}: {ok}/{len(syms)} symbols with data; probe earliest {depth}",
                "Q4_survivorship_risk": "MEDIUM — delisted names may be absent from current FireAnt pull; OOS universe is trade-conditioned",
                "Q5_ratio_rebuildable": "YES on matched symbol-days; gaps exclude ticker-day from rolling windows",
            }
        )
        deg = (
            rs1["std"] < RATIO_DEGEN_STD
            or rs1.get("pct_near_one", 100) > RATIO_NEAR_ONE_PCT
            or matched < 100
        )
        s17["precheck_verdict"] = "DEGENERATE" if deg else "EXPRESSIBLE"
        s17["data_discovery_verdict"] = (
            "PROCEED TO PRE-CHECK" if s17["precheck_verdict"] == "EXPRESSIBLE" else "S17 REMAINS CONCEPTUAL"
        )
    else:
        s17.update(
            {
                "error": "FIREANT_TOKEN missing",
                "precheck_verdict": "VN-SUBSUMED",
                "data_discovery_verdict": "S17 REMAINS CONCEPTUAL",
            }
        )

    # ── S18 sector breadth / persistence ────────────────────────────────────
    print("S18: sector returns...", flush=True)
    sector_rets = _sector_daily_returns(panel, sector_map)
    # sector member counts in panel
    sym_sector = panel.groupby("symbol")["close"].count()
    members = Counter(sector_map.get(s, "Unknown") for s in sym_sector.index if s in sector_map)
    s18_is = _compute_s18(sector_rets, IS_WINDOW)
    s18_oos = _compute_s18(sector_rets, OOS_WINDOW)
    s18 = {
        "sector_member_counts_panel": dict(members.most_common(20)),
        "sectors_ge10_members": [s for s, n in members.items() if n >= MIN_SECTOR_MEMBERS],
        "is": s18_is,
        "oos": s18_oos,
        "verdict": s18_oos.get("verdict", "UNKNOWN"),
    }

    # ── S19 co-sector cohort ───────────────────────────────────────────────
    print("S19: co-sector cohorts...", flush=True)
    s19 = _compute_s19(trades, sector_map)

    meta = {
        "generated": pd.Timestamp.now().isoformat(),
        "oos_window": list(OOS_WINDOW),
        "is_window": list(IS_WINDOW),
        "source_fireant": "REST API historical-quotes",
        "S17": s17,
        "S18": s18,
        "S19": s19,
    }
    OUT_META.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    # signal_data_schema.md
    schema_lines = [
        "# Signal Data Schema (partial — S17 discovery 2026-07-05)",
        "",
        "## FireAnt historical-quotes — buy/sell flow (S17)",
        "- **source**: FireAnt REST `GET /symbols/{symbol}/historical-quotes`",
        "- **method**: API",
        "- **buy field**: `buyQuantity` (matched buy-side quantity)",
        "- **sell field**: `sellQuantity` (matched sell-side quantity)",
        "- **put-through**: `putthroughVolume` (separate; exclude from S17 ratios unless council decides otherwise)",
        "- **NOT in repo OHLCV CSVs**: `data/stocks/*.csv` has date, OHLCV only — S17 requires live FireAnt fetch or extended cache",
        f"- **OOS coverage**: {s17.get('symbols_fetched_ok', 'N/A')}/{oos_trades['symbol'].nunique()} symbols, "
        f"{s17.get('signal_day_match_pct', 0):.1f}% signal-day match",
        f"- **S17 pre-check verdict**: {s17.get('precheck_verdict', 'UNKNOWN')}",
        "",
    ]
    SCHEMA.write_text("\n".join(schema_lines), encoding="utf-8")

    lines = [
        "# S17 / S18 / S19 — Batch Degeneracy Pre-Check",
        "",
        f"**Date:** 2026-07-05",
        f"**Script:** `pp_backtest/cortex_schwager_s17_s18_s19_precheck_batch.py`",
        f"**OOS window:** {OOS_WINDOW[0]}–{OOS_WINDOW[1]}",
        "",
        "---",
        "",
        "## S17 — FireAnt buy/sell flow data discovery",
        "",
        f"**Data discovery verdict:** {s17.get('data_discovery_verdict', 'UNKNOWN')}",
        f"**Pre-check verdict:** {s17.get('precheck_verdict', 'UNKNOWN')}",
        "",
        "| Q | Answer |",
        "|---|--------|",
        f"| Q1 classification | {s17.get('Q1_classification_basis', 'N/A')} |",
        f"| Q2 put-through | {s17.get('Q2_putthrough_excluded', 'N/A')} |",
        f"| Q3 coverage | {s17.get('Q3_historical_coverage', 'N/A')} |",
        f"| Q4 survivorship | {s17.get('Q4_survivorship_risk', 'N/A')} |",
        f"| Q5 rebuildable | {s17.get('Q5_ratio_rebuildable', 'N/A')} |",
        "",
    ]
    if s17.get("ratio_1d"):
        r = s17["ratio_1d"]
        lines += [
            f"- ratio_1d: n={r['n']}, std={r.get('std', float('nan')):.4f}, pct_near_1.0={r.get('pct_near_one', float('nan')):.1f}%",
            f"- ratio_5d: n={s17['ratio_5d']['n']}, std={s17['ratio_5d'].get('std', float('nan')):.4f}",
            f"- ratio_20d: n={s17['ratio_20d']['n']}, std={s17['ratio_20d'].get('std', float('nan')):.4f}",
            "",
        ]

    lines += [
        "---",
        "",
        "## S18 — Sector breadth & persistence",
        "",
        f"**VERDICT (OOS diagnostic):** {s18.get('verdict', 'UNKNOWN')}",
        f"- Sectors with ≥10 panel members: {', '.join(s18.get('sectors_ge10_members', [])[:12]) or 'none'}",
        f"- IS qualifying sectors (activity proxy): {s18_is.get('n_qualifying_sectors', 0)}",
        f"- OOS mean fire rate (k=1.0): {s18_oos.get('fire_rate_k1_mean', float('nan')):.1%}",
        f"- OOS mean fire rate (k=0.75): {s18_oos.get('fire_rate_k075_mean', float('nan')):.1%}",
        f"- IS mean continuation (up-days, k=1.0): {s18_is.get('is_continuation_rate_mean', float('nan')):.1%}",
        "",
        "---",
        "",
        "## S19 — Co-sector cohort & VIN leader stability",
        "",
        f"**VERDICT:** {s19.get('verdict', 'UNKNOWN')}",
        f"- Co-sector signal days (≥2 same sector, OOS): **{s19.get('cosector_cohort_days_oos', 0)}**",
        "",
        "| Sector | Leader stability (% days top RS = same symbol) |",
        "|--------|-----------------------------------------------|",
    ]
    for sec, pct in sorted(s19.get("leader_stability_by_sector", {}).items(), key=lambda x: -x[1])[:15]:
        flag = " ⚠ degenerate" if pct > LEADER_DEGEN_PCT else ""
        lines.append(f"| {sec} | {pct:.1f}%{flag} |")
    lines += ["", "### VIN check", ""]
    for sym, info in s19.get("vin_leader_check", {}).items():
        lines.append(f"- **{sym}** ({info.get('sector')}): leader stability {info.get('leader_stability_pct', float('nan')):.1f}%")
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"S17": s17.get("precheck_verdict"), "S18": s18.get("verdict"), "S19": s19.get("verdict")}, indent=2))
    return meta


if __name__ == "__main__":
    main()
