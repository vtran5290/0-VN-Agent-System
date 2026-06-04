"""
Vietnam Market & Sector Valuation Verification
Date: 2026-05-30
Source: FireAnt SSOT (data/fireant_ssot/) + ICB industry history exports
"""
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

ICB_L1_NAMES = {
    1:    'Oil & Gas (Dầu khí)',
    1000: 'Basic Materials (Vật liệu cơ bản)',
    2000: 'Industrials (Công nghiệp)',
    3000: 'Consumer Goods (Hàng tiêu dùng)',
    4000: 'Healthcare (Y tế)',
    5000: 'Consumer Services (Dịch vụ tiêu dùng)',
    6000: 'Telecom (Viễn thông)',
    7000: 'Utilities (Hạ tầng/Tiện ích)',
    8000: 'Financials (Tài chính)',
    9000: 'Technology (Công nghệ)',
}

# -----------------------------------------------------------------------
# 1. ICB L1 SECTOR HISTORY
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 1: ICB L1 SECTOR HISTORY — FIREANT")
print("="*70)

df = pd.read_csv(
    'data/fireant_exports/industries/industries_history_L1_2012-01-01_2026-04-30.csv',
    parse_dates=['date']
)
df['industryCode'] = df['industryCode'].astype(int)
print(f"Loaded {len(df):,} rows | Date range: {df['date'].min().date()} to {df['date'].max().date()}")
print(f"ICB L1 codes: {sorted(df['industryCode'].unique())}")

# Latest snapshot
latest_date = df['date'].max()
latest = df[df['date'] == latest_date].copy()
print(f"\nLatest snapshot: {latest_date.date()}")
print(f"{'Sector':<40} {'P/E':>6} {'P/B':>6} {'MktCap(VNDbn)':>14}")
print("-"*70)
for _, row in latest.iterrows():
    name = ICB_L1_NAMES.get(int(row['industryCode']), str(row['industryCode']))
    mc_bn = row['marketCap'] / 1e9 if pd.notna(row['marketCap']) else 0
    pe = f"{row['pe']:.2f}" if pd.notna(row['pe']) and row['pe'] > 0 else "N/A"
    pb = f"{row['pb']:.2f}" if pd.notna(row['pb']) and row['pb'] > 0 else "N/A"
    print(f"  {name:<38} {pe:>6} {pb:>6} {mc_bn:>14,.0f}")

# -----------------------------------------------------------------------
# 2. AGGREGATE VN-INDEX LEVEL P/E AND P/B
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 2: VN-INDEX AGGREGATE VALUATION (MARKET-CAP WEIGHTED)")
print("="*70)

# Sum across all ICB L1 sectors for "market" aggregate
# Note: ICB L1 sectors cover all HOSE+HNX+UPCoM listed companies
# VN-Index is HOSE only but FireAnt's sector data aggregates all exchanges

# Compute implied earnings and book equity from P/E and P/B
latest['implied_earnings'] = np.where(
    (latest['pe'] > 0) & (latest['pe'].notna()),
    latest['marketCap'] / latest['pe'],
    np.nan
)
latest['implied_book'] = np.where(
    (latest['pb'] > 0) & (latest['pb'].notna()),
    latest['marketCap'] / latest['pb'],
    np.nan
)

total_mc = latest['marketCap'].sum()
total_earnings = latest['implied_earnings'].sum()  # excludes sectors with pe=0 or N/A
total_book = latest['implied_book'].sum()

agg_pe = total_mc / total_earnings if total_earnings > 0 else np.nan
agg_pb = total_mc / total_book if total_book > 0 else np.nan

print(f"Total Market Cap (all sectors): {total_mc/1e12:.2f} trillion VND")
print(f"Aggregate LTM P/E (market-cap weighted): {agg_pe:.2f}x")
print(f"Aggregate LTM P/B (market-cap weighted): {agg_pb:.2f}x")
print(f"(Note: This includes all exchanges; VN-Index HOSE-only may differ slightly)")

# -----------------------------------------------------------------------
# 3. HISTORICAL CYCLE BOTTOMS
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 3: HISTORICAL CYCLE BOTTOM P/E AND P/B")
print("="*70)

# Aggregate across all sectors per day
daily = df.copy()
daily['implied_earnings'] = np.where(
    (daily['pe'] > 0) & (daily['pe'].notna()),
    daily['marketCap'] / daily['pe'],
    np.nan
)
daily['implied_book'] = np.where(
    (daily['pb'] > 0) & (daily['pb'].notna()),
    daily['marketCap'] / daily['pb'],
    np.nan
)

daily_agg = daily.groupby('date').agg(
    total_mc=('marketCap', 'sum'),
    total_earnings=('implied_earnings', 'sum'),
    total_book=('implied_book', 'sum'),
).reset_index()

daily_agg['pe_agg'] = daily_agg['total_mc'] / daily_agg['total_earnings']
daily_agg['pb_agg'] = daily_agg['total_mc'] / daily_agg['total_book']

# VN-Index level (load)
vnindex = pd.read_parquet('data/fireant_ssot/ta_vnindex.parquet')
print("VNIndex columns:", list(vnindex.columns)[:10])
if 'date' not in vnindex.columns and vnindex.index.name == 'date':
    vnindex = vnindex.reset_index()
