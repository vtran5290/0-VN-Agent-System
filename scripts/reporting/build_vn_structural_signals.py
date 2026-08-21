#!/usr/bin/env python
"""Render VN structural-shift signals + La Bàn engine views; inject into tollbooth tracker.

Display/advisory only. Reads data/decision/*.json, computes freshness / working weights /
frame diagnostics, emits fragments, and idempotently injects into
reports/tollbooth_tracker_latest.html between marker comments.

Design constraints (2026-08-01 + La Bàn v2.0 2026-08-02):

* FOUR-STATE CONTRACT. Missing → NOT_RUN; never a substantive fake reading.
* NO AUTO-FETCH. Operator-maintained observations.
* NO EXPOSURE DIRECTIVES / no OMS feed.
* La Bàn weights: ConvergedDesign §2 (recompute-from-anchors, zero-sum maps, cluster cap,
  ±7pp clip, FRAME-TENSION, cold-start null, refuse-to-publish).
* stdlib only. utf-8 everywhere.

Usage:
    python scripts/reporting/build_vn_structural_signals.py
    python scripts/reporting/build_vn_structural_signals.py --inject
    python scripts/reporting/build_vn_structural_signals.py --as-of 2026-09-01 --inject
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "reporting"))

from laban_engine import (  # noqa: E402
    EXTRAORDINARY_MSG,
    MODEL_CONTRADICTION_MSG,
    ModelContradiction,
    dumps_stable,
    load_json,
    run_engine,
)
from laban_render import (  # noqa: E402
    LABAN_BEGIN,
    LABAN_END,
    render_laban_block,
    split_tabs,
)
from rate_pivot_transmission import normalize_transmission_contract  # noqa: E402

SIGNALS_PATH = REPO / "data" / "decision" / "vn_structural_signals.json"
SCENARIOS_PATH = REPO / "data" / "decision" / "laban_scenarios.json"
SIGNATURES_PATH = REPO / "data" / "decision" / "laban_signatures.json"
AXIS_PATH = REPO / "data" / "decision" / "laban_axis_state.json"
FRAME_LOG_PATH = REPO / "data" / "decision" / "laban_frame_log.json"
KILL_PATH = REPO / "data" / "decision" / "laban_kill_conditions.json"
ASSUMPTIONS_PATH = REPO / "data" / "decision" / "laban_thesis_assumptions.json"
ADVISORY_LINKS_PATH = REPO / "data" / "decision" / "laban_advisory_links.json"
RATE_PIVOT_MONITOR_PATH = REPO / "data" / "research" / "rate_pivot_monitor.json"
SNAPSHOT_PATH = REPO / "data" / "decision" / "laban_engine_snapshot.json"
FRAGMENT_PATH = REPO / "reports" / "vn_structural_signals_fragment.html"
TOLLBOOTH_PATH = REPO / "reports" / "tollbooth_tracker_latest.html"

# Staged shell-rebuild contract (2026-08-10, ChatGPT REDIRECT on
# 2026-08-10-1251_ReviewPack_ReportSuiteOrchestrator.md — see decision file
# Chatgpt/responses/2026-08-10_ReportSuiteOrchestrator_Decision.md). The shell writer
# (rebuild_laban_html_shell.py) NEVER writes tollbooth_tracker_latest.html directly — it
# writes here, stamped SHELL_ONLY. This module's --publish-shell mode is the only path
# permitted to turn a SHELL_ONLY staging file into a new tollbooth_tracker_latest.html,
# and it does so via inject + verify + atomic replace, never a direct overwrite.
STAGING_PATH = REPO / "reports" / ".build" / "tollbooth_tracker.shell_only.html"
STATE_SENTINEL_RE = re.compile(r"<!-- LABAN_BUILD_STATE:(\w+) -->")
STATE_SHELL_ONLY = "SHELL_ONLY"
STATE_INJECTED = "INJECTED"

BEGIN = "<!-- VN_STRUCTURAL_SIGNALS:BEGIN -->"
END = "<!-- VN_STRUCTURAL_SIGNALS:END -->"

T1_BEGIN, T1_END = "<!-- LABAN_T1:BEGIN -->", "<!-- LABAN_T1:END -->"
T2_BEGIN, T2_END = "<!-- LABAN_T2:BEGIN -->", "<!-- LABAN_T2:END -->"
T3_BEGIN, T3_END = "<!-- LABAN_T3:BEGIN -->", "<!-- LABAN_T3:END -->"
T4_BEGIN, T4_END = "<!-- LABAN_T4:BEGIN -->", "<!-- LABAN_T4:END -->"
T6_BEGIN, T6_END = "<!-- LABAN_T6:BEGIN -->", "<!-- LABAN_T6:END -->"
_REQUIRED_TAB_MARKERS = {
    "T1": (T1_BEGIN, T1_END),
    "T2": (T2_BEGIN, T2_END),
    "T3": (T3_BEGIN, T3_END),
    "T4": (T4_BEGIN, T4_END),
    "T6": (T6_BEGIN, T6_END),
}

ADVISORY = (
    "Tín hiệu dịch chuyển cấu trúc — quan sát thủ công, tần suất theo nguồn công bố · "
    "hiển thị/tham khảo · KHÔNG nuôi tín hiệu giao dịch, universe hay OMS · as-of {date}"
)

STATUS_STYLE = {
    "FRESH": ("#00c896", "Trong hạn"),
    "STALE": ("#f0a030", "Quá hạn công bố"),
    "NOT_RUN": ("#6b7280", "Chưa có quan sát"),
}

THESIS_LABEL = {
    "infrastructure-for-automation": "Hạ tầng cho tự động hóa",
    "supply-chain-diversification": "Đa dạng hóa chuỗi cung",
    "value-retention": "Giữ lại giá trị",
    "upstream-migration": "Dịch lên thượng nguồn",
    "inputs-vs-capex": "Nguyên liệu vs capex",
}


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def evaluate(sig: dict, today: date) -> dict:
    obs = [o for o in (sig.get("observations") or []) if _parse_date(o.get("as_of"))]
    obs.sort(key=lambda o: _parse_date(o["as_of"]))

    if not obs:
        return {"status": "NOT_RUN", "latest": None, "prev": None, "delta": None, "age_days": None}

    latest = obs[-1]
    prev = obs[-2] if len(obs) > 1 else None
    age = (today - _parse_date(latest["as_of"])).days
    cadence = int(sig.get("cadence_days") or 31)
    status = "STALE" if age > cadence + 45 else "FRESH"

    delta = None
    if prev is not None and isinstance(latest.get("value"), (int, float)) and isinstance(
        prev.get("value"), (int, float)
    ):
        delta = round(float(latest["value"]) - float(prev["value"]), 2)

    return {"status": status, "latest": latest, "prev": prev, "delta": delta, "age_days": age}


def _direction_cell(sig: dict, ev: dict) -> str:
    if ev["delta"] is None:
        return '<span style="color:#4a5168">— cần ≥2 quan sát</span>'
    d = ev["delta"]
    good_up = sig.get("direction_good") == "up"
    if d == 0:
        return '<span style="color:#8b9eb8">đi ngang</span>'
    improving = (d > 0) if good_up else (d < 0)
    colour = "#00c896" if improving else "#f05050"
    word = "cải thiện" if improving else "xấu đi"
    return f'<span style="color:{colour}">{d:+.2f} · {word}</span>'


def render(signals: list[dict], today: date) -> str:
    rows = []
    for sig in signals:
        ev = evaluate(sig, today)
        colour, status_text = STATUS_STYLE[ev["status"]]
        latest = ev["latest"]

        if latest is None:
            val_cell = '<span style="color:#4a5168">—</span>'
            asof_cell = '<span style="color:#4a5168">—</span>'
        else:
            unit = "pp" if sig.get("unit") == "pp" else "%"
            val_cell = f'<strong>{float(latest["value"]):+.1f}{unit}</strong>'
            asof_cell = escape(str(latest["as_of"]))

        note = escape(str((latest or {}).get("note", "")))
        rows.append(
            "<tr>"
            f'<td><div style="font-weight:600">{escape(sig["label"])}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-top:2px">'
            f'{escape(THESIS_LABEL.get(sig.get("thesis",""), sig.get("thesis","")))}</div></td>'
            f'<td class="mono num">{val_cell}</td>'
            f'<td class="mono">{asof_cell}</td>'
            f'<td>{_direction_cell(sig, ev)}</td>'
            f'<td><span style="color:{colour};font-weight:600">{status_text}</span></td>'
            f'<td style="font-size:11px;color:#8b9eb8">{escape(sig.get("benchmark_label",""))}'
            + (f'<div style="margin-top:4px;color:#6b7280">{note}</div>' if note else "")
            + f'<div style="margin-top:4px;font-size:10px;color:#4a5168">Nguồn: '
            f'{escape(sig.get("source",""))}</div></td>'
            "</tr>"
        )

    counts = {}
    for sig in signals:
        st = evaluate(sig, today)["status"]
        counts[st] = counts.get(st, 0) + 1
    summary = " · ".join(
        f'<span style="color:{STATUS_STYLE[k][0]}">{v} {STATUS_STYLE[k][1].lower()}</span>'
        for k, v in sorted(counts.items())
    )

    return f"""{BEGIN}
