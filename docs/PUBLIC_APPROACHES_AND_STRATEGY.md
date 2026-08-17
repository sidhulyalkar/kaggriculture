# Public Approach Landscape and Development Strategy

Updated: 2026-08-17

This note separates **publicly observable approaches** from claims that still need reproduction. Kaggle notebook pages are sometimes JS-rendered and do not expose cell source to external crawlers, so a notebook title or community comment is treated as a hypothesis unless the implementation/artifact is available locally.

## Public approach families

### 1. Fixed rule / heuristic agents

Typical shape:

- deterministic routing and farming priorities;
- hand-authored crop / animal targets;
- fixed expansion days;
- threshold-based selling;
- minimal opponent modeling.

Strengths: very high reliability, tiny runtime, easy debugging, easy submission packaging. Weaknesses: manual tuning and predictable shared-market behavior.

**Use in our system:** keep as the exact execution layer and as the baseline/champion lineage. Do not discard it.

### 2. Open-loop macro programs / replay macros

Community discussion strongly suggests that several high-performing agents behave approximately open-loop at the macro level. A replay macro is effectively a scheduled action/program learned or copied from successful trajectories.

Strengths: collapses the search space dramatically; often surprisingly strong in long deterministic games. Weaknesses: exact action playback is brittle to weeds, shops, state divergence, and shared-market changes.

**Use in our system:** mine day-indexed macro targets, not raw action playback. Let the deterministic controller repair state deviations.

### 3. Replay mining / ladder analytics

Public notebooks and datasets mine episode outcomes, actions, daily farm statistics, and ratings. This is currently the highest-leverage public infrastructure because it exposes what the *actual ladder population* is doing.

Strengths: real opponent distribution, real outcomes, strategy discovery, meta tracking. Weaknesses: selection bias, engine-era contamination, duplicated/copied policies, rating confounding.

**Use in our system:** make replay/population data the research substrate. Correct for engine era, opponent strength, repeated submissions, and policy clones.

### 4. Linear regression / score prediction

Public analysis includes linear models over episode features and outcomes.

Strengths: fast, interpretable, useful for finding coarse economic associations. Weaknesses: raw bank score is not the ladder objective; shared-market interactions are nonlinear; opponent strength and seat create confounding; correlation does not identify an action policy.

**Use in our system:** diagnostic/surrogate only. Prefer pairwise win models and actor-grouped validation.

### 5. Evolution / neuroevolution

Community reports describe evolutionary approaches plateauing well below the strongest ladder ratings when applied too directly to the large action space.

Strengths: derivative-free and easy to parallelize. Weaknesses: raw turn-level search is enormous and sample-hungry.

**Use in our system:** evolve/CEM a compact macro parameterization, never the full 720-turn primitive-action policy.

### 6. Cross-Entropy Method (CEM) macro search

Community discussion explicitly identifies CEM as promising because the environment has limited stochasticity and strong open-loop structure.

Strengths: stable, CPU-friendly, easy to optimize against a policy zoo, excellent fit for 15–30 macro variables. Weaknesses: a pure best response can overfit a stale meta.

**Use in our system:** primary near-term optimizer, with robust expectation + worst-case/CVaR objective and a meta-equilibrium mixture.

### 7. Reinforcement learning

Community reports are mixed: RL has a higher theoretical ceiling but is currently difficult, slow, and sensitive. Similar Kaggle simulation competitions have eventually seen learned policies overtake rules, so it should not be dismissed.

Strengths: can learn nonlinear long-horizon state-dependent policies. Weaknesses: huge action space, delayed reward, shared market, hidden inventory, mechanical invalid-action risk, expensive training.

**Use in our system:** later and hierarchically. Train value/residual/policy-selection models over macro decisions before attempting end-to-end primitive-action RL.

### 8. Behavior cloning / sequence models

Replay datasets make BC / temporal sequence modeling possible.

Strengths: directly distills strong public behavior and can initialize RL. Weaknesses: copies crowded strategies, compounds action errors, and cannot outperform demonstrations by imitation alone.

**Use in our system:** learn opponent models, macro schedules, and priors. If used for control, clone macro decisions and distill into a compact runtime model.

### 9. Adaptive market / opponent-conditioned agents

Community participants are actively exploring market-conditioned actions and long-term planning.

Strengths: directly exploits the two-player shared economy, which fixed scripts largely ignore. Weaknesses: requires forecasting hidden opponent inventory and avoiding overreaction to noisy market signals.

**Use in our system:** this is the main differentiator layered on top of a robust macro policy. First targets: opponent archetype, 24-turn sell volume, crash probability, and liquidation timing.

### 10. Faster simulator implementations

A public community notebook advertises a C++ environment implementation for faster strategy testing.

Strengths: simulation throughput can multiply search quality by orders of magnitude. Weaknesses: a fast wrong simulator is worse than a slow correct one.

**Use in our system:** build or adopt a fast backend only after parity tests against the official Python engine. Then use it for large CEM/policy-zoo searches.

---

# The public dataset opportunity

