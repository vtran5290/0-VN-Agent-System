# Quan Trắc — Weekly Content Workflow
**Date:** 2026-06-19
**Cadence:** Every Sunday/Monday after the weekly report generates

---

## One Input → Five Outputs

```
INPUT: python -m src.report.weekly
  ↓
  data/decision/weekly_report.md    (auto-generated)
  data/state/regime_state.json      (auto-generated)
  ↓
OUTPUT PIPELINE (manual, ~45 min total):
  1. Substack memo      (30 min — sanitize + publish)
  2. X thread           (5 min — extract key numbers)
  3. Regime flash        (1 min — run script)
  4. FireAnt/CafeF post  (5 min — rewrite in Vietnamese)
  5. Facebook post       (5 min — adapt from FireAnt version)
```

---

## Step-by-Step Weekly Workflow

### Sunday Evening (after market data is final)

**Step 1: Run the weekly pipeline**
```powershell
cd "D:\V\0. VN Agent System"
python -m src.report.weekly
```
Verify: `data/decision/weekly_report.md` and `data/state/regime_state.json` are updated.

**Step 2: Generate regime flash**
```powershell
python scripts/extract_regime_flash.py --format x
python scripts/extract_regime_flash.py --format telegram
```
Copy the X-format output → schedule as Monday morning tweet.
Copy the telegram output → save for Substack preview if needed.

**Step 3: Sanitize weekly report → Substack memo**
```
Open: data/decision/weekly_report.md
Open: outputs/public_launch/05_weekly_memo_template.md (template)
Open: outputs/public_launch/02_language_sanitization_map.md (reference)

Process:
a. Copy the template sections into a new draft
b. Fill each section from weekly_report.md data
c. REMOVE: all ticker-specific directional language
d. REMOVE: A3 action board, "if X do Y" action language
e. REMOVE: allocation weights, NAV references, position data
f. REPLACE: "watchlist" → "screen output", per sanitization map
g. ADD: one historical case study (≥6 months old)
h. ADD: disclaimer at top and bottom
i. READ ALOUD: does any sentence sound like advice? Fix it.
```

**Step 4: Write X launch thread**
```
Template (adapt numbers from this week's data):

1/ Quan Trắc — Issue [N] is live.
   [One-line regime summary]
   → [LANDING_PAGE_URL]

2/ This week:
   Regime: [state] ([global] / [vn])
   VNINDEX: [level]
   Distribution: [count] on VN30
   Breadth: [zone]

3/ [One interesting observation — RS, sector, or probability]

4/ Full issue: [LANDING_PAGE_URL]
   Not investment advice.
```

**Step 5: Write FireAnt/CafeF post (Vietnamese)**
```
Template:

[Title] Quan Trắc tuần [date] — Framework đọc gì?

[2-3 paragraphs covering:]
- Regime state and what drove it
- Breadth observation (one specific data point)
- One historical context point

[Closing:]
Bản đầy đủ: [LANDING_PAGE_URL]
Quan sát framework, không phải khuyến nghị đầu tư.
```

**Step 6: Adapt for Facebook (Vietnamese)**
```
Shorter version of the FireAnt post.
3-5 lines max. Link to Substack.
Add: "Không phải khuyến nghị đầu tư."
```

### Monday Morning

**Step 7: Publish in order**
```
07:00 ICT — Publish Substack memo
08:00 ICT — Post X thread
08:30 ICT — Post regime flash (separate X post)
12:00 ICT — Post FireAnt/CafeF version
18:00 ICT — Post Facebook version
```

All posts from anonymous device/browser. Never from work machine.

---

## Weekly Quality Checklist (before hitting Publish)

- [ ] Disclaimer at top AND bottom of Substack memo
- [ ] No ticker names with directional language
- [ ] No buy/sell/hold/signal/alert/target/portfolio/allocation
- [ ] No NAV, returns, P&L, position sizes
- [ ] No file paths, usernames, or API references
- [ ] Case study is ≥6 months old
- [ ] All data has source cited
- [ ] Probabilities include n= and methodology note
- [ ] "Not investment advice" appears in every output
- [ ] Post timing does not overlap with personal account activity

---

## Automation Opportunities (Future)

| Task | Current | Automated? |
|---|---|---|
| Weekly report generation | `python -m src.report.weekly` | Already automated |
| Regime flash extraction | `python scripts/extract_regime_flash.py` | Already automated |
| Memo sanitization | Manual | Could build a sanitization linter (Cursor task) |
| X thread generation | Manual template | Could script from weekly_report.md sections |
| Vietnamese post generation | Manual rewrite | Keep manual — stylometric safety |
| Publishing to Substack | Manual | Substack API exists but adds complexity |
| Scheduling X posts | Manual | Use X's built-in scheduler |

**Recommendation:** Keep the Vietnamese content manual (prevents cross-platform stylometric fingerprinting). Automate the English/data extraction side.

---

## Time Budget

| Task | Time | When |
|---|---|---|
| Run pipeline + extract flash | 5 min | Sunday evening |
| Sanitize weekly report → memo | 25-30 min | Sunday evening |
| Write X thread | 5 min | Sunday evening |
| Write FireAnt post (VN) | 10 min | Sunday evening |
| Adapt Facebook post | 5 min | Sunday evening |
| Review + publish all | 10 min | Monday morning |
| **Total** | **~60 min/week** | |

*This workflow document is for the operator's internal use only — do not publish.*
