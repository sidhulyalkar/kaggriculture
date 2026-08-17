# Kaggriculture: Replay Intelligence + Best-Response Agent System

> A CPU-first research and submission stack for Kaggle's **Kaggriculture** simulation competition.
>
> Goal: maximize **head-to-head win probability** on the ladder, not merely farm cash against passive bots.

This repository is the working competition lab for building a high-floor Kaggriculture agent and then upgrading it with public replay intelligence, opponent modeling, future-market prediction, and population-based best-response search.

The central design principle is simple:

**Do not ask machine learning to relearn deterministic mechanics.**

Kaggriculture's farming mechanics, routing constraints, market execution order, crop lifecycles, shed limits, labor reset, and terminal scoring are known. Those belong in an exact deterministic controller. Learning is reserved for the uncertain strategic layer: what opponents are likely to do next, what the shared market will look like, and which macro policy has the best chance of winning the matchup.

---

## Competition objective

A ladder episode runs for 720 turns. The winner is the player with the most bank cash at the end. The public ladder rating is driven by **win / loss / tie**, not by the size of the cash margin.

That distinction shapes the whole project:

- Cash is a useful diagnostic.
- Passive-opponent score is a useful smoke test.
- **Pairwise win rate against a realistic opponent population is the promotion metric.**
- A strategy that scores less cash in isolation can still be better if it is a stronger shared-market best response.

---

## System architecture

```text
                 PUBLIC LEADERBOARD EPISODES
                           │
                           ▼
                 ┌──────────────────┐
                 │ Replay Factory   │
                 │ current era only │
                 └────────┬─────────┘
                          │
             ┌────────────┼──────────────┐
             ▼            ▼              ▼
      Ladder Forensics  Macro Miner   Future Labels
       win / strength   archetypes    opp sells t+24
             │            │              │
             └────────────┼──────────────┘
                          ▼
                 ┌──────────────────┐
                 │ Opponent Belief  │
                 │ archetype probs  │
                 └────────┬─────────┘
                          │
          ┌───────────────┴────────────────┐
          ▼                                ▼
   Future Market Model              Policy Zoo
   expected sell floods     default / counter / shop / etc.
          │                                │
          └──────────────┬─────────────────┘
                         ▼
                 CEM Best Response
                  win probability
                         │
                         ▼
               Selective Macro Planner
               confidence + hysteresis
                         │
                         ▼
                Exact Farm Controller
            routing / water / feed / shed
                         │
                         ▼
                 Kaggle submission
```

### Layer A: Exact execution controller

The controller is responsible for mechanics that must never be guessed:

- routing farmers and temporary hands;
- plant, water, harvest, feed, care, fertilize, pickup/drop/place;
- keeping new plants alive on planting day;
- daily re-hiring of temporary labor;
- seed and animal acquisition timing;
- shed-capacity protection;
- market-order limits;
- land expansion;
- terminal liquidation.

### Layer B: Macro policy

The macro layer chooses targets rather than raw movements:

- hands by phase;
- land unlock timing;
- cow / sheep targets;
- wheat / melon / strawberry allocation;
- specialist crops when shop demand justifies them;
- product-specific sell reserves;
- terminal liquidation start.

This is deliberately low dimensional, making search and A/B attribution much easier than end-to-end RL.

### Layer C: Replay intelligence

Public ladder episodes are transformed into:

- turn-level state/action tables;
- daily macro tables;
- opponent-adjusted strength estimates;
- open-loop / reactive behavior measurements;
- strategy archetypes;
- future opponent sell-volume labels;
- win and value diagnostics.

### Layer D: Selective predictive control

The first learned intervention is intentionally conservative: **sell earlier when a strong predicted opponent dump is likely and the current premium price is still healthy.**

Prediction may accelerate liquidation. It may not violate mechanics or invent unsafe actions. If no trained model is present, the submission falls back to the deterministic policy.

### Layer E: Best-response search

