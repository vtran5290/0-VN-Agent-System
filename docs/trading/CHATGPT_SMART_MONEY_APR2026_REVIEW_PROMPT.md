# ChatGPT Review + Fund Landscape Synthesis — Smart Money April 2026

**Paste this entire file into ChatGPT and attach:** `smart_money_apr2026_chatgpt_review.zip`

No prior chat context required.

---

## Your role (two-part mandate)

You perform **both** tasks below, in order. Use `extracted_text/*.txt` and `*_tables.json` as **primary evidence**. Use `deliverables/smart_money_apr_2026_digest.md` and `smart_money_apr_2026_structured.json` as **draft synthesis to audit** — not as sole source of truth.

### Part A — Independent QA audit

Validate the builder’s digest/JSON against extracts.

### Part B — Independent fund landscape re-synthesis

**Re-read all April 2026 fund extracts** and produce a **fresh, operator-grade fund landscape** for Vietnam equities. This is **not** a short summary of the digest — rebuild cross-fund views from source text. Where the digest is wrong or thin, **correct it** and say so in Part A.

**You are not** writing a generic Vietnam macro note from training data. **Do not** give buy/sell orders, position sizing, or “buy X tomorrow” advice.

---

## Package summary (FACTS — from builder)

| Item | Value |
|------|--------|
| **Report month ref** | `2026-04` |
| **Source folder** | `D:\V\1. Current Trade Sys\Reports\Funds April 2026` |
| **April funds (cross-fund stats)** | **10** — exclude `vnh-investor-report-march-2026 (1).pdf` (as-of **2026-03-31**) |
| **Deliverables to audit** | `deliverables/smart_money_apr_2026_digest.md`, `deliverables/smart_money_apr_2026_structured.json` |
| **Extraction** | pypdf + pdfplumber; KDEF = medium confidence |

**Hash-named PDFs:** `1778481240_...` = **KIM Vietnam Growth UCITS**; `1778813555_...` = **KIM Growth Dividend Equity Fund (KDEF)**

**Known caveats (keep visible in both parts):**

- Mixed return currencies (VND CCQ / USD TR / EUR) — do not rank funds without stating basis
- PDF binaries not in zip — see `SOURCE_PDF_MANIFEST.txt`
- Cap-weight **VN-Index** may be **Vingroup-skewed** (2025–2026); use **ex-Vingroup** manager statements when discussing breadth

---

## Files in this zip

| Path | Role |
|------|------|
| `REVIEW_PROMPT.md` | This file |
| `deliverables/smart_money_apr_2026_digest.md` | Draft synthesis (audit target) |
| `deliverables/smart_money_apr_2026_structured.json` | Draft JSON (audit target) |
| `extracted_text/*.txt` | **Primary SSOT for Part B** |
| `extracted_text/*_tables.json` | Holdings / performance tables |
| `SOURCE_PDF_MANIFEST.txt` | Original PDF list |

---

## Data discipline (both parts)

- **Source** = fund factsheets / monthly reports in zip only
- **Not in scope** = broker notes, FireAnt, news, your memory of “typical” Vietnam data
- Unverified → **UNKNOWN** or **NEEDS SOURCE CHECK**
- Label **FACT** (quoted or table-derived) vs **INFERENCE** (your cross-fund synthesis)
- Keep original **ticker spellings** from PDFs; do not infer tickers from company names unless the PDF states both

---

# PART A — QA AUDIT

## QA checklist

### A. File inventory
- [ ] 11 PDFs in manifest; VNH = March only
### B. Spot-check ≥4 funds (VDEF, PYN Elite, VEIL, KIM VGF): returns, top 10 weights, macro bullets
### C. Cross-fund math: ticker frequency, ~95% Vingroup claim, crowded names
### D. FACT vs INFERENCE in digest
### E. JSON schema + diagnostics

## Part A output headings

### A1. Verdict
`PASS` | `PASS WITH FIXES` | `FAIL` — one line.

### A2. Confirmed accurate (≤10 bullets)
Verified against extracts only.

### A3. Errors / corrections

| Location | Stated | Should be | Evidence (extract file) |
|----------|--------|-----------|-------------------------|

### A4. Missing / weak extraction

### A5. FACT vs INFERENCE audit (digest)

### A6. VIN / breadth handling

### A7. Suggested JSON patches (minimal)

---

# PART B — FUND LANDSCAPE RE-SYNTHESIS (April 2026)

Rebuild from extracts. **Prefer depth over repeating Part A.** Cross-fund synthesis matters more than 10 mini fund summaries.

## Required sections (use these exact headings)

### B1. Fund universe map (table)

