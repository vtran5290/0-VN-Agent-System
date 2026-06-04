# Results summary — v2 (decision-grade T2)

## Executive conclusion

**Pine speed reset is fixed.** **Exact T2 re-simulation invalidates the v1 C3 headline:** C3 (`tsa_trendspeed_slope_3 ≥ 0` at fill) **underperforms** A3 baseline (MAR 0.075 vs 0.098, ΔMAR −0.024). The prior +0.023 MAR lift was an artifact of the `blended×0.85` approximation. **TSA does not earn APPROVE_FOR_SHADOW** on T2 gating. **Entry filter A5** (`tsa_norm_speed ≥ 0.50`) remains the strongest overlay (MAR 0.127, ΔMAR +0.029, DD −21.7% vs −24.7%) but is **WATCHLIST_ONLY** (retained 78.5%, ΔMAR < +0.05). **Ranking** is weakly monotonic (Spearman ~0.35 on decile means); **fifo** slightly beats TSA composite slot selection. **Exit overlay** not assessed (removed).

## Updated table

| Variant | MAR | ΔMAR vs A3 | Max DD | Retained % | Verdict |
|---------|-----|------------|--------|------------|---------|
| **A3 baseline (C0 / A0)** | **0.098** | — | −24.7% | 100% | Baseline |
| C3 T2 gate (exact) | 0.075 | **−0.024** | −25.0% | 100% | **REJECT** |
| A5 entry `norm≥0.50` | 0.127 | +0.029 | −21.7% | 78.5% | WATCHLIST_ONLY |
| Best ranking: fifo | 0.101 | +0.003 | −24.4% | slot-limited | WATCHLIST_ONLY |
| Exit overlay | — | — | — | — | **Not run (v2)** |

## TSA classification (overall)

| Use case | Verdict |
|----------|---------|
| A3 incremental | **Unclear / No** for T2; marginal for entry context |
| S3 | **No** (MAR −0.021) |
| Entry filter | **WATCHLIST_ONLY** |
| T2 gate | **REJECT** (exact sim) |
| Ranking | **WATCHLIST_ONLY** |
| Exit overlay | **REJECT / N/A** |

**Production contract unchanged. Research only.**
