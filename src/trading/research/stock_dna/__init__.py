"""
VN Stock DNA Research Module
Research-only. Does not modify production A3 logic, final_action, OMS, or DNSE routing.

Council decision 2026-06-04: APPROVE_WITH_MODIFICATIONS
Scope v1:
  - 4 candidate lines: EMA20, EMA50, SMA100, SMA150
  - Walk-forward profile discovery with shuffled-null benchmark
  - Regime-split obedience scores (bull / bear / neutral)
  - OOS holdout: final 12 months reserved
  - Variant 1: T2 support gate (annotation-only, research CSV only)
  - Variant 4: Danger line exit warning (annotation-only, research CSV only)
"""
