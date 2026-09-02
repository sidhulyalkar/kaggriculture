# V33 WorkGraph: Counterfactual Capital Twin

## Decision

V32 remains the live champion. V33 is a research candidate that wraps the **exact runtime-verified V32 artifact** and is allowed to change only one action family: a small number of expensive `HIRE` orders.

The production builder will refuse to create a submission if the supplied V32 archive does not match the champion SHA-256:

`ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`

This is deliberate. A V33 experiment built on a merely similar controller is not evidence about improving V32.

## Why rethink the architecture

Recent experiments produced a consistent pattern:

- difficult V32 regimes are predictable from public state;
- opponent sale behavior is often predictable;
- broad policy switches and forecast-triggered market actions have not converted that prediction quality into better gameplay;
- Wave 18B found rare, very large single-decision regret around `HIRE` and strawberry-seed decisions, but unconditional intervention was harmful.

So V33 changes the unit of adaptation.

Instead of asking:

```text
Which strategy should replace V32?
```

it asks:

```text
V32 proposed this exact action.
What is the state-dependent marginal value of that action?
```

## Black-box champion architecture

```text
observation
    |
    v
EXACT V32 artifact
    |
    v
complete V32 action dictionary
    |
    +-------------------------------+
    |                               |
non-HIRE actions                proposed HIREs
immutable                          |
                                  v
                           WorkGraph twin
                                  |
                         marginal labor value
                                  |
                     +------------+------------+
                     |                         |
                  uncertain                certified
                     |                         |
                     v                         v
                 keep V32              remove HIRE only
```

The final Kaggle file embeds exact V32 source in an isolated namespace and then calls it first on every turn. V33 deep-copies the result and only filters eligible `HIRE` orders.

Therefore, when the gate is inactive:

> **V33 is exact black-box action parity with V32.**

V33 does not need to know or reimplement V32's crop plan, route, market model, or internal state.

## WorkGraph world model

Temporary hands disappear at the end of the day while hire cost rises on a Fibonacci curve. The value of another hand depends on the work it can actually complete before expiry.

WorkGraph converts visible farm state into an economically weighted service queue.

High-value or critical work includes:

- planting-day watering;
- already-dry crops;
- animal feeding;
- ripe crop and animal harvests.

Lower-weight work includes:

- care;
- fertilizer collection;
- weeds;
- bounded constructive demand from available land.

It also estimates a bounded amount of predictable work arriving later in the same day from productive crop and animal counts.

The structural state is:

```text
backlog
weighted economic consequence
critical-service demand
existing labor capacity
marginal hand capacity
hours until labor expires
```

## Distributional value instead of a point estimate

The marginal hand is evaluated under three execution scenarios:

```text
pessimistic
neutral
optimistic
```

For each scenario:

```text
residual_queue = max(0, backlog - existing_capacity)
useful_tasks = min(residual_queue, marginal_hand_capacity)
scenario_value = useful_tasks * economic_value_per_task
```

The decision uses a lower-tail-biased value:

```text
expected_value
  = 0.25 * pessimistic
  + 0.50 * neutral
  + 0.25 * optimistic

robust_value
  = 0.55 * expected_value
  + 0.45 * worst_scenario_value

robust_roi = robust_value / next_fibonacci_hire_cost
```

This is intentionally closer to a tiny model-predictive controller than a classifier.

## Capital optionality

A hand expires. Cash survives.

V33 therefore prices the opportunity cost of consuming liquid capital around expansion cliffs and when reserves are thin. It does **not** move land purchases or invent new purchases. It only raises the hurdle an expiring hand must clear.

## Intervention firewall

### Midgame

Only days `11-18` are eligible.

At most **one** hire may be removed per day, and only when:

- the counterfactual next hire costs at least `$233`;
- `robust_roi < 0.60`;
- cash is below `$3,500` or the third quadrant is not unlocked;
- critical feed/water work is already covered.