<div class="card">
  <h3>Tín hiệu dịch chuyển cấu trúc VN</h3>
  <p style="font-size:12px;color:#9ca3af;margin:0 0 4px">{escape(ADVISORY.format(date=today.isoformat()))}</p>
  <p style="font-size:11px;color:#6b7280;margin:0 0 12px">{summary}</p>
  <div style="overflow-x:auto">
  <table style="width:100%;border-collapse:collapse;font-size:12px;min-width:640px">
    <thead><tr>
      <th style="text-align:left">Tín hiệu</th>
      <th style="text-align:right">Mới nhất</th>
      <th style="text-align:left">As-of</th>
      <th style="text-align:left">Chiều</th>
      <th style="text-align:left">Trạng thái</th>
      <th style="text-align:left">Mốc &amp; ghi chú</th>
    </tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>
  </div>
  <p style="font-size:10px;color:#4a5168;margin-top:10px">
    Cập nhật: sửa <code>data/decision/vn_structural_signals.json</code> → chạy
    <code>python scripts/reporting/build_vn_structural_signals.py --inject</code>.
    Chiều tính so với quan sát TRƯỚC ĐÓ, không so với mốc. Không có quan sát → NOT_RUN,
    không bao giờ hiển thị thành một phán đọc.
  </p>
