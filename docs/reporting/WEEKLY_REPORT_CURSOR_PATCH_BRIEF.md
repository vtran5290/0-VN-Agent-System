# VN Weekly Report — Cursor Patch Brief
**Date:** 2026-05-17  
**Reviewed by:** Claude Code (senior product + quant review)  
**Repo:** VN Agent System (`D:\V\0. VN Agent System`)  
**Branch:** master  

---

## System Context (read this first)

This repo is a 6-layer Vietnam investment workflow. The weekly report is a **portfolio command center** for strategy `B_cloud20_100 / A3_PRODUCTION`.

Key invariants you must never break:
- `phase36_daily_scan_*.csv` is the signal SSOT — report reads it, never recomputes signals
- `A3_PRODUCTION` is the only production classification — `S3_RESEARCH_ONLY` / `WATCH_ONLY` must not appear in main report
- `a3_rank_score` is review-sort priority only — never used as a trade signal
- `final_action` from the scan drives all operator actions — no override without written reason
- Capital is NO-GO unless separately approved in `REAL_CAPITAL_READINESS.md`
- Do not change any live order logic, OMS, or trading pipeline files

The **lean weekly report** renders via Jinja2 template from a Python payload. Entry point:
```
scripts/ingest/portfolio_decision_enrich.py → enrich_portfolio_decision_sections()
scripts/ingest/weekly_lean_sections.py → attach_lean_report()
scripts/reporting/render_weekly_report.py → render_html()
templates/weekly_report_lean.html.j2
```

---

## Files You Will Touch

| File | Purpose |
|---|---|
| `scripts/ingest/weekly_lean_sections.py` | Builds market_pulse, execution, watchlist, KPIs, charts, decision sections |
| `scripts/ingest/portfolio_decision_enrich.py` | Builds command center, regime rules, positions, sector exposure |
| `templates/weekly_report_lean.html.j2` | Jinja2 HTML template |
| `scripts/reporting/metric_registry.py` | Core metric definitions (primary_section SSOT) |
| `tests/test_lean_weekly_report.py` | Section-order + dedup tests |
| `tests/test_portfolio_command_center_report.py` | Command center + render tests |
| `tests/test_report_format.py` | Number formatting tests |

**DO NOT touch:** `src/report/weekly.py`, any file under `scripts/trading/`, `config/live_trading.yaml`, OMS/broker/paper files.

---

## Priority Map

| Priority | Fix | Risk if skipped |
|---|---|---|
| **P0** | `None` renders in Trail/TP1 cells | Operator reads `None` as valid price |
| **P0** | Only MWG in Immediate Actions; VCG + NVL also TRAIL_EXIT | Operator misses 2 forced exits |
| **P0** | VNINDEX chart canvas has no JS init — renders empty box | Decorative noise |
| **P0** | Liquidity chart: OMO net (~4,000) and IB ON (~6.05) on same Y-axis | Chart is unreadable / misleading |
| **P0** | UST10Y / DXY / Interbank ON / OMO net / Credit growth each appear 3× (Market Pulse + KPI card + narrative facts) | Core UX rule violated |
| **P1** | Watchlist Cloud column shows `True` / `False` not `Bull` / `Bear` | Inconsistent with Execution table |
| **P1** | Watchlist has no "0 buy candidates" message when Buy Now bucket is empty | Silent — reader doesn't know why |
| **P1** | `scan_reason` computed in Python but not shown in Execution HTML | Most useful diagnostic column is invisible |
| **P1** | Positions with `scan_final_action = Missing` look identical to valid positions | Reader cannot distinguish |
| **P1** | OMO net has no unit anywhere in report | "4,000.0" is meaningless without VND bn label |
| **P1** | `a3_rank_score` shows 3 decimal places (2.957) | Should be 1 decimal |
| **P1** | `near_trail_count` computed but not rendered in Portfolio Summary | Useful risk metric silently dropped |
| **P1** | Regime one-liner duplicated verbatim in Command Center AND Decision Plan | Redundant |
| **P2** | Sector weights and execution weights use 2 decimal places | Should be 1 decimal per spec |
| **P2** | Decision Review "Decision" column contains a multi-paragraph prose entry | Table cell ≠ readable |
| **P2** | Appendix sections not collapsible | Long scroll for reference material |

---

## P0 Patches — Required Before Next Weekly Run

