#!/usr/bin/env python3
"""
E&MA Research — standalone HTML report generator.
Reads:  data/research/ma_reaction_study.json           (VNINDEX)
        data/research/ma_reaction_stocks.json           (IA Tier 2-3 liquid stocks)
        data/research/ma_reaction_liquid_expanded.json  (269 liquid ADV50>=2B, optional)
Writes: data/research/reports/ema_research_latest.html
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

REPO         = Path(__file__).resolve().parents[1]
STUDY_PATH   = REPO / "data/research/ma_reaction_study.json"
STOCKS_PATH  = REPO / "data/research/ma_reaction_stocks.json"
LIQUID_PATH  = REPO / "data/research/ma_reaction_liquid_expanded.json"
OUT_PATH     = REPO / "data/research/reports/ema_research_latest.html"

TODAY = date.today().isoformat()

# ── colour helpers ────────────────────────────────────────────────────────────

_SENTINEL = -999.0   # insufficient data marker from run_ma_reaction_study.py

def _score_bg(score: float | None, lo: float = 10, hi: float = 50) -> str:
    """Dark-theme cell background: red→amber→green."""
    if score is None or score <= _SENTINEL + 1:
        return "#0d1117"
    t = max(0.0, min(1.0, (score - lo) / (hi - lo)))
    if t < 0.5:
        r, g, b = int(80 + 40 * (1 - t * 2)), int(20 + 30 * t * 2), 20
    else:
        r, g, b = int(20 + 60 * (1 - (t - 0.5) * 2)), int(80 + 40 * (t - 0.5) * 2), 20
    return f"rgb({r},{g},{b})"

def _sr_color(v: float | None) -> str:
    if v is None:  return "#5a7090"
    if v >= 70:    return "#4caf50"
    if v >= 55:    return "#ffc107"
    return "#f44336"

def _ret_color(v: float | None) -> str:
    if v is None:  return "#5a7090"
    if v >= 3:     return "#4caf50"
    if v >= 1:     return "#8bc34a"
    if v >= 0:     return "#ffc107"
    return "#f44336"

def _esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.5}
a{color:#58a6ff;text-decoration:none}
h1{font-size:1.25rem;font-weight:700;color:#e6edf3;margin-bottom:0.2rem}
h2{font-size:1rem;font-weight:700;color:#aac4f0;border-bottom:1px solid #21262d;padding-bottom:6px;margin-bottom:12px}
h3{font-size:0.85rem;font-weight:700;color:#8ab4f8;margin-bottom:8px}
.header{background:#161b22;border-bottom:1px solid #21262d;padding:14px 24px;display:flex;align-items:center;gap:16px}
.badge{background:#1f3a5f;color:#58a6ff;border:1px solid #1f6feb;border-radius:12px;padding:2px 10px;font-size:0.72rem;font-weight:700}
.container{max-width:1400px;margin:0 auto;padding:20px 24px}
/* tabs */
.tabs{display:flex;gap:4px;margin-bottom:20px;border-bottom:1px solid #21262d;padding-bottom:0}
.tab{padding:8px 18px;cursor:pointer;border-radius:6px 6px 0 0;font-size:0.85rem;font-weight:600;color:#8b949e;border:1px solid transparent;border-bottom:none;margin-bottom:-1px}
.tab.active{background:#161b22;color:#58a6ff;border-color:#21262d;border-bottom:1px solid #161b22}
.tab:hover:not(.active){color:#c9d1d9}
.pane{display:none}.pane.active{display:block}
/* cards */
.card-row{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px 18px;min-width:180px;flex:1}
.card.gold{border-color:#b8860b}
.card.silver{border-color:#7a8a9a}
.card.bronze{border-color:#8b4513}
.card-rank{font-size:0.68rem;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;color:#8b949e;margin-bottom:4px}
.card-ma{font-size:1.6rem;font-weight:800;color:#e6edf3;margin-bottom:2px}
.card-score{font-size:1rem;font-weight:700;color:#58a6ff}
.card-meta{font-size:0.75rem;color:#8b949e;margin-top:4px}
/* insight box */
.insight{background:#1a2332;border-left:3px solid #58a6ff;border-radius:0 6px 6px 0;padding:10px 16px;margin-bottom:20px;font-size:0.82rem;color:#aac4f0}
.insight b{color:#e6edf3}
/* tables */
.tbl-wrap{overflow-x:auto;margin-bottom:24px}
table{border-collapse:collapse;width:100%;font-size:0.8rem}
th{background:#161b22;color:#8ab4f8;font-weight:700;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;padding:7px 10px;border-bottom:2px solid #21262d;white-space:nowrap;text-align:left}
td{padding:6px 10px;border-bottom:1px solid #161b22;vertical-align:middle;white-space:nowrap}
tr:hover td{background:#1c2130}
.num{text-align:right;font-variant-numeric:tabular-nums}
.rank-no{width:28px;color:#5a6a7a;font-size:0.72rem;font-weight:700;text-align:center}
/* heatmap cell */
.hm{text-align:center;font-weight:700;font-size:0.78rem;border-radius:4px;padding:5px 8px}
/* sym card grid */
.sym-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;margin-bottom:24px}
.sym-card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px}
.sym-card.breach{border-color:#8b2020}
.sym-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.sym-name{font-size:1rem;font-weight:800;color:#e6edf3}
.sym-best{font-size:0.78rem;font-weight:700;color:#58a6ff;background:#1f3a5f;border-radius:4px;padding:2px 8px}
.sym-row{display:flex;justify-content:space-between;font-size:0.8rem;padding:3px 0;border-bottom:1px solid #1a2030}
.sym-row:last-child{border-bottom:none}
.sym-lbl{color:#8b949e}
.sym-val{font-weight:600}
/* sr bar */
.sr-bar-bg{background:#21262d;border-radius:3px;height:6px;width:80px;display:inline-block;vertical-align:middle;margin-left:6px}
.sr-bar{height:6px;border-radius:3px;display:block}
/* section label */
.section-hdr{display:flex;align-items:center;gap:10px;margin-bottom:16px}
.ssot-tag{font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;background:#0f2010;color:#5edd5e;border:1px solid #1e4020;border-radius:3px;padding:1px 7px}
.warn-tag{font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;background:#2e1f00;color:#ffc107;border:1px solid #5a3d00;border-radius:3px;padding:1px 7px}
/* window pills */
.win-pill{display:inline-block;background:#1a2a40;color:#8ab4f8;border-radius:10px;padding:2px 9px;font-size:0.7rem;font-weight:700;margin:0 2px}
/* footnote */
.footnote{font-size:0.72rem;color:#5a7090;margin-top:8px}
"""

