"""Full-History Institutional Accumulation Backtest — Master Runner.

Phases:
  0. Data coverage audit
  1. Universe design (top-N ADV50)
  2. Panel scoring (using ta_ohlcv_panel.parquet as primary source)
  3. Forward outcomes (T+1 entry, no lookahead)
  4. Event-level validation (P1/P2-style)
  5. Portfolio simulation (multiple universes)
  6. Compare vs P3.2 modern (2024+)
  7. HTML report
  8. Review pack

Critical safety constraints:
  - No A3/S3/OMS/final_action/DNSE/live trading/sizing/Phase36 changed.
  - All outputs: RESEARCH_ONLY_NOT_PRODUCTION

Usage:
  .venv/Scripts/python.exe scripts/research/institutional_accumulation_backtest/run_full_history_backtest.py
  .venv/Scripts/python.exe scripts/research/institutional_accumulation_backtest/run_full_history_backtest.py --skip-panel
  .venv/Scripts/python.exe scripts/research/institutional_accumulation_backtest/run_full_history_backtest.py --phases 0,1
"""
from __future__ import annotations

import argparse
import sys
import uuid
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

# Repo root (3 levels up from this script)
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

FH_OUT_DIR = REPO / "data" / "research" / "institutional_accumulation_full_history"
HTML_OUT = REPO / "reports" / "research" / "institutional_accumulation_full_history" / "full_history_accumulation_validation.html"
REVIEW_DIR = REPO / "outputs" / "review_packages"

# Cadence-specific paths set at runtime in main() based on --cadence arg
PANEL_PARTS_DIR = FH_OUT_DIR / "panel_scores_parts"
PANEL_PATH = FH_OUT_DIR / "full_history_panel_scores.parquet"
OUTCOMES_PATH = FH_OUT_DIR / "full_history_forward_outcomes.parquet"

# Chunk size for panel building (tickers per worker job)
DEFAULT_CHUNK_SIZE = 100


def _cadence_paths(cadence: str) -> tuple:
    """Return (PANEL_PARTS_DIR, PANEL_PATH, OUTCOMES_PATH) for the given cadence."""
    if cadence == "monthly":
        parts_dir = FH_OUT_DIR / "panel_scores_parts_monthly"
        panel_path = FH_OUT_DIR / "full_history_panel_scores_monthly.parquet"
        outcomes_path = FH_OUT_DIR / "full_history_forward_outcomes_monthly.parquet"
    else:
        parts_dir = FH_OUT_DIR / "panel_scores_parts"
        panel_path = FH_OUT_DIR / "full_history_panel_scores.parquet"
        outcomes_path = FH_OUT_DIR / "full_history_forward_outcomes.parquet"
    return parts_dir, panel_path, outcomes_path


