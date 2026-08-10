#!/usr/bin/env python
"""One-shot / idempotent shell rebuild for La Bàn VN 5-tab layout.

Preserves GATES / FILTERS / INVAL array literals byte-for-byte from the current
tollbooth_tracker_latest.html. Does not invent ontology content.

STAGED BUILD CONTRACT (2026-08-10, ChatGPT REDIRECT — see
Chatgpt/responses/2026-08-10_ReportSuiteOrchestrator_Decision.md). This script NEVER
writes tollbooth_tracker_latest.html directly. It reads the current final file only as
the SOURCE for byte-preserved content (T5 GATES/FILTERS/INVAL, EVENTS, provenance,
signals block) and writes its rebuilt output to a staging file stamped SHELL_ONLY.

This template unconditionally resets tabs T1/T2/T4/T6 (and the LABAN_T3 marker body)
to "pending inject" placeholder text on every run — it does not preserve whatever was
previously injected there. Running this used to overwrite the live report directly,
which is exactly what destroyed tab T6 on 2026-08-09 (a template bug meant the tab
vanished, and nobody knew until a human opened the page). Now the destructive step
only ever touches a throwaway staging file; the live report is only replaced by
`build_vn_structural_signals.py --publish-shell`, which refuses to run unless this
script's SHELL_ONLY output verifiably restored every required tab.

Usage: after this script runs, you MUST run
    python scripts/reporting/build_vn_structural_signals.py --publish-shell
before the shell changes reach tollbooth_tracker_latest.html. This is a manual,
occasional, template-maintenance operation — it is NOT part of the routine daily
report-suite build (which only runs `build_vn_structural_signals.py --inject`,
the safe in-place data refresh that never touches the template).
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATH = REPO / "reports" / "tollbooth_tracker_latest.html"
STAGING_PATH = REPO / "reports" / ".build" / "tollbooth_tracker.shell_only.html"
STATE_SENTINEL = "<!-- LABAN_BUILD_STATE:SHELL_ONLY -->"

PORTFOLIO_CARDS = """  <div class="grid2">
    <div>
      <div class="card"><h3>Cấu trúc danh mục mục tiêu</h3>
        <ul>
          <li><b>Core tollbooth tự tài trợ: 45–55%</b> — GMD, BWE(*) | Conditional: REE (SOTP), CTR, PHP</li>
          <li><b>Tactical EPC/thiết bị/materials: 10–15%</b> — GEE, PC1, TV2 (bỏ qua được nếu không có edge)</li>
          <li><b>Plumbing event FTSE 21/9: 10–15%</b> — SSI/VCI/HCM, có kỳ hạn</li>
          <li><b>Cash: 15–20%</b> — kịch bản D + cơ hội định giá</li>
        </ul>
        <p style="margin-top:6px">(*) BWE điều kiện: vốn rights 1.162 tỷ phải tạo ROIC &gt; WACC</p>
      </div>
      <div class="card"><h3>Hurdle rate</h3><p>Big 4 online 12T: <b>6,8%/năm</b> (07/2026). Mọi vị thế phải hứa hẹn vượt đáng kể risk-free này.</p></div>
    </div>
    <div>
      <div class="card"><h3>Chuỗi value-capture bắt buộc</h3>
        <p>Nút thắt thật → hợp đồng → margin/cash conversion → ROIC &gt; WACC → tài trợ không phá hủy cổ đông → FCF/cổ phiếu tăng → mua ở định giá hợp lý.<br><br><b>Lỗi chí mạng cần tránh:</b> đánh tráo "nhu cầu đầu tư không thể tránh" thành "lợi nhuận cổ đông không thể tránh".</p>
      </div>
      <div class="card"><h3>Quy tắc gate</h3>
        <ul>
          <li>Gate gán theo <b>DỰ ÁN</b>, không theo ticker — không có "đồng hồ quốc gia"</li>
          <li>Chuyển gate cần <b>đồng thời</b>: commitment vật lý + commitment tiền (announcement không tính — bài học FDI đăng ký +61% vs thực hiện +11%)</li>
          <li>Gate chỉnh <b>size &amp; required return</b> — không phát lệnh rotation máy móc</li>
          <li>Không bán compounder tốt chỉ vì nhãn phase đổi</li>
        </ul>
      </div>
    </div>
  </div>
