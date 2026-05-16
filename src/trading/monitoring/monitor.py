"""Monitoring orchestration."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.trading.config import LiveTradingConfig
from src.trading.monitoring.alerts import MockAlertHook
from src.trading.monitoring.kill_switch import evaluate_kill_switch, save_kill_switch
from src.trading.util.timeutil import utc_now_iso


def write_alerts_md(config: LiveTradingConfig, asof_date: str, lines: list[str]) -> Path:
    config.live_dir.mkdir(parents=True, exist_ok=True)
    path = config.live_dir / f"alerts_{asof_date.replace('-', '')}.md"
    header = [f"# Alerts — {asof_date}", f"Generated: {utc_now_iso()}", ""]
    path.write_text("\n".join(header + lines), encoding="utf-8")
    return path


def run_monitoring(
    config: LiveTradingConfig,
    asof_date: str,
    data_health: Dict[str, Any],
    reconciliation: Dict[str, Any],
) -> Dict[str, Any]:
    ks = evaluate_kill_switch(config, data_health, reconciliation)
    save_kill_switch(config, ks)
    hook = MockAlertHook(log_path=config.live_dir / "alerts.jsonl")
    if ks.status == "BLOCK":
        hook.send("error", f"Kill switch BLOCK on {asof_date}", ks.to_dict())
        write_alerts_md(config, asof_date, [f"**BLOCK**: {', '.join(ks.reasons)}"])
    elif ks.status == "WARN":
        hook.send("warning", f"Kill switch WARN on {asof_date}", ks.to_dict())
        write_alerts_md(config, asof_date, [f"**WARN**: {', '.join(ks.reasons)}"])
    else:
        write_alerts_md(config, asof_date, ["Kill switch CLEAR"])
    return ks.to_dict()
