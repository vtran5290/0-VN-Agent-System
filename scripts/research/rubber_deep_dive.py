"""
Rubber sector deep-dive: full technical + FA analysis
Stocks: PHR, DPR, TRC, HRC, GVR, CSM, SRC, SVR
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from pathlib import Path

ROOT  = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
FA_A  = ROOT / "data/fireant_ssot/fa_annual.parquet"
FA_Q  = ROOT / "data/fireant_ssot/fa_quarterly.parquet"

RUBBER = ["PHR","DPR","TRC","HRC","GVR","CSM","SRC","SVR"]

# ── helpers ────────────────────────────────────────────────────────────────────
def slope_pct(arr):
    if len(arr) < 2: return 0.0
    x = np.arange(len(arr), dtype=float)
    m = np.polyfit(x, arr, 1)[0]
    return float(m / abs(arr[0]) * 100) if arr[0] != 0 else 0.0

def rsi_val(close, n=14):
    if len(close) < n+1: return 50.0
    delta = np.diff(close[-(n+2):])
    gains  = np.where(delta>0, delta, 0.0)
    losses = np.where(delta<0,-delta, 0.0)
    ag = np.mean(gains[-n:]);  al = np.mean(losses[-n:])
    return float(100 - 100/(1+ag/al)) if al>0 else 100.0

def macd_signal(close):
    if len(close) < 35: return 0.0, 0.0
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd  = ema12 - ema26
    sig   = pd.Series(macd).ewm(span=9, adjust=False).mean().values
    return float(macd[-1]), float(sig[-1])

def bb_width_pct(close, n=20, history=252):
    if len(close) < n+history: return np.nan, np.nan
    widths = []
    for i in range(history, 0, -1):
        w  = close[-(n+i):-(i)]
        if len(w) < n: continue
        m  = np.mean(w); s = np.std(w)
        widths.append(2*s/m*100 if m else 0)
    if not widths: return np.nan, np.nan
    # current
    curr_w = close[-n:]
    curr   = 2*np.std(curr_w)/np.mean(curr_w)*100 if np.mean(curr_w) else 0
    pct    = float(np.mean(np.array(widths) <= curr) * 100)
    return round(curr, 2), round(pct, 0)

def stoch_rsi_val(close, n=14, smooth=3):
    """StochRSI: RSI of RSI, smoothed."""
    if len(close) < n*2+smooth+5: return np.nan
    # compute RSI series over last n+smooth+n bars
    r_series = []
    for i in range(smooth+n, 0, -1):
        r_series.append(rsi_val(close[:len(close)-i+1], n))
    if not r_series: return np.nan
    lo, hi = min(r_series), max(r_series)
    if hi == lo: return 50.0
    raw = [(v-lo)/(hi-lo)*100 for v in r_series]
    return float(np.mean(raw[-smooth:]))

def atr_n(sd, n=14):
    h,l,c = sd["high"].values, sd["low"].values, sd["close"].values
    if len(h) < n+1: return np.nan
    tr = np.maximum(h[1:]-l[1:], np.maximum(abs(h[1:]-c[:-1]), abs(l[1:]-c[:-1])))
    return float(np.mean(tr[-n:]))

def obv_slope(close, vol, n=20):
    if len(close) < n+1: return 0.0
    d = np.diff(close[-(n+1):])
    o = np.cumsum(np.where(d>0, vol[-n:], np.where(d<0,-vol[-n:], 0)))
    return float(slope_pct(o))

def cmf_val(sd, n=20):
    if len(sd) < n: return 0.0
    h,l,c,v = (sd["high"].values[-n:], sd["low"].values[-n:],
                sd["close"].values[-n:], sd["volume"].values[-n:])
    hl = h-l
    mfv = np.where(hl>0, ((c-l)-(h-c))/hl*v, 0)
    return float(np.sum(mfv)/np.sum(v)) if np.sum(v)>0 else 0.0

def rs_vs_vni(stock_c, vni_c, n=60):
    if len(stock_c)<n or len(vni_c)<n: return np.nan
    sr = stock_c[-1]/stock_c[-n]-1
    vr = vni_c[-1]/vni_c[-n]-1
    return round((sr-vr)*100, 1)

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("Loading OHLCV...")
df = pd.read_parquet(PANEL)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol","date"])
if df.groupby("symbol")["close"].median().median() < 500:
    for col in ["open","high","low","close"]: df[col] *= 1000
if df["value"].median() < 1e8: df["value"] *= 1000

vni = pd.read_parquet(VNIDX).sort_values("date")
vni_c = vni["close"].values if "close" in vni.columns else vni.iloc[:,1].values

# ── Load FA ───────────────────────────────────────────────────────────────────
print("Loading FA data...")
fa_a = pd.read_parquet(FA_A); fa_a.columns = [c.lower() for c in fa_a.columns]
fa_q = pd.read_parquet(FA_Q); fa_q.columns = [c.lower() for c in fa_q.columns]

# column aliases
REV   = "financialvalues_totalrevenue"
PAT   = "financialvalues_profitaftertax"        # profit after tax
EPS   = "financialvalues_basiceps"
ROE   = "financialvalues_roe"
ROA   = "financialvalues_roa"
GM    = "financialvalues_grossmargin"
GP    = "financialvalues_grossprofit"
DEBT  = "financialvalues_totaldebt"
EQ    = "financialvalues_stockholderequity"
CR    = "financialvalues_currentratio"
EPS_G = "financialvalues_basicepsgrowth"        # YoY EPS growth pre-computed

def safe_pct(new, old):
    return round((new/old-1)*100, 1) if (pd.notna(new) and pd.notna(old) and old!=0) else np.nan

def get_fa(sym):
    out = {"symbol": sym}

    # ── Annual (quarter==0 rows are the annual snapshot) ────────────────────
    a = fa_a[(fa_a["symbol"]==sym) & (fa_a["quarter"]==0)].sort_values("year")
    if not a.empty:
        def lastval(col):
            if col not in a.columns: return np.nan
            v = a[col].dropna()
            return float(v.iloc[-1]) if len(v)>0 else np.nan
        def prevval(col, n=1):
            if col not in a.columns: return np.nan
            v = a[col].dropna()
            return float(v.iloc[-1-n]) if len(v)>n else np.nan

        rev_last  = lastval(REV);  rev_prev  = prevval(REV);  rev_2y = prevval(REV,2)
        pat_last  = lastval(PAT);  pat_prev  = prevval(PAT)
        eps_last  = lastval(EPS);  eps_prev  = prevval(EPS)
        gp_last   = lastval(GP);   gp_prev   = prevval(GP)

        out["rev_yoy"]    = safe_pct(rev_last, rev_prev)
        out["rev_2y"]     = safe_pct(rev_last, rev_2y)
        out["ni_yoy"]     = safe_pct(pat_last, pat_prev)
        out["eps_ttm"]    = eps_last
        out["eps_yoy"]    = safe_pct(eps_last, eps_prev)
        # pre-computed EPS growth from FA (lfy = last full year)
        epsg = lastval(EPS_G)
        out["eps_growth_fa"] = round(epsg*100, 1) if (pd.notna(epsg) and abs(epsg)<50) else out["eps_yoy"]
        out["roe"]        = round(lastval(ROE)*100, 1) if pd.notna(lastval(ROE)) else np.nan
        out["roa"]        = round(lastval(ROA)*100, 1) if pd.notna(lastval(ROA)) else np.nan
        out["gross_margin"]= round(lastval(GM)*100, 1)  if (pd.notna(lastval(GM)) and lastval(GM)<1) else round(lastval(GM),1) if pd.notna(lastval(GM)) else np.nan
        # gross margin calculated
        if pd.notna(gp_last) and pd.notna(rev_last) and rev_last>0:
            out["gross_margin"] = round(gp_last/rev_last*100, 1)
        out["de_ratio"]   = round(lastval(DEBT)/lastval(EQ), 2) if (pd.notna(lastval(DEBT)) and pd.notna(lastval(EQ)) and lastval(EQ)>0) else np.nan
        out["curr_ratio"] = round(lastval(CR), 2) if pd.notna(lastval(CR)) else np.nan
        out["latest_year"]= int(a["year"].iloc[-1]) if len(a)>0 else np.nan

    # ── Quarterly (quarter in 1-4) ────────────────────────────────────────────
    q = fa_q[(fa_q["symbol"]==sym) & (fa_q["quarter"]>0)].sort_values(["year","quarter"])
    if not q.empty and REV in q.columns and PAT in q.columns:
        q_rev = q[REV].dropna()
        q_pat = q[PAT].dropna()
        if len(q_pat)>=5:
            out["ni_yoy_q"] = safe_pct(float(q_pat.iloc[-1]), float(q_pat.iloc[-5]))
            out["ni_qoq"]   = safe_pct(float(q_pat.iloc[-1]), float(q_pat.iloc[-2]))
        if len(q_rev)>=5:
            out["rev_yoy_q"]= safe_pct(float(q_rev.iloc[-1]), float(q_rev.iloc[-5]))
        # revenue acceleration (last 2Q vs prior 2Q)
        if len(q_rev)>=4:
            recent2 = float(q_rev.iloc[-2:].sum())
            prior2  = float(q_rev.iloc[-4:-2].sum())
            out["rev_accel"] = safe_pct(recent2, prior2)

    return out

# ── Technical analysis ─────────────────────────────────────────────────────────
print("Computing technical indicators...")
tech_rows = []
for sym in RUBBER:
    sd = df[df["symbol"]==sym].copy().reset_index(drop=True)
    if len(sd) < 60:
        print(f"  {sym}: only {len(sd)} bars — skipping"); continue
    n = len(sd)
    c = sd["close"].values; v = sd["volume"].values; price = c[-1]
    adv50 = sd["value"].iloc[-50:].mean() if n>=50 else sd["value"].mean()

    # Returns
    def ret(p): return round((c[-1]/c[-p]-1)*100,1) if n>p else np.nan

    # MAs
    ma50  = np.mean(c[-50:])  if n>=50  else np.nan
    ma150 = np.mean(c[-150:]) if n>=150 else np.nan
    ma200 = np.mean(c[-200:]) if n>=200 else np.nan
    ma50_sl  = slope_pct(c[-50:])  if n>=50  else np.nan
    ma150_sl = slope_pct(c[-150:]) if n>=150 else np.nan

    s2_pm50  = price > ma50  if not np.isnan(ma50)  else False
    s2_pm150 = price > ma150 if not np.isnan(ma150) else False
    s2_pm200 = price > ma200 if not np.isnan(ma200) else False
    s2_align = (not any(np.isnan([ma50,ma150,ma200]))) and ma50>ma150>ma200
    s2_slope = ma50_sl > 0 if not np.isnan(ma50_sl) else False
    stage2   = sum([s2_pm50, s2_pm150, s2_pm200, s2_align, s2_slope])

    # 52w
    hi52 = np.max(c[-min(252,n):]); lo52 = np.min(c[-min(252,n):])
    dist_hi = round((price/hi52-1)*100, 1)
    dist_lo = round((price/lo52-1)*100, 1)

    # Volatility
    atr14  = atr_n(sd, 14)
    atr50  = atr_n(sd, 50) if n>=60 else np.nan
    atr_r  = round(atr14/atr50, 2) if (pd.notna(atr14) and pd.notna(atr50) and atr50>0) else np.nan

    # Bollinger
    bb_w, bb_pct = bb_width_pct(c) if n >= 272 else (np.nan, np.nan)

    # RSI / StochRSI / MACD
    rsi14  = round(rsi_val(c, 14), 1)  if n>=20 else np.nan
    srsi   = round(stoch_rsi_val(c), 1) if n>=60 else np.nan
    mc, ms = macd_signal(c)
    macd_b = mc > ms

    # Volume / MF
    avg_v10 = np.mean(v[-10:]) if n>=10 else np.nan
    avg_v50 = np.mean(v[-50:]) if n>=50 else np.nan
    vol_r   = round(avg_v10/avg_v50, 2) if (pd.notna(avg_v50) and avg_v50>0) else np.nan
    cmf20   = round(cmf_val(sd, 20), 3)
    obv_slp = round(obv_slope(c, v, 20), 2)

    # Distribution days (last 25 sessions)
    if n>=25:
        base_v = avg_v50 if pd.notna(avg_v50) else np.mean(v)
        ret_d  = np.diff(c[-26:])/c[-26:-1]
        vol_d  = v[-25:]
        dist_d = int(np.sum((ret_d<-0.002) & (vol_d>base_v)))
    else:
        dist_d = 0

    # RS vs VNINDEX
    rs60  = rs_vs_vni(c, vni_c, 60)
    rs20  = rs_vs_vni(c, vni_c, 20)
    rs252 = rs_vs_vni(c, vni_c, min(252,n-1))

    # Wyckoff phase
    base_forming = pd.notna(atr_r) and atr_r < 0.85
    spring = (dist_lo < 5) and (dist_hi < -15) and vol_r>1.2 if pd.notna(vol_r) else False
    if price > ma200 and not np.isnan(ma200) and cmf20>0.05 and obv_slp>0 and dist_hi>-10:
        wyckoff = "Phase E (markup)"
    elif price > (ma50 if not np.isnan(ma50) else 0) and cmf20>0 and obv_slp>0 and base_forming:
        wyckoff = "Phase D (SOS/LPS)"
    elif spring:
        wyckoff = "Phase C (spring?)"
    elif base_forming and -30<dist_hi<-5:
        wyckoff = "Phase B (base)"
    elif dist_hi < -30:
        wyckoff = "Phase A (stop/AR)"
    else:
        wyckoff = "Undefined"

    tech_rows.append({
        "symbol": sym, "price_k": round(price/1000,1), "adv50_B": round(adv50/1e9,2),
        "r5":ret(5),"r10":ret(10),"r20":ret(20),"r60":ret(60),"r120":ret(120),"r252":ret(min(252,n-1)),
        "vs_ma50": round((price/ma50-1)*100,1)  if not np.isnan(ma50)  else np.nan,
        "vs_ma150":round((price/ma150-1)*100,1) if not np.isnan(ma150) else np.nan,
        "vs_ma200":round((price/ma200-1)*100,1) if not np.isnan(ma200) else np.nan,
        "ma_align":s2_align, "ma50_slope":round(ma50_sl,4) if not np.isnan(ma50_sl) else np.nan,
        "stage2":stage2, "dist_hi52":dist_hi, "dist_lo52":dist_lo,
        "rsi14":rsi14, "srsi":srsi, "macd_bull":macd_b,
        "cmf20":cmf20, "obv_slp":obv_slp, "vol_ratio":vol_r, "dist_days":dist_d,
        "atr_ratio":atr_r, "bb_w":bb_w, "bb_pct":bb_pct,
        "rs60":rs60, "rs20":rs20, "rs252":rs252,
        "wyckoff":wyckoff, "base_forming":base_forming,
    })

tech_df = pd.DataFrame(tech_rows)

# ── FA ────────────────────────────────────────────────────────────────────────
print("Extracting FA metrics...")
fa_rows = [get_fa(sym) for sym in RUBBER]
fa_df   = pd.DataFrame(fa_rows)

merged = tech_df.merge(fa_df, on="symbol", how="left")

# PE
def pe(row):
    eps = row.get("eps_ttm")
    if pd.notna(eps) and eps>0:
        return round(row["price_k"]*1000/eps, 1)
    return np.nan
merged["pe"] = merged.apply(pe, axis=1)

# ── Composite score: Tech 60 + FA 40 ─────────────────────────────────────────
def composite(row):
    t = 0.0
    r20=row.get("r20"); r60=row.get("r60"); r120=row.get("r120"); r252=row.get("r252")
    # Momentum (20)
    t += min(8, max(0, r20/2))    if pd.notna(r20)  else 0
    t += min(7, max(0, r60/4))    if pd.notna(r60)  else 0
    t += min(5, max(0, r120/8))   if pd.notna(r120) else 0
    # Stage2 / MA (10)
    t += row.get("stage2",0) * 2
    # RS vs VNINDEX (5)
    rs = row.get("rs60"); t += min(5, max(0, rs/4)) if pd.notna(rs) else 0
    # Volume/MF (10)
    cmf = row.get("cmf20",0)
    t += min(5, max(0, cmf*30))
    t += 3 if row.get("obv_slp",0)>0 else 0
    t += 2 if (pd.notna(row.get("vol_ratio")) and row.get("vol_ratio",0)>1) else 0
    # Base quality / ATR contraction (5)
    ar = row.get("atr_ratio")
    t += max(0, min(5, (1-ar)*10)) if pd.notna(ar) else 0
    # 52w proximity (5): -5% from hi = 10pts, -20% = 2pts
    dh = row.get("dist_hi52",0)
    t += max(0, min(5, (30+dh)/6))
    # Distribution days penalty (5)
    t -= min(5, row.get("dist_days",0)*1.5)

    f = 0.0
    # Revenue growth (10)
    ry=row.get("rev_yoy"); rq=row.get("rev_yoy_q"); ra=row.get("rev_accel")
    f += min(4, max(0, ry/5))   if pd.notna(ry) else 0
    f += min(4, max(0, rq/5))   if pd.notna(rq) else 0
    f += min(2, max(0, ra/10))  if pd.notna(ra) else 0
    # NI growth (10)
    ny=row.get("ni_yoy"); nq=row.get("ni_yoy_q")
    f += min(5, max(0, ny/5))   if pd.notna(ny) else 0
    f += min(5, max(0, nq/5))   if pd.notna(nq) else 0
    # EPS growth (8)
    eg=row.get("eps_yoy")
    f += min(8, max(0, eg/5))   if pd.notna(eg) else 0
    # ROE (7): 15%=7pts, 10%=4pts
    roe=row.get("roe")
    f += min(7, max(0, roe/2.5))if pd.notna(roe) else 0
    # Gross margin (5)
    gm=row.get("gross_margin")
    f += min(5, max(0, gm/6))   if pd.notna(gm) else 0

    return round(min(100, max(0, t+f)), 1)

merged["composite"] = merged.apply(composite, axis=1)
merged = merged.sort_values("composite", ascending=False).reset_index(drop=True)

# ── Print full report ─────────────────────────────────────────────────────────
W = 92
def bar(n, mx=5, w=10):
    filled = int(round(n/mx*w))
    return "[" + "#"*filled + "."*(w-filled) + "]"

def fs(v, sfx="%"): return f"{v:+.1f}{sfx}" if pd.notna(v) else "--"
def fn(v):          return f"{v:.1f}"        if pd.notna(v) else "--"

print("\n" + "="*W)
print("  CAO SU (RUBBER) — DEEP DIVE ANALYSIS  |  Tech + FA Composite Score")
print(f"  Data as of 2026-05-08  |  Prices in kVND")
print("="*W)

for rank, (_, row) in enumerate(merged.iterrows(), 1):
    sym = row["symbol"]
    score = row["composite"]
    wyck  = row["wyckoff"]

    grade = "A+" if score>=70 else "A" if score>=60 else "B+" if score>=50 else "B" if score>=40 else "C"

    print(f"\n{'='*W}")
    print(f"  #{rank}  {sym}  |  {grade} ({score}/100)  |  Price: {row['price_k']}k  |  ADV50: {row['adv50_B']:.1f}B VND")
    print(f"  Wyckoff: {wyck}  |  Stage2 criteria: {row['stage2']}/5  |  MA aligned: {row['ma_align']}")
    print(f"{'='*W}")

    # Momentum
    print(f"\n  [MOMENTUM]")
    print(f"    r5={fs(row['r5'])}  r10={fs(row['r10'])}  r20={fs(row['r20'])}  r60={fs(row['r60'])}  r120={fs(row['r120'])}  r252={fs(row['r252'])}")
    print(f"    RS vs VNINDEX: 20d={fs(row['rs20'])}  60d={fs(row['rs60'])}  252d={fs(row['rs252'])}")
    mom_flag = "OUTPERFORM" if (pd.notna(row['rs60']) and row['rs60']>0) else "UNDERPERFORM"
    print(f"    => Index relative: {mom_flag}")

    # MA / Stage2
    print(f"\n  [MA / STAGE2]")
    print(f"    Price vs MA50={fs(row['vs_ma50'])}  MA150={fs(row['vs_ma150'])}  MA200={fs(row['vs_ma200'])}")
    print(f"    MA50 slope: {row['ma50_slope']:.4f}/bar  |  Stage2 score: {row['stage2']}/5")
    s2_items = [
        ("P>MA50",  row.get("vs_ma50",  np.nan)>0 if pd.notna(row.get("vs_ma50"))  else False),
        ("P>MA150", row.get("vs_ma150", np.nan)>0 if pd.notna(row.get("vs_ma150")) else False),
        ("P>MA200", row.get("vs_ma200", np.nan)>0 if pd.notna(row.get("vs_ma200")) else False),
        ("MA align",row.get("ma_align", False)),
        ("MA50 up", row.get("ma50_slope",0)>0),
    ]
    s2_str = "  ".join([f"{'[OK]' if v else '[--]'} {k}" for k,v in s2_items])
    print(f"    {s2_str}")

    # 52w
    print(f"\n  [52-WEEK POSITION]")
    print(f"    Distance from 52w HIGH: {fs(row['dist_hi52'])}  |  from 52w LOW: {fs(row['dist_lo52'])}")

    # Oscillators
    rsi_lvl = "Overbought" if (pd.notna(row['rsi14']) and row['rsi14']>70) else "Oversold" if (pd.notna(row['rsi14']) and row['rsi14']<30) else "Neutral"
    print(f"\n  [OSCILLATORS]")
    print(f"    RSI14: {fn(row['rsi14'])} ({rsi_lvl})  |  StochRSI: {fn(row['srsi'])}  |  MACD: {'Bullish cross' if row['macd_bull'] else 'Bearish cross'}")

    # Volume / Money Flow
    vol_trend = "Above avg" if (pd.notna(row['vol_ratio']) and row['vol_ratio']>1) else "Below avg"
    print(f"\n  [VOLUME / MONEY FLOW]")
    print(f"    CMF20: {row['cmf20']:+.3f}  ({'Accumulation' if row['cmf20']>0.05 else 'Distribution' if row['cmf20']<-0.05 else 'Neutral'})")
    print(f"    OBV slope: {row['obv_slp']:+.2f}%/bar  |  Vol10/50: {fn(row['vol_ratio'])}x ({vol_trend})  |  Dist.days: {row['dist_days']}")

    # Volatility / Base
    atr_flag = "CONTRACTING" if (pd.notna(row['atr_ratio']) and row['atr_ratio']<0.85) else "expanding"
    bb_str   = f"{row['bb_pct']:.0f}th pct" if pd.notna(row.get('bb_pct')) else "--"
    print(f"\n  [VOLATILITY / BASE]")
    print(f"    ATR14/ATR50: {fn(row['atr_ratio'])} ({atr_flag})  |  BB width: {fn(row['bb_w'])} ({bb_str})")
    print(f"    Base forming: {row['base_forming']}")

    # FA
    print(f"\n  [FUNDAMENTAL]")
    yr = row.get("latest_year","")
    print(f"    Revenue  : YoY={fs(row.get('rev_yoy'))}  2Y={fs(row.get('rev_2y'))}  QoQ_YoY={fs(row.get('rev_yoy_q'))}  Accel={fs(row.get('rev_accel'))}")
    print(f"    NetProfit: YoY={fs(row.get('ni_yoy'))}  QoQ={fs(row.get('ni_qoq'))}  same-Q_YoY={fs(row.get('ni_yoy_q'))}")
    print(f"    EPS      : {fn(row.get('eps_ttm'))} VND  |  EPS_YoY={fs(row.get('eps_yoy'))}  |  PE={fn(row.get('pe'))}x  (yr {yr})")
    print(f"    ROE={fn(row.get('roe'))}%  ROA={fn(row.get('roa'))}%  Gross_margin={fn(row.get('gross_margin'))}%  D/E={fn(row.get('de_ratio'))}x  CR={fn(row.get('curr_ratio'))}x")

# ── Summary table ─────────────────────────────────────────────────────────────
print("\n\n" + "="*W)
print("  RANKING SUMMARY")
print("="*W)
print(f"  {'#':<3} {'Sym':<5} {'Score':>5} {'Grade':>5}  {'r20':>7} {'r60':>7} {'RS60':>7} {'CMF':>7} {'EPS_yoy':>8} {'ROE':>6} {'PE':>6}  Wyckoff")
print("  " + "-"*(W-2))
for i, (_, r) in enumerate(merged.iterrows(), 1):
    g = "A+" if r['composite']>=70 else "A" if r['composite']>=60 else "B+" if r['composite']>=50 else "B" if r['composite']>=40 else "C"
    print(f"  #{i:<2} {r['symbol']:<5} {r['composite']:>5.1f} {g:>5}  "
          f"{fs(r['r20']):>7} {fs(r['r60']):>7} {fs(r['rs60']):>7} {r['cmf20']:>+7.3f}"
          f" {fs(r.get('eps_yoy')):>8} {fn(r.get('roe')):>5}% {fn(r.get('pe')):>5}x"
          f"  {r['wyckoff']}")

# save
out = ROOT / "data/research/rubber_deep_dive_results.csv"
merged.to_csv(out, index=False, encoding="utf-8-sig")
print(f"\nSaved: {out}")
print("Done.")
