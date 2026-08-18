# Kaggriculture: Replay Intelligence + Robust Meta-Agent

> **Two autonomous farmers. 30 days. 720 turns. One shared market.**
>
> Build a farm, route workers, keep crops alive, care for animals, expand land, read the economy, anticipate the opponent, and turn the whole operation into more cash than the agent across the market.

This repository is a CPU-first research and submission stack for Kaggle's **Kaggriculture** simulation competition. The goal is not merely to build a farm that makes money in isolation. It is to build an agent that wins **head-to-head** against an evolving population of other agents.

The core design rule is:

> **Do not ask machine learning to relearn deterministic mechanics.**

Routing, watering, feeding, harvesting, shed handling, labor reset, land purchase order, market-order constraints, and endgame liquidation belong in a deterministic controller. Learning is reserved for the uncertain strategic layer: **What is the opponent building? What are they likely to sell next? How will the shared market move? Which macro strategy gives us the best chance of winning this matchup?**

---

# 🌾 The game the agents are actually playing

Kaggriculture looks like a farming game, but strategically it behaves more like a compact real-time economy game with logistics, biological deadlines, and an opponent who can move the market underneath you.

## At a glance

| | Game mechanic |
|---|---|
| **Players** | 2 autonomous agents |
| **Horizon** | 30 in-game days × 24 turns/day = **720 turns** |
| **Farm** | A **10×10** board split into four 5×5 quadrants |
| **Starting land** | Northwest quadrant unlocked; the rest can be purchased |
| **Starting cash** | 3,000 |
| **Crops** | Wheat, carrot, tomato, strawberry, melon |
| **Animals** | Goose, cow, sheep |
| **Animal products** | Eggs, milk, wool, plus fertilizer |
| **Labor** | One persistent farmer + temporary farm hands hired each day |
| **Storage** | A finite-capacity shed at the center of the farm |
| **Economy** | Both players interact with the **same market inventory and prices** |
| **Winner** | The player with the most **bank cash** at the end |

Unsold inventory is not terminal wealth. A gorgeous shed full of melons on turn 720 is economically equivalent to a very decorative mistake.

## The farm

Each player controls a separate 10×10 farm. Only the northwest 5×5 quadrant begins usable.

```text
                  10 × 10 FARM

        ┌────────────────┬────────────────┐
        │                │                │
        │   NW: START    │   NE: $1,000   │
        │   25 tiles     │   25 tiles     │
        │                │                │
        ├──────── shed access ────────────┤
        │                │                │
        │   SW: $2,000   │   SE: $4,000   │
        │   25 tiles     │   25 tiles     │
        │                │                │
        └────────────────┴────────────────┘
```

Expansion is therefore an economic decision, not just a map unlock. Buying land creates future production capacity but removes cash that could have gone into seeds, animals, labor, or a better-timed market play.

The four inner-corner tiles provide access to the shed. Workers must physically route around the board, collect outputs, and return inventory to storage. A theoretically perfect farm plan can still lose if its logistics are sloppy.

## What a worker can do

Every farmer or temporary hand acts on the tile it occupies.

| Category | Actions |
|---|---|
| **Movement** | North, south, east, west, pass |
| **Crops** | Plant, water, fertilize, harvest, dig |
| **Structures** | Build coop, build pasture |
| **Animals** | Place animal, feed, care, harvest product, collect fertilizer |
| **Logistics** | Pick up from shed, drop/place into shed |

Meanwhile, the player can also submit market/economy orders:

```text
BUY_SEED       BUY_ANIMAL       BUY_PRODUCT
SELL           HIRE             BUY_LAND
```

Only wheat and fertilizer are directly buyable as products. Everything else must be grown, raised, or acquired through the farm itself.

## Crops are tiny scheduling problems

Different crops create different timing profiles.

| Crop | Seed cost | First yield | Production style | Base market price |
|---|---:|---:|---|---:|
| Wheat | 10 | Day 2 | finite harvest | 25 |
| Carrot | 20 | Day 2 | finite harvest | 35 |
| Tomato | 50 | Day 8 | ongoing | 60 |
| Strawberry | 100 | Day 10 | ongoing | 120 |
| Melon | 80 | Day 10 | finite harvest | 250 |

The agent cannot simply plant and forget:

- planting day already counts as an unwatered day;
- a new crop that is not watered before the first nightly refresh becomes a weed;
- ongoing crops produce on crop-specific intervals;
- finite crops have a useful harvest window and eventually decay;
- fertilizer can increase production, but only if the underlying watering requirement is met.

This creates a routing problem inside the strategic problem. If an agent plants twelve high-value tiles but cannot physically water them in time, it has not created twelve investments. It has created twelve future weeds.

