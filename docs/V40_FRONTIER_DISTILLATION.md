# V40 Frontier Distillation / Fertilizer Flywheel

## Why V40 is a new branch of the research tree

V32 is still the strongest proven live submission in this repository, but the recent residual campaign did not create a new ceiling. N3, N5, N6, N7, P4, and P5 all preserve most of V32 and attempt to add context, prediction, or narrow market interventions. The repeated result is that adaptive intelligence does not compensate for a weaker economic backbone.

V40 therefore changes the backbone.

It starts from the public MIT-licensed `lonespear/kaggriculture` `main_v20.py` controller at commit `774b26093ccf4246525517d48420349b841b6e50`. That line is structurally different from V32: it recomputes farm tasks each turn, uses standing-on-work dispatch plus global assignment, aggressively manages shed logistics, and derives its production economy from town demand rather than replaying a mostly fixed route.

This is not copied blindly. The public parent is a new experimental control. V40 tests whether we can add a mechanism that the source repository itself identified but had not resolved: cheap market fertilizer may be able to unlock a higher strawberry/labor/land frontier.

## Core hypothesis: the fertilizer flywheel

The source line documents a frontier gap in which stronger farms used much more fertilizer and supported larger productive acreage. Fertilizer is unusual because it can become extremely cheap when supply is abundant while a correctly applied unit can create a much more valuable incremental strawberry unit.

V40 treats fertilizer as a capital allocation decision with a shadow-value gate rather than a fixed purchase rule.

A fertilizer purchase is permitted only when all of these are true:

- day 8 through 23;
- enough strawberries already exist to use the input;
- several current strawberry tiles are outside the active fertilizer window;
- fertilizer is cheap relative to current strawberry value;
- shed occupancy leaves substantial headroom;
- current fertilizer stock is below a small target;
- cash remains above a feed-aware reserve after the purchase;
- there is an unused market-order slot.

The purchase is deliberately capped. V40 is testing whether a missing input channel increases realized productivity, not trying to reproduce a 600-unit public purchase pattern in one leap.

## Re-open ceilings after the mechanism changes

A major lesson in the public frontier research is that a ceiling measured under one implementation can disappear after an efficiency improvement. V40 therefore re-tests scale only after the fertilizer channel exists.

The candidate family is:

| Candidate | Strawberries | Hands | Quadrants | Other change |
| --- | ---: | ---: | ---: | --- |
| `V40_FERT_FLYWHEEL` | 24 | 11 | 2 | fertilizer + market risk ordering |
| `V40_FERT_SCALE28` | 28 | 12 | 2 | moderate scale |
| `V40_FERT_SCALE32` | 32 | 12 | 3 | larger productive footprint |
| `V40_FERT_SCALE36` | 36 | 13 | 3 | aggressive scale stress |
| `V40_FERT_MILK_HEDGE` | 30 | 12 | 3 | 7 cows / 7 sheep + milk-crash execution priority |
| `V40_MARKET_ONLY` | 24 | 11 | 2 | attribution control, no fertilizer buying |

The point of the larger arms is not that 32 or 36 strawberries are assumed to be better. They are tests of whether the new productivity channel changes the location of the economic frontier.

## Market layer

The V40 overlay does not rewrite total existing sale quantities. It only permutes the slots occupied by existing SELL orders using a supply-exposure risk score based on visible rival crops/animals and the current product price.

A separate milk-crash arm moves an already-planned MILK sell ahead of other sells when combined cow exposure is very high and milk is no longer trading strongly. This is intentionally a sequencing change, not a new speculative sale.

## Why this is safer than the failed V33 artifact

V33 exposed a loader failure caused by postponed annotations plus `dataclass` execution inside Kaggle's last-callable loader namespace. V40's generated hot-path overlay contains no dataclasses, no file access, and no dynamic imports.

Before packaging, the builder runs:

1. source compilation;
2. normal import/callable discovery;
3. a bare `exec` loader simulation that reproduces the V33 failure shape;
4. paired both-seat tournament screens;
5. held-out tournament confirmation;
6. the official `get_last_callable` loader;
7. a complete Kaggriculture self-play runtime;
8. tar repacking;
9. the exec and official runtime gates again on the exact repacked archive.

## Promotion logic

The frontier parent and exact V32 are both controls.

A novel child is promoted only if it has zero invalid games, is non-negative against the frontier parent in held-out paired score, does not create a large new worst-family regression, and maintains at least a 0.50 direct score against exact V32 on the same held-out panel.

A near-neutral child may be emitted as `LIVE_PROBE` when it is within 0.015 paired score of the frontier parent, has no severe family regression, and clears the V32 direct floor. This is a deliberately weaker standard for one informative ladder experiment, not champion promotion.

If no child clears either gate, the builder writes `decision: HOLD` and does not create a submission tar. This is intentional. A daily submission slot is more valuable than an offline regression.

## Kaggle run card

Use the companion notebook `notebooks/40_v40_frontier_distillation_cpu.ipynb`.

Settings:

- Accelerator: None / CPU
- Internet: ON
- Save Version -> Save & Run All

Required input:

- exact `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`

Strongly recommended public-agent outputs/datasets:

- `kaggriculture-frontier-the-soil-remembers-rain`
- `adaptive-farming-strategy-for-kaggriculture`
- `kaggriculture-rank-your-agent`
- `3094-score-kaggriculture`
- `v16-rc5-high-score-8c-4s-premium-market-lead`
- `kaggriculture-frontier-the-moon-counts-melons`
- the current public WEED-slip/frontier notebook output when available

Primary output when a candidate survives:

`/kaggle/working/v40_frontier_distillation/SUBMIT_V40_FRONTIER_DISTILLED.tar.gz`

Always inspect:

- `V40_DECISION.json`
- `V40_FINAL_TABLE.csv`
- `heldout_vs_v32.csv`
- `heldout_vs_parent.csv`

## Interpretation

A positive V40 result would mean the next generation should continue on the closed-loop economic/worker frontier and use opponent models only as scenario weights. A failure would still be informative: it would reject the simplest fertilizer-supply explanation for the public efficiency gap and point the next wave toward logistics and assignment efficiency rather than another V32 residual.
