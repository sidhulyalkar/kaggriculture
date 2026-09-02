# V35 Live Probes and V36 Market MPC Strategy

## Why change direction now

V32 Premium-First is already a strong robust anchor. V33 showed that identifying an Adaptive/3094-like opponent is not enough: the classifier was excellent while the switched counter-policy was substantially worse. The next experiments therefore keep Soil/V32 mechanics and search for small, general market edges.

The live ladder should be used as an information source, not a hyperparameter optimizer. Each V35 candidate represents a distinct structural hypothesis.

## V35 live probe pack

Run `scripts/v35_live_probe_pack.py` with the runtime-verified V32 notebook output attached. It emits three independently runtime-verified tarballs.

### V35A — Shadow Priority

**Hypothesis:** when multiple premium products are already scheduled for sale, the most price-sensitive order should receive the earliest market slot.

The policy computes exact revenue under the current public market curve and compares it with the revenue after a small competing-supply stress. It sorts existing premium sales by the revenue that would be lost if another seller reached the market first.

No sale quantity, crop choice, animal choice, route, hire, land purchase, or terminal rule is changed.

**Leaderboard role:** safest first probe. A meaningful improvement would validate market-slot microstructure as a real competitive edge beyond the binary Premium-First ordering discovered in V32.

### V35B — Slot Race

**Hypothesis:** the same execution edge applies to all products, and SELL orders should generally monetize inventory before purchases/hiring consume an earlier slot.

All already-planned SELL orders are sorted by exact delay risk and moved ahead of non-sale market orders. Quantities are unchanged.

This is more aggressive than V35A because order sequencing can alter whether a later purchase is affordable at the moment it executes.

**Leaderboard role:** mechanism probe. Compare with V35A to learn whether the edge is premium-specific or general market sequencing.

### V35C — Front-Run Light

**Hypothesis:** V33's failed response to external supply pressure had the sign wrong. When market inventory jumps but the premium price is still healthy, a small sale should happen *before* the remaining supply wave arrives.

The policy starts with V35A and may inject at most one small premium SELL when all of the following hold:

- midgame, not the opening or terminal window;
- no sale of that product is already planned;
- at least eight units are in the shed;
- net external inventory pressure is at least 12 units after subtracting our previous requested sale;
- current price is at least 80% of base;
- there is an unused market-order slot.

The injected order is capped at eight units and approximately 25% of current shed inventory.

**Leaderboard role:** high-information directional test. It should be evaluated only after V35A/B establish the sequencing baseline.

## Recommended live submission order

1. `SUBMIT_V35A_SHADOW_PRIORITY.tar.gz`
2. `SUBMIT_V35B_SLOT_RACE.tar.gz`
3. `SUBMIT_V35C_FRONT_RUN_LIGHT.tar.gz`

Do not resubmit V33: its final artifact selected the V32 anchor after the counter-policy failed the robustness gate, so it contains no new strategic information relative to V32.

Do not promote a V35 candidate from its first displayed rating. Let it accumulate enough episodes to reduce rating uncertainty and inspect the actual opponent/replay mix. The primary evidence is win/loss behavior against similarly rated opponents, not cash margin.

## V36 — Shadow-Price Market MPC

V35 tests whether market timing matters. If it does, the next full strategy should stop treating selling as a static threshold problem and instead solve a small receding-horizon liquidation problem every turn.

### Core idea

For each product, estimate the value of selling one unit now versus holding it for the next 24 turns.

At turn `t`, construct several plausible future market-inventory paths using:

1. current public market inventory and exact price curve;
2. recent inventory flow after removing our own sales;
3. unlocked town shops and their deterministic demand cadence;
4. opponent visible crops/animals and their likely harvest windows;
5. our own visible production and private shed inventory;
6. remaining shed capacity and terminal horizon.

For each product and candidate sale quantity, calculate expected liquidation revenue under the scenarios.

Conceptually:

`shadow_value(product) = E[value of holding 1 unit for 24 turns]`

Sell now when:

`current marginal sale revenue > shadow_value + risk_buffer`

and hold when expected future scarcity is worth more than current execution.

### Why this is different from V33

V33 first classified an opponent and then switched to a largely different policy. A classification error or an imperfect best response therefore changed many decisions at once.

V36 keeps the robust Soil route permanently and changes only a continuously valued economic residual. An uncertain forecast causes a small timing adjustment, not a wholesale strategy switch.

### Scenario model

Use three cheap trajectories rather than a heavyweight learned model:

- **scarcity scenario:** external supply dries up and town demand dominates;
- **neutral scenario:** recent flow mean-reverts;
- **crowded scenario:** opponent/public production adds a supply pulse.

Weight scenarios from visible opponent farm composition and recent market flow. Recompute every turn. The horizon can be only 24–48 turns, so exhaustive product-level quantity evaluation is tiny.

### Risk objective

Do not maximize expected cash alone. Optimize approximately:

`0.60 * expected revenue + 0.25 * lower-tail revenue + 0.15 * terminal/shed safety`

The controller should become more risk-seeking when inventory is low and more liquidation-biased as shed or terminal pressure rises.

### Public-data learning loop

Use current top-episode/replay data to estimate only quantities the runtime cannot observe directly:

- distribution of harvest-to-sale delay by visible farm composition;
- supply-pulse size after crop/animal maturity;
- product-specific sell propensity by price ratio;
- opponent inventory-flow archetypes.

Do not behavior-clone entire public strategies. Use public traces to calibrate scenario priors, then let exact engine economics choose actions.

## Promotion path

V36 should be promoted only if it beats V32 in paired held-out simulation and does not create a new family weakness. Recommended gates:

- robust paired win delta >= +0.02;
- Adaptive/3094 delta >= +0.05;
- worst-family delta >= -0.02;
- lower-tail/CVaR improvement non-negative;
- passive/self-play economy >= 99% of V32;
- zero invalid games;
- official loader + full environment runtime gate passes on the exact final archive.

The strategic thesis is simple: **keep the best public route, but make inventory a financial asset with an explicit shadow price instead of a pile of crops waiting for a threshold.**
