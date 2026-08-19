# Kaggriculture Project Status

Last updated: 2026-08-18

## Current control

**V32 Premium-First** remains the stable champion/control.

Exact runtime artifact:

`SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`

SHA-256:

`ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`

V32 is preserved by default. New strategies are expected to wrap it with sparse residual logic unless a replacement backbone independently proves superior.

## Active research program

The current program is **NeuroLoss**, a neuroscience-inspired loss-driven learning framework.

The project now treats a loss as the beginning of a causal investigation:

```text
loss
 -> regime diagnosis
 -> reverse replay
 -> one-decision counterfactual branches
 -> episodic / generalized learning
 -> sparse residual
 -> hard/safe/seat promotion gates
 -> live confirmation
 -> new losses
```

The neuroscience terminology is computational inspiration rather than a biological model.

## Current live ablation family

Five V32-derived experimental agents have been prepared:

- **N1 Dopamine** — minimal causal reward-prediction-error residual.
- **N2 Hippocampus** — episodic hard-regime memory rescue.
- **N3 LC** — loss-risk-gated adaptive plasticity.
- **N4 CLS** — episodic/generalized consensus before override.
- **N5 NeuroStack** — integrated regime, episodic, causal, and FarmLedger context.

See:

- `docs/NEUROLOSS_STRATEGIES.md`
- `experiments/neuroloss5/README.md`

## Important established findings

### Regime risk is real

A 640-game / 64-seed stress panel showed that visible exogenous regime features strongly predict V32 losses.

The whole-seed grouped model reached approximately:

- AUC: `0.921`
- Brier: `0.094`
- top-risk-quartile loss rate: `0.806`
- lift: `2.46x`

This motivates state-dependent plasticity rather than global strategy replacement.

### Opponent liquidation is predictable

FarmLedger leave-one-policy-family-out experiments showed strong generalization for several future-sale targets, with median linear AUC around `0.91` across the tested sale tasks.

However, direct forecast-based front-running did not improve paired gameplay.

Permanent lesson:

> Forecasts are context for value estimation, not automatic action triggers.

### Large counterfactual regrets exist, but are rare

Some individual HIRE or seed-purchase suppressions changed final margin by thousands of dollars.

But unconditional use of those interventions was harmful.

Permanent lesson:

> Learn the state gate, not the action rule.

### Whole-seed validation is mandatory

The first regret learner looked more reliable when grouping by seed + opponent. Correcting the split to hold out entire seeds revealed that the current branch dataset is underpowered at the independent-seed level.

Permanent lesson:

> AUC does not promote a policy. The induced out-of-seed policy must have positive realized value.

## Agentic framework status

Implemented under `src/kagv2/agentic/`:

- regime-risk modeling
- unseen-family forecast validation
- known-hard / surprise loss queues
- bounded intervention grammar
- deterministic one-decision counterfactual factory
- distributional regret learning
- hard/safe/seat/direct-champion promotion contract
- policy-population / PSRO reporting
- end-to-end evolution orchestration

Local CI covers the framework and the branch is maintained as a draft research PR until the new architecture has accumulated enough live evidence.

## Next major offline experiment

The next compute wave should generate a substantially larger counterfactual dataset across independent:

- hard seeds
- safe-control seeds
- seat-asymmetry seeds
- opponent families

Priority decision families:

- HIRE suppress / delay
- strawberry-seed half / suppress
- land timing
- wheat procurement / reserve only in high-risk regimes
- premium sale timing only when opponent forecasts pass unseen-family reliability gates

The target is a distributional residual-value learner that can estimate not only expected gain, but downside and win-flip probability under strict whole-seed validation.

## Long-term target

The project is moving toward a population of strategically distinct specialists rather than a single endlessly complicated policy.

Once genuine specialists exist, PSRO / double-oracle iteration can search for robust best responses against the evolving meta.

The desired loop is:

```text
champion
 -> learn from failures
 -> create specialist
 -> validate
 -> add to population
 -> solve robust response
 -> confirm live
 -> repeat
```

## Submission discipline

The ladder is a confirmation environment, not the primary optimizer.

Every future promoted submission should record:

- exact artifact SHA-256
- branch / commit
- offline promotion evidence
- hard/safe/seat results
- live timestamp
- rating trajectory
- informative replay IDs
- execution failures if any

Negative results remain part of the project history because they constrain the next search direction.