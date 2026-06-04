"""
Generate charts for Vietnam Market Valuation Verification — 2026-05-30
Outputs:
  data/decision/charts/chart01_vni_pe_history.png
  data/decision/charts/chart02_sector_pe_pb_heatmap.png
  data/decision/charts/chart03_cycle_bottoms.png
  data/decision/charts/chart04_sector_scatter.png
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings('ignore')

os.makedirs('data/decision/charts', exist_ok=True)

# ── colour palette ────────────────────────────────────────────────────────────
GREEN  = '#2E7D32'
ORANGE = '#E65100'
RED    = '#B71C1C'
BLUE   = '#1565C0'
GREY   = '#616161'
LGREY  = '#EEEEEE'

# ─────────────────────────────────────────────────────────────────────────────
# CHART 1 — VN-Index Historical P/E with cycle bottoms annotated
# ─────────────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=False)

# P/E panel
ax1 = axes[0]
years  = [2009, 2012, 2016, 2020, 2022, 2026]
pe_cg  = [10.46, 7.41, 12.71, 10.45, 9.98, None]   # ChatGPT claims
pe_our = [None, None, 10.18, 9.58, 8.74, 14.40]     # our calculations

ax1.axhline(y=13.25, color=BLUE, linewidth=1.5, linestyle='--', alpha=0.7, label='Current headline P/E (13.25x)')
ax1.axhline(y=11.19, color=BLUE, linewidth=1.2, linestyle=':', alpha=0.7, label='Current ex-Vin P/E (11.19x)')
ax1.axhspan(7, 10.5, alpha=0.08, color=GREEN, label='Deep-value zone (<10.5x)')
ax1.axhspan(10.5, 12.5, alpha=0.06, color=ORANGE, label='Attractive zone (10.5–12.5x)')

bottom_labels = {2016: '2016\nJan', 2020: '2020\nMar', 2022: '2022\nNov'}
for yr, pe, pc in zip(years, pe_our, pe_cg):
    if pe is not None:
        color = GREEN if yr < 2026 else BLUE
        ax1.scatter(yr, pe, s=120, color=color, zorder=5)
        ax1.annotate(f'Ours: {pe:.2f}x', (yr, pe),
                     textcoords='offset points', xytext=(-28, 10),
                     fontsize=8.5, color=color, fontweight='bold')
    if pc is not None:
        ax1.scatter(yr, pc, s=80, color=RED, marker='x', zorder=4, linewidths=2)
        ax1.annotate(f'GPT: {pc:.2f}x', (yr, pc),
                     textcoords='offset points', xytext=(8, -15),
                     fontsize=8, color=RED)
    if yr in bottom_labels:
        ax1.axvline(x=yr, color=GREY, linewidth=0.8, linestyle=':', alpha=0.5)
        ax1.text(yr, 6.5, bottom_labels[yr], ha='center', fontsize=8, color=GREY)

ax1.set_xlim(2007, 2028)
ax1.set_ylim(5, 18)
ax1.set_ylabel('P/E (LTM, market-cap weighted)', fontsize=10)
ax1.set_title('VN-Index LTM P/E at Cycle Bottoms — Our Calculation vs ChatGPT Claims',
              fontsize=12, fontweight='bold')
ax1.legend(loc='upper left', fontsize=8.5, framealpha=0.9)
ax1.grid(axis='y', alpha=0.3)
ax1.set_xticks(years)

# P/B panel
ax2 = axes[1]
pb_cg  = [1.24, 1.25, 1.78, 1.65, 1.71, None]
pb_our = [None, None, 1.42, 1.49, 1.45, 2.09]

ax2.axhline(y=2.09, color=BLUE, linewidth=1.5, linestyle='--', alpha=0.7, label='Current headline P/B (2.09x)')
ax2.axhline(y=1.66, color=BLUE, linewidth=1.2, linestyle=':', alpha=0.7, label='Current ex-Vin P/B (1.66x)')
ax2.axhspan(1.0, 1.55, alpha=0.08, color=GREEN, label='Deep-value zone (<1.55x)')

for yr, pb, pc in zip(years, pb_our, pb_cg):
    if pb is not None:
        color = GREEN if yr < 2026 else BLUE
        ax2.scatter(yr, pb, s=120, color=color, zorder=5)
        ax2.annotate(f'Ours: {pb:.2f}x', (yr, pb),
                     textcoords='offset points', xytext=(-28, 10),
                     fontsize=8.5, color=color, fontweight='bold')
    if pc is not None:
        ax2.scatter(yr, pc, s=80, color=RED, marker='x', zorder=4, linewidths=2)
        ax2.annotate(f'GPT: {pc:.2f}x', (yr, pc),
                     textcoords='offset points', xytext=(8, -15),
                     fontsize=8, color=RED)

ax2.set_xlim(2007, 2028)
ax2.set_ylim(0.8, 3.0)
ax2.set_ylabel('P/B (market-cap weighted)', fontsize=10)
ax2.set_title('VN-Index LTM P/B at Cycle Bottoms — Our Calculation vs ChatGPT Claims', fontsize=12, fontweight='bold')
ax2.legend(loc='upper left', fontsize=8.5, framealpha=0.9)
ax2.grid(axis='y', alpha=0.3)
ax2.set_xticks(years)

our_dot   = mpatches.Patch(color=GREEN, label='Our calc (SSOT data)')
gpt_cross = mpatches.Patch(color=RED, label='ChatGPT claim')
cur_dot   = mpatches.Patch(color=BLUE, label='Current (May 2026)')
fig.legend(handles=[our_dot, gpt_cross, cur_dot], loc='lower center',
           ncol=3, fontsize=9, bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.04, 1, 1])
plt.savefig('data/decision/charts/chart01_vni_pe_history.png', dpi=150, bbox_inches='tight')
plt.close()
print("Chart 1 saved.")

# ─────────────────────────────────────────────────────────────────────────────
# CHART 2 — Sector P/E vs P/B heatmap / scatter
# ─────────────────────────────────────────────────────────────────────────────
sectors = {
    'Banks':              {'pe': 9.08,  'pb': 1.42, 'roe': 17.0, 'mc': 103.0},
    'Securities':         {'pe': 13.65, 'pb': 1.59, 'roe': 11.0, 'mc': 9.2},
    'RE (ex-Vin)':        {'pe': 17.61, 'pb': 1.07, 'roe': 5.5,  'mc': 12.8},
    'RE (Vin)':           {'pe': 27.04, 'pb': 4.58, 'roe': 12.0, 'mc': 35.8},
    'Oil & Gas':          {'pe': 13.60, 'pb': 1.95, 'roe': 14.0, 'mc': 9.3},
    'Steel/Materials':    {'pe': 9.50,  'pb': 1.36, 'roe': 11.0, 'mc': 7.0},
    'Consumer Goods/F&B': {'pe': 15.10, 'pb': 2.99, 'roe': 16.0, 'mc': 15.5},
    'Tech/Telecom':       {'pe': 14.40, 'pb': 3.81, 'roe': 24.0, 'mc': 14.2},
    'Power/Utilities':    {'pe': 16.2,  'pb': 1.55, 'roe': 10.5, 'mc': 6.8},
    'Aviation':           {'pe': 21.0,  'pb': 2.40, 'roe': 9.0,  'mc': 4.5},
    'Chemicals/Fert':     {'pe': 8.50,  'pb': 1.20, 'roe': 13.0, 'mc': 3.1},
    'Transport/Logistics':{'pe': 11.0,  'pb': 1.85, 'roe': 14.5, 'mc': 2.8},
    'Seafood Export':     {'pe': 6.90,  'pb': 1.22, 'roe': 15.0, 'mc': 1.4},
    'Textile Export':     {'pe': 5.80,  'pb': 1.61, 'roe': 17.0, 'mc': 0.6},
}

labels  = list(sectors.keys())
pe_vals = [sectors[s]['pe']  for s in labels]
pb_vals = [sectors[s]['pb']  for s in labels]
roe_vals= [sectors[s]['roe'] for s in labels]
mc_vals = [sectors[s]['mc']  for s in labels]

fig, ax = plt.subplots(figsize=(13, 8))

sc_size = [max(80, m * 25) for m in mc_vals]
sc_color = roe_vals

cmap = LinearSegmentedColormap.from_list('roe_cmap', ['#F44336','#FFC107','#4CAF50'])
sc = ax.scatter(pb_vals, pe_vals, s=sc_size, c=sc_color, cmap=cmap,
                vmin=5, vmax=25, alpha=0.85, edgecolors='white', linewidths=1.5, zorder=5)

cbar = plt.colorbar(sc, ax=ax)
cbar.set_label('ROE (%)', fontsize=10)

for i, lbl in enumerate(labels):
    offset = (6, 4) if pb_vals[i] < 4 else (-60, 4)
    ax.annotate(lbl, (pb_vals[i], pe_vals[i]),
                textcoords='offset points', xytext=offset,
                fontsize=8.5, fontweight='bold' if mc_vals[i] > 15 else 'normal')

ax.axhline(y=10.5, color=GREEN, linewidth=1.2, linestyle='--', alpha=0.6, label='P/E 10.5x (historical floor)')
ax.axvline(x=1.5,  color=ORANGE, linewidth=1.0, linestyle=':', alpha=0.6, label='P/B 1.5x')

ax.set_xlabel('P/B (LTM)', fontsize=11)
ax.set_ylabel('P/E (LTM, agg)', fontsize=11)
ax.set_title('Sector Valuation Matrix — P/E vs P/B\n(Bubble size = market cap USD; Color = ROE%)',
             fontsize=12, fontweight='bold')
ax.grid(alpha=0.3)
ax.legend(fontsize=9)

note = "Source: FireAnt SSOT fa_quarterly + TradingView screener | Date: 2026-05-30"
fig.text(0.5, 0.01, note, ha='center', fontsize=8, color=GREY)

plt.tight_layout(rect=[0, 0.03, 1, 1])
plt.savefig('data/decision/charts/chart02_sector_pe_pb_scatter.png', dpi=150, bbox_inches='tight')
plt.close()
print("Chart 2 saved.")

# ─────────────────────────────────────────────────────────────────────────────
# CHART 3 — Cycle bottom comparison bar chart
# ─────────────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

periods  = ['2016\nBottom', '2020 Covid\nBottom', '2022 Crisis\nBottom', 'Current\nMay 2026']
our_pe   = [10.18, 9.58, 8.74, 14.40]
gpt_pe   = [12.71, 10.45, 9.98, 13.70]
our_pb   = [1.42,  1.49,  1.45,  2.09]
gpt_pb   = [1.78,  1.65,  1.71,  2.08]

x = np.arange(len(periods))
w = 0.35

bars1 = ax1.bar(x - w/2, our_pe, w, label='Our SSOT Calc', color=GREEN, alpha=0.85, edgecolor='white')
bars2 = ax1.bar(x + w/2, gpt_pe, w, label='ChatGPT Claim', color=RED,   alpha=0.70, edgecolor='white')

for bar in bars1:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
             f'{bar.get_height():.2f}x', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color=GREEN)
for bar in bars2:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
             f'{bar.get_height():.2f}x', ha='center', va='bottom', fontsize=8.5, color=RED)

ax1.axhline(y=14.40, color=BLUE, linestyle='--', linewidth=1.5, alpha=0.7, label='Current P/E 14.40x')
ax1.set_xticks(x)
ax1.set_xticklabels(periods, fontsize=9)
ax1.set_ylabel('LTM P/E (market-cap weighted)', fontsize=10)
ax1.set_title('P/E at Cycle Bottoms', fontsize=12, fontweight='bold')
ax1.legend(fontsize=9)
ax1.grid(axis='y', alpha=0.3)
ax1.set_ylim(0, 17)

bars3 = ax2.bar(x - w/2, our_pb, w, label='Our SSOT Calc', color=GREEN, alpha=0.85, edgecolor='white')
bars4 = ax2.bar(x + w/2, gpt_pb, w, label='ChatGPT Claim', color=RED,   alpha=0.70, edgecolor='white')

for bar in bars3:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{bar.get_height():.2f}x', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color=GREEN)
for bar in bars4:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{bar.get_height():.2f}x', ha='center', va='bottom', fontsize=8.5, color=RED)

ax2.axhline(y=2.09, color=BLUE, linestyle='--', linewidth=1.5, alpha=0.7, label='Current P/B 2.09x')
ax2.set_xticks(x)
ax2.set_xticklabels(periods, fontsize=9)
ax2.set_ylabel('LTM P/B (market-cap weighted)', fontsize=10)
ax2.set_title('P/B at Cycle Bottoms', fontsize=12, fontweight='bold')
ax2.legend(fontsize=9)
ax2.grid(axis='y', alpha=0.3)
ax2.set_ylim(0, 2.8)

fig.suptitle('VN-Index Cycle Bottom Valuations: SSOT Verification vs ChatGPT Claims\n'
             'ChatGPT overstates historical bottoms by ~10-15% — current market is NOT near historical floor',
             fontsize=11, fontweight='bold', y=1.01)

note = "Source: FireAnt fa_quarterly + ta_ohlcv_panel | Methodology: MC-weighted P/E (positive earners only) | Date: 2026-05-30"
fig.text(0.5, -0.02, note, ha='center', fontsize=8, color=GREY)

plt.tight_layout()
plt.savefig('data/decision/charts/chart03_cycle_bottoms.png', dpi=150, bbox_inches='tight')
plt.close()
print("Chart 3 saved.")

# ─────────────────────────────────────────────────────────────────────────────
# CHART 4 — Sector ranking (horizontal bar)
# ─────────────────────────────────────────────────────────────────────────────
ranking = [
    ('Seafood Export',      6.90,  'BUY',   GREEN),
    ('Textile Export',      5.80,  'BUY',   GREEN),
    ('Banks',               9.08,  'BUY',   GREEN),
    ('Steel/Materials',     9.50,  'BUY',   GREEN),
    ('Chemicals/Fert',      8.50,  'BUY',   GREEN),
    ('Transport/Logistics', 11.0,  'HOLD',  ORANGE),
    ('Oil & Gas',           13.60, 'HOLD',  ORANGE),
    ('Securities',          13.65, 'HOLD',  ORANGE),
    ('Tech/Telecom',        14.40, 'HOLD',  ORANGE),
    ('Consumer Goods/F&B',  15.10, 'AVOID', RED),
    ('Power/Utilities',     16.2,  'AVOID', RED),
    ('RE (ex-Vin)',         17.61, 'AVOID', RED),
    ('Aviation',            21.0,  'AVOID', RED),
    ('RE (Vin)',            27.04, 'AVOID', RED),
]
ranking.sort(key=lambda x: x[1])

fig, ax = plt.subplots(figsize=(11, 8))

names  = [r[0] for r in ranking]
pes    = [r[1] for r in ranking]
colors = [r[3] for r in ranking]

y_pos = np.arange(len(names))
bars  = ax.barh(y_pos, pes, color=colors, alpha=0.85, edgecolor='white', height=0.7)

for i, (bar, pe) in enumerate(zip(bars, pes)):
    ax.text(pe + 0.2, bar.get_y() + bar.get_height()/2,
            f'{pe:.1f}x', va='center', fontsize=9, fontweight='bold')
    verdict = ranking[i][2]
    ax.text(-0.5, bar.get_y() + bar.get_height()/2,
            verdict, va='center', ha='right', fontsize=8.5,
            color=colors[i], fontweight='bold')

ax.axvline(x=10.5, color=GREEN, linestyle='--', linewidth=1.5, alpha=0.6, label='Historical floor ~10.5x')
ax.axvline(x=14.40, color=BLUE, linestyle='--', linewidth=1.2, alpha=0.6, label='VNI headline 14.40x')

ax.set_yticks(y_pos)
ax.set_yticklabels(names, fontsize=9.5)
ax.set_xlabel('LTM P/E (aggregate, market-cap weighted)', fontsize=10)
ax.set_title('Sector Valuation Ranking — BUY / HOLD / AVOID\n(Ranked by LTM P/E ascending)',
             fontsize=12, fontweight='bold')
ax.legend(fontsize=9, loc='lower right')
ax.grid(axis='x', alpha=0.3)

buy_patch   = mpatches.Patch(color=GREEN,  label='BUY   — below 12x, strong fundamentals')
hold_patch  = mpatches.Patch(color=ORANGE, label='HOLD  — 12–16x, fair value')
avoid_patch = mpatches.Patch(color=RED,    label='AVOID — above 16x or structural issues')
ax.legend(handles=[buy_patch, hold_patch, avoid_patch], loc='lower right', fontsize=9)

note = "Source: FireAnt fa_quarterly + TradingView screener | Date: 2026-05-30"
fig.text(0.5, -0.01, note, ha='center', fontsize=8, color=GREY)

plt.tight_layout(rect=[0.05, 0.01, 1, 1])
plt.savefig('data/decision/charts/chart04_sector_ranking.png', dpi=150, bbox_inches='tight')
plt.close()
print("Chart 4 saved.")

print("\nAll charts written to data/decision/charts/")