</div>
{END}"""


def _replace_markers(html: str, begin: str, end: str, body: str) -> str:
    if begin in html and end in html:
        head, rest = html.split(begin, 1)
        _, tail = rest.split(end, 1)
        return head + begin + "\n" + body + "\n" + end + tail
    return html


def _apply_injection(html: str, fragment: str, laban_tabs: dict[str, str]) -> tuple[str, str]:
    """Pure in-memory transform: signals block + La Bàn tabs + engine dump.

    Shared by both write paths (`inject`, direct-to-final; `publish_shell`,
    staged) so the two can never drift apart on what "injected" means.
    """
    if BEGIN in html and END in html:
        head, rest = html.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        html = head + fragment + tail
        action = "replaced signals block"
    else:
        action = "signals markers missing — skipped signals inject"

    # La Bàn tab bodies
    html = _replace_markers(html, T1_BEGIN, T1_END, laban_tabs.get("T1", ""))
    html = _replace_markers(html, T2_BEGIN, T2_END, laban_tabs.get("T2", ""))
    html = _replace_markers(html, T3_BEGIN, T3_END, laban_tabs.get("T3", ""))
    html = _replace_markers(html, T4_BEGIN, T4_END, laban_tabs.get("T4", ""))
    html = _replace_markers(html, T6_BEGIN, T6_END, laban_tabs.get("T6", ""))

    # Full engine dump (audit) between LABAN_ENGINE markers
    engine_body = (
        f'<script type="application/json" id="laban-engine-json">'
        f'/* snapshot also at data/decision/laban_engine_snapshot.json */</script>'
    )
    if LABAN_BEGIN in html and LABAN_END in html:
        html = _replace_markers(html, LABAN_BEGIN, LABAN_END, engine_body)

    return html, action


def inject(fragment: str, laban_tabs: dict[str, str], path: Path) -> str:
    """Refresh signal/engine content directly on the CURRENT final tollbooth file.

    Non-destructive by construction: `_replace_markers` only ever swaps what is
    between an existing BEGIN/END pair, regardless of what was there before (placeholder
    or prior real content) — it never touches the page shell/template. This is the safe,
    routine, run-as-often-as-you-like path (daily data refresh). It is NOT the operation
    that caused the 2026-08-09 T6 incident — that was rebuild_laban_html_shell.py
    unconditionally regenerating the whole page from a hardcoded template. See
    `publish_shell()` for the guarded path that follows a shell rebuild.
    """
    html = path.read_text(encoding="utf-8")
    html, action = _apply_injection(html, fragment, laban_tabs)
    path.write_text(html, encoding="utf-8")
    return action


def publish_shell(fragment: str, laban_tabs: dict[str, str]) -> str:
    """Staged publish: SHELL_ONLY staging file -> verified INJECTED -> atomic replace.

    Only path permitted to turn a fresh rebuild_laban_html_shell.py output into the
    live tollbooth_tracker_latest.html. Refuses loudly (raises SystemExit, final file
    untouched) if the staging file is missing, unreadable, or not stamped SHELL_ONLY —
    this is the state-machine ChatGPT's 2026-08-10 REDIRECT specified in place of the
    original (flawed) "inspect the current final file" guard, which would have tripped
    on every ordinary second build since a healthy final file is always left INJECTED.
    """
    if not STAGING_PATH.is_file():
        raise SystemExit(
            f"ERROR: no staging file at {STAGING_PATH} — run "
            "rebuild_laban_html_shell.py first (it writes there, never to the final file)."
        )
    html = STAGING_PATH.read_text(encoding="utf-8")

    m = STATE_SENTINEL_RE.search(html)
    state = m.group(1) if m else None
    if state != STATE_SHELL_ONLY:
        raise SystemExit(
            f"ERROR: staging file at {STAGING_PATH} is not stamped {STATE_SHELL_ONLY} "
            f"(found: {state!r}). Refusing to publish — this file may be stale, "
            "already-published, or hand-edited. Delete it and re-run "
            "rebuild_laban_html_shell.py to get a fresh SHELL_ONLY staging file. "
            "Final tollbooth_tracker_latest.html was NOT touched."
        )

    html, action = _apply_injection(html, fragment, laban_tabs)

    # Structural verification (two-sided non-vacuity: this must fire if a required tab
    # marker pair vanished from the template, and stay silent on a normal build). We do
    # NOT check against placeholder wording (ChatGPT flag #2: "placeholder text is not a
    # state machine" — presentation copy can change independently of build state).
    missing, empty = [], []
    for name, (b, e) in _REQUIRED_TAB_MARKERS.items():
        if b not in html or e not in html:
            missing.append(name)
            continue
        body = html.split(b, 1)[1].split(e, 1)[0].strip()
        if not body:
            empty.append(name)
    if missing:
        raise SystemExit(
            f"ERROR: staging file is missing required tab marker(s) {missing} — this is "
            "exactly the 2026-08-09 T6-disappears failure mode. Fix "
            "rebuild_laban_html_shell.py's template, do not publish. Final untouched."
        )
    if empty:
        raise SystemExit(
            f"ERROR: injected tab body empty for {empty} after _apply_injection — "
            "publish refused. Final untouched."
        )

    html = STATE_SENTINEL_RE.sub(f"<!-- LABAN_BUILD_STATE:{STATE_INJECTED} -->", html, count=1)

    # Atomic publish: write to a same-directory temp file, then os.replace (atomic
    # single-file rename on both POSIX and Windows) onto the live path. The last
    # known-good tollbooth_tracker_latest.html is preserved on disk at every instant
    # until the moment the new one is fully verified and ready (ChatGPT risk flag #4).
    tmp_path = TOLLBOOTH_PATH.with_suffix(f".tmp-{os.getpid()}.html")
    tmp_path.write_text(html, encoding="utf-8")
    os.replace(tmp_path, TOLLBOOTH_PATH)

    STAGING_PATH.unlink()  # consumed — no reuse, no stale SHELL_ONLY state to trip over
    return f"{action}; published {STAGING_PATH.name} -> {TOLLBOOTH_PATH.name} (atomic)"


def _append_weight_snapshot(frame_log: dict, snapshot: dict) -> dict:
    """Append-only weight snapshot when a published change occurs."""
    w = snapshot.get("weights") or {}
    if not w.get("published"):
        return frame_log
    snaps = list(frame_log.get("weight_snapshots") or [])
    entry = {
        "as_of": snapshot.get("as_of"),
        "working": w.get("working"),
        "anchors": w.get("anchors"),
        "status": w.get("status"),
    }
    # Idempotency against ANY existing identical snapshot, not just the last one — the test
    # suite runs the live builder with --as-of 2026-08-02 between real runs, so writers
    # alternate as_of values and a last-entry-only dedup appends forever (observed: 8
    # oscillating duplicates on 2026-08-03).
    for s in snaps:
        if s.get("working") == entry["working"] and s.get("as_of") == entry["as_of"]:
            return frame_log
    snaps.append(entry)
    frame_log = dict(frame_log)
    frame_log["weight_snapshots"] = snaps
    frame_log["last_valid_weight_snapshot"] = entry
    return frame_log


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="VN structural signals + La Bàn engine (display-only)")
    ap.add_argument("--as-of", dest="as_of", default=None, help="YYYY-MM-DD (default: today)")
    _inject_group = ap.add_mutually_exclusive_group()
    _inject_group.add_argument(
        "--inject", action="store_true",
        help="Routine data refresh: patch tollbooth_tracker_latest.html in place "
             "(safe, non-destructive, run as often as you like).",
    )
    _inject_group.add_argument(
        "--publish-shell", action="store_true",
        help="Staged publish: consume the SHELL_ONLY staging file left by "
             "rebuild_laban_html_shell.py, verify, and atomically replace "
             "tollbooth_tracker_latest.html. Run this ONLY after a shell rebuild.",
    )
    ap.add_argument("--signals", default=str(SIGNALS_PATH))
    ap.add_argument("--skip-laban", action="store_true", help="Signals fragment only (legacy)")
    args = ap.parse_args()

    today = date.fromisoformat(args.as_of) if args.as_of else date.today()

    src = Path(args.signals)
    if not src.is_file():
        print(f"ERROR: signals file not found: {src}", file=sys.stderr)
        return 2
    data = json.loads(src.read_text(encoding="utf-8"))
    signals = data.get("signals") or []
    if not signals:
        print("ERROR: no signals defined", file=sys.stderr)
        return 2

    for sig in signals:
        ev = evaluate(sig, today)
        n = len(sig.get("observations") or [])
        print(f"  {sig['id']:<34} {ev['status']:<8} obs={n} age={ev['age_days']}")

    fragment = render(signals, today)
    FRAGMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRAGMENT_PATH.write_text(fragment, encoding="utf-8")
    print(f"WROTE {FRAGMENT_PATH}")

    laban_tabs = {"T1": "", "T2": "", "T3": "", "T4": "", "T6": ""}
    if not args.skip_laban:
        for p in (SCENARIOS_PATH, SIGNATURES_PATH, AXIS_PATH, FRAME_LOG_PATH):
            if not p.is_file():
                print(f"ERROR: missing La Bàn data file: {p}", file=sys.stderr)
                return 2
        scenarios = load_json(SCENARIOS_PATH)
        signatures = load_json(SIGNATURES_PATH)
        axis_state = load_json(AXIS_PATH)
        frame_log = load_json(FRAME_LOG_PATH)
        kill_doc = load_json(KILL_PATH) if KILL_PATH.is_file() else {"rows": []}
        assumptions_doc = (
            load_json(ASSUMPTIONS_PATH) if ASSUMPTIONS_PATH.is_file() else None
        )
        advisory_links_doc = (
            load_json(ADVISORY_LINKS_PATH) if ADVISORY_LINKS_PATH.is_file() else None
        )

        # Structural assertion (Round 7, 2026-08-09, dual-judge REDIRECT — "reference, not
        # containment"): advisory content must NEVER be persisted inside the axis object
        # itself, and must never leak into scoring-relevant keys. Fails loud, not silent.
        for _ax in axis_state.get("axes") or []:
            if "advisory_links" in _ax:
                print(
                    f"ERROR: laban_axis_state.json axis '{_ax.get('axis_id')}' carries a "
                    "persisted 'advisory_links' key — containment is forbidden post-Round-7 "
                    "(see 05_AI_Handoffs/2026-08-09-1100_ReviewPack_AdvisoryLinksUIPlacement.md). "
                    "Move it to laban_advisory_links.json with an axis_refs pointer instead.",
                    file=sys.stderr,
                )
                return 2
        _scoring_keys = {"evidence_basis", "state", "coverage", "confidence"}
        for _al in (advisory_links_doc or {}).get("advisory_links") or []:
            _leak = _scoring_keys & set(_al.keys())
            if _leak:
                print(
                    f"ERROR: laban_advisory_links.json entry '{_al.get('id')}' declares "
                    f"scoring-reserved key(s) {_leak} — advisory links may only carry "
                    "*_effect: NONE fields, never the scoring keys themselves.",
                    file=sys.stderr,
                )
                return 2

        if frame_log.get("extraordinary_event"):
            print(EXTRAORDINARY_MSG, file=sys.stderr)

        try:
            snapshot = run_engine(
                scenarios,
                signatures,
                data,
                axis_state,
                frame_log,
                as_of=today.isoformat(),
                kill_doc=kill_doc,
                assumptions_doc=assumptions_doc,
            )
        except ModelContradiction as e:
            print(e.message, file=sys.stderr)
            # Keep last valid snapshot on disk / page — do not overwrite with bad weights
            if SNAPSHOT_PATH.is_file():
                print(f"KEPT last valid snapshot {SNAPSHOT_PATH}", file=sys.stderr)
            return 3

        transmission_contract = normalize_transmission_contract(
            load_json(RATE_PIVOT_MONITOR_PATH) if RATE_PIVOT_MONITOR_PATH.is_file() else {}
        )

        w = snapshot["weights"]
        print(f"LABAN status={w['status']} published={w['published']} "
              f"n_valid={w['n_valid_obs']} n_axes={w['n_axes_covered']}")

        # Persist kill-condition breach streaks (success path only). Streaks count DISTINCT
        # observations — the evaluator only advances on a new as_of — so writing back here
        # keeps multi-cycle conditions alive across runs while repeat runs stay byte-stable.
        if kill_doc and KILL_PATH.is_file():
            _res_by_id = {
                r.get("kill_condition_id"): r
                for r in (snapshot.get("kill_conditions") or {}).get("rows") or []
            }
            _kill_changed = False
            for _row in kill_doc.get("rows") or []:
                _res = _res_by_id.get(_row.get("kill_condition_id"))
                if not _res or "breach_streak" not in _res:
                    continue
                # last_evaluated deliberately NOT persisted — it lives in the snapshot; writing
                # it here would churn the file every time a different as_of runs (tests use
                # --as-of 2026-08-02 against live files).
                for _k in ("breach_streak", "last_obs_as_of"):
                    if _row.get(_k) != _res.get(_k):
                        _row[_k] = _res.get(_k)
                        _kill_changed = True
            if _kill_changed:
                KILL_PATH.write_text(
                    json.dumps(kill_doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"WROTE {KILL_PATH} (breach streaks persisted)")

        frame_log2 = _append_weight_snapshot(frame_log, snapshot)
        if frame_log2 is not frame_log:
            FRAME_LOG_PATH.write_text(dumps_stable(frame_log2), encoding="utf-8")

        SNAPSHOT_PATH.write_text(dumps_stable(snapshot), encoding="utf-8")
        print(f"WROTE {SNAPSHOT_PATH}")

        block = render_laban_block(
            snapshot, scenarios, signatures, data,
            frame_log2 if frame_log2 else frame_log,
            assumptions_doc=assumptions_doc,
            advisory_links_doc=advisory_links_doc,
            transmission_contract=transmission_contract,
        )
        laban_tabs = split_tabs(block)
        if w.get("working") is None:
            for k, v in laban_tabs.items():
                if "Working" in v:
                    raise SystemExit(
                        "ERROR: cold-start render leaked capital-W 'Working' "
                        f"into tab {k} — fix laban_render.py"
                    )

    if args.inject:
        if not TOLLBOOTH_PATH.is_file():
            print(f"ERROR: tracker not found: {TOLLBOOTH_PATH}", file=sys.stderr)
            return 2
        print(f"INJECT {TOLLBOOTH_PATH}: {inject(fragment, laban_tabs, TOLLBOOTH_PATH)}")
    elif args.publish_shell:
        # publish_shell() raises SystemExit with a clear message on any refusal —
        # let it propagate (main() is already wrapped by `raise SystemExit(main())`).
        print(f"PUBLISH-SHELL: {publish_shell(fragment, laban_tabs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
