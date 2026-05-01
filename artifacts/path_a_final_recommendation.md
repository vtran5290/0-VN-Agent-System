# Path A Final Recommendation

## 1. Champion vs Challenger by period

| period | Champion MAR | Challenger MAR |
|--------|--------------|----------------|
| 2018-2021 | 2.4775 | 1.7685 |
| 2024-2026Q1 | 0.4411 | 0.7522 |
| 2022-2024 | 0.3387 | 0.2026 |
| full_sample | 0.5138 | 0.5551 |

## 2. Robustness

- Champion robustness (avg MAR − penalties): 0.9428
- Challenger robustness: 0.8196
- **Better on robustness:** Champion

## 3. Recent regime (2024-2026Q1)

- Champion MAR: 0.4411
- Challenger MAR: 0.7522
- **Better on recent:** Challenger

## 4. Full-sample MAR and extra slots

- Champion (8 slots) full-sample MAR: 0.5138
- Challenger (12 slots) full-sample MAR: 0.5551
- **Worth extra slots?** Challenger's higher full-sample MAR may justify 12 slots for a research branch; Champion remains simpler (8 slots) and best on robustness.


## 5. chosen_rate and rejected_max_positions

- **2018-2021:** Champion chosen_rate=0.01219 rejected_max_pos=2159; Challenger chosen_rate=0.01706 rejected_max_pos=886
- **2024-2026Q1:** Champion chosen_rate=0.0267 rejected_max_pos=1298; Challenger chosen_rate=0.02367 rejected_max_pos=607
- **full_sample:** Champion chosen_rate=0.02079 rejected_max_pos=5940; Challenger chosen_rate=0.02793 rejected_max_pos=3215

## 6. Recommendation

- **Use Champion as new production baseline** (extension_first, 8 slots).
- **Keep Challenger as secondary research branch** (simple_composite, 12 slots) for continued tracking.
- Evidence does not justify switching production to Challenger; Champion is better on robustness and recent period; Challenger wins full-sample MAR only.
