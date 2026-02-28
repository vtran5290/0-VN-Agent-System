# Lesson Learned — 2026-02

## 1) Performance Summary
- n_closed: 35
- win_rate: None
- avg R-multiple: None
- best_3: []
- worst_3: []

## 2) Top 3 Recurring Patterns
- **Missing stop recorded** (count=35, severity=med)
- **No reason_tag** (count=35, severity=low)

## 3) 1–2 Rule Adjustments (actionable)
- Require stop_price_at_entry on every trade (no exceptions)
- Require reason_tag from controlled set (breakout_base, pocket_pivot, vcp, add_on, reentry, ...)

## 4) What NOT to change (anti-overfit)
- Do not change entry/exit/sizing rules based on single month.
- Do not auto-apply rule_change_proposals; review manually.

## 5) Open Questions (max 3)
- WoW regime vs. execution alignment?
- R-multiple coverage on open positions?
- Council execution vs. plan?

## Insight Bursts
- [RED] Missing stop recorded rate: 100% (35/35)
- [RED] No reason_tag rate: 100% (35/35)
