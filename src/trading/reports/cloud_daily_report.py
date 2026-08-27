"""Cloud Daily Report — operator decision support for A3/S3 strategy.

Read-only: reads CSVs, writes HTML/MD/JSON only.
No external JS/CSS dependencies.
No auto orders. No S3 live capital.

Includes VNINDEX Distribution Risk Lens v1.2 (Section G) — context only; does not change final_action.
"""
from __future__ import annotations

import html
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.trading.reports.distribution_risk_card import (
    load_distribution_risk_latest,
    refresh_distribution_risk_for_reports,
    render_distribution_risk_html,
    render_distribution_risk_md,
)
from src.trading.reports.rs_correction_card import (
    load_rs_correction_latest,
    refresh_rs_correction_for_reports,
    render_rs_correction_html,
    render_rs_correction_md,
)
from src.trading.reports.rs_c3_card import (
    build_rs_c3_section_for_cloud_daily,
)
from src.trading.reports.seasonality_card import (
    load_seasonality_data,
    render_seasonality_html,
    render_seasonality_md,
)
from src.trading.reports.report_suite_common import (
    SUITE_NAV_CSS,
    PERMISSION_PRECEDENCE_CLOUD,
    build_inst_accum_ticker_index,
    build_structural_ta_index,
    load_institutional_accumulation_compact,
    load_position_context,
    load_structural_ta_compact,
    position_context_by_symbol,
    render_inst_accum_cell,
    render_provenance_header,
    render_structural_ta_cards_section,
    render_suite_nav,
    structural_ta_file_meta,
)

REPO = Path(__file__).resolve().parents[3]
SCAN_DIR = REPO / "data/research/portfolio_optimization/missing_work"
INTRADAY_DIR = REPO / "data/research/intraday"
REPORTS_DIR = REPO / "data/research/reports"
HOLDINGS_PATH = REPO / "data/trading/holdings.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: Any, digits: int = 2) -> str:
    """Format numeric value; return '—' for None/NaN."""
    if v is None:
        return "—"
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return "—"
        return f"{fv:.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _badge(text: str, color: str) -> str:
    """Return HTML badge span."""
    return f'<span class="badge bg-{color}">{_esc(text)}</span>'


def _esc(x: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(x if x is not None else ""))


def _signed_pct(v: Any) -> str:
    """Format a signed percentage, or '—' for None."""
    try:
        return f"{float(v):+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _dashboard_t2_permission_display(
    regime_bull: bool | None,
    breadth_pct: float | None,
    breadth_t2_perm: bool,
) -> tuple[str, str]:
    """Dashboard display only — does not change scan ``final_action`` or OMS."""
    if regime_bull is True and breadth_pct is not None and breadth_pct < 0.40:
        return "CAUTION", "amber"
    if breadth_t2_perm:
        return "OK", "green"
    if not breadth_t2_perm:
        return "BLOCKED", "red"
    return "OK", "green"


def _dashboard_t2_adds_label(
    regime_bull: bool | None,
    breadth_pct: float | None,
    breadth_t2_perm: bool,
) -> tuple[str, str]:
    """Human-readable T2 row for CIO permission table (display only)."""
    label, color = _dashboard_t2_permission_display(regime_bull, breadth_pct, breadth_t2_perm)
    if label == "CAUTION":
        return "Caution (breadth <40%, participation warning)", color
    if label == "BLOCKED":
        return "Blocked (breadth <40% or permission denied)", color
    return "OK", color


_SECTION_G_BREADTH_FOOTNOTE = (
    "Breadth below 40% = participation warning only; it cannot restrict T2 by itself "
    "when VNINDEX regime is BULL. Scan rows may still show NO_T2_BREADTH — operator "
    "uses caution, not a hard dashboard block. "
    "2024–now breadth-zone inversion is research context only, not production evidence. "
    "VNINDEX bear blocks new T1. Sector L4 = dashboard warning only."
)


def _col(df: pd.DataFrame, col: str, default: Any = None) -> pd.Series:
    """Get column from DataFrame or return series of defaults."""
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _get(row: dict, key: str, default: Any = None) -> Any:
    """Safe dict get."""
    val = row.get(key, default)
    if val is None:
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
    except TypeError:
        pass
    return val


def normalize_bool(value: Any) -> "bool | None":
    """Normalize bool-like values to Python True/False/None.

    Handles: bool, numpy.bool_, int 0/1, strings 'true'/'false'/'1'/'0'/'yes'/'no'.
    Returns None for NaN, None, or unrecognized values.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes"):
            return True
        if v in ("false", "0", "no"):
            return False
        return None
    try:
        fv = float(value)
        if math.isnan(fv):
            return None
        return fv != 0.0
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #0d0f12;
  --panel: #13161b;
  --card: #181c22;
  --border: #252a35;
  --accent: #00c896;
  --red: #f05050;
  --amber: #f0a030;
  --blue: #4a9eff;
  --text: #d8dde8;
  --dim: #7a8399;
  --muted: #4a5168;
}
body { font-family: "IBM Plex Sans", Inter, system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility; letter-spacing: -0.01em; line-height: 1.6; }
.container { max-width: 1280px; margin: 0 auto; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 16px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.25); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin: 2px; vertical-align: middle; }
.bg-green { background: #1a3a1a; color: #00c896; border: 1px solid #2d6a2d; }
.bg-amber { background: #3a2800; color: #f0a030; border: 1px solid #6a4e00; }
.bg-red { background: #3a1010; color: #f05050; border: 1px solid #6a2020; }
.bg-gray { background: #1e2a38; color: var(--blue); border: 1px solid #2d3f57; }
.section-title { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--dim); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin: 16px 0 8px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.action-card { border-left: 4px solid; }
.action-card.green { border-color: #4caf50; }
.action-card.amber { border-color: #f0a030; }
.action-card.red { border-color: #f05050; }
.action-list { margin: 4px 0; padding-left: 20px; }
.action-list li { margin: 4px 0; font-size: 13px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; margin: 8px 0; }
th, td { border: 1px solid var(--border); padding: 4px 8px; text-align: left; vertical-align: middle; }
th { background: var(--panel); font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--dim); position: sticky; top: 0; z-index: 1; vertical-align: middle; }
.td-trunc { max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: help; display: inline-block; vertical-align: middle; }
tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
.row-green td:first-child { border-left: 3px solid #4caf50; }
.row-amber td:first-child { border-left: 3px solid #f0a030; }
.row-red td:first-child { border-left: 3px solid #f05050; }
.row-gray td:first-child { border-left: 3px solid var(--muted); }
.warn-banner { background: #3a0f0f; border: 1px solid #c0392b; border-left: 3px solid var(--red); border-radius: 6px; padding: 12px 16px; margin: 8px 0; color: #f7a0a0; font-weight: 600; }
.preview-banner { background: #3a2800; border: 1px solid #c9a227; border-left: 3px solid var(--amber); border-radius: 6px; padding: 12px 16px; margin: 8px 0; color: #f0a030; font-weight: 600; }
.s3-section { border: 1px dashed #4a3000; background: #111005; }
details summary { cursor: pointer; color: var(--blue); font-weight: 600; padding: 4px 0; }
.meta { color: var(--dim); font-size: 12px; }
.pending { color: #f0a030; font-style: italic; }
.footnote { font-size: 12px; color: var(--muted); margin-top: 4px; }
.subsection-title { font-size: 11px; font-weight: 700; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 2px; margin: 12px 0 4px; }
.nav-bar { background: var(--panel); border-radius: 6px; padding: 6px 12px; margin: 6px 0 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; }
.nav-bar a { color: var(--blue); text-decoration: none; padding: 2px 8px; border-radius: 3px; border: 1px solid var(--border); transition: background 0.1s; }
.nav-bar a:hover { background: #1e3050; }
/* Sidebar TOC */
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 158px; position: sticky; top: 0; height: 100vh; overflow-y: auto; border-right: 1px solid var(--border); background: var(--panel); padding: 12px 0; flex-shrink: 0; }
.sidebar-logo { padding: 8px 12px 10px; font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; border-bottom: 1px solid var(--border); margin-bottom: 8px; font-weight: 700; }
.sidebar h3 { margin: 10px 12px 3px; font-size: 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
.sidebar a { display: block; margin: 1px 6px; padding: 5px 8px; color: var(--dim); text-decoration: none; font-size: 11px; border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sidebar a:hover, .sidebar a.active { background: #1e2330; color: var(--text); }
@media (max-width: 860px) { .sidebar { display: none; } }
.ctx-tag { display: inline-block; background: #0f1e2e; color: #6a9cc8; border: 1px solid #1e3650; border-radius: 3px; padding: 0 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; vertical-align: middle; margin-left: 4px; }
.tilt-tag { font-size: 10px; font-weight: 600; margin-left: 4px; vertical-align: middle; }
.tilt-lead { color: #00c896; }
.tilt-lag { color: var(--muted); opacity: 0.85; }
.arc-killed { color: var(--muted); opacity: 0.65; }
.phase-d-arc { margin: 8px 0 12px 18px; font-size: 13px; line-height: 1.55; }
.phase-d-arc li { margin: 6px 0; }
.ssot-tag { display: inline-block; background: #0f2010; color: var(--accent); border: 1px solid #1e4020; border-radius: 3px; padding: 0 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; vertical-align: middle; margin-left: 4px; }
.ctx-safety { background: #0c1825; border-left: 3px solid #2a5080; border-radius: 0 4px 4px 0; padding: 6px 12px; margin: 6px 0; font-size: 12px; color: #7aa8d0; }
.scroll-table { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 4px 0; }
.cio-cockpit { background: #0d1e30; border: 1px solid #2a5080; border-left: 3px solid var(--blue); border-radius: 6px; padding: 12px 16px; margin: 10px 0; }
.cio-oneliner { font-size: 14px; font-weight: 700; color: #e0eaff; margin-bottom: 10px; }
.cio-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; margin-top: 6px; }
.cio-block { background: var(--panel); border-radius: 4px; padding: 6px 10px; }
.cio-block-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dim); margin-bottom: 4px; }
.cio-block ul { margin: 4px 0 0 14px; padding: 0; font-size: 13px; }
.cio-block li { margin: 2px 0; }
.cio-block table { font-size: 13px; margin: 0; }
.ar-p1 { color: #f05050; font-weight: 700; }
.ar-p2 { color: #f0a030; font-weight: 700; }
.ar-p3 { color: var(--blue); font-weight: 700; }
.ar-p4 { color: var(--dim); }
.ar-p5 { color: var(--muted); }
.port-must-act { border-left: 4px solid #f05050; }
.port-verify { border-left: 4px solid #f0a030; }
.port-hold { border-left: 4px solid var(--muted); }
/* Chart popup modal */
.fa-sym { cursor: pointer; color: var(--blue); font-weight: 700; border-bottom: 1px dashed #4a7ab8; padding: 0 2px; border-radius: 2px; transition: background 0.1s, color 0.1s; }
.fa-sym:hover { background: #1a3050; color: #aaccff; }
#fa-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 9998; }
#fa-overlay.on { display: block; }
#fa-modal { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); width: min(1100px,95vw); height: min(700px,88vh); background: #131722; border: 1px solid #2a4060; border-radius: 12px; z-index: 9999; flex-direction: column; box-shadow: 0 16px 48px rgba(0,0,0,0.6); overflow: hidden; }
#fa-modal.on { display: flex; }
#fa-modal-hdr { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--panel); border-bottom: 1px solid var(--border); flex-shrink: 0; }
#fa-modal-title { font-weight: 700; color: var(--blue); font-size: 14px; flex: 1; }
#fa-modal-link { color: var(--dim); font-size: 12px; text-decoration: none; transition: opacity 0.15s; }
#fa-modal-link:hover { opacity: 0.75; text-decoration: underline; }
#fa-modal-close { cursor: pointer; color: var(--dim); font-size: 1.3rem; padding: 0 5px; border-radius: 4px; line-height: 1; user-select: none; }
#fa-modal-close:hover { color: var(--text); background: #1e3050; }
#fa-modal-body { flex: 1; overflow: hidden; background: var(--bg); position: relative; }
#fa-modal-body iframe { width: 100%; height: 100%; border: none; display: block; }
#fa-fallback { display: none; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 20px; color: var(--dim); font-size: 14px; text-align: center; }
#fa-fallback strong { color: var(--text); font-size: 16px; }
#fa-fallback a { color: var(--blue); font-size: 14px; font-weight: 700; padding: 8px 22px; border: 1px solid #2a5080; border-radius: 6px; text-decoration: none; margin: 4px; transition: background 0.1s; }
#fa-fallback a:hover { background: #1a3050; }
/* MA Urgency badges */
.urg-high { background: #3d0808; color: #ff6b6b; border: 1px solid #7a1515; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.07em; vertical-align: middle; margin-left: 5px; }
.urg-med { background: #2e1f00; color: #f0a030; border: 1px solid #5a3d00; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.07em; vertical-align: middle; margin-left: 5px; }
.urg-low { background: #0d1f10; color: #6ecb80; border: 1px solid #1e4028; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; vertical-align: middle; margin-left: 5px; }
/* MA Profile card */
.ma-prof { background: #090f18; border: 1px solid #1a2e48; border-radius: 6px; padding: 8px 12px; margin-top: 8px; min-width: 260px; max-width: 380px; }
.ma-prof-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 20px; margin-top: 4px; }
.ma-prof-lbl { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 1px; }
.ma-prof-val { color: #ccd8f0; font-weight: 600; font-size: 13px; font-family: "IBM Plex Mono", monospace; }
.ma-prof-src { font-size: 11px; color: #3a6090; margin-top: 6px; border-top: 1px solid #161f2e; padding-top: 4px; }
details.ma-det > summary { list-style: none; cursor: pointer; display: inline; }
details.ma-det > summary::-webkit-details-marker { display: none; }
/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.18); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
""" + SUITE_NAV_CSS

_TV_POPUP_JS = """
<div id="fa-overlay"></div>
<div id="fa-modal">
  <div id="fa-modal-hdr">
    <span id="fa-modal-title">Chart</span>
    <a id="fa-modal-link" href="#" target="_blank" rel="noopener">Mở FireAnt ↗</a>
    <span id="fa-modal-close">&#10005;</span>
  </div>
  <div id="fa-modal-body">
    <iframe id="fa-iframe" allowfullscreen></iframe>
    <div id="fa-fallback">
      <strong id="fa-fallback-title"></strong>
      <span>Mã này không có trên TradingView (UPCOM hoặc đã huỷ niêm yết).</span>
      <div>
        <a id="fa-fallback-fa" href="#" target="_blank" rel="noopener">Xem trên FireAnt ↗</a>
        <a id="fa-fallback-vnd" href="#" target="_blank" rel="noopener">Xem trên VNDirect ↗</a>
      </div>
    </div>
  </div>
</div>
<script>
(function(){
  // HNX-listed stocks (prefix HNX:)
  var HNX=new Set(['NTP','PVS','SHI','VCG','VND','APS','HUT','MBS','PJT','IDC','SGT','SRA','TNG','PXS','VDS','SHS','APG','WSS','PLC','VIT','BCC','HAN','HBS','KLF','VLF','PVI','NVB','SHB','CEO']);
  // UPCOM stocks — TradingView coverage poor; show FireAnt fallback directly
  var UPCOM=new Set(['AAV','ASM','BIG','DSE','DTD','G36','ILS','KSV','L40','PIV','PSI','PVP','ABB','DXS','HNM','PIV','PSD']);

  function tvSym(t){ return (HNX.has(t)?'HNX':'HSX')+':'+t; }

  var overlay=document.getElementById('fa-overlay');
  var modal=document.getElementById('fa-modal');
  var iframe=document.getElementById('fa-iframe');
  var fallback=document.getElementById('fa-fallback');

  function showTVChart(ticker){
    var sym=tvSym(ticker);
    var faUrl='https://fireant.vn/ma-chung-khoan/'+ticker;
    document.getElementById('fa-modal-link').href=faUrl;
    document.getElementById('fa-modal-link').textContent='Mở FireAnt ↗';

    iframe.style.display='block';
    fallback.style.display='none';

    var src='https://www.tradingview.com/widgetembed/?symbol='+encodeURIComponent(sym)
      +'&interval=D&theme=dark&style=1&timezone=Asia%2FHo_Chi_Minh'
      +'&withdateranges=1&locale=en&hide_top_toolbar=0&save_image=0';
    iframe.src=src;
  }

  function showFallback(ticker){
    var faUrl='https://fireant.vn/ma-chung-khoan/'+ticker;
    var vndUrl='https://dstock.vndirect.com.vn/tim-kiem/'+ticker;
    document.getElementById('fa-modal-link').href=faUrl;
    document.getElementById('fa-modal-link').textContent='Mở FireAnt ↗';
    document.getElementById('fa-fallback-title').textContent=ticker+' (UPCOM)';
    document.getElementById('fa-fallback-fa').href=faUrl;
    document.getElementById('fa-fallback-vnd').href=vndUrl;

    iframe.style.display='none';
    fallback.style.display='flex';
  }

  function openChart(ticker){
    document.getElementById('fa-modal-title').textContent=ticker;
    overlay.classList.add('on');
    modal.classList.add('on');
    if(UPCOM.has(ticker)){ showFallback(ticker); }
    else { showTVChart(ticker); }
  }

  function closeChart(){
    overlay.classList.remove('on');
    modal.classList.remove('on');
    iframe.src='about:blank';
    iframe.style.display='block';
    fallback.style.display='none';
  }

  document.getElementById('fa-modal-close').addEventListener('click',closeChart);
  overlay.addEventListener('click',function(e){ if(e.target===overlay) closeChart(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeChart(); });

  function wire(td){
    var t=td.textContent.trim();
    if(/^[A-Z][A-Z0-9]{1,4}$/.test(t)&&!td.querySelector('.fa-sym')){
      td.innerHTML='<span class="fa-sym" title="Chart '+t+'">'+t+'</span>';
      (function(ticker){
        td.querySelector('.fa-sym').addEventListener('click',function(e){
          e.stopPropagation();
          openChart(ticker);
        });
      })(t);
    }
  }

  function wireTickers(){
    document.querySelectorAll('tr[class*="row-"] td:first-child').forEach(wire);
    document.querySelectorAll('table').forEach(function(tbl){
      var fh=tbl.querySelector('thead th:first-child,tr:first-child th:first-child');
      if(fh&&/^symbol$/i.test(fh.textContent.trim())){
        tbl.querySelectorAll('tbody tr td:first-child').forEach(wire);
      }
    });
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',wireTickers);
  else wireTickers();
})();
</script>
"""

