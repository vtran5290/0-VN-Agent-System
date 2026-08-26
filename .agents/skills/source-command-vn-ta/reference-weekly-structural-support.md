# Weekly Structural Support, MA Compression & Role-Reversal Zones

**SSOT for weekly-chart analysis** used by `vn-ta-fireant`.  
Companion to `reference-mtf-structural-support.md` (monthly + general confluence) and  
`reference-support-vs-trend.md` (support score vs trend score, failed/reclaim, 2×2) and  
`reference-polarity-pivot-zone.md` (pivot zone first; polarity / role reversal).

**Core principle:**

> **A strong weekly level exists when multiple independent forms of market memory converge in the same price zone.**

Applies to: chart reviews, support/resistance detection, Wyckoff classification, stock ranking, automated screening.

---

## 1. Weekly chart purpose

Weekly charts answer:

1. Where is the intermediate-term structural support?
2. Is the stock building or repairing a base?
3. Is supply being absorbed?
4. Is a prior resistance level becoming support?
5. Is the stock in Phase C, Phase D, or Phase E?
6. Is the current pullback a healthy LPS/backup or structural failure?

Weekly charts sit between:

- Monthly = secular structure / major supply-demand
- Weekly = intermediate structure / Wyckoff / institutional base
- Daily = execution / exact entry / stop

---

## 2. Support is a zone, not an exact price

If a trader marks:

“61.7 is strong support”

do NOT interpret this as:

“61.700 must hold exactly.”

Instead determine the surrounding structural zone.

Example:

Representative level = 61.7

Actual support zone might be:

> **60.5–62.0**

The representative level is often simply the center, pivot, or visually important point inside a broader institutional support area.

---

## 3. Weekly MA compression / confluence

Calculate at minimum:

- SMA20W
- SMA50W
- SMA100W
- optional SMA200W
- EMA10W
- EMA20W

Identify **MA Compression Zones**.

Example:

- SMA20W = 61.25
- SMA50W = 61.35
- SMA100W = 60.60

These three moving averages are clustered within approximately 1–2%.

Interpretation:

> Multiple investment horizons are recognizing approximately the same equilibrium price.

This is more meaningful than one isolated MA.

Define:

```
MA_cluster_width = (max selected MA - min selected MA) / mean selected MA
```

Suggested interpretation:

- <2% = very tight confluence
- 2–4% = strong confluence
- 4–7% = moderate
- >7% = weak/no meaningful cluster

Score a support zone more highly when:

- multiple weekly MAs overlap,
- MAs are flat-to-rising,
- price is reclaiming them together,
- they overlap horizontal structure.

Do NOT automatically treat a tight MA cluster as bullish if all MAs are steeply declining.

---

## 4. Horizontal weekly pivots

Identify levels that repeatedly acted as:

- support,
- resistance,
- close clusters,
- breakout shelves,
- consolidation boundaries.

Use weekly closes and bodies more heavily than isolated intraday wicks.

Strong horizontal pivot characteristics:

- multiple reactions over several months,
- repeated weekly closes near the same zone,
- former resistance later acts as support,
- high historical trading activity around the zone.

A weekly pivot is stronger when the market repeatedly “accepts” price around it.

---

## 5. Role reversal

One of the strongest weekly structural signals is:

> resistance → breakout → retest → support.

Or:

> support → breakdown → reclaim → support again.

For every important level, ask:

1. Was this previously resistance?
2. Was it later broken?
3. Did price subsequently test it?
4. Did the market reject lower prices?
5. Has the zone changed role?

If yes, classify:

`ROLE_REVERSAL_SUPPORT`

This should receive more weight than an arbitrary MA touch.

---

## 6. Prior base boundary

Determine whether the zone corresponds to:

- upper boundary of a previous accumulation base,
- lower boundary of a recent re-accumulation,
- prior LPS,
- prior breakout shelf.

A level where price spent many weeks building a base has stronger market memory than a level created by only one candle.

Important distinction:

> **Base boundaries are areas of prior acceptance.**

The more time price previously spent there, the greater the probability that the zone matters again.

---

## 7. Origin of markup

Ask:

> “Where did the latest meaningful weekly markup begin?”

If price launched strongly from a zone and later returns there, identify it as:

`ORIGIN_OF_MARKUP`

Reasons it can matter:

- earlier accumulation may have occurred there,
- previous buyers may defend cost basis,
- missed buyers may see a second opportunity,
- old institutional demand may reappear.

Do NOT assume the zone will automatically hold.

Require price-volume confirmation.

---

## 8. Weekly volume behavior

For support analysis, distinguish:

### Healthy support test

- price approaches support,
- weekly volume contracts,
- spreads narrow,
- selling does not accelerate,
- lower wicks appear,
- subsequent rebound volume improves.

Interpretation:

> Potential supply exhaustion / absorption.

### Weak/no-demand condition

- volume contracts,
- but price continues falling easily,
- no meaningful rebound appears.

Interpretation:

> Low supply does NOT necessarily mean accumulation; demand may also be absent.

### Structural failure

- support breaks,
- weekly volume expands,
- wide bearish spread,
- close near weekly low,
- following week fails to reclaim.

Interpretation:

