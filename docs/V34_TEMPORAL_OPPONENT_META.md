# V34 Temporal Opponent Meta: from static archetypes to strategy trajectories

## Live evidence entering V34

Current ladder observations still make V32 the control:

| candidate | live score | delta vs V32 |
|---|---:|---:|
| V32 runtime-verified premium-first | **2035.0** | control |
| N3 learned loss-risk adaptive | 1989.5 | -45.5 |
| N7 shadow-price option | 1983.0 | -52.0 |
| N5 NeuroStack | 1954.2 | -80.8 |
| N6 contextual liquidity router | 1547.7 | -487.3 |
| N1 dopamine | 600.0 | unresolved/poor |

The critical lesson is not that adaptation is bad.  It is that **classification
quality and response quality are different problems**.  N6 could recognize a
hard family extremely well and still choose a response that lost badly.

## New structural discovery from the exact V32 champion artifact

The runtime-verified V32 archive is more revealing than the ladder score alone.
Its strategic backbone is a 719-step tape-derived modal route learned from ten
official public replays.  The champion then adds narrow observation-driven weed
repair and premium-first market ordering.

That explains both its strength and its remaining ceiling:

- it begins from a highly optimized trajectory prior;
- it is extremely stable and therefore hard to break with noisy live signals;
- but most strategic choices are still open-loop with respect to the current
  opponent.

V34 does **not** throw this away.  V32 becomes the protected default policy and
V34 learns when a small best-response residual has earned the right to override
one decision family.

## The opponent is a trajectory, not a label

A strong opponent can change strategy several times in one game:

```text
EARLY EXPANSION
      |
      v
ANIMAL BUILD -----> INPUT ACCUMULATION
      |                      |
      v                      v
PREMIUM PRODUCTION -----> LIQUIDATION
                               |
                               v
                         TERMINAL DEFENSE
```

A snapshot classifier can call both players `ANIMAL_HEAVY` even when one is
building animals and the other is liquidating them.  Those states require very
different responses.

V34 therefore represents an opponent with three levels of belief:

1. **actor/style prior**: what kind of policy this opponent resembles overall;
2. **current strategy motif**: what they appear to be doing now;
3. **change probability / segment age**: whether the current motif is stable or
   whether a pivot is underway.

## Online-safe observations

The submitted agent may use only information visible in the game observation.
The temporal model tracks deltas and slopes of:

- opponent cash;
- temporary hand count;
- quadrant expansion;
- crop mix;
- animal mix;
- ready-to-harvest composition;
- pasture/coop construction;
- market inventory shocks by product;
- market prices as context;
- short and long EWMA versions of the above.

The tracker intentionally does not need opponent private inventory or replay
metadata.

## Change detection

V34 combines two timescales:

```text
short EWMA  ~ "what has the opponent done recently?"
long EWMA   ~ "what has this phase usually looked like?"
```

The disagreement between the two feeds a bounded CUSUM.  A change is not
confirmed from one unusual turn.  It requires persistent evidence across
multiple observations.

This gives us a cheap BOCPD-like runtime signal without carrying a 719-element
run-length posterior.

The runtime exposes:

```text
motif posterior
motif confidence
change probability
confirmed-change flag
segment age
number of observed strategy pivots
```

## Replay-trained strategy motifs

Offline, we are allowed to inspect the opponent's real replay actions.  We use
those actions as an **oracle only to discover the latent phase vocabulary**.
They are never runtime features.

Candidate motifs should emerge from the data rather than being hard-coded, but
human-readable names can include:

- EXPANSION
- CROP_BUILD
- ANIMAL_BUILD
- INPUT_ACCUMULATION
- OPERATIONS
- PREMIUM_HARVEST
- LIQUIDATION
- TERMINAL_DEFENSE

Training procedure:

1. convert replays to turn frames;
2. join the opponent row for offline action labels;
3. derive public opponent-state deltas;
4. smooth on 4/8/16-turn windows;
5. detect within-game strategy segments;
6. cluster segment summaries into motifs;
7. fit runtime centroids using **public features only**;
8. learn motif transition probabilities;
9. validate motif vocabulary with entire opponent submissions held out.

The implementation begins in `src/kagv2/temporal_meta.py` and the hot-path
tracker is `submission/temporal_opponent_model.py`.

## The response zoo must be residual, not replacement agents

The failed adaptive agents taught us not to switch the whole farm brain merely
because the opponent looks difficult.

V34's policy zoo should therefore be a set of **small response operators around
exact V32**:

### 0. V32

Exact no-op champion.  Every uncertain state returns here.

### 1. CAPITAL_HOLD

Protect persistent capital by suppressing only a demonstrably redundant
expensive temporary hand.  This is the V33 WorkGraph idea.

Useful against an opponent whose expansion makes persistent asset timing more
important than matching labor count.

### 2. PREMIUM_FRONT

Advance or reorder a premium sale only when the model predicts an imminent
opponent supply shock and a paired branch shows that the timing changes win
probability, not merely final cash.

This is much narrower than N7's generic shadow-price option.

### 3. SUPPLY_PATIENCE

Delay one sale when an opponent has just liquidated the same product and the
next-turn price recovery has positive lower-tail value.

### 4. INPUT_RESERVE

Preserve/buy a bounded amount of wheat only when the opponent's phase implies a
real supply squeeze **and** our own service graph predicts feed risk.