One row per **April 2026** fund (10 rows). Columns:

| Fund | Manager / vehicle type | Mandate (1 line) | AUM or NAV (as stated) | Apr return | YTD | Benchmark cited | Vingroup stance (hold / avoid / underweight / overweight) | Extraction confidence |

Add footnote row for **VNH (Mar 2026 only)** if you reference it — do not mix into April counts.

### B2. April market — what managers actually said (FACTS only)

Bullets only from fund text: VN-Index move, ex-Vingroup move, sector winners/losers, Q1 earnings, foreign flow, liquidity, oil/geopolitics, CPI/PMI/FDI, FTSE/MSCI. Cite which funds said each (e.g. “VinaCapital ×4, KIM, PYN”).

### B3. Positioning landscape

#### B3a. Most widely held names (consensus)
Table: `Ticker | # funds (of 10) | Typical weight range | Funds holding | Sector`

Count from **disclosed top holdings only** (do not assume full portfolio).

#### B3b. Crowded trades
Names/sectors where alignment is tight **and** weights are large.

#### B3c. Selective / differentiated bets
Names held by ≤2 funds or high weight at only one fund (STB at PYN, BVH at VESAF, KDH at VOF, GVR at KIM, etc.).

#### B3d. Sector consensus vs gaps
Which sectors dominate (banks, steel, retail) vs underrepresented (energy, tech, healthcare, etc.).

#### B3e. Fund clusters (archetypes)
Group funds by **observed** behavior, e.g.:
- Ex-Vingroup quality (VinaCapital open-end)
- Index / Vingroup-aligned (KIM VGF, VEF)
- Underweight VIN vs index (VEIL)
- Closed-end / capital structure (VOF, VEIL)
- Concentrated frontier (PYN)
- Dividend / income tilt (KDEF, VDEF)

Labels must be justified by holdings + commentary — not generic labels.

### B4. Performance divergence (FACTS + INFERENCE)

- Who beat / lagged **VN-Index** in April and **why managers say so** (especially Vingroup exclusion)
- YTD dispersion across funds (note currency)
- **INFERENCE:** Is “headline index” a misleading benchmark this month?

### B5. Macro & policy regime (cross-fund)

#### B5a. Repeated macro data points (table)
| Metric | Values cited | Funds mentioning |

#### B5b. Shared themes (policy, flows, upgrades, risks)

#### B5c. Contradictions between managers
(e.g. consumer strong vs soft; BVH bull vs bear; Vingroup opportunity vs avoidance)

### B6. Smart money consensus (INFERENCE — label clearly)

- **Consensus positions** (5–8 tickers max)
- **Consensus thesis** (4–6 bullets)
- **Emerging risks** (4–6 bullets)
- **Regime classification** (one phrase + 2–3 sentence justification)

### B7. Implications for Vietnam equity research workflow (INFERENCE)

4–6 bullets for a **serious allocator / researcher** (monitoring list, benchmark choice, VIN contamination checks, what to watch next month). **No trade instructions.**

### B8. Comparison vs builder digest

Short subsection:
- **Aligns with digest:** …
- **Digest overstated / wrong / missing:** …
- **Net:** trust digest for X; redo Y from your Part B

---

## Reference claims (verify in Part A; re-derive in Part B)

1. VN-Index **+10.7%** April; **~95%** Vingroup; ex-Vingroup **~+0.5%** Apr / **~-1% YTD**
2. VinaCapital retail funds **no Vingroup** → lagged index
3. **MBB, CTG, MWG, HPG** ubiquitous in top holdings
4. Q1 profit **+35–36%**; banks **+12%** dispersed
5. CPI **~5.5%**; PMI **50.5**; FDI **+32% / +9.8%** (4M26)
6. KIM: foreign **-USD 544mn**; turnover **USD 915mn** (-20.8% MoM)
7. FTSE Secondary EM (timing varies by fund)

---

## Output length & style

- Professional English, bullet-heavy, tables where useful
- Part A: concise (~1–2 pages)
- Part B: substantive (**2–4 pages**) — this is the main deliverable for the operator
- Every section B2+ must separate **FACT** and **INFERENCE** sub-bullets or labels where mixed

---

## Optional (if token budget allows)

Append a compact **JSON fragment** (not full schema) for downstream ingest:

```json
{
  "report_month_ref": "2026-04",
  "audit_verdict": "PASS | PASS WITH FIXES | FAIL",
  "landscape_regime": "",
  "consensus_tickers": [],
  "differentiated_bets": [],
  "macro_themes": [],
  "digest_trust_level": "high | medium | low"
}
```

---

*End of prompt.*
