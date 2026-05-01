---
name: vn-ta-fireant
description: Analyze Vietnamese stocks using FireAnt OHLCV data and generate fact-grounded technical JSON reports (Wyckoff, volume profile, trade plan). Use when the user asks for VN stock technical analysis, FireAnt-based TA, or structured JSON outputs for Vietnamese tickers.
---

# VN Technical Analysis via FireAnt

## When to use this skill

Use this skill when:
- The user asks for **technical analysis of Vietnamese stocks** (HOSE/HNX/UPCoM).
- The user mentions **FireAnt**, **OHLCV**, **Wyckoff**, **VSA**, **volume profile (VP/VPVR)**, **MA/OBV/CMF/MACD**, or wants a **JSON technical report**.
- The user provides **1 or more tickers** and wants **fact-based**, **non‑hallucinated** technical output with clear price levels and trade plans.

Scope: short- to medium‑term swing/position analysis on **daily + weekly** timeframes using FireAnt OHLCV and (optionally) VNINDEX for context.

---

## Inputs (skill contract)

Normalize inputs into this internal request object (even if the user gives a looser prompt):

```json
{
  "tickers": ["VCI", "HCM"],
  "asof_date": "YYYY-MM-DD",
  "horizon_days": 90,
  "timeframes": ["D", "W"],
  "risk_mode": "conservative",          // or "standard", "aggressive"
  "vp_bins": 100,
  "value_area_pct": 0.7                 // 70% volume around POC
}
```

Defaults if user does not specify:
- **asof_date**: today (system date).
- **horizon_days**: 260 (≈ 1 year of daily data).
- **timeframes**: `["D", "W"]`.
- **risk_mode**: `"standard"`.
- **vp_bins**: `100`.
- **value_area_pct**: `0.7`.

For testing multiple tickers (e.g. `VCI, HCM, MBS, VND, REE, ANV, NT2`), treat `tickers` as an array and produce one JSON object per ticker (or a list of such objects) while **preserving the same schema per ticker**.

---

## Outputs (schema + failure modes)

For **each ticker**, return a **single JSON object** with this schema. Do not wrap with explanations or extra text.

### Core analysis object

