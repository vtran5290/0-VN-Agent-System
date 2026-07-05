# vn-trading-advisor — Source Provenance Log (PENDING UPDATE)
# ⚠️ PENDING UPDATE — this file contains the planned updated content for:
#    D:\V\.claude\brains\vn-trading-advisor\sources.md
# The canonical file is write-protected in the 2026-07-05 session.
# Changes: old S6 row (Tharp→A3) annotated; S6–S10 rows added; cross-discipline books added to queue
# Apply by copying the updated sections to the canonical file.

## Book sources (Calibre library)

| Belief ID | Book | Author | Chapter / Section | Format | Calibre path |
|-----------|------|--------|-------------------|--------|--------------|
| S1, S2 | How to Make Money in Stocks | William J. O'Neil | Ch.2 (CAN-SLIM C+A), Ch.9 (Market timing) | EPUB | E:\Calibre-books\Trading\William J. O'Neil\How to Make Money in Stocks (2)\ |
| A1 | Market Wizards (series) | Jack D. Schwager | Meta-pattern across all interviews | EPUB | E:\Calibre-books\Trading\Jack D. Schwager\ |
| S3 | Think and Trade Like a Champion | Mark Minervini | "Position Sizing for Optimal Results," "Eight Keys to Unlocking Superperformance" | EPUB | E:\Calibre-books\Trading\Mark Minervini\Think and Trade Like a Champion_ The (3)\ |
| S4 | How I Made $2,000,000 in the Stock Market | Nicolas Darvas | Ch.4 (Box Theory) | EPUB | E:\Calibre-books\Trading\Nicolas Darvas\How I Made $2,000,000 in the Stock M (6)\ |
| S5 | The Battle for Investment Survival | Gerald M. Loeb | "Investment Manager's Dilemma" | EPUB | E:\Calibre-books\Trading\Gerald M. Loeb\The Battle for Investment Survival\ |
| A3 (formerly S6) | Trade Your Way to Financial Freedom | Van Tharp | Foreword, "What's Really Important to Trading," "Modeling Market Geniuses" | EPUB | E:\Calibre-books\Trading\Van Tharp\Trade Your Way to Financial Freedom (8)\ |
| A2 | Unknown Market Wizards (2024) | Jack D. Schwager | Interview meta-pattern (edge = discipline, not signal) | EPUB | E:\Calibre-books\Trading\Jack D. Schwager\Unknown Market Wizards\ |
| S6 | Information Theory: A Tutorial Introduction | Jim V. Stone | Ch.6–8 (Shannon entropy, mutual information, Kelly criterion) | Print/Digital | E:\Calibre-books\Cross-Discipline\Jim V. Stone\Information Theory\ |
| S7 | Thinking in Bets: Making Smarter Decisions When You Don't Have All the Facts | Annie Duke | Ch.1–3 (Decision quality vs outcome quality, resulting bias) | Print/Digital | E:\Calibre-books\Cross-Discipline\Annie Duke\Thinking in Bets\ |
| S8 | Thinking in Systems: A Primer | Donella Meadows | Ch.3–4 (Feedback Loops, Limits to Growth) | Print/Digital | E:\Calibre-books\Cross-Discipline\Donella Meadows\Thinking in Systems\ |
| S9 | Algorithms to Live By: The Computer Science of Human Decisions | Brian Christian & Tom Griffiths | Ch.1–2 (Optimal Stopping, Explore/Exploit) | Print/Digital | E:\Calibre-books\Cross-Discipline\Christian & Griffiths\Algorithms to Live By\ |
| S10 | Manias, Panics, and Crashes: A History of Financial Crises (6th ed.) | Kindleberger & Aliber | Ch.2–3 (Anatomy of a Typical Crisis) | Print/Digital | E:\Calibre-books\Cross-Discipline\Kindleberger\Manias Panics Crashes\ |

## Session sources (VN Agent System)

| Belief ID | Session / File | Date | Notes |
|-----------|---------------|------|-------|
| C1 | resolver_rules.yml §3 + A3_RS paper runs | 2026 ongoing | Bear regime gate is live in production logic |
| C2 | VN Agent Phase D session | 2026-06 | MAR 0.381 locked; Phases B/C rejected |
| C3 | VN Agent signal audit | 2026 | VIN distortion flagged in scan CSVs |
| C4 | TCX sector incident | 2026 | AI guessed wrong; FireAnt verified correct |

## Pending extractions (Calibre books not yet distilled)

