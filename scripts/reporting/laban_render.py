"""Render La Bàn VN T1–T4 HTML fragments from engine snapshot + fixture JSON.

Injected into tollbooth_tracker_latest.html between LABAN_* markers.
stdlib only. Deterministic for fixed as_of + inputs.
"""
from __future__ import annotations

from html import escape
from typing import Any


LABAN_BEGIN = "<!-- LABAN_ENGINE:BEGIN -->"
LABAN_END = "<!-- LABAN_ENGINE:END -->"


def _pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.1f}".rstrip("0").rstrip(".") + "%"


def _state_chip(state: str) -> str:
    colour = {
        "NOT_RUN": "#6b7280",
        "WEAK": "#f43f5e",
        "MIXED": "#f59e0b",
        "IMPROVING": "#3b82f6",
        "STRONG": "#00c896",
        "ACTIVE": "#f43f5e",
        "INACTIVE": "#64748b",
        "PUBLISHED": "#00c896",
    }.get(state, "#64748b")
    return (
        f'<span style="color:{colour};font-weight:700;font-size:11px">'
        f"{escape(state)}</span>"
    )


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    """Word-wrap for SVG tspans — never cuts mid-word (fix 2026-08-02)."""
    words, out, cur = str(text).split(), [], ""
    for word in words:
        cand = f"{cur} {word}".strip()
        if len(cand) <= width:
            cur = cand
            continue
        if cur:
            out.append(cur)
        cur = word
        if len(out) == max_lines:
            break
    if cur and len(out) < max_lines:
        out.append(cur)
    if len(out) == max_lines and len(" ".join(words)) > len(" ".join(out)):
        out[-1] = out[-1][: max(0, width - 1)] + "…"
    return out or [""]