def _build_panel_worker_job(payload: dict) -> dict:
    """Process-pool worker: build panel chunk from parquet loader."""
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    import sys
    sys.path.insert(0, payload["repo_root"])

    from pathlib import Path
    import pandas as pd

    from src.research.institutional_accumulation_backtest.fh_data_loader import (
        ParquetSymbolLoader, load_fh_benchmark,
    )
    from src.research.institutional_accumulation_backtest.data_loader import load_sector_map, resolve_sources
    from src.research.institutional_accumulation_backtest.panel import PanelConfig
    from src.research.institutional_accumulation_backtest.fh_panel_fast import build_panel_fast
    from src.research.institutional_accumulation_backtest.regimes import build_benchmark_regimes
    from src.research.institutional_accumulation_backtest.schema import ContextMode, VinPolicy

    loader = ParquetSymbolLoader.build(verbose=False)
    benchmark = load_fh_benchmark()
    start, end = payload["start"], payload["end"]
    # Use FULL benchmark (not sliced) so pre-computed RS covers entire history
    benchmark_full = benchmark.copy()
    benchmark_full["date"] = pd.to_datetime(benchmark_full["date"])
    benchmark_slice = benchmark_full[
        (benchmark_full["date"] >= pd.Timestamp(start))
        & (benchmark_full["date"] <= pd.Timestamp(end))
    ]
    sources = resolve_sources()
    sectors = load_sector_map(sources.sector_map_path)
    regimes = build_benchmark_regimes(benchmark_slice)
    cfg = PanelConfig(
        start=start,
        end=end,
        cadence=payload.get("cadence", "weekly"),
        context_mode=ContextMode.from_cli("ohlcv_only"),
        min_history_days=120,
        min_adv20_vnd=500_000_000.0,   # relaxed for full history (0.5B)
        min_adv50_vnd=250_000_000.0,   # relaxed for full history (0.25B)
    )
    # Use fast panel builder (pre-computes add_indicators once per symbol ~30x speedup)
    panel_chunk, notes = build_panel_fast(
        cfg,
        benchmark=benchmark_full,   # full benchmark for RS pre-computation
        benchmark_slice=benchmark_slice,
        symbols=payload["symbols"],
        stocks_dir=sources.stocks_dir,
        sector_map=sectors,
        regimes=regimes,
        vin_policy=VinPolicy(),
        symbol_loader=loader,
    )
    part = Path(payload["part_path"])
    part.parent.mkdir(parents=True, exist_ok=True)
    panel_chunk.to_parquet(part, index=False)
    return {
        "part_path": str(part),
        "symbols": payload["symbols"],
        "rows": len(panel_chunk),
        "blocked_columns": notes.get("blocked_columns", []),
    }


def phase0_coverage(loader, verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.research.institutional_accumulation_backtest.fh_coverage import run_coverage_audit
    return run_coverage_audit(loader, FH_OUT_DIR)


def phase1_universe(loader, verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.research.institutional_accumulation_backtest.fh_universe import build_universe_coverage
    return build_universe_coverage(loader, FH_OUT_DIR, verbose=verbose)


def phase2_panel(
    loader,
    symbols: list[str],
    start: str,
    end: str,
    workers: int = 1,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    resume: bool = True,
    cadence: str = "weekly",
) -> pd.DataFrame:
    """Build full-history panel scores from parquet loader.

    Args:
        cadence: 'weekly' (default) or 'monthly'. Monthly is ~4x faster and
                 uses a separate panel_scores_parts_monthly/ directory.
    """
    parts_dir, panel_path, _ = _cadence_paths(cadence)
    parts_dir.mkdir(parents=True, exist_ok=True)

    # Build chunk jobs
    chunk_jobs = []
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i: i + chunk_size]
        part = parts_dir / f"fh_panel_part_{i:05d}_{i+len(chunk)-1:05d}.parquet"
        if resume and part.is_file():
            print(f"[Phase 2] Resume: skip chunk {i} ({part.name})")
            continue
        chunk_jobs.append({"symbols": chunk, "part_path": str(part)})

    if chunk_jobs:
        payloads = [
            {
                **job,
                "start": start,
                "end": end,
                "cadence": cadence,
                "repo_root": str(REPO),
            }
            for job in chunk_jobs
        ]
        print(f"[Phase 2] Building panel: {len(payloads)} chunks, {workers} worker(s)")
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_build_panel_worker_job, p): p for p in payloads}
                for fut in as_completed(futures):
                    r = fut.result()
                    print(f"[Phase 2] chunk done: {len(r['symbols'])} tickers, {r['rows']} rows")
        else:
            for payload in payloads:
                r = _build_panel_worker_job(payload)
                print(f"[Phase 2] chunk done: {len(r['symbols'])} tickers, {r['rows']} rows")

    # Consolidate
    parts = sorted(parts_dir.glob("fh_panel_part_*.parquet"))
    if not parts:
        print("[Phase 2] WARNING: no panel parts found")
        return pd.DataFrame()

    panel = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    panel = panel.drop_duplicates(subset=["scan_date", "ticker"], keep="last")
    panel.to_parquet(panel_path, index=False)
    print(f"[Phase 2] Panel: {panel_path} rows={len(panel):,}")
    return panel


