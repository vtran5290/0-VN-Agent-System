# S3 Lead Window Patch Notes (Round 2)

Date: 2026-05-16

---

## Problem

`S3_LEAD_A3_FINDINGS.md` stated in the Verdict section:
"MAR difference at 30-bar window (with_s3 − without_s3): +0.061"

This was misleading because:
- The implementation uses `a3_s3_lead_5d` — the **5-bar** window
- The 5-bar delta is **+0.083** (0.291 vs 0.208), not +0.061
- The 30-bar result is diagnostic, not the operational rule

The receiver of that document could incorrectly believe the 30-bar window is
what was implemented, or that the delta is +0.061 rather than +0.083.

---

## Fix Applied

`S3_LEAD_A3_FINDINGS.md` updated to:
- Mark the 5-bar row as the selected rule in the summary table (bold)
- Change the Verdict section to lead with: "Selected rule: 5-bar lead (`a3_s3_lead_5d`)"
- State the correct delta: **+0.083 at 5-bar window**
- Explicitly label 30-bar result as "diagnostic only"
- Add a "Why 5-Bar, Not 30-Bar" section with the window comparison table
- Clarify what `a3_s3_lead_5d = True` does and does NOT do

---

## Operational Rule Confirmed

```
a3_s3_lead_5d = True
    when: S3 EMA21/55 cloud breakout on same symbol within 5 bars before A3 signal

Effect: On days with multiple NEW_T1 signals, a3_s3_lead_5d=True ranked first.

Does NOT: block A3, force A3 entry, change position size, route S3 capital.
```
