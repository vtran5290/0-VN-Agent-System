"""
PM Regime Dashboard Generator
Reads data/raw/pm_dashboard_data.json (manually-curated content) and optionally
merges live macro fields from data/raw/manual_inputs.json + data/state/regime_state.json,
then renders the full dark-theme HTML to reports/pm_regime_dashboard_latest.html.

Usage:
  python scripts/reporting/generate_pm_regime_dashboard.py
  python scripts/reporting/generate_pm_regime_dashboard.py --output reports/pm_regime_dashboard_latest.html
  python scripts/reporting/generate_pm_regime_dashboard.py --data data/raw/pm_dashboard_data.json

Edit data/raw/pm_dashboard_data.json to update regime verdict, KPIs, tickers, events, risks,
and forward triggers. Re-run this script to regenerate the HTML.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger("pm_dashboard")

# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg:      #0d0f1a;
  --s1:      #13162a;
  --s2:      #1a1e35;
  --border:  #252a45;
  --text:    #e2e8f0;
  --muted:   #64748b;
  --faint:   #374060;

  --g:  #10b981;
  --a:  #f59e0b;
  --r:  #f43f5e;
  --b:  #3b82f6;
  --p:  #a855f7;
  --gb: rgba(16,185,129,.10);
  --ab: rgba(245,158,11,.10);
  --rb: rgba(244,63,94,.10);
  --bb: rgba(59,130,246,.10);
  --pb: rgba(168,85,247,.10);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 13px;
  line-height: 1.5;
}
.page { max-width: 1200px; margin: 0 auto; padding: 32px 24px 48px; }

/* HEADER */
.hdr { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 28px; border-bottom: 1px solid var(--border); padding-bottom: 14px; }
.hdr-title { font-size: 15px; font-weight: 700; letter-spacing: .02em; }
.hdr-meta { font-size: 11px; color: var(--muted); }

/* SECTION LABEL */
.slabel { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }

/* S1 REGIME VERDICT */
.verdict {
  background: var(--s1);
  border: 1px solid var(--border);
  border-left: 4px solid var(--a);
  border-radius: 8px;
  padding: 18px 22px;
  margin-bottom: 24px;
}
.verdict-text { font-size: 15px; font-weight: 600; line-height: 1.5; margin-bottom: 12px; }
.pills { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.pill { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; letter-spacing: .02em; }
.pill-g { background: var(--gb); color: var(--g); border: 1px solid rgba(16,185,129,.25); }
.pill-a { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.25); }
.pill-r { background: var(--rb); color: var(--r); border: 1px solid rgba(244,63,94,.25); }
.pill-b { background: var(--bb); color: var(--b); border: 1px solid rgba(59,130,246,.25); }

.inval {
  background: rgba(244,63,94,.06);
  border: 1px solid rgba(244,63,94,.22);
  border-radius: 5px;
  padding: 10px 14px;
  margin-top: 4px;
}
.inval-label { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--r); margin-bottom: 7px; }
.inval ul { margin: 0; padding-left: 14px; font-size: 11px; line-height: 1.9; }
.inval ul li { color: var(--muted); }
.inval ul li strong { color: var(--r); }

/* Evidence tags */
.tag { display: inline-block; font-size: 8px; font-weight: 700; padding: 1px 4px; border-radius: 2px; text-transform: uppercase; letter-spacing: .04em; vertical-align: middle; margin-right: 2px; }
.tag-f { background: var(--gb); color: var(--g); border: 1px solid rgba(16,185,129,.2); }
.tag-s { background: var(--bb); color: var(--b); border: 1px solid rgba(59,130,246,.2); }
.tag-e { background: var(--pb); color: var(--p); border: 1px solid rgba(168,85,247,.2); }
.tag-a { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.2); }

/* S2 PULSE STRIP */
.pulse { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin-bottom: 24px; }
@media (max-width: 900px) { .pulse { grid-template-columns: repeat(4, 1fr); } }
.kpi { background: var(--s1); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; }
.kpi-label { font-size: 10px; color: var(--muted); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 5px; }
.kpi-val { font-size: 18px; font-weight: 700; line-height: 1.1; }
.kpi-sub { font-size: 10px; margin-top: 3px; }
.kpi.ok   { border-top: 2px solid var(--g); }
.kpi.warn { border-top: 2px solid var(--a); }
.kpi.bad  { border-top: 2px solid var(--r); }
.up   { color: var(--g); }
.down { color: var(--r); }
.flat { color: var(--a); }
.dim  { color: var(--muted); }

/* S3 EVENTS */
.moves { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 24px; }
@media (max-width: 700px) { .moves { grid-template-columns: 1fr; } }
.move-card { background: var(--s1); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; display: flex; align-items: flex-start; gap: 12px; }
.move-glyph { font-size: 18px; flex-shrink: 0; width: 28px; text-align: center; margin-top: 1px; }
.move-body { flex: 1; }
.move-who { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 2px; }
.move-what { font-size: 12px; color: var(--text); line-height: 1.4; }
.move-tag { font-size: 10px; color: var(--muted); margin-top: 3px; }
.date-warn { display: inline-block; margin-top: 3px; padding: 1px 6px; background: var(--ab); border: 1px solid rgba(245,158,11,.3); border-radius: 3px; font-size: 9px; color: var(--a); font-weight: 600; }

/* S3.5 RISK STRIP */
.risk-strip {
  background: var(--s1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 700px) { .risk-strip { grid-template-columns: 1fr; } }
.risk-col-title { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.risk-row { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(37,42,69,.5); }
.risk-row:last-child { border-bottom: none; }
.risk-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.dot-r { background: var(--r); }
.dot-a { background: var(--a); }
.risk-body { flex: 1; }
.risk-title { font-size: 11px; font-weight: 600; }
.risk-sub   { font-size: 10px; color: var(--muted); margin-top: 1px; }

/* S4 POSITIONING BOARD */
.board { background: var(--s1); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; margin-bottom: 24px; }
.board table { width: 100%; min-width: 900px; border-collapse: collapse; }
.board th {
  background: var(--s2);
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.board td { padding: 8px 12px; border-bottom: 1px solid rgba(37,42,69,.6); vertical-align: top; font-size: 12px; }
.board tr:last-child td { border-bottom: none; }
.bucket-header td { font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; padding: 6px 12px; color: var(--muted); }
.bucket-core  .bucket-header td { background: rgba(16,185,129,.06); color: var(--g); }
.bucket-watch .bucket-header td { background: rgba(245,158,11,.06); color: var(--a); }
.bucket-cat   .bucket-header td { background: rgba(59,130,246,.06); color: var(--b); }
.bucket-avoid .bucket-header td { background: rgba(244,63,94,.06);  color: var(--r); }
.bucket-core  tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--g); }
.bucket-watch tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--a); }
.bucket-cat   tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--b); }
.bucket-avoid tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--r); }

.tk          { font-weight: 700; font-size: 13px; }
.thesis      { color: var(--muted); font-size: 11px; }
.price-col   { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.trigger-col { color: var(--muted); font-size: 11px; min-width: 160px; }
.inval-col   { color: var(--r);     font-size: 11px; min-width: 160px; }
.date-col    { color: var(--b);     font-size: 11px; min-width: 110px; font-weight: 600; white-space: nowrap; }
.flow-col    { text-align: center; font-size: 13px; white-space: nowrap; }
.prev        { font-size: 10px; color: var(--faint); margin-left: 3px; }

/* S5 FORWARD TRIGGERS */
.triggers { display: flex; flex-direction: column; }
.trigger-item { display: flex; align-items: center; gap: 16px; padding: 11px 0; border-bottom: 1px solid var(--border); }
.trigger-item:last-child { border-bottom: none; }
.trigger-date { width: 80px; flex-shrink: 0; font-size: 11px; font-weight: 700; color: var(--a); font-variant-numeric: tabular-nums; }
.trigger-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; background: var(--faint); }
.trigger-dot.hot { background: var(--a); box-shadow: 0 0 6px var(--a); }
.trigger-text { flex: 1; font-size: 12px; }
.trigger-text strong { color: var(--text); }
.trigger-text span { color: var(--muted); }

/* FOOTER */
.footer { margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 10px; color: var(--muted); line-height: 1.7; }
""".strip()


