import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

l4 = pd.read_csv('data/research/industry_wave_probability_l4_tune_d_latest.csv')
l4 = l4.sort_values('p_wave_20d', ascending=False).head(20).reset_index(drop=True)

screen = pd.read_csv('artifacts/composite_vn_screen/ranked_table.csv')
sector_tickers = {}
for _, row in screen.iterrows():
    sl4 = str(row.get('Sector L4', ''))
    if sl4 and sl4 not in ('Unknown', 'nan'):
        code = sl4.split(' - ')[0].strip()
        sector_tickers.setdefault(code, []).append(str(row['Ticker']))

colors, annotations = [], []
for _, row in l4.iterrows():
    code = str(int(row['industryCode']))
    tickers = sector_tickers.get(code, [])
    colors.append('#2ECC71' if tickers else '#5DADE2')
    annotations.append(', '.join(tickers[:5]) if tickers else '')

def shorten(name, n=34):
    return name[:n] + '..' if len(name) > n else name

labels = [f"{shorten(r['industryName'])} ({int(r['industryCode'])})" for _, r in l4.iterrows()]
vals20 = (l4['p_wave_20d'] * 100).round(1).tolist()
vals10 = (l4['p_wave_10d'] * 100).round(1).tolist()

fig, ax = plt.subplots(figsize=(15, 10))
fig.patch.set_facecolor('#1C2833')
ax.set_facecolor('#1C2833')

y = np.arange(len(labels))
bh = 0.38

bars10 = ax.barh(y + bh/2, vals10, bh, color=[c + '66' for c in colors], label='p_wave_10d')
bars20 = ax.barh(y - bh/2, vals20, bh, color=colors, label='p_wave_20d')

for i, (v10, v20, ann) in enumerate(zip(vals10, vals20, annotations)):
    ax.text(v20 + 0.3, i - bh/2, f'{v20}%', va='center', ha='left', fontsize=8.5, color='white', fontweight='bold')
    ax.text(v10 + 0.3, i + bh/2, f'{v10}%', va='center', ha='left', fontsize=7.5, color='#AAAAAA')
    if ann:
        ax.text(max(vals10) * 1.05, i, ann, va='center', ha='left', fontsize=9,
                color='#F9E79F', fontweight='bold')

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9.5, color='#ECF0F1')
ax.invert_yaxis()
ax.set_xlabel('Xác suất vào sóng (%)', color='#ECF0F1', fontsize=11)
ax.set_title('Industry Wave Probability — Level 4  |  as of 08/05/2026', color='white',
             fontsize=14, fontweight='bold', pad=15)
ax.tick_params(colors='#ECF0F1', axis='both')
for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)
for spine in ['bottom', 'left']:
    ax.spines[spine].set_color('#444')
ax.set_xlim(0, max(vals10) * 1.55)
ax.xaxis.grid(True, color='#2C3E50', linewidth=0.7, linestyle='--')
ax.set_axisbelow(True)
ax.tick_params(axis='x', colors='#ECF0F1')

p1 = mpatches.Patch(color='#2ECC71', label='Co co phieu setup (screener 9/5)')
p2 = mpatches.Patch(color='#5DADE2', label='Chua co co phieu trong screen')
p3 = mpatches.Patch(color='#888888', alpha=0.5, label='Bar nhat = p_wave_10d')
ax.legend(handles=[p1, p2, p3], loc='lower right', facecolor='#2C3E50',
          edgecolor='#555', labelcolor='white', fontsize=9.5)

ax.annotate('Date: 08/05/2026  |  Model: Bayesian walk-forward calibrated  |  Screen: composite_vn 09/05',
            xy=(0.01, 0.01), xycoords='figure fraction', fontsize=7.5, color='#777')

plt.tight_layout()
out = 'data/research/wave_prob_l4_chart_20260508.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved: {out}')