## Animals are production assets with upkeep

| Animal | Cost | Structure | Product | First yield |
|---|---:|---|---|---:|
| Goose | 300 | Coop | Egg | Day 4 |
| Cow | 400 | Pasture | Milk | Day 8 |
| Sheep | 500 | Pasture | Wool | Day 6 |

Animals consume farm space and require attention:

- animals need wheat feed;
- two consecutive missed feeding days can make an animal escape;
- care + feed can bank an additional production bonus;
- animals periodically create fertilizer;
- fertilizer can be used on crops **or sold into the market**.

That makes wheat especially interesting. It can be a crop for sale, a strategic reserve for animal feed, or something the agent buys from the shared market to protect a larger animal economy.

## Labor is powerful, temporary, and nonlinear

The main farmer persists. Additional farm hands vanish every night and must be hired again.

Daily hire costs increase on a Fibonacci curve:

```text
1, 1, 2, 3, 5, 8, 13, 21, 34, ...
```

More hands mean more watering, harvesting, feeding, hauling, and construction capacity, but labor can quietly eat the margin it was hired to create.

The decision is not simply:

> "Can another worker do useful work?"

It is:

> "Is the marginal work this extra hand can complete today worth more than its escalating hire cost, and does that work unlock future value?"

## The shared market is where the opponent enters your farm

This is the core strategic twist.

Both agents sell into and buy from the **same market inventory**. Prices are functions of that shared inventory:

```text
scarcity  -> inventory falls -> price rises
glut      -> inventory rises -> price falls
```

Selling increases market supply and can push the price downward. Buying wheat or fertilizer removes supply and can push price upward.

Town demand pushes in the opposite direction. Shops periodically consume recipe ingredients from the market, for example:

```text
Bakery       -> egg + wheat
Pizza Shop   -> milk + tomato + wheat
Yarn Store   -> wool
Ice Cream    -> strawberry + milk + wheat
Smoothie     -> strawberry + milk
```

So prices are the result of three interacting forces:

```text
YOUR PRODUCTION
      +
OPPONENT PRODUCTION
      +
TOWN CONSUMPTION
      ↓
SHARED MARKET INVENTORY
      ↓
CURRENT + FUTURE PRICES
```

A crop can be excellent in a vacuum and terrible in a matchup.

If both agents build strawberry-heavy farms and dump inventory at the same time, the premium can collapse. If the opponent is about to flood milk into a healthy market, selling one day earlier may beat patiently waiting for a nominally better price that never survives.

This is why opponent modeling matters.

---

# 🧠 What does an agent actually have to think about?

A strong agent is continuously juggling several timescales.

### This turn

- Which worker is closest to the most urgent task?
- Which newly planted crop must be watered immediately?
- Is an animal one missed feed away from escaping?
- Is a worker carrying valuable inventory that should return to the shed?
- Are we about to overflow the shed?

### This day

- How many temporary hands are worth rehiring?
- Which crops should occupy the available tiles?
- Should we build more pasture or preserve crop capacity?
- Do we have enough wheat to feed the animal population tomorrow?
- Is today the right time to buy another land quadrant?

### This matchup

- Is the opponent crop-heavy or animal-heavy?
- Are they accumulating strawberries, melons, milk, or wool?
- Are their actions consistent with a known macro archetype?
- Is a supply flood likely in the next 24 turns?
- Which of our precomputed strategies is strongest against that archetype?

### This season

- Are long-maturation crops still worth planting?
- When should growth spending stop?
- When should inventory reserves become aggressive sales?
- How early should terminal liquidation begin so everything reaches cash before the final turn?

A useful mental model is:

```text
         BIOLOGY
     water / feed / grow
            │
            v
LOGISTICS -> FARM -> PRODUCTION
 workers      │
 routing      v
          INVENTORY
            │
            v
          MARKET <------ OPPONENT
            │              │
            v              │
           CASH            │
            │              │
            └---- WIN / LOSS
```

The farm is not the objective. The farm is a machine for creating **timed exposure to a shared economy**.

---

# 🎯 A concrete strategic example

Imagine it is the middle of the game.

Our farm has cows and strawberries. Milk and strawberry prices are currently healthy. The opponent has recently expanded pasture and its public farm state suggests a milk-heavy strategy.

A naive agent might say:

> "Price is good, but my reserve threshold says wait."

A matchup-aware agent can reason differently:

```text
1. Opponent pasture count increased.
2. Their inferred archetype is now animal-heavy.
3. The future-supply model predicts a milk sell burst within ~24 turns.
4. Current milk price is already above our acceptable reserve.
5. A large opponent sale would increase shared inventory and depress our exit price.
6. Sell part of our milk now.
7. Keep enough wheat and operating inventory to avoid damaging farm production.
```

