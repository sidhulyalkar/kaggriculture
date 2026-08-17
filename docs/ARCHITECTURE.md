# Architecture

## Design objective

Maximize expected pairwise ladder win probability while keeping the low-level executor deterministic, testable, and comfortably under the per-turn runtime budget.

The system is deliberately hierarchical:

```text
Episodes Index / public replays
          |
          v
Replay Data Factory
          |
   +------+------+----------------+
   |             |                |
   v             v                v
Ladder       Macro Miner      Conditional
Strength     + Policy Zoo     Reactions
   |             |                |
   +-------------+----------------+
                 v
        Opponent archetype model
                 |
       +---------+----------+
       |                    |
       v                    v
Future-supply model   Policy payoff matrix
       |                    |
       |              Robust CEM search
       |                    |
       |              Meta-equilibrium mix
       |                    |
       +---------+----------+
                 v
       Confidence-gated selector
                 |
       Exact deterministic executor
                 |
          Kaggle submission
```

## Modules

### 1. Replay Data Factory

`src/kagv2/replay.py` and `src/kagv2/schema.py`

Responsibilities:
- discover episode-index schema;
- parse replay JSON;
- normalize player trajectories;
- build turn-level and daily tables;
- create future-action labels;
- keep engine-era metadata.

### 2. Ladder Forensics

`src/kagv2/ladder.py`

Responsibilities:
- deduplicate matchups;
- fit Bradley-Terry opponent-adjusted strength;
- quantify macro action entropy/open-loopness;
- separate raw cash from actual win outcomes.

### 3. Strategy + Conditional-Reaction Miner

`src/kagv2/macros.py` and `src/kagv2/reactions.py`

Responsibilities:
- create episode macro profiles;
- cluster recurring strategies;
- distill day-indexed target schedules;
- detect market shocks and high-variance events;
- cluster **reactions to events**, not only 720-turn raw action traces;
- strength-weight observations so successful ladder behavior matters more.

Conditional reaction features are especially useful for distinguishing two agents that have nearly identical farms but behave differently when strawberry/melon prices collapse.

### 4. Predictive Models

`src/kagv2/models.py` and `src/kagv2/runtime_features.py`

Responsibilities:
- train CPU-friendly future-supply models;
- train diagnostic win/value models;
- estimate opponent archetype probabilities;
- export only runtime-safe public feature sets;
- distill models to tiny JSON / pure-Python arithmetic.

### 5. Robust Best-Response Search

`src/kagv2/cem.py`

CEM searches a low-dimensional macro parameter vector **offline**. Two objectives are supported:

- `cem_optimize`: scalar pure best response for controlled experiments;
- `cem_optimize_population`: robust population objective combining expected value, worst-archetype value, and lower-tail CVaR.

The latter is the default candidate generator for the policy zoo because a ladder strategy must survive meta drift.

### 6. Meta-Equilibrium

`src/kagv2/equilibrium.py`

Responsibilities:
- build smoothed policy x opponent-archetype payoff matrices;
- solve a rectangular zero-sum game with multiplicative-weights/no-regret updates;
- report a duality-gap exploitability diagnostic;
- blend current-meta exploitation with a maximin equilibrium prior.

The equilibrium mixture is **not** used to randomly change low-level behavior every turn. It becomes a robustness prior for the live macro selector and can also be represented across multiple maintained ladder submissions.

### 7. Experimental Active Market Probes

`src/kagv2/probes.py`

Responsibilities:
- detect discontinuities in opponent next-turn selling as a function of market price;
- calculate exact price/inventory impact of tiny candidate sell probes;
- rank threshold-crossing probe candidates;
- enforce a paired A/B promotion gate.

Important engine constraint: crops cannot be bought back from the product market. Only WHEAT and FERTILIZER are legal `BUY_PRODUCT` items. Therefore the research target is **information acquisition / threshold testing**, not a fictional dump-and-scoop strategy.

Active probes are disabled in the live submission until they beat the non-probing control in large paired tournaments.

### 8. Deterministic Submission Controller

`submission/base_controller.py`

Owns mechanical correctness and remains independently useful if every learned artifact is deleted.

### 9. Tiny Live Meta Selector

`submission/meta_runtime.py`

At most once per in-game day it:
- consumes the opponent archetype posterior;
- multiplies a tiny precomputed payoff matrix;
- regularizes by the robust equilibrium prior;
- switches macro policy only if expected gain clears a hysteresis margin.

There is no hot-path CEM or sklearn dependency.

### 10. Selective Predictive Layer

`submission/predictive_agent.py`

Prediction is allowed to:
- choose among promoted precomputed macro policies;
- accelerate premium-product selling ahead of a predicted supply flood.

Prediction may not replace mechanical safety. Missing/malformed artifacts reduce to the deterministic fallback.

## State separation

A strict distinction is maintained between:

- **public runtime features**: legal inputs available to the agent during an episode;
- **private offline labels**: replay information that may be used as a training target but never included in live features.

This prevents accidental train/runtime leakage.

## Runtime budget philosophy

Heavy computation belongs offline:

- replay parsing;
- clustering;
- CEM;
- policy-zoo tournaments;
- equilibrium solving;
- probe threshold discovery.

Live computation is intentionally tiny:

```text
public state -> features -> archetype posterior -> matrix-vector score -> macro policy
```

The deterministic controller then executes that policy. This keeps the agent comfortably inside the action-time budget while still exploiting learned strategic information.
