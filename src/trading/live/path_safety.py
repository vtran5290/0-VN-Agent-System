"""Guard execution paths — never write under data/paper_trade/."""
from __future__ import annotations

from pathlib import Path

from src.trading.config import REPO_ROOT

FORBIDDEN_PARTS = ("data", "paper_trade")


class ForbiddenLedgerPathError(ValueError):
    pass


def is_under_paper_trade(path: Path) -> bool:
    try:
        resolved = path.resolve()
        parts = [p.lower() for p in resolved.parts]
        for i in range(len(parts) - 1):
            if parts[i] == "data" and parts[i + 1] == "paper_trade":
                return True
        rel = resolved
        try:
            rel = resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            pass
        rel_parts = [p.lower() for p in rel.parts]
        for i in range(len(rel_parts) - 1):
            if rel_parts[i] == "data" and rel_parts[i + 1] == "paper_trade":
                return True
    except OSError:
        return False
    return False


def validate_live_output_path(path: Path, *, context: str = "") -> Path:
    """Raise if path would write under research ledger data/paper_trade/."""
    if is_under_paper_trade(path):
        msg = f"Forbidden output path (research ledger): {path}"
        if context:
            msg = f"{msg} [{context}]"
        raise ForbiddenLedgerPathError(msg)
    return path
