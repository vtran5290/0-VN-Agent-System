# Support/Resistance Polarity, Role Reversal & Pivot-Zone Logic

**SSOT for polarity / role-reversal analysis** used by `vn-ta-fireant`.  
Companions: `reference-mtf-structural-support.md`, `reference-weekly-structural-support.md`, `reference-support-vs-trend.md`.

**Core doctrine:**

> **Support and resistance are often two states of the same structural pivot zone.**

And:

> **The zone itself is structural.  
> “Support” or “resistance” is contextual.**

---

## 1. Do not label a level too early

When identifying an important price zone, first classify it as:

`STRUCTURAL_PIVOT_ZONE`

before calling it support or resistance.

Only assign a directional role after asking:

1. Is current price above or below the zone?
2. From which side is price approaching?
3. Has price broken through the zone before?
4. Was that break accepted?
5. Has a retest occurred?
6. What was the price-volume response?

Example:

Zone = 21–22

Do NOT immediately say:

“21.5 is support.”

Instead say:

> “21–22 is a major weekly pivot zone.”

Then determine its current role.

---

## 2. Polarity principle

### Resistance → Support

Typical sequence:

1. Price repeatedly fails below zone.
2. Zone acts as resistance.
3. Price breaks above zone.
4. Breakout is accepted.
5. Price later pulls back.
6. Zone holds from above.
7. Price resumes upward.

Classification:

`ROLE_REVERSAL_SUPPORT`

Canonical structure:

> Resistance → Breakout → Retest → Support

---

### Support → Resistance

Typical sequence:

1. Price repeatedly holds above zone.
2. Zone acts as support.
3. Price breaks below zone.
4. Breakdown is accepted.
5. Price later rallies back.
6. Rally fails at the old support zone.
7. Price resumes downward.

Classification:

`ROLE_REVERSAL_RESISTANCE`

Canonical structure:

> Support → Breakdown → Retest → Resistance

---

## 3. A cross is not enough

Do not consider support/resistance role reversed merely because price crossed the level.

Require evidence of **acceptance**.

### Breakout acceptance

- daily/weekly close above zone,
- preferably multiple closes above,
- price spends meaningful time above,
- breakout not immediately reversed,
- volume behavior constructive.

### Breakdown acceptance

- close below zone,
- follow-through selling,
- price fails to reclaim,
- old support acts as resistance.

A wick through a level does NOT automatically create role reversal.

---

## 4. Retest is the real test

The highest-quality role reversal usually occurs on retest.

### Bullish retest

After breakout:

- price returns toward old resistance,
- volume contracts,
- downside spreads narrow,
- sellers fail to push price materially lower,
- price closes back above zone,
- demand returns.

Interpretation:

> Former resistance has become support.

This can be:

- breakout retest,
- backup,
- LPS,
- support confirmation.

### Bearish retest

After breakdown:

- price rallies toward old support,
- recovery volume is weak,
- price fails to reclaim zone,
- upper wicks/rejection appear,
- selling resumes.

Interpretation:

> Former support has become resistance.

---

## 5. Support/resistance is a zone, not a line

Never model polarity using exact single-price precision.

If a trader marks:

21.45

determine the actual zone, for example:

20.8–22.0

The exact marked price may simply be:

- center of zone,
- reference close,
- MA intersection,
- historical pivot,
- representative anchor.

The market reacts to areas of supply/demand, not exact decimals.

---

## 6. Determine current role by approach direction

For every structural pivot zone:

### If price approaches from below

Default interpretation:

> Resistance candidate.

Questions:

- Does price reject?
- Does volume expand on rejection?
- Can price close above?
- Is the breakout accepted?

### If price approaches from above

Default interpretation:

> Support candidate.

Questions:

- Does price bounce?
- Does selling volume contract?
- Does price close back above?
- Is the zone defended?

### If price oscillates through repeatedly

Interpretation:

> Equilibrium / acceptance zone.

Do NOT force support/resistance labels.

Possible classification:

`PIVOT / EQUILIBRIUM ZONE`

This means market has not yet established directional control.

---

## 7. Role-reversal quality score

Score a candidate role reversal /100.

### A. Historical Importance — 20

- repeated historical reactions: 8
- prior major support/resistance: 6
- multi-month/multi-year significance: 6

### B. Break Quality — 20

- decisive close through zone: 8
- volume confirmation: 6
- follow-through: 6

### C. Acceptance — 15

- multiple closes on new side: 8
- price remains on new side: 7

### D. Retest Quality — 25

- retest reaches zone cleanly: 5
- countertrend volume contracts: 7
- rejection from zone: 6
- continuation after retest: 7

### E. Higher-Timeframe Confluence — 20

