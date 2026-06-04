"""
Vietnam Market & Sector Valuation — Bottom-up from FireAnt FA + TradingView sector data
Date: 2026-05-30
"""
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------------
# 1. LOAD FA QUARTERLY DATA — LATEST QUARTER PER SYMBOL
# -----------------------------------------------------------------------
print("="*70)
print("STEP 1: FireAnt FA quarterly — latest period per symbol")
print("="*70)

COLS = [
    'symbol', 'year', 'quarter',
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
    'financialValues_ProfitAfterTax_TTM',
    'financialValues_TotalShareHolderEquity',
    'financialValues_TotalStockHolderEquity',
    'financialValues_ShareAtPeriodEnd',
    'financialValues_MarketCapAtPeriodEnd',
    'financialValues_BookValuePerShare',
    'financialValues_SectorPE',
    'financialValues_SectorPB',
    'financialValues_SectorROE',
]

fa = pd.read_parquet('data/fireant_ssot/fa_quarterly.parquet', columns=COLS)
fa['period_num'] = fa['year'] * 10 + fa['quarter']
latest_fa = fa.sort_values('period_num').groupby('symbol').last().reset_index()

print(f"Symbols: {len(latest_fa)}")
print("Latest periods by count:")
print(latest_fa.groupby(['year','quarter'])['symbol'].count().tail(6))

# Rename for clarity
latest_fa = latest_fa.rename(columns={
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM': 'ltm_profit',
    'financialValues_ProfitAfterTax_TTM': 'ltm_profit_total',
    'financialValues_TotalShareHolderEquity': 'book_equity',
    'financialValues_TotalStockHolderEquity': 'book_equity2',
    'financialValues_ShareAtPeriodEnd': 'shares',
    'financialValues_MarketCapAtPeriodEnd': 'mc_fa',  # VND billions
    'financialValues_BookValuePerShare': 'bvps',
    'financialValues_SectorPE': 'sector_pe',
    'financialValues_SectorPB': 'sector_pb',
    'financialValues_SectorROE': 'sector_roe',
})

# Use parent company profit; fall back to total if missing
latest_fa['ltm_profit_use'] = latest_fa['ltm_profit'].where(
    latest_fa['ltm_profit'].notna(), latest_fa['ltm_profit_total']
)
# Book equity: prefer TotalShareHolderEquity
latest_fa['book_use'] = latest_fa['book_equity'].where(
    latest_fa['book_equity'].notna() & (latest_fa['book_equity'] > 0),
    latest_fa['book_equity2']
)

print("\nLTM profit stats (VND bn):")
p = latest_fa['ltm_profit_use'] / 1e9  # assumes FA is in VND, not billion
print(f"  non-null: {p.notna().sum()} | positive: {(p>0).sum()} | negative: {(p<0).sum()}")

print("\nMarket cap from FA (sample):")
mc_sample = latest_fa[latest_fa['mc_fa'].notna()][['symbol','mc_fa']].head(10)
print(mc_sample.to_string(index=False))
print("(units to be determined from data)")

# -----------------------------------------------------------------------
# 2. LOAD LATEST PRICES
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 2: Latest prices from OHLCV panel")
print("="*70)

ta = pd.read_parquet('data/fireant_ssot/ta_ohlcv_panel.parquet', columns=['symbol','date','close'])
ta['date'] = pd.to_datetime(ta['date'])
latest_price = ta.sort_values('date').groupby('symbol').last().reset_index()[['symbol','date','close']]
print(f"Symbols with price: {len(latest_price)}")
print(f"Latest date: {latest_price['date'].max().date()}")
print(f"Price unit sample (VND): {latest_price[latest_price['symbol']=='VCB']['close'].values}")

# -----------------------------------------------------------------------
# 3. LOAD TRADINGVIEW DATA FOR SECTOR CLASSIFICATION + REFERENCE P/E P/B
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 3: TradingView sector classification")
print("="*70)

import json as _json
with open(r'C:\Users\LOLII\.claude\projects\D--V-0--VN-Agent-System\1ea1e81f-b061-4463-a169-9d71a43dec43\tool-results\mcp-tradingview-mcp-server-screen_stocks-1780103864150.txt') as f:
    tv_data = _json.load(f)
