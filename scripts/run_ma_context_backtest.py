"""
MA Context Backtest — does entering near a symbol's historically best MA improve A3 trade outcomes?

Inputs:
  - data/research/ema_levels/phase2_trades.parquet       (1M A3 trades with returns)
  - data/research/sector_l4_causality/stock_daily_cloud_panel.parquet (OHLCV)
  - data/research/ma_reaction_liquid_expanded.json       (per-symbol best MAs)

Output:
  - data/research/ma_context_backtest_results.json
  - prints summary table
"""

from pathlib import Path
import json, warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parent.parent

TRADES_PQ   = REPO / "data/research/ema_levels/phase2_trades.parquet"
PANEL_PQ    = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
MA_JSON     = REPO / "data/research/ma_reaction_liquid_expanded.json"
OUT_JSON    = REPO / "data/research/ma_context_backtest_results.json"

MA_PERIODS  = [5, 10, 20, 50, 100, 150, 200]
TOUCH_BANDS = [0.005, 0.010, 0.015, 0.020, 0.030]  # ±0.5% … ±3%
MIN_SCORE   = 25.0   # minimum MA reaction score to be considered "high-quality"
MIN_EVENTS  = 5      # minimum historical touch events for a MA to qualify
PRIMARY_WIN = "2y"   # window used for best-MA lookup


def compute_mas(close_series: pd.Series) -> pd.DataFrame:
    """Compute all 14 MAs for a price series."""
    out = {}
    for p in MA_PERIODS:
        out[f"SMA{p}"] = close_series.rolling(p, min_periods=p).mean()
        out[f"EMA{p}"] = close_series.ewm(span=p, adjust=False).mean()
    return pd.DataFrame(out, index=close_series.index)


def load_best_ma_map(ma_json: dict, window: str = PRIMARY_WIN) -> dict:
    """Return {symbol: {'ma': str, 'score': float, 'sr_10d': float, 'n': int}}."""
    result = {}
    psw = ma_json.get("per_symbol_windows", {})
    for sym, sdata in psw.items():
        wins = sdata.get("windows", {})
        cands = wins.get(window, [])
        if not cands:
            # fallback to 1y
            cands = wins.get("1y", [])
        if cands:
            best = cands[0]
            if best.get("score", 0) >= MIN_SCORE and best.get("n", 0) >= MIN_EVENTS:
                result[sym] = best
    return result


