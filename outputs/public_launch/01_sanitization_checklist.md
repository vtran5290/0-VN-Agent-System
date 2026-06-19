# Report & Dashboard Sanitization Checklist
**Date:** 2026-06-17
**Status:** Pre-launch gate — must complete before any public publication
**Council authority:** Opus judgment gate (2026-06-17)

> All outputs split into two pipelines: **INTERNAL** (never leaves local machine) and **PUBLIC** (cleared for free publication). When in doubt, internal wins.

---

## Artifact-by-Artifact Decisions

### 1. Cloud Daily Report (HTML / MD)

**Verdict: NEEDS SANITIZATION before publish (static snapshots only)**

Safe to publish:
- Regime label (Bull / Bear / Fragile) — observation, not advice
- Breadth reading (% stocks above EMA) — observation
- VNINDEX context (index level, week-over-week move) — observation
- Top RS sector names (no tickers, no weights) — observation
- Macro summary (UST, DXY direction in plain language) — observation

Must remove before publish:
- [ ] Any field labeled `signal`, `action`, `buy`, `sell`, `entry`, `exit`, `stop`
- [ ] `allocation` or `weight` fields
- [ ] Individual ticker names paired with directional language ("FPT forming base", "VHM near entry zone")
- [ ] `final_action` field or any OMS-bound output
- [ ] Paper-trade NAV, position sizes, P&L references
- [ ] File paths, local usernames, repo paths in HTML comments or metadata
- [ ] API keys, DNSE credentials, broker account references anywhere in source or rendered output
- [ ] Timestamps that reveal work hours if those hours are within employer work hours

Safe replacement framing:
- "Stocks currently meeting the momentum breadth criterion: N stocks" (count only, no names)
- "The rules-based regime framework reads [Bull/Bear/Fragile] this week"
- "Macro conditions summary: [plain text observation]"

Publish format: **Static PNG snapshot embedded in memo only. No live HTML with current data.**

---

### 2. Weekly Report (MD)

**Verdict: NEEDS SANITIZATION — publishable after cleanup**

Safe to publish:
- Regime narrative (what the regime is, how it changed)
- Breadth conditions (quantitative observations, no ticker names)
- Sector rotation observations (sector names only, no tickers)
- Historical case study section (≥6 months old, multi-stock, no individual trade replay)
- Risk and macro context (general level, no advice language)
- "Model behavior" section renamed to "Rules-based framework observations"

Must remove / rewrite:
- [ ] Any "watchlist" framing that includes current tickers + directional language
  → Replace with: "Stocks currently meeting objective criterion X — observation only, not a view"
- [ ] "Allocation" or "sizing" references
- [ ] "If X, do Y" action language → replace with "Historically, when X has occurred, Y has followed — this is a historical observation, not a prediction"
- [ ] A3 action board or any section that reads as a trade plan
- [ ] Paper-trade performance references (returns, win rate, NAV)
- [ ] Single-stock case studies using stocks currently in paper portfolio
- [ ] Forward-looking language: "will", "should", "expect" → replace with "has historically", "the model notes", "prior regimes showed"
- [ ] Author byline or any metadata linking to real identity

Publish format: **Markdown → static site or Substack post. No embedded live data.**

---

### 3. Streamlit Dashboard

**Verdict: DO NOT PUBLISH publicly in Year 1**
**Council authority: Opus CAUTION → deferred to Year 2**

Reasons:
- Interactivity mimics personalized recommendation infrastructure
- Live/near-daily refresh reads as a signal service
- Server logs create data-processing obligations (Decree 13/2023)
- Hosting infrastructure (Streamlit Cloud, Railway, etc.) creates account trails

Year 1 alternative:
- Export **static PNG snapshots** of specific charts (regime chart, breadth chart, RS heatmap)
- Embed in weekly memo as images
- No interactivity, no per-ticker drilldown, no live data update

Specific fields to never screenshot/export:
- [ ] Any tab showing individual ticker signals or actions
- [ ] NAV curve or performance chart
- [ ] Position sizes or allocation weights
- [ ] Paper-trade execution log
- [ ] Any tab with `final_action`, `signal`, `buy`, `sell` column headers visible

Safe screenshot subjects:
- Regime state indicator (single label + date)
- Breadth histogram (counts, not ticker names)
- Sector heatmap (sector-level, not stock-level)
- Macro indicators chart (UST, DXY, SBV rate — public data)

---

### 4. RS Leader CSVs / Parquet

**Verdict: DO NOT PUBLISH raw files**

Reason: A ranked CSV of tickers with RS scores functions as a screener output / recommendation list regardless of disclaimers. It is copy-pasteable into a brokerage account.

Safe alternative:
- Publish **aggregate statistics only**: "N stocks in the top RS decile this week; sector distribution: Financials 30%, Industrials 25%..."
- Publish **methodology description** without the output: "The RS score ranks stocks by 12-1 relative performance vs VNINDEX; this week's leader universe contains stocks in the top 20%"
- Never publish a file with schema `{ticker, RS_score, rank}` or similar

Fields to strip if any aggregate export is considered:
- [ ] Ticker symbols (replace with anonymized IDs if truly needed for illustration)
- [ ] Individual RS scores (replace with decile/quintile tier only)
- [ ] `signal`, `action`, `recommendation` columns

---

### 5. Institutional Accumulation Scan

**Verdict: CAUTION — publishable in aggregate form only**

What this is: Scans for unusual volume patterns suggesting institutional buying/selling.

