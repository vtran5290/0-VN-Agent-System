#!/usr/bin/env python3
"""
MA / EMA reaction study — full liquid universe (ADV50 >= 2B VND).

Universe: all symbols in OHLCV parquet with recent ADV50 >= 2B VND (~269 symbols).
Previous version used stocks_in_sectors_p20_gt_015_adv50_ge_2bn.csv which applied
an extra sector_p20 momentum filter, cutting the universe from ~269 to 142.

Sector source: sector_l4_coverage_audit.csv (273 symbols, English sector_l4,
204 known + 69 Unknown).

Outputs:
  data/research/ma_reaction_liquid_expanded.json

Methodology identical to run_ma_reaction_stocks.py.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO           = Path(__file__).resolve().parents[1]
OHLCV_PATH     = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
SECTOR_AUDIT   = REPO / "data/research/sector_l4_causality/sector_l4_coverage_audit.csv"
OUT            = REPO / "data/research/ma_reaction_liquid_expanded.json"

ADV50_MIN_B    = 2.0   # billion VND — filter applied from recent 90-day average
ADV50_LOOKBACK = 90    # days for computing recent ADV50

PERIODS   = [5, 10, 20, 50, 100, 150, 200]
MA_TYPES  = ["SMA", "EMA"]
FWD_DAYS  = [5, 10, 20]

TOUCH_TOL   = 0.015
APPROACH_LB = 5

WINDOWS = [
    ("10y", 2520),
    ("5y",  1260),
    ("2y",   504),
    ("1y",   252),
    ("6m",   126),
    ("3m",    63),
]

# Excluded per VIN_EMA_CLOUD_BASELINE.md (SSOT §A — non-negotiable dual universe)
VIN_SYMS = {"VIC", "VHM", "VRE"}


# ── helpers ──────────────────────────────────────────────────────────────────

def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for p in PERIODS:
        out[f"SMA{p}"] = df["close"].rolling(p).mean()
        out[f"EMA{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return out


def find_touch_events(df: pd.DataFrame, ma_col: str) -> pd.DataFrame:
    closes = df["close"].values
    ma     = df[ma_col].values
    n      = len(df)

    in_zone    = np.abs(closes - ma) / (ma + 1e-9) <= TOUCH_TOL
    above_zone = closes > ma * (1 + TOUCH_TOL)

    events = []
    last_event_idx = -10

    for i in range(APPROACH_LB, n):
        if np.isnan(ma[i]) or ma[i] == 0:
            continue
        if not in_zone[i]:
            continue
        was_above = any(above_zone[max(0, i - APPROACH_LB): i])
        if not was_above:
            continue
        if i - last_event_idx < 3:
            continue
        events.append(i)
        last_event_idx = i

    if not events:
        return pd.DataFrame()

    rows = []
    for idx in events:
        touch_close = closes[idx]
        fwd = {}
        for fd in FWD_DAYS:
            end = idx + fd
            if end < n:
                ret = (closes[end] - touch_close) / touch_close * 100
                mdd = (closes[idx:end+1].min() - touch_close) / touch_close * 100
            else:
                ret, mdd = np.nan, np.nan
            fwd[f"ret{fd}d"]  = None if np.isnan(ret)  else round(float(ret), 3)
            fwd[f"mdd{fd}d"]  = None if np.isnan(mdd)  else round(float(mdd), 3)
        rows.append({"date": str(df["date"].iloc[idx].date()), **fwd})
    return pd.DataFrame(rows)


def score_events(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    result = {}
    for fd in FWD_DAYS:
        col, mdd_col = f"ret{fd}d", f"mdd{fd}d"
        rets = events[col].dropna()
        mdds = events[mdd_col].dropna()
        if len(rets) == 0:
            continue
        result[f"n_{fd}d"]     = int(len(rets))
        result[f"sr_{fd}d"]    = round((rets > 0).mean() * 100, 1)
        result[f"avg_{fd}d"]   = round(rets.mean(), 2)
        result[f"med_{fd}d"]   = round(rets.median(), 2)
        result[f"mdd_{fd}d"]   = round(mdds.mean(), 2)
        result[f"gt2_{fd}d"]   = round((rets > 2.0).mean() * 100, 1)
        result[f"gt5_{fd}d"]   = round((rets > 5.0).mean() * 100, 1)
    return result


def composite_score(stats: dict, fd: int = 10) -> float:
    sr  = stats.get(f"sr_{fd}d",  0)
    ar  = stats.get(f"avg_{fd}d", 0)
    p2  = stats.get(f"gt2_{fd}d", 0)
    mdd = abs(stats.get(f"mdd_{fd}d", 0))
    n   = stats.get(f"n_{fd}d",   0)
    if n < 5:
        return -999.0
    return round(0.4 * sr + 0.3 * ar + 0.2 * p2 - 0.1 * mdd, 3)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load sector audit — use sector_l3 for grouping (proper industry names, not company-named L4)
    sec_audit = (
        pd.read_csv(SECTOR_AUDIT)[["symbol", "sector_l3", "sector_l4", "sector_l1"]]
        .drop_duplicates("symbol")
        .set_index("symbol")
    )

    # Load full OHLCV parquet — all symbols
    print("Loading OHLCV parquet...")
    raw = pd.read_parquet(OHLCV_PATH, columns=["symbol", "date", "close", "volume", "value", "adv50"])
    raw["date"] = pd.to_datetime(raw["date"])

    end_date  = raw["date"].max()
    all_dates = sorted(raw["date"].unique())

    # Compute recent ADV50 per symbol (last ADV50_LOOKBACK calendar days) to filter liquid universe
    recent_cutoff = end_date - pd.Timedelta(days=ADV50_LOOKBACK)
    recent = raw[raw["date"] >= recent_cutoff]
    sym_adv50_b = recent.groupby("symbol")["adv50"].mean() / 1e9  # VND -> billions
    liquid_syms = sorted(sym_adv50_b[sym_adv50_b >= ADV50_MIN_B].index.tolist())

    SYMBOLS    = liquid_syms
    SYMBOLS_EX = [s for s in SYMBOLS if s not in VIN_SYMS]   # ex-VIN (primary per SSOT)
    print(f"Liquid universe (ADV50 >= {ADV50_MIN_B}B, recent {ADV50_LOOKBACK}d): "
          f"{len(SYMBOLS)} full | {len(SYMBOLS_EX)} ex-VIN ({','.join(sorted(VIN_SYMS))} excluded)")

    # Filter raw to liquid universe
    raw = raw[raw["symbol"].isin(SYMBOLS)].copy()
    n_sym_found = raw["symbol"].nunique()
    print(f"Data end: {end_date.date()} | symbols in OHLCV: {n_sym_found} / {len(SYMBOLS)}")

    # Precompute MAs per symbol (full history for accuracy)
    print("Computing MAs...")
    sym_dfs: dict[str, pd.DataFrame] = {}
    for sym, grp in raw.groupby("symbol"):
        g = grp.sort_values("date").reset_index(drop=True)
        sym_dfs[sym] = compute_mas(g)
    print(f"MAs computed for {len(sym_dfs)} symbols.")

    output: dict = {
        "asof_date":         str(end_date.date()),
        "universe":          SYMBOLS,
        "universe_ex_vin":   SYMBOLS_EX,
        "n_symbols":         len(SYMBOLS),
        "n_symbols_ex_vin":  len(SYMBOLS_EX),
        "vin_excluded":      sorted(VIN_SYMS),
        "adv50_min_b":       ADV50_MIN_B,
        "universe_source":   "OHLCV parquet — full, no sector momentum filter (adv50_min_b filter only)",
        "note":              "rankings = ex-VIN (primary, per VIN_EMA_CLOUD_BASELINE.md); rankings_full = all symbols.",
        "windows": {},
    }

    # ── Window loop ──────────────────────────────────────────────────────────
    for win_label, win_bars in WINDOWS:
        win_start_date = all_dates[max(0, len(all_dates) - win_bars)]
        win_start_ts   = pd.Timestamp(win_start_date)
        print(f"\n{'='*72}")
        print(f"  {win_label.upper()}  ({win_start_date.date()} -> {end_date.date()})")
        print(f"{'='*72}")

        # Aggregate events across all symbols for each MA
        ma_events: dict[str, list[pd.DataFrame]] = defaultdict(list)    # full universe
        sym_coverage: dict[str, list[str]]        = defaultdict(list)

        # Sector-level: sector_l3 -> ma -> list of DataFrames (ex-VIN only, per SSOT)
        sec_ma_events: dict[str, dict[str, list[pd.DataFrame]]] = defaultdict(lambda: defaultdict(list))

        for sym, df in sym_dfs.items():
            sym_in_window = df[df["date"] >= win_start_ts]
            if len(sym_in_window) < 20:
                continue
            sec_l3  = sec_audit.loc[sym, "sector_l3"] if sym in sec_audit.index else "Unknown"
            is_vin  = sym in VIN_SYMS

            for ma_type in MA_TYPES:
                for period in PERIODS:
                    ma_col = f"{ma_type}{period}"
                    events = find_touch_events(df, ma_col)
                    if events.empty:
                        continue
                    events["date_dt"] = pd.to_datetime(events["date"])
                    win_events = events[events["date_dt"] >= win_start_ts].drop(columns=["date_dt"])
                    if len(win_events) == 0:
                        continue
                    win_events = win_events.copy()
                    win_events["symbol"]   = sym
                    win_events["is_vin"]   = is_vin
                    win_events["sec_l3"]   = sec_l3
                    ma_key = f"{ma_type}{period}"
                    ma_events[ma_key].append(win_events)
                    sym_coverage[ma_key].append(sym)
                    # Sector events: ex-VIN only (avoid VIN return distortion in sector conclusions)
                    if not is_vin:
                        sec_ma_events[sec_l3][ma_key].append(win_events)

        # ── Score each MA — full universe AND ex-VIN ─────────────────────
        def _score_ma_set(event_lists: dict, label: str) -> list:
            results = []
            for ma_type in MA_TYPES:
                for period in PERIODS:
                    ma_key = f"{ma_type}{period}"
                    parts = event_lists.get(ma_key, [])
                    if not parts:
                        continue
                    combined = pd.concat(parts, ignore_index=True)
                    if label == "ex_vin":
                        combined = combined[~combined["is_vin"]]
                    stats = score_events(combined)
                    score = composite_score(stats)
                    syms = sorted(combined["symbol"].unique().tolist())
                    results.append({
                        "ma": ma_key, "type": ma_type, "period": period,
                        "score": score, "n_symbols": len(syms), **stats,
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            return results

        ma_results      = _score_ma_set(ma_events, "full")    # all symbols
        ma_results_exv  = _score_ma_set(ma_events, "ex_vin")  # ex-VIN (primary per SSOT)

        # ── Score by sector (best MA per sector) ─────────────────────────
        sector_results: dict[str, dict] = {}
        for sec, sec_ma_dict in sec_ma_events.items():
            best_score, best_ma_key, best_stats = -999.0, None, {}
            sec_ma_ranking = []
            for ma_key, parts in sec_ma_dict.items():
                if not parts:
                    continue
                combined = pd.concat(parts, ignore_index=True)
                stats = score_events(combined)
                score = composite_score(stats)
                sec_ma_ranking.append({"ma": ma_key, "score": score, **stats})
                if score > best_score:
                    best_score   = score
                    best_ma_key  = ma_key
                    best_stats   = stats
            sec_ma_ranking.sort(key=lambda x: x["score"], reverse=True)
            sector_results[sec] = {
                "best_ma":    best_ma_key,
                "best_score": best_score,
                "n_symbols":  len({
                    sym
                    for ma_parts in sec_ma_events[sec].values()
                    for df in ma_parts
                    for sym in df["symbol"].unique()
                }),
                "ma_ranking": sec_ma_ranking[:5],  # top 5 MAs per sector
            }

        # ── Score by MA type (SMA vs EMA) — ex-VIN ───────────────────────
        type_results: dict[str, dict] = {}
        for ma_type in MA_TYPES:
            parts_all = []
            for period in PERIODS:
                parts_all.extend(ma_events.get(f"{ma_type}{period}", []))
            if not parts_all:
                continue
            combined = pd.concat(parts_all, ignore_index=True)
            combined = combined[~combined["is_vin"]]
            stats = score_events(combined)
            type_results[ma_type] = {"score": composite_score(stats), **stats}

        # ── Score by period bucket — ex-VIN ───────────────────────────────
        bucket_map = {
            "short_5_20":    [5, 10, 20],
            "medium_50_100": [50, 100],
            "long_150_200":  [150, 200],
        }
        bucket_results: dict[str, dict] = {}
        for bname, bperiods in bucket_map.items():
            parts_all = []
            for ma_type in MA_TYPES:
                for p in bperiods:
                    parts_all.extend(ma_events.get(f"{ma_type}{p}", []))
            if not parts_all:
                continue
            combined = pd.concat(parts_all, ignore_index=True)
            combined = combined[~combined["is_vin"]]
            stats = score_events(combined)
            bucket_results[bname] = {"score": composite_score(stats), **stats}

        # Print top 10 (ex-VIN, primary)
        print(f"\n  {'MA':<10} {'Score(exV)':>10} {'Score(full)':>11} {'N_ev':>5} {'SR%':>6} {'Avg10d':>7}")
        exv_map = {r["ma"]: r for r in ma_results_exv}
        for r in ma_results_exv[:10]:
            rf = next((x for x in ma_results if x["ma"] == r["ma"]), {})
            print(f"  {r['ma']:<10} {r['score']:>10.2f} {rf.get('score',0):>11.2f} "
                  f"{r.get('n_10d',0):>5}  {r.get('sr_10d',0):>5.1f}%  {r.get('avg_10d',0):>+6.2f}%")

        output["windows"][win_label] = {
            "window_start":    str(win_start_date.date()),
            "window_end":      str(end_date.date()),
            "rankings":        ma_results_exv,   # primary (ex-VIN) per SSOT
            "rankings_full":   ma_results,        # full universe (VIN included)
            "by_type":         type_results,
            "by_period_bucket": bucket_results,
            "by_sector":       sector_results,
        }

    # ── Per-symbol: all MA scores per window (for heatmap + top-2 standard view) ──
    print(f"\n{'='*72}")
    print("  PER-SYMBOL MA SCORES — all 6 windows (for heatmap)")
    print(f"{'='*72}")

    sym_detail: dict[str, dict] = {}

    for sym, df in sym_dfs.items():
        sec_l3 = sec_audit.loc[sym, "sector_l3"] if sym in sec_audit.index else "Unknown"
        sec_l1 = sec_audit.loc[sym, "sector_l1"] if sym in sec_audit.index else "Unknown"

        # Cache touch events for this symbol (full history) to avoid recomputing per window
        cached: dict[str, pd.DataFrame] = {}
        for ma_type in MA_TYPES:
            for period in PERIODS:
                ma_col = f"{ma_type}{period}"
                ev = find_touch_events(df, ma_col)
                if not ev.empty:
                    ev = ev.copy()
                    ev["date_dt"] = pd.to_datetime(ev["date"])
                    cached[f"{ma_type}{period}"] = ev

        if not cached:
            continue

        sym_wins: dict[str, list] = {}
        for win_label, win_bars in WINDOWS:
            win_start_ts = pd.Timestamp(all_dates[max(0, len(all_dates) - win_bars)])
            cands = []
            for ma_key, ev in cached.items():
                we = ev[ev["date_dt"] >= win_start_ts]
                if len(we) < 3:
                    continue
                stats = score_events(we.drop(columns=["date_dt"]))
                s = composite_score(stats)
                if s > -900:
                    cands.append({
                        "ma":     ma_key,
                        "score":  round(s, 1),
                        "sr_10d": round(stats.get("sr_10d", 0), 1),
                        "avg_10d": round(stats.get("avg_10d", 0), 2),
                        "n":      stats.get("n_10d", 0),
                    })
            if cands:
                cands.sort(key=lambda x: -x["score"])
                sym_wins[win_label] = cands   # all scored MAs; top-2 identified by position

        if sym_wins:
            sym_detail[sym] = {
                "sector_l3": sec_l3,
                "sector_l1": sec_l1,
                "is_vin":    sym in VIN_SYMS,
                "windows":   sym_wins,
            }
            # Print top line for 2y
            top = sym_wins.get("2y", sym_wins.get("1y", [{}]))[0]
            print(f"  {sym:<6}  {sec_l3[:22]:<22}  best={top.get('ma','—'):<8}  score={top.get('score',0):.1f}")

    output["per_symbol_windows"] = sym_detail
    output["per_symbol_best_2y"] = {   # keep for backward compat with HTML report
        sym: {
            "best_ma":   d["windows"].get("2y", d["windows"].get("1y", [{}]))[0].get("ma", "—"),
            "score":     d["windows"].get("2y", d["windows"].get("1y", [{}]))[0].get("score", 0),
            "sr_10d":    d["windows"].get("2y", d["windows"].get("1y", [{}]))[0].get("sr_10d", 0),
            "avg_10d":   d["windows"].get("2y", d["windows"].get("1y", [{}]))[0].get("avg_10d", 0),
            "n_events":  d["windows"].get("2y", d["windows"].get("1y", [{}]))[0].get("n", 0),
            "sector_l3": d["sector_l3"],
            "sector_l1": d["sector_l1"],
            "is_vin":    d["is_vin"],
            "top3_mas":  (d["windows"].get("2y", d["windows"].get("1y", []))[:3]),
        }
        for sym, d in sym_detail.items()
    }

    # ── Cross-window composite (ex-VIN = primary; full = secondary) ──────
    def _cross_window_avg(key: str) -> dict:
        cross: dict[str, list[float]] = defaultdict(list)
        for win_data in output["windows"].values():
            for r in win_data.get(key, []):
                if r["score"] > -900:
                    cross[r["ma"]].append(r["score"])
        return dict(sorted(
            {ma: round(float(np.mean(s)), 3) for ma, s in cross.items() if len(s) >= 3}.items(),
            key=lambda x: -x[1]
        ))

    output["cross_window_avg_score"]      = _cross_window_avg("rankings")       # ex-VIN primary
    output["cross_window_avg_score_full"] = _cross_window_avg("rankings_full")  # full universe

    # ── Cross-window by sector (best MA per sector, aggregated) ───────────
    cross_sector: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    for win_data in output["windows"].values():
        for sec, sdata in win_data.get("by_sector", {}).items():
            for mr in sdata.get("ma_ranking", []):
                if mr["score"] > -900:
                    cross_sector[sec][mr["ma"]].append(mr["score"])

    cross_sector_summary: dict[str, dict] = {}
    for sec, ma_scores in cross_sector.items():
        avgs = {ma: round(float(np.mean(s)), 3)
                for ma, s in ma_scores.items() if len(s) >= 2}
        if avgs:
            best = max(avgs, key=avgs.get)
            cross_sector_summary[sec] = {
                "best_ma_cross_window": best,
                "best_score": avgs[best],
                "all_ma_scores": dict(sorted(avgs.items(), key=lambda x: -x[1])[:5]),
            }
    output["cross_window_by_sector"] = cross_sector_summary

    # ── Cross-window by type ───────────────────────────────────────────────
    cross_type: dict[str, list[float]] = defaultdict(list)
    for win_data in output["windows"].values():
        for t, tdata in win_data.get("by_type", {}).items():
            s = tdata.get("score", -999)
            if s > -900:
                cross_type[t].append(s)
    output["cross_window_by_type"] = {
        t: round(float(np.mean(s)), 3)
        for t, s in cross_type.items() if len(s) >= 3
    }

    # ── Cross-window by bucket ─────────────────────────────────────────────
    cross_bucket: dict[str, list[float]] = defaultdict(list)
    for win_data in output["windows"].values():
        for b, bdata in win_data.get("by_period_bucket", {}).items():
            s = bdata.get("score", -999)
            if s > -900:
                cross_bucket[b].append(s)
    output["cross_window_by_bucket"] = {
        b: round(float(np.mean(s)), 3)
        for b, s in cross_bucket.items() if len(s) >= 3
    }

    # Print summaries
    print(f"\n{'='*72}")
    print("  CROSS-WINDOW MA RANKING — ex-VIN (primary) | full (secondary)")
    print(f"{'='*72}")
    full_map = output.get("cross_window_avg_score_full", {})
    for ma, avg in list(output["cross_window_avg_score"].items())[:14]:
        full_v = full_map.get(ma, float("nan"))
        print(f"  {ma:<10}  ex-VIN={avg:.3f}  full={full_v:.3f}")

    print(f"\n{'='*72}")
    print("  SMA vs EMA cross-window:", output["cross_window_by_type"])
    print("  Bucket cross-window:    ", output["cross_window_by_bucket"])

    print(f"\n{'='*72}")
    print("  SECTOR BEST MA (cross-window)")
    print(f"{'='*72}")
    for sec, d in sorted(cross_sector_summary.items(), key=lambda x: -x[1]["best_score"]):
        sec_safe = sec.encode("ascii", errors="replace").decode()
        print(f"  {sec_safe:<28}  best={d['best_ma_cross_window']:<8}  score={d['best_score']:.3f}")

    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten: {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