def phase3_outcomes(panel: pd.DataFrame, loader, outcomes_path=None) -> pd.DataFrame:
    from src.research.institutional_accumulation_backtest.fh_outcomes import (
        compute_fh_forward_outcomes, save_fh_outcomes,
    )
    outcomes = compute_fh_forward_outcomes(panel, loader, verbose=True)
    outcomes["research_only_flag"] = RESEARCH_ONLY_FLAG
    save_fh_outcomes(outcomes, FH_OUT_DIR, out_path=outcomes_path)
    return outcomes


def phase11_membership(panel_path: Path) -> pd.DataFrame:
    """Phase 11: Build ticker-level universe membership from panel parquet (~30s)."""
    from src.research.institutional_accumulation_backtest.fh_universe_membership import (
        build_membership_from_panel,
    )
    return build_membership_from_panel(panel_path, FH_OUT_DIR, verbose=True)


def phase12_adv_audit(loader, panel: pd.DataFrame) -> None:
    """Phase 12: Audit ADV unit inflation in 2017-2018 parquet data (~60s)."""
    from src.research.institutional_accumulation_backtest.fh_universe_membership import (
        run_adv_unit_audit,
    )
    run_adv_unit_audit(loader, panel, FH_OUT_DIR, verbose=True)


def phase13_effectiveness(membership_wide: pd.DataFrame, portfolio_results: dict) -> None:
    """Phase 13: Universe filter effectiveness audit."""
    from src.research.institutional_accumulation_backtest.fh_universe_membership import (
        run_universe_filter_effectiveness,
    )
    pm = portfolio_results.get("portfolio_metrics", pd.DataFrame())
    run_universe_filter_effectiveness(membership_wide, pm, FH_OUT_DIR, verbose=True)


def phase4_validation(
    outcomes: pd.DataFrame,
    universe_weekly: pd.DataFrame,
    membership_wide: pd.DataFrame | None = None,
) -> dict:
    from src.research.institutional_accumulation_backtest.fh_validation import run_full_history_validation
    return run_full_history_validation(
        outcomes, universe_weekly, FH_OUT_DIR, membership_wide=membership_wide, verbose=True
    )


def phase5_portfolio(
    outcomes: pd.DataFrame,
    universe_weekly: pd.DataFrame,
    loader,
    membership_wide: pd.DataFrame | None = None,
) -> dict:
    from src.research.institutional_accumulation_backtest.fh_portfolio import run_fh_portfolio
    return run_fh_portfolio(
        outcomes, universe_weekly, loader, FH_OUT_DIR,
        membership_wide=membership_wide, verbose=True
    )


def phase6_compare(portfolio_results: dict, validation_results: dict) -> tuple[pd.DataFrame, dict]:
    from src.research.institutional_accumulation_backtest.fh_compare import (
        build_comparison, build_comparison_answers,
    )
    pm = portfolio_results.get("portfolio_metrics", pd.DataFrame())
    compare_df = build_comparison(pm, FH_OUT_DIR)
    answers = build_comparison_answers(compare_df, validation_results)
    return compare_df, answers


def phase7_html(
    validation_results: dict,
    portfolio_results: dict,
    coverage_dfs: tuple,
    universe_dfs: tuple,
    compare_df: pd.DataFrame,
    answers: dict,
    run_date: str,
) -> None:
    from src.research.institutional_accumulation_backtest.fh_report import write_fh_html_report

    cov_audit, cov_summary = coverage_dfs
    u_weekly, u_yearly = universe_dfs

    # Load new v0.2 audit data if available
    adv_unit_audit = None
    adv_unit_summary = None
    membership_effectiveness = None

    adv_audit_path = FH_OUT_DIR / "adv_unit_audit.csv"
    if adv_audit_path.is_file():
        adv_unit_audit = pd.read_csv(adv_audit_path)

    adv_summary_path = FH_OUT_DIR / "adv_unit_summary.csv"
    if adv_summary_path.is_file():
        adv_unit_summary = pd.read_csv(adv_summary_path)

    effectiveness_path = FH_OUT_DIR / "universe_filter_effectiveness.csv"
    if effectiveness_path.is_file():
        membership_effectiveness = pd.read_csv(effectiveness_path)

    write_fh_html_report(
        out_path=HTML_OUT,
        coverage_summary=cov_summary,
        coverage_audit=cov_audit,
        universe_yearly=u_yearly,
        universe_weekly=u_weekly,
        score_decile=validation_results.get("score_decile", pd.DataFrame()),
        component_validation=validation_results.get("component", pd.DataFrame()),
        distribution_flag=validation_results.get("distribution_flag", pd.DataFrame()),
        top_decile_exhaustion=validation_results.get("top_decile_exhaustion", pd.DataFrame()),
        variant_event=validation_results.get("variant_event", pd.DataFrame()),
        portfolio_metrics=portfolio_results.get("portfolio_metrics", pd.DataFrame()),
        yearly_returns=portfolio_results.get("yearly_returns", pd.DataFrame()),
        compare_df=compare_df,
        comparison_answers=answers,
        run_date=run_date,
        adv_unit_audit=adv_unit_audit,
        adv_unit_summary=adv_unit_summary,
        membership_effectiveness=membership_effectiveness,
    )


