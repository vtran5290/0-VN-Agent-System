from __future__ import annotations
from typing import Dict, Any, Optional

def _delta(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    if cur is None or prev is None:
        return None
    return cur - prev

def build_core_features(cur: Dict[str, Any], prev: Dict[str, Any]) -> Dict[str, Any]:
    g0, g1 = cur.get("global", {}), prev.get("global", {})
    v0, v1 = cur.get("vietnam", {}), prev.get("vietnam", {})
    m0, m1 = cur.get("market", {}), prev.get("market", {})

    return {
        "asof_date": cur.get("asof_date"),
        "global": {
            "ust_2y_chg_wow": _delta(g0.get("ust_2y"), g1.get("ust_2y")),
            "ust_10y_chg_wow": _delta(g0.get("ust_10y"), g1.get("ust_10y")),
            "dxy_chg_wow": _delta(
                float(g0["dxy"]) if g0.get("dxy") is not None else None,
                float(g1["dxy"]) if g1.get("dxy") is not None else None,
            ),
            "dxy_reconstructed_chg_wow": _delta(
                float(g0["dxy_reconstructed"]) if g0.get("dxy_reconstructed") is not None else None,
                float(g1["dxy_reconstructed"]) if g1.get("dxy_reconstructed") is not None else None,
            ),
            "usd_broad_index_fred_chg_wow": _delta(
                float(g0["usd_broad_index_fred"]) if g0.get("usd_broad_index_fred") is not None else None,
                float(g1["usd_broad_index_fred"]) if g1.get("usd_broad_index_fred") is not None else None,
            ),
            "nonfarm_payroll_change_persons_chg_wow": _delta(
                float(g0["nonfarm_payroll_change_persons"])
                if g0.get("nonfarm_payroll_change_persons") is not None
                else None,
                float(g1["nonfarm_payroll_change_persons"])
                if g1.get("nonfarm_payroll_change_persons") is not None
                else None,
            ),
        },
        "vietnam": {
            "omo_net_chg_wow": _delta(v0.get("omo_net"), v1.get("omo_net")),
            "interbank_on_chg_wow": _delta(v0.get("interbank_on"), v1.get("interbank_on")),
            "credit_growth_yoy_chg_wow": _delta(v0.get("credit_growth_yoy"), v1.get("credit_growth_yoy")),
        },
        "market": {
            "vnindex_chg_wow": _delta(m0.get("vnindex_level"), m1.get("vnindex_level")),
            "dist_days_chg_wow": _delta(m0.get("distribution_days_rolling_20"), m1.get("distribution_days_rolling_20")),
        }
    }
