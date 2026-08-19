# Wave 20 Sandbox Validation

Date: 2026-08-18

This validation runs the new agentic analytics stack on actual Wave 18/19 send-back artifacts and validates the reusable counterfactual branch factory.

## Inputs

- Wave 18B counterfactual branches: 600 activated branches
- Wave 19A leave-one-family-out forecast metrics: 60,396 rows across 7 families
- Wave 19B held-out candidate games: 384 games
- Wave 19D seed-regime games: 640 games across 64 seeds
- Wave 19D fixed hard/safe/seat seed suite

## Software validation

- local unit/integration tests: **9 passed**
- end-to-end CLI run on all real artifacts: **PASS**
- deterministic counterfactual branch factory: **PASS** with fresh agent instances, order fingerprints, bounded one-decision mutation, and runtime-visible state capture

## Regime model

Whole-seed grouped OOF:

- AUC: **0.92096**
- Brier: **0.09407**
- base loss rate: **0.32813**
- top-quartile predicted-risk loss rate: **0.80625**
- lift: **2.457x**

Result: **PASS as a research signal**. Seed/state regime is strongly informative about champion failure.

## Forecast generalization

Linear leave-one-family-out median AUC across sale targets: **0.91248**.

Default deployable targets require median AUC >= 0.85 and worst held-family AUC >= 0.80.

Eligible:

- sell4: MELON, MILK, STRAWBERRY
- sell12: MELON, MILK, STRAWBERRY
- sell24: MELON, MILK, STRAWBERRY, WHEAT

Rejected as universal signals:

- sell4 WHEAT, WOOL
- sell12 WHEAT, WOOL
- sell24 WOOL

Result: **PASS as context**, but Wave 19B proved that prediction alone is not an action policy.

## Regret learner

The original counterfactual result becomes much less optimistic when validation holds out whole seeds instead of seed+opponent pairs:

- independent loss seeds: **5**
- benefit AUC: **0.89444**
- positive branch rate: **0.08667**
- mean-delta MAE: **$3,835.85**
- q10 coverage: **0.69**
- q90 coverage: **0.625**
- conservative OOF gate with >=8 selected events and positive mean realized delta: **none**

Result: **NOT READY**. The current counterfactual dataset is too small at the seed level to support a runtime residual.

This is the most important negative finding from the sandbox run. A high AUC is insufficient when the induced action policy still loses money out of seed.

## Promotion replay of Wave 19B

### FRONT_Q2_990

- robust delta: -0.0078125
- target delta: 0
- direct V32 score: 0.4375
- cash ratio: 0.99990
- hard/safe evidence: missing because the held-out run did not use the fixed 19D suites

### FRONT_Q4_990

- robust delta: -0.0078125
- target delta: 0
- direct V32 score: 0.4375
- cash ratio: 0.99986

Result: **REJECT** both.

## Population solver

FRONT_Q2 and FRONT_Q4 have the same smoothed matchup row in this panel and both are slightly worse than V32. PSRO has no strategically useful specialist to mix yet.

## Decision

The architecture itself passes sandbox validation. It correctly:

1. recovers the real hard-regime signal;
2. filters opponent forecasts by unseen-family generalization;
3. detects that the current regret dataset is underpowered and overoptimistic under weaker grouping;
4. rejects both Wave 19B candidates;
5. refuses promotion when hard/safe-suite evidence is absent;
6. can now generate new deterministic one-decision counterfactual datasets from losses without notebook-specific mutation code.

The next compute wave should focus on counterfactual data generation across many independent hard/safe seeds with full runtime-state features, not on another immediate live submission.
