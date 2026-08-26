---
name: source-command-vn-ta
description: Analyze Vietnamese stocks using FireAnt OHLCV with multi-timeframe structural pivots, support/resistance polarity, role reversal, market memory, dual-axis support-vs-trend scoring, Wyckoff/VSA, volume profile, and trade plans. Use when the user asks to run vn-ta, VN stock technical analysis, FireAnt-based TA, pivot zone, role reversal, resistance-to-support, failed breakout, support vs trend, MA cluster, LPS/backup, or structured JSON outputs for Vietnamese tickers.
---

# source-command-vn-ta

Use this skill when the user asks to run the migrated source command `vn-ta`.

# VN Technical Analysis via FireAnt

## When to use this skill

Use this skill when:
- The user asks for **technical analysis of Vietnamese stocks** (HOSE/HNX/UPCoM).
- The user mentions **FireAnt**, **OHLCV**, **Wyckoff**, **VSA**, **volume profile**, **monthly/weekly support**, **pivot zone**, **polarity**, **role reversal**, **resistance became support**, **failed breakout**, **market memory**, **MA compression**, **reclaim**, **failed support**, **breakout shelf**, **LPS**, **support vs trend**, **2x2**, **confluence**, **supply absorption**, or wants a **JSON technical report**.
- The user provides **1 or more tickers** and wants **fact-based**, **non‑hallucinated** technical output with clear price **zones** and trade plans.

**Mandatory before analysis:** read all four
1. `.agents/skills/source-command-vn-ta/reference-mtf-structural-support.md` (M→W→D hierarchy)
2. `.agents/skills/source-command-vn-ta/reference-weekly-structural-support.md` (weekly cluster / LPS / weekly score)
3. `.agents/skills/source-command-vn-ta/reference-support-vs-trend.md` (market memory, failed/reclaim, dual scores, 2×2)
4. `.agents/skills/source-command-vn-ta/reference-polarity-pivot-zone.md` (STRUCTURAL_PIVOT_ZONE first; polarity / role reversal)

(Same content as `.cursor/skills/vn-ta-fireant/`.)

Scope: swing/position analysis on **monthly + weekly + daily** using FireAnt OHLCV and (optionally) VNINDEX for context. Intraday only for tactical triggers.

---

## Core doctrine (summary)

> **Zoom out to define structural supply/demand. Zoom in to define timing. Never use a short-timeframe chart to decide the magnitude of a long-timeframe supply problem.**

> **A strong weekly level exists when multiple independent forms of market memory converge in the same price zone.**

> **Support strength and stock trend quality are separate dimensions and must be scored separately.**

> **Support and resistance are contextual states of the same structural pivot zone.**

- First label `STRUCTURAL_PIVOT_ZONE`; only then assign Support / Resistance / Role-reversal / Equilibrium from **approach direction + acceptance + retest**.
- A cross is not enough; wick ≠ role reversal. Retest is the real test.
- **Strong support ≠ strong stock**; **at support ≠ good entry**.
- Prefer **acceptance / market memory** over isolated wicks, single MA touches, or round numbers.
- Broken support → `FAILED_SUPPORT` until high-quality reclaim + retest → `RECLAIMED_SUPPORT` / `ROLE_REVERSAL_SUPPORT`.
- Failed breakout/breakdown can flip polarity again (bull trap / spring).
- **MONTHLY** → structure. **WEEKLY** → repair/accumulation / MA cluster. **DAILY** → execution.
- Weekly/monthly **closes** outweigh intra-period wicks.
- Phase D LPS/backup ≫ blindly buying a falling stock at an MA.

References: `.agents/skills/source-command-vn-ta/reference-mtf-structural-support.md` · `.agents/skills/source-command-vn-ta/reference-weekly-structural-support.md` · `.agents/skills/source-command-vn-ta/reference-support-vs-trend.md` · `.agents/skills/source-command-vn-ta/reference-polarity-pivot-zone.md`.

---

## Inputs (skill contract)

Normalize inputs into this internal request object:

