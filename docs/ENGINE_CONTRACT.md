# Engine Contract

The Kaggle `kaggle_environments/envs/kaggriculture/kaggriculture.py` interpreter is the source of truth.

## Current invariants encoded by the project

### Crops
- Planting initializes `consecutive_unwatered = 1`.
- A newly planted crop that is not watered before the first end-of-day refresh becomes a weed.
- Strawberry production is finite rather than indefinite.
- Non-ongoing crops are not harvested merely because `yield_units > 0`; the controller protects their useful growth window.

### Animals
- An unfed animal can escape after consecutive missed feeding days.
- Care + feed adds +1 pending care bonus per qualifying day.
- Occupied coops/pastures cannot be cleared with `DIG`.
- Fertilizer production is treated as a first-class economic output.

### Movement and shed
- Units may move onto and through `LOCKED` tiles.
- Tile-mutating operations on locked tiles no-op.
- Shed access is the four center cells on the default board.
- Hands disappear at end of day.
- End-of-day carried inventory drops into the shed subject to capacity; overflow can be lost.

### Market
- Farm/unit actions process before market orders each turn.
- Market order slots are capped per turn.
- Buy/sell processing is per-unit and shared between players.
- Fertilizer is a sellable product in the engine.
- Shared inventory means a strategy's value depends on the opponent's production and sell timing.

### Terminal scoring
- Final reward is bank cash.
- Unsold inventory is not terminal wealth.
- Terminal liquidation is therefore a required policy phase.

## Regression policy

If Kaggle updates the engine:
1. pin the new engine commit/version;
2. diff interpreter behavior;
3. add or update regression tests;
4. tag replay data by engine era;
5. rerun offline baselines before trusting old learned artifacts.
