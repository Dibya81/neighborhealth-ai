# Model card: BBMP weekly dengue forecast

**Task:** forecast weekly lab-confirmed dengue cases reported for BBMP, 1–4 weeks ahead, with 50/80/95% prediction intervals.

**Evaluation:** rolling-origin backtest (train on weeks ≤ t, predict t+h, slide forward 1 week). Intervals are online conformal, using only residuals already observable at each origin.

**Champion:** `gbm` (version `20261026-131436-gbm`, data 2021-10-10 → 2024-11-03, 161 weeks)

```json
{
  "mae": 240.98153399174976,
  "skill_vs_seasonal_naive": 0.0008280743559055115,
  "wis": 199.64701575368426,
  "coverage80": 0.746112585257322,
  "coverage50": 0.5371580588685851,
  "coverage95": 0.8884152624284203
}
```

## Backtest results (all models)

Skill = 1 − MAE / MAE(seasonal naive). Positive means better than the baseline.

| model | horizon | mae | wis | coverage50 | coverage80 | coverage95 | skill_vs_seasonal_naive | n |
|---|---|---|---|---|---|---|---|---|
| ensemble | 1 | 208.470 | 189.399 | 0.600 | 0.825 | 0.925 | 0.136 | 48 |
| gbm | 1 | 218.480 | 184.518 | 0.650 | 0.775 | 0.925 | 0.094 | 48 |
| glm_poisson | 1 | 286.977 | 230.682 | 0.600 | 0.825 | 0.950 | -0.190 | 48 |
| persistence | 1 | 246.912 | 1793.246 | 0.575 | 0.800 | 0.875 | -0.024 | 48 |
| sarima | 1 | 263.437 | 291.443 | 0.650 | 0.800 | 0.900 | -0.092 | 48 |
| seasonal_naive | 1 | 241.181 | 350.158 | 0.450 | 0.650 | 0.850 | 0.000 | 48 |
| ensemble | 2 | 236.972 | 194.046 | 0.590 | 0.795 | 0.949 | 0.017 | 48 |
| gbm | 2 | 245.340 | 199.036 | 0.538 | 0.744 | 0.949 | -0.017 | 48 |
| glm_poisson | 2 | 336.852 | 296.788 | 0.564 | 0.795 | 0.923 | -0.397 | 48 |
| persistence | 2 | 279.071 | 2097.148 | 0.564 | 0.769 | 0.872 | -0.157 | 48 |
| sarima | 2 | 278.385 | 246.243 | 0.692 | 0.846 | 0.949 | -0.154 | 48 |
| seasonal_naive | 2 | 241.181 | 361.427 | 0.462 | 0.615 | 0.846 | 0.000 | 48 |
| ensemble | 3 | 252.533 | 224.566 | 0.526 | 0.789 | 0.921 | -0.047 | 48 |
| gbm | 3 | 256.984 | 239.685 | 0.474 | 0.763 | 0.842 | -0.066 | 48 |
| glm_poisson | 3 | 376.097 | 396.616 | 0.553 | 0.789 | 0.868 | -0.559 | 48 |
| persistence | 3 | 295.242 | 4149.684 | 0.553 | 0.789 | 0.921 | -0.224 | 48 |
| sarima | 3 | 288.060 | 225.284 | 0.658 | 0.895 | 0.974 | -0.194 | 48 |
| seasonal_naive | 3 | 241.181 | 367.427 | 0.474 | 0.605 | 0.816 | 0.000 | 48 |
| ensemble | 4 | 258.495 | 194.377 | 0.541 | 0.865 | 0.946 | -0.072 | 48 |
| gbm | 4 | 243.122 | 175.349 | 0.486 | 0.703 | 0.838 | -0.008 | 48 |
| glm_poisson | 4 | 283.013 | 292.487 | 0.595 | 0.838 | 0.973 | -0.173 | 48 |
| persistence | 4 | 357.452 | 8756.961 | 0.595 | 0.784 | 0.892 | -0.482 | 48 |
| sarima | 4 | 291.456 | 251.199 | 0.568 | 0.892 | 0.946 | -0.208 | 48 |
| seasonal_naive | 4 | 241.181 | 377.195 | 0.486 | 0.622 | 0.811 | 0.000 | 48 |

## Promotion history

- 2026-10-26T08:34:07 `20261026-083407-ensemble`: rejected (does not beat seasonal naive (skill -0.002))
- 2026-10-26T08:36:00 `20261026-083600-gbm`: PROMOTED (first model to pass the quality gate)
- 2026-10-26T13:14:36 `20261026-131436-gbm`: PROMOTED (wis: candidate 199.65 vs champion gbm 199.65 on the same backtest)

## Limitations

- Targets are *reported* cases: they depend on testing volume and reporting delays.
- One weather point for the whole city.
- Ward values in the app are allocations of the city forecast (population × risk factors), not ward-level predictions learned from ward data.