```json
{
  "tickers": ["VCI", "HCM"],
  "asof_date": "YYYY-MM-DD",
  "horizon_days": 1260,
  "timeframes": ["M", "W", "D"],
  "risk_mode": "conservative",
  "vp_bins": 100,
  "value_area_pct": 0.7
}
```

Defaults if user does not specify:
- **asof_date**: today (system date).
- **horizon_days**: **1260** (≈ 5 years daily) so monthly SMA50/SMA100 and multi-year pivots are computable. Floor: 260 if user caps data.
- **timeframes**: `["M", "W", "D"]`.
- **risk_mode**: `"standard"`.
- **vp_bins**: `100`.
- **value_area_pct**: `0.7`.

For multiple tickers, produce one object per ticker with the **same schema**.

---

## Output modes

### A. JSON technical report (user asks for JSON / schema output)

Return **JSON only** per schema below (one object per ticker).

### B. Human chart review (default conversational TA)

1. MTF narrative: `reference-mtf-structural-support.md` §11.
2. Weekly material: `reference-weekly-structural-support.md` §13.
3. Dual-axis: `reference-support-vs-trend.md` §19 (Support Score + Trend Score + 2×2).
4. For each important zone: pivot polarity format `reference-polarity-pivot-zone.md` §13 (`STRUCTURAL_PIVOT_ZONE` → current role → confirm/invalidate).
5. Ground every claim in FireAnt facts; unknowns → `"not confirmed"` / Unknown.

---

## Outputs (JSON schema + failure modes)

For **each ticker**, return a **single JSON object** with this schema.

### Core analysis object