Safe to publish:
- Sector-level aggregates: "Institutional accumulation signals concentrated in [sector] this week"
- Count summaries: "N stocks showed accumulation signals meeting the criteria"
- Historical comparisons: "This count is above/below the 12-month average of N"

Must not publish:
- [ ] Individual ticker names with accumulation/distribution labels
- [ ] "Smart money is buying X" or any language implying informed-trader advantage
- [ ] Fund-flow data attributed to specific funds without public filing source
- [ ] Any framing suggesting the reader should act on the accumulation signal

Rule: Every institutional scan observation must cite the observable criterion (volume ratio, price action criterion) — never imply privileged information.

---

### 6. Fund Holdings / Smart-Money Tracker

**Verdict: CAUTION — publishable only if sourced from public filings**

Distinction:
- Reporting what a fund disclosed in its public quarterly filing = news-adjacent, generally safe
- Computing fund aggression scores / ranking funds by conviction = closer to the line (implies analysis that could constitute investment consulting)

Safe to publish:
- "Fund X disclosed Y position in its [date] filing" — with filing source cited
- Sector allocation changes across fund universe (aggregate, not per-fund)
- "Filing-based consensus: financials sector saw net addition across N funds this quarter"

Must not publish:
- [ ] "Computed" flows or estimates not directly from public filings
- [ ] Rankings of funds by conviction/aggression without explicit sourcing
- [ ] Any framing: "smart money is moving into X" — replace with "public filings show net additions to sector X this period"

---

### 7. Downtrend Probability Model Output

**Verdict: NEEDS SANITIZATION — publishable as regime context only**

Safe to publish:
- "The downtrend probability model reads X% this week" — as a single number, regime context
- Historical distribution: "The model has spent N% of weeks above 70% probability since 2012"
- Directional change: "Probability increased/decreased vs prior week"

Must not publish:
- [ ] Per-ticker downtrend probability scores
- [ ] "Avoid X stock because downtrend probability is high" — advice language
- [ ] Model output used as a screener filter result with named stocks

---

### 8. Regime State JSON (`data/state/regime_state.json`)

**Verdict: INTERNAL ONLY — do not publish the raw file**

Reason: The JSON schema likely contains internal field names, model versioning, calibration parameters, and potentially file paths or system metadata.

Safe alternative:
- Extract the regime label only (`bull` / `bear` / `fragile`) for public mention
- Extract the date of last update
- Publish as a single line in the weekly memo: "Current regime (as of [date]): [label]"

Fields to never expose publicly:
- [ ] Internal calibration thresholds
- [ ] Model version identifiers
- [ ] File paths or system metadata
- [ ] Any field not already described in the public methodology

---

### 9. Allocation Plan JSON

**Verdict: BLOCK — never publish in any form**
**Council authority: Opus hard BLOCK**

Reason: Any file with schema `{ticker: weight}` or `{ticker: size, action: buy/sell}` constitutes portfolio construction output. It is copy-pasteable into a brokerage account regardless of disclaimers. This is the single artifact most likely to be interpreted as unauthorized portfolio management.

Action:
- [ ] Move to `data/private/` or a folder explicitly in `.gitignore`
- [ ] Add a guard in the build pipeline that prevents this file from appearing in `outputs/`
- [ ] Never reference allocation weights in public content — use tier labels instead ("overweight sector", "top RS tier") if any position sizing concept must be discussed

---

### 10. Paper-Trade History / NAV / Execution Audit

**Verdict: BLOCK — never publish in any form in Year 1**
**Council authority: Opus hard BLOCK**

Reason: A NAV curve is a performance track record. Publishing it converts "research notebook" into "strategy operator with measured returns" — which is the regulated activity the project is trying to stay outside of. The execution audit log adds portfolio management texture (tickers, sizes, timestamps).

Actions:
- [ ] Move all paper-trade output files to `data/private/`
- [ ] Add `data/paper_trade/` to `.gitignore` explicitly
- [ ] Add `trade_logs/` to `.gitignore` explicitly
- [ ] Never reference "the model returned X%" or "paper NAV is X" in any public content
- [ ] If model behavior must be discussed: use directional/rank descriptions only ("signals concentrated in financials during bull regime", "breadth thrust preceded RS leadership shift by N weeks")

---

## Pipeline Split Action Items

Before July 1, complete these structural changes:

- [ ] Create `data/private/` folder — add to `.gitignore`
- [ ] Move to `data/private/`: paper_trade/, trade_logs/, allocation JSON, execution audit
- [ ] Add `outputs/public_launch/` to a separate public-facing repo or deploy folder — never the full repo
- [ ] Review HTML report template for hardcoded file paths, usernames, and API references in HTML comments
- [ ] Create a `make public-export` or equivalent script that generates sanitized snapshots only — never exports raw signal files
- [ ] Run `git status` on all `.env` files — confirm none are tracked

---

## Pre-Publication Final Check

Before publishing anything:
- [ ] Open the artifact and read it as an adversary: employer HR, SSC investigator, journalist
- [ ] Does any sentence imply a specific action on a specific stock? → Remove
- [ ] Does any number imply a performance track record? → Remove
- [ ] Does any metadata (filename, path, timestamp) reveal identity? → Remove
- [ ] Does the disclaimer appear at the top AND bottom of every published piece? → Confirm

---

*AI advisory only — not legal advice. Consult qualified Vietnamese legal counsel before any public launch.*
