"""One-shot patch: apply Jun-12 council-approved fixes to pm_dashboard_data.json."""
import json

INPUT = "data/raw/pm_dashboard_data.json"
OUTPUT = INPUT

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

# ---- 1a: meta/as-of dates ----
data["meta"]["data_date"] = "12 Jun 2026 (Jun 12 ATC close)"
data["meta"]["prices_date"] = "12 Jun 2026 (Jun 12 ATC)"
data["meta"]["updated_date"] = "12 Jun 2026"

# ---- 1a: VNI KPI ----
for kpi in data["pulse"]["kpis"]:
    if kpi["label"] == "VN-Index":
        kpi["value"] = "1,791.65"
        kpi["sub"] = "Jun 12 ATC · recovery failed: 1,803.71 → 1,791.65 · back at 1,790 support · still below 1,810"
        break

# ---- 1a+c: regime verdict_text ----
data["regime"]["verdict_text"] = (
    "⚠ Council 12 Jun: NO_NEW_BUYS (vote 2-2 HOLD vs NO_NEW_BUYS — risk bias). "
    "VNI 1,791.65 (Jun 12 ATC) — recovery failed (1,803.71→1,791.65); retesting 1,790 support; still below 1,810 gate. "
    "Breadth 24.1% (defense; T1/T2 blocked). Dist 8/25d (Jun 12) · DOWNTREND_WARNING. "
    "Chair: mandatory TRIM HSG (sma150 −19.7%) + TCX (ema10 −12%); tighten GEE/GEX on confirmation. "
    "Book gross 0.55 / cash 0.45. P(MA50 breach 20d)=60.8% — price-action bias active. "
    "Upgrade gate: VN30 reclaims MA20 AND dist_days ≤3 same session. "
    "DXY 135.0 [SUSPECT — Yahoo proxy failed sanity; FRED reconstructed ~98.1] / UST10Y 4.49% — outflow condition still met."
)

# ---- 1c: Dist Days pill ----
for pill in data["regime"]["pills"]:
    if "Dist Days 6" in pill.get("text", ""):
        pill["text"] = "Dist 8/25d (Jun 12) · DOWNTREND_WARNING"
        break

# ---- 1a: VNI pill ----
for pill in data["regime"]["pills"]:
    if "VNI 1,803" in pill.get("text", ""):
        pill["text"] = "VNI 1,791 · Recovery Failed"
        break

# ---- 1c: Breadth KPI ----
for kpi in data["pulse"]["kpis"]:
    if kpi["label"] == "Breadth":
        kpi["value"] = "Dist 8/25d"
        kpi["sub"] = "Dist 8/25d (Jun 12) · DOWNTREND_WARNING · Cloud 24.1% · Defense zone"
        break

# ---- 1e: Foreign Flow YTD KPI ----
for kpi in data["pulse"]["kpis"]:
    if kpi["label"] == "Foreign Flow YTD":
        kpi["value"] = "~−$2.43bn"
        kpi["sub"] = "YTD May-end (est −$2.80bn through Jun 10) · −$370mn Jun 2–10 · −$730mn May"
        break

# ---- 1b: prepend new Jun 12 A3 scan event ----
new_a3_event = {
    "glyph": "⚠",
    "glyph_color": "r",
    "who": "A3 ATC Daily Scan · 12 Jun · Phase36 · 95 symbols",
    "who_tags": [{"type": "f", "text": "Fact"}],
    "what": (
        '<span class="tag tag-f">Fact</span> Phase36 A3 scan (Jun 12 ATC close, 95 symbols). '
        '<strong>VNI 1,791.65</strong> — recovery failed (1,803.71→1,791.65); retesting 1,790 support. '
        'Regime: VNINDEX BEAR (EMA20<EMA100). Cloud breadth: 24.1% (defense zone — T2 adds <strong>blocked</strong>). '
        'Portfolio TRAIL_EXIT: <strong>1 active — POW only</strong> (close 13.50 < trail 13.97; priority exit). '
        'MSB no longer TRAIL_EXIT (SKIP_VNINDEX_BEAR at 15.0). '
        'Holdings NOT in scan universe: <strong>STB, TCX, GEE, GAS</strong> (verify coverage). '
        'New T1 candidates: 0. Dist 10/25/50: 3/8/9 — VNINDEX raw: DOWNTREND_WARNING.'
    ),
    "note": (
        "→ Bear scenario active (VNI < 1,810). Execute exit on POW TRAIL_EXIT. "
        "STB/TCX/GEE/GAS not in scan — verify positions manually. "
        "Next gate: VNI reclaim 1,810 + breadth >40%."
    ),
    "date_warn": None,
}
# Insert at index 1 (after council event at index 0)
data["events"].insert(1, new_a3_event)