```json
{
  "ticker": "...",
  "asof": "YYYY-MM-DD",
  "data": {
    "timeframes": {
      "M": {"bars": 0, "start": null, "end": null, "adjusted": false},
      "W": {"bars": 0, "start": null, "end": null, "adjusted": false},
      "D": {"bars": 0, "start": null, "end": null, "adjusted": false}
    }
  },
  "levels": {
    "support_zones": [
      {
        "price_low": 0.0,
        "price_high": 0.0,
        "timeframe_origin": "M",
        "zone_role": "structural",
        "basis": ["MA50M", "PivotRoleReversal", "MarkupOrigin", "PriorBase"],
        "status": "under_test",
        "structural_support_score": 0,
        "score_breakdown": {
          "htf_ma": 0,
          "horizontal": 0,
          "markup_base": 0,
          "volume": 0,
          "momentum_trend": 0,
          "invalidation_clarity": 0
        },
        "confluence": {
          "ma": "...",
          "horizontal_pivot": "...",
          "origin_of_markup": "...",
          "prior_base": "...",
          "volume_behavior": "..."
        },
        "confidence": "low"
      }
    ],
    "resistance_zones": [
      {
        "price_low": 0.0,
        "price_high": 0.0,
        "timeframe_origin": "W",
        "zone_role": "structural",
        "basis": ["VP:VAH", "SwingHigh", "HVN"],
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
    "monthly": {
      "state": "uptrend",
      "ma_stack": "...",
      "price_vs_ma": {},
      "secular_trend_intact": true
    },
    "weekly": {
      "state": "range",
      "ma_stack": "...",
      "price_vs_ma": {}
    },
    "daily": {
      "state": "downtrend",
      "ma_stack": "...",
      "price_vs_ma": {}
    },
    "regime_summary": "Monthly defines structure; weekly phase; daily timing only.",
    "zoom_discipline": {
      "monthly_answers": "structural supply/demand",
      "weekly_answers": "Wyckoff phase / institutional support / MA cluster",
      "daily_answers": "trade trigger / stop"
    }
  },
  "weekly_structure": {
    "trend": "...",
    "current_range_base": "...",
    "wyckoff_phase": "unclear",
    "ma_cluster": {
      "available": true,
      "count": 3,
      "selected_mas": {"ma20": 61.25, "ma50": 61.35, "ma100": 60.60},
      "mean": 61.07,
      "representative_level": 61.07,
      "price_low": 60.60,
      "price_high": 61.35,
      "width_pct": 1.23,
      "classification": "very_tight",
      "slopes": {"ma20": "flat", "ma50": "up", "ma100": "up"},
      "flat_or_rising": true,
      "trend_quality": "flat_or_rising"
    },
    "zones": [
      {
        "representative_level": 0.0,
        "price_low": 0.0,
        "price_high": 0.0,
        "tags": ["MA_CLUSTER", "ROLE_REVERSAL_SUPPORT", "ORIGIN_OF_MARKUP", "PRIOR_BASE"],
        "ma_cluster": "...",
        "horizontal_pivot": "...",
        "role_reversal": "not confirmed",
        "prior_base": "...",
        "origin_of_markup": "...",
        "weekly_structural_support_score": 78,
        "score_breakdown": {
          "ma_confluence": 18,
          "horizontal_pivot": 16,
          "role_reversal": 12,
          "prior_base_origin_markup": 0,
          "volume_absorption": 14,
          "momentum_invalidation": 0
        },
        "score_classification": "Strong weekly support",
        "status": "under_test",
        "weekly_close_test": {
          "state": "support_test_held",
          "confirmation_close": "...",
          "invalidation_close": "..."
        }
      }
    ],
    "volume_supply_demand": {
      "supply": "unknown",
      "demand": "unknown",
      "absorption_evidence": []
    },
    "phase_interpretation": {
      "phase": "unclear",
      "sos": "not confirmed",
      "lps": "not confirmed",
      "breakout_status": "not confirmed"
    },
    "final_verdict": {
      "label": "Support under test",
      "confidence": "Low",
      "why": ["..."]
    }
  },
  "dual_axis": {
    "support_quality_score": null,
    "support_score_breakdown": {
      "market_memory": null,
      "ma_confluence": null,
      "role_reversal_reclaim": null,
      "base_markup": null,
      "volume_absorption": null,
      "invalidation_clarity": null
    },
    "trend_quality_score": null,
    "trend_score_breakdown": {
      "price_vs_mas": null,
      "structure": null,
      "relative_strength": null,
      "volume_money_flow": null,
      "momentum_entry": null
    },
    "matrix_2x2": "Strong Support + Weak Trend",
    "support_status": "SUPPORT_UNDER_TEST",
    "reclaim_quality": "not_applicable",
    "zone_tier": "Tier2",
    "market_memory": {
      "acceptance_vs_rejection": "not confirmed",
      "notes": "..."
    }
  },
  "pivot_zones": [
    {
      "label": "STRUCTURAL_PIVOT_ZONE",
      "representative_level": 0.0,
      "price_low": 0.0,
      "price_high": 0.0,
      "timeframe": "W",
      "historical_significance": "...",
      "current_role": "Unconfirmed",
      "approach_direction": "from_above",
      "break_history": "not confirmed",
      "acceptance": "not confirmed",
      "retest": "not confirmed",
      "volume_behavior": "...",
      "htf_confluence": "...",
      "role_reversal_quality_score": null,
      "role_reversal_score_breakdown": {
        "historical_importance": null,
        "break_quality": null,
        "acceptance": null,
        "retest_quality": null,
        "htf_confluence": null
      },
      "confirmation": "...",
      "invalidation": "..."
    }
  ],
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
    },
    "supply_absorption": {
      "status": "unresolved",
      "evidence_for": ["..."],
      "evidence_against": ["..."],
      "effort_vs_result": "..."
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
      "D": {"ma20": 0.0, "ma50": 0.0, "ma100": 0.0, "ma200": 0.0, "slope_ma50": "flat"},
      "W": {
        "sma20": 0.0,
        "sma50": 0.0,
        "sma100": 0.0,
        "sma200": null,
        "ema10": 0.0,
        "ema20": 0.0,
        "slope_sma50": "flat"
      },
      "M": {"sma10": 0.0, "sma20": 0.0, "sma50": 0.0, "sma100": 0.0, "slope_sma50": "rising"}
    },
    "rsi": {
      "D": {"value": null, "note": "context only; oversold ≠ bottom"},
      "W": {"value": null, "note": "RSI14W context; reset ≠ buy signal"},
      "M": {"value": null}
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
    "primary_timeframe": "W",
    "phase": "unclear",
    "schematic_guess": "unclear",
    "events": {
      "ps": {"present": false, "why": "not confirmed"},
      "sc": {"present": false, "why": "not confirmed"},
      "ar": {"present": false, "why": "not confirmed"},
      "st": {"present": false, "why": "not confirmed"},
      "spring": {"present": false, "why": "not confirmed"},
      "sos": {"present": false, "why": "not confirmed"},
      "lps": {"present": false, "why": "not confirmed"}
    },
    "logic": ["..."]
  },
  "entry_quality": {
    "good_chart": null,
    "good_entry_now": null,
    "better_entry": "...",
    "trigger": "...",
    "invalidation": "..."
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
  "final_verdict": {
    "label": "Support under test",
    "confidence": "Medium",
    "why": ["..."]
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
    "liquidity_flag": "ok",
    "adjusted": false,
    "adjustment_notes": "adjusted/unadjusted status and caveats"
  },
  "warnings": ["..."],
  "errors": ["..."]
}
```

