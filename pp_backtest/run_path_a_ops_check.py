"""
Path A operational check runner.

Lightweight operator-facing script that reports:
- Data freshness for Path A stack
- Recent Champion vs Tuned Challenger snapshot
- Governance status and operating recommendation

Outputs:
- artifacts/path_a_ops_check.csv
- artifacts/path_a_ops_check.md
"""
from __future__ import annotations

import sys
from datetime import datetime
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


def _parse_date(s: str | float | int | None) -> datetime | None:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return None
    try:
        return datetime.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _data_freshness() -> Dict[str, Any]:
    """Inspect latest dates from existing artifacts to gauge staleness."""
    res: Dict[str, Any] = {}

    # From champion vs tuned comparison
    cmp_csv = ARTIFACTS_DIR / "path_a_champion_vs_tuned_challenger.csv"
    df_cmp = _safe_read_csv(cmp_csv)
    latest_backtest_end: datetime | None = None
    if not df_cmp.empty and "period" in df_cmp.columns:
        # end is encoded in period label
        for period in df_cmp["period"].unique():
            parts = str(period).split("_to_")
            if len(parts) == 2:
                end_dt = _parse_date(parts[1])
                if end_dt and (latest_backtest_end is None or end_dt > latest_backtest_end):
                    latest_backtest_end = end_dt

    # From rolling review
    roll_csv = ARTIFACTS_DIR / "path_a_tuned_challenger_rolling_review.csv"
    df_roll = _safe_read_csv(roll_csv)
    latest_rolling_end: datetime | None = None
    if not df_roll.empty and "window_end" in df_roll.columns:
        for s in df_roll["window_end"].dropna().astype(str):
            end_dt = _parse_date(s)
            if end_dt and (latest_rolling_end is None or end_dt > latest_rolling_end):
                latest_rolling_end = end_dt

    # From monitoring snapshot (recent weekly / regime window)
    mon_csv = ARTIFACTS_DIR / "path_a_monitoring_snapshot.csv"
    df_mon = _safe_read_csv(mon_csv)
    monitoring_period: str | None = None
    if not df_mon.empty and "period" in df_mon.columns:
        monitoring_period = str(df_mon["period"].iloc[0])

    today = datetime.utcnow().date()
    latest_any = max(
        [d.date() for d in [latest_backtest_end, latest_rolling_end] if d is not None],
        default=None,
    )
    if latest_any is not None:
        days_stale = (today - latest_any).days
        # Flag as "current" if data within last 45 days
        looks_current = days_stale <= 45
    else:
        days_stale = None
        looks_current = False

    res["latest_backtest_end"] = latest_backtest_end.date().isoformat() if latest_backtest_end else None
    res["latest_rolling_end"] = latest_rolling_end.date().isoformat() if latest_rolling_end else None
    res["monitoring_period"] = monitoring_period
    res["latest_any_date"] = latest_any.isoformat() if latest_any else None
    res["days_stale"] = days_stale
    res["data_looks_current"] = bool(looks_current)
    return res


def _recent_snapshot() -> Dict[str, Any]:
    """Champion vs Tuned Challenger snapshot for latest 2024+ period from comparison + monitoring."""
    out: Dict[str, Any] = {}

    # Comparison metrics
    cmp_csv = ARTIFACTS_DIR / "path_a_champion_vs_tuned_challenger.csv"
    df_cmp = _safe_read_csv(cmp_csv)
    recent_label = None
    if not df_cmp.empty and "period" in df_cmp.columns:
        # Prefer 2024-01-01_to_... if present; else last row
        mask_2024 = df_cmp["period"].astype(str).str.startswith("2024-01-01_to_")
        if mask_2024.any():
            recent_label = df_cmp[mask_2024]["period"].iloc[-1]
        else:
            recent_label = df_cmp["period"].iloc[-1]

    out["recent_period"] = str(recent_label) if recent_label is not None else None
    if recent_label is not None:
        sub = df_cmp[df_cmp["period"] == recent_label]
        for name in ["champion", "challenger_tuned"]:
            row = sub[sub["config_name"] == name]
            if row.empty:
                continue
            r = row.iloc[0]
            prefix = f"{name}_recent"
            out[f"{prefix}_cagr"] = float(r.get("cagr", np.nan))
            out[f"{prefix}_mdd"] = float(r.get("mdd", np.nan))
            out[f"{prefix}_mar"] = float(r.get("mar", np.nan))
            out[f"{prefix}_n_trades"] = int(r.get("n_trades", 0))
            out[f"{prefix}_trades_per_month"] = float(r.get("trades_per_month", np.nan))

    # Admission / chosen_rate from monitoring snapshot if available
    mon_csv = ARTIFACTS_DIR / "path_a_monitoring_snapshot.csv"
    df_mon = _safe_read_csv(mon_csv)
    if not df_mon.empty and "config_name" in df_mon.columns:
        for src_name, dst in [("champion", "champion"), ("challenger", "challenger_tuned")]:
            row = df_mon[df_mon["config_name"] == src_name]
            if row.empty:
                continue
            r = row.iloc[0]
            out[f"{dst}_chosen_rate"] = float(r.get("chosen_rate", np.nan))
            out[f"{dst}_rejected_max_positions"] = int(r.get("rejected_max_positions", 0))

    return out