"""


def extract_const_array(html: str, name: str) -> str:
    m = re.search(rf"const {name} = (\[[\s\S]*?\n\];)", html)
    if not m:
        raise SystemExit(f"ERROR: const {name} not found")
    return m.group(1)


def extract_events(html: str) -> str:
    m = re.search(r"const EVENTS = (\[[\s\S]*?\n\];)", html)
    if not m:
        raise SystemExit("ERROR: EVENTS not found")
    return m.group(1)


def extract_signals_block(html: str) -> str:
    begin = "<!-- VN_STRUCTURAL_SIGNALS:BEGIN -->"
    end = "<!-- VN_STRUCTURAL_SIGNALS:END -->"
    if begin not in html or end not in html:
        return f"{begin}\n<div class=\"card\"><p style=\"color:#6b7280\">NOT_RUN — signals fragment pending inject</p></div>\n{end}"
    return begin + html.split(begin, 1)[1].split(end, 1)[0] + end


def sha_array(literal: str) -> str:
    return hashlib.sha256(literal.encode("utf-8")).hexdigest()


def build(html: str) -> str:
    gates = extract_const_array(html, "GATES")
    filters = extract_const_array(html, "FILTERS")
    inval = extract_const_array(html, "INVAL")
    events = extract_events(html)
    signals = extract_signals_block(html)

    print("PRE GATES", sha_array(gates))
    print("PRE FILTERS", sha_array(filters))
    print("PRE INVAL", sha_array(inval))

    # Keep suite provenance / nav from current file if present
    prov = ""
    m = re.search(r'(<div class="suite-provenance">[\s\S]*?</div>\s*<div class="suite-nav">[\s\S]*?</div>)', html)
    if m:
        prov = m.group(1)
        # Update title wording inside provenance lightly
        prov = prov.replace("TOLLBOOTH 10Y TRACKER", "LA BÀN VN — 10Y · 36M")
    else:
        prov = '<div class="suite-provenance"><div class="sp-title">LA BÀN VN</div></div>'

    css_extra = """