Nothing about that decision requires an enormous neural network. It requires the right decomposition of **mechanics, prediction, and game theory**.

That decomposition is the central idea of this project.

---

# Why head-to-head play changes the optimization target

A game lasts 720 turns. Final bank cash determines the winner. The ladder rating is driven by win / loss / tie outcomes, so the central offline metric is:

```text
pairwise win rate
+ both seats
+ held-out seeds
+ realistic opponent population
```

Mean cash is useful for debugging, but it is not the promotion target.

An agent that earns slightly less cash on average but avoids catastrophic matchups can be a much stronger ladder agent than a brittle high-ceiling policy.

---

# Architecture

```text
              PUBLIC LADDER EPISODES
                       |
                       v
              Replay Data Factory
                       |
       +---------------+----------------+
       |               |                |
       v               v                v
 Ladder Strength   Macro Mining    Future Labels
 Bradley-Terry     + Open-loop     opp sells t+24
       |               |                |
       +---------------+----------------+
                       v
               Opponent Belief
             archetype posterior
                       |
         +-------------+-------------+
         |                           |
         v                           v
 Future Market Model           Policy Zoo
 predicted supply floods       robust CEM
         |                           |
         |                    payoff matrix
         |                           |
         |                    meta-equilibrium
         |                           |
         +-------------+-------------+
                       v
             Confidence-Gated
              Macro Selector
                       |
                       v
        Exact Deterministic Controller
        route / water / feed / harvest
                       |
                       v
              Kaggle submission
```

The live policy is intentionally small. Expensive search happens offline; deterministic execution and tiny predictive/meta calculations run during the game.

A parallel research branch mines **conditional reactions** around market shocks and evaluates small active-market probes. Probes remain disabled unless paired simulator experiments demonstrate a robust positive edge.

---

# Why this hierarchy

The public meta contains a strong clue that many competitive agents may be approximately **open-loop at the macro level**. If that is true, the search problem is much smaller than generic end-to-end RL:

```text
not:
720 turns × every low-level action

but closer to:
land timing
labor schedule
crop mix
animal mix
sell reserves
terminal timing
```

The repository tests this hypothesis rather than assuming it.

`src/kagv2/ladder.py` measures action-macro entropy for repeated submissions at the same day/hour. Low entropy among strong actors supports heavier use of macro search. High conditional variation supports more opponent-aware adaptation.

---

# Current agent layers

## 1. Exact execution controller

`submission/base_controller.py`

Owns mechanics that must never be guessed:

- farmer and temporary-hand routing;
- planting and same-day watering;
- harvest timing;
- animal feed/care/fertilizer collection;
- pickup/drop/place around the shed;
- daily labor rehiring;
- seed and animal acquisition;
- land expansion;
- shed-capacity protection;
- market-order limits;
- terminal liquidation.

If every learned artifact is deleted, the agent still plays a complete deterministic game.

## 2. Parametric macro policy

`submission/parametric_agent.py`

The macro controller exposes a compact policy vector covering:

- early/mid/late labor targets;
- cow and sheep targets;
- wheat/melon/strawberry allocation;
- premium-product sell reserves;
- fertilizer reserve;
- terminal liquidation start.

This is the space CEM searches offline.

## 3. Replay intelligence

`src/kagv2/replay.py`, `schema.py`, `features.py`, `ladder.py`

Public episodes become:

- turn-level Parquet;
- daily macro summaries;
- win/loss/margin labels;
- opponent next-horizon sell labels;
- Bradley-Terry strength estimates;
- open-loop scores.

The replay layer keeps a strict boundary between legal live features and private offline labels.

## 4. Strategy and reaction mining

`src/kagv2/macros.py` clusters recurring farm strategies and distills day-indexed macro schedules.

`src/kagv2/reactions.py` clusters **conditional responses** around high-variance events such as:

- strawberry/melon price crashes;
- market floods;
- market drains;
- abrupt price spikes.

This avoids clustering 720 turns of noisy low-level movement. Bradley-Terry strength weights emphasize reactions exhibited by successful ladder agents.

## 5. Predictive models

`src/kagv2/models.py`, `submission/runtime_model.py`

Initial learned targets:

- opponent sell volume over the next 24 turns;
- opponent macro archetype;
- diagnostic win/value estimates.

The runtime model is distilled to tiny pure-Python arithmetic. No sklearn inference is required in the submission hot path.

## 6. Robust population CEM

`src/kagv2/cem.py`

