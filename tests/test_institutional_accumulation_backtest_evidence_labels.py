from __future__ import annotations

import pandas as pd

from src.research.institutional_accumulation_backtest.evidence_labels import build_evidence_summary


def test_evidence_labels_match_p02_expectations() -> None:
    ablation = pd.DataFrame(
        [
            {"component": "institutional_accumulation_score", "spread_q5_q1": 0.000345},
            {"component": "score_without_context", "spread_q5_q1": 0.000345},
        ]
    )
    yearly = pd.DataFrame({"q5_minus_q1_ret60": [0.01, -0.02, 0.03, -0.01, 0.0, 0.02, -0.01]})
    coverage = {"tier1_rows": 0}
    metrics = pd.DataFrame(
        [
            {"strategy": "S1B_tier12_equal", "gross_return": -0.876},
        ]
    )
    dist = pd.DataFrame(
        [
            {"distribution_risk_flag": True, "max_dd_60d_mean": -0.12},
            {"distribution_risk_flag": False, "max_dd_60d_mean": -0.07},
        ]
    )
    warning = pd.DataFrame([{"ret_60d_mean": 0.01}, {"ret_60d_mean": 0.02}])
    changes = pd.DataFrame([{"ret_60d_mean": -0.01}])
    summary, ab = build_evidence_summary(
        ablation=ablation,
        yearly=yearly,
        coverage_summary=coverage,
        metrics=metrics,
        dist_flag=dist,
        warning_validation=warning,
        changes_event=changes,
        context_mode="OHLCV_ONLY",
    )
    assert summary["composite_score"][0] == "INCONCLUSIVE"
    assert summary["tier1"][0] == "INCONCLUSIVE"
    assert summary["tier12"][0] == "REJECTED"
    assert summary["fund_backed"][0] == "BLOCKED_BY_DATA"
    assert summary["distribution_risk_flag"][0] == "SUPPORTED_AS_RISK_WARNING"
    assert summary["changes_upgrades"][0] == "REJECTED"
    assert ab.loc[ab["component"] == "institutional_accumulation_score", "evidence_status"].iloc[0] == "INCONCLUSIVE"