tv_df = pd.DataFrame(tv_data['stocks'])
tv_df['symbol'] = tv_df['symbol'].str.replace(r'^(HOSE:|HNX:|UPCOM:)', '', regex=True)
tv_df = tv_df.rename(columns={
    'market_cap_basic': 'tv_mc',
    'price_earnings_ttm': 'tv_pe',
    'price_book_ratio': 'tv_pb',
    'return_on_equity': 'tv_roe',
    'average_volume_10d_calc': 'adtv_10d',
})
tv_df = tv_df[['symbol','close','tv_mc','tv_pe','tv_pb','tv_roe','sector','adtv_10d']].copy()
print(f"TradingView symbols: {len(tv_df)}")
print("TradingView sectors:")
print(tv_df.groupby('sector')['tv_mc'].sum().sort_values(ascending=False).head(10))

# -----------------------------------------------------------------------
# 4. MERGE: FA + OHLCV PRICE + TV SECTOR
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 4: Merge datasets")
print("="*70)

data = latest_fa.merge(latest_price, on='symbol', how='left')
data = data.merge(tv_df, on='symbol', how='left')
print(f"Merged: {len(data)} symbols")

# Determine market cap unit
# FA mc_fa: check against TV mc for known stocks
vcb = data[data['symbol'] == 'VCB'].iloc[0] if len(data[data['symbol']=='VCB']) > 0 else None
if vcb is not None:
    print(f"\nVCB check:")
    print(f"  TV market cap: {vcb['tv_mc']:.2f}")
    print(f"  FA mc_fa: {vcb['mc_fa']:.2f}")
    print(f"  FA shares: {vcb['shares']:.2f}")
    print(f"  Price: {vcb['close_x']:.0f} VND")
    if pd.notna(vcb['shares']) and vcb['shares'] > 0 and pd.notna(vcb['close_x']):
        mc_computed = vcb['close_x'] * vcb['shares']
        print(f"  Computed mc (price*shares): {mc_computed:.2f}")

# Use TV market cap as primary (it's in USD)
# TV mc is confirmed to be in USD
# FA profit unit: need to determine
# If FA profit is in VND (not billions), then P/E = (TV_mc * USDVND) / ltm_profit
# If FA profit is in VND billions, P/E = (TV_mc * USDVND) / (ltm_profit * 1e9)

# Check with a known stock: VCB LTM profit should be ~20,000 VND bn (reported)
# VCB 2024 PAT ~21,000 VND bn based on public data
USDVND = 25137  # SBV reference rate from weekly report

if vcb is not None:
    print(f"\nProfit unit check for VCB:")
    print(f"  ltm_profit_use: {vcb['ltm_profit_use']:.2f}")
    print(f"  If VND: {vcb['ltm_profit_use']/1e9:.1f} bn VND")
    print(f"  If VND bn: {vcb['ltm_profit_use']:.1f} bn VND")
    # Expected VCB LTM profit ~20,000-21,000 VND bn
    if vcb['ltm_profit_use'] > 1e12:
        print("  => Profit appears to be in VND (not billions)")
        PROFIT_UNIT = 1  # VND
    elif vcb['ltm_profit_use'] > 1000:
        print("  => Profit appears to be in VND billions")
        PROFIT_UNIT = 1e9  # multiply by 1e9 to get VND
    else:
        print("  => Profit appears to be in VND trillions")
        PROFIT_UNIT = 1e12

# -----------------------------------------------------------------------
# 5. COMPUTE P/E AND P/B
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 5: Market-cap weighted P/E and P/B")
print("="*70)

# Use TV market cap (USD) for weighting
# P/E = MC (USD) / Profit (USD)
# Profit (USD) = Profit (VND) / USDVND
# Since we use ratios, USD vs VND cancels if consistent

# Actually: P/E = Total MC / Total LTM Profit (both in same currency)
# TV mc is in USD; FA profit in VND => need to convert
# P/E = TV_mc_USD / (ltm_profit_VND / USDVND)

# Determine profit unit based on VCB check
if vcb is not None and pd.notna(vcb['ltm_profit_use']):
    if vcb['ltm_profit_use'] > 1e12:
        profit_mult = 1 / USDVND  # VND -> USD
    else:
        profit_mult = 1e9 / USDVND  # VND bn -> USD

