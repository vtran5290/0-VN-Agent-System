# Council Vote Card (Lean Mode)

Each brain outputs ONLY this JSON. No narrative. No paragraphs.

```json
{
  "stance": "BUY | HOLD | SELL | NO_NEW_BUYS",
  "confidence": 0,
  "top_3_evidence": ["≤10 words", "≤10 words", "≤10 words"],
  "top_2_risks": ["≤10 words", "≤10 words"],
  "change_my_mind": "one short sentence"
}
```

**Guardrails:**
- **change_my_mind:** Required, non-empty. One sentence that would invalidate this view (quality anchor).
- **top_3_evidence:** Evidence-type only (facts, levels, counts). Not opinion. Examples: "DistDays=4, vol up", "Close < MA20 day2", "Fed tone hawkish". Forbidden in evidence: "likely", "maybe", "seems", "good", "bad".
- evidence bullets ≤ 10 words each.
