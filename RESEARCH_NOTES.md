# Research Notes: Episode Mining, Public Frontier, and V3 Design

## Community signals worth taking seriously

### 1. “Treat the simulation like it’s open-loop”

This remains one of the highest-value clues, but it is now supported by stronger instrumentation than action entropy alone. The public corpus contains prefix stream hashes at turns 24, 100, 200, 400, and 719. These can measure whether a submission emits the same action prefix across different episodes without opening full replay payloads.

Practical consequence: treat open-loopness as a measurable spectrum. Strong agents may use a nearly fixed opening and only become reactive later. Search macro composition, hiring schedule, land timing, sell reserves, and terminal timing first; add reactive logic only where the population evidence shows a payoff.

### 2. “Macros = taking actions out of a replay and running them”

The public frontier confirms that replay/tape-derived action programs can be extremely strong. `Soil Remembers Rain` contains an outcome-blind modal route plus live weed repair and was the strongest robust reference in our controlled finalist panel.

This changes the earlier assumption that exact action replay is inherently too brittle. The correct distinction is:

- blind replay with no repair is fragile;
- a high-quality open-loop route with small state-aware repairs can be frontier-grade.

The V3 design therefore keeps exact/open-loop policies as first-class candidates and measures which reactive repairs actually help.

### 3. CEM still fits the environment, but not before the execution frontier

The earlier plan promoted CEM over a compact macro vector. That remains attractive, but Phase 2/V3 showed that the repository controller was far below the public deterministic/economic frontier. Optimizing a weak execution kernel is the wrong order of operations.

Revised order:

1. match frontier execution and passive economy;
2. build a family-balanced opponent zoo;
3. search macro parameters with robust CEM;
4. add small market/opponent residuals;
5. only then evaluate larger learned controllers.

### 4. RL scores against starter/passive bots are not ladder evidence

A 100k+ passive score establishes economic competence, not ladder skill. The V3 experiments make this concrete: `pure_score3094` produced more passive cash than Soil but had a lower family-balanced robust score.

### 5. New submissions should be information-dense

Do not spray byte-identical or weakly motivated variants into the ladder. The preferred sequence is one offline-selected candidate, then a targeted contrast only after enough hosted episodes exist to diagnose the first submission.

## Public data and executable-agent assets

The project now uses three complementary public substrates:

1. `episodes.csv`, `episode_features.csv`, `teams.csv`, and `daily_stats.csv` for population-level structure.
2. `stream_hashes.csv` for exact/prefix behavioral-family and open-loop analysis.
3. attached public `main.py` / `submission.tar.gz` artifacts for direct controlled tournaments.

The 4.6 GB `replays.parquet` archive is now a microscope, not the census layer. Select strong/distinct actors first, then parse only targeted replays.

## Current-engine boundaries

The research dataset must be tagged by engine era. The August 7, 2026 town rebalance changed town-center demand and shop unlocking, making pre-rebalance economy trajectories partly stale. Official engine source remains the source of truth.

Hard invariants in the local mirror/tests include:

- planting-day unwatered crop becomes a weed at end of day;
- animal care bonus accumulates +1, not +2;
- fertilizer is sellable;
- occupied animal structures cannot be dug up;
- movement through locked tiles is allowed;
- shed access is the four center-adjacent cells;
- hands disappear at end of day;
- market processing is capped by order slots and uses lockstep per-unit execution.

## Phase 2 public frontier findings

A public-agent zoo discovered 42 raw candidates and 38 exact-unique implementations. All 38 executed successfully in the local mirror.

A Swiss stage followed by a both-seat finalist round robin identified the strongest robust public references. The most important finalist result was `Kaggriculture Frontier | The Soil Remembers Rain`, which scored 0.909 in the 44-game finalist round robin.

Phase 2B then confirmed the public economic gap against the current GitHub controller and showed that several large, adaptive public agents share substantial source lineage. In particular, Adaptive Farming and Multi-Route were nearly identical by normalized token similarity, so public submission frequency cannot be treated as independent strategy evidence.

## V3 Frontier Transplant Lab

The V3 lab tested pure public references plus behavior-level transplants:

- pure Soil, Adaptive, 3094, V16, Ranker, Melon, Strict Future, Findings;
- Soil micro/farmer/hands with another policy's market actions;
- reverse micro/market controls;
- day-7/day-11 phase switches with both source policies shadow-called every turn.

The meta was family-normalized so near-clone lineages did not receive duplicate weight.

### V3 held-out result

The promotion gate selected `pure_soil`.

- robust score: 0.6590
- mean family win rate: 0.8056
- worst family: Adaptive/3094 at 0.375
- passive cash: 171,985
- runner-up: `pure_score3094`, robust 0.5806, passive cash 178,791
- invalid games: 0

Soil was 1.000 against Findings, V16/premium, Ranker/Melon, and Strict Future in the held-out family matrix. Broad transplants generally regressed, often because micro and market policies are tightly coupled to the physical/economic state created by their own route.

Full result tables are stored under `experiments/v3_frontier_transplant/` and summarized in `docs/V3_FRONTIER_TRANSPLANT_RESULTS.md`.

## V3.1 hypothesis: surgical market residuals

The next experiment targets Soil's one clear weakness without changing its farmer/hand execution.

`notebooks/14_v3_soil_route_counter_lab.ipynb` searches small public-state market residuals:

- detect prior-turn increases in shared premium-product inventory;
- treat those increases as candidate opponent sell/flood signals;
- defer Soil's already-scheduled premium SELL under a configurable shock/price threshold;
- release deferred quantity at the next safe scheduled sale;
- disable deferral under shed pressure;
- force terminal liquidation;
- test premium SELL slot position.

### Anti-overfit structure

Stage 1 optimizes against Adaptive plus guardrail opponents, while 3094 is withheld. Stage 2 introduces 3094 as a held-out sibling of the target lineage and restores the full family-balanced meta.

Promotion requires all of:

1. Adaptive/3094 held-out win-rate gain >= +0.10 versus pure Soil.
2. Global robust-score delta >= -0.01 versus pure Soil.
3. Passive cash >= 97% of pure Soil.
4. Zero invalid games.

If no residual passes, pure Soil remains the correct next live calibration.

## Revised architecture

### Layer A - Population and executable frontier

Public episode summaries + stream hashes + executable public agents.

### Layer B - Frontier execution kernel

Routing, task order, watering, weed repair, worker utilization, shed trips, and open-loop route integrity.

### Layer C - Macro policy zoo

Distinct economic schedules represented once per strategic family rather than once per public submission.

### Layer D - Robust search

CEM / parameter search against family-balanced opponents, both seats, held-out seeds, with passive-economy floors.

### Layer E - Small adaptive residuals

Market collision avoidance, future supply forecasting, opponent-family confidence, and other reversible decisions. These may alter only a narrow layer unless held-out evidence justifies deeper adaptation.

### Layer F - Learned policies

DQN/RL assets are research-only until their exact state/action contract is recovered and they beat deterministic frontier references in controlled population tests.

## Promotion criteria

A new component is promoted only if it:

1. passes engine-mechanics regression tests;
2. improves or preserves both-seat held-out robustness on new seeds;
3. survives family-normalized opponents rather than a clone-heavy raw population;
4. does not materially increase invalid/no-op action rate;
5. stays comfortably below the 1-second per-turn budget;
6. maintains a frontier-level passive economic floor;
7. improves the targeted family if it is a counter-specific change;
8. is evaluated on win/loss/tie, not cash score alone.
