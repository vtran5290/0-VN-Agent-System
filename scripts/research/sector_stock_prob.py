"""
Per-stock rotation priority score (heuristic, NOT a calibrated probability).
rotation_priority_score = sector_weight × (stock_technical_score / 100) × 100

NOTE: "final_prob" was renamed to "rotation_priority_score" — this is a
heuristic ranking metric, not a statistically calibrated probability.
Calibration requires a trained+validated model (see indicator_walkforward.py).

Liquid universe: ADV50 >= 2B VND/day
Sector map: data/master/sector_map.csv (canonical taxonomy)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from pathlib import Path

ROOT  = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
SMAP  = ROOT / "data/master/sector_map.csv"

# ── Canonical sector rotation weights (qualitative, NOT probabilities) ──────
# Key: primary_sector from sector_map.csv
SECTOR_WEIGHT = {
    "Banks":      0.45,
    "Oil_Gas":    0.35,
    "Rubber":     0.25,
    "Agri":       0.20,
    "Consumer":   0.15,
    "BDS":        0.12,
    "Logistics":  0.12,
    "Securities": 0.10,
    "Textile":    0.08,
    "Steel":      0.06,
    "VIN_Group":  0.05,
    "Tech":       0.04,
}

ADV50_MIN = 2_000_000_000   # 2B VND/day — computed from close_VND × volume

def load_data():
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    # Panel close is always in thousand-VND; scale to VND
    med = df.groupby("symbol")["close"].median().median()
    if med < 500:
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col] * 1000
    # Compute ADV50 directly from close_VND × volume (avoids value-column unit ambiguity)
    df["_value_vnd"] = df["close"] * df["volume"]
    return df


def load_sector_map() -> dict:
    """Return {symbol: primary_sector} from canonical sector_map.csv."""
    sm = pd.read_csv(SMAP)
    return dict(zip(sm["symbol"], sm["primary_sector"]))

def compute_signals(df):
    results = []
    symbols = df["symbol"].unique()
    for sym in symbols:
        sd = df[df["symbol"]==sym].copy().reset_index(drop=True)
        if len(sd) < 60:
            continue
        # ADV50 from close_VND × volume (no value-column ambiguity)
        adv50 = sd["_value_vnd"].iloc[-50:].mean() if len(sd)>=50 else sd["_value_vnd"].mean()
        if adv50 < ADV50_MIN:
            continue

        close = sd["close"].values
        vol   = sd["volume"].values
        n = len(close)

        # Returns
        def ret(p): return (close[-1]/close[-p]-1)*100 if n>p else np.nan
        r5   = ret(5)
        r20  = ret(20)
        r60  = ret(60)
        r120 = ret(120)
        r252 = ret(min(252, n-1))

        # MA alignment
        ma50  = np.mean(close[-50:])  if n>=50  else np.nan
        ma150 = np.mean(close[-150:]) if n>=150 else np.nan
        ma200 = np.mean(close[-200:]) if n>=200 else np.nan
        price = close[-1]
        ma_ok = (not np.isnan(ma50) and not np.isnan(ma150) and not np.isnan(ma200)
                 and price > ma50 > ma150 > ma200)

        # 52w distance
        hi52 = np.max(close[-min(252,n):])
        dist_hi52 = (price / hi52 - 1) * 100

        # ATR contraction
        def atr_series(w):
            tr = np.maximum(sd["high"].values[-w:]-sd["low"].values[-w:],
                 np.maximum(abs(sd["high"].values[-w:]-np.roll(sd["close"].values[-w:],1)),
                            abs(sd["low"].values[-w:] -np.roll(sd["close"].values[-w:],1))))
            return np.mean(tr[1:])
        atr14 = atr_series(15) if n>=15 else np.nan
        atr50 = atr_series(51) if n>=51 else np.nan
        atr_ratio = atr14/atr50 if (not np.isnan(atr14) and atr50>0) else 1.0

        # OBV direction (slope of last 20 bars)
        if n >= 20:
            obv = np.cumsum(np.where(np.diff(close[-21:])>0, vol[-20:],
                  np.where(np.diff(close[-21:])<0, -vol[-20:], 0)))
            obv_slope = np.polyfit(np.arange(len(obv)), obv, 1)[0]
            obv_up = obv_slope > 0
        else:
            obv_up = False

        # CMF20
        if n >= 20:
            hl   = sd["high"].values[-20:] - sd["low"].values[-20:]
            mfv  = np.where(hl>0,
                   ((sd["close"].values[-20:]-sd["low"].values[-20:])-
                    (sd["high"].values[-20:]-sd["close"].values[-20:]))/hl * vol[-20:], 0)
            cmf20 = np.sum(mfv)/np.sum(vol[-20:]) if np.sum(vol[-20:])>0 else 0
        else:
            cmf20 = 0

        # Distribution days (close down >0.2% on above-avg volume, last 25 sessions)
        if n >= 25:
            avg_v = np.mean(vol[-50:]) if n>=50 else np.mean(vol)
            ret_d = np.diff(close[-26:]) / close[-26:-1]
            vol_d = vol[-25:]
            dist_days = int(np.sum((ret_d < -0.002) & (vol_d > avg_v)))
        else:
            dist_days = 0

        # ── Scoring ──────────────────────────────────────────────────────────
        score = 0
        # Momentum (40 pts)
        score += min(10, max(0, r20/2))      if not np.isnan(r20)  else 0
        score += min(10, max(0, r60/4))      if not np.isnan(r60)  else 0
        score += min(10, max(0, r120/6))     if not np.isnan(r120) else 0
        score += min(10, max(0, r252/10))    if not np.isnan(r252) else 0
        # MA alignment (15 pts)
        score += 15 if ma_ok else 0
        # 52w proximity (10 pts)  — closer to high is better
        score += max(0, 10 + dist_hi52/2)   # dist_hi52 is negative
        # ATR contraction (10 pts) — lower ratio = quieter base
        score += max(0, min(10, (1-atr_ratio)*20))
        # Volume/MF (15 pts)
        score += 8 if obv_up else 0
        score += min(7, max(0, cmf20*50))
        # Distribution penalty (10 pts max deduct)
        score -= min(10, dist_days * 2)

        score = max(0, min(100, score))

        momentum_flag = "UP" if (not np.isnan(r20) and r20>0 and not np.isnan(r60) and r60>0) else "FLAT/DN"

        results.append({
            "symbol":        sym,
            "adv50_B":       round(adv50/1e9, 2),   # billions VND/day, from close_VND × vol
            "close":         round(price/1000, 1),   # back to kVND display
            "stock_score":   round(score, 1),
            "r5":            round(r5,   1) if not np.isnan(r5)   else None,
            "r20":           round(r20,  1) if not np.isnan(r20)  else None,
            "r60":           round(r60,  1) if not np.isnan(r60)  else None,
            "r120":          round(r120, 1) if not np.isnan(r120) else None,
            "cmf20":         round(cmf20, 3),
            "dist_hi52_pct": round(dist_hi52, 1),
            "obv_up":        obv_up,
            "dist_days":     dist_days,
            "momentum":      momentum_flag,
            "ma_aligned":    ma_ok,
        })
    return pd.DataFrame(results)

def main():
    print("Loading panel data...")
    df = load_data()
    print(f"  {len(df):,} rows | {df['symbol'].nunique()} tickers | last date {df['date'].max().date()}")

    print("Loading sector map...")
    sector_map = load_sector_map()

    print("Computing signals (ADV50 >= 2B filter)...")
    sig = compute_signals(df)
    print(f"  {len(sig)} liquid stocks passed filter")

    # Map to canonical sector taxonomy
    sig["sector"]       = sig["symbol"].map(sector_map).fillna("Other")
    sig["sector_weight"] = sig["sector"].map(SECTOR_WEIGHT).fillna(0.0)

    # rotation_priority_score = heuristic ranking (NOT a calibrated probability)
    sig["rotation_priority_score"] = (
        sig["sector_weight"] * sig["stock_score"] / 100 * 100
    ).round(1)

    # ── Output ────────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  PER-STOCK ROTATION PRIORITY SCORE  [HEURISTIC — not calibrated probability]")
    print("  score = sector_weight x stock_tech_score  |  ADV50 from close_VND x volume")
    print("="*80)

    sector_order = sorted(SECTOR_WEIGHT.keys(), key=lambda s: -SECTOR_WEIGHT[s])

    for sector in sector_order:
        sub = sig[sig["sector"]==sector].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("rotation_priority_score", ascending=False)
        sw  = SECTOR_WEIGHT[sector]
        print(f"\n{'='*80}")
        print(f"  {sector}  |  sector_weight = {sw*100:.0f}  |  {len(sub)} stocks")
        print(f"{'='*80}")
        hdr = f"  {'Ticker':<6} {'ADV50':>6} {'Price':>7} {'Score':>6} {'PriScore':>9}  {'r20':>6} {'r60':>6} {'r120':>7} {'CMF20':>7} {'DistHi':>7} {'Mom':>7} {'DD':>3}"
        print(hdr)
        print("  " + "-"*(len(hdr)-2))
        for _, row in sub.iterrows():
            r20s  = f"{row['r20']:+.1f}%" if row['r20']  is not None else "  --"
            r60s  = f"{row['r60']:+.1f}%" if row['r60']  is not None else "  --"
            r120s = f"{row['r120']:+.1f}%" if row['r120'] is not None else "  --"
            print(f"  {row['symbol']:<6} {row['adv50_B']:>5.1f}B {row['close']:>7.1f}k"
                  f"  {row['stock_score']:>5.1f}   {row['rotation_priority_score']:>8.1f}"
                  f"  {r20s:>7} {r60s:>7} {r120s:>8}"
                  f"  {row['cmf20']:>7.3f}"
                  f"  {row['dist_hi52_pct']:>+7.1f}%"
                  f"  {row['momentum']:>7}"
                  f"  {row['dist_days']:>2}")

    # ── Ranked cross-sector top 30 ────────────────────────────────────────────
    top30 = sig[sig["sector"].isin(SECTOR_WEIGHT)].sort_values(
        "rotation_priority_score", ascending=False).head(30)
    print("\n" + "="*80)
    print("  TOP 30 STOCKS — ROTATION PRIORITY SCORE  [CANDIDATE_RESEARCH]")
    print("="*80)
    hdr2 = f"  {'Rk':>3} {'Ticker':<6} {'Sector':<12} {'Weight':>7} {'Score':>6} {'PriScore':>9}  {'r20':>7} {'r60':>7} {'Mom':>7}"
    print(hdr2)
    print("  " + "-"*(len(hdr2)-2))
    for i, (_, row) in enumerate(top30.iterrows(), 1):
        r20s = f"{row['r20']:+.1f}%" if row['r20'] is not None else "  --"
        r60s = f"{row['r60']:+.1f}%" if row['r60'] is not None else "  --"
        print(f"  {i:>3}. {row['symbol']:<6} {row['sector']:<12}"
              f" {row['sector_weight']*100:>6.0f}  {row['stock_score']:>5.1f}"
              f"   {row['rotation_priority_score']:>8.1f}"
              f"  {r20s:>7} {r60s:>7}  {row['momentum']:>7}")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    out = ROOT / "data/research/sector_stock_prob_v2.csv"
    sig_out = sig[sig["sector"].isin(SECTOR_WEIGHT)].sort_values(
        ["sector_weight", "rotation_priority_score"], ascending=[False, False])
    # Rename for backward compat: keep final_prob as alias
    sig_out = sig_out.copy()
    sig_out["final_prob"] = sig_out["rotation_priority_score"]
    sig_out.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {out}")
    print("Note: 'final_prob' column kept as alias. Use 'rotation_priority_score' going forward.")
    print("Done.")

if __name__ == "__main__":
    main()