| Book | Author | Priority | Likely brain target |
|------|--------|----------|---------------------|
| Wei Zhi — Trade Like Jesse Livermore | Wei Zhi | MED | vn-trading-advisor (tape reading — transfers weakly per opus; VN lacks true intraday tape) |
| Trade Like an O'Neil Disciple / In the Trading Cockpit | Gil Morales | LOW | vn-trading-advisor — covered by Minervini + O'Neil; mine only for pocket-pivot / buyable-gap-up setups not in either |
| Market Wizards (1992) / New / Little Book / Stock Market Wizards | Schwager (6 remaining copies) | LOW | vn-trading-advisor — meta-covered by Unknown Market Wizards (A2); re-mine only if a specific named trader's method is requested |
| 24 Essential Lessons for Investment Success | William J. O'Neil | LOW | vn-trading-advisor — same school as O'Neil #1 (S1, S2); low marginal info |
| How to Make Money Selling Stocks Short | William J. O'Neil | NONE | Short-selling unavailable to VN retail — not transferable |

## Covered-by / dedupe notes (per opus council ruling 2026-07-02)
- **Gil Morales** (both titles): same O'Neil-disciple school as S1/S2/S3. Do not extract fully —
  mine only for pocket-pivot / buyable-gap-up patterns not already in Minervini or O'Neil.
- **Schwager Wizard books** (7 of 8 copies, excluding Unknown Market Wizards used for A2):
  meta-covered. Extracting each separately is diminishing-returns (interview-format overlap).
- **Stock Market Wizards** has a literal duplicate file in the library — dedupe at file level, not a Cortex concern.

## Static pattern library (NOT brains — per fable council 2026-07-02, see rules/source-of-truth.md)
Filed as raw reference material only. No belief lifecycle. Not wired to the active MSG Đồng Xoài deal.
| Book | Author | Target (deferred) |
|------|--------|---------------------|
| Investment Banking | Joshua Rosenbaum | deal-maker brain (blocked until vn-trading clears expansion gate) |
| Never Split the Difference | Chris Voss | deal-maker brain (blocked until vn-trading clears expansion gate) |

## PENDING_CANDIDATE_SOURCES (added 2026-07-03 per ChatGPT judge review)
# Source: D:\V\00. Command Center\05_AI_Handoffs\2026-07-03-1600_VNTradingBrain_BookAugmentation_DecisionReceived.md
#
# EXTRACTION STATUS: FROZEN (unchanged 2026-07-05).
# Freeze condition: session count (1/10) is binding constraint.
# Resume condition: >= 5/10 sessions. One belief allowed as genuine by-product of a real /cortex session.
# See canonical sources.md for full freeze rationale.

### MUST-READ NOW (source cards — frozen for extraction until >=5/10 sessions)

| Book | Author | Gap filled |
|------|--------|------------|
| Trading and Exchanges: Market Microstructure for Practitioners | Larry Harris | Order book behavior, spreads, liquidity, transaction costs |
| Official VN market-structure regulations (HOSE/HNX/VSDC/SSC circulars) | — (regulatory) | The actual VN rulebook |
| Evidence-Based Technical Analysis | David Aronson | Statistical rigor, data-mining bias, OOS discipline |
| Systematic Trading | Robert Carver | System design, forecast scaling, risk targeting |
| Adaptive Markets | Andrew W. Lo | Why edges decay/re-emerge |
| Winning in Emerging Markets | Tarun Khanna & Krishna Palepu | Institutional voids, governance, disclosure quality |

---

## Book Queue (priority order — updated 2026-07-05)

**Bottleneck: session count (1/10) is the binding constraint, not SOURCED count (9/10 active).**

**Mandatory pre-check before any pre-registration** (per Advisor A + Fable council 2026-07-04):
1. Expressibility: Does the belief's independent variable actually vary within the system's constraints?
2. Claim fidelity: Is the backtest testing the book's actual claim, or a convenient proxy?

### Pipeline status (updated 2026-07-05)

