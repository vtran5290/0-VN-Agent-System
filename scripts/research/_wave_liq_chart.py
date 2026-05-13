import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# --- Load data ---
liq = pd.read_csv('data/research/industry_value_share_1m_level4.csv')
liq['industryCode'] = liq['industryCode'].astype(str)
liq = liq[liq['avg_daily_value_bn_vnd'] > 0].sort_values('avg_daily_value_bn_vnd', ascending=False).head(20)

wave = pd.read_csv('data/research/industry_wave_probability_l4_tune_d_latest.csv')
wave['industryCode'] = wave['industryCode'].astype(str)
wave_map = wave.set_index('industryCode')['p_wave_20d'].to_dict()

screen = pd.read_csv('artifacts/composite_vn_screen/ranked_table.csv')
sector_tickers = {}
for _, row in screen.iterrows():
    sl4 = str(row.get('Sector L4', ''))
    if sl4 and sl4 not in ('Unknown', 'nan'):
        code = sl4.split(' - ')[0].strip()
        sector_tickers.setdefault(code, []).append(str(row['Ticker']))

liq['p_wave_20d'] = liq['industryCode'].map(wave_map).fillna(0) * 100
liq['tickers'] = liq['industryCode'].map(lambda c: ', '.join(sector_tickers.get(c, [])[:4]))
liq['has_setup'] = liq['tickers'].str.len() > 0

def shorten(name, n=26):
    return name[:n] + '..' if len(name) > n else name

liq['label'] = liq['industryName'].apply(shorten)

# --- Figure: dual bar chart (liquidity + wave prob) ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9))
fig.patch.set_facecolor('#1C2833')
for ax in [ax1, ax2]:
    ax.set_facecolor('#1C2833')
    ax.tick_params(colors='#ECF0F1', axis='both')
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']:
        ax.spines[spine].set_color('#444')

df = liq.sort_values('avg_daily_value_bn_vnd', ascending=True).reset_index(drop=True)
y = np.arange(len(df))

# Color by wave prob quartile
def wave_color(p):
    if p >= 22:   return '#2ECC71'   # high
    elif p >= 17: return '#F39C12'   # medium
    else:         return '#5DADE2'   # low

colors = [wave_color(p) for p in df['p_wave_20d']]

# --- LEFT: Thanh khoản ---
bars = ax1.barh(y, df['avg_daily_value_bn_vnd'], color=colors, height=0.65, edgecolor='#333')
for i, (v, t) in enumerate(zip(df['avg_daily_value_bn_vnd'], df['tickers'])):
    ax1.text(v + 30, i, f'{v:,.0f}', va='center', ha='left', fontsize=8.5, color='white')
    if t:
        ax1.text(v + 30, i - 0.28, t, va='center', ha='left', fontsize=7.5, color='#F9E79F', fontweight='bold')

ax1.set_yticks(y)
ax1.set_yticklabels([f"{r['label']} ({r['industryCode']})" for _, r in df.iterrows()],
                    fontsize=9, color='#ECF0F1')
ax1.set_xlabel('GT giao dịch TB ngày (tỷ VND)', color='#ECF0F1', fontsize=10)
ax1.set_title('THANH KHOAN NGAY TB (22 phien)', color='white', fontsize=12, fontweight='bold')
ax1.xaxis.grid(True, color='#2C3E50', linewidth=0.6, linestyle='--')
ax1.set_axisbelow(True)
ax1.tick_params(axis='x', colors='#ECF0F1')
ax1.set_xlim(0, df['avg_daily_value_bn_vnd'].max() * 1.25)

# --- RIGHT: Wave probability ---
bars2 = ax2.barh(y, df['p_wave_20d'], color=colors, height=0.65, edgecolor='#333')
for i, (p, t) in enumerate(zip(df['p_wave_20d'], df['tickers'])):
    ax2.text(p + 0.3, i, f'{p:.1f}%', va='center', ha='left', fontsize=8.5, color='white')

# Reference line at mean
mean_p = df['p_wave_20d'].mean()
ax2.axvline(mean_p, color='#E74C3C', linestyle='--', linewidth=1.2, alpha=0.8)
ax2.text(mean_p + 0.2, len(df) - 0.5, f'avg {mean_p:.1f}%', color='#E74C3C', fontsize=8)

ax2.set_yticks(y)
ax2.set_yticklabels([f"{r['label']} ({r['industryCode']})" for _, r in df.iterrows()],
                    fontsize=9, color='#ECF0F1')
ax2.set_xlabel('Xac suat vao song 20 ngay (%)', color='#ECF0F1', fontsize=10)
ax2.set_title('WAVE PROBABILITY p_wave_20d', color='white', fontsize=12, fontweight='bold')
ax2.xaxis.grid(True, color='#2C3E50', linewidth=0.6, linestyle='--')
ax2.set_axisbelow(True)
ax2.tick_params(axis='x', colors='#ECF0F1')
ax2.set_xlim(0, 35)

# Legend
import matplotlib.patches as mpatches
p1 = mpatches.Patch(color='#2ECC71', label='p20 >= 22% (cao)')
p2 = mpatches.Patch(color='#F39C12', label='p20 17-22% (trung binh)')
p3 = mpatches.Patch(color='#5DADE2', label='p20 < 17% (thap)')
ax2.legend(handles=[p1, p2, p3], loc='lower right', facecolor='#2C3E50',
           edgecolor='#555', labelcolor='white', fontsize=9)

fig.suptitle('Top 20 Nganh Thanh Khoan Cao x Wave Probability L4  |  08/05/2026',
             color='white', fontsize=14, fontweight='bold', y=1.01)
ax1.annotate('Ticker vang = co co phieu setup trong screener 9/5  |  Mau = muc wave prob',
             xy=(0.01, -0.04), xycoords='axes fraction', fontsize=8, color='#888')

plt.tight_layout()
out = 'data/research/wave_liq_top20_chart_20260508.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved: {out}')
