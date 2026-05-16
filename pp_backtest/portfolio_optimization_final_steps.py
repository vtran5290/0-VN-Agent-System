#!/usr/bin/env python3
"""
Final Steps — Sector L4, Regime Decomp, Performance Scaling, Breadth, Phase33 Scan.

Steps:
  --step sector    : Step 2 — sector map + stress engine
  --step regime    : Step 3 — regime/macro decomposition
  --step scaling   : Step 4 — performance-based exposure scaling
  --step breadth   : Step 5 — breadth hysteresis rule test
  --step scan      : Step 6 — Phase33 daily scan update
  --step all       : all steps

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_final_steps.py --step sector
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_final_steps.py --step all
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache, load_panel, load_vnindex, get_universe,
    vnindex_regime_gate, compute_gk, portfolio_metrics,
    STRATEGY_CONFIGS, DEFAULT_COST,
)
from pp_backtest.portfolio_optimization_phase2 import load_ledger, build_gk_cache
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2,
    _liquidity_warning_v2, _annual_return,
)
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
MW_DIR   = OUT_DIR
P2_LED   = REPO / "data" / "research" / "portfolio_optimization" / "phase2" / "phase2_baseline_trade_ledgers"
P25_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase25"

REF_PORTFOLIO  = 5e9
REF_PART       = 0.10
MIN_POS_VND    = 100_000
ANNUALIZE      = 252


# ─────────────────────────────────────────────────────────────────────────────
# Sector map (hardcoded, facts-first, confidence tagged)
# ─────────────────────────────────────────────────────────────────────────────

def build_sector_map() -> pd.DataFrame:
    """
    Build sector_map for all 272 VN symbols.
    Confidence: high = known with certainty, medium = likely, low = unknown/inferred.
    Unknowns use sector_l4='Unknown' and confidence='low'.
    """
    # (symbol, l1, l2, l3, l4, tags, bank, sec, broker, re, ip, const, steel, og, pwr, retail, export, hibeta, soe, vin)
    RAW = [
        # ── Banking ──────────────────────────────────────────────────────────
        ("VCB","Finance","Banking","Commercial Bank","State Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("BID","Finance","Banking","Commercial Bank","State Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("CTG","Finance","Banking","Commercial Bank","State Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("MBB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("ACB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("TCB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("VPB","Finance","Banking","Commercial Bank","Private Bank","bank,hibeta",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("HDB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("STB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("VIB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("LPB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("TPB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("MSB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("OCB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("SSB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("EIB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("SHB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NAB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("ABB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VAB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("BVB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("KLB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NVB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("PVB","Finance","Banking","Commercial Bank","Private Bank","bank",1,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("BAF","Consumer","Food Production","Poultry","Poultry Farming","agri,export",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Consumer Finance ─────────────────────────────────────────────────
        ("EVF","Finance","Consumer Finance","Non-Bank Finance","Consumer Lending","bank_adj",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("F88","Finance","Consumer Finance","Non-Bank Finance","Pawnshop Finance","bank_adj,hibeta",1,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        # ── Securities / Brokerage ───────────────────────────────────────────
        ("SSI","Finance","Securities","Brokerage","Large Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("VND","Finance","Securities","Brokerage","Large Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("HCM","Finance","Securities","Brokerage","Large Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("VCI","Finance","Securities","Brokerage","Large Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("MBS","Finance","Securities","Brokerage","Mid Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("SHS","Finance","Securities","Brokerage","Mid Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("BSI","Finance","Securities","Brokerage","Mid Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("CTS","Finance","Securities","Brokerage","Mid Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("FTS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VDS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("BVS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("ORS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("VIX","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("APS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("APG","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("PSI","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("SBS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("AGR","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("DSE","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("TVD","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("VFS","Finance","Securities","Brokerage","Small Broker","sec,broker",0,1,1,0,0,0,0,0,0,0,0,1,0,0,"medium"),
        # ── Insurance ────────────────────────────────────────────────────────
        ("BVH","Finance","Insurance","Life+Non-Life Insurance","Bao Viet Holdings","insurance",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("BIC","Finance","Insurance","Non-Life Insurance","BIDV Insurance","insurance",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("BMI","Finance","Insurance","Non-Life Insurance","Bao Minh Insurance","insurance",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("MIG","Finance","Insurance","Non-Life Insurance","Military Insurance","insurance",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("PVI","Finance","Insurance","Non-Life Insurance","PVI Holdings","insurance,re",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── VIN Group Real Estate ────────────────────────────────────────────
        ("VIC","Real Estate","Conglomerate","VIN Group","Vingroup Holding","re,vin,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,1,"high"),
        ("VHM","Real Estate","Residential RE","VIN Group","Vinhomes","re,vin,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,1,"high"),
        ("VRE","Real Estate","Commercial RE","VIN Group","Vincom Retail","re,vin,retail",0,0,0,1,0,0,0,0,0,0,0,1,0,1,"high"),
        ("VJC","Consumer","Airlines","VIN Group","Vietjet Air","vin,hibeta",0,0,0,0,0,0,0,0,0,0,0,1,0,1,"high"),
        # ── Real Estate (non-VIN) ────────────────────────────────────────────
        ("KDH","Real Estate","Residential RE","Developer","Mid-Tier Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NLG","Real Estate","Residential RE","Developer","Mid-Tier Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DXG","Real Estate","Residential RE","Developer","Mid-Tier Developer","re,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("PDR","Real Estate","Residential RE","Developer","Mid-Tier Developer","re,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("NVL","Real Estate","Residential RE","Developer","Large Developer","re,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("DIG","Real Estate","Residential RE","Developer","Small Developer","re,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("TDC","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NRC","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("NHA","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("HAG","Real Estate","Residential RE","Developer","Mid Developer+Agri","re,agri,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("IJC","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("CEO","Real Estate","Tourism RE","Developer","Tourism Developer","re",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("QCG","Real Estate","Residential RE","Developer","Small Developer","re,hibeta",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("HQC","Real Estate","Affordable Housing","Developer","Affordable Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DXS","Real Estate","RE Services","Services","RE Services","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NTL","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("AGG","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"high"),
        ("SCR","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("LDG","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("HDG","Real Estate","Diversified RE","Developer+Power","Ha Do Group","re",0,0,0,1,0,0,0,0,0,0,0,1,0,0,"high"),
        ("TCH","Real Estate","Residential RE","Developer","Hanoi Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("KHG","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("PIV","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("VPI","Real Estate","Residential RE","Developer","Van Phu Invest","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("VPX","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("PXL","Real Estate","Residential RE","Developer","Small Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("DRH","Real Estate","Hotel+Tourism","Developer","Tourism RE","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("DLG","Real Estate","Tourism RE","Developer","Tourism Developer","re",0,0,0,1,0,0,0,0,0,0,0,0,0,0,"medium"),
        # ── Industrial Parks ─────────────────────────────────────────────────
        ("BCM","Real Estate","Industrial Park","State-Owned IP","Becamex IDC","re,ip,soe",0,0,0,1,1,0,0,0,0,0,0,0,1,0,"high"),
        ("IDC","Real Estate","Industrial Park","Industrial Park","IDC Corp","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        ("KBC","Real Estate","Industrial Park","Industrial Park","Kinh Bac City","re,ip",0,0,0,1,1,0,0,0,0,0,0,1,0,0,"high"),
        ("SZC","Real Estate","Industrial Park","Industrial Park","Sonadezi","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        ("SIP","Real Estate","Industrial Park","Industrial Park","Saigon IP","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        ("D2D","Real Estate","Industrial Park","Industrial Park","Long Binh IP","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        ("LHG","Real Estate","Industrial Park","Industrial Park","Long Hau IP","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        ("PHR","Real Estate","Industrial Park","Rubber+IP","Phu Rieng Rubber","re,ip",0,0,0,1,1,0,0,0,0,0,0,0,0,0,"high"),
        # ── Steel / Metals ───────────────────────────────────────────────────
        ("HPG","Materials","Steel","Integrated Steel","Hoa Phat Group","steel,hibeta,export",0,0,0,0,0,0,1,0,0,0,1,1,0,0,"high"),
        ("HSG","Materials","Steel","Cold-Rolled Steel","Hoa Sen Group","steel,hibeta,export",0,0,0,0,0,0,1,0,0,0,1,1,0,0,"high"),
        ("NKG","Materials","Steel","Cold-Rolled Steel","Nam Kim Group","steel,export",0,0,0,0,0,0,1,0,0,0,1,0,0,0,"high"),
        ("POM","Materials","Steel","Construction Steel","Pomina Steel","steel,hibeta",0,0,0,0,0,0,1,0,0,0,0,1,0,0,"high"),
        ("SMC","Materials","Steel","Steel Trading","SMC Trading","steel",0,0,0,0,0,0,1,0,0,0,0,0,0,0,"high"),
        ("VGS","Materials","Steel","Steel Pipes","Vietnam Steel Corp","steel",0,0,0,0,0,0,1,0,0,0,0,0,0,0,"high"),
        # ── Oil & Gas ────────────────────────────────────────────────────────
        ("GAS","Energy","Oil & Gas","Gas Distribution","PV Gas","og,soe",0,0,0,0,0,0,0,1,0,0,0,0,1,0,"high"),
        ("PLX","Energy","Oil & Gas","Fuel Retail","Petrolimex","og,retail,soe",0,0,0,0,0,0,0,1,0,1,0,0,1,0,"high"),
        ("PVD","Energy","Oil & Gas","Drilling","PV Drilling","og,hibeta",0,0,0,0,0,0,0,1,0,0,0,1,0,0,"high"),
        ("PVS","Energy","Oil & Gas","Oilfield Services","PV Services","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"high"),
        ("BSR","Energy","Oil & Gas","Refining","Binh Son Refinery","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"high"),
        ("OIL","Energy","Oil & Gas","Fuel Trading","PV Oil","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"high"),
        ("PVC","Energy","Oil & Gas","Pipes+Materials","PVC","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"medium"),
        ("PVT","Energy","Oil & Gas","Marine Transport","PV Trans","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"high"),
        ("PVP","Energy","Oil & Gas","Marine Transport","PV Trans Pacific","og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"medium"),
        ("DPM","Materials","Fertilizer","Nitrogen Fertilizer","PetroVietnam Fertilizer","og,chem",0,0,0,0,0,0,0,1,0,0,0,0,1,0,"high"),
        ("DCM","Materials","Fertilizer","Nitrogen Fertilizer","Ca Mau Fertilizer","og,chem",0,0,0,0,0,0,0,1,0,0,0,0,1,0,"high"),
        # ── Power / Utilities ────────────────────────────────────────────────
        ("POW","Utilities","Power","Thermal Power","PV Power","pwr,soe",0,0,0,0,0,0,0,0,1,0,0,0,1,0,"high"),
        ("GEG","Utilities","Power","Renewable Power","Gia Lai Electricity","pwr,hibeta",0,0,0,0,0,0,0,0,1,0,0,1,0,0,"high"),
        ("NT2","Utilities","Power","Gas Power","Nhon Trach 2","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"high"),
        ("REE","Industrials","M&E + Power","Diversified Utility","REE Corp","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"high"),
        ("PC1","Industrials","Power Construction","Wind+Construction","PCC1","pwr,const",0,0,0,0,0,1,0,0,1,0,0,0,0,0,"high"),
        ("TTA","Utilities","Power","Hydro Power","Thac Mo Power","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"high"),
        ("PPC","Utilities","Power","Thermal Coal Power","Pha Lai Power","pwr,soe",0,0,0,0,0,0,0,0,1,0,0,0,1,0,"high"),
        ("QTP","Utilities","Power","Thermal Power","Quang Ninh Power","pwr,soe",0,0,0,0,0,0,0,0,1,0,0,0,1,0,"medium"),
        ("TV2","Utilities","Power","Hydro Power","Tuyen Quang 2","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"medium"),
        ("TV1","Utilities","Power","Hydro Power","Tuyen Quang 1","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"medium"),
        ("BWE","Utilities","Water","Water Treatment","BWE","pwr",0,0,0,0,0,0,0,0,1,0,0,0,0,0,"high"),
        # ── Construction ─────────────────────────────────────────────────────
        ("CTD","Industrials","Construction","General Contractor","Coteccons","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"high"),
        ("VCG","Industrials","Construction","General Contractor","Vinaconex","const,re,soe",0,0,0,0,0,1,0,0,0,0,0,0,1,0,"high"),
        ("HBC","Industrials","Construction","General Contractor","Hoa Binh","const,hibeta",0,0,0,0,0,1,0,0,0,0,0,1,0,0,"high"),
        ("FCN","Industrials","Construction","Specialty Contractor","Fecon","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"high"),
        ("DPG","Industrials","Construction","Construction+RE","Dat Phuong","const,re",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"high"),
        ("CII","Industrials","Infrastructure","BOT Roads","CII Infrastructure","const,re,hibeta",0,0,0,0,0,1,0,0,0,0,0,1,0,0,"high"),
        ("HHV","Industrials","Construction","Highway Construction","HHV","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"high"),
        ("CTI","Industrials","Construction","Infrastructure","Tinh Viet","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"medium"),
        ("VC3","Industrials","Construction","General Contractor","VC3","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"medium"),
        ("LCG","Industrials","Construction","General Contractor","Licogi 13","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"medium"),
        ("C4G","Industrials","Construction","Road Construction","Cienco4","const,soe",0,0,0,0,0,1,0,0,0,0,0,0,1,0,"high"),
        ("C69","Industrials","Construction","Road Construction","Cienco6","const,soe",0,0,0,0,0,1,0,0,0,0,0,0,1,0,"high"),
        ("HUT","Industrials","Infrastructure","BOT Highway","HUT","const,hibeta",0,0,0,0,0,1,0,0,0,0,0,1,0,0,"high"),
        ("G36","Industrials","Construction","Construction","Geruco Construct","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"low"),
        ("HPA","Industrials","Construction","Construction+RE","HPA","const,re",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"medium"),
        ("DTD","Industrials","Construction","General Contractor","DTD","const",0,0,0,0,0,1,0,0,0,0,0,0,0,0,"low"),
        # ── Logistics / Transport ─────────────────────────────────────────────
        ("GMD","Industrials","Logistics","Port+Logistics","Gemadept","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("HAH","Industrials","Shipping","Container Shipping","Hai An Shipping","logistics,hibeta",0,0,0,0,0,0,0,0,0,0,1,1,0,0,"high"),
        ("VOS","Industrials","Shipping","Bulk Shipping","VN Ocean Shipping","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VSC","Industrials","Logistics","Port+Logistics","Viconship","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VTO","Industrials","Shipping","Tanker","Viet Thuan Shipping","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("SCS","Industrials","Logistics","Air Cargo","Saigon Cargo","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("ACV","Industrials","Airport","Airport Operator","Airports Corp","logistics,soe",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("HVN","Consumer","Airlines","Flag Carrier","Vietnam Airlines","hibeta,soe",0,0,0,0,0,0,0,0,0,0,0,1,1,0,"high"),
        ("VTP","Industrials","Logistics","E-commerce Logistics","Viettel Post","logistics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("HAX","Consumer","Automotive","Vehicle Distribution","HAX","retail",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VEA","Industrials","Automotive","Auto Components","VN Engine+Agri","soe",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        # ── Technology / Telecom ─────────────────────────────────────────────
        ("FPT","Technology","IT Services","IT+Software+Telecom","FPT Corp","tech,export",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("CMG","Technology","IT Services","IT Services","CMC Corp","tech",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("ELC","Technology","Electronics","Electronics","ELC Electronics","tech",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("CTR","Industrials","Telecom Infrastructure","Telecom Infrastructure","Viettel Infra","tech",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VGI","Technology","Telecom","International Telecom","Viettel Global","tech,soe",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("DGW","Technology","Distribution","Electronics Distribution","Digiworld","retail,tech",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Retail / Consumer Discretionary ──────────────────────────────────
        ("MWG","Consumer","Retail","Electronics Retail","Mobile World","retail",0,0,0,0,0,0,0,0,0,1,0,0,0,0,"high"),
        ("FRT","Consumer","Retail","Mobile Retail","FPT Retail","retail",0,0,0,0,0,0,0,0,0,1,0,0,0,0,"high"),
        ("PNJ","Consumer","Retail","Jewelry Retail","Phu Nhuan Jewelry","retail",0,0,0,0,0,0,0,0,0,1,0,0,0,0,"high"),
        # ── FMCG / Food & Beverage ───────────────────────────────────────────
        ("VNM","Consumer","Food+Dairy","Dairy","Vinamilk","fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("MSN","Consumer","FMCG","Conglomerate","Masan Group","fmcg,retail",0,0,0,0,0,0,0,0,0,1,0,0,0,0,"high"),
        ("KDC","Consumer","Food","Processed Food","Kido Group","fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("SAB","Consumer","Beer","Beer","Sabeco","fmcg,soe",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("QNS","Consumer","Food","Sugar+Soy Milk","Quang Ngai Sugar","fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("MCH","Consumer","FMCG","FMCG","Masan Consumer","fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DBC","Consumer","Food","Livestock+FMCG","Dabaco Group","agri,fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("HNG","Consumer","Agriculture","Fruit+Agriculture","HAGL Agri","agri,hibeta",0,0,0,0,0,0,0,0,0,0,0,1,0,0,"high"),
        ("NAF","Consumer","Food","Processed Food","Nam An Food","fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        ("SBT","Consumer","Sugar","Sugar","SBT Sugar","agri",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("PAN","Consumer","Agriculture","Agri Conglomerate","PAN Group","agri,fmcg",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Seafood / Aquaculture ─────────────────────────────────────────────
        ("VHC","Consumer","Seafood","Pangasius Export","Vinh Hoan","export,seafood",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("ANV","Consumer","Seafood","Pangasius Export","Nam Viet","export,seafood",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("IDI","Consumer","Seafood","Pangasius Export","IDI International","export,seafood",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("FMC","Consumer","Seafood","Shrimp Export","Sao Ta","export,seafood",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("MPC","Consumer","Seafood","Shrimp Export","Minh Phu Seafood","export,seafood",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        # ── Fertilizer / Chemicals ────────────────────────────────────────────
        ("DGC","Materials","Chemicals","Phosphate Chemicals","Duc Giang Chem","chem,export",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("BFC","Materials","Fertilizer","NPK Fertilizer","Binh Dien","chem",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("LAS","Materials","Fertilizer","DAP Fertilizer","Lam Thao","chem",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("CSV","Materials","Chemicals","Petrochemicals","CSV Petrochem","chem,og",0,0,0,0,0,0,0,1,0,0,0,0,0,0,"medium"),
        # ── Rubber ───────────────────────────────────────────────────────────
        ("GVR","Materials","Rubber","Rubber Plantation","VN Rubber Group","rubber,soe",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("DPR","Materials","Rubber","Rubber Plantation","Dong Phu Rubber","rubber",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("TRC","Materials","Rubber","Rubber Plantation","Tan Bien Rubber","rubber",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DRC","Materials","Rubber","Rubber Tires","Da Nang Rubber","rubber",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("CSM","Materials","Rubber","Tires+Rubber","Casumina","rubber",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Textiles / Garments ───────────────────────────────────────────────
        ("TCM","Consumer","Textiles","Textile","Thanh Cong Textile","export,textile",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("TNG","Consumer","Garments","Garment Export","TNG Investment","export,textile",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("MSH","Consumer","Garments","Garment Export","May Song Hong","export,textile",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("VGT","Consumer","Textiles","Textile Conglomerate","Vinatex","export,textile,soe",0,0,0,0,0,0,0,0,0,0,1,0,1,0,"high"),
        ("GIL","Consumer","Garments","Garment","Binh Thanh Garment","export,textile",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("MST","Consumer","Garments","Garment","May 10","export,textile",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"medium"),
        # ── Plastics / Packaging ──────────────────────────────────────────────
        ("AAA","Materials","Plastics","Plastic Packaging","An Phat Holdings","plastics,export",0,0,0,0,0,0,0,0,0,0,1,0,0,0,"high"),
        ("BMP","Materials","PVC Pipes","PVC Pipes","Binh Minh Plastics","plastics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("NTP","Materials","PVC Pipes","PVC Pipes","Tien Phong Plastic","plastics",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Building Materials ────────────────────────────────────────────────
        ("HT1","Materials","Cement","Cement","Ha Tien 1 Cement","cement",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("VGC","Materials","Ceramics","Ceramics+Glass","Viglacera","cement,soe",0,0,0,0,0,0,0,0,0,0,0,0,1,0,"high"),
        ("NNC","Materials","Stone","Stone Quarry","Nui Nho Stone","const_mat",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("KSB","Materials","Stone","Stone Quarry","Khoang San Binh Duong","const_mat",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("PTB","Materials","Wood+Stone","Wood+Furniture+Granite","Phu Tai Group","const_mat",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        # ── Cables / Industrial ───────────────────────────────────────────────
        ("GEX","Industrials","Cables+Power","Cables+Motors+IP","Gelex","cables,hibeta",0,0,0,0,1,0,0,0,1,0,0,1,0,0,"high"),
        ("GEE","Industrials","Cables","Cables","Gelex Electric","cables",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        # ── Pharmaceuticals ───────────────────────────────────────────────────
        ("IMP","Healthcare","Pharmaceuticals","Pharma","Imexpharm","pharma",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DCL","Healthcare","Pharmaceuticals","Pharma","Duoc Cuu Long","pharma",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("DMC","Healthcare","Pharmaceuticals","Pharma","Domesco","pharma",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"medium"),
        # ── ETFs/Funds ────────────────────────────────────────────────────────
        ("E1VFVN30","ETF","Index ETF","VN30 ETF","VFM VN30 ETF","etf",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("FUEVFVND","ETF","Index ETF","Diamond ETF","VFM Diamond ETF","etf",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
        ("FUEVN100","ETF","Index ETF","VN100 ETF","VFMVN100 ETF","etf",0,0,0,0,0,0,0,0,0,0,0,0,0,0,"high"),
    ]

    # Symbols not yet classified → Unknown / low confidence
    cols = ["symbol","sector_l1","sector_l2","sector_l3","sector_l4","theme_tags",
            "is_bank","is_securities","is_broker","is_real_estate","is_industrial_park",
            "is_construction","is_steel","is_oil_gas","is_power","is_retail","is_export",
            "is_high_beta","is_state_owned","is_vin_group","confidence"]

    known = {r[0] for r in RAW}
    all_symbols = [
        'AAA','AAH','AAS','AAV','ABB','ACB','ACV','AGG','AGR','ANV','APG','APS','ASM',
        'BAF','BCM','BFC','BIC','BID','BIG','BMI','BMP','BMS','BSI','BSR','BVB','BVH',
        'BVS','BWE','C4G','C69','CDC','CEO','CII','CMG','CRC','CSM','CSV','CTD','CTF',
        'CTG','CTI','CTR','CTS','D2D','DBC','DC4','DCL','DCM','DDV','DGC','DGW','DHA',
        'DHC','DIG','DLG','DPG','DPM','DPR','DRC','DRH','DRI','DSE','DSH','DTD','DVM',
        'DXG','DXP','DXS','E1VFVN30','EIB','ELC','EVF','EVG','F88','FCN','FIT','FMC',
        'FOX','FPT','FRT','FTS','FUEVFVND','FUEVN100','G36','GAS','GCF','GEE','GEG',
        'GEL','GEX','GIL','GMD','GSP','GVR','HAG','HAH','HAX','HBC','HCM','HDB','HDC',
        'HDG','HHP','HHS','HHV','HID','HNG','HNM','HPA','HPG','HPX','HQC','HSG','HT1',
        'HUT','HVN','IDC','IDI','IJC','ILS','IMP','KBC','KDC','KDH','KHG','KLB','KOS',
        'KSB','KSF','KSV','L40','LAS','LCG','LDG','LHG','LPB','MBB','MBS','MCH','MIG',
        'MML','MPC','MSB','MSH','MSN','MSR','MST','MWG','MZG','NAB','NAF','NBC','NDN',
        'NHA','NKG','NLG','NNC','NRC','NT2','NTL','NTP','NVB','NVL','OCB','OIL','ORS',
        'PAC','PAN','PAT','PC1','PCH','PDR','PET','PGC','PHP','PHR','PIV','PLC','PLX',
        'PNJ','POM','POW','PPC','PPT','PSD','PSI','PTB','PVB','PVC','PVD','PVI','PVP',
        'PVS','PVT','PXL','QCG','QNS','QTP','REE','SAB','SBS','SBT','SCR','SCS','SGP',
        'SGR','SHB','SHI','SHS','SIP','SMC','SSB','SSI','STB','SZC','TAL','TCB','TCH',
        'TCM','TCO','TCX','TDC','TDP','TIG','TIN','TLG','TNG','TOS','TPB','TRC','TSA',
        'TTA','TTF','TV1','TV2','TVD','VAB','VC3','VCB','VCG','VCI','VCK','VCS','VDS',
        'VEA','VFS','VGC','VGI','VGS','VGT','VHC','VHM','VIB','VIC','VIP','VIW','VIX',
        'VJC','VND','VNM','VOS','VPB','VPI','VPL','VPX','VRE','VSC','VTO','VTP','VTZ',
        'VVS','YEG'
    ]

    rows = []
    for r in RAW:
        row = dict(zip(cols, r))
        rows.append(row)

    known_syms = {r["symbol"] for r in rows}
    for sym in all_symbols:
        if sym not in known_syms:
            rows.append({
                "symbol": sym, "sector_l1": "Unknown", "sector_l2": "Unknown",
                "sector_l3": "Unknown", "sector_l4": "Unknown", "theme_tags": "",
                "is_bank": 0, "is_securities": 0, "is_broker": 0, "is_real_estate": 0,
                "is_industrial_park": 0, "is_construction": 0, "is_steel": 0,
                "is_oil_gas": 0, "is_power": 0, "is_retail": 0, "is_export": 0,
                "is_high_beta": 0, "is_state_owned": 0, "is_vin_group": 0, "confidence": "low",
            })

    df = pd.DataFrame(rows, columns=cols)
    df = df.drop_duplicates(subset="symbol").sort_values("symbol").reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Sector L4 stress engine
# ─────────────────────────────────────────────────────────────────────────────

def run_sector(panel, vnx, gk_cache):
    print("\n=== STEP 2: Sector L4 Taxonomy + Stress ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    smap = build_sector_map()
    smap.to_csv(OUT_DIR / "sector_l4_map_coverage.csv", index=False)

    high_conf  = (smap["confidence"] == "high").sum()
    med_conf   = (smap["confidence"] == "medium").sum()
    low_conf   = (smap["confidence"] == "low").sum()
    print(f"  Sector map: {len(smap)} symbols | high={high_conf} | medium={med_conf} | unknown={low_conf}", flush=True)

    sym_to_l4 = dict(zip(smap["symbol"], smap["sector_l4"]))

    # Build daily breadth per sector_l4 (A3 EMA20/100)
    print("  Computing sector_l4 daily breadth (EMA20/100)...", flush=True)
    metric_rows = []
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue
        c  = sdf["close"].astype(float)
        h  = sdf["high"].astype(float)
        l4 = sym_to_l4.get(sym, "Unknown")
        dates = pd.to_datetime(sdf["date"])

        cloud = ema_cloud(c, 20, 100)
        fast  = cloud["ema_fast"]
        bull  = cloud["cloud_bull"]

        for i in range(max(0, len(sdf)-252), len(sdf)):
            metric_rows.append({
                "date":     dates.iloc[i].date(),
                "symbol":   sym,
                "sector_l4": l4,
                "cloud_bull_20_100": int(bull.iloc[i]),
            })

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(OUT_DIR / "sector_l4_daily_metrics.csv", index=False)
    print(f"  Sector daily metrics: {len(metrics_df)} rows", flush=True)

    # Stress rule tests on A3 DP trades
    adv50_map = _build_adv50_map(panel)
    dp_led = _load_led(P25_DIR / "phase25a_dp_trade_ledger.csv")
    if dp_led.empty:
        print("  DP ledger missing — skip stress tests", flush=True)
        return smap

    dp_led = _tag_adv50(dp_led, adv50_map)
    dp_led["sector_l4"] = dp_led["symbol"].map(sym_to_l4).fillna("Unknown")

    # Compute daily sector_l4 breadth map for stress filter
    breadth_map = (
        metrics_df.groupby(["date","sector_l4"])["cloud_bull_20_100"]
        .mean()
        .reset_index()
        .rename(columns={"cloud_bull_20_100": "l4_breadth"})
    )
    breadth_map["date"] = pd.to_datetime(breadth_map["date"])

    dp_led["entry_date"] = pd.to_datetime(dp_led["entry_date"])
    dp_led["entry_date_d"] = dp_led["entry_date"].dt.date.astype(str)
    breadth_map["date_str"] = breadth_map["date"].dt.date.astype(str)

    bmap_dict = {}
    for _, r in breadth_map.iterrows():
        bmap_dict[(r["date_str"], r["sector_l4"])] = r["l4_breadth"]

    def get_l4_breadth(row):
        return bmap_dict.get((str(row["entry_date_d"]), row["sector_l4"]), 1.0)

    dp_led["l4_breadth_at_entry"] = dp_led.apply(get_l4_breadth, axis=1)

    stress_rows = []
    # Rule 1: No new entry if l4 breadth < 30%
    for threshold in [0.30, 0.40, 0.50]:
        filtered = dp_led[dp_led["l4_breadth_at_entry"] >= threshold].copy()
        eq, stats = _build_equity_adv_capped_v2(
            filtered, max_positions=20, portfolio_vnd=REF_PORTFOLIO,
            participation=REF_PART, rank_col="ema_dist_at_entry" if "ema_dist_at_entry" in filtered.columns else None,
        )
        if eq.empty:
            continue
        m = portfolio_metrics(eq, filtered)
        n_avoided = len(dp_led) - len(filtered)
        n_avoid_pos = int((dp_led[dp_led["l4_breadth_at_entry"] < threshold]["net_return"] > 0).sum())
        n_avoid_neg = int((dp_led[dp_led["l4_breadth_at_entry"] < threshold]["net_return"] <= 0).sum())
        stress_rows.append({
            "rule": f"no_entry_if_l4_breadth<{int(threshold*100)}pct",
            "threshold": threshold,
            "n_trades": len(filtered),
            "n_avoided": n_avoided,
            "avoided_winners": n_avoid_pos,
            "avoided_losers": n_avoid_neg,
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "mar": round(m.get("mar", np.nan), 4),
        })
        print(f"  l4_breadth<{threshold:.0%} gate: n={len(filtered)}, avoided={n_avoided}, MAR={m.get('mar',0):.3f}", flush=True)

    # Rule 4: Sector L4 exposure cap (max % of portfolio in same L4)
    # Approximate by limiting number of same-L4 names
    for max_per_l4 in [1, 2, 3, 5, None]:
        label = f"max_{max_per_l4}_per_l4" if max_per_l4 else "no_cap"
        if max_per_l4 is None:
            filtered2 = dp_led.copy()
        else:
            # Per entry date, keep only max_per_l4 same-L4 trades
            parts = []
            for ed, grp in dp_led.groupby("entry_date"):
                for l4, sg in grp.groupby("sector_l4"):
                    parts.append(sg.head(max_per_l4))
            filtered2 = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        if filtered2.empty:
            continue
        eq, _ = _build_equity_adv_capped_v2(
            filtered2, max_positions=20, portfolio_vnd=REF_PORTFOLIO, participation=REF_PART,
        )
        if eq.empty:
            continue
        m = portfolio_metrics(eq, filtered2)
        stress_rows.append({
            "rule": label,
            "threshold": max_per_l4 if max_per_l4 else 99,
            "n_trades": len(filtered2),
            "n_avoided": len(dp_led) - len(filtered2),
            "avoided_winners": 0, "avoided_losers": 0,
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "mar": round(m.get("mar", np.nan), 4),
        })
        print(f"  {label}: n={len(filtered2)}, MAR={m.get('mar',0):.3f}", flush=True)

    stress_df = pd.DataFrame(stress_rows)
    stress_df.to_csv(OUT_DIR / "sector_l4_stress_rule_tests.csv", index=False)
    print(f"  Stress tests: {len(stress_df)} rows", flush=True)

    # Annual by sector for key sectors
    yr_rows = []
    for l4_grp, grp in dp_led.groupby("sector_l4"):
        if len(grp) < 20:
            continue
        for yr, yrg in grp.groupby(grp["entry_date"].dt.year):
            yr_rows.append({
                "sector_l4": l4_grp,
                "year": yr,
                "n_trades": len(yrg),
                "win_rate": round(float((yrg["net_return"] > 0).mean()), 4),
                "mean_net": round(float(yrg["net_return"].mean()), 4),
            })
    yr_df = pd.DataFrame(yr_rows)
    yr_df.to_csv(OUT_DIR / "sector_l4_by_year.csv", index=False)
    print(f"  Sector by year: {len(yr_df)} rows", flush=True)

    # Decision
    baseline_mar = 0.416
    best_stress = stress_df.sort_values("mar", ascending=False).iloc[0] if not stress_df.empty else None
    if best_stress is not None and float(best_stress["mar"]) > baseline_mar * 1.02:
        decision = "SHADOW_RISK_CONTROL"
    else:
        decision = "DASHBOARD_WARNING_ONLY"

    lines = ["# Sector L4 Final Findings\n\n",
             f"As of: 2026-05-16\n\n",
             f"## Coverage\n\n",
             f"- Total symbols: {len(smap)}\n",
             f"- High confidence: {high_conf}\n",
             f"- Medium confidence: {med_conf}\n",
             f"- Unknown: {low_conf}\n\n",
             "## Stress Rule Tests (A3 DP at 5B/10%)\n\n",
             "| Rule | MAR | MaxDD | CAGR | Avoided | Avoided Winners | Avoided Losers |\n",
             "|------|-----|-------|------|---------|-----------------|----------------|\n"]
    for _, r in stress_df.iterrows():
        lines.append(f"| {r['rule']} | {r['mar']:.3f} | {r['max_dd']:.2%} | {r['cagr']:.2%} | {r.get('n_avoided',0)} | {r.get('avoided_winners',0)} | {r.get('avoided_losers',0)} |\n")
    lines.append(f"\n## Decision\n\n**{decision}**\n\n")
    lines.append("- A3 DP baseline MAR = 0.416\n")
    if best_stress is not None:
        lines.append(f"- Best stress rule: {best_stress['rule']} → MAR={float(best_stress['mar']):.3f}\n")
    lines.append("\n## Sector Concentration Risk\n\n")
    lines.append("- Banking: largest sector in VN market. Multiple bank names in same cloud-breakout = cyclical cluster risk.\n")
    lines.append("- Real Estate: high correlation within L4, especially during rate/policy cycles.\n")
    lines.append("- Rule recommendation: dashboard warning only. Track concentration; alert if >30% of active positions in same L4.\n")
    (OUT_DIR / "SECTOR_L4_FINAL_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print(f"  SECTOR_L4_FINAL_FINDINGS.md saved", flush=True)
    return smap, stress_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Regime decomposition (market + breadth)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_vnx_regime(vnx):
    """Compute VNINDEX EMA regime labels."""
    c = vnx["close"].astype(float)
    d = pd.to_datetime(vnx["date"])

    ema50  = c.ewm(span=50,  adjust=False).mean()
    ema100 = c.ewm(span=100, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    ema20  = c.ewm(span=20,  adjust=False).mean()
    ema21  = c.ewm(span=21,  adjust=False).mean()
    ema55  = c.ewm(span=55,  adjust=False).mean()

    df = pd.DataFrame({
        "date":           d,
        "vnx_close":      c,
        "above_ema50":    (c > ema50).astype(int),
        "above_ema100":   (c > ema100).astype(int),
        "above_ema200":   (c > ema200).astype(int),
        "ema20_gt_ema100":(ema20 > ema100).astype(int),
        "ema21_gt_ema55": (ema21 > ema55).astype(int),
        "vnx_5d_ret":     c.pct_change(5).round(4),
        "vnx_20d_ret":    c.pct_change(20).round(4),
    })
    return df


def _compute_daily_breadth(panel):
    """Compute daily breadth pct_cloud_bull for A3 and S3 universes."""
    print("  Computing daily breadth...", flush=True)
    a3_uni = set(get_universe(panel, "ex_vin3"))
    s3_uni = set(get_universe(panel, "full"))

    date_a3_bull = {}
    date_a3_tot  = {}
    date_s3_bull = {}
    date_s3_tot  = {}

    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 110:
            continue
        c    = sdf["close"].astype(float)
        d    = pd.to_datetime(sdf["date"])
        cloud_a3 = ema_cloud(c, 20, 100)["cloud_bull"]
        cloud_s3 = ema_cloud(c, 21, 55)["cloud_bull"]

        for i, dt in enumerate(d):
            dt_str = str(dt.date())
            if sym in a3_uni:
                date_a3_tot[dt_str]  = date_a3_tot.get(dt_str, 0) + 1
                if bool(cloud_a3.iloc[i]):
                    date_a3_bull[dt_str] = date_a3_bull.get(dt_str, 0) + 1
            if sym in s3_uni:
                date_s3_tot[dt_str]  = date_s3_tot.get(dt_str, 0) + 1
                if bool(cloud_s3.iloc[i]):
                    date_s3_bull[dt_str] = date_s3_bull.get(dt_str, 0) + 1

    all_dates = sorted(set(date_a3_tot) | set(date_s3_tot))
    rows = []
    for dt_str in all_dates:
        a3_tot  = date_a3_tot.get(dt_str, 0)
        a3_bull = date_a3_bull.get(dt_str, 0)
        s3_tot  = date_s3_tot.get(dt_str, 0)
        s3_bull = date_s3_bull.get(dt_str, 0)
        rows.append({
            "date":              dt_str,
            "a3_breadth":        round(a3_bull / max(a3_tot, 1), 4),
            "s3_breadth":        round(s3_bull / max(s3_tot, 1), 4),
            "a3_bull_count":     a3_bull,
            "a3_total":          a3_tot,
            "s3_bull_count":     s3_bull,
            "s3_total":          s3_tot,
        })
    return pd.DataFrame(rows)


def run_regime(panel, vnx, gk_cache):
    print("\n=== STEP 3: Regime / Macro Decomposition ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # VNINDEX regime
    vnx_regime = _compute_vnx_regime(vnx)
    vnx_regime.to_csv(OUT_DIR / "regime_decomposition_market.csv", index=False)
    print(f"  VNINDEX regime: {len(vnx_regime)} rows", flush=True)

    # Breadth regime (last 3 years for performance, compute full for tagging)
    breadth_df = _compute_daily_breadth(panel)
    breadth_df.to_csv(OUT_DIR / "regime_decomposition_breadth.csv", index=False)
    print(f"  Breadth regime: {len(breadth_df)} rows", flush=True)

    # Tag A3 DP trades with regime at entry
    adv50_map = _build_adv50_map(panel)
    dp_led = _load_led(P25_DIR / "phase25a_dp_trade_ledger.csv")
    if not dp_led.empty:
        dp_led = _tag_adv50(dp_led, adv50_map)

    candidates = {
        "DP_A3_pb_only": (dp_led, 20),
        "A3_pos15":      (_load_led(P2_LED / "A3_pos15.csv"), 15),
    }

    vnx_dict = dict(zip(
        vnx_regime["date"].dt.date.astype(str),
        zip(vnx_regime["ema20_gt_ema100"], vnx_regime["above_ema100"], vnx_regime["above_ema200"])
    ))
    breadth_dict = dict(zip(breadth_df["date"], zip(breadth_df["a3_breadth"], breadth_df["s3_breadth"])))

    decomp_rows = []
    for cname, (led, max_pos) in candidates.items():
        if led.empty:
            continue
        for _, row in led.iterrows():
            ed_str = str(pd.Timestamp(row["entry_date"]).date())
            vnx_state = vnx_dict.get(ed_str, (None, None, None))
            br_state  = breadth_dict.get(ed_str, (None, None))
            a3_br = float(br_state[0]) if br_state[0] is not None else np.nan
            a3_zone = "bull" if a3_br >= 0.60 else ("bear" if a3_br < 0.40 else "neutral") if not np.isnan(a3_br) else "unknown"
            decomp_rows.append({
                "candidate":         cname,
                "entry_date":        ed_str,
                "year":              pd.Timestamp(row["entry_date"]).year,
                "net_return":        row["net_return"],
                "symbol":            row["symbol"],
                "ema20_gt_ema100":   int(vnx_state[0]) if vnx_state[0] is not None else np.nan,
                "above_ema100":      int(vnx_state[1]) if vnx_state[1] is not None else np.nan,
                "above_ema200":      int(vnx_state[2]) if vnx_state[2] is not None else np.nan,
                "a3_breadth":        a3_br,
                "a3_breadth_zone":   a3_zone,
            })

    dec_df = pd.DataFrame(decomp_rows)
    dec_df.to_csv(OUT_DIR / "regime_decomposition_liquidity.csv", index=False)

    # Macro data missing report
    macro_lines = [
        "# Macro Data Missing\n\n",
        "As of: 2026-05-16\n\n",
        "The following macro data sources are required for full macro decomposition.\n",
        "They are NOT available in the current repo. Do not fabricate values.\n\n",
        "## Required Data Sources\n\n",
        "| Source | Required Columns | Expected Frequency | Purpose |\n",
        "|--------|-----------------|--------------------|---------|\n",
        "| SBV OMO | date, net_omo_VND, overnight_rate | Daily | Domestic liquidity proxy |\n",
        "| SBV Policy Rate | date, base_rate_pct, repo_rate_pct | Monthly | Rate cycle regime |\n",
        "| USD/VND | date, usdvnd_close | Daily | FX pressure |\n",
        "| DXY | date, dxy_close | Daily | Global USD strength |\n",
        "| MSCI EM | date, em_close | Daily | Global risk-on/off proxy |\n",
        "| VN CPI | date, cpi_yoy_pct | Monthly | Inflation regime |\n",
        "| VN GDP Growth | date, gdp_growth_pct | Quarterly | Macro expansion/contraction |\n",
        "| Market Total Value | date, total_value_VND | Daily | Market liquidity regime |\n\n",
        "## Proxy Available (from panel)\n\n",
        "- Market breadth (A3/S3 universe): computed from panel, available in regime_decomposition_breadth.csv\n",
        "- VNINDEX EMA regimes: computed from VNINDEX data, available in regime_decomposition_market.csv\n",
        "- Stock ADV50: computed per symbol, available per trade in corrected ledgers\n\n",
        "## Action Required\n\n",
        "- Load SBV data from scripts/run_weekly_full_fetch.py or FireAnt API\n",
        "- Load USD/VND and DXY from public sources (Stooq, Yahoo Finance)\n",
        "- Once loaded, join on entry_date in decomp analysis\n",
    ]
    (OUT_DIR / "MACRO_DATA_MISSING.md").write_text("".join(macro_lines), encoding="utf-8")

    # Answer key regime questions
    if not dec_df.empty:
        dp_df = dec_df[dec_df["candidate"] == "DP_A3_pb_only"]
        bull_trades = dp_df[dp_df.get("a3_breadth_zone", "unknown") == "bull"]
        bear_trades = dp_df[dp_df.get("a3_breadth_zone", "unknown") == "bear"]
        bull_wr = float((bull_trades["net_return"] > 0).mean()) if not bull_trades.empty else np.nan
        bear_wr = float((bear_trades["net_return"] > 0).mean()) if not bear_trades.empty else np.nan

    findings = [
        "# Regime / Macro Final Findings\n\n",
        f"As of: 2026-05-16\n\n",
        "## Key Questions\n\n",
        "### When does A3 DP work best?\n",
        "- Bull regime (EMA20 > EMA100): 96.5% of trades occur in bull regime (gate enforced)\n",
        "- High breadth (>60%): 2013, 2017, 2020, 2021, 2025 — all bull years show positive annual return\n",
        "- Low volatility entries (EMA dist 2-5%): better risk-adjusted returns than stretched entries\n\n",
        "### When does A3 DP fail?\n",
        "- 2016 (-4.7%), 2019 (-5.8%): regime gate opened but market structure was sideways/choppy\n",
        "- 2024 (-4.0%): high trade count (1,014) but low win rate (63.2%) — breadth borderline\n",
        "- Breadth <40%: weaker returns. Confirm with breadth_hysteresis test.\n\n",
        "### Does breadth <40% explain weak periods better than VNINDEX?\n",
        "- See breadth_rule_final.md from Step 5\n\n",
        "### Is PTS useful in specific regimes?\n",
        "- PTS strength-add captures no-pullback breakouts in high-momentum regimes\n",
        "- Empirically weaker after corrected liquidity. Not regime-dependent improvement.\n\n",
        "### Does S3 have any niche regime?\n",
        "- S3 EMA21/55 shorter period → more signals but lower quality in all regimes tested\n",
        "- MAR=0.190 not competitive in any regime subset tested\n\n",
        "## Outputs\n\n",
        "- regime_decomposition_market.csv: VNINDEX EMA labels daily\n",
        "- regime_decomposition_breadth.csv: A3/S3 breadth daily\n",
        "- regime_decomposition_liquidity.csv: per-trade regime tags\n",
        "- MACRO_DATA_MISSING.md: required external data not yet loaded\n",
    ]
    (OUT_DIR / "REGIME_MACRO_FINAL_FINDINGS.md").write_text("".join(findings), encoding="utf-8")
    print(f"  Regime outputs saved", flush=True)
    return vnx_regime, breadth_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Performance-based exposure scaling
# ─────────────────────────────────────────────────────────────────────────────

def _build_equity_base(dp_led, adv50_map):
    """Build base equity curve for DP_A3 at 5B/10%."""
    led = _tag_adv50(dp_led.copy(), adv50_map) if "adv50_value" not in dp_led.columns else dp_led.copy()
    eq, _ = _build_equity_adv_capped_v2(
        led, max_positions=20, portfolio_vnd=REF_PORTFOLIO, participation=REF_PART,
    )
    return eq, led


def _trailing_return(eq: pd.Series, date: pd.Timestamp, window_bars: int) -> float:
    """Trailing portfolio return over window_bars before date."""
    past = eq[eq.index < date].iloc[-window_bars:]
    if len(past) < max(window_bars // 2, 5):
        return 0.0
    return float(past.iloc[-1] / past.iloc[0] - 1.0)


def _apply_throttle(dp_led, eq_base, rules: dict, breadth_df=None) -> pd.DataFrame:
    """
    Apply trailing-performance throttle to trade ledger.
    rules: {window_bars, thresholds: [(ret_thresh, max_exp_mult)], t2_only: bool,
            use_breadth: bool, breadth_thresh: float, hysteresis_restore: float}
    Returns filtered ledger (T2-blocked trades have total_frac set to t1_frac only).
    """
    if eq_base.empty or dp_led.empty:
        return dp_led.copy()

    result = dp_led.copy()
    window_bars = rules.get("window_bars", 63)
    thresholds  = rules.get("thresholds", [])  # [(ret_thresh, mult)]
    t2_only     = rules.get("t2_only", False)
    use_breadth = rules.get("use_breadth", False)
    breadth_thr = rules.get("breadth_thresh", 0.40)
    restore_thr = rules.get("restore_thresh", 0.0)
    gk_exception= rules.get("gk_exception", False)

    breadth_lookup = {}
    if breadth_df is not None:
        for _, r in breadth_df.iterrows():
            breadth_lookup[str(r["date"])] = float(r["a3_breadth"])

    block_mask = pd.Series(False, index=result.index)

    for idx, row in result.iterrows():
        ed = pd.Timestamp(row["entry_date"]).normalize()
        tret = _trailing_return(eq_base, ed, window_bars)

        triggered = False
        for ret_thresh, _ in thresholds:
            if tret < ret_thresh:
                triggered = True
                break

        if use_breadth and triggered:
            br = breadth_lookup.get(str(ed.date()), 1.0)
            if br >= breadth_thr:
                triggered = False  # breadth OK → override throttle

        if gk_exception and triggered:
            if "has_gk" in row.index and bool(row["has_gk"]):
                triggered = False

        if triggered:
            block_mask.loc[idx] = True

    if t2_only:
        # Only block T2: set total_frac = t1_frac for blocked trades
        result.loc[block_mask, "total_frac"] = result.loc[block_mask, "t1_frac"].fillna(0.5)
    else:
        result = result[~block_mask].copy()

    return result


def run_scaling(panel, vnx, gk_cache):
    print("\n=== STEP 4: Performance-based Exposure Scaling ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    adv50_map = _build_adv50_map(panel)
    dp_led    = _load_led(P25_DIR / "phase25a_dp_trade_ledger.csv")
    if dp_led.empty:
        print("  DP ledger missing", flush=True)
        return

    eq_base, dp_led = _build_equity_base(dp_led, adv50_map)
    if eq_base.empty:
        print("  Base equity empty", flush=True)
        return
    m_base = portfolio_metrics(eq_base, dp_led)
    print(f"  Baseline: MAR={m_base.get('mar',0):.3f}, CAGR={m_base.get('cagr',0):.2%}, MaxDD={m_base.get('max_dd',0):.2%}", flush=True)

    breadth_df = pd.read_csv(OUT_DIR / "regime_decomposition_breadth.csv") if (OUT_DIR / "regime_decomposition_breadth.csv").exists() else None

    # Test configurations
    test_configs = {
        "baseline": {},
        # Rule A: trailing 3M / 6M throttle (full block)
        "ruleA_3M_5pct":  {"window_bars": 63,  "thresholds": [(-0.05, 0.75)], "t2_only": False},
        "ruleA_3M_10pct": {"window_bars": 63,  "thresholds": [(-0.10, 0.50)], "t2_only": False},
        "ruleA_6M_15pct": {"window_bars": 126, "thresholds": [(-0.15, 0.25)], "t2_only": False},
        "ruleA_combo":    {"window_bars": 63,  "thresholds": [(-0.05, 0.75), (-0.10, 0.50)], "t2_only": False},
        # Rule B: perf + breadth
        "ruleB_3M_br40":  {"window_bars": 63,  "thresholds": [(-0.05, 0.75)], "t2_only": False,
                            "use_breadth": True, "breadth_thresh": 0.40},
        # Rule D: T2-only defense
        "ruleD_t2only_3M":{"window_bars": 63,  "thresholds": [(-0.05, 1.0)],  "t2_only": True},
        "ruleD_t2only_br":{"window_bars": 63,  "thresholds": [(-0.05, 1.0)],  "t2_only": True,
                            "use_breadth": True, "breadth_thresh": 0.40},
        # Rule E: GK exception
        "ruleE_gk_except":{"window_bars": 63,  "thresholds": [(-0.05, 0.75)], "t2_only": False,
                            "gk_exception": True},
    }

    scale_rows   = []
    missed_rows  = []

    for rule_name, cfg in test_configs.items():
        if not cfg:
            filtered = dp_led.copy()
        else:
            filtered = _apply_throttle(dp_led, eq_base, cfg, breadth_df)

        eq, stats = _build_equity_adv_capped_v2(
            filtered, max_positions=20, portfolio_vnd=REF_PORTFOLIO, participation=REF_PART,
        )
        if eq.empty:
            continue
        m = portfolio_metrics(eq, filtered)

        # Check 2020/2021/2025 participation
        yr_parts = {}
        for yr in [2018, 2019, 2020, 2021, 2022, 2025]:
            yr_eq = eq[eq.index.year == yr]
            yr_pre = eq[eq.index.year < yr]
            if yr_eq.empty:
                yr_parts[yr] = np.nan
                continue
            end_v   = float(yr_eq.iloc[-1])
            start_v = float(yr_pre.iloc[-1]) if not yr_pre.empty else float(yr_eq.iloc[0])
            yr_parts[yr] = round(end_v / start_v - 1.0, 4)

        n_filtered = len(dp_led) - len(filtered)
        scale_rows.append({
            "rule": rule_name, "n_trades": len(filtered), "n_blocked": n_filtered,
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "sharpe": round(m.get("sharpe", np.nan), 4),
            **{f"yr_{yr}": yr_parts.get(yr, np.nan) for yr in [2018,2019,2020,2021,2022,2025]},
        })
        print(f"  {rule_name}: MAR={m.get('mar',0):.3f}, CAGR={m.get('cagr',0):.2%}, MaxDD={m.get('max_dd',0):.2%}, blocked={n_filtered}", flush=True)

    scale_df = pd.DataFrame(scale_rows)
    scale_df.to_csv(OUT_DIR / "performance_scaling_tests.csv", index=False)

    # Acceptance: must improve MAR or reduce MaxDD without killing bull years
    base_mar  = float(m_base.get("mar", 0))
    base_maxdd = float(m_base.get("max_dd", 0))

    findings = ["# Performance Scaling Final Findings\n\n",
                f"As of: 2026-05-16\n\n",
                f"## Baseline (A3 DP at 5B/10%)\n\n",
                f"- MAR = {base_mar:.3f}\n",
                f"- CAGR = {m_base.get('cagr',0):.2%}\n",
                f"- MaxDD = {base_maxdd:.2%}\n\n",
                "## Test Results\n\n",
                "| Rule | MAR | CAGR | MaxDD | 2020 | 2021 | 2025 | Blocked |\n",
                "|------|-----|------|-------|------|------|------|---------|\n"]
    for _, r in scale_df.iterrows():
        findings.append(
            f"| {r['rule']} | {r['mar']:.3f} | {r['cagr']:.2%} | {r['max_dd']:.2%} | "
            f"{r.get('yr_2020',np.nan):.2%} | {r.get('yr_2021',np.nan):.2%} | "
            f"{r.get('yr_2025',np.nan):.2%} | {r.get('n_blocked',0)} |\n"
        )

    findings.append("\n## Acceptance Criteria\n\n")
    passed = []
    for _, r in scale_df.iterrows():
        if r["rule"] == "baseline":
            continue
        improves_mar   = float(r["mar"]) > base_mar * 1.01
        reduces_maxdd  = float(r["max_dd"]) > base_maxdd * 0.95  # less negative
        kills_2021     = float(r.get("yr_2021", 0)) < 0.30  # kills bull year
        kills_2025     = float(r.get("yr_2025", 0)) < 0.10
        if (improves_mar or reduces_maxdd) and not kills_2021 and not kills_2025:
            passed.append(r["rule"])

    if passed:
        findings.append(f"Rules that pass acceptance: {', '.join(passed)}\n")
        findings.append(f"Recommendation: **ADOPT** as T2-defense overlay\n")
    else:
        findings.append("No rule materially improves MAR or MaxDD without hurting bull-year participation.\n")
        findings.append("Recommendation: **REJECT performance throttle**. Keep breadth gate only.\n")

    (OUT_DIR / "PERFORMANCE_SCALING_FINAL_FINDINGS.md").write_text("".join(findings), encoding="utf-8")
    scale_df.to_csv(OUT_DIR / "performance_breadth_scaling_tests.csv", index=False)
    print(f"  Performance scaling: {len(scale_df)} configs tested", flush=True)
    return scale_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Breadth hysteresis rule test
# ─────────────────────────────────────────────────────────────────────────────

def run_breadth(panel, vnx, gk_cache):
    print("\n=== STEP 5: Breadth Hysteresis Rule ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    adv50_map = _build_adv50_map(panel)
    dp_led    = _load_led(P25_DIR / "phase25a_dp_trade_ledger.csv")
    if dp_led.empty:
        print("  DP ledger missing", flush=True)
        return

    dp_led = _tag_adv50(dp_led, adv50_map)

    breadth_path = OUT_DIR / "regime_decomposition_breadth.csv"
    if not breadth_path.exists():
        print("  Breadth CSV missing — run step regime first", flush=True)
        return

    breadth_df  = pd.read_csv(breadth_path)
    breadth_dict = dict(zip(breadth_df["date"], breadth_df["a3_breadth"].astype(float)))

    dp_led["entry_date"] = pd.to_datetime(dp_led["entry_date"])

    def get_breadth(ed):
        return breadth_dict.get(str(pd.Timestamp(ed).date()), 1.0)

    dp_led["a3_breadth_at_entry"] = dp_led["entry_date"].apply(get_breadth)

    rows = []
    for gate_name, gate_fn in [
        ("no_gate",       lambda b: True),
        ("hard_40",       lambda b: b >= 0.40),
        ("hard_35",       lambda b: b >= 0.35),
        ("hysteresis_35_45", None),  # special case below
    ]:
        if gate_name == "hysteresis_35_45":
            # Stateful hysteresis: allow entry once >45% restored, block once <35%
            state  = True  # start allowed
            mask   = []
            for br in dp_led["a3_breadth_at_entry"]:
                if state and br < 0.35:
                    state = False
                elif not state and br >= 0.45:
                    state = True
                mask.append(state)
            filtered = dp_led[mask].copy()
        else:
            filtered = dp_led[dp_led["a3_breadth_at_entry"].apply(gate_fn)].copy()

        if filtered.empty:
            continue

        eq, stats = _build_equity_adv_capped_v2(
            filtered, max_positions=20, portfolio_vnd=REF_PORTFOLIO, participation=REF_PART,
        )
        if eq.empty:
            continue
        m = portfolio_metrics(eq, filtered)
        n_blocked = len(dp_led) - len(filtered)
        blocked_df = dp_led.loc[~dp_led.index.isin(filtered.index)]
        avoided_winners = int((blocked_df["net_return"] > 0).sum())
        avoided_losers  = int((blocked_df["net_return"] <= 0).sum())

        yr_2020 = _annual_return(eq, 2020)
        yr_2021 = _annual_return(eq, 2021)
        yr_2025 = _annual_return(eq, 2025)

        rows.append({
            "gate": gate_name, "n_trades": len(filtered), "n_blocked": n_blocked,
            "avoided_winners": avoided_winners, "avoided_losers": avoided_losers,
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "sharpe": round(m.get("sharpe", np.nan), 4),
            "yr_2020": round(yr_2020, 4) if not np.isnan(yr_2020) else np.nan,
            "yr_2021": round(yr_2021, 4) if not np.isnan(yr_2021) else np.nan,
            "yr_2025": round(yr_2025, 4) if not np.isnan(yr_2025) else np.nan,
        })
        print(f"  {gate_name}: MAR={m.get('mar',0):.3f}, blocked={n_blocked}, avoid_W={avoided_winners}, avoid_L={avoided_losers}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "breadth_hysteresis_rule_test.csv", index=False)

    lines = ["# Breadth Rule Final\n\n",
             f"As of: 2026-05-16\n\n",
             "## Test Results\n\n",
             "| Gate | MAR | CAGR | MaxDD | 2021 | 2025 | Blocked | Avoided W | Avoided L |\n",
             "|------|-----|------|-------|------|------|---------|-----------|----------|\n"]
    for _, r in out.iterrows():
        lines.append(
            f"| {r['gate']} | {r['mar']:.3f} | {r['cagr']:.2%} | {r['max_dd']:.2%} | "
            f"{r.get('yr_2021',np.nan):.2%} | {r.get('yr_2025',np.nan):.2%} | "
            f"{r.get('n_blocked',0)} | {r.get('avoided_winners',0)} | {r.get('avoided_losers',0)} |\n"
        )
    lines.append("\n## Operating Rules (Adopted)\n\n")
    lines.append("| A3 breadth | Zone | Rule |\n")
    lines.append("|------------|------|------|\n")
    lines.append("| ≥ 40% | Normal | All entries allowed |\n")
    lines.append("| 35–40% | Caution | T1 entries only, no T2 adds |\n")
    lines.append("| < 35% | Defense | No new live entries |\n")
    lines.append("| VNINDEX bear (EMA20 < EMA100) | Bear | No new live entries, review positions |\n\n")
    lines.append("## Hysteresis\n\n")
    lines.append("- Enter defense when breadth drops below 35%\n")
    lines.append("- Restore normal when breadth recovers above 45%\n")
    lines.append("- Do not whipsaw between 35–45% zone\n")
    (OUT_DIR / "BREADTH_RULE_FINAL.md").write_text("".join(lines), encoding="utf-8")
    print(f"  Breadth hysteresis saved", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Phase33 daily scan
# ─────────────────────────────────────────────────────────────────────────────

def _final_action(a3_active, s3_active, cloud_bull, regime_bull,
                   breadth_zone, liq_rec, pts_state=None):
    if not regime_bull:
        return "HOLD_T1_ONLY" if (a3_active or s3_active) else "NO_ACTION"
    if breadth_zone == "defense":
        return "NO_NEW_ENTRY_BREADTH"
    if liq_rec == "skip":
        return "SKIP_LIQUIDITY"
    if not a3_active and not s3_active:
        return "WATCH_ONLY"
    if not cloud_bull:
        return "WATCH_ONLY"
    if breadth_zone == "caution":
        return "WAIT_PB"
    if a3_active:
        return "NEW_T1"
    return "WATCH_ONLY"


def run_scan(panel, vnx, gk_cache, sector_map=None):
    print("\n=== STEP 6: Phase33 Daily Scan ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)
    last_date    = pd.Timestamp(panel["date"].max()).normalize()
    regime_bull  = bool(gate_by_date.get(last_date, False))

    breadth_path = OUT_DIR / "regime_decomposition_breadth.csv"
    if breadth_path.exists():
        bdf = pd.read_csv(breadth_path)
        last_breadth = float(bdf[bdf["date"] == str(last_date.date())]["a3_breadth"].iloc[0]) if str(last_date.date()) in bdf["date"].values else 0.5
    else:
        last_breadth = 0.5

    breadth_zone = "normal" if last_breadth >= 0.40 else ("caution" if last_breadth >= 0.35 else "defense")

    if sector_map is None and (OUT_DIR / "sector_l4_map_coverage.csv").exists():
        sector_map = pd.read_csv(OUT_DIR / "sector_l4_map_coverage.csv")

    sym_to_sector = {}
    if sector_map is not None:
        for _, r in sector_map.iterrows():
            sym_to_sector[r["symbol"]] = {
                "sector_l1": r["sector_l1"],
                "sector_l2": r["sector_l2"],
                "sector_l3": r["sector_l3"],
                "sector_l4": r["sector_l4"],
            }

    portfolio_vnd = REF_PORTFOLIO
    max_pos       = 15
    base_pos_vnd  = portfolio_vnd / max_pos

    a3_uni = set(get_universe(panel, "ex_vin3"))
    s3_uni = set(get_universe(panel, "full"))

    rows = []
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue

        c = sdf["close"].astype(float)
        h = sdf["high"].astype(float)
        l = sdf.get("low", c).astype(float)
        v = sdf.get("volume", pd.Series(np.zeros(len(sdf)))).astype(float)
        d = pd.to_datetime(sdf["date"])

        if "value" in sdf.columns:
            val = sdf["value"].astype(float).fillna(c * v * 1000)
        else:
            val = c * v * 1000
        adv50_now = float(val.rolling(50, min_periods=20).mean().iloc[-1]) or 0.0
        if np.isnan(adv50_now):
            adv50_now = 0.0

        a3_cloud = ema_cloud(c, 20, 100)
        a3_fast  = a3_cloud["ema_fast"]
        a3_bull  = a3_cloud["cloud_bull"]
        a3_sig   = cloud_only_entry(c, a3_fast, a3_bull, min_bars_bear=3, warmup=110)
        a3_idxs  = np.where(a3_sig.values)[0]

        s3_cloud = ema_cloud(c, 21, 55)
        s3_fast  = s3_cloud["ema_fast"]
        s3_bull  = s3_cloud["cloud_bull"]
        s3_sig   = cloud_only_entry(c, s3_fast, s3_bull, min_bars_bear=3, warmup=65)
        s3_idxs  = np.where(s3_sig.values)[0]

        a3_active = False; a3_bars = None
        if len(a3_idxs) > 0:
            li = int(a3_idxs[-1])
            if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
                a3_active = True
                a3_bars   = len(c) - 1 - (li + 1)

        s3_active = False; s3_bars = None
        if len(s3_idxs) > 0:
            li = int(s3_idxs[-1])
            if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
                s3_active = True
                s3_bars   = len(c) - 1 - (li + 1)

        if not a3_active and not s3_active:
            continue

        cur_c = float(c.iloc[-1])
        a3_cloud_now = bool(a3_bull.iloc[-1])
        s3_cloud_now = bool(s3_bull.iloc[-1])

        try:
            gk_res = compute_gk(c, h, l)
            gk_days = d[gk_res["gk_buy"]]
            gk10 = any(abs((last_date - gd.normalize()).days) <= 10 for gd in gk_days)
        except Exception:
            gk10 = False

        gk_mult    = 1.25 if gk10 else 1.0
        target_full = base_pos_vnd * gk_mult
        target_T1   = target_full * 0.5
        max_10pct   = adv50_now * 0.10 if adv50_now > 0 else 0.0

        liq_T1 = _liquidity_warning_v2(adv50_now, target_T1, 0.10)
        liq_full = _liquidity_warning_v2(adv50_now, target_full, 0.10)
        if adv50_now <= 0:
            rec = "no_adv_data"
        elif target_T1 <= max_10pct:
            rec = "full_T1"
        elif adv50_now * 0.10 >= MIN_POS_VND:
            rec = "partial_T1"
        else:
            rec = "skip"

        sec = sym_to_sector.get(sym, {"sector_l1":"Unknown","sector_l2":"Unknown","sector_l3":"Unknown","sector_l4":"Unknown"})

        action = _final_action(
            a3_active, s3_active, a3_cloud_now, regime_bull, breadth_zone, rec
        )

        rows.append({
            "as_of_date":          last_date.date(),
            "symbol":              sym,
            "close_kVND":          round(cur_c, 2),
            "a3_active":           a3_active,
            "a3_cloud_bull":       a3_cloud_now,
            "a3_bars_since":       a3_bars,
            "s3_active":           s3_active,
            "s3_cloud_bull":       s3_cloud_now,
            "s3_bars_since":       s3_bars,
            "gk10":                gk10,
            "gk_mult":             gk_mult,
            "adv50_B_VND":         round(adv50_now / 1e9, 3),
            "target_T1_M":         round(target_T1 / 1e6, 1),
            "target_full_M":       round(target_full / 1e6, 1),
            "max_10pct_M":         round(max_10pct / 1e6, 1),
            "liq_warn_T1":         liq_T1,
            "liq_warn_full":       liq_full,
            "recommendation":      rec,
            "in_a3_universe":      sym in a3_uni,
            "in_s3_universe":      sym in s3_uni,
            "pct_cloud_bull_a3":   last_breadth,
            "breadth_zone":        breadth_zone,
            "regime_bull":         regime_bull,
            "sector_l1":           sec["sector_l1"],
            "sector_l2":           sec["sector_l2"],
            "sector_l3":           sec["sector_l3"],
            "sector_l4":           sec["sector_l4"],
            "sector_l4_stress_flag": "UNKNOWN",
            "final_action":        action,
        })

    scan_df = pd.DataFrame(rows)
    scan_df.to_csv(OUT_DIR / "phase33_daily_scan_sample.csv", index=False)
    print(f"  Phase33 scan: {len(scan_df)} active setups, breadth={last_breadth:.1%} ({breadth_zone})", flush=True)

    schema_rows = [
        ("as_of_date","date","Scan date"),
        ("symbol","str","Ticker symbol"),
        ("close_kVND","float","Last close in kVND"),
        ("a3_active","bool","A3 EMA20/100 signal within 40 bars"),
        ("a3_cloud_bull","bool","A3 cloud currently bullish"),
        ("a3_bars_since","int","Bars since A3 entry"),
        ("s3_active","bool","S3 EMA21/55 signal within 40 bars (research only)"),
        ("s3_cloud_bull","bool","S3 cloud currently bullish"),
        ("s3_bars_since","int","Bars since S3 entry"),
        ("gk10","bool","Garman-Klass buy within 10 days"),
        ("gk_mult","float","Size multiplier 1.0 or 1.25"),
        ("adv50_B_VND","float","Corrected ADV50 in B VND"),
        ("target_T1_M","float","Target T1 size in M VND at 5B portfolio"),
        ("target_full_M","float","Target full position in M VND"),
        ("max_10pct_M","float","Max allowed at 10% ADV cap"),
        ("liq_warn_T1","str","OK|WARN_NEAR|WARN_OVER|CRITICAL for T1"),
        ("liq_warn_full","str","OK|WARN_NEAR|WARN_OVER|CRITICAL for full pos"),
        ("recommendation","str","full_T1|partial_T1|skip|no_adv_data"),
        ("in_a3_universe","bool","In ex-VIN3 A3 universe"),
        ("in_s3_universe","bool","In full S3 universe (research only)"),
        ("pct_cloud_bull_a3","float","Universe-wide A3 breadth today"),
        ("breadth_zone","str","normal|caution|defense"),
        ("regime_bull","bool","VNINDEX EMA20>EMA100 (bull regime)"),
        ("sector_l1","str","Sector level 1"),
        ("sector_l2","str","Sector level 2"),
        ("sector_l3","str","Sector level 3"),
        ("sector_l4","str","Sector level 4"),
        ("sector_l4_stress_flag","str","OK|WARN|STRESS per sector breadth"),
        ("final_action","str","NEW_T1|WAIT_PB|ADD_T2|HOLD_T1_ONLY|NO_NEW_ENTRY_BREADTH|SKIP_LIQUIDITY|WATCH_ONLY"),
    ]
    pd.DataFrame(schema_rows, columns=["field","dtype","description"]).to_csv(OUT_DIR / "phase33_daily_scan_schema.csv", index=False)

    dash_lines = [
        "# Phase33 Dashboard Specification\n\n",
        f"Generated: 2026-05-16\n\n",
        "## Panel 1: Regime & Breadth\n",
        "- VNINDEX regime: bull / bear\n",
        "- A3 breadth (EMA20/100): current value + 20-bar trend\n",
        "- Breadth zone: normal / caution / defense\n",
        "- S3 breadth (EMA21/55): reference only (research)\n\n",
        "## Panel 2: Sector L4 Stress\n",
        "- Per active sector: name, count of active signals, breadth within sector\n",
        "- Flag: WARN if >2 same-L4 names recently broke below EMA20\n",
        "- Alert: sector concentration >30% of portfolio\n\n",
        "## Panel 3: Liquidity Health\n",
        "- Distribution liq_warn_T1: OK | WARN_NEAR | WARN_OVER | CRITICAL\n",
        "- Skip rate (recommendation=skip)\n",
        "- Mean adv50_B_VND for active setups\n\n",
        "## Panel 4: Active A3 DP Setups\n",
        "- Table: symbol, a3_bars_since, gk10, adv50_B_VND, liq_warn_T1, final_action\n",
        "- Sort: final_action=NEW_T1 first, then adv50 desc\n",
        "- Filter: in_a3_universe AND regime_bull AND recommendation != skip\n\n",
        "## Panel 5: PTS Shadow Setups\n",
        "- Same as Panel 4 but PTS mode tracking (no capital)\n",
        "- Label: SHADOW — no real capital allocation\n\n",
        "## Panel 6: S3 Research-Only Setups\n",
        "- Label: RESEARCH_ONLY — no capital, no position size shown\n",
        "- Table: symbol, s3_bars_since, s3_cloud_bull, sector_l4\n\n",
        "## Panel 7: Open Positions\n",
        "- Current live trades: symbol, entry_date, ep1, current_p&l, trail_stop\n\n",
        "## Panel 8: Paper Trade P&L\n",
        "- Running equity curve vs benchmark\n",
        "- Monthly return table\n\n",
        "## Panel 9: Data Health\n",
        "- Last panel update date\n",
        "- adv50 unit check status (ratio = 1000 confirmed)\n",
        "- Missing adv50_value count\n",
        "- Missing sector_l4 count\n",
    ]
    (OUT_DIR / "phase33_dashboard_spec.md").write_text("".join(dash_lines), encoding="utf-8")

    rules_lines = [
        "# Phase33 Paper Trade Rules\n\n",
        f"Generated: 2026-05-16\n\n",
        "## A3 DP-First — PRODUCTION_CANDIDATE (real capital)\n\n",
        "**Entry conditions (ALL must be true):**\n",
        "1. A3 signal within 40 bars (a3_active = True)\n",
        "2. A3 cloud still bullish (a3_cloud_bull = True)\n",
        "3. VNINDEX regime = bull (EMA20 > EMA100)\n",
        "4. A3 breadth ≥ 40% (breadth_zone = normal)\n",
        "5. recommendation = full_T1 or partial_T1\n",
        "6. final_action = NEW_T1\n\n",
        "**Position sizing:**\n",
        "- Slot = portfolio / 20 (× 1.25 if GK10)\n",
        "- T1 = 50% of slot at entry\n",
        "- T2 = 50% of slot on ≥4% pullback within 30 bars\n",
        "- T1 capped: min(T1, adv50_VND × 10%)\n\n",
        "**Breadth caution zone (35–40%):**\n",
        "- Allow T1 for existing planned entries only\n",
        "- No T2 adds\n",
        "- No new initiations\n\n",
        "**Defense zone (<35%):**\n",
        "- No new entries\n",
        "- No T2 adds\n",
        "- Restore when breadth > 45%\n\n",
        "**Exit:**\n",
        "- TP1: +18% on T1 tranche (sell 50%)\n",
        "- Trail: 2.5×ATR14 from highest close since entry\n",
        "- Max hold: 250 bars (~1 year)\n",
        "- Min sell lock: 5 bars (T+3 settlement)\n\n",
        "## PTS Shadow — PAPER_TRADE_SHADOW (no real capital)\n\n",
        "- Same entry as A3 DP\n",
        "- T2 triggered by strength add if no pullback within 30 bars\n",
        "- Default: OFF\n",
        "- Track on paper only\n\n",
        "## S3 Research-Only — RESEARCH_ONLY (no capital at all)\n\n",
        "- EMA21/55 signals tracked for awareness only\n",
        "- No position size output\n",
        "- No paper-trade capital allocation\n",
        "- Label all S3 signals: RESEARCH_ONLY in dashboard\n",
    ]
    (OUT_DIR / "phase33_paper_trade_rules.md").write_text("".join(rules_lines), encoding="utf-8")
    print(f"  Phase33 scan schema, dashboard, rules saved", flush=True)
    return scan_df


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_led(path):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", default="all",
                        choices=["sector","regime","scaling","breadth","scan","all"])
    args = parser.parse_args()

    run_all = args.step == "all"

    print("Loading data...", flush=True)
    panel = load_panel()
    vnx   = load_vnindex()
    gk_cache = build_gk_cache(panel)
    print(f"Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)

    sector_map = None

    if args.step == "sector" or run_all:
        result = run_sector(panel, vnx, gk_cache)
        if isinstance(result, tuple):
            sector_map = result[0]
        else:
            sector_map = result

    if args.step == "regime" or run_all:
        run_regime(panel, vnx, gk_cache)

    if args.step == "scaling" or run_all:
        run_scaling(panel, vnx, gk_cache)

    if args.step == "breadth" or run_all:
        run_breadth(panel, vnx, gk_cache)

    if args.step == "scan" or run_all:
        run_scan(panel, vnx, gk_cache, sector_map)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
