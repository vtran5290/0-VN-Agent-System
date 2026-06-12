"""
Fix pm7_regime_dashboard_2026_06.html per council-approved changes (Step 4).
Run: .venv/Scripts/python.exe scripts/reporting/fix_pm7_html.py
"""
import sys

HTML_PATH = 'reports/pm7_regime_dashboard_2026_06.html'

with open(HTML_PATH, encoding='utf-8') as f:
    content = f.read()

original = content  # for diff count

changes = []

# 4a: Header updated date
old = 'Updated: 10 Jun 2026 · Jun 8 close data'
new = 'Updated: 12 Jun 2026 · mixed Jun 8–12 data'
if old in content:
    content = content.replace(old, new)
    changes.append('4a: Header updated date')
else:
    changes.append('4a SKIP: old string not found')

# 4b: Footer regime
old = 'Regime: UNCHANGED | RESEARCH ONLY'
new = 'Regime: SHIFTED → Defensive (Jun 8 bear trigger) | RESEARCH ONLY'
if old in content:
    content = content.replace(old, new)
    changes.append('4b: Footer regime text updated')
else:
    changes.append('4b SKIP: old string not found')

# 4c: VNI 1,803.71 as "latest" — add Jun 12 note
# The context is: "Jun 10 recovery to 1,803.71 — still below 1,810"
old = 'Jun 10 recovery to 1,803.71 — still below 1,810'
new = 'Jun 10 recovery to 1,803.71 — still below 1,810 · Jun 12: 1,791.65 (recovery failed)'
if old in content:
    content = content.replace(old, new)
    changes.append('4c: VNI 1,803.71 — Jun 12 note appended')
else:
    changes.append('4c SKIP: exact string not found')

# 4d: POW close 13.65 -> 13.50 (Jun 12)
old = 'TRAIL_EXIT &#8212; Close 13.65 &lt; Trail 13.97'
new = 'TRAIL_EXIT &#8212; Close 13.50 &lt; Trail 13.97 (Jun 12)'
if old in content:
    content = content.replace(old, new)
    changes.append('4d: POW TRAIL_EXIT close updated 13.65 → 13.50')
else:
    changes.append('4d SKIP: POW 13.65 string not found')

# 4d also: Pre-ATC scan alert with 13,650
old = 'Close 13,650 &lt; Trail 13,970'
new = 'Close 13,500 &lt; Trail 13,970 (Jun 12)'
if old in content:
    content = content.replace(old, new)
    changes.append('4d: Pre-ATC alert close updated 13,650 → 13,500')
else:
    changes.append('4d SKIP: Pre-ATC 13,650 string not found')

# 4d: Watchlist Changes table POW row — append TRAIL_EXIT warning
old = 'HSC + Vietcap both BUY; net cash by 2027; Shell LNG GSA removes supply risk; 2027 core +34%'
new = 'HSC + Vietcap both BUY; net cash by 2027; Shell LNG GSA removes supply risk; 2027 core +34% · ⚠ A3 TRAIL_EXIT active — exit first, re-entry per gates'
if old in content:
    content = content.replace(old, new)
    changes.append('4d: POW Watchlist row TRAIL_EXIT warning appended')
else:
    changes.append('4d SKIP: POW watchlist rationale string not found')

# 4e: VCB divergence line reword
old = '<strong>Key divergence: VCB foreign buying Jun 8 despite TRAIL_EXIT signal</strong> — verify before executing exit.'
new = '[INTERPRETATION] VCB saw foreign+prop buying Jun 8 — context only, does NOT override A3 exits. (VCB no longer a holding per Jun-12 scan.)'
if old in content:
    content = content.replace(old, new)
    changes.append('4e: VCB divergence line reworded')
else:
    changes.append('4e SKIP: VCB divergence exact string not found')

# 4f: MA20 resistance 1,890 -> ≈1,854 (Jun 12)
old = 'class="tech-value resistance">1,890</span>'
new = 'class="tech-value resistance">≈1,854 (Jun 12)</span>'
if old in content:
    content = content.replace(old, new)
    changes.append('4f: MA20 resistance updated 1,890 → ≈1,854 (Jun 12)')
else:
    changes.append('4f SKIP: MA20 1,890 string not found')

# 4g: Ex-right date note
old = 'Ex-right date: <span class="warn">16 Jun</span> — timing risk'
new = 'Ex-right date: <span class="warn">16 Jun</span> [verify: ex-right vs record date — different sessions] — timing risk'
if old in content:
    content = content.replace(old, new)
    changes.append('4g: Ex-right date note updated')
else:
    changes.append('4g SKIP: ex-right string not found')

# 4h: Footer date
old = 'PM7 Vietcap Update | Updated: 10 Jun 2026 (Jun 8 close)'
new = 'PM7 Vietcap Update | Updated: 12 Jun 2026 (mixed Jun 8–12 data)'
if old in content:
    content = content.replace(old, new)
    changes.append('4h: Footer date updated')
else:
    changes.append('4h SKIP: footer date string not found')

# 4i: Typo ACB resilient (+26,500 -> (at 26,500
old = 'ACB resilient (+26,500'
new = 'ACB resilient (at 26,500'
if old in content:
    content = content.replace(old, new)
    changes.append('4i: ACB resilient typo fixed (+26,500 → at 26,500)')
else:
    changes.append('4i SKIP: ACB resilient (+26,500 not found')

# 4j: DXY ~135 suspect label
old = 'DXY ~135 /'
new = 'DXY ~135 [SUSPECT — proxy] /'
if old in content:
    content = content.replace(old, new)
    changes.append('4j: DXY ~135 suspect label added')
else:
    changes.append('4j SKIP: DXY ~135 / not found')

# Write back
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('pm7 HTML changes applied:')
for c in changes:
    print(' ', c)
print(f'Characters changed: {sum(1 for a,b in zip(original, content) if a!=b)} char-diffs')
