# ChatGPT Review Prompt — VNINDEX sector rotation & index leadership

**Attach zip:** `vn_sector_rotation_index_chatgpt_review.zip`  
**As-of:** 2026-05-20  
**Repo:** VN Agent System (Vietnam equities, FireAnt-first)

---

Copy everything **below the line** into a **new ChatGPT conversation** and attach the zip.

---

You are a **senior Vietnam equity strategist + market microstructure analyst**. A Cursor agent produced a same-day diagnosis after the user observed: (1) BDS sold on negative sector news; (2) NQ79/SOE names had bid around Vin adjustment but faded when a policy meeting had no concrete outcome; (3) FPT and oil/gas names felt “dragged down” intraday; (4) derivatives turned positive into the close; (5) confusion about **which sector the market actually expects to lead VNINDEX**.

Your job: **independent second opinion** — validate facts, challenge interpretation, add flow/policy context the agent may have missed. **Do not invent prices or weights** not in the zip; label **UNKNOWN** and say what file would confirm.

## Non-negotiables

| Rule | Detail |
|------|--------|
| FACTS vs INTERPRETATION | Separate strictly; cite file + field |
| FireAnt discipline | source=FireAnt, method=REST/CSV, date range, native vs derived |
| VIN baseline | Cap-weight VNINDEX may be Vingroup-skewed 2025–2026; prefer breadth + ex-VIN lens |
| No trade orders | Do not override `final_action` or OMS; portfolio is context only |
| Vietnamese market | Rates, credit, fiscal, FX, sentiment, foreign flow where relevant |

## Read first (in zip)

| Order | File | Purpose |
|-------|------|---------|
| 1 | `REVIEW_PROMPT.md` | This prompt |
| 2 | `handoff/sector_rotation_index_handoff_20260520.md` | Cursor summary + open questions |
| 3 | `data/sector_bucket_returns_20260520.csv` | Sector 1D returns (panel) |
| 4 | `data/vnindex_ohlcv_recent.csv` | VNINDEX last ~30 sessions |
| 5 | `data/distribution_risk_latest.json` | Dist days, ex-VIN probabilities |
| 6 | `data/phase36_daily_scan_latest.csv` | EOD scan SSOT (101 symbols) |
| 7 | `data/cloud_daily_report_latest.md` | Operator daily report |
| 8 | `data/daily_scan.md` | Portfolio + regime snapshot |
| 9 | `data/current_positions_derived.json` | User holdings |
| 10 | `data/intraday_scan_latest_meta.json` | Pre-ATC VNINDEX overlay |
| 11 | `docs/VIN_EMA_CLOUD_BASELINE.md` | Dual full vs ex-VIN rules |

## Core user question

> **Liệu thị trường đang kỳ vọng thực vào ngành nào để dẫn index?**  
> Weighting lens: **Vin, BDS, FPT, energy (oil/gas/PVS…), securities, banks.**

## Specific tasks

### A. Fact-check the handoff
- Agree/disagree with sector return table and VNINDEX +0.02% flat close after low 1859.  
- Reconcile user “FPT/energy kéo giảm” vs EOD **positive** sector returns — intraday vs close narrative.  
- Flag any internal contradictions between scan, panel returns, and reports.

### B. Index leadership map (required output table)

Produce a table:

| Sector bucket | Est. index weight (band) | Today return | Index contribution (qualitative) | Leadership score 1–5 | Evidence |
|---------------|--------------------------|--------------|-----------------------------------|----------------------|----------|

Buckets: **VIN, BDS, FPT/Tech, Energy, Banks, Securities, NQ79/SOE proxy, Other**.

Use zip data only; if weight unknown, say **UNKNOWN** and give a reasonable **HOSE liquidity proxy** (e.g. adv50 from scan) with label **proxy-not-official-weight**.

### C. What is the market “pricing” for the next 2–4 weeks?

Choose the **best-fit** narrative (can combine, rank #1–#3):
1. Vin-driven index (adjustment / cap events)  
2. Policy/SOE (NQ79) re-rating  
3. Commodity-energy volatility leadership  
4. Tech/barometer (FPT) risk-on  
5. Bank + securities beta broadening  
6. No sector — stock-picking / defense / range-bound  
7. Derivative-led technical bounces without cash breadth

For each chosen narrative: **confirming signals** and **falsifying signals** (observable, Vietnam-specific).

### D. Portfolio implications (user book)

From `current_positions_derived.json` + scan:
- Top **3** risks given defense breadth + distribution lens + sector moves today  
- Top **3** actions (reduce / hedge / hold / rotate) — **judgment**, not system overrides  
- Mismatch: holdings **not** in scan (PDR, STB, TCX) — how does that affect your advice?

### E. Operator questions (answer directly)

1. Should user treat late-session derivative strength as **real risk-on** or **index defense**?  
2. Is adding **OIL / BID / VGI** (scan NEW_T1 manual review) consistent with sector map or fighting tape?  
3. When does **ex-VIN** VNINDEX view matter more than headline VNINDEX for this book?

## Output format (strict)

```markdown
## FACTS (verified from zip)
- bullets with file citations

## FACT CHECK vs Cursor handoff
- agree / disagree list

## Sector leadership table
(table)

## INTERPRETATION — who leads index next?
- Primary thesis (#1)
- Secondary (#2)
- What would change your mind (3 bullets)

## Portfolio — Top 3 risks / Top 3 actions

## Signals to monitor next week
- bullet list

## If X happens → do Y
- 3 conditional rules

## UNKNOWN / need more data
- bullet list
```

## Scoring rubric (optional footer)

Rate Cursor handoff quality 1–5 on: factual accuracy, VIN distortion handling, intraday vs EOD nuance, portfolio relevance, actionability.

---

_End of prompt. Zip built by `scripts/reporting/build_sector_rotation_chatgpt_zip.py`._
