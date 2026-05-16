"""Data health checker for production trading pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.market_data import build_adv50_map
from src.trading.util.timeutil import utc_now_iso


@dataclass
class DataHealthResult:
    status: str  # PASS | WARN | CRITICAL_FAIL
    block_order_generation: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    latest_panel_date: str = ""
    generated_at: str = ""

    def to_status_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "BLOCK_ORDER_GENERATION": self.block_order_generation,
            "latest_panel_date": self.latest_panel_date,
            "generated_at": self.generated_at,
            "checks": self.checks,
        }


def _add(checks: List[Dict], name: str, level: str, message: str) -> None:
    checks.append({"check": name, "level": level, "message": message})


def run_data_health(config: LiveTradingConfig, asof_date: Optional[str] = None) -> DataHealthResult:
    checks: List[Dict[str, Any]] = []
    critical = False
    latest_panel_date = ""

    panel_path = config.panel_path
    if not panel_path.exists():
        _add(checks, "panel_exists", "CRITICAL", f"Panel missing: {panel_path}")
        critical = True
    else:
        panel = pd.read_parquet(panel_path)
        panel["date"] = pd.to_datetime(panel["date"])
        latest_panel_date = panel["date"].max().strftime("%Y-%m-%d")
        if asof_date and latest_panel_date < asof_date[:10]:
            _add(
                checks,
                "stale_panel",
                "WARN",
                f"latest_panel_date={latest_panel_date} < asof={asof_date}",
            )

        dup = panel.duplicated(subset=["symbol", "date"]).sum()
        if dup > 0:
            _add(checks, "duplicate_rows", "CRITICAL", f"{dup} duplicate symbol-date rows")
            critical = True

        if (panel["close"] <= 0).any():
            _add(checks, "zero_negative_close", "CRITICAL", "Non-positive close values found")
            critical = True

        if "volume" in panel.columns and (panel["volume"] < 0).any():
            _add(checks, "negative_volume", "CRITICAL", "Negative volume values found")
            critical = True

        missing_sym = panel.groupby("symbol")["close"].apply(lambda s: s.isna().sum()).sum()
        if missing_sym > 0:
            _add(checks, "missing_ohlcv", "CRITICAL", f"{missing_sym} missing close bars")
            critical = True

        # ADV unit check on sample symbols
        adv_map = build_adv50_map(panel)
        sample_syms = list(adv_map.keys())[:5]
        for sym in sample_syms:
            sdf = panel[panel["symbol"] == sym].sort_values("date").tail(60)
            if sdf.empty:
                continue
            c = sdf["close"].astype(float)
            v = sdf.get("volume", pd.Series(0, index=sdf.index)).astype(float)
            if "value" in sdf.columns:
                val = sdf["value"].astype(float).fillna(c * v * 1000)
            else:
                val = c * v * 1000
            adv_panel = val.rolling(50, min_periods=20).mean().iloc[-1]
            adv_map_val = float(adv_map[sym].dropna().iloc[-1]) if not adv_map[sym].dropna().empty else 0
            if adv_panel > 0 and adv_map_val > 0:
                ratio = adv_map_val / adv_panel
                if ratio > 500 or ratio < 0.002:
                    _add(
                        checks,
                        "adv_unit",
                        "CRITICAL",
                        f"{sym} ADV ratio {ratio:.2f} suggests unit bug",
                    )
                    critical = True
                    break

    vn_path = config.vnindex_path
    if not vn_path.exists():
        _add(checks, "vnindex", "CRITICAL", f"VNINDEX missing: {vn_path}")
        critical = True
    else:
        vnx = pd.read_parquet(vn_path)
        if vnx.empty:
            _add(checks, "vnindex", "CRITICAL", "VNINDEX file empty")
            critical = True

    _add(checks, "breadth", "WARN", "Breadth series not wired; dashboard may show pending")
    _add(checks, "macro", "WARN", "Macro data pending external source")

    if not critical and not any(c["level"] == "CRITICAL" for c in checks):
        status = "WARN" if any(c["level"] == "WARN" for c in checks) else "PASS"
    else:
        status = "CRITICAL_FAIL"

    return DataHealthResult(
        status=status,
        block_order_generation=critical or status == "CRITICAL_FAIL",
        checks=checks,
        latest_panel_date=latest_panel_date,
        generated_at=utc_now_iso(),
    )


def save_data_health(config: LiveTradingConfig, result: DataHealthResult) -> None:
    config.live_dir.mkdir(parents=True, exist_ok=True)
    status_path = config.data_health_status_path
    status_path.write_text(json.dumps(result.to_status_dict(), indent=2), encoding="utf-8")

    csv_path = config.live_dir / "data_health_report.csv"
    pd.DataFrame(result.checks).to_csv(csv_path, index=False)

    md_lines = [
        f"# Data Health Report — {result.generated_at}",
        f"Status: **{result.status}**",
        f"Block order generation: {result.block_order_generation}",
        f"Latest panel date: {result.latest_panel_date}",
        "",
    ]
    for c in result.checks:
        md_lines.append(f"- [{c['level']}] {c['check']}: {c['message']}")
    (config.live_dir / "data_health_report.md").write_text("\n".join(md_lines), encoding="utf-8")


def load_data_health_status(config: LiveTradingConfig) -> Dict[str, Any]:
    p = config.data_health_status_path
    if not p.exists():
        return {"status": "UNKNOWN", "BLOCK_ORDER_GENERATION": True}
    return json.loads(p.read_text(encoding="utf-8"))