# ---------------------------------------------------------------------------
# classify_operator_action
# ---------------------------------------------------------------------------

_A3_SSOT_FINAL_ACTIONS = frozenset({
    "NEW_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH",
    "ADD_T2",
    "NO_T2_BREADTH",
    "WAIT_PB",
    "HOLD_T1_ONLY",
    "TP1_PARTIAL",
    "TRAIL_EXIT",
    "MAX_HOLD_EXIT",
    "SKIP_LIQUIDITY",
    "SKIP_VNINDEX_BEAR",
    "WATCH_ONLY",
})


def classify_operator_action(row: dict, mode: str) -> dict:
    """Return dict with action_group, operator_action, reason."""
    final_action = str(_get(row, "final_action", "")).strip()
    s3_shadow = str(_get(row, "s3_shadow_action", "")).strip()
    is_intraday = mode in ("pre-lunch", "pre-atc")

    planning_action = final_action
    if is_intraday:
        wbfa_plan = str(_get(row, "would_be_final_action", "")).strip()
        if wbfa_plan:
            planning_action = wbfa_plan

    # S3 shadow applies only to watch-only / non-planning rows — not production T1/T2 SSOT actions
    if s3_shadow == "PAPER_S3_SHADOW" and planning_action in (
        "",
        "WATCH_ONLY",
        "INTRADAY_PREVIEW",
    ):
        return {
            "action_group": "S3_PAPER",
            "operator_action": "PAPER_ONLY",
            "reason": "s3_shadow_action=PAPER_S3_SHADOW",
        }

    if is_intraday:
        wbfa = planning_action
        # Map would_be to action_group
        EOD_GROUP_MAP = {
            "NEW_T1": "NEW_T1",
            "NEW_T1_MANUAL_REVIEW_BREADTH": "MANUAL_REVIEW_T1",
            "ADD_T2": "ADD_T2",
            "NO_T2_BREADTH": "T2_BLOCKED",
            "WAIT_PB": "ADD_T2",
            "HOLD_T1_ONLY": "HOLD",
            "TP1_PARTIAL": "EXIT_REVIEW",
            "TRAIL_EXIT": "EXIT_REVIEW",
            "MAX_HOLD_EXIT": "EXIT_REVIEW",
            "SKIP_LIQUIDITY": "SKIP",
            "SKIP_VNINDEX_BEAR": "SKIP",
            "WATCH_ONLY": "SKIP",
        }
        action_group = EOD_GROUP_MAP.get(wbfa, "UNKNOWN")
        # Intraday operator_action is never PREPARE_NEXT_OPEN
        if action_group in ("SKIP", "UNKNOWN", "T2_BLOCKED"):
            operator_action = "NO_ACTION"
        else:
            operator_action = "REVIEW_MANUAL"
        return {
            "action_group": action_group,
            "operator_action": operator_action,
            "reason": f"intraday preview; would_be={wbfa}",
        }

    # EOD mapping (report layer: manual review wording only — no order instructions)
    _EOD_MAP = {
        "NEW_T1":                         ("NEW_T1",           "REVIEW_MANUAL"),
        "NEW_T1_MANUAL_REVIEW_BREADTH":   ("MANUAL_REVIEW_T1", "REVIEW_MANUAL"),
        "ADD_T2":                         ("ADD_T2",           "ADD_T2"),
        "NO_T2_BREADTH":                  ("T2_BLOCKED",       "ADD_BLOCKED_BY_BREADTH"),
        "WAIT_PB":                        ("ADD_T2",           "WAIT_FOR_PULLBACK"),
        "HOLD_T1_ONLY":                   ("HOLD",             "HOLD_ONLY"),
        "TP1_PARTIAL":                    ("EXIT_REVIEW",      "TAKE_PARTIAL"),
        "TRAIL_EXIT":                     ("EXIT_REVIEW",      "REVIEW_TRAIL_EXIT"),
        "MAX_HOLD_EXIT":                  ("EXIT_REVIEW",      "REVIEW_TRAIL_EXIT"),
        "SKIP_LIQUIDITY":                 ("SKIP",             "NO_ACTION"),
        "SKIP_VNINDEX_BEAR":              ("SKIP",             "NO_ACTION"),
        "WATCH_ONLY":                     ("SKIP",             "WATCH_ONLY"),
    }
    if final_action in _EOD_MAP:
        ag, oa = _EOD_MAP[final_action]
    else:
        ag, oa = "UNKNOWN", "NO_ACTION"

    return {
        "action_group": ag,
        "operator_action": oa,
        "reason": f"final_action={final_action}",
    }


# ---------------------------------------------------------------------------
# load_inputs
# ---------------------------------------------------------------------------

def load_inputs(mode: str, scan_path: Path | None = None) -> dict:
    """Load scan_df, intraday_df, intraday_meta, holdings, prev_json, warnings."""
    warnings_list: list[str] = []
    files_used: list[str] = []

    # ---- Resolve mode ----
    if mode == "auto":
        intraday_csv = INTRADAY_DIR / "phase36_intraday_scan_latest.csv"
        if intraday_csv.exists():
            mtime = datetime.fromtimestamp(intraday_csv.stat().st_mtime, tz=timezone.utc)
            age_h = (datetime.now(tz=timezone.utc) - mtime).total_seconds() / 3600
            resolved_mode = "pre-lunch" if age_h <= 6 else "eod"
        else:
            resolved_mode = "eod"
    else:
        resolved_mode = mode

    # ---- EOD scan (SSOT: phase36_daily_scan_latest.csv) ----
    ssot_scan = SCAN_DIR / "phase36_daily_scan_latest.csv"
    _scan_candidates: list[Path] = []
    if scan_path:
        _scan_candidates.append(Path(scan_path))
    if ssot_scan.exists():
        _scan_candidates.append(ssot_scan)
    for cand in (
        SCAN_DIR / "phase36_daily_scan_sample.csv",
        SCAN_DIR / "phase35_daily_scan_sample.csv",
        SCAN_DIR / "phase34_daily_scan_sample.csv",
    ):
        if cand not in _scan_candidates:
            _scan_candidates.append(cand)

    scan_df = pd.DataFrame()
    scan_file_used: Path | None = None
    for cand in _scan_candidates:
        if cand.exists():
            try:
                scan_df = pd.read_csv(cand)
                scan_file_used = cand
                files_used.append(str(cand.relative_to(REPO)))
                if cand != ssot_scan and ssot_scan.exists():
                    warnings_list.append(
                        f"scan_path override: using {cand.name} instead of phase36_daily_scan_latest.csv"
                    )
                break
            except Exception as e:
                warnings_list.append(f"Failed to read {cand.name}: {e}")

    if scan_df.empty:
        warnings_list.append("scan_file_missing: no EOD scan CSV found")
    elif scan_file_used and scan_file_used.resolve() != ssot_scan.resolve() and ssot_scan.exists():
        warnings_list.append(
            "NEEDS_REVIEW: EOD scan not loaded from phase36_daily_scan_latest.csv"
        )

    # ---- Intraday ----
    intraday_df = pd.DataFrame()
    intraday_meta: dict = {}

    if resolved_mode in ("pre-lunch", "pre-atc"):
        intraday_csv = INTRADAY_DIR / "phase36_intraday_scan_latest.csv"
        intraday_meta_path = INTRADAY_DIR / "phase36_intraday_scan_latest_meta.json"
        if intraday_csv.exists():
            try:
                intraday_df = pd.read_csv(intraday_csv)
                files_used.append(str(intraday_csv.relative_to(REPO)))
            except Exception as e:
                warnings_list.append(f"Failed to read intraday CSV: {e}")
        else:
            warnings_list.append("intraday CSV not found")
        if intraday_meta_path.exists():
            try:
                intraday_meta = json.loads(intraday_meta_path.read_text(encoding="utf-8"))
                files_used.append(str(intraday_meta_path.relative_to(REPO)))
            except Exception as e:
                warnings_list.append(f"Failed to read intraday meta: {e}")

    # ---- Portfolio state (SSoT for NAV + current positions) ----
    from src.trading.portfolio_state import (
        PORTFOLIO_STATE_PATH,
        get_current_nav_vnd,
        load_current_positions,
        load_portfolio_state,
    )
    port_state = load_portfolio_state()
    nav_vnd: float | None = None
    positions_df: pd.DataFrame = pd.DataFrame()
    positions_source: str = "missing"
    portfolio_state_path_str: str | None = None

    portfolio_as_of_date: str | None = port_state.get("as_of_date") if port_state else None

    if not port_state:
        warnings_list.append(
            "Portfolio state file missing — NAV/current port context not available."
        )
    else:
        try:
            portfolio_state_path_str = str(PORTFOLIO_STATE_PATH.relative_to(REPO))
        except ValueError:
            portfolio_state_path_str = str(PORTFOLIO_STATE_PATH)
        files_used.append(portfolio_state_path_str)
        nav_vnd = get_current_nav_vnd(port_state)
        if nav_vnd is None:
            warnings_list.append("NAV missing or invalid in portfolio state.")

    positions_df, positions_source = load_current_positions(port_state)

    if positions_source == "missing":
        warnings_list.append(
            "Current positions file missing — duplicate-position check not performed."
        )
    elif "holdings.txt" in positions_source:
        warnings_list.append(
            "Using legacy holdings.txt fallback — consider updating portfolio_state.json positions_path."
        )
    else:
        if positions_source not in files_used:
            files_used.append(positions_source)

    # Symbol list (backward compat; extracted from positions_df)
    holdings: list[str] = []
    if not positions_df.empty and "symbol" in positions_df.columns:
        holdings = positions_df["symbol"].dropna().astype(str).str.upper().tolist()

    # ---- Previous report JSON ----
    prev_json: dict | None = None
    prev_path = REPORTS_DIR / "cloud_daily_report_latest.json"
    if prev_path.exists():
        try:
            prev_json = json.loads(prev_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "mode": resolved_mode,
        "scan_df": scan_df,
        "intraday_df": intraday_df,
        "intraday_meta": intraday_meta,
        "holdings": holdings,
        "nav_vnd": nav_vnd,
        "positions_df": positions_df,
        "positions_source": positions_source,
        "portfolio_state_path": portfolio_state_path_str,
        "portfolio_as_of_date": portfolio_as_of_date,
        "prev_json": prev_json,
        "warnings": warnings_list,
        "scan_path": str(scan_file_used.relative_to(REPO)) if scan_file_used else None,
        "files_used": files_used,
    }


# ---------------------------------------------------------------------------
# HTML/MD helpers
# ---------------------------------------------------------------------------

def _html_table(headers: list[str], rows: list[list[str]], row_classes: list[str] | None = None) -> str:
    th_html = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    rows_html = ""
    for i, row_cells in enumerate(rows):
        cls = ""
        if row_classes and i < len(row_classes):
            cls = f' class="{row_classes[i]}"'
        tds = "".join(f"<td>{cell}</td>" for cell in row_cells)
        rows_html += f"<tr{cls}>{tds}</tr>"
    return f"<table><thead><tr>{th_html}</tr></thead><tbody>{rows_html}</tbody></table>"


def _td_trunc(text: str, max_chars: int = 48) -> str:
    """Truncate text cell with full value in tooltip. Keeps tables scannable."""
    t = str(text)
    if not t or t == "None":
        return "<span style='color:#3a5570'>—</span>"
    if len(t) <= max_chars:
        return _esc(t)
    return f'<span class="td-trunc" title="{_esc(t)}">{_esc(t[:max_chars])}…</span>'


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    head = "| " + " | ".join(headers) + " |"
    body = "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return f"{head}\n{sep}\n{body}"


# ---------------------------------------------------------------------------
# CF observation ledger append (cloud report)
# ---------------------------------------------------------------------------

_CF_OBS_LEDGER = REPO / "data" / "research" / "capital_footprint" / "cf_annotation_observation_ledger.csv"
_CF_OBS_HEADERS = [
    "scan_date", "symbol", "final_action", "current_holding_flag",
    "cf_phase_label", "cf_operator_note", "cf_event_age", "cf_event_cooldown_flag",
    "cf_breadth_regime_bucket", "close_price", "operator_action",
    "forward_5d_return", "forward_10d_return", "forward_20d_return",
    "max_drawdown_20d", "operator_comment", "hindsight_result",
]