```json
{
  "ticker": "...",
  "asof": "YYYY-MM-DD",
  "data": {
    "timeframes": {
      "D": {"bars": 0, "start": null, "end": null, "adjusted": false},
      "W": {"bars": 0, "start": null, "end": null, "adjusted": false}
    }
  },
  "levels": {
    "support_zones": [
      {
        "price_low": 0.0,
        "price_high": 0.0,
        "basis": ["VP:VAL", "SwingLow", "HVN", "MA50"],
        "confidence": "low"
      }
    ],
    "resistance_zones": [
      {
        "price_low": 0.0,
        "price_high": 0.0,
        "basis": ["VP:VAH", "SwingHigh", "HVN", "Gap"],
        "confidence": "low"
      }
    ],
    "key_inflection_levels": [
      {
        "price": 0.0,
        "why": "..."
      }
    ]
  },
  "trend_regime": {
    "daily": {
      "state": "range",
      "ma_stack": "...",
      "price_vs_ma": {}
    },
    "weekly": {
      "state": "range",
      "ma_stack": "...",
      "price_vs_ma": {}
    },
    "regime_summary": "..."
  },
  "price_action": {
    "tightness": {
      "last_10d_range_pct": 0.0,
      "last_5d_close_stdev_pct": 0.0,
      "interpretation": "tight"
    },
    "bar_shape_notes": ["..."],
    "gaps": [
      {
        "date": "...",
        "type": "gap_up",
        "gap_pct": 0.0,
        "follow_through": "yes"
      }
    ]
  },
  "volume_action": {
    "volume_context": {
      "vol_vs_sma20": 1.0,
      "vol_vs_sma50": 1.0
    },
    "vsa_signals_recent": [
      {
        "date": "...",
        "signal": "demand",
        "evidence": "..."
      }
    ],
    "distribution_score": {
      "lookback_days": 25,
      "heavy_down_days": 0,
      "heavy_up_days": 0,
      "interpretation": "neutral"
    }
  },
  "volume_profile": {
    "long_260d": {
      "poc": [0.0, 0.0],
      "vah": [0.0, 0.0],
      "val": [0.0, 0.0],
      "hvn": [[0.0, 0.0], [0.0, 0.0]],
      "lvn": [[0.0, 0.0], [0.0, 0.0]]
    },
    "mid_90d": {
      "poc": [0.0, 0.0],
      "vah": [0.0, 0.0],
      "val": [0.0, 0.0],
      "hvn": [[0.0, 0.0], [0.0, 0.0]],
      "lvn": [[0.0, 0.0], [0.0, 0.0]]
    },
    "short_30d": {
      "poc": [0.0, 0.0],
      "vah": [0.0, 0.0],
      "val": [0.0, 0.0],
      "hvn": [[0.0, 0.0], [0.0, 0.0]],
      "lvn": [[0.0, 0.0], [0.0, 0.0]]
    },
    "vp_read": [
      "Explain supply/overhead based on HVN above price",
      "Explain acceptance/rejection around VAH/VAL",
      "Explain likelihood of breakout vs mean reversion"
    ]
  },
  "indicators": {
    "ma": {
      "ma20": 0.0,
      "ma50": 0.0,
      "ma100": 0.0,
      "ma200": 0.0,
      "slope_ma50": "flat"
    },
    "obv": {
      "state": "flat",
      "divergence": "none",
      "evidence": "..."
    },
    "cmf20": {
      "value": 0.0,
      "state": "neutral"
    },
    "macd_12_26_9": {
      "macd": 0.0,
      "signal": 0.0,
      "hist": 0.0,
      "state": "turning",
      "notes": "..."
    }
  },
  "wyckoff": {
    "phase": "unclear",
    "schematic_guess": "unclear",
    "events": {
      "ps": {"present": false, "why": "..."},
      "sc": {"present": false, "why": "..."},
      "ar": {"present": false, "why": "..."},
      "st": {"present": false, "why": "..."},
      "spring": {"present": false, "why": "..."},
      "sos": {"present": false, "why": "..."},
      "lps": {"present": false, "why": "..."}
    },
    "logic": ["..."]
  },
  "trade_plan_1_3m": {
    "bias": "neutral",
    "trigger": {
      "type": "breakout",
      "price": 0.0,
      "conditions": ["..."]
    },
    "invalidations": [
      {
        "price": 0.0,
        "why": "..."
      }
    ],
    "risk": {
      "atr14": 0.0,
      "suggested_stop_atr_mult": 1.5,
      "position_size_hint": "risk 0.5%-1% equity"
    },
    "targets": [
      {
        "price": 0.0,
        "basis": ["VP HVN", "prior swing high"]
      }
    ],
    "what_to_watch_next": ["..."],
    "setup_type": "base_breakout",
    "entry_model": "stop_order",
    "stop_model": "atr_trailing",
    "add_on_rules": ["..."],
    "sell_signals": ["..."]
  },
  "confidence": {
    "overall": "low",
    "why": ["..."]
  },
  "notes": ["..."],
  "evidence_map": [
    {
      "type": "demand_bar",
      "date": "...",
      "value": "...",
      "comment": "..."
    }
  ],
  "data_integrity": {
    "missing_bars": 0,
    "missing_pct": 0.0,
    "median_value_traded": 0.0,
    "liquidity_flag": "ok",        // "ok" | "thin" | "very_thin"
    "adjusted": false,
    "adjustment_notes": "adjusted/unadjusted status and caveats"
  },
  "warnings": ["..."],
  "errors": ["..."]
}
```

### Failure / partial data behavior

- **Never hallucinate data.** If a metric cannot be computed, set it to `null`, `"not available"`, or an empty list as appropriate, and explain briefly in `warnings` or `data_integrity`.
- If FireAnt or network fails for a ticker, return a JSON object with:
  - `"errors"` containing the failure reason (best effort).
  - `"data.timeframes"` zeroed/empty.
  - All other sections filled with safe defaults and `"overall"` confidence `"low"`.
- Always ensure the **JSON shape is valid** (all top-level keys present) even on partial failures.

---

## Data sources and hygiene

### 1. FireAnt OHLCV and helpers

- Prefer using the existing helper in this repo:
  - `src/canslim/fireant_fetcher.py` → `fetch_ohlcv(symbol, start, end, resolution="D"|"W")`.
- For index context (VNINDEX/VN30), reuse:
  - `scripts/fetch_vietnam_market.py` (VNINDEX/VN30 levels) if helpful for relative strength.

### 2. Timeframes and lookbacks

- **Daily (`D`)**:
  - Fetch at least the last **260 trading days** up to `asof_date`.
- **Weekly (`W`)**:
  - Either call `fetch_ohlcv(..., resolution="W")` or resample daily → weekly as implemented in `fireant_fetcher`.

If fewer bars are returned than requested, record this in `data_integrity.missing_bars` and reduce confidence accordingly.

