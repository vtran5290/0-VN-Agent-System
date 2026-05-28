from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.reporting import write_html_report


def _safe_csv(path: str, cols: list[str] | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        return pd.DataFrame(columns=cols or [])
    return pd.read_csv(p)


def main() -> None:
    root = Path("data/research/institutional_accumulation")
    metrics = _safe_csv(root / "portfolio_metrics_summary.csv")
    yearly = _safe_csv(root / "yearly_validation.csv")
    regime = _safe_csv(root / "regime_validation.csv")
    ablation = _safe_csv(root / "component_ablation_oos.csv")
    risk = _safe_csv(root / "risk_penalty_calibration.csv")
    dist = _safe_csv(root / "distribution_flag_validation.csv")
    vin = _safe_csv(root / "vin_sensitivity_summary.csv")
    warning = _safe_csv(root / "warning_validation.csv", ["section", "n", "ret_60d_mean"])
    changes = _safe_csv(root / "changes_event_study.csv", ["event", "n", "ret_20d_mean", "ret_60d_mean"])
    coverage = _safe_csv(root / "run_coverage_audit.csv", ["metric", "value"])
    context_mode = "OHLCV_ONLY"
    run_status = "INCONCLUSIVE"
    benchmark_ok = False
    ex_vin_ok = False
    mpath = root / "backtest_manifest.json"
    if mpath.is_file():
        import json

        m = json.loads(mpath.read_text(encoding="utf-8"))
        context_mode = m.get("fund_context_mode", context_mode)
        run_status = m.get("final_run_status", run_status)
    bval = _safe_csv(root / "benchmark_validation.csv")
    if not bval.empty:
        benchmark_ok = str(bval.iloc[0].get("status", "")) == "OK"
    vsa = _safe_csv(root / "vin_sensitivity_summary.csv")
    if not vsa.empty and "universe" in vsa.columns:
        vin_only_n = 0
        full_n = 0
        ex_n = 0
        if "n" in vsa.columns:
            vin_only_n = int(vsa.loc[vsa["universe"] == "vin_only", "n"].fillna(0).sum())
            full_n = int(vsa.loc[vsa["universe"] == "full", "n"].fillna(0).sum())
            ex_n = int(vsa.loc[vsa["universe"] == "ex_vin", "n"].fillna(0).sum())
        ex_vin_ok = vin_only_n > 0 and ex_n < full_n
    coverage_summary: dict[str, object] = {}
    if not coverage.empty and "metric" in coverage.columns and "value" in coverage.columns:
        for _, r in coverage.iterrows():
            coverage_summary[str(r["metric"])] = r["value"]
    out = Path("reports/research/institutional_accumulation/institutional_accumulation_backtest_summary.html")
    write_html_report(
        out,
        metrics=metrics,
        yearly=yearly,
        regime=regime,
        ablation=ablation,
        risk=risk,
        dist_flag=dist,
        vin=vin,
        warning_validation=warning,
        changes_event=changes,
        coverage_summary=coverage_summary,
        context_mode=context_mode,
        run_status=run_status,
        benchmark_ok=benchmark_ok,
        ex_vin_ok=ex_vin_ok,
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