Two optimizers are available:

- `cem_optimize`: scalar best response for controlled experiments;
- `cem_optimize_population`: robust population search.

The robust objective combines:

```text
expected population utility
+ worst-archetype utility
+ lower-tail CVaR
```

This deliberately sacrifices some narrow peak performance to reduce the chance of collapsing when the ladder meta shifts.

## 7. Meta-equilibrium

`src/kagv2/equilibrium.py`

The policy zoo produces a policy × opponent-archetype payoff matrix. A multiplicative-weights/no-regret solver estimates a rectangular zero-sum equilibrium and reports a duality-gap exploitability diagnostic.

The final prior blends:

```text
current-meta exploitation
+
maximin robustness
```

The live agent does **not** run CEM or equilibrium search. Those are entirely offline.

## 8. Tiny live meta selector

`submission/meta_runtime.py`

Once per in-game day, the live agent:

1. updates the opponent archetype posterior;
2. scores precomputed macro policies against that posterior;
3. regularizes using the robust equilibrium prior;
4. switches only if the expected gain clears a hysteresis threshold.

This is a tiny matrix-vector calculation, comfortably suited to the action-time budget.

## 9. Predictive selling

`submission/predictive_agent.py`

The first learned market intervention is deliberately conservative:

> Sell premium inventory earlier when the model predicts a near-term opponent supply flood and the current price is still healthy.

This is lower risk than rebuilding the farm based on an uncertain prediction.

## 10. Experimental active-market probes

`src/kagv2/probes.py`

The code can detect price bands where opponent next-turn selling changes abruptly, then calculate exact market impact for small candidate sell probes.

Important engine reality:

- any product can be sold;
- only **WHEAT** and **FERTILIZER** are legal `BUY_PRODUCT` items.

Therefore a strategy such as "dump strawberries, then buy them back cheaply" is impossible. The only plausible use of a probe is **information acquisition / threshold testing**.

Probes are research-only and disabled by default. Promotion requires a paired control/probe tournament with a positive lower confidence bound.

---

# Repository layout

```text
.
├── README.md
├── STATUS.md
├── RESEARCH_NOTES.md
├── requirements.txt
├── pyproject.toml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ENGINE_CONTRACT.md
│   ├── EXPERIMENT_PROTOCOL.md
│   └── KAGGLE_NOTEBOOK_RUNBOOK.md
│
├── notebooks/
│   ├── 00_episode_index_audit.ipynb
│   ├── 01_replay_factory.ipynb
│   ├── 02_ladder_forensics.ipynb
│   ├── 03_macro_strategy_miner.ipynb
│   ├── 04_predictive_models_cpu.ipynb
│   ├── 05_cem_best_response_search.ipynb
│   ├── 06_build_v2_submission.ipynb
│   └── 07_meta_equilibrium_and_probes.ipynb
│
├── src/kagv2/
│   ├── constants.py
│   ├── schema.py
│   ├── replay.py
│   ├── features.py
│   ├── ladder.py
│   ├── macros.py
│   ├── reactions.py
│   ├── models.py
│   ├── runtime_features.py
│   ├── cem.py
│   ├── equilibrium.py
│   ├── probes.py
│   └── simulator.py
│
├── submission/
│   ├── main.py
│   ├── predictive_agent.py
│   ├── parametric_agent.py
│   ├── base_controller.py
│   ├── runtime_model.py
│   ├── meta_runtime.py
│   └── learned_model.json
│
├── baselines/v1/
│   ├── main.py
│   ├── counter_agent.py
│   └── champion_agent.py
│
├── scripts/
│   ├── build_submission.py
│   ├── build_meta_artifact.py
│   ├── check_submission.py
│   ├── engine_audit.py
│   ├── replay_cli_plan.py
│   └── tournament.py
│
└── tests/
    ├── test_engine_mirror.py
    ├── test_runtime.py
    └── test_meta.py
```

---

# Kaggle CPU notebook pipeline

The research path is deliberately CPU-friendly:

```text
Accelerator: None

E000 → E001 → E002 → E003 → E004 → E005 → E007 → E006
```

