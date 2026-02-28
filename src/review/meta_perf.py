"""
Meta performance dashboard for trades: Process × R × Regime.

Reads monthly diagnostic + canonical input; writes:
- data/decision/meta_perf_YYYY-MM.json
- data/decision/meta_perf_latest.json
- optional .md when --render
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import DECISION_DIR, REPO

logger = logging.getLogger(__name__)

TRADE_INPUT = DECISION_DIR / "trade_review_input.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_policy() -> Dict[str, Any]:
    policy_path = DECISION_DIR / "review_policy.json"
    default_meta = {
        "weights": {"stop_present": 0.4, "stop_manual": 0.2, "reason_tag": 0.4},
        "r_coverage_min": 0.7,
        "missing_thresholds": {"red": 0.5, "yellow": 0.2},
        "manual_share_min": 0.3,
        "regime_map": {"B": "under_pressure"},
    }
    if not policy_path.exists():
        return {
            "min_sample_to_act": 10,
            "meta_perf": default_meta,
        }
    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "min_sample_to_act": 10,
            "meta_perf": default_meta,
        }
    meta_cfg = data.get("meta_perf") or {}
    # ensure defaults without overwriting existing keys
    for k, v in default_meta.items():
        meta_cfg.setdefault(k, v)
    data["meta_perf"] = meta_cfg
    if "min_sample_to_act" not in data:
        data["min_sample_to_act"] = 10
    return data


def _label_from_rate(present_rate: Optional[float], thresholds: Dict[str, float]) -> str:
    if present_rate is None:
        return "RED"
    missing = 1.0 - float(present_rate)
    red_th = float(thresholds.get("red", 0.5))
    yellow_th = float(thresholds.get("yellow", 0.2))
    if missing >= red_th:
        return "RED"
    if missing >= yellow_th:
        return "YELLOW"
    return "GREEN"


def _collect_r_and_context(
    trades: List[Dict[str, Any]],
    regime_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[float], List[Dict[str, Any]]]:
    r_values: List[float] = []
    ctx_rows: List[Dict[str, Any]] = []
    for t in trades:
        risk = t.get("risk") or {}
        r = risk.get("r_multiple")
        if r is not None:
            try:
                r_val = float(r)
                ctx = t.get("context") or {}
                raw_reg = ctx.get("regime_at_entry") or "unknown"
                norm_reg = raw_reg
                if regime_map:
                    norm_reg = regime_map.get(raw_reg, raw_reg)
                # Normalize into a small set; unknown codes fall back to "unknown"
                if norm_reg not in ("confirmed", "under_pressure", "correction", "unknown"):
                    norm_reg = "unknown"
                r_values.append(r_val)
                ctx_rows.append(
                    {
                        "r": r_val,
                        "regime_at_entry": norm_reg,
                        "regime_at_entry_raw": raw_reg,
                        "risk_flag_at_entry": ctx.get("risk_flag_at_entry") or "unknown",
                        "dist_days_20_at_entry": ctx.get("dist_days_20_at_entry"),
                        "stop_source": (risk.get("stop_source") or "unknown").lower(),
                    }
                )
            except (TypeError, ValueError):
                continue
    return r_values, ctx_rows


def _edge_r_distribution(r_values: List[float]) -> Dict[str, Any]:
    n_closed = len(r_values)
    if n_closed == 0:
        return {
            "n_closed": 0,
            "n_with_r": 0,
            "win_rate": None,
            "avg_R": None,
            "median_R": None,
            "p25_R": None,
            "p75_R": None,
            "tail_R_min": None,
            "tail_3_avg": None,
        }
    vals = sorted(r_values)
    n = len(vals)
    avg_R = sum(vals) / n
    mid = n // 2
    median_R = (vals[mid] + vals[mid - 1]) / 2 if n > 1 else vals[0]
    def _pct(p: float) -> float:
        if n == 1:
            return vals[0]
        k = max(0, min(n - 1, int(p * (n - 1))))
        return vals[k]
    p25 = _pct(0.25)
    p75 = _pct(0.75)
    tail_min = vals[0]
    tail_3 = vals[:3]
    tail_3_avg = sum(tail_3) / len(tail_3) if len(tail_3) == 3 else None
    win_rate = sum(1 for v in vals if v > 0) / n
    return {
        "n_closed": n,
        "n_with_r": n,
        "win_rate": round(win_rate, 4),
        "avg_R": round(avg_R, 4),
        "median_R": round(median_R, 4),
        "p25_R": round(p25, 4),
        "p75_R": round(p75, 4),
        "tail_R_min": round(tail_min, 4),
        "tail_3_avg": round(tail_3_avg, 4) if tail_3_avg is not None else None,
    }


def _bucket_dist(dist: Any) -> str:
    if dist is None:
        return "unknown"
    try:
        v = float(dist)
    except (TypeError, ValueError):
        return "unknown"
    if v <= 2:
        return "0-2"
    if v <= 4:
        return "3-4"
    return "5+"


def _group_stats(rows: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, List[float]] = {}
    for r in rows:
        k = str(r.get(key) or "unknown")
        groups.setdefault(k, []).append(r["r"])
    out: Dict[str, Dict[str, Any]] = {}
    for g, vals in groups.items():
        n = len(vals)
        avg_R = sum(vals) / n if n else None
        win_rate = sum(1 for v in vals if v > 0) / n if n else None
        out[g] = {
            "n": n,
            "n_with_r": n,
            "avg_R": round(avg_R, 4) if avg_R is not None else None,
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
        }
    return out


def _build_meta_perf(month: str, render: bool = False) -> Dict[str, Any]:
    diag_path = DECISION_DIR / f"trade_diagnostic_{month}.json"
    diagnostic = _load_json(diag_path)
    input_data = _load_json(TRADE_INPUT)
    policy = _load_policy()

    summary = diagnostic.get("summary_stats") or {}
    n_closed = summary.get("n_closed") or 0
    stop_present_rate = summary.get("stop_present_rate")
    stop_manual_rate = summary.get("stop_manual_rate")
    reason_present_rate = summary.get("reason_tag_present_rate")

    meta_cfg = policy.get("meta_perf") or {}
    weights = meta_cfg.get("weights") or {"stop_present": 0.4, "stop_manual": 0.2, "reason_tag": 0.4}
    missing_th = meta_cfg.get("missing_thresholds") or {"red": 0.5, "yellow": 0.2}
    regime_map = meta_cfg.get("regime_map") or {}

    stop_label = _label_from_rate(stop_present_rate, missing_th)
    manual_label = _label_from_rate(stop_manual_rate, missing_th)
    reason_label = _label_from_rate(reason_present_rate, missing_th)

    def _score(rate: Optional[float]) -> float:
        if rate is None:
            return 0.0
        return max(0.0, min(1.0, float(rate)))

    comp_score = (
        _score(stop_present_rate) * float(weights.get("stop_present", 0.4))
        + _score(stop_manual_rate) * float(weights.get("stop_manual", 0.2))
        + _score(reason_present_rate) * float(weights.get("reason_tag", 0.4))
    )
    comp_score = round(comp_score * 100, 1)

    # Overall label = worst of three
    overall = "GREEN"
    for lab in (stop_label, manual_label, reason_label):
        if lab == "RED":
            overall = "RED"
            break
        if lab == "YELLOW" and overall != "RED":
            overall = "YELLOW"

    trades = input_data.get("trades_closed") or []
    r_values, ctx_rows = _collect_r_and_context(trades, regime_map=regime_map)
    n_with_r = len(r_values)
    r_coverage_rate = (n_with_r / n_closed) if n_closed else None
    # manual share among r-multiple trades
    manual_r = sum(1 for r in ctx_rows if r.get("stop_source") == "manual")
    r_manual_share = (manual_r / n_with_r) if n_with_r else None

    # Dual edge: all stops vs manual-only
    r_dist_all = _edge_r_distribution(r_values)
    r_dist_all["note"] = "all_stops"
    manual_r_values = [row["r"] for row in ctx_rows if row.get("stop_source") == "manual"]
    r_dist_manual = _edge_r_distribution(manual_r_values)
    r_dist_manual["note"] = "manual_only"
    # Low sample warning for manual-only edge
    manual_n = r_dist_manual.get("n_with_r") or 0
    manual_low_sample = manual_n and manual_n < 3
    if manual_low_sample:
        for k in ("win_rate", "avg_R", "median_R", "p25_R", "p75_R", "tail_R_min", "tail_3_avg"):
            r_dist_manual[k] = None

    # Regime interaction (normalized + raw)
    by_regime_norm = _group_stats(ctx_rows, "regime_at_entry")
    by_regime_raw = _group_stats(ctx_rows, "regime_at_entry_raw")
    by_risk_flag = _group_stats(ctx_rows, "risk_flag_at_entry")
    # add dist bucket
    rows_with_bucket = []
    for r in ctx_rows:
        r2 = dict(r)
        r2["dist_bucket"] = _bucket_dist(r2.pop("dist_days_20_at_entry"))
        rows_with_bucket.append(r2)
    by_dist = _group_stats(rows_with_bucket, "dist_bucket")

    min_sample_to_act = policy.get("min_sample_to_act", 10)
    r_cov_min = float(meta_cfg.get("r_coverage_min", 0.7))
    manual_share_min = float(meta_cfg.get("manual_share_min", 0.3))

    gate_cfg = policy.get("process_gate") or {}
    sp_min = float(gate_cfg.get("stop_present_min", 0.7))
    rt_min = float(gate_cfg.get("reason_tag_present_min", 0.8))
    sm_min = float(gate_cfg.get("stop_manual_min", 0.3))

    # Primary process gate from thresholds (stop_present + reason_tag)
    present_ok_stop = stop_present_rate is not None and stop_present_rate >= sp_min
    present_ok_reason = reason_present_rate is not None and reason_present_rate >= rt_min
    process_gate_on = not (present_ok_stop and present_ok_reason)

    # Secondary manual-stop gate
    manual_ok = stop_manual_rate is not None and stop_manual_rate >= sm_min
    manual_stop_gate_on = (not process_gate_on) and not manual_ok

    # Caution reasons
    caution_reasons: List[str] = []
    if process_gate_on:
        caution_reasons.append("process_gate_on")
    if manual_stop_gate_on:
        caution_reasons.append("manual_stop_gate_on")
    if r_coverage_rate is not None and r_coverage_rate < r_cov_min:
        caution_reasons.append("low_r_coverage")
    if n_closed < min_sample_to_act:
        caution_reasons.append("low_sample")
    if r_manual_share is not None and r_manual_share < manual_share_min:
        caution_reasons.append("low_manual_stop_share")

    interpret_with_caution = bool(
        process_gate_on
        or manual_stop_gate_on
        or ("low_r_coverage" in caution_reasons)
        or ("low_sample" in caution_reasons)
    )

    data_quality = {
        "process_gate_on": process_gate_on,
        "manual_stop_gate_on": manual_stop_gate_on,
        "interpret_with_caution": interpret_with_caution,
        "r_coverage_rate": round(r_coverage_rate, 4) if r_coverage_rate is not None else None,
        "r_manual_share": round(r_manual_share, 4) if r_manual_share is not None else None,
        "caution_reasons": caution_reasons,
    }

    process_compliance = {
        "stop_present_rate": stop_present_rate,
        "stop_manual_rate": stop_manual_rate,
        "reason_tag_present_rate": reason_present_rate,
        "compliance_score": comp_score,
        "labels": {
            "stop_present": stop_label,
            "stop_manual": manual_label,
            "reason_tag": reason_label,
            "overall": overall,
        },
    }

    # Top actions (max 3) — KPI objects
    from datetime import datetime as _dt

    try:
        y, m = int(month[:4]), int(month[5:7])
        if m == 12:
            next_month = f"{y+1}-01"
        else:
            next_month = f"{y}-{m+1:02d}"
    except Exception:
        next_month = month

    top_actions: List[Dict[str, Any]] = []
    gate_for_actions = process_gate_on or manual_stop_gate_on or overall != "GREEN"

    if gate_for_actions:
        if stop_present_rate is not None and stop_present_rate < sp_min:
            top_actions.append(
                {
                    "priority": "P0",
                    "type": "process",
                    "metric": "stop_present_rate",
                    "current": stop_present_rate,
                    "target": sp_min,
                    "deadline": next_month,
                    "action": f"Raise stop_present_rate to ≥ {sp_min:.0%} before changing strategy.",
                }
            )
        if reason_present_rate is not None and reason_present_rate < rt_min:
            top_actions.append(
                {
                    "priority": "P0",
                    "type": "process",
                    "metric": "reason_tag_present_rate",
                    "current": reason_present_rate,
                    "target": rt_min,
                    "deadline": next_month,
                    "action": f"Raise reason_tag_present_rate to ≥ {rt_min:.0%} with controlled tags.",
                }
            )
        if stop_manual_rate is not None and stop_manual_rate < sm_min:
            top_actions.append(
                {
                    "priority": "P1",
                    "type": "process",
                    "metric": "stop_manual_rate",
                    "current": stop_manual_rate,
                    "target": sm_min,
                    "deadline": next_month,
                    "action": f"Increase manual stop recording to ≥ {sm_min:.0%} of trades.",
                }
            )
    else:
        # Allow one process + one execution + one risk action (facts-only)
        if reason_present_rate is not None and reason_present_rate < rt_min:
            top_actions.append(
                {
                    "priority": "P1",
                    "type": "process",
                    "metric": "reason_tag_present_rate",
                    "current": reason_present_rate,
                    "target": rt_min,
                    "deadline": next_month,
                    "action": f"Raise reason_tag_present_rate to ≥ {rt_min:.0%}.",
                }
            )
        if n_with_r and r_dist_all.get("avg_R") is not None and r_dist_all["avg_R"] < 0:
            top_actions.append(
                {
                    "priority": "P1",
                    "type": "execution",
                    "metric": "avg_R",
                    "current": r_dist_all["avg_R"],
                    "target": 0.0,
                    "deadline": next_month,
                    "action": "Review exit timing in regimes with negative avg_R; consider tighter sell rules there.",
                }
            )
        if by_regime_norm:
            worst_reg = min(
                by_regime_norm.items(),
                key=lambda kv: kv[1]["avg_R"] if kv[1]["avg_R"] is not None else 9999,
            )[0]
            worst_stats = by_regime_norm[worst_reg]
            top_actions.append(
                {
                    "priority": "P1",
                    "type": "risk",
                    "metric": "avg_R_by_regime",
                    "current": worst_stats.get("avg_R"),
                    "target": 0.0,
                    "deadline": next_month,
                    "action": f"Monitor positions more tightly when regime_at_entry='{worst_reg}' (avg_R low).",
                }
            )

    top_actions = top_actions[:3]
    top_actions_text = [a.get("action", "") for a in top_actions]

    # Watch items (max 3)
    watch_items: List[str] = []
    if caution_reasons:
        watch_items.append("Caution reasons: " + ", ".join(caution_reasons))
    if interpret_with_caution and len(watch_items) < 3:
        watch_items.append("Interpret edge metrics with caution: process or sample/coverage flags are ON.")
    if r_manual_share is not None and r_manual_share < manual_share_min and len(watch_items) < 3:
        watch_items.append("R metrics mostly based on system_default stops; manual stop share is low.")
    if by_regime_norm and len(watch_items) < 3:
        worst_reg, worst_stats = min(
            by_regime_norm.items(),
            key=lambda kv: kv[1]["avg_R"] if kv[1]["avg_R"] is not None else 9999,
        )
        if worst_stats.get("avg_R") is not None and worst_stats["avg_R"] < 0:
            watch_items.append(f"Losses concentrate when regime_at_entry='{worst_reg}' (avg_R={worst_stats['avg_R']}).")
    watch_items = watch_items[:3]

    warnings: List[str] = []
    if n_closed == 0:
        warnings.append("No closed trades in window; meta_perf limited to process + hygiene.")
    if n_with_r == 0 and n_closed > 0:
        warnings.append("No trades with r_multiple; R distribution metrics unavailable.")
    if manual_low_sample:
        warnings.append("manual_only_edge_low_sample")

    payload = {
        "asof_date": diagnostic.get("asof_date") or input_data.get("asof_date", ""),
        "month": month,
        "input_hash": input_data.get("input_hash", ""),
        "data_quality": data_quality,
        "process_compliance": process_compliance,
        "edge_r_distribution": r_dist_all,
        "edge_r_distribution_manual_only": r_dist_manual,
        "regime_interaction": {
            "by_regime_at_entry": by_regime_norm,
            "by_regime_at_entry_norm": by_regime_norm,
            "by_regime_at_entry_raw": by_regime_raw,
            "by_risk_flag_at_entry": by_risk_flag,
            "by_dist_days_bucket_at_entry": by_dist,
        },
        "top_actions": top_actions,
        "top_actions_text": top_actions_text,
        "watch_items": watch_items,
        "warnings": warnings,
    }

    # --- Multi-month trends (MoM + rolling 3M) ---
    # Gather up to last 3 months (current, prev1, prev2)
    def _month_back(m: str, k: int) -> str:
        y, mm = int(m[:4]), int(m[5:7])
        for _ in range(k):
            mm -= 1
            if mm == 0:
                y -= 1
                mm = 12
        return f"{y}-{mm:02d}"

    window_months = [month]
    window_months.insert(0, _month_back(month, 1))
    window_months.insert(0, _month_back(month, 2))

    hist: List[Tuple[str, Dict[str, Any]]] = []
    for m in sorted(set(window_months)):
        if m == month:
            hist.append((m, payload))
        else:
            mp = DECISION_DIR / f"meta_perf_{m}.json"
            if mp.exists():
                try:
                    hist.append((m, json.loads(mp.read_text(encoding="utf-8"))))
                except Exception:
                    continue

    hist.sort(key=lambda x: x[0])  # oldest -> newest
    n_hist = len(hist)

    # Month-on-month deltas (prev vs current)
    trends_mom: Dict[str, Any] = {"available": False, "prev_month": None, "deltas": {}}
    if n_hist >= 2:
        prev_month, prev_data = hist[-2]
        curr_month, curr_data = hist[-1]
        def _delta(path: List[str]) -> Dict[str, Optional[float]]:
            d_prev = prev_data
            d_curr = curr_data
            for key in path:
                d_prev = d_prev.get(key) if isinstance(d_prev, dict) else None
                d_curr = d_curr.get(key) if isinstance(d_curr, dict) else None
            prev_v = d_prev if isinstance(d_prev, (int, float)) else None
            curr_v = d_curr if isinstance(d_curr, (int, float)) else None
            if prev_v is None or curr_v is None:
                return {"prev": prev_v, "current": curr_v, "delta": None}
            return {"prev": prev_v, "current": curr_v, "delta": curr_v - prev_v}

        deltas = {
            "compliance_score": _delta(["process_compliance", "compliance_score"]),
            "avg_R_all": _delta(["edge_r_distribution", "avg_R"]),
            "avg_R_manual": _delta(["edge_r_distribution_manual_only", "avg_R"]),
        }
        trends_mom = {
            "available": True,
            "prev_month": prev_month,
            "deltas": deltas,
        }

    # Rolling 3M aggregates (use whatever months we have in hist, up to 3)
    agg: Dict[str, Optional[float]] = {
        "avg_R_all_weighted": None,
        "win_rate_all_weighted": None,
        "compliance_score_avg": None,
        "stop_present_rate_avg": None,
        "stop_manual_rate_avg": None,
        "reason_tag_present_rate_avg": None,
        "r_manual_share_avg": None,
    }
    series: Dict[str, List[Dict[str, Any]]] = {
        "stop_present_rate": [],
        "stop_manual_rate": [],
        "reason_tag_present_rate": [],
        "compliance_score": [],
        "avg_R_all": [],
        "avg_R_manual": [],
    }

    total_weight = 0.0
    sum_avgR = 0.0
    sum_win = 0.0
    comp_vals: Dict[str, List[float]] = {
        "stop_present_rate": [],
        "stop_manual_rate": [],
        "reason_tag_present_rate": [],
        "compliance_score": [],
        "r_manual_share": [],
    }

    for m, d in hist:
        ss = d.get("process_compliance") or {}
        dq_m = d.get("data_quality") or {}
        ed = d.get("edge_r_distribution") or {}
        edm = d.get("edge_r_distribution_manual_only") or {}

        # series
        series["stop_present_rate"].append({"month": m, "value": ss.get("stop_present_rate")})
        series["stop_manual_rate"].append({"month": m, "value": ss.get("stop_manual_rate")})
        series["reason_tag_present_rate"].append({"month": m, "value": ss.get("reason_tag_present_rate")})
        series["compliance_score"].append({"month": m, "value": ss.get("compliance_score")})
        series["avg_R_all"].append({"month": m, "value": ed.get("avg_R")})
        series["avg_R_manual"].append({"month": m, "value": edm.get("avg_R")})

        # compliance averages (simple means)
        for key in ("stop_present_rate", "stop_manual_rate", "reason_tag_present_rate", "compliance_score"):
            v = ss.get(key)
            if isinstance(v, (int, float)):
                comp_vals[key].append(float(v))
        v_rm = dq_m.get("r_manual_share")
        if isinstance(v_rm, (int, float)):
            comp_vals["r_manual_share"].append(float(v_rm))

        # weighted avg_R and win_rate (all stops)
        n_wr = ed.get("n_with_r") or 0
        avgR = ed.get("avg_R")
        win = ed.get("win_rate")
        if isinstance(avgR, (int, float)) and n_wr:
            w = float(n_wr)
            total_weight += w
            sum_avgR += float(avgR) * w
            if isinstance(win, (int, float)):
                sum_win += float(win) * w

    if total_weight > 0:
        agg["avg_R_all_weighted"] = round(sum_avgR / total_weight, 4)
        agg["win_rate_all_weighted"] = round(sum_win / total_weight, 4)

    for key, vals in comp_vals.items():
        if vals:
            mean_v = sum(vals) / len(vals)
            if key == "stop_present_rate":
                agg["stop_present_rate_avg"] = round(mean_v, 4)
            elif key == "stop_manual_rate":
                agg["stop_manual_rate_avg"] = round(mean_v, 4)
            elif key == "reason_tag_present_rate":
                agg["reason_tag_present_rate_avg"] = round(mean_v, 4)
            elif key == "compliance_score":
                agg["compliance_score_avg"] = round(mean_v, 1)
            elif key == "r_manual_share":
                agg["r_manual_share_avg"] = round(mean_v, 4)

    rolling_3m = {
        "n_months": n_hist,
        "aggregates": agg,
        "series": series,
        "warnings": [],
    }
    if n_hist < 3:
        rolling_3m["warnings"].append(f"rolling_window_partial: only {n_hist} months found")

    payload["trends_mom"] = trends_mom
    payload["rolling_3m"] = rolling_3m

    return payload


def _render_md(month: str, payload: Dict[str, Any]) -> str:
    dq = payload.get("data_quality") or {}
    pc = payload.get("process_compliance") or {}
    rdist_all = payload.get("edge_r_distribution") or {}
    rdist_manual = payload.get("edge_r_distribution_manual_only") or {}
    reg = (payload.get("regime_interaction") or {}).get("by_regime_at_entry") or {}
    trends = payload.get("trends_mom") or {}
    rolling = payload.get("rolling_3m") or {}

    lines: List[str] = []
    lines.append(f"# Meta Performance — {month}")
    lines.append("")
    lines.append(
        f"- OVERALL: process_gate_on={dq.get('process_gate_on')} | interpret_with_caution={dq.get('interpret_with_caution')}"
    )
    lines.append("")
    lines.append("## Process")
    lines.append(
        f"- compliance_score: {pc.get('compliance_score')} | overall_label={pc.get('labels', {}).get('overall')}"
    )
    lines.append(
        f"- stop_present_rate={pc.get('stop_present_rate')} | stop_manual_rate={pc.get('stop_manual_rate')} | reason_tag_present_rate={pc.get('reason_tag_present_rate')}"
    )
    if dq.get("caution_reasons"):
        lines.append(f"- caution_reasons: {', '.join(dq.get('caution_reasons') or [])}")
    lines.append("")
    lines.append("## Edge (R multiple)")
    lines.append(
        f"- ALL stops: n_with_R={rdist_all.get('n_with_r')} | avg_R={rdist_all.get('avg_R')} | median_R={rdist_all.get('median_R')}"
    )
    lines.append(
        f"- ALL p25_R={rdist_all.get('p25_R')} | p75_R={rdist_all.get('p75_R')} | tail_R_min={rdist_all.get('tail_R_min')} | tail_3_avg={rdist_all.get('tail_3_avg')}"
    )
    if rdist_manual.get("n_with_r"):
        lines.append(
            f"- MANUAL only: n_with_R={rdist_manual.get('n_with_r')} | avg_R={rdist_manual.get('avg_R')} | median_R={rdist_manual.get('median_R')}"
        )
        lines.append(
            f"- MANUAL p25_R={rdist_manual.get('p25_R')} | p75_R={rdist_manual.get('p75_R')} | tail_R_min={rdist_manual.get('tail_R_min')} | tail_3_avg={rdist_manual.get('tail_3_avg')}"
        )
    else:
        lines.append("- MANUAL only: no or low-sample R trades; edge not summarized.")
    lines.append("")
    lines.append("## Regime highlights")
    if reg:
        # top 2 by avg_R and worst 1
        items = [(k, v) for k, v in reg.items() if v.get("avg_R") is not None]
        items_sorted = sorted(items, key=lambda kv: kv[1]["avg_R"], reverse=True)
        for k, st in items_sorted[:2]:
            lines.append(f"- Top regime: {k} | avg_R={st['avg_R']} | n={st['n']}")
        if items_sorted:
            worst_k, worst_st = items_sorted[-1]
            lines.append(f"- Worst regime: {worst_k} | avg_R={worst_st['avg_R']} | n={worst_st['n']}")
    else:
        lines.append("- No regime data (all unknown or no R).")
    lines.append("")
    lines.append("## Top actions")
    for a in payload.get("top_actions") or []:
        lines.append(f"- {a}")
    if not payload.get("top_actions"):
        lines.append("- None.")
    lines.append("")
    if payload.get("warnings"):
        lines.append("## Warnings")
        for w in payload["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    return "\n".join(lines)


def run_meta_perf(month: Optional[str] = None, render: bool = False) -> Tuple[Path, Path]:
    """
    Compute meta performance for given month (YYYY-MM).
    Writes meta_perf_YYYY-MM.json, meta_perf_latest.json, and optional md.
    """
    if not month:
        from datetime import datetime

        month = datetime.now().strftime("%Y-%m")[:7]
    month_key = month[:7]
    payload = _build_meta_perf(month_key, render=render)

    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    out_json = DECISION_DIR / f"meta_perf_{month_key}.json"
    latest_json = DECISION_DIR / "meta_perf_latest.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if render:
        md = _render_md(month_key, payload)
        out_md = DECISION_DIR / f"meta_perf_{month_key}.md"
        latest_md = DECISION_DIR / "meta_perf_latest.md"
        out_md.write_text(md, encoding="utf-8")
        latest_md.write_text(md, encoding="utf-8")
    else:
        out_md = DECISION_DIR / f"meta_perf_{month_key}.md"
        latest_md = DECISION_DIR / "meta_perf_latest.md"

    logger.info("Wrote %s and meta_perf_latest.json", out_json.name)
    return out_json, latest_json