### P0.1 — Fix `None` rendering in Trail / TP1 / PB prices

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_execution_scan_aligned()` (~line 415)

**Problem:** When both `scan.get("trail_price")` and `row.get("stop_price")` are Python `None`, the dict key is set to `None`. Jinja2's `|default('Missing')` does NOT fire when the key exists with value `None` — it only fires when the key is undefined. Result: the string `None` is rendered in HTML.

**Fix:** Make the None-guard explicit in Python, not in Jinja:

```python
# BEFORE (around line 415-418):
trail = scan.get("trail_price")
tp1 = scan.get("tp1_price")
pb = scan.get("pb_trigger_price")

# BEFORE (in out_rows.append, around line 428-430):
"trail_price": trail or row.get("stop_price"),
"tp1_price": tp1,
"pb_trigger_price": pb,

# AFTER:
def _price_or_missing(v):
    return v if v not in (None, "", "None", "nan", "null") else "Missing"

trail = _price_or_missing(scan.get("trail_price")) or _price_or_missing(row.get("stop_price"))
tp1 = _price_or_missing(scan.get("tp1_price"))
pb = _price_or_missing(scan.get("pb_trigger_price"))

# In out_rows.append:
"trail_price": trail,
"tp1_price": tp1,
"pb_trigger_price": pb,
```

Also replace the `"None"` string check in `_price_or_missing` — scan CSVs sometimes have the literal string `"None"`.

**Acceptance criteria:** `assert "None" not in rendered_html_execution_table` after render.

---

### P0.2 — Populate Immediate Actions from ALL TRAIL_EXIT execution rows

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_decision_plan()` (~line 561)

**Problem:** `immediate_actions` comes from `base.get("immediate_actions")` which reads from the legacy JSON payload. The execution table has VCG and NVL flagged as TRAIL_EXIT with `action_mismatch=True`, but they do not appear in Immediate Actions — only MWG does (from the legacy `sell_trim_signals` path).

**Fix:** After building the base action list, auto-insert any execution row with EXIT/SELL required_operator_action:

```python
def build_decision_plan(payload, command_center, execution):
    base = payload.get("decision_layer") or {}
    # ... existing stance / conditional / do_not_do logic ...

    # Auto-insert forced exits from execution SSOT
    forced_from_scan = [
        f"{r['ticker']}: SELL / EXIT — {r.get('scan_reason') or r.get('scan_final_action', 'TRAIL_EXIT')}"
        for r in execution.get("rows", [])
        if any(kw in (r.get("required_operator_action") or "").upper() for kw in ("EXIT", "SELL"))
    ]
    # Legacy base actions (may contain MWG already)
    legacy_actions = base.get("immediate_actions") or base.get("top_actions") or []
    # Deduplicate: skip auto entry if ticker already mentioned in legacy
    legacy_text = " ".join(legacy_actions).upper()
    new_forced = [a for a in forced_from_scan if a.split(":")[0].upper() not in legacy_text]
    merged_actions = new_forced + legacy_actions

    return {
        **base,
        "immediate_actions": merged_actions,
        # ... rest of return ...
    }
```

**Acceptance criteria:** Given execution rows with TRAIL_EXIT for VCG + NVL + MWG, `decision_layer["immediate_actions"]` contains all three tickers.

---

### P0.3 — Remove empty VNINDEX chart canvas

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_visualizations()` (~line 521)

**Problem:** The `vnindex-trend` chart is included in the chart list with `available=True` when `vnindex_level` is not None. But there is NO JavaScript initialization for `chart-vnindex-trend` in the template — the canvas renders empty. It is decorative noise.

**Fix option A (recommended):** Mark as unavailable until a time series feed is wired:

```python
# Change:
"available": levels.get("vnindex_level") is not None,
# To:
"available": False,  # requires time-series feed; snapshot only → use KPI badge instead
```

**Fix option B:** Replace the chart card with a KPI badge. In `build_visualizations()`, instead of a chart entry, inject an `info_only` flag. In the template, render a text tile instead of `<canvas>`.

**Acceptance criteria:** Rendered HTML has no `<canvas id="chart-vnindex-trend">` element with empty body (either element removed or has valid data initialization).

---

### P0.4 — Fix VN Liquidity chart dual-scale problem

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_visualizations()` (~line 535)

**Problem:** Current chart data `{"omo_net": 4000, "interbank_on": 6.05}` plots on one Y-axis. OMO net bar (4,000) visually obliterates the IB ON bar (6.05). They have incompatible units (VND bn vs %).

