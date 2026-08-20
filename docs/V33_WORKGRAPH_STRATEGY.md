# V33 WorkGraph: Counterfactual Capital Twin

## Thesis

V32 remains the live control. Recent experiments established two facts that should shape the next design:

1. hard games are often recognizable from public state;
2. recognizing danger does not mean we know the correct broad counter-policy.

V33 therefore changes the unit of adaptation. Instead of asking *which strategy should replace V32?*, it asks:

> What is this exact V32 action worth in the state we are actually in?

The first action family is HIRE because temporary hands disappear at the end of the day while their price follows a steep Fibonacci curve. A $1 hand and a $233 hand are not economically equivalent simply because both help reach the same fixed daily target.

V33 treats the marginal hand as a short-dated option on the visible work queue.

## Public-frontier lesson incorporated without copying its policy

A current public competitor report provides an important independent clue. `Seyamalam/Kaggriculture` V21 showed that an unconditional late policy change was harmful, while a **one-time public-bank lead latch** could safely disable a risky late residual in already-buffered wins. Their report used a different backbone and a different market intervention.

V33 does not copy that market logic. It adopts the more general experimental lesson:

> late-game risk mode should be latched once from an online-safe public signal, not recomputed every turn and not applied globally.

Reference: `Seyamalam/Kaggriculture/reports/v21-capital-latch.md`.

## Architecture

```text
                         observation
                              |
                              v
                       V32-style backbone
                              |
                 +------------+-------------+
                 |                          |
                 v                          v
           all non-HIRE actions       proposed HIREs
                 |                          |
                 |                          v
                 |                   WorkGraph twin
                 |                          |
                 |                robust marginal value
                 |                          |
                 +-------------+------------+
                               |
                       tiny residual gate
                               |
                  +------------+-------------+
                  |                          |
             preserve V32             suppress HIRE
                                           only
```

At step 577 a second signal becomes available:

```text
public bank lead read once
          |
          +-- lead < $6,500 --> BASE forever
          |
          +-- lead >= $6,500 -> DEFEND forever
```

The mode is latched. An opponent cannot create turn-level oscillation by briefly changing the scoreboard after the checkpoint.

## What V33 leaves untouched

V33 deliberately does **not** change:

- crop targets;
- animal targets;
- premium-first sell logic;
- wheat/feed purchase volume;
- land timing;
- animal purchases;
- seed volume;
- farmer movement;
- hand routing;
- watering/feeding/harvest priorities;
- terminal liquidation.

This is not another full policy switch. It is a capital-allocation residual around one exact V32 decision family.

## WorkGraph state

The runtime model converts the visible farm into economically weighted service demand.

Critical/high-value work includes:

- planting-day watering;
- already-dry crops;
- animal feeding;
- ripe crop and animal harvests.

Lower-weight work includes:

- care;
- fertilizer collection;
- weeds;
- bounded construction/planting demand on empty tiles.

The model also estimates predictable within-day arrivals from productive crop and animal count.

The resulting structural state is:

```text
backlog
weighted economic consequence
critical-service demand
existing labor capacity
marginal hand capacity
hours before temporary labor expires
```

## Ephemeral labor option model

Each proposed hand is valued under three execution scenarios:

1. pessimistic routing/service efficiency;
2. neutral efficiency;
3. optimistic efficiency.

For each scenario:

```text
residual_queue = max(0, backlog - existing_capacity)

useful_tasks
    = min(residual_queue, marginal_hand_capacity)

scenario_value
    = useful_tasks * economic_value_per_task
```

V33 deliberately weights the lower tail:

```text
expected_value
    = 0.25 * pessimistic
    + 0.50 * neutral
    + 0.25 * optimistic

robust_value
    = 0.55 * expected_value
    + 0.45 * worst_scenario_value
```

The relevant object is not raw value but:

```text
robust_roi = robust_value / next_fibonacci_hire_cost
```

## Capital optionality

Saved cash persists. A hand does not.

Around the two V32 expansion cliffs the model therefore charges temporary labor an additional opportunity-cost penalty. This does not create or advance a land purchase. It simply makes an expiring hand prove that it deserves capital that may shortly fund a persistent productive asset.

## Intervention firewall

The initial implementation was intentionally tightened after reviewing the full live evidence. V33 is now much more conservative than a generic `robust_roi < 1` rule.

### Midgame

Only days 11-18 are eligible.

At most **one** HIRE can be suppressed per day, and only if all conditions hold:

