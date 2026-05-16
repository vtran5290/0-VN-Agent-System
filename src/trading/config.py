"""Trading configuration loaded from config/trading.yaml and environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YAML = REPO_ROOT / "config" / "trading.yaml"
LIVE_YAML = REPO_ROOT / "config" / "live_trading.yaml"


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass
class TradingConfig:
    broker: str = "paper"
    live_trading: bool = False
    dry_run: bool = True
    confirm_live_broker: str = ""

    max_position_pct_nav: float = 0.10
    max_total_exposure_pct_nav: float = 0.95
    max_order_value_vnd: float = 500_000_000.0
    max_daily_new_positions: int = 3
    min_adv50_vnd: float = 500_000_000.0
    max_order_pct_adv50: float = 0.05
    market_data_max_age_hours: float = 36.0
    allow_margin: bool = False

    initial_cash_vnd: float = 1_000_000_000.0
    data_root: Path = field(default_factory=lambda: REPO_ROOT / "data" / "trading")

    @property
    def order_proposals_dir(self) -> Path:
        return self.data_root / "order_proposals"

    @property
    def orders_dir(self) -> Path:
        return self.data_root / "orders"

    @property
    def audit_dir(self) -> Path:
        return self.data_root / "audit"

    @property
    def reconciliation_dir(self) -> Path:
        return self.data_root / "reconciliation"

    @property
    def reports_dir(self) -> Path:
        return self.data_root / "reports"

    @property
    def audit_log_path(self) -> Path:
        return self.audit_dir / "order_events.jsonl"

    @property
    def paper_broker_state_path(self) -> Path:
        return self.data_root / "paper_broker_state.json"

    @property
    def live_dir(self) -> Path:
        return self.data_root / "live"

    @property
    def baseline_positions_dir(self) -> Path:
        return self.data_root / "baseline_positions"

    @property
    def dashboard_dir(self) -> Path:
        return self.live_dir / "dashboard"

    @property
    def proposals_dir(self) -> Path:
        return self.data_root / "proposals"

    def ensure_dirs(self) -> None:
        for d in (
            self.data_root,
            self.order_proposals_dir,
            self.proposals_dir,
            self.orders_dir,
            self.audit_dir,
            self.reconciliation_dir,
            self.reports_dir,
            self.live_dir,
            self.baseline_positions_dir,
            self.dashboard_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def live_dnse_orders_allowed(self) -> bool:
        """Triple gate for future real DNSE order placement."""
        return (
            self.live_trading
            and not self.dry_run
            and self.confirm_live_broker.upper() == "DNSE"
            and self.broker.lower() == "dnse"
            and self.max_order_value_vnd > 0
        )

    def paper_execution_allowed(self) -> bool:
        """Paper broker may submit when dry_run is off and live_trading is on (paper mode)."""
        return (
            self.broker.lower() == "paper"
            and self.live_trading
            and not self.dry_run
        )


def load_trading_config(
    yaml_path: Optional[Path] = None,
    data_root_override: Optional[Path] = None,
) -> TradingConfig:
    path = yaml_path or DEFAULT_YAML
    raw: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    data_root = data_root_override
    if data_root is None:
        dr = raw.get("data_root", "data/trading")
        data_root = Path(dr) if Path(dr).is_absolute() else REPO_ROOT / dr

    cfg = TradingConfig(
        broker=os.environ.get("BROKER", raw.get("broker", "paper")),
        live_trading=_env_bool("LIVE_TRADING", bool(raw.get("live_trading", False))),
        dry_run=_env_bool("DRY_RUN", bool(raw.get("dry_run", True))),
        confirm_live_broker=os.environ.get("CONFIRM_LIVE_BROKER", ""),
        max_position_pct_nav=_env_float(
            "TRADING_MAX_POSITION_PCT_NAV",
            float(raw.get("max_position_pct_nav", 0.10)),
        ),
        max_total_exposure_pct_nav=_env_float(
            "TRADING_MAX_TOTAL_EXPOSURE_PCT_NAV",
            float(raw.get("max_total_exposure_pct_nav", 0.95)),
        ),
        max_order_value_vnd=_env_float(
            "TRADING_MAX_ORDER_VALUE_VND",
            float(raw.get("max_order_value_vnd", 500_000_000)),
        ),
        max_daily_new_positions=_env_int(
            "TRADING_MAX_DAILY_NEW_POSITIONS",
            int(raw.get("max_daily_new_positions", 3)),
        ),
        min_adv50_vnd=_env_float(
            "TRADING_MIN_ADV50_VND",
            float(raw.get("min_adv50_vnd", 500_000_000)),
        ),
        max_order_pct_adv50=_env_float(
            "TRADING_MAX_ORDER_PCT_ADV50",
            float(raw.get("max_order_pct_adv50", 0.05)),
        ),
        market_data_max_age_hours=_env_float(
            "TRADING_MARKET_DATA_MAX_AGE_HOURS",
            float(raw.get("market_data_max_age_hours", 36)),
        ),
        allow_margin=_env_bool("TRADING_ALLOW_MARGIN", bool(raw.get("allow_margin", False))),
        initial_cash_vnd=_env_float(
            "TRADING_INITIAL_CASH_VND",
            float(raw.get("initial_cash_vnd", 1_000_000_000)),
        ),
        data_root=data_root,
    )
    return cfg


@dataclass
class LiveTradingConfig(TradingConfig):
    """Extended config for live-workflow / real-capital readiness."""

    mode: str = "paper"
    portfolio_size_vnd: float = 5_000_000_000.0
    max_slots: int = 20
    adv_participation: float = 0.10
    max_daily_orders: int = 10
    min_sell_lock_bars: int = 5
    max_daily_loss_pct: float = 0.02
    max_portfolio_drawdown_pct: float = 0.15

    allow_pts_shadow: bool = False
    allow_s3_capital: bool = False
    allow_sector_l4_block: bool = False
    allow_performance_throttle: bool = False
    require_regime_bull: bool = True
    require_data_health: bool = True
    require_reconciliation_clean: bool = True

    enable_live_auto: bool = False
    require_manual_approval_for_live_manual: bool = True
    allow_same_day_same_symbol_side: bool = False

    block_on_data_health_critical: bool = True
    block_on_reconciliation_failure: bool = True
    block_on_kill_switch: bool = True
    block_on_adv_unit_failure: bool = True

    scan_csv_path: Path = field(
        default_factory=lambda: REPO_ROOT
        / "data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv"
    )
    panel_path: Path = field(
        default_factory=lambda: REPO_ROOT / "data/research/ema_cloud/ohlcv_panel_ext2012.parquet"
    )
    vnindex_path: Path = field(
        default_factory=lambda: REPO_ROOT / "data/fireant_ssot/ta_vnindex.parquet"
    )
    ex_vin3_symbols: list = field(default_factory=lambda: ["VIC", "VHM", "VRE", "VPL"])
    production_strategy: str = "A3_DP"

    @property
    def paper_trades_path(self) -> Path:
        return self.live_dir / "paper_trades.csv"

    @property
    def paper_positions_path(self) -> Path:
        return self.live_dir / "paper_positions.csv"

    @property
    def data_health_status_path(self) -> Path:
        return self.live_dir / "data_health_status.json"

    @property
    def kill_switch_status_path(self) -> Path:
        return self.live_dir / "kill_switch_status.json"

    @property
    def reconciliation_status_path(self) -> Path:
        return self.live_dir / "reconciliation_status.json"

    def order_intents_path(self, asof_date: str) -> Path:
        return self.live_dir / f"order_intents_{asof_date.replace('-', '')}.csv"

    def risk_check_path(self, asof_date: str) -> Path:
        return self.live_dir / f"risk_check_{asof_date.replace('-', '')}.csv"

    def live_auto_allowed(self) -> bool:
        return self.enable_live_auto and self.mode == "live_auto"


def load_live_trading_config(
    trading_yaml: Optional[Path] = None,
    live_yaml: Optional[Path] = None,
    data_root_override: Optional[Path] = None,
) -> LiveTradingConfig:
    base = load_trading_config(trading_yaml, data_root_override)
    live_path = live_yaml or LIVE_YAML
    raw: dict[str, Any] = {}
    if live_path.exists():
        with open(live_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    mode = os.environ.get("TRADING_MODE", raw.get("mode", "paper"))
    sf = raw.get("strategy_flags", {}) or {}
    ef = raw.get("execution_flags", {}) or {}
    safety = raw.get("safety", {}) or {}
    paths = raw.get("paths", {}) or {}

    scan_path = paths.get("scan_csv_path", "")
    panel_path = paths.get("panel_path", "")
    vnindex_path = paths.get("vnindex_path", "")

    return LiveTradingConfig(
        broker=base.broker,
        live_trading=_env_bool("LIVE_TRADING", ef.get("live_trading", base.live_trading)),
        dry_run=_env_bool("DRY_RUN", ef.get("dry_run", base.dry_run)),
        confirm_live_broker=base.confirm_live_broker,
        max_position_pct_nav=base.max_position_pct_nav,
        max_total_exposure_pct_nav=base.max_total_exposure_pct_nav,
        max_order_value_vnd=_env_float(
            "TRADING_MAX_ORDER_VALUE_VND",
            float(raw.get("max_order_value_VND", base.max_order_value_vnd)),
        ),
        max_daily_new_positions=_env_int(
            "TRADING_MAX_DAILY_NEW_POSITIONS",
            int(raw.get("max_daily_new_positions", base.max_daily_new_positions)),
        ),
        min_adv50_vnd=base.min_adv50_vnd,
        max_order_pct_adv50=base.max_order_pct_adv50,
        market_data_max_age_hours=base.market_data_max_age_hours,
        allow_margin=base.allow_margin,
        initial_cash_vnd=_env_float(
            "TRADING_INITIAL_CASH_VND",
            float(raw.get("portfolio_size_VND", base.initial_cash_vnd)),
        ),
        data_root=base.data_root,
        mode=mode,
        portfolio_size_vnd=float(raw.get("portfolio_size_VND", 5_000_000_000)),
        max_slots=int(raw.get("max_slots", 20)),
        adv_participation=float(raw.get("adv_participation", 0.10)),
        max_daily_orders=int(raw.get("max_daily_orders", 10)),
        min_sell_lock_bars=int(raw.get("min_sell_lock_bars", 5)),
        max_daily_loss_pct=float(raw.get("max_daily_loss_pct", 0.02)),
        max_portfolio_drawdown_pct=float(raw.get("max_portfolio_drawdown_pct", 0.15)),
        allow_pts_shadow=bool(sf.get("allow_pts_shadow", False)),
        allow_s3_capital=bool(sf.get("allow_s3_capital", False)),
        allow_sector_l4_block=bool(sf.get("allow_sector_l4_block", False)),
        allow_performance_throttle=bool(sf.get("allow_performance_throttle", False)),
        require_regime_bull=bool(sf.get("require_regime_bull", True)),
        require_data_health=bool(sf.get("require_data_health", True)),
        require_reconciliation_clean=bool(sf.get("require_reconciliation_clean", True)),
        enable_live_auto=bool(ef.get("enable_live_auto", False)),
        require_manual_approval_for_live_manual=bool(
            ef.get("require_manual_approval_for_live_manual", True)
        ),
        allow_same_day_same_symbol_side=bool(
            ef.get("allow_same_day_same_symbol_side", False)
        ),
        block_on_data_health_critical=bool(safety.get("block_on_data_health_critical", True)),
        block_on_reconciliation_failure=bool(safety.get("block_on_reconciliation_failure", True)),
        block_on_kill_switch=bool(safety.get("block_on_kill_switch", True)),
        block_on_adv_unit_failure=bool(safety.get("block_on_adv_unit_failure", True)),
        scan_csv_path=(
            Path(scan_path)
            if scan_path and Path(scan_path).is_absolute()
            else REPO_ROOT / scan_path
            if scan_path
            else REPO_ROOT / "data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv"
        ),
        panel_path=(
            Path(panel_path)
            if panel_path and Path(panel_path).is_absolute()
            else REPO_ROOT / panel_path
            if panel_path
            else REPO_ROOT / "data/research/ema_cloud/ohlcv_panel_ext2012.parquet"
        ),
        vnindex_path=(
            Path(vnindex_path)
            if vnindex_path and Path(vnindex_path).is_absolute()
            else REPO_ROOT / vnindex_path
            if vnindex_path
            else REPO_ROOT / "data/fireant_ssot/ta_vnindex.parquet"
        ),
        ex_vin3_symbols=list(raw.get("ex_vin3_symbols", ["VIC", "VHM", "VRE", "VPL"])),
        production_strategy=str(raw.get("production_strategy", "A3_DP")),
    )
