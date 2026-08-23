# V44 Frontier Margin Engine

V44 is a deliberate break from the recent regime-switching line. It does not try to identify an opponent archetype and then replace the farm policy mid-episode. Instead, it qualifies one current frontier parent and keeps that parent's physical farm choreography intact for the full game.

## Thesis

The strongest evidence in this project says that frontier Kaggriculture policies are often close to open-loop production programs with small repairs. V32's live 2035 result also came from a narrow market-order overlay rather than a wholesale controller rewrite. V44 therefore treats the physical farm as a protected execution kernel and searches only small public-state residuals around the shared market.

## Runtime layers

1. **Current-parent compiler**
   - discovers attached current `Moon Counts Melons` and/or `Soil Remembers Rain` sources;
   - runs a local both-seat qualification against the attached frontier family;
   - selects exactly one physical parent;
   - embeds that parent's `main.py` verbatim inside a single generated runtime file.

2. **Exact slot-fragility ordering**
   - preserves every non-SELL market slot;
   - only permutes already-planned SELL orders among the parent's existing SELL slots;
   - ranks sales by exact revenue lost if shared-market supply reaches the market first;
   - adds recent external inventory pressure and visible opponent harvest supply to the stress scenario.

3. **One-turn demand synchronization (experimental finalist only)**
   - may replace one premium SELL with a same-slot `PASS` for exactly one turn;
   - only activates on a town-consumption tick, under high observed external pressure, with shed and cash safety margins;
   - only defers when the exact projected post-demand revenue gain clears a configured minimum;
   - never activates when the parent has HIRE/BUY_LAND/BUY_ANIMAL orders that may depend on same-turn sale revenue.

4. **Mirror breaker**
   - detects near-mirror farms from public land, hand, herd, crop, and cash state;
   - after a persistence streak, may add only one tiny premium sale (1 or 2 units depending on candidate) when a market slot is free;
   - uses a 24-turn cooldown and a price-ratio floor.

5. **Late protect latch**
   - begins no earlier than step 576;
   - latches only after a sustained estimated economic lead;
   - cancels only capital purchases whose remaining-horizon value is especially weak (late animals, extremely late land, seeds that cannot mature);
   - uses `PASS` in the original slot so surrounding market-slot choreography does not shift.

6. **Step-718 liquidation**
   - if a carrier is already standing on a shed tile and its entire inventory fits, V44 can issue `DROP` on the last actionable turn;
   - the engine applies unit actions before market orders, allowing the same turn to sell the newly dropped goods;
   - V44 then replaces the final market list with up to nine executable product liquidation orders;
   - it never forces a DROP that would overflow the 100-unit shed.

## Causal candidate portfolio

The lab deliberately searches a small interpretable set instead of a combinatorial parameter cloud:

- `V44_COMPILED_CONTROL`: embedded parent, no residual changes;
- `V44_CORE`: fragility ordering + pressure forecast + terminal liquidation;
- `V44_MIRROR`: core + one-unit mirror breaker;
- `V44_LATCH`: core + late protect latch;
- `V44_FULL_SAFE`: core + mirror + latch;
- `V44_FULL_TIMING`: full-safe + strict one-turn demand synchronization;
- `V44_MIRROR_2`: core + two-unit mirror breaker.

Every finalist has a causal interpretation. If a variant wins, the result tells us what kind of intervention earned the gain.

## Promotion protocol

### Stage A: physical-parent qualification

Moon and Soil are evaluated both seats against the attached competitive family on seeds disjoint from the V44 search seeds. The selected parent maximizes a robust score combining mean and worst-family win rate.

### Stage B: residual screen

The direct parent and `V44_COMPILED_CONTROL` are both evaluated. Their cash and score must be exactly identical on paired games. This is the first hard gate: if source embedding changes behavior, V44 aborts.

Residuals then need:

- zero invalid games;
- screen paired-score delta >= -0.01;
- worst-family delta >= -0.08;
- physical-action divergence <= 2%.

Only the best three residuals reach the sealed test.

### Stage C: sealed held-out gate

A V44 candidate is promotable only when all are true:

- zero invalid games;
- paired competitive score delta >= **+0.02** versus compiled parent;
- worst-family paired delta >= **-0.03**;
- passive cash >= **97%** of the compiled parent's passive cash;
- V32 score no worse than compiled parent minus 0.02 when V32 is attached;
- physical-action divergence <= **2%**;
- mean call time < **100 ms**.

If no candidate clears every gate, the run emits `HOLD` and does not create a fake promoted V44 submission.

## Required Kaggle inputs

Attach as notebook inputs:

- this Kaggriculture repository version containing V44;
- current Moon and/or Soil public notebook output/source (both are strongly preferred);
- at least one additional competitive agent for a meaningful family gate, or both Moon + Soil;
- exact V32 runtime archive if available (recommended);
- Adaptive, Ranker, Strict Future, 3094, V16, Weed Slip, and Findings are optional but make the held-out panel much stronger.

The discovery layer accepts either a `submission.tar.gz` or a directory containing `main.py` under input paths matching the known public notebook slugs.

## Outputs

A successful promoted run writes:

- `SUBMIT_V44_FRONTIER_MARGIN.tar.gz` with `main.py` at archive root;
- `CONTROL_CURRENT_FRONTIER.tar.gz`;
- `V44_DECISION.json`;
- `V44_ATTRIBUTION.json`;
- parent, screen, and held-out game tables;
- compiled-parent parity report;
- input manifest with source paths and hashes.

A failed promotion writes `HOLD_V44_DO_NOT_SUBMIT.txt` and the diagnostic tables instead.

## Runtime contract

The final generated submission is a single Python file. It does not depend on sibling imports or outer `__file__` resolution. The embedded parent is executed in a private globals dictionary so the final top-level callable remains V44's `agent`, satisfying Kaggle's last-callable loader behavior.