def _append_cf_obs_ledger_cloud(
    cf_ann_df: pd.DataFrame,
    holdings_set: set[str],
    scan_date: str,
) -> None:
    """Append today's CF-annotated symbols to the observation ledger CSV."""
    import csv as _csv

    _CF_OBS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _CF_OBS_LEDGER.exists()

    rows_to_write: list[dict] = []
    for _, r in cf_ann_df.iterrows():
        sym = str(r.get("symbol", "")).upper()
        phase = str(r.get("cf_phase_label", "") or "")
        if not phase or phase == "NEUTRAL":
            continue
        rows_to_write.append({
            "scan_date": scan_date,
            "symbol": sym,
            "final_action": "",
            "current_holding_flag": "Y" if sym in holdings_set else "N",
            "cf_phase_label": phase,
            "cf_operator_note": str(r.get("cf_operator_note", "") or ""),
            "cf_event_age": r.get("cf_event_age", ""),
            "cf_event_cooldown_flag": r.get("cf_event_cooldown_flag", ""),
            "cf_breadth_regime_bucket": str(r.get("cf_breadth_regime_bucket", "") or ""),
            "close_price": "",
            "operator_action": "",
            "forward_5d_return": "",
            "forward_10d_return": "",
            "forward_20d_return": "",
            "max_drawdown_20d": "",
            "operator_comment": "",
            "hindsight_result": "",
        })

    if not rows_to_write:
        return

    with open(_CF_OBS_LEDGER, "a", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=_CF_OBS_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows_to_write)


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def build_report(mode: str, inputs: dict, ts: datetime) -> tuple[str, str, dict]:
    """Build HTML, MD, and JSON. Returns (html_str, md_str, json_payload)."""
    scan_df: pd.DataFrame = inputs["scan_df"]
    intraday_df: pd.DataFrame = inputs["intraday_df"]
    intraday_meta: dict = inputs.get("intraday_meta", {})
    holdings: list[str] = inputs.get("holdings", [])
    nav_vnd: float | None = inputs.get("nav_vnd")
    positions_df: pd.DataFrame = inputs.get("positions_df", pd.DataFrame())
    positions_source: str = inputs.get("positions_source", "missing")
    portfolio_state_path: str | None = inputs.get("portfolio_state_path")
    portfolio_as_of_date: str | None = inputs.get("portfolio_as_of_date")
    prev_json: dict | None = inputs.get("prev_json")
    warnings_list: list[str] = list(inputs.get("warnings", []))
    files_used: list[str] = list(inputs.get("files_used", []))
    scan_path_str: str | None = inputs.get("scan_path")
    is_intraday = mode in ("pre-lunch", "pre-atc")

    drl_data = inputs.get("distribution_risk_lens")
    drl_warns = list(inputs.get("distribution_risk_warnings") or [])
    rs_data = inputs.get("rs_correction_lens")
    rs_warns = list(inputs.get("rs_correction_warnings") or [])
    rs_c3_html_block: str | None = inputs.get("rs_c3_html")
    rs_c3_warns: list[str] = list(inputs.get("rs_c3_warnings") or [])
    _seasonality_data = load_seasonality_data()
    if drl_data is None:
        drl_data, load_warns = load_distribution_risk_latest()
        drl_warns.extend(load_warns)

    # ---- E&MA Research: load primary MA levels for holdings/watchlist ----
    _ma_levels_map: dict[str, dict] = {}
    _ma_levels_path = REPO / "data/state/ma_levels_daily.json"
    if _ma_levels_path.exists():
        try:
            _ml_raw = json.loads(_ma_levels_path.read_text(encoding="utf-8"))
            _ma_levels_map = {r["symbol"]: r for r in _ml_raw.get("records", [])}
        except Exception:
            pass

    # ---- E&MA Research: per-symbol historical reaction data (IA-fav 22 symbols) ----
    _ema_research_map: dict[str, dict] = {}
    _ema_research_path = REPO / "data/research/ma_reaction_stocks.json"
    if _ema_research_path.exists():
        try:
            _er_raw = json.loads(_ema_research_path.read_text(encoding="utf-8"))
            _ema_research_map = _er_raw.get("per_symbol_best_2y", {})
        except Exception:
            pass

    # ---- MA Context: liquid universe (269 symbols) best-MA touch quality ----
    _ma_ctx_map: dict[str, dict] = {}
    _ma_ctx_path = REPO / "data/research/ma_context_daily.json"
    if _ma_ctx_path.exists():
        try:
            _ma_ctx_raw = json.loads(_ma_ctx_path.read_text(encoding="utf-8"))
            _ma_ctx_map = _ma_ctx_raw.get("symbols", {})
        except Exception:
            pass

    _inst_accum_compact = load_institutional_accumulation_compact()
    _inst_accum_index = build_inst_accum_ticker_index(_inst_accum_compact)
    _position_ctx_payload = load_position_context()
    _position_ctx_map = position_context_by_symbol(_position_ctx_payload)
    _sta_compact = load_structural_ta_compact()
    _sta_meta = structural_ta_file_meta(_sta_compact)
    _sta_index = build_structural_ta_index(_sta_compact)

    for w in drl_warns:
        if w not in warnings_list:
            warnings_list.append(w)

    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    ts_file = ts.strftime("%Y%m%d_%H%M")

    # ---- Safety checks ----
    if not intraday_df.empty and is_intraday:
        if "auto_order_allowed" in intraday_df.columns:
            bad_mask = intraday_df["auto_order_allowed"].apply(lambda v: normalize_bool(v) is True)
            bad = intraday_df[bad_mask]
            if not bad.empty:
                syms_bad = list(bad["symbol"]) if "symbol" in bad.columns else list(bad.index)
                warnings_list.append(
                    f"auto_order_allowed=True found in intraday rows: {syms_bad}"
                )
        if "final_action" in intraday_df.columns:
            bad2 = intraday_df[intraday_df["final_action"] != "INTRADAY_PREVIEW"]
            if not bad2.empty:
                symbols_bad = list(bad2["symbol"]) if "symbol" in bad2.columns else []
                warnings_list.append(
                    f"intraday final_action != INTRADAY_PREVIEW for: {symbols_bad}"
                )

    if not scan_df.empty and "s3_no_real_order_flag" in scan_df.columns:
        bad_s3_mask = scan_df["s3_no_real_order_flag"].apply(lambda v: normalize_bool(v) is False)
        bad_s3 = scan_df[bad_s3_mask]
        if not bad_s3.empty:
            syms = list(bad_s3["symbol"]) if "symbol" in bad_s3.columns else []
            warnings_list.append(f"s3_no_real_order_flag=False for: {syms}")

    # ---- Signal-today with numeric prices → data integrity ----
    if not scan_df.empty and "a3_signal_today" in scan_df.columns:
        for _, srow in scan_df.iterrows():
            if normalize_bool(srow.get("a3_signal_today")) is True:
                for price_col in ("pb_trigger_price", "tp1_price", "trail_price"):
                    val = srow.get(price_col)
                    if val is not None:
                        try:
                            fv = float(val)
                            if not math.isnan(fv):
                                sym = srow.get("symbol", "?")
                                warnings_list.append(
                                    f"[NEEDS_REVIEW] a3_signal_today=True but "
                                    f"{price_col}={fv:.4f} is non-null for {sym} — expected NaN"
                                )
                        except (TypeError, ValueError):
                            pass

    # ---- Intraday quote-quality ----
    if is_intraday and intraday_meta:
        qc = intraday_meta.get("intraday_quote_coverage_pct")
        if qc is not None:
            try:
                qc_f = float(qc)
                pct = qc_f * 100 if qc_f <= 1.0 else qc_f
                if pct < 100:
                    warnings_list.append(f"intraday_quote_coverage_pct < 100%: {pct:.1f}%")
            except (TypeError, ValueError):
                pass
        mq = intraday_meta.get("missing_quote_count")
        if mq is not None:
            try:
                if float(mq) > 0:
                    warnings_list.append(f"missing_quote_count={int(float(mq))}")
            except (TypeError, ValueError):
                pass
        stale_keys = [k for k in intraday_meta if "stale" in k.lower()]
        for sk in stale_keys:
            sv = intraday_meta[sk]
            if sv and str(sv).lower() not in ("false", "0", "none", ""):
                warnings_list.append(f"stale data: {sk}={sv}")

    if scan_df.empty:
        warnings_list.append("scan_file_missing: report may be incomplete")

    # Check for unknown final_action
    if not scan_df.empty and "final_action" in scan_df.columns:
        known = {
            "NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH", "ADD_T2", "NO_T2_BREADTH",
            "WAIT_PB", "HOLD_T1_ONLY", "TP1_PARTIAL", "TRAIL_EXIT", "MAX_HOLD_EXIT",
            "SKIP_LIQUIDITY", "SKIP_VNINDEX_BEAR", "WATCH_ONLY", "INTRADAY_PREVIEW",
        }
        unk_mask = ~scan_df["final_action"].isin(known)
        unk_actions = scan_df.loc[unk_mask, "final_action"].unique().tolist()
        if unk_actions:
            warnings_list.append(f"unexpected final_action values: {unk_actions}")

    # ---- Macro context from scan ----
    def _macro_val(col: str, default: Any = None) -> Any:
        if not scan_df.empty and col in scan_df.columns:
            vals = scan_df[col].dropna()
            if not vals.empty:
                return vals.iloc[0]
        return default

    regime_bull = normalize_bool(_macro_val("regime_bull", intraday_meta.get("regime_bull")))
    breadth_zone = str(_macro_val("breadth_zone", intraday_meta.get("breadth_zone", ""))).lower()
    pct_cloud_bull_a3 = _macro_val("pct_cloud_bull_a3", intraday_meta.get("last_breadth"))
    pct_cloud_bull_s3 = _macro_val("pct_cloud_bull_s3", intraday_meta.get("last_s3_breadth"))
    breadth_t1_perm = _macro_val("breadth_t1_permission", True)
    breadth_t2_perm = _macro_val("breadth_t2_permission", True)

    try:
        breadth_pct = float(pct_cloud_bull_a3) if pct_cloud_bull_a3 is not None else None
    except (TypeError, ValueError):
        breadth_pct = None

    try:
        s3_breadth_pct = float(pct_cloud_bull_s3) if pct_cloud_bull_s3 is not None else None
    except (TypeError, ValueError):
        s3_breadth_pct = None

    panel_asof = str(_macro_val("as_of_date", intraday_meta.get("panel_asof", "")))
    scan_date = panel_asof[:10] if panel_asof else ""

    # ---- CF annotation (optional, display-only, never touches final_action) ----
    _cf_enabled = False
    cf_ann_df = pd.DataFrame()
    try:
        from src.trading.research.capital_footprint.annotation import (
            is_cf_annotation_enabled,
            build_cf_annotation_for_date,
            build_cf_annotation_json,
        )
        _cf_enabled = is_cf_annotation_enabled()
        if _cf_enabled and scan_date:
            cf_ann_df = build_cf_annotation_for_date(scan_date)
    except Exception as _cf_exc:
        warnings_list.append(f"CF annotation skipped: {_cf_exc}")

    # ---- D3/D4 propagation display (optional, read-only from state artifacts) ----
    _prop_sector_enabled = False
    _prop_cash_enabled = False
    _prop_tilt_tag = lambda sym: ""  # noqa: E731
    _prop_sector_caption = ""
    _prop_cash_cockpit = ""
    try:
        from src.trading.overlays.propagation_display import (
            PHASE_D_FINDINGS,
            is_cash_plus_display_enabled,
            is_sector_annotation_enabled,
            load_cash_plus_for_display,
            symbol_tilt_tag_html,
        )
        _prop_sector_enabled = is_sector_annotation_enabled()
        _prop_cash_enabled = is_cash_plus_display_enabled()
        if _prop_sector_enabled:
            _prop_sector_caption = PHASE_D_FINDINGS["sector_caption"]
            _prop_tilt_tag = lambda sym: symbol_tilt_tag_html(sym, scan_date)  # noqa: E731
        if _prop_cash_enabled:
            _cash_disp = load_cash_plus_for_display() or {}
            _idle = float(_cash_disp.get("idle_earning_vnd") or 0)
            _net = _cash_disp.get("net_yield_pct", "—")
            _prop_cash_cockpit = f"{_idle/1e9:.2f}bn @ {_net}% (iPower)"
    except Exception as _prop_exc:
        warnings_list.append(f"Propagation display skipped: {_prop_exc}")

    _report_controls_css = ""
    _sys_controls_html = ""
    _sys_controls_js = ""
    _live_mode_js = ""
    try:
        from src.trading.overlays.propagation_display import (
            build_live_mode_js,
            build_report_controls_css,
            build_system_controls_html,
            build_system_controls_js,
        )
        _report_controls_css = build_report_controls_css()
        _sys_controls_html = build_system_controls_html()
        _sys_controls_js = build_system_controls_js()
        _live_mode_js = build_live_mode_js("cloud_daily")
    except Exception as _rc_exc:
        warnings_list.append(f"Report controls skipped: {_rc_exc}")

    # ---- Classify all scan rows ----
    classified: list[dict] = []
    if not scan_df.empty:
        for _, row in scan_df.iterrows():
            rd = row.to_dict()
            ca = classify_operator_action(rd, mode)
            rd["_action_group"] = ca["action_group"]
            rd["_operator_action"] = ca["operator_action"]
            rd["_reason"] = ca["reason"]
            classified.append(rd)

    def _filter(group: str) -> list[dict]:
        return [r for r in classified if r["_action_group"] == group]

    new_t1_rows = _filter("NEW_T1")
    manual_t1_rows = _filter("MANUAL_REVIEW_T1")
    add_t2_rows = _filter("ADD_T2")
    t2_blocked_rows = _filter("T2_BLOCKED")
    hold_rows = _filter("HOLD")
    exit_rows = _filter("EXIT_REVIEW")
    skip_rows = _filter("SKIP")
    s3_rows = _filter("S3_PAPER")
    unknown_rows = _filter("UNKNOWN")

    # Intraday rows classified
    intraday_classified: list[dict] = []
    if not intraday_df.empty:
        for _, row in intraday_df.iterrows():
            rd = row.to_dict()
            ca = classify_operator_action(rd, mode)
            rd["_action_group"] = ca["action_group"]
            rd["_operator_action"] = ca["operator_action"]
            intraday_classified.append(rd)

    # Sort all T1 candidates together (3-level tier sort — zone secondary for S2 only).
    # PRIMARY:   SigQ tier (S2=3 > S1=2 > base=0; S1∩S2=1 demoted — DEGRADING-REJECT MAR 0.87)
    # SECONDARY: Zone band for S2 tier only (S21: Zone 4-7% > Extended >7% > Near <4%)
    #            Non-S2 tiers: constant zone=1 -> term cancels -> rank orders them.
    # TERTIARY:  a3_rank_score (compound ED+S3 lead boost; secondary for base/S1)
    #
    # S21 evidence: N=1621 pure-S2 OOS 2020-2026, Zone mean 32.83% / median +3.48% / win 53.5%
    #   vs Near 8.82% / −3.33% / 45.2%. Robust 6/7 years. Ed_pct recovered from ed_score:
    #   ed_pct = 20.0 × (1 − ed_score)   [good_band=20 hardcoded in scan engine]
    # WARNING: ed_score_bucket label "optimal" = Near band = WORST. Never sort on label directly.
    # Bear caveat: Zone edge inverts in Bear (2022). Regime tracked separately; display-only.
    # Escalation: any move of zone into sizing/filtering/final_action requires pre-reg + T#5.
    # Opus advisory verdict: 2026-07-08. No Trigger #5 required (display/sort only, not OMS).
    # User approval: 2026-07-08 session.
    def _sq_tier(r: dict) -> int:
        s2 = normalize_bool(_get(r, "s2_pass"))
        s1 = normalize_bool(_get(r, "s1_pass"))
        if s2 and s1:  return 1  # S1∩S2 combined = DEGRADING-REJECT (MAR 0.87) — demote
        if s2:         return 3  # pure S2 (MAR 2.48, regime-agnostic)
        if s1:         return 2  # pure S1 (MAR 1.78, regime-dependent)
        return 0                 # base (MAR 0.84)

    def _zone_band(r: dict) -> int:
        """Zone-targeting priority from recovered ED% (higher int = better).
        ed_pct = 20.0 × (1 − ed_score)  [good_band hardcoded=20 in scan engine].
        S21 monotonic ordering (mean AND median): Zone(4-7%)>Extended(>7%)>Near(<4%).
        Applied to S2 tier (tier==3) only; untested on S1/base — do not extrapolate."""
        try:
            es = float(_get(r, "ed_score", 0) or 0)
        except (TypeError, ValueError):
            return 1  # unknown → neutral (middle band)
        ed_pct = 20.0 * (1.0 - es)
        if 4.0 <= ed_pct <= 7.0:
            return 2  # Zone     — best  (median +3.48%)
        if ed_pct < 4.0:
            return 0  # Near     — worst (median −3.33%, >50% losers)
        return 1      # Extended — middle (median −2.28%)

    def _sort_key_t1(r: dict):
        tier   = _sq_tier(r)
        zone   = _zone_band(r) if tier == 3 else 1  # S2 only; const for others
        rank   = float(_get(r, "a3_rank_score", 0) or 0)
        liq_ok = 0 if str(_get(r, "liq_warn_T1", "")).strip().upper() == "OK" else 1
        sym    = str(_get(r, "symbol", "")).upper()
        return (-tier, -zone, -rank, liq_ok, sym)

    new_t1_rows_combined = sorted(
        [r for r in classified if r["_action_group"] in ("NEW_T1", "MANUAL_REVIEW_T1")],
        key=_sort_key_t1,
    )

    # ---- New entry symbols ----
    new_entry_symbols = [_get(r, "symbol", "") for r in new_t1_rows_combined]

    # ---- Counts ----
    counts = {
        "new_t1": sum(1 for r in classified if r["_action_group"] == "NEW_T1"),
        "manual_review_t1": sum(1 for r in classified if r["_action_group"] == "MANUAL_REVIEW_T1"),
        "add_t2": sum(1 for r in classified if r["_action_group"] == "ADD_T2"),
        "no_t2_breadth": sum(1 for r in classified if r["_action_group"] == "T2_BLOCKED"),
        "hold": sum(1 for r in classified if r["_action_group"] == "HOLD"),
        "exit_review": sum(1 for r in classified if r["_action_group"] == "EXIT_REVIEW"),
        "s3_paper": sum(1 for r in classified if r["_action_group"] == "S3_PAPER"),
        "intraday_candidates": len(intraday_classified),
    }

    # ---- Warnings: if unknown actions found ----
    if unknown_rows:
        unk_syms = [_get(r, "symbol", "?") for r in unknown_rows]
        warnings_list.append(f"unexpected final_action for symbols: {unk_syms}")

    # ---- Delta vs prev ----
    delta: dict = {}
    if prev_json:
        prev_symbols = set(prev_json.get("new_entry_symbols", []))
        curr_symbols = set(new_entry_symbols)
        added = sorted(curr_symbols - prev_symbols)
        removed = sorted(prev_symbols - curr_symbols)
        delta["new_candidates_added"] = added
        delta["new_candidates_removed"] = removed
        prev_zone = prev_json.get("breadth_zone", "")
        if prev_zone != breadth_zone:
            delta["breadth_zone_changed"] = {"from": prev_zone, "to": breadth_zone}
        prev_regime = prev_json.get("regime_bull")
        if prev_regime != regime_bull:
            delta["regime_changed"] = {"from": prev_regime, "to": regime_bull}
        prev_counts = prev_json.get("counts", {})
        count_delta = {}
        for k in counts:
            if counts[k] != prev_counts.get(k):
                count_delta[k] = {"from": prev_counts.get(k), "to": counts[k]}
        if count_delta:
            delta["count_changes"] = count_delta

    # ---- Report status ----
    if drl_data:
        from src.trading.reports.distribution_risk_card import (
            STALE_NEEDS_REVIEW_MD,
            lens_needs_stale_review,
        )

        if lens_needs_stale_review(drl_data):
            warnings_list.append(f"distribution_risk_lens: {STALE_NEEDS_REVIEW_MD}")

    has_safety_warning = any(
        "auto_order_allowed" in w.lower() or
        "s3_no_real_order_flag" in w.lower() or
        "scan_file_missing" in w.lower() or
        "PRIMARY_VIEW_STALE" in w or
        "NEEDS_REVIEW" in w
        for w in warnings_list
    )
    if has_safety_warning:
        report_status = "NEEDS_REVIEW"
    elif is_intraday:
        report_status = "PREVIEW_OK"
    else:
        report_status = "OK"

    # ---- Top actions ----
    top_actions: list[dict] = []
    for r in new_t1_rows_combined[:5]:
        top_actions.append({
            "symbol": _get(r, "symbol"),
            "action_group": r["_action_group"],
            "operator_action": r["_operator_action"],
            "rank_score": _get(r, "a3_rank_score"),
        })

    # ========================================================================
    # Pre-compute decision bullets (used in CIO Cockpit and Section B)
    # ========================================================================

    action_now_items: list[str] = []
    if new_t1_rows_combined:
        n_new = counts["new_t1"]
        n_manual = counts["manual_review_t1"]
        if n_new:
            action_now_items.append(f"Review {n_new} A3 NEW_T1 candidate(s) for manual checklist")
        if n_manual:
            mr_syms = ", ".join(
                _get(r, "symbol", "?") for r in sorted(manual_t1_rows, key=_sort_key_t1)
            )
            action_now_items.append(
                f"Prepare manual review checklist for next-open candidates: {mr_syms} (breadth gate)"
            )
        pending_rows = [
            r for r in new_t1_rows_combined
            if normalize_bool(_get(r, "a3_signal_today", False)) is True
        ]
        if pending_rows and not is_intraday:
            pend_syms = ", ".join(_get(r, "symbol", "?") for r in pending_rows)
            action_now_items.append(
                f"Review next-open candidate(s): {pend_syms} (pending levels)"
            )
    if is_intraday:
        signal_today_rows = [
            r for r in intraday_classified
            if normalize_bool(_get(r, "a3_signal_today", False)) is True
        ]
        if signal_today_rows:
            sym_list = ", ".join(_get(r, "symbol", "?") for r in signal_today_rows)
            action_now_items.append(
                f"Review would-be A3 candidate(s) if close now; wait for EOD confirmation. ({sym_list})"
            )
    exit_holdings = [r for r in exit_rows if _get(r, "symbol", "") in holdings]
    if exit_holdings:
        sym_list = ", ".join(_get(r, "symbol", "?") for r in exit_holdings)
        action_now_items.append(f"Review exit-risk holdings: {sym_list}")

    watch_items: list[str] = []
    if is_intraday:
        would_be_new = [r for r in intraday_classified if r.get("_action_group") in ("NEW_T1", "MANUAL_REVIEW_T1")]
        if would_be_new:
            watch_items.append(f"{len(would_be_new)} would-be NEW_T1 if close now")
    watch_items.append(f"S3 paper setups: {counts['s3_paper']}")
    watch_items.append(f"T2 candidates (ADD_T2 + WAIT_PB): {counts['add_t2']}")

    dont_items: list[str] = []
    if breadth_pct is not None and breadth_pct < 0.40:
        if regime_bull is True:
            dont_items.append(
                f"T2 caution: breadth <40% ({breadth_pct*100:.1f}%) participation warning — "
                "extra selectivity; not an automatic block when VNINDEX is BULL"
            )
        else:
            dont_items.append(f"Do not add T2 (breadth < 40%: {breadth_pct*100:.1f}%)")
    elif not breadth_t2_perm:
        dont_items.append("Do not add T2 (T2 permission blocked)")
    dont_items.append("Do not trade S3 as live capital")
    if is_intraday:
        dont_items.append("Do not use intraday preview as order source")
    dup_holdings = [_get(r, "symbol", "") for r in new_t1_rows_combined if _get(r, "symbol", "") in holdings]
    if dup_holdings:
        dont_items.append(f"Do not duplicate held positions: {', '.join(dup_holdings)}")
    dont_items.append("Do not base orders on AFL visuals")

    # ========================================================================
    # BUILD HTML
    # ========================================================================

    def _section(title: str, content: str, cls: str = "card") -> str:
        return f'<div class="{cls}"><div class="section-title">{_esc(title)}</div>{content}</div>'

    parts: list[str] = []
    parts.append(f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
                 f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                 f"<title>Cloud Daily Report — {_esc(ts_str)}</title>"
                 f"<link rel='preconnect' href='https://fonts.googleapis.com'>"
                 f"<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap' rel='stylesheet'>"
                 f"<style>{CSS}{_report_controls_css}</style></head><body>"
                 f"<div class='layout'>"
                 f"<aside class='sidebar'>"
                 f"<div class='sidebar-logo'>Cloud Daily</div>"
                 f"<h3>Overview</h3>"
                 f"<a href='#section-cio'>CIO Cockpit</a>"
                 f"<h3>Actions</h3>"
                 f"<a href='#section-b'>B. Decisions</a>"
                 f"<a href='#section-c'>C. A3 Board</a>"
                 f"<a href='#section-d'>D. Portfolio</a>"
                 f"<a href='#section-ar'>Action Register</a>"
                 f"<h3>Context</h3>"
                 f"<a href='#section-g'>G. Market</a>"
                 f"<a href='#section-h'>H. Delta</a>"
                 f"<a href='#section-i'>I. Appendix</a>"
                 f"</aside>"
                 f"<div class='container'>")

    _data_mode = "SNAPSHOT" if is_intraday else "FROZEN"
    _prov_sources = list(files_used) if files_used else []
    if _position_ctx_payload:
        _prov_sources.append("data/state/position_context_daily.json")
    if _inst_accum_compact:
        _prov_sources.append("data/decision/institutional_accumulation_compact.json")
    parts.append(render_provenance_header(
        title="Cloud Daily Report",
        generated_at=ts_str,
        data_as_of=scan_date or panel_asof[:10] if panel_asof else "—",
        data_mode=_data_mode,
        universe_scope="269-symbol liquid scan universe (A3 board); 19-symbol IA-fav for E&MA breach cards",
        source_files=_prov_sources[:8],
    ))
    parts.append(render_suite_nav("cloud_daily"))

    # ---- Section A: Header strip ----
    mode_label = {"eod": "EOD", "pre-lunch": "PRE-LUNCH PREVIEW", "pre-atc": "PRE-ATC PREVIEW", "auto": "AUTO"}.get(mode, mode.upper())
    mode_color = "green" if mode == "eod" else "amber"

    regime_label = "BULL" if regime_bull is True else ("BEAR" if regime_bull is False else "UNKNOWN")
    regime_color = "green" if regime_bull is True else ("red" if regime_bull is False else "gray")

    bz_upper = breadth_zone.upper() if breadth_zone else "UNKNOWN"
    bz_color = {"normal": "green", "caution": "amber", "defense": "red"}.get(breadth_zone, "gray")

    t1_perm_label = "OK" if breadth_t1_perm else "BLOCKED"
    t1_perm_color = "green" if breadth_t1_perm else "red"
    if not breadth_t1_perm and counts.get("manual_review_t1", 0) > 0:
        t1_perm_label = "MANUAL REVIEW"
        t1_perm_color = "amber"

    t2_perm_label, t2_perm_color = _dashboard_t2_permission_display(
        regime_bull, breadth_pct, bool(breadth_t2_perm)
    )

    if nav_vnd is not None:
        nav_label = f"NAV: {nav_vnd/1e9:.2f}bn VND"
        nav_color = "gray"
    else:
        nav_label = "NAV: unknown"
        nav_color = "amber"

    header_badges = (
        _badge(f"Mode: {mode_label}", mode_color) +
        _badge(nav_label, nav_color) +
        _badge(f"VNINDEX: {regime_label}", regime_color) +
        _badge(f"Breadth: {bz_upper}", bz_color) +
        _badge(f"T1: {t1_perm_label}", t1_perm_color) +
        _badge(f"T2: {t2_perm_label}", t2_perm_color)
    )
    # S2/S1 advisory filter badge (reads active_filter from scan rows; fails safe to s2)
    _active_filter_val = "s2"
    _filter_cfg_source = "default"
    if not scan_df.empty and "active_filter" in scan_df.columns:
        _af_vals = scan_df["active_filter"].dropna().unique().tolist()
        if _af_vals:
            _active_filter_val = str(_af_vals[0]).strip().lower()
            _filter_cfg_source = "scan"
    if _active_filter_val not in ("s2", "s1"):
        _active_filter_val = "s2"
    if _active_filter_val == "s2":
        _filter_label = "ENTRY FILTER: S2 PRIMARY (vol ≥1.3× 50d)"
        _filter_color = "green"
        _filter_ref = "OOS MAR 2.4804 | regime-agnostic"
    else:
        _filter_label = "ENTRY FILTER: S1 FALLBACK (52wk hi ≥85%)"
        _filter_color = "amber"
        _filter_ref = "OOS MAR 1.7844 | regime-sensitive"
    if _filter_cfg_source == "default":
        _filter_label += " (default — config unreadable)"
        _filter_color = "amber"
    header_badges += _badge(_filter_label, _filter_color)
    if is_intraday:
        header_badges += _badge("PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW", "amber")

    pos_src_label = _esc(positions_source) if positions_source != "missing" else "missing"
    header_html = (
        f"<div class='card'>"
        f"<h2 style='margin:0 0 0.5rem;'>Cloud Daily Report &mdash; {_esc(ts_str)}</h2>"
        f"{header_badges}"
        f"<div class='footnote' style='margin-top:0.5rem;'>Daily scan is source of truth. AFL is visual cockpit.</div>"
        f"<div class='footnote'>Port = stock holdings only (excludes cash). "
        f"NAV is user-updated; not inferred from positions. "
        f"Positions source: <code>{pos_src_label}</code></div>"
    )
    if is_intraday:
        header_html += (
            "<div class='footnote'>Intraday preview only. "
            "final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.</div>"
        )
    header_html += "</div>"
    parts.append(header_html)
    if _sys_controls_html:
        parts.append(_sys_controls_html)

    # ---- Section CIO: CIO Cockpit ----
    def _perm_row(label: str, val: str, color: str) -> str:
        return f"<tr><th style='width:130px;font-weight:600;'>{_esc(label)}</th><td>{_badge(val, color)}</td></tr>"

    _exit_n = counts["exit_review"]  # scan-wide EXIT_REVIEW count
    _port_exit_n = len(exit_holdings)  # portfolio-level exit count (holdings with exit signal)
    _new_t1_n = counts["new_t1"] + counts["manual_review_t1"]
    _bpct_str = f"{breadth_pct*100:.0f}%" if breadth_pct is not None else "—"
    if regime_bull is True and breadth_zone == "normal":
        _oneliner = (
            f"BULL · Breadth {_bpct_str} (normal) — Full T1+T2 open"
            + (f" · {_new_t1_n} candidate(s) ready" if _new_t1_n else "")
            + (f" · execute {_exit_n} pending exit(s) first" if _exit_n else " · no pending exits")
        )
        _ol_color = "#5edd5e"
    elif regime_bull is True and breadth_zone == "defense":
        _exit_detail = (
            f"{_port_exit_n} portfolio + {_exit_n} scan-wide"
            if _port_exit_n > 0 else f"{_exit_n} scan-wide"
        )
        _oneliner = (
            f"BULL · Breadth {_bpct_str} (defense, &lt;40%) — "
            f"T2 blocked · selective T1 only · "
            f"triage {_exit_detail} exit(s) before any entry"
        )
        _ol_color = "#ffc107"
    elif regime_bull is False:
        _exit_detail = (
            f"{_port_exit_n} portfolio + {_exit_n} scan-wide"
            if _port_exit_n > 0 else f"{_exit_n} scan-wide"
        )
        _oneliner = (
            f"BEAR · Breadth {_bpct_str} — "
            f"Triage {_exit_detail} exit(s) now · "
            f"No new entries · Protect capital first"
        )
        _ol_color = "#f77"
    else:
        _oneliner = (
            f"Regime unknown ({bz_upper} breadth) — verify data before acting"
        )
        _ol_color = "#8ab4f8"

    _perm_html = (
        "<table><tbody>"
        + _perm_row("New T1",
                    "Blocked (BEAR)" if regime_bull is False else
                    ("Manual review only (defense)" if breadth_zone == "defense" else "OK"),
                    "red" if regime_bull is False else ("amber" if breadth_zone == "defense" else "green"))
        + _perm_row("T2 adds", *_dashboard_t2_adds_label(
            regime_bull, breadth_pct, bool(breadth_t2_perm)))
        + _perm_row("S3 paper", "Paper shadow only (research)", "gray")
        + _perm_row("Exits", "Always execute per A3 plan", "green")
        + _perm_row("Manual override", "Operator sign-off required", "amber")
        + (
            _perm_row("Sector tilt", "Leading sectors sized 1.25× (D3)", "green")
            if _prop_sector_enabled else ""
        )
        + "</tbody></table>"
    )

    _exit_open  = '<strong style="color:#f77;">'
    _exit_close = '</strong>'
    _counts_html = (
        "<table><tbody>"
        + f"<tr><th>Exit signals (scan-wide)</th><td>"
          f"{_exit_open if _exit_n else ''}"
          f"{_exit_n}"
          f"{_exit_close if _exit_n else ''}"
          f"</td></tr>"
        + f"<tr><th>Portfolio exit review</th><td>"
          f"{_exit_open if _port_exit_n else ''}"
          f"{_port_exit_n}"
          f"{_exit_close if _port_exit_n else ''}"
          f"</td></tr>"
        + f"<tr><th>Holdings NOT in scan</th><td>"
          + (lambda nin: f"<strong style='color:#ffc107;'>{nin}</strong>" if nin > 0 else "0")(
              sum(1 for h in holdings if h not in {_get(r, "symbol", "") for r in classified})
          )
          + "</td></tr>"
        + f"<tr><th>New T1 candidates</th><td>{_new_t1_n}</td></tr>"
        + f"<tr><th>T2 breadth caution (scan NO_T2_BREADTH)</th><td>{counts['no_t2_breadth']}</td></tr>"
        + (
            f"<tr><th>Idle cash earning</th><td>{_esc(_prop_cash_cockpit)}</td></tr>"
            if _prop_cash_enabled and _prop_cash_cockpit else ""
        )
        + "</tbody></table>"
    )

    _required_items = action_now_items[:3] or ["No immediate actions required."]
    _req_html = "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in _required_items) + "</ul>"

    _forbidden_items = dont_items[:3] or ["No active restrictions."]
    _forb_html = "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in _forbidden_items) + "</ul>"

    _cf_counts_html = ""
    if _cf_enabled and not cf_ann_df.empty:
        try:
            _sa_bull = int(((cf_ann_df["cf_phase_label"] == "SUPPLY_ABSORPTION_SETUP") &
                            (cf_ann_df["cf_breadth_regime_bucket"] == "BULL_BROAD")).sum())
            _sa_weak = int(((cf_ann_df["cf_phase_label"] == "SUPPLY_ABSORPTION_SETUP") &
                            (cf_ann_df["cf_breadth_regime_bucket"] != "BULL_BROAD")).sum())
            _ext_old = int(((cf_ann_df["cf_phase_label"] == "EXTENSION_DISTRIBUTION_RISK") &
                            (cf_ann_df.get("cf_event_age", pd.Series(dtype=float)) >= 5)).sum())
            _research_only = int((cf_ann_df["cf_annotation_active"] == 0).sum())
            _cf_counts_html = (
                f"<div class='cio-block' style='margin-top:0.5rem;'>"
                f"<div class='cio-block-title'>CF Active Notes <span class='ctx-tag'>RESEARCH ONLY</span></div>"
                f"SA Bull-broad: <strong>{_sa_bull}</strong> &nbsp;|&nbsp; "
                f"SA weak-regime: <strong>{_sa_weak}</strong> &nbsp;|&nbsp; "
                f"Extension age≥5: <strong>{_ext_old}</strong> &nbsp;|&nbsp; "
                f"Research-only: <strong>{_research_only}</strong>"
                f"</div>"
            )
        except Exception:
            pass

    # Breadth C1 context block — meaning + action always shown
    _breadth_c1_block = ""
    try:
        import pandas as _pd
        _bc1_path = REPO / "data" / "research" / "regime" / "breadth_c1_series.parquet"
        if _bc1_path.exists():
            _bc1_df = _pd.read_parquet(_bc1_path)
            if not _bc1_df.empty:
                _bc1 = _bc1_df.iloc[-1]
                _bc1_pct = float(_bc1["breadth_pct"])
                _bc1_sig = str(_bc1["regime_b1"])
                _bc1_asof = str(_bc1["date"])[:10]
                if _bc1_pct >= 45:
                    _bc1_color = "#5edd5e"
                    _bc1_meaning = f"{_bc1_pct:.1f}% of stocks above EMA50 — broad participation"
                    _bc1_action = "Normal entry sizing permitted"
                elif _bc1_pct >= 40:
                    _bc1_color = "#ffc107"
                    _bc1_meaning = f"{_bc1_pct:.1f}% of stocks above EMA50 — borderline breadth"
                    _bc1_action = "Reduce new entry size; hold existing"
                elif _bc1_pct >= 30:
                    _bc1_color = "#f0a030"
                    _bc1_meaning = f"{_bc1_pct:.1f}% of stocks above EMA50 — market narrowing"
                    _bc1_action = "No new entries; defend existing; watch exits"
                else:
                    _bc1_color = "#f77"
                    _bc1_meaning = f"{_bc1_pct:.1f}% of stocks above EMA50 — thin, few leaders"
                    _bc1_action = "Avoid new entries; prioritise exit discipline"
                _bc1_stale = bool(scan_date) and bool(_bc1_asof) and _bc1_asof < scan_date
                _bc1_stale_html = (
                    ' &nbsp;<span style="color:#f0a030;font-weight:700">RESEARCH SERIES — STALE '
                    f'(not current breadth; scan as-of {scan_date})</span>'
                    if _bc1_stale else ""
                )
                _breadth_c1_block = (
                    f'<div style="margin:6px 0 2px;padding:6px 10px;'
                    f'background:rgba(255,255,255,.03);border-left:3px solid {_bc1_color};border-radius:3px;font-size:11px;">'
                    f'<span style="color:{_bc1_color};font-weight:700">Breadth C1 {_bc1_asof}: '
                    f'{_bc1_pct:.1f}% [{_bc1_sig}]</span>'
                    f'{_bc1_stale_html}'
                    f' &nbsp;·&nbsp; {_esc(_bc1_meaning)}'
                    f' &nbsp;→&nbsp; <strong>{_esc(_bc1_action)}</strong>'
                    f'</div>'
                )
    except Exception:
        pass

    cio_html = (
        f'<div id="section-cio" class="cio-cockpit">'
        f'<div class="cio-oneliner" style="color:{_ol_color};">&#9654; {_oneliner}</div>'
        f'{_breadth_c1_block}'
        f'<div class="cio-grid">'
        f'<div class="cio-block"><div class="cio-block-title">Permission Matrix</div>'
        f'<p class="perm-precedence-note">{PERMISSION_PRECEDENCE_CLOUD}</p>{_perm_html}</div>'
        f'<div class="cio-block"><div class="cio-block-title">Action Counts</div>{_counts_html}</div>'
        f'<div class="cio-block"><div class="cio-block-title">Required Actions</div>{_req_html}</div>'
        f'<div class="cio-block"><div class="cio-block-title">Forbidden</div>{_forb_html}</div>'
        f'</div>'
        f'{_cf_counts_html}'
        f'</div>'
    )
    parts.append(cio_html)

    # ---- Navigation bar ----
    _nav_sections = [
        ("#section-cio", "CIO Cockpit"),
        ("#section-b", "B. Actions"),
        ("#section-c", "C. A3 Board"),
        ("#section-d", "D. Portfolio"),
        ("#section-ar", "Action Register"),
        ("#section-g", "G. Market"),
        ("#section-h", "H. Delta"),
        ("#section-i", "I. Appendix"),
    ]
    if is_intraday:
        _nav_sections.insert(5, ("#section-e", "E. Intraday"))
    _nav_links = " ".join(
        f'<a href="{href}">{label}</a>' for href, label in _nav_sections
    )
    parts.append(
        f'<div class="nav-bar"><span style="color:#4a6888;font-weight:700;font-size:0.72rem;">JUMP TO:</span> {_nav_links}</div>'
    )

    # ---- Warnings banner ----
    if warnings_list:
        warn_items = "".join(f"<li>{_esc(w)}</li>" for w in warnings_list)
        parts.append(f"<div class='warn-banner'>⚠ Warnings:<ul>{warn_items}</ul></div>")

    # ---- Section B: Decision cards ----
    # action_now_items, watch_items, dont_items pre-computed above in decision bullets block
    action_now_li = "".join(f"<li>{_esc(item)}</li>" for item in action_now_items) if action_now_items else "<li><em>No immediate actions required</em></li>"
    action_now_card = (
        f"<div class='card action-card green'>"
        f"<strong style='color:#5edd5e;'>ACTION NOW</strong>"
        f"<ul class='action-list'>{action_now_li}</ul>"
        f"</div>"
    )

    # WATCH/PREPARE
    watch_li = "".join(f"<li>{_esc(item)}</li>" for item in watch_items)
    watch_card = (
        f"<div class='card action-card amber'>"
        f"<strong style='color:#ffc107;'>WATCH / PREPARE</strong>"
        f"<ul class='action-list'>{watch_li}</ul>"
        f"</div>"
    )

    # DO NOT DO
    dont_li = "".join(f"<li>{_esc(item)}</li>" for item in dont_items)
    dont_card = (
        f"<div class='card action-card red'>"
        f"<strong style='color:#f77;'>DO NOT DO</strong>"
        f"<ul class='action-list'>{dont_li}</ul>"
        f"</div>"
    )

    parts.append(
        f'<div id="section-b" class="section-title">B. Decision Summary '
        f'<span class="ssot-tag">ACTION SSOT: final_action</span></div>'
        f"<div class='card-grid'>{action_now_card}{watch_card}{dont_card}</div>"
    )

    # ---- Structural TA (advisory cards; separate from ACTION SSOT tables) ----
    _sta_tickers: list[str] = list(holdings) if holdings else []
    for r in new_t1_rows_combined or []:
        sym = str(_get(r, "symbol", "") or "").upper()
        if sym:
            _sta_tickers.append(sym)
    _sta_section = render_structural_ta_cards_section(
        _sta_tickers,
        _sta_index,
        file_meta=_sta_meta,
        section_id="structural-ta",
        title="Structural TA (holdings + T1)",
    )
    if _sta_section:
        parts.append(_sta_section)

    # ---- MA Context cell (liquid 269-symbol universe, backtest-validated) ----
    def _ma_ctx_cell(s: str) -> str:
        """Best-MA touch quality. PRIME: +9.7pp SR lift vs base 39.1%. NEAR: +8.2pp."""
        ctx = _ma_ctx_map.get(s)
        if not ctx:
            return "<span style='color:#3a5570'>—</span>"
        quality  = ctx.get("quality", "far")
        best_ma  = ctx.get("best_ma", "?")
        dist_pct = ctx.get("dist_pct")
        sr10d    = ctx.get("best_ma_sr10d")
        score    = ctx.get("best_ma_score", 0)
        dist_str = f"{dist_pct:+.1f}%" if dist_pct is not None else "?"
        sr_str   = f"SR {sr10d:.0f}%" if sr10d is not None else ""
        if quality == "prime":
            badge    = "<span style='background:#1d9e75;color:#e1f5ee;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700;margin-right:3px'>PRIME</span>"
            dist_col = "#1d9e75"
        elif quality == "near":
            badge    = "<span style='background:#ba7517;color:#faeeda;padding:1px 5px;border-radius:3px;font-size:0.7rem;font-weight:700;margin-right:3px'>NEAR</span>"
            dist_col = "#ba7517"
        else:
            badge    = ""
            dist_col = "#5a7090"
        ma_line    = f"<span style='color:#8b9eb8;font-size:0.75rem'>{best_ma}</span>"
        dist_line  = f"<span style='color:{dist_col};font-size:0.75rem'>{dist_str}</span>"
        sr_line    = f"<span style='color:#5a8098;font-size:0.72rem'> {sr_str}</span>" if sr_str else ""
        score_line = f"<span style='color:#3a5570;font-size:0.68rem'> sc{score:.0f}</span>"
        summary    = f"{badge}{ma_line} {dist_line}{sr_line}{score_line}"

        # Quick/slow at recent window (opus-approved 2026-07-01) — tactical entry/stop
        # (quick) and trend/support (slow) lines, pinned to the same earliest qualifying
        # window. Collapsed by default to keep the action-board row scannable. No
        # PRIME/NEAR badge reuse — that calibration doesn't transfer to this selection.
        quick_ma, slow_ma = ctx.get("quick_ma"), ctx.get("slow_ma")
        if not quick_ma and not slow_ma:
            return summary
        win = _esc(ctx.get("recent_window", "?"))
        rows = [
            f"<div><span class='ma-prof-lbl'>Quick ({win})</span>"
            f"<span class='ma-prof-val'>{_esc(quick_ma) + ' ' + _signed_pct(ctx.get('quick_dist_pct')) if quick_ma else '—'}</span></div>",
            f"<div><span class='ma-prof-lbl'>Slow ({win})</span>"
            f"<span class='ma-prof-val'>{_esc(slow_ma) + ' ' + _signed_pct(ctx.get('slow_dist_pct')) if slow_ma else '—'}</span></div>",
        ]
        grid = "<div class='ma-prof-grid'>" + "".join(rows) + "</div>"
        card = (
            f"<div class='ma-prof'>{grid}"
            f"<div class='ma-prof-src'>Tactical lines, recent window · research scan, not backtest-validated · "
            f"data: ma_context_daily.json</div></div>"
        )
        return f"<details class='ma-det'><summary>{summary}</summary>{card}</details>"

    # ---- Section C: A3 Action Board ----
    c_parts = [
        '<div id="section-c" class="section-title">C. A3 Action Board '
        '<span class="ssot-tag">ACTION SSOT: final_action</span></div>'
    ]

    # Group 1: New T1
    if new_t1_rows_combined:
        c_parts.append("<strong>Group 1: New T1 Candidates</strong>")
        headers_t1 = ["Symbol", "Action", "Rank", "Close", "Signal timing", "PB trigger", "TP1", "Trail", "Liquidity", "S3 lead", "Sector L4", "S2 Vol†", "ED Band‡", "S1 52wk†", "Inst Flow", "MA Ctx", "Note"]
        rows_t1 = []
        row_cls_t1 = []
        for r in new_t1_rows_combined:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", "")
            rank = _fmt(_get(r, "a3_rank_score"))
            close = _fmt(_get(r, "close_kVND"))
            sig_timing = _esc(str(_get(r, "a3_planned_entry_timing", "—")))

            sig_today = normalize_bool(_get(r, "a3_signal_today", False))
            if sig_today is True:
                pb = '<span class="pending">pending*</span>'
                tp1 = '<span class="pending">pending*</span>'
                trail = '<span class="pending">pending*</span>'
                note = (
                    '<span class="td-trunc" style="color:var(--dim);font-size:0.75rem" '
                    'title="Signal confirmed at today\'s close; planned fill is next session open. '
                    'Entry levels are pending until the next-open fill price is known.">see ↓ note</span>'
                )
            else:
                pb = _fmt(_get(r, "pb_trigger_price"))
                tp1 = _fmt(_get(r, "tp1_price"))
                trail = _fmt(_get(r, "trail_price"))
                note = ""

            liq = _esc(str(_get(r, "liq_warn_T1", "OK")))
            s3_lead = _esc(str(_get(r, "s3_lead_bucket", "none")))
            sector = _esc(str(_get(r, "sector_l4", "—")))

            # S2/S1 advisory filter cells (ADVISORY ONLY — final_action is the binding surface)
            _s2_mult = _get(r, "s2_vol_mult")
            _s2_ok = normalize_bool(_get(r, "s2_pass"))
            _s1_prox = _get(r, "s1_prox_52wk")
            _s1_ok = normalize_bool(_get(r, "s1_pass"))
            _is_primary_s2 = (_active_filter_val == "s2")
            if _s2_mult is not None:
                _s2_num = f'<span style="font-family:monospace;font-size:0.8rem">{float(_s2_mult):.2f}×</span>'
                if _s2_ok is True:
                    _s2_cell = (
                        f'<span style="color:#1d9e75;font-weight:700">PASS</span> {_s2_num}'
                        + (' <span style="font-size:0.65rem;color:#5edd5e">▶PRIMARY</span>' if _is_primary_s2 else '')
                    )
                elif _s2_ok is False:
                    _s2_cell = (
                        f'<span style="color:#8b4040">FAIL</span> {_s2_num}'
                        + (' <span style="font-size:0.65rem;color:#8b4040">▶PRIMARY</span>' if _is_primary_s2 else '')
                    )
                else:
                    _s2_cell = '<span style="color:#5a7090">—</span>'
            else:
                _s2_cell = '<span style="color:#5a7090">no vol</span>'
            if _s1_prox is not None:
                _s1_num = f'<span style="font-family:monospace;font-size:0.8rem">{float(_s1_prox)*100:.1f}%</span>'
                if _s1_ok is True:
                    _s1_cell = (
                        f'<span style="color:#1d9e75;font-weight:700">PASS</span> {_s1_num}'
                        + ('' if _is_primary_s2 else ' <span style="font-size:0.65rem;color:#ffc107">▶FALLBK</span>')
                    )
                elif _s1_ok is False:
                    _s1_cell = f'<span style="color:#8b4040">FAIL</span> {_s1_num}'
                else:
                    _s1_cell = '<span style="color:#5a7090">—</span>'
            else:
                _s1_cell = '<span style="color:#5a7090">no data</span>'

            # ED band cell — S21 Zone finding (S2-tier only; display annotation, not OMS)
            # Zone (4-7% above EMA cloud): best S2 entry band (median +3.48%, win 53.5%)
            # Near (<4%): worst band (median −3.33%, >50% losers). Extended (>7%): intermediate.
            # ed_pct recovered: ed_pct = 20 × (1 − ed_score)  [good_band=20, hardcoded]
            if _s2_ok is True:
                _zb = _zone_band(r)
                _es_val = float(_get(r, "ed_score", 0) or 0)
                _ep_val = 20.0 * (1.0 - _es_val)
                if _zb == 2:   # Zone 4-7%
                    _zone_cell = (
                        f'<span style="color:#1d9e75;font-weight:700">Zone</span>'
                        f' <span style="font-family:monospace;font-size:0.78rem">{_ep_val:.1f}%</span>'
                    )
                elif _zb == 0:  # Near <4%
                    _zone_cell = (
                        f'<span style="color:#e09040;font-weight:600">Near</span>'
                        f' <span style="font-family:monospace;font-size:0.78rem">{_ep_val:.1f}%</span>'
                    )
                else:           # Extended >7%
                    _zone_cell = (
                        f'<span style="color:#5a7090">Ext</span>'
                        f' <span style="font-family:monospace;font-size:0.78rem">{_ep_val:.1f}%</span>'
                    )
            else:
                _zone_cell = '<span style="color:#5a7090">—</span>'

            cls_str = "row-green" if r["_action_group"] == "NEW_T1" else "row-amber"
            rows_t1.append([_esc(sym) + _prop_tilt_tag(sym), _esc(str(fa)), rank, close, sig_timing, pb, tp1, trail, liq, s3_lead, sector, _s2_cell, _zone_cell, _s1_cell, render_inst_accum_cell(sym, _inst_accum_index), _ma_ctx_cell(sym), note])
            row_cls_t1.append(cls_str)
        c_parts.append(
            '<div class="scroll-table">' + _html_table(headers_t1, rows_t1, row_cls_t1) + "</div>"
        )
        c_parts.append(
            '<p class="footnote">* Signal confirmed at today\'s close; planned fill is next session open. '
            'Entry levels are pending until the next-open fill price is known.</p>'
        )
        c_parts.append(
            f'<p class="footnote" style="color:#7a9ab0;">'
            f'† S2/S1 ADVISORY — entry filter status at signal bar. '
            f'Active filter: <strong>{_esc(_active_filter_val.upper())}</strong> '
            f'({_esc(_filter_ref)}). '
            f'DOES NOT change final_action. '
            f'S1+S2 combined use FORBIDDEN (knowledge.md). '
            f'To operationalize: Trigger #5 dual-judge required (high-stakes-triggers.md).</p>'
        )
        c_parts.append(
            '<p class="footnote" style="color:#7a9ab0;">'
            '‡ ED Band (S21 TESTED, N=1,621 pure-S2 OOS 2020–2026): '
            '<strong style="color:#1d9e75">Zone</strong> 4–7% above EMA cloud = best band '
            '(median +3.48%, win 53.5%); '
            '<strong style="color:#e09040">Near</strong> &lt;4% = worst band '
            '(median −3.33%, &gt;50% losers); '
            'Ext &gt;7% = intermediate. '
            'Display-only — does not affect final_action. '
            'Escalation to sizing/OMS requires pre-reg + Trigger #5.</p>'
        )
        c_parts.append(
            '<p class="footnote" style="color:#aec6e8;">'
            'Evidence status: Needs more history — not statistically validated.</p>'
        )

    # Group 2: T2/pullback
    t2_all = add_t2_rows + t2_blocked_rows
    if t2_all:
        c_parts.append("<strong>Group 2: T2 / Pullback Candidates</strong>")
        headers_t2 = ["Symbol", "Action", "Reason", "Close", "Rank", "Inst Flow", "MA Ctx"]
        rows_t2 = []
        row_cls_t2 = []
        for r in t2_all:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", r.get("would_be_final_action", ""))
            reason = _get(r, "final_action_reason", "")
            close = _fmt(_get(r, "close_kVND"))
            rank = _fmt(_get(r, "a3_rank_score"))
            cls_str = "row-amber" if r["_action_group"] == "ADD_T2" else "row-red"
            rows_t2.append([_esc(str(sym)), _esc(str(fa)), _td_trunc(reason), close, rank, render_inst_accum_cell(sym, _inst_accum_index), _ma_ctx_cell(sym)])
            row_cls_t2.append(cls_str)
        c_parts.append(_html_table(headers_t2, rows_t2, row_cls_t2))
        c_parts.append(
            '<p class="footnote" style="color:#aec6e8;">'
            'Evidence status: Needs more history — not statistically validated. '
            'Breadth block active; validation pending.</p>'
        )

    # Group 3: Exits
    if exit_rows:
        c_parts.append("<strong>Group 3: Exits</strong>")
        headers_ex = ["Symbol", "Action", "Close", "Trail", "MA Ctx", "Reason"]
        rows_ex = []
        for r in exit_rows:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", "")
            close = _fmt(_get(r, "close_kVND"))
            trail = _fmt(_get(r, "trail_price"))
            reason = _get(r, "final_action_reason", "")
            rows_ex.append([_esc(str(sym)), _esc(str(fa)), close, trail, _ma_ctx_cell(sym), _td_trunc(reason)])
        c_parts.append(_html_table(headers_ex, rows_ex, ["row-red"] * len(rows_ex)))
        c_parts.append(
            '<p class="footnote" style="color:#aec6e8;">'
            'Evidence status: Exit rule active; forward risk-control evidence pending.</p>'
        )

    # Group 4: Hold only (top 10)
    if hold_rows:
        c_parts.append("<strong>Group 4: Hold Only</strong>")
        headers_h = ["Symbol", "Close", "Rank", "MA Ctx", "Reason"]
        rows_h = []
        for r in hold_rows[:10]:
            sym = _get(r, "symbol", "?")
            close = _fmt(_get(r, "close_kVND"))
            rank = _fmt(_get(r, "a3_rank_score"))
            reason = _get(r, "final_action_reason", "")
            rows_h.append([_esc(str(sym)), close, rank, _ma_ctx_cell(sym), _td_trunc(reason)])
        c_parts.append(_html_table(headers_h, rows_h, ["row-gray"] * len(rows_h)))
        if len(hold_rows) > 10:
            c_parts.append(f'<p class="footnote">+ {len(hold_rows)-10} more in appendix</p>')

    parts.append('<div class="card">' + "".join(c_parts) + "</div>")

    # ---- Section D: Portfolio Command (Must Act / Verify / Hold) ----
    d_parts = [
        '<div id="section-d" class="section-title">D. Portfolio Command '
        '<span class="ssot-tag">ACTION SSOT: final_action</span></div>',
        f'<p class="footnote">Port = stock holdings only (excludes cash). '
        f'NAV is user-updated. Source: <code>{_esc(positions_source)}</code>'
        f'{"; per-holding context: <code>data/state/position_context_daily.json</code>" if _position_ctx_payload else ""}</p>',
        '<p class="footnote" style="color:#aec6e8;">'
        'Evidence status: Workflow control; needs position snapshot history.</p>',
    ]

    scan_sym_map: dict[str, dict] = {_get(r, "symbol", ""): r for r in classified}
    _exit_action_set = frozenset({"TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"})
    holdings_set_d = set(holdings)
    scan_syms_set = set(scan_sym_map.keys())

    # Build position detail map
    pos_detail: dict[str, dict] = {}
    if not positions_df.empty and "symbol" in positions_df.columns:
        for _, pr in positions_df.iterrows():
            s = str(pr.get("symbol", "")).upper()
            pos_detail[s] = pr.to_dict()

    has_lots = any("lots" in d for d in pos_detail.values())
    has_entry = any("entry_price" in d for d in pos_detail.values())

    if _prop_sector_enabled and holdings:
        try:
            from src.trading.overlays.propagation_display import build_portfolio_tilt_summary_html
            _tilt_positions: list[dict] = []
            for sym in holdings:
                pd_row = pos_detail.get(sym, {})
                lots = pd_row.get("lots")
                ep = pd_row.get("entry_price")
                scan_r = scan_sym_map.get(sym) or {}
                close_kvnd = _get(scan_r, "close_kVND")
                mkt_vnd = 0.0
                try:
                    if lots is not None and close_kvnd not in (None, "", "—"):
                        mkt_vnd = float(lots) * float(close_kvnd) * 1000.0
                    elif lots is not None and ep is not None:
                        mkt_vnd = float(lots) * float(ep)
                except (TypeError, ValueError):
                    mkt_vnd = 0.0
                _tilt_positions.append({"symbol": sym, "mkt_value_vnd": mkt_vnd})
            _tilt_summary = build_portfolio_tilt_summary_html(
                _tilt_positions, scan_date, include_empty_sectors=True, show_caption=False,
            )
            if _tilt_summary:
                d_parts.append(_tilt_summary)
        except Exception as _tilt_exc:
            warnings_list.append(f"Portfolio tilt summary skipped: {_tilt_exc}")

    def _dist(price: Any, ref: Any) -> str:
        try:
            p, rr = float(price), float(ref)
            if math.isnan(p) or math.isnan(rr) or rr == 0:
                return "—"
            return f"{((p - rr) / rr * 100):.1f}%"
        except (TypeError, ValueError):
            return "—"

    def _pos_row(sym: str, show_action: bool = True) -> tuple[list[str], str]:
        r = scan_sym_map.get(sym)
        ctx_rec = _position_ctx_map.get(sym, {})
        pd_row = pos_detail.get(sym, {})
        if not pd_row and ctx_rec:
            pd_row = {
                "lots": ctx_rec.get("lots"),
                "entry_price": ctx_rec.get("entry_price_vnd"),
            }
        lots_str = _fmt(pd_row.get("lots"), 0) if has_lots else "—"
        ep = pd_row.get("entry_price")
        entry_str = _fmt(float(ep) / 1000.0 if ep is not None else None) if has_entry else "—"

        cost_basis = None
        if pd_row.get("lots") is not None and ep is not None:
            try:
                cost_basis = float(pd_row["lots"]) * float(ep)
            except (TypeError, ValueError):
                pass

        # MA Dist — urgency-tagged + expandable profile card
        def _ma_urgency(ma_source: str, pct: float, sr_10d) -> str | None:
            """HIGH / MED / LOW urgency for breach positions only."""
            if pct >= 0:
                return None
            depth = abs(pct)
            dna = (ma_source == "dna")
            ema_res = (ma_source == "ema_research")
            sr_ok = sr_10d is not None and sr_10d >= 65.0
            if dna and depth >= 5.0:   return "HIGH"
            if dna and depth >= 2.0:   return "MED"
            if dna:                    return "LOW"   # near-zero DNA breach
            if ema_res and depth >= 5.0 and sr_ok: return "MED"
            if depth >= 10.0:          return "MED"   # fallback but very deep
            return "LOW"

        def _ma_dist_cell(s: str) -> str:
            rec = _ma_levels_map.get(s, {})
            pct = rec.get("pct_distance")
            breach = rec.get("primary_ma_breach", False)
            lbl = rec.get("ma_label", "")
            ma_source = rec.get("ma_source", "fallback")
            if pct is None:
                return "—"

            # E&MA historical reaction data (19 liquid IA-fav universe)
            er = _ema_research_map.get(s, {})
            sr_10d  = er.get("sr_10d")
            avg_10d = er.get("avg_10d")
            best_ma = er.get("best_ma")

            # Distance badge
            if breach:
                dist_html = f"<span style='color:#e74c3c;font-weight:bold;'>{pct:+.1f}% ({lbl})</span>"
            elif pct >= 0:
                dist_html = f"<span style='color:#27ae60;'>{pct:+.1f}% ({lbl})</span>"
            else:
                dist_html = f"<span style='color:#e67e22;'>{pct:+.1f}% ({lbl})</span>"

            # Non-breach: just show distance, no card
            if not breach:
                return dist_html

            # Urgency badge
            urgency = _ma_urgency(ma_source, pct, sr_10d)
            urg_map = {"HIGH": "<span class='urg-high'>HIGH</span>",
                       "MED":  "<span class='urg-med'>MED</span>",
                       "LOW":  "<span class='urg-low'>LOW</span>"}
            urg_html = urg_map.get(urgency, "")

            # Profile card rows
            src_label = {"dna": "DNA — High/Med Conf", "ema_research": "E&MA Research",
                         "fallback": "Fallback EMA10"}.get(ma_source, ma_source)
            card_cells = []
            card_cells.append(
                f"<div><span class='ma-prof-lbl'>Primary MA</span>"
                f"<span class='ma-prof-val'>{lbl.upper()}</span></div>"
            )
            card_cells.append(
                f"<div><span class='ma-prof-lbl'>Source</span>"
                f"<span class='ma-prof-val'>{src_label}</span></div>"
            )
            if sr_10d is not None:
                sr_c = "#27ae60" if sr_10d >= 70 else "#e67e22" if sr_10d >= 50 else "#e74c3c"
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Obedience (10d SR)</span>"
                    f"<span class='ma-prof-val' style='color:{sr_c};'>{sr_10d:.0f}%</span></div>"
                )
            else:
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Obedience (10d SR)</span>"
                    f"<span class='ma-prof-val' style='color:#3a5570;'>—</span></div>"
                )
            if avg_10d is not None:
                avg_c = "#27ae60" if avg_10d > 0 else "#e74c3c"
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Avg Bounce (10d)</span>"
                    f"<span class='ma-prof-val' style='color:{avg_c};'>{avg_10d:+.1f}%</span></div>"
                )
            else:
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Avg Bounce (10d)</span>"
                    f"<span class='ma-prof-val' style='color:#3a5570;'>—</span></div>"
                )
            if best_ma and best_ma.lower() != lbl.lower():
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Best MA (2y)</span>"
                    f"<span class='ma-prof-val' style='color:#8ab4f8;'>{best_ma}</span></div>"
                )

            # Quick/slow at recent window (opus-approved 2026-07-01) — see _ma_ctx_cell
            # for full rationale. Sourced from the broader 269-symbol liquid universe
            # (ma_context_daily.json), not the 19-symbol ema_research_map above.
            _mctx = _ma_ctx_map.get(s, {})
            _win = _mctx.get("recent_window")
            if _win:
                _win_e = _esc(_win)
                _qma = _mctx.get("quick_ma")
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Quick ({_win_e})</span>"
                    f"<span class='ma-prof-val'>"
                    f"{_esc(_qma) + ' ' + _signed_pct(_mctx.get('quick_dist_pct')) if _qma else '—'}"
                    f"</span></div>"
                )
                _sma = _mctx.get("slow_ma")
                card_cells.append(
                    f"<div><span class='ma-prof-lbl'>Slow ({_win_e})</span>"
                    f"<span class='ma-prof-val'>"
                    f"{_esc(_sma) + ' ' + _signed_pct(_mctx.get('slow_dist_pct')) if _sma else '—'}"
                    f"</span></div>"
                )

            grid = "<div class='ma-prof-grid'>" + "".join(card_cells) + "</div>"
            card = (
                f"<div class='ma-prof'>{grid}"
                f"<div class='ma-prof-src'>Tap to collapse · data: ma_reaction_stocks.json + ma_context_daily.json + DNA</div>"
                f"</div>"
            )
            summary = f"{dist_html}{urg_html}"
            return f"<details class='ma-det'><summary>{summary}</summary>{card}</details>"

        if r is None:
            base = ["NO", _esc(sym) + _prop_tilt_tag(sym)]
            if has_lots: base.append(lots_str)
            if has_entry: base.append(entry_str)
            base += ["NOT IN SCAN", "—", "—", "—", "VERIFY", _ma_dist_cell(sym)]
            return base, "row-amber"

        fa = _get(r, "final_action", "") or ctx_rec.get("final_action", "")
        close_kvnd = _get(r, "close_kVND") or ctx_rec.get("close_kvnd")
        trail = _get(r, "trail_price") or ctx_rec.get("trail_price_kvnd")
        tp1 = _get(r, "tp1_price") or ctx_rec.get("tp1_price_kvnd")
        oa = _esc(r["_operator_action"])
        dist_trail = (
            f"{ctx_rec['dist_trail_pct']:.1f}%"
            if ctx_rec.get("dist_trail_pct") is not None
            else _dist(close_kvnd, trail)
        )
        dist_tp1 = (
            f"{ctx_rec['dist_tp1_pct']:.1f}%"
            if ctx_rec.get("dist_tp1_pct") is not None
            else _dist(close_kvnd, tp1)
        )
        cls = "row-red" if r["_action_group"] == "EXIT_REVIEW" else "row-gray"
        base = ["YES", _esc(sym) + _prop_tilt_tag(sym)]
        if has_lots: base.append(lots_str)
        if has_entry: base.append(entry_str)
        if show_action:
            base += [_esc(str(fa)), _fmt(close_kvnd), dist_trail, dist_tp1, oa, _ma_dist_cell(sym)]
        else:
            base += ["—", "—", "—", "—", "VERIFY", _ma_dist_cell(sym)]
        return base, cls

    _port_headers = ["In Scan?", "Symbol"]
    if has_lots: _port_headers.append("Lots")
    if has_entry: _port_headers.append("Entry kVND")
    _port_headers += ["A3 Action", "Close kVND", "Dist Trail", "Dist TP1", "Op Action", "MA Signal ▾"]

    if not holdings:
        d_parts.append('<p class="meta">No holdings on record — skipping portfolio command.</p>')
    else:
        # Bucket 1: Must Act (exit-eligible)
        must_act_syms = [h for h in holdings
                         if _get(scan_sym_map.get(h) or {}, "final_action", "") in _exit_action_set]
        d_parts.append(
            '<div class="card port-must-act" style="margin:0.5rem 0;">'
            '<div class="subsection-title">&#9888; Must Act / Review — TRAIL_EXIT / TP1_PARTIAL</div>'
        )
        if must_act_syms:
            ma_rows, ma_cls = zip(*[_pos_row(s) for s in must_act_syms])
            d_parts.append('<div class="scroll-table">' + _html_table(_port_headers, list(ma_rows), list(ma_cls)) + "</div>")
        else:
            d_parts.append('<p class="meta">No TRAIL_EXIT or TP1_PARTIAL in current holdings.</p>')
        d_parts.append("</div>")

        # Bucket 2: Verify (not in scan)
        verify_syms = [h for h in holdings if h not in scan_syms_set]
        d_parts.append(
            '<div class="card port-verify" style="margin:0.5rem 0;">'
            '<div class="subsection-title">&#9888; Verify — Not in Scan Universe</div>'
        )
        if verify_syms:
            d_parts.append(
                '<p class="meta" style="color:#ffc107;">These holdings are NOT in today\'s scan. '
                'Verify positions and scan coverage manually.</p>'
            )
            v_rows, v_cls = zip(*[_pos_row(s, show_action=False) for s in verify_syms])
            d_parts.append('<div class="scroll-table">' + _html_table(_port_headers, list(v_rows), list(v_cls)) + "</div>")
        else:
            d_parts.append('<p class="meta">All holdings present in scan universe.</p>')
        d_parts.append("</div>")

        # Bucket 3: Hold / Watch
        hold_syms = [h for h in holdings
                     if h in scan_syms_set
                     and _get(scan_sym_map.get(h) or {}, "final_action", "") not in _exit_action_set]
        d_parts.append(
            '<div class="card port-hold" style="margin:0.5rem 0;">'
            '<div class="subsection-title">Hold / Watch</div>'
        )
        if hold_syms:
            hw_rows, hw_cls = zip(*[_pos_row(s) for s in hold_syms])
            d_parts.append('<div class="scroll-table">' + _html_table(_port_headers, list(hw_rows), list(hw_cls)) + "</div>")
        else:
            d_parts.append('<p class="meta">No hold/watch holdings.</p>')
        d_parts.append("</div>")

    if _prop_sector_enabled and _prop_sector_caption:
        d_parts.append(f'<p class="footnote meta">{_esc(_prop_sector_caption)}</p>')

    parts.append('<div class="card">' + "".join(d_parts) + "</div>")

    # ---- Section AR: Action Register ----
    ar_parts = [
        '<div id="section-ar" class="section-title">Action Register '
        '<span class="ssot-tag">ACTION SSOT: final_action</span></div>',
        '<p class="footnote">Priority-ordered. P1 = portfolio exits. P2 = not-in-scan holdings. '
        'P3 = manual review T1. P4 = T2 blocked in portfolio. '
        + ('P5 = CF annotation only (research, non-binding). ' if _cf_enabled else '')
        + '</p>',
    ]

    # Build CF lookup
    _cf_note_map: dict[str, str] = {}
    if _cf_enabled and not cf_ann_df.empty and "symbol" in cf_ann_df.columns:
        for _, cf_r in cf_ann_df.iterrows():
            _s = str(cf_r.get("symbol", "")).upper()
            _n = str(cf_r.get("cf_operator_note", "") or "")
            if _n:
                _cf_note_map[_s] = _n[:80]

    ar_headers = ["Priority", "Symbol", "final_action", "Operator Action", "Close kVND", "In Portfolio"]
    if _cf_enabled:
        ar_headers.append("CF Note")
    ar_rows: list[list[str]] = []
    ar_cls: list[str] = []

    # P1: Portfolio exits
    for r in exit_rows:
        sym = _get(r, "symbol", "?")
        if sym not in holdings_set_d:
            continue
        fa = _esc(_get(r, "final_action", ""))
        oa = _esc(r["_operator_action"])
        close = _fmt(_get(r, "close_kVND"))
        row = ['<span class="ar-p1">P1 EXIT</span>', _esc(sym), fa, oa, close, "YES"]
        if _cf_enabled:
            row.append(_esc(_cf_note_map.get(sym, "")))
        ar_rows.append(row)
        ar_cls.append("row-red")

    # P2: Holdings not in scan
    for sym in sorted(holdings_set_d - scan_syms_set):
        row = ['<span class="ar-p2">P2 VERIFY</span>', _esc(sym),
               "NOT IN SCAN", "VERIFY MANUALLY", "—", "YES"]
        if _cf_enabled:
            row.append(_esc(_cf_note_map.get(sym, "")))
        ar_rows.append(row)
        ar_cls.append("row-amber")

    # P3: Manual review T1
    for r in manual_t1_rows:
        sym = _get(r, "symbol", "?")
        fa = _esc(_get(r, "final_action", ""))
        oa = _esc(r["_operator_action"])
        close = _fmt(_get(r, "close_kVND"))
        row = ['<span class="ar-p3">P3 T1 MR</span>', _esc(sym), fa, oa, close,
               "YES" if sym in holdings_set_d else "No"]
        if _cf_enabled:
            row.append(_esc(_cf_note_map.get(sym, "")))
        ar_rows.append(row)
        ar_cls.append("row-amber")

    # P4: T2 blocked in portfolio
    for r in t2_blocked_rows:
        sym = _get(r, "symbol", "?")
        if sym not in holdings_set_d:
            continue
        fa = _esc(_get(r, "final_action", ""))
        oa = _esc(r["_operator_action"])
        close = _fmt(_get(r, "close_kVND"))
        row = ['<span class="ar-p4">P4 T2 BLK</span>', _esc(sym), fa, oa, close, "YES"]
        if _cf_enabled:
            row.append(_esc(_cf_note_map.get(sym, "")))
        ar_rows.append(row)
        ar_cls.append("row-gray")

    # P5: CF annotation only (not already covered above)
    if _cf_enabled and not cf_ann_df.empty:
        _ar_covered = {r[1] for r in ar_rows}  # all symbols already in register (HTML-escaped)
        try:
            cf_active = cf_ann_df[cf_ann_df["cf_annotation_active"] == 1]
            for _, cf_r in cf_active.iterrows():
                sym = str(cf_r.get("symbol", "")).upper()
                if _esc(sym) in _ar_covered:
                    continue
                note = str(cf_r.get("cf_operator_note", "") or "")[:80]
                row = ['<span class="ar-p5">P5 CF</span>', _esc(sym),
                       _esc(str(cf_r.get("cf_phase_label", ""))),
                       _esc(note), "—",
                       "YES" if sym in holdings_set_d else "No",
                       _esc(note)]
                ar_rows.append(row)
                ar_cls.append("row-gray")
        except Exception:
            pass

    if ar_rows:
        ar_parts.append('<div class="scroll-table">' + _html_table(ar_headers, ar_rows, ar_cls) + "</div>")
    else:
        ar_parts.append('<p class="meta">No priority actions requiring attention.</p>')

    parts.append('<div class="card">' + "".join(ar_parts) + "</div>")

    # ---- Section E: Intraday Preview Board ----
    if is_intraday:
        e_parts = ['<div class="section-title">E. Intraday Preview Board</div>']
        e_parts.append(
            '<div class="preview-banner">PREVIEW ONLY — no auto orders — '
            'would_be_final_action is planning only</div>'
        )
        e_parts.append(
            '<div class="preview-banner">'
            'auto_order_allowed = False for all rows. '
            'AUTO ORDER OFF. IF_CLOSE_NOW signal only.</div>'
        )

        # Meta info
        session_phase = intraday_meta.get("session_phase", "UNKNOWN")
        quote_cov = intraday_meta.get("intraday_quote_coverage_pct", None)
        missing_q = intraday_meta.get("missing_quote_count", "?")
        quoted_count = intraday_meta.get("quoted_symbols_count", "?")
        scan_count = intraday_meta.get("scan_symbols_count", "?")
        e_parts.append(
            f'<p class="meta">Session phase: {_esc(str(session_phase))} | '
            f'Quote coverage: {_fmt(quote_cov, 1) if quote_cov is not None else "?"} | '
            f'Quoted: {quoted_count}/{scan_count} | Missing quotes: {missing_q}</p>'
        )

        # VNINDEX
        vni = intraday_meta.get("vnindex", {})
        if vni:
            vni_eod = vni.get("vnindex_eod_close")
            vni_intra = vni.get("vnindex_intraday_close")
            vni_changed = vni.get("vnindex_regime_changed", False)
            e_parts.append(
                f'<p class="meta">VNINDEX EOD: {_fmt(vni_eod, 2)} | '
                f'Intraday: {_fmt(vni_intra, 2)} | '
                f'Regime changed: {vni_changed}</p>'
            )

        # Table
        if not intraday_df.empty:
            headers_intra = ["Symbol", "would_be", "auto_order", "data_quality", "session_phase"]
            rows_intra = []
            row_cls_intra = []
            for r in intraday_classified:
                sym = _get(r, "symbol", "?")
                wbfa = _get(r, "would_be_final_action", "—")
                auto_ord = _get(r, "auto_order_allowed", False)
                dq = _get(r, "intraday_data_quality", "—")
                sp = _get(r, "session_phase", "—")
                auto_ord_str = str(auto_ord)
                cls_str = "row-red" if str(auto_ord).lower() == "true" else "row-gray"
                rows_intra.append([_esc(str(sym)), _esc(str(wbfa)), _esc(auto_ord_str), _esc(str(dq)), _esc(str(sp))])
                row_cls_intra.append(cls_str)
            e_parts.append(_html_table(headers_intra, rows_intra, row_cls_intra))
        else:
            e_parts.append('<p class="meta">No intraday rows.</p>')

        parts.append('<div class="card">' + "".join(e_parts) + "</div>")

    # ---- Section F: S3 Radar ----
    f_parts = ['<div class="section-title">F. S3 Radar</div>']
    f_parts.append(
        '<p class="footnote" style="color:#ffc107;">'
        'S3 is paper-shadow only. Do not trade as live capital. '
        'Paper-shadow only; no real order.</p>'
    )
    if s3_rows:
        headers_s3 = ["Symbol", "S3 action", "GK5", "s3_top100_adv", "S3 lead bucket", "A3 link", "s3_no_real_order_flag"]
        rows_s3 = []
        for r in s3_rows:
            sym = _get(r, "symbol", "?")
            s3a = _get(r, "s3_shadow_action", "")
            gk5 = _fmt(_get(r, "s3_gk5"))
            top100 = _get(r, "s3_top100_adv", "—")
            lead_b = _get(r, "s3_lead_bucket", "none")
            a3_link = _get(r, "a3_active", "")
            no_real = _get(r, "s3_no_real_order_flag", True)
            rows_s3.append([_esc(str(sym)), _esc(str(s3a)), gk5, _esc(str(top100)),
                            _esc(str(lead_b)), _esc(str(a3_link)), _esc(str(no_real))])
        f_parts.append(_html_table(headers_s3, rows_s3, ["row-gray"] * len(rows_s3)))
    else:
        f_parts.append('<p class="meta">No S3 paper-shadow candidates.</p>')
    parts.append('<div class="card s3-section">' + "".join(f_parts) + "</div>")

    # ---- Section G: Market context ----
    g_parts = [
        '<div id="section-g" class="section-title">G. Market / Breadth / Risk '
        '<span class="ctx-tag">MARKET CONTEXT</span></div>',
        '<div class="ctx-safety">Distribution Risk and RS Correction are context lenses only — '
        'they do <strong>not</strong> set or override <code>final_action</code>.</div>',
    ]
    sector_stress = 0
    liq_warn = 0
    if not scan_df.empty:
        if "sector_l4_stress_flag" in scan_df.columns:
            sector_stress = int(scan_df["sector_l4_stress_flag"].isin(["OK", "UNKNOWN"]).sum() - len(scan_df))
            # Actually count non-OK and non-UNKNOWN
            sector_stress = int((~scan_df["sector_l4_stress_flag"].isin(["OK", "UNKNOWN"])).sum())
        if "liq_warn_T1" in scan_df.columns:
            liq_warn = int((scan_df["liq_warn_T1"] != "OK").sum())

    quote_cov_str = ""
    stale_str = ""
    if is_intraday:
        qc = intraday_meta.get("intraday_quote_coverage_pct")
        quote_cov_str = f"{_fmt(qc, 3)}" if qc is not None else "?"
        stale_keys = [k for k in intraday_meta if "stale" in k.lower()]
        stale_str = "; ".join(f"{k}={intraday_meta[k]}" for k in stale_keys)

    # E&MA Research: market-level MA breadth from market_flags.json
    _mf_path = REPO / "data/alerts/market_flags.json"
    _pct_above_sma200_str = "—"
    _ma_breach_str = "—"
    if _mf_path.exists():
        try:
            _mf = json.loads(_mf_path.read_text(encoding="utf-8"))
            _ma200_sum = _mf.get("ma200", {}).get("summary", {})
            _pct_above = _ma200_sum.get("pct_above")
            _above_n   = _ma200_sum.get("above_ma200_count", 0)
            _total_n   = _ma200_sum.get("above_ma200_count", 0) + _ma200_sum.get("below_ma200_count", 0)
            if _pct_above is not None:
                _pct_above_sma200_str = f"{_pct_above}% ({_above_n}/{_total_n} IA-liq)"
            _breach_alerts = _mf.get("ma_breach_alerts", {})
            _bc = _breach_alerts.get("breach_count", 0)
            _bs = _breach_alerts.get("breach_symbols", [])
            if _bc:
                _ma_breach_str = f"{_bc}: {', '.join(_bs)}"
            else:
                _ma_breach_str = "0"
        except Exception:
            pass

    kv_rows = [
        ["VNINDEX regime", regime_label],
        ["A3 breadth %", f"{breadth_pct * 100:.1f}%" if breadth_pct is not None else "—"],
        ["S3 breadth %", f"{s3_breadth_pct * 100:.1f}%" if s3_breadth_pct is not None else "—"],
        ["Breadth zone", bz_upper],
        ["T1 permission", t1_perm_label],
        ["T2 permission", t2_perm_label],
        ["Sector L4 stress count", str(sector_stress)],
        ["Liquidity warnings", str(liq_warn)],
        ["% above SMA200 (IA-liq)", _pct_above_sma200_str],
        ["Primary MA breaches", _ma_breach_str],
    ]
    if is_intraday:
        kv_rows.append(["Quote coverage", quote_cov_str])
        if stale_str:
            kv_rows.append(["Stale data", stale_str])

    kv_html = "<table><tbody>"
    for k, v in kv_rows:
        kv_html += f"<tr><th style='width:220px;'>{_esc(k)}</th><td>{_esc(v)}</td></tr>"
    kv_html += "</tbody></table>"
    g_parts.append(kv_html)
    g_parts.append(f'<p class="footnote">{_SECTION_G_BREADTH_FOOTNOTE}</p>')
    if drl_data:
        g_parts.append(
            "<details><summary>Distribution Risk Lens (click to expand)</summary>"
            + render_distribution_risk_html(drl_data)
            + '<p class="footnote" style="color:#aec6e8;">'
              'Risk context only; evidence incomplete until N/event count is available.</p>'
            + "</details>"
        )
    if rs_data:
        g_parts.append(
            "<details><summary>RS Correction Lens (click to expand)</summary>"
            + render_rs_correction_html(rs_data, scan_df=scan_df, holdings=holdings)
            + '<p class="footnote" style="color:#aec6e8;">'
              'Directional only — insufficient history.</p>'
            + "</details>"
        )
    if rs_c3_html_block is None:
        rs_c3_html_block, _c3w = build_rs_c3_section_for_cloud_daily(
            scan_date=scan_date, scan_df=scan_df, holdings=holdings
        )
        rs_c3_warns.extend(_c3w)
    if rs_c3_html_block:
        g_parts.append(
            "<details><summary>RS C3 Lens — review-ranking only; OOS IC near zero (click to expand)</summary>"
            + rs_c3_html_block
            + '<p class="footnote" style="color:#aec6e8;">'
              'Review-ranking only; not alpha.</p>'
            + "</details>"
        )
    if _seasonality_data:
        g_parts.append(
            "<details><summary>Seasonality Lens — VNINDEX Jun/Jul + H2 Calendar "
            "(click to expand)</summary>"
            + render_seasonality_html(_seasonality_data, today=ts)
            + "</details>"
        )
    parts.append('<div class="card">' + "".join(g_parts) + "</div>")

    # ---- Section CF: Capital Footprint Annotation Details (collapsed, optional) ----
    if _cf_enabled and not cf_ann_df.empty:
        cf_detail_parts = [
            '<div class="section-title">CF Annotation Details '
            '<span class="ctx-tag">RESEARCH ONLY — non-binding</span></div>',
            '<p class="footnote" style="color:#ffc107;">'
            'Phase 3 research labels. Do NOT change final_action, sizing, OMS, or DNSE logic. '
            'Operator review only.</p>',
        ]
        try:
            cf_active = cf_ann_df[cf_ann_df["cf_annotation_active"] == 1]
            cf_passive = cf_ann_df[
                (cf_ann_df["cf_annotation_active"] != 1) &
                cf_ann_df.get("cf_phase_label", pd.Series(dtype=str)).notna() &
                (cf_ann_df.get("cf_phase_label", pd.Series(dtype=str)) != "NEUTRAL") &
                (cf_ann_df.get("cf_phase_label", pd.Series(dtype=str)) != "")
            ]

            if not cf_active.empty:
                cf_act_headers = ["Symbol", "CF Label", "Operator Note", "Event Age", "Regime"]
                cf_act_rows = []
                for _, cfr in cf_active.iterrows():
                    age = _fmt(cfr.get("cf_event_age"), 0) if not pd.isna(cfr.get("cf_event_age", float("nan"))) else "—"
                    cf_act_rows.append([
                        _esc(str(cfr.get("symbol", ""))),
                        _esc(str(cfr.get("cf_phase_label", ""))),
                        _esc(str(cfr.get("cf_operator_note", ""))[:80]),
                        age,
                        _esc(str(cfr.get("cf_breadth_regime_bucket", ""))),
                    ])
                cf_detail_parts.append(f"<strong>Active annotations ({len(cf_active)})</strong>")
                cf_detail_parts.append(_html_table(cf_act_headers, cf_act_rows,
                                                    ["row-amber"] * len(cf_act_rows)))

            if not cf_passive.empty:
                cf_pas_headers = ["Symbol", "CF Label", "Note"]
                cf_pas_rows = [
                    [_esc(str(r.get("symbol", ""))),
                     _esc(str(r.get("cf_phase_label", ""))),
                     _esc(str(r.get("cf_operator_note", ""))[:80])]
                    for _, r in cf_passive.iterrows()
                ]
                cf_detail_parts.append(f"<strong>Passive / observe-only ({len(cf_passive)})</strong>")
                cf_detail_parts.append(_html_table(cf_pas_headers, cf_pas_rows,
                                                    ["row-gray"] * len(cf_pas_rows)))
        except Exception:
            cf_detail_parts.append('<p class="meta">CF annotation data unavailable.</p>')

        parts.append(
            '<div class="card">'
            "<details><summary>Capital Footprint Annotation Details (click to expand)</summary>"
            + "".join(cf_detail_parts)
            + "</details></div>"
        )

    # ---- Section H: Delta ----
    h_parts = ['<div id="section-h" class="section-title">H. Delta vs Previous</div>']
    if prev_json:
        if delta.get("new_candidates_added"):
            h_parts.append(f"<p>New candidates added: <strong>{', '.join(delta['new_candidates_added'])}</strong></p>")
        if delta.get("new_candidates_removed"):
            h_parts.append(f"<p>Candidates removed: <strong>{', '.join(delta['new_candidates_removed'])}</strong></p>")
        if delta.get("breadth_zone_changed"):
            bz_ch = delta["breadth_zone_changed"]
            h_parts.append(f"<p>Breadth zone changed: {_esc(str(bz_ch.get('from')))} → {_esc(str(bz_ch.get('to')))}</p>")
        if delta.get("regime_changed"):
            rc = delta["regime_changed"]
            h_parts.append(f"<p>Regime changed: {_esc(str(rc.get('from')))} → {_esc(str(rc.get('to')))}</p>")
        if delta.get("count_changes"):
            cc_rows = [[k, str(v.get("from")), str(v.get("to"))] for k, v in delta["count_changes"].items()]
            h_parts.append(_html_table(["Metric", "Previous", "Current"], cc_rows))
        if not any(delta.values()):
            h_parts.append('<p class="meta">No changes from previous report.</p>')
    else:
        h_parts.append('<p class="meta">No previous report found — first run.</p>')
    parts.append('<div class="card">' + "".join(h_parts) + "</div>")

    # ---- Section I: Appendix (collapsible) ----
    i_parts = ['<div id="section-i" class="section-title">I. Appendix</div>']
    try:
        from src.trading.overlays.propagation_display import build_phase_d_arc_html
        _arc_html = build_phase_d_arc_html(scan_date)
        if _arc_html:
            i_parts.append(
                '<details><summary>Phase D Research Arc (D1–D4)</summary>'
                + _arc_html
                + "</details>"
            )
    except Exception:
        pass
    i_parts.append("<details><summary>Full scan table (click to expand)</summary>")
    if not scan_df.empty:
        cols_show = [c for c in scan_df.columns if not c.startswith("_")][:30]
        app_headers = list(cols_show)
        app_rows = []
        for _, row in scan_df[cols_show].iterrows():
            app_rows.append([_esc(str(row[c])) for c in cols_show])
        i_parts.append('<div class="scroll-table">' + _html_table(app_headers, app_rows) + "</div>")
    else:
        i_parts.append('<p class="meta">No scan data.</p>')
    i_parts.append("</details>")
    i_parts.append("<details><summary>Files used</summary><ul>")
    for f in files_used:
        i_parts.append(f"<li>{_esc(f)}</li>")
    i_parts.append("</ul></details>")
    parts.append('<div class="card">' + "".join(i_parts) + "</div>")

    _sidebar_spy_js = """<script>
(function(){
  var divs=document.querySelectorAll('[id^="section-"]');
  var links=document.querySelectorAll('.sidebar a');
  if(!divs.length||!links.length)return;
  var obs=new IntersectionObserver(function(entries){entries.forEach(function(e){if(e.isIntersecting){links.forEach(function(l){l.classList.remove('active');});var a=document.querySelector('.sidebar a[href="#'+e.target.id+'"]');if(a)a.classList.add('active');}});},{threshold:0.15,rootMargin:'-10% 0px -70% 0px'});
  divs.forEach(function(s){obs.observe(s);});
})();
</script>"""
    parts.append("</div></div>" + _TV_POPUP_JS + _sys_controls_js + _live_mode_js + _sidebar_spy_js + "</body></html>")
    html_str = "\n".join(parts)

    # ========================================================================
    # BUILD MD
    # ========================================================================

    md_parts: list[str] = []
    md_parts.append(f"# Cloud Daily Report — {ts_str}")
    nav_md = f"{nav_vnd/1e9:.2f}bn VND" if nav_vnd is not None else "unknown"
    pos_src_md = positions_source if positions_source != "missing" else "missing"
    md_parts.append(
        f"\n**Mode:** {mode_label} | **VNINDEX:** {regime_label} | "
        f"**Breadth:** {bz_upper} | **T1:** {t1_perm_label} | **T2:** {t2_perm_label} | "
        f"**NAV:** {nav_md} | **Positions:** {pos_src_md}"
    )

    if is_intraday:
        md_parts.append("\n> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW")
        md_parts.append("> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.")

    md_parts.append("\n> Daily scan is source of truth. AFL is visual only.")

    if warnings_list:
        md_parts.append("\n## Warnings")
        for w in warnings_list:
            md_parts.append(f"- {w}")

    md_parts.append("\n## B. Decision Summary")
    md_parts.append("\n### ACTION NOW")
    for item in action_now_items:
        md_parts.append(f"- {item}")
    if not action_now_items:
        md_parts.append("- No immediate actions required")

    md_parts.append("\n### WATCH / PREPARE")
    for item in watch_items:
        md_parts.append(f"- {item}")

    md_parts.append("\n### DO NOT DO")
    for item in dont_items:
        md_parts.append(f"- {item}")

    md_parts.append("\n## C. A3 Action Board")

    if new_t1_rows_combined:
        md_parts.append("\n### Group 1: New T1 Candidates")
        t1_md_rows = []
        for r in new_t1_rows_combined:
            sig_today = normalize_bool(_get(r, "a3_signal_today", False))
            if sig_today is True:
                pb = "pending*"
                tp1_v = "pending*"
                trail_v = "pending*"
                note = (
                    "Signal confirmed at today's close; planned fill is next session open. "
                    "Entry levels are pending until the next-open fill price is known."
                )
            else:
                pb = _fmt(_get(r, "pb_trigger_price"))
                tp1_v = _fmt(_get(r, "tp1_price"))
                trail_v = _fmt(_get(r, "trail_price"))
                note = ""
            t1_md_rows.append([
                str(_get(r, "symbol", "?")),
                str(_get(r, "final_action", "")),
                _fmt(_get(r, "a3_rank_score")),
                _fmt(_get(r, "close_kVND")),
                pb, tp1_v, trail_v, note,
            ])
        md_parts.append(_md_table(["Symbol", "Action", "Rank", "Close", "PB", "TP1", "Trail", "Note"], t1_md_rows))
        md_parts.append(
            "\n*Signal confirmed at today's close; planned fill is next session open. "
            "Entry levels are pending until the next-open fill price is known.*"
        )

    if t2_all:
        md_parts.append("\n### Group 2: T2 / Pullback")
        t2_md_rows = [[str(_get(r, "symbol")), str(_get(r, "final_action")), _fmt(_get(r, "close_kVND")), _fmt(_get(r, "a3_rank_score"))] for r in t2_all]
        md_parts.append(_md_table(["Symbol", "Action", "Close", "Rank"], t2_md_rows))

    if exit_rows:
        md_parts.append("\n### Group 3: Exits")
        ex_md_rows = [[str(_get(r, "symbol")), str(_get(r, "final_action")), _fmt(_get(r, "close_kVND")), _fmt(_get(r, "trail_price")), str(_get(r, "final_action_reason", ""))] for r in exit_rows]
        md_parts.append(_md_table(["Symbol", "Action", "Close", "Trail", "Reason"], ex_md_rows))

    md_parts.append("\n## G. Market Context")
    md_parts.append(f"- VNINDEX regime: {regime_label}")
    md_parts.append(f"- A3 breadth: {_fmt(pct_cloud_bull_a3, 4)}")
    md_parts.append(f"- Breadth zone: {bz_upper}")
    md_parts.append(f"- T1 permission: {t1_perm_label}")
    md_parts.append(f"- T2 permission: {t2_perm_label}")
    md_parts.append(f"- Sector L4 stress: {sector_stress}")
    md_parts.append(f"- Liquidity warnings: {liq_warn}")
    if drl_data:
        md_parts.append("\n" + render_distribution_risk_md(drl_data))
    if rs_data:
        md_parts.append(
            "\n" + render_rs_correction_md(rs_data, scan_df=scan_df, holdings=holdings)
        )
    if rs_c3_html_block:
        from src.trading.reports.rs_c3_card import (
            build_rs_c3_section_for_daily_scan as _build_c3_md,
        )
        c3_md, _ = _build_c3_md(scan_date=scan_date, scan_df=scan_df)
        md_parts.append(c3_md)
    if _seasonality_data:
        md_parts.append(render_seasonality_md(_seasonality_data))

    if delta:
        md_parts.append("\n## H. Delta vs Previous")
        if delta.get("new_candidates_added"):
            md_parts.append(f"- New: {', '.join(delta['new_candidates_added'])}")
        if delta.get("new_candidates_removed"):
            md_parts.append(f"- Removed: {', '.join(delta['new_candidates_removed'])}")
    else:
        if prev_json is not None:
            md_parts.append("\n## H. Delta vs Previous\nNo changes from previous report.")
        else:
            md_parts.append("\n## H. Delta vs Previous\nNo previous report found — first run.")

    md_str = "\n".join(md_parts)

    # ========================================================================
    # BUILD JSON
    # ========================================================================

    json_payload = {
        "report_mode": mode,
        "report_timestamp": ts.isoformat(),
        "scan_path": scan_path_str,
        "panel_asof_date": panel_asof,
        "scan_date": scan_date,
        "report_status": report_status,
        "counts": counts,
        "top_actions": top_actions,
        "warnings": warnings_list,
        "files_used": files_used,
        "previous_report_delta": delta,
        "new_entry_symbols": new_entry_symbols,
        "regime_bull": regime_bull,
        "breadth_zone": breadth_zone,
        # Portfolio state fields
        "portfolio_state_path": portfolio_state_path,
        "portfolio_nav_vnd": nav_vnd,
        "portfolio_as_of_date": portfolio_as_of_date,
        "positions_path": positions_source if positions_source != "missing" else None,
        "port_excludes_cash": True,
        "nav_is_user_updated": True,
        "distribution_risk_lens": drl_data,
        "distribution_risk_lens_version": (
            drl_data.get("method_version") if isinstance(drl_data, dict) else None
        ),
        "rs_correction_lens": rs_data,
        "rs_correction_lens_version": (
            rs_data.get("method_version") if isinstance(rs_data, dict) else None
        ),
    }

    # CF annotation JSON payload (non-binding; never includes final_action)
    if _cf_enabled and not cf_ann_df.empty:
        try:
            json_payload["cf_annotation"] = build_cf_annotation_json(
                cf_ann_df, as_of_date=scan_date
            )
        except Exception:
            json_payload["cf_annotation"] = {"enabled": True, "error": "build failed"}
    elif _cf_enabled:
        json_payload["cf_annotation"] = {"enabled": True, "n_active": 0, "active_annotations": []}

    # CF observation ledger append (when enabled)
    if _cf_enabled and not cf_ann_df.empty and scan_date:
        try:
            _append_cf_obs_ledger_cloud(cf_ann_df, holdings_set_d, scan_date)
        except Exception as _led_exc:
            warnings_list.append(f"CF ledger append skipped: {_led_exc}")

    return html_str, md_str, json_payload


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------