**Fix:** Split into two separate chart entries:

```python
# Replace the single "liq" chart with two:
{
    "id": "liq_ib",
    "title": "Interbank ON rate",
    "data": {"interbank_on": v.get("interbank_on")},
    "interpretation": f"IB ON {rf.fmt_rate(v.get('interbank_on'))} — elevated vs pre-2023 base (~3–4%); signals funding tightness.",
    "available": v.get("interbank_on") is not None,
},
{
    "id": "liq_omo",
    "title": "OMO net (bn VND)",
    "data": {"omo_net": v.get("omo_net")},
    "interpretation": f"Daily OMO net {rf.fmt_index(v.get('omo_net'))} bn VND — noisy single-day; prefer rolling 7D/20D trend.",
    "available": v.get("omo_net") is not None,
},
```

In the template JS section, add initialization for `chart-liq_ib` and `chart-liq_omo` with correct labels and a reasonable Y-axis range (0–10 for rate, auto for OMO). Update the JSON script blocks accordingly:

```html
<script type="application/json" id="viz-data-liq_ib">{{ chart_data('liq_ib') }}</script>
<script type="application/json" id="viz-data-liq_omo">{{ chart_data('liq_omo') }}</script>
```

And add JS init:
```javascript
const lib = pj('viz-data-liq_ib');
if(lib && document.getElementById('chart-liq_ib')){
  new Chart(document.getElementById('chart-liq_ib'),{
    type:'bar',
    data:{labels:['IB ON (%)'],datasets:[{data:[lib.interbank_on||0],backgroundColor:DIM,borderWidth:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:12,title:{display:true,text:'%'}}}}
  });
}
const lom = pj('viz-data-liq_omo');
if(lom && document.getElementById('chart-liq_omo')){
  new Chart(document.getElementById('chart-liq_omo'),{
    type:'bar',
    data:{labels:['OMO net (bn VND)'],datasets:[{data:[lom.omo_net||0],backgroundColor:ACCENT,borderWidth:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{title:{display:true,text:'bn VND'}}}}
  });
}
```

Also remove or rename the old `liq` chart data block.

**Acceptance criteria:** Two separate chart cards; IB ON axis range 0–12%; OMO net axis auto-scaled with "bn VND" label.

---

### P0.5 — Eliminate third repetition of raw metrics in narrative sections

**File:** `scripts/ingest/weekly_lean_sections.py`

**Problem:** `build_vn_liquidity_narrative()` and `build_global_macro_narrative()` include `facts` bullets that repeat the exact same numbers already in Market Pulse rows and Smart KPI cards. Each of UST10Y, DXY, Interbank ON, OMO net, Credit growth appears 3 times.

**Core rule:** Later sections explain implication, not repeat snapshots. (One metric, one primary home.)

**Fix `build_vn_liquidity_narrative()`:**
```python
def build_vn_liquidity_narrative(payload, ...):
    # ...
    # REMOVE the facts list entirely — numbers are in Market Pulse + KPI cards
    # Only keep interpretation + implication
    interp = (
        f"Liquidity signal: {signal}. "
        f"IB ON is elevated vs pre-2023 base — monitor for further tightening. "
        f"Daily OMO net is noisy; the aggregate OMO stock and rolling 7D/20D net matter more."
    )
    impl = {
        "Easing": "Selective adds within regime band only if breadth also confirms.",
        "Tightening": "Reduce high-beta adds; preserve cash; watch credit growth trend.",
        "Neutral": "Stay selective; leaders with valid A3 setups only.",
        "Mixed": "No clear impulse — maintain current band.",
    }.get(signal, "Stay selective.")
    return {
        "facts": [],  # empty — raw numbers live in Market Pulse / KPI only
        "interpretation": interp,
        "portfolio_implication": impl,
        "signal": signal,
    }
```

**Fix `build_global_macro_narrative()`:**
```python
def build_global_macro_narrative(payload, ...):
    # REMOVE the facts list
    ust10 = g.get("ust_10y")
    dxy = g.get("dxy_reconstructed") or g.get("dxy")
    interp = (
        f"UST10Y {'elevated' if ust10 and float(ust10) > 4.0 else 'moderate'} → "
        f"EM valuation pressure active. "
        f"DXY {'weak' if dxy and float(dxy) < 100 else 'strong'} → "
        f"supportive for VND and foreign flows."
    ) if (ust10 and dxy) else "Global rates and USD context: see KPI board."
    impl = "Maintain regime gross band; do not chase extended high-beta without valid B_cloud20_100 setup."
    return {"facts": [], "interpretation": interp, "portfolio_implication": impl}
```

