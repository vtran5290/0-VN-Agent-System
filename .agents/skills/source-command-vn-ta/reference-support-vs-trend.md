# Market Memory, Reclaim Quality & Support-vs-Stock Distinction

**SSOT for two-axis evaluation** used by `vn-ta-fireant`.  
Companions: `reference-mtf-structural-support.md`, `reference-weekly-structural-support.md`, `reference-polarity-pivot-zone.md`.

**Key doctrine:**

> **Support strength and stock trend quality are separate dimensions and must be scored separately.**

Do NOT equate:

> “Strong support” = “Strong stock”

or:

> “Price is at support” = “Good entry”.

Applies to: TA reviews, stock ranking, market-structure analysis, support detection, Wyckoff classification, screening.

---

## 1. Two-dimension framework

Every chart must be evaluated on two independent axes.

### AXIS A — STRUCTURAL SUPPORT QUALITY

Question:

> “How meaningful is this price zone as historical demand / equilibrium / market memory?”

Consider:

- horizontal pivots,
- MA confluence,
- prior base,
- origin of markup,
- role reversal,
- repeated acceptance,
- historical reactions.

### AXIS B — TREND / STOCK QUALITY

Question:

> “How strong is the stock’s current trend and probability of continuation?”

Consider:

- price vs MA20/50/100/200,
- MA slope,
- relative strength,
- higher-high/higher-low structure,
- volume confirmation,
- momentum,
- overhead supply,
- position inside current range.

Always report both.

Example:

VCI:

- Structural support quality: High
- Trend quality: Medium

PC1:

- Structural support quality: Good
- Trend quality: High

Therefore:

> PC1 may be the better trade even if VCI has the stronger historical support zone.

---

## 2. Market memory

Define “market memory” as a zone where price historically spent significant time, reacted repeatedly, or launched major moves.

Strong market-memory zones often include:

- repeated weekly/monthly closes,
- old resistance,
- old support,
- major congestion,
- accumulation base,
- breakout shelf,
- prior LPS,
- origin of markup.

Market memory should be weighted more heavily than:

- one isolated wick,
- one moving average touch,
- arbitrary round numbers.

---

## 3. Market acceptance vs rejection

For each price zone, determine whether the market historically:

A. ACCEPTED the price  
or  
B. REJECTED the price.

### Acceptance

Signs:

- many weekly/monthly closes near the zone,
- repeated sideways trading,
- multiple body overlaps,
- price repeatedly returns to the same level.

Interpretation:

> strong equilibrium / market memory.

### Rejection

Signs:

- one sharp wick,
- immediate reversal,
- little time spent at the level.

Interpretation:

> possibly important reaction zone, but weaker market memory.

Prefer acceptance zones for structural support.

---

## 4. Failed support must be downgraded

A major upgrade:

Do NOT keep calling a level “strong support” after price has decisively broken it.

If a zone:

- was support,
- was broken on strong volume,
- price accepted below it,

then downgrade status to:

`FAILED_SUPPORT`

Do NOT assume it will automatically support price again.

To regain support status, require:

1. price reclaims the zone;
2. closes above it on weekly/monthly basis;
3. subsequent retest holds;
4. ideally volume contracts on retest.

Then upgrade to:

`RECLAIMED_SUPPORT`

or:

`ROLE_REVERSAL_RECLAIM`.

---

## 5. Reclaim quality

Score reclaim quality separately.

A HIGH-QUALITY RECLAIM has:

- decisive close above broken level,
- strong volume or strong spread,
- multiple closes above,
- retest on lower volume,
- support response after retest.

A LOW-QUALITY RECLAIM has:

- one weak close above,
- immediate rejection,
- price remains below key MAs,
- no volume confirmation.

Interpretation:

> reclaim quality tells whether the market has truly accepted the level again.

---

## 6. Prior breakout shelf

Identify zones where:

- price consolidated,
- then broke out strongly,
- later returned to the breakout area.

These zones are especially important when they overlap:

- weekly SMA20/50,
- monthly SMA10/20,
- prior LPS,
- high-volume base.

Classify as:

`BREAKOUT_SHELF_SUPPORT`

The first successful retest after breakout often has high continuation value.

---

## 7. Origin of markup

Identify the zone where the prior major markup began.

A strong origin-of-markup zone usually has:

- prior accumulation/consolidation,
- sudden price expansion,
- increased volume,
- sustained trend afterward.

