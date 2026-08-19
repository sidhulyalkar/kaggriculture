# N6 Contextual Liquidity Router

## Why N6 exists

The first NeuroLoss live probes produced a useful separation:

- V32 remains the stable live reference.
- N3 LC and N5 NeuroStack validated successfully and entered the ladder, but their current displayed ratings remain below V32.
- N1 Dopamine still displays the default 600 rating. Kaggriculture only actively tracks the latest two submissions, so this should not be interpreted as a completed performance estimate.

The lesson is not to add more model complexity. It is to make adaptation more selective.

## Hypothesis

> A strong open-loop backbone should remain untouched in ordinary games, while high-confidence hard-matchup states should activate only small operational priorities that directly protect production.

N6 therefore keeps exact V32 as its default policy and adds a public-state hard-archetype detector trained from Wave 18C.

Positive training families:

- Adaptive
- Ranker

Negative/reference families include Soil, Findings, Melon, Strict, and V16.

Whole-seed grouped out-of-fold performance:

- AUC: **0.9930**
- gate threshold: **0.97**
- OOF precision at the gate: **1.000**
- OOF recall at the gate: **0.582**

N6 requires **three consecutive** high-confidence observations after day 4 before committing to hard-matchup mode.

## Strategy modes

N6 carries a small internal strategy state machine:

```text
V32
  |
  +-- high-confidence hard archetype --> HARD_OBSERVE
                                         |
                                         +-- thin wheat/feed cover --> FEED_FORTRESS
                                         +-- large cash deficit ----> CASH_DEFENSE
                                         +-- large enemy herd ------> ANIMAL_HEAVY
```

The important design choice is that diagnosis does not automatically imply a large policy rewrite.

### Enabled intervention 1: causal RPE correction

At step 262 the exact one-unit WHEAT seed purchase is suppressed.

Wave 18B measured this branch 20 times and found:

- 20/20 positive
- mean margin delta: +10
- median margin delta: +10

This remains the cleanest causal residual found so far.

### Enabled intervention 2: feed-first liquidity protection

In a high-confidence hard matchup, if wheat cover is below two units per visible animal and V32 already plans a `BUY_PRODUCT WHEAT` after one or more HIRE orders, N6 moves that existing wheat purchase immediately before the first HIRE.

Crucially:

- no new market volume is created;
- wheat quantity is unchanged;
- crop mix is unchanged;
- worker route is unchanged;
- land timing is unchanged;
- animal targets are unchanged;
- only the execution priority of an already-planned feed purchase changes.

The economic rationale is that daily hands are expendable while losing animal production to feed scarcity can damage several future days. The shared wheat market also means an opponent can change the price before a late-slot purchase executes.

## What N6 deliberately does not do

We tested and rejected broader variants before packaging N6:

- unconditional HIRE suppression;
- delayed land purchases;
- global melon-to-wheat rewrites;
- blanket premium front-running;
- broad sell-order permutations;
- forcing all productive buys before hires.

Several of these looked strategically plausible but produced large paired regressions locally. N6 leaves them disabled.

## Local validation

Exact tar was extracted and imported independently. The dependency-free repository mirror was then used on three seed panels against exact V32 and raw Soil.

| suite | opponent | games | N6 score | mean margin |
|---|---|---:|---:|---:|
| fresh | V32 | 16 | 0.9375 | +10.0 |
| fresh | Soil | 16 | 1.0000 | +270.0 |
| hard-19D subset | V32 | 16 | 0.5000 | +10.0 |
| hard-19D subset | Soil | 16 | 0.5000 | +248.1 |
| safe-19D subset | V32 | 16 | 0.8125 | +10.0 |
| safe-19D subset | Soil | 16 | 0.9375 | +351.9 |

On the same Soil seed subsets, V32 had the same win scores and exactly $10 lower mean margin, which is the intended footprint of the causal RPE residual when the hard router stays dormant.

A reconstructed sample of Wave 18C states also confirmed that the 0.97 gate activates frequently for Adaptive/Ranker examples and did not activate on sampled Soil, Findings, or Strict states.

## Submission artifact

`SUBMIT_N6_CONTEXTUAL_LIQUIDITY_ROUTER.tar.gz`

SHA-256:

`6217201f8333317f63d1563085962cd2533330655baeead27f04e4d60657bae3`

Parent V32 SHA-256:

`ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`

## Recommended live description

`N6 Contextual Router | exact V32 + high-confidence hard-matchup detection + feed-first liquidity defense`

## What we want to learn

N6 is a test of **selective strategy arbitration** rather than model scale.

If N6 improves on N3/N5 while preserving V32-like performance, the next wave should expand the strategy library one mechanism at a time. If it does not, the hard-archetype detector remains useful as research infrastructure, but feed-priority alone is not enough to solve the difficult matchups.