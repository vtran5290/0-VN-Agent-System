"""
Quick verification of VinaCapital/Kokalari claims (KTSG article 2026-06-04)
Claims to check:
  1. >70% of stocks trading below P/E 10x
  2. Vingroup ecosystem ~30% of VN-Index market cap
  3. Q1 2026 NPAT growth +51% YoY (listed companies); ex-VHM +30%
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

USDVND = 25137

# ── Load FA data ─────────────────────────────────────────────────────────────
COLS = ['symbol','year','quarter',
        'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
        'financialValues_ProfitAfterTax_TTM',
        'financialValues_ShareAtPeriodEnd',
        'financialValues_MarketCapAtPeriodEnd']

fa = pd.read_parquet('data/fireant_ssot/fa_quarterly.parquet', columns=COLS)
fa = fa.rename(columns={
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM': 'ltm_profit',
    'financialValues_ProfitAfterTax_TTM': 'ltm_profit_total',
    'financialValues_ShareAtPeriodEnd': 'shares',
    'financialValues_MarketCapAtPeriodEnd': 'mc_fa',
})
fa['ltm'] = fa['ltm_profit'].where(fa['ltm_profit'].notna(), fa['ltm_profit_total'])
fa['period_num'] = fa['year'] * 10 + fa['quarter']
latest = fa.sort_values('period_num').groupby('symbol').last().reset_index()

# ── Load latest prices ────────────────────────────────────────────────────────
ta = pd.read_parquet('data/fireant_ssot/ta_ohlcv_panel.parquet', columns=['symbol','date','close'])
ta['date'] = pd.to_datetime(ta['date'])
lp = ta.sort_values('date').groupby('symbol').last().reset_index()[['symbol','date','close']]

m = latest.merge(lp, on='symbol', how='inner')
m = m[m['shares'].notna() & (m['shares'] > 0) & m['close'].notna() & (m['close'] > 0)]
m['mc_vnd'] = m['close'] * 1000 * m['shares']   # VND (close stored in VND/1000)
m['mc_usd'] = m['mc_vnd'] / USDVND

# ─────────────────────────────────────────────────────────────────────────────
# CLAIM 1: >70% of stocks trading below P/E 10x
# ─────────────────────────────────────────────────────────────────────────────
print("="*65)
print("CLAIM 1: >70% of stocks trading below P/E 10x")
print("="*65)

pe_df = m[m['ltm'].notna() & (m['ltm'] != 0)].copy()
pe_df['pe'] = m['mc_vnd'] / pe_df['ltm']

# Exclude extreme outliers
pe_valid = pe_df[(pe_df['pe'] > 0) & (pe_df['pe'] < 200)].copy()
pe_neg   = pe_df[pe_df['ltm'] < 0].copy()    # loss-making: excluded from valid P/E

total_universe = len(m)
n_loss     = len(pe_df[pe_df['ltm'] < 0])
n_pe_valid = len(pe_valid)
n_below10  = (pe_valid['pe'] < 10).sum()
n_below12  = (pe_valid['pe'] < 12).sum()

print(f"Total symbols w/ price+FA: {total_universe}")
print(f"  Loss-making (ltm < 0): {n_loss} ({n_loss/total_universe*100:.0f}%)")
print(f"  P/E valid [0-200x]:    {n_pe_valid}")
print(f"  P/E < 10x:             {n_below10} ({n_below10/n_pe_valid*100:.0f}% of valid P/E stocks)")
print(f"  P/E < 12x:             {n_below12} ({n_below12/n_pe_valid*100:.0f}% of valid P/E stocks)")

# As % of total universe (incl loss-makers — they could be considered "not expensive")
n_below10_or_loss = n_below10 + n_loss
print(f"  P/E < 10x OR loss-making: {n_below10_or_loss} ({n_below10_or_loss/total_universe*100:.0f}% of all stocks)")
print()
print("P/E distribution of valid-P/E stocks:")
bins = [0,5,8,10,12,15,20,30,50,200]
labels = ['0-5','5-8','8-10','10-12','12-15','15-20','20-30','30-50','50+']
pe_valid['bucket'] = pd.cut(pe_valid['pe'], bins=bins, labels=labels)
dist = pe_valid['bucket'].value_counts().sort_index()
for bucket, count in dist.items():
    pct = count/n_pe_valid*100
    bar = '#' * int(pct/2)
    print(f"  {bucket:>6}x: {count:>4} ({pct:5.1f}%) {bar}")

# ─────────────────────────────────────────────────────────────────────────────
# CLAIM 2: Vingroup ecosystem ~30% of VN-Index market cap
# ─────────────────────────────────────────────────────────────────────────────
print()
print("="*65)
print("CLAIM 2: Vingroup ecosystem ~30% of VN-Index market cap")
print("="*65)

# Known Vingroup-related listed tickers (HOSE/HNX)
# Core: VIC, VHM, VRE, VPL (VinPearl not yet publicly listed as of 2026)
# Related: check if VFS listed in Vietnam (typically NYSE)
VIN_CORE   = ['VIC', 'VHM', 'VRE', 'VPL']
VIN_BROAD  = ['VIC', 'VHM', 'VRE', 'VPL', 'VGI', 'VHH']  # add any known VIN-linked

total_mc = m['mc_usd'].sum()
for grp, syms in [('VIN_CORE (VIC+VHM+VRE+VPL)', VIN_CORE), ('VIN_BROAD (+ VGI+VHH)', VIN_BROAD)]:
    sub = m[m['symbol'].isin(syms)]
    sub_mc = sub['mc_usd'].sum()
    print(f"  {grp}:")
    for _, row in sub.sort_values('mc_usd', ascending=False).iterrows():
        print(f"    {row['symbol']}: ${row['mc_usd']/1e9:.1f}B")
    print(f"    Total: ${sub_mc/1e9:.1f}B = {sub_mc/total_mc*100:.1f}% of all-listed MC")
    print()

print(f"  All listed MC (computed): ${total_mc/1e9:.0f}B")

# The VN-Index is a subset (HOSE-listed, adjusted float weights)
# Check top-200 as proxy
top200 = m.nlargest(200, 'mc_usd')
top200_mc = top200['mc_usd'].sum()
for grp, syms in [('VIN_CORE top200', VIN_CORE)]:
    sub = top200[top200['symbol'].isin(syms)]
    sub_mc = sub['mc_usd'].sum()
    print(f"  {grp}: ${sub_mc/1e9:.1f}B = {sub_mc/top200_mc*100:.1f}% of top-200 MC")

# ─────────────────────────────────────────────────────────────────────────────
# CLAIM 3: Q1 2026 NPAT growth +51% YoY; ex-VHM +30%
# ─────────────────────────────────────────────────────────────────────────────
print()
print("="*65)
print("CLAIM 3: Q1 2026 NPAT growth +51% YoY; ex-VHM +30%")
print("="*65)

# Need quarterly profit (not TTM) — approximate from TTM change or look for quarterly field
# Method: use TTM at Q1 2026 vs TTM at Q1 2025 as proxy
# Q1 2026 = year=2026, quarter=1
# Q1 2025 = year=2025, quarter=1

fa_raw = pd.read_parquet('data/fireant_ssot/fa_quarterly.parquet',
    columns=['symbol','year','quarter',
             'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
             'financialValues_ProfitAfterTax_TTM'])
fa_raw = fa_raw.rename(columns={
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM': 'ltm',
    'financialValues_ProfitAfterTax_TTM': 'ltm_total',
})
fa_raw['ltm_use'] = fa_raw['ltm'].where(fa_raw['ltm'].notna(), fa_raw['ltm_total'])

q1_2026 = fa_raw[(fa_raw['year']==2026) & (fa_raw['quarter']==1)][['symbol','ltm_use']].rename(columns={'ltm_use':'ltm_26Q1'})
q1_2025 = fa_raw[(fa_raw['year']==2025) & (fa_raw['quarter']==1)][['symbol','ltm_use']].rename(columns={'ltm_use':'ltm_25Q1'})

growth = q1_2026.merge(q1_2025, on='symbol', how='inner')
growth = growth[growth['ltm_26Q1'].notna() & growth['ltm_25Q1'].notna()]
growth = growth[growth['ltm_25Q1'] > 0]  # only where last year positive (meaningful YoY)

total_ltm_26 = growth['ltm_26Q1'].sum()
total_ltm_25 = growth['ltm_25Q1'].sum()
yoy_all = (total_ltm_26 - total_ltm_25) / total_ltm_25 * 100

growth_exvhm = growth[growth['symbol'] != 'VHM']
ex_26 = growth_exvhm['ltm_26Q1'].sum()
ex_25 = growth_exvhm['ltm_25Q1'].sum()
yoy_exvhm = (ex_26 - ex_25) / ex_25 * 100

print(f"NOTE: Using TTM profit change Q1-2026 vs Q1-2025 as proxy for annual LTM growth")
print(f"(Article claims quarterly NPAT Q1/2026 vs Q1/2025 — TTM is a smoothed proxy)")
print()
print(f"  Matched symbols: {len(growth)}")
print(f"  TTM profit sum Q1-26: {total_ltm_26/1e12:.1f} tn VND")
print(f"  TTM profit sum Q1-25: {total_ltm_25/1e12:.1f} tn VND")
print(f"  YoY LTM growth (all listed): {yoy_all:+.1f}%")
print(f"  YoY LTM growth (ex-VHM):     {yoy_exvhm:+.1f}%")
print()
print(f"  VHM contribution check:")
vhm = growth[growth['symbol']=='VHM']
if len(vhm) > 0:
    vhm_ltm_26 = vhm['ltm_26Q1'].values[0]
    vhm_ltm_25 = vhm['ltm_25Q1'].values[0]
    print(f"    VHM LTM Q1-26: {vhm_ltm_26/1e9:.0f} bn VND")
    print(f"    VHM LTM Q1-25: {vhm_ltm_25/1e9:.0f} bn VND")
    print(f"    VHM LTM growth: {(vhm_ltm_26-vhm_ltm_25)/vhm_ltm_25*100:+.0f}%")

# ─────────────────────────────────────────────────────────────────────────────
# QUICK MARKET CONTEXT
# ─────────────────────────────────────────────────────────────────────────────
print()
print("="*65)
print("MARKET CONTEXT (for Opus briefing)")
print("="*65)
print(f"Total listed universe: {len(m)} symbols | MC=${m['mc_usd'].sum()/1e9:.0f}B")
print(f"Latest price date:     {lp['date'].max().date()}")
print(f"Latest FA period:      {latest.sort_values('period_num')['period_num'].max()}")

# Median P/E
med_pe = pe_valid['pe'].median()
print(f"Median P/E (valid):    {med_pe:.1f}x  (cap-wtd agg: ~14.4x)")
print(f"Mean P/E  (valid):     {pe_valid['pe'].mean():.1f}x")
