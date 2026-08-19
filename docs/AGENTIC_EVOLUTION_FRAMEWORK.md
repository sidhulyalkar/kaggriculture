# Agentic Evolution Framework

## Objective

Kaggriculture should be treated as a non-stationary two-player economic game, not as a fixed farming puzzle. The research system therefore needs to improve by converting losses into causal evidence while preserving a proven champion by default.

The core design is:

```text
live / offline losses
        |
        v
regime risk model ---- opponent forecast
        |                    |
        +---------+----------+
                  v
           replay priority queue
                  |
                  v
       counterfactual branch factory
                  |
                  v
   distributional residual value learner
                  |
                  v
      sparse candidate policy library
                  |
                  v
       hard/safe/seat stress suites
                  |
                  v
          policy population / PSRO
                  |
                  v
            promotion contract
                  |
                  v
        runtime-verified submission
```

The runtime agent should remain conservative. The offline research stack may be expensive, but the submitted policy should normally be the exact champion plus a small number of distilled, high-confidence residuals.

## Design principles

1. **Champion first.** V32 stays intact unless a departure has positive causal evidence.
2. **Learn residual value, not the whole game.** Estimate the value and downside of changing one decision relative to V32.
3. **Seed isolation is mandatory.** Counterfactual models must hold out whole seeds. Splitting the same seed across opponent families can produce dangerously optimistic value estimates.
4. **Opponent forecasts are context, not actions.** Wave 19 showed that opponent sales are predictable, but direct front-running did not improve wins.
5. **Hard regimes are first-class test cases.** Every candidate must be tested on ordinary held-out seeds, fixed hard seeds, safe controls, seat-asymmetric seeds, broad guards, and direct champion games.
6. **Policy-level validation matters more than AUC.** A classifier can have excellent AUC and still choose catastrophic interventions. Promotion depends on realized out-of-fold policy value.
7. **Population robustness comes after diversity.** PSRO cannot help if every candidate has the same payoff profile. Specialists enter the population only after they demonstrate distinct matchup value.
8. **No leaderboard tuning.** Live submissions are confirmation experiments after offline promotion, never development samples.

## Components

### 1. Regime model

`kagv2.agentic.regime` estimates the probability that the current champion loses in a seed/state regime. It uses grouped out-of-fold evaluation with entire seeds held out.

Wave 19D real-data sandbox replay gives:

- 640 games
- 64 independent seeds
- loss-rate 0.3281
- grouped OOF AUC 0.9210
- Brier score 0.0941
- top-quartile loss rate 0.8063
- top-quartile lift 2.46x

The model is useful both for runtime gating and for deciding which losses deserve expensive counterfactual search.

### 2. Opponent forecast validation

`kagv2.agentic.forecast` reads leave-one-family-out metrics and allows only targets that generalize to unseen policy families.

From Wave 19A, linear runtime-compatible forecasts pass the default unseen-family gate for:

- 4-turn MELON, MILK, STRAWBERRY sales
- 12-turn MELON, MILK, STRAWBERRY sales
- 24-turn MELON, MILK, STRAWBERRY and WHEAT sales

WHEAT at 4/12 turns and WOOL at 4/12/24 turns fail the current worst-family threshold and should not be treated as universally reliable runtime signals.

### 3. Loss replay queue

`kagv2.agentic.losses` produces two queues:

- `known_hard`: high-confidence failures ideal for causal branch search
- `surprise`: low-predicted-risk failures that expand the regime model and protect against novel metas

### 4. Counterfactual intervention grammar

`kagv2.agentic.interventions` defines a bounded offline grammar:

- HIRE / BUY_LAND: suppress or delay one turn
- BUY_SEED / BUY_PRODUCT / BUY_ANIMAL: suppress or halve quantity
- SELL: halve or delay one turn

Nothing in this grammar is automatically enabled in the live agent.

### 5. Distributional regret learner

`kagv2.agentic.regret` learns:

- probability an intervention improves final margin
- expected final-margin delta
- empirical downside from the tree ensemble

The current Wave 18B dataset is not ready for deployment under the corrected validation boundary:

- 600 branches
- only 5 independent loss seeds
- seed-held-out benefit AUC 0.8944
- mean-delta MAE about $3,836
- q10/q90 coverage 0.69 / 0.625
- no conservative gate with enough selected events has positive out-of-fold realized EV

This is a critical result. The older seed+opponent grouping leaked seed regime information across folds and made the residual policy look much safer than it really was.

### 6. Promotion contract

`kagv2.agentic.promotion` requires all applicable gates to pass:

- zero invalid games
- nonzero intervention activation
- positive robust delta
- positive hard-seed delta
- positive target delta
- bounded safe-seed regression
- bounded worst-guard regression
- non-negative direct champion score
- near-parity aggregate cash

Missing hard/safe evidence is a rejection, not an implicit pass.

### 7. Policy population

`kagv2.agentic.population` reuses the existing zero-sum equilibrium solver. PSRO becomes useful only after strategically distinct specialists exist.

Wave 19B FRONT_Q2 and FRONT_Q4 have effectively identical payoff profiles and both are slightly worse than V32, so there is currently nothing useful to mix.

## Learning state machine

```text
DISCOVER LOSS
  -> CLASSIFY REGIME
  -> PRIORITIZE REPLAY
  -> BRANCH COUNTERFACTUALS
  -> FIT DISTRIBUTIONAL RESIDUAL MODEL
  -> REJECT IF SEED-HELD-OUT POLICY EV <= 0
  -> DISTILL SMALL RESIDUAL
  -> HARD/SAFE/SEAT TEST
  -> BROAD GUARD TEST
  -> ADD DISTINCT SURVIVOR TO POPULATION
  -> SOLVE ROBUST MIX / BEST RESPONSE
  -> INDEPENDENT CONFIRMATION
  -> RUNTIME PACKAGING
  -> LIVE CONFIRMATION
  -> UPDATE CHAMPION OR RECORD FAILURE
```

## Next data-generation wave

The next counterfactual dataset should be generated on the fixed 19D hard, safe-control, and seat-asymmetry suites, not on a small arbitrary loss sample. It should record runtime-visible state at every branch and include at least 12 independent seeds per development/validation partition.

Priority intervention families:

1. HIRE suppress/delay around days 5-12
2. strawberry-seed half/suppress around the first major expansion wave
3. land timing around the second and third quadrant purchase
4. wheat reserve/procurement only in high predicted loss-risk regimes
5. premium sale timing only for forecast targets that pass leave-one-family-out reliability

The objective is not to maximize average counterfactual delta. It is to discover a small residual policy whose seed-held-out, risk-adjusted realized value remains positive and whose gameplay effect survives hard-seed promotion.