def main():
    print("Loading MA reaction JSON...")
    with open(MA_JSON) as f:
        ma_json = json.load(f)

    print("Loading phase2 trades...")
    trades = pd.read_parquet(TRADES_PQ)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    print(f"  Total trades: {len(trades):,} | symbols: {trades['symbol'].nunique()}")

    print("Loading OHLCV panel...")
    panel = pd.read_parquet(PANEL_PQ)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[["symbol", "date", "close"]].sort_values(["symbol", "date"])
    print(f"  Panel: {panel['symbol'].nunique()} symbols, {panel['date'].min().date()} -> {panel['date'].max().date()}")

    print("Computing all 14 MAs per symbol...")
    ma_frames = []
    for sym, grp in panel.groupby("symbol"):
        grp = grp.set_index("date").sort_index()
        mas = compute_mas(grp["close"])
        mas["symbol"] = sym
        mas["date"]   = mas.index
        ma_frames.append(mas.reset_index(drop=True))
    ma_panel = pd.concat(ma_frames, ignore_index=True)
    print(f"  MA panel shape: {ma_panel.shape}")

    print(f"Building best-MA map ({PRIMARY_WIN} window, score≥{MIN_SCORE}, n≥{MIN_EVENTS})...")
    best_ma_map = load_best_ma_map(ma_json, PRIMARY_WIN)
    print(f"  Symbols with qualified best MA: {len(best_ma_map)}")

    # Merge: trades → MA panel at entry_date
    print("Merging trades with MA values at entry...")
    trades_sym = trades.rename(columns={"entry_date": "date"})
    merged = trades_sym.merge(
        ma_panel,
        on=["symbol", "date"],
        how="left"
    )
    print(f"  Merged shape: {merged.shape}, MA nulls: {merged['SMA20'].isna().sum():,}")

    # ── Core metric: distance from best MA at entry ──────────────────────────
    print("Computing best-MA distance at entry...")
    merged["best_ma_label"]  = merged["symbol"].map(lambda s: best_ma_map.get(s, {}).get("ma"))
    merged["best_ma_score"]  = merged["symbol"].map(lambda s: best_ma_map.get(s, {}).get("score"))
    merged["best_ma_sr10d"]  = merged["symbol"].map(lambda s: best_ma_map.get(s, {}).get("sr_10d"))

    def get_ma_val(row):
        ma_lbl = row["best_ma_label"]
        if pd.isna(ma_lbl) or ma_lbl not in row.index:
            return np.nan
        return row[ma_lbl]

    merged["best_ma_val"]    = merged.apply(get_ma_val, axis=1)
    merged["dist_from_best"] = (merged["entry_price"] - merged["best_ma_val"]) / merged["best_ma_val"]
    merged["above_best_ma"]  = merged["dist_from_best"] >= 0

    valid = merged.dropna(subset=["dist_from_best", "gross_return"]).copy()
    print(f"  Valid rows for analysis: {len(valid):,} / {len(merged):,}")

    # Base rate
    base_n     = len(valid)
    base_sr    = (valid["gross_return"] > 0).mean() * 100
    base_avg   = valid["gross_return"].mean() * 100
    base_mae   = valid["mae"].abs().mean() * 100 if "mae" in valid.columns else np.nan
    base_mfe   = valid["mfe"].mean() * 100       if "mfe" in valid.columns else np.nan

    print(f"\nBase rate (all valid trades): N={base_n:,} | SR={base_sr:.1f}% | avg_ret={base_avg:+.2f}% | avg_MAE={base_mae:.2f}%")

    # ── Band analysis ────────────────────────────────────────────────────────
    results_bands = []
    for band in TOUCH_BANDS:
        near = valid[valid["dist_from_best"].abs() <= band]
        far  = valid[valid["dist_from_best"].abs() >  band]
        if len(near) < 30:
            continue
        r = {
            "band_pct":       round(band * 100, 1),
            "near_n":         len(near),
            "near_pct_total": round(len(near) / base_n * 100, 1),
            "near_sr":        round((near["gross_return"] > 0).mean() * 100, 1),
            "near_avg_ret":   round(near["gross_return"].mean() * 100, 2),
            "near_avg_mae":   round(near["mae"].abs().mean() * 100, 2) if "mae" in near.columns else None,
            "far_n":          len(far),
            "far_sr":         round((far["gross_return"] > 0).mean() * 100, 1),
            "far_avg_ret":    round(far["gross_return"].mean() * 100, 2),
            "far_avg_mae":    round(far["mae"].abs().mean() * 100, 2) if "mae" in far.columns else None,
            "sr_lift":        round((near["gross_return"] > 0).mean() * 100 - base_sr, 1),
            "avg_ret_lift":   round(near["gross_return"].mean() * 100 - base_avg, 2),
        }
        results_bands.append(r)

    # ── Direction split (above vs below MA at entry) ─────────────────────────
    for band in [0.010, 0.015, 0.020]:
        near = valid[valid["dist_from_best"].abs() <= band]
        if len(near) < 30:
            continue
        above = near[near["above_best_ma"]]
        below = near[~near["above_best_ma"]]
        results_bands.append({
            "band_pct":       round(band * 100, 1),
            "split":          "above_vs_below",
            "above_n":        len(above),
            "above_sr":       round((above["gross_return"] > 0).mean() * 100, 1) if len(above) > 5 else None,
            "above_avg_ret":  round(above["gross_return"].mean() * 100, 2) if len(above) > 5 else None,
            "below_n":        len(below),
            "below_sr":       round((below["gross_return"] > 0).mean() * 100, 1) if len(below) > 5 else None,
            "below_avg_ret":  round(below["gross_return"].mean() * 100, 2) if len(below) > 5 else None,
        })

    # ── High-score MA filter (score ≥ threshold) ─────────────────────────────
    results_score = []
    for score_thr in [30, 35, 40]:
        for band in [0.010, 0.015, 0.020]:
            hs = valid[(valid["best_ma_score"] >= score_thr) & (valid["dist_from_best"].abs() <= band)]
            base_hs = valid[valid["best_ma_score"] >= score_thr]
            if len(hs) < 20:
                continue
            results_score.append({
                "score_thr":    score_thr,
                "band_pct":     round(band * 100, 1),
                "n":            len(hs),
                "base_n_hs":    len(base_hs),
                "sr":           round((hs["gross_return"] > 0).mean() * 100, 1),
                "avg_ret":      round(hs["gross_return"].mean() * 100, 2),
                "avg_mae":      round(hs["mae"].abs().mean() * 100, 2) if "mae" in hs.columns else None,
                "sr_vs_base":   round((hs["gross_return"] > 0).mean() * 100 - base_sr, 1),
                "avg_ret_vs_base": round(hs["gross_return"].mean() * 100 - base_avg, 2),
            })

    # ── Per-MA-type analysis ──────────────────────────────────────────────────
    results_by_ma = []
    for ma_lbl in [f"{t}{p}" for t in ["EMA","SMA"] for p in MA_PERIODS]:
        sub = valid[(valid["best_ma_label"] == ma_lbl) & (valid["dist_from_best"].abs() <= 0.015)]
        base_sub = valid[valid["best_ma_label"] == ma_lbl]
        if len(sub) < 20:
            continue
        results_by_ma.append({
            "ma":           ma_lbl,
            "near_n":       len(sub),
            "base_n":       len(base_sub),
            "sr":           round((sub["gross_return"] > 0).mean() * 100, 1),
            "avg_ret":      round(sub["gross_return"].mean() * 100, 2),
            "avg_mae":      round(sub["mae"].abs().mean() * 100, 2) if "mae" in sub.columns else None,
            "sr_vs_base":   round((sub["gross_return"] > 0).mean() * 100 -
                                  (base_sub["gross_return"] > 0).mean() * 100, 1) if len(base_sub) > 5 else None,
        })
    results_by_ma.sort(key=lambda x: -(x["sr"] or 0))

    # ── Print summary ────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  BASE RATE — all valid trades")
    print(f"{'='*72}")
    print(f"  N={base_n:,} | SR={base_sr:.1f}% | avg_ret={base_avg:+.2f}% | avg_MAE={base_mae:.2f}%")

    print(f"\n{'='*72}")
    print(f"  BAND ANALYSIS — near vs far from best MA")
    print(f"{'='*72}")
    print(f"  {'Band':>6}  {'Near N':>8}  {'Near SR':>8}  {'Far SR':>7}  {'SR lift':>8}  {'Ret lift':>9}  {'Near MAE':>9}")
    for r in results_bands:
        if "split" not in r:
            print(f"  {r['band_pct']:>5}%  {r['near_n']:>8,}  {r['near_sr']:>7.1f}%  {r['far_sr']:>6.1f}%  {r['sr_lift']:>+7.1f}pp  {r['avg_ret_lift']:>+8.2f}%  {r['near_avg_mae']:>8.2f}%")

    print(f"\n  DIRECTION SPLIT within band:")
    for r in results_bands:
        if "split" in r:
            a_sr = r.get('above_sr') or 0
            b_sr = r.get('below_sr') or 0
            print(f"  ±{r['band_pct']}%: above_MA SR={a_sr:.1f}% (N={r['above_n']}) | below_MA SR={b_sr:.1f}% (N={r['below_n']})")

    print(f"\n{'='*72}")
    print(f"  HIGH-SCORE MA FILTER (score ≥ threshold + distance band)")
    print(f"{'='*72}")
    print(f"  {'Score':>6}  {'Band':>6}  {'N':>7}  {'SR':>7}  {'SR vs base':>11}  {'Ret vs base':>12}")
    for r in results_score:
        print(f"  {r['score_thr']:>6}  {r['band_pct']:>5}%  {r['n']:>7,}  {r['sr']:>6.1f}%  {r['sr_vs_base']:>+10.1f}pp  {r['avg_ret_vs_base']:>+11.2f}%")

    print(f"\n{'='*72}")
    print(f"  PER-MA-TYPE — near ±1.5%, SR ranking")
    print(f"{'='*72}")
    print(f"  {'MA':>8}  {'Near N':>8}  {'SR':>7}  {'SR vs base_sub':>15}  {'avg_ret':>8}  {'avg_MAE':>8}")
    for r in results_by_ma[:15]:
        sv = r['sr_vs_base'] or 0
        print(f"  {r['ma']:>8}  {r['near_n']:>8,}  {r['sr']:>6.1f}%  {sv:>+14.1f}pp  {r['avg_ret']:>+7.2f}%  {r['avg_mae']:>7.2f}%")

    # ── Write output ────────────────────────────────────────────────────────
    output = {
        "asof_date": str(pd.Timestamp.today().date()),
        "data_source": {
            "trades": str(TRADES_PQ),
            "panel":  str(PANEL_PQ),
            "ma_json": str(MA_JSON),
        },
        "base_rate": {
            "n": base_n, "sr_pct": round(base_sr, 1),
            "avg_ret_pct": round(base_avg, 2), "avg_mae_pct": round(base_mae, 2),
        },
        "band_results": results_bands,
        "score_filter_results": results_score,
        "per_ma_results": results_by_ma,
        "primary_window": PRIMARY_WIN,
        "min_score": MIN_SCORE,
        "min_events": MIN_EVENTS,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten: {OUT_JSON}")


if __name__ == "__main__":
    main()
