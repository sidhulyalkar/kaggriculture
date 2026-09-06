# V58 Opponent Policy Compiler

## Goal

Move Kaggriculture from a single strong macro route toward a two-timescale system:

1. **Between matches:** harvest the newest public top episodes, fingerprint strategy lineages, recover strong macro policies, and continuously rebuild a counter-policy library.
2. **Inside a match:** infer the opponent's likely lineage from legal public state, then make only state-compatible, bounded deviations from the selected macro backbone.

The runtime must never depend on replay-private fields. Replays may be used offline to label strategy families and future behavior, but the features distilled into the submission must be computable from the live observation.

## Why not copy the opponent verbatim during the game?

Many actions are path dependent. Land unlocks, worker positions, crop ages, animal placement, and inventories make a late switch between unrelated 720-turn tapes unsafe. V58 therefore separates **recognition** from **control**:

- recognize a strategy family early;
- predict what that family is likely to do next;
- counter only through compatible controls such as market timing, budget protection, terminal liquidation, and pre-qualified route forks that share the already executed prefix.

## Runtime architecture

```text
public observation
      |
      +--> shop/world signature
      +--> opponent public farm morphology
      +--> money / land / workforce trajectory
      +--> exact market-flow reconstruction
      |
      v
OpponentBelief
 P(family | history)
      |
      +--> family-conditioned sale / purchase hazard
      +--> likely route branch
      +--> confidence / novelty score
      |
      v
CounterPolicyRouter
      |
      +--> keep frontier macro policy by default
      +--> switch only among prefix-compatible route branches
      +--> bounded market preemption when expected value is positive
      +--> fail closed on novel / low-confidence opponents
```

## Recognition checkpoints

The initial compiler measures classification quality at turns 72, 120, and 144. The intent is to identify how early a useful posterior becomes possible without using the opponent's private state or hidden action field.

Strategy-family labels are built offline from the first 120 actions of public traces. To avoid treating tiny quantity changes as entirely new strategies, actions are converted to an operation/item skeleton and lineages are clustered by prefix similarity.

Runtime-visible features include:

- unlocked shop prefix;
- opponent money;
- unlocked land count;
- worker count and positions;
- hires today;
- public tile morphology: crop/coop/pasture/weed counts and crop/animal composition;
- shared market inventory and price trajectory;
- later, exact opponent market-flow estimates after subtracting our own known actions.

## Promotion contract

A V58 runtime policy is not eligible for submission merely because its classifier is accurate. Promotion requires all of the following:

1. Family recognition is evaluated with the target team excluded from its training set.
2. Runtime inputs are public-state only.
3. Every adaptive intervention is auditable and bounded.
4. The adaptive candidate is compared against the exact same macro backbone on both seats and disjoint seeds.
5. No meaningful regression is accepted against sibling/frontier families.
6. A new macro route discovered from public episodes may replace the backbone only after independent exact-engine qualification.

## Intended submission portfolio

Keep one stable frontier backbone active while V58 is developed. The second active slot becomes the exploration lane. V58 should replace that slot only after it beats the protected backbone or provides a demonstrably complementary matchup profile.