- the next hire costs at least `$233`;
- robust ROI is below `0.60`;
- current cash is below `$3,500` or the third quadrant is not yet unlocked;
- there is no critical feed/water service gap.

So the midgame model cannot quietly rewrite V32 into an 11-hand strategy.

### Late DEFEND mode

At the first observation at or after step `577`, V33 reads public bank values once.

If own bank exceeds opponent bank by at least `$6,500`, DEFEND is latched for the remainder of the episode.

Only days 24-27 are eligible. At most two expensive hires may be suppressed per day, and only if:

- hire cost is at least `$144`;
- robust ROI is below `0.90`;
- critical work is already covered.

If the lead is smaller, the mode latches BASE and the entire late-game policy stays V32.

There is intentionally no CHASE mode in V33. We do not yet have causal evidence for a safe aggressive late residual.

## Why this is different from N3 / N5 / N6 / N7

Those experiments mostly asked questions such as:

```text
Is this a hard opponent?
Is V32 likely to lose?
Will supply arrive soon?
```

Those predictions can be excellent while the resulting action still has negative value.

V33 instead asks:

```text
If V32 wants to buy this exact marginal hand,
what work can that hand plausibly complete before expiry,
what is that work worth,
and what persistent capital are we giving up?
```

Risk diagnosis is context. Action value is the gate.

## Why HIRE is the right first target

Wave 18B found that only `52 / 600` single-decision branches were positive and none of the tested branches flipped a loss to a win in that small sample. However, some HIRE and strawberry-seed branches changed final margin by several thousand dollars, occasionally above `$10k`.

The unconditional mean was negative, so the lesson was never "stop hiring." The lesson was:

> the marginal value of an expensive hire is strongly state dependent.

WorkGraph is a structural attempt to model that state dependence before we have enough independent counterfactual seeds for a reliable learned regret model.

## Runtime artifact

Build with:

```bash
python scripts/build_v33_workgraph_submission.py
```

The builder emits:

```text
artifacts/SUBMIT_V33_WORKGRAPH.py
artifacts/SUBMIT_V33_WORKGRAPH.tar.gz
artifacts/SUBMIT_V33_WORKGRAPH.manifest.json
```

It then checks the exact Kaggle runtime contract:

1. compose one standalone source file;
2. forbid `__file__` in final source;
3. reproduce compile/exec loading;
4. confirm `agent` is the last callable;
5. execute a synthetic observation;
6. package exactly one root `main.py`;
7. re-extract the exact archive;
8. run the loader gate again;
9. record source and archive SHA-256 hashes.

## Required offline evaluation

V33 should be evaluated against exact V32 with the same seed and both seats.

Primary outcome diagnostics:

- paired win delta;
- V32 win -> V33 loss flips;
- V32 loss -> V33 win flips;
- paired final-cash delta;
- worst opponent-family delta.

Mechanism diagnostics:

- number of V32 HIRE proposals;
- V33 suppressions;
- hire cost suppressed;
- day/hour of activation;
- WorkGraph backlog and robust ROI;
- critical-service exceptions;
- capital-latch mode and checkpoint lead;
- next-day cash difference;
- downstream land/animal/seed timing;
- preventable weeds or animal feed failures.

The most important statistic is **realized policy value conditional on activation**.

## Promotion gate

V33 does not replace V32 because the model is clever. It replaces V32 only if the induced policy wins more games.

Recommended gate:

```text
paired win delta vs V32             >= +0.015
hard-regime win delta               >= +0.03
safe-regime win delta               >= -0.005
worst-family delta                  >= -0.01
Q10 paired margin delta             >= 0
win -> loss flips                   <= loss -> win flips / 3
preventable weed/escape regression  = 0
invalid games                       = 0
V32 parity when gate inactive       = 100%
```

Thresholds must be frozen before an independent confirmation seed set.

## Next evolution if V33 works

Do not immediately create a giant planner.

Use the same pattern on exactly one additional decision family:

```text
V32 proposes action
       |
       v
state-specific structural/counterfactual valuation
       |
       v
change only when the lower-tail advantage clears a strict hurdle
```

The next likely candidates are strawberry seed volume or land timing. Once the Wave 20 counterfactual factory contains enough independent seeds, replace the hand-designed WorkGraph value with a calibrated distributional regret model while preserving the same firewall.

That is the path from a strong fixed tape toward a safe model-predictive agent: **earn the right to change one action at a time.**
