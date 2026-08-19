# NeuroLoss: Neuroscience-Inspired Learning From Failure

## Purpose

NeuroLoss is the current experimental learning framework for Kaggriculture.

Its objective is not to replace a strong farming controller with a black-box policy. Instead, it asks a narrower and more useful question:

> **When a proven strategy is likely to lose, can we identify a small alternative decision that has positive causal value, and can we learn when that lesson should be reused?**

The current champion lineage, V32, is treated as the stable behavioral prior. NeuroLoss adds sparse, uncertainty-aware residual decisions around that prior.

The neuroscience terminology is used as a **computational analogy**. The system is not intended as a biological model of dopamine, hippocampus, locus coeruleus, basal ganglia, or cortex.

---

# 1. Why learn from losses instead of replacing the whole policy?

Kaggriculture has a strong asymmetry between deterministic mechanics and uncertain strategy.

Deterministic mechanics include:

- worker routing;
- same-day watering;
- feed/care deadlines;
- shed logistics;
- legal market orders;
- land order;
- terminal liquidation.

The strategic uncertainty lives elsewhere:

- whether the current seed/town regime is favorable;
- whether an opponent is approaching a liquidation event;
- whether a hire, land purchase, or seed purchase is locally harmful;
- how much risk to take when the baseline itself is likely to lose.

Relearning everything end to end would discard useful structure.

NeuroLoss therefore decomposes the policy as:

```text
Action(state) = V32(state) + sparse learned residual(state)
```

where the residual is normally zero.

---

# 2. Negative prediction error as a learning trigger

A loss is useful when it violates what the agent expected.

Let:

```text
V_t = estimated probability of eventually winning from state t
```

At the end of a loss:

```text
prediction_error = 0 - V_T
```

A large negative error says that the policy was more confident than reality justified.

Rather than globally reducing confidence in every earlier decision, we replay the trajectory and search for decisions where an alternative would have materially improved the final relative margin.

This is the computational role played by the **Dopamine / RPE** analogy in NeuroLoss.

---

# 3. Reverse replay and causal branch search

The key research primitive is deterministic counterfactual branching.

For an observed decision at time `t`:

```text
same seed
same opponent
same seat
same history until t
```

we compare:

```text
A0 = exact V32 decision
A1 = suppress
A2 = halve
A3 = delay one turn
```

when those alternatives are legal for the decision type.

The resulting causal label is:

```text
DeltaMargin = final_margin(Ai) - final_margin(A0)
```

We can also track:

```text
DeltaScore
loss -> win flip
win -> loss flip
own cash change
opponent cash change
```

This is much stronger evidence than correlation.

"The agent lost after hiring" is weak evidence.

"Suppressing this exact hire on the same seed, seat, and opponent improves final margin by $7,000" is causal evidence.

---

# 4. Episodic memory: the Hippocampus analogy

Some failures are rare and highly state-specific.

Immediately folding one unusual loss into a global model risks overgeneralizing it.

NeuroLoss therefore distinguishes:

```text
fast episodic memory
vs
slow statistical consolidation
```

An episodic memory contains a compact representation of:

- visible game state;
- seed/town regime features;
- opponent public trajectory;
- V32 action;
- tested alternative;
- realized counterfactual gain;
- seat and opponent context.

At runtime, an episodic agent asks whether the current state resembles a previously important failure strongly enough to retrieve the old rescue action.

If not, it falls back to V32.

This is the core idea behind **N2 Hippocampus**.

---

# 5. Complementary learning systems

Fast episodic learning and slow generalization solve different problems.

Episodic memory can preserve a rare exception after one important experience.

A generalized model can discover recurring structure across many independent seeds.

The CLS-inspired arbitration is:

```text
episodic estimate = value from similar historical states
slow estimate     = value from population-level statistical learning
```

When the two agree strongly, confidence in an override increases.

When they disagree, the safest action is often to preserve V32 or request deeper offline investigation rather than forcing a decision.

This is the core idea behind **N4 CLS**.

---

# 6. Adaptive plasticity: the LC analogy

A fixed residual threshold is suboptimal because risk tolerance should depend on how good the baseline is in the current regime.

Suppose:

```text
rho = P(V32 loses | current visible regime)
```

If `rho` is low, V32 is probably already winning and the learner should be conservative.

If `rho` is extremely high, refusing every uncertain alternative simply preserves a likely loss.

So the override threshold can be state-dependent:

```text
low loss risk  -> high evidence threshold
high loss risk -> lower evidence threshold
```

This is the core idea behind **N3 LC**.

The regime model is learned with **whole seeds held out**, preventing the same exogenous seed state from leaking across folds through different opponent identities.

---

# 7. Go / No-Go value decomposition

Mean expected gain alone is not enough.

An intervention can have attractive average upside while containing catastrophic negative tails.

A more useful decomposition is:

```text
Q_plus  = expected positive upside
Q_minus = expected negative downside
```

Then:

```text
utility = Q_plus - lambda(state) * Q_minus
```

where `lambda(state)` is larger in safe regimes and smaller when the baseline is already very likely to lose.

In the current codebase, this principle is represented by the distributional regret learner and conservative policy-level promotion gates. The full runtime Go / No-Go value head is a future extension once enough independent counterfactual data exists.

---

# 8. FarmLedger as context, not a reflex