# ── HTML builders ─────────────────────────────────────────────────────────────

def _medal(i: int) -> str:
    return ["🥇","🥈","🥉","  4","  5","  6","  7","  8","  9"," 10"," 11"," 12"," 13"," 14"][i] if i < 14 else f"{i+1:3}"

def top_cards(ranking: list[tuple[str, float]], n: int = 5) -> str:
    colors = ["gold","silver","bronze","",""]
    labels = ["#1 Cross-Window","#2","#3","#4","#5"]
    out = '<div class="card-row">'
    for i, (ma, score) in enumerate(ranking[:n]):
        cls = colors[i] if i < len(colors) else ""
        out += f'''<div class="card {cls}">
  <div class="card-rank">{labels[i]}</div>
  <div class="card-ma">{_esc(ma)}</div>
  <div class="card-score">Score {score:.2f}</div>
</div>'''
    out += "</div>"
    return out


def vnindex_section(study: dict) -> str:
    cw = sorted(study["cross_window_avg_score"].items(), key=lambda x: -x[1])
    windows_order = ["10y","5y","2y","1y","6m","3m"]
    all_mas = [ma for ma, _ in cw]

    parts = []

    # Insight box
    top3 = ", ".join(f"<b>{ma}</b> ({sc:.1f})" for ma, sc in cw[:3])
    parts.append(f'<div class="insight">Cross-window leaders (VNINDEX 2012–2026, 6 windows × 14 MAs): {top3}. '
                 f'SMA200 dominates long windows; EMA5 active in recent regimes.</div>')

    # Top 5 hero cards
    parts.append(top_cards(cw, 5))

    # Heatmap table: rows = windows, cols = MAs (ranked by cross-window)
    parts.append('<h3>Score Heatmap — by Window &amp; MA</h3>')
    parts.append('<p class="footnote">Score = 0.4×SR% + 0.3×avg_ret_10d + 0.2×pct_gt2_10d − 0.1×avgMDD_10d. '
                 'Colour: <span style="color:#4caf50">■</span> high &nbsp; '
                 '<span style="color:#ffc107">■</span> mid &nbsp; '
                 '<span style="color:#f44336">■</span> low</p>')
    parts.append('<div class="tbl-wrap"><table>')

    # Header row
    th_mas = "".join(f"<th class='num'>{_esc(ma)}</th>" for ma in all_mas)
    parts.append(f"<thead><tr><th>Window</th><th>Period</th>{th_mas}</tr></thead><tbody>")

    for wk in windows_order:
        wdata = study["windows"].get(wk)
        if not wdata:
            continue
        score_map = {r["ma"]: r["score"] for r in wdata["rankings"]}
        period = f"{wdata.get('window_start','')[:7]} → {wdata.get('window_end','')[:7]}"
        cells = ""
        for ma in all_mas:
            sc = score_map.get(ma)
            is_sentinel = sc is not None and sc <= _SENTINEL + 1
            bg = _score_bg(sc)
            if sc is None or is_sentinel:
                cells += "<td class='hm' style='background:#0d1117;color:#3a5570'>—</td>"
            else:
                cells += f"<td class='hm' style='background:{bg}'>{sc:.1f}</td>"
        parts.append(f"<tr><td><span class='win-pill'>{wk}</span></td><td style='color:#5a7090;font-size:0.75rem'>{period}</td>{cells}</tr>")

    parts.append("</tbody></table></div>")

    # Full ranking table (cross-window, all MAs)
    parts.append('<h3>Full Ranking — Cross-Window Average Score</h3>')
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th class="rank-no">#</th><th>MA</th><th class="num">Avg Score</th>'
                 '<th class="num">10y</th><th class="num">5y</th><th class="num">2y</th>'
                 '<th class="num">1y</th><th class="num">6m</th><th class="num">3m</th>'
                 '</tr></thead><tbody>')
    for i, (ma, avg_sc) in enumerate(cw):
        win_scores = []
        for wk in windows_order:
            wdata = study["windows"].get(wk, {})
            sm = {r["ma"]: r["score"] for r in wdata.get("rankings", [])}
            sc = sm.get(ma)
            if sc is not None:
                win_scores.append(f"<td class='num' style='color:#8ab4f8'>{sc:.1f}</td>")
            else:
                win_scores.append("<td class='num' style='color:#3a5570'>—</td>")
        bg = _score_bg(avg_sc)
        parts.append(
            f"<tr><td class='rank-no'>{i+1}</td>"
            f"<td><b>{_esc(ma)}</b></td>"
            f"<td class='num'><span class='hm' style='background:{bg}'>{avg_sc:.2f}</span></td>"
            + "".join(win_scores) + "</tr>"
        )
    parts.append("</tbody></table></div>")

    # Detailed window tables (collapsible)
    parts.append('<h3>Per-Window Detail Tables</h3>')
    for wk in windows_order:
        wdata = study["windows"].get(wk)
        if not wdata:
            continue
        period = f"{wdata.get('window_start','')[:10]} → {wdata.get('window_end','')[:10]}"
        parts.append(f'<details style="margin-bottom:10px"><summary style="cursor:pointer;color:#58a6ff;font-weight:700;padding:6px 0">'
                     f'Window: <span class="win-pill">{wk}</span> &nbsp; <span style="color:#5a7090;font-size:0.78rem;font-weight:400">{period}</span></summary>')
        parts.append('<div class="tbl-wrap" style="margin-top:8px"><table><thead><tr>'
                     '<th class="rank-no">#</th><th>MA</th>'
                     '<th class="num">Score</th><th class="num">N Events</th>'
                     '<th class="num">SR 5d</th><th class="num">SR 10d</th><th class="num">SR 20d</th>'
                     '<th class="num">Avg 5d</th><th class="num">Avg 10d</th><th class="num">Avg 20d</th>'
                     '<th class="num">MDD 10d</th>'
                     '</tr></thead><tbody>')
        for i, r in enumerate(wdata["rankings"]):
            sc = r["score"]
            is_sentinel = sc <= _SENTINEL + 1
            bg = _score_bg(sc)
            sr5c  = _sr_color(r.get("success_rate_5d"))
            sr10c = _sr_color(r.get("success_rate_10d"))
            sr20c = _sr_color(r.get("success_rate_20d"))
            a5c   = _ret_color(r.get("avg_ret_5d"))
            a10c  = _ret_color(r.get("avg_ret_10d"))
            a20c  = _ret_color(r.get("avg_ret_20d"))
            if is_sentinel:
                insuf = "<td class='num' style='color:#3a5570' colspan='8'>insufficient data (n≤2)</td>"
                parts.append(
                    f"<tr style='opacity:0.4'>"
                    f"<td class='rank-no'>—</td>"
                    f"<td style='color:#3a5570'>{_esc(r['ma'])}</td>"
                    f"<td class='num' style='color:#3a5570'>—</td>"
                    f"<td class='num' style='color:#3a5570'>{r.get('n_events_10d','—')}</td>"
                    f"{insuf}</tr>"
                )
            else:
                parts.append(
                    f"<tr>"
                    f"<td class='rank-no'>{i+1}</td>"
                    f"<td><b>{_esc(r['ma'])}</b></td>"
                    f"<td class='num'><span class='hm' style='background:{bg}'>{sc:.1f}</span></td>"
                    f"<td class='num' style='color:#5a7090'>{r.get('n_events_10d','—')}</td>"
                    f"<td class='num' style='color:{sr5c}'>{r.get('success_rate_5d','—')}%</td>"
                    f"<td class='num' style='color:{sr10c}'><b>{r.get('success_rate_10d','—')}%</b></td>"
                    f"<td class='num' style='color:{sr20c}'>{r.get('success_rate_20d','—')}%</td>"
                    f"<td class='num' style='color:{a5c}'>{r.get('avg_ret_5d',0):+.2f}%</td>"
                    f"<td class='num' style='color:{a10c}'><b>{r.get('avg_ret_10d',0):+.2f}%</b></td>"
                    f"<td class='num' style='color:{a20c}'>{r.get('avg_ret_20d',0):+.2f}%</td>"
                    f"<td class='num' style='color:#e67e22'>{r.get('avg_mdd_10d',0):+.2f}%</td>"
                    f"</tr>"
                )
        parts.append("</tbody></table></div></details>")

    return "\n".join(parts)


