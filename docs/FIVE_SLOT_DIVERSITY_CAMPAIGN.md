# Five-Slot Diversity Campaign

## Why this campaign exists

V32 remains the strongest live control at 2035.0. The next submission window should not be spent on five correlated tweaks to the same residual idea. Recent live evidence already showed that strong opponent classification is not sufficient if the selected response is weak, and that stacking more adaptive components can reduce robustness.

The goal of this campaign is **information gain**. Each live slot tests a different mechanism while preserving the exact runtime-verified V32 production backbone.

## V33 validation failure

`SUBMIT_V33_WORKGRAPH_EXACT_V32.tar.gz` failed the Kaggle validation episode. The failure was reproduced locally under an exec-style loader: the generated root used `@dataclass` together with postponed annotations. In a loader namespace whose `__name__` is not registered in `sys.modules`, Python's dataclass annotation handling can raise `AttributeError: 'NoneType' object has no attribute '__dict__'` during module execution.

The earlier import-based smoke gate did not reproduce that loader condition. The five probes below therefore:

- use only loader-safe stdlib constructs in the overlay;
- avoid dataclasses and type-resolution dependencies in the Kaggle hot path;
- preserve both `main.py` and the exact `soil_parent/main.py` from the V32 champion archive;
- run an exec-style last-callable gate before and after repacking;
- run full 719-turn local simulator episodes before and after repacking;
- enforce the 10-order market cap.

V33 should be repaired in research, but it should **not** consume one of these five live slots: in exact-V32 local self-play its current WorkGraph gate produced zero interventions, so even a runtime-fixed resubmission would likely add little new ladder information.

## The five probes

### P1 — Demand Pulse Arbitrage

**Modeling idea:** deterministic event-driven arbitrage.

Town shops consume inventory after the market phase every fourth turn. A seller acting one turn later can sometimes monetize the resulting scarcity pulse. P1 watches unlocked shops and, on `step % 4 == 1`, may inject one capped premium sale when:

- the item was consumed by an unlocked shop;
- at least eight units are in our shed;
- V32 did not already schedule that product for sale;
- current price is at least 1.02x base;
- there is a free market slot;
- the game is outside opening and terminal windows.

The injected sale is capped at four units.

This is not opponent classification and not a V32 quantity rewrite. It is a **mechanistic timing residual derived directly from engine event order**.

Small fresh paired local screens were encouraging but noisy. On one 12-game both-seat panel P1 scored 0.75 directly against exact V32, with mean margin +205.9 and 9/12 positive margins. Treat this as a prioritization signal, not proof of leaderboard superiority.

**Recommended live order:** first.

### P2 — Shadow Priority

**Modeling idea:** exact market microstructure / execution-risk optimization.

P2 never changes quantities. When multiple premium sells already exist, it estimates the revenue lost if competing supply reaches the market first, using the exact public price curve. Premium orders are sorted by this delay risk.

This tests whether the binary `Premium-First` insight in V32 can be upgraded to an exact continuous ordering rule.

**Recommended live role:** low-risk mechanism probe.

### P3 — Predatory Margin Denial

**Modeling idea:** adversarial relative-utility optimization.

Most previous agents optimize our absolute cash. Kaggriculture is head-to-head, so the real objective is relative cash. P3 asks a different question:

> Is it worth selling a small amount now because doing so degrades the price of a product for which the opponent has a much larger visible pipeline?

P3 compares our and the opponent's visible premium production/ready yield. If the opponent has materially greater exposure, we have at least four units available, and a capped sale is predicted to create meaningful opponent revenue harm, it fronts at most four units.

This is an explicit **anti-agent**. It is designed to discover whether offensive market manipulation is valuable even when it is not independently optimal for our own inventory timing.

**Recommended live role:** highest-value adversarial probe.

### P4 — Wheat Corner

**Modeling idea:** input-market pressure / resource-denial counterplay.

P4 targets a visibly feed-dependent animal economy. It activates only if:

- the opponent has at least eight animals;
- the opponent has at least four more animals than us;
- at least four opponent animals are currently unfed;
- WHEAT is still at or below 30;
- we have at least 6000 cash and shed headroom;
- the game is in days 10–24.

It then fronts a very small WHEAT purchase, capped at five total units including an existing V32 buy. The economic intent is dual-use: acquire feed optionality for us while moving the shared WHEAT market against a more feed-dependent rival.

This is deliberately narrow because N6 showed that generic feed-first routing can be disastrous. P4 tests a much more adversarial and conditional hypothesis.

**Recommended live role:** specialist counter probe.

### P5 — Temporal Meta Switcher

**Modeling idea:** online opponent change detection plus bounded response selection.

P5 is the direct test of the temporal-opponent thesis. It tracks the difference between our V32 trajectory and the opponent's public trajectory using:

- worker count;
- land expansion;
- COW/SHEEP/GOOSE counts;
- WHEAT/STRAWBERRY/MELON composition;
- visible ready production.

It maintains short and long EWMAs of structural divergence. A persistent increase must survive a three-step confirmation gate before a specialist is activated for a short 12-turn window.

The possible responses are:

- `INPUT`: tiny WHEAT-corner response to a new animal/feed-heavy phase;
- `OUTPUT`: capped predatory premium sale against a newly exposed premium pipeline;
- `SHADOW`: quantity-preserving shadow-priority sequencing for other confirmed structural pivots;
- `BASE`: exact V32.

This is intentionally much smaller than the eventual replay-trained V34 model. Its purpose is to answer one live question cleanly:

> Does within-game strategy-change tracking have value beyond static V32 and static specialists?

**Recommended live role:** fifth, after the static probes establish useful context.

## Recommended submission order

1. `SUBMIT_P1_DEMAND_PULSE_ARBITRAGE.tar.gz`
2. `SUBMIT_P2_SHADOW_PRIORITY.tar.gz`
3. `SUBMIT_P3_PREDATORY_MARGIN_DENIAL.tar.gz`
4. `SUBMIT_P4_WHEAT_CORNER.tar.gz`
5. `SUBMIT_P5_TEMPORAL_META_SWITCHER.tar.gz`

The order is intentional. P1 has the strongest fresh local mechanism signal. P2 establishes a low-risk microstructure reference. P3 and P4 are static anti-agents that give P5 interpretable specialist baselines. P5 then tests whether dynamic selection adds value over those static responses.

## How to interpret the ladder

Do not compare only final displayed ratings. For each probe, inspect episode-level outcomes and ask:

- Did the residual actually activate?
- What opponent family/state caused activation?
- Did it create a V32 loss-to-win flip?
- Did it create a V32 win-to-loss flip?
- Was the effect seat-asymmetric?
- Was improvement caused by our own cash or by suppressing opponent cash?
- Did temporal P5 outperform the specialist it selected?

The most important object after this campaign is a **response payoff table conditioned on opponent state**, not a leaderboard ranking of five opaque agents.

## Next modeling frontier

If the anti-agents activate usefully, the next full system should become a constrained partially observable stochastic game controller:

1. replay-trained temporal opponent belief;
2. change-point posterior rather than a static archetype label;
3. a policy zoo containing independently validated specialists;
4. paired counterfactual response values with explicit loss-to-win and win-to-loss heads;
5. conservative hysteresis and immediate fallback to exact V32 under uncertainty;
6. PSRO/fictitious-play training against a population of adaptive opponents;
7. a relative-margin objective that values both our cash generation and opponent economic denial.

That would turn V32 from a fixed champion script into the robust default policy inside a genuine adaptive game-theoretic agent.