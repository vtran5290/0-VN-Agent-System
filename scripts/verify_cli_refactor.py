"""Structural verification of cli.py — Phase 1 + Phase 2 refactor."""
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "src/trading/cli.py"
src = CLI.read_text(encoding="utf-8")

errors = []

# 1. AST parse
try:
    ast.parse(src)
    print("AST parse: OK")
except SyntaxError as e:
    errors.append(f"SYNTAX ERROR: {e}")

# 2. Line count
lines = src.splitlines()
print(f"Lines: {len(lines)}")

# 3. Handler imports present (Phase 1 + Phase 2)
for mod in [
    "apply_manual_review",
    "build_intents",
    "cloud_daily_report",
    "data_health",
    "distribution_risk",
    "generate_order_intent",
    "intraday_scan",
    "manual_review",
    "resolve_scan",
    "validate_order_intent",
]:
    needle = f"import {mod} as"
    status = "OK" if needle in src else "MISSING"
    print(f"  handler import {mod}: {status}")
    if status == "MISSING":
        errors.append(f"Missing handler import: {mod}")

# 4. register(sub) calls
n_reg = src.count(".register(sub)")
print(f"register(sub) calls: {n_reg}  (expect 10)")
if n_reg != 10:
    errors.append(f"Expected 10 register(sub) calls, found {n_reg}")

# 5. hasattr dispatcher
if 'hasattr(args, "func")' in src:
    print("hasattr(args, func) dispatcher: OK")
else:
    errors.append("Missing hasattr(args, func) dispatcher")

# 6. Opus C3 regression assert
if "live-workflow must not route via func" in src:
    print("Opus C3 assertion: OK")
else:
    errors.append("Missing Opus C3 regression assertion")

# 7. Old inline if-blocks removed (Phase 1 + Phase 2)
for cmd in [
    "resolve-scan",
    "data-health",
    "validate-order-intent",
    "intraday-scan",
    "distribution-risk",
    "cloud-daily-report",
    "generate-order-intent",
    "build-intents",
    "manual-review",
    "apply-manual-review",
]:
    needle = f'args.command == "{cmd}"'
    count = src.count(needle)
    if count == 0:
        print(f"  old block '{cmd}': REMOVED")
    else:
        errors.append(f"Old block still present: {cmd} ({count}x)")
        print(f"  old block '{cmd}': STILL PRESENT ({count}x)")

# 8. live-workflow stays inline (no set_defaults near its subparser)
lw_idx = src.find('"live-workflow"')
if lw_idx >= 0:
    lw_lines = src[:lw_idx].splitlines()[-5:]
    if any("set_defaults" in l for l in lw_lines):
        errors.append("live-workflow may have set_defaults(func) — C1 violation")
    else:
        print("live-workflow inline (no set_defaults): OK")

# 9. snapshot-baseline stays inline (broker-touching — Phase 3)
if 'args.command == "snapshot-baseline"' in src:
    print("snapshot-baseline inline (Phase 3 pending): OK")
else:
    errors.append("snapshot-baseline missing from inline block")

print()
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("All checks PASSED")
    sys.exit(0)