The opponent's hidden shed is private, but the game exposes enough public state to make near-term economic behavior surprisingly predictable.

FarmLedger uses visible features such as:

- opponent money;
- hands;
- quadrants;
- crop counts;
- harvest-ready crops;
- animal counts;
- market inventories;
- market prices;
- town progression.

Leave-one-policy-family-out validation showed that several near-term opponent sale targets remained highly predictable.

But direct front-running failed to improve gameplay.

That produced a permanent design rule:

> **A good forecast is context for decision valuation, not an automatic action trigger.**

N5 therefore uses FarmLedger to modify confidence/arbitration and reorder already-planned premium sales, rather than blindly adding large new sell quantities.

---

# 9. The initial five agents

## N1 Dopamine

**Question:** Can the cleanest counterfactually supported correction improve V32 without creating meaningful downside?

Design:

```text
exact V32
  +
minimal reward-prediction-error residual
```

The initial implementation is intentionally tiny. It tests the principle that a causal correction can be layered onto the champion without opening a broad policy surface.

Artifact SHA-256:

`5f2e723dd8f4be8589e3c1599efa242cc7d8561398afa68c40a6266108a15e25`

---

## N2 Hippocampus

**Question:** Can explicit memory of historically difficult regimes provide useful rescue behavior?

Design:

```text
exact V32
  +
episodic nearest-hard-regime retrieval
  +
sparse rescue actions
```

The current version uses representative hard/safe prototypes learned from the Wave 19D regime panel.

Artifact SHA-256:

`3d22f9c34bac119850fdd67b446636f0c1b5c9cc1e22373ad75e7d20f4e4a391`

---

## N3 LC

**Question:** Does baseline loss risk provide the correct control signal for policy plasticity?

Design:

```text
exact V32
  +
whole-seed regime-risk model
  +
risk-dependent sparse deviations
```

This is the cleanest test of the hypothesis that an agent should become more willing to depart from habit only in regimes where habit is likely to fail.

Artifact SHA-256:

`6fb37f9499dbfd10fce5ca573393be117bf27b2b8b90ff1ca15ff0fb71a9c708`

---

## N4 CLS

**Question:** Is an override safer when episodic memory and slow generalized risk agree?

Design:

```text
exact V32
  +
episodic risk
  +
generalized regime risk
  +
consensus gate
```

Artifact SHA-256:

`d7d40365706c3b275dbcf7e87380a021d375fdd8c8053d0adc6fbfaa91db6b25`

---

## N5 NeuroStack

**Question:** Does integrated arbitration outperform isolated mechanisms?

Design:

```text
exact V32
  +
generalized regime risk
  +
episodic memory
  +
minimal causal residual
  +
FarmLedger context
  +
conservative arbitration
```

Artifact SHA-256:

`cb50ebf13ecfedc19a7fb9c1f937b9fdaf7fcea237a70b354a0b458f726d0b4b`

---

# 10. Why these five are an ablation study

The point of submitting five agents is not to maximize the number of lottery tickets.

Each submission isolates a different computational hypothesis:

```text
N1  causal correction alone
N2  episodic memory alone
N3  regime-dependent plasticity
N4  fast + slow learning consensus
N5  integrated stack
```

That means even a losing submission can be scientifically useful.

Examples:

```text
N3 > N1
```

would support the idea that *when to adapt* matters more than the tiny residual itself.

```text
N2 > N3
```

would suggest that local episodic similarity captures something the generalized regime model loses.

```text
N4 > N2 and N3
```

would support complementary arbitration.

```text
N5 < N3
```

would warn that adding opponent-forecast context increases complexity without improving action value.

This is why the leaderboard is treated as a structured experiment rather than a set of anonymous submissions.

---

# 11. What data should be collected from each live agent?

For every hosted episode, preserve when available:

```text
agent artifact SHA
opponent
seat
replay
final reward / rating update
regime-risk trace
residual activation count
activation type
FarmLedger predictions
V32 counterfactual action
```

The most valuable games are:

- losses from states predicted to be hard;
- surprise losses from states predicted to be safe;
- wins where a residual actually fired;
- direct comparisons where two NeuroLoss variants faced similar regimes.

These games become the next reverse-replay queue.

---

# 12. Current limitation

The main bottleneck is **independent causal coverage**.

The first large counterfactual dataset contained many branches but only a small number of independent loss seeds. A model can look statistically impressive while still failing to generalize its action value to a new seed.

Therefore future residual models must use:

```text
whole-seed held-out validation
```

and must demonstrate positive realized value for the **policy induced by the model**, not merely good predictive metrics.

The next major compute wave should generate counterfactual branches across many more independent hard, safe, and seat-asymmetric seed regimes.

---

# 13. Long-term learning loop

The long-term goal is a continuously improving offline research agent:

```text
1. play current population
2. identify known-hard and surprise losses
3. reverse replay those losses
4. branch bounded alternative decisions
5. estimate distributional counterfactual value
6. store rare exceptions episodically
7. consolidate repeated lessons statistically
8. distill a tiny runtime residual
9. test hard / safe / seat / guard suites
10. add distinct survivors to a policy population
11. solve robust mixture / best response
12. confirm live
13. feed new failures back into step 2
```

This is the sense in which the project is becoming **agentic**: the research system is organized around diagnosing its own failures and generating the evidence required for the next generation.