This is deliberately stricter than N6's feed-first routing.

### 5. LAND_RACE

Protect cash around a verified land/animal expansion cliff if the opponent has
entered a persistent expansion phase.  It may suppress an expiring cost, but it
never invents an untested land purchase by itself.

### 6. TERMINAL_SHIELD

Late-game win-preservation residual: freeze risky expansion and prioritize
realizable liquidation when a public lead is already buffered.

### 7. TERMINAL_CHASE

Research-only until causal evidence exists.  A losing position is not license
to perform random aggression.

## Train responses on policy value, not strategy labels

For each state/phase and each residual `r`, we need paired counterfactuals:

```text
exact V32 from state S
vs
exact V32 + residual r from the same state S
```

Primary labels:

```text
P(loss/draw -> win | r)
P(win -> loss | r)
paired win-score delta
paired final-margin delta
Q10 / CVaR margin delta
```

The best-response gate is trained on these labels.

A response is not promoted because it predicts an opponent motif correctly.
It is promoted because, conditional on the belief trajectory, it produces a
positive lower confidence bound on **game outcome value**.

## Dynamic response selector

`submission/temporal_response_selector.py` implements the intended runtime
contract.

For each residual and motif it consumes precomputed:

- paired win-score delta;
- V32-win-to-loss flip probability;
- standard error;
- sample support.

At runtime it integrates these values against the current motif posterior and
uses a conservative score:

```text
lower_value
  = E[win_delta]
    - z * uncertainty
    - lambda * P(V32 win -> residual loss)
    - low-confidence penalty
    - change-instability penalty
```

A specialist must beat both zero and the currently selected policy.  Entering a
specialist requires persistent evidence; returning to V32 is intentionally
faster.

## Why change probability should make us *more* conservative

A tempting design is:

> "We detected a strategy switch, switch our policy immediately."

That recreates N6 in temporal form.

The correct design is:

> "We detected that the old model is no longer trustworthy.  Temporarily widen
> uncertainty, collect evidence for the new motif, then switch only if a
> specific response has proven value in that belief region."

The change detector is therefore an uncertainty signal first and an action
trigger second.

## Training campaign

### Wave T0: exact-control lock

- SHA-bind the 2035 V32 archive.
- Verify both seats and runtime packaging.
- No new agent is allowed to call itself V32-preserving without exact parity
  when all gates are inactive.

### Wave T1: temporal replay warehouse

- Reparse the strongest available public population.
- Keep full turn resolution for strategic events.
- Group validation by opponent submission/actor, never random rows.

### Wave T2: phase discovery

Train 6, 8, 10 and 12 motif vocabularies.

Select based on:

- actor-held-out motif stability;
- transition entropy;
- segment duration plausibility;
- ability of public features to recover the replay-oracle phase;
- downstream best-response separation.

The last metric matters most.

### Wave T3: synthetic switch laboratory

Create opponents that intentionally switch halfway through a game:

- crop -> animal;
- expansion -> liquidation;
- conservative -> premium dump;
- animal -> cash defense;
- normal -> terminal liquidation.

Measure:

- change detection delay;
- false alarms per episode;
- motif reacquisition delay;
- action regret caused during the uncertainty window.

### Wave T4: residual policy zoo

Generate variants within one decision family at a time.  Search thresholds and
quantities offline, then freeze candidates before evaluation.

Do not combine residuals yet.

### Wave T5: response matrix

For every opponent motif/family and residual:

- both seats;
- paired seeds;
- independent opponent actors;
- enough samples for win-flip confidence intervals.

This creates the matrix consumed by `TemporalResponseSelector`.

### Wave T6: dynamic meta-controller

Compare:

1. exact V32;
2. best static residual;
3. static archetype router;
4. temporal motif router without change detector;
5. temporal motif + change detector;
6. temporal motif + change detector + conservative action-value gate.

This ablation tells us whether temporal reasoning itself is earning value.

### Wave T7: held-out confirmation

Freeze all thresholds and test on entirely unseen opponent submissions and
seeds.  The selector must not be tuned after this point.

## Promotion gates

A dynamic agent should clear all of these before a scarce Kaggle slot:

```text
paired win-score delta vs exact V32       >= +0.015
95% lower bound on win delta              > 0 if sample size permits
V32 win -> candidate loss flips           <= 1/3 of good flips
safe-family win delta                      >= -0.005
worst opponent-family delta                >= -0.01
both-seat regression                       none material
false strategy-change alarms               low and bounded
median change detection delay              <= 8 turns
Q10 paired margin delta                    >= 0
invalid episodes                           0
inactive exact-V32 parity                  100%
```

## Submission strategy

Do not send five correlated versions of one router.  Use ladder slots as
controlled sensors:

1. **V33 WorkGraph exact-V32**: one new action-value family only.
2. **V34 Temporal Conservative**: temporal detector + one best proven residual.
3. **V34 Temporal Portfolio**: two or three independently proven residuals with
   the conservative selector.
4. **V34 Robust Static Mix**: best residual mixture without within-game
   switching, to isolate the value of temporal adaptation.
5. Keep one slot for a clean replication/control if the ladder behaves
   unexpectedly.

The target architecture is not a bot that constantly changes its mind.  It is a
strong open-loop champion surrounded by a small set of **causally validated
reflexes**, with a temporal model deciding when the opponent has entered the
specific region where one of those reflexes is worth using.
