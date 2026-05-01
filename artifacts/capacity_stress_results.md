# Extended Capacity Stress

Period: 2018-01-01 to 2021-12-31. Ranking: extension_only.

## Raw results

    CAGR       MDD      MAR  n_trades  final_equity  avg_heat  avg_gross_exposure  skipped_ineligible  skipped_regime_off  skipped_no_new_positions  skipped_max_positions  skipped_liquidity  avg_position_size_vnd  max_position_size_vnd  nav_bn  initial_equity_vnd
0.286043 -0.115457 2.477484        45  2.726006e+09  0.018451            0.468674                1275                1804                       460                   2159                  0           1.050592e+08           2.783192e+08       1          1000000000
0.234809 -0.117060 2.005886        45  1.159084e+10  0.018910            0.413140                1275                1804                       460                   2159                  0           4.604312e+08           1.167065e+09       5          5000000000
0.171400 -0.105784 1.620282        45  1.878797e+10  0.019566            0.332057                1275                1804                       460                   2159                  0           7.431059e+08           1.861473e+09      10         10000000000
0.110040 -0.080931 1.359684        45  3.032243e+10  0.020298            0.236503                1275                1804                       460                   2159                  0           1.007593e+09           2.809106e+09      20         20000000000
0.046086 -0.046235 0.996778        45  5.983725e+10  0.021148            0.118692                1275                1804                       460                   2159                  0           1.251410e+09           5.213479e+09      50         50000000000
0.023683 -0.023845 0.993194        45  1.097799e+11  0.021502            0.062009                1275                1804                       460                   2159                  0           1.272943e+09           5.987720e+09     100        100000000000

## Notes

- First NAV where skipped_liquidity becomes material (>10): Nonebn VND.
- CAGR/MAR degrades smoothly (no single drop >15pp): True.
- Safe practical NAV range (under current execution): suggest up to 10–20bn if skipped_liquidity still 0; cap at level where skipped_liquidity first rises.