# ── HTML renderers ─────────────────────────────────────────────────────────────

def _render_pills(pills: list[dict]) -> str:
    parts = []
    for p in pills:
        c = p.get("color", "a")
        parts.append(f'<span class="pill pill-{c}">{escape(p["text"])}</span>')
    return "\n      ".join(parts)


def _render_invalidation(conditions: list[dict]) -> str:
    items = []
    for c in conditions:
        items.append(
            f'<li><strong>{escape(c["trigger"])}</strong> → {escape(c["consequence"])}</li>'
        )
    return "\n        ".join(items)


def _render_kpi(k: dict) -> str:
    val_class = k.get("value_class", "")
    sub_class = k.get("sub_class", "dim")
    val_span = f'<span class="{val_class}">{escape(k["value"])}</span>' if val_class else escape(k["value"])
    return (
        f'<div class="kpi {k["status"]}">\n'
        f'  <div class="kpi-label">{escape(k["label"])}</div>\n'
        f'  <div class="kpi-val">{val_span}</div>\n'
        f'  <div class="kpi-sub {sub_class}">{escape(k["sub"])}</div>\n'
        f'</div>'
    )


def _render_event(ev: dict) -> str:
    glyph_color = ev.get("glyph_color", "a")
    who_tags_html = "".join(
        f'<span class="tag tag-{t["type"]}">{escape(t["text"])}</span>'
        for t in ev.get("who_tags", [])
    )
    date_warn_html = ""
    if ev.get("date_warn"):
        date_warn_html = f'\n        <div class="date-warn">{ev["date_warn"]}</div>'
    return (
        f'<div class="move-card">\n'
        f'  <div class="move-glyph" style="color:var(--{glyph_color})">{ev["glyph"]}</div>\n'
        f'  <div class="move-body">\n'
        f'    <div class="move-who">{escape(ev["who"])} {who_tags_html}</div>\n'
        f'    <div class="move-what">{ev["what"]}</div>\n'
        f'    <div class="move-tag">{escape(ev["note"])}</div>'
        f'{date_warn_html}\n'
        f'  </div>\n'
        f'</div>'
    )