The currently attached community `Kaggriculture Episodes` dataset exposes a particularly useful bundle:

- `episodes.csv`
- `episode_features.csv`
- `daily_stats.csv`
- `replays.parquet`
- `teams.csv`
- `stream_hashes.csv`
- supporting extraction/repack scripts

This changes the optimal data pipeline. We should **not** download and reparse hundreds of replays by default if the packed corpus is already mounted.

The official `Kaggriculture Episodes Index` should instead be used for freshness/current-engine reconciliation and as an acquisition fallback.

## Particularly valuable fields/artifacts

### `episodes.csv`
Likely episode-level matchup data: submission/team IDs, bank outcomes, ratings, timestamps. Use it to build pairwise win labels and rating-adjusted strength.

### `episode_features.csv`
Use for rapid feature/outcome forensics and surrogate models. Do not assume its feature definitions are suitable for online control until inspected.

### `daily_stats.csv`
Potentially the most useful table for macro strategy mining because it removes primitive movement noise while preserving day-by-day farm evolution.

### `replays.parquet`
Use full replays selectively for action timing, market reactions, hidden-state target construction, and exact forensic reconstruction.

### `stream_hashes.csv`
Potentially extremely valuable for **policy clone detection**. If it hashes action streams/submissions, it lets us prevent one copied public strategy from dominating the empirical meta simply because many teams resubmitted it.

---

# Most advantageous development path

## Stage A — Build a clone-adjusted current-meta warehouse

1. Discover Kaggle inputs recursively, never by a hard-coded mount path.
2. Load the packed public corpus directly.
3. Reconcile episodes with the official Episodes Index.
4. Filter or tag engine eras.
5. Build one row per matchup and one row per submission/policy identity.
6. Use stream hashes / trajectory signatures to merge identical or near-identical strategies.
7. Weight the meta by unique policy families as well as raw episode frequency.

This is a large improvement over naïvely treating every episode as an independent strategy sample.

## Stage B — Measure whether the ladder is actually open-loop

For the same submission across multiple episodes, quantify:

- day-indexed farm composition variance;
- land purchase timing variance;
- labor schedule variance;
- market action variance conditional on price;
- action-stream similarity;
- reaction to opponent/market shocks.

If top policies are low-variance, emphasize macro CEM. If top policies react strongly, emphasize opponent-conditioned policy selection.

## Stage C — Mine the strategy manifold

Cluster **submission-level profiles**, not episode-level trajectories. Useful macro dimensions include:

- hand schedule by phase;
- land unlock days;
- crop allocation by phase;
- cow/sheep/goose counts;
- fertilizer usage;
- late crop rotation;
- inventory/sell thresholds;
- terminal liquidation timing.

Representative policies from each cluster become the policy zoo.

## Stage D — Search robust macro policies

Run CEM/evolution only over compact macro variables. Evaluate both seats against the replay-derived zoo.

Optimize a robust objective such as:

`0.50 * mean_win_value + 0.30 * worst_archetype_value + 0.20 * lower_tail_CVaR`

Then build the empirical policy-vs-archetype payoff matrix and solve for a mixed/meta-equilibrium prior.

## Stage E — Add prediction only where it can create edge

Train small CPU models for:

- opponent archetype from early visible state;
- opponent premium-product sell volume in the next 24 turns;
- probability of a market crash before our next harvest;
- likely expansion/labor regime;
- optional hidden inventory estimates using replay-private labels offline.

Keep mechanics deterministic. Learned components choose macro policy or accelerate a sale; they never directly issue fragile movement/water/feed commands.

## Stage F — Build a surrogate-assisted optimizer

Once exact simulation becomes the bottleneck, train a policy-matchup surrogate from simulation results. Use it to reject poor CEM candidates cheaply, then exact-simulate only the top candidates. This is a higher-value use of supervised ML than raw final-score regression.

## Stage G — Introduce RL as a residual, not as the whole farmer

Promising later forms:

- daily macro-action offline RL;
- value model over macro choices;
- residual correction to the deterministic macro planner;
- policy selector over the zoo;
- BC initialization followed by self-play.

Only move to primitive-action RL if it clearly beats the hierarchical system in held-out policy-zoo tournaments.

---

# Highest-priority competitive ideas

1. **Clone-adjusted meta estimation** using stream hashes.
2. **Current-engine filtering** so stale strategies do not poison the search.
3. **Submission-level open-loop measurement** rather than episode-level action entropy alone.
4. **Robust CEM against real replay-derived archetypes.**
5. **Fast exact simulator** after parity certification.
6. **Opponent supply forecasting** for premium-product pre-selling.
7. **Confidence-gated policy selection** with hysteresis.
8. **Meta-equilibrium regularization** so today's counter is not tomorrow's glass cannon.
9. **Targeted full-replay forensics** only for surprising/high-value episodes.
10. **Controlled ladder variants** to isolate macro search, market prediction, and meta selection.

The central competitive thesis is therefore:

> **Do not imitate the public meta blindly. Reconstruct it, deduplicate it, model it, then search robust counters to its strategy distribution.**
