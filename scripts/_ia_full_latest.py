"""Get the full current IA tier snapshot (2026-05-27) across all panel parts."""
import pandas as pd
import glob
import os

COLS = ["scan_date", "ticker", "tier", "institutional_accumulation_score",
        "is_liquid", "adv50_vnd", "has_fund_disclosure_tag", "fund_context_bucket"]

parts = sorted(glob.glob(
    "data/research/institutional_accumulation/panel_scores_parts/panel_part_*.parquet"
))

# Use only the non-consolidated parts (two-range names, where end-start <= 100)
# to avoid double-counting from the overlapping consolidated files
# Strategy: use small 20-symbol parts for recent data; skip large merged ones
dfs = []
for p in parts:
    name = os.path.basename(p).replace("panel_part_", "").replace(".parquet", "")
    parts_range = name.split("_")
    if len(parts_range) == 2:
        try:
            start, end = int(parts_range[0]), int(parts_range[1])
            span = end - start
            if span <= 100:  # use small granular parts only (avoid duplicates from merged)
                df = pd.read_parquet(p, columns=COLS)
                dfs.append(df)
        except ValueError:
            pass

combined = pd.concat(dfs, ignore_index=True)
combined = combined.drop_duplicates(subset=["scan_date", "ticker"])

latest = combined["scan_date"].max()
latest_df = combined[combined["scan_date"] == latest].copy()

print(f"Latest scan date: {latest}")
print(f"Total tickers in scan: {len(latest_df)}")
print(f"Tier distribution:\n{latest_df['tier'].value_counts().to_string()}")
print()

# All Tier 1/2/3
favs = latest_df[latest_df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])].sort_values(
    ["tier", "institutional_accumulation_score"], ascending=[True, False]
)
print(f"IA Favorites (Tier 1-3): {len(favs)}")
print(favs[["ticker", "tier", "institutional_accumulation_score", "is_liquid", "adv50_vnd"]].to_string())

print()
# Compare to hardcoded 19
hardcoded_19 = ["NAF","PET","C69","HHP","LPB","MSB","VPL","PCH","VPI","QNS",
                "VCB","DCL","SSB","VC3","OCB","VND","CDC","DXS","PDR"]
fav_tickers = set(favs["ticker"].tolist())
print("=== Hardcoded 19 vs Current IA Tiers ===")
for sym in hardcoded_19:
    row = latest_df[latest_df["ticker"] == sym]
    if len(row) > 0:
        tier = row.iloc[0]["tier"]
        score = row.iloc[0]["institutional_accumulation_score"]
        print(f"  {sym:<6}  tier={tier:<8}  score={score:.1f}")
    else:
        print(f"  {sym:<6}  NOT IN PANEL")

print()
print("=== New IA favorites NOT in hardcoded 19 (Tier 1-3) ===")
new_favs = favs[~favs["ticker"].isin(hardcoded_19)]
if len(new_favs) > 0:
    print(new_favs[["ticker", "tier", "institutional_accumulation_score", "is_liquid"]].to_string())
else:
    print("  (none)")