def phase8_review_pack(run_date: str, validation_results: dict, portfolio_results: dict) -> Path:
    """Build Phase 8 review pack ZIP."""
    tag = f"institutional_accumulation_full_history_2012_2026_review_pack_{run_date.replace('-', '')}"
    zip_path = REVIEW_DIR / f"{tag}.zip"
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # Guard: check outputs are non-trivial
    csv_files = list(FH_OUT_DIR.glob("*.csv"))
    total_rows = 0
    for f in csv_files:
        try:
            total_rows += len(pd.read_csv(f))
        except Exception:
            pass

    pm = portfolio_results.get("portfolio_metrics", pd.DataFrame())
    if total_rows < 10000:
        print(f"[Phase 8] WARNING: total_rows={total_rows} < 10000 — fixture-sized output guard")

    # Build open questions
    open_questions = [
        "Does full-history top-200 universe provide sufficient evidence to change the dashboard universe filter?",
        "Should ex-VIN be the primary benchmark given VIN 2025-2026 distortion?",
        "Are 2019-2021 years (230-251 tickers) sufficient for regime-level conclusions?",
        "Should distribution-risk filter be a hard exclude or soft penalty?",
        "What additional data sources are needed for true 2012-2016 stock backtest?",
    ]

    # Impl report text
    impl_lines = [
        "# Full-History IA Backtest — Implementation Report",
        f"\nRun date: {run_date}",
        f"\nResearch-only. RESEARCH_ONLY_NOT_PRODUCTION.",
        "\nNo A3/S3/OMS/final_action/DNSE/live trading/sizing/Phase36 changed.",
        "\n## Data Coverage",
        "Panel: ta_ohlcv_panel.parquet (2017-05-18 → 2026-05-27, 1564 symbols)",
        "Benchmark: minervini_backtest/data/raw/VNINDEX.csv (2012-01-03 → 2026-05-28)",
        "Pre-2017: BLOCKED_BY_DATA_COVERAGE for stock universe",
        "\n## Universe Design",
        "Primary: U1_TOP_200_ADV50, U1_TOP_300_ADV50, U2_TOP_30PCT_ADV50, U3_ADV50_5B",
        "Modern reference: U0_ADV50_20B (2024+ only)",
        "Fixed 20B pre-2024: REJECTED as full-history methodology",
        "\n## Portfolio Results",
        pm.to_csv(index=False) if not pm.empty else "(no portfolio results)",
        "\n## Open Questions for ChatGPT",
        "\n".join(f"- {q}" for q in open_questions),
    ]

    source_files = [
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_data_loader.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_coverage.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_universe.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_universe_membership.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_outcomes.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_validation.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_portfolio.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_compare.py",
        REPO / "src" / "research" / "institutional_accumulation_backtest" / "fh_report.py",
        REPO / "tests" / "test_institutional_accumulation_full_history_validation.py",
        REPO / "tests" / "test_institutional_accumulation_full_history_universe_membership.py",
        Path(__file__),
    ]

    # Source inventory
    inventory_rows = []
    for p in source_files:
        inventory_rows.append({"file": str(p.relative_to(REPO)), "exists": p.is_file(), "size_bytes": p.stat().st_size if p.is_file() else 0})
    inventory_df = pd.DataFrame(inventory_rows)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Implementation report
        zf.writestr("implementation_report.md", "\n".join(impl_lines))
        # Open questions
        zf.writestr("open_questions_for_chatgpt.md", "\n".join(f"- {q}" for q in open_questions))
        # Source inventory
        zf.writestr("source_file_inventory.csv", inventory_df.to_csv(index=False))
        # All CSV outputs
        for csv in FH_OUT_DIR.glob("*.csv"):
            zf.write(csv, f"data/{csv.name}")
        # HTML report
        if HTML_OUT.is_file():
            zf.write(HTML_OUT, f"reports/{HTML_OUT.name}")
        # Source snapshots
        for p in source_files:
            if p.is_file():
                arc = f"source_snapshots/{p.relative_to(REPO)}".replace("\\", "/")
                zf.write(p, arc)

    print(f"[Phase 8] Review pack: {zip_path}")
    return zip_path


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    ap = argparse.ArgumentParser(description="Full-History IA Backtest")
    ap.add_argument("--start", default="2017-01-01",
                    help="Backtest start (parquet min is 2017-05-18; earlier dates produce BLOCKED label)")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    ap.add_argument("--cadence", default="weekly", choices=["weekly", "monthly"],
                    help="Panel scan cadence. 'monthly' is ~4x faster (uses separate output directory)")
    ap.add_argument(
        "--phases", default="0,1,2,3,4,5,6,7,8",
        help=(
            "Comma-separated list of phases to run. "
            "Integers 0-8 = original phases. "
            "11 = ticker-level membership (Phase 11), "
            "12 = ADV unit audit (Phase 12), "
            "13 = universe filter effectiveness (Phase 13). "
            "Example: --phases 11,12,4,5,6,7,8,13"
        ),
    )
    ap.add_argument("--skip-panel", action="store_true",
                    help="Skip panel rebuild (Phase 2) — use existing PANEL_PATH")
    ap.add_argument("--skip-outcomes", action="store_true",
                    help="Skip outcomes rebuild (Phase 3) — use existing OUTCOMES_PATH")
    ap.add_argument("--resume", action="store_true", default=True,
                    help="Skip existing panel parts (default True)")
    args = ap.parse_args()
    cadence = args.cadence
    _, cadence_panel_path, cadence_outcomes_path = _cadence_paths(cadence)

    run_phases = set(int(x.strip()) for x in args.phases.split(","))
    run_date = str(date.today())

    print(f"\n{'='*60}")
    print(f"FULL-HISTORY IA BACKTEST — {run_date}")
    print(f"RESEARCH_ONLY_NOT_PRODUCTION")
    print(f"Cadence: {cadence}  |  Range: {args.start} to {args.end}")
    print(f"Phases: {sorted(run_phases)}")
    print(f"{'='*60}\n")

    # Load data loader (used in multiple phases)
    from src.research.institutional_accumulation_backtest.fh_data_loader import (
        ParquetSymbolLoader, discover_fh_symbols,
    )
    print("[Init] Loading parquet + aux data sources …")
    loader = ParquetSymbolLoader.build(verbose=True)
    symbols = discover_fh_symbols(loader)
    print(f"[Init] {len(symbols)} symbols available")

    cov_audit = cov_summary = pd.DataFrame()
    u_weekly = u_yearly = pd.DataFrame()
    panel = pd.DataFrame()
    outcomes = pd.DataFrame()
    membership_wide: pd.DataFrame | None = None
    validation_results: dict = {}
    portfolio_results: dict = {}
    compare_df = pd.DataFrame()
    answers: dict = {}

    # Phase 0: Coverage audit
    if 0 in run_phases:
        cov_audit, cov_summary = phase0_coverage(loader)

    # Phase 1: Universe design
    if 1 in run_phases:
        u_weekly, u_yearly = phase1_universe(loader)
    elif (FH_OUT_DIR / "universe_coverage_by_week.csv").is_file():
        u_weekly = pd.read_csv(FH_OUT_DIR / "universe_coverage_by_week.csv")
        u_yearly = pd.read_csv(FH_OUT_DIR / "universe_coverage_by_year.csv")
        print("[Phase 1] Loaded cached universe coverage")

    # Phase 2: Panel building
    if 2 in run_phases and not args.skip_panel:
        panel = phase2_panel(
            loader, symbols, args.start, args.end,
            workers=args.workers, chunk_size=args.chunk_size, resume=args.resume,
            cadence=cadence,
        )
    elif cadence_panel_path.is_file():
        panel = pd.read_parquet(cadence_panel_path)
        print(f"[Phase 2] Loaded existing panel ({cadence}): {len(panel):,} rows")
    else:
        print(f"[Phase 2] No panel available for cadence={cadence} — skipping dependent phases")

    # Phase 3: Forward outcomes
    if 3 in run_phases and not panel.empty and not args.skip_outcomes:
        outcomes = phase3_outcomes(panel, loader, outcomes_path=cadence_outcomes_path)
    elif cadence_outcomes_path.is_file():
        outcomes = pd.read_parquet(cadence_outcomes_path)
        print(f"[Phase 3] Loaded existing outcomes ({cadence}): {len(outcomes):,} rows")

    # Phase 11: Ticker-level universe membership (must run before Phase 4/5 for fix)
    if 11 in run_phases and cadence_panel_path.is_file():
        membership_wide = phase11_membership(cadence_panel_path)
    elif (FH_OUT_DIR / "universe_membership_wide.parquet").is_file():
        membership_wide = pd.read_parquet(FH_OUT_DIR / "universe_membership_wide.parquet")
        membership_wide["scan_date"] = pd.to_datetime(membership_wide["scan_date"]).dt.normalize()
        print("[Phase 11] Loaded cached ticker-level membership")

    # Phase 12: ADV unit audit
    if 12 in run_phases and not panel.empty:
        phase12_adv_audit(loader, panel)

    # Phase 4: Event-level validation
    if 4 in run_phases and not outcomes.empty and not u_weekly.empty:
        validation_results = phase4_validation(outcomes, u_weekly, membership_wide=membership_wide)

    # Phase 5: Portfolio simulation
    if 5 in run_phases and not outcomes.empty and not u_weekly.empty:
        portfolio_results = phase5_portfolio(outcomes, u_weekly, loader, membership_wide=membership_wide)

    # Phase 6: Comparison
    if 6 in run_phases:
        compare_df, answers = phase6_compare(portfolio_results, validation_results)

    # Phase 13: Universe filter effectiveness audit (requires portfolio_results)
    if 13 in run_phases and membership_wide is not None:
        phase13_effectiveness(membership_wide, portfolio_results)

    # Phase 7: HTML report
    if 7 in run_phases:
        phase7_html(
            validation_results, portfolio_results,
            (cov_audit, cov_summary), (u_weekly, u_yearly),
            compare_df, answers, run_date,
        )

    # Phase 8: Review pack
    if 8 in run_phases:
        phase8_review_pack(run_date, validation_results, portfolio_results)

    # Final summary
    print(f"\n{'='*60}")
    print("FULL-HISTORY IA BACKTEST COMPLETE")
    print(f"RESEARCH_ONLY_NOT_PRODUCTION")
    print(f"Panel rows: {len(panel):,}")
    print(f"Outcomes rows: {len(outcomes):,}")
    pm = portfolio_results.get("portfolio_metrics", pd.DataFrame())
    if not pm.empty and "label" in pm.columns:
        print(f"Portfolio PROMISING: {(pm['label']=='PORTFOLIO_PROMISING').sum()}")
        print(f"Portfolio REJECTED: {(pm['label']=='REJECTED_PORTFOLIO').sum()}")
    print(f"HTML: {HTML_OUT}")
    print(f"\nConfirmation: No A3/S3/OMS/final_action/DNSE/live trading/sizing/Phase36 changed.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
