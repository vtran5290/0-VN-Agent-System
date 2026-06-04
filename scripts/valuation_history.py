"""
Historical VN-Index P/E and P/B at cycle bottoms — from FireAnt FA + OHLCV
Uses: ltm_profit (VND), bvps (VND/share), shares (count), price (VND thousands in OHLCV)
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')

FA_COLS = ['symbol','year','quarter',
           'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
           'financialValues_ProfitAfterTax_TTM',
           'financialValues_BookValuePerShare',
           'financialValues_ShareAtPeriodEnd']
fa = pd.read_parquet('data/fireant_ssot/fa_quarterly.parquet', columns=FA_COLS)
fa = fa.rename(columns={
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM': 'ltm_profit',
    'financialValues_ProfitAfterTax_TTM': 'ltm_profit_total',
    'financialValues_BookValuePerShare': 'bvps',
    'financialValues_ShareAtPeriodEnd': 'shares',
})
fa['ltm'] = fa['ltm_profit'].where(fa['ltm_profit'].notna(), fa['ltm_profit_total'])

ta = pd.read_parquet('data/fireant_ssot/ta_ohlcv_panel.parquet', columns=['symbol','date','close'])
ta['date'] = pd.to_datetime(ta['date'])

vnindex = pd.read_parquet('data/fireant_ssot/ta_vnindex.parquet').reset_index()
vnindex.columns = [c.lower() for c in vnindex.columns]
vnindex['date'] = pd.to_datetime(vnindex['date'])

def compute_snapshot(price_d1, price_d2, fa_year, fa_qtr, label):
    fa_period = fa[(fa['year']==fa_year) & (fa['quarter']==fa_qtr)].copy()
    if len(fa_period) == 0:
        print(f"  {label}: no FA data for {fa_year}Q{fa_qtr}")
        return

    price_w = ta[(ta['date'] >= price_d1) & (ta['date'] <= price_d2)]
    price_low = price_w.groupby('symbol')['close'].min().reset_index().rename(columns={'close': 'price_lo'})

    m = fa_period.merge(price_low, on='symbol', how='inner')
    m = m[m['shares'].notna() & (m['shares'] > 0) & m['price_lo'].notna() & (m['price_lo'] > 0)]

    # price_lo is in VND (stored as VND, not thousands — confirm from VCB=62 meaning 62,000 VND)
    # Actually: close=62 for VCB at 62,000 VND => stored in thousands VND => multiply by 1000
    m['mc'] = m['price_lo'] * 1000 * m['shares']  # VND

    # Profit in VND (raw)
    total_mc = m['mc'].sum()
    pos = m[m['ltm'].notna() & (m['ltm'] > 0)]
    pe = pos['mc'].sum() / pos['ltm'].sum() if pos['ltm'].sum() > 0 else np.nan
    n_neg = (m['ltm'].fillna(0) < 0).sum()

    # P/B: use bvps (VND/share) * shares
    pb_df = m[m['bvps'].notna() & (m['bvps'] > 100)]  # bvps > 100 VND (filter junk)
    pb_df = pb_df.copy()
    pb_df['book'] = pb_df['bvps'] * pb_df['shares']
    pb = pb_df['mc'].sum() / pb_df['book'].sum() if pb_df['book'].sum() > 0 else np.nan

    # VN-Index
    vni_w = vnindex[(vnindex['date'] >= price_d1) & (vnindex['date'] <= price_d2)]
    vni_lo = vni_w['close'].min() if len(vni_w) > 0 else np.nan

    print(f"  {label}: VNI_low={vni_lo:.0f}, N={len(m)}, PE={pe:.2f}x, PB={pb:.2f}x, "
          f"neg_earners={n_neg} ({n_neg/len(m)*100:.0f}%)")
    return {'label': label, 'vni_low': vni_lo, 'pe': pe, 'pb': pb, 'n': len(m)}

print("VN-Index Historical P/E and P/B at Cycle Bottoms (FireAnt FA data)")
print("="*70)
print("NOTE: P/E = market-cap weighted, excl. negative earners")
print("NOTE: P/B = book-value-per-share method, all positive-BVPS stocks")
print()

snapshots = [
    ("2016-01-20", "2016-02-05", 2015, 3, "2016 bottom (Jan 2016)"),
    ("2020-03-19", "2020-03-25", 2019, 4, "2020 Covid bottom (Mar 2020)"),
    ("2022-11-10", "2022-11-16", 2022, 3, "2022 crisis bottom (Nov 2022)"),
    ("2026-05-20", "2026-05-29", 2025, 4, "Current May 2026"),
]

results = []
for d1, d2, yr, qtr, lbl in snapshots:
    r = compute_snapshot(d1, d2, yr, qtr, lbl)
    if r:
        results.append(r)

print()
print("ChatGPT claims vs our calculation:")
print(f"{'Period':<30} {'ChatGPT P/E':>12} {'Our P/E':>10} {'ChatGPT P/B':>12} {'Our P/B':>10}")
print("-"*80)
claims = {
    "2009 bottom": (10.46, 1.24),
    "2012 bottom": (7.41, 1.25),
    "2016 bottom": (12.71, 1.78),
    "2020 Covid": (10.45, 1.65),
    "2022 crisis": (9.98, 1.71),
}
label_map = {
    "2016 bottom (Jan 2016)": "2016 bottom",
    "2020 Covid bottom (Mar 2020)": "2020 Covid",
    "2022 crisis bottom (Nov 2022)": "2022 crisis",
    "Current May 2026": "Current",
}
for r in results:
    cg_label = label_map.get(r['label'])
    if cg_label and cg_label in claims:
        cg_pe, cg_pb = claims[cg_label]
        print(f"  {r['label']:<28} {cg_pe:>12.2f}x {r['pe']:>9.2f}x {cg_pb:>12.2f}x {r['pb']:>9.2f}x")
    else:
        print(f"  {r['label']:<28} {'N/A':>12} {r['pe']:>9.2f}x {'N/A':>12} {r['pb']:>9.2f}x")