.frame-stress { border: 1px solid rgba(244,63,94,.45); background: rgba(244,63,94,.06); border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
.laban-sub { font-size: 11px; color: var(--muted); margin: 0 0 8px; }
details.card summary { list-style: none; }
.card summary { transition: opacity 100ms ease; }
.card summary:hover { opacity: 0.75; }
.card summary::before { content: "\\25B8"; display: inline-block; margin-right: 4px; transition: transform 150ms cubic-bezier(0.34,1.56,0.64,1); }
.card details[open] summary::before { transform: rotate(90deg); }
"""

    # Extract head styles from original up to </style>
    head_m = re.search(r"(<style>[\s\S]*?</style>)", html)
    style = head_m.group(1) if head_m else "<style></style>"
    style = style.replace("</style>", css_extra + "</style>")

    new = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>La Bàn VN — 10Y thesis · 36M scenario lens</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
{style}
</head>
<body>
{STATE_SENTINEL}
<div class="page">
<div class="hdr">
  <div class="hdr-title">La Bàn VN <span style="color:var(--muted);font-weight:400">— 10Y thesis · 36M scenario lens</span></div>
  <div class="hdr-meta">Frame v2.0 · countersign 2026-08-02<br>T5 Tollbooth portfolio byte-preserved</div>
</div>
{prov}
<div class="evbadges" id="badges"></div>

<div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;font-size:10px;color:var(--muted);padding:5px 0 8px;margin-bottom:2px;border-bottom:1px solid var(--border)">
  <span style="color:var(--faint);font-weight:600">CÁCH 6 TAB LIÊN KẾT:</span>
  <span style="background:var(--s1,#171a2c);border:1px solid var(--border);border-radius:9999px;padding:2px 8px">T6 giả định</span>
  <span style="color:var(--faint)">+</span>
  <span style="background:var(--s1,#171a2c);border:1px solid var(--border);border-radius:9999px;padding:2px 8px">T3 tín hiệu</span>
  <span style="color:var(--faint)">+</span>
  <span style="background:var(--s1,#171a2c);border:1px solid var(--border);border-radius:9999px;padding:2px 8px">T4 chính sách</span>
  <span style="color:var(--faint)">→ nạp engine →</span>
  <span style="background:var(--s1,#171a2c);border:1px solid var(--b);border-radius:9999px;padding:2px 8px;color:var(--b)">T2 trục &amp; kịch bản</span>
  <span style="color:var(--faint)">→</span>
  <span style="background:var(--s1,#171a2c);border:1px solid var(--b);border-radius:9999px;padding:2px 8px;color:var(--b)">T1 bức tranh</span>
  <span style="color:var(--border)">|</span>
  <span style="background:var(--s1,#171a2c);border:1px dashed var(--border);border-radius:9999px;padding:2px 8px;opacity:0.75" title="Danh mục cụ thể — gate/filter/invalidation do người biên tập trực tiếp, không tự tính lại từ T1/T2">T5 danh mục (độc lập, byte-preserved)</span>
</div>

<div class="tabs" id="tabs">
  <div class="tab active" data-p="p0">T1 Bức tranh</div>
  <div class="tab" data-p="p1">T2 Kịch bản &amp; Trục</div>
  <div class="tab" data-p="p2">T3 Tín hiệu &amp; Cơ chế</div>
  <div class="tab" data-p="p3">T4 Chính sách</div>
  <div class="tab" data-p="p4">T5 Danh mục 10Y (Tollbooth)</div>
  <div class="tab" data-p="p5">T6 Giả định</div>
</div>

<div class="panel show" id="p0">
  <div class="card"><h3>Cần chú ý <span id="dirtyFlag" class="attn-dirty" style="display:none">● có thay đổi chưa lưu — Export JSON để giữ</span></h3><div id="attn"></div></div>
  <!-- LABAN_T1:BEGIN -->
  <div class="card"><p class="laban-sub">La Bàn engine view pending inject — run build_vn_structural_signals.py --inject</p></div>
  <!-- LABAN_T1:END -->
</div>

<div class="panel" id="p1">
  <!-- LABAN_T2:BEGIN -->
  <div class="card"><p class="laban-sub">T2 pending inject</p></div>
  <!-- LABAN_T2:END -->
</div>

<div class="panel" id="p2">
  {signals}
  <!-- LABAN_T3:BEGIN -->
  <div class="card"><p class="laban-sub">T3 mapping/signatures pending inject</p></div>
  <!-- LABAN_T3:END -->
  <!-- street_coverage_fragment: injection contract preserved (suite may place Tier-A strip here) -->
  <!-- STREET_COVERAGE:BEGIN -->
  <!-- STREET_COVERAGE:END -->
</div>

<div class="panel" id="p3">
  <!-- LABAN_T4:BEGIN -->
  <div class="card"><p class="laban-sub">T4 pending inject</p></div>
  <!-- LABAN_T4:END -->
</div>

<div class="panel" id="p4">
  <p class="laban-sub">Tollbooth 10Y portfolio layer — gates / 7-filter / invalidation (byte-preserved micro framework)</p>
{PORTFOLIO_CARDS}
  <div class="card"><h3>Gate Dashboard</h3>
  <div class="toolbar">
    <input type="text" id="q1" placeholder="Lọc mã/dự án..." oninput="renderGates()">
    <button onclick="exportState()">⬇ Export state JSON</button>
    <label class="btn">⬆ Import state JSON<input type="file" accept=".json" style="display:none" onchange="importState(event)"></label>
  </div>
  <div class="tblwrap"><table><thead><tr><th>Mã</th><th>Dự án</th><th style="width:66px">Gate</th><th>Bằng chứng vật lý</th><th>Bằng chứng tiền</th><th style="width:118px">Trạng thái</th><th style="width:220px">Ghi chú (editable)</th></tr></thead><tbody id="tb1"></tbody></table></div>
  <div class="note">Gate 0 Optionality · 1 Committed build · 2 Commissioning/ramp · 3 Mature capture. Sửa trạng thái/ghi chú rồi Export JSON để lưu; mở lại thì Import. Đề xuất lưu state tại <span style="font-family:'IBM Plex Mono',monospace">reports/tollbooth_tracker_state.json</span>.</div>
  </div>
  <div class="card"><h3>Sàng lọc 7 tiêu chí</h3>
  <div class="tblwrap"><table><thead><tr><th>Mã</th><th>Sleeve</th><th>CP CAGR 21-25</th><th>CFO/EBITDA</th><th>AR days '25 (max)</th><th>Incr. ROIC</th><th>FCF/cp '25</th><th>Pass-through</th><th>Ghi chú</th></tr></thead><tbody id="tb2"></tbody></table></div>
  <div class="note">Số liệu FY2021–2025 tính từ FireAnt panel (all_financial_data_annual_2016_2026.parquet) — <b>chưa verify BCTC gốc từng ô</b>. Ưu tiên spot-check: TV2 AR days 590, GEE CFO/EBITDA 0.19x, TDM rights 10:1. 7 tiêu chí: FCF&amp;EPS/cp tăng · incr. ROIC&gt;WACC · CFO/EBITDA&gt;70% · CP CAGR&lt;5% (loại pro-rata) · pass-through · RPT sạch · định giá vào.</div>
  </div>
  <div class="card"><h3>Invalidation &amp; Chỉ báo</h3>
  <div class="toolbar">
    <button onclick="exportState()">⬇ Export state JSON</button>
    <label class="btn">⬆ Import state JSON<input type="file" accept=".json" style="display:none" onchange="importState(event)"></label>
    <span id="dirtyFlag3" class="attn-dirty" style="display:none">● có thay đổi chưa lưu</span>
  </div>
  <div class="tblwrap"><table><thead><tr><th>Đối tượng</th><th>Ngưỡng / chỉ báo (frozen 22/07/26)</th><th style="width:76px">Tần suất</th><th style="width:118px">Trạng thái</th><th>Nếu vi phạm</th><th style="width:180px">Log (editable)</th></tr></thead><tbody id="tb3"></tbody></table></div>
  <div class="note">Cột "Ngưỡng" không sửa — muốn đổi, ghi log lý do. Trạng thái + Log editable, Export JSON để lưu.</div>
  </div>
</div>

<div class="panel" id="p5">
  <!-- LABAN_T6:BEGIN -->
  <div class="card"><p class="laban-sub">T6 pending inject</p></div>
  <!-- LABAN_T6:END -->
</div>

<!-- LABAN_ENGINE:BEGIN -->
<!-- LABAN_ENGINE:END -->

<script>
"use strict";
// ===== DATA SNAPSHOT (generated 2026-07-22; regen candidate: emit từ FireAnt pipeline) =====
// SCEN bars removed from T1 (superseded by La Bàn engine). Anchors live in data/decision/laban_scenarios.json.
const EVENTS = {events}
const GATES = {gates}
const FILTERS = {filters}
const INVAL = {inval}
let state = {{gates:{{}}, inval:{{}}}};
const stOpts = ["OK","THEO DÕI","CHƯA ĐO","CHƯA VERIFY","MÂU THUẪN","VI PHẠM","CHỜ EVENT","ĐANG TĂNG","CHƯA ĐẠT","BINARY 24/07","OK 22/07","CHỜ","6.8%"];
function stClass(s){{ if(!s) return ""; if(/OK|ĐANG TĂNG|6.8/.test(s)) return "st-ok"; if(/MÂU THUẪN|VI PHẠM|BINARY/.test(s)) return "st-bad"; return "st-warn"; }}
function gateClass(g){{ if(/3/.test(g)) return "g3"; if(/2/.test(g)) return "g2"; if(/1/.test(g)) return "g1"; return "g0"; }}
function esc(s){{ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }}
function renderBadges(){{
  const now = new Date();
  document.getElementById("badges").innerHTML = EVENTS.map(([n,d,hot])=>{{
    const dd = Math.ceil((new Date(d+"T00:00:00") - now)/86400000);
    const t = dd>0 ? `còn <b>${{dd}} ngày</b>` : (dd===0?"<b>HÔM NAY</b>":`đã qua ${{-dd}} ngày`);
    return `<div class="evb${{hot&&dd<=3&&dd>=-1?" hot":""}}${{dd<0?" past":""}}">${{n}}: ${{t}} (${{d.split("-").reverse().join("/")}})</div>`;
  }}).join("");
}}
function goTab(p){{ const t=document.querySelector(`.tab[data-p="${{p}}"]`); if(t) t.click(); }}
function renderAttn(){{
  const items=[];
  GATES.forEach(g=>{{ const st=state.gates[g.id]?.st ?? g.st;
    if(/MÂU THUẪN|VI PHẠM/.test(st)) items.push({{sev:0,tag:"ĐỎ",p:"p4",txt:`${{g.ma}} — ${{g.da}}: <b>${{st}}</b>`+(g.note?` · ${{g.note}}`:"")}});
    else if(/THEO DÕI|CHƯA VERIFY/.test(st)) items.push({{sev:1,tag:"VÀNG",p:"p4",txt:`${{g.ma}} — ${{g.da}}: ${{st}}`}});
  }});
  INVAL.forEach(i=>{{ const st=state.inval[i.id]?.st ?? i.st;
    if(/MÂU THUẪN|VI PHẠM/.test(st)) items.push({{sev:0,tag:"ĐỎ",p:"p4",txt:`${{i.o}} — ${{i.n}}: <b>${{st}}</b>`}});
    else if(/THEO DÕI/.test(st)) items.push({{sev:1,tag:"VÀNG",p:"p4",txt:`${{i.o}}: ${{st}} — ${{i.n}}`}});
  }});
  items.sort((a,b)=>a.sev-b.sev);
  const shown=items.slice(0,8);
  const el=document.getElementById("attn");
  if(!el) return;
  el.innerHTML = (shown.length? shown.map(it=>
    `<div class="attn-line" onclick="goTab('${{it.p}}')"><span class="attn-tag ${{it.sev===0?"red":"amber"}}">${{it.tag}}</span><span>${{it.txt}}</span></div>`).join("")
    : `<div style="font-size:12px;color:var(--g)">Không có mục đỏ/vàng nào — mọi trạng thái OK hoặc chưa tới kỳ đo.</div>`)
    + (items.length>shown.length? `<div style="font-size:10px;color:var(--muted);margin-top:4px">… +${{items.length-shown.length}} mục khác trong T5 Tollbooth</div>`:"")
    + `<div style="font-size:10px;color:var(--muted);margin-top:6px">Bấm một dòng để nhảy tới T5. Tổng hợp tự động từ Gate + Invalidation.</div>`;
}}
let dirty=false;
function markDirty(){{ dirty=true; ["dirtyFlag","dirtyFlag3"].forEach(id=>{{const el=document.getElementById(id); if(el) el.style.display="inline";}}); }}
function renderGates(){{
  const qEl=document.getElementById("q1"); const q = ((qEl&&qEl.value)||"").toLowerCase();
  const tb=document.getElementById("tb1"); if(!tb) return;
  tb.innerHTML = GATES
    .filter(g=>!q || (g.ma+g.da).toLowerCase().includes(q))
    .map(g=>{{
      const st = state.gates[g.id]?.st ?? g.st;
      const note = state.gates[g.id]?.note ?? g.note;
      return `<tr><td><b>${{g.ma}}</b></td><td>${{g.da}}</td><td class="${{gateClass(g.gate)}}"><b>${{g.gate}}</b></td>
      <td>${{g.ly}}</td><td>${{g.ti}}</td>
      <td><select onchange="setG('${{g.id}}','st',this.value)">${{stOpts.map(o=>`<option${{o===st?" selected":""}}>${{o}}</option>`).join("")}}</select><div class="${{stClass(st)}}" style="margin-top:3px">${{st}}</div></td>
      <td><textarea onchange="setG('${{g.id}}','note',this.value)">${{esc(note)}}</textarea></td></tr>`;
    }}).join("");
}}
function renderFilters(){{
  const tb=document.getElementById("tb2"); if(!tb) return;
  const cls = s=>s.startsWith("CORE")?"core":s.startsWith("COND")?"cond":s==="TACTICAL"?"tact":s==="EVENT"?"event":"out";
  tb.innerHTML = FILTERS.map(r=>
    `<tr><td><b>${{r[0]}}</b></td><td><span class="pill ${{cls(r[1])}}">${{r[1]}}</span></td>`+
    r.slice(2).map(c=>`<td>${{c}}</td>`).join("")+`</tr>`).join("");
}}
function renderInval(){{
  const tb=document.getElementById("tb3"); if(!tb) return;
  tb.innerHTML = INVAL.map(i=>{{
    const st = state.inval[i.id]?.st ?? i.st;
    const log = state.inval[i.id]?.log ?? i.log;
    return `<tr><td><b>${{i.o}}</b></td><td>${{i.n}}</td><td>${{i.f}}</td>
    <td><select onchange="setI('${{i.id}}','st',this.value)">${{stOpts.map(o=>`<option${{o===st?" selected":""}}>${{o}}</option>`).join("")}}</select><div class="${{stClass(st)}}" style="margin-top:3px">${{st}}</div></td>
    <td>${{i.v}}</td><td><textarea placeholder="ngày + ghi chú..." onchange="setI('${{i.id}}','log',this.value)">${{esc(log)}}</textarea></td></tr>`;
  }}).join("");
}}
function setG(id,k,v){{ state.gates[id]=state.gates[id]||{{}}; state.gates[id][k]=v; markDirty(); renderGates(); renderAttn(); }}
function setI(id,k,v){{ state.inval[id]=state.inval[id]||{{}}; state.inval[id][k]=v; markDirty(); renderInval(); renderAttn(); }}
function exportState(){{
  const blob = new Blob([JSON.stringify({{exported:new Date().toISOString(),state}},null,2)],{{type:"application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "tollbooth_tracker_state_"+new Date().toISOString().slice(0,10)+".json";
  a.click();
  dirty=false; ["dirtyFlag","dirtyFlag3"].forEach(id=>{{const el=document.getElementById(id); if(el) el.style.display="none";}});
}}
function importState(ev){{
  const f = ev.target.files[0]; if(!f) return;
  const rd = new FileReader();
  rd.onload = e=>{{ try{{ state = JSON.parse(e.target.result).state || state; renderGates(); renderInval(); renderAttn(); dirty=false; ["dirtyFlag","dirtyFlag3"].forEach(id=>{{const el=document.getElementById(id); if(el) el.style.display="none";}}); }}catch(err){{ alert("File JSON không hợp lệ"); }} }};
  rd.readAsText(f);
}}
document.getElementById("tabs").addEventListener("click", e=>{{
  const t = e.target.closest(".tab"); if(!t) return;
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(x=>x.classList.remove("show"));
  t.classList.add("active");
  document.getElementById(t.dataset.p).classList.add("show");
}});
renderBadges(); renderGates(); renderFilters(); renderInval(); renderAttn();
</script>


</div>
</body>
</html>
"""
    # Verify arrays survived
    g2 = extract_const_array(new, "GATES")
    f2 = extract_const_array(new, "FILTERS")
    i2 = extract_const_array(new, "INVAL")
    print("POST GATES", sha_array(g2), "MATCH" if g2 == gates else "DIFF")
    print("POST FILTERS", sha_array(f2), "MATCH" if f2 == filters else "DIFF")
    print("POST INVAL", sha_array(i2), "MATCH" if i2 == inval else "DIFF")
    if g2 != gates or f2 != filters or i2 != inval:
        raise SystemExit("ERROR: T5 array byte-preservation failed")
    return new


def main() -> int:
    if not PATH.is_file():
        raise SystemExit(f"ERROR: source file not found: {PATH} (nothing to rebuild from)")
    html = PATH.read_text(encoding="utf-8")
    new = build(html)
    STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGING_PATH.write_text(new, encoding="utf-8")
    print(f"WROTE {STAGING_PATH} bytes={len(new.encode('utf-8'))} state=SHELL_ONLY")
    print(
        f"NEXT: python scripts/reporting/build_vn_structural_signals.py --publish-shell "
        f"  (this will verify + atomically replace {PATH.name})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