def render_simple_flow_svg(
    axes: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    working: dict[str, float] | None,
    anchors: dict[str, float],
    diagnostics: dict[str, Any] | None = None,
    adv_counts: dict[str, int] | None = None,
) -> str:
    """T1: N axes → M scenarios (dynamic pitch; v2.1 = 5 axes).

    Edge = FROZEN envelope CONSTRAINT (spec: edges never re-mean with data). An axis whose
    envelope admits every state is not a constraint for that scenario, so no edge is drawn —
    that is what makes the picture readable instead of a 20-line mesh. Edge weight encodes how
    tight the frozen constraint is; it does not move when observations move. All data-driven
    movement lives in node badges, per the converged spec.
    """
    w, h = 760, 300
    ax_y, sc_y = 44, 196
    n_ax, n_sc = len(axes), len(scenarios)
    margin = 70
    if n_ax <= 1:
        ax_xs = [w / 2]
    else:
        pitch = (w - 2 * margin) / (n_ax - 1)
        ax_xs = [margin + i * pitch for i in range(n_ax)]
    if n_sc <= 1:
        sc_xs = [w / 2]
    else:
        sc_pitch = (w - 2 * 60) / (n_sc - 1)
        sc_xs = [60 + i * sc_pitch for i in range(n_sc)]
    node_half = 70  # axis node width 140
    aria = f"La Ban: {n_ax} truc toi {n_sc} kich ban"
    lines = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:760px;display:block;margin:8px 0" '
        f'xmlns="http://www.w3.org/2000/svg" aria-label="{aria}">'
    ]
    for i, ax in enumerate(axes):
        aid = ax.get("id") or ax.get("axis_id")
        for j, sc in enumerate(scenarios):
            if aid == "domestic_capital_formation_quality":
                env = sc.get("dcfq_envelope") or []
            else:
                env = (sc.get("axis_envelope") or {}).get(aid) or []
            # Draw ONLY the DEFINING constraints — an envelope pinned to a single state.
            # (First cut skipped only >=3-state envelopes; every frozen envelope is 1-2 states,
            # so nothing was skipped and the picture stayed a 20-line mesh. Pinning to len==1
            # halves it AND carries real meaning: which axis DEFINES which scenario. Still a
            # frozen property — it does not move when observations move.)
            if len(env) != 1:
                continue
            lines.append(
                f'<line x1="{ax_xs[i]}" y1="{ax_y + 20}" x2="{sc_xs[j]}" y2="{sc_y - 22}" '
                f'stroke="#4a5578" stroke-width="1.6" opacity="0.85"/>'
            )
    for i, ax in enumerate(axes):
        st = str(ax.get("state") or "NOT_RUN")
        live = st != "NOT_RUN"
        nm = _wrap(str(ax.get("name_vi") or ax.get("axis_id") or ax.get("id") or ""), 22, 2)
        tsp = "".join(
            f'<tspan x="{ax_xs[i]}" dy="{0 if k == 0 else 11}">{escape(t)}</tspan>'
            for k, t in enumerate(nm)
        )
        n_adv = (adv_counts or {}).get(str(ax.get("id") or ax.get("axis_id") or ""), 0)
        # Round 7 (2026-08-09, dual-judge REDIRECT): tiny non-directional flag only — no
        # colour/size encoding tied to direction (that vocabulary is reserved for ±pp badges
        # on scenario nodes). Purely "there is related research"; count sourced from the
        # separate laban_advisory_links.json, joined at render time.
        adv_flag = ""
        if n_adv:
            adv_flag = (
                f'<circle cx="{ax_xs[i] + node_half - 9}" cy="{ax_y - 15}" r="8" '
                f'fill="#1f2340" stroke="#5b6472" stroke-width="1"/>'
                f'<text x="{ax_xs[i] + node_half - 9}" y="{ax_y - 12}" text-anchor="middle" '
                f'fill="#8b93a8" font-size="8" font-family="IBM Plex Mono,monospace">⚑{n_adv}</text>'
            )
        lines.append(
            f'<rect x="{ax_xs[i] - node_half}" y="{ax_y - 20}" width="{node_half * 2}" height="42" rx="6" '
            f'fill="{"#13162a" if live else "#171a2c"}" stroke="{"#3b82f6" if live else "#252a45"}"/>'
            f'<text y="{ax_y - 6}" text-anchor="middle" fill="{"#e2e8f0" if live else "#7a8399"}" '
            f'font-size="10" font-family="IBM Plex Sans,sans-serif">{tsp}</text>'
            f'<text x="{ax_xs[i]}" y="{ax_y + 17}" text-anchor="middle" '
            f'fill="{"#8ab4f8" if live else "#5b6472"}" font-size="9" '
            f'font-family="IBM Plex Mono,monospace">{escape(st)}</text>'
            f"{adv_flag}"
        )
    for j, sc in enumerate(scenarios):
        sid = sc["id"]
        a = anchors.get(sid)
        wk = working.get(sid) if working else None
        nm = _wrap(str(sc.get("name_vi") or sid), 19, 2)
        tsp = "".join(
            f'<tspan x="{sc_xs[j]}" dy="{0 if k == 0 else 11}">{escape(t)}</tspan>'
            for k, t in enumerate(nm)
        )
        if wk is not None:
            headline = f"{sid} · {_pct(wk)}"
            sub = f"neo {_pct(a)}"
        else:
            headline = f"{sid} · {_pct(a)}"
            sub = "neo (chưa có working)"
        badge = ""
        if wk is not None and a is not None:
            d = wk - a
            if abs(d) >= 0.05:  # same threshold, now rendered at matching precision
                col = "#00c896" if d > 0 else "#f43f5e"
                lines.append(
                    f'<rect x="{sc_xs[j] + 26}" y="{sc_y - 34}" width="44" height="15" rx="7" '
                    f'fill="{col}" opacity="0.9"/>'
                    f'<text x="{sc_xs[j] + 48}" y="{sc_y - 23}" text-anchor="middle" fill="#0d0f1a" '
                    f'font-size="9" font-weight="700" font-family="IBM Plex Mono,monospace">'
                    f'{"+" if d > 0 else "−"}{abs(d):.1f}pp</text>'
                )
        lines.append(
            f'<rect x="{sc_xs[j] - 68}" y="{sc_y - 20}" width="136" height="58" rx="6" '
            f'fill="#13162a" stroke="#252a45"/>'
            f'<text y="{sc_y - 4}" text-anchor="middle" fill="#e2e8f0" font-size="10" '
            f'font-family="IBM Plex Sans,sans-serif">{tsp}</text>'
            f'<text x="{sc_xs[j]}" y="{sc_y + 21}" text-anchor="middle" fill="#e2e8f0" '
            f'font-size="11" font-weight="600" font-family="IBM Plex Mono,monospace">'
            f"{escape(headline)}</text>"
            f'<text x="{sc_xs[j]}" y="{sc_y + 32}" text-anchor="middle" fill="#64748b" '
            f'font-size="8" font-family="IBM Plex Mono,monospace">{escape(sub)}</text>'
            f"{badge}"
        )
    d = diagnostics or {}
    not_run = list(d.get("not_run") or [])
    active = list(d.get("active") or [])
    if active:
        lane_txt = "FRAME-STRESS: " + ", ".join(str(x) for x in active)
        lane_fill, lane_stroke, lane_col = "#2a0f1a", "#f43f5e", "#f43f5e"
    else:
        health = str(d.get("frame_health") or "NOT_RUN")
        lane_txt = f"FRAME-STRESS: không có cờ nào · {health}"
        if not_run:
            lane_txt += f" · chưa chạy: {', '.join(str(x) for x in not_run)}"
        lane_fill, lane_stroke, lane_col = "#131a17", "#2d4a3a", "#7a9c8a"
    lines.append(
        f'<rect x="8" y="{h - 32}" width="{w - 16}" height="26" rx="4" fill="{lane_fill}" '
        f'stroke="{lane_stroke}"/>'
        f'<text x="18" y="{h - 14}" fill="{lane_col}" font-size="9.5" '
        f'font-family="IBM Plex Mono,monospace">{escape(lane_txt[:110])}</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


def render_network_svg(
    signals: list[dict[str, Any]],
    axes: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> str:
    w, h = 860, 320
    sx = [40 + i * 70 for i in range(len(signals))]
    ax = [120 + i * 160 for i in range(len(axes))]
    sc = [80 + i * 150 for i in range(len(scenarios))]
    y_s, y_a, y_c = 40, 150, 270
    out = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:860px" '
        f'xmlns="http://www.w3.org/2000/svg">'
    ]
    thesis_to_axis = {
        "infrastructure-for-automation": "infrastructure_conversion",
        "supply-chain-diversification": "supply_chain_depth",
        "value-retention": "domestic_value_retention",
        "upstream-migration": "supply_chain_depth",
        "inputs-vs-capex": "supply_chain_depth",
    }
    def _aid(a: dict) -> str:
        return str(a.get("id") or a.get("axis_id") or "")

    axis_idx = {_aid(a): i for i, a in enumerate(axes)}
    sc_idx = {s["id"]: i for i, s in enumerate(scenarios)}
    default_ax = _aid(axes[0]) if axes else ""
    for i, sig in enumerate(signals):
        aid = thesis_to_axis.get(sig.get("thesis", ""), default_ax)
        if aid in axis_idx:
            j = axis_idx[aid]
            out.append(
                f'<line x1="{sx[i]}" y1="{y_s + 10}" x2="{ax[j]}" y2="{y_a - 10}" '
                f'stroke="#374060" stroke-width="1"/>'
            )
        sm = sig.get("scenario_map") or {}
        for sid, m in sm.items():
            if sid in sc_idx and abs(float(m)) > 0 and aid in axis_idx:
                k = sc_idx[sid]
                thick = min(3.0, 0.8 + abs(float(m)) * 0.6)
                col = "#00c896" if float(m) > 0 else "#f43f5e"
                out.append(
                    f'<line x1="{ax[axis_idx[aid]]}" y1="{y_a + 10}" x2="{sc[k]}" y2="{y_c - 10}" '
                    f'stroke="{col}" stroke-width="{thick}" opacity="0.35"/>'
                )
    for i, sig in enumerate(signals):
        out.append(
            f'<circle cx="{sx[i]}" cy="{y_s}" r="10" fill="#1a1e35" stroke="#3b82f6"/>'
            f'<text x="{sx[i]}" y="{y_s + 28}" text-anchor="middle" fill="#8b9eb8" font-size="7">'
            f'{escape(sig["id"][:10])}</text>'
        )
    for i, a in enumerate(axes):
        out.append(
            f'<rect x="{ax[i] - 40}" y="{y_a - 12}" width="80" height="24" rx="4" '
            f'fill="#13162a" stroke="#252a45"/>'
            f'<text x="{ax[i]}" y="{y_a + 4}" text-anchor="middle" fill="#e2e8f0" font-size="8">'
            f'{escape(_aid(a)[:14])}</text>'
        )
    for i, s in enumerate(scenarios):
        out.append(
            f'<rect x="{sc[i] - 40}" y="{y_c - 12}" width="80" height="24" rx="4" '
            f'fill="#13162a" stroke="#252a45"/>'
            f'<text x="{sc[i]}" y="{y_c + 4}" text-anchor="middle" fill="#e2e8f0" font-size="8">'
            f'{escape(s["id"])}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


_REL_VI = {
    "REQUIRED": "CẦN giả định này",
    "COMPATIBLE": "tương thích",
    "ADVERSE": "bất lợi cho giả định",
    "INVALIDATING": "PHÁ VỠ giả định",
}

_ASTATE_COL = {"PASS": "#00c896", "TENSION": "#f59e0b", "BREACH": "#f43f5e", "NOT_RUN": "#64748b"}


def render_fx_transmission_mirror(contract: dict[str, Any] | None) -> str:
    """Compact T6 read-only mirror of FX→liquidity transmission (non-scoring)."""
    c = contract or {}
    state = c.get("current_state") or {}
    state_id = state.get("id")
    integrity = str(c.get("integrity_status") or "UNKNOWN")
    as_of = escape(str(c.get("as_of") or "Unknown"))
    ehash = escape(str(c.get("evidence_hash") or ""))
    if integrity != "VALID" or not isinstance(state_id, int):
        return (
            '<div class="card" style="border-color:var(--border)">'
            "<h3>FX–LIQUIDITY TRANSMISSION</h3>"
            '<p style="font-size:12px;color:var(--muted)"><b>UNKNOWN / STALE</b> · Not confirmed</p>'
            '<p style="font-size:11px;color:var(--muted)">Observation / Inference / Confirmation unavailable '
            "until the Rate Pivot transmission contract validates.</p>"
            '<p style="font-size:11px;color:var(--faint)">GT1 impact: monitoring only</p>'
            f'<details style="font-size:10px;color:var(--faint)"><summary>audit</summary>'
            f"as_of {as_of}<br><code style=\"word-break:break-all\">{ehash}</code></details></div>"
        )
    return (
        '<div class="card" style="border-color:rgba(59,130,246,.35);background:rgba(59,130,246,.04)">'
        "<h3>FX–LIQUIDITY TRANSMISSION</h3>"
        f'<p style="font-size:12px"><b>State {state_id}</b> · Positive-marginal · Not confirmed</p>'
        '<p style="font-size:11px;color:var(--muted);line-height:1.45">'
        "Observation: informal FX pressure easing<br>"
        "Inference: reserve-rebuild capacity may improve<br>"
        "Confirmation: absent</p>"
        '<p style="font-size:11px;color:var(--faint)">GT1 impact: monitoring only</p>'
        f'<details style="font-size:10px;color:var(--faint)"><summary>audit</summary>'
        f"as_of {as_of}<br><code style=\"word-break:break-all\">{ehash}</code></details></div>"
    )


def render_t6_assumptions(
    assumptions_doc: dict[str, Any] | None,
    assumptions_eval: dict[str, Any] | None,
    transmission_contract: dict[str, Any] | None = None,
) -> str:
    """T6 — thesis-assumption dependency panel (v1-minimal coupling, REDIRECT design).

    Text-based by design: no name×scenario heatmap, no scores, no scenario-weight arithmetic
    on judgment rows, and NO action vocabulary — the panel says which assumptions the data is
    challenging, never what to own.
    """
    mirror = render_fx_transmission_mirror(transmission_contract)
    ev = assumptions_eval or {}
    by_id = {r.get("assumption_id"): r for r in ev.get("rows") or []}
    docs = (assumptions_doc or {}).get("assumptions") or []
    if not docs:
        return (
            mirror
            + '<div class="card"><h3>Giả định danh mục</h3>'
            '<p style="font-size:11px;color:var(--muted)">NOT_RUN — chưa có registry giả định '
            "(laban_thesis_assumptions.json).</p></div>"
        )
    parts = [mirror]
    if ev.get("alarm"):
        breached = [r for r in ev.get("rows") or [] if r.get("state") == "BREACH"]
        items = "".join(
            f'<li><b>{escape(str(r.get("assumption_id")))}</b> — {escape(str(r.get("reason") or ""))} '
            f'· dự án: <code>{escape(", ".join(r.get("linked_projects") or []))}</code></li>'
            for r in breached
        )
        parts.append(
            f'<div class="card" style="border-color:var(--r);background:var(--rb)">'
            f'<h3 style="color:var(--r)">THESIS DEPENDENCY BREACH</h3>'
            f'<ul style="font-size:12px">{items}</ul>'
            f'<p style="font-size:10px;color:var(--muted)">Cảnh báo hiển thị — không phải khuyến nghị. '
            f"Giả định nền của các dự án nêu trên đã bị dữ liệu bẻ gãy theo ngưỡng tiền đăng ký; "
            f"việc tiếp theo là NGƯỜI xem xét lại luận điểm, không phải một hành động tự động.</p></div>"
        )
    stressed = [r for r in ev.get("rows") or [] if r.get("state") in ("TENSION", "BREACH")]
    if stressed and not ev.get("alarm"):
        items = "".join(
            f'<li><b>{escape(str(r.get("assumption_id")))}</b> — {escape(str(r.get("reason") or ""))}</li>'
            for r in stressed
        )
        parts.append(
            f'<div class="card" style="border-color:var(--a)"><h3>Giả định đang chịu áp lực</h3>'
            f'<ul style="font-size:12px">{items}</ul></div>'
        )
    if not stressed:
        parts.append(
            '<div class="card"><h3>Giả định đang chịu áp lực</h3>'
            '<p style="font-size:12px;color:var(--muted)">Không có — mọi giả định máy-đo được đang '
            "trong biên; các giả định chưa đo được hiển thị NOT_RUN bên dưới, không được tính là đạt.</p></div>"
        )
    cards = []
    for a in docs:
        aid = a.get("assumption_id")
        r = by_id.get(aid) or {}
        st = str(r.get("state") or "NOT_RUN")
        col = _ASTATE_COL.get(st, "#64748b")
        chips = " ".join(
            f'<code style="font-size:10px">{escape(p)}</code>' for p in (a.get("linked_projects") or [])
        )
        rel = (a.get("scenario_relationship") or {})
        rel_txt = " · ".join(
            f"{sid}: {_REL_VI.get(str(v), str(v))}" for sid, v in rel.items()
        )
        mc = a.get("machine_check")
        mc_txt = (
            f'máy-đo: <code>{escape(str(mc.get("diagnostic_id")))} {escape(str(mc.get("operator")))} '
            f'{escape(str(mc.get("threshold")))}</code>'
            if mc else "đánh giá thủ công (chưa có chuỗi máy-đo — nêu rõ, không giả vờ đo)"
        )
        # Executive view (2026-08-09, V feedback "T6 cũng vậy"): statement stays inline (that's
        # the claim itself, the one line worth reading without a click); mechanism/dependent
        # projects/scenario-relationship/machine-check/source/current-reading collapse into one
        # <details> toggle. No information removed, just not force-read by default.
        cards.append(
            f'<div class="card">'
            f'<h3>{escape(str(aid))} <span style="color:{col};font-size:11px;font-weight:700">{escape(st)}</span> '
            f'<span style="color:var(--faint);font-size:10px">[{escape(str(a.get("soft_or_hard")))}'
            f' · {escape(str(a.get("basis") or ""))}]</span></h3>'
            f'<p style="font-size:12px">{escape(str(a.get("statement_vi") or ""))}</p>'
            f'<details style="font-size:10px;color:var(--muted)"><summary style="cursor:pointer;color:var(--faint)">chi tiết</summary>'
            f'<p>Cơ chế: {escape(str(a.get("mechanism_vi") or ""))}</p>'
            f'<p>Dự án phụ thuộc: {chips}</p>'
            f'<p>Kịch bản ↔ giả định: {escape(rel_txt)}</p>'
            f'<p>{mc_txt} · nguồn: {escape(str(a.get("source") or ""))} '
            f'· đọc hiện tại: {escape(str(r.get("reason") or "—"))}</p></details></div>'
        )
    footer = (
        '<div class="card" style="border-color:var(--border)"><p style="font-size:10px;color:var(--faint)">'
        "Ranh giới cứng của panel này (REDIRECT 2026-08-03, hai seat + V): nói giả định nào đang bị "
        "dữ liệu thách thức — KHÔNG BAO GIỜ nói mua/bán/tăng/giảm/thay thế; không nhân xác suất kịch bản "
        "với ô phán đoán; không điểm số tập trung. Kịch bản đổi trọng số → giả định nào đáng chú ý đổi; "
        "bằng chứng đổi → trạng thái giả định đổi; dự án chỉ HIỂN THỊ mình phụ thuộc giả định nào.</p></div>"
    )
    return "".join(parts) + "".join(cards) + footer


def render_laban_block(
    snapshot: dict[str, Any],
    scenarios_doc: dict[str, Any],
    signatures_doc: dict[str, Any],
    signals_doc: dict[str, Any],
    frame_log: dict[str, Any],
    assumptions_doc: dict[str, Any] | None = None,
    advisory_links_doc: dict[str, Any] | None = None,
    transmission_contract: dict[str, Any] | None = None,
) -> str:
    w = snapshot.get("weights") or {}
    d = snapshot.get("diagnostics") or {}
    axes = (snapshot.get("axis_state") or {}).get("axes") or []

    # Round 7 (2026-08-09, dual-judge REDIRECT): advisory links live in a SEPARATE file
    # (laban_advisory_links.json), never inside the axis object. Join by axis_id here, at
    # render time only — this function must never write anything back into `axes`/`ax`.
    adv_links_all = (advisory_links_doc or {}).get("advisory_links") or []
    adv_by_axis: dict[str, list[dict[str, Any]]] = {}
    for _al in adv_links_all:
        for _aref in _al.get("axis_refs") or []:
            adv_by_axis.setdefault(_aref, []).append(_al)
    sc_list = scenarios_doc.get("scenarios") or []
    anchors = w.get("anchors") or {s["id"]: s["anchor_prior_pct"] for s in sc_list}
    working = w.get("working")
    published = bool(w.get("published"))
    status = str(w.get("status") or "")
    as_of = snapshot.get("as_of") or "—"
    n_obs = w.get("n_valid_obs") or 0
    n_ax = w.get("n_axes_covered") or 0

    # Anchor-vs-working strip
    weight_rows = []
    for s in sc_list:
        sid = s["id"]
        a = anchors.get(sid)
        wk = working.get(sid) if working else None
        if working is None:
            weight_rows.append(
                f'<div class="scen"><div class="bar" style="width:{(a or 0) * 6}px;background:var(--faint)"></div>'
                f'<span><b>Anchor {_pct(a)}</b> {escape(s.get("name_vi") or sid)}'
                f' <span style="color:var(--muted)">(working=null)</span></span></div>'
            )
        else:
            dpp = (wk or 0) - (a or 0)
            weight_rows.append(
                f'<div class="scen"><div class="bar" style="width:{(wk or 0) * 6}px;background:var(--b)"></div>'
                f'<span><b>Working {_pct(wk)}</b> · Anchor {_pct(a)} · '
                f'{"+" if dpp >= 0 else ""}{dpp:.1f}pp · {escape(s.get("name_vi") or sid)}</span></div>'
            )

    n_axes_total = len(axes)
    if working is None:
        aw_line = (
            f'<p style="font-size:12px;color:var(--muted)">Anchors only · n valid obs={n_obs} · '
            f'{n_ax}/{n_axes_total} axes · updated {escape(str(as_of))} · '
            f'<b style="color:var(--a)">{escape(status)}</b></p>'
        )
    else:
        # pick dominant for summary line
        top = max(sc_list, key=lambda s: working.get(s["id"], 0))
        sid = top["id"]
        dpp = working[sid] - anchors.get(sid, 0)
        aw_line = (
            f'<p style="font-size:12px">Working {_pct(working[sid])} · Anchor {_pct(anchors.get(sid))} · '
            f'{"+" if dpp >= 0 else ""}{dpp:.1f}pp · n obs={n_obs} · '
            f'{n_ax}/{n_axes_total} axes · updated {escape(str(as_of))}</p>'
        )

    # Frame health
    diag_list = d.get("diagnostics") or []
    diag_bits = " · ".join(
        f'{escape(x["id"])}={escape(x["state"])}' for x in diag_list
    )
    health = (
        f'<div class="card" style="border-color:#6a2a4a">'
        f'<h3>Frame health</h3>'
        f'<p><b>FRAME HEALTH: PARTIALLY OBSERVED</b></p>'
        f'<p style="font-size:11px;color:var(--muted)">{diag_bits or "—"}</p>'
        f'<p style="font-size:10px;color:var(--faint)">Never a single completeness %. '
        f'Active: {escape(", ".join(d.get("active") or []) or "none")} · '
        f'NOT_RUN: {escape(", ".join(d.get("not_run") or []) or "none")}</p></div>'
    )

    kill = snapshot.get("kill_conditions") or {}
    n_armed = int(kill.get("n_armed") or 0)
    if n_armed >= 1:
        inv_title = f"HARD INVALIDATION ENGINE: ARMED ({n_armed} rows)"
        inv_body = (
            f'<p style="font-size:11px;color:var(--muted)">Evaluator active — '
            f'{escape(str(kill.get("engine_state") or ""))}. '
            f'FIRED rows refuse publish (MODEL-CONTRADICTION). '
            f'Absence of observation → NOT_RUN, never PASS.</p>'
        )
    else:
        inv_title = "HARD INVALIDATION ENGINE: NOT_OPERATIONAL"
        inv_body = (
            f'<p style="font-size:11px;color:var(--muted)">Schema + evaluator wired '
            f'(<code>laban_kill_conditions.json</code>) nhưng chưa có hàng ARMED — '
            f'nội dung điều kiện là Claude freeze act, không dịch từ văn bản đóng băng tại đây. '
            f'Khi ≥1 hàng ARMED, card này chuyển sang ARMED (n rows).</p>'
        )
    invalidation = (
        f'<div class="card" style="border-color:var(--r)">'
        f'<h3>{escape(inv_title)}</h3>'
        f"{inv_body}"
        f'<p style="font-size:10px;color:var(--faint)">v2.1: DCFQ axis engine-wired (NOT_RUN until assessed); '
        f'signal↔axis divergence = flag only, never overwrites operator state.</p></div>'
    )

    stress = ""
    if w.get("frame_tension"):
        stress = (
            f'<div class="card" style="border-color:var(--r)">'
            f'<h3>FRAME-TENSION</h3><p>{escape(status)}</p>'
            f'<p style="font-size:11px;color:var(--muted)">No weights published.</p></div>'
        )
    if "EXTRAORDINARY" in status:
        stress += (
            f'<div class="card" style="border-color:var(--r)">'
            f'<h3>Publication frozen</h3><p>{escape(status)}</p></div>'
        )

    moves = w.get("moves") or []
    move_html = (
        "<ul>"
        + "".join(
            f'<li><code>{escape(m.get("scenario_id",""))}</code>: '
            f'{escape(str(m))}</li>'
            for m in moves
        )
        + "</ul>"
        if moves
        else '<p style="color:var(--muted);font-size:12px">No movement this run (or unpublished).</p>'
    )

    # Merge Vietnamese axis names from the frozen ontology into the axis-state records.
    # (Fix 2026-08-02: axis_state carries axis_id + state only, so the flow was rendering raw
    # English IDs. The two files stay structurally separate by design — this joins them for
    # DISPLAY only, it does not move name_vi into the state file.)
    _ax_names = {
        a.get("id"): a.get("name_vi")
        for a in (scenarios_doc.get("axes") or [])
        if a.get("id")
    }
    axes = [
        {**a, "name_vi": a.get("name_vi") or _ax_names.get(a.get("axis_id") or a.get("id"))}
        for a in axes
    ]
    flow = render_simple_flow_svg(
        axes, sc_list, working, anchors, d,
        adv_counts={k: len(v) for k, v in adv_by_axis.items()},
    )
    flow_title = f"{len(axes)} trục → {len(sc_list)} kịch bản"

    t1 = f"""
<div id="laban-t1-body">
  <div class="card">
    <h3>{escape(flow_title)}</h3>
    <p style="font-size:11px;color:var(--muted);margin-bottom:6px">Đường nối = <b>ràng buộc định danh</b> (envelope đóng băng chốt đúng 1 trạng thái cho trục đó) — không đổi nghĩa theo dữ liệu. Mọi chuyển động hiển thị bằng <b>huy hiệu ±pp</b> trên node. Số lớn = working, dòng dưới = neo (anchor).</p>
    {flow}
    {aw_line}
    <div>{''.join(weight_rows)}</div>
  </div>
  {health}
  {invalidation}
  {stress}
  <div class="card"><h3>What moved this run</h3>{move_html}</div>
</div>
"""

    # T2 scenario cards
    sig_rows = signatures_doc.get("rows") or []
    cards = []
    for s in sc_list:
        sid = s["id"]
        rows = [r for r in sig_rows if r.get("scenario_id") == sid]
        # scoreboard counts — honest NOT_RUN when no matured state
        core = [r for r in rows if r.get("diagnostic_strength") == "CORE"]
        score = (f"CORE rows={len(core)} · MATCH/MISS/NOT-YET/NO-DATA = 0/0/0/{len(core)} "
                 f"— chưa có chẩn đoán nào tới hạn (forecast_horizon chưa đến)")
        env = s.get("axis_envelope") or {}
        env_row = " · ".join(f"{escape(k)}:{'/'.join(v)}" for k, v in env.items())
        kills = "".join(f"<li>{escape(k)}</li>" for k in (s.get("kill_conditions") or []))
        a = anchors.get(sid)
        wk = working.get(sid) if working else None
        cards.append(
            f'<div class="card">'
            f'<h3>{escape(s.get("name_vi") or sid)} <code>{escape(sid)}</code></h3>'
            f'<p style="font-size:11px">{escape(s.get("definition") or "")}</p>'
            f'<p style="font-size:11px;color:var(--muted)">Envelope: {env_row}</p>'
            f'<p style="font-size:11px">Signature: {escape(score)}</p>'
            f'<p style="font-size:11px">Anchor {_pct(a)}'
            + (f' · Working {_pct(wk)}' if working is not None else ' · working=null')
            + f'</p>'
            f'<p style="font-size:11px;color:var(--a)">Trạng thái: chưa có TENSION, chưa có DEFINITION-BREACH '
            f'— chưa đủ quan sát tới hạn để chấm</p>'
            f'<p style="font-size:10px;color:var(--faint)">Kill-conditions (văn bản đóng băng — '
            f'hàng máy-đọc-được chờ Claude freeze vào laban_kill_conditions.json):</p>'
            f'<ul style="font-size:11px">{kills}</ul></div>'
        )

    div_diag = next(
        (x for x in diag_list if x.get("id") == "signal_axis_divergence"), None
    )
    div_by_axis = {
        r.get("axis_id"): r
        for r in ((div_diag or {}).get("per_axis") or [])
    }
    axis_cards = []
    for ax in axes:
        aid = ax.get("axis_id") or ""
        drow = div_by_axis.get(aid) or {}
        dres = str(drow.get("result") or "NOT_LINKED")
        divergent = dres == "DIVERGENT"
        # Executive view (2026-08-09, V feedback "T2 wordy quá"): only DIVERGENT signal↔axis
        # surfaces inline (it's an active flag, needs to be seen without a click). Everything
        # else that used to always-render as a paragraph now lives behind one <details> toggle
        # per card — same information, zero forced reading.
        if divergent:
            dflag_inline = (
                f'<p style="font-size:11px;color:var(--r);font-weight:700">'
                f'⚠ SIGNAL↔AXIS DIVERGENT — {escape(str(drow.get("reason") or ""))}</p>'
            )
            dflag_detail = ""
        else:
            dflag_inline = ""
            dflag_detail = f'<p>SIGNAL↔AXIS: {escape(dres)} (flag only; operator state never auto-overwritten)</p>'
        dcfq_detail = ""
        if aid == "domestic_capital_formation_quality":
            dcfq_detail = (
                "<p>Envelope = set-membership (dcfq_envelope); NOT_RUN contributes nothing to "
                "envelope score.</p>"
            )
        # Round 7 (2026-08-09, dual-judge REDIRECT): advisory_links are NOT read from `ax`
        # (never persisted inside the axis object — reference, not containment). Card only
        # shows a tiny non-directional badge; full content lives in the separate
        # "RESEARCH CONTEXT — NON-SCORING" block below, joined by axis_id at render time.
        axis_adv = adv_by_axis.get(aid) or []
        adv_badge = (
            f' <span style="font-size:10px;color:var(--muted)" title="research context, non-scoring">⚑{len(axis_adv)}</span>'
            if axis_adv else ""
        )
        cov = ax.get("coverage")
        cov_pct = f"{float(cov) * 100:.0f}%" if isinstance(cov, (int, float)) else "—"
        cov_bar_w = f"{min(max(float(cov), 0) * 100, 100):.0f}%" if isinstance(cov, (int, float)) else "0%"
        detail_bits = f"{dflag_detail}{dcfq_detail}<p>{escape(str(ax.get('status') or ''))}</p>"
        axis_cards.append(
            f'<div class="card">'
            f'<h3>{escape(str(aid))}{adv_badge}</h3>'
            f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0 4px">'
            f'{_state_chip(str(ax.get("state") or "NOT_RUN"))}'
            f'<span style="flex:1;height:4px;background:var(--border);border-radius:9999px;overflow:hidden">'
            f'<span style="display:block;height:100%;width:{cov_bar_w};background:var(--b)"></span></span>'
            f'<span style="font-size:10px;color:var(--muted);white-space:nowrap">cov {cov_pct}</span>'
            f"</div>"
            f"{dflag_inline}"
            f'<details style="font-size:10px;color:var(--muted)"><summary style="cursor:pointer;color:var(--faint)">chi tiết</summary>{detail_bits}</details>'
            f"</div>"
        )

    t2 = f'<div id="laban-t2-body"><div class="grid2">{"".join(cards)}</div>'
    t2 += f'<h3 style="margin:12px 0 8px;font-size:12px;color:var(--dim)">AXIS STATE</h3>'
    t2 += f'<div class="grid2">{"".join(axis_cards)}</div>'
    if adv_links_all:
        rc_rows = "".join(
            f'<div class="card" style="border-color:#3a3a55">'
            f'<h3 style="font-size:12px">{escape(str(al.get("id") or ""))} '
            f'<span style="font-size:10px;color:var(--muted)">→ {escape(", ".join(al.get("axis_refs") or []))}</span></h3>'
            f'<p style="font-size:10px;color:var(--muted)">[{escape(str(al.get("status") or "ADVISORY"))} · '
            f'effect on scoring: NONE — reference only]</p>'
            f'<details style="font-size:10px;color:var(--faint)"><summary style="cursor:pointer;color:var(--muted)">đọc thêm</summary>'
            f'<p>{escape(str(al.get("reading") or ""))}</p></details>'
            f"</div>"
            for al in adv_links_all
        )
        t2 += (
            '<h3 style="margin:12px 0 8px;font-size:12px;color:var(--dim)">'
            'RESEARCH CONTEXT — NON-SCORING</h3>'
            f'<div class="grid2">{rc_rows}</div>'
        )
    t2 += "</div>"

    # T3 mapping + signatures + network
    map_rows = []
    for sig in signals_doc.get("signals") or []:
        sm = sig.get("scenario_map")
        if not sm:
            map_rows.append(
                f'<tr><td>{escape(sig["id"])}</td><td colspan="5" style="color:#6b7280">NOT_RUN — no scenario_map</td></tr>'
            )
            continue
        cells = "".join(f'<td class="mono">{int(sm.get(s["id"], 0)):+d}</td>' for s in sc_list)
        map_rows.append(f'<tr><td>{escape(sig["id"])}</td>{cells}</tr>')

    sig_table = []
    for r in sig_rows:
        sig_table.append(
            "<tr>"
            f'<td>{escape(str(r.get("scenario_id")))}</td>'
            f'<td>{escape(str(r.get("diagnostic_id")))}</td>'
            f'<td>{escape(str(r.get("expected_state")))}</td>'
            f'<td>{escape(",".join(r.get("allowed_states") or []))}</td>'
            f'<td>{escape(str(r.get("diagnostic_strength")))}</td>'
            f'<td>{escape(str(r.get("failure_type")))}</td>'
            f'<td style="color:#6b7280">NOT_RUN</td>'
            "</tr>"
        )

    net = render_network_svg(signals_doc.get("signals") or [], axes, sc_list)
    t3_extra = f"""
<div id="laban-t3-extra">
  <div class="card"><h3>Bản đồ tín hiệu → kịch bản (đóng băng v2.0)</h3>
  <div class="tblwrap"><table><thead><tr><th>Signal</th>
  {''.join(f'<th>{escape(s["id"])}</th>' for s in sc_list)}
  </tr></thead><tbody>{''.join(map_rows)}</tbody></table></div></div>
  <div class="card"><h3>Scenario signatures</h3>
  <div class="tblwrap"><table><thead><tr>
  <th>Scenario</th><th>Diagnostic</th><th>Expected</th><th>Allowed</th><th>Strength</th><th>Failure</th><th>Read</th>
  </tr></thead><tbody>{''.join(sig_table)}</tbody></table></div></div>
  <details class="card"><summary style="cursor:pointer;font-weight:700;color:var(--dim)">Full signals→axes→scenarios network (collapsed)</summary>
  {net}
  </details>
</div>
"""

    # T4 policy
    events = frame_log.get("policy_events") or []
    ev_rows = []
    for e in events:
        ev_rows.append(
            "<tr>"
            f'<td>{escape(str(e.get("date")))}</td>'
            f'<td>{escape(str(e.get("instrument")))}</td>'
            f'<td>{escape(str(e.get("stage")))}</td>'
            f'<td>{escape(str(e.get("driver_tag")))}</td>'
            f'<td>{escape(str(e.get("axis_tag")))}</td>'
            f'<td style="font-size:10px;color:var(--muted)">{escape(str(e.get("source")))}</td>'
            "</tr>"
        )
    ptr = frame_log.get("policy_trigger_radar_pointer") or {}
    # Tariff watch synthesis (2026-08-09, V asked "khi nào biết VN có bị áp thêm thuế không" —
    # answer required piecing together 3 rows from the raw table below; this card does that
    # synthesis once so it doesn't have to be re-derived by reading the raw table every time).
    tariff_events = [e for e in events if e.get("driver_tag") == "TARIFF_MARKET_ACCESS"]
    tariff_rows = "".join(
        f'<tr><td>{escape(str(e.get("stage") or ""))}</td>'
        f'<td>{escape(str(e.get("instrument") or ""))}</td>'
        f'<td class="mono">{escape(str(e.get("date") or "OPEN"))}</td>'
        f'<td style="font-size:10px;color:var(--muted)">{escape(str(e.get("source") or ""))}</td></tr>'
        for e in tariff_events
    )
    tariff_card = (
        '<div class="card" style="border-color:var(--b)"><h3>⏱ Tariff watch — khi nào biết VN có bị áp thêm thuế</h3>'
        '<p style="font-size:11px;color:var(--muted)">3 nhánh Section 301 chạy song song. '
        'Mốc gần nhất đáng canh: <b>29/11/2026</b> (hạn quyết định nhánh IP theo luật — có thể lùi tới '
        '28/02/2027 nếu gia hạn 3 tháng). Nhánh dư thừa công suất CHƯA có hạn công bố.</p>'
        f'<div class="tblwrap"><table><thead><tr><th>Trạng thái</th><th>Nhánh</th><th>Ngày</th><th>Nguồn</th></tr></thead>'
        f'<tbody>{tariff_rows or "<tr><td colspan=4 style=color:#6b7280>chưa có policy_event nào gắn TARIFF_MARKET_ACCESS</td></tr>"}</tbody></table></div>'
        '<p style="font-size:10px;color:var(--faint);margin-top:6px">Kill-condition D1: nếu IP + overcapacity đều KHÔNG hành động thuế mới suốt 4 quý liên tiếp → "threat not materialising". '
        'Nhánh lao động = CONFIRMED trực tiếp USTR; 2 nhánh còn lại (ngày khởi điều tra, hạn 29/11) = SOURCE-SECONDARY, chưa Claude đối chiếu trực tiếp Federal Register.</p>'
        '</div>'
    )
    t4 = f"""
<div id="laban-t4-body">
  {tariff_card}
  <div class="card"><h3>Policy events (structured)</h3>
  <div class="tblwrap"><table><thead><tr>
  <th>Date</th><th>Instrument</th><th>Stage</th><th>Driver</th><th>Axis</th><th>Source</th>
  </tr></thead><tbody>{''.join(ev_rows) if ev_rows else '<tr><td colspan="6" style="color:#6b7280">NOT_RUN — empty policy list</td></tr>'}
  </tbody></table></div>
  <p style="font-size:11px;color:var(--muted);margin-top:8px">policy_trigger_radar pointer: {escape(str(ptr.get("path")))} · {escape(str(ptr.get("staleness_note")))}</p>
  </div>
</div>
"""

    # Blind-spot / quarterly top3 strip for T1 stress lane label update
    bs = next((x for x in diag_list if x.get("id") == "causal_blind_spot"), None)
    bs_html = ""
    if bs:
        bs_html = (
            f'<div class="card"><h3>Causal blind-spot (quarterly)</h3>'
            f'<p style="font-size:11px">state={escape(bs.get("state",""))} · {escape(bs.get("reason",""))}</p>'
            f'<pre style="font-size:10px;color:var(--muted);white-space:pre-wrap">'
            f'{escape(str(bs.get("quarterly_top3") or []))}</pre></div>'
        )

    return (
        f"{LABAN_BEGIN}\n"
        f'<div id="laban-root" data-published="{str(published).lower()}" data-status="{escape(status)}">\n'
        f"<!--TAB:T1-->{t1}{bs_html}<!--/TAB:T1-->\n"
        f"<!--TAB:T2-->{t2}<!--/TAB:T2-->\n"
        f"<!--TAB:T3-->{t3_extra}<!--/TAB:T3-->\n"
        f"<!--TAB:T4-->{t4}<!--/TAB:T4-->\n"
        f"<!--TAB:T6-->{render_t6_assumptions(assumptions_doc, snapshot.get('assumptions'), transmission_contract=transmission_contract)}<!--/TAB:T6-->\n"
        f"</div>\n"
        f"{LABAN_END}"
    )


def split_tabs(block: str) -> dict[str, str]:
    """Extract TAB sections from laban block for panel placement."""
    import re

    out = {}
    for name in ("T1", "T2", "T3", "T4", "T6"):
        m = re.search(
            rf"<!--TAB:{name}-->([\s\S]*?)<!--/TAB:{name}-->", block
        )
        out[name] = m.group(1) if m else ""
    return out