Cross-Entropy Method (CEM) searches a compact policy vector against a policy zoo. The objective is both-seat pairwise win rate with a tiny cash-margin tie-breaker, not passive final score.

---

## Why this approach

Community discussion around the competition contains an important hypothesis: many strong agents behave approximately **open-loop** at the macro level. In other words, the winning search space may be closer to an optimized farming program than a giant reactive RL policy.

This repository does not assume that hypothesis is true. It tests it.

`src/kagv2/ladder.py` measures action-macro entropy for repeated submissions at the same day/hour across different episodes. If high-rated agents have low entropy, macro search gets more emphasis. If strong agents are highly opponent-conditioned, the belief and predictive layers get more emphasis.

The same philosophy applies to RL: it remains an option, but it must beat simpler methods on held-out pairwise tournaments before entering the hot path.

---

## Repository layout

```text
.
├── README.md
├── STATUS.md
├── RESEARCH_NOTES.md
├── pyproject.toml
├── requirements.txt
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
│   └── 06_build_v2_submission.ipynb
│
├── src/kagv2/
│   ├── constants.py
│   ├── schema.py
│   ├── replay.py
│   ├── features.py
│   ├── ladder.py
│   ├── macros.py
│   ├── models.py
│   ├── runtime_features.py
│   ├── cem.py
│   └── simulator.py
│
├── submission/
│   ├── main.py
│   ├── predictive_agent.py
│   ├── parametric_agent.py
│   ├── base_controller.py
│   ├── runtime_model.py
│   └── learned_model.json
│
├── baselines/v1/
│   ├── main.py
│   ├── counter_agent.py
│   └── champion_agent.py
│
├── scripts/
│   ├── build_submission.py
│   ├── check_submission.py
│   ├── engine_audit.py
│   ├── replay_cli_plan.py
│   └── tournament.py
│
└── tests/
    ├── test_engine_mirror.py
    └── test_runtime.py
```

---

## Current status

### V1

The first submitted policy is a deterministic tournament-oriented heuristic with:

- three-quadrant economic plan;
- daily Fibonacci labor;
- cow / sheep fertilizer engine;
- wheat / melon / strawberry portfolio;
- visible-opponent counter-meta switch;
- price-aware selling;
- terminal liquidation.

The first Kaggle submission entered at the ladder's initial rating of **600**. That is not yet evidence of strength or weakness; hosted episodes and rating movement are the evidence we need.

### V2 scaffold

V2 adds:

- replay ingestion;
- ladder forensics;
- macro archetypes;
- future supply forecasting;
- CEM policy search;
- tiny runtime model support;
- confidence-gated predictive selling.

The checked-in `submission/learned_model.json` is intentionally allowed to be empty. Until replay-trained artifacts are promoted, V2 behaves as a safe deterministic fallback.

---

## Local setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
```

Or:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest -q
```

Expected current baseline:

```text
6 passed
```

Build the competition bundle:

```bash
python scripts/build_submission.py
python scripts/check_submission.py artifacts/submission_v2.tar.gz
```

The Kaggle archive must have `main.py` at its root. Do **not** upload this whole repository as the competition submission.

---

# Kaggle CPU notebook pipeline

All research notebooks are designed to run with:

```text
Accelerator: None
```

The notebooks intentionally separate acquisition from modeling so expensive repeated replay parsing is avoided.

## E000 — Episode Index Audit

**Notebook**: `notebooks/00_episode_index_audit.ipynb`

**Kaggle inputs**

1. `kaggle/kaggriculture-episodes-index`
2. this repository or an uploaded copy of the suite

**Accelerator**: None  
**Internet**: Off  
**Expected input files**: CSV / Parquet / JSON files supplied by the Episodes Index dataset. The notebook discovers the schema rather than assuming filenames.

**Outputs**

```text
episode_schema_report.csv
episode_catalog.parquet
```

