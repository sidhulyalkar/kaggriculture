# V46 Adaptive Counterplay Strategy

## Objective

Maximize episode win probability against the evolving Kaggriculture population. Do not optimize raw cash as the primary objective. Treat the game as a non-transitive shared-market game in which matchup-specific best responses can dominate pooled-score improvements.

## What V45 taught us

The first automated full executable slate selected H6 Aggro over the exact Soil/V76 parent, but exposed a severe Moon-family weakness. Route imitation from winner action traces was not informative: learned route maps were empty and the route candidates were behaviorally tied to the parent. The NVIDIA council's global parameter and route proposals also produced no executable uplift.

The implication is not that adaptation is useless. It is that adaptation must be attached to **causal public signals** and judged against the family it is intended to exploit.

## Controller architecture

### Layer 1: deterministic production executor

Retain a proven route/schedule library and stable low-level worker choreography. This layer owns movement, build/plant/animal actions, task completion, pickup/drop logic and ordinary liquidation. It should be deterministic, fast and difficult to break.

Why: strong policies share long useful prefixes, and worker travel is a major hidden cost. Replanning low-level actions every turn creates churn without adding strategic information.

### Layer 2: regime and route selector

Make only a few macro decisions at moments when new information becomes public.

Candidate decision points:

- opening route at step 0 when justified by seed-known state
- first shop signal around step 72
- second shop signal around step 144
- optional late branch around step 216

Inputs:

- unlocked-shop prefix
- current prices and market inventory
- projected deterministic town/shop drain
- own cash and farm completion state
- opponent visible animal/crop shape
- opponent-family posterior

The selector chooses among already executable route experts rather than synthesizing cell-level actions.

### Layer 3: opponent belief state

Maintain a compact belief over opponent archetypes and latent supply.

Archetype evidence can include:

- first/second shop-conditioned farm decisions
- cow/sheep counts and acquisition timing
- pasture/crop mix
- public market inventory deltas after subtracting own sales and deterministic town drain
- inferred liquidation cadence
- route timing fingerprints
- cash gap trajectory

Do not force a single label. Maintain probabilities such as:

```text
P(Moon/sheep-overlay) = 0.72
P(Soil/Kaito-style)   = 0.18
P(other)              = 0.10
```

For each relevant commodity, maintain an opponent inventory interval or distribution, not false exactness:

```text
wool_estimate
wool_lower
wool_upper
wool_uncertainty
floor_sale_risk
private_loss_risk
```

The shared-market conservation equations give information about opponent supply, but $1-floor selling, DROP/overflow and ambiguous transitions widen the interval.

### Layer 4: adversarial market residual

This layer can modify only the market portion of the deterministic action when expected win value is positive.

Core actions:

1. **Pre-dump sell**: sell 1–4 turns before a high-probability rival liquidation.
2. **Town-drain wait**: delay a sale when deterministic town/shop consumption will create a materially better scarcity price before rival supply arrives.
3. **Commodity avoidance**: if a rival strongly specializes in wool or another premium product, switch macro production toward a less-contested complementary line rather than mirror-selling into the same glut curve.
4. **Scarcity buy/produce**: exploit tomato/carrot/egg only when shop demand, current inventory and time-to-production make the scarcity opportunity reachable.
5. **Liquidity guard**: never front-run so aggressively that the underlying route misses a required seed, animal, land or labor purchase.
6. **Terminal liquidation**: become increasingly myopic near the end of the season, but account for opponent dump ordering and floor risk.

## First targeted best response: Moon

The public Moon family is unusually interpretable. Its special overlay activates when the first unlocked shop is YARN_STORE and converts planned cow purchases into sheep, producing extra wool and selling it through a known schedule.

H6 already has a late sheep-heavy classifier and a three-turn market front-run. The weakness is timing: it waits for the rival farm shape to become obvious, while the first-YARN shop signal arrives earlier.

V46 therefore tests:

- H6 + first-YARN -> 6c8s
- H6 + first-YARN -> 8c6s
- H6 + first-YARN -> 10c4s
- H6 with stronger family-specific preemption fractions
- route-pivot + stronger family-specific preemption hybrids
- H6 generic preemption beginning at step 72 instead of 96

The promotion gate is family-aware: improve Moon by at least 15 percentage points and reach at least 50% against Moon, while keeping overall full-league W/L within 4 points of H6 and not worsening the worst-family floor.

## Second targeted best response: Soil/current parent family

If H6 remains weak against current Soil, separate the cause into:

- physical route mismatch
- market timing mismatch
- opponent classifier delay
- terminal liquidation mismatch

Do not change all four at once. Build one-factor best responses and then compose only interventions whose gains survive paired tests.

## Scarcity opportunist lane

The current engine intentionally makes tomato, carrot and egg scarcity profitable in some shop-demand regimes. Treat this as an option, not a default farm plan.

For each commodity compute an approximate opportunity score:

```text
expected scarcity revenue
- seed/animal capital
- worker-turn/travel cost
- time-to-first-output penalty
- opponent latent supply risk
- price-floor downside
- route displacement cost
```

Only take the option when the lower-confidence estimate is positive enough to justify diverging from the protected route.

## Search algorithm

Use successive halving rather than a flat full tournament.

1. **Family screen**: 5 paired seeds, both seats, only the intended target family.
2. **Representative league**: target family + H6 + exact parent + two orthogonal strong public families.
3. **Full league**: all current public families, both seats, multiple sealed seeds.
4. **Population exploitability check**: update the payoff matrix and ensure the candidate does not create a new catastrophic matchup.
5. **Kaggle probe**: only candidates with a causal mechanism and meaningful executable divergence consume a submission slot.

## Portfolio policy

Because the game is non-transitive, final strategy selection should use a payoff matrix rather than a single scalar leaderboard.

Maintain a population containing:

- strongest generalist
- current-meta aggressor
- Moon/sheep counter
- Soil/current-parent counter
- scarcity opportunist or other orthogonal hedge

Use PSRO-style iteration:

```text
population -> identify exploitable family -> search best response
           -> evaluate full payoff matrix -> retain useful response
           -> repeat
```

The two final live slots should be chosen for expected Bradley-Terry strength and complementary matchup coverage, not source-code novelty alone.

## Required telemetry

Every evaluation should retain:

- W/L/draw
- opponent family
- seed and seat
- first/second shop prefix
- first physical divergence step
- market-action divergence steps
- cash trajectory
- farm animal/crop counts at checkpoints
- inferred opponent inventory interval by commodity
- preemption events and units
- missed planned purchases caused by residuals
- terminal liquidation state

When authenticated Kaggle replay access is available, the same telemetry should be computed on real rated losses so offline-family weights can be calibrated to actual transfer.