def _refresh_governance_monitor() -> Dict[str, Any]:
    """Run governance monitor to refresh status, then read its CSV."""
    # Import and run in-process to reuse existing logic
    try:
        from pp_backtest.run_path_a_governance_monitor import main as gov_main  # type: ignore

        gov_main()
    except Exception:
        # Fallback: proceed with existing artifacts if import fails
        pass

    csv_path = ARTIFACTS_DIR / "path_a_governance_monitor.csv"
    df = _safe_read_csv(csv_path)
    if df.empty:
        return {}
    r = df.iloc[0]
    return {
        "default_config": r.get("default_config", "champion"),
        "tuned_challenger_status": r.get("tuned_challenger_status", "under_watch"),
        "qualifies_for_formal_review": bool(r.get("qualifies_for_formal_review", False)),
        "data_looks_current": bool(r.get("data_looks_current", True))
        if "data_looks_current" in df.columns
        else None,
    }


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    freshness = _data_freshness()
    snapshot = _recent_snapshot()
    gov = _refresh_governance_monitor()

    # Merge for CSV row
    row: Dict[str, Any] = {}
    row.update(freshness)
    row.update(snapshot)
    row.update(gov)

    ops_csv = ARTIFACTS_DIR / "path_a_ops_check.csv"
    pd.DataFrame([row]).to_csv(ops_csv, index=False)

    # Markdown report
    ops_md = ARTIFACTS_DIR / "path_a_ops_check.md"
    with open(ops_md, "w", encoding="utf-8") as f:
        f.write("# Path A Operational Check\n\n")

        # 0. Clear status line
        champion_default = gov.get("default_config", "champion") == "champion"
        tuned_under_watch = gov.get("tuned_challenger_status", "under_watch") == "under_watch"
        formal_open = bool(gov.get("qualifies_for_formal_review", False))
        data_ok = bool(freshness.get("data_looks_current"))
        f.write(
            f"**Status:** data current = {data_ok}; "
            f"champion default = {champion_default}; "
            f"tuned challenger under watch = {tuned_under_watch}; "
            f"formal review open = {formal_open}.\n\n"
        )

        # 1. Data freshness summary
        f.write("## 1. Data freshness summary\n\n")
        f.write(
            f"- Latest backtest end date: **{freshness.get('latest_backtest_end')}**\n"
            f"- Latest rolling window end date: **{freshness.get('latest_rolling_end')}**\n"
        )
        if freshness.get("monitoring_period"):
            f.write(f"- Monitoring snapshot period: **{freshness.get('monitoring_period')}**\n")
        if freshness.get("latest_any_date") is not None:
            f.write(
                f"- Latest any-date in stack: **{freshness.get('latest_any_date')}** "
                f"(staleness ≈ {freshness.get('days_stale')} days)\n"
            )
        f.write(
            f"- Data looks current (<=45 days stale): **{freshness.get('data_looks_current')}**\n\n"
        )

        # 2. Recent Champion vs Tuned Challenger snapshot
        f.write("## 2. Recent Champion vs Tuned Challenger snapshot\n\n")
        recent_period = snapshot.get("recent_period")
        f.write(f"- Period: **{recent_period}**\n\n" if recent_period else "- Period: **Unknown**\n\n")

        # Compact comparison table
        f.write("| config | period | CAGR | MDD | MAR | n_trades | trades_per_month | chosen_rate | rejected_max_positions |\n")
        f.write("|--------|--------|------|-----|-----|----------|------------------|------------|------------------------|\n")
        # Champion row
        f.write(
            f"| Champion | {recent_period or ''} | "
            f"{snapshot.get('champion_recent_cagr', np.nan):.2%} | "
            f"{snapshot.get('champion_recent_mdd', np.nan):.2%} | "
            f"{snapshot.get('champion_recent_mar', np.nan):.4f} | "
            f"{int(snapshot.get('champion_recent_n_trades', 0))} | "
            f"{snapshot.get('champion_recent_trades_per_month', np.nan):.2f} | "
            f"{snapshot.get('champion_chosen_rate', np.nan):.4g} | "
            f"{int(snapshot.get('champion_rejected_max_positions', 0))} |\n"
        )
        # Tuned Challenger row
        f.write(
            f"| Tuned Challenger | {recent_period or ''} | "
            f"{snapshot.get('challenger_tuned_recent_cagr', np.nan):.2%} | "
            f"{snapshot.get('challenger_tuned_recent_mdd', np.nan):.2%} | "
            f"{snapshot.get('challenger_tuned_recent_mar', np.nan):.4f} | "
            f"{int(snapshot.get('challenger_tuned_recent_n_trades', 0))} | "
            f"{snapshot.get('challenger_tuned_recent_trades_per_month', np.nan):.2f} | "
            f"{snapshot.get('challenger_tuned_chosen_rate', np.nan):.4g} | "
            f"{int(snapshot.get('challenger_tuned_rejected_max_positions', 0))} |\n\n"
        )

        # 3. Drift / alert section
        f.write("## 3. Drift & alerts\n\n")
        alerts = []
        days_stale = freshness.get("days_stale")
        if days_stale is not None and days_stale > 45:
            alerts.append(f"- Data is stale by {days_stale} days (>45); refresh FireAnt stack and rerun checks.")

        champ_mar = snapshot.get("champion_recent_mar")
        chal_mar = snapshot.get("challenger_tuned_recent_mar")
        champ_mdd = snapshot.get("champion_recent_mdd")
        chal_mdd = snapshot.get("challenger_tuned_recent_mdd")
        if (
            champ_mar is not None
            and chal_mar is not None
            and not np.isnan(champ_mar)
            and not np.isnan(chal_mar)
            and chal_mar >= champ_mar * 1.2  # meaningfully higher MAR
        ):
            # MDD not materially worse (<= ~3–4 ppts deeper)
            if (
                champ_mdd is not None
                and chal_mdd is not None
                and not np.isnan(champ_mdd)
                and not np.isnan(chal_mdd)
                and chal_mdd >= champ_mdd - 0.04
            ):
                alerts.append(
                    "- Tuned Challenger shows meaningfully higher recent MAR without materially worse MDD; "
                    "governance may need manual review."
                )

        if not alerts:
            f.write("- No immediate drift alerts; continue normal monitoring cadence.\n\n")
        else:
            for line in alerts:
                f.write(f"{line}\n")
            f.write("\n")

        # 4. Governance status
        f.write("## 4. Governance status\n\n")
        default_cfg = gov.get("default_config", "champion")
        tuned_status = gov.get("tuned_challenger_status", "under_watch")
        qualifies = bool(gov.get("qualifies_for_formal_review", False))

        f.write(f"- Champion default? **{default_cfg == 'champion'}**\n")
        f.write(f"- Tuned Challenger under watch? **{tuned_status == 'under_watch'}**\n")
        f.write(f"- Formal baseline review opened? **{qualifies}**\n\n")

        # 5. Plain-English operating recommendation & cadence
        f.write("## 5. Operating recommendation\n\n")
        if qualifies:
            f.write(
                "- **Open formal baseline review of Tuned Challenger vs Champion**, while keeping Champion as default "
                "until the review concludes. Monitor rolling MAR/MDD and admission pressure.\n"
            )
        else:
            f.write(
                "- **Keep Champion as default Path A** and **keep Tuned Challenger under watch**. "
                "Data stack appears reasonably current; re-run this ops check periodically to see if "
                "rolling performance and risk justify opening a formal review.\n"
            )

        f.write("\n## 6. Suggested cadence\n\n")
        f.write(
            "- Recommended rerun cadence: **weekly** or whenever a fresh batch of FireAnt data is ingested.\n"
            "- Trigger a **manual governance review** if:\n"
            "  - data becomes stale by more than ~45 days;\n"
            "  - Tuned Challenger sustains higher recent MAR over several ops checks **without** materially worse MDD;\n"
            "  - or governance monitor (`path_a_governance_monitor.md`) starts flagging that promotion conditions are close to satisfied.\n"
        )


if __name__ == "__main__":
    main()

