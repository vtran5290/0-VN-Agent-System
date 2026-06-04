"""
Vietnam Market & Sector Valuation — Bottom-up calculation from FireAnt FA data
Date: 2026-05-30
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------
FA_QUARTERLY = 'data/fireant_ssot/fa_quarterly.parquet'
TA_OHLCV = 'data/fireant_ssot/ta_ohlcv_panel.parquet'
TA_VNINDEX = 'data/fireant_ssot/ta_vnindex.parquet'

ICB_L1_MAP = {
    'O': 'Oil & Gas',
    1000: 'Basic Materials',
    2000: 'Industrials',
    3000: 'Consumer Goods',
    4000: 'Healthcare',
    5000: 'Consumer Services',
    6000: 'Telecom',
    7000: 'Utilities',
    8000: 'Financials',
    9000: 'Technology',
}

# -----------------------------------------------------------------------
# 1. LOAD FA QUARTERLY DATA
# -----------------------------------------------------------------------
print("Loading FA quarterly data...")
fa = pd.read_parquet(FA_QUARTERLY, columns=[
    'symbol', 'year', 'quarter', 'icbCode', 'icbName', 'companyType',
    'financialValues_ParentCompanyShareholderProfitAfterTax_TTM',
    'financialValues_ProfitAfterTax_TTM',
    'balanceSheetValues_TotalOwnersEquity',
    'balanceSheetValues_ParentCompanyShareholdersEquity',
    'fundamentalsValues_OutstandingShare',
    'fundamentalsValues_PE',
    'fundamentalsValues_PB',
    'fundamentalsValues_ROE',
    'fundamentalsValues_MarketCap',
])

print(f"Shape: {fa.shape}")
print(f"Period range: {fa['year'].min()} Q{fa['quarter'].min()} to {fa['year'].max()} Q{fa['quarter'].max()}")

# -----------------------------------------------------------------------
# 2. GET LATEST QUARTER PER SYMBOL
# -----------------------------------------------------------------------
fa['period_num'] = fa['year'] * 10 + fa['quarter']
latest_fa = fa.sort_values('period_num').groupby('symbol').last().reset_index()
print(f"\nSymbols with latest FA data: {len(latest_fa)}")

# Show period distribution
period_dist = fa.groupby(['year','quarter'])['symbol'].count().reset_index()
print("Latest 6 periods:")
print(period_dist.tail(6).to_string(index=False))

# -----------------------------------------------------------------------
# 3. LOAD LATEST PRICES FROM OHLCV
# -----------------------------------------------------------------------
print("\nLoading latest OHLCV prices...")
# Read only last 5 dates to get current price
ta = pd.read_parquet(TA_OHLCV, columns=['symbol','date','close','volume'])
ta['date'] = pd.to_datetime(ta['date'])
latest_price = ta.sort_values('date').groupby('symbol').last().reset_index()[['symbol','date','close','volume']]
print(f"Symbols with price data: {len(latest_price)}")
print(f"Latest price date: {latest_price['date'].max().date()}")

# -----------------------------------------------------------------------
# 4. MERGE FA + PRICE
# -----------------------------------------------------------------------
data = latest_fa.merge(latest_price, on='symbol', how='inner')
print(f"\nMerged dataset: {data.shape[0]} symbols")

# -----------------------------------------------------------------------
# 5. COMPUTE MARKET CAP
# -----------------------------------------------------------------------
# Use fundamentalsValues_MarketCap if available (in VND billion from FireAnt)
# Otherwise compute from price * shares
data['shares'] = data['fundamentalsValues_OutstandingShare']
data['price'] = data['close']

# FireAnt marketCap may be in VND billions
data['mc_fa'] = data['fundamentalsValues_MarketCap']  # VND billions
data['mc_computed'] = data['price'] * data['shares']  # VND

# Use FA market cap if available, otherwise compute
data['market_cap_vnd'] = np.where(
    data['mc_fa'].notna() & (data['mc_fa'] > 0),
    data['mc_fa'] * 1e9,  # convert VND billions to VND
    np.where(data['shares'].notna() & (data['shares'] > 0),
             data['price'] * data['shares'],
             np.nan)
)

print("\nMarket cap sample (VND bn):")
print(data[['symbol','price','shares','mc_fa','market_cap_vnd']].head(10).assign(
    mc_vnd_bn=data['market_cap_vnd']/1e9).to_string())

# -----------------------------------------------------------------------
# 6. COMPUTE AGGREGATES
# -----------------------------------------------------------------------
# LTM Net Profit = parent company shareholder profit TTM
data['ltm_profit'] = data['financialValues_ParentCompanyShareholderProfitAfterTax_TTM']
# Book equity
data['book_equity'] = data['balanceSheetValues_ParentCompanyShareholdersEquity']
if data['book_equity'].isna().all():
    data['book_equity'] = data['balanceSheetValues_TotalOwnersEquity']

# Flag negatives
data['profit_negative'] = data['ltm_profit'] < 0

print(f"\nSymbols with LTM profit data: {data['ltm_profit'].notna().sum()}")
print(f"Symbols with negative LTM profit: {data['profit_negative'].sum()}")
print(f"Symbols with book equity data: {data['book_equity'].notna().sum()}")

# -----------------------------------------------------------------------
# 7. EXTRACT ICB L1 FROM ICB CODE
# -----------------------------------------------------------------------
def get_icb_l1(code):
    if pd.isna(code):
        return None
    try:
        c = int(str(code).strip())
        if c < 1000:
            return 'Oil & Gas'
        elif c < 2000:
            return 'Basic Materials'
        elif c < 3000:
            return 'Industrials'
        elif c < 4000:
            return 'Consumer Goods'
        elif c < 5000:
            return 'Healthcare'
        elif c < 6000:
            return 'Consumer Services'
        elif c < 7000:
            return 'Telecom'
        elif c < 8000:
            return 'Utilities'
        elif c < 9000:
            return 'Financials'
        elif c < 10000:
            return 'Technology'
        else:
            return 'Other'
    except:
        return str(code)

data['icb_l1'] = data['icbCode'].apply(get_icb_l1)
print("\nICB L1 distribution:")
print(data.groupby('icb_l1')['market_cap_vnd'].sum().sort_values(ascending=False).apply(
    lambda x: f"{x/1e12:.1f}T VND" if pd.notna(x) else "N/A"
))

# -----------------------------------------------------------------------
# 8. INDEX-LEVEL P/E AND P/B
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("VN-INDEX AGGREGATE VALUATION (MARKET-CAP WEIGHTED)")
print("="*70)

def agg_pe_pb(df, label=""):
    """Compute market-cap weighted P/E and P/B"""
    d = df.copy()
    d = d[d['market_cap_vnd'].notna() & (d['market_cap_vnd'] > 0)]

    total_mc = d['market_cap_vnd'].sum()

    # P/E: excluding negative earners version
    d_pos = d[d['ltm_profit'].notna() & (d['ltm_profit'] > 0)]
    d_neg = d[d['ltm_profit'].notna() & (d['ltm_profit'] < 0)]

    pe_excl_neg = d_pos['market_cap_vnd'].sum() / d_pos['ltm_profit'].sum() if d_pos['ltm_profit'].sum() > 0 else np.nan
    # P/E including negatives (net basis)
    d_all_p = d[d['ltm_profit'].notna()]
    total_profit_all = d_all_p['ltm_profit'].sum()
    pe_incl_neg = d_all_p['market_cap_vnd'].sum() / total_profit_all if total_profit_all > 0 else np.nan

    # P/B
    d_pb = d[d['book_equity'].notna() & (d['book_equity'] > 0)]
    pb = d_pb['market_cap_vnd'].sum() / d_pb['book_equity'].sum() if d_pb['book_equity'].sum() > 0 else np.nan

    # Coverage
    n_total = len(d)
    n_pe = len(d_pos)
    n_pb = len(d_pb)

    if label:
        print(f"\n{label}")
        print(f"  Stocks: {n_total} | With +profit: {n_pe} | With book eq: {n_pb}")
        print(f"  Market Cap: {total_mc/1e12:.1f}T VND")
        print(f"  LTM P/E (excl negatives): {pe_excl_neg:.2f}x")
        print(f"  LTM P/E (incl negatives, net): {pe_incl_neg:.2f}x")
        print(f"  LTM P/B: {pb:.2f}x")
        mc_neg = d_neg['market_cap_vnd'].sum()
        print(f"  Negative earners mktcap: {mc_neg/1e12:.1f}T VND ({mc_neg/total_mc*100:.1f}%)")

    return {'pe_excl': pe_excl_neg, 'pe_incl': pe_incl_neg, 'pb': pb,
            'total_mc_t': total_mc/1e12, 'n': n_total}

# Full market
r_full = agg_pe_pb(data, "FULL MARKET (All HOSE+HNX+UPCoM FA coverage)")

# VN-Index proxy: HOSE-listed, market cap > threshold
# Note: VN-Index includes ~416 HOSE stocks, cap-weighted
# We'll filter by exchange (HOSE tickers don't have HNX/UPCoM prefix)
# In the FA data, icbCode should indicate exchange... let's use symbol pattern
# HNX stocks often in uppercase 3-char, UPCOM listed in UPCOM
# Best proxy: all symbols in TA OHLCV panel that are HOSE

# Vin group: VIC, VHM, VRE, VPL
vin_group = ['VIC', 'VHM', 'VRE', 'VPL']
data_ex_vic_vhm = data[~data['symbol'].isin(['VIC', 'VHM'])]
data_ex_vin = data[~data['symbol'].isin(vin_group)]

r_ex_vic_vhm = agg_pe_pb(data_ex_vic_vhm, "EX VIC + VHM")
r_ex_vin = agg_pe_pb(data_ex_vin, "EX FULL VIN GROUP (VIC, VHM, VRE, VPL)")

# Vin group contribution
vin_data = data[data['symbol'].isin(vin_group)]
print("\nVin Group Constituent Data:")
print(vin_data[['symbol','market_cap_vnd','ltm_profit','book_equity']].assign(
    mc_bn=lambda x: x['market_cap_vnd']/1e9,
    profit_bn=lambda x: x['ltm_profit']/1e9
)[['symbol','mc_bn','profit_bn']].to_string())

# -----------------------------------------------------------------------
# 9. SECTOR-LEVEL P/E AND P/B
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("SECTOR-LEVEL VALUATION (MARKET-CAP WEIGHTED)")
print("="*70)

sector_results = []
for sector in sorted(data['icb_l1'].dropna().unique()):
    sdf = data[data['icb_l1'] == sector]
    r = agg_pe_pb(sdf)
    # Also compute from fundamentalsValues_PE (if populated)
    fa_pe = sdf[sdf['fundamentalsValues_PE'].notna() & (sdf['fundamentalsValues_PE'] > 0) & (sdf['fundamentalsValues_PE'] < 200)]['fundamentalsValues_PE'].median()
    fa_pb = sdf[sdf['fundamentalsValues_PB'].notna() & (sdf['fundamentalsValues_PB'] > 0)]['fundamentalsValues_PB'].median()
    fa_roe = sdf[sdf['fundamentalsValues_ROE'].notna()]['fundamentalsValues_ROE'].median()
    n_names = len(sdf)
    top5 = sdf.nlargest(5, 'market_cap_vnd')['symbol'].tolist()
    sector_results.append({
        'Sector': sector,
        'N': n_names,
        'MC_TVND': r['total_mc_t'],
        'PE_agg': r['pe_excl'],
        'PB_agg': r['pb'],
        'PE_median': fa_pe,
        'PB_median': fa_pb,
        'ROE_median': fa_roe,
        'Top5': ', '.join(top5),
    })

sdf_result = pd.DataFrame(sector_results).sort_values('MC_TVND', ascending=False)
print(sdf_result.to_string(index=False, float_format=lambda x: f'{x:.2f}'))

# -----------------------------------------------------------------------
# 10. DETAILED SECTOR BREAKDOWN — FINANCIALS (sub-sectors)
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("FINANCIALS SECTOR BREAKDOWN (Banks vs Securities vs RE vs Insurance)")
print("="*70)

fin_data = data[data['icb_l1'] == 'Financials'].copy()

def get_fin_subsector(row):
    code = row['icbCode']
    name = str(row.get('icbName', '')).lower()
    try:
        c = int(str(code).strip())
        if 8300 <= c < 8400:
            return 'Banks'
        elif 8500 <= c < 8600:
            return 'Insurance'
        elif 8600 <= c < 8700:
            return 'Real Estate'
        elif 8700 <= c < 8900:
            return 'Securities & FinSvcs'
        elif 8900 <= c < 9000:
            return 'Funds'
        else:
            return 'Other Finance'
    except:
        return 'Other Finance'

fin_data['fin_sub'] = fin_data.apply(get_fin_subsector, axis=1)

for subsec in ['Banks', 'Securities & FinSvcs', 'Real Estate', 'Insurance']:
    sdf2 = fin_data[fin_data['fin_sub'] == subsec]
    if len(sdf2) == 0:
        continue
    r = agg_pe_pb(sdf2, f"  {subsec}")
    top5 = sdf2.nlargest(5, 'market_cap_vnd')['symbol'].tolist()
    print(f"  Top 5 by mktcap: {top5}")

# -----------------------------------------------------------------------
# 11. KEY INDIVIDUAL STOCKS VERIFICATION
# -----------------------------------------------------------------------
print("\n" + "="*70)
print("KEY STOCK VERIFICATION TABLE")
print("="*70)

key_stocks = [
    # Banks
    'VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'SHB', 'HDB', 'LPB', 'STB',
    # Securities
    'SSI', 'VND', 'HCM', 'VCI', 'MBS', 'VIX',
    # Real Estate
    'VHM', 'VIC', 'VRE', 'VPL', 'NVL', 'PDR', 'KDH', 'BCM', 'DXG',
    # Industrial Parks
    'KBC', 'IDC', 'VGC', 'SZC', 'BCM',
    # Steel/Materials
    'HPG', 'HSG', 'NKG',
    # Oil & Gas
    'GAS', 'PLX', 'BSR', 'PVD', 'PVS', 'PVT',
    # Fertilizer/Chemicals
    'DPM', 'DCM', 'DGC', 'GVR',
    # Transport/Logistics
    'GMD', 'HAH', 'VTP',
    # Aviation
    'ACV', 'HVN', 'VJC',
    # Consumer/F&B
    'MWG', 'FRT', 'PNJ', 'VNM', 'SAB', 'MSN', 'MCH', 'QNS',
    # Technology
    'FPT', 'CMG',
    # Power/Utilities
    'POW', 'GAS', 'REE', 'GEG', 'PC1', 'BWE',
    # Insurance
    'BVH', 'PVI',
    # Export/Seafood
    'VHC', 'ANV',
    # Export/Textile
    'TNG', 'MSH', 'TCM',
]
key_stocks = list(dict.fromkeys(key_stocks))  # deduplicate

kdf = data[data['symbol'].isin(key_stocks)].copy()
kdf['pe_stock'] = kdf['market_cap_vnd'] / kdf['ltm_profit']
kdf['pb_stock'] = kdf['market_cap_vnd'] / kdf['book_equity']
kdf['roe_stock'] = kdf['fundamentalsValues_ROE']
kdf['mc_bn'] = kdf['market_cap_vnd'] / 1e9

# Use FA provided P/E if our computed is extreme
kdf['pe_display'] = np.where(
    (kdf['pe_stock'] > 0) & (kdf['pe_stock'] < 200),
    kdf['pe_stock'],
    kdf['fundamentalsValues_PE']
)
kdf['pb_display'] = np.where(
    (kdf['pb_stock'] > 0),
    kdf['pb_stock'],
    kdf['fundamentalsValues_PB']
)

display = kdf[['symbol','icb_l1','mc_bn','pe_display','pb_display','roe_stock']].copy()
display = display.sort_values('mc_bn', ascending=False)
print(display.to_string(index=False, float_format=lambda x: f'{x:.2f}'))

print("\n[DONE]")