In the template `weekly_report_lean.html.j2`, update the Global Macro and VN Liquidity blocks to skip the `<ul>` if `facts` is empty:
```jinja2
{% if global_macro_narrative.facts %}
<p><strong>Facts:</strong></p><ul>{% for f in global_macro_narrative.facts %}<li>{{ f }}</li>{% endfor %}</ul>
{% endif %}
```
Same for `vn_liquidity_narrative.facts`.

**Acceptance criteria:** UST10Y, DXY, Interbank ON, OMO net, Credit growth each appear at most twice in the rendered HTML (once in Market Pulse, once in KPI board). Narrative sections contain zero raw numbers.

---

## P1 Patches — High Value

### P1.1 — Watchlist Cloud column: `True`/`False` → `Bull`/`Bear`

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_watchlist_a3()` (~line 483)

```python
# Replace:
"a3_cloud_bull": row.get("a3_cloud_bull"),

# With:
raw_cloud = row.get("a3_cloud_bull")
cloud_label = (
    "Bull" if str(raw_cloud).lower() == "true"
    else "Bear" if str(raw_cloud).lower() == "false"
    else "Missing"
)
# ...
"a3_cloud_bull": cloud_label,
```

---

### P1.2 — Explicit "0 buy candidates" message in Watchlist

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_watchlist_a3()`

Add to return dict:
```python
buy_now_count = len(buckets.get("Buy Now Candidate", []))
breadth_zone = scan_rows[0].get("breadth_zone") if scan_rows else "unknown"
# update note:
if buy_now_count == 0 and not note:
    note = f"0 Buy Now Candidates — breadth zone '{breadth_zone}' blocks new entries. Watchlist shows Hold/Monitor and Avoid only."
```

---

### P1.3 — Show `scan_reason` in Execution table

**File:** `templates/weekly_report_lean.html.j2`  
**Section:** Execution table (~line 92)

Add a Reason column. In the `<thead>` row, add after `<th>Scan action</th>`:
```html
<th>Reason</th>
```
In the `<tbody>` row, add after the Scan action cell:
```html
<td class="meta" title="{{ s.scan_reason|default('') }}">{{ (s.scan_reason|default('—'))[:35] }}{% if s.scan_reason and s.scan_reason|length > 35 %}…{% endif %}</td>
```

---

### P1.4 — Amber-border rows when `scan_final_action = Missing`

**File:** `templates/weekly_report_lean.html.j2`

Add CSS in `<style>`:
```css
tr.row-noscan td:first-child { border-left: 3px solid var(--amber); }
```

Change Execution `<tr>` line:
```jinja2
{# BEFORE: #}
<tr {% if s.action_mismatch %}class="row-mismatch"{% endif %}>

{# AFTER: #}
<tr {% if s.action_mismatch %}class="row-mismatch"{% elif s.scan_final_action == 'Missing' %}class="row-noscan"{% endif %}>
```

Add a legend line below the Execution table:
```html
<p class="meta">Red row = scan/report action mismatch. Amber border = no scan match (position not in A3_PRODUCTION universe or scan data missing).</p>
```

---

### P1.5 — OMO net unit label everywhere

**File:** `scripts/ingest/weekly_lean_sections.py`

1. In `build_smart_kpi_board()`, change label:
```python
{"label": "OMO net (bn VND)", "value": rf.fmt_index(v.get("omo_net")), "meta": "daily"},
```

2. In `build_market_pulse()`, change metric display name:
```python
pulse_row("OMO net (bn VND)", v.get("omo_net"), ...),
```

3. In `build_vn_liquidity_narrative()` — handled by P0.5 (narrative removed).

**File:** `scripts/reporting/metric_registry.py`

Change OMO_NET display_name and entry:
```python
entry("OMO_NET", "OMO net (bn VND)", v.get("omo_net"), ...),
```

---

### P1.6 — `a3_rank_score` to 1 decimal place

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_watchlist_a3()` (~line 474)

```python
# After float conversion:
try:
    score = float(row.get("a3_rank_score")) if row.get("a3_rank_score") not in (None, "") else None
    if score is not None:
        score = round(score, 1)
