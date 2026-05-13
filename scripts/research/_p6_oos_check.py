"""Quick OOS concentration check — re-runs C06 OOS fold and identifies top contributors."""
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Inline the engine (copy-paste from phase5 for self-containment)
CACHE = REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet"
VNIDX = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
START  = pd.Timestamp("2023-01-01")
END    = pd.Timestamp("2026-04-30")
OOS1   = pd.Timestamp("2025-01-01")
EXCL   = {"VPL"}
ADV50_MIN = 2.0

def _ema(a, span):
    alpha = 2.0/(span+1); out = np.full(len(a),np.nan)
    for i in range(len(a)):
        v = float(a[i])
        if np.isnan(v): continue
        p = out[i-1] if i>0 and not np.isnan(out[i-1]) else np.nan
        out[i] = v if np.isnan(p) else alpha*v+(1-alpha)*p
    return out
def _watr(h,l,c,n):
    tr=np.empty(len(c)); tr[0]=h[0]-l[0]
    for i in range(1,len(c)): tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    out=np.full(len(tr),np.nan)
    if len(tr)>=n:
        out[n-1]=float(np.mean(tr[:n]))
        for i in range(n,len(tr)): out[i]=tr[i]/n+out[i-1]*(1-1/n)
    return out
def _adv50(val):
    out=np.full(len(val),np.nan)
    for i in range(50,len(val)): out[i]=float(np.mean(val[i-50:i]))/1e9
    return out
