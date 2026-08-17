# Kaggriculture: Replay Intelligence + Robust Meta-Agent

> CPU-first research, simulation, opponent-modeling, and submission stack for Kaggle's **Kaggriculture** simulation competition.
>
> Primary objective: maximize **head-to-head ladder win probability**, not merely farm cash against passive bots.

This repository is the canonical research lab for building a high-floor Kaggriculture agent and then upgrading it with public replay intelligence, opponent modeling, future-market prediction, robust policy search, and meta-equilibrium selection.

The core design rule is:

> **Do not ask machine learning to relearn deterministic mechanics.**

Routing, watering, feeding, harvesting, shed handling, labor reset, land purchase order, market-order constraints, and endgame liquidation belong in a deterministic controller. Learning is reserved for the uncertain strategic layer: what the opponent is probably doing, what the shared market is likely to do next, and which precomputed macro strategy has the best chance of winning this matchup.

---

## Competition objective

A game lasts 720 turns. Final bank cash determines the winner. The ladder rating is driven by win / loss / tie outcomes, so the central offline metric is:

```text
pairwise win rate
+ both seats
+ held-out seeds
+ realistic opponent population
```

Mean cash is useful for debugging, but it is not the promotion target.

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

A parallel research branch mines **conditional reactions** around market shocks and evaluates tiny active-market probes, but probes remain disabled unless paired simulator experiments show a robust positive edge.

---

# Why this hierarchy

The public meta contains a strong clue that many competitive agents may be approximately **open-loop at the macro level**. If that is true, the search problem is much smaller than generic end-to-end RL:

```text
not:
720 turns x every low-level action

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

# Current layers

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

If every learned artifact is deleted, the agent still runs a complete deterministic game.

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

`src/kagv2/macros.py`

Clusters recurring farm strategies and distills day-indexed macro schedules.

`src/kagv2/reactions.py`

Clusters **conditional responses** around high-variance events such as:

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

- `cem_optimize`: pure scalar best response for controlled experiments;
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

The policy zoo produces a policy x opponent-archetype payoff matrix. A multiplicative-weights/no-regret solver estimates a rectangular zero-sum equilibrium and reports a duality-gap exploitability diagnostic.

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

> sell premium inventory earlier when the model predicts a near-term opponent supply flood and the current price is still healthy.

This is lower risk than rebuilding the farm based on an uncertain prediction.

## 10. Experimental active market probes

`src/kagv2/probes.py`

The code can detect price bands where opponent next-turn selling changes abruptly, then calculate exact market impact for small candidate sell probes.

Important engine reality:

- any product can be sold;
- only **WHEAT** and **FERTILIZER** are legal `BUY_PRODUCT` items.

Therefore a strategy such as “dump strawberries, then buy them back cheaply” is impossible. The only plausible use of a probe is **information acquisition / threshold testing**.

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

All research notebooks are designed for:

```text
Accelerator: None
```

The intended order is:

```text
E000 -> E001 -> E002 -> E003 -> E004 -> E005 -> E007 -> E006
```

E006 remains the final build notebook even though E007 was added later.

## E000 — Episode Index Audit

**Notebook:** `00_episode_index_audit.ipynb`

**Inputs**
- `kaggle/kaggriculture-episodes-index`
- repository source

**Accelerator:** None  
**Internet:** Off

**Outputs**
- `episode_schema_report.csv`
- `episode_catalog.parquet`

Purpose: discover the official Episodes Index schema rather than guessing column names.

## E001 — Replay Factory

**Inputs**
- E000 catalog
- replay JSON files

**Accelerator:** None  
**Internet:** On only for acquisition, Off for parsing

**Outputs**
- `turns.parquet`
- `daily_macros.parquet`
- replay manifest

Purpose: create one reusable current-engine replay warehouse.

## E002 — Ladder Forensics

**Inputs:** E001 tables  
**Accelerator:** None  
**Internet:** Off

**Outputs**
- `open_loop_report.csv`
- `bt_strength.csv`

Purpose: measure opponent-adjusted strength and test whether strong agents are actually macro-open-loop.

## E003 — Macro Strategy Miner

**Inputs:** E001 + E002  
**Accelerator:** None  
**Internet:** Off

**Outputs**
- `archetype_profiles.parquet`
- `macro_library.json`

Purpose: discover recurring ladder strategies and distill them into robust target schedules.

## E004 — Predictive Models

**Inputs:** replay warehouse + archetypes  
**Accelerator:** None  
**Internet:** Off

**Outputs**
- `learned_model.json`
- model metrics

Purpose: train future-supply and opponent-belief models using actor-grouped validation.

## E005 — Robust Population CEM + Policy Zoo

**Inputs:** repository/controller, recommended E003/E004 artifacts  
**Accelerator:** None  
**Internet:** Off

**Outputs**
- `cem_best.json`
- `policy_params.json`
- `policy_matchups.parquet`

Purpose: search policies against a population, not one static bot.

## E007 — Meta Equilibrium + Conditional Reactions + Probe Audit

**Inputs**
- E001 `turns.parquet`
- E002 `bt_strength.csv`
- E005 `policy_matchups.parquet`
- optional `policy_params.json`

**Accelerator:** None  
**Internet:** Off

**Outputs**
- `reaction_events.parquet`
- `reaction_profiles.parquet`
- `reaction_archetypes.parquet`
- `reaction_model.json`
- `probe_thresholds.json`
- `meta_artifact.json`

Purpose: build the robust policy prior and understand how strong agents react under pressure.

## E006 — Build Submission

**Inputs**
- repository source
- promoted E004 model
- promoted E007 meta artifact

**Accelerator:** None  
**Internet:** Off

**Output**
- `submission_v2.tar.gz`

The final archive is flat and contains:

```text
main.py
predictive_agent.py
parametric_agent.py
base_controller.py
runtime_model.py
meta_runtime.py
learned_model.json
```

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

**The engine source is the source of truth.**

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

The first deterministic submission entered the ladder at the initial rating of 600. That is not itself evidence of strength or weakness.

The V2 codebase now contains the full infrastructure for:

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
