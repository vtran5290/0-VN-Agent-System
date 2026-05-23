from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import SMART_MONEY_MONTHLY_DIR, SMART_MONEY_PRIORS_PATH


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _ticker_meta_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Richer monthly fields (forward-compatible)."""
    meta: Dict[str, Any] = {}
    for key in ("n_top5", "n_top10", "avg_weight_top10", "n_funds"):
        if row.get(key) is not None:
            try:
                meta[key] = float(row[key]) if "weight" in key else int(row[key])
            except (TypeError, ValueError):
                meta[key] = row[key]
    funds = row.get("funds_top10") or []
    if isinstance(funds, list):
        meta["funds_top10"] = [str(f) for f in funds]
    tags = row.get("conviction_tags") or row.get("tags") or []
    if isinstance(tags, list):
        meta["conviction_tags"] = [str(t) for t in tags]
    return meta


def load_smart_money_context(month: Optional[str] = None) -> Dict[str, Any]:
    monthly_path = None
    if month:
        p = SMART_MONEY_MONTHLY_DIR / f"smart_money_{month}.json"
        if p.is_file():
            monthly_path = p
    if monthly_path is None and month is None:
        files = sorted(SMART_MONEY_MONTHLY_DIR.glob("smart_money_*.json"), reverse=True)
        for p in files:
            if p.is_file():
                monthly_path = p
                break

    if monthly_path and monthly_path.is_file():
        raw = _read_json(monthly_path)
        if raw:
            return _normalize_monthly(raw, source=f"monthly:{monthly_path.name}")

    priors = _read_json(SMART_MONEY_PRIORS_PATH)
    if priors:
        return _normalize_priors(priors, source="fallback:apr2026_default_priors.json")
    return _empty_context("missing_all_context")


def _normalize_priors(p: Dict[str, Any], source: str) -> Dict[str, Any]:
    core = [str(x).upper() for x in p.get("consensus_core") or []]
    ring = [str(x).upper() for x in p.get("consensus_second_ring") or []]
    commentary = [str(x).upper() for x in p.get("commentary_mentions") or []]
    selective = [str(x).upper() for x in p.get("selective_fund_bets") or []]
    vin = [str(x).upper() for x in p.get("vingroup_distortion_symbols") or []]
    sectors = [str(s) for s in p.get("sector_consensus") or []]
    themes = p.get("theme_tags") or {}
    return {
        "context_source": source,
        "month": p.get("month"),
        "regime_label": p.get("regime_label"),
        "regime_notes": list(p.get("regime_notes") or []),
        "universe_policy": dict(p.get("universe_policy") or {}),
        "consensus_core": core,
        "consensus_second_ring": ring,
        "commentary_mentions": commentary,
        "selective_fund_bets": selective,
        "commentary_notes": list(p.get("commentary_notes") or []),
        "vingroup_distortion_symbols": vin,
        "sector_consensus": sectors,
        "sector_name_aliases": dict(p.get("sector_name_aliases") or {}),
        "theme_tags": {k: [str(t).upper() for t in v] for k, v in themes.items() if isinstance(v, list)},
        "risk_flags": list(p.get("risk_flags") or []),
        "ticker_meta": {},
    }


def _normalize_monthly(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    core: List[str] = []
    ring: List[str] = []
    ticker_meta: Dict[str, Dict[str, Any]] = {}
    for row in raw.get("ticker_consensus") or []:
        if not isinstance(row, dict):
            continue
        t = str(row.get("ticker") or "").strip().upper()
        if not t:
            continue
        n10 = int(row.get("n_top10") or 0)
        n5 = int(row.get("n_top5") or 0)
        n_funds = len(row.get("funds_top10") or []) if isinstance(row.get("funds_top10"), list) else n10
        meta = _ticker_meta_from_row(row)
        meta.setdefault("n_funds", n_funds)
        meta.setdefault("n_top10", n10)
        meta.setdefault("n_top5", n5)
        ticker_meta[t] = meta
        if n10 >= 4:
            core.append(t)
        elif n10 >= 2:
            ring.append(t)
    sectors = [str(s.get("sector") or "") for s in raw.get("sector_consensus") or [] if isinstance(s, dict)]
    flags = list(raw.get("flags") or [])
    priors = _read_json(SMART_MONEY_PRIORS_PATH) or {}
    vin = [str(x).upper() for x in priors.get("vingroup_distortion_symbols") or ["VIC", "VHM", "VRE", "VPL"]]
    commentary = list(priors.get("commentary_mentions") or [])
    for row in raw.get("ticker_consensus") or []:
        if not isinstance(row, dict):
            continue
        t = str(row.get("ticker") or "").upper()
        if t and row.get("mentioned_in_commentary"):
            if t not in commentary:
                commentary.append(t)
    return {
        "context_source": source,
        "month": raw.get("month"),
        "regime_label": raw.get("regime_bias") or priors.get("regime_label"),
        "regime_notes": list(priors.get("regime_notes") or []),
        "universe_policy": dict(priors.get("universe_policy") or {}),
        "consensus_core": core or list(priors.get("consensus_core") or []),
        "consensus_second_ring": ring or list(priors.get("consensus_second_ring") or []),
        "commentary_mentions": commentary,
        "selective_fund_bets": list(priors.get("selective_fund_bets") or []),
        "commentary_notes": list(priors.get("commentary_notes") or []),
        "vingroup_distortion_symbols": vin,
        "sector_consensus": sectors or list(priors.get("sector_consensus") or []),
        "sector_name_aliases": dict(priors.get("sector_name_aliases") or {}),
        "theme_tags": dict(priors.get("theme_tags") or {}),
        "risk_flags": flags or list(priors.get("risk_flags") or []),
        "ticker_meta": ticker_meta,
    }


def _empty_context(reason: str) -> Dict[str, Any]:
    return {
        "context_source": reason,
        "month": None,
        "regime_label": "unknown",
        "regime_notes": [],
        "universe_policy": {},
        "consensus_core": [],
        "consensus_second_ring": [],
        "commentary_mentions": [],
        "selective_fund_bets": [],
        "commentary_notes": [],
        "vingroup_distortion_symbols": ["VIC", "VHM", "VRE", "VPL"],
        "sector_consensus": [],
        "sector_name_aliases": {},
        "theme_tags": {},
        "risk_flags": [],
        "ticker_meta": {},
    }


def load_sector_map(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    try:
        import pandas as pd

        df = pd.read_csv(path)
        if "symbol" not in df.columns:
            return {}
        col = "proxy_industryName_l4" if "proxy_industryName_l4" in df.columns else "industryCode_l3"
        out: Dict[str, str] = {}
        for _, row in df.iterrows():
            sym = str(row.get("symbol") or "").upper()
            if sym and sym not in out:
                out[sym] = str(row.get(col) or "Unknown")
        return out
    except Exception:
        return {}


def tag_symbol(symbol: str, sector: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    sym = symbol.upper()
    tags: List[str] = []
    core: Set[str] = set(ctx.get("consensus_core") or [])
    ring: Set[str] = set(ctx.get("consensus_second_ring") or [])
    commentary: Set[str] = set(ctx.get("commentary_mentions") or [])
    selective: Set[str] = set(ctx.get("selective_fund_bets") or [])
    vin: Set[str] = set(ctx.get("vingroup_distortion_symbols") or [])
    themes: Dict[str, List[str]] = ctx.get("theme_tags") or {}
    meta = (ctx.get("ticker_meta") or {}).get(sym) or {}

    fund_context_bucket = "outside_fund_disclosure"
    if sym in core:
        tags.append("consensus_core")
        fund_context_bucket = "consensus_core"
    elif sym in ring:
        tags.append("consensus_second_ring")
        fund_context_bucket = "consensus_second_ring"
    elif sym in selective:
        tags.append("selective_fund_bet")
        fund_context_bucket = "selective_fund_bet"
    elif sym in commentary:
        tags.append("fund_commentary_mention")
        fund_context_bucket = "fund_commentary_mention"
    else:
        tags.append("outside_fund_disclosure")

    n_funds = meta.get("n_funds") or meta.get("n_top10")
    if isinstance(n_funds, (int, float)) and n_funds >= 5:
        tags.append("high_fund_conviction")
    elif isinstance(n_funds, (int, float)) and 2 <= n_funds < 5:
        tags.append("moderate_fund_conviction")

    avg_w = meta.get("avg_weight_top10")
    if avg_w is not None:
        try:
            if float(avg_w) >= 0.05:
                tags.append("heavy_weight_consensus")
        except (TypeError, ValueError):
            pass

    for ct in meta.get("conviction_tags") or []:
        if ct and ct not in tags:
            tags.append(str(ct))

    if sym not in vin:
        tags.append("ex_vingroup_quality")
    if sym in vin:
        tags.append("vingroup_distortion_risk")

    sector_l = (sector or "").lower()
    for sec in ctx.get("sector_consensus") or []:
        if sec.lower() in sector_l or sector_l in sec.lower():
            tags.append("sector_consensus")
            break

    for theme, tickers in themes.items():
        if sym in {t.upper() for t in tickers}:
            if theme == "ftse_beneficiary":
                tags.append("ftse_beneficiary_candidate")
            elif theme == "infrastructure_domestic_demand":
                tags.append("infrastructure_domestic_demand_aligned")
            elif theme == "policy_liquidity_sensitive":
                tags.append("policy_liquidity_sensitive")

    has_fund_disclosure_tag = fund_context_bucket != "outside_fund_disclosure"

    return {
        "smart_money_tags": tags,
        "smart_money_tag": ",".join(tags[:5]),
        "fund_context_bucket": fund_context_bucket,
        "has_fund_disclosure_tag": has_fund_disclosure_tag,
        "in_consensus_core": sym in core,
        "in_consensus_second_ring": sym in ring,
        "in_commentary_mention": sym in commentary,
        "in_selective_fund_bet": sym in selective,
        "fund_n_top10": meta.get("n_top10"),
        "fund_avg_weight_top10": meta.get("avg_weight_top10"),
    }


def context_score(tag_info: Dict[str, Any], ctx: Dict[str, Any]) -> float:
    score = 50.0
    if tag_info.get("in_consensus_core"):
        score += 28.0
    elif tag_info.get("in_consensus_second_ring"):
        score += 14.0
    elif tag_info.get("in_commentary_mention"):
        score += 10.0
    elif tag_info.get("in_selective_fund_bet"):
        score += 8.0
    if "sector_consensus" in (tag_info.get("smart_money_tags") or []):
        score += 8.0
    if "ex_vingroup_quality" in (tag_info.get("smart_money_tags") or []):
        score += 6.0
    if "high_fund_conviction" in (tag_info.get("smart_money_tags") or []):
        score += 5.0
    if "heavy_weight_consensus" in (tag_info.get("smart_money_tags") or []):
        score += 4.0
    if "vingroup_distortion_risk" in (tag_info.get("smart_money_tags") or []):
        score -= 18.0
    if "ftse_beneficiary_candidate" in (tag_info.get("smart_money_tags") or []):
        score += 4.0
    regime = str(ctx.get("regime_label") or "").lower()
    if "narrow" in regime or "fragile" in regime:
        if "vingroup_distortion_risk" in (tag_info.get("smart_money_tags") or []):
            score -= 8.0
    return float(max(0.0, min(100.0, score)))
