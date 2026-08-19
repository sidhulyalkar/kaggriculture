# Winning Research Roadmap

Last updated: 2026-08-18

This document defines how the project should allocate compute, choose experiments, and decide which agents deserve leaderboard slots.

## Objective

Build an agent that wins by combining a strong production backbone with sparse, learned, opponent-aware residual decisions.

The current control is V32. Until evidence says otherwise, V32 is treated as a high-value invariant rather than a disposable baseline.

## Strategic thesis

The public field has converged on strong 30-day production programs, replay/tape backbones, stable routing, and modest market corrections. Our durable edge should come from capabilities that static tapes do not have:

1. infer when the current champion is entering a historically dangerous seed/town regime;
2. forecast near-term opponent economic behavior from public state;
3. branch counterfactually from exact V32 decisions and learn state-dependent regret;
4. preserve rare high-value exceptions episodically without immediately rewriting the global policy;
5. consolidate repeated lessons slowly across independent seeds;
6. apply only sparse, uncertainty-aware residuals unless a replacement backbone independently proves itself;
7. evolve a population of strategically distinct specialists and solve for robust responses.

The active implementation of this thesis is the **NeuroLoss** program.

## Current research stack

```text
                   LIVE LADDER
                       ^
                       |
             live experimental probes
                       ^
                       |
            runtime-safe sparse residuals
                       ^
                       |
             exact V32 champion anchor

Offline learning loop:

losses
  |
  +--> regime-risk model
  +--> FarmLedger opponent forecast
  +--> known-hard / surprise queue
  +--> counterfactual branch factory
  +--> episodic memory
  +--> distributional regret learner
  +--> hard/safe/seat promotion
  +--> specialist population / PSRO
```

## Why neuroscience-inspired organization?

The neuroscience labels provide a useful decomposition of the learning problem:

- **Dopamine / RPE:** unexpected loss creates a teaching signal.
- **Hippocampus:** retain rare but important episodes and retrieve similar failure states.
- **LC:** modulate plasticity based on predicted baseline failure risk.
- **CLS:** combine fast episodic learning with slow statistical consolidation.
- **Go / No-Go:** separately value upside and downside before allowing an override.

The analogy is computational, not biological.

## NeuroLoss-5 live ablation family

The first five agents are deliberately different hypotheses:

```text
N1 Dopamine
    minimal causal correction

N2 Hippocampus
    episodic memory rescue

N3 LC
    regime-risk adaptive plasticity

N4 CLS
    episodic + generalized consensus

N5 NeuroStack
    integrated regime + episodic + FarmLedger arbitration
```

This lets every live result answer a research question rather than simply producing another rating.

See `experiments/neuroloss5/README.md`.

## Promotion pipeline

### Gate 0: experiment integrity

Before strategic conclusions:

- dynamic imports registered in `sys.modules`;
- zero unexpected invalid games;
- exact source/artifact hashes recorded;
- no-op wrapper parity when an exact-anchor residual is claimed;
- actual intervention activation count reported.

Failure here means **INFRA INVALID**, not strategy rejection.

### Gate 1: mechanism evidence

A subsystem must show that its mechanism exists.

Examples:

- regime model: whole-seed group-held-out AUC + calibration;
- opponent forecast: leave-one-policy-family-out AUC;
- regret model: whole-seed OOF discrimination and value calibration;
- episodic retrieval: support from multiple independent matching episodes;
- market residual: actual order changes and local economic advantage.

### Gate 2: policy-level out-of-fold value

A predictive model cannot promote itself.

The policy induced by the learned gate must have positive realized out-of-fold value under whole-seed validation.

This gate was added after a regret model retained strong classification AUC while failing to produce a conservative positive-EV action policy.

### Gate 3: paired gameplay screen

Use same seed, both seats, exact control.

Kill candidates that:

- have invalid actions;
- do not actually activate;
- materially reduce target or robust performance;
- reduce aggregate cash dramatically even if a small win-rate sample is lucky.

### Gate 4: broad fresh holdout