### 3. Liquidity and anomalies (UPCoM/HNX etc.)

- Compute **median daily traded value** if possible:
  - If only volume is available, at least compute `median(volume * close)` as a proxy.
- Set `data_integrity.liquidity_flag`:
  - `"ok"` if median value traded ≥ reasonable threshold (e.g. 5e9 VND; choose a consistent default).
  - `"thin"` if below threshold but still usable.
  - `"very_thin"` if extremely illiquid or many zero-volume bars.
- In `"warnings"`, add messages for:
  - Very thin liquidity.
  - Unusual volume spikes without price movement (possible data issues).

### 4. Adjusted vs unadjusted

- If FireAnt returns an **adjusted series** and this can be detected, set `"adjusted": true` in `data.timeframes`.
- If not clear, assume **unadjusted**, set `"adjusted": false`, and add a warning:
  - e.g. `"Price series likely unadjusted; MA/VP may be distorted by splits/dividends."`

---

## Indicator definitions (must be consistent)

- **MAs on close**:
  - `MA20`, `MA50`, `MA100`, `MA200`: simple moving average.
  - `EMA21`, `EMA50`: exponential MA (if needed).
- **ATR14**: Wilder ATR on the chosen timeframe.
- **OBV**: standard cumulative On-Balance Volume.
- **CMF20**: 20‑period Chaikin Money Flow.
- **MACD(12,26,9)**:
  - MACD line = EMA12 − EMA26.
  - Signal line = EMA9(MACD).
  - Histogram = MACD − Signal.
- **Volume SMAs**:
  - `VolSMA20`, `VolSMA50` on raw volume.
- **Tightness metrics**:
  - `10-bar range% = (max(high,10) - min(low,10))/close * 100`.
  - `5-bar close stdev% = stdev(close,5)/close * 100`.

---

## VSA / supply–demand heuristics

On **daily timeframe**, for at least the last **30 bars**:

- **Supply bar**:
  - Down bar (close < prior close),
  - Volume > 1.5 × VolSMA20,
  - Close in lower 30% of bar range.
- **Demand bar**:
  - Up bar (close > prior close),
  - Volume > 1.5 × VolSMA20,
  - Close in upper 30% of bar range.
- **No supply**:
  - Down bar,
  - Volume < 0.8 × VolSMA20,
  - Range < 0.8 × ATR14.
- **No demand**:
  - Up bar,
  - Volume < 0.8 × VolSMA20,
  - Narrow spread (similar to no‑supply).
- **Absorption** (heuristic):
  - Repeated tests of a level with high volume but limited downward progress, e.g.:
    - Equal/lower lows within a small % band **while** cumulative down‑volume decreases, **or**
    - Long lower wicks + close mid/high with elevated volume.

Write recent signals into `"volume_action.vsa_signals_recent"` with **dates + short evidence string**, and also into `"evidence_map"` for the most important ones.

---

## Volume Profile (VPVR-style)

Work on **daily bars**. For each window:

- **Windows**:
  - Long: last **260** daily bars.
  - Mid: last **90** daily bars.
  - Short: last **30** daily bars.
- **Bins**:
  - Use `vp_bins` (default 100) between global min(low) and max(high) of the window.
- **Price assignment**:
  - With daily OHLC only, assign **all volume** of a bar to the **typical price**: `(high + low + close) / 3` (or at least close). Be consistent.
- **POC / VA**:
  - POC = price bin with highest volume.
  - Value Area = contiguous bins around POC that together contain `value_area_pct` (default 70%) of total volume; report `[VAL_low, VAL_high]` and `[VAH_low, VAH_high]`.
- **HVN/LVN**:
  - HVN = local maxima bins (volume peaks) with a minimum **prominence** threshold to avoid noise.
  - LVN = local minima between HVNs.
  - For each window, return **top 2 HVNs and top 2 LVNs** as price ranges.

In `"volume_profile.vp_read"`, write 2–3 concise bullets interpreting:
- Overhead supply / support based on HVN above/below current price.
- Acceptance/rejection around VAH/VAL.
- Bias toward breakout vs mean reversion given current location vs VA and recent trend.

---

## Wyckoff module

- Use **daily** data and VP for structural context.
- Map price–volume behavior into phases **only when evidence is strong**:
  - Phases: `"A"`, `"B"`, `"C"`, `"D"`, `"E"`, or `"unclear"`.
  - Schematics: `"accumulation"`, `"distribution"`, `"re-accumulation"`, `"re-distribution"`, or `"unclear"`.

