# V41.2 Soil Mechanism Distillation

V41 identified a promising `V32 -> Soil` hybrid: the held-out winner reached 0.7857 mean score, 1.00 direct score against exact V32, +0.1429 paired score delta, 0.50 worst-family score, and no measured family regression in the tested panel.

The next question is causal attribution. A full Soil switch is too broad to explain *why* the hybrid works. V41.2 therefore shadow-runs exact V32 and Soil every turn and isolates the following post-switch grafts:

- `SELL_ORDER_ONLY`
- `SELL_REPLACE`
- `CAPITAL_ONLY` (`HIRE`, `BUY_LAND`)
- `INPUT_BUYS_ONLY` (`BUY_SEED`, `BUY_PRODUCT`, `BUY_ANIMAL`)
- `MARKET_MACRO`
- `MARKET_ALL`
- `FARMER_ONLY`
- `HANDS_ONLY`
- `WORKERS_ALL`
- `FULL_SOIL_SWITCH` as the positive control

If a successful V41.1 decision artifact is attached, its selected switch step is used. Otherwise the research fallback is turn 288.

## Promotion contract

A sparse mechanism may be promoted only if fresh held-out evaluation shows all of:

- paired score delta >= +0.03 vs exact V32
- direct score vs exact V32 >= 0.75
- worst-family score >= 0.45
- worst-family paired delta >= 0
- zero observed V32 win -> candidate loss flips
- zero invalid games
- mean score within 0.03 of the full Soil-switch positive control
- loader/runtime verification before and after tar repacking

If no sparse mechanism clears these gates but the full switch still does, the decision is `FULL_SWITCH_ONLY`. If neither survives, the decision is `HOLD`.

The purpose is to convert the V41 empirical win into a compact, interpretable residual that preserves more of exact V32 and is safer to evolve further.