When price returns:

Do NOT automatically buy.

Instead ask:

- Is selling volume contracting?
- Is price stabilizing?
- Is the zone still above long-term trend support?
- Is there a reclaim / response?

Origin-of-markup is a strong reference zone, not a guaranteed floor.

---

## 8. Multi-timeframe MA clusters

Weekly MA clusters:

- SMA20W
- SMA50W
- SMA100W

Monthly MA clusters:

- SMA10M
- SMA20M
- SMA50M

Compute:

```
MA_cluster_width = (max(MA values) - min(MA values)) / mean(MA values)
```

Interpretation:

- <2% = exceptional
- 2–4% = strong
- 4–7% = moderate
- >7% = weak

But do NOT score highly if all MAs are falling sharply.

A cluster is strongest when:

- flat or rising,
- overlaps horizontal pivot,
- overlaps prior base,
- price reclaims it.

---

## 9. Support zone hierarchy

Rank support zones in this order:

### Tier 1 — Major Structural Support

Confluence of:

- monthly/weekly market memory,
- role reversal,
- origin of markup,
- MA cluster.

### Tier 2 — Intermediate Structural Support

Confluence of:

- weekly pivot,
- weekly MA cluster,
- breakout shelf,
- prior base.

### Tier 3 — Tactical Support

Daily MA / short-term swing / recent low.

Do not confuse Tier 3 support with Tier 1 structural support.

---

## 10. “Support under test” vs “Support confirmed”

When price is inside a support zone, classify:

`SUPPORT_UNDER_TEST`

Do NOT call it confirmed.

Confirmation requires:

- rejection of lower prices,
- weekly/monthly close above zone,
- volume stabilization,
- subsequent upside response.

Use:

`SUPPORT_CONFIRMED`

only after price shows demand response.

---

## 11. Strong support does not mean strong stock

This distinction must be explicit in every review.

Example:

A stock can have:

- Strong structural support
- Weak trend
- Poor relative strength
- Heavy overhead supply

That is NOT automatically a good trade.

Conversely:

A stock can have:

- Moderate support
- Strong trend
- Strong RS
- Clean breakout/retest

and be a better trade.

Always score:

STRUCTURAL SUPPORT SCORE  
and  
TREND QUALITY SCORE

separately.

---

## 12. Support Quality Score — 100

### A. Market Memory — 25

- repeated historical reactions: 10
- acceptance / multiple closes: 10
- multi-year relevance: 5

### B. MA Confluence — 20

- multi-MA overlap: 8
- cluster width tight: 5
- MAs flat/rising: 4
- price reclaiming cluster: 3

### C. Role Reversal / Reclaim — 20

- old resistance → support: 8
- broken support successfully reclaimed: 6
- successful retest: 6

### D. Prior Base / Origin of Markup — 15

- base boundary: 7
- origin of major markup: 8

### E. Volume / Absorption — 15

- declining sell volume: 5
- failed breakdown / lower wick: 5
- rebound confirmation: 5

### F. Invalidation Clarity — 5

- clear fail level: 3
- next support identifiable: 2

---

## 13. Trend Quality Score — 100

### A. Price vs MAs — 25

- above MA20/50/100/200: 10
- proper alignment: 10
- long MA rising: 5

### B. Structure — 20

- higher highs/lows: 10
- current base holds: 5
- limited overhead supply: 5

### C. Relative Strength — 20

- outperforming benchmark: 10
- RS rising: 5
- RS near highs: 5

### D. Volume/Money Flow — 20

- volume expands on up moves: 10
- contracts on pullbacks: 5
- OBV/CMF positive: 5

### E. Momentum / Entry Position — 15

- RSI/momentum healthy: 5
- not extended: 5
- close to actionable pivot/LPS: 5

---

## 14. Final 2x2 matrix

Classify every stock into one of four boxes.

### A. Strong Support + Strong Trend

Highest-quality setups.

Example:

- leader testing breakout shelf,
- MA cluster rising,
- volume dry-up.

Action: High priority.

### B. Strong Support + Weak Trend

Potential turnaround / accumulation candidate.

Action: Watch for demand confirmation.

Do NOT buy only because support is strong.

### C. Weak Support + Strong Trend

Momentum stock with less structural cushion.

Action: Tradeable but risk control important.

### D. Weak Support + Weak Trend

Low priority / avoid.

Threshold guidance (unless overridden by judgment):