data['profit_usd'] = data['ltm_profit_use'] * profit_mult
data['book_usd'] = data['book_use'] * profit_mult  # same conversion

# Cross-check P/E for VCB
if vcb is not None:
    vcb_row = data[data['symbol']=='VCB'].iloc[0]
    pe_check = vcb_row['tv_mc'] / vcb_row['profit_usd'] if vcb_row['profit_usd'] > 0 else np.nan
    print(f"VCB P/E cross-check: computed={pe_check:.2f}x, TV={vcb_row['tv_pe']:.2f}x")

def sector_agg(df, label=""):
    d = df.copy()
    d = d[d['tv_mc'].notna() & (d['tv_mc'] > 0)]
    total_mc = d['tv_mc'].sum()
    if total_mc == 0:
        return {}

    d_pos = d[d['profit_usd'].notna() & (d['profit_usd'] > 0)]
    total_profit = d_pos['profit_usd'].sum()
    pe = total_mc / total_profit if total_profit > 0 else np.nan
    # Using only stocks where both mc and profit positive
    pe_coverage_pct = d_pos['tv_mc'].sum() / total_mc * 100

    d_pb = d[d['book_usd'].notna() & (d['book_usd'] > 0)]
    total_book = d_pb['book_usd'].sum()
    pb = total_mc / total_book if total_book > 0 else np.nan
    pb_coverage_pct = d_pb['tv_mc'].sum() / total_mc * 100

    n_neg = (d['profit_usd'] < 0).sum()
    n_total = len(d)
    mc_neg = d[d['profit_usd'] < 0]['tv_mc'].sum()

    # Also show TV P/E as reference (where available)
    tv_pe_median = d[d['tv_pe'].notna() & (d['tv_pe'] > 0) & (d['tv_pe'] < 100)]['tv_pe'].median()
    tv_pb_median = d[d['tv_pb'].notna() & (d['tv_pb'] > 0)]['tv_pb'].median()
    tv_roe_median = d[d['tv_roe'].notna()]['tv_roe'].median()

    return {
        'label': label,
        'n_stocks': n_total,
        'mc_usd_b': total_mc / 1e9,
        'pe_agg': pe,
        'pe_coverage_pct': pe_coverage_pct,
        'pb_agg': pb,
        'pb_coverage_pct': pb_coverage_pct,
        'n_neg_earners': n_neg,
        'mc_neg_pct': mc_neg / total_mc * 100 if total_mc > 0 else 0,
        'tv_pe_median': tv_pe_median,
        'tv_pb_median': tv_pb_median,
        'tv_roe_median': tv_roe_median,
    }

# Full market aggregate
r_full = sector_agg(data, "FULL MARKET")
print(f"\n{'='*60}")
print(f"FULL MARKET AGGREGATE")
print(f"{'='*60}")
for k, v in r_full.items():
    print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

# Vin group
vin_symbols = ['VIC', 'VHM', 'VRE', 'VPL']
vin_data = data[data['symbol'].isin(vin_symbols)].copy()
non_vin = data[~data['symbol'].isin(vin_symbols)].copy()
ex_vic_vhm = data[~data['symbol'].isin(['VIC','VHM'])].copy()
ex_vin = data[~data['symbol'].isin(vin_symbols)].copy()

print(f"\n{'='*60}")
print("VIN GROUP CONTRIBUTIONS")
print(f"{'='*60}")
print(vin_data[['symbol','tv_mc','profit_usd','book_usd','tv_pe','tv_pb']].assign(
    mc_usd_b=lambda x: x['tv_mc']/1e9
)[['symbol','mc_usd_b','profit_usd','book_usd','tv_pe','tv_pb']].to_string(index=False, float_format=lambda x: f'{x:.2f}'))

total_mc = data['tv_mc'].sum()
vin_mc = vin_data['tv_mc'].sum()
print(f"\nVin group market cap: ${vin_mc/1e9:.1f}B ({vin_mc/total_mc*100:.1f}% of total)")

r_ex_vic_vhm = sector_agg(ex_vic_vhm, "EX VIC+VHM")
r_ex_vin = sector_agg(ex_vin, "EX FULL VIN")