Purpose: identify episode IDs, submission/team metadata, timestamps, ratings if available, and current-engine filtering fields.

## E001 — Replay Factory

**Notebook**: `notebooks/01_replay_factory.ipynb`

**Kaggle inputs**

1. E000 artifacts
2. replay JSON files, if already downloaded

**Accelerator**: None  
**Internet**: On only if replay acquisition is required; Off otherwise.  
**Key files expected**: episode catalog plus `episode-*-replay.json` files when parsing locally.

**Outputs**

```text
turns.parquet
daily_macros.parquet
replay_manifest.parquet
```

Purpose: create one reusable research warehouse rather than reparsing raw JSON in every experiment.

## E002 — Ladder Forensics

**Notebook**: `notebooks/02_ladder_forensics.ipynb`

**Kaggle inputs**: E001 artifacts  
**Accelerator**: None  
**Internet**: Off

**Outputs**

```text
open_loop_report.csv
bt_strength.csv
ladder_forensics.json
```

Purpose:

- estimate opponent-adjusted strength with Bradley-Terry;
- quantify open-loop behavior;
- compare raw cash with actual win probability;
- identify repeatedly strong submissions worth archetyping.

## E003 — Macro Strategy Miner

**Notebook**: `notebooks/03_macro_strategy_miner.ipynb`

**Kaggle inputs**: E001 + E002 artifacts  
**Accelerator**: None  
**Internet**: Off

**Outputs**

```text
archetype_profiles.parquet
macro_library.json
```

Purpose: cluster strong trajectories by farm composition and timing, then distill robust day-indexed target schedules instead of brittle raw action playback.

## E004 — Predictive Models

**Notebook**: `notebooks/04_predictive_models_cpu.ipynb`

**Kaggle inputs**: E001 + E003 artifacts  
**Accelerator**: None  
**Internet**: Off

**Outputs**

```text
learned_model.json
model_metrics.json
```

Initial targets:

- opponent sell volume over the next 24 turns;
- opponent macro archetype;
- win-probability/value diagnostics.

Only features available to the live agent are eligible for the runtime model.

## E005 — CEM Best-Response Search

**Notebook**: `notebooks/05_cem_best_response_search.ipynb`

**Kaggle inputs**: E003 + E004 artifacts  
**Accelerator**: None  
**Internet**: Off

**Outputs**

```text
cem_best.json
policy_by_archetype.json
```

Purpose: optimize a compact macro policy vector against the policy zoo in both seats across many seeds.

## E006 — Build Submission

**Notebook**: `notebooks/06_build_v2_submission.ipynb`

**Kaggle inputs**: promoted E004/E005 artifacts plus repository source  
**Accelerator**: None  
**Internet**: Off

**Output**

```text
submission_v2.tar.gz
```

Purpose: embed only promoted tiny artifacts into the deterministic controller and verify the archive before submission.

---

## Replay acquisition from the ladder

Kaggle's simulation CLI can list a submission's episodes and download replays. The workflow is:

```bash
kaggle competitions submissions kaggriculture
kaggle competitions episodes <SUBMISSION_ID> -v
kaggle competitions replay <EPISODE_ID> -p ./replays
```

For public-safe top-team scouting, use the leaderboard/team-submission workflow supported by the Kaggle CLI and store only data made public through the competition tooling.

The repository intentionally does not embed scraped private information or credentials.

---

# Engine contract

**The engine source is the source of truth.** Documentation and community explanations are useful, but strategy code is written against tested interpreter behavior.

Important current invariants include:

1. A newly planted crop begins already counting as unwatered. If it is not watered before end-of-day refresh, it becomes a weed that night.
2. Animal care + feed banks **+1** pending care bonus per qualifying day.
3. Fertilizer is sellable by the market engine.
4. `DIG` does not remove an occupied animal structure.
5. Movement onto and through `LOCKED` cells is allowed, while tile-mutating operations on locked cells are not.
6. Shed access is through the four center cells `(4,4)`, `(5,4)`, `(4,5)`, `(5,5)` on the 10×10 board.
7. Temporary farm hands disappear every night and must be rehired.
8. The shed has finite capacity; overflow can destroy value.
9. Farm actions execute before market orders on the same turn.
10. The final reward is bank cash, so terminal liquidation matters.