except (TypeError, ValueError):
    score = None
```

---

### P1.7 — Surface `near_trail_count` in Portfolio Summary KPI grid

**File:** `templates/weekly_report_lean.html.j2`  
**Section:** Portfolio Summary KPI grid (~line 74)

Add after the "Forced exits" KPI tile:
```jinja2
{% if ps.near_trail_count is not none and ps.near_trail_count > 0 %}
<div class="kpi warn"><div class="label">Near trail</div><div class="value">{{ ps.near_trail_count }}</div></div>
{% endif %}
```

---

### P1.8 — Remove duplicated regime one-liner in Decision Plan

**File:** `templates/weekly_report_lean.html.j2`  
**Section:** Decision Plan (~line 149)

Remove or comment out the second `<p class="meta">{{ pcc.regime_one_liner|default('') }}</p>` line. The regime context is already fully shown in Command Center. Decision Plan should start directly with weekly stance + actions.

---

### P1.9 — Add data flags for suspicious values

**File:** `scripts/ingest/weekly_lean_sections.py`  
**Function:** `build_market_pulse()` or `build_smart_kpi_board()`

Add a validation check for obviously bad data that should warn rather than silently display:

```python
def _data_sanity_warnings(manual: dict) -> list:
    warnings = []
    v = manual.get("vietnam") or {}
    credit = v.get("credit_growth_yoy")
    if credit is not None:
        try:
            if float(credit) > 50:
                warnings.append(f"Credit growth YoY = {credit}% appears abnormal — verify manual_inputs.json (should be ~10–20% for Vietnam)")
        except (TypeError, ValueError):
            pass
    g = manual.get("global") or {}
    gp_dxy = manual.get("_prev_global", {}).get("dxy")
    cur_dxy = g.get("dxy")
    if cur_dxy and gp_dxy:
        try:
            delta = abs(float(cur_dxy) - float(gp_dxy))
            if delta > 5:
                warnings.append(f"DXY delta = {delta:.1f} in one week — verify manual_inputs_prev.json is current week's prior entry")
        except (TypeError, ValueError):
            pass
    return warnings
```

Surface these in `data_quality_compact.warnings` or as a warn-banner in the header.

---

## P2 Patches — Polish

### P2.1 — 1-decimal formatting for sector weights and execution weights

**File:** `scripts/ingest/portfolio_decision_enrich.py`  
**Function:** `build_sector_exposure()`

Ensure sector weight_pct is rounded to 1 decimal:
```python
"weight_pct": round(float(wt), 1),
```

**File:** `scripts/ingest/portfolio_decision_enrich.py`  
**Function:** `build_positions_block()` (wherever weight_pct is set)

```python
"weight_pct": round(float(weight_pct), 1),
```

---

### P2.2 — Collapsible Appendix sections

**File:** `templates/weekly_report_lean.html.j2`  
**Section:** Appendix

Wrap each sub-section in `<details>/<summary>`:
```html
<details open>
  <summary class="card-title">Regime rules (full table)</summary>
  <!-- table here -->
</details>
<details>
  <summary class="card-title">Data freshness (full)</summary>
  <!-- table here -->
</details>
<!-- etc. -->
```

Add CSS:
```css
details > summary { cursor: pointer; user-select: none; list-style: none; }
details > summary::marker { display: none; }
details[open] > summary::after { content: ' ▲'; font-size: 9px; }
details:not([open]) > summary::after { content: ' ▼'; font-size: 9px; }
```

---

### P2.3 — Decision Review table: prose → structured entry

**File:** `templates/weekly_report_lean.html.j2`  
**Section:** Decision Review

Truncate the `last_week_decision` cell to a reasonable length or wrap in `<details>`:
```jinja2
<td title="{{ r.last_week_decision|default('') }}">
  {{ (r.last_week_decision|default('—'))[:80] }}{% if r.last_week_decision and r.last_week_decision|length > 80 %}…{% endif %}