def stocks_section(stocks: dict) -> str:
    cw_raw = stocks.get("cross_window_avg_score", {})
    cw = sorted(cw_raw.items(), key=lambda x: -x[1])
    psb = stocks.get("per_symbol_best_2y", {})
    windows_order = list(stocks.get("windows", {}).keys())  # 10y,5y,2y

    parts = []

    # Insight
    top3 = ", ".join(f"<b>{ma}</b> ({sc:.1f})" for ma, sc in cw[:3])
    n_sym = len(psb)
    parts.append(f'<div class="insight">Universe: <b>{n_sym} liquid IA-favourite stocks</b> (IA Tier 2-3, 2026-05-27 panel scan). '
                 f'Cross-window leaders: {top3}. Per-symbol best MA varies significantly — check individual cards below.</div>')

    # Top 5 hero cards
    parts.append(top_cards(cw, 5))

    # Per-symbol cards (sorted by score desc)
    sorted_syms = sorted(psb.items(), key=lambda x: -(x[1].get("score") or 0))

    parts.append('<h3>Per-Symbol Best MA Profile (2-Year Window)</h3>')
    parts.append('<div class="sym-grid">')
    for sym, d in sorted_syms:
        best_ma  = d.get("best_ma", "—")
        score    = d.get("score")
        sr_10d   = d.get("sr_10d")
        avg_10d  = d.get("avg_10d")
        n_events = d.get("n_events", "—")

        sr_color  = _sr_color(sr_10d)
        ret_color = _ret_color(avg_10d)
        sc_bg     = _score_bg(score, 20, 55)

        sr_bar_w = f"{min(100, int(sr_10d or 0))}px"
        sr_bar_c = sr_color

        parts.append(f'''<div class="sym-card">
  <div class="sym-hdr">
    <span class="sym-name">{_esc(sym)}</span>
    <span class="sym-best">{_esc(best_ma)}</span>
  </div>
  <div class="sym-row">
    <span class="sym-lbl">Score (2y)</span>
    <span class="sym-val"><span class="hm" style="background:{sc_bg};padding:2px 8px">{score:.1f}</span></span>
  </div>
  <div class="sym-row">
    <span class="sym-lbl">Obedience SR (10d)</span>
    <span class="sym-val" style="color:{sr_color}">{sr_10d:.0f}%
      <span class="sr-bar-bg"><span class="sr-bar" style="width:{sr_bar_w};background:{sr_bar_c}"></span></span>
    </span>
  </div>
  <div class="sym-row">
    <span class="sym-lbl">Avg Bounce (10d)</span>
    <span class="sym-val" style="color:{ret_color}">{avg_10d:+.2f}%</span>
  </div>
  <div class="sym-row">
    <span class="sym-lbl">Touch Events (2y)</span>
    <span class="sym-val" style="color:#8b949e">{n_events}</span>
  </div>
</div>''')
    parts.append("</div>")  # sym-grid

    # Summary table (sortable by eye)
    parts.append('<h3>Summary Table — All Symbols</h3>')
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th class="rank-no">#</th><th>Symbol</th><th>Best MA (2y)</th>'
                 '<th class="num">Score</th><th class="num">SR (10d)</th>'
                 '<th class="num">Avg Ret (10d)</th><th class="num">N Events</th>'
                 '</tr></thead><tbody>')
    for i, (sym, d) in enumerate(sorted_syms):
        best_ma  = d.get("best_ma","—")
        score    = d.get("score", 0)
        sr_10d   = d.get("sr_10d")
        avg_10d  = d.get("avg_10d")
        n_events = d.get("n_events","—")
        bg = _score_bg(score, 20, 55)
        parts.append(
            f"<tr>"
            f"<td class='rank-no'>{i+1}</td>"
            f"<td><b>{_esc(sym)}</b></td>"
            f"<td style='color:#58a6ff;font-weight:700'>{_esc(best_ma)}</td>"
            f"<td class='num'><span class='hm' style='background:{bg}'>{score:.1f}</span></td>"
            f"<td class='num' style='color:{_sr_color(sr_10d)}'><b>{sr_10d:.0f}%</b></td>"
            f"<td class='num' style='color:{_ret_color(avg_10d)}'>{avg_10d:+.2f}%</td>"
            f"<td class='num' style='color:#5a7090'>{n_events}</td>"
            f"</tr>"
        )
    parts.append("</tbody></table></div>")

    # Cross-window MA ranking for stocks
    parts.append('<h3>Cross-Window MA Ranking — Stock Universe</h3>')
    parts.append('<p class="footnote">Aggregated across 10y / 5y / 2y windows, 19-symbol liquid IA-fav universe.</p>')
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th class="rank-no">#</th><th>MA</th><th class="num">Avg Score</th>'
                 + "".join(f"<th class='num'>{w}</th>" for w in windows_order)
                 + '</tr></thead><tbody>')
    for i, (ma, avg_sc) in enumerate(cw):
        bg = _score_bg(avg_sc, 10, 40)
        win_cells = ""
        for wk in windows_order:
            wdata = stocks["windows"].get(wk, {})
            sm = {r["ma"]: r["score"] for r in wdata.get("rankings", [])}
            sc = sm.get(ma)
            if sc is not None:
                win_cells += f"<td class='num' style='color:{_sr_color(sc-10)}'>{sc:.1f}</td>"
            else:
                win_cells += "<td class='num' style='color:#3a5570'>—</td>"
        parts.append(
            f"<tr><td class='rank-no'>{i+1}</td>"
            f"<td><b>{_esc(ma)}</b></td>"
            f"<td class='num'><span class='hm' style='background:{bg}'>{avg_sc:.2f}</span></td>"
            + win_cells + "</tr>"
        )
    parts.append("</tbody></table></div>")

    return "\n".join(parts)


