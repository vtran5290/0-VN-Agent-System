# src/knowledge/resolver.py — Resolve backtest edge, regime_break, relevance (deterministic)
from __future__ import annotations
import hashlib
import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = _REPO / "knowledge" / "backtests" / "index.json"
RULES_PATH = _REPO / "knowledge" / "resolver_rules.yml"
PRESETS_PATH = _REPO / "pp_backtest" / "presets.yml"
REGIME_BREAK_PATH = _REPO / "knowledge" / "regime_break.json"
RESULTS_CSV = _REPO / "pp_backtest" / "pp_sell_backtest_results.csv"
LEDGER_CSV = _REPO / "pp_backtest" / "pp_trade_ledger.csv"
SYSTEM_WARNINGS_LOG = _REPO / "knowledge" / "logs" / "system_warnings.log"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_preset(strategy_id: str) -> dict:
    data = _load_yaml(PRESETS_PATH)
    presets = data.get("presets", {})
    return presets.get(strategy_id, {"id": strategy_id, "version": "1.0.0"})


def _params_hash(preset: dict, date_range: dict, data_source: str) -> str:
    blob = json.dumps({
        "preset": preset,
        "date_range": date_range,
        "data_source": data_source,
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def compute_relevance(context: dict) -> dict[str, Any]:
    """
    Deterministic relevance from context. If required keys missing → label Unknown, score null.
    required: vn30_dd20, stock_below_ma50, regime_flag (or regime for backward compat).
    """
    required = ["vn30_dd20", "stock_below_ma50", "regime_flag"]
    # Allow regime as fallback for regime_flag
    if context.get("regime_flag") is None and context.get("regime") is not None:
        context = {**context, "regime_flag": context.get("regime")}
    missing = [k for k in required if context.get(k, None) is None]
    if missing:
        return {"label": "Unknown", "score": None, "missing": missing, "notes": []}

    score = 0.8
    notes = []
    if context.get("vn30_dd20") is not None and context["vn30_dd20"] >= 7:
        score -= 0.2
        notes.append("vn30_dd20>=7")
    if context.get("stock_below_ma50"):
        score -= 0.3
        notes.append("stock_below_ma50")
    regime_flag = (context.get("regime_flag") or "").lower() if context.get("regime_flag") else ""
    if regime_flag == "risk_off" or "risk" in regime_flag or "tight" in regime_flag:
        score -= 0.1
        notes.append("regime=risk_off")
    score = max(0.0, min(1.0, score))
    label = "High" if score >= 0.7 else "Medium" if score >= 0.5 else "Low"
    return {"label": label, "score": score, "missing": [], "notes": notes}


def load_regime_break() -> dict[str, Any]:
    """
    Load regime_break.json. If active and today > expires_at → treat as inactive, set expired_warning.
    Does NOT write back to file.
    Returns: { "active": bool (effective), "expired": bool, "expired_warning": str | None, "raw": dict }
    """
    out = {"active": False, "expired": False, "expired_warning": None, "raw": {}}
    if not REGIME_BREAK_PATH.exists():
        return out
    try:
        raw = json.loads(REGIME_BREAK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return out
    out["raw"] = raw
    if not raw.get("active"):
        return out
    expires_at_s = (raw.get("expires_at") or "").strip()
    if not expires_at_s:
        out["active"] = True
        return out
    try:
        expires_at = date.fromisoformat(expires_at_s[:10])
        today = date.today()
        if today > expires_at:
            out["expired"] = True
            out["expired_warning"] = "Regime break expired — manual review recommended."
            out["active"] = False
            # Optional: append to system_warnings.log
            if SYSTEM_WARNINGS_LOG.parent.exists():
                line = f"{datetime.now().isoformat()} [regime_break] {out['expired_warning']}\n"
                try:
                    with open(SYSTEM_WARNINGS_LOG, "a", encoding="utf-8") as f:
                        f.write(line)
                except Exception:
                    pass
            return out
    except Exception:
        pass
    out["active"] = True
    return out


def get_regime_break_status() -> dict[str, Any]:
    """For Decision injection: effective active, expired_warning, and any message for footer."""
    r = load_regime_break()
    return {
        "active": r["active"],
        "expired_warning": r["expired_warning"],
        "reason": r["raw"].get("reason", ""),
        "since": r["raw"].get("since", ""),
    }


def _mtime_stale_warning(record: dict) -> str | None:
    """
    If backtest data files are newer than record inputs → warn re-publish.
    Uses grace_period_hours: only warn when data has been newer for longer than that
    (e.g. 24h = no spam right after backtest; warn after 1–2 days if still not published).
    """
    inputs = record.get("inputs") or {}
    if not inputs:
        return None
    rules = _load_yaml(RULES_PATH)
    staleness_cfg = rules.get("staleness") or {}
    grace_period_hours = float(staleness_cfg.get("grace_period_hours", 24))
    now_ts = time.time()
    for key, path in [("results_csv_mtime", RESULTS_CSV), ("ledger_csv_mtime", LEDGER_CSV)]:
        stored = inputs.get(key)
        if not stored or not path.exists():
            continue
        try:
            current_ts = path.stat().st_mtime
            stored_dt = datetime.fromisoformat(stored.replace("Z", "+00:00"))
            stored_ts = stored_dt.timestamp()
            if current_ts <= stored_ts:
                continue
            hours_since_file_modified = (now_ts - current_ts) / 3600.0
            if hours_since_file_modified > grace_period_hours:
                return "Backtest data newer than knowledge record — re-publish recommended."
        except Exception:
            continue
    return None


def get_backtest_edge(
    symbol: str,
    strategy_id: str | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """
    Load backtest knowledge for symbol; return summary + relevance + warnings (deterministic).
    context: optional { regime, regime_flag, vn30_dd20, stock_below_ma50, mkt_flags } for relevance.
    Returns: {
      "found": bool,
      "summary_lines": list[str],
      "relevance": { "label", "score"|None, "missing", "notes" },
      "warnings": list[str],
      "record": dict | None,
    }
    """
    context = context or {}
    rules = _load_yaml(RULES_PATH)
    strategy_id = strategy_id or rules.get("default_strategy_id", "PP_GIL_V4")
    regime_break = load_regime_break()

    out = {
        "found": False,
        "summary_lines": [],
        "relevance": {"label": "N/A", "score": None, "missing": [], "notes": []},
        "warnings": [],
        "record": None,
    }

    if not INDEX_PATH.exists():
        return out

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    latest = index.get("latest", {})
    rel_path = (latest.get(symbol) or {}).get(strategy_id)
    if not rel_path:
        return out

    rec_path = _REPO / rel_path.replace("/", "\\")
    if not rec_path.exists():
        return out

    record = json.loads(rec_path.read_text(encoding="utf-8"))
    out["record"] = record
    out["found"] = True

    # Stale: preset params_hash mismatch
    preset = _load_preset(strategy_id)
    date_range = record.get("date_range", {})
    data_source = record.get("data_source", "fireant_historical")
    current_hash = _params_hash(preset, date_range, data_source)
    stored_hash = record.get("params_hash") or record.get("build", {}).get("params_hash")
    if stored_hash and current_hash != stored_hash:
        out["warnings"].append(
            "Stale backtest: preset hash mismatch (record vs current). Re-run backtest recommended."
        )

    # mtime: data newer than record
    mtime_warn = _mtime_stale_warning(record)
    if mtime_warn:
        out["warnings"].append(mtime_warn)

    # Relevance (deterministic; regime_break caps when active)
    relevance = compute_relevance(context)
    if regime_break["active"]:
        relevance = {
            "label": "Low",
            "score": min(relevance.get("score") or 0.5, 0.5),
            "missing": relevance.get("missing", []),
            "notes": relevance.get("notes", []) + ["regime_break_active"],
        }
        out["warnings"].append(
            "Regime break active — backtest relevance downgraded; re-validate required."
        )
    out["relevance"] = relevance

    # Summary lines (facts)
    s = record.get("stats", {})
    dr = record.get("date_range", {})
    range_str = f"{dr.get('start', '')}–{dr.get('end', '')}"
    out["summary_lines"] = [
        f"Backtest edge ({symbol}, {strategy_id}, {range_str}):",
        f"  Win rate: {s.get('win_rate', 0):.0%}  Expectancy: {s.get('avg_ret', 0):.2%}/trade",
        f"  Avg win / loss: {s.get('avg_win') or 0:.2%} / {s.get('avg_loss') or 0:.2%}  PF: {s.get('profit_factor') or 0:.2f}  MDD: {s.get('max_drawdown') or 0:.1%}",
    ]
    exit_br = record.get("exit_reason_breakdown", {})
    if exit_br:
        notable = []
        for reason, data in exit_br.items():
            mfe = data.get("mfe_20_avg")
            if mfe is not None and mfe > 5:
                notable.append(f"{reason} exits MFE~{mfe:.1f}%")
        if notable:
            out["summary_lines"].append("  Notable: " + "; ".join(notable))

    return out


def get_personal_reminders(context: dict) -> list[str]:
    """Phase 2: return reminder lines for decision. MVP returns []."""
    return []