- weekly/monthly MA cluster: 6
- prior base boundary: 5
- origin of markup/markdown: 5
- Wyckoff LPS/UT context: 4

Classification:

- 85–100: Exceptional role reversal
- 70–84: Strong
- 55–69: Moderate
- 40–54: Unconfirmed
- <40: Weak / noise

---

## 8. Failed role reversal

A breakout can fail.

Example:

Resistance 100  
→ breakout 102  
→ closes above briefly  
→ falls back below 100  
→ retest from below fails  

Interpretation:

> Failed breakout / bull trap.

The original resistance may become even stronger.

Likewise:

Support 100  
→ breakdown 98  
→ rapid reclaim 102  
→ holds above  

Interpretation:

> Failed breakdown / bear trap / potential spring.

Do not mechanically preserve the new role after failed acceptance.

---

## 9. Wyckoff integration

Role reversal should integrate with Wyckoff structure.

### Accumulation / Re-accumulation

Typical bullish sequence:

Range resistance  
→ SOS breakout  
→ pullback  
→ old resistance holds  
→ LPS  
→ Phase E  

The old resistance becoming support is one of the best signs that supply has been absorbed.

### Distribution / Re-distribution

Typical bearish sequence:

Range support  
→ Sign of Weakness  
→ rally  
→ old support becomes resistance  
→ LPSY  
→ markdown  

This is bearish role reversal.

---

## 10. Volume interpretation

Do not classify role reversal without volume context.

### Bullish role reversal

Ideal pattern:

Breakout: expanding volume, strong close.  
Retest: lower volume, smaller down bars.  
Continuation: volume improves again.

Meaning:

> Demand overwhelmed supply, then old supply dried up on retest.

### Bearish role reversal

Ideal pattern:

Breakdown: expanding sell volume.  
Retest: weak recovery volume.  
Rejection: selling increases again.

Meaning:

> Support failed and demand is insufficient to reclaim it.

---

## 11. Higher-timeframe priority

When a level exists on multiple timeframes:

Monthly pivot > weekly pivot > daily pivot > intraday pivot

But execution still occurs on lower timeframes.

Example:

Monthly zone 58–60  
+ Weekly role reversal at 59  
+ Daily retest at 59.2  

This is much stronger than a random daily support at 59.2.

---

## 12. Do not confuse pivot with support

### Structural Pivot Zone

A historically important area.

### Support

A pivot currently being approached/tested from above and successfully defended.

### Resistance

A pivot currently being approached/tested from below and successfully rejecting price.

Thus:

> **Support/resistance is a behavior, not only a location.**

---

## 13. Required output format for pivot-zone analysis

For each important zone, output:

### Structural Zone

- Representative level:
- Actual zone:
- Timeframe:
- Historical significance:

### Current Role

Choose:

- Support
- Resistance
- Role-reversal support
- Role-reversal resistance
- Equilibrium/pivot
- Unconfirmed

### Why

- approach direction:
- break history:
- acceptance:
- retest:
- volume behavior:
- higher-timeframe confluence:

### Confirmation

What price/volume behavior would confirm current role?

### Invalidation

What would prove current interpretation wrong?

---

## 14. Reference case — VCG

Use only as a teaching example.

Zone: approximately 21–22

Interpretation:

The zone has historically changed roles multiple times.

Possible sequence:

- old resistance,
- breakout shelf,
- later support,
- breakdown,
- subsequent resistance/pivot.

Therefore do NOT permanently label 21.45 as support.

Correct classification:

> “21–22 is a major weekly structural pivot / role-reversal zone.”

If price is below 21–22 and rallies into it:

> resistance candidate.

If price reclaims 21–22 and later retests from above:

> potential support.

The current role depends on price behavior, not the name originally assigned to the level.

---

## 15. Key doctrines

Retain permanently:

> **Support and resistance are contextual states of structural pivot zones.**

> **Resistance can become support after a successful breakout and retest.**

> **Support can become resistance after a successful breakdown and failed reclaim.**

> **A cross is not enough; acceptance and retest matter.**

> **The same level can change roles multiple times.**

> **Approach direction determines the current default role.**

> **Zone > line.**

> **Weekly close > intraday wick for weekly structure.**

> **Price-volume reaction determines whether role reversal is real.**

> **A failed breakout or breakdown can reverse the polarity again.**

> **Do not call something support merely because price once bounced there.**

> **Strong role reversal usually combines horizontal memory, higher-timeframe structure, volume confirmation, and successful retest.**

Integrate into: support/resistance detection, chart reviews, Wyckoff classification, breakout/retest logic, automated screening, structural support scoring, entry and invalidation analysis.
