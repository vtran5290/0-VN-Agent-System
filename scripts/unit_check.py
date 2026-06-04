import pandas as pd, numpy as np

FA_COLS = ['symbol','year','quarter',
           'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
           'financialValues_TotalShareHolderEquity',
           'financialValues_ShareAtPeriodEnd',
           'financialValues_MarketCapAtPeriodEnd',
           'financialValues_BookValuePerShare']
fa = pd.read_parquet('data/fireant_ssot/fa_quarterly.parquet', columns=FA_COLS)
fa = fa.rename(columns={
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM':'ltm_profit',
    'financialValues_TotalShareHolderEquity':'book_eq',
    'financialValues_ShareAtPeriodEnd':'shares',
    'financialValues_MarketCapAtPeriodEnd':'mc_fa',
    'financialValues_BookValuePerShare':'bvps',
})

for sym in ['VCB','HPG','FPT','VNM']:
    sub = fa[fa['symbol']==sym].sort_values(['year','quarter']).tail(2)
    if len(sub) == 0:
        continue
    row = sub.iloc[-1]
    print(f"\n{sym} ({int(row['year'])}Q{int(row['quarter'])})")
    print(f"  ltm_profit: {row['ltm_profit']:.2e}")
    print(f"  book_eq:    {row['book_eq']:.2e}")
    print(f"  shares:     {row['shares']:.2e}")
    print(f"  mc_fa:      {row['mc_fa']:.2e}")
    print(f"  bvps:       {row['bvps']:.2f}")

    # Determine units
    if row['ltm_profit'] > 1e11:
        p_unit = 'VND (raw)'
        p_bn = row['ltm_profit'] / 1e9
    else:
        p_unit = 'VND bn'
        p_bn = row['ltm_profit']
    print(f"  => profit ~{p_bn:.0f} bn VND ({p_unit})")

    if row['book_eq'] > 1e11:
        bq_unit = 'VND (raw)'
        bq_bn = row['book_eq'] / 1e9
    else:
        bq_unit = 'VND bn'
        bq_bn = row['book_eq']
    print(f"  => book_eq ~{bq_bn:.0f} bn VND ({bq_unit})")

    # bvps in VND
    if row['bvps'] > 1000:
        print(f"  => bvps likely in VND: {row['bvps']:.0f}")
    else:
        print(f"  => bvps: {row['bvps']:.2f}")

    # Compute P/B from bvps and price
    # If bvps is in VND and shares available, book_total = bvps * shares
    if pd.notna(row['bvps']) and row['bvps'] > 100 and pd.notna(row['shares']) and row['shares'] > 0:
        implied_book = row['bvps'] * row['shares']
        print(f"  => implied_book (bvps*shares): {implied_book:.2e}")
        if pd.notna(row['book_eq']):
            ratio = implied_book / row['book_eq']
            print(f"  => ratio implied_book / book_eq: {ratio:.2f} (expect 1.0 if same units)")
