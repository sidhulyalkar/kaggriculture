# V34 Market Timing Lab

V34 tests small market-timing overlays on top of the runtime-verified V32 Premium-First anchor. It does **not** replace V32's farm controller, movement, maintenance, crop targets, or animal targets.

The purpose is to answer one narrow question at a time: can changing *when and how much* premium inventory is sold improve paired match outcomes without damaging the robust anchor?

## Experimental arms

- `anchor`: exact V32 behavior through the wrapper. This is the paired control.
- `elastic_drip`: limits a premium sale using the exact public market price curve so the order does not self-induce a large marginal-price collapse.
- `front_run8` / `front_run15`: detects positive external market inventory pressure after subtracting our previous sale and accelerates premium liquidation while price is still acceptable. This intentionally tests the opposite direction from the failed V33 shock-deferral idea.
- `scarcity8`: detects net market drainage and sells into already-elevated premium prices.
- `dual8` / `dual12`: combines crowd front-running and scarcity harvesting.
- `terminal_vwap`: starts progressively unwinding inventory before the final hard-liquidation window.
- `hybrid12`: combines exact impact control, both regime signals, and progressive terminal liquidation.

## Why the signal is called external pressure

Consecutive public market inventory observations contain opponent sales, town consumption, and our own prior sales. V34 subtracts our requested prior premium sale, but it cannot perfectly separate opponent activity from town demand. The signal is therefore treated as **net external pressure**, not as a claim that a specific opponent sold a specific number of units.

## Kaggle inputs

The lab expects:

1. A V32 artifact containing `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`, `NEXT_SUBMIT_v32.tar.gz`, or another V32 `main.py`. You can pass the exact path with `--anchor` if auto-discovery is ambiguous.
2. The same public-agent inputs used by `scripts/soil_route_counter_lab.py`, ideally including Soil, Adaptive, 3094, and V16 Premium Market Lead.
3. The current repository source. If the simulator is not present in the working checkout or Kaggle inputs, the script falls back to cloning the repository and therefore requires Internet access.

CPU is sufficient. The experiment is simulator-bound and does not need a GPU.

## Run

```bash
python scripts/v34_market_timing_lab.py \
  --input-root /kaggle/input \
  --work /kaggle/working/v34_market_timing \
  --workers 4
```

To pin the control artifact explicitly:

```bash
python scripts/v34_market_timing_lab.py \
  --anchor /kaggle/input/<dataset>/SUBMIT_V32_RUNTIME_VERIFIED.tar.gz
```

## Tournament design

Stage 1 screens all arms against the available hard set, preferring Adaptive, 3094, Soil, and V16. Every matchup is evaluated with paired seeds and both seats.

Only the top three non-anchor arms advance. Stage 2 evaluates those finalists plus the anchor against every discovered public-agent family using fresh held-out seeds.

The promotion gate is intentionally asymmetric because V32 is already the champion:

- robust paired score delta `>= +0.015`
- adaptive-lineage paired delta `>= +0.040`
- worst opponent paired delta `>= -0.030`
- zero invalid games

If no arm clears all gates, V32 remains selected.

## Outputs

The work directory contains:

- `screen_games.csv`
- `screen_summary.csv`
- `heldout_games.csv`
- `heldout_summary.csv`
- `decision.json`
- generated candidate directories used by the local simulator

`decision.json` always sets `submission_ready` to `false`. A winning research arm must be compiled into a single-file runtime and pass `docs/KAGGLE_RUNTIME_SUBMISSION_CONTRACT.md` before upload.

## Interpretation

The most informative result is not necessarily a promotion. For example:

- `elastic_drip` positive while front-running is neutral means self-price-impact is the likely lever.
- front-running positive after V33 deferral was negative would establish the *direction* of response to supply shocks.
- scarcity harvesting positive only against some families suggests the signal belongs in a behavioral router rather than the universal policy.
- terminal VWAP positive broadly suggests the anchor's endgame inventory schedule, not opponent adaptation, is the next optimization frontier.

This structure is designed to turn each CPU run into a causal policy lesson instead of another opaque strategy-zoo score.