**Zone status values:** `"strong_candidate"` | `"under_test"` | `"confirmed"` | `"failed"` | `"reclaimed"`.  
**zone_role / tier:** `"structural"` Tier1–2 (M/W) | `"tactical"` Tier3 (D/intraday).  
**Zone tags:** `STRUCTURAL_PIVOT_ZONE` | `MA_CLUSTER` | `ROLE_REVERSAL_SUPPORT` | `ROLE_REVERSAL_RESISTANCE` | `ROLE_REVERSAL_RECLAIM` | `ORIGIN_OF_MARKUP` | `PRIOR_BASE` | `BREAKOUT_SHELF_SUPPORT` | `LPS_BACKUP` | `FAILED_SUPPORT` | `FAILED_BREAKOUT` | `FAILED_BREAKDOWN` | `RECLAIMED_SUPPORT` | `SUPPORT_UNDER_TEST` | `SUPPORT_CONFIRMED` | `EQUILIBRIUM_PIVOT`.  
**pivot_zones[].current_role:** `Support` | `Resistance` | `Role-reversal support` | `Role-reversal resistance` | `Equilibrium/pivot` | `Unconfirmed`.  
**dual_axis.support_status:** `FAILED_SUPPORT` | `RECLAIM_ATTEMPT` | `RECLAIMED_SUPPORT` | `ROLE_REVERSAL_SUPPORT` | `ROLE_REVERSAL_RESISTANCE` | `SUPPORT_UNDER_TEST` | `SUPPORT_CONFIRMED` | `BREAKOUT_SHELF_SUPPORT`.  
**dual_axis.matrix_2x2:**  
`Strong Support + Strong Trend` | `Strong Support + Weak Trend` | `Weak Support + Strong Trend` | `Weak Support + Weak Trend`.  
**final_verdict.label (overall):**  
`Exceptional structural support` | `Strong structural support` | `Support under test` | `Reclaimed support` | `Role-reversal support` | `Role-reversal resistance` | `LPS candidate` | `Failed support` | `Failed breakout` | `Weak / non-structural support` | `Equilibrium/pivot` | `Re-accumulation candidate` | `Phase D late` | `Phase E fresh breakout` | `Distribution risk` | `Structural failure`.  
**weekly_structure.final_verdict.label:**  
`Strong weekly support` | `Support under test` | `LPS candidate` | `Phase D support` | `Role-reversal support` | `Role-reversal resistance` | `Weak support` | `Failed support` | `Equilibrium/pivot`.

### Dual-axis scores (mandatory)

Per `reference-support-vs-trend.md` §12–14 — Support Quality + Trend Quality; never merge into one “bullishness” score. **`dual_axis` is ranking SSOT** across names.

### Role-reversal quality score (when polarity is the question)

Per `reference-polarity-pivot-zone.md` §7 (20+20+15+25+20). Fill `pivot_zones[].role_reversal_quality_score`. Do not call role reversal on a wick cross alone.

### Failure / partial data behavior

- **Never hallucinate data.** Missing → `null`, `"not confirmed"`, or empty list + `warnings`.
- FireAnt/network fail → `errors` + zeroed `data.timeframes` + `"overall": "low"`.
- Always keep **valid JSON shape** (all top-level keys present).
- After decisive break + acceptance below → do **not** label `STRONG_SUPPORT`; use `FAILED_SUPPORT` / `RECLAIM_ATTEMPT`.
- Never permanently hard-code a pivot as “support” or “resistance” without current role context.

