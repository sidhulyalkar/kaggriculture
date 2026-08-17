# Experiment Protocol

## Primary metric

Pairwise win rate, both seats, against a representative opponent population.

## Secondary diagnostics

- final cash;
- cash margin;
- invalid/no-op action rate;
- useful worker-action rate;
- crop loss/weed rate;
- animal escape rate;
- shed overflow/lost inventory;
- market revenue by product;
- unsold terminal inventory;
- per-turn latency.

## Controlled A/B rule

A promotion experiment should change one coherent subsystem at a time:

- macro portfolio;
- market timing;
- routing/task assignment;
- opponent classifier;
- future supply predictor;
- liquidation logic.

Do not merge unrelated changes before attribution is established.

## Seed protocol

- evaluate both seats;
- use a fixed development seed set;
- maintain a separate held-out seed set;
- expand to fresh seeds before promotion;
- report mean and paired uncertainty when sample size justifies it.

## Population protocol

At minimum include:
- current champion;
- premium-crop meta;
- wheat-heavy counter;
- livestock-heavy agent;
- shop-adaptive agent;
- randomized/noisy variant.

Replay-derived archetypes should replace hand-authored approximations as soon as they are available.

## Learned-model protocol

Use actor/submission grouped validation. Never randomly split adjacent turns from the same replay into train and validation.

A learned component is promoted only if:
- held-out performance improves;
- tournament performance improves;
- it remains runtime-safe;
- confidence gating has a deterministic fallback.

## Ladder protocol

The leaderboard is a confirmation environment, not the hyperparameter optimizer. Record:
- submission ID;
- git commit SHA;
- description;
- ladder rating over time;
- episodes played;
- replay IDs;
- opponent and result where public;
- any detected execution failure.