- Support Strong if Support Score ≥ 70; Weak if &lt; 55 (55–69 = treat as Weak for matrix unless confirmed response).
- Trend Strong if Trend Score ≥ 70; Weak if &lt; 55 (same mid-band rule).

---

## 15. Weekly vs monthly priority

When weekly and monthly disagree:

MONTHLY: defines structural support.

WEEKLY: defines whether the stock is actually repairing / accumulating.

DAILY: defines execution.

Example:

Monthly VCI: strong support around 25–27.

Weekly VCI: trend still neutral/weak.

Correct conclusion:

> Strong structural support, but demand confirmation still missing.

Do NOT say:

> “Strong buy because monthly support is strong.”

---

## 16. Volume response rule

Support is only meaningful if it produces price response.

### Case A

Selling volume falls + price stabilizes + subsequent rally appears → bullish absorption.

### Case B

Selling volume falls + price continues drifting lower → no demand.

### Case C

Selling volume expands + support breaks → support failure.

### Case D

Large selling effort + little downside result + quick reclaim → possible absorption / shakeout.

---

## 17. Monthly confirmation

On monthly charts, emphasize:

- monthly close,
- body position,
- volume,
- response next month.

A temporary intramonth break below support does NOT invalidate the zone.

A decisive monthly close below the zone with expanding volume is much more important.

---

## 18. Weekly confirmation

On weekly charts, emphasize:

- weekly close,
- retest quality,
- volume trend,
- number of closes above/below support.

One isolated wick should not override structure.

---

## 19. Required output format

Whenever reviewing a marked support level:

### Structural Zone

- Representative level:
- Actual zone:

### Market Memory

- Historical acceptance:
- Prior support/resistance:
- Prior base:
- Origin of markup:

### MA Confluence

- Weekly MAs:
- Monthly MAs:
- Cluster width:
- MA slope:

### Reclaim / Role Reversal

- Was the level previously broken?
- Has it been reclaimed?
- Has retest succeeded?

### Volume / Absorption

- Supply expanding or contracting?
- Demand response confirmed?

### Support Score

- X/100

### Trend Score

- X/100

### 2x2 Classification

- Strong Support + Strong Trend
- Strong Support + Weak Trend
- Weak Support + Strong Trend
- Weak Support + Weak Trend

### Final Verdict

Use one:

- Exceptional structural support
- Strong structural support
- Support under test
- Reclaimed support
- Role-reversal support
- LPS candidate
- Failed support
- Weak / non-structural support

Confidence: Low / Medium / High.

---

## 20. Reference cases

### VCG

Approximate structural zone: 20–21.5

Interpretation:

- historically meaningful;
- but prior support was broken;
- price later traded materially below;
- therefore support quality must be downgraded until reclaimed.

Correct label:

`FAILED_SUPPORT → RECLAIM_ATTEMPT`

Not:

`STRONG_SUPPORT`

---

### PC1

Approximate zone: 25.5–26.8

Interpretation:

- prior breakout shelf,
- strong underlying trend,
- price above longer MAs,
- potential LPS / backup.

Correct label:

`STRONG_TREND + GOOD_SUPPORT`

Higher trade quality than many turnaround charts.

---

### VCI WEEKLY

Approximate zone: 25.8–27.3

Interpretation:

- SMA20/50/100 cluster,
- prior base,
- origin of markup,
- current equilibrium.

Correct label:

`STRONG_SUPPORT + NEUTRAL TREND`

Requires demand confirmation.

---

### VCI MONTHLY

Approximate zone: 25–27

Interpretation:

- multi-year market memory,
- SMA10/20M confluence,
- prior breakout shelf,
- origin of major markup.

Correct label:

`MAJOR_MONTHLY_STRUCTURAL_SUPPORT`

But do NOT automatically classify the stock as strong.

---

## 21. Key doctrines

Retain permanently:

> **Strong support is not the same as strong stock.**

> **Market memory matters more than one isolated MA.**

> **A broken support must be downgraded until successfully reclaimed.**

> **Reclaim + retest is stronger evidence than merely touching support.**

> **Repeated acceptance is more important than a single wick.**

> **Origin of markup is a demand reference, not a guaranteed floor.**

> **Monthly defines structural support; weekly defines repair/accumulation; daily defines execution.**

> **Support must eventually produce positive price response.**

> **No-supply without demand is not bullish.**

> **A good structural zone can still be a poor trade if trend quality is weak.**