### Guardrail

- If there are **not at least 2 independent confirming signals** (e.g. spring + reclaim VAL + demand bar cluster), set:
  - `"phase": "unclear"`,
  - `"schematic_guess": "unclear"`,
  - and use `"logic"` to describe **candidate interpretations** instead of strong claims.

Populate `"wyckoff.events"` with `present: true/false` and a short `"why"` string grounded in:
- Range contractions/expansions.
- Tests of lows/highs.
- VP regions (VAL retests, POC rotations).
- VSA signals.

---

## Trade plan (analysis vs execution)

Use analysis to define **scenarios**, not predictions.

- `"bias"`: `"long"`, `"short"`, or `"neutral"` over the next **1–3 months**.
- `"trigger"`:
  - `"type"`: `"breakout"`, `"pullback"`, or `"mean_reversion"`.
  - `"price"`: numeric level (e.g. breakout above VAH or swing high).
  - `"conditions"`: list of objective conditions (e.g. `"close above 52-week high with volume > 1.5x VolSMA20"`).
- `"invalidations"`:
  - Prices/conditions that would **negate** the setup (e.g. loss of key support, failed breakout).
- `"risk"`:
  - Use **ATR14** to set a stop suggestion: `stop = entry -/+ ATR14 * 1.5` according to direction.
  - `"position_size_hint"`: keep `"risk 0.5%-1% equity"` unless user specifies otherwise.
- `"targets"`:
  - Use HVNs, prior swing highs/lows, and measured move projections as basis.
- `"setup_type"`, `"entry_model"`, `"stop_model"`, `"add_on_rules"`, `"sell_signals"`:
  - Fill with concise, rule‑based descriptions (O’Neil/Minervini style) but **grounded in the actual chart structure**.

---

## No-hallucination & evidence map

At the end of the analysis for each ticker:

1. **Check for hidden assumptions**:
   - If you inferred something (e.g. “probably re‑accumulation”) without direct evidence, either:
     - downgrade confidence, **or**
     - move it to `"notes"` as a soft hypothesis.
2. Populate `"evidence_map"` with the **5–10 most important pieces of evidence**, for example:
   - Key demand/supply bars with dates and volume multiples.
   - Breaks/retests of VAH/VAL or POC with dates and close prices.
   - Current ATR14 and MA50 values.
   - Notable divergences in OBV, CMF, or MACD with dates.
3. Ensure `"confidence.overall"` reflects:
   - Data quality (`data_integrity`),
   - Clarity of structure (trend vs choppy),
   - Strength of confluence (multiple independent signals vs noisy mix).

If a field cannot be grounded in **available data**, explicitly:
- Set it to `null` or an empty structure, and
- Add a short explanation in `"warnings"` or `"notes"`.

---

## Implementation workflow (per ticker)

1. **Normalize inputs** into the internal request object (tickers, asof_date, etc.).
2. **Fetch data**:
   - Use `fetch_ohlcv` from `src/canslim/fireant_fetcher.py` for `"D"` (and `"W"` if desired).
   - Optionally fetch VNINDEX/VN30 for relative context via `scripts/fetch_vietnam_market.py`.
3. **Compute indicators & VP**:
   - MAs, ATR, OBV, CMF20, MACD, volume SMAs, tightness metrics.
   - Volume profiles for 260d/90d/30d windows with POC/VAH/VAL/HVN/LVN.
4. **Detect VSA signals** over the last 30 daily bars.
5. **Assess trend regime**, price action, Wyckoff structure, and volume‑based support/resistance.
6. **Build trade plan** for 1–3 months, clearly separating:
   - Objective trigger conditions,
   - Invalidation levels,
   - Risk (ATR‑based) and targets.
7. **Fill `data_integrity`, `warnings`, `errors`, and `evidence_map`**, then:
   - Set `"confidence.overall"` to `"low"`, `"med"`, or `"high"` with reasons.
8. **Return JSON only** (per schema above) when the user explicitly requests the technical report output.

---

## Example usage (conceptual)

- User: “Phân tích kỹ thuật FireAnt cho VCI, HCM, MBS, VND, REE, ANV, NT2, timeframe daily/weekly, cho mình JSON chi tiết.”
- Agent (using this skill):
  1. Normalizes request into the input object.
  2. Fetches FireAnt OHLCV.
  3. Computes all indicators, VP, Wyckoff events, and trade plans.
  4. Returns **only** the JSON objects (one per ticker) following the schema, including `data_integrity`, `warnings`, `errors`, and `evidence_map`.