def _render_risk_rows(risks: list[dict], dot_class: str) -> str:
    rows = []
    for r in risks:
        rows.append(
            f'<div class="risk-row">\n'
            f'  <div class="risk-dot {dot_class}"></div>\n'
            f'  <div class="risk-body">\n'
            f'    <div class="risk-title">{escape(r["title"])}</div>\n'
            f'    <div class="risk-sub">{r["sub"]}</div>\n'
            f'  </div>\n'
            f'</div>'
        )
    return "\n      ".join(rows)


def _render_ticker_row(t: dict, bucket_id: str) -> str:
    chg_class = t.get("chg_class", "")
    if chg_class == "prev":
        chg_html = f'<span class="prev">{escape(t["chg"])}</span>'
    elif chg_class:
        chg_html = f'<span class="{chg_class}">{escape(t["chg"])}</span>'
    else:
        chg_html = escape(t["chg"])

    flow_class = t.get("flow_class", "dim")
    return (
        f'<tr>\n'
        f'  <td><span class="tk">{escape(t["ticker"])}</span></td>\n'
        f'  <td><span class="thesis">{escape(t["thesis"])}</span></td>\n'
        f'  <td class="price-col">{escape(t["price"])} {chg_html}</td>\n'
        f'  <td class="flow-col {chg_class if chg_class != "prev" else "dim"}">{"▲" if chg_class == "up" else ("▼" if chg_class == "down" else "—")}</td>\n'
        f'  <td class="trigger-col">{escape(t["trigger"])}</td>\n'
        f'  <td class="inval-col">{escape(t["invalidation"])}</td>\n'
        f'  <td class="date-col">{escape(t["event_date"])}</td>\n'
        f'  <td class="flow-col {flow_class}">{escape(t["flow"])}</td>\n'
        f'</tr>'
    )


def _render_bucket(b: dict) -> str:
    bid = b["id"]
    header_row = f'<tr class="bucket-header"><td colspan="8">▸ {escape(b["label"])}</td></tr>'
    rows = "\n        ".join(_render_ticker_row(t, bid) for t in b["tickers"])
    return (
        f'<tbody class="bucket-{bid}">\n'
        f'  {header_row}\n'
        f'  {rows}\n'
        f'</tbody>'
    )


def _render_forward_trigger(tr_: dict) -> str:
    hot_class = " hot" if tr_.get("hot") else ""
    return (
        f'<div class="trigger-item">\n'
        f'  <div class="trigger-date">{escape(tr_["date"])}</div>\n'
        f'  <div class="trigger-dot{hot_class}"></div>\n'
        f'  <div class="trigger-text"><strong>{escape(tr_["title"])}</strong> <span>{tr_["body"]}</span></div>\n'
        f'</div>'
    )


# ── Main builder ──────────────────────────────────────────────────────────────

def build_html(data: dict) -> str:
    meta    = data["meta"]
    regime  = data["regime"]
    pulse   = data["pulse"]
    events  = data["events"]
    risks   = data["risks"]
    action  = data["action_bar"]
    triggers = data["forward_triggers"]
    footer  = data["footer"]

    pills_html       = _render_pills(regime["pills"])
    inval_html       = _render_invalidation(regime["invalidation_conditions"])
    kpis_html        = "\n    ".join(_render_kpi(k) for k in pulse["kpis"])
    events_html      = "\n    ".join(_render_event(e) for e in events)
    high_risks_html  = _render_risk_rows(risks["high"],   "dot-r")
    med_risks_html   = _render_risk_rows(risks["medium"], "dot-a")
    buckets_html     = "\n      ".join(_render_bucket(b) for b in action["buckets"])
    price_date       = escape(action.get("price_date", ""))
    triggers_html    = "\n      ".join(_render_forward_trigger(t) for t in triggers)

    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PM Vietnam — Regime Dashboard</title>
