"""DNSE read-only shadow — diff broker state vs internal paper state."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.brokers.dnse import DNSEAuthError, DNSEBroker
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.portfolio_state import REPO, get_current_nav_vnd, load_portfolio_state
from src.trading.util.timeutil import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class ShadowReport:
    asof_date: str
    status: str  # CLEAN | MISMATCH | AUTH_FAILED
    dnse_nav: Optional[float] = None
    internal_nav: Optional[float] = None
    nav_divergence_pct: Optional[float] = None
    unexpected_positions: List[Dict[str, Any]] = field(default_factory=list)
    missing_positions: List[Dict[str, Any]] = field(default_factory=list)
    qty_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_line(self) -> str:
        if self.status == "AUTH_FAILED":
            return f"DNSE Shadow: status=AUTH_FAILED | error={self.error}"
        nav_pct = f"{self.nav_divergence_pct:.1f}%" if self.nav_divergence_pct is not None else "n/a"
        mismatches = (
            len(self.unexpected_positions)
            + len(self.missing_positions)
            + len(self.qty_mismatches)
        )
        return (
            f"DNSE Shadow: status={self.status} | NAV divergence={nav_pct} | "
            f"mismatches={mismatches}"
        )


def _normalize_positions(positions: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in positions:
        sym = str(p.get("symbol", "")).upper().strip()
        if not sym:
            continue
        qty = int(p.get("qty", p.get("quantity", 0)))
        if qty > 0:
            out[sym] = qty
    return out


def _load_internal_positions(config: TradingConfig) -> Dict[str, int]:
    paths: List[Path] = []
    if isinstance(config, LiveTradingConfig):
        paths.append(config.paper_positions_path)
    paths.append(config.live_dir / "paper_positions.csv")
    paths.append(config.data_root / "live" / "paper_positions.csv")

    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(path)
            if df.empty:
                continue
            sym_col = "symbol" if "symbol" in df.columns else None
            qty_col = "quantity" if "quantity" in df.columns else None
            if not sym_col or not qty_col:
                continue
            positions = []
            for _, row in df.iterrows():
                positions.append(
                    {"symbol": str(row[sym_col]).upper(), "qty": int(float(row[qty_col] or 0))}
                )
            loaded = _normalize_positions(positions)
            if loaded:
                return loaded
        except (OSError, ValueError, pd.errors.EmptyDataError) as exc:
            logger.warning("Failed reading paper positions %s: %s", path, exc)

    state = load_portfolio_state(config.live_dir / "portfolio_state.json")
    if not state:
        state = load_portfolio_state()
    pos_path_raw = state.get("positions_path")
    if pos_path_raw:
        pos_path = Path(pos_path_raw)
        if not pos_path.is_absolute():
            pos_path = REPO / pos_path
        if pos_path.exists():
            try:
                df = pd.read_csv(pos_path)
                if "symbol" in df.columns:
                    qty_col = "quantity" if "quantity" in df.columns else "qty"
                    if qty_col in df.columns:
                        positions = [
                            {"symbol": str(r["symbol"]).upper(), "qty": int(float(r[qty_col] or 0))}
                            for _, r in df.iterrows()
                        ]
                        return _normalize_positions(positions)
            except (OSError, ValueError, pd.errors.EmptyDataError):
                pass
    return {}


def _load_internal_nav(config: TradingConfig, positions: Dict[str, int]) -> Optional[float]:
    state_paths = [
        config.live_dir / "portfolio_state.json",
        config.data_root / "live" / "portfolio_state.json",
    ]
    for p in state_paths:
        nav = get_current_nav_vnd(load_portfolio_state(p))
        if nav is not None:
            return nav
    nav = get_current_nav_vnd()
    if nav is not None:
        return nav
    if isinstance(config, LiveTradingConfig) and config.paper_positions_path.exists():
        try:
            df = pd.read_csv(config.paper_positions_path)
            if "market_value_VND" in df.columns:
                return float(df["market_value_VND"].fillna(0).astype(float).sum())
        except (OSError, ValueError, pd.errors.EmptyDataError):
            pass
    return None


def diff_positions(
    dnse_positions: Dict[str, int],
    internal_positions: Dict[str, int],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    unexpected: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    mismatches: List[Dict[str, Any]] = []

    for sym, qty in dnse_positions.items():
        if sym not in internal_positions:
            unexpected.append({"symbol": sym, "dnse_qty": qty})
        elif internal_positions[sym] != qty:
            mismatches.append(
                {
                    "symbol": sym,
                    "dnse_qty": qty,
                    "internal_qty": internal_positions[sym],
                }
            )

    for sym, qty in internal_positions.items():
        if sym not in dnse_positions:
            missing.append({"symbol": sym, "internal_qty": qty})

    return unexpected, missing, mismatches


def compute_nav_divergence_pct(
    dnse_nav: Optional[float], internal_nav: Optional[float]
) -> Optional[float]:
    if dnse_nav is None or internal_nav is None or internal_nav <= 0:
        return None
    return abs(dnse_nav - internal_nav) / internal_nav * 100.0


class DNSEShadowRunner:
    """Fetch DNSE read-only state and diff against internal paper ledger."""

    def __init__(
        self,
        config: TradingConfig,
        *,
        broker: Optional[DNSEBroker] = None,
    ):
        self.config = config
        self.config.ensure_dirs()
        self.shadow_dir = getattr(config, "shadow_dir", config.data_root / "shadow")
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        self._broker = broker

    def report_path(self, asof_date: str) -> Path:
        safe = asof_date.replace("/", "-")
        return self.shadow_dir / f"shadow_report_{safe}.json"

    def run(self, asof_date: str) -> ShadowReport:
        report = ShadowReport(asof_date=asof_date, status="MISMATCH")
        try:
            broker = self._broker or DNSEBroker(self.config)
            broker.login()
            balances = broker.get_balances()
            dnse_positions = _normalize_positions(broker.get_positions())
            internal_positions = _load_internal_positions(self.config)

            report.dnse_nav = balances.get("total_portfolio_value_vnd")
            report.internal_nav = _load_internal_nav(self.config, internal_positions)
            report.nav_divergence_pct = compute_nav_divergence_pct(
                report.dnse_nav, report.internal_nav
            )
            (
                report.unexpected_positions,
                report.missing_positions,
                report.qty_mismatches,
            ) = diff_positions(dnse_positions, internal_positions)

            has_mismatch = (
                report.unexpected_positions
                or report.missing_positions
                or report.qty_mismatches
                or (
                    report.nav_divergence_pct is not None
                    and report.nav_divergence_pct > 0.01
                )
            )
            report.status = "MISMATCH" if has_mismatch else "CLEAN"
        except DNSEAuthError as exc:
            report.status = "AUTH_FAILED"
            report.error = str(exc)
            logger.warning("DNSE shadow auth failed: %s", exc)
        except Exception as exc:
            report.status = "AUTH_FAILED"
            report.error = f"{type(exc).__name__}: {exc}"
            logger.warning("DNSE shadow failed: %s", exc)

        self._write_report(report)
        return report

    def _write_report(self, report: ShadowReport) -> None:
        path = self.report_path(report.asof_date)
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        logger.info(report.summary_line())
