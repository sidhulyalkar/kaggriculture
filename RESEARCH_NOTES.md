# Kaggriculture Research Notes

Last updated: 2026-08-18

## Core competition framing

Kaggriculture is a 720-turn, two-player farming economy in which both agents interact with the same market. The best agent is therefore not simply the farm that produces the most gross value in isolation. It is the policy that converts production into final bank cash more reliably than a changing opponent population.

The research program has converged on a layered architecture:

```text
deterministic mechanics
+
strong validated champion route
+
opponent / regime inference
+
sparse counterfactual residuals
+
robust promotion gates
```

The current champion/control is V32.

## Major strategic shift

The main research question has shifted from:

> What globally better farm schedule should replace the current controller?

into:

> When and why does the current champion lose, and can those losses teach us a small state-dependent correction that transfers to new seeds?

This is the foundation of the NeuroLoss program.

## Loss-driven learning thesis

A loss should produce four kinds of information:

1. **prediction error** — was the outcome more surprising than expected?
2. **causal regret** — which earlier decisions would actually have changed the final relative margin?
3. **recurrence** — is this state likely to happen again?
4. **confidence** — how many independent seeds support the same lesson?

The priority of a learning event can be thought of as:

```text
priority
  = recurrence
  × expected policy gain
  × surprise
  × confidence
```

This prevents the research loop from overreacting to spectacular but one-off branches.

## Neuroscience-inspired decomposition

The neuroscience terminology is used as a computational analogy:

- **Dopamine / RPE** — unexpected negative outcomes create a teaching signal.
- **Hippocampus** — preserve rare but important episodes and retrieve similar failure states.
- **LC / adaptive plasticity** — alter willingness to deviate based on predicted baseline failure risk.
- **CLS** — combine fast episodic memory with slow population-level generalization.
- **Go / No-Go** — model upside and downside separately rather than relying on a single mean-value estimate.

The resulting live ablation family contains N1 Dopamine, N2 Hippocampus, N3 LC, N4 CLS, and N5 NeuroStack.

## Key experimental findings

### Unconditional residuals are dangerous

Broad wheat, hiring, land, and market overrides frequently either failed to activate or reduced broad performance. This does not imply that the underlying action is always wrong. It implies that the correct research target is the state gate.

### Counterfactual branches show large local effects

Individual one-decision branches occasionally improve final margin by several thousand dollars. Yet the same mutation can have strongly negative average value.

Conclusion: learn the conditional value of a departure from V32 rather than the global desirability of an action.

### FarmLedger generalizes

Near-term opponent selling remains predictable even when holding out an entire opponent policy family. This supports the idea that public game state contains transferable economic information rather than only policy-identity signatures.

### Prediction does not imply exploitation

Forecast-gated premium front-running failed to improve fresh paired gameplay despite strong opponent-sale prediction.

Conclusion: an opponent forecast should be an input into counterfactual action valuation, not a reflexive market command.

### Hard regimes are predictable

The 64-seed stress experiment showed that town/seed/early-state features strongly predict when V32 fails. Whole-seed grouped OOF AUC is around 0.921.

Conclusion: the agent should be conservative in regimes where V32 is likely to win and more exploratory only where the baseline is already vulnerable.

### Whole-seed validation matters

The regret learner initially looked safer under seed+opponent grouping. Holding out entire seeds exposed much larger uncertainty.

Conclusion: never let one seed appear in both train and validation through different opponent families when learning strategic residual value.

## Current live experiment

NeuroLoss-5 is a five-agent mechanistic ablation family built from the exact V32 runtime artifact.

The first live comparison is designed around:

```text
N1 minimal causal correction
N3 adaptive regime plasticity
N5 integrated stack
```

followed by:

```text
N2 episodic retrieval
N4 fast/slow consensus
```

Each hosted loss should be treated as a future reverse-replay candidate rather than just a rating decrement.

## What to collect from live episodes

Where possible preserve:

- submission SHA
- opponent
- seat
- replay ID
- final reward
- rating before/after
- whether a residual activated
- regime-risk trace
- opponent forecast trace
- whether the loss was predicted-hard or surprising

The most valuable new data is not necessarily the worst loss. Surprise losses are especially important because they reveal holes in the current regime model.

## Next offline target

The next major CPU wave should generate a much larger causal branch dataset across many independent seeds.

Priority mutations:

- HIRE suppress/delay
- strawberry-seed half/suppress
- land timing
- wheat procurement/reserve in high-risk regimes
- premium sale timing only when the underlying forecast generalizes to held-out families

The learned output should estimate a distribution, not just a mean:

```text
P(DeltaMargin > 0)
E[DeltaMargin]
Q10(DeltaMargin)
P(loss -> win)
```

Runtime intervention should be allowed only when the induced policy itself has positive whole-seed held-out value.

## Population-level direction

Once multiple specialists demonstrate distinct payoff profiles, use the existing equilibrium / PSRO machinery to move beyond a single monolithic policy.

Desired population examples:

- V32 stable control
- hard-regime capital specialist
- feed/wheat-deficit specialist
- early-expansion specialist
- anti-premium-liquidation specialist
- terminal-control specialist

A useful population is one whose members cover different failure modes. Five versions of the same residual threshold are not strategic diversity.

## Research discipline

- preserve exact champion hashes;
- record infrastructure failures separately from strategy failures;
- require both-seat paired evaluation;
- use whole-seed splits;
- use family holdout for opponent models;
- retain hard/safe/seat suites;
- promote policies, not predictive metrics;
- keep negative findings in the experiment ledger;
- treat the ladder as confirmation rather than optimization.