print(f"\n{'='*60}")
print("SUMMARY: FULL vs EX-VIN")
print(f"{'='*60}")
print(f"{'Metric':<30} {'Full':>8} {'Ex VIC+VHM':>12} {'Ex Vin Group':>14}")
print("-"*66)
for metric in ['pe_agg','pb_agg','tv_pe_median','tv_pb_median','tv_roe_median','mc_usd_b']:
    v1 = r_full.get(metric, np.nan)
    v2 = r_ex_vic_vhm.get(metric, np.nan)
    v3 = r_ex_vin.get(metric, np.nan)
    def fmt(x):
        if isinstance(x, float) and not np.isnan(x):
            return f"{x:.2f}"
        return "N/A"
    print(f"  {metric:<28} {fmt(v1):>8} {fmt(v2):>12} {fmt(v3):>14}")

# -----------------------------------------------------------------------
# 6. SECTOR-LEVEL BREAKDOWN (TradingView sectors)
# -----------------------------------------------------------------------
print(f"\n{'='*70}")
print("SECTOR-LEVEL VALUATION TABLE")
print(f"{'='*70}")

TV_SECTOR_MAP = {
    'Finance': 'Financials',
    'Non-Energy Minerals': 'Materials/Steel',
    'Energy Minerals': 'Oil & Gas',
    'Utilities': 'Utilities/Power',
    'Consumer Non-Durables': 'Consumer Goods/F&B',
    'Consumer Services': 'Consumer Services/RE/Aviation',
    'Technology Services': 'Technology',
    'Retail Trade': 'Retail',
    'Distribution Services': 'Distribution/Oil Dist',
    'Transportation': 'Transport/Aviation',
    'Electronic Technology': 'Industrial Goods/Tech',
    'Process Industries': 'Chemicals/Fertilizer',
    'Industrial Services': 'Oil Services/Industrial',
    'Producer Manufacturing': 'Manufacturing',
    'Consumer Durables': 'Consumer Durables/RE',
    'Commercial Services': 'Commercial Services',
    'Health Technology': 'Healthcare',
    'Miscellaneous': 'Other',
}

results = []
for tv_sector in sorted(data['sector'].dropna().unique()):
    sdf = data[data['sector'] == tv_sector]
    if len(sdf) == 0:
        continue
    r = sector_agg(sdf)
    if not r:
        continue
    top5 = sdf.nlargest(5, 'tv_mc')['symbol'].tolist()
    r['tv_sector'] = tv_sector
    r['top5'] = ', '.join(top5)
    results.append(r)

rdf = pd.DataFrame(results).sort_values('mc_usd_b', ascending=False)
print(rdf[['tv_sector','n_stocks','mc_usd_b','pe_agg','pb_agg','tv_pe_median','tv_pb_median','tv_roe_median','n_neg_earners','top5']].to_string(
    index=False, float_format=lambda x: f'{x:.2f}'))

# -----------------------------------------------------------------------
# 7. FINANCIALS SUB-SECTOR BREAKDOWN
# -----------------------------------------------------------------------
print(f"\n{'='*70}")
print("FINANCIALS SUB-SECTOR BREAKDOWN")
print(f"{'='*70}")

# Use FA sector_pe/sector_pb which should be ICB-level aggregates
# Instead, use known ticker lists

BANKS = ['VCB','BID','CTG','TCB','VPB','MBB','ACB','STB','LPB','HDB','SHB','VIB',
         'TPB','MSB','SSB','EIB','NAB','OCB','BVB','VBB','PGB','BAB','ABB','KLB','BGB']
SECURITIES = ['SSI','VND','HCM','VCI','MBS','VIX','BSI','SHS','TVS','ORS','AGR','APS',
              'FTS','CTS','BMS','VDS','SBS','DSC','PSI','IVS']
REAL_ESTATE = ['VHM','VIC','VRE','VPL','NVL','PDR','KDH','BCM','DXG','NLG','CEO','DIG',
               'QCG','DRH','TNR','SC5','VPH','VC9','STG','CII','LDG','SJS','KHG','HQC']
INDUSTRIAL_PARKS = ['KBC','IDC','VGC','SZC','BCM','TIP','TN1','LHG','NTC','D2D','SNZ']
INSURANCE = ['BVH','PVI','BMI','BIC','MIG','PTI','PRE','VNR']