def write_report(mode: str, ts: datetime | None = None, scan_path: Path | None = None) -> dict:
    """Top-level: load, build, write files. Returns dict of output paths."""
    if ts is None:
        ts = datetime.now(tz=timezone.utc)

    inputs = load_inputs(mode, scan_path=scan_path)
    resolved_mode = inputs["mode"]

    drl_as_of = None
    scan_df = inputs.get("scan_df")
    if scan_df is not None and not scan_df.empty:
        raw = scan_df.iloc[0].get("as_of_date")
        if raw is not None and str(raw) not in ("", "nan"):
            drl_as_of = str(raw)[:10]

    drl_warnings: list[str] = []
    skip_lens_refresh = os.environ.get("SKIP_LENS_REFRESH", "").strip() in ("1", "true", "yes")
    try:
        if not skip_lens_refresh:
            drl_warnings.extend(refresh_distribution_risk_for_reports(as_of=drl_as_of))
        drl_data, load_warns = load_distribution_risk_latest()
        drl_warnings.extend(load_warns)
        inputs["distribution_risk_lens"] = drl_data
        inputs["distribution_risk_warnings"] = drl_warnings
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Distribution Risk Lens refresh skipped: %s", exc)
        inputs["distribution_risk_lens"] = None
        inputs["distribution_risk_warnings"] = [f"distribution_risk_lens refresh failed: {exc}"]

    rs_warnings: list[str] = []
    try:
        if not skip_lens_refresh:
            rs_warnings.extend(refresh_rs_correction_for_reports(as_of=drl_as_of))
        rs_data, rs_load_warns = load_rs_correction_latest()
        rs_warnings.extend(rs_load_warns)
        inputs["rs_correction_lens"] = rs_data
        inputs["rs_correction_warnings"] = rs_warnings
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("RS correction lens refresh skipped: %s", exc)
        inputs["rs_correction_lens"] = None
        inputs["rs_correction_warnings"] = [f"rs_correction_lens refresh failed: {exc}"]

    try:
        _c3_html, _c3_warns = build_rs_c3_section_for_cloud_daily(
            scan_date=drl_as_of, scan_df=scan_df
        )
        inputs["rs_c3_html"] = _c3_html
        inputs["rs_c3_warnings"] = _c3_warns
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("RS C3 card skipped: %s", exc)
        inputs["rs_c3_html"] = None
        inputs["rs_c3_warnings"] = [f"rs_c3_card skipped: {exc}"]

    try:
        from scripts.reporting.build_position_context_daily import build_position_context
        from src.trading.reports.report_suite_common import POSITION_CONTEXT_PATH

        _pc_payload = build_position_context()
        POSITION_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        POSITION_CONTEXT_PATH.write_text(
            json.dumps(_pc_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("position_context_daily build skipped: %s", exc)

    html_str, md_str, json_payload = build_report(resolved_mode, inputs, ts)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    ts_file = ts.strftime("%Y%m%d_%H%M")

    html_latest = REPORTS_DIR / "cloud_daily_report_latest.html"
    html_ts = REPORTS_DIR / f"cloud_daily_report_{ts_file}.html"
    md_latest = REPORTS_DIR / "cloud_daily_report_latest.md"
    md_ts = REPORTS_DIR / f"cloud_daily_report_{ts_file}.md"
    json_path = REPORTS_DIR / "cloud_daily_report_latest.json"

    html_latest.write_text(html_str, encoding="utf-8")
    html_ts.write_text(html_str, encoding="utf-8")
    md_latest.write_text(md_str, encoding="utf-8")
    md_ts.write_text(md_str, encoding="utf-8")
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return {
        "mode": resolved_mode,
        "report_status": json_payload["report_status"],
        "html_latest": str(html_latest),
        "html_ts": str(html_ts),
        "md_latest": str(md_latest),
        "md_ts": str(md_ts),
        "json_path": str(json_path),
        "warnings": json_payload["warnings"],
        "counts": json_payload["counts"],
    }