<style>
{_CSS}
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-title">PM · Vietnam Regime Dashboard</div>
    <div class="hdr-meta">Data: {escape(meta["data_date"])} · Prices: {escape(meta["prices_date"])} · Updated: {escape(meta["updated_date"])} · <span style="color:var(--b)">Council conditions applied: {escape(meta["council_conditions_date"])}</span></div>
  </div>

  <!-- S1 · REGIME VERDICT -->
  <div class="slabel">Regime</div>
  <div class="verdict">
    <div class="verdict-text">{escape(regime["verdict_text"])}</div>
    <div class="pills">
      {pills_html}
    </div>
    <div class="inval">
      <div class="inval-label">⚠ Thesis Invalidation — any one flips the regime verdict</div>
      <ul>
        {inval_html}
      </ul>
    </div>
  </div>

  <!-- S2 · PULSE STRIP -->
  <div class="slabel">Macro &amp; Market Pulse <span class="tag tag-f" style="vertical-align:middle">All: Fact</span></div>
  <div class="pulse">
    {kpis_html}
  </div>

  <!-- S3 · EVENTS -->
  <div class="slabel">Events</div>
  <div class="moves">
    {events_html}
  </div>

  <!-- S3.5 · RISK DASHBOARD -->
  <div class="slabel">Risk Dashboard <span style="font-size:9px;color:var(--b);font-weight:400;text-transform:none;letter-spacing:0">[above Action Bar — council hierarchy]</span></div>
  <div class="risk-strip">
    <div>
      <div class="risk-col-title" style="color:var(--r)">● High</div>
      {high_risks_html}
    </div>
    <div>
      <div class="risk-col-title" style="color:var(--a)">● Medium</div>
      {med_risks_html}
    </div>
  </div>

  <!-- S4 · ACTION BAR -->
  <div class="slabel">Action Bar <span style="font-size:9px;color:var(--b);font-weight:400;text-transform:none;letter-spacing:0">[trigger · invalidation · event date added per council Condition 4]</span></div>
  <div class="board">
    <table>
      <thead>
        <tr>
          <th style="width:80px">Ticker</th>
          <th style="min-width:130px">Thesis</th>
          <th style="width:120px;text-align:right">Price · {price_date}</th>
          <th style="width:45px;text-align:center">Chg%</th>
          <th style="min-width:160px;color:var(--g)">▲ Trigger Level</th>
          <th style="min-width:160px;color:var(--r)">✕ Invalidation</th>
          <th style="min-width:110px;color:var(--b)">📅 Event Date</th>
          <th style="width:55px;text-align:center">Flow</th>
        </tr>
      </thead>
      {buckets_html}
    </table>
  </div>

  <!-- S5 · FORWARD TRIGGERS -->
  <div class="slabel">Forward Triggers</div>
  <div style="background:var(--s1);border:1px solid var(--border);border-radius:8px;padding:6px 18px 10px;">
    <div class="triggers">
      {triggers_html}
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    {escape(footer["sources"])} &nbsp;|&nbsp;
    {escape(footer["prev_note"])} &nbsp;|&nbsp;
    <strong style="color:var(--b)">Council conditions applied {escape(meta["council_conditions_date"])}:</strong>
    <span style="color:var(--b)">{escape(footer["council_conditions_text"])}</span> &nbsp;|&nbsp;
    Council-reviewed by {escape(footer["council_reviewer"])} &nbsp;|&nbsp; Not financial advice. &nbsp;|&nbsp;
    <span style="color:var(--faint)">Generated: {generated_ts}</span>
  </div>

</div>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PM Regime Dashboard Generator")
    parser.add_argument(
        "--data",
        default=str(ROOT / "data" / "raw" / "pm_dashboard_data.json"),
        help="Path to pm_dashboard_data.json",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports" / "pm_regime_dashboard_latest.html"),
        help="Output HTML path",
    )
    args = parser.parse_args()

    data_path   = Path(args.data)
    output_path = Path(args.output)

    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Building PM Regime Dashboard from: %s", data_path)
    html = build_html(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written: %s", output_path)


if __name__ == "__main__":
    main()