def gk_sig(c,h,l,gk_len=100,gk_mult=2.0,gk_atr=14,gk_conf=2):
    n=len(c); lag=max(int((gk_len-1)//2),0)
    pc=np.empty(n)
    for i in range(n): j=i-lag; pc[i]=c[j] if j>=0 else c[i]
    zl=_ema(c+(c-pc),gk_len); atr=_watr(h,l,c,gk_atr)
    gu=zl+atr*gk_mult; gl=zl-atr*gk_mult; cb=gk_conf-1
    ab=c>gu; bl=c<gl; a1=np.concatenate([[False],ab[:-1]]); b1=np.concatenate([[False],bl[:-1]])
    acb=np.concatenate([np.full(max(cb,0),False),ab[:-cb]]) if cb>0 else ab.copy()
    bcb=np.concatenate([np.full(max(cb,0),False),bl[:-cb]]) if cb>0 else bl.copy()
    zp=np.concatenate([[np.nan],zl[:-1]]); zr=zl>zp; zf=zl<zp
    vl=~np.isnan(gu)&~np.isnan(gl)
    bull=ab&a1&acb&zr&vl; bear=bl&b1&bcb&zf&vl
    raw=np.where(bull,1.0,np.where(bear,-1.0,np.nan))
    s=pd.Series(raw).ffill().fillna(0.0).astype(int).values
    prev=np.zeros(n,dtype=int); prev[1:]=s[:-1]; flip=(s!=prev)&(s!=0)
    return {"gk_buy":flip&(s==1),"gk_sell":flip&(s==-1)}

panel=pd.read_parquet(CACHE)
panel=panel[~panel["symbol"].isin(EXCL)].copy()
panel["date"]=pd.to_datetime(panel["date"])
panel=panel[(panel["date"]>=START)&(panel["date"]<=END)].copy()

vnx=pd.read_csv(VNIDX); vnx["date"]=pd.to_datetime(vnx["date"]); vnx=vnx.sort_values("date")
vc=vnx["close"].values.astype(float); e50=_ema(vc,50)
vnx_state={}
for i in range(len(vnx)):
    d=str(vnx["date"].iloc[i].date())
    vnx_state[d]={"above_e50":bool(vc[i]>e50[i]) if not np.isnan(e50[i]) else True}

base={}
for sym,grp in panel.groupby("symbol"):
    df=grp.sort_values("date").reset_index(drop=True)
    c=df["close"].values.astype(float); h=df["high"].values.astype(float)
    l=df["low"].values.astype(float); o=df["open"].values.astype(float)
    val=df["value"].values.astype(float); dts=pd.to_datetime(df["date"].values)
    adv=_adv50(val); g=gk_sig(c,h,l)
    ve=np.full(len(c),np.nan)
    for i in range(len(c)):
        if not np.isnan(adv[i]) and adv[i]>0: ve[i]=val[i]/(adv[i]*1e9)
    e20=_ema(c,20)
    base[sym]={"dates":dts,"open":o,"close":c,"gk_fast":g,"adv50_lag":adv,"volexp":ve,"ema20":e20,
               "date_to_idx":{str(d.date()):i for i,d in enumerate(dts)}}

all_dates=sorted({d for b in base.values() for d in b["dates"]})
all_dates=[d for d in all_dates if START<=d<=END]
oos_dates=[d for d in all_dates if d>=OOS1]
print(f"OOS dates: {len(oos_dates)} ({oos_dates[0].date()} to {oos_dates[-1].date()})")

# Run C06 OOS
FEE=35/10000; CA=2.0; MAX_P=10
cash=1.0; holdings={}; pending_exits={}; pending_entries=[]; trades=[]; eq=[]; prev_eq=1.0
for day_i,td in enumerate(oos_dates):
    ds=str(td.date()); vnx=vnx_state.get(ds,{})
    for sym,(t_sig,rsn) in list(pending_exits.items()):
        b=base[sym]; tex=b["date_to_idx"].get(ds)
        if tex is None: continue
        op=float(b["open"][tex]); pos=holdings.pop(sym); proceeds=pos["sh"]*op*(1-FEE/2); cash+=proceeds
        trades.append({"symbol":sym,"entry_dt":str(pos["edt"].date()),"exit_dt":str(td.date()),
                       "exit_reason":rsn,"net_ret":(op*(1-FEE/2))/pos["epx"]-1,"hold_bars":day_i-pos["edi"]})
    pending_exits.clear()
    slots=MAX_P-len(holdings)
    sel=sorted(pending_entries,key=lambda x:-x["adv"])[:slots]
    for e in sel:
        sym=e["sym"]; b=base[sym]; tex=b["date_to_idx"].get(ds)
        if tex is None or sym in holdings: continue
        op=float(b["open"][tex])
        if op<=0: continue
        sf=0.5 if not vnx.get("above_e50",True) else 1.0
        slot=(prev_eq/MAX_P)*sf; px_eff=op*(1+FEE/2); sh=slot/px_eff; cash-=slot
        holdings[sym]={"sh":sh,"epx":px_eff,"eop":op,"edt":td,"edi":day_i,"adv":e["adv"],"mfe":0.,"mae":0.}
    pending_entries.clear()
    mv=0.
    for sym,pos in holdings.items():
        b=base[sym]; t=b["date_to_idx"].get(ds)
        if t is None: continue
        cn=float(b["close"][t]); mv+=pos["sh"]*cn
        u=cn/pos["eop"]-1; pos["mfe"]=max(pos["mfe"],u); pos["mae"]=min(pos["mae"],u)
    eq_now=cash+mv; prev_eq=eq_now
    eq.append({"date":td,"equity":eq_now,"n_pos":len(holdings)})
    for sym,pos in list(holdings.items()):
        b=base[sym]; t=b["date_to_idx"].get(ds)
        if t is None or t+1>=len(b["close"]): continue
        bars=day_i-pos["edi"]; cn=float(b["close"][t]); lo=float(b["low"][t] if "low" in b else cn)
        tri,rsn=False,""
        if bool(b["gk_fast"]["gk_sell"][t]): tri,rsn=True,"GK_SELL"
        if not tri and bars>=20:
            cr=cn/pos["eop"]-1
            if cr<=0: tri,rsn=True,"TSTOP"
        if tri: pending_exits[sym]=(t,rsn)
    for sym,b in base.items():
        if sym in holdings or sym in pending_exits or any(x["sym"]==sym for x in pending_entries): continue
        t=b["date_to_idx"].get(ds)
        if t is None or t+1>=len(b["close"]): continue
        adv=float(b["adv50_lag"][t])
        if np.isnan(adv) or adv<CA: continue
        if not bool(b["gk_fast"]["gk_buy"][t]): continue
        ve=float(b["volexp"][t])
        if np.isnan(ve) or ve<1.2: continue
        pending_entries.append({"sym":sym,"adv":adv,"ve":ve})

tr=pd.DataFrame(trades)
print(f"\nOOS trades: {len(tr)}")
if not tr.empty:
    total=tr["net_ret"].sum()
    tkr=tr.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
    print("\nTop-10 OOS tickers by PnL:")
    for sym,v in tkr.head(10).items():
        pct=v/total*100 if total!=0 else 0
        print(f"  {sym:6s}  sum_ret={v:.4f}  pct={pct:.1f}%  n={len(tr[tr['symbol']==sym])}")
    print("\nTop-10 OOS trades by net_ret:")
    best=tr.sort_values("net_ret",ascending=False).head(10)
    for _,r in best.iterrows():
        print(f"  {r['symbol']:6s}  {r['entry_dt']} -> {r['exit_dt']}  ret={r['net_ret']:.3f}  reason={r['exit_reason']}")
    CA_SYMS={"VIC","VHM","VRE","VGI","SAB","L40","TCH","ANV","BIC","CSV","DPM","DPR","IMP","MCH","MSH","NTL","SIP","TCB","TCO"}
    ca_contrib=tkr[tkr.index.isin(CA_SYMS)].sum()
    print(f"\nCA-watchlist PnL contribution: {ca_contrib/total*100:.1f}%")