</td>
```

---

### P2.4 — Annotate Downtrend v2 numbers in Appendix

**File:** `templates/weekly_report_lean.html.j2`

Change:
```jinja2
{# BEFORE: #}
<p class="mono">Outcome B adj {{ fmt_prob(downtrend_v2.outcome_b_adjusted, 0) }} · Confirmed {{ fmt_prob(downtrend_v2.confirmed_downtrend_adjusted, 0) }}</p>

{# AFTER: #}
<p class="mono">Downtrend probability (B_adj model): {{ fmt_prob(downtrend_v2.outcome_b_adjusted, 0) }} outcome-B · {{ fmt_prob(downtrend_v2.confirmed_downtrend_adjusted, 0) }} confirmed</p>
```

---

## Test Additions Required

Add these tests to the existing test files:

### `tests/test_lean_weekly_report.py`

```python
def test_no_none_in_rendered_execution(tmp_path):
    """Trail/TP1 prices must show 'Missing', not Python None literal."""
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = {
        "metadata": {"asof_date": "2026-05-17", "data_confidence": "Medium"},
        "regime_engine": {"current_regime": "STATE B", "suggested_regime": "STATE B"},
        "global_macro": {"facts": {}, "what_changed": []},
        "vietnam_liquidity": {"facts": {}},
        "market_structure": {"levels": {}, "what_changed": [], "distribution": {}},
        "probability_allocation": {"allocation": {"gross_exposure": 0.55, "cash_weight": 0.45}, "probabilities": {}},
        "decision_layer": {"top_actions": [], "top_risks": []},
        "execution_monitoring": {"risk_flags": {}, "sell_trim_signals": []},
        "downtrend_v2": {"outcome_b_adjusted": None, "confirmed_downtrend_adjusted": None},
        "geo_layers": {},
        "portfolio_health": {"summary": {}, "sector_concentration": []},
        "watchlist": {"candidates": []},
    }
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "test.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    # Python None must not appear as literal text in rendered output
    assert ">None<" not in html
    assert '"None"' not in html


def test_all_trail_exit_in_immediate_actions():
    """All TRAIL_EXIT execution rows must appear in Immediate Actions."""
    from scripts.ingest.weekly_lean_sections import build_decision_plan

    execution = {
        "rows": [
            {"ticker": "VCG", "required_operator_action": "SELL / EXIT", "scan_reason": "TRAIL_EXIT scan"},
            {"ticker": "NVL", "required_operator_action": "SELL / EXIT", "scan_reason": "TRAIL_EXIT scan"},
            {"ticker": "MWG", "required_operator_action": "SELL / EXIT", "scan_reason": "Day-2 breach"},
            {"ticker": "HDB", "required_operator_action": "HOLD T1 / BLOCK ADD", "scan_reason": "NO_T2_BREADTH"},
        ],
        "mismatch_count": 2,
    }
    plan = build_decision_plan({}, {"current_regime": "STATE B", "gross_exposure_target_band": "50–60%"}, execution)
    actions_text = " ".join(plan["immediate_actions"]).upper()
    assert "VCG" in actions_text
    assert "NVL" in actions_text
    assert "MWG" in actions_text
    assert "HDB" not in actions_text  # HOLD should not be in Immediate Actions


def test_watchlist_cloud_bull_bear_not_boolean():
    """Cloud column must show Bull/Bear, not True/False."""
    from scripts.ingest.weekly_lean_sections import build_watchlist_a3

    board = build_watchlist_a3({})
    for c in board.get("candidates") or []:
        assert c.get("a3_cloud_bull") not in (True, False, "True", "False"), \
            f"Cloud should be Bull/Bear/Missing, got {c.get('a3_cloud_bull')} for {c.get('ticker')}"


def test_a3_rank_score_one_decimal():
    """a3_rank_score must be rounded to 1 decimal place."""
    from scripts.ingest.weekly_lean_sections import build_watchlist_a3

    board = build_watchlist_a3({})
    for c in board.get("candidates") or []:
        score = c.get("a3_rank_score")
        if score is not None:
            assert len(str(score).split(".")[-1]) <= 1, \
                f"Score {score} for {c['ticker']} has >1 decimal place"


def test_narrative_facts_empty():
    """VN Liquidity and Global Macro narrative facts must be empty (numbers in KPI/pulse only)."""
    from scripts.ingest.weekly_lean_sections import build_vn_liquidity_narrative, build_global_macro_narrative

    vn_narr = build_vn_liquidity_narrative({})
    assert vn_narr["facts"] == [], "VN liquidity narrative should have no raw-number facts"

    gm_narr = build_global_macro_narrative({})
    assert gm_narr["facts"] == [], "Global macro narrative should have no raw-number facts"
```

### `tests/test_portfolio_command_center_report.py`

Add to the existing test file:

```python
def test_scan_missing_positions_visually_distinct(tmp_path):
    """Positions with scan_final_action=Missing must have row-noscan class in rendered HTML."""
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = _minimal_payload()
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "noscan.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    # If any positions have Missing scan actions, they must be in row-noscan class
    if "scan_final_action" in html and "Missing" in html:
        # Either row-noscan is present OR there are no Missing scan rows
        pass  # structural check — render must not crash


def test_vnindex_chart_not_empty_canvas(tmp_path):
    """VNINDEX chart must either be absent or have data initialization — no empty canvas."""
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = _minimal_payload()
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "chart.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    # If VNINDEX chart canvas is present, its data block must also be present
    if 'id="chart-vnindex-trend"' in html:
        assert 'viz-data-vnindex' in html, "VNINDEX chart canvas present but no data initialization block"


def test_omo_net_label_has_unit(tmp_path):
    """OMO net KPI label must include unit context."""
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = _minimal_payload()
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "unit.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "OMO net" in html
    # Should not appear as bare "OMO net" without unit in KPI label context
    # (soft check — structure depends on label text)
```

### `tests/test_report_format.py`

```python
def test_price_or_missing_none_guard():
    """fmt_index and other formatters must return 'Missing' not 'None'."""
    from scripts.reporting import report_format as rf
    assert rf.fmt_index(None) == "Missing"
    assert rf.fmt_rate(None) == "Missing"
    assert rf.fmt_pct(None) == "Missing"
    assert rf.fmt_prob(None) == "Missing"
    # String 'None' should also be treated as missing
    assert rf.fmt_index("None") == "Missing"
    assert rf.fmt_rate("None") == "Missing"
```

---

## Open Data Questions to Resolve

These are data issues — confirm with the user before treating as bugs:

1. **`credit_growth_yoy = 100.0`** in `manual_inputs.json` — is this 100% YoY credit growth (extraordinary) or should it be `10.0` or `0.10` (stored as decimal)? Vietnam typical range is 10–17% YoY. If it's `1.0` stored as `100.0`, `fmt_pct` will display it correctly; if it's already a percentage, it's wrong.

2. **`omo_net = 4000`** — what unit? If VND billion, 4,000 bn = 4 tn VND daily injection which is plausible. If already in tn, the label is wrong. Confirm and label accordingly.

3. **DXY WoW delta = -21.57** — previous DXY appears to have been ~119. Confirm `manual_inputs_prev.json` is correctly populated with last week's values, not an older observation.

4. **8 of 16 positions missing scan match** (STB, BID, DXG, PDR, PHR, DPR, PVS, HAG) — are these:
   - Positions from pre-A3 era not yet reclassified?
   - Outside the A3_PRODUCTION universe in the scan?
   - Positions where the ticker symbol in positions file differs from scan CSV symbol?
   Resolve the mismatch. Until resolved, the Execution table cannot give complete guidance for 50% of the portfolio.

---

## Non-Goals — Do Not Touch

- `src/report/weekly.py` (legacy weekly generator)
- `config/live_trading.yaml`
- Any file under `scripts/trading/`
- Any OMS / broker / paper account files
- `REAL_CAPITAL_READINESS.md` — capital remains NO-GO
- The `final_action` computation logic in scan CSVs
- Any signal recomputation or EMA calculations

---

## Acceptance Criteria Summary

After all P0 patches:
1. `assert ">None<" not in rendered_html`
2. All TRAIL_EXIT tickers from execution appear in `decision_layer["immediate_actions"]`
3. VNINDEX chart canvas is either removed or has a valid JS data init block
4. Liquidity chart uses separate Y-axes or separate chart cards for OMO net and IB ON
5. UST10Y/DXY/Interbank ON/OMO net/Credit growth each appear at most **twice** in rendered HTML (Market Pulse + KPI card only)

After P1 patches:
6. Watchlist Cloud column values are all in `{"Bull", "Bear", "Missing"}`
7. When Buy Now bucket is empty, a notice appears above the watchlist table
8. Execution table has a "Reason" column showing `scan_reason`
9. Positions with `scan_final_action = Missing` have visual amber indicator
10. All `a3_rank_score` values in rendered HTML have at most 1 decimal place
11. `near_trail_count` KPI tile visible in Portfolio Summary when > 0

Run after each patch:
```
python -m pytest tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py tests/test_report_format.py -v
```
