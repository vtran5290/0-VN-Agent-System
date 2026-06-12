"""
Fix pm_dashboard_data.json per council-approved changes.
Run: .venv/Scripts/python.exe scripts/reporting/fix_pm_json.py
"""
import json, sys

with open('data/raw/pm_dashboard_data.json', encoding='utf-8') as f:
    raw = f.read()

# Step 2i check first: raw double-escapes
if '&amp;lt;' in raw:
    print("  Found &amp;lt; — fixing double-escapes in raw")
    raw = raw.replace('&amp;lt;', '<').replace('&amp;gt;', '>')

data = json.loads(raw)

# STEP 2a: meta dates
data['meta']['data_date'] = "12 Jun 2026 (Jun 12 ATC close)"
data['meta']['prices_date'] = "12 Jun 2026 (Jun 12 ATC)"
print("2a: meta dates updated")

# STEP 2b: VNI KPI
for kpi in data['pulse']['kpis']:
    if kpi['label'] == 'VN-Index':
        kpi['value'] = "1,791.65"
        kpi['value_class'] = "down"
        kpi['sub'] = "Jun 12 ATC · recovery failed (1,803.71 Jun 10 → 1,791.65) · still below 1,810 · near 1,790.53 low"
        kpi['status'] = "bad"
        print("2b: VNI KPI updated")

# STEP 2c: VNI pill
for pill in data['regime']['pills']:
    if '1,803' in pill['text']:
        pill['text'] = "VNI 1,792 · Below 1,810 · Recovery Failed"
        print("2c: VNI pill updated")

# STEP 2d: Breadth KPI
for kpi in data['pulse']['kpis']:
    if kpi['label'] == 'Breadth':
        kpi['value'] = "Dist D8"
        kpi['sub'] = "Dist 8/25d (Jun 12) · DOWNTREND_WARNING · Defense zone · Cloud 24.1%"
        print("2d: Breadth KPI updated")

# STEP 2e: Replace A3 scan event (Jun 10 -> Jun 12)
for i, ev in enumerate(data['events']):
    if '10 Jun' in ev.get('who', '') and 'A3 ATC Daily Scan' in ev.get('who', ''):
        ev['who'] = "A3 ATC Daily Scan · 12 Jun · Phase36 · 95 symbols"
        ev['what'] = (
            '<span class="tag tag-f">Fact</span> Phase36 A3 scan (Jun 12 ATC close, 95 symbols). '
            '<strong>VNI 1,791.65</strong> (recovery failed — 1,803.71 Jun 10 → 1,791.65; near 1,790.53 low). '
            'Regime: VNINDEX BEAR (EMA20&lt;EMA100). Cloud breadth: 24.1% '
            '(DOWNTREND_WARNING · defense zone — T1 blocked; T2 adds <strong>blocked</strong>, breadth &lt;40%). '
            '<strong>1 portfolio TRAIL_EXIT</strong>: <strong>POW</strong> 13.50 &lt; trail 13.97 '
            '(priority exit review). MSB signal cleared (now SKIP_VNINDEX_BEAR at 15.0). '
            'Holdings not in scan: STB, TCX, GEE, GAS. New T1 candidates: 0.'
        )
        ev['note'] = (
            "→ T1/T2 blocked. Execute exit discipline: POW TRAIL_EXIT (13.50 < 13.97). "
            "Holdings outside scan universe — verify coverage. "
            "Upgrade gate: VNI reclaim 1,810 + breadth >40%."
        )
        ev['date_warn'] = None
        print(f"2e: A3 event updated at index {i}")
        break

# STEP 2f: VCB note fix in flow card
for ev in data['events']:
    who = ev.get('who', '')
    if 'Khối Ngoại' in who or 'HOSE Flow' in who:
        for field in ['note', 'what']:
            val = ev.get(field, '')
            new_val = val.replace(
                'VCB: both foreign + prop buying Jun 8 (positive signal).',
                'INTERPRETATION: VCB saw foreign+prop buying Jun 8 — context only, does NOT override A3 exits. (VCB no longer a holding per Jun-12 scan.)'
            )
            if new_val != val:
                ev[field] = new_val
                print(f"2f: VCB note updated in {field} of flow event")

# STEP 2g: OMO figures — label both values
# In council event note: "OMO +12,000bn" -> labeled
for ev in data['events']:
    if 'Investment Council' in ev.get('who', ''):
        note = ev.get('note', '')
        new_note = note.replace(
            'OMO +12,000bn',
            'OMO +2,000bn WoW (wk Jun 2) / +12,000bn cumulative (wk Jun 9)'
        )
        if new_note != note:
            ev['note'] = new_note
            print("2g: OMO updated in council event note")

