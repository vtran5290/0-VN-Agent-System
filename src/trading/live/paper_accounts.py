"""Named paper-trading account configuration and initialization."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from src.trading.config import REPO_ROOT, LiveTradingConfig, load_live_trading_config
from src.trading.live.csv_parse import parse_csv_bool
from src.trading.live.path_safety import validate_live_output_path

REFERENCE_SIZING_WARNING_TEXT = (
    "This account may show cash drag because scan sizing is based on reference NAV, "
    "not account-scaled target sizing."
)

PAPER_ACCOUNTS_YAML = REPO_ROOT / "config" / "paper_accounts.yaml"
DEFAULT_ACCOUNT_ID = "A3_PROD_PAPER_5B"
A3_ACCOUNT_TYPES = frozenset({
    "a3_production",
    "a3_production_small",
    "a3_production_scale",
    "a3_production_scale_stress",
})

# Daily paper-live run order (A3 only; S3 separate via s3-shadow)
A3_PAPER_RUN_ORDER = [
    "A3_DSE_PILOT_PAPER_SMALL",
    "A3_PROD_PAPER_5B",
    "A3_SCALE_PAPER_10B",
    "A3_SCALE_PAPER_20B",
]


def get_a3_paper_run_order() -> List[str]:
    return list(A3_PAPER_RUN_ORDER)


def scan_size_basis_metadata(account: PaperAccountConfig) -> Dict[str, Any]:
    warn = (
        account.starting_cash_VND > account.scan_reference_nav_VND
        and not account.account_nav_scaling_enabled
    )
    return {
        "scan_size_basis": account.scan_size_basis,
        "scan_reference_nav_VND": account.scan_reference_nav_VND,
        "account_nav_scaling_enabled": account.account_nav_scaling_enabled,
        "reference_sizing_warning": warn,
        "reference_sizing_warning_text": REFERENCE_SIZING_WARNING_TEXT if warn else "",
    }


def account_observation_role(account: PaperAccountConfig) -> str:
    """Operator label for dashboard / compare (not strategy)."""
    mapping = {
        "A3_DSE_PILOT_PAPER_SMALL": "tiny pilot (future DSE mimic)",
        "A3_PROD_PAPER_5B": "reference (A3 production paper)",
        "A3_SCALE_PAPER_10B": "scale check (10B NAV)",
        "A3_SCALE_PAPER_20B": "liquidity stress (20B NAV)",
    }
    return mapping.get(account.account_id, account.type)


@dataclass
class PaperAccountConfig:
    account_id: str
    enabled: bool = True
    type: str = "a3_production"
    strategy: str = "A3_DP"
    starting_cash_VND: float = 5_000_000_000.0
    max_slots: Optional[int] = 20
    adv_participation: float = 0.10
    max_daily_new_positions: int = 3
    max_daily_orders: int = 10
    max_order_value_VND: float = 500_000_000.0
    allow_margin: bool = False
    allow_s3: bool = False
    allow_pts: bool = False
    allow_real_orders: bool = False
    allow_dnse: bool = False
    allow_dse: bool = False
    separate_pnl: bool = False
    sizing_policy: str = "scan_size_strict"
    min_trade_value_VND: float = 0.0
    scan_size_basis: str = "5B_reference_scan"
    scan_reference_nav_VND: float = 5_000_000_000.0
    account_nav_scaling_enabled: bool = False
    ledger_root: Path = field(default_factory=lambda: REPO_ROOT / "data/trading/live/accounts/A3_PROD_PAPER_5B")

    @property
    def is_a3_production(self) -> bool:
        return self.type in A3_ACCOUNT_TYPES

    @property
    def is_s3_shadow(self) -> bool:
        return self.type == "s3_shadow"

    def resolve_ledger_root(self) -> Path:
        p = self.ledger_root
        if not p.is_absolute():
            p = REPO_ROOT / p
        validate_live_output_path(p, context=f"paper_account:{self.account_id}")
        return p


def load_paper_accounts_config(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or PAPER_ACCOUNTS_YAML
    if not p.exists():
        return {"default_account": DEFAULT_ACCOUNT_ID, "paper_accounts": {}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_paper_accounts(enabled_only: bool = False) -> List[PaperAccountConfig]:
    raw = load_paper_accounts_config()
    accounts = raw.get("paper_accounts", {}) or {}
    out: List[PaperAccountConfig] = []
    for aid, spec in accounts.items():
        pa = _parse_account(aid, spec)
        if enabled_only and not pa.enabled:
            continue
        out.append(pa)
    return out


def get_paper_account(account_id: str, path: Optional[Path] = None) -> PaperAccountConfig:
    raw = load_paper_accounts_config(path)
    accounts = raw.get("paper_accounts", {}) or {}
    if account_id not in accounts:
        raise KeyError(f"Unknown paper account: {account_id}")
    return _parse_account(account_id, accounts[account_id])


def get_default_account_id(path: Optional[Path] = None) -> str:
    raw = load_paper_accounts_config(path)
    return str(raw.get("default_account", DEFAULT_ACCOUNT_ID))


def _parse_account(account_id: str, spec: Dict[str, Any]) -> PaperAccountConfig:
    lr = spec.get("ledger_root", f"data/trading/live/accounts/{account_id}")
    max_slots = spec.get("max_slots")
    return PaperAccountConfig(
        account_id=account_id,
        enabled=parse_csv_bool(spec.get("enabled", True)),
        type=str(spec.get("type", "a3_production")),
        strategy=str(spec.get("strategy", "A3_DP")),
        starting_cash_VND=float(spec.get("starting_cash_VND", 0)),
        max_slots=int(max_slots) if max_slots is not None else None,
        adv_participation=float(spec.get("adv_participation", 0.10)),
        max_daily_new_positions=int(spec.get("max_daily_new_positions", 3)),
        max_daily_orders=int(spec.get("max_daily_orders", 10)),
        max_order_value_VND=float(spec.get("max_order_value_VND", 500_000_000)),
        allow_margin=parse_csv_bool(spec.get("allow_margin", False)),
        allow_s3=parse_csv_bool(spec.get("allow_s3", False)),
        allow_pts=parse_csv_bool(spec.get("allow_pts", False)),
        allow_real_orders=parse_csv_bool(spec.get("allow_real_orders", False)),
        allow_dnse=parse_csv_bool(spec.get("allow_dnse", False)),
        allow_dse=parse_csv_bool(spec.get("allow_dse", False)),
        separate_pnl=parse_csv_bool(spec.get("separate_pnl", True)),
        sizing_policy=str(spec.get("sizing_policy", "scan_size_strict")),
        min_trade_value_VND=float(spec.get("min_trade_value_VND", 0)),
        scan_size_basis=str(spec.get("scan_size_basis", "5B_reference_scan")),
        scan_reference_nav_VND=float(spec.get("scan_reference_nav_VND", 5_000_000_000)),
        account_nav_scaling_enabled=parse_csv_bool(spec.get("account_nav_scaling_enabled", False)),
        ledger_root=Path(lr),
    )


def resolve_account_paths(account: PaperAccountConfig) -> Dict[str, Path]:
    root = account.resolve_ledger_root()
    return {
        "ledger_root": root,
        "paper_trades": root / "paper_trades.csv",
        "paper_positions": root / "paper_positions.csv",
        "paper_broker_state": root / "paper_broker_state.json",
        "paper_equity_curve": root / "paper_equity_curve.csv",
        "dashboard": root / "dashboard",
        "orders": root / "orders",
        "order_proposals": root / "order_proposals",
        "audit": root / "audit",
        "reconciliation": root / "reconciliation",
        "run_locks": root / "run_locks",
        "run_manifests": root / "run_manifests",
    }


def build_live_config_for_account(
    account_id: Optional[str] = None,
    data_root_override: Optional[Path] = None,
    ledger_root_override: Optional[Path] = None,
) -> tuple[LiveTradingConfig, PaperAccountConfig]:
    """Return LiveTradingConfig scoped to account ledger + risk overrides."""
    aid = account_id or get_default_account_id()
    acct = get_paper_account(aid)
    if acct.is_s3_shadow:
        raise ValueError(
            f"Account {aid} is S3 shadow only. Use: python -m src.trading.cli s3-shadow update"
        )
    base = load_live_trading_config(data_root_override=data_root_override)
    root = ledger_root_override if ledger_root_override else acct.resolve_ledger_root()
    root.mkdir(parents=True, exist_ok=True)

    cfg = LiveTradingConfig(
        broker="paper",
        live_trading=base.live_trading,
        dry_run=base.dry_run,
        confirm_live_broker=base.confirm_live_broker,
        max_position_pct_nav=base.max_position_pct_nav,
        max_total_exposure_pct_nav=base.max_total_exposure_pct_nav,
        max_order_value_vnd=acct.max_order_value_VND,
        max_daily_new_positions=acct.max_daily_new_positions,
        min_adv50_vnd=base.min_adv50_vnd,
        max_order_pct_adv50=base.max_order_pct_adv50,
        market_data_max_age_hours=base.market_data_max_age_hours,
        allow_margin=acct.allow_margin,
        initial_cash_vnd=acct.starting_cash_VND,
        data_root=REPO_ROOT / "data" / "trading",
        mode=base.mode,
        portfolio_size_vnd=acct.starting_cash_VND,
        max_slots=int(acct.max_slots or 20),
        adv_participation=acct.adv_participation,
        max_daily_orders=acct.max_daily_orders,
        allow_pts_shadow=acct.allow_pts,
        allow_s3_capital=acct.allow_s3,
        scan_csv_path=base.scan_csv_path,
        panel_path=base.panel_path,
        vnindex_path=base.vnindex_path,
        production_strategy=acct.strategy,
        allow_sample_scan=base.allow_sample_scan,
        allow_missing_reconciliation=base.allow_missing_reconciliation,
        require_manual_review_approval=base.require_manual_review_approval,
        allow_risk_reducing_sell_when_regime_blocked=base.allow_risk_reducing_sell_when_regime_blocked,
        sell_exit_liquidity_policy=base.sell_exit_liquidity_policy,
        block_sell_on_dirty_reconciliation=base.block_sell_on_dirty_reconciliation,
    )
    cfg.account_id = aid
    cfg.account_root = root
    cfg.paper_account = acct  # type: ignore[attr-defined]
    return cfg, acct


def initialize_paper_account(
    account_id: str,
    *,
    reset: bool = False,
    confirm_reset: bool = False,
    ledger_root_override: Optional[Path] = None,
) -> Dict[str, Path]:
    acct = get_paper_account(account_id)
    if ledger_root_override is not None:
        acct.ledger_root = ledger_root_override
    paths = resolve_account_paths(acct)
    root = paths["ledger_root"]

    if reset:
        if not confirm_reset:
            raise ValueError("Reset requires confirm_reset=True (--confirm-reset)")
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

    for key in ("dashboard", "orders", "order_proposals", "audit", "reconciliation", "run_locks", "run_manifests"):
        paths[key].mkdir(parents=True, exist_ok=True)

    if acct.is_a3_production:
        if reset or not paths["paper_trades"].exists():
            pd.DataFrame(columns=[]).to_csv(paths["paper_trades"], index=False)
        if reset or not paths["paper_positions"].exists():
            from src.trading.live.paper_ledger import POSITIONS_COLS
            pd.DataFrame(columns=POSITIONS_COLS).to_csv(paths["paper_positions"], index=False)
        if reset or not paths["paper_broker_state"].exists():
            state = {
                "logged_in": True,
                "cash_vnd": acct.starting_cash_VND,
                "positions": {},
                "orders": {},
                "account_id": account_id,
            }
            paths["paper_broker_state"].write_text(json.dumps(state, indent=2), encoding="utf-8")

    if acct.is_s3_shadow:
        from src.trading.live.paper_ledger import TRADES_COLS
        paths["dashboard"].mkdir(parents=True, exist_ok=True)
        for name in ("s3_shadow_trades.csv", "s3_shadow_positions.csv", "s3_shadow_equity_curve.csv"):
            p = paths["ledger_root"] / name
            if reset or not p.exists():
                pd.DataFrame({c: pd.Series(dtype=object) for c in TRADES_COLS}).to_csv(p, index=False)

    return paths