### Late DEFEND latch

At the first observation at or after step `577`, V33 reads the public bank difference exactly once.

```text
own lead < $6,500  -> BASE forever
own lead >= $6,500 -> DEFEND forever
```

The latch is never recomputed, preventing turn-level policy churn or easy opponent steering.

In DEFEND, only days `24-27` are eligible. At most two hires may be removed per day, and only when:

- hire cost is at least `$144`;
- `robust_roi < 0.90`;
- critical work is covered.

There is deliberately no CHASE mode. We do not yet have causal evidence for a safe aggressive residual when behind.

## Public-frontier lesson

A public competitor's V20/V21 research provides a useful independent design clue: an unconditional late change hurt strong-opponent cases, while a one-time online-safe capital latch made the late residual selective. Their backbone and intervention are different from ours; V33 adopts only the general experimental principle of a latched late risk gate.

Reference: `Seyamalam/Kaggriculture/reports/v20-late-abstain-screen.md` and `reports/v21-capital-latch.md`.

## Production build

The exact champion archive is intentionally required:

```bash
python scripts/build_v33_workgraph_submission.py \
  --v32-tar /path/to/SUBMIT_V32_RUNTIME_VERIFIED.tar.gz
```

Outputs:

```text
artifacts/SUBMIT_V33_WORKGRAPH_EXACT_V32.py
artifacts/SUBMIT_V33_WORKGRAPH_EXACT_V32.tar.gz
artifacts/SUBMIT_V33_WORKGRAPH_EXACT_V32.manifest.json
```

The builder:

1. verifies the exact V32 tar SHA-256;
2. extracts its single root `main.py`;
3. independently validates the V32 last-callable contract;
4. compresses and embeds those exact champion bytes into the V33 single-file runtime;
5. isolates V32 globals from V33 globals;
6. verifies no `__file__` dependency in the final source;
7. checks that final `agent` is the last callable;
8. performs a synthetic runtime call;
9. creates a deterministic one-file tar archive;
10. extracts and validates the exact final archive again;
11. records base/source/archive hashes in the manifest.

CI uses an explicit `--dev-base-source` mode only to exercise packaging mechanics. Its manifest is marked `base_verified_champion=false` and is **not submission-ready**.

## Direct exact-control screen

Once the exact V32 tar is present:

```bash
python scripts/evaluate_v33_workgraph.py \
  --v32-tar /path/to/SUBMIT_V32_RUNTIME_VERIFIED.tar.gz \
  --seeds 64
```

This loads V32 into independent namespaces for the control and the V33-wrapped copy, runs both seats on each seed, and records:

- direct V33 score versus V32;
- cash margin;
- intervention frequency;
- value conditional on intervention;
- late latch mode and checkpoint lead.

This direct screen is necessary but not sufficient. Any survivor must still run against the fixed hard/safe/seat-asymmetry suites and the broad opponent zoo.

## Promotion contract

The key question is not whether WorkGraph is elegant. It is whether the **induced policy** improves match outcomes.

Recommended promotion gates:

```text
paired win delta vs V32             >= +0.015
hard-regime win delta               >= +0.03
safe-regime win delta               >= -0.005
worst-family delta                  >= -0.01
Q10 paired margin delta             >= 0
win -> loss flips                   <= loss -> win flips / 3
preventable weed/escape regression  = 0
invalid games                       = 0
inactive-gate action parity         = 100%
```

Thresholds must be frozen before independent confirmation.

## What V33 is trying to discover

V33 is not meant to be the final planner. It is a test of a new development philosophy:

> **Treat the champion as an invariant. Price one proposed action at a time, and earn the right to change it.**

If this works, the same black-box residual architecture can next evaluate strawberry seed volume or land timing. Once the counterfactual dataset has enough independent seeds, the hand-built structural value can be replaced by a calibrated distributional regret model without changing the safety firewall.
