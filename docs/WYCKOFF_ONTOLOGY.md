# WYCKOFF_ONTOLOGY — Core Definitions & Logic Gates

**Purpose:** Mathematical and structural definitions for Wyckoff events. Use this to guide the AI in identifying market phases and validating trade setups. Acts as advisor/sparring partner for technical signals (Richard Wyckoff).

---

## 1. Structural Definitions (The Trading Range — TR)

A **Trading Range (TR)** is the price action between **Resistance (AR)** and **Support (SC)**.

| Term | Full Name | Quantitative Logic |
|------|-----------|--------------------|
| **SC** | Selling Climax | Volume > 2.0× SMA(20) AND Spread > 1.5× ATR AND Close > Low (long lower wick). Marks the temporary bottom. |
| **AR** | Automatic Rally | The highest point reached immediately following an SC. Usually driven by short-covering. Defines the top of the TR. |
| **ST** | Secondary Test | Price returns to SC area on lower volume and narrower spread. Validates that supply is decreasing. |
| **TR_Width** | TR Range | AR_High − SC_Low. Use for Cause and price targets. |

---

## 2. Phase-Based State Machine

Track the **State** of the stock. A setup is valid only if the stock has progressed through these phases:

### Phase A: Stopping the Trend

- **Entrance:** Prevailing downtrend (Price < MA200).
- **Events:** Preliminary Support (PS) → SC → AR → ST.
- **Exit:** Once AR high is established, the "Trading Range" state begins.

### Phase B: Building the Cause

- **Logic:** Price fluctuates between AR and SC.
- **Goal:** Supply absorption.
- **Indicator:** Volume should generally trend downward. Any Upthrusts (UT) within Phase B must be met with immediate rejection.

### Phase C: The Test (The Setup)

- **The Spring (Bear Trap):**
  - Price < SC_Low (breaks support).
  - Volume < SC_Volume (supply exhaustion).
  - **Logic gate:** Must reclaim SC_Low within N bars (usually 3–8).

### Phase D: Trend Confirmation (The Trigger)

- **SOS (Sign of Strength):** High-volume move from bottom of TR to top.
- **JAC (Jump Across the Creek):** Close > AR_High with Volume > 1.5× SMA(20).
- **LPS (Last Point of Support):** Shallow pullback to AR level (now support) on very low volume.

---

## 3. The 3 Laws (Implementation Logic)

### Law 1: Supply and Demand

- **Bullish:** Volume_UpBars > Volume_DownBars AND Price_Closes > Midpoint.
- **Bearish:** Volume_DownBars > Volume_UpBars AND Price_Closes < Midpoint.

### Law 2: Cause and Effect

- **Horizontal Count:** Count bars in Phase B and Phase C.
- **Target:** Target = TR_Low + (Number_of_Bars × Point_Value). (Simplified P&F logic.)

### Law 3: Effort vs. Result (Divergence Check)

- **Anomaly 1:** Volume == Ultra_High BUT Spread == Narrow → Hidden supply/demand; high probability of reversal.
- **Anomaly 2:** Price == New_High BUT Volume < Previous_High_Volume → Buying exhaustion.

---

## 4. Engine Config: W4 (Pro-Logic)

Config lives in `minervini_backtest/configs/W4_Advanced.yaml`. Summary:

- **Logic engine:** State_Machine.
- **Thresholds:** climax_vol 2.5×, climax_spread 2.0× ATR, test_vol_max 0.8, recovery_window 5 bars.
- **Sequence validation:** SC (required) → AR (required) → SPRING (preferred) → JAC (trigger).
- **Risk:** stop = 0.5× ATR below Spring_Low; R-multiple target 3.0; break-even when price touches Phase D SOS high.
- **Exits:** SOW (Sign of Weakness), BC (Buying Climax) per defined logic.

---

## 5. Instructions for Cursor (System Prompt Add-on)

When analyzing a chart or coding a strategy using **Wyckoff Brain**:

1. **Identify the TR:** Locate SC and AR to define boundaries.
2. **Determine the Phase:** State whether Phase B (Accumulation) or Phase D (Mark-up).
3. **Check Effort vs Result:** Compare breakout volume to price spread — "Squat" bar vs "Thrust"?
4. **Validate the Spring:** If price breaks support, check volume. High volume → warn "Fall through the ice" (bearish). Low volume → alert "Spring" (bullish).
5. **T+2.5 Logic (VN):** For a Trigger, ensure the Cause (Phase B) is at least 3× the duration of the expected T+3 move for liquidity risk.

---

## 6. Pipeline Mapping (Engine Integration)

| Layer | Wyckoff equivalent |
|-------|----------------------|
| **Filter** | Phase / structure (downtrend stopped, TR established) |
| **Setup** | Accumulation pattern: SC → AR → ST; Phase B with volume downtrend |
| **Trigger** | Spring (reclaim within N bars) or JAC / SOS / LPS |
| **Risk** | Stop below Spring_Low (0.5× ATR); R-multiple target |
| **Exit** | SOW, BC, or break of key level |

---

## 7. VN Adaptation

- **Liquidity:** Cause (Phase B) duration should be ≥ 3× expected holding period; thin names need wider recovery_window.
- **Data:** FireAnt OHLCV; use same schema as vn-ta-fireant skill (`wyckoff.events`, `wyckoff.phase`).
- **Sparring:** When user asks "is this a valid Wyckoff setup?", validate sequence (SC → AR → Spring/JAC) and Effort vs Result before confirming.