vnindex['date'] = pd.to_datetime(vnindex['date'])
vnindex = vnindex.rename(columns={c: c.lower() for c in vnindex.columns})
print("VNIndex head:", vnindex[['date','close']].head(3).to_string())

# Merge valuation with VN-Index price
merged = daily_agg.merge(vnindex[['date','close']], on='date', how='left')

# Define cycle bottoms by approximate date range
bottoms = {
    '2009 bottom':  ('2009-01-01', '2009-04-30'),
    '2012 bottom':  ('2012-01-01', '2012-12-31'),
    '2016 bottom':  ('2015-11-01', '2016-03-31'),
    '2020 Covid':   ('2020-03-01', '2020-04-30'),
    '2022 crisis':  ('2022-11-01', '2022-12-31'),
}

print(f"\n{'Period':<20} {'VNIndex Low':>12} {'P/E at Low':>12} {'P/B at Low':>12}")
print("-"*60)
for label, (start, end) in bottoms.items():
    sub = merged[(merged['date'] >= start) & (merged['date'] <= end)].dropna(subset=['close'])
    if len(sub) == 0:
        print(f"  {label:<18} {'NO DATA':>12}")
        continue
    # Find row with minimum VN-Index close
    row = sub.loc[sub['close'].idxmin()]
    print(f"  {label:<18} {row['close']:>12.0f} {row['pe_agg']:>12.2f}x {row['pb_agg']:>12.2f}x  ({row['date'].date()})")

# Current level
current = merged.dropna(subset=['close','pe_agg']).iloc[-1]
print(f"\n  {'Current':18} {current['close']:>12.0f} {current['pe_agg']:>12.2f}x {current['pb_agg']:>12.2f}x  ({current['date'].date()})")

# Historical stats
hist = merged.dropna(subset=['pe_agg','pb_agg'])
print(f"\n  PE 10yr avg: {hist[hist['date']>='2016-01-01']['pe_agg'].mean():.2f}x  | PE 5yr avg: {hist[hist['date']>='2021-01-01']['pe_agg'].mean():.2f}x")
print(f"  PB 10yr avg: {hist[hist['date']>='2016-01-01']['pb_agg'].mean():.2f}x  | PB 5yr avg: {hist[hist['date']>='2021-01-01']['pb_agg'].mean():.2f}x")

# Percentile
pe_pct = (hist[hist['date']>='2016-01-01']['pe_agg'] < current['pe_agg']).mean() * 100
pb_pct = (hist[hist['date']>='2016-01-01']['pb_agg'] < current['pb_agg']).mean() * 100
print(f"  Current PE percentile vs 10yr history: {pe_pct:.0f}th")
print(f"  Current PB percentile vs 10yr history: {pb_pct:.0f}th")

# -----------------------------------------------------------------------
# 4. SECTOR HISTORICAL CONTEXT
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 4: SECTOR-LEVEL HISTORICAL AVERAGES AND PERCENTILES")
print("="*70)

sector_stats = []
for code, name in ICB_L1_NAMES.items():
    sec = df[df['industryCode'] == code].copy()
    if len(sec) == 0:
        continue
    sec_latest = sec[sec['date'] == sec['date'].max()].iloc[0]
    sec_10yr = sec[sec['date'] >= '2016-01-01']
    sec_5yr = sec[sec['date'] >= '2021-01-01']

    cur_pe = sec_latest['pe']
    cur_pb = sec_latest['pb']

    # Historical averages (exclude 0 and NaN)
    pe_hist_10 = sec_10yr[sec_10yr['pe'] > 0]['pe'].mean()
    pb_hist_10 = sec_10yr[sec_10yr['pb'] > 0]['pb'].mean()
    pe_hist_5 = sec_5yr[sec_5yr['pe'] > 0]['pe'].mean()

    # Percentile
    if cur_pe > 0:
        pe_pct = (sec_10yr[sec_10yr['pe'] > 0]['pe'] < cur_pe).mean() * 100
    else:
        pe_pct = np.nan

    # 2022 bottom P/E
    b22 = sec[(sec['date'] >= '2022-11-01') & (sec['date'] <= '2022-12-31') & (sec['pe'] > 0)]
    pe_2022_bottom = b22['pe'].min() if len(b22) > 0 else np.nan
    b20 = sec[(sec['date'] >= '2020-03-01') & (sec['date'] <= '2020-04-30') & (sec['pe'] > 0)]
    pe_2020_bottom = b20['pe'].min() if len(b20) > 0 else np.nan

    sector_stats.append({
        'Sector': name[:35],
        'PE_now': cur_pe,
        'PB_now': cur_pb,
        'PE_10yr_avg': pe_hist_10,
        'PB_10yr_avg': pb_hist_10,
        'PE_5yr_avg': pe_hist_5,
        'PE_pct_vs10yr': pe_pct,
        'PE_2022_bot': pe_2022_bottom,
        'PE_2020_bot': pe_2020_bottom,
    })

sdf = pd.DataFrame(sector_stats)
print(sdf.to_string(index=False, float_format=lambda x: f'{x:.2f}'))

print("\n[Done — STEP 4]")
