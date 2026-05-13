import pandas as pd
import json

# Check VIC close at 2026-03-16
for path in ['data/stocks/VIC.csv', 'minervini_backtest/data/raw/VIC.csv']:
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    row = df[df['date'] == '2026-03-16']
    if not row.empty:
        print(f"{path}: close={row['close'].iloc[0]}, vol={row['volume'].iloc[0]}")

# Quarterly shares for VIC at 2025-Q4 and 2026-Q1
df = pd.read_parquet('data/fireant_exports/financials/all_financial_data_quarterly_2016Q1_2026Q2.parquet')
sub = df[(df['symbol'].isin(['VIC','VHM','VRE'])) & (df['year'] >= 2025)][['symbol','year','quarter','financialValues_ShareAtPeriodEnd']]
print(sub.to_string(index=False))

# Snapshot
snap = json.loads(open('artifacts/vnindex_ex_vin_result.json', 'r', encoding='utf-8').read())
print(json.dumps(snap, indent=2))

# Compute manual cap_VIN_3sym at 2026-03-16 from CSV closes (assumed thousand VND) and shares
CLOSES = {}
SHARES = {'VIC': 3823661561.0, 'VHM': 4354200000.0, 'VRE': 2272318410.0}  # placeholders, will pull from actual quarterly
for s in ['VIC','VHM','VRE']:
    df = pd.read_csv(f'minervini_backtest/data/raw/{s}.csv')
    df['date'] = pd.to_datetime(df['date'])
    row = df[df['date'] == '2026-03-16']
    if not row.empty:
        CLOSES[s] = float(row['close'].iloc[0])
        print(f"{s} close on 2026-03-16: {CLOSES[s]}")
print("CLOSES:", CLOSES)
