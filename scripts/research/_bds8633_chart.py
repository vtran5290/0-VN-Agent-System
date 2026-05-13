import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

df = pd.read_csv('data/research/sector8630_stock_p20.csv')
df['median_traded_value_20d'] = pd.to_numeric(df['median_traded_value_20d'], errors='coerce').fillna(0)
df['lead_prob_20d'] = pd.to_numeric(df['lead_prob_20d'], errors='coerce').fillna(0)
df['liq_bn'] = df['median_traded_value_20d'] / 1e9  # VND -> tỷ

# Filter: có trading
df = df[df['median_traded_value_20d'] > 0].copy()

# Screen stocks (từ composite screener)
screen_tickers = {'NRC', 'VIC', 'VHM', 'NVL', 'TCH', 'DXG', 'KDH', 'PDR', 'CEO', 'KBC'}

df = df.sort_values('lead_prob_20d', ascending=False).head(30).reset_index(drop=True)

def liq_label(v):
    if v >= 500: return f'{v:,.0f}bn ★★★'
    if v >= 50:  return f'{v:,.0f}bn ★★'
    if v >= 5:   return f'{v:.1f}bn ★'
    if v > 0:    return f'{v*1000:.0f}mn'
    return '—'

def bar_color(row):
    t = row['symbol']
    p = row['lead_prob_20d']
    if t in screen_tickers:
        return '#F1C40F'  # gold - in screen
    if p >= 0.55: return '#2ECC71'
    if p >= 0.40: return '#F39C12'
    return '#5DADE2'

colors = [bar_color(r) for _, r in df.iterrows()]
labels = [f"{r['symbol']}  {r['name'][:22]}.." if len(r['name']) > 22 else f"{r['symbol']}  {r['name']}"
          for _, r in df.iterrows()]
vals = (df['lead_prob_20d'] * 100).round(1).tolist()
exch = df['exchange'].tolist()
liqs = df['liq_bn'].tolist()

fig, ax = plt.subplots(figsize=(15, 11))
fig.patch.set_facecolor('#1C2833')
ax.set_facecolor('#1C2833')

y = np.arange(len(df))
bars = ax.barh(y, vals, color=colors, height=0.65, edgecolor='#2C3E50', linewidth=0.5)

for i, (v, ex, liq, t) in enumerate(zip(vals, exch, liqs, df['symbol'])):
    # prob value
    ax.text(v + 0.5, i, f'{v:.1f}%', va='center', ha='left', fontsize=9,
            color='white', fontweight='bold')
    # exchange badge
    ex_color = {'HSX': '#3498DB', 'HNX': '#E67E22', 'UPCOM': '#95A5A6'}.get(ex, '#888')
    ax.text(62, i, ex, va='center', ha='left', fontsize=7.5,
            color=ex_color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#1C2833', edgecolor=ex_color, linewidth=0.7))
    # liquidity
    ax.text(69, i, liq_label(liq), va='center', ha='left', fontsize=7.5, color='#BDC3C7')

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9, color='#ECF0F1', fontfamily='monospace')
ax.invert_yaxis()

ax.set_xlabel('lead_prob_20d (%)', color='#ECF0F1', fontsize=10)
ax.set_title('Co phieu BDS dau co & phat trien (8633)  |  lead_prob_20d  |  29/04/2026',
             color='white', fontsize=13, fontweight='bold', pad=12)

ax.set_xlim(0, 100)
ax.axvline(50, color='#E74C3C', linestyle='--', linewidth=1, alpha=0.6)
ax.text(50.5, len(df) - 0.5, '50%', color='#E74C3C', fontsize=8)
ax.xaxis.grid(True, color='#2C3E50', linewidth=0.6, linestyle='--')
ax.set_axisbelow(True)
ax.tick_params(colors='#ECF0F1', axis='both')
for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)
for spine in ['bottom', 'left']:
    ax.spines[spine].set_color('#444')

p1 = mpatches.Patch(color='#F1C40F', label='Co trong composite screen (9/5)')
p2 = mpatches.Patch(color='#2ECC71', label='lead_prob >= 55%')
p3 = mpatches.Patch(color='#F39C12', label='lead_prob 40-55%')
p4 = mpatches.Patch(color='#5DADE2', label='lead_prob < 40%')
ax.legend(handles=[p1, p2, p3, p4], loc='lower right', facecolor='#2C3E50',
          edgecolor='#555', labelcolor='white', fontsize=8.5)

ax.annotate('★★★ > 500 ty/ngay  ★★ > 50 ty  ★ > 5 ty  |  Loc: chi hien co giao dich (median_traded_value_20d > 0)',
            xy=(0.01, -0.04), xycoords='axes fraction', fontsize=7.5, color='#888')

plt.tight_layout()
out = 'data/research/bds8633_stock_prob_20260508.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved: {out}')