sub_groups = {
    'Banks': BANKS,
    'Securities': SECURITIES,
    'Real Estate (ex-Vin)': [s for s in REAL_ESTATE if s not in vin_symbols],
    'Real Estate (Vin only)': vin_symbols,
    'Industrial Parks': INDUSTRIAL_PARKS,
    'Insurance': INSURANCE,
}

for grp, symbols in sub_groups.items():
    sdf = data[data['symbol'].isin(symbols)]
    if len(sdf) == 0:
        print(f"  {grp}: no data")
        continue
    r = sector_agg(sdf)
    top5 = sdf.nlargest(5, 'tv_mc')['symbol'].tolist()
    print(f"\n  {grp} ({r['n_stocks']} stocks, ${r['mc_usd_b']:.1f}B)")
    print(f"    Agg P/E: {r['pe_agg']:.2f}x  |  Agg P/B: {r['pb_agg']:.2f}x  |  Median P/E: {r['tv_pe_median']:.2f}x  |  Median P/B: {r['tv_pb_median']:.2f}x")
    print(f"    Median ROE: {r['tv_roe_median']:.1f}%  |  Neg earners: {r['n_neg_earners']} ({r['mc_neg_pct']:.1f}% MC)")
    print(f"    Top 5: {top5}")

# -----------------------------------------------------------------------
# 8. KEY SECTOR GROUPS
# -----------------------------------------------------------------------
print(f"\n{'='*70}")
print("SECTOR GROUPS: OIL GAS, CHEMICALS, TRANSPORT, CONSUMER, POWER, TECH, EXPORT")
print(f"{'='*70}")

sector_groups = {
    'Oil & Gas': ['GAS','PLX','BSR','PVD','PVS','PVT','PVC','PVB','PGS','CNG','COM'],
    'Chemicals/Fertilizer': ['DPM','DCM','DGC','GVR','BFC','LAS','VAF','DDV','DDB'],
    'Transport/Logistics': ['GMD','HAH','VTP','PVT','PHP','VOS','HHR','TMS','STG'],
    'Aviation': ['ACV','HVN','VJC','SAS'],
    'Consumer/Retail': ['MWG','FRT','PNJ','DGW','PET','BHX'],
    'Consumer Goods/F&B': ['VNM','SAB','MSN','MCH','QNS','KDC','ANV','VHC','NAF','DBC','BAF'],
    'Steel/Construction': ['HPG','HSG','NKG','TLH','SMC','VGS','BMP','BCC'],
    'Power/Utilities': ['POW','GAS','REE','GEG','PC1','BWE','TDM','NT2','QTP','PPC','HND'],
    'Technology/Telecom': ['FPT','CMG','ELC','SGT','VGI','CTR','VTC','FOX','GEE'],
    'Industrial Goods/Elec': ['GEX','PC1','REE','TV2','CAV','SAM','TBC','LEC'],
    'Seafood Export': ['VHC','ANV','IDI','FMC','ACL','HVG'],
    'Textile Export': ['TNG','MSH','TCM','GIL','KMT','STK'],
}

print(f"\n{'Sector Group':<30} {'N':>4} {'MC$B':>8} {'PE_agg':>8} {'PB_agg':>8} {'PE_med':>8} {'Top 3'}")
print("-"*90)
for grp, symbols in sector_groups.items():
    sdf = data[data['symbol'].isin(symbols)]
    if len(sdf) == 0:
        continue
    r = sector_agg(sdf)
    top3 = sdf.nlargest(3, 'tv_mc')['symbol'].tolist()
    pe_fmt = f"{r['pe_agg']:.1f}x" if not np.isnan(r.get('pe_agg', np.nan)) else 'N/A'
    pb_fmt = f"{r['pb_agg']:.2f}x" if not np.isnan(r.get('pb_agg', np.nan)) else 'N/A'
    pe_med = f"{r['tv_pe_median']:.1f}x" if not np.isnan(r.get('tv_pe_median', np.nan)) else 'N/A'
    mc_fmt = f"{r['mc_usd_b']:.1f}"
    print(f"  {grp:<28} {r['n_stocks']:>4} {mc_fmt:>8} {pe_fmt:>8} {pb_fmt:>8} {pe_med:>8}  {top3}")

print("\n[DONE]")