# ── Liquid universe section ───────────────────────────────────────────────────

def _bucket_label(b: str) -> str:
    return {"short_5_20": "Short (5–20)", "medium_50_100": "Medium (50–100)", "long_150_200": "Long (150–200)"}.get(b, b)


def liquid_section(liquid: dict) -> str:
    cw_raw  = liquid.get("cross_window_avg_score", {})
    cw      = sorted(cw_raw.items(), key=lambda x: -x[1])
    psb     = liquid.get("per_symbol_best_2y", {})
    n_sym   = liquid.get("n_symbols", len(liquid.get("universe", [])))
    windows_order = ["10y", "5y", "2y", "1y", "6m", "3m"]
    all_mas = [ma for ma, _ in cw]

    cw_type   = liquid.get("cross_window_by_type", {})
    cw_bucket = liquid.get("cross_window_by_bucket", {})
    cw_sector = liquid.get("cross_window_by_sector", {})

    parts = []

    # Insight
    top3 = ", ".join(f"<b>{ma}</b> ({sc:.1f})" for ma, sc in cw[:3])
    sma_sc = cw_type.get("SMA", 0)
    ema_sc = cw_type.get("EMA", 0)
    winner = "EMA" if ema_sc > sma_sc else "SMA"
    n_ex = liquid.get("n_symbols_ex_vin", n_sym)
    vin_excl = ", ".join(liquid.get("vin_excluded", []))
    parts.append(
        f'<div class="insight">Universe: <b>{n_sym} liquid stocks</b> (ADV50 ≥ 2B VND, 20 sectors, 6 windows). '
        f'Rankings = <b>ex-VIN</b> ({n_ex} symbols; {vin_excl} excluded per SSOT). '
        f'Cross-window leaders: {top3}. '
        f'Type edge: <b>{winner}</b> ({max(sma_sc,ema_sc):.2f} vs {min(sma_sc,ema_sc):.2f}). '
        f'<span style="color:#ffc107">Research scan — survivorship-biased ADV filter. Not a tradable backtest.</span></div>'
    )

    # Hero cards
    parts.append(top_cards(cw, 5))

    # ── 1. Cross-window heatmap (same as VNINDEX tab) ─────────────────────
    parts.append(f'<h3>Score Heatmap — by Window &amp; MA ({n_sym} liquid stocks)</h3>')
    parts.append('<p class="footnote">Score = 0.4×SR% + 0.3×avg_ret_10d + 0.2×pct_gt2_10d − 0.1×avgMDD_10d. '
                 'Events aggregated across all symbols per window.</p>')
    parts.append('<div class="tbl-wrap"><table>')
    th_mas = "".join(f"<th class='num'>{_esc(ma)}</th>" for ma in all_mas)
    parts.append(f"<thead><tr><th>Window</th><th>Period</th>{th_mas}</tr></thead><tbody>")
    for wk in windows_order:
        wdata = liquid["windows"].get(wk)
        if not wdata:
            continue
        score_map = {r["ma"]: r["score"] for r in wdata.get("rankings", [])}
        period = f"{wdata.get('window_start','')[:7]} → {wdata.get('window_end','')[:7]}"
        cells = ""
        for ma in all_mas:
            sc = score_map.get(ma)
            if sc is None or sc <= -998:
                cells += "<td class='hm' style='background:#0d1117;color:#3a5570'>—</td>"
            else:
                bg = _score_bg(sc)
                cells += f"<td class='hm' style='background:{bg}'>{sc:.1f}</td>"
        parts.append(f"<tr><td><span class='win-pill'>{wk}</span></td>"
                     f"<td style='color:#5a7090;font-size:0.75rem'>{period}</td>{cells}</tr>")
    parts.append("</tbody></table></div>")

    # ── 2. Full MA ranking table (cross-window) ────────────────────────────
    parts.append('<h3>Full MA Ranking — Cross-Window Average</h3>')
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th class="rank-no">#</th><th>MA</th><th class="num">Avg Score</th>'
                 + "".join(f"<th class='num'>{w}</th>" for w in windows_order)
                 + '</tr></thead><tbody>')
    for i, (ma, avg_sc) in enumerate(cw):
        bg = _score_bg(avg_sc)
        win_cells = ""
        for wk in windows_order:
            wdata = liquid["windows"].get(wk, {})
            sm = {r["ma"]: r["score"] for r in wdata.get("rankings", [])}
            sc = sm.get(ma)
            if sc is not None and sc > -998:
                win_cells += f"<td class='num' style='color:#8ab4f8'>{sc:.1f}</td>"
            else:
                win_cells += "<td class='num' style='color:#3a5570'>—</td>"
        parts.append(
            f"<tr><td class='rank-no'>{i+1}</td>"
            f"<td><b>{_esc(ma)}</b></td>"
            f"<td class='num'><span class='hm' style='background:{bg}'>{avg_sc:.2f}</span></td>"
            + win_cells + "</tr>"
        )
    parts.append("</tbody></table></div>")

    # ── 3. SMA vs EMA comparison table ────────────────────────────────────
    parts.append('<h3>SMA vs EMA — by Window</h3>')
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th>Window</th><th class="num">SMA Score</th>'
                 '<th class="num">EMA Score</th><th>Edge</th>'
                 '</tr></thead><tbody>')
    for wk in windows_order:
        wdata = liquid["windows"].get(wk)
        if not wdata:
            continue
        by_type = wdata.get("by_type", {})
        sma_s = by_type.get("SMA", {}).get("score", None)
        ema_s = by_type.get("EMA", {}).get("score", None)
        if sma_s is None and ema_s is None:
            continue
        sma_str = f"{sma_s:.2f}" if sma_s is not None else "—"
        ema_str = f"{ema_s:.2f}" if ema_s is not None else "—"
        if sma_s is not None and ema_s is not None:
            edge = "<b style='color:#4caf50'>EMA</b>" if ema_s > sma_s else "<b style='color:#8ab4f8'>SMA</b>"
            diff = abs(ema_s - sma_s)
            edge += f" <span style='color:#5a7090;font-size:0.75rem'>(+{diff:.2f})</span>"
        else:
            edge = "—"
        parts.append(
            f"<tr><td><span class='win-pill'>{wk}</span></td>"
            f"<td class='num' style='color:#8ab4f8'>{sma_str}</td>"
            f"<td class='num' style='color:#4caf50'>{ema_str}</td>"
            f"<td>{edge}</td></tr>"
        )
    # Cross-window row
    sma_cw = cw_type.get("SMA")
    ema_cw = cw_type.get("EMA")
    if sma_cw is not None and ema_cw is not None:
        edge_cw = ("<b style='color:#4caf50'>EMA</b>" if ema_cw > sma_cw else "<b style='color:#8ab4f8'>SMA</b>") + \
                  f" <span style='color:#5a7090;font-size:0.75rem'>(+{abs(ema_cw-sma_cw):.2f})</span>"
        parts.append(
            f"<tr style='border-top:2px solid #30404d'>"
            f"<td><span class='win-pill' style='background:#0f2830'>All</span></td>"
            f"<td class='num' style='color:#8ab4f8'><b>{sma_cw:.2f}</b></td>"
            f"<td class='num' style='color:#4caf50'><b>{ema_cw:.2f}</b></td>"
            f"<td>{edge_cw}</td></tr>"
        )
    parts.append("</tbody></table></div>")

    # ── 4. Period bucket comparison table ─────────────────────────────────
    parts.append('<h3>MA Period Bucket — by Window</h3>')
    buckets = ["short_5_20", "medium_50_100", "long_150_200"]
    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th>Window</th>'
                 + "".join(f"<th class='num'>{_bucket_label(b)}</th>" for b in buckets)
                 + '<th>Best Bucket</th></tr></thead><tbody>')
    for wk in windows_order:
        wdata = liquid["windows"].get(wk)
        if not wdata:
            continue
        bb = wdata.get("by_period_bucket", {})
        scores = {b: bb.get(b, {}).get("score") for b in buckets}
        valid = {b: s for b, s in scores.items() if s is not None and s > -998}
        best_b = max(valid, key=valid.get) if valid else None
        cells = ""
        for b in buckets:
            s = scores.get(b)
            if s is None or s <= -998:
                cells += "<td class='num' style='color:#3a5570'>—</td>"
            else:
                is_best = (b == best_b)
                color = "#ffc107" if is_best else "#8ab4f8"
                cells += f"<td class='num' style='color:{color}'>{'<b>' if is_best else ''}{s:.2f}{'</b>' if is_best else ''}</td>"
        best_label = _bucket_label(best_b) if best_b else "—"
        parts.append(f"<tr><td><span class='win-pill'>{wk}</span></td>{cells}"
                     f"<td style='color:#ffc107;font-weight:700;font-size:0.8rem'>{_esc(best_label)}</td></tr>")
    # Cross-window row
    if cw_bucket:
        best_b_cw = max(cw_bucket, key=cw_bucket.get) if cw_bucket else None
        cells_cw = ""
        for b in buckets:
            s = cw_bucket.get(b)
            is_best = (b == best_b_cw)
            color = "#ffc107" if is_best else "#8ab4f8"
            cells_cw += f"<td class='num' style='color:{color}'>{'<b>' if is_best else ''}{s:.2f}{'</b>' if is_best else ''}</td>" if s else "<td class='num' style='color:#3a5570'>—</td>"
        best_b_cw_label = _bucket_label(best_b_cw) if best_b_cw else "—"
        parts.append(
            f"<tr style='border-top:2px solid #30404d'>"
            f"<td><span class='win-pill' style='background:#0f2830'>All</span></td>"
            f"{cells_cw}"
            f"<td style='color:#ffc107;font-weight:700;font-size:0.8rem'>{_esc(best_b_cw_label)}</td></tr>"
        )
    parts.append("</tbody></table></div>")

    # ── 5. Sector: compact window table + expandable heatmap ─────────────
    import re as _re

    def _sec_slug(s: str) -> str:
        return _re.sub(r'[^a-zA-Z0-9]', '_', s)

    # Build per-sector per-window full MA ranking
    sec_win_data: dict[str, dict[str, list]] = {}
    for wk in windows_order:
        wdata = liquid["windows"].get(wk, {})
        for sec, sdata in wdata.get("by_sector", {}).items():
            if sec not in sec_win_data:
                sec_win_data[sec] = {}
            ranking = sdata.get("ma_ranking", [])
            if ranking:
                sec_win_data[sec][wk] = ranking

    # Sort sectors by cross-window best score
    sec_order = sorted(
        cw_sector.keys(),
        key=lambda s: -(cw_sector[s].get("best_score", -999))
    )

    WIN_LABELS_SEC = ["10y", "5y", "2y", "1y", "6m", "3m"]
    win_dates_sec  = {wk: f"{liquid['windows'][wk]['window_start'][:7]} → {liquid['windows'][wk]['window_end'][:7]}"
                      if wk in liquid.get("windows", {}) else "" for wk in WIN_LABELS_SEC}

    parts.append('<h3>Sector Best MA — Cross-Window'
                 '  <span style="color:#5a7090;font-size:0.78rem;font-weight:400">'
                 '▶ click row to expand heatmap</span></h3>')
    parts.append('<p class="footnote">Top-2 MAs per sector by window. Click row to expand full MA heatmap. Score = composite_score(10d).</p>')

    parts.append("""<script>
function toggleSec(slug) {
  var row = document.getElementById('hm-sec-' + slug);
  var icon = document.getElementById('ic-sec-' + slug);
  if (row.style.display === 'none') {
    row.style.display = 'table-row';
    icon.textContent = '▼';
  } else {
    row.style.display = 'none';
    icon.textContent = '▶';
  }
}
</script>""")

    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th style="width:20px"></th>'
                 '<th class="rank-no">#</th><th>Sector</th><th class="num">N Sym</th>'
                 + "".join(f"<th class='num'>{w}</th>" for w in WIN_LABELS_SEC)
                 + '</tr></thead><tbody>')

    for i, sec in enumerate(sec_order):
        slug  = _sec_slug(sec)
        sec_d = cw_sector.get(sec, {})
        n_sym = liquid["windows"].get("2y", {}).get("by_sector", {}).get(sec, {}).get("n_symbols", "—")
        wins  = sec_win_data.get(sec, {})

        # Window cells — top-2 MA chips
        win_cells = ""
        for wk in WIN_LABELS_SEC:
            cands = wins.get(wk, [])
            if not cands:
                win_cells += "<td class='num' style='color:#3a5570'>—</td>"
                continue
            cell_html = "<td class='num' style='padding:3px 6px;vertical-align:top'>"
            for m in cands[:2]:
                sc  = m.get("score", 0)
                ma  = m.get("ma", "")
                bg  = _score_bg(sc, 10, 45)
                cell_html += (
                    f"<div style='margin-bottom:2px'>"
                    f"<span class='hm' style='background:{bg};font-size:0.68rem;padding:1px 4px'>{sc:.1f}</span>"
                    f"<span style='color:#8b9eb8;font-size:0.68rem;margin-left:3px'>{_esc(ma)}</span>"
                    f"</div>"
                )
            cell_html += "</td>"
            win_cells += cell_html

        parts.append(
            f"<tr style='cursor:pointer' onclick=\"toggleSec('{slug}')\">"
            f"<td style='color:#5a7090;font-size:0.8rem;text-align:center'>"
            f"<span id='ic-sec-{slug}'>▶</span></td>"
            f"<td class='rank-no'>{i+1}</td>"
            f"<td style='font-size:0.8rem'>{_esc(sec)}</td>"
            f"<td class='num' style='color:#5a7090;font-size:0.78rem'>{n_sym}</td>"
            + win_cells + "</tr>"
        )

        # Heatmap detail row (hidden)
        all_ma_scores = sec_d.get("all_ma_scores", {})
        if all_ma_scores:
            ma_cols = sorted(all_ma_scores, key=lambda x: -all_ma_scores[x])
        else:
            ma_agg: dict[str, list] = {}
            for cands in wins.values():
                for m in cands:
                    ma_agg.setdefault(m["ma"], []).append(m["score"])
            ma_cols = sorted(ma_agg, key=lambda x: -sum(ma_agg[x]) / len(ma_agg[x]))

        win_ma_lookup: dict[str, dict] = {wk: {m["ma"]: m for m in cands} for wk, cands in wins.items()}

        hm_html = (
            f"<tr id='hm-sec-{slug}' style='display:none;background:#0d1117'>"
            f"<td colspan='{4 + len(WIN_LABELS_SEC)}' style='padding:8px 12px'>"
            f"<div style='font-size:0.72rem;color:#5a7090;margin-bottom:6px'>"
            f"Score heatmap — {_esc(sec)} · {n_sym} symbol(s) · "
            f"Score = 0.4×SR% + 0.3×avg_ret_10d + 0.2×pct_gt2_10d − 0.1×avgMDD_10d</div>"
            f"<table style='border-collapse:collapse;font-size:0.72rem'>"
            f"<thead><tr>"
            f"<th style='padding:3px 8px;color:#5a7090;text-align:left'>WINDOW</th>"
            f"<th style='padding:3px 8px;color:#5a7090;text-align:left'>PERIOD</th>"
        )
        for ma in ma_cols:
            hm_html += f"<th style='padding:3px 6px;color:#8b949e;min-width:52px'>{_esc(ma)}</th>"
        hm_html += "</tr></thead><tbody>"

        for wk in WIN_LABELS_SEC:
            wma = win_ma_lookup.get(wk, {})
            hm_html += (
                f"<tr>"
                f"<td style='padding:3px 8px;color:#58a6ff;font-weight:700'>{wk}</td>"
                f"<td style='padding:3px 8px;color:#5a7090'>{win_dates_sec.get(wk,'')}</td>"
            )
            for ma in ma_cols:
                entry = wma.get(ma)
                if entry:
                    sc  = entry["score"]
                    sr  = entry.get("sr_10d", 0)
                    avg = entry.get("avg_10d", 0)
                    bg  = _score_bg(sc, 10, 45)
                    hm_html += (
                        f"<td style='padding:3px 6px;text-align:center'>"
                        f"<span class='hm' style='background:{bg};display:block;font-size:0.72rem'>"
                        f"<b>{sc:.1f}</b></span>"
                        f"<span style='color:#5a7090;font-size:0.62rem'>{sr:.0f}% / {avg:+.1f}%</span>"
                        f"</td>"
                    )
                else:
                    hm_html += "<td style='padding:3px 6px;color:#2a3a4a;text-align:center'>—</td>"
            hm_html += "</tr>"

        hm_html += "</tbody></table></td></tr>"
        parts.append(hm_html)

    parts.append("</tbody></table></div>")

    # ── 6. Per-symbol: compact window table + expandable heatmap ─────────────
    sym_windows = liquid.get("per_symbol_windows", {})
    WIN_LABELS  = ["10y", "5y", "2y", "1y", "6m", "3m"]

    # Sort by best score in 2y window (fall back to 1y)
    def _sym_sort_key(item):
        wins = item[1].get("windows", {})
        top = wins.get("2y", wins.get("1y", [{}]))
        return -(top[0].get("score", 0) if top else 0)

    sorted_syms = sorted(sym_windows.items(), key=_sym_sort_key)

    parts.append('<h3>Per-Symbol — Top 2 MAs per Window  '
                 '<span style="color:#5a7090;font-size:0.78rem;font-weight:400">'
                 '▶ click row to expand heatmap</span></h3>')

    # JS toggle
    parts.append("""<script>
function toggleHm(sym) {
  var row = document.getElementById('hm-' + sym);
  var icon = document.getElementById('ic-' + sym);
  if (row.style.display === 'none') {
    row.style.display = 'table-row';
    icon.textContent = '▼';
  } else {
    row.style.display = 'none';
    icon.textContent = '▶';
  }
}
</script>""")

    parts.append('<div class="tbl-wrap"><table><thead><tr>'
                 '<th style="width:20px"></th>'
                 '<th class="rank-no">#</th><th>Symbol</th><th>Sector (L3)</th>'
                 + "".join(f"<th class='num'>{w}</th>" for w in WIN_LABELS)
                 + '</tr></thead><tbody>')

    for i, (sym, d) in enumerate(sorted_syms):
        sec_lbl = d.get("sector_l3", "—")
        wins    = d.get("windows", {})

        # Build window cells (top-2 MAs per window)
        win_cells = ""
        for wk in WIN_LABELS:
            cands = wins.get(wk, [])
            if not cands:
                win_cells += "<td class='num' style='color:#3a5570'>—</td>"
                continue
            cell_html = "<td class='num' style='padding:3px 6px;vertical-align:top'>"
            for m in cands[:2]:
                sc   = m.get("score", 0)
                ma   = m.get("ma", "")
                bg   = _score_bg(sc, 15, 55)
                cell_html += (
                    f"<div style='margin-bottom:2px'>"
                    f"<span class='hm' style='background:{bg};font-size:0.68rem;padding:1px 4px'>{sc:.1f}</span>"
                    f"<span style='color:#8b9eb8;font-size:0.68rem;margin-left:3px'>{_esc(ma)}</span>"
                    f"</div>"
                )
            cell_html += "</td>"
            win_cells += cell_html

        parts.append(
            f"<tr style='cursor:pointer' onclick=\"toggleHm('{sym}')\">"
            f"<td style='color:#5a7090;font-size:0.8rem;text-align:center'>"
            f"<span id='ic-{sym}'>▶</span></td>"
            f"<td class='rank-no'>{i+1}</td>"
            f"<td><b>{_esc(sym)}</b></td>"
            f"<td style='color:#8b949e;font-size:0.75rem'>{_esc(sec_lbl)}</td>"
            + win_cells + "</tr>"
        )

        # Heatmap detail row (hidden by default)
        # Collect all unique MAs that appear in any window, ordered by cross-window avg score
        ma_scores_cross: dict[str, list] = {}
        for wk, cands in wins.items():
            for m in cands:
                ma_scores_cross.setdefault(m["ma"], []).append(m["score"])
        ma_cols = sorted(ma_scores_cross, key=lambda x: -sum(ma_scores_cross[x]) / len(ma_scores_cross[x]))

        hm_html = (
            f"<tr id='hm-{sym}' style='display:none;background:#0d1117'>"
            f"<td colspan='{4 + len(WIN_LABELS)}' style='padding:8px 12px'>"
            f"<div style='font-size:0.72rem;color:#5a7090;margin-bottom:6px'>"
            f"Score heatmap — {_esc(sym)} · Score = 0.4×SR% + 0.3×avg_ret_10d + 0.2×pct_gt2_10d − 0.1×avgMDD_10d</div>"
            f"<table style='border-collapse:collapse;font-size:0.72rem'>"
            f"<thead><tr>"
            f"<th style='padding:3px 8px;color:#5a7090;text-align:left'>WINDOW</th>"
            f"<th style='padding:3px 8px;color:#5a7090;text-align:left'>PERIOD</th>"
        )
        for ma in ma_cols:
            hm_html += f"<th style='padding:3px 6px;color:#8b949e;min-width:52px'>{_esc(ma)}</th>"
        hm_html += "</tr></thead><tbody>"

        # Build a lookup: window -> ma -> entry
        win_ma: dict[str, dict] = {}
        for wk, cands in wins.items():
            win_ma[wk] = {m["ma"]: m for m in cands}

        win_period = {wdata.get("window_start", "")[:7]: wk for wk, wdata in liquid.get("windows", {}).items()}
        win_dates  = {wk: f"{liquid['windows'][wk]['window_start'][:7]} → {liquid['windows'][wk]['window_end'][:7]}"
                      if wk in liquid.get("windows", {}) else "" for wk in WIN_LABELS}

        for wk in WIN_LABELS:
            wma = win_ma.get(wk, {})
            hm_html += (
                f"<tr>"
                f"<td style='padding:3px 8px;color:#58a6ff;font-weight:700'>{wk}</td>"
                f"<td style='padding:3px 8px;color:#5a7090'>{win_dates.get(wk,'')}</td>"
            )
            for ma in ma_cols:
                entry = wma.get(ma)
                if entry:
                    sc  = entry["score"]
                    sr  = entry.get("sr_10d", 0)
                    avg = entry.get("avg_10d", 0)
                    bg  = _score_bg(sc, 15, 55)
                    hm_html += (
                        f"<td style='padding:3px 6px;text-align:center'>"
                        f"<span class='hm' style='background:{bg};display:block;font-size:0.72rem'>"
                        f"<b>{sc:.1f}</b></span>"
                        f"<span style='color:#5a7090;font-size:0.62rem'>{sr:.0f}% / {avg:+.1f}%</span>"
                        f"</td>"
                    )
                else:
                    hm_html += "<td style='padding:3px 6px;color:#2a3a4a;text-align:center'>—</td>"
            hm_html += "</tr>"

        hm_html += "</tbody></table></td></tr>"
        parts.append(hm_html)

    parts.append("</tbody></table></div>")

    # ── 7. Per-window detail tables (collapsible) ──────────────────────────
    parts.append('<h3>Per-Window Detail Tables</h3>')
    for wk in windows_order:
        wdata = liquid["windows"].get(wk)
        if not wdata:
            continue
        period = f"{wdata.get('window_start','')[:10]} → {wdata.get('window_end','')[:10]}"
        parts.append(
            f'<details style="margin-bottom:10px">'
            f'<summary style="cursor:pointer;color:#58a6ff;font-weight:700;padding:6px 0">'
            f'Window: <span class="win-pill">{wk}</span> &nbsp; '
            f'<span style="color:#5a7090;font-size:0.78rem;font-weight:400">{period}</span></summary>'
        )
        parts.append('<div class="tbl-wrap" style="margin-top:8px"><table><thead><tr>'
                     '<th class="rank-no">#</th><th>MA</th>'
                     '<th class="num">Score</th><th class="num">N Events</th><th class="num">N Sym</th>'
                     '<th class="num">SR 5d</th><th class="num">SR 10d</th><th class="num">SR 20d</th>'
                     '<th class="num">Avg 5d</th><th class="num">Avg 10d</th><th class="num">Avg 20d</th>'
                     '<th class="num">MDD 10d</th>'
                     '</tr></thead><tbody>')
        for i, r in enumerate(wdata.get("rankings", [])):
            sc = r.get("score", -999)
            if sc <= -998:
                parts.append(
                    f"<tr style='opacity:0.4'><td class='rank-no'>—</td>"
                    f"<td style='color:#3a5570'>{_esc(r['ma'])}</td>"
                    f"<td class='num' style='color:#3a5570'>—</td>"
                    f"<td class='num' style='color:#3a5570'>{r.get('n_10d','—')}</td>"
                    f"<td colspan='8' class='num' style='color:#3a5570'>insufficient data</td></tr>"
                )
            else:
                bg    = _score_bg(sc)
                sr5c  = _sr_color(r.get("sr_5d"))
                sr10c = _sr_color(r.get("sr_10d"))
                sr20c = _sr_color(r.get("sr_20d"))
                a5c   = _ret_color(r.get("avg_5d"))
                a10c  = _ret_color(r.get("avg_10d"))
                a20c  = _ret_color(r.get("avg_20d"))
                parts.append(
                    f"<tr><td class='rank-no'>{i+1}</td>"
                    f"<td><b>{_esc(r['ma'])}</b></td>"
                    f"<td class='num'><span class='hm' style='background:{bg}'>{sc:.1f}</span></td>"
                    f"<td class='num' style='color:#5a7090'>{r.get('n_10d','—')}</td>"
                    f"<td class='num' style='color:#5a7090'>{r.get('n_symbols','—')}</td>"
                    f"<td class='num' style='color:{sr5c}'>{r.get('sr_5d','—')}%</td>"
                    f"<td class='num' style='color:{sr10c}'><b>{r.get('sr_10d','—')}%</b></td>"
                    f"<td class='num' style='color:{sr20c}'>{r.get('sr_20d','—')}%</td>"
                    f"<td class='num' style='color:{a5c}'>{r.get('avg_5d',0):+.2f}%</td>"
                    f"<td class='num' style='color:{a10c}'><b>{r.get('avg_10d',0):+.2f}%</b></td>"
                    f"<td class='num' style='color:{a20c}'>{r.get('avg_20d',0):+.2f}%</td>"
                    f"<td class='num' style='color:#e67e22'>{r.get('mdd_10d',0):+.2f}%</td>"
                    f"</tr>"
                )
        parts.append("</tbody></table></div></details>")

    return "\n".join(parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    study  = json.loads(STUDY_PATH.read_text(encoding="utf-8"))
    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    liquid = json.loads(LIQUID_PATH.read_text(encoding="utf-8")) if LIQUID_PATH.exists() else None

    asof_study  = study.get("asof_date", "—")
    asof_stocks = stocks.get("asof_date", "—")
    asof_liquid = liquid.get("asof_date", "—") if liquid else "—"
    universe    = stocks.get("universe", {})
    uni_desc    = universe.get("description", "") if isinstance(universe, dict) else str(universe)

    # Symbol count for IA tab label (from per_symbol_best_2y keys)
    n_ia_sym = len(stocks.get("per_symbol_best_2y", stocks.get("universe", [])))

    # Tabs and panes — conditionally add liquid tab
    n_liq = liquid.get("n_symbols", 0) if liquid else 0
    tab_liquid  = f'<div class="tab" onclick="show(\'liquid\',this)">{n_liq} Liquid Stocks</div>' if liquid else ""
    pane_liquid = ""
    if liquid:
        n_sym = liquid.get("n_symbols", "—")
        pane_liquid = f"""
<!-- LIQUID PANE -->
<div id="pane-liquid" class="pane">
  <div class="section-hdr">
    <h2>{n_sym} Liquid Stocks (ADV50 ≥ 2B VND) — MA Reaction Study</h2>
    <span class="ssot-tag">SSOT: ma_reaction_liquid_expanded.json</span>
    <span class="warn-tag">OHLCV max {asof_liquid}</span>
  </div>
  <p class="footnote" style="margin-bottom:14px">
    Universe: ADV50 ≥ 2B VND/day, 20 sectors &nbsp;·&nbsp;
    14 MAs × 6 windows (10y/5y/2y/1y/6m/3m) &nbsp;·&nbsp;
    Score = 0.4×SR% + 0.3×avg_ret_10d + 0.2×pct_gt2_10d − 0.1×avgMDD_10d
  </p>
  {liquid_section(liquid)}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E&amp;MA Research — {TODAY}</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <div>
    <h1>E&amp;MA Research</h1>
    <div style="font-size:0.78rem;color:#8b949e;margin-top:2px">
      VNINDEX study: <b>{asof_study}</b> &nbsp;·&nbsp;
      Stocks study: <b>{asof_stocks}</b> &nbsp;·&nbsp;
      {"Liquid study: <b>" + asof_liquid + "</b> &nbsp;·&nbsp;" if liquid else ""}
      Generated: <b>{TODAY}</b>
    </div>
  </div>
  <span class="badge">RESEARCH ONLY</span>
</div>

<div class="container">

<div class="tabs">
  <div class="tab active" onclick="show('vnindex',this)">VNINDEX (10y)</div>
  <div class="tab" onclick="show('stocks',this)">{n_ia_sym} IA-Fav Stocks</div>
  {tab_liquid}
</div>

<!-- VNINDEX PANE -->
<div id="pane-vnindex" class="pane active">
  <div class="section-hdr">
    <h2>VNINDEX — MA Reaction Study</h2>
    <span class="ssot-tag">SSOT: ma_reaction_study.json</span>
  </div>
  <p class="footnote" style="margin-bottom:14px">
    Source: FireAnt VNINDEX OHLCV 2012–2026 (3,586 bars) &nbsp;·&nbsp;
    Method: touch events within ±1.5% band from above, forward return 5/10/20d &nbsp;·&nbsp;
    14 MAs × 6 time windows
  </p>
  {vnindex_section(study)}
</div>

<!-- STOCKS PANE -->
<div id="pane-stocks" class="pane">
  <div class="section-hdr">
    <h2>{n_ia_sym} Liquid IA-Favourite Stocks — MA Reaction Study</h2>
    <span class="ssot-tag">SSOT: ma_reaction_stocks.json</span>
    <span class="warn-tag">OHLCV max 2026-05-25</span>
  </div>
  <p class="footnote" style="margin-bottom:14px">
    Universe: {_esc(uni_desc)} &nbsp;·&nbsp;
    14 MAs × up to 3 windows (10y/5y/2y, subject to listing history)
  </p>
  {stocks_section(stocks)}
</div>

{pane_liquid}

</div><!-- container -->

<script>
function show(id, el) {{
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('pane-' + id).classList.add('active');
  el.classList.add('active');
}}
</script>
</body>
</html>"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Written: {OUT_PATH}  ({OUT_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