# ---- 1d: OMO contradiction in risks ----
for risk in data["risks"]["high"]:
    if "Interbank ON spike" in risk.get("title", ""):
        risk["sub"] = risk["sub"].replace(
            "SBV offsetting via OMO +2,000bn WoW.",
            "SBV offsetting via OMO +2,000bn [SOURCE UNCLEAR — verify OMO window; manual_inputs.json shows omo_net=+12,000bn (field label undated)].",
        )
        break

# ---- 1e: Foreign sustained selling risk ----
for risk in data["risks"]["high"]:
    if "Foreign sustained selling" in risk.get("title", ""):
        risk["sub"] = (
            '<span class="tag tag-f">Fact</span> '
            "−$2.43bn YTD May-end (est −$2.80bn through Jun 10); "
            "−$730mn May; 84% order-book — broad and clean. Not derivative hedging."
        )
        break

# ---- 1f: DXY in VNI Jun 8 event ----
for event in data["events"]:
    if "VN-Index · Jun 8" in event.get("who", ""):
        event["what"] = event["what"].replace(
            "DXY ~135",
            "DXY 135.0 [SUSPECT — Yahoo proxy failed sanity; FRED reconstructed ~98.1]",
        )
        break

# ---- 1g: VCB note in foreign flow event ----
for event in data["events"]:
    if "Khối Ngoại" in event.get("who", ""):
        event["note"] = event["note"].replace(
            "VCB: both foreign + prop buying Jun 8 (positive signal).",
            "INTERPRETATION: VCB saw foreign+prop buying Jun 8. Context only — does NOT override A3 exits; execute per A3. (VCB no longer a portfolio holding — historical context only.)",
        )
        break

# ---- 1h: unescape double-escaped HTML entities ----
def unescape_fields(obj):
    if isinstance(obj, dict):
        return {k: unescape_fields(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [unescape_fields(v) for v in obj]
    elif isinstance(obj, str):
        return obj.replace("&lt;", "<").replace("&gt;", ">")
    return obj

data = unescape_fields(data)

# ---- 1i: action_bar price_date and ticker prices from Jun 12 scan ----
data["action_bar"]["price_date"] = "12 Jun"

scan_closes = {
    "ACB": ("26,500", "+2.1%", "up"),
    "VCB": ("61,600", "−0.5%", "down"),
    "BID": ("41,050", "−0.2%", "down"),
    "POW": ("13,500", "−0.4%", "down"),
    "MSB": ("15,000", "+2.7%", "up"),
    "OCB": ("12,450", "+1.2%", "up"),
    "HSG": ("11,700", "−1.7%", "down"),
    "VIX": ("17,050", "−1.0%", "down"),
    "VND": ("17,100", "+0.4%", "up"),
}

for bucket in data["action_bar"]["buckets"]:
    for ticker in bucket["tickers"]:
        sym = ticker["ticker"]
        if sym in scan_closes:
            p, chg, cls = scan_closes[sym]
            ticker["price"] = p
            ticker["chg"] = chg
            ticker["chg_class"] = cls
        # POW special: flag A3 exit
        if sym == "POW":
            ticker["thesis"] = (
                "Power · hot season · ⚠ A3 TRAIL_EXIT active — exit first; "
                "broker BUY ratings do not override"
            )
            ticker["flow"] = "⚠ TRAIL_EXIT"
            ticker["flow_class"] = "down"
        # VCB note update
        if sym == "VCB":
            ticker["thesis"] = "Anchor bank · foreign buy (historical context — not a current holding)"

# ---- 1j: footer price source ----
data["footer"]["sources"] = data["footer"]["sources"].replace(
    "FireAnt ATC 05 Jun 2026", "FireAnt ATC 12 Jun 2026"
)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("DONE: pm_dashboard_data.json patched successfully.")
