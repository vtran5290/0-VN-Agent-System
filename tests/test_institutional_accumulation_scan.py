"""Methodology-only regression tests for Institutional Accumulation Scan v1.1."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.scans.institutional_accumulation.config import (
    EMERGING_MAX_RISK_PENALTY,
    EMERGING_MIN_MONEY_FLOW,
    FRAGILE_REGIME_LABEL,
    TIER1_MAX_RISK,
    TIER1_MIN_MONEY_FLOW,
    TIER1_MIN_SCORE,
    TIER2_MIN_SCORE,
    TIER2_MIN_SCORE_FRAGILE,
    TIER3_CONSENSUS_MIN_MONEY,
    TIER3_CONSENSUS_MIN_SCORE,
    TIER3_MIN_SCORE_FRAGILE,
    ScanConfig,
)
from src.scans.institutional_accumulation.context import load_smart_money_context, tag_symbol
from src.scans.institutional_accumulation.filters import is_etf_or_open_fund
from src.scans.institutional_accumulation.indicators import vingroup_distortion_diagnosis
from src.scans.institutional_accumulation.pipeline import _build_universe_policy
from src.scans.institutional_accumulation.scoring import assign_tier, score_money_flow
from src.scans.institutional_accumulation.validation import (
    confirm_no_execution_fields,
    confirm_no_lookahead,
    unit_handling_check,
)

REPO = Path(__file__).resolve().parents[1]
STOCKS = REPO / "data" / "stocks"
SCAN_CSV = REPO / "outputs" / "scans" / "institutional_accumulation_2026-04-30.csv"
SCAN_JSON = REPO / "outputs" / "scans" / "institutional_accumulation_2026-04-30.json"
AS_OF = "2026-04-30"
SPOT = ["MBB", "CTG", "MWG", "HPG", "GMD", "VIC", "VHM", "VCB", "STB"]


def _emerging_mask(df: pd.DataFrame, cfg: ScanConfig | None = None) -> pd.Series:
    cfg = cfg or ScanConfig()
    return (
        df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])
        & (df["has_fund_disclosure_tag"] == False)  # noqa: E712
        & (df["liquidity_ok"] == True)  # noqa: E712
        & (df["score_money_flow"] >= cfg.emerging_min_money_flow)
        & (df["score_risk_penalty"] <= cfg.emerging_max_risk_penalty)
    )


@pytest.fixture
def scan_df() -> pd.DataFrame:
    if not SCAN_CSV.is_file():
        pytest.skip(f"Missing scan output: {SCAN_CSV}")
    return pd.read_csv(SCAN_CSV)


@pytest.fixture
def scan_payload() -> dict:
    if not SCAN_JSON.is_file():
        pytest.skip(f"Missing scan json: {SCAN_JSON}")
    return json.loads(SCAN_JSON.read_text(encoding="utf-8"))


def test_universe_policy_is_full_liquid_universe_by_default():
    cfg = ScanConfig()
    ctx = load_smart_money_context("2026-04")
    policy = _build_universe_policy(cfg, ctx, n_symbols=1500)
    assert policy["mode"] == "full_liquid_universe"
    assert "fund lists" in policy["note"].lower() or "context priors" in policy["note"].lower()


def test_fund_context_five_buckets_no_differentiated_bet():
    ctx = load_smart_money_context("2026-04")
    buckets = set()
    for sym in (
        list(ctx.get("consensus_core") or [])[:3]
        + list(ctx.get("consensus_second_ring") or [])[:2]
        + list(ctx.get("commentary_mentions") or [])[:2]
        + list(ctx.get("selective_fund_bets") or [])[:2]
        + ["ZZZZ"]
    ):
        info = tag_symbol(sym, "Unknown", ctx)
        buckets.add(info["fund_context_bucket"])
    assert "differentiated_bet" not in buckets
    assert buckets <= {
        "consensus_core",
        "consensus_second_ring",
        "fund_commentary_mention",
        "selective_fund_bet",
        "outside_fund_disclosure",
    }


def test_score_money_flow_is_mean_of_four_groups():
    money = {
        "cmf20_daily": 0.12,
        "cmf20_weekly": 0.08,
        "cmf20_daily_slope_10": 0.01,
        "cmf20_weekly_slope_8": 0.005,
        "obv_slope_20": 0.02,
        "obv_slope_50": 0.01,
        "obv_vs_ma20": 0.05,
        "pvt_slope_20": 0.015,
        "pvt_slope_50": 0.008,
        "adl_slope_20": 0.01,
        "adl_price_divergence_bearish": False,
        "up_down_volume_ratio_20": 1.3,
        "hv_up_days_20": 8,
        "hv_down_days_20": 4,
        "turnover_accel_ratio_5d50d": 0.15,
        "cmf_flow_conflict": False,
    }
    score, _, groups = score_money_flow(money)
    assert set(groups.keys()) == {"cmf", "obv_pvt", "adl", "participation"}
    assert score == pytest.approx(float(np.mean(list(groups.values()))), rel=1e-6)


def test_emerging_candidate_requires_no_fund_disclosure_tag(scan_df: pd.DataFrame):
    emerg = scan_df[scan_df["emerging_accumulation_candidate"] == True]  # noqa: E712
    if emerg.empty:
        pytest.skip("No emerging rows in scan sample")
    assert (emerg["has_fund_disclosure_tag"] == False).all()  # noqa: E712


def test_emerging_candidate_excluded_when_risk_penalty_exceeds_gate():
    rows = [
        {
            "tier": "Tier 2",
            "has_fund_disclosure_tag": False,
            "liquidity_ok": True,
            "score_money_flow": 70.0,
            "score_risk_penalty": 40.0,
        },
        {
            "tier": "Tier 2",
            "has_fund_disclosure_tag": False,
            "liquidity_ok": True,
            "score_money_flow": 70.0,
            "score_risk_penalty": 25.0,
        },
    ]
    df = pd.DataFrame(rows)
    mask = _emerging_mask(df)
    assert mask.iloc[0] is np.bool_(False) or mask.iloc[0] is False
    assert bool(mask.iloc[1]) is True


def test_etf_excluded_from_emerging_candidates(scan_df: pd.DataFrame):
    assert "E1VFVN30" not in set(scan_df["ticker"])
    assert is_etf_or_open_fund("E1VFVN30", "Quỹ mở") is True
    assert is_etf_or_open_fund("MBB", "Ngân hàng") is False


def test_vin_distortion_fires_for_vic(scan_df: pd.DataFrame):
    if "VIC" not in scan_df["ticker"].values:
        pytest.skip("VIC not in scan")
    vic = scan_df.loc[scan_df["ticker"] == "VIC"].iloc[0]
    assert bool(vic["vingroup_distortion_flag"]) is True


def test_vin_distortion_diagnosis_includes_daily_cmf_missing_when_null():
    money = {
        "cmf20_daily": None,
        "cmf20_weekly": -0.02,
        "cmf_flow_conflict": True,
        "obv_slope_20": 0.0,
        "obv_slope_50": 0.0,
        "adl_slope_20": 0.0,
    }
    price = {
        "rs_vs_vnindex_20": 0.35,
        "extension_pct_above_ma20": 20.0,
    }
    flag, diag = vingroup_distortion_diagnosis("VHM", money, price, ["VIC", "VHM", "VRE"])
    assert flag is True
    assert diag is not None
    assert "daily_CMF_missing" in diag


def test_tier1_requires_all_three_gates_simultaneously():
    assert assign_tier(80, 60, 20, liquidity_ok=True) == "Tier 1"
    assert assign_tier(80, 60, 40, liquidity_ok=True) != "Tier 1"
    assert assign_tier(70, 60, 20, liquidity_ok=True) != "Tier 1"
    assert assign_tier(80, 50, 20, liquidity_ok=True) != "Tier 1"
    assert (
        assign_tier(TIER1_MIN_SCORE, TIER1_MIN_MONEY_FLOW, TIER1_MAX_RISK, liquidity_ok=True)
        == "Tier 1"
    )


def test_tier2_fragile_floor_lower_than_normal():
    score, money, risk = 53.0, 45.0, 40.0
    assert (
        assign_tier(score, money, risk, liquidity_ok=True, regime_label="normal")
        == "Tier 3"
    )
    assert (
        assign_tier(score, money, risk, liquidity_ok=True, regime_label=FRAGILE_REGIME_LABEL)
        == "Tier 2"
    )
    assert TIER2_MIN_SCORE_FRAGILE < TIER2_MIN_SCORE


def test_tier3_consensus_core_floor_fires_in_fragile_regime():
    tier = assign_tier(
        TIER3_CONSENSUS_MIN_SCORE,
        TIER3_CONSENSUS_MIN_MONEY,
        45.0,
        liquidity_ok=True,
        regime_label=FRAGILE_REGIME_LABEL,
        in_consensus_core=True,
    )
    assert tier == "Tier 3"
    assert TIER3_MIN_SCORE_FRAGILE <= TIER3_CONSENSUS_MIN_SCORE


def test_no_execution_fields_in_scan_output(scan_payload: dict):
    ok, issues = confirm_no_execution_fields(scan_payload)
    assert ok is True
    assert issues == []


def test_no_lookahead_slice_through():
    if not (STOCKS / "MBB.csv").is_file():
        pytest.skip("MBB.csv missing")
    assert confirm_no_lookahead("MBB", STOCKS, AS_OF) is True


def test_unit_handling_all_rows_have_price_unit_mode(scan_df: pd.DataFrame):
    assert "price_unit_mode" in scan_df.columns
    assert scan_df["price_unit_mode"].notna().all()
    check = unit_handling_check(scan_df)
    assert check["status"] in ("ok", "warn")


def test_score_percentile_computed_only_for_liquid_universe(scan_df: pd.DataFrame):
    liquid = scan_df[scan_df["liquidity_ok"] == True]  # noqa: E712
    illiquid = scan_df[scan_df["liquidity_ok"] == False]  # noqa: E712
    assert liquid["score_percentile"].notna().all()
    if not illiquid.empty:
        assert illiquid["score_percentile"].isna().all()


def test_emerging_max_risk_penalty_default():
    cfg = ScanConfig()
    assert cfg.emerging_max_risk_penalty == EMERGING_MAX_RISK_PENALTY == 30.0
    assert cfg.emerging_min_money_flow == EMERGING_MIN_MONEY_FLOW


def test_high_risk_names_not_emerging_after_gate(scan_df: pd.DataFrame):
    for sym in ("TNT", "KSF", "PVP"):
        if sym not in scan_df["ticker"].values:
            continue
        row = scan_df.loc[scan_df["ticker"] == sym].iloc[0]
        if float(row["score_risk_penalty"]) > EMERGING_MAX_RISK_PENALTY:
            assert bool(row["emerging_accumulation_candidate"]) is False