---

## Data sources and hygiene

### 1. FireAnt OHLCV and helpers

- Prefer: `src/canslim/fireant_fetcher.py` → `fetch_ohlcv(symbol, start, end, resolution="D"|"W"|"M")`.
- Monthly/weekly: `FireAntClient.get_ohlcv` resamples daily → `W` / `M` when requested.
- Index context: `scripts/fetch_vietnam_market.py` if helpful for RS.

### 2. Timeframes and lookbacks

- **Daily (`D`)**: ≥ **260** trading days (prefer full `horizon_days`).
- **Weekly (`W`)**: resample or `resolution="W"`.
- **Monthly (`M`)**: resample or `resolution="M"`; need enough history for **SMA50M** (≈ 50 months) when claiming monthly MA confluence — if bars < 50, set MA fields `null` and warn.

If fewer bars than requested, record in `data_integrity` and reduce confidence.

### 3. Liquidity and anomalies

- Median daily traded value proxy: `median(volume * close)`.
- `liquidity_flag`: `"ok"` | `"thin"` | `"very_thin"` (default ok threshold ~5e9 VND).
- Warn on thin liquidity and anomalous volume spikes.

### 4. Adjusted vs unadjusted

- Detect adjusted → `"adjusted": true`; else assume unadjusted + warning that MA/VP may be distorted by splits/dividends.

---

## Indicator definitions (must be consistent)

- **Daily MAs**: SMA20/50/100/200 on close.
- **Weekly MAs (required)**: SMA20W, SMA50W, SMA100W, optional SMA200W, EMA10W, EMA20W.
- **Monthly MAs (required for cluster)**: SMA10M, SMA20M, SMA50M (also SMA100M when available).
- **MA_cluster_width**: `(max - min) / mean` — weekly on SMA20/50/100; monthly on SMA10/20/50. Labels: `<2%` exceptional · `2–4%` strong · `4–7%` moderate · `>7%` weak.
- **ATR14**, **OBV**, **CMF20**, **MACD(12,26,9)**, VolSMA20/50 — standard definitions.
- **RSI14** (D/W/M): context only; never sole bottom/reversal signal.
- **Tightness**: 10-bar range%; 5-bar close stdev%.
- Prefer **weekly/monthly closes and bodies** over isolated wick prints.

---

## Analysis hierarchy (mandatory order)

1. **Monthly** — structural demand/supply, market memory, SMA10/20/50M cluster, markup origin. Not for precise entries. Downgrade broken zones to `FAILED_SUPPORT`.
2. **Weekly** — institutional / Wyckoff TF; MA20/50/100 cluster; role reversal / reclaim quality; Phase C/D/E; LPS/backup; judge by **weekly close**.
3. **Daily** — trigger/stop only; must not override M/W structure without evidence.
4. Score **Support Quality** and **Trend Quality** separately → fill `dual_axis` + 2×2 matrix.
5. Classify zone status / tier (Tier1–3); never call Tier3 a Tier1 structural hold.
6. Entry quality separately from chart quality / support quality.
7. Verdict + confidence (never “strong buy” from monthly support alone).

---

## VSA / supply–demand heuristics

On **daily** (and mirror on **weekly** near structural zones), last **30** bars:

- **Supply bar**: down, vol > 1.5× VolSMA20, close in lower 30% of range.
- **Demand bar**: up, vol > 1.5× VolSMA20, close in upper 30% of range.
- **No supply**: down, vol < 0.8× VolSMA20, range < 0.8× ATR14.
- **No demand**: up, vol < 0.8× VolSMA20, narrow spread.
- **Absorption**: high effort, limited downside; long lower wicks; repeated tests with less result; OBV/CMF stabilizing.

Weekly-specific volume states (healthy test / no-demand / structural failure): see `reference-weekly-structural-support.md` §8.

Fill `volume_action.supply_absorption` with evidence for/against and effort-vs-result.  
No-supply without upward response may be **no-demand** — do not call accumulation.