> Support failure confirmed.

---

## 9. Weekly close > intraweek wick

Give greater importance to:

- weekly close,
- weekly body,
- next-week confirmation,

than to an isolated intraday penetration.

Example:

Support zone = 60.5–62

Price trades to 59.8 intraday but closes week at 61.9:

This may still be a successful shakeout / support test.

Conversely:

Price briefly touches 61.7 but closes week at 59.5 on expanding volume:

Support likely failed.

Core doctrine:

> **How the week closes matters more than whether price briefly crosses an exact line.**

---

## 10. Weekly RSI / momentum reset

Use RSI14W as context.

Healthy intermediate correction:

- prior RSI >65–70,
- price corrects,
- RSI resets toward 40–55,
- price reaches structural support,
- RSI then stabilizes/reverses.

This can indicate:

> excess momentum has been removed without destroying long-term structure.

Do NOT use RSI as a standalone reversal signal.

---

## 11. Wyckoff weekly integration

Map the structure where possible:

### Phase C

- spring/shakeout,
- support test,
- failed breakdown.

### Phase D

- SOS,
- reclaim of MA cluster,
- price holds upper half of range,
- LPS forms.

### Phase E

- range high breaks,
- price accepts above pivot,
- volume confirms,
- retest holds.

Weekly support tests after SOS should be evaluated as possible:

`LPS / BACKUP`

A high-quality LPS typically has:

- shallower pullback,
- lower volume,
- holds former resistance,
- holds MA cluster,
- subsequent demand appears quickly.

---

## 12. Weekly structural support score

Score /100.

### A. MA Confluence — 20

- 2+ weekly MAs overlap: 8
- cluster width <4%: 5
- MAs flat/rising: 4
- price reclaiming cluster: 3

### B. Horizontal Pivot — 20

- repeated weekly reactions: 8
- multiple historical closes near zone: 6
- prior support/resistance significance: 6

### C. Role Reversal — 15

- prior resistance became support: 8
- breakout + successful retest: 7

### D. Prior Base / Origin of Markup — 15

- prior base boundary: 7
- origin of meaningful markup: 8

### E. Volume / Absorption — 20

- sell volume contracting: 6
- narrow downside spreads: 4
- no strong downside result despite selling effort: 4
- rebound volume improves: 6

### F. Momentum / Invalidation Quality — 10

- RSI reset without structural damage: 4
- clear invalidation level: 3
- next lower structural zone identifiable: 3

Classification:

- 85–100 = Exceptional weekly support
- 70–84 = Strong weekly support
- 55–69 = Moderate / under test
- 40–54 = Weak
- <40 = Not meaningful

---

## 13. Required weekly output

Whenever reviewing a weekly chart, output:

### Weekly Structure

- Trend:
- Current range/base:
- Current Wyckoff phase:

### Key Weekly Zones

For each zone:

- Representative level:
- Actual zone:
- MA cluster:
- Horizontal pivot:
- Role reversal:
- Prior base:
- Origin of markup:

### Volume / Supply-Demand

- Supply expanding or contracting?
- Demand confirmed or absent?
- Evidence of absorption?

### Weekly Close Test

- What weekly close would confirm support?
- What weekly close would invalidate support?

### Phase Interpretation

- Phase C / D / E
- SOS:
- LPS:
- breakout status:

### Structural Support Score

- X/100

### Final Verdict

Use one of:

- Strong weekly support
- Support under test
- LPS candidate
- Phase D support
- Role-reversal support
- Weak support
- Failed support

Include confidence:

Low / Medium / High.

---

## 14. Reference example — VCB

Use only as a teaching case.

Representative marked level:

61.7

Observed weekly confluence approximately:

- SMA20W ≈ 61.25
- SMA50W ≈ 61.35
- SMA100W ≈ 60.60

Therefore:

> The important structure is not exactly 61.7.

The relevant weekly zone is approximately:

> **60.5–62**

Reasons:

1. Tight MA20/50/100 weekly compression.
2. Historical horizontal pivot.
3. Prior support/resistance role reversal.
4. Current base boundary.
5. Price reclaiming the zone.
6. RSI weekly recovering into neutral/positive territory.

Bullish confirmation:

- weekly retest of 60.5–62,
- lower volume,
- rejection of lower prices,
- close back above the zone,
- subsequent continuation higher.

Failure:

- decisive weekly close below approximately 60–60.5,
- expanding volume,
- inability to reclaim,
- subsequent resistance at the broken support.

Then move analysis to the next lower structural zone.

---

## 15. Key weekly doctrines

Retain permanently:

> **Weekly support is a structural zone, not an exact number.**

> **A cluster of MA20/50/100 is more informative than one moving average.**

> **MA confluence is strongest when it overlaps horizontal market memory.**

> **Role reversal is one of the highest-quality forms of weekly support.**

> **A support test should produce a response; otherwise “no supply” may simply be “no demand.”**

> **Weekly close matters more than temporary intraday penetration.**

> **Volume decides whether the support is being absorbed or failing.**

> **Phase D support/LPS is much higher quality than blindly buying a falling stock at an MA.**

> **Zoom monthly to understand structural context, weekly to identify institutional support, and daily to execute.**
