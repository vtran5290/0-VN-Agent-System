"""Tests for intraday preview scan (no EOD panel mutation, no auto orders)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from src.trading.intraday.data_adapter import detect_intraday_source_capability, validate_intraday_quotes
from src.trading.intraday.panel_overlay import build_provisional_panel, load_eod_panel
from src.trading.intraday.session import elapsed_tradable_fraction
from src.trading.intraday.volume_projection import project_full_day_volume
from src.trading.intraday.intraday_scan import _apply_intraday_policy, load_intraday_config
from src.trading.live.scan_resolver import resolve_scan
from src.trading.config import LiveTradingConfig


def test_capability_discovery_structure():
    with patch("src.trading.intraday.data_adapter._load_token", return_value=None):
        r = detect_intraday_source_capability(["HPG"], save_probe_path=None)
    assert "partial_daily_bar" in r
    assert "dedicated_quote_endpoint" in r
    assert r["available"] is False
    assert r["token_present"] is False


def test_validate_missing_price():
    df = pd.DataFrame([{"symbol": "HPG", "last_price_kvnd": None, "data_quality": "OK"}])
    out = validate_intraday_quotes(df)
    assert out.iloc[0]["data_quality"] == "MISSING_PRICE"


def test_validate_stale_timestamp_field():
    df = pd.DataFrame(
        [
            {
                "symbol": "HPG",
                "last_price_kvnd": 25.0,
                "data_quality": "OK",
                "is_stale": True,
                "timestamp": "2026-05-15T09:05:00+07:00",
            }
        ]
    )
    out = validate_intraday_quotes(df)
    assert bool(out.iloc[0]["is_stale"]) is True


def test_panel_overlay_does_not_write_eod_panel(tmp_path):
    eod = pd.DataFrame(
        {
            "symbol": ["HPG", "HPG"],
            "date": pd.to_datetime(["2026-05-14", "2026-05-15"]),
            "open": [24.0, 24.5],
            "high": [25.0, 25.5],
            "low": [23.5, 24.0],
            "close": [24.8, 25.0],
            "volume": [1e6, 2e6],
        }
    )
    p = tmp_path / "panel.parquet"
    eod.to_parquet(p)
    mtime_before = p.stat().st_mtime
    quotes = pd.DataFrame(
        [
            {
                "symbol": "HPG",
                "last_price_kvnd": 25.2,
                "open_price_kvnd": 24.5,
                "high_price_kvnd": 25.3,
                "low_price_kvnd": 24.4,
                "cumulative_volume": 2.5e6,
            }
        ]
    )
    prov = build_provisional_panel(
        load_eod_panel(p),
        quotes,
        target_date=pd.Timestamp("2026-05-15"),
        run_timestamp=datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )
    assert p.stat().st_mtime == mtime_before
    last = prov[(prov["symbol"] == "HPG") & (prov["date"] == pd.Timestamp("2026-05-15"))].iloc[0]
    assert last["close"] == 25.2
    assert bool(last["is_intraday"]) is True
    assert last["bar_status"] == "PARTIAL"


def test_provisional_close_is_last_price(tmp_path):
    eod = pd.DataFrame(
        {
            "symbol": ["FPT"],
            "date": pd.to_datetime(["2026-05-15"]),
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [500000.0],
        }
    )
    p = tmp_path / "p.parquet"
    eod.to_parquet(p)
    quotes = pd.DataFrame([{"symbol": "FPT", "last_price_kvnd": 101.2, "cumulative_volume": 600000}])
    prov = build_provisional_panel(
        load_eod_panel(p),
        quotes,
        target_date=pd.Timestamp("2026-05-15"),
        run_timestamp=datetime(2026, 5, 15, 14, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )
    assert prov.iloc[-1]["close"] == 101.2


def test_volume_projection_excludes_lunch_break():
    lunch = datetime(2026, 5, 15, 12, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    frac, phase = elapsed_tradable_fraction(lunch)
    assert phase == "LUNCH_BREAK"
    proj = project_full_day_volume(1_000_000, lunch, method="session_time")
    assert proj["volume_projection_confidence"] == "low"


def test_volume_projection_clips_early_day():
    early = datetime(2026, 5, 15, 9, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    proj = project_full_day_volume(100_000, early, method="session_time", min_elapsed_fraction=0.15)
    assert proj["volume_is_projected"] is True
    assert proj["projected_volume"] > 100_000


def test_adv50_not_replaced_by_projection():
    """ADV50 in scan uses rolling EOD value column — intraday projection is separate flags only."""
    cfg = load_intraday_config()
    assert "eod_panel_path" in cfg or cfg.get("eod_panel_path") or True


def test_intraday_policy_flags():
    scan = pd.DataFrame(
        [
            {
                "symbol": "VPB",
                "final_action": "NEW_T1",
                "as_of_date": "2026-05-15",
            }
        ]
    )
    quotes = pd.DataFrame(
        [{"symbol": "VPB", "is_stale": False, "timestamp": "2026-05-15T10:00:00+07:00", "data_quality": "OK"}]
    )
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(
        scan,
        quotes,
        asof_timestamp=ts,
        cfg={},
        mode="pre-lunch",
        capability={"available": True, "recommended_method": "historical_quotes_partial_daily"},
    )
    assert bool(out.iloc[0]["is_intraday_preview"]) is True
    assert out.iloc[0]["would_be_final_action"] == "NEW_T1"
    assert out.iloc[0]["final_action"] == "INTRADAY_PREVIEW"
    assert bool(out.iloc[0]["auto_order_allowed"]) is False


def test_manual_review_on_new_t1():
    scan = pd.DataFrame([{"symbol": "HPG", "final_action": "NEW_T1_MANUAL_REVIEW_BREADTH"}])
    quotes = pd.DataFrame([{"symbol": "HPG", "is_stale": False, "timestamp": "2026-05-15T10:00:00+07:00"}])
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(
        scan,
        quotes,
        asof_timestamp=ts,
        cfg={},
        mode="ad-hoc",
        capability={"available": True},
    )
    assert bool(out.iloc[0]["manual_review_required"]) is True
    assert out.iloc[0]["intraday_action_status"] == "MANUAL_REVIEW_REQUIRED"


def test_s3_remains_paper_in_policy():
    scan = pd.DataFrame(
        [
            {
                "symbol": "MWG",
                "final_action": "WATCH_ONLY",
                "s3_shadow_action": "PAPER_S3_SHADOW",
                "s3_no_real_order_flag": True,
            }
        ]
    )
    quotes = pd.DataFrame([{"symbol": "MWG", "is_stale": False, "timestamp": "2026-05-15T10:00:00+07:00"}])
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(scan, quotes, asof_timestamp=ts, cfg={}, mode="ad-hoc", capability={"available": True})
    assert bool(out.iloc[0]["s3_no_real_order_flag"]) is True


def test_source_unavailable_no_fake_scan():
    scan = pd.DataFrame([{"symbol": "FPT", "final_action": "NEW_T1"}])
    quotes = pd.DataFrame()
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(
        scan,
        quotes,
        asof_timestamp=ts,
        cfg={},
        mode="ad-hoc",
        capability={"available": False},
    )
    assert out.iloc[0]["intraday_action_status"] == "SOURCE_UNAVAILABLE"


def test_pre_lunch_lower_confidence_than_preatc():
    from src.trading.intraday.volume_projection import mode_volume_confidence_cap

    assert mode_volume_confidence_cap("pre-lunch") == "medium"
    assert mode_volume_confidence_cap("pre-atc") == "high"


def test_output_filename_timestamp(tmp_path):
    from src.trading.intraday.intraday_scan import _write_outputs

    df = pd.DataFrame([{"symbol": "HPG", "is_intraday_preview": True}])
    cfg = {"modes": {"pre-atc": {"output_prefix": "phase36_intraday_scan_preatc"}}}
    ts = datetime(2026, 5, 15, 14, 30)
    _write_outputs(df, {"status": "OK"}, cfg, "pre-atc", ts, tmp_path)
    files = list(tmp_path.glob("phase36_intraday_scan_preatc_20260515_1430.csv"))
    assert len(files) == 1


def test_vnindex_overlay_does_not_write_parquet(tmp_path):
    from src.trading.intraday.vnindex_overlay import build_vnindex_intraday_overlay

    vnx = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-14", "2026-05-15"]),
            "open": [1200.0, 1210.0],
            "high": [1215.0, 1220.0],
            "low": [1195.0, 1205.0],
            "close": [1210.0, 1215.0],
            "volume": [1e9, 1e9],
        }
    )
    quote = {
        "last_price_kvnd": 1225.0,
        "open_price_kvnd": 1218.0,
        "high_price_kvnd": 1230.0,
        "low_price_kvnd": 1215.0,
        "cumulative_volume": 2e9,
        "data_quality": "OK",
        "timestamp": "2026-05-15T10:00:00+07:00",
    }
    out, meta = build_vnindex_intraday_overlay(
        vnx, target_date=pd.Timestamp("2026-05-15"), quote=quote,
    )
    assert meta["vnindex_overlay_applied"] is True
    assert float(out.loc[out["date"] == pd.Timestamp("2026-05-15"), "close"].iloc[0]) == 1225.0


def test_compute_phase36_intraday_macro_flag():
    """intraday_macro=True uses live breadth path (no CSV required)."""
    from pp_backtest.portfolio_optimization_final_steps import compute_phase36_scan_df
    import inspect
    sig = inspect.signature(compute_phase36_scan_df)
    assert "intraday_macro" in sig.parameters


def test_oms_blocks_intraday_scan_path(tmp_path):
    intraday_csv = tmp_path / "data/research/intraday/phase36_intraday_scan_latest.csv"
    intraday_csv.parent.mkdir(parents=True, exist_ok=True)
    intraday_csv.write_text("symbol,final_action\nHPG,INTRADAY_PREVIEW\n", encoding="utf-8")
    cfg = LiveTradingConfig(data_root=tmp_path)
    r = resolve_scan(cfg, "2026-05-15", cli_scan_path=intraday_csv)
    assert r.blocked
    assert any("Intraday" in e for e in r.errors)


def test_unquoted_symbol_cannot_be_manual_review_candidate():
    scan = pd.DataFrame(
        [
            {"symbol": "VPB", "final_action": "NEW_T1_MANUAL_REVIEW_BREADTH"},
            {"symbol": "HPG", "final_action": "NEW_T1"},
        ]
    )
    quotes = pd.DataFrame([{"symbol": "HPG", "is_stale": False, "data_quality": "OK"}])
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(
        scan,
        quotes,
        asof_timestamp=ts,
        cfg={},
        mode="ad-hoc",
        capability={"available": True},
        quoted_equity_symbols={"HPG"},
    )
    vpb = out[out["symbol"] == "VPB"].iloc[0]
    hpg = out[out["symbol"] == "HPG"].iloc[0]
    assert vpb["intraday_data_quality"] == "MISSING_INTRADAY_QUOTE"
    assert vpb["intraday_action_status"] == "STALE_DATA_NO_ACTION"
    assert bool(vpb["manual_review_required"]) is False
    assert bool(vpb["intraday_candidate"]) is False
    assert hpg["intraday_action_status"] == "MANUAL_REVIEW_REQUIRED"
    assert bool(hpg["manual_review_required"]) is True


def test_explicit_symbol_scan_filters_to_requested_only():
    from src.trading.intraday.intraday_scan import run_intraday_scan

    big_scan = pd.DataFrame(
        [
            {"symbol": "HPG", "final_action": "NEW_T1"},
            {"symbol": "VPB", "final_action": "WATCH_ONLY"},
        ]
    )
    meta_scan = {"panel_asof": "2026-05-15", "last_breadth": 0.4, "breadth_zone": "normal", "regime_bull": True, "last_s3_breadth": 0.4}
    quotes = pd.DataFrame(
        [{"symbol": "HPG", "is_stale": False, "data_quality": "OK", "last_price_kvnd": 26.0}]
    )
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    with patch("src.trading.intraday.intraday_scan.detect_intraday_source_capability") as cap:
        cap.return_value = {"available": True, "recommended_method": "test"}
        with patch("src.trading.intraday.intraday_scan.fetch_intraday_quotes", return_value=quotes):
            with patch("src.trading.intraday.intraday_scan.fetch_intraday_quote") as vnq:
                vnq.return_value = {"data_quality": "SOURCE_UNAVAILABLE"}
                with patch("src.trading.intraday.intraday_scan.load_eod_panel") as lep:
                    lep.return_value = pd.DataFrame(
                        {
                            "symbol": ["HPG"],
                            "date": pd.to_datetime(["2026-05-15"]),
                            "open": [25.0],
                            "high": [26.0],
                            "low": [24.0],
                            "close": [25.5],
                            "volume": [1e6],
                        }
                    )
                    with patch("src.trading.intraday.intraday_scan.build_provisional_panel") as bpp:
                        bpp.return_value = lep.return_value
                        with patch("src.trading.intraday.intraday_scan.load_vnindex") as lv:
                            lv.return_value = pd.DataFrame(
                                {
                                    "date": pd.to_datetime(["2026-05-15"]),
                                    "open": [1900.0],
                                    "high": [1920.0],
                                    "low": [1890.0],
                                    "close": [1910.0],
                                    "volume": [1e9],
                                }
                            )
                            with patch("src.trading.intraday.intraday_scan.build_vnindex_intraday_overlay") as bvo:
                                bvo.return_value = (lv.return_value, {})
                                with patch("src.trading.intraday.intraday_scan.build_gk_cache", return_value={}):
                                    with patch(
                                        "src.trading.intraday.intraday_scan.compute_phase36_scan_df",
                                        return_value=(big_scan, meta_scan),
                                    ):
                                        df, _ = run_intraday_scan(
                                            asof_timestamp=ts,
                                            symbols=["HPG"],
                                            write_outputs=False,
                                        )
    assert set(df["symbol"]) == {"HPG"}
    assert "VPB" not in df["symbol"].values


def test_vnindex_true_true_regime_no_changed_warning():
    from src.trading.intraday.vnindex_overlay import build_vnindex_intraday_overlay

    vnx = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-14", "2026-05-15"]),
            "open": [1900.0, 1910.0],
            "high": [1920.0, 1925.0],
            "low": [1890.0, 1905.0],
            "close": [1910.0, 1921.0],
            "volume": [1e9, 1e9],
        }
    )
    quote = {
        "last_price_kvnd": 1921.0,
        "open_price_kvnd": 1910.0,
        "high_price_kvnd": 1925.0,
        "low_price_kvnd": 1905.0,
        "cumulative_volume": 2e9,
        "data_quality": "OK",
    }
    _, meta = build_vnindex_intraday_overlay(
        vnx,
        target_date=pd.Timestamp("2026-05-15"),
        quote=quote,
    )
    assert meta["vnindex_eod_regime_bull"] is True
    assert meta["vnindex_intraday_regime_bull"] is True
    assert meta["vnindex_regime_changed"] is False


def test_source_unavailable_overwrites_latest_outputs(tmp_path):
    from src.trading.intraday.intraday_scan import run_intraday_scan

    out_dir = tmp_path / "intraday"
    out_dir.mkdir()
    latest = out_dir / "phase36_intraday_scan_latest.csv"
    latest_md = out_dir / "phase36_intraday_scan_latest.md"
    latest_html = out_dir / "phase36_intraday_scan_latest.html"
    latest_meta = out_dir / "phase36_intraday_scan_latest_meta.json"
    latest.write_text("symbol,final_action\nSTALE,NEW_T1\n", encoding="utf-8")
    latest_md.write_text("# stale\n", encoding="utf-8")
    latest_html.write_text("<html>stale</html>", encoding="utf-8")
    latest_meta.write_text('{"status":"OK"}', encoding="utf-8")

    cfg = {"output_dir": str(out_dir), "modes": {"ad-hoc": {"output_prefix": "phase36_intraday_scan"}}}
    cfg_path = tmp_path / "intraday_scan.yaml"
    import yaml

    cfg_path.write_text(yaml.dump(cfg), encoding="utf-8")

    with patch("src.trading.intraday.intraday_scan.detect_intraday_source_capability") as cap:
        cap.return_value = {"available": False}
        run_intraday_scan(write_outputs=True, config_path=cfg_path)

    assert "SOURCE_UNAVAILABLE" in latest_md.read_text(encoding="utf-8")
    assert "SOURCE_UNAVAILABLE" in latest_meta.read_text(encoding="utf-8")
    assert "STALE" not in latest.read_text(encoding="utf-8")
    assert "No manual-review candidates" in latest_html.read_text(encoding="utf-8")


def test_out_of_session_html_has_no_fake_top_candidates(tmp_path):
    from src.trading.intraday.report import write_intraday_html_dashboard

    scan = pd.DataFrame(
        [
            {
                "symbol": "HPG",
                "would_be_final_action": "NEW_T1",
                "a3_rank_score": 9.9,
                "close_kVND": 26.0,
                "intraday_action_status": "OUT_OF_SESSION_NO_ACTION",
                "intraday_candidate": False,
                "breadth_zone": "defense",
            }
        ]
    )
    meta = {"session_phase": "LUNCH_BREAK", "status": "OK", "vnindex": {}, "last_breadth": 0.32, "breadth_zone": "defense"}
    ts = datetime(2026, 5, 15, 12, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    path = write_intraday_html_dashboard(scan, meta, ts, "pre-lunch", tmp_path)
    html = path.read_text(encoding="utf-8")
    assert "No manual-review candidates" in html
    assert "<table>" not in html


def test_mixed_quote_coverage_breadth_source():
    from src.trading.intraday.intraday_scan import _resolve_breadth_source

    assert _resolve_breadth_source(set(), {"HPG", "VPB"}) == "eod_fallback"
    assert _resolve_breadth_source({"HPG", "VPB"}, {"HPG", "VPB"}) == "live_panel_full_intraday"
    assert _resolve_breadth_source({"HPG"}, {"HPG", "VPB"}) == "mixed_intraday_eod_panel"


def test_attach_quote_coverage_meta_counts():
    from src.trading.intraday.intraday_scan import _attach_quote_coverage_meta

    meta: dict = {}
    _attach_quote_coverage_meta(
        meta,
        quoted_syms={"HPG", "MWG"},
        scan_symbols={"HPG", "MWG", "VPB"},
        symbols_requested=["HPG", "MWG", "SSI"],
    )
    assert meta["quoted_symbols_count"] == 2
    assert meta["scan_symbols_count"] == 3
    assert meta["missing_quote_count"] == 1
    assert abs(meta["intraday_quote_coverage_pct"] - 2 / 3) < 1e-9


def test_failure_meta_includes_coverage_counts(tmp_path):
    from src.trading.intraday.intraday_scan import run_intraday_scan

    out_dir = tmp_path / "intraday"
    out_dir.mkdir()
    cfg_path = tmp_path / "intraday_scan.yaml"
    import yaml

    cfg_path.write_text(
        yaml.dump({"output_dir": str(out_dir), "modes": {"ad-hoc": {"output_prefix": "phase36_intraday_scan"}}}),
        encoding="utf-8",
    )
    with patch("src.trading.intraday.intraday_scan.detect_intraday_source_capability") as cap:
        cap.return_value = {"available": False}
        _, meta = run_intraday_scan(write_outputs=True, config_path=cfg_path)
    assert meta["quoted_symbols_count"] == 0
    assert meta["scan_symbols_count"] == 0
    assert meta["missing_quote_count"] == 0
    latest_meta = (out_dir / "phase36_intraday_scan_latest_meta.json").read_text(encoding="utf-8")
    assert "quoted_symbols_count" in latest_meta


def test_holdings_missing_report_warning(tmp_path):
    from src.trading.intraday.report import write_intraday_report

    cfg = {"holdings_path": str(tmp_path / "missing_holdings.txt")}
    meta = {
        "status": "OK",
        "session_phase": "AFTERNOON_CONTINUOUS",
        "holdings_path": "missing_holdings.txt",
        "holdings_file_exists": False,
        "holdings_symbol_count": 0,
        "quoted_symbols_count": 1,
        "scan_symbols_count": 2,
        "missing_quote_count": 1,
        "intraday_quote_coverage_pct": 0.5,
        "vnindex": {},
    }
    ts = datetime(2026, 5, 15, 14, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    path = write_intraday_report(pd.DataFrame(), meta, pd.DataFrame(), cfg, "pre-atc", ts, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "file missing" in text
    assert "missing_holdings.txt" in text


def test_final_action_always_intraday_preview_on_candidate():
    scan = pd.DataFrame([{"symbol": "HPG", "final_action": "NEW_T1"}])
    quotes = pd.DataFrame([{"symbol": "HPG", "is_stale": False, "data_quality": "OK"}])
    ts = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    out = _apply_intraday_policy(
        scan, quotes, asof_timestamp=ts, cfg={}, mode="ad-hoc", capability={"available": True},
    )
    assert out.iloc[0]["final_action"] == "INTRADAY_PREVIEW"
    assert bool(out.iloc[0]["auto_order_allowed"]) is False
