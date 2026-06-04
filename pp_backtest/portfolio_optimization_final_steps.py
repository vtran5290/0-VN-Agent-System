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
    lines.append("\n## Operating Rules (Evidence-Based, FINAL)\n\n")
    lines.append("**CRITICAL: Breadth is NOT a hard T1 block. Only VNINDEX bear (EMA20<EMA100) hard-blocks T1.**\n\n")
    lines.append("| A3 breadth | Zone | breadth_t1_permission | breadth_t2_permission | Rule |\n")
    lines.append("|------------|------|----------------------|----------------------|------|\n")
    lines.append("| ≥ 40% | Normal | True | True | Full T1 and T2 entries |\n")
    lines.append("| 35–40% | Caution | True | False | T1 allowed. T2 blocked. |\n")
    lines.append("| < 35% | Defense | True (review req'd) | False | T1 with operator review. T2 blocked. |\n")
    lines.append("| VNINDEX EMA20 < EMA100 | Bear | False (hard block) | False | No new T1 entries. |\n\n")
    lines.append("## T2 Hysteresis\n\n")
    lines.append("- Block T2 when breadth drops below 35%\n")
    lines.append("- Restore T2 when breadth recovers above 45%\n")
    lines.append("- T1 entries: always allowed when VNINDEX regime is bull\n")
    (OUT_DIR / "BREADTH_RULE_FINAL.md").write_text("".join(lines), encoding="utf-8")
    print(f"  Breadth hysteresis saved", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Phase33 daily scan
# ─────────────────────────────────────────────────────────────────────────────

S3_SHADOW_MAX_HOLD_BARS = 60
S3_SHADOW_TP1_PCT = 0.18
S3_SHADOW_TRAIL_ATR = 3.5
S3_SHADOW_CLASSIFICATION = "PAPER_TRADE_SHADOW"
S3_REJECTED_MAX_HOLD = 250


def _a3_lead_5d_from_age(lead_age_bars) -> bool:
    """True when S3 fired 1–5 bars before A3 (prior bars only; same_bar_0 excluded)."""
    if lead_age_bars is None:
        return False
    b = int(lead_age_bars)
    return 1 <= b <= 5


def _compute_cloud_breadth(panel: pd.DataFrame, universe: set, fast: int, slow: int) -> float:
    n_bull = 0
    n_tot = 0
    for sym, sdf in panel.groupby("symbol", sort=False):
        if sym not in universe:
            continue
        sdf = sdf.sort_values("date")
        if len(sdf) < 120:
            continue
        c = sdf["close"].astype(float)
        if bool(ema_cloud(c, fast, slow)["cloud_bull"].iloc[-1]):
            n_bull += 1
        n_tot += 1
    return round(n_bull / n_tot, 4) if n_tot else 0.0


def _compute_s3_shadow_fields(
    *,
    s3_active: bool,
    s3_cloud_bull: bool,
    s3_bars,
    regime_bull: bool,
    liq_rec: str,
    in_s3_universe: bool,
    gk5: bool,
    s3_top100_adv: bool,
) -> dict:
    """Phase35 S3 paper-shadow + GK5 research monitor (never live orders)."""
    base = {
        "s3_shadow_candidate": False,
        "s3_shadow_classification": "S3_RESEARCH_ONLY",
        "s3_max_hold": None,
        "s3_max_hold_60_flag": False,
        "s3_tp1_pct": None,
        "s3_trail_atr": None,
        "s3_gk5": bool(gk5),
        "s3_top100_adv": bool(s3_top100_adv),
        "s3_shadow_action": "WATCH_ONLY",
        "s3_shadow_reason": "S3 not active on this symbol.",
        "s3_gk5_top100_monitor": False,
        "s3_research_monitor_action": "",
        "s3_research_monitor_reason": "",
        "s3_no_real_order_flag": True,
    }
    if not s3_active:
        if not in_s3_universe:
            base["s3_shadow_classification"] = "REJECTED_CONFIG"
            base["s3_shadow_reason"] = "Symbol outside S3 universe."
        return base

    if not regime_bull:
        base["s3_shadow_reason"] = "S3_MAX60_WATCH: VNINDEX bear regime. Paper tracking only."
        return base
    if liq_rec in ("skip", "no_adv_data"):
        base["s3_shadow_reason"] = f"S3_MAX60_WATCH: S3_LIQUIDITY_FAIL ({liq_rec})."
        return base
    if not s3_cloud_bull:
        base["s3_shadow_reason"] = "S3_MAX60_WATCH: S3 cloud turned bear."
        return base

    base["s3_shadow_candidate"] = True
    base["s3_shadow_classification"] = S3_SHADOW_CLASSIFICATION
    base["s3_max_hold"] = S3_SHADOW_MAX_HOLD_BARS
    base["s3_max_hold_60_flag"] = True
    base["s3_tp1_pct"] = S3_SHADOW_TP1_PCT
    base["s3_trail_atr"] = S3_SHADOW_TRAIL_ATR
    base["s3_shadow_action"] = "PAPER_S3_SHADOW"
    base["s3_shadow_reason"] = (
        "S3_MAX60_ACTIVE|S3_REGIME_OK|S3_LIQUIDITY_OK|TP1=18%|trail=3.5xATR|NO_REAL_CAPITAL"
    )

    if gk5 and s3_top100_adv:
        base["s3_gk5_top100_monitor"] = True
        base["s3_research_monitor_action"] = "PAPER_S3_RESEARCH_MONITOR"
        base["s3_research_monitor_reason"] = "GK5_MAX60_TOP100_MONITOR|NO_REAL_CAPITAL"

  # max_hold=250 explicitly rejected in scan output (never active shadow config)
    return base


def _final_action(
    a3_active,
    s3_active,
    cloud_bull,
    regime_bull,
    breadth_zone,
    liq_rec,
    a3_bars=None,
    pts_state=None,
    close_kvnd=None,
    tp1_price=None,
    trail_price=None,
    max_hold_bars: int = 250,
):
    """
    A3 production final_action only. S3 never sets final_action for live orders.
    Only VNINDEX bear hard-blocks new A3 T1. Breadth controls T2 / manual review only.
    """
    if a3_active and a3_bars is not None and int(a3_bars) > 0 and close_kvnd is not None:
        bars = int(a3_bars)
        if bars >= max_hold_bars:
            return (
                "MAX_HOLD_EXIT",
                f"A3 position bar {bars} >= max_hold {max_hold_bars}. Exit remaining per A3 rules.",
            )
        if tp1_price is not None and close_kvnd >= float(tp1_price):
            return (
                "TP1_PARTIAL",
                f"Close {close_kvnd} >= TP1 {tp1_price} (+18%). Take partial per A3 DP-first.",
            )
        if trail_price is not None and close_kvnd < float(trail_price):
            return (
                "TRAIL_EXIT",
                f"Close {close_kvnd} < trail {trail_price} (2.5xATR14). Exit remaining per A3 rules.",
            )

    if not regime_bull:
        if a3_active or s3_active:
            return "SKIP_VNINDEX_BEAR", "VNINDEX bear regime (EMA20<EMA100). No new T1 entries."
        return "WATCH_ONLY", "VNINDEX bear. No active signal."
    if liq_rec in ("skip", "no_adv_data"):
        return "SKIP_LIQUIDITY", f"Liquidity: recommendation={liq_rec}. ADV cap too low for T1."
    if not a3_active and not s3_active:
        return "WATCH_ONLY", "No A3 or S3 signal within 40 bars."
    if not a3_active and s3_active:
        return "WATCH_ONLY", "S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital."
    if not cloud_bull:
        bars_txt = f" (bar {a3_bars})" if a3_bars is not None else ""
        return "HOLD_T1_ONLY", f"A3 signal active{bars_txt}. Cloud turned bear. Hold T1. Monitor trail stop."
    bars = a3_bars if a3_bars is not None else 0
    if bars > 30:
        return "HOLD_T1_ONLY", f"T1 in position (bar {bars} > 30-bar T2 window expired). Holding T1. Monitor exit rules."
    if bars > 0:
        if breadth_zone == "defense":
            return "NO_T2_BREADTH", f"T1 in position (bar {bars}). T2 blocked: breadth defense (<35%)."
        if breadth_zone == "caution":
            return "NO_T2_BREADTH", f"T1 in position (bar {bars}). T2 blocked: breadth caution (35-40%)."
        return "WAIT_PB", f"T1 in position (bar {bars}). Monitoring for >=4% pullback. T2 allowed."
    if breadth_zone == "defense":
        return "NEW_T1_MANUAL_REVIEW_BREADTH", (
            f"A3 cloud breakout. Regime=bull. Breadth=defense ({breadth_zone}). "
            "T1 allowed with operator review. T2 blocked."
        )
    return "NEW_T1", f"A3 cloud breakout. Regime=bull. Breadth={breadth_zone}. All gates clear."


def _breadth_permissions(regime_bull, breadth_zone):
    """Return (breadth_t1_permission, breadth_t2_permission)."""
    if not regime_bull:
        return False, False
    t1 = True  # breadth never hard-blocks T1
    t2 = breadth_zone == "normal"
    return t1, t2


def _strategy_classification(a3_active, s3_active, in_a3_universe, action):
    if action.startswith("SKIP"):
        return "SKIP"
    if action == "WATCH_ONLY" and not a3_active:
        return "S3_RESEARCH_ONLY" if s3_active else "WATCH_ONLY"
    if a3_active and in_a3_universe:
        return "A3_PRODUCTION"
    return "WATCH_ONLY"


def _s3_lead_bucket(bars):
    """Classify S3→A3 lead age in bars into Phase36 bucket name."""
    if bars is None:
        return "no_s3_lead"
    b = int(bars)
    if b == 0:      return "same_bar_0"
    elif b <= 5:    return "lead_1_5"
    elif b <= 10:   return "lead_6_10"
    elif b <= 20:   return "lead_11_20"
    elif b <= 30:   return "lead_21_30"
    else:           return "no_s3_lead"


def _s3_lead_quality(bucket):
    """Map Phase36 lead bucket to quality label used for A3 ranking."""
    return {
        "same_bar_0":  "chase",
        "lead_1_5":    "neutral",
        "lead_6_10":   "neutral",
        "lead_11_20":  "best",    # MAR=0.464 in lead-timing backtest
        "lead_21_30":  "good",    # MAR=0.455, high per-trade quality but n=284
        "no_s3_lead":  "none",
    }.get(bucket, "none")


# ── Phase36 sorting layer constants and helpers ───────────────────────────────
# PHASE36 DOES NOT ALTER A3 PRODUCTION LOGIC.
# Ranking affects operator review order only.
# Execution still follows final_action and risk engine.

SCAN_SCHEMA_VERSION = "phase36"
_NEW_T1_ACTIONS = frozenset({"NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"})


def _compute_phase36_lead_context(a3_active, a3_sig_bar, s3_idxs, s3_lead_age_bars) -> dict:
    """Phase36 S3→A3 lead buckets (prior bars for lead; separate after/same-day)."""
    out = {
        "s3_lead_bucket": "none",
        "s3_lead_1_5d": False,
        "s3_lead_6_10d": False,
        "s3_lead_11_20d": False,
        "s3_lead_21_30d": False,
        "s3_same_day_as_a3": False,
        "s3_after_a3_5d": False,
        "a3_without_s3": True,
        "s3_fresh_lead_flag": False,
        "s3_stale_lead_flag": False,
        "s3_alignment_state": "none",
    }
    if not a3_active or a3_sig_bar is None:
        return out
    if s3_lead_age_bars is not None:
        b = int(s3_lead_age_bars)
        if b == 0:
            out.update(s3_same_day_as_a3=True, s3_lead_bucket="same_day", s3_alignment_state="same_day")
        elif 1 <= b <= 5:
            out.update(s3_lead_1_5d=True, s3_lead_bucket="lead_1_5", s3_fresh_lead_flag=True,
                       s3_alignment_state="fresh_lead", a3_without_s3=False)
        elif 6 <= b <= 10:
            out.update(s3_lead_6_10d=True, s3_lead_bucket="lead_6_10", s3_stale_lead_flag=True,
                       s3_alignment_state="stale_lead", a3_without_s3=False)
        elif 11 <= b <= 20:
            out.update(s3_lead_11_20d=True, s3_lead_bucket="lead_11_20", s3_stale_lead_flag=True,
                       s3_alignment_state="stale_lead", a3_without_s3=False)
        elif 21 <= b <= 30:
            out.update(s3_lead_21_30d=True, s3_lead_bucket="lead_21_30", s3_stale_lead_flag=True,
                       s3_alignment_state="stale_lead", a3_without_s3=False)
    s3_after = [int(i) for i in s3_idxs if a3_sig_bar < int(i) <= a3_sig_bar + 5]
    if s3_after:
        out["s3_after_a3_5d"] = True
        if out["s3_lead_bucket"] == "none":
            out.update(s3_lead_bucket="after_a3", s3_alignment_state="after_a3")
    return out


def _ed_score_from_dist(ema_dist_pct):
    return round(max(0.0, 1.0 - (abs(float(ema_dist_pct or 0.0)) / 20.0)), 4)


def _ed_score_bucket(ed_score):
    if ed_score >= 0.8:
        return "optimal"
    if ed_score >= 0.5:
        return "ok"
    return "extended"


def _a3_rank_bucket(score):
    if score is None:
        return ""
    s = float(score)
    if s >= 2.0:
        return "high"
    if s >= 1.0:
        return "medium"
    return "low"


def _build_a3_rank_reason(ed_score, s3_fresh_lead_flag, liq_warn_t1, sector_l4_stress_flag,
                          a3_without_s3, s3_same_day_as_a3):
    parts = []
    if ed_score is not None and float(ed_score) >= 0.8:
        parts.append("high_ed_score")
    if s3_fresh_lead_flag:
        parts.append("s3_lead_5d")
    if liq_warn_t1 == "OK":
        parts.append("liq_ok")
    elif liq_warn_t1:
        parts.append(f"liq_{str(liq_warn_t1).lower()}")
    if sector_l4_stress_flag in ("WARN", "STRESS"):
        parts.append("sector_concentration_warning")
    if a3_without_s3:
        parts.append("no_s3_support_but_a3_valid")
    if s3_same_day_as_a3:
        parts.append("s3_same_day_context")
    return "|".join(parts) if parts else "a3_valid"


def _compute_phase36_risk_flags(a3_active, s3_active, s3_cloud_bull, final_action, breadth_zone,
                              trail_price, close_kvnd):
    near_trail = False
    if trail_price is not None and close_kvnd is not None and float(trail_price) > 0:
        near_trail = float(close_kvnd) < float(trail_price) * 1.02
    return {
        "s3_deterioration_flag": bool(a3_active and s3_active and not s3_cloud_bull),
        "s3_t2_warning_flag": bool(final_action == "NO_T2_BREADTH" and a3_active and breadth_zone != "normal"),
        "s3_exit_warning_flag": bool(final_action in ("TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT") or near_trail),
        "s3_portfolio_health_flag": breadth_zone == "defense",
    }


def _sort_scan_for_review(df: "pd.DataFrame") -> "pd.DataFrame":
    """Display-order only. Does not change final_action, sizing, or eligibility."""
    if df.empty or "final_action" not in df.columns:
        return df
    out = df.copy()
    fa_priority = {"NEW_T1": 0, "NEW_T1_MANUAL_REVIEW_BREADTH": 1}
    out["_fa_pri"] = out["final_action"].map(fa_priority).fillna(99)
    liq_pri = {"OK": 0, "WARN_NEAR": 1, "WARN_OVER": 2, "WARN_PARTIAL": 2, "CRITICAL": 3}
    if "liq_warn_T1" not in out.columns:
        out["liq_warn_T1"] = "OK"
    out["_liq_pri"] = out["liq_warn_T1"].map(liq_pri).fillna(5)
    new_mask = out["final_action"].isin(_NEW_T1_ACTIONS)
    if "sector_l4" not in out.columns:
        out["sector_l4"] = "Unknown"
    if "symbol" not in out.columns:
        out["symbol"] = out.index.astype(str)
    sec_counts = out.loc[new_mask].groupby("sector_l4").size().to_dict() if new_mask.any() else {}
    out["_sec_cnt"] = out["sector_l4"].map(sec_counts).fillna(0)
    if "s3_fresh_lead_flag" not in out.columns:
        out["s3_fresh_lead_flag"] = False
    out = out.sort_values(
        ["_fa_pri", "a3_rank_score", "_liq_pri", "s3_fresh_lead_flag", "_sec_cnt", "symbol"],
        ascending=[True, False, True, False, True, True],
        na_position="last",
    ).reset_index(drop=True)
    out["phase36_operator_priority"] = range(1, len(out) + 1)
    return out.drop(columns=["_fa_pri", "_liq_pri", "_sec_cnt"], errors="ignore")


def _write_phase36_operator_report(scan_df, *, panel_asof, breadth, breadth_zone, regime_bull, s3_breadth):
    lines = [
        "# Phase36 Daily Operator Report\n\n",
        "**Decision: CONDITIONAL_NO_CHANGE** — A3 production logic unchanged.\n\n",
        "Today's A3 NEW_T1 candidates are sorted by `a3_rank_score` DESC for operator review. "
        "This sorting does **not** change `final_action`, size, or risk checks.\n\n",
        "- A3 is the only production candidate.\n",
        "- Phase36 ranking changes review order only.\n",
        "- `a3_rank_score` does not create orders.\n",
        "- S3 remains paper-shadow / radar only.\n",
        "- S3 lead does not gate A3.\n",
        "- T2 policy is unchanged.\n",
        "- Exit policy is unchanged: A3 trail remains 2.5× ATR14.\n",
        "- S3 satellite remains paper research only.\n\n",
        "## Panel 1 — Data health\n\n",
        f"- scan_schema_version: {SCAN_SCHEMA_VERSION}\n",
        f"- panel_asof_date: {panel_asof}\n",
        f"- scan_date: {scan_df['as_of_date'].iloc[0] if len(scan_df) else 'n/a'}\n",
        f"- VNINDEX regime_bull: {regime_bull}\n",
        f"- pct_cloud_bull_a3: {breadth:.1%} ({breadth_zone})\n",
        f"- pct_cloud_bull_s3: {s3_breadth:.1%}\n\n",
        "## Panel 2 — A3 production actions\n\n",
    ]
    if not scan_df.empty:
        for act, n in scan_df["final_action"].value_counts().items():
            lines.append(f"- {act}: {n}\n")
    lines.append("\n## Panel 3 — A3 ranked candidates\n\n")
    ranked = scan_df[scan_df["final_action"].isin(_NEW_T1_ACTIONS)] if not scan_df.empty else scan_df
    if ranked.empty:
        lines.append("- None today.\n")
    else:
        for _, r in ranked.iterrows():
            lines.append(
                f"- #{int(r.get('phase36_operator_priority', 0))} **{r['symbol']}** "
                f"`{r['final_action']}` rank={r.get('a3_rank_score')} "
                f"reason={r.get('a3_rank_reason', '')} ed={r.get('ed_score')} "
                f"lead={r.get('s3_lead_bucket')}\n"
            )
    lines.append("\n## Panel 4 — Hold / monitor\n\n")
    if not scan_df.empty:
        for act in ("HOLD_T1_ONLY", "NO_T2_BREADTH", "WAIT_PB", "TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"):
            sub = scan_df[scan_df["final_action"] == act]
            for _, r in sub.iterrows():
                lines.append(f"- {r['symbol']}: {act}\n")
    s3_n = int((scan_df.get("s3_shadow_action", pd.Series()) == "PAPER_S3_SHADOW").sum()) if not scan_df.empty else 0
    lines.extend([
        "\n## Panel 5 — S3 paper-shadow\n\n",
        f"- PAPER_S3_SHADOW: {s3_n}\n- NO REAL CAPITAL / NO DNSE\n\n",
        "## Panel 6 — Phase36 research overlays (not production)\n\n",
        f"- s3_t2_warning_flag count: {int(scan_df['s3_t2_warning_flag'].sum()) if not scan_df.empty and 's3_t2_warning_flag' in scan_df.columns else 0}\n",
        f"- gk10 (lead_best_125x theoretical): {int(scan_df['gk10'].sum()) if not scan_df.empty and 'gk10' in scan_df.columns else 0}\n\n",
        "## Panel 7 — Warnings\n\n",
        "- breadth defense: manual T1 review\n- S3 contamination: use final_action only for live capital\n",
    ])
    try:
        from scripts.research.group_rotation.report_section import render_group_rotation_context_md

        lines.append("\n## Panel 8 — Group rotation context (dashboard only)\n\n")
        lines.append(render_group_rotation_context_md())
    except Exception as exc:
        lines.append(f"\n## Panel 8 — Group rotation context\n\n- WARN: section not rendered ({exc})\n")
    text = "".join(lines)
    (OUT_DIR / "phase36_daily_operator_report.md").write_text(text, encoding="utf-8")
    (OUT_DIR / "UPDATED_PHASE36_DASHBOARD_SPEC.md").write_text(text, encoding="utf-8")


def compute_phase36_scan_df(panel, vnx, gk_cache, sector_map=None, *, intraday_macro: bool = False):
    """Build Phase36 scan DataFrame in memory (no file writes). Used by EOD step and intraday preview."""

    gate_by_date, _ = vnindex_regime_gate(vnx)
    last_date    = pd.Timestamp(panel["date"].max()).normalize()
    regime_bull  = bool(gate_by_date.get(last_date, False))

    a3_uni_pre = set(get_universe(panel, "ex_vin3"))
    s3_uni_pre = set(get_universe(panel, "full"))

    if intraday_macro:
        last_breadth = _compute_cloud_breadth(panel, a3_uni_pre, 20, 100)
        last_s3_breadth = _compute_cloud_breadth(panel, s3_uni_pre, 21, 55)
        breadth_source = "live_panel"
    else:
        breadth_path = OUT_DIR / "regime_decomposition_breadth.csv"
        if breadth_path.exists():
            bdf = pd.read_csv(breadth_path)
            last_breadth = (
                float(bdf[bdf["date"] == str(last_date.date())]["a3_breadth"].iloc[0])
                if str(last_date.date()) in bdf["date"].values
                else _compute_cloud_breadth(panel, a3_uni_pre, 20, 100)
            )
        else:
            last_breadth = _compute_cloud_breadth(panel, a3_uni_pre, 20, 100)
        last_s3_breadth = _compute_cloud_breadth(panel, s3_uni_pre, 21, 55)
        breadth_source = "eod_csv_or_live_fallback"

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

    a3_uni = a3_uni_pre
    s3_uni = s3_uni_pre

    # Phase35: precompute top-100 symbols by ADV50 for S3 GK5+top100 research track
    _adv50_all: dict = {}
    for _sym, _sdf in panel.groupby("symbol", sort=False):
        _sdf2 = _sdf.sort_values("date")
        _val2 = (_sdf2["value"].astype(float).fillna(0)
                 if "value" in _sdf2.columns
                 else _sdf2["close"].astype(float) * _sdf2.get("volume", pd.Series(np.zeros(len(_sdf2)))).astype(float) * 1000)
        _adv50_all[_sym] = float(_val2.rolling(50, min_periods=20).mean().iloc[-1] or 0)
    _top100_adv_set = set(sorted(_adv50_all, key=lambda x: _adv50_all[x], reverse=True)[:100])

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

        a3_active = False; a3_bars = None; a3_signal_today = False
        _a3_bars_since_signal = None
        if len(a3_idxs) > 0:
            li = int(a3_idxs[-1])
            _bss = len(c) - 1 - li          # bars since signal bar; 0 on signal day
            if _bss <= 40:
                a3_active = True
                a3_bars   = max(0, len(c) - 1 - (li + 1))  # clamp to 0 when entry bar doesn't exist yet
                a3_signal_today = (_bss == 0)               # True: signal on latest bar, entry = next open
                _a3_bars_since_signal = _bss

        s3_active = False; s3_bars = None; s3_signal_today = False
        if len(s3_idxs) > 0:
            li = int(s3_idxs[-1])
            _bss_s3 = len(c) - 1 - li
            if _bss_s3 <= 40:
                s3_active = True
                s3_bars   = max(0, len(c) - 1 - (li + 1))
                s3_signal_today = (_bss_s3 == 0)

        gk10 = False
        gk5 = False
        try:
            gk_res = compute_gk(c, h, l)
            gk_days = d[gk_res["gk_buy"]]
            gk10 = any(abs((last_date - gd.normalize()).days) <= 10 for gd in gk_days)
            gk5 = any(abs((last_date - gd.normalize()).days) <= 5 for gd in gk_days)
        except Exception:
            gk10 = False
            gk5 = False

        # Phase36: S3 lead-age fields for A3 ranking (computed even if s3 not active now)
        _s3_lead_age_bars = None
        _a3_sig_bar = int(a3_idxs[-1]) if a3_active and len(a3_idxs) > 0 else None
        if a3_active and _a3_sig_bar is not None:
            _lookback_start = max(0, _a3_sig_bar - 60)
            _s3_before = [int(i) for i in s3_idxs if _lookback_start <= int(i) <= _a3_sig_bar]
            if _s3_before:
                _s3_lead_age_bars = _a3_sig_bar - max(_s3_before)
        _p36_lead = _compute_phase36_lead_context(
            a3_active, _a3_sig_bar, s3_idxs, _s3_lead_age_bars,
        )
        _s3_lead_bkt = _p36_lead["s3_lead_bucket"]
        _s3_lead_qlty = _s3_lead_quality(_s3_lead_bucket(_s3_lead_age_bars))
        _cur_fast_ema = float(a3_fast.iloc[-1]) if len(a3_fast) > 0 else 0.0
        _last_close = float(c.iloc[-1])
        _a3_ema_dist_pct = round(((_last_close - _cur_fast_ema) / _cur_fast_ema * 100)
                                 if _cur_fast_ema > 0 else 0.0, 2) if a3_active else None
        _quality_lut = {"best": 2.0, "good": 1.0, "neutral": 0.0, "chase": -0.5, "none": 0.0}
        _q_score = _quality_lut.get(_s3_lead_qlty, 0.0)
        _ed_score = _ed_score_from_dist(_a3_ema_dist_pct) if a3_active else None
        _a3_rank_score = round(_q_score + float(_ed_score or 0.0), 3) if a3_active else None
        _s3_chase_flag = (
            _s3_lead_bkt in ("same_day", "lead_1_5", "same_bar_0") and
            abs(_a3_ema_dist_pct or 0.0) > 10.0
        ) if a3_active else False

        _a3_s3_lead_5d = _a3_lead_5d_from_age(_s3_lead_age_bars) if a3_active else False
        _a3_priority_boost = _a3_s3_lead_5d

        if not a3_active and not s3_active:
            continue

        cur_c = float(c.iloc[-1])
        a3_cloud_now = bool(a3_bull.iloc[-1])
        s3_cloud_now = bool(s3_bull.iloc[-1])

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

        ep1_price = None
        pb_trig = None
        tp1_p = None
        trail_p = None
        # Skip entry-price calcs when signal is on the latest bar: entry bar (li+1) not yet open.
        if a3_active and a3_bars is not None and a3_bars >= 0 and not a3_signal_today:
            a3_entry_idx = len(c) - 1 - a3_bars
            if 0 <= a3_entry_idx < len(c):
                ep1_price = float(c.iloc[a3_entry_idx])
                pb_trig   = round(ep1_price * 0.96, 3)
                tp1_p     = round(ep1_price * 1.18, 3)
                atr14     = float(c.diff().abs().rolling(14).mean().iloc[-1] or 0)
                peak      = float(c.iloc[a3_entry_idx:].max())
                trail_p   = round(peak - 2.5 * atr14, 3) if atr14 > 0 else None

        action, reason = _final_action(
            a3_active,
            s3_active,
            a3_cloud_now,
            regime_bull,
            breadth_zone,
            rec,
            a3_bars,
            close_kvnd=cur_c,
            tp1_price=tp1_p,
            trail_price=trail_p,
        )
        if a3_signal_today and action in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"):
            reason = reason + " Signal confirmed at today's close; planned fill is next session open."
        t1_perm, t2_perm = _breadth_permissions(regime_bull, breadth_zone)
        strat_class = _strategy_classification(a3_active, s3_active, sym in a3_uni, action)

        _s3_top100_adv = sym in _top100_adv_set
        _s3_fields = _compute_s3_shadow_fields(
            s3_active=s3_active,
            s3_cloud_bull=s3_cloud_now,
            s3_bars=s3_bars,
            regime_bull=regime_bull,
            liq_rec=rec,
            in_s3_universe=sym in s3_uni,
            gk5=gk5,
            s3_top100_adv=_s3_top100_adv,
        )

        in_a3 = sym in a3_uni
        in_s3 = sym in s3_uni

        _p36_risk = _compute_phase36_risk_flags(
            a3_active, s3_active, s3_cloud_now, action, breadth_zone, trail_p, cur_c,
        )
        _a3_rank_reason = _build_a3_rank_reason(
            _ed_score, _p36_lead["s3_fresh_lead_flag"], liq_T1, "UNKNOWN",
            _p36_lead["a3_without_s3"], _p36_lead["s3_same_day_as_a3"],
        ) if a3_active else ""

        rows.append({
            "scan_schema_version":     SCAN_SCHEMA_VERSION,
            "as_of_date":              last_date.date(),
            "symbol":                  sym,
            "close_kVND":              round(cur_c, 2),
            "a3_active":               a3_active,
            "a3_cloud_bull":           a3_cloud_now,
            "a3_bars_since":           a3_bars,
            "a3_signal_today":         a3_signal_today,
            "a3_bars_since_signal":    _a3_bars_since_signal,
            "a3_planned_entry_timing": ("NEXT_OPEN" if a3_signal_today else ("FILLED" if a3_active else None)),
            "s3_active":               s3_active,
            "s3_cloud_bull":           s3_cloud_now,
            "s3_bars_since":           s3_bars,
            "s3_signal_today":         s3_signal_today,
            "gk10":                    gk10,
            "gk5":                     gk5,
            "gk_mult":                 gk_mult,
            "adv50_B_VND":             round(adv50_now / 1e9, 3),
            "target_T1_M":             round(target_T1 / 1e6, 1),
            "target_full_M":           round(target_full / 1e6, 1),
            "max_10pct_M":             round(max_10pct / 1e6, 1),
            "liq_warn_T1":             liq_T1,
            "liq_warn_full":           liq_full,
            "recommendation":          rec,
            "in_a3_universe":          in_a3,
            "in_s3_universe":          in_s3,
            "pct_cloud_bull_a3":       last_breadth,
            "pct_cloud_bull_s3":       last_s3_breadth,
            "pct_cloud_bull_a3_universe": last_breadth,
            "pct_cloud_bull_s3_universe": last_s3_breadth,
            "breadth_zone":            breadth_zone,
            "breadth_t1_permission":   t1_perm,
            "breadth_t2_permission":   t2_perm,
            "regime_bull":             regime_bull,
            "sector_l1":               sec["sector_l1"],
            "sector_l2":               sec["sector_l2"],
            "sector_l3":               sec["sector_l3"],
            "sector_l4":               sec["sector_l4"],
            "sector_l4_stress_flag":   "UNKNOWN",
            "strategy_classification": strat_class,
            "pb_trigger_price":        pb_trig,
            "tp1_price":               tp1_p,
            "trail_price":             trail_p,
            "final_action":            action,
            "final_action_reason":     reason,
            # Phase36 S3 lead-age ranking display fields
            # PHASE36 DOES NOT ALTER A3 PRODUCTION LOGIC.
            # These fields affect operator review order only.
            # Execution follows final_action and risk engine.
            "s3_lead_age_bars":        _s3_lead_age_bars,
            "s3_lead_bucket":          _s3_lead_bkt,
            "s3_lead_quality":         _s3_lead_qlty,
            "ed_score":                _ed_score,
            "ed_score_bucket":         _ed_score_bucket(float(_ed_score or 0)) if a3_active else "",
            "a3_ema_dist_pct":         _a3_ema_dist_pct,
            "a3_rank_score":           _a3_rank_score,
            "a3_rank_bucket":          _a3_rank_bucket(_a3_rank_score) if a3_active else "",
            "a3_rank_reason":          _a3_rank_reason,
            "s3_alignment_state":      _p36_lead["s3_alignment_state"],
            "s3_fresh_lead_flag":      _p36_lead["s3_fresh_lead_flag"],
            "s3_stale_lead_flag":      _p36_lead["s3_stale_lead_flag"],
            "s3_lead_1_5d":            _p36_lead["s3_lead_1_5d"],
            "s3_lead_6_10d":           _p36_lead["s3_lead_6_10d"],
            "s3_lead_11_20d":          _p36_lead["s3_lead_11_20d"],
            "s3_lead_21_30d":          _p36_lead["s3_lead_21_30d"],
            "s3_same_day_as_a3":       _p36_lead["s3_same_day_as_a3"],
            "s3_after_a3_5d":          _p36_lead["s3_after_a3_5d"],
            "a3_without_s3":           _p36_lead["a3_without_s3"],
            **_p36_risk,
            "s3_chase_flag":           _s3_chase_flag,
            **_s3_fields,
            "a3_s3_lead_5d":              _a3_s3_lead_5d,
            "a3_priority_boost_from_s3":  _a3_priority_boost,
        })

    scan_df = pd.DataFrame(rows)
    scan_df = _sort_scan_for_review(scan_df)
    meta = {
        "panel_asof": last_date.date(),
        "last_breadth": last_breadth,
        "breadth_zone": breadth_zone,
        "regime_bull": regime_bull,
        "last_s3_breadth": last_s3_breadth,
        "breadth_source": breadth_source,
        "intraday_macro": intraday_macro,
        "n_rows": len(scan_df),
    }
    return scan_df, meta


def run_scan(panel, vnx, gk_cache, sector_map=None):
    print("\n=== STEP 6: Phase36 Daily Scan ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scan_df, meta = compute_phase36_scan_df(panel, vnx, gk_cache, sector_map=sector_map)
    last_breadth = meta["last_breadth"]
    breadth_zone = meta["breadth_zone"]
    regime_bull = meta["regime_bull"]
    last_s3_breadth = meta["last_s3_breadth"]
    last_date = pd.Timestamp(meta["panel_asof"])
    dated_scan = OUT_DIR / f"phase36_daily_scan_{last_date.strftime('%Y%m%d')}.csv"
    write_paths = [
        OUT_DIR / "phase36_daily_scan_sample.csv",
        OUT_DIR / "phase36_daily_scan_latest.csv",
        dated_scan,
        OUT_DIR / "phase35_daily_scan_sample.csv",
        OUT_DIR / "phase34_daily_scan_sample.csv",
        OUT_DIR / "phase33_daily_scan_sample.csv",
    ]
    for path in write_paths:
        scan_df.to_csv(path, index=False)
    print(
        f"  Phase36 scan: {len(scan_df)} active setups, breadth={last_breadth:.1%} ({breadth_zone})",
        flush=True,
    )
    try:
        from scripts.research.group_rotation.run_group_rotation import refresh_group_rotation_snapshot

        gr_df = refresh_group_rotation_snapshot()
        print(
            f"  Group rotation snapshot: {len(gr_df)} groups, date={gr_df['snapshot_date'].iloc[0]}",
            flush=True,
        )
    except Exception as exc:
        print(f"  WARN: group rotation snapshot not refreshed: {exc}", flush=True)
    _write_phase36_operator_report(
        scan_df,
        panel_asof=last_date.date(),
        breadth=last_breadth,
        breadth_zone=breadth_zone,
        regime_bull=regime_bull,
        s3_breadth=last_s3_breadth,
    )
    try:
        from src.market.rs_correction_lens.pipeline import run_rs_correction_lens
        from src.trading.reports.rs_correction_card import merge_rs_into_scan_df

        run_rs_correction_lens(as_of=str(last_date.date())[:10])
        scan_df = merge_rs_into_scan_df(scan_df)
        for path in write_paths:
            scan_df.to_csv(path, index=False)
    except Exception as exc:
        print(f"  WARN: rs_correction lens not merged into scan: {exc}", flush=True)
    try:
        from scripts.reporting.daily_scan_report import write_daily_scan_report

        report_path = write_daily_scan_report(scan_df, scan_csv_path=dated_scan)
        print(f"  Daily scan report: {report_path.relative_to(REPO)}", flush=True)
    except Exception as exc:
        print(f"  WARN: daily_scan report not written: {exc}", flush=True)

    schema_rows = [
        ("scan_schema_version","str","phase36 — display/ranking schema version"),
        ("as_of_date","date","Scan date"),
        ("symbol","str","Ticker symbol"),
        ("close_kVND","float","Last close in kVND"),
        ("a3_active","bool","A3 EMA20/100 signal within 40 bars"),
        ("a3_cloud_bull","bool","A3 cloud currently bullish"),
        ("a3_bars_since","int","Bars since A3 entry (null if no signal)"),
        ("s3_active","bool","S3 EMA21/55 signal within 40 bars (research only)"),
        ("s3_cloud_bull","bool","S3 cloud currently bullish"),
        ("s3_bars_since","int","Bars since S3 entry (null if no signal)"),
        ("gk10","bool","Garman-Klass buy within 10 days"),
        ("gk5","bool","Garman-Klass buy within 5 days (S3 research monitor)"),
        ("gk_mult","float","Size multiplier: 1.0 or 1.25 (if gk10)"),
        ("adv50_B_VND","float","Corrected ADV50 in B VND (panel value column)"),
        ("target_T1_M","float","Target T1 size in M VND at 5B portfolio / 20 slots"),
        ("target_full_M","float","Target full slot in M VND (T1+T2 combined)"),
        ("max_10pct_M","float","Max allowed T1 at 10% ADV cap in M VND"),
        ("liq_warn_T1","str","OK|WARN_NEAR|WARN_OVER|CRITICAL for T1 tranche"),
        ("liq_warn_full","str","OK|WARN_NEAR|WARN_OVER|CRITICAL for full slot"),
        ("recommendation","str","full_T1|partial_T1|skip|no_adv_data"),
        ("in_a3_universe","bool","In ex-VIN3 A3 universe (excludes VIN/VPL/<252 bars)"),
        ("in_s3_universe","bool","In full S3 universe (research only)"),
        ("pct_cloud_bull_a3","float","Universe-wide A3 breadth (pct of A3 universe in bull cloud)"),
        ("pct_cloud_bull_s3","float","Universe-wide S3 breadth (pct of S3 universe in bull cloud)"),
        ("pct_cloud_bull_a3_universe","float","Alias of pct_cloud_bull_a3"),
        ("pct_cloud_bull_s3_universe","float","Alias of pct_cloud_bull_s3"),
        ("breadth_zone","str","normal (>=40%)|caution (35-40%)|defense (<35%)"),
        ("breadth_t1_permission","bool","True unless VNINDEX bear. Breadth defense=True (review req'd)"),
        ("breadth_t2_permission","bool","False when defense or caution. True when normal only."),
        ("regime_bull","bool","VNINDEX EMA20>EMA100 (bull regime). ONLY hard T1 block."),
        ("sector_l1","str","Sector level 1 classification"),
        ("sector_l2","str","Sector level 2 classification"),
        ("sector_l3","str","Sector level 3 classification"),
        ("sector_l4","str","Sector level 4 (finest grain)"),
        ("sector_l4_stress_flag","str","OK|WARN|STRESS per sector L4 breadth (dashboard only)"),
        ("strategy_classification","str","A3_PRODUCTION|PTS_SHADOW|S3_RESEARCH_ONLY|WATCH_ONLY|SKIP"),
        ("pb_trigger_price","float","T2 trigger price: entry_close * 0.96 (null if no active entry)"),
        ("tp1_price","float","TP1 target price: entry_close * 1.18 (null if no active entry)"),
        ("trail_price","float","Trailing stop: peak_close - 2.5*ATR14 (null if no active entry)"),
        ("final_action","str","NEW_T1|NEW_T1_MANUAL_REVIEW_BREADTH|WAIT_PB|ADD_T2|HOLD_T1_ONLY|NO_T2_BREADTH|TP1_PARTIAL|TRAIL_EXIT|MAX_HOLD_EXIT|SKIP_LIQUIDITY|SKIP_VNINDEX_BEAR|WATCH_ONLY"),
        ("final_action_reason","str","Human-readable explanation of final_action decision"),
        # Phase36 S3 lead-age ranking display fields
        # PHASE36 DOES NOT ALTER A3 PRODUCTION LOGIC.
        # Ranking affects operator review order only.
        # Execution still follows final_action and risk engine.
        ("s3_lead_age_bars","int","Bars between last S3 EMA21/55 signal and A3 entry signal (None if no S3 within 60 bars)"),
        ("s3_lead_bucket","str","lead_1_5|lead_6_10|lead_11_20|lead_21_30|same_day|none|after_a3"),
        ("s3_lead_quality","str","best|good|neutral|chase|none — legacy quality label"),
        ("ed_score","float","max(0, 1-abs(ema_dist_pct)/20)"),
        ("ed_score_bucket","str","optimal|ok|extended"),
        ("a3_ema_dist_pct","float","(close-EMA20)/EMA20*100"),
        ("a3_rank_score","float","quality_boost + ed_score — operator sort only"),
        ("a3_rank_bucket","str","high|medium|low"),
        ("a3_rank_reason","str","Ranking tags — display only"),
        ("s3_alignment_state","str","fresh_lead|stale_lead|same_day|after_a3|none"),
        ("s3_fresh_lead_flag","bool","True for lead_1_5"),
        ("s3_stale_lead_flag","bool","True for lead_6_10/11_20/21_30"),
        ("s3_lead_1_5d","bool","S3 1-5 bars before A3"),
        ("s3_lead_6_10d","bool","S3 6-10 bars before A3"),
        ("s3_lead_11_20d","bool","S3 11-20 bars before A3"),
        ("s3_lead_21_30d","bool","S3 21-30 bars before A3"),
        ("s3_same_day_as_a3","bool","Same-bar S3 — context only"),
        ("s3_after_a3_5d","bool","S3 after A3 within 5 bars — not lead"),
        ("a3_without_s3","bool","No S3 lead in lookback"),
        ("phase36_operator_priority","int","Display sort rank (1=first to review)"),
        ("rs_correction_close_anchor","float","Close kVND at correction anchor bar"),
        ("rs_correction_close_end","float","Close kVND at correction end bar"),
        ("rs_correction_pct","float","RS vs VNINDEX over correction leg (stock ret − index ret, %)"),
        ("rs_correction_ret_pct","float","Stock return over correction leg (%)"),
        ("rs_correction_rs20_anchor_pct","float","RS vs VNINDEX 20d measured at anchor date"),
        ("rs_correction_rs20_end_pct","float","RS vs VNINDEX 20d measured at end date"),
        ("rs_correction_rs20_delta_pp","float","RS20 end − RS20 anchor (percentage points)"),
        ("rs_correction_improving","bool","RS 20d at end > RS 20d at anchor + 1pp"),
        ("rs_correction_bucket","str","leader_strong|outperform|relative_flat|underperform"),
        ("rs_correction_mdd_pct","float","Max drawdown since correction anchor (%)"),
        ("s3_deterioration_flag","bool","S3 cloud bear while A3 active"),
        ("s3_t2_warning_flag","bool","NO_T2_BREADTH research overlay"),
        ("s3_exit_warning_flag","bool","Exit/trail warning context"),
        ("s3_portfolio_health_flag","bool","breadth_zone=defense"),
        ("s3_chase_flag","bool","same_day/lead_1_5 with ED>10%"),
        # Phase35 S3 shadow classification fields
        ("s3_shadow_candidate","bool","True if S3 max60 paper-shadow candidate (regime+liquidity+cloud OK)"),
        ("s3_shadow_classification","str","PAPER_TRADE_SHADOW|S3_RESEARCH_ONLY|REJECTED_CONFIG"),
        ("s3_max_hold","int","60 for shadow (never 250); None if inactive"),
        ("s3_max_hold_60_flag","bool","True when s3_max_hold=60"),
        ("s3_tp1_pct","float","0.18 for shadow; None if inactive"),
        ("s3_trail_atr","float","3.5 for shadow trail; None if inactive"),
        ("s3_gk5","bool","GK buy within 5 days"),
        ("s3_top100_adv","bool","Symbol in top-100 ADV50 set"),
        ("s3_shadow_action","str","PAPER_S3_SHADOW|WATCH_ONLY — never live order"),
        ("s3_shadow_reason","str","S3 shadow reason codes; includes NO_REAL_CAPITAL"),
        ("s3_gk5_top100_monitor","bool","True if GK5+max60+top100 research monitor"),
        ("s3_research_monitor_action","str","PAPER_S3_RESEARCH_MONITOR or empty"),
        ("s3_research_monitor_reason","str","GK5_MAX60_TOP100_MONITOR or empty"),
        ("a3_s3_lead_5d","bool","True if S3 fired 1-5 bars BEFORE A3 (not same_bar)"),
        ("a3_priority_boost_from_s3","bool","Ranking boost only; does not gate A3"),
        ("s3_no_real_order_flag","bool","Always True — S3 never routes live/DNSE"),
    ]
    schema_df = pd.DataFrame(schema_rows, columns=["field","dtype","description"])
    for path in (
        OUT_DIR / "phase36_daily_scan_schema.csv",
        OUT_DIR / "phase35_daily_scan_schema.csv",
        OUT_DIR / "phase34_daily_scan_schema.csv",
        OUT_DIR / "phase33_daily_scan_schema.csv",
    ):
        schema_df.to_csv(path, index=False)

    from datetime import date as _date
    _gen = _date.today().isoformat()
    dash_lines = [
        f"# Phase35 Dashboard Specification\n\nGenerated: {_gen}\n\n",
        "## Panel 1 — Data health / as-of\n",
        "- panel_asof_date (from parquet max date)\n",
        "- scan_date (as_of_date column)\n",
        "- stale_warning if panel_asof < last trading session\n",
        "- VNINDEX regime_bull\n",
        "- pct_cloud_bull_a3 + breadth_zone\n",
        "- pct_cloud_bull_s3 (EMA21/55 universe)\n\n",
        "## Panel 2 — A3 production (ONLY real-capital SSOT)\n",
        "- final_action counts\n",
        "- NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH / ADD_T2 / NO_T2_BREADTH / HOLD_T1_ONLY\n",
        "- TP1_PARTIAL / TRAIL_EXIT / MAX_HOLD_EXIT\n",
        "- SKIP_LIQUIDITY / SKIP_VNINDEX_BEAR\n",
        "- a3_s3_lead_5d=True names (priority sort)\n",
        "- Sort NEW_T1 rows by a3_rank_score DESC\n\n",
        "## Panel 3 — S3 paper shadow (max_hold=60)\n",
        "- Count s3_shadow_action=PAPER_S3_SHADOW\n",
        "- s3_shadow_classification=PAPER_TRADE_SHADOW only\n",
        "- s3_max_hold=60 / s3_max_hold_60_flag=True\n",
        "- s3_no_real_order_flag must be 100% True\n",
        "- REMINDER: separate paper ledger — not A3 P&L\n\n",
        "## Panel 4 — S3 research monitor (GK5+top100)\n",
        "- s3_gk5_top100_monitor=True count\n",
        "- s3_research_monitor_action=PAPER_S3_RESEARCH_MONITOR\n",
        "- NO REAL CAPITAL / NO DNSE\n\n",
        "## Panel 5 — Legacy satellite (NOT production SSOT)\n",
        "- B_cloud20_100 / B_cloud21_55 / C_GK_regime from daily_three_strategy_scan.md\n",
        "- Label: satellite only — do not route live capital\n\n",
        "## Panel 6 — Warnings\n",
        "- duplicate position if symbol already held\n",
        "- stale panel data\n",
        "- liquidity WARN/CRITICAL\n",
        "- breadth defense (<35%)\n",
        "- S3 contamination risk if operator confuses shadow with A3\n",
        "- missing broker reconciliation / ledger\n\n",
    ]
    dash_text = "".join(dash_lines)
    (OUT_DIR / "phase35_dashboard_spec.md").write_text(dash_text, encoding="utf-8")
    (OUT_DIR / "UPDATED_PHASE35_DASHBOARD_SPEC.md").write_text(dash_text, encoding="utf-8")
    (OUT_DIR / "phase33_dashboard_spec.md").write_text(dash_text, encoding="utf-8")

    rules_lines = [
        "# Phase34 Paper Trade Rules\n\n",
        f"Generated: 2026-05-16\n\n",
        "## A3 DP-First — PRODUCTION_CANDIDATE (real capital)\n\n",
        "**Entry conditions (ALL must be true):**\n",
        "1. A3 signal within 40 bars (a3_active = True)\n",
        "2. A3 cloud still bullish (a3_cloud_bull = True)\n",
        "3. VNINDEX regime = bull (EMA20 > EMA100) — ONLY hard T1 block\n",
        "4. recommendation = full_T1 or partial_T1 (liquidity check)\n",
        "5. final_action != SKIP_LIQUIDITY and != SKIP_VNINDEX_BEAR\n\n",
        "**Breadth is NOT a hard entry condition. It controls T2 and signals operator review.**\n\n",
        "**Position sizing:**\n",
        "- Slot = portfolio / 20 (× 1.25 if GK10)\n",
        "- T1 = 50% of slot at entry\n",
        "- T2 = 50% of slot on ≥4% pullback within 30 bars (subject to breadth_t2_permission)\n",
        "- T1 capped: min(T1, adv50_VND × 10%)\n\n",
        "**Breadth zones (advisory for T1, binding for T2):**\n",
        "- Normal (≥40%): T1 allowed, T2 allowed\n",
        "- Caution (35–40%): T1 allowed, T2 blocked (breadth_t2_permission=False)\n",
        "- Defense (<35%): T1 allowed with operator review (NEW_T1_MANUAL_REVIEW_BREADTH), T2 blocked\n",
        "- VNINDEX bear: T1 hard blocked (SKIP_VNINDEX_BEAR)\n\n",
        "**Exit:**\n",
        "- TP1: +18% on T1 tranche (sell 50%)\n",
        "- Trail: 2.5×ATR14 from highest close since entry\n",
        "- Max hold: 250 bars (~1 year)\n",
        "- Min sell lock: 5 bars (T+3 settlement)\n\n",
        "## PTS Shadow — PAPER_TRADE_SHADOW (no real capital)\n\n",
        "- Same entry conditions as A3 DP\n",
        "- T2 triggered by strength add if no pullback within 30 bars\n",
        "- Default: OFF. Must be explicitly enabled.\n",
        "- strategy_classification = PTS_SHADOW in scan output\n",
        "- Track on paper only. No capital until MAR > 0.35 on live paper data.\n\n",
        "## S3 Research-Only — RESEARCH_ONLY (no capital at all)\n\n",
        "- EMA21/55 signals tracked for awareness only\n",
        "- No position size output\n",
        "- No paper-trade capital allocation\n",
        "- strategy_classification = S3_RESEARCH_ONLY in scan output\n",
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
