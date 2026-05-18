import pandas as pd
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
vni = pd.read_parquet(REPO / "data/fireant_ssot/ta_vnindex.parquet")
vni["date"] = pd.to_datetime(vni["date"])
vni = vni.sort_values("date")

for sym in ["VIC", "VHM", "VRE", "VNINDEX"]:
    if sym == "VNINDEX":
        d = vni[["date", "close", "volume"]].copy()
    else:
        d = pd.read_csv(REPO / f"data/stocks/{sym}.csv")
        d["date"] = pd.to_datetime(d["date"])
        d = d.sort_values("date")
    for h in [5, 20, 60]:
        d[f"r{h}"] = d["close"] / d["close"].shift(h) - 1
    r = d.iloc[-1]
    print(sym, r["date"].date(), f"r5={r['r5']*100:.1f}%", f"r20={r['r20']*100:.1f}%", f"r60={r['r60']*100:.1f}%")

c, v = vni["close"].astype(float), vni["volume"].astype(float)
dist = (c <= c.shift(1) * 0.998) & (v > v.shift(1))
print("dist last10", int(dist.tail(10).sum()))
print("last dist", vni.loc[dist, "date"].tail(8).dt.strftime("%Y-%m-%d").tolist())
