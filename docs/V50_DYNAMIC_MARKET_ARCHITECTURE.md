# V50 Dynamic Market Architecture

## Why V50 exists

The H6 / V46 / V47 lineage repeatedly produced attractive local promotions and weak Kaggle transfer. The response is not another route-map mutation. V50 separates execution validity, information learnability, strategy construction, and external promotion so each claim can be falsified independently.

## Scientific gates before a submission

### Gate A — observation parity

The Kaggriculture environment can omit `observation.step` for seat 1 while synchronizing `day` and `hour`. A parity shim is useful only if three separate claims hold:

1. the engine asymmetry is reproduced;
2. the missing clock materially changes the candidate's action trace;
3. restoring the clock improves external/current-meta W/L without hurting seat 0.

V49B measures claims 2 and 3. A bug existing in the engine is not sufficient reason to consume a Kaggle slot.

### Gate B — opponent-sale learnability

V50 predicts whether an opponent will issue a `SELL` for each product within the next three turns. Features are restricted to public state available before simultaneous actions:

- day/hour and canonical competition clock;
- both public farms and unit positions;
- visible crop/animal composition and held yield on structures;
- market inventory and price;
- unlocked shops and exact default town-demand cadence;
- public money, hands, and unlocked quadrants.

`observation.private`, hidden shed stock, hidden carried inventory, and future actions are forbidden as inputs. Replay actions are labels only.

A commodity is considered learnable only if held-out evaluation reaches both:

- AUROC >= 0.65;
- top-decile precision lift >= 2.0 over prevalence.

The probe also compares a market-only feature set with the full public farm state. If market-only prediction is within 0.02 AUROC of the full model, runtime should use the smaller representation.

## Proposed runtime stack

```text
public observation
       |
       v
seat-safe state normalization
       |
       +------------------------------+
       |                              |
       v                              v
market/town state               opponent farm state
       |                              |
       +---------------+--------------+
                       v
               compact belief state
                       |
          +------------+-------------+
          |                          |
          v                          v
  sell-hazard forecast       production pressure
          |                          |
          +------------+-------------+
                       v
              marginal-value layer
                       |
        +--------------+---------------+
        |              |               |
        v              v               v
 livestock target   crop target   liquidity/land/labor
        |              |               |
        +--------------+---------------+
                       v
           deterministic farm executor
                       |
                       v
             market action residual
```

The deterministic executor remains valuable. What changes is the authority above it: fixed routes such as `8c6s`, `10c4s`, and `6c12s` become reference operating points rather than the strategy itself.

## Dynamic production objective

For a candidate unit of production, reason approximately in marginal value:

```text
marginal value
  = expected future harvest * expected sale value
  + fertilizer side-stream value
  - feed/input cost
  - labor and walking opportunity cost
  - land opportunity cost
  - liquidity cost
  - expected opponent-glut penalty
```

This permits the same first shop to produce different farms depending on market inventory, existing rival capacity, sale hazard, and cash state.

## Market microstructure

The engine processes player market queues before deterministic town consumption. Market inventory therefore contains usable information about recent external supply. Existing `src/kagv2/market_microstructure.py` already implements exact sale-revenue and delay-loss calculations and should be reused rather than rewritten.

Important constraints:

- only WHEAT and FERTILIZER can be bought via `BUY_PRODUCT`;
- premium products can crash rapidly toward the $1 floor;
- at the floor, sold units are not added to public market inventory, creating censored opponent-flow observations;
- duplicate shop instances accumulate demand;
- single-product shops consume 2x per tick;
- shop demand ticks every 4 turns and town-center demand every 24 turns under defaults.

Beliefs should therefore carry uncertainty, especially for floor-censored MILK/WOOL/STRAWBERRY/MELON flows.

## Promotion contract

Internal self-play has zero promotion weight. It is retained only for debugging, regression detection, and mechanism isolation.

A candidate may promote only when it:

1. improves current external W/L by at least 0.02;
2. does not regress recent replay W/L by more than 0.01;
3. does not regress worst-family W/L by more than 0.02;
4. has no external family below 0.35;
5. does not regress either seat by more than 0.03;
6. has zero invalid external games.

The implementation lives in `swarm/external_promotion.py`.

## Two active submissions

The second active submission should not be a correlated clone of the first. Among externally qualified candidates, choose the pair that maximizes the floor and then mean of per-family best coverage, subject to both members being individually competitive. This turns the two active slots into a robust population probe rather than two noisy measurements of the same lineage.

## Development order

1. V49B: establish whether parity has a competitive effect.
2. V50 sale-intent probe: establish whether opponent market behavior is learnable.
3. Distill only validated predictive signals into lightweight runtime code.
4. Build dynamic portfolio targets above the deterministic executor.
5. Evaluate against current external agents and recent replay teachers, both seats.
6. Apply external-only promotion gates.
7. Spend one Kaggle slot on a single causal change before combining improvements.
