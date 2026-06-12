import pandas as pd
import glob
import os

# Find most recent parts by modification time
parts = glob.glob("data/research/institutional_accumulation/panel_scores_parts/panel_part_*.parquet")
parts_by_mtime = sorted(parts, key=os.path.getmtime, reverse=True)

print("=== Most recently modified parts ===")
for p in parts_by_mtime[:5]:
    df = pd.read_parquet(p, columns=["scan_date", "ticker"])
    name = os.path.basename(p)
    print(f"  {name}: {df['scan_date'].min()} -> {df['scan_date'].max()} | {df['ticker'].nunique()} tickers | {len(df)} rows")

# Find the part with the most recent scan dates
print()
print("=== Checking the largest consolidated part for recent IA scores ===")
# The _00000_00199 part covers the oldest dates
# The _01400_01499, _01500_01563 likely cover recent dates
for p in ["data/research/institutional_accumulation/panel_scores_parts/panel_part_01400_01499.parquet",
          "data/research/institutional_accumulation/panel_scores_parts/panel_part_01500_01563.parquet",
          "data/research/institutional_accumulation/panel_scores_parts/panel_part_01200_01399.parquet"]:
    if os.path.exists(p):
        df = pd.read_parquet(p, columns=["scan_date", "ticker", "tier", "institutional_accumulation_score",
                                          "is_liquid", "adv50_vnd"])
        latest = df["scan_date"].max()
        print(f"\n  {os.path.basename(p)}: {df['scan_date'].min()} -> {latest} | {df['ticker'].nunique()} tickers")
        latest_df = df[df["scan_date"] == latest]
        print(f"  Latest ({latest}): {len(latest_df)} rows | Tier dist: {latest_df['tier'].value_counts().to_dict()}")
        tier_fav = latest_df[latest_df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])]
        if len(tier_fav) > 0:
            print("  IA Favorites (Tier 1-3):")
            print(tier_fav[["ticker", "tier", "institutional_accumulation_score", "is_liquid", "adv50_vnd"]].sort_values("institutional_accumulation_score", ascending=False).to_string())