Use fresh seeds and every available opponent family.

Primary metric: paired win delta.

Secondary metrics:

- paired final-margin delta;
- direct V32 score;
- worst-family delta;
- activation count;
- own cash ratio;
- per-turn latency.

### Gate 5: adversarial seed suites

Every candidate should be tested on:

- hard seeds;
- safe-control seeds;
- seat-asymmetry seeds;
- both seats.

A strong residual should improve losing regimes without damaging states where V32 is already reliable.

### Gate 6: independent confirmation

Freeze code and thresholds before this gate.

Use unseen seeds. Do not retune after reading the result. A failure sends the mechanism back to research rather than prompting threshold surgery on the confirmation set.

### Gate 7: runtime contract

Exact archive should pass:

1. official last-callable loader;
2. full Kaggriculture episode;
3. pack archive;
4. unpack exact archive;
5. loader again;
6. full episode again;
7. SHA-256 recorded.

### Gate 8: live ladder

The live ladder confirms offline evidence and supplies new failure cases. It is not the optimizer.

For every official submission record:

- artifact hash;
- git branch/commit;
- exact offline decision record;
- submission timestamp;
- rating snapshots and episode count;
- replay IDs for informative wins/losses;
- execution logs for failures.

## Compute allocation

When multiple CPU notebooks can run simultaneously, prefer orthogonal lanes:

- 30% counterfactual data generation on independent seeds;
- 20% regime / surprise modeling;
- 20% opponent forecasting and hidden-state inference;
- 20% residual value learning + calibration;
- 10% policy-population / adversarial evaluation.

Do not spend four notebooks on neighboring thresholds of the same mechanism.

## Immediate next major compute wave

The highest-value missing asset is a substantially larger **independent causal dataset**.

Generate bounded counterfactual branches across:

- fixed hard seeds;
- safe controls;
- seat-asymmetry seeds;
- new random seeds;
- multiple opponent families;
- both seats.

Priority intervention families:

1. HIRE suppress/delay around days 5-12;
2. strawberry-seed half/suppress around the first major expansion wave;
3. land timing around the second and third quadrant purchase;
4. wheat procurement/reserve only in high predicted loss-risk regimes;
5. premium sale timing only for forecast targets that pass unseen-family reliability.

The target learner should estimate:

```text
P(DeltaMargin > 0)
E[DeltaMargin]
Q10(DeltaMargin)
P(loss -> win)
```

The runtime residual should remain tiny.

## Population-level evolution

PSRO / double-oracle methods become useful once the project has genuinely different specialists.

A future population might contain:

- V32 stable control;
- hard-regime capital specialist;
- feed/wheat-deficit specialist;
- early-expansion specialist;
- anti-premium-liquidation specialist;
- terminal-control specialist.

The loop then becomes:

```text
current population
    |
    v
solve payoff matrix / robust mixture
    |
    v
identify exploitable weakness
    |
    v
train best response from loss/counterfactual data
    |
    v
validate specialist
    |
    v
add to population
    |
    +---- repeat
```

## Submission-slot policy

A live slot should represent a distinct hypothesis with a reason for existing.

Never spend a slot on:

- exact-byte clones;
- zero-activation wrappers;
- candidates that failed offline promotion when the goal is champion replacement;
- candidates created solely because an early rating snapshot is noisy;
- infrastructure-invalid experiments.

The NeuroLoss-5 family is a special case because the slots are intentionally being used as an **ablation experiment**. Each agent isolates a different learning mechanism and is tracked accordingly.

## Definition of real progress

A version number is not progress. Real progress is one of:

- a new causal mechanism with held-out support;
- a substantial reduction in a known failure mode;
- a new adversarial evaluation set that improves promotion quality;
- a learned residual whose induced policy has positive whole-seed out-of-fold value;
- a strategically distinct specialist that improves population robustness;
- a promoted agent that beats the champion on fresh paired games without sacrificing safe regimes;
- a reproducible live improvement consistent with the mechanism being tested.

Everything else belongs in diagnostics, not in the champion.