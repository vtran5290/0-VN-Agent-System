"""
Per-stock rotation probability = sector_rotation_prob × (stock_technical_score / 100)
Liquid universe: ADV50 >= 2B VND/day
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"

# ── Sector rotation probabilities (from qualitative analysis) ──────────────
SECTOR_PROB = {
    "Banks":     0.45,
    "Rubber":    0.25,
    "Oil_Gas":   0.35,
    "Agri":      0.20,
    "Consumer":  0.15,
    "RE":        0.12,
    "Logistic":  0.12,
    "Securi":    0.10,
    "Textile":   0.08,
    "Steel":     0.06,
    "Tech":      0.04,
    "VIN":       0.05,
}

# ── Sector membership (liquid names only — extend as needed) ───────────────
SECTOR_MAP = {
    # Banks
    "VCB":"Banks","BID":"Banks","CTG":"Banks","MBB":"Banks","TCB":"Banks",
    "VPB":"Banks","ACB":"Banks","HDB":"Banks","STB":"Banks","TPB":"Banks",
    "LPB":"Banks","SHB":"Banks","MSB":"Banks","OCB":"Banks","VIB":"Banks",
    "EIB":"Banks","SSB":"Banks","BAB":"Banks","ABB":"Banks","NVB":"Banks",
    # Oil & Gas
    "GAS":"Oil_Gas","PVS":"Oil_Gas","PVD":"Oil_Gas","PLX":"Oil_Gas",
    "BSR":"Oil_Gas","OIL":"Oil_Gas","PVC":"Oil_Gas",
    # Steel / Materials
    "HPG":"Steel","NKG":"Steel","HSG":"Steel","TLH":"Steel","TVN":"Steel",
    "POM":"Steel","VIS":"Steel",
    # Real Estate
    "VIC":"VIN","VHM":"VIN","VRE":"VIN",    # VIN group in RE
    "NVL":"RE","PDR":"RE","DXG":"RE","DIG":"RE","KDH":"RE","CEO":"RE",
    "HDC":"RE","LDG":"RE","AGG":"RE","SZC":"RE","BCM":"RE","IJC":"RE",
    # Securities
    "SSI":"Securi","VND":"Securi","HCM":"Securi","MBS":"Securi","VCI":"Securi",
    "SHS":"Securi","BSI":"Securi","FTS":"Securi","CTS":"Securi","AGR":"Securi",
    # Consumer / Retail / Food
    "MWG":"Consumer","FRT":"Consumer","PNJ":"Consumer","MSN":"Consumer",
    "SAB":"Consumer","VNM":"Consumer","MCH":"Consumer","ANV":"Consumer",
    "DBC":"Consumer","BAF":"Consumer","HAG":"Consumer","HNG":"Consumer",
    # Tech / Telecom
    "FPT":"Tech","VGI":"Tech","CMG":"Tech","ELC":"Tech","ICT":"Tech",
    # Rubber
    "PHR":"Rubber","DPR":"Rubber","TRC":"Rubber","SVR":"Rubber","HRC":"Rubber",
    # Agri / Fertilizer
    "DCM":"Agri","DPM":"Agri","BFC":"Agri","LTG":"Agri","HAH":"Agri",
    # Logistics / Port
    "GMD":"Logistic","VSC":"Logistic","DVP":"Logistic","HAH":"Logistic",
    "PHP":"Logistic","TMS":"Logistic","VOS":"Logistic","PVT":"Logistic",
    # Textile / Garment
    "MSH":"Textile","TCM":"Textile","TNG":"Textile","VGT":"Textile",
    "GIL":"Textile","STK":"Textile",
}

ADV50_MIN = 2_000_000_000   # 2B VND/day (value column is in VND)

def load_data():
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol","date"])
    # unit check: if median close < 500 assume thousand-VND → multiply
    med = df.groupby("symbol")["close"].median()
    if med.median() < 500:
        df["close"] = df["close"] * 1000
        df["open"]  = df["open"]  * 1000
        df["high"]  = df["high"]  * 1000
        df["low"]   = df["low"]   * 1000
    # value column: if median value < 1e8 assume thousand-VND
    med_val = df["value"].median()
    if med_val < 1e8:
        df["value"] = df["value"] * 1000
    return df

def compute_signals(df):
    results = []
    symbols = df["symbol"].unique()
    for sym in symbols:
        sd = df[df["symbol"]==sym].copy().reset_index(drop=True)
        if len(sd) < 60:
            continue
        # ADV50
        adv50 = sd["value"].iloc[-50:].mean() if len(sd)>=50 else sd["value"].mean()
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
            "adv50_B":       round(adv50/1e9, 2),
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

    print("Computing signals (ADV50 >= 2B filter)...")
    sig = compute_signals(df)
    print(f"  {len(sig)} liquid stocks passed filter")

    # Map to sector
    sig["sector"] = sig["symbol"].map(SECTOR_MAP).fillna("Other")
    sig["sector_prob"] = sig["sector"].map(SECTOR_PROB).fillna(0.0)
    sig["final_prob"]  = (sig["sector_prob"] * sig["stock_score"] / 100 * 100).round(1)

    # ── Output ────────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  PER-STOCK ROTATION PROBABILITY  |  final_prob = sector_prob x stock_score")
    print("="*80)

    sector_order = sorted(SECTOR_PROB.keys(), key=lambda s: -SECTOR_PROB[s])

    for sector in sector_order:
        sub = sig[sig["sector"]==sector].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("final_prob", ascending=False)
        sp  = SECTOR_PROB[sector]
        print(f"\n{'='*80}")
        print(f"  {sector}  |  sector_rotation_prob = {sp*100:.0f}%  |  {len(sub)} stocks")
        print(f"{'='*80}")
        hdr = f"  {'Ticker':<6} {'ADV50':>6} {'Price':>7} {'Score':>6} {'FinalProb':>10}  {'r20':>6} {'r60':>6} {'r120':>7} {'CMF20':>7} {'DistHi':>7} {'Mom':>7} {'DD':>3}"
        print(hdr)
        print("  " + "-"*(len(hdr)-2))
        for _, row in sub.iterrows():
            r20s  = f"{row['r20']:+.1f}%" if row['r20']  is not None else "  --"
            r60s  = f"{row['r60']:+.1f}%" if row['r60']  is not None else "  --"
            r120s = f"{row['r120']:+.1f}%" if row['r120'] is not None else "  --"
            print(f"  {row['symbol']:<6} {row['adv50_B']:>5.1f}B {row['close']:>7.1f}k"
                  f"  {row['stock_score']:>5.1f}   {row['final_prob']:>8.1f}%"
                  f"  {r20s:>7} {r60s:>7} {r120s:>8}"
                  f"  {row['cmf20']:>7.3f}"
                  f"  {row['dist_hi52_pct']:>+7.1f}%"
                  f"  {row['momentum']:>7}"
                  f"  {row['dist_days']:>2}")

    # ── Ranked cross-sector top 30 ────────────────────────────────────────────
    top30 = sig[sig["sector"].isin(SECTOR_PROB)].sort_values("final_prob", ascending=False).head(30)
    print("\n" + "="*80)
    print("  TOP 30 STOCKS ACROSS ALL SECTORS  (final_prob = sector x score)")
    print("="*80)
    hdr2 = f"  {'Rk':>3} {'Ticker':<6} {'Sector':<10} {'SectP':>6} {'Score':>6} {'FinalProb':>10}  {'r20':>7} {'r60':>7} {'Mom':>7}"
    print(hdr2)
    print("  " + "-"*(len(hdr2)-2))
    for i, (_, row) in enumerate(top30.iterrows(), 1):
        r20s = f"{row['r20']:+.1f}%" if row['r20'] is not None else "  --"
        r60s = f"{row['r60']:+.1f}%" if row['r60'] is not None else "  --"
        print(f"  {i:>3}. {row['symbol']:<6} {row['sector']:<10}"
              f" {row['sector_prob']*100:>5.0f}%  {row['stock_score']:>5.1f}"
              f"   {row['final_prob']:>8.1f}%"
              f"  {r20s:>7} {r60s:>7}  {row['momentum']:>7}")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    out = ROOT / "data/research/sector_stock_prob.csv"
    sig_out = sig[sig["sector"].isin(SECTOR_PROB)].sort_values(
        ["sector_prob","final_prob"], ascending=[False,False])
    sig_out.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {out}")
    print("Done.")

if __name__ == "__main__":
    main()
