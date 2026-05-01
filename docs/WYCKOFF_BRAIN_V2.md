# WYCKOFF_BRAIN v2.0 — The Institutional Flow Engine

**Core Philosophy:** Price is an advertisement. Volume is the truth. We only trade when the **Composite Man** (Institutional Money) has finished absorbing supply and is ready to mark up the price.

---

## 1. The VSA (Volume Spread Analysis) Engine

Cursor must understand the relationship between **Spread** (High minus Low) and **Volume**. This is the **Effort vs. Result** law in action.

| VSA Signal | Logic for Cursor (The Math) | Meaning |
|------------|-----------------------------|---------|
| **Stopping Volume** | Price_Down AND Volume > 2.5× SMA20 AND Long_Lower_Wick | Smart Money is "catching" the falling knives. |
| **No Supply Test** | Narrow_Spread AND Close_in_Mid AND Volume < 50% of SMA20 | The bears are exhausted. Path is clear for uptrend. |
| **Squat Bar** | High_Volume AND Narrow_Price_Spread | Effort without result. A "hidden" reversal is happening. |
| **Effort to Rise** | Wide_Spread_Up AND Volume > 1.5× SMA20 | Institutional "Markup" is confirmed. |

---

## 2. The Deterministic State Machine (The 5 Phases)

To prevent Cursor from calling every dip a "Spring," enforce **Sequential Validation** gates.

### Phase A: Stopping the Previous Trend

- **Gate 1 (SC):** Volume must be the **highest in 50 bars**. Marks the Selling Climax.
- **Gate 2 (AR):** A fast rally of **> 5%** from the SC low. Sets the Resistance Ceiling.
- **Gate 3 (ST):** Price returns to SC area. Volume must be **lower than SC**. If higher, the floor is still "wet."

### Phase B: Building the Cause (The Absorption)

- **Logic:** Price stays between AR (High) and SC (Low).
- **Validation:** Look for **Upthrusts (UT)** at the AR level that fail—Composite Man testing how much supply is left.

### Phase C: The Test (The Professional Entry)

- **The Spring:** Must break the SC support level.
- **Validation:** **Price_Recovery** back into the TR within **5 bars**. If it stays below → "Fall through the Ice" (Bearish).

### Phase D: The Markup (The Trend Confirmation)

- **SOS (Sign of Strength):** The "Jump Across the Creek."
  - **Logic:** Close > AR_High with high conviction (Spread & Volume).
- **LPS (Last Point of Support):** The first pullback to the old AR high. Volume must be **ultra-low**.

---

## 3. Upgraded Config: W2 (Institutional Signature)

```yaml
# W2 — Deterministic Wyckoff Engine
name: W2_Institutional_Flow
logic_gate: Sequential_Event_Validation

# Event Definitions for AI Calculation
events:
  sc_climax: "Vol > 3.0 * SMA20 AND Spread > 2.0 * ATR"
  spring_test: "Price < TR_Support AND Vol < 0.7 * SC_Vol"
  sos_thrust: "Close > TR_Mid AND Spread > 1.5 * ATR AND Vol > 1.2 * SMA20"

# Structural Constraints
constraints:
  min_tr_duration: 60        # Bars (Law of Cause and Effect)
  max_tr_volatility: 0.20    # 20% height max to ensure tight absorption
  rs_index_trend: rising     # Relative Strength vs Market must be improving

# Trigger: The "Jump"
trigger:
  type: JAC_LPS_Combo        # Buy the first pullback after the breakout
  entry_point: Retest of AR_Level
  confirmation: Low_Vol_Doji on Support

# Exit Strategy (Phase E)
exits:
  - event: Buying_Climax     # Vertical move, exhausted buyers
    logic: "Price > 2.5 * ATR above MA20 AND Vol Spike"
  - event: SOW_Break         # Sign of Weakness
    logic: "First down-bar that is larger than previous 10 up-bars"
```

---

## 4. The "Composite Man" Sparring Prompts

When using Cursor, force it to think like the manipulator:

1. **"Where is the Liquidity?"**  
   "Cursor, find the high-volume zones below the support. Is the current Spring deep enough to hit the stop-losses of retail traders?"

2. **"Who is Winning the Bar?"**  
   "In the last 5 candles, is the Volume increasing on the Up-moves or the Down-moves? Show me the 'Effort vs. Result' divergence."

3. **"Is the Creek Jumpable?"**  
   "Analyze the resistance level (The Creek). Is the volume of the current attack high enough to clear the 'hanging supply' from Phase B?"

---

## 5. Vietnam Market "Lái" Adaptation (The Washout)

In the VN market (VNI), **Springs are often more violent (Washouts)**.

- **Logic upgrade:** At VNI, a Spring often undercuts support by **5–7%** due to low liquidity and high margin-call pressure.
- **T+2.5 filter:** Never buy the Spring bar itself. Only buy the **"Test of the Spring"**—the second successful tap of the low on low volume. This avoids getting caught in a "Falling Ice" scenario during the T+2.5 waiting period.

---

## 6. Final Check Before Handoff

| Item | v2.0 Status |
|------|------------|
| **Definitions** | SC, AR, ST, Spring, SOS, LPS are defined by **math** (Vol, Spread, ATR), not just names. |
| **Logic** | Cursor follows a **sequence** (A → B → C → D). |
| **VSA** | Every candle is analyzed for **internal health** (Effort vs. Result). |
