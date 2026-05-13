import pandas as pd
for s in ['VIC','VHM','VRE','VPL']:
    for path in [f'data/stocks/{s}.csv', f'minervini_backtest/data/raw/{s}.csv']:
        try:
            df = pd.read_csv(path)
            print(f'{path:>45}: rows={len(df):5d}  first={df["date"].min()}  last={df["date"].max()}')
        except Exception as e:
            print(f'{path:>45}: MISSING ({e.__class__.__name__})')