See `docs/ENGINE_CONTRACT.md` and `tests/`.

---

# Evaluation protocol

A candidate does **not** get promoted because it has a higher passive score.

Promotion gates:

1. All engine regression tests pass.
2. No meaningful increase in invalid/no-op actions.
3. Runtime remains comfortably below the per-turn budget.
4. Both-seat tournament win rate improves on held-out seeds.
5. Improvement survives multiple opponent archetypes, not just one hand-picked bot.
6. Learned components improve actor-grouped replay validation.
7. The component is disabled automatically when confidence/evidence is inadequate.
8. A leaderboard submission is used as confirmation, not as the primary optimizer.

Recommended offline comparison:

```text
candidate vs baseline
candidate vs premium-meta
candidate vs wheat-heavy
candidate vs livestock-heavy
candidate vs shop-adaptive
candidate vs prior champion
```

Always alternate seats.

---

# Why not pure RL yet?

End-to-end RL has a much larger search problem:

- hundreds of low-level movement and farm actions;
- long delayed economic rewards;
- shared-market interaction;
- hidden opponent inventories;
- random weeds and shop draws;
- strict action-time budget.

Meanwhile, deterministic execution already solves much of the mechanical problem exactly.

That does not mean RL has no role. Promising later uses include:

- value estimation;
- residual corrections over macro policies;
- opponent belief updates;
- policy selection;
- offline RL over replay-derived macro actions.

But any learned system must beat the simpler hierarchy on held-out tournaments before promotion.

---

# Experiment philosophy

Treat every ladder submission as an expensive experiment.

Bad experiment:

```text
change routing + crop mix + animal mix + selling + model simultaneously
```

Good experiment:

```text
control       = current champion
variant       = current champion + one strategic intervention
offline A/B   = many seeds, both seats, policy zoo
ladder A/B    = only after offline promotion
```

The five-submission daily allowance is best used for controlled validation and recovery, not blind parameter search.

---

# Near-term research roadmap

### Phase 1 — Build the population dataset

- audit the official Episodes Index;
- download a recent, diverse set of public ladder episodes;
- filter stale engine eras;
- cache turn/day Parquet.

### Phase 2 — Discover what actually wins

- fit opponent-adjusted strength;
- measure open-loopness;
- identify dominant macro schedules;
- quantify labor, land, crop, animal, and liquidation timing.

### Phase 3 — Predict the shared market

- forecast opponent 24-turn supply;
- infer likely unsold inventory from public history where possible;
- deploy only confidence-gated early-selling interventions.

### Phase 4 — Search best responses

- build a realistic policy zoo;
- run CEM over macro parameters;
- learn policy-by-archetype mappings;
- optimize expected ladder win probability.

### Phase 5 — Adaptive V2/V3

- maintain belief over opponent archetypes;
- use hysteresis to prevent policy thrashing;
- select or blend best responses;
- optionally add a small value/residual model.

---

# Reproducibility and safety

- Keep all research artifacts versioned by experiment ID and engine era.
- Do not overwrite a promoted model without saving its metrics.
- Do not use the whole repository as the Kaggle submission artifact.
- Do not place Kaggle API credentials in this repository.
- Treat public leaderboard notebooks/chat claims as hypotheses until reproduced.
- Keep the exact controller operational even when learned artifacts are missing or malformed.

---

## Disclaimer

This repository is designed to maximize the chance of producing a top Kaggriculture submission through disciplined engineering and empirical iteration. No codebase can honestly guarantee first place before it has been evaluated against the evolving live population.

The objective here is to make every iteration measurable, reproducible, and harder to fool ourselves with.
