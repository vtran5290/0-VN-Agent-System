"""
Wyckoff Phase D/E Scanner — Vietnam Equities
As-of: 2026-05-12  |  Data: data/fireant_ssot/ta_ohlcv_panel.parquet
"""
import warnings; warnings.filterwarnings("ignore")
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd
from pathlib import Path

BASE       = Path(r"D:\V\0. VN Agent System")
OHLCV_PATH = BASE / "data/fireant_ssot/ta_ohlcv_panel.parquet"
OUT_CSV    = BASE / "artifacts/composite_vn_screen/wyckoff_phase_de_20260512.csv"
ADV50_MIN  = 2_000_000_000
MIN_BARS   = 250

# ─────────────────────────────────────────────────────────────────────────────
# LOAD + UNIT CHECK
# ─────────────────────────────────────────────────────────────────────────────
def load_panel():
    df = pd.read_parquet(OHLCV_PATH)
    df.columns = df.columns.str.lower().str.strip()
    if "symbol" in df.columns:
        df = df.rename(columns={"symbol": "ticker"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    med = df["close"].median()
    if 1 <= med <= 500:
        price_unit = "thousand_VND"
        for col in ["open","high","low","close"]:
            df[f"{col}_v"] = df[col] * 1000
    else:
        price_unit = "VND"
        for col in ["open","high","low","close"]:
            df[f"{col}_v"] = df[col]

    if "value" in df.columns and df["value"].notna().mean() > 0.5:
        samp = df[(df["volume"]>0)&(df["close_v"]>0)].copy()
        samp["comp"] = samp["close_v"] * samp["volume"]
        ratio = (samp["value"] / samp["comp"]).median()
        if 0.5 < ratio < 2.0:
            df["tv"] = df["value"]
            vol_unit = f"shares; value=VND (ratio={ratio:.2f})"
        elif 0.005 < ratio < 0.05:
            df["tv"] = df["value"] * 1000
            vol_unit = f"shares; value=kVND×1000 (ratio={ratio:.3f})"
        else:
            df["tv"] = df["close_v"] * df["volume"]
            vol_unit = f"computed (ratio={ratio:.3f})"
    else:
        df["tv"] = df["close_v"] * df["volume"]
        vol_unit = "computed (no value col)"

    return df, price_unit, vol_unit

def filter_universe(df):
    as_of = df["date"].max()
    cnt   = df.groupby("ticker")["date"].count()
    ok    = cnt[cnt >= MIN_BARS].index
    df    = df[df["ticker"].isin(ok)].copy()
    after_bars = df["ticker"].nunique()

    def adv50(g):
        last = g.nlargest(50,"date")["tv"].replace(0,np.nan).dropna()
        return last.mean() if len(last) >= 45 else np.nan

    adv = df.groupby("ticker").apply(adv50)
    ok2 = adv[adv >= ADV50_MIN].index
    df  = df[df["ticker"].isin(ok2)].copy()
    return df, after_bars, df["ticker"].nunique(), adv, as_of

# ─────────────────────────────────────────────────────────────────────────────
# DAILY INDICATORS
# ─────────────────────────────────────────────────────────────────────────────
def daily_ind(g):
    g = g.sort_values("date").copy()
    c, h, l, v = g["close_v"], g["high_v"], g["low_v"], g["volume"]
    for n,col in [(20,"sma20"),(50,"sma50"),(150,"sma150"),(200,"sma200")]:
        g[col] = c.rolling(n).mean()
    for sp,col in [(10,"ema10"),(20,"ema20"),(50,"ema50")]:
        g[col] = c.ewm(span=sp,adjust=False).mean()
    g["sma200_20d"] = g["sma200"].shift(20)
    pc  = c.shift(1)
    tr  = pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    g["atr14"]   = tr.rolling(14).mean()
    g["atr_pct"] = g["atr14"] / c.replace(0,np.nan)
    std20 = c.rolling(20).std(); sma20 = c.rolling(20).mean()
    g["bb_width"] = (4*std20) / sma20.replace(0,np.nan)
    obv = (np.sign(c.diff().fillna(0))*v).cumsum()
    g["obv"]       = obv
    g["obv_ma20"]  = obv.rolling(20).mean()
    g["obv_52wh"]  = obv.rolling(252).max()
    hl  = (h-l).replace(0,np.nan)
    mfm = ((c-l)-(h-c))/hl; mfv = mfm*v
    vs  = v.rolling(20).sum().replace(0,np.nan)
    g["cmf20"] = mfv.rolling(20).sum()/vs
    d    = c.diff(); gain=d.clip(lower=0).rolling(14).mean()
    loss = (-d).clip(lower=0).rolling(14).mean()
    rs   = gain/loss.replace(0,np.nan)
    g["rsi14"] = 100-100/(1+rs)
    rmin=g["rsi14"].rolling(14).min(); rmax=g["rsi14"].rolling(14).max()
    sk = (g["rsi14"]-rmin)/(rmax-rmin).replace(0,np.nan)
    g["stochrsi_k"] = sk.rolling(3).mean()*100
    g["stochrsi_d"] = g["stochrsi_k"].rolling(3).mean()
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    ml=e12-e26; sig=ml.ewm(span=9,adjust=False).mean()
    g["macd"]=ml; g["macd_sig"]=sig; g["macd_hist"]=ml-sig
    ret=c.pct_change()
    dd=(((ret<=-0.002)&(v>v.shift(1))).astype(int))
    g["dist_days_25d"] = dd.rolling(25).sum()
    g["high_52w"] = h.rolling(252).max()
    g["low_52w"]  = l.rolling(252).min()
    return g

# ─────────────────────────────────────────────────────────────────────────────
# WEEKLY RESAMPLE + INDICATORS
# ─────────────────────────────────────────────────────────────────────────────
def to_weekly(g):
    g2 = g.set_index("date")
    w  = g2.resample("W").agg(
        open_v=("open_v","first"), high_v=("high_v","max"),
        low_v=("low_v","min"),     close_v=("close_v","last"),
        volume=("volume","sum"),   tv=("tv","sum"),
    ).dropna(subset=["close_v"]).reset_index()

    c,h,l,v = w["close_v"],w["high_v"],w["low_v"],w["volume"]
    for sp,col in [(10,"w_e10"),(20,"w_e20"),(50,"w_e50")]:
        w[col] = c.ewm(span=sp,adjust=False).mean()
    for n,col in [(30,"w_s30"),(40,"w_s40")]:
        w[col] = c.rolling(n).mean()
    pc=c.shift(1); tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    w["w_atr14"]  = tr.rolling(14).mean()
    w["w_atr_p"]  = w["w_atr14"]/c.replace(0,np.nan)
    std20=c.rolling(20).std(); sma20=c.rolling(20).mean()
    w["w_bb_w"] = (4*std20)/sma20.replace(0,np.nan)
    obv=(np.sign(c.diff().fillna(0))*v).cumsum()
    w["w_obv"]    = obv
    w["w_obv_m10"]= obv.rolling(10).mean()
    w["w_obv_m20"]= obv.rolling(20).mean()
    w["w_obv_52h"]= obv.rolling(52).max()
    hl=(h-l).replace(0,np.nan); mfm=((c-l)-(h-c))/hl; mfv=mfm*v
    vs=v.rolling(20).sum().replace(0,np.nan)
    w["w_cmf20"] = mfv.rolling(20).sum()/vs
    d=c.diff(); gain=d.clip(lower=0).rolling(14).mean()
    loss=(-d).clip(lower=0).rolling(14).mean(); rs=gain/loss.replace(0,np.nan)
    w["w_rsi14"] = 100-100/(1+rs)
    rmin=w["w_rsi14"].rolling(14).min(); rmax=w["w_rsi14"].rolling(14).max()
    sk=(w["w_rsi14"]-rmin)/(rmax-rmin).replace(0,np.nan)
    w["w_srsi_k"] = sk.rolling(3).mean()*100
    w["w_srsi_d"] = w["w_srsi_k"].rolling(3).mean()
    w["close_pos"]= ((c-l)/(h-l).replace(0,np.nan)).clip(0,1)
    w["vol_a20"]  = v.rolling(20).mean()
    w["tv_a20"]   = w["tv"].rolling(20).mean()
    w["w_ret"]    = c.pct_change()
    return w

# ─────────────────────────────────────────────────────────────────────────────
# RANGE DETECTION (12-80 weeks)
# ─────────────────────────────────────────────────────────────────────────────
def detect_range(wdf):
    if len(wdf) < 15:
        return None
    c,h,l,v = wdf["close_v"].values, wdf["high_v"].values, wdf["low_v"].values, wdf["volume"].values
    n = len(wdf)
    best=None; best_sc=-1
    for win in range(12, min(81,n)):
        sh=h[-win:]; sl=l[-win:]; sc=c[-win:]
        rh=np.nanpercentile(sh,88); rl=np.nanpercentile(sl,12)
        if rh<=rl: continue
        depth=(rh-rl)/rh
        if not (0.10<=depth<=0.50): continue
        tol=0.045
        rt=int(np.sum(sh>=rh*(1-tol))); st=int(np.sum(sl<=rl*(1+tol)))
        if rt<2 or st<2: continue
        inside=np.mean((sc>=rl)&(sc<=rh))
        if inside<0.55: continue
        sc2=(rt+st)*inside*(1-depth)
        if sc2>best_sc:
            best_sc=sc2; curr=c[-1]
            pos=np.clip((curr-rl)/(rh-rl),0,1) if rh>rl else 0.5
            best=dict(range_high=rh,range_low=rl,range_mid=(rh+rl)/2,
                      range_depth=depth,range_weeks=win,
                      sup_tests=st,res_tests=rt,curr_pos=float(pos),
                      seg_start=str(wdf.iloc[-win]["date"])[:10])
    return best

def prior_context(wdf, ri):
    if ri is None or len(wdf)<20: return "Unknown"
    c=wdf["close_v"].values; win=ri["range_weeks"]; rl=ri["range_low"]
    before=c[:-win] if len(c)>win else c
    if len(before)<8: return "Unknown"
    max_b=np.nanmax(before); range_start=c[-win] if len(c)>=win else c[0]
    dd=(max_b-range_start)/max_b if max_b>0 else 0
    if len(before)>=26:
        pl=np.nanmin(before[-52:]) if len(before)>=52 else np.nanmin(before)
        gain=(range_start-pl)/pl if pl>0 else 0
    else:
        gain=0
    if dd>0.35: return "Accumulation"
    if gain>0.40 and dd<0.50: return "Re-accumulation"
    if dd>0.20: return "Accumulation"
    return "Re-accumulation"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE D DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def detect_phase_d(wdf, ri):
    ev=dict(spring=False,spring_week=None,spring_low=np.nan,
            sos=False,sos_week=None,lps=False,lps_week=None,
            pos_upper=False,obv_conf=0,supply_abs=0,rejection=None)
    if ri is None or len(wdf)<20:
        ev["rejection"]="no_range"; return False,None,ev

    c=wdf["close_v"].values; h=wdf["high_v"].values
    l=wdf["low_v"].values;   v=wdf["volume"].values
    obv=wdf["w_obv"].values; obvm=wdf["w_obv_m20"].values
    cmf=wdf["w_cmf20"].values; cp=wdf["close_pos"].values
    e10=wdf["w_e10"].values; e20=wdf["w_e20"].values; e50=wdf["w_e50"].values

    rh=ri["range_high"]; rl=ri["range_low"]; rm=ri["range_mid"]
    win=ri["range_weeks"]; curr=c[-1]; avg20=np.nanmean(v[-20:]) if len(v)>=20 else np.nanmean(v)

    # Reject: OBV lower lows
    if len(obv)>=20:
        o=obv[-20:]; o_c=o[~np.isnan(o)]
        if len(o_c)>=10 and o_c[-1]<o_c[0]*0.80 and o_c[-1]<np.nanmax(o_c[:5])*0.80:
            ev["rejection"]="OBV_lower_lows"; return False,None,ev

    # Reject: declining W_EMA50 with price below
    if len(e50)>=10 and pd.notna(e50[-1]) and pd.notna(e50[-10]):
        if curr<e50[-1]*0.98 and e50[-1]<e50[-10]:
            ev["rejection"]="below_declining_ema50"; return False,None,ev

    # Spring detection
    search_s=max(0,len(c)-win-5)
    spring_idx=None; best_sp=0
    for i in range(search_s,max(0,len(c)-2)):
        if l[i]<rl*0.99:
            cl_ok=(cp[i]>=0.40 if i<len(cp) else False)
            fut=l[i+1:min(i+9,len(l))]
            no_ret=(len(fut)==0 or np.nanmin(fut)>=l[i]*0.99)
            sc=cl_ok*3+no_ret*2+(v[i]>=avg20*0.8)*1
            if sc>best_sp: best_sp=sc; spring_idx=i
    if spring_idx is not None and best_sp>=3:
        # Spring low not broken afterward?
        post=l[spring_idx+1:]
        if len(post)>0 and np.nanmin(post)<l[spring_idx]*0.99:
            ev["rejection"]="spring_low_broken"; return False,None,ev
        ev["spring"]=True; ev["spring_week"]=str(wdf.iloc[spring_idx]["date"])[:10]
        ev["spring_low"]=float(l[spring_idx])

    # SOS detection
    sos_idx=None
    start_sos=(spring_idx+1) if spring_idx is not None else max(0,len(c)-win)
    for i in range(start_sos,len(c)):
        if i==0: continue
        wret=(c[i]/c[i-1]-1) if c[i-1]>0 else 0
        cp_i=cp[i] if i<len(cp) else 0.5
        if wret>0.05 and cp_i>=0.65 and v[i]>=avg20*1.2:
            ev["sos"]=True; ev["sos_week"]=str(wdf.iloc[i]["date"])[:10]; sos_idx=i; break
        elif wret>0.03 and cp_i>=0.55 and not ev["sos"]:
            ev["sos"]=True; ev["sos_week"]=str(wdf.iloc[i]["date"])[:10]; sos_idx=i
    # Fallback SOS: price in upper range above EMAs
    if not ev["sos"]:
        for i in range(max(0,len(c)-win),len(c)):
            if c[i]>rm+(rh-rm)*0.33 and pd.notna(e10[i]) and c[i]>e10[i] and pd.notna(e20[i]) and c[i]>e20[i]:
                ev["sos"]=True; ev["sos_week"]=str(wdf.iloc[i]["date"])[:10]
                if sos_idx is None: sos_idx=i
                break

    # LPS detection
    if sos_idx is not None and sos_idx<len(c)-2:
        sh=h[sos_idx]
        for i in range(sos_idx+1,len(c)):
            pull=(c[i]/sh-1) if sh>0 else -1
            if -0.15<pull<-0.01 and v[i]<v[sos_idx]*0.85:
                ev["lps"]=True; ev["lps_week"]=str(wdf.iloc[i]["date"])[:10]; break
            elif -0.20<pull<0 and v[i]<avg20*0.90 and not ev["lps"]:
                ev["lps"]=True; ev["lps_week"]=str(wdf.iloc[i]["date"])[:10]

    ev["pos_upper"]=(curr>=rm)

    # OBV confirmation score
    oc=0
    if len(obv)>0 and len(obvm)>0 and pd.notna(obv[-1]) and pd.notna(obvm[-1]):
        if obv[-1]>obvm[-1]: oc+=1
    if len(obvm)>=10 and pd.notna(obvm[-1]) and pd.notna(obvm[-10]) and obvm[-1]>obvm[-10]: oc+=1
    if "w_obv_52h" in wdf.columns:
        oh=wdf["w_obv_52h"].iloc[-1]
        if pd.notna(oh) and pd.notna(obv[-1]) and obv[-1]>=oh*0.95: oc+=1
    if len(c)>=21:
        up=np.diff(c[-21:])>0; dn=np.diff(c[-21:])<=0
        vs=v[-20:]
        if up.sum()>0 and dn.sum()>0:
            if np.nanmean(vs[up])>np.nanmean(vs[dn]): oc+=1
    if ev["spring"] and spring_idx is not None and spring_idx>0:
        if pd.notna(obv[spring_idx]) and pd.notna(obv[spring_idx-1]) and obv[spring_idx]>=obv[spring_idx-1]*0.85: oc+=1
    ev["obv_conf"]=oc

    # Supply absorption score
    ab=0
    atr_v=wdf["w_atr_p"].values[-20:] if len(wdf)>=20 else wdf["w_atr_p"].values
    atr_v=atr_v[~np.isnan(atr_v)]
    if len(atr_v)>=10:
        if np.nanmean(atr_v[-5:])<np.nanmean(atr_v[:5])*0.85: ab+=1
    bb_v=wdf["w_bb_w"].values[-20:] if len(wdf)>=20 else wdf["w_bb_w"].values
    bb_v=bb_v[~np.isnan(bb_v)]
    if len(bb_v)>=10 and bb_v[-1]<np.nanmean(bb_v)*0.85: ab+=1
    cmf_c=cmf[~np.isnan(cmf)]
    if len(cmf_c)>=8:
        if np.nanmean(cmf_c[-4:])>np.nanmean(cmf_c[-8:-4]) or np.nanmean(cmf_c[-4:])>0: ab+=1
    if len(c)>=20:
        fh=c[-20:-10]; sh2=c[-10:]
        if len(fh)>0 and len(sh2)>0 and np.nanmin(sh2)>np.nanmin(fh): ab+=1
    if len(c)>=11:
        dn2=np.diff(c[-11:])<0; up2=np.diff(c[-11:])>0; vs2=v[-10:]
        dv=vs2[dn2]; uv=vs2[up2]
        if len(dv)>0 and len(uv)>0 and np.nanmean(dv)<np.nanmean(uv): ab+=1
    ev["supply_abs"]=ab

    # Reject: CMF deeply negative + worsening
    cmf_cur=cmf[-1] if len(cmf)>0 and pd.notna(cmf[-1]) else 0
    if len(cmf_c)>=8 and cmf_cur<-0.15 and np.nanmean(cmf_c[-4:])<np.nanmean(cmf_c[-8:-4]):
        ev["rejection"]="CMF_deeply_neg"; return False,None,ev
    # Reject: lower third with no SOS
    if ri["curr_pos"]<0.33 and not ev["sos"]:
        ev["rejection"]="lower_third_no_sos"; return False,None,ev

    # Qualify
    ok=((ev["spring"] or ev["sos"]) and
        (ev["pos_upper"] or (ev["spring"] and ev["sos"])) and
        ev["obv_conf"]>=1 and ev["supply_abs"]>=1)
    if not ok:
        ev["rejection"]="insufficient_evidence"; return False,None,ev

    # Sub-classify
    near_rh=(curr>=rh*0.95)
    if near_rh and ev["sos"] and ev["lps"]: sub="Phase_D_Late"
    elif ev["sos"] and ev["lps"] and ev["pos_upper"]: sub="Phase_D_Late"
    elif ev["spring"] and ev["sos"]: sub="Phase_D_Early"
    elif ev["sos"] and ev["pos_upper"]: sub="Phase_D_Early"
    else: sub="Phase_D_Early"

    return True, sub, ev

# ─────────────────────────────────────────────────────────────────────────────
# PHASE E DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def detect_phase_e(wdf, ri, ld):
    bo=dict(breakout=False,breakout_week=None,bvr=np.nan,
            retest=False,retest_week=None,two_above=False,
            rejection=None,ext_piv=np.nan,ext_sma50=np.nan,ext_we10=np.nan)
    if ri is None or len(wdf)<15:
        bo["rejection"]="no_range"; return False,None,bo

    c=wdf["close_v"].values; h=wdf["high_v"].values
    l=wdf["low_v"].values;   v=wdf["volume"].values
    obv=wdf["w_obv"].values; e10=wdf["w_e10"].values; e20=wdf["w_e20"].values
    cmf=wdf["w_cmf20"].values

    rh=ri["range_high"]; rl=ri["range_low"]; curr=c[-1]
    avg20=np.nanmean(v[-20:]) if len(v)>=20 else np.nanmean(v)

    # Find breakout (last 20 weeks)
    bo_idx=None
    for i in range(max(0,len(c)-20),len(c)):
        if c[i]>rh*1.01:
            bvr=v[i]/avg20 if avg20>0 else 1
            post=c[i+1:] if i<len(c)-1 else np.array([])
            fell=(len(post)>0 and np.nanmin(post)<rl)
            if not fell:
                bo["breakout"]=True; bo["breakout_week"]=str(wdf.iloc[i]["date"])[:10]
                bo["bvr"]=float(bvr); bo_idx=i; break

    if not bo["breakout"]:
        bo["rejection"]="no_breakout"; return False,None,bo

    # Reject weak breakout that fell back
    if bo["bvr"]<0.7 and bo_idx is not None:
        post=c[bo_idx+1:] if bo_idx<len(c)-1 else np.array([])
        if len(post)>0 and np.nanmin(post)<rh*0.97:
            bo["rejection"]="weak_vol_fell_back"; return False,None,bo

    # Two closes above
    if bo_idx is not None and bo_idx<len(c)-1 and c[bo_idx+1]>rh*1.01:
        bo["two_above"]=True

    # Trend confirmation
    if not (pd.notna(e10[-1]) and curr>e10[-1] and pd.notna(e20[-1]) and curr>e20[-1]):
        bo["rejection"]="below_ema_after_bo"; return False,None,bo

    # OBV divergence: price up but OBV down after breakout
    if bo_idx is not None and len(obv)>bo_idx:
        if pd.notna(obv[bo_idx]) and pd.notna(obv[-1]) and curr>c[bo_idx] and obv[-1]<obv[bo_idx]*0.90:
            bo["rejection"]="obv_negative_divergence"; return False,None,bo

    # Distribution days
    dd=ld.get("dist_days_25d",0) or 0
    if dd>=5:
        bo["rejection"]="excessive_dist_days"; return False,None,bo

    # Retest
    if bo_idx is not None and bo_idx<len(c)-2:
        for j in range(bo_idx+1,len(c)):
            if l[j]<=rh*1.03 and c[j]>=rh*0.97 and v[j]<avg20:
                bo["retest"]=True; bo["retest_week"]=str(wdf.iloc[j]["date"])[:10]; break

    # Extensions
    bo["ext_piv"]=float(curr/rh-1)
    sma50=ld.get("sma50",np.nan)
    if pd.notna(sma50) and sma50>0: bo["ext_sma50"]=float(curr/sma50-1)
    if pd.notna(e10[-1]) and e10[-1]>0: bo["ext_we10"]=float(curr/e10[-1]-1)

    too_ext=(bo["ext_piv"]>0.10 or
             (pd.notna(bo["ext_sma50"]) and bo["ext_sma50"]>0.20) or
             (pd.notna(bo["ext_we10"]) and bo["ext_we10"]>0.12))

    if too_ext: sub="Phase_E_Extended"
    elif bo["retest"]: sub="Phase_E_Retest_Confirmed"
    else: sub="Phase_E_Fresh_Breakout"

    return True, sub, bo

# ─────────────────────────────────────────────────────────────────────────────
# 100-PT SCORING
# ─────────────────────────────────────────────────────────────────────────────
def score100(wdf, ri, ctx, ev, bo, ld):
    if ri is None: return 0, {}
    c=wdf["close_v"].values; h=wdf["high_v"].values
    l=wdf["low_v"].values;   v=wdf["volume"].values
    obv=wdf["w_obv"].values; obvm=wdf["w_obv_m20"].values
    cmf=wdf["w_cmf20"].values; e10=wdf["w_e10"].values; e20=wdf["w_e20"].values
    curr=c[-1]; rh=ri["range_high"]; rl=ri["range_low"]; rm=ri["range_mid"]
    avg20=np.nanmean(v[-20:]) if len(v)>=20 else np.nanmean(v)
    s={}; total=0

    # 1. Range Quality (15)
    rq=0; win=ri["range_weeks"]
    if win>=24: rq+=4
    elif win>=16: rq+=3
    elif win>=12: rq+=2
    d=ri["range_depth"]
    if 0.10<=d<=0.25: rq+=3
    elif d<=0.35: rq+=2
    elif d<=0.45: rq+=1
    tests=ri["sup_tests"]+ri["res_tests"]
    if tests>=8: rq+=3
    elif tests>=5: rq+=2
    elif tests>=4: rq+=1
    atr_v=wdf["w_atr_p"].values[-20:]; atr_v=atr_v[~np.isnan(atr_v)]
    if len(atr_v)>=10:
        ar=np.nanmean(atr_v[-5:])/max(np.nanmean(atr_v[:5]),1e-9)
        if ar<0.70: rq+=3
        elif ar<0.85: rq+=2
        elif ar<1.0: rq+=1
    if ctx=="Re-accumulation": rq+=2
    elif ctx=="Accumulation": rq+=1
    s["rq"]=min(rq,15); total+=s["rq"]

    # 2. Spring/Shakeout (15)
    sq=0
    if ev.get("spring"):
        sq+=5+3+2+(2 if ev.get("pos_upper") else 0)+3
    elif ev.get("obv_conf",0)>=2: sq+=3
    s["sq"]=min(sq,15); total+=s["sq"]

    # 3. SOS/Demand (15)
    sosd=0
    if ev.get("sos"):
        sosd+=4+3+3
        if pd.notna(e10[-1]) and curr>e10[-1]: sosd+=1
        if pd.notna(e20[-1]) and curr>e20[-1]: sosd+=1
        if ev.get("supply_abs",0)>=2: sosd+=3
    s["sosd"]=min(sosd,15); total+=s["sosd"]

    # 4. LPS/Pullback (15)
    lq=0
    if ev.get("lps"):
        lq+=4+4+(4 if curr>=rm else 2)
        if len(atr_v)>=10 and ar<0.85: lq+=2
        lq+=1
    elif ev.get("supply_abs",0)>=3: lq+=5
    s["lq"]=min(lq,15); total+=s["lq"]

    # 5. OBV/CMF (15)
    mf=0
    if len(obv)>0 and len(obvm)>0 and pd.notna(obv[-1]) and pd.notna(obvm[-1]):
        if obv[-1]>obvm[-1]: mf+=3
    if len(obvm)>=10 and pd.notna(obvm[-1]) and pd.notna(obvm[-10]) and obvm[-1]>obvm[-10]: mf+=3
    if "w_obv_52h" in wdf.columns:
        oh=wdf["w_obv_52h"].iloc[-1]
        if pd.notna(oh) and pd.notna(obv[-1]) and obv[-1]>=oh*0.95: mf+=3
    cmf_cur=cmf[-1] if len(cmf)>0 and pd.notna(cmf[-1]) else 0
    if cmf_cur>0.05: mf+=3
    elif cmf_cur>0: mf+=2
    elif cmf_cur>-0.05: mf+=1
    mf+=3  # passed OBV divergence check
    s["mf"]=min(mf,15); total+=s["mf"]

    # 6. Phase E Breakout (15)
    be=0
    if bo.get("breakout"):
        be+=5
        bvr=bo.get("bvr",0) or 0
        if bvr>=1.2: be+=3
        elif bvr>=0.9: be+=1
        if bo.get("two_above") or bo.get("retest"): be+=3
        if len(c)>=5 and curr>np.nanmax(c[-5:-1]): be+=2
        if bo.get("retest"): be+=2
    s["be"]=min(be,15); total+=s["be"]

    # 7. Entry Quality (10)
    eq=0
    ext_p=bo.get("ext_piv",np.nan) if bo.get("breakout") else (curr/rh-1)
    if pd.notna(ext_p):
        if ext_p<=0.05: eq+=3
        elif ext_p<=0.10: eq+=2
        elif ext_p<=0.15: eq+=1
    sma50=ld.get("sma50",np.nan)
    if pd.notna(sma50) and sma50>0:
        ext50=curr/sma50-1
        if ext50<=0.15: eq+=2
        elif ext50<=0.20: eq+=1
    e20_w=wdf["w_e20"].iloc[-1] if len(wdf)>0 else np.nan
    sl=ev.get("spring_low",np.nan)
    cands=[x for x in [sl,rl,e20_w] if pd.notna(x) and x>0 and x<curr]
    hard_stop=max(cands) if cands else curr*0.88
    sd=(curr-hard_stop)/curr
    if sd<=0.08: eq+=2
    elif sd<=0.12: eq+=1
    h52=ld.get("high_52w",np.nan)
    if pd.notna(h52) and h52>curr and sd>0:
        rr=(h52/curr-1)/sd
        if rr>=3: eq+=2
        elif rr>=2: eq+=1
    dd=ld.get("dist_days_25d",0) or 0
    if dd<=2: eq+=1
    s["eq"]=min(eq,10); total+=s["eq"]

    return min(total,100), s

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY METADATA
# ─────────────────────────────────────────────────────────────────────────────
def entry_meta(wdf, ri, ev, bo, ld):
    m={}
    if ri is None: return m
    c=wdf["close_v"].values; curr=c[-1]
    rh=ri["range_high"]; rl=ri["range_low"]
    e20=wdf["w_e20"].values; atr=ld.get("atr14",np.nan)
    sl=ev.get("spring_low",np.nan); e20_w=float(e20[-1]) if len(e20)>0 and pd.notna(e20[-1]) else np.nan

    m["pivot"]=float(rh)
    cands=[x for x in [sl,rl,e20_w] if pd.notna(x) and x>0 and x<curr]
    m["support"]=float(max(cands)) if cands else float(rl)
    inv_c=[x for x in [sl,rl] if pd.notna(x) and x>0 and x<curr]
    if pd.notna(e20_w) and pd.notna(atr): inv_c.append(e20_w-atr)
    m["invalidation"]=float(max(inv_c)) if inv_c else float(rl*0.97)
    m["stop_pct"]=float((curr-m["invalidation"])/curr*100)
    m["dist_piv_pct"]=float((curr/rh-1)*100)
    sma50=ld.get("sma50",np.nan)
    m["ext_sma50_pct"]=float((curr/sma50-1)*100) if pd.notna(sma50) and sma50>0 else np.nan
    e10_w=wdf["w_e10"].iloc[-1] if len(wdf)>0 else np.nan
    m["ext_we10_pct"]=float((curr/e10_w-1)*100) if pd.notna(e10_w) and e10_w>0 else np.nan

    if bo.get("breakout"):
        if (m.get("ext_sma50_pct") or 0)>20 or m["dist_piv_pct"]>15:
            m["entry_cat"]="Too_Extended"
        elif bo.get("retest"):
            m["entry_cat"]="Confirmed_Breakout"
        elif m["dist_piv_pct"]<=8:
            m["entry_cat"]="Confirmed_Breakout"
        else:
            m["entry_cat"]="Too_Extended"
    else:
        dp=m["dist_piv_pct"]
        if -5<=dp<=3: m["entry_cat"]="Near_Trigger"
        elif dp<-5:   m["entry_cat"]="LPS_Entry"
        else:         m["entry_cat"]="Too_Extended"
    return m

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("="*80)
    print(" WYCKOFF PHASE D/E SCANNER — VIETNAM EQUITIES")
    print(f" As-of: 2026-05-12  |  Scan started...")
    print("="*80)

    print("\n[1/5] Loading data...")
    df, pu, vu = load_panel()
    init_n = df["ticker"].nunique()
    print(f"      {len(df):,} rows | {init_n} tickers | price_unit={pu} | vol_unit={vu}")

    print("\n[2/5] Filtering universe...")
    df, n_bars, n_liq, adv_map, as_of = filter_universe(df)
    print(f"      After >=250 bars : {n_bars} tickers")
    print(f"      After ADV50>=2B  : {n_liq} tickers")
    print(f"      Data as-of       : {as_of.date()}")

    print("\n[3/5] Daily indicators...")
    daily_g={}
    for tk, g in df.groupby("ticker"):
        try: daily_g[tk]=daily_ind(g.copy())
        except: pass
    print(f"      Done: {len(daily_g)} tickers")

    print("\n[4/5] Weekly indicators + Wyckoff scan...")
    weekly_g={}
    for tk, g in daily_g.items():
        try: weekly_g[tk]=to_weekly(g)
        except: pass

    rows=[]
    excluded_liq=[]; excluded_data=[]
    for tk in daily_g:
        dg=daily_g[tk]; wg=weekly_g.get(tk)
        adv50v=adv_map.get(tk,np.nan)
        if pd.isna(adv50v) or adv50v<ADV50_MIN:
            excluded_liq.append(tk); continue
        if wg is None or len(wg)<15:
            excluded_data.append(tk); continue

        ld=dg.iloc[-1].to_dict()
        ri=detect_range(wg)
        ctx=prior_context(wg,ri)
        is_pd,pd_sub,ev=detect_phase_d(wg,ri)
        is_pe,pe_sub,bo=detect_phase_e(wg,ri,ld)
        sc,sc_d=score100(wg,ri,ctx,ev,bo,ld)
        em=entry_meta(wg,ri,ev,bo,ld)

        curr=ld["close_v"]
        cmf_cur=wg["w_cmf20"].iloc[-1] if "w_cmf20" in wg.columns else np.nan
        obv_cur=wg["w_obv"].iloc[-1]; obvm_cur=wg["w_obv_m20"].iloc[-1]
        obv_s="Strong" if (pd.notna(obv_cur) and pd.notna(obvm_cur) and obv_cur>obvm_cur and ev.get("obv_conf",0)>=2) else \
              ("OK" if (pd.notna(obv_cur) and pd.notna(obvm_cur) and obv_cur>obvm_cur) else "Weak")

        vol_pat="Up>Down" if ev.get("supply_abs",0)>=3 else ("Mixed" if ev.get("supply_abs",0)>=2 else "Down>Up")

        phase_final=pe_sub if is_pe else (pd_sub if is_pd else "Other")

        rows.append(dict(
            ticker=tk,
            close=round(curr,0),
            adv50_b=round(adv50v/1e9,2),
            score=sc,
            score_rq=sc_d.get("rq",0), score_sq=sc_d.get("sq",0),
            score_sosd=sc_d.get("sosd",0), score_lq=sc_d.get("lq",0),
            score_mf=sc_d.get("mf",0), score_be=sc_d.get("be",0),
            score_eq=sc_d.get("eq",0),
            phase=phase_final,
            is_pd=is_pd, is_pe=is_pe,
            ctx=ctx,
            range_weeks=ri["range_weeks"] if ri else np.nan,
            range_low=round(ri["range_low"],0) if ri else np.nan,
            range_high=round(ri["range_high"],0) if ri else np.nan,
            range_depth_pct=round(ri["range_depth"]*100,1) if ri else np.nan,
            curr_pos_pct=round(ri["curr_pos"]*100,1) if ri else np.nan,
            spring=ev.get("spring",False),
            spring_week=ev.get("spring_week",""),
            sos=ev.get("sos",False),
            sos_week=ev.get("sos_week",""),
            lps=ev.get("lps",False),
            lps_week=ev.get("lps_week",""),
            obv_status=obv_s,
            cmf20=round(cmf_cur,3) if pd.notna(cmf_cur) else np.nan,
            vol_pattern=vol_pat,
            dist_piv_pct=round(em.get("dist_piv_pct",np.nan),1),
            ext_sma50_pct=round(em.get("ext_sma50_pct",np.nan),1) if pd.notna(em.get("ext_sma50_pct")) else np.nan,
            ext_we10_pct=round(em.get("ext_we10_pct",np.nan),1) if pd.notna(em.get("ext_we10_pct")) else np.nan,
            pivot=round(em.get("pivot",np.nan),0) if pd.notna(em.get("pivot")) else np.nan,
            support=round(em.get("support",np.nan),0) if pd.notna(em.get("support")) else np.nan,
            invalidation=round(em.get("invalidation",np.nan),0) if pd.notna(em.get("invalidation")) else np.nan,
            stop_pct=round(em.get("stop_pct",np.nan),1) if pd.notna(em.get("stop_pct")) else np.nan,
            entry_cat=em.get("entry_cat",""),
            bo_week=bo.get("breakout_week","") if is_pe else "",
            bvr=round(bo.get("bvr",np.nan),2) if is_pe and pd.notna(bo.get("bvr")) else np.nan,
            retest=bo.get("retest",False) if is_pe else False,
            dist_days=int(ld.get("dist_days_25d",0) or 0),
            stochrsi_k=round(ld.get("stochrsi_k",np.nan),1) if pd.notna(ld.get("stochrsi_k")) else np.nan,
            w_rsi14=round(wg["w_rsi14"].iloc[-1],1) if "w_rsi14" in wg.columns and pd.notna(wg["w_rsi14"].iloc[-1]) else np.nan,
            supply_abs=ev.get("supply_abs",0),
            obv_conf=ev.get("obv_conf",0),
            rejection=ev.get("rejection","") if not (is_pd or is_pe) else "",
        ))

    df_r=pd.DataFrame(rows).sort_values("score",ascending=False).reset_index(drop=True)
    df_r["rank"]=df_r.index+1

    # Save CSV
    OUT_CSV.parent.mkdir(parents=True,exist_ok=True)
    df_r.to_csv(OUT_CSV,index=False)
    print(f"      Scored {len(df_r)} tickers | CSV: {OUT_CSV}")

    # ─────── OUTPUT SECTIONS ──────────────────────────────────────────────────
    SEP="─"*90

    # ── SECTION 1: Universe Summary ──
    pd_df  = df_r[df_r["is_pd"]==True]
    pe_df  = df_r[df_r["is_pe"]==True]
    print(f"\n{'═'*90}")
    print(" SECTION 1 — UNIVERSE AND DATA QUALITY SUMMARY")
    print(f"{'═'*90}")
    print(f"  as_of_date              : {as_of.date()}")
    print(f"  initial_ticker_count    : {init_n}")
    print(f"  tickers_with_250+_bars  : {n_bars}")
    print(f"  tickers_ADV50_pass      : {n_liq}")
    print(f"  tickers_excluded_liq    : {len(excluded_liq)}")
    print(f"  tickers_excluded_data   : {len(excluded_data)}")
    print(f"  price_unit_assumption   : {pu}")
    print(f"  volume_value_unit       : {vu}")
    print(f"  Phase_D_candidates      : {len(pd_df)}")
    print(f"  Phase_E_candidates      : {len(pe_df)}")
    print(f"  Both_phase_D_and_E      : {len(df_r[df_r['is_pd']&df_r['is_pe']])}")

    # ── SECTION 2: Phase D ──
    print(f"\n{'═'*90}")
    print(" SECTION 2 — TOP PHASE D CANDIDATES")
    print(f"{'═'*90}")
    pd_top=pd_df.sort_values("score",ascending=False).head(25)
    pd_cols=["rank","ticker","close","adv50_b","score","phase","ctx",
             "range_weeks","range_low","range_high","curr_pos_pct",
             "spring","sos","lps","obv_status","cmf20","vol_pattern",
             "dist_piv_pct","support","invalidation","stop_pct","entry_cat"]
    # Rename for display
    pd_disp=pd_top[pd_cols].copy()
    pd_disp.columns=["#","Ticker","Close","ADV50B","Score","Phase","AccType",
                     "RngWk","RngLow","RngHi","Pos%",
                     "Spring","SOS","LPS","OBV","CMF20","VolPat",
                     "DistPiv%","Support","Inval","Stop%","EntryCat"]
    print(pd_disp.to_string(index=False,max_colwidth=22))

    # ── SECTION 3: Phase E ──
    print(f"\n{'═'*90}")
    print(" SECTION 3 — TOP PHASE E CANDIDATES")
    print(f"{'═'*90}")
    pe_top=pe_df.sort_values("score",ascending=False).head(25)
    pe_cols=["rank","ticker","close","adv50_b","score","phase","ctx",
             "range_weeks","range_high","bo_week","bvr","retest",
             "obv_status","cmf20","dist_piv_pct","ext_sma50_pct","ext_we10_pct",
             "support","invalidation","entry_cat"]
    pe_disp=pe_top[pe_cols].copy()
    pe_disp.columns=["#","Ticker","Close","ADV50B","Score","Phase","AccType",
                     "RngWk","Pivot","BOWeek","BVR","Retest",
                     "OBV","CMF20","ExtPiv%","ExtSMA50%","ExtWE10%",
                     "Support","Inval","EntryCat"]
    print(pe_disp.to_string(index=False,max_colwidth=22))

    # ── SECTION 4: Best 10 Actionable ──
    print(f"\n{'═'*90}")
    print(" SECTION 4 — BEST ACTIONABLE SETUPS RIGHT NOW (Top 10)")
    print(f"{'═'*90}")
    actionable=df_r[(df_r["is_pd"]|df_r["is_pe"]) &
                    (df_r["entry_cat"].isin(["Near_Trigger","LPS_Entry","Confirmed_Breakout"])) &
                    (df_r["score"]>=65)].head(10)
    for _,r in actionable.iterrows():
        phase_lbl=r["phase"]; tk=r["ticker"]
        spr="Spring+SOS+LPS" if r["spring"] and r["sos"] and r["lps"] else \
            ("Spring+SOS" if r["spring"] and r["sos"] else \
             ("SOS+LPS" if r["sos"] and r["lps"] else \
              ("SOS" if r["sos"] else "Accumulating")))
        conf="High" if r["score"]>=80 else ("Medium" if r["score"]>=70 else "Low")
        print(f"\n  ┌─ #{int(r['rank'])} {tk}  |  Score:{r['score']}/100  |  {phase_lbl}  |  Confidence:{conf}")
        print(f"  |  Close:{r['close']:,.0f}  ADV50:{r['adv50_b']:.1f}B  AccType:{r['ctx']}")
        print(f"  |  Range:{r['range_low']:,.0f}–{r['range_high']:,.0f}  ({r['range_weeks']}wk,{r['range_depth_pct']:.0f}%deep)  Pos:{r['curr_pos_pct']:.0f}%")
        print(f"  |  Evidence: {spr}  |  OBV:{r['obv_status']}  CMF:{r['cmf20']:.3f}  SupplyAbs:{r['supply_abs']}/5")
        print(f"  |  Entry: {r['entry_cat']}  Dist-to-pivot:{r['dist_piv_pct']:+.1f}%")
        print(f"  |  Support:{r['support']:,.0f}  Invalidation:{r['invalidation']:,.0f}  Stop:{r['stop_pct']:.1f}%")
        trig="Weekly close > {:.0f} on vol >1.3x avg20w".format(r["range_high"]) if not r["is_pe"] else \
             ("Hold above {:.0f}; add on LPS pullback".format(r["support"]) if r.get("retest") else
              "Hold above {:.0f}".format(r["support"]))
        print(f"  |  Trigger: {trig}")
        fail="Break below {:.0f} on volume".format(r["invalidation"])
        print(f"  └  Fails if: {fail}")

    # ── SECTION 5: Extended but Strong ──
    print(f"\n{'═'*90}")
    print(" SECTION 5 — TOO EXTENDED BUT STRONG")
    print(f"{'═'*90}")
    ext_df=df_r[(df_r["is_pe"]==True) & (df_r["entry_cat"]=="Too_Extended") & (df_r["score"]>=70)].head(15)
    if len(ext_df)==0: print("  (none at this threshold)")
    else:
        ext_cols=["rank","ticker","close","score","phase","dist_piv_pct","ext_sma50_pct","ext_we10_pct","support","cmf20"]
        ext_disp=ext_df[ext_cols].copy()
        ext_disp.columns=["#","Ticker","Close","Score","Phase","ExtPiv%","ExtSMA50%","ExtWE10%","Support","CMF20"]
        print(ext_disp.to_string(index=False))
        print("\n  Pullback/base to watch for re-entry:")
        for _,r in ext_df.head(5).iterrows():
            print(f"  {r['ticker']}: retrace to W_EMA10 or {r['support']:,.0f} would reset risk/reward")

    # ── SECTION 6: Rejected/Warning ──
    print(f"\n{'═'*90}")
    print(" SECTION 6 — REJECTED / WARNING LIST (sample)")
    print(f"{'═'*90}")
    rej=df_r[(df_r["is_pd"]==False)&(df_r["is_pe"]==False)&(df_r["rejection"]!="")&(df_r["score"]>=40)].head(20)
    if len(rej)>0:
        rej_disp=rej[["rank","ticker","close","adv50_b","score","rejection"]].copy()
        rej_disp.columns=["#","Ticker","Close","ADV50B","Score","Reason"]
        print(rej_disp.to_string(index=False))
    print(f"\n  Also excluded:")
    print(f"  - ADV50 <2B: {len(excluded_liq)} tickers")
    print(f"  - Insufficient weekly bars: {len(excluded_data)} tickers")

    # ── SECTION 7: Final Rankings ──
    print(f"\n{'═'*90}")
    print(" SECTION 7 — FINAL RANKINGS AND RECOMMENDATIONS")
    print(f"{'═'*90}")

    pd_late=pd_df[pd_df["phase"]=="Phase_D_Late"].sort_values("score",ascending=False).head(5)
    pe_ret =pe_df[pe_df["phase"]=="Phase_E_Retest_Confirmed"].sort_values("score",ascending=False).head(5)
    near_t =df_r[(df_r["is_pd"]|df_r["is_pe"])&(df_r["entry_cat"]=="Near_Trigger")].head(5)
    lps_b  =df_r[(df_r["is_pd"]|df_r["is_pe"])&(df_r["entry_cat"]=="LPS_Entry")].head(5)
    ext_s  =df_r[(df_r["is_pe"])&(df_r["entry_cat"]=="Too_Extended")&(df_r["score"]>=70)].head(5)

    def rank_block(label, sub):
        print(f"\n  ── {label} ──")
        if len(sub)==0: print("    (none)")
        for _,r in sub.iterrows():
            dp=f"{r.get('dist_piv_pct',0):+.1f}%" if pd.notna(r.get('dist_piv_pct')) else "--"
            print(f"    {r['ticker']:<8}  Score={r['score']}  {r.get('phase','')}  ADV50={r.get('adv50_b',''):.1f}B  DistPiv={dp}  CMF={r.get('cmf20',np.nan):.3f}  Stop={r.get('stop_pct',np.nan):.1f}%")

    rank_block("Top 5 Phase D Late", pd_late)
    rank_block("Top 5 Phase E Retest Confirmed", pe_ret)
    rank_block("Top 5 Near Trigger", near_t)
    rank_block("Top 5 LPS Pullback", lps_b)
    rank_block("Top 5 Extended But Strong", ext_s)

    # Macro judgment
    print(f"\n  ── FINAL JUDGMENT ──")
    n_pd=len(pd_df); n_pe=len(pe_df)
    if n_pe>n_pd*1.5: dom="The market is offering more Phase E (breakout/markup) setups than Phase D."
    elif n_pd>n_pe*1.5: dom="The market is offering more Phase D (late accumulation) setups — breakouts not yet dominant."
    else: dom=f"Phase D ({n_pd}) and Phase E ({n_pe}) setups are roughly balanced."
    print(f"  {dom}")

    n_acc=len(df_r[(df_r["is_pd"]|df_r["is_pe"])&(df_r["ctx"]=="Accumulation")])
    n_reacc=len(df_r[(df_r["is_pd"]|df_r["is_pe"])&(df_r["ctx"]=="Re-accumulation")])
    print(f"  Context: {n_reacc} re-accumulation vs {n_acc} bottom-accumulation setups — "
          + ("re-accumulation dominant (higher quality)." if n_reacc>n_acc else "mixed/bottom-heavy."))

    # Breakout volume quality
    pe_strong_vol=pe_df[pe_df["bvr"]>=1.2]
    pe_weak_vol=pe_df[pe_df["bvr"]<1.0]
    if len(pe_df)>0:
        vol_pct=len(pe_strong_vol)/len(pe_df)*100
        print(f"  Breakout volume quality: {vol_pct:.0f}% of Phase E have BVR>=1.2x — "
              + ("volume-confirmed breakouts dominate." if vol_pct>=50 else "many breakouts are volume-light — higher failure risk."))

    print(f"\n{'═'*90}")
    print(" END OF WYCKOFF PHASE D/E SCAN REPORT")
    print(f"{'═'*90}\n")

    return df_r

if __name__=="__main__":
    result=main()
