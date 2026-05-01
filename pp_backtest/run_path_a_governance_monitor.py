"""
Lightweight governance monitor for Path A.

Reads existing artifacts to summarize:
- Champion (default) vs Tuned Challenger (under watch)
- Recent-period performance (2024-01-01 to 2026-02-21 if available)
- Rolling 6m/12m evidence
- Governance rule status and operating recommendation

Outputs:
- artifacts/path_a_governance_monitor.csv
- artifacts/path_a_governance_monitor.md
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


ARTIFACTS_DIR = _REPO / "artifacts"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_recent_period_metrics() -> Dict[str, Any]:
    """Load Champion vs Tuned Challenger metrics for the recent period if available."""
    csv_path = ARTIFACTS_DIR / "path_a_champion_vs_tuned_challenger.csv"
    df = _safe_read_csv(csv_path)
    if df.empty:
        return {}

    # Prefer explicit 2024–2026Q1 label
    recent_label = "2024-01-01_to_2026-02-21"
    if recent_label not in df["period"].unique():
        # fall back to last period in file
        recent_label = df["period"].iloc[-1]

    sub = df[df["period"] == recent_label]
    out: Dict[str, Any] = {"period": recent_label}
    for name in ["champion", "challenger_tuned"]:
        row = sub[sub["config_name"] == name]
        if row.empty:
            continue
        r = row.iloc[0]
        out[f"{name}_cagr"] = float(r.get("cagr", np.nan))
        out[f"{name}_mdd"] = float(r.get("mdd", np.nan))
        out[f"{name}_mar"] = float(r.get("mar", np.nan))
    return out


def _load_monitoring_admission() -> Dict[str, Any]:
    """Load chosen_rate / rejected_max_positions from monitoring snapshot if present."""
    csv_path = ARTIFACTS_DIR / "path_a_monitoring_snapshot.csv"
    df = _safe_read_csv(csv_path)
    if df.empty:
        return {}
    out: Dict[str, Any] = {}
    for name, label in [("champion", "champion"), ("challenger", "challenger_tuned")]:
        row = df[df["config_name"] == name]
        if row.empty:
            continue
        r = row.iloc[0]
        out[f"{label}_chosen_rate"] = float(r.get("chosen_rate", np.nan))
        out[f"{label}_rejected_max_positions"] = int(r.get("rejected_max_positions", 0))
    return out


def _load_rolling_summary() -> Dict[str, Any]:
    """Summarize 6m and 12m rolling evidence from tuned rolling CSV."""
    csv_path = ARTIFACTS_DIR / "path_a_tuned_challenger_rolling_review.csv"
    df = _safe_read_csv(csv_path)
    if df.empty:
        return {}
    out: Dict[str, Any] = {}
    df_valid = df.dropna(subset=["mar", "mdd"])
    import math

    for kind in ["6m", "12m"]:
        sub = df_valid[df_valid["window_kind"] == kind]
        if sub.empty:
            continue
        # win counts
        pivot = sub.pivot_table(
            index="window_label",
            columns="config_name",
            values="mar",
            aggfunc="first",
        )
        champ_wins = 0
        chal_wins = 0
        for _, row in pivot.iterrows():
            cm = row.get("champion")
            ct = row.get("challenger_tuned")
            if pd.isna(cm) or pd.isna(ct):
                continue
            if cm > ct:
                champ_wins += 1
            elif ct > cm:
                chal_wins += 1

        # averages
        avg = sub.groupby("config_name").agg(
            avg_mar=("mar", "mean"),
            avg_mdd=("mdd", "mean"),
        )
        kind_key = f"{kind}"
        out[f"{kind_key}_champ_wins"] = int(champ_wins)
        out[f"{kind_key}_chal_wins"] = int(chal_wins)
        for cfg in ["champion", "challenger_tuned"]:
            if cfg in avg.index:
                r = avg.loc[cfg]
                out[f"{kind_key}_{cfg}_avg_mar"] = float(r["avg_mar"])
                out[f"{kind_key}_{cfg}_avg_mdd"] = float(r["avg_mdd"])
    return out


def _evaluate_governance(rolling: Dict[str, Any], recent: Dict[str, Any]) -> Dict[str, Any]:
    """Apply governance rule: does tuned Challenger qualify for formal baseline review?"""
    # Basic signals
    # Condition A: rolling win rate on MAR reasonably high in 6m and/or 12m
    sixm_total = rolling.get("6m_champ_wins", 0) + rolling.get("6m_chal_wins", 0)
    sixm_win_rate = (
        rolling.get("6m_chal_wins", 0) / sixm_total if sixm_total > 0 else 0.0
    )
    twelvem_total = rolling.get("12m_champ_wins", 0) + rolling.get("12m_chal_wins", 0)
    twelvem_win_rate = (
        rolling.get("12m_chal_wins", 0) / twelvem_total if twelvem_total > 0 else 0.0
    )

    # Condition B: MDD not materially worse on average
    sixm_mdd_champ = rolling.get("6m_championship_avg_mdd")  # typo guard, may be None
    sixm_mdd_champ = rolling.get("6m_champion_avg_mdd", sixm_mdd_champ)
    sixm_mdd_chal = rolling.get("6m_challenger_tuned_avg_mdd", None)
    twelvem_mdd_champ = rolling.get("12m_champion_avg_mdd", None)
    twelvem_mdd_chal = rolling.get("12m_challenger_tuned_avg_mdd", None)

    def _mdd_ok(ch_mdd, ct_mdd) -> bool:
        if ch_mdd is None or ct_mdd is None or np.isnan(ch_mdd) or np.isnan(ct_mdd):
            return False
        # mdd numbers are negative; higher (less negative) is better
        # require tuned not worse than ~3–4 ppts on average
        return ct_mdd >= ch_mdd - 0.04

    mdd_ok_6m = _mdd_ok(sixm_mdd_champ, sixm_mdd_chal)
    mdd_ok_12m = _mdd_ok(twelvem_mdd_champ, twelvem_mdd_chal)

    # Condition C: full-sample / recent MAR not clearly worse
    mar_champ_recent = recent.get("champion_mar")
    mar_chal_recent = recent.get("challenger_tuned_mar")
    mar_ok_recent = (
        mar_champ_recent is not None
        and mar_chal_recent is not None
        and not np.isnan(mar_champ_recent)
        and not np.isnan(mar_chal_recent)
        and mar_chal_recent >= 0.9 * mar_champ_recent
    )

    qualifies = (
        (sixm_win_rate >= 0.6 or twelvem_win_rate >= 0.6)
        and (mdd_ok_6m or mdd_ok_12m)
        and mar_ok_recent
    )

    return {
        "sixm_win_rate": sixm_win_rate,
        "twelvem_win_rate": twelvem_win_rate,
        "mdd_ok_6m": mdd_ok_6m,
        "mdd_ok_12m": mdd_ok_12m,
        "mar_ok_recent": mar_ok_recent,
        "qualifies_for_formal_review": bool(qualifies),
    }


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    recent = _load_recent_period_metrics()
    admission = _load_monitoring_admission()
    rolling = _load_rolling_summary()
    gov_eval = _evaluate_governance(rolling, recent)

    # CSV: one row summary
    row: Dict[str, Any] = {
        "default_config": "champion",
        "tuned_challenger_status": "under_watch",
    }
    row.update(recent)
    row.update(admission)
    row.update(rolling)
    row.update(gov_eval)

    monitor_csv = ARTIFACTS_DIR / "path_a_governance_monitor.csv"
    pd.DataFrame([row]).to_csv(monitor_csv, index=False)

    # MD report
    monitor_md = ARTIFACTS_DIR / "path_a_governance_monitor.md"
    with open(monitor_md, "w", encoding="utf-8") as f:
        f.write("# Path A Governance Monitor\n\n")

        # 1. Current default
        f.write("## 1. Current default\n\n")
        f.write("- Champion: **default Path A** (extension_first, max_positions=8).\n")
        f.write("- Tuned Challenger: **under watch** (simple_composite, max_positions=12, max_heat=0.04, risk_per_trade=0.004).\n\n")

        # 2. Recent-period comparison
        f.write("## 2. Recent-period comparison\n\n")
        if recent:
            f.write(f"- Period: {recent.get('period')}\n\n")
            f.write("| config | CAGR | MDD | MAR |\n")
            f.write("|--------|------|-----|-----|\n")
            f.write(
                f"| Champion | {recent.get('champion_cagr', np.nan):.2%} | "
                f"{recent.get('champion_mdd', np.nan):.2%} | {recent.get('champion_mar', np.nan):.4f} |\n"
            )
            f.write(
                f"| Tuned Challenger | {recent.get('challenger_tuned_cagr', np.nan):.2%} | "
                f"{recent.get('challenger_tuned_mdd', np.nan):.2%} | {recent.get('challenger_tuned_mar', np.nan):.4f} |\n\n"
            )
        else:
            f.write("- Recent-period metrics unavailable.\n\n")

        f.write("Chosen/admission pressure (if snapshot available):\n\n")
        f.write("| config | chosen_rate | rejected_max_positions |\n")
        f.write("|--------|-------------|------------------------|\n")
        f.write(
            f"| Champion | {admission.get('champion_chosen_rate', np.nan):.4g} | "
            f"{int(admission.get('champion_rejected_max_positions', 0))} |\n"
        )
        f.write(
            f"| Tuned Challenger | {admission.get('challenger_tuned_chosen_rate', np.nan):.4g} | "
            f"{int(admission.get('challenger_tuned_rejected_max_positions', 0))} |\n\n"
        )

        # 3. Rolling evidence
        f.write("## 3. Rolling evidence\n\n")
        # 6m
        f.write("### 6m windows\n\n")
        f.write(
            f"- Champion MAR wins: {rolling.get('6m_champ_wins', 0)}\n"
            f"- Tuned Challenger MAR wins: {rolling.get('6m_chal_wins', 0)}\n\n"
        )
        f.write("| config | avg_MAR_6m | avg_MDD_6m |\n")
        f.write("|--------|------------|-----------|\n")
        f.write(
            f"| Champion | {rolling.get('6m_champion_avg_mar', np.nan):.4f} | "
            f"{rolling.get('6m_champion_avg_mdd', np.nan):.2%} |\n"
        )
        f.write(
            f"| Tuned Challenger | {rolling.get('6m_challenger_tuned_avg_mar', np.nan):.4f} | "
            f"{rolling.get('6m_challenger_tuned_avg_mdd', np.nan):.2%} |\n\n"
        )

        # 12m
        f.write("### 12m windows\n\n")
        f.write(
            f"- Champion MAR wins: {rolling.get('12m_champ_wins', 0)}\n"
            f"- Tuned Challenger MAR wins: {rolling.get('12m_chal_wins', 0)}\n\n"
        )
        f.write("| config | avg_MAR_12m | avg_MDD_12m |\n")
        f.write("|--------|-------------|------------|\n")
        f.write(
            f"| Champion | {rolling.get('12m_champion_avg_mar', np.nan):.4f} | "
            f"{rolling.get('12m_champion_avg_mdd', np.nan):.2%} |\n"
        )
        f.write(
            f"| Tuned Challenger | {rolling.get('12m_challenger_tuned_avg_mar', np.nan):.4f} | "
            f"{rolling.get('12m_challenger_tuned_avg_mdd', np.nan):.2%} |\n\n"
        )

        # 4. Governance rule status
        f.write("## 4. Governance rule status\n\n")
        qualifies = gov_eval["qualifies_for_formal_review"]
        f.write(f"- Does Tuned Challenger qualify for **formal baseline review**? **{'yes' if qualifies else 'no'}**.\n")
        f.write(
            f"- 6m rolling win rate (Tuned Challenger): {gov_eval['sixm_win_rate']:.1%}; "
            f"12m: {gov_eval['twelvem_win_rate']:.1%}.\n"
        )
        f.write(
            f"- MDD acceptable? 6m: {gov_eval['mdd_ok_6m']}, 12m: {gov_eval['mdd_ok_12m']}.\n"
        )
        f.write(f"- Recent MAR acceptable (Tuned vs Champion)? {gov_eval['mar_ok_recent']}.\n\n")

        f.write("### Why it does / does not qualify\n\n")
        if qualifies:
            f.write(
                "- Tuned Challenger shows strong rolling MAR win rates and does not worsen MDD materially; "
                "it meets the promotion rule and can move to formal baseline review.\n\n"
            )
        else:
            f.write(
                "- Although Tuned Challenger has some rolling wins, its average MDD is meaningfully worse on key windows, "
                "and/or its recent MAR is not clearly superior. It therefore does **not** meet the promotion rule for "
                "formal baseline review.\n\n"
            )

        # 5. What would change the decision
        f.write("## 5. What would change the decision\n\n")
        f.write(
            "- Tuned Challenger would need to show **repeated 6m/12m rolling superiority on MAR** (e.g. ≥60% of recent windows)\n"
            "  **and** keep average MDD no more than ~3–4 percentage points worse than Champion, ideally better.\n"
            "- Full-sample and recent-period MAR should be at least comparable to Champion, not structurally lower.\n\n"
        )

        # 6. Final operating recommendation
        f.write("## 6. Final operating recommendation\n\n")
        if qualifies:
            f.write("- **Open formal review** of Tuned Challenger vs Champion; keep Champion as default until review concludes.\n")
        else:
            f.write(
                "- **Keep Champion as default** and **keep Tuned Challenger under watch**. "
                "Re-run this governance monitor periodically; only open formal review if the rolling and risk profile "
                "shifts clearly in favor of Tuned Challenger.\n"
            )


if __name__ == "__main__":
    main()

