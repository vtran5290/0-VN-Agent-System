"""Research-only Cloud Daily Report validation framework.

RESEARCH_ONLY_NOT_PRODUCTION — outputs from this package must not be used
to modify live trading signals, final_action logic, or OMS behavior.
"""
from .schema import RESEARCH_ONLY_LABEL, EvidenceStatus, EvidenceLabel, DashboardRecommendation

__all__ = [
    "RESEARCH_ONLY_LABEL",
    "EvidenceStatus",
    "EvidenceLabel",
    "DashboardRecommendation",
]
