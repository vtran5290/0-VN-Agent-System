import pandas as pd, numpy as np
panel = pd.read_parquet('data/research/ema_cloud/ohlcv_panel_cache.parquet')
panel['date'] = pd.to_datetime(panel['date'])
print('Full range:', panel['date'].min().date(), 'to', panel['date'].max().date())
print('Symbols:', panel['symbol'].nunique(), '  Rows:', len(panel))
for yr in [2018,2019,2020,2021,2022,2023,2024,2025,2026]:
    s = panel[panel['date'].dt.year == yr]
    print(f'  {yr}: {s["symbol"].nunique()} syms, {len(s)} rows')
ca = ['VIC','VHM','VRE','VGI','SAB','L40','TCH','VGC','MSN']
print()
for sym in ca:
    s = panel[panel['symbol']==sym]
    if len(s):
        d = s.sort_values('date')
        c = d['close'].values.astype(float)
        gaps = []
        for i in range(1,len(c)):
            if c[i-1]>0:
                g = c[i]/c[i-1]-1
                if abs(g)>=0.15:
                    gaps.append(round(g*100,1))
        print(f'  {sym}: {s["date"].min().date()} to {s["date"].max().date()}, {len(s)} rows, gaps>=15pct: {len(gaps)} {gaps[:5]}')
    else:
        print(f'  {sym}: NOT IN PANEL')

# Check phase5 OOS top contributors
import json
try:
    df = pd.read_csv('data/research/gk_audit/phase5/phase5_walk_forward.csv')
    print('\nWalk-forward file loaded, cols:', list(df.columns)[:10])
except Exception as e:
    print('WF file error:', e)
try:
    df = pd.read_csv('data/research/gk_audit/phase5/phase5_summary.csv')
    print('Summary arms:', df['arm_id'].tolist())
except Exception as e:
    print('Summary error:', e)
