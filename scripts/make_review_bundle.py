"""Create a reproducible MCP-orchestration review bundle.

The bundle contains the minimum Python source + configs needed to run:

    python scripts/mcp_smoke.py
    python scripts/mcp_status.py
    python scripts/mcp_live_guard.py
    pytest tests/test_mcp_orchestration.py -q
    pytest tests/test_mcp_client_compatibility.py -q
    pytest tests/test_live_execution_guard.py -q
    pytest tests/test_risk_enforcer_blocks.py -q

Excluded by policy:
  * Parquet / CSV market data (data/fireant_ssot/*.parquet, data/master/*.csv)
  * Secrets (.env, *.token, *_secret*)
  * Compiled bytecode (__pycache__, *.pyc)

Folder layout in the zip mirrors the repo exactly so paths still resolve.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── Inclusion list ────────────────────────────────────────────────────────
# Each entry is repo-relative. Globs allowed.
SOURCE_PATTERNS: List[str] = [
    # MCP layer + entrypoint
    "src/mcp_server/*.py",
    "scripts/mcp_quant_engine.py",
    "scripts/mcp_smoke.py",
    "scripts/mcp_status.py",
    "scripts/mcp_live_guard.py",
    "scripts/mcp_risk_smoke.py",
    "scripts/mcp_paper_smoke.py",
    "scripts/make_review_bundle.py",
    "scripts/refresh_mcp_decision_inputs.py",
    # Regime layer (required by adapters.regime_snapshot)
    "src/regime/__init__.py",
    "src/regime/state_machine.py",
    "src/regime/regime_types.py",
    # Trading core required by adapters / paper_broker / risk
    "src/trading/__init__.py",
    "src/trading/config.py",
    "src/trading/models.py",
    "src/trading/util/__init__.py",
    "src/trading/util/timeutil.py",
    # Risk engine
    "src/trading/risk/__init__.py",
    "src/trading/risk/engine.py",
    "src/trading/risk/rules.py",
    "src/trading/risk/live_rules.py",
    "src/trading/risk/batch_context.py",
    # Monitoring / kill switch
    "src/trading/monitoring/__init__.py",
    "src/trading/monitoring/kill_switch.py",
    # Brokers (paper + DNSE stub, mocked in tests)
    "src/trading/brokers/__init__.py",
    "src/trading/brokers/base.py",
    "src/trading/brokers/paper.py",
    "src/trading/brokers/dnse.py",
    # Reporting subprocess invoked by run_council_audit
    "src/report/__init__.py",
    "src/report/council_secretary.py",
    # Tests for MCP orchestration only
    "tests/test_mcp_orchestration.py",
    "tests/test_mcp_client_compatibility.py",
    "tests/test_live_execution_guard.py",
    "tests/test_risk_enforcer_blocks.py",
    "tests/test_mcp_decision_gates.py",
    # Configs (no secrets)
    "config/mcp/permissions.default.json",
    "config/mcp/strategy_registry.yaml",
    "config/mcp/cursor_mcp_config.example.json",
    "config/mcp/claude_code_mcp_config.example.json",
    "config/mcp/local_quant_engine.env.example",
    "config/live_trading.yaml",
    "config/trading.yaml",
    ".cursor/mcp.json",
    ".mcp.json",
    # Docs (review reading)
    "docs/MCP_ARCHITECTURE.md",
    "docs/MCP_TOOL_CONTRACTS.md",
    "docs/MCP_CLIENT_SETUP.md",
    "docs/PERMISSION_MODEL.md",
    "docs/RISK_ENFORCER_SPEC.md",
    "docs/DECISION_LOG_SCHEMA.md",
    "docs/MANUAL_INPUTS_MCP_POLICY.md",
    # Top-level project docs
    "AGENTS.md",
    "CLAUDE.md",
    "requirements.txt",
    "Makefile",
]

FORBIDDEN_PATTERNS: List[str] = [
    "*.parquet",
    "*.pyc",
    "__pycache__/*",
    "*/__pycache__/*",
    ".env",
    "*.env",  # but allow `local_quant_engine.env.example` which has no leading dot
    "*token*",
    "*secret*",
    "*credential*",
    "*api_key*",
]

# Files we explicitly allow even if a forbidden glob would catch them.
ALLOWLIST: List[str] = [
    "config/mcp/local_quant_engine.env.example",
]


def _matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _expand(patterns: Iterable[str]) -> List[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pat in patterns:
        for p in sorted(REPO_ROOT.glob(pat)):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT).as_posix()
            if rel in ALLOWLIST:
                pass
            elif _matches_any(rel, FORBIDDEN_PATTERNS):
                continue
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _scan_size(files: Iterable[Path]) -> int:
    return sum(f.stat().st_size for f in files)


def build(
    output_zip: Path,
    *,
    verbose: bool = False,
    write_manifest: bool = True,
) -> dict:
    files = _expand(SOURCE_PATTERNS)
    if not files:
        raise SystemExit("No files matched SOURCE_PATTERNS; check repo layout.")

    missing_required = []
    required_for_smoke = [
        "src/mcp_server/server.py",
        "src/mcp_server/adapters.py",
        "src/mcp_server/audit.py",
        "src/mcp_server/permissions.py",
        "src/mcp_server/schemas.py",
    "src/mcp_server/decision_gates.py",
        "src/mcp_server/config.py",
        "scripts/mcp_quant_engine.py",
        "scripts/mcp_smoke.py",
        "scripts/mcp_status.py",
        "scripts/mcp_live_guard.py",
        "tests/test_mcp_orchestration.py",
        "config/mcp/permissions.default.json",
        "config/mcp/strategy_registry.yaml",
    ]
    rels = {f.relative_to(REPO_ROOT).as_posix() for f in files}
    for r in required_for_smoke:
        if r not in rels:
            missing_required.append(r)
    if missing_required:
        raise SystemExit(
            "Required files missing from bundle:\n  - " + "\n  - ".join(missing_required)
        )

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            arc = p.relative_to(REPO_ROOT).as_posix()
            zf.write(p, arcname=arc)
            if verbose:
                print(f"  + {arc}")
        # Manifest
        if write_manifest:
            manifest = {
                "bundle": output_zip.name,
                "file_count": len(files),
                "total_uncompressed_bytes": _scan_size(files),
                "required_for_smoke": required_for_smoke,
                "excluded_patterns": FORBIDDEN_PATTERNS,
                "notes": (
                    "Re-run: python scripts/mcp_smoke.py && pytest tests/test_mcp_orchestration.py -q"
                ),
                "files": sorted(f.relative_to(REPO_ROOT).as_posix() for f in files),
            }
            zf.writestr(
                "BUNDLE_MANIFEST.json",
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )

    return {
        "zip": str(output_zip),
        "file_count": len(files),
        "uncompressed_bytes": _scan_size(files),
        "zip_bytes": output_zip.stat().st_size,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=REPO_ROOT / "mcp_orchestration_review_bundle.zip",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--no-manifest", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    info = build(
        args.output.resolve(),
        verbose=args.verbose,
        write_manifest=not args.no_manifest,
    )
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
