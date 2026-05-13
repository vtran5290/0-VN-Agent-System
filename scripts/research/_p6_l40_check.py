"""Inspect L40 price history for CA gap timing."""
import pandas as pd, numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
panel = pd.read_parquet(REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet")
panel["date"] = pd.to_datetime(panel["date"])

l40 = panel[panel["symbol"]=="L40"].sort_values("date").reset_index(drop=True)
c = l40["close"].values.astype(float)
o = l40["open"].values.astype(float)
h = l40["high"].values.astype(float)
lv = l40["low"].values.astype(float)
val = l40["value"].values.astype(float)
dts = l40["date"].values

print("L40 full history:")
print(f"  Start: {pd.Timestamp(dts[0]).date()}  End: {pd.Timestamp(dts[-1]).date()}")
print(f"  Rows: {len(l40)}")
print()

# Find all gaps >= 10%
print("All gaps >= 10% (absolute):")
for i in range(1, len(c)):
    if c[i-1] > 0:
        gap = c[i] / c[i-1] - 1
        if abs(gap) >= 0.10:
            dt = pd.Timestamp(dts[i]).date()
            print(f"  {dt}  prev_close={c[i-1]:.2f}  close={c[i]:.2f}  gap={gap*100:.1f}%  vol_bn={val[i]/1e9:.3f}")

print()

# Show L40 around the OOS trade period (Sep 2025 - Dec 2025)
print("L40 price: Sep 2025 to Dec 2025 (OOS trade period)")
mask = (l40["date"] >= "2025-08-01") & (l40["date"] <= "2025-12-31")
sub = l40[mask]
for _, r in sub.iterrows():
    prev_i = l40[l40["date"] < r["date"]].index
    if len(prev_i):
        prev_c = l40.loc[prev_i[-1], "close"]
        gap = r["close"] / prev_c - 1 if prev_c > 0 else 0
        flag = " <-- GAP" if abs(gap) >= 0.10 else ""
        print(f"  {r['date'].date()}  open={r['open']:.2f}  close={r['close']:.2f}  gap={gap*100:.1f}%{flag}")

# Also check MCH
print()
mch = panel[panel["symbol"]=="MCH"].sort_values("date").reset_index(drop=True)
c2 = mch["close"].values.astype(float)
dts2 = mch["date"].values
print("MCH gaps >= 10%:")
for i in range(1, len(c2)):
    if c2[i-1] > 0:
        gap = c2[i]/c2[i-1]-1
        if abs(gap) >= 0.10:
            dt = pd.Timestamp(dts2[i]).date()
            print(f"  {dt}  prev={c2[i-1]:.2f}  close={c2[i]:.2f}  gap={gap*100:.1f}%")

# Check VIC gap date
print()
vic = panel[panel["symbol"]=="VIC"].sort_values("date").reset_index(drop=True)
cv = vic["close"].values.astype(float)
dtsv = vic["date"].values
print("VIC gaps >= 10%:")
for i in range(1, len(cv)):
    if cv[i-1] > 0:
        gap = cv[i]/cv[i-1]-1
        if abs(gap) >= 0.10:
            dt = pd.Timestamp(dtsv[i]).date()
            print(f"  {dt}  prev={cv[i-1]:.2f}  close={cv[i]:.2f}  gap={gap*100:.1f}%")

# Check SAB
print()
sab = panel[panel["symbol"]=="SAB"].sort_values("date").reset_index(drop=True)
cs = sab["close"].values.astype(float)
dtss = sab["date"].values
print("SAB gaps >= 10%:")
for i in range(1, len(cs)):
    if cs[i-1] > 0:
        gap = cs[i]/cs[i-1]-1
        if abs(gap) >= 0.10:
            dt = pd.Timestamp(dtss[i]).date()
            print(f"  {dt}  prev={cs[i-1]:.2f}  close={cs[i]:.2f}  gap={gap*100:.1f}%")