| Stage | Notebook | Purpose | Key outputs |
|---|---|---|---|
| **E000** | `00_episode_index_audit.ipynb` | Discover the official Episodes Index schema | catalog + schema report |
| **E001** | `01_replay_factory.ipynb` | Build the current-engine replay warehouse | turn + daily Parquet |
| **E002** | `02_ladder_forensics.ipynb` | Estimate opponent-adjusted strength and open-loop behavior | Bradley-Terry + entropy reports |
| **E003** | `03_macro_strategy_miner.ipynb` | Discover recurring ladder strategies | archetype profiles + macro library |
| **E004** | `04_predictive_models_cpu.ipynb` | Train future-supply and opponent-belief models | learned model + metrics |
| **E005** | `05_cem_best_response_search.ipynb` | Search a robust policy population | policy zoo + matchup matrix |
| **E007** | `07_meta_equilibrium_and_probes.ipynb` | Solve meta equilibrium, reaction archetypes, probe audit | meta artifact + reaction models |
| **E006** | `06_build_v2_submission.ipynb` | Package the promoted runtime | `submission_v2.tar.gz` |

E006 remains the final build notebook even though E007 was added later.

The final submission archive is flat and contains:

```text
main.py
predictive_agent.py
parametric_agent.py
base_controller.py
runtime_model.py
meta_runtime.py
learned_model.json
```

See `docs/KAGGLE_NOTEBOOK_RUNBOOK.md` for exact notebook inputs and operating instructions.

---

# Local development

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
```

Build and validate the submission:

```bash
python scripts/build_submission.py
python scripts/check_submission.py artifacts/submission_v2.tar.gz
```

Run a both-seat local tournament:

```bash
python scripts/tournament.py \
  --a submission.predictive_agent:agent \
  --b baselines.v1.main:agent \
  -n 16
```

Build a meta artifact from policy-zoo results:

```bash
python scripts/build_meta_artifact.py artifacts/policy_matchups.parquet \
  --policy-params artifacts/policy_params.json \
  --out artifacts/meta_artifact.json
```

---

# Engine contract

**The Kaggle engine is the source of truth.** The repository maintains explicit regression tests for engine details that materially change strategy.

Important tested invariants include:

1. planting day already counts as unwatered;
2. an unwatered new crop becomes a weed that night;
3. animal care + feed banks +1 pending bonus;
4. fertilizer can be sold;
5. occupied animal structures cannot be dug;
6. units may move through locked cells;
7. tile-mutating actions on locked cells fail;
8. shed access is the four center cells;
9. temporary hands disappear every night;
10. farm actions resolve before market orders;
11. shed capacity is finite;
12. final reward is bank cash.

See `docs/ENGINE_CONTRACT.md` and `tests/`.

---

# Promotion protocol

A candidate is promoted only if it passes all relevant gates:

1. engine regression tests;
2. submission packaging/import smoke test;
3. runtime well below the per-turn budget;
4. both-seat held-out tournament improvement;
5. improvement against multiple opponent archetypes;
6. acceptable worst-archetype/CVaR performance;
7. actor-grouped validation for learned components;
8. no material increase in invalid/no-op actions;
9. predictive intervention automatically falls back when confidence is low;
10. active probes remain disabled unless separately proven.

The ladder is a confirmation environment, not our primary optimizer.

---

# Current status

The first deterministic submission entered the ladder at the initial rating of 600. That number is a starting point, not evidence of strength or weakness.

The V2 codebase now contains the infrastructure for:

- replay mining;
- open-loop analysis;
- macro archetypes;
- conditional-reaction archetypes;
- future-supply prediction;
- robust population CEM;
- policy-zoo payoff matrices;
- meta-equilibrium solving;
- confidence-gated live policy selection;
- experimental market-probe analysis;
- deterministic fallback and packaging.

The checked-in `submission/learned_model.json` intentionally contains no promoted learned weights yet. Until E004/E005/E007 generate validated artifacts, the agent remains on its deterministic fallback.

---

# Near-term roadmap

1. Run E000 on the official Episodes Index.
2. Acquire a large recent current-engine replay sample.
3. Measure which top agents are truly open-loop.
4. Build macro and reaction archetypes from strong actors.
5. Train future opponent-supply and archetype models.
6. Expand the executable policy zoo.
7. Run robust CEM across both seats and many seeds.
8. Solve the policy-zoo meta game.
9. Distill the tiny artifact into the runtime selector.
10. Promote one candidate and immediately mine its hosted games.

Longer term, RL remains interesting for value estimation, residual corrections, or offline macro-policy learning, but only after it beats this simpler hierarchy on held-out tournaments.

---

## Reproducibility and safety

- version experiments by engine era;
- never train on stale mechanics without explicit tagging;
- never include private replay fields as runtime features;
- never commit Kaggle credentials;
- never upload the entire repository as the competition artifact;
- keep deterministic fallback operational if learned artifacts are missing or malformed;
- treat community claims as hypotheses until reproduced.

## Disclaimer

This repository is designed to maximize the chance of producing a top Kaggriculture submission through disciplined engineering and empirical iteration. No codebase can honestly guarantee first place against an evolving live population before it has been tested there.