---

## Volume Profile (VPVR-style)

Daily windows: **260d / 90d / 30d**; `vp_bins` (default 100); volume at typical price `(H+L+C)/3`.  
POC / 70% VA / top-2 HVN & LVN. Interpret overhead supply, VAL/VAH acceptance, breakout vs mean reversion in `vp_read`.  
VP levels are **confluence inputs**, not sole support justification.

---

## Wyckoff module

- **Primary timeframe: weekly.** Daily refines events; monthly sets whether the range is re-accumulation vs major distribution risk.
- After SOS, evaluate pullbacks as possible **LPS / BACKUP** (shallower, lower volume, holds former resistance + MA cluster).
- Phases: `"A"`–`"E"` or `"unclear"`. Schematics: `"accumulation"` | `"distribution"` | `"re-accumulation"` | `"re-distribution"` | `"unclear"` | `"markdown"`.
- Guardrail: need **≥ 2 independent confirming signals** or set phase/schematic `"unclear"` and list candidates in `logic`.
- Unknown events → `"present": false`, `"why": "not confirmed"`.

---

## Trade plan (analysis vs execution)

Scenarios, not predictions. Separate **good chart** vs **good entry now**.

- Bias 1–3m: long / short / neutral.
- Trigger types: breakout / pullback / mean_reversion — with objective conditions.
- Invalidation: prefer **decisive weekly close below structural zone** (not a single MA tick or wick).
- Risk: ATR14 × 1.5 default; size hint `risk 0.5%-1% equity`.
- Targets: HVNs, prior swings, measured moves.

---

## No-hallucination & evidence map

1. Soft hypotheses → lower confidence or `notes`.
2. `evidence_map`: 5–10 dated facts (bars, retests, MA cluster values, role-reversal evidence, divergences, markup origin).
3. `confidence.overall` reflects data quality, structure clarity, and **confluence strength**.

---

## Implementation workflow (per ticker)

1. Normalize inputs (`timeframes` include M/W/D; horizon ≥ 1260 when possible).
2. Fetch FireAnt OHLCV daily; resample W and M (or fetch with `resolution`).
3. Compute M/W/D MAs (W: SMA20/50/100; M: SMA10/20/50), clusters, ATR, OBV, CMF, MACD, RSI, VP.
4. Map zones as bands; tag failed/reclaim/breakout-shelf/memory; score Support + Trend → 2×2.
5. Weekly Wyckoff + absorption; daily VSA for timing only.
6. Fill `weekly_structure` + `dual_axis` + entry_quality + verdicts.
7. Integrity / warnings / evidence_map / confidence.
8. JSON if requested; else MTF §11 + weekly §13 + dual-axis §19 + polarity §13.

---

## Teaching examples (not live targets)

- **MWG (monthly):** ≈57–60 demand zone — rising SMA50M + pivot + markup origin (MTF ref).
- **VCB (weekly):** representative 61.7 → zone ≈**60.5–62** from SMA20/50/100 compression (weekly ref §14).
- **VCG ≈21–22:** `STRUCTURAL_PIVOT_ZONE` / role-reversal zone — **not** permanently “21.45 support”; below → resistance candidate; reclaim+retest → support candidate (polarity ref §14). Older 20–21.5 failed-support note still applies if break accepted.
- **PC1 ≈25.5–26.8:** breakout shelf + strong trend → often **better trade** than a stronger-support/weaker-trend name.
- **VCI weekly ≈25.8–27.3:** strong support + neutral trend → needs demand confirmation.
- **VCI monthly ≈25–27:** major monthly structural support — still **not** automatic “strong stock”.

Incorrect:

> Strong buy because monthly support is strong / 61.7 must hold because SMA50W is there / 21.45 is support forever.

Correct:

> Label pivot zone first; assign current role from approach + acceptance + retest; report Support Score and Trend Score separately.

---

## Example usage (conceptual)

- User: “Phân tích weekly support VCB — MA cluster và role reversal.”
- Agent: read both references → fetch ≥5y OHLCV → M context → weekly cluster/score/§13 → daily only for trigger.
