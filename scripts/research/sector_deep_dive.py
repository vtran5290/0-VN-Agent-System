"""
Multi-sector deep-dive: Tech + FA composite
Sectors: BDS (Real Estate), Securities, Banks
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

SECTORS = {
    "BDS": [
        "VHM","VRE","NVL","PDR","DXG","DIG","KDH","CEO","HDC","BCM",
        "NLG","CII","DXS","SCR","TCH","HPX","AGG","SZC","IJC","LDG",
        "TDC","TDH","HDG","HBC","DRH","API","HQC","PTL","DXG","VCG",
    ],
    "Securities": [
        "SSI","VND","HCM","MBS","VCI","SHS","BSI","FTS","CTS","AGR",
        "VIX","APG","ORS","TVB","APS","BMS","PSI","WSS","EVS","IVS",
    ],
    "Banks": [
        "VCB","BID","CTG","MBB","TCB","VPB","ACB","HDB","STB","TPB",
        "LPB","SHB","MSB","OCB","VIB","EIB","SSB","BAB","ABB","NVB",
        "NAB","KLB","PGB","VAB","VBB","BVB","SGB","WBC",
    ],
}

# FA column constants
REV  = "financialvalues_totalrevenue"
PAT  = "financialvalues_profitaftertax"
EPS  = "financialvalues_basiceps"
ROE  = "financialvalues_roe"
ROA  = "financialvalues_roa"
GM   = "financialvalues_grossmargin"
GP   = "financialvalues_grossprofit"
DEBT = "financialvalues_totaldebt"
EQ   = "financialvalues_stockholderequity"
CR   = "financialvalues_currentratio"
NIM  = "financialvalues_nim"    # for banks
NPL  = "financialvalues_nplratio"

# ── helpers ────────────────────────────────────────────────────────────────────
def slope_pct(arr):
    if len(arr) < 2: return 0.0
    x = np.arange(len(arr), dtype=float)
    m = np.polyfit(x, arr, 1)[0]
    return float(m / abs(arr[0]) * 100) if arr[0] != 0 else 0.0

def rsi_val(close, n=14):
    if len(close) < n+2: return 50.0
    delta = np.diff(close[-(n+2):])
    gains = np.where(delta>0, delta, 0.0)
    losses= np.where(delta<0,-delta, 0.0)
    ag = np.mean(gains[-n:]); al = np.mean(losses[-n:])
    return float(100 - 100/(1+ag/al)) if al>0 else 100.0

def macd_sig(close):
    if len(close) < 35: return 0.0, 0.0
    e12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    e26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    m   = e12 - e26
    s   = pd.Series(m).ewm(span=9, adjust=False).mean().values
    return float(m[-1]), float(s[-1])

def stoch_rsi(close, n=14, smooth=3):
    if len(close) < n*2+smooth+5: return np.nan
    r_series = []
    for i in range(smooth+n, 0, -1):
        r_series.append(rsi_val(close[:len(close)-i+1], n))
    if not r_series: return np.nan
    lo, hi = min(r_series), max(r_series)
    if hi == lo: return 50.0
    raw = [(v-lo)/(hi-lo)*100 for v in r_series]
    return float(np.mean(raw[-smooth:]))

def bb_pct_rank(close, n=20, history=252):
    if len(close) < n+history: return np.nan, np.nan
    widths = []
    for i in range(history, 0, -1):
        w = close[-(n+i):-(i)]
        if len(w) < n: continue
        m = np.mean(w); s = np.std(w)
        widths.append(2*s/m*100 if m else 0)
    if not widths: return np.nan, np.nan
    curr_w = close[-n:]
    curr   = 2*np.std(curr_w)/np.mean(curr_w)*100 if np.mean(curr_w) else 0
    pct    = float(np.mean(np.array(widths) <= curr) * 100)
    return round(curr, 2), round(pct, 0)

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
    hl = h - l
    mfv = np.where(hl>0, ((c-l)-(h-c))/hl*v, 0)
    return float(np.sum(mfv)/np.sum(v)) if np.sum(v)>0 else 0.0

def rs_vs_vni(sc, vc, n=60):
    if len(sc)<n or len(vc)<n: return np.nan
    return round(((sc[-1]/sc[-n])-(vc[-1]/vc[-n]))*100, 1)

def safe_pct(new, old):
    return round((new/old-1)*100, 1) if (pd.notna(new) and pd.notna(old) and old!=0) else np.nan

# ── Load data ──────────────────────────────────────────────────────────────────
print("Loading OHLCV...")
df = pd.read_parquet(PANEL)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol","date"])
if df.groupby("symbol")["close"].median().median() < 500:
    for col in ["open","high","low","close"]: df[col] *= 1000
if df["value"].median() < 1e8: df["value"] *= 1000

vni = pd.read_parquet(VNIDX).sort_values("date")
vni_c = vni["close"].values if "close" in vni.columns else vni.iloc[:,1].values

print("Loading FA...")
fa_a = pd.read_parquet(FA_A); fa_a.columns = [c.lower() for c in fa_a.columns]
fa_q = pd.read_parquet(FA_Q); fa_q.columns = [c.lower() for c in fa_q.columns]

# ── FA extraction ──────────────────────────────────────────────────────────────
def get_fa(sym, sector):
    out = {"symbol": sym}
    a = fa_a[(fa_a["symbol"]==sym) & (fa_a["quarter"]==0)].sort_values("year")
    if not a.empty:
        def lv(col):
            if col not in a.columns: return np.nan
            v = a[col].dropna(); return float(v.iloc[-1]) if len(v)>0 else np.nan
        def pv(col, n=1):
            if col not in a.columns: return np.nan
            v = a[col].dropna(); return float(v.iloc[-1-n]) if len(v)>n else np.nan

        out["rev_yoy"]  = safe_pct(lv(REV), pv(REV))
        out["rev_2y"]   = safe_pct(lv(REV), pv(REV,2))
        out["ni_yoy"]   = safe_pct(lv(PAT), pv(PAT))
        out["eps_ttm"]  = lv(EPS)
        out["eps_yoy"]  = safe_pct(lv(EPS), pv(EPS))
        out["roe"]      = round(lv(ROE)*100, 1) if (pd.notna(lv(ROE)) and abs(lv(ROE))<10) else lv(ROE)
        out["roa"]      = round(lv(ROA)*100, 1) if (pd.notna(lv(ROA)) and abs(lv(ROA))<10) else lv(ROA)
        gp_v = lv(GP); rev_v = lv(REV)
        out["gross_margin"] = round(gp_v/rev_v*100,1) if (pd.notna(gp_v) and pd.notna(rev_v) and rev_v>0) else np.nan
        out["de_ratio"] = round(lv(DEBT)/lv(EQ),2) if (pd.notna(lv(DEBT)) and pd.notna(lv(EQ)) and lv(EQ)>0) else np.nan
        out["curr_ratio"]= round(lv(CR),2) if pd.notna(lv(CR)) else np.nan
        out["latest_year"] = int(a["year"].iloc[-1]) if len(a)>0 else np.nan
        # Bank-specific
        out["nim"]      = round(lv(NIM)*100,2) if (pd.notna(lv(NIM)) and abs(lv(NIM))<1) else lv(NIM)
        out["npl"]      = round(lv(NPL)*100,2) if (pd.notna(lv(NPL)) and abs(lv(NPL))<1) else lv(NPL)
        # Book value per share approximation
        eq_v = lv(EQ)
        if pd.notna(eq_v) and pd.notna(lv(EPS)) and lv(EPS)>0:
            # rough shares = PAT / EPS
            pat_v = lv(PAT)
            if pd.notna(pat_v) and pat_v>0 and lv(EPS)>0:
                shares = pat_v / lv(EPS)
                if shares > 0:
                    out["bvps"] = round(eq_v / shares, 0)
        out["latest_year"] = int(a["year"].iloc[-1]) if len(a)>0 else np.nan

    q = fa_q[(fa_q["symbol"]==sym) & (fa_q["quarter"]>0)].sort_values(["year","quarter"])
    if not q.empty:
        if REV in q.columns:
            qr = q[REV].dropna()
            if len(qr)>=5: out["rev_yoy_q"] = safe_pct(float(qr.iloc[-1]), float(qr.iloc[-5]))
            if len(qr)>=4:
                out["rev_accel"] = safe_pct(float(qr.iloc[-2:].sum()), float(qr.iloc[-4:-2].sum()))
        if PAT in q.columns:
            qp = q[PAT].dropna()
            if len(qp)>=2: out["ni_qoq"]   = safe_pct(float(qp.iloc[-1]), float(qp.iloc[-2]))
            if len(qp)>=5: out["ni_yoy_q"] = safe_pct(float(qp.iloc[-1]), float(qp.iloc[-5]))
    return out

# ── Technical per stock ────────────────────────────────────────────────────────
def compute_tech(sym):
    sd = df[df["symbol"]==sym].copy().reset_index(drop=True)
    if len(sd) < 60: return None
    n = len(sd)
    c = sd["close"].values; v = sd["volume"].values; price = c[-1]
    adv50 = sd["value"].iloc[-50:].mean() if n>=50 else sd["value"].mean()

    def ret(p): return round((c[-1]/c[-p]-1)*100,1) if n>p else np.nan

    ma50  = np.mean(c[-50:])  if n>=50  else np.nan
    ma150 = np.mean(c[-150:]) if n>=150 else np.nan
    ma200 = np.mean(c[-200:]) if n>=200 else np.nan
    ma50_sl = slope_pct(c[-50:]) if n>=50 else np.nan

    s2_pm50  = price>ma50  if not np.isnan(ma50)  else False
    s2_pm150 = price>ma150 if not np.isnan(ma150) else False
    s2_pm200 = price>ma200 if not np.isnan(ma200) else False
    s2_align = (not any(np.isnan([ma50,ma150,ma200]))) and ma50>ma150>ma200
    s2_slope = ma50_sl>0 if not np.isnan(ma50_sl) else False
    stage2   = sum([s2_pm50,s2_pm150,s2_pm200,s2_align,s2_slope])

    hi52 = np.max(c[-min(252,n):]); lo52 = np.min(c[-min(252,n):])
    dist_hi = round((price/hi52-1)*100,1)
    dist_lo = round((price/lo52-1)*100,1)

    atr14  = atr_n(sd,14)
    atr50  = atr_n(sd,50) if n>=60 else np.nan
    atr_r  = round(atr14/atr50,2) if (pd.notna(atr14) and pd.notna(atr50) and atr50>0) else np.nan

    bb_w, bb_p = bb_pct_rank(c) if n>=272 else (np.nan,np.nan)

    rsi14 = round(rsi_val(c,14),1)   if n>=20 else np.nan
    srsi  = round(stoch_rsi(c),1)    if n>=60 else np.nan
    mc,ms = macd_sig(c)
    macd_b= mc>ms

    avg_v10 = np.mean(v[-10:]) if n>=10 else np.nan
    avg_v50 = np.mean(v[-50:]) if n>=50 else np.nan
    vol_r   = round(avg_v10/avg_v50,2) if (pd.notna(avg_v50) and avg_v50>0) else np.nan
    cmf20   = round(cmf_val(sd,20),3)
    obv_slp = round(obv_slope(c,v,20),2)

    if n>=25:
        base_v = avg_v50 if pd.notna(avg_v50) else np.mean(v)
        ret_d  = np.diff(c[-26:])/c[-26:-1]
        vol_d  = v[-25:]
        dist_d = int(np.sum((ret_d<-0.002)&(vol_d>base_v)))
    else:
        dist_d = 0

    rs60  = rs_vs_vni(c, vni_c, 60)
    rs20  = rs_vs_vni(c, vni_c, 20)
    rs252 = rs_vs_vni(c, vni_c, min(252,n-1))

    base_forming = pd.notna(atr_r) and atr_r<0.85
    spring = dist_lo<5 and dist_hi<-15 and (vol_r or 0)>1.2

    if not np.isnan(ma200) and price>ma200 and cmf20>0.05 and obv_slp>0 and dist_hi>-10:
        wyckoff = "Phase E (markup)"
    elif not np.isnan(ma50) and price>ma50 and cmf20>0 and obv_slp>0 and base_forming:
        wyckoff = "Phase D (SOS/LPS)"
    elif spring:
        wyckoff = "Phase C (spring?)"
    elif base_forming and -30<dist_hi<-5:
        wyckoff = "Phase B (base)"
    elif dist_hi< -30:
        wyckoff = "Phase A (stop/AR)"
    else:
        wyckoff = "Undefined"

    return {
        "symbol":sym, "price_k":round(price/1000,1), "adv50_B":round(adv50/1e9,2),
        "r5":ret(5),"r10":ret(10),"r20":ret(20),"r60":ret(60),"r120":ret(120),"r252":ret(min(252,n-1)),
        "vs_ma50":round((price/ma50-1)*100,1)  if not np.isnan(ma50)  else np.nan,
        "vs_ma150":round((price/ma150-1)*100,1) if not np.isnan(ma150) else np.nan,
        "vs_ma200":round((price/ma200-1)*100,1) if not np.isnan(ma200) else np.nan,
        "ma_align":s2_align, "ma50_slope":round(ma50_sl,4) if not np.isnan(ma50_sl) else np.nan,
        "stage2":stage2, "dist_hi52":dist_hi, "dist_lo52":dist_lo,
        "rsi14":rsi14,"srsi":srsi,"macd_bull":macd_b,
        "cmf20":cmf20,"obv_slp":obv_slp,"vol_ratio":vol_r,"dist_days":dist_d,
        "atr_ratio":atr_r,"bb_w":bb_w,"bb_pct":bb_p,
        "rs60":rs60,"rs20":rs20,"rs252":rs252,
        "wyckoff":wyckoff,"base_forming":base_forming,
    }

# ── Composite score (Tech 60 + FA 40) ─────────────────────────────────────────
def composite(row, sector):
    t = 0.0
    r20=row.get("r20"); r60=row.get("r60"); r120=row.get("r120")
    t += min(8,max(0,r20/2))   if pd.notna(r20)  else 0
    t += min(7,max(0,r60/4))   if pd.notna(r60)  else 0
    t += min(5,max(0,r120/8))  if pd.notna(r120) else 0
    t += row.get("stage2",0)*2
    rs=row.get("rs60"); t += min(5,max(0,rs/4)) if pd.notna(rs) else 0
    cmf=row.get("cmf20",0)
    t += min(5,max(0,cmf*30))
    t += 3 if row.get("obv_slp",0)>0 else 0
    t += 2 if (pd.notna(row.get("vol_ratio")) and row.get("vol_ratio",0)>1) else 0
    ar=row.get("atr_ratio")
    t += max(0,min(5,(1-ar)*10)) if pd.notna(ar) else 0
    dh=row.get("dist_hi52",0)
    t += max(0,min(5,(30+dh)/6))
    t -= min(5,row.get("dist_days",0)*1.5)

    f = 0.0
    ry=row.get("rev_yoy"); rq=row.get("rev_yoy_q"); ra=row.get("rev_accel")
    f += min(4,max(0,ry/5))  if pd.notna(ry) else 0
    f += min(3,max(0,rq/5))  if pd.notna(rq) else 0
    f += min(3,max(0,ra/10)) if pd.notna(ra) else 0
    ny=row.get("ni_yoy"); nq=row.get("ni_yoy_q")
    f += min(5,max(0,ny/5))  if pd.notna(ny) else 0
    f += min(5,max(0,nq/5))  if pd.notna(nq) else 0
    eg=row.get("eps_yoy")
    f += min(8,max(0,eg/5))  if pd.notna(eg) else 0
    roe=row.get("roe")
    # banks: ROE 15%+ is good; BDS/securi 10%+ good
    roe_max = 20 if sector=="Banks" else 15
    f += min(7,max(0,roe/roe_max*7)) if pd.notna(roe) else 0
    gm=row.get("gross_margin")
    if sector != "Banks":
        f += min(3,max(0,gm/10)) if pd.notna(gm) else 0

    return round(min(100,max(0,t+f)),1)

# ── Print helpers ──────────────────────────────────────────────────────────────
from tabulate import tabulate as _tab
W = 92
def fs(v, sfx="%"): return f"{v:+.1f}{sfx}" if pd.notna(v) else "--"
def fn(v):          return f"{v:.1f}"        if pd.notna(v) else "--"
def grade(s):       return "A+" if s>=70 else "A" if s>=60 else "B+" if s>=50 else "B" if s>=40 else "C"

def make_ranking_rows(merged, sector):
    rows = []
    for i, (_, r) in enumerate(merged.iterrows(), 1):
        g    = grade(r['composite'])
        pe_s = f"{r['pe']:.1f}x"   if pd.notna(r.get('pe'))  else "--"
        pb_s = f"{r['pb']:.2f}x"   if pd.notna(r.get('pb'))  else "--"
        roe_s= f"{r['roe']:.1f}%"  if pd.notna(r.get('roe')) else "--"
        eps_g= fs(r.get('eps_yoy'))
        nim_s= f"{r['nim']:.2f}%"  if pd.notna(r.get('nim')) else "--"
        rows.append([
            f"#{i}",
            r['symbol'],
            f"{r['composite']:.1f}",
            g,
            fs(r['r20']),
            fs(r['r60']),
            fs(r.get('rs60')),
            f"{r['cmf20']:+.3f}",
            eps_g,
            roe_s,
            pe_s,
            r['wyckoff'],
        ])
    headers = ["#","Ticker","Score","Gr","r20(1M)","r60(3M)","RS60(vni)","CMF20","EPS_g","ROE","P/E","Wyckoff"]
    return rows, headers

def print_ranking_table(merged, sector, title):
    rows, headers = make_ranking_rows(merged, sector)
    print(f"\n{title}")
    print(_tab(rows, headers=headers, tablefmt="simple", stralign="right", numalign="right"))

def make_top_rows(df_combined):
    rows = []
    for i, (_, r) in enumerate(df_combined.iterrows(), 1):
        g    = grade(r['composite'])
        pe_s = f"{r['pe']:.1f}x"   if pd.notna(r.get('pe'))  else "--"
        roe_s= f"{r['roe']:.1f}%"  if pd.notna(r.get('roe')) else "--"
        rows.append([
            f"#{i}",
            r['symbol'],
            r['sector'],
            f"{r['composite']:.1f}",
            g,
            fs(r['r20']),
            fs(r['r60']),
            fs(r.get('rs60')),
            f"{r['cmf20']:+.3f}",
            roe_s,
            pe_s,
        ])
    headers = ["#","Ticker","Sector","Score","Gr","r20(1M)","r60(3M)","RS60(vni)","CMF20","ROE","P/E"]
    return rows, headers

# ── Main loop ─────────────────────────────────────────────────────────────────
all_results = {}

for sector, stocks in SECTORS.items():
    print(f"\n{'='*W}")
    print(f"  Processing {sector} ({len(stocks)} stocks)...")
    print(f"{'='*W}")

    # deduplicate
    stocks = list(dict.fromkeys(stocks))

    tech_rows = []
    for sym in stocks:
        t = compute_tech(sym)
        if t: tech_rows.append(t)
        else: print(f"  {sym}: skipped (insufficient data)")

    if not tech_rows:
        print(f"  No data for {sector}"); continue

    tech_df = pd.DataFrame(tech_rows)
    fa_rows = [get_fa(sym, sector) for sym in tech_df["symbol"].tolist()]
    fa_df   = pd.DataFrame(fa_rows)
    merged  = tech_df.merge(fa_df, on="symbol", how="left")

    # PE
    def pe(row):
        eps=row.get("eps_ttm")
        if pd.notna(eps) and eps>0: return round(row["price_k"]*1000/eps,1)
        return np.nan
    merged["pe"] = merged.apply(pe, axis=1)

    # PB (price / BVPS)
    def pb(row):
        bv=row.get("bvps")
        if pd.notna(bv) and bv>0: return round(row["price_k"]*1000/bv,2)
        return np.nan
    merged["pb"] = merged.apply(pb, axis=1)

    merged["composite"] = merged.apply(lambda r: composite(r, sector), axis=1)
    merged = merged.sort_values("composite", ascending=False).reset_index(drop=True)
    all_results[sector] = merged

    # ── Per-stock detail ──────────────────────────────────────────────────────
    print(f"\n\n{'#'*W}")
    print(f"  SECTOR: {sector.upper()}")
    print(f"{'#'*W}")

    for _, row in merged.iterrows():
        sym   = row["symbol"]
        score = row["composite"]
        g     = grade(score)
        wyck  = row["wyckoff"]

        print(f"\n{'='*W}")
        print(f"  {sym}  |  {g} ({score}/100)  |  {row['price_k']}k  |  ADV50: {row['adv50_B']:.1f}B  |  {wyck}")
        print(f"  Stage2: {row['stage2']}/5  |  MA aligned: {row['ma_align']}  |  Dist.days: {row['dist_days']}")
        print(f"{'─'*W}")

        # Returns + RS
        print(f"  Momentum : r5={fs(row['r5'])}  r20={fs(row['r20'])}  r60={fs(row['r60'])}  r120={fs(row['r120'])}  r252={fs(row['r252'])}")
        print(f"  RS/Index : 20d={fs(row['rs20'])}  60d={fs(row['rs60'])}  252d={fs(row['rs252'])}")

        # MA
        ma_items = []
        for lab, col in [("P>MA50","vs_ma50"),("P>MA150","vs_ma150"),("P>MA200","vs_ma200")]:
            v = row.get(col); ok = pd.notna(v) and v>0
            ma_items.append(f"{'[v]' if ok else '[x]'}{lab}={fs(v)}")
        align_s = "[v]MA-align" if row['ma_align'] else "[x]MA-align"
        slope_s = f"[v]MA50-up" if row.get('ma50_slope',0)>0 else f"[x]MA50-dn"
        print(f"  MA       : {' '.join(ma_items)}  {align_s}  {slope_s}")
        print(f"  52w      : hi={fs(row['dist_hi52'])}  lo={fs(row['dist_lo52'])}")

        # Oscillators
        rsi_lbl = "OB" if (pd.notna(row['rsi14']) and row['rsi14']>70) else "OS" if (pd.notna(row['rsi14']) and row['rsi14']<30) else "OK"
        print(f"  Osc      : RSI14={fn(row['rsi14'])}({rsi_lbl})  StochRSI={fn(row['srsi'])}  MACD={'Bull' if row['macd_bull'] else 'Bear'}")

        # Vol/MF
        cmf_lbl = "Accum" if row['cmf20']>0.05 else "Distr" if row['cmf20']<-0.05 else "Neut"
        vr_s = f"{row['vol_ratio']:.2f}x" if pd.notna(row.get('vol_ratio')) else "--"
        print(f"  Vol/MF   : CMF20={row['cmf20']:+.3f}({cmf_lbl})  OBV={row['obv_slp']:+.2f}%/bar  vol10/50={vr_s}")

        # Base
        atr_lbl = "CONTR" if (pd.notna(row['atr_ratio']) and row['atr_ratio']<0.85) else "expnd"
        bb_s = f"{row['bb_pct']:.0f}th-pct" if pd.notna(row.get('bb_pct')) else "--"
        print(f"  Base     : ATR={fn(row['atr_ratio'])}({atr_lbl})  BB={fn(row['bb_w'])}({bb_s})  base={row['base_forming']}")

        # FA
        yr = row.get("latest_year","")
        print(f"  Rev      : YoY={fs(row.get('rev_yoy'))}  2Y={fs(row.get('rev_2y'))}  Q_YoY={fs(row.get('rev_yoy_q'))}  accel={fs(row.get('rev_accel'))}")
        print(f"  NI       : YoY={fs(row.get('ni_yoy'))}  QoQ={fs(row.get('ni_qoq'))}  Q_YoY={fs(row.get('ni_yoy_q'))}")

        pe_s  = fn(row.get('pe'))+"x" if pd.notna(row.get('pe'))  else "--"
        pb_s  = fn(row.get('pb'))+"x" if pd.notna(row.get('pb'))  else "--"
        eps_s = f"{row.get('eps_ttm'):.0f}" if pd.notna(row.get('eps_ttm')) else "--"
        print(f"  EPS/Val  : EPS={eps_s}  EPS_YoY={fs(row.get('eps_yoy'))}  PE={pe_s}  PB={pb_s}  (yr {yr})")

        if sector == "Banks":
            nim_s = fn(row.get('nim'))+"%" if pd.notna(row.get('nim')) else "--"
            npl_s = fn(row.get('npl'))+"%" if pd.notna(row.get('npl')) else "--"
            print(f"  Bank KPIs: ROE={fn(row.get('roe'))}%  NIM={nim_s}  NPL={npl_s}  D/E={fn(row.get('de_ratio'))}x")
        else:
            print(f"  Quality  : ROE={fn(row.get('roe'))}%  GM={fn(row.get('gross_margin'))}%  D/E={fn(row.get('de_ratio'))}x  CR={fn(row.get('curr_ratio'))}x")

# ── Cross-sector summary tables ───────────────────────────────────────────────
for sector, merged in all_results.items():
    print_ranking_table(merged, sector, f"\n{'='*W}\n  RANKING TABLE: {sector.upper()}\n{'='*W}")

# ── Top 15 overall cross-sector ───────────────────────────────────────────────
combined = pd.concat(list(all_results.values()), keys=list(all_results.keys()))
combined = combined.reset_index(level=0).rename(columns={"level_0":"sector"})
top15 = combined.sort_values("composite", ascending=False).head(15)

rows, headers = make_top_rows(top15)
print(f"\n\n{'='*W}\n  TOP 15 ACROSS ALL THREE SECTORS  (data: 2026-05-13)\n{'='*W}")
print(_tab(rows, headers=headers, tablefmt="simple", stralign="right", numalign="right"))

# ── Save ──────────────────────────────────────────────────────────────────────
out = ROOT / "data/research/bds8633_stock_prob_20260508.csv"
combined.to_csv(out, index=False, encoding="utf-8-sig")
print(f"\nSaved: {out}")
print("Done.")
