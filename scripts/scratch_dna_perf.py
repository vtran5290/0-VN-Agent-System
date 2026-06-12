"""
DNA on A3 — performance stats.

Methodology:
  - Each A3-like event is an independent 20-day trade (entry = date, exit = date+20d).
  - Sequential equity curve: sort by date, compound each trade in order.
    This is the standard "system equity curve" methodology for event-driven strategies.
  - No position sizing, no stop-loss — pure raw signal quality test.
  - IMPORTANT: this overstates real drawdowns (real portfolio diversifies across names;
    this curve holds one trade at a time). Use as relative comparison only.
"""
import pandas as pd
import numpy as np

df = pd.read_csv('data/research/stock_dna/stock_dna_trade_level_overlay_full.csv')
df['date'] = pd.to_datetime(df['date'])
df = df[df['fwd_ret_20d'].notna()].copy()
df = df.sort_values('date').reset_index(drop=True)


def equity_stats(trades_df, label):
    rets = trades_df['fwd_ret_20d'].values

    # Sequential equity curve
    eq = np.cumprod(1 + rets)

    start_date = trades_df['date'].iloc[0]
    end_date   = trades_df['date'].iloc[-1]
    years = (end_date - start_date).days / 365.25

    # Annualise: (final_equity)^(1/years) - 1
    cagr = eq[-1] ** (1 / years) - 1

    # Max drawdown
    roll_max = np.maximum.accumulate(eq)
    dd = eq / roll_max - 1
    max_dd = dd.min()
    mar = cagr / abs(max_dd) if max_dd != 0 else float('nan')

    wins   = rets[rets > 0]
    losses = rets[rets <= 0]
    wr     = len(wins) / len(rets)
    expect = rets.mean()

    # Trades per year
    tpy = len(rets) / years

    print(f"--- {label} ---")
    print(f"  N trades          : {len(rets):,}  ({tpy:.0f}/yr)")
    print(f"  Date range        : {start_date.date()} -> {end_date.date()} ({years:.1f} yr)")
    print(f"  Win rate          : {wr:.1%}")
    print(f"  Expectancy        : {expect:.2%}/trade")
    print(f"  Avg win           : {wins.mean():.2%}   Avg loss: {losses.mean():.2%}")
    print(f"  Win/Loss ratio    : {abs(wins.mean()/losses.mean()):.2f}x")
    print(f"  CAGR              : {cagr:.1%}")
    print(f"  Max drawdown      : {max_dd:.1%}")
    print(f"  MAR               : {mar:.2f}")
    print()


equity_stats(df, "Baseline — all A3-like events")
equity_stats(df[df['is_stock_dna_aligned'] == 1].reset_index(drop=True),
             "DNA-filtered — aligned events only")
equity_stats(
    df[df['edge_confidence'].isin(['MODERATE', 'STRONG'])].reset_index(drop=True),
    "DNA MODERATE+STRONG confidence"
)
equity_stats(
    df[
        (df['is_stock_dna_aligned'] == 1) &
        (df['breadth_regime'].isin(['BULL_BROAD', 'BULL_NARROW']))
    ].reset_index(drop=True),
    "DNA-aligned + BULL regime only"
)