# Also fix in risks high (interbank ON spike sub text)
for risk in data['risks'].get('high', []):
    if 'OMO' in risk.get('sub', ''):
        old = risk['sub']
        new = old.replace('OMO +2,000bn WoW', 'OMO +2,000bn WoW (wk Jun 2)')
        if new != old:
            risk['sub'] = new
            print("2g: OMO updated in risk sub")

# Also fix in footer
footer_text = data['footer'].get('council_conditions_text', '')
new_footer = footer_text.replace(
    'OMO +12,000bn',
    'OMO +2,000bn WoW (wk Jun 2) / +12,000bn cumulative (wk Jun 9)'
)
if new_footer != footer_text:
    data['footer']['council_conditions_text'] = new_footer
    print("2g: OMO updated in footer council_conditions_text")

# STEP 2h: Foreign flow row YTD sub text
for kpi in data['pulse']['kpis']:
    if kpi['label'] == 'Foreign Flow YTD':
        old_sub = kpi['sub']
        kpi['sub'] = "−$2.43bn YTD (May-end) · est −$2.80bn through Jun 10 · −$370mn Jun 2–10"
        print("2h: Foreign Flow YTD sub updated")

# STEP 2j: action_bar price_date and prices
ab = data['action_bar']
old_pd = ab.get('price_date', '')
ab['price_date'] = "12 Jun"
print(f"2j: price_date updated from '{old_pd}' to '12 Jun'")

for bucket in ab.get('buckets', []):
    for ticker in bucket.get('tickers', []):
        t = ticker['ticker']
        if t == 'POW':
            ticker['price'] = "13,500"
            ticker['chg'] = "-0.4%"
            ticker['chg_class'] = "down"
            print("2j: POW price updated to 13,500 (Jun 12)")
        elif t == 'ACB':
            ticker['price'] = "26,500"
            ticker['chg'] = "+2.1%"
            ticker['chg_class'] = "up"
            print("2j: ACB price updated to 26,500 (Jun 12)")
        elif t == 'MSB':
            # MSB not in action_bar CORE/WATCH buckets but mark if found
            ticker['price'] = "15,000"
            print("2j: MSB price updated to 15,000 (Jun 12)")
        # Other symbols: keep price but tag price_date note
        # (all share the same price_date field at bucket level, already set to 12 Jun)

# STEP 2k: DXY ~135 suspect label
def add_dxy_suspect(text):
    result = text.replace(
        'DXY ~135',
        'DXY ~135 [SUSPECT — proxy; last good reconstructed 98.1]'
    ).replace(
        'DXY 135',
        'DXY ~135 [SUSPECT — proxy; last good reconstructed 98.1]'
    )
    return result

# regime verdict_text
old = data['regime']['verdict_text']
new = add_dxy_suspect(old)
if new != old:
    data['regime']['verdict_text'] = new
    print("2k: DXY suspect label added to regime verdict_text")

# events
for ev in data['events']:
    for field in ['what', 'note']:
        old = ev.get(field, '')
        new = add_dxy_suspect(old)
        if new != old:
            ev[field] = new
            print(f"2k: DXY suspect label added in event '{ev.get('who','')[:40]}' field '{field}'")

# risks
for level in ['high', 'medium']:
    for risk in data['risks'].get(level, []):
        for field in ['title', 'sub']:
            old = risk.get(field, '')
            new = add_dxy_suspect(old)
            if new != old:
                risk[field] = new
                print(f"2k: DXY suspect label added in risk '{risk.get('title','')[:40]}' field '{field}'")

# STEP 2l: Tag inference lines in flow card
for ev in data['events']:
    who = ev.get('who', '')
    if 'Khối Ngoại' in who or 'HOSE Flow' in who:
        note = ev.get('note', '')
        new_note = note
        if 'VIC block was mechanical' in new_note and new_note.find('[INTERPRETATION]') < new_note.find('VIC block was mechanical') - 5 or '[INTERPRETATION]' not in new_note:
            new_note = new_note.replace(
                'VIC block was mechanical',
                '[INTERPRETATION] VIC block was mechanical',
                1
            )
        if 'FPT +1,501 wk1' in new_note:
            # Only add tag if not already tagged right before
            pos = new_note.find('FPT +1,501 wk1')
            already = '[INTERPRETATION]' in new_note[max(0,pos-20):pos]
            if not already:
                new_note = new_note.replace(
                    'FPT +1,501 wk1',
                    '[INTERPRETATION] FPT +1,501 wk1',
                    1
                )
        if new_note != note:
            ev['note'] = new_note
            print("2l: INTERPRETATION tags added to flow card note")

print("\nWriting updated JSON...")
with open('data/raw/pm_dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("JSON write complete.")