| Belief | Book | Degeneracy pre-check | Pre-registered? | Pipeline status | Priority |
|--------|------|---------------------|-----------------|-----------------|----------|
| S1 — 52-week high proximity | O'Neil Ch.2 | DONE 2026-07-04: EXPRESSIBLE | YES — 2026-07-04_cortex_book2_s1_52wkhi_prereg.md | AWAITING HARNESS RUN (Cursor) | **IMMEDIATE** |
| S2 — 40%+ breakout volume | O'Neil Ch.2 | DONE 2026-07-04: LIKELY EXPRESSIBLE | YES — 2026-07-04_cortex_book2_s2_breakout_volume_prereg.md | AWAITING HARNESS RUN (Cursor) | **IMMEDIATE** |
| S5 — cut losses (judgment) | Loeb | N/A (Lane B) | N/A | LANE B — 1/3 sessions | **CONCURRENT** |
| S4 — Darvas box breakout | Darvas Ch.4 | DONE 2026-07-05: EXPRESSIBLE (VN-THIN pre-check required) | YES — 2026-07-05_cortex_book3_s4_darvas_box_prereg.md | VN-THIN PRE-CHECK PENDING (Cursor) | **MED — Book 3** |
| S6 — Kelly/entropy sizing | Stone | DONE 2026-07-05: UNCERTAIN-PENDING-EMPIRICAL | YES — 2026-07-05_cortex_xdisc_s6_stone_kelly_prereg.md (pre-check gates only) | DISTRIBUTIONAL PRE-CHECK PENDING (Cursor) | **MED — cross-discipline** |
| S7 — decision quality | Duke | N/A (Lane B) | N/A | LANE B + PA-001 pending | **CONCURRENT** |
| S8 — systems loops | Meadows | N/A (Lane B) | N/A | LANE B | **CONCURRENT** |
| S9 — explore/exploit | Algorithms | N/A (Lane B) | N/A | LANE B + PA-002 pending | **CONCURRENT** |
| S10 — bubble lifecycle | Kindleberger | N/A (Lane B) | N/A | LANE B | **CONCURRENT** |
| S3 — risk_pct cap | Minervini | DONE 2026-07-04: VN-SUBSUMED | N/A | PARKED | NONE |
| Exit rules | Minervini TTLAC | N/A | N/A | UNRESOURCED GAP | **HIGH** — mine exit chapters |
| PENDING batch (Harris, Aronson, etc.) | Various | N/A | N/A | FROZEN until >= 5/10 sessions | HIGH (post-freeze) |

### Next actions (post S1/S2 Cursor run)

1. S1/S2 verdicts → update knowledge.md (SOURCED → CALIBRATED or INVALIDATED per gates addenda)
2. S4 VN-THIN pre-check → if passes: write gates addendum → Cursor harness
3. S6 distributional pre-check → if passes: write sizing-sweep gates → Cursor harness
4. Exit rules gap — mine Minervini TTLAC sell/exit chapters
5. PENDING batch — after >= 5/10 sessions

---

## Book Completion Criteria (mandatory — added 2026-07-04 per Opus+Fable council)
[unchanged from canonical sources.md — see D:\V\.claude\brains\vn-trading-advisor\sources.md]

## Book completion log (updated 2026-07-05)

| Book | Author | Beliefs sourced | Terminal verdicts | Status | Notes |
|------|--------|-----------------|-------------------|--------|-------|
| Trade Your Way to Financial Freedom | Van Tharp | A3 (formerly S6) | A3: AXIOMATIC | **COMPLETE** | Only 1 belief sourced; reached terminal state AXIOMATIC. |
| Think and Trade Like a Champion | Mark Minervini | S3 | S3: VN-SUBSUMED | **IN PROGRESS** | Sizing claim processed. Exit beliefs NOT yet extracted. |
| How to Make Money in Stocks | William J. O'Neil | S1, S2 | None yet — pre-regs written, harnesses not run | **IN PROGRESS — Book 2 pipeline** | Gates addenda LOCKED. Awaiting Cursor. |
| How I Made $2,000,000 in the Stock Market | Nicolas Darvas | S4 | None yet — VN-THIN pre-check pending | **IN PROGRESS — Book 3 slot** | Formal degeneracy pre-check DONE 2026-07-05. |
| The Battle for Investment Survival | Gerald M. Loeb | S5 | None yet — Lane B (forward evidence) | **IN PROGRESS — Lane B** | Awaiting /cortex session accumulation. |
| Market Wizards (series) | Jack D. Schwager | A1 | A1: AXIOMATIC | **COMPLETE** | AXIOMATIC only — no Lane A beliefs. |
| Unknown Market Wizards (2024) | Jack D. Schwager | A2 | A2: AXIOMATIC | **COMPLETE** | AXIOMATIC only — no Lane A beliefs. |
| Information Theory (Stone) | Jim V. Stone | S6 | None yet — distributional pre-check pending | **IN PROGRESS — Cross-discipline** | Pre-check gates locked 2026-07-05. |
| Thinking in Bets (Duke) | Annie Duke | S7 | None yet — Lane B | **IN PROGRESS — Cross-discipline** | PA-001 generated 2026-07-05. |
| Thinking in Systems (Meadows) | Donella Meadows | S8 | None yet — Lane B | **IN PROGRESS — Cross-discipline** | Added 2026-07-05. |
| Algorithms to Live By | Christian & Griffiths | S9 | None yet — Lane B | **IN PROGRESS — Cross-discipline** | PA-002 generated 2026-07-05. |
| Manias, Panics, and Crashes | Kindleberger & Aliber | S10 | None yet — Lane B | **IN PROGRESS — Cross-discipline** | Added 2026-07-05. |
