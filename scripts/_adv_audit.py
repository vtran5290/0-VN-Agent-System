import pandas as pd, numpy as np

raw = pd.read_parquet("data/research/sector_l4_causality/stock_daily_cloud_panel.parquet",
                      columns=["symbol", "date", "adv50", "value"])
raw["date"] = pd.to_datetime(raw["date"])

recent = raw[raw["date"] >= raw["date"].max() - pd.Timedelta(days=90)]
sym_adv = recent.groupby("symbol")["adv50"].mean() / 1e9  # billions VND

print("Total symbols in OHLCV parquet:", raw["symbol"].nunique())
print("Symbols ADV50 >= 2.0B:", int((sym_adv >= 2.0).sum()))
print("Symbols ADV50 >= 1.0B:", int((sym_adv >= 1.0).sum()))
print("Symbols ADV50 >= 0.5B:", int((sym_adv >= 0.5).sum()))
print("Symbols ADV50 >= 0.3B:", int((sym_adv >= 0.3).sum()))
print("Symbols ADV50 >= 0.1B:", int((sym_adv >= 0.1).sum()))
print()
bins  = [0, 0.1, 0.3, 0.5, 1, 2, 5, 10, 9999]
labels = ["<0.1B", "0.1-0.3B", "0.3-0.5B", "0.5-1B", "1-2B", "2-5B", "5-10B", ">10B"]
counts, _ = np.histogram(sym_adv.values, bins=bins)
for l, c in zip(labels, counts):
    print(f"  {l:>12}: {c:3d} symbols")

# Also check IA report — what does the current IA list look like?
print()
print("--- Checking institutional accumulation sources ---")
import glob, os
ia_files = glob.glob("data/research/institutional_accumulation/*.csv")
for f in ia_files[:5]:
    print(f, "->", os.path.getsize(f), "bytes")
