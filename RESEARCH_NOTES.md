# Research Notes: Episode Mining, Discord Signals, and V2 Design

## Community signals worth taking seriously

### 1. “Treat the simulation like it’s open-loop”
This is the highest-value clue in the Discord transcript, but it is a hypothesis rather than a law. If strong submissions exhibit low action entropy at the same day/hour across different opponents, the search problem collapses from a huge RL problem into a low-dimensional macro program. E002 measures this directly with `open_loop_score = 1 - normalized action entropy`.

Practical consequence: first search farm composition, hiring schedule, land timing, sell reserves, and endgame timing. Only add reactive modeling where replay data shows it pays.

### 2. “Macros = taking actions out of a replay and running them”
Exact action replay is useful as a diagnostic but unsafe as a submission strategy. Weeds, shop draws, market interactions, and small state divergences break exact movement sequences. E003 therefore performs **macro distillation**: infer day-indexed targets from replays, then let a state-aware deterministic controller satisfy those targets.

### 3. CEM may fit this environment better than generic RL
The Discord discussion independently points toward CEM because random variation is limited. That matches the structure of the problem. E005 optimizes a 18-dimensional macro vector rather than 720 low-level actions. The objective is both-seat pairwise win rate against a policy zoo.

### 4. RL scores against the starter bot are not ladder evidence
A reported 100k+ against starter only establishes economic competence. Ladder skill is based on wins/losses against other submissions. Every offline metric in this suite keeps this distinction explicit.

### 5. New submissions receive more games while uncertainty is high
This is strategically useful for experiment scheduling. Do not resubmit byte-identical agents just to create noise, but use meaningful variants when the previous submission has accumulated enough episodes to diagnose it.

## Public notebook roles

The Kaggle web crawler currently exposes the notebook pages/titles but not their cell bodies in this environment, so the suite treats their public purposes as inspiration rather than pretending we reviewed inaccessible implementation details. For a cell-by-cell critique, pull/export the `.ipynb` files and add them to the project.

### `busyaprime/what-actually-wins-on-the-kaggriculture-ladder`
High-value idea: analyze the *ladder population*, not only the game engine. E002 generalizes this into:
- Bradley–Terry opponent-adjusted strength.
- win/loss analysis instead of raw-coin optimization.
- open-loopness by submission.
- phase-specific farm signatures.
- actor-grouped evaluation to reduce repeated-submission leakage.

### `llccqq624/kaggriculture-replay-data-miner`
High-value idea: public replays are the competition’s behavioral dataset. E001 turns this into a reusable data factory with cached raw replays, turn-level Parquet, day-level macro Parquet, outcome labels, and future opponent-sale labels.

The key upgrade is to prioritize recent current-engine episodes and strong/diverse actors, rather than scrape an undifferentiated archive.

### `devraai/episodes-data-analysis-and-linear-regression-mo`
Linear regression is useful as an interpretable diagnostic, but final coins are a poor primary optimization target because:
- the ladder only cares about win/loss/tie;
- shared-market congestion creates nonlinear interaction effects;
- opponent strength confounds raw final score;
- repeated episodes from the same submission create leakage.

E004 therefore uses regularized linear models where they are appropriate (future sell-volume forecasting) and logistic models for win diagnostics, with grouped validation. More complex CPU teachers can later be added and distilled into a tiny runtime model.

## Current-engine boundaries

The research dataset must be tagged by engine era. In particular, the August 7, 2026 town rebalance changed town-center demand and shop unlocking, making pre-rebalance economy trajectories partially stale. The official engine source is always the source of truth.

Hard invariants in the local mirror/tests include:
- planting-day unwatered crop becomes a weed at end of day;
- animal care bonus accumulates +1, not +2;
- fertilizer is sellable;
- occupied animal structures cannot be dug up;
- movement through locked tiles is allowed;
- shed access is the four center-adjacent cells;
- hands disappear at end of day;
- market processing is capped by order slots and uses lockstep per-unit execution.

## V2 hierarchy

### Layer A — Replay Data Factory
Raw episodes -> turn table -> daily macros -> current-engine filter.

### Layer B — Strategy Miner
Cluster trajectories into macro archetypes and estimate day-indexed target schedules.

### Layer C — Opponent Model
At runtime infer a distribution over archetypes from only public state/history.

### Layer D — Future Market Model
Predict opponent sell volume over the next 24 turns. This is the first model promoted because market timing is reversible and lower-risk than farm restructuring.

### Layer E — Best-Response Search
Use CEM over a compact policy vector. Evaluate against a zoo of fixed agents and replay-derived macro archetypes, both seats, many seeds.

### Layer F — Selective Controller
Prediction never replaces mechanical safety. If confidence or expected advantage is low, fall back to the high-floor deterministic policy.

## Promotion criteria

A new component is promoted only if it:
1. passes engine-mechanics regression tests;
2. improves both-seat tournament win rate on held-out seeds;
3. survives at least one actor-grouped replay holdout when learned from data;
4. does not materially increase invalid/no-op action rate;
5. stays comfortably below the 1-second per-turn budget;
6. wins against a **population** rather than only increasing passive-opponent cash.
