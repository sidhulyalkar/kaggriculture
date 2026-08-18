# V3.1 Soil Route Counter Lab

## Motivation

V3 selected pure Soil. Its held-out family matrix was:

- Adaptive/3094: 0.375
- Findings: 1.000
- Premium/V16: 1.000
- Ranker/Melon: 1.000
- Strict Future: 1.000
- Soil/self family: 0.458

Broad micro/market and phase transplants regressed badly. V3.1 therefore preserves Soil's exact farmer/hands route and tests only a surgical market residual.

## Hypothesis

A prior-turn increase in shared premium-product inventory is evidence consistent with opponent selling. If Soil is scheduled to sell that same premium product immediately afterward, delaying the sale can sometimes avoid shared-market collision pressure.

The residual may:

- inspect only public market inventory/prices and the player's own shed;
- defer an already-scheduled premium `SELL`;
- merge deferred quantity into the next scheduled sell for that product;
- disable deferral when shed pressure is high;
- force terminal liquidation;
- optionally move premium sells toward the front/back of the 10-slot market queue.

It never changes Soil's farmer or hand actions.

## Search space

- inventory shock thresholds: 8, 15, 25, 40;
- premium set: strawberry/melon/milk/wool;
- hard-premium set: melon/milk/wool;
- price guards: 55%, 65%, 75% of base price;
- combined shock + price guards;
- guard start day: 6, 10, 15, 20;
- premium sell slot: keep/front/back.

## Anti-overfit split

Stage 1 searches against Adaptive plus guardrail opponents. 3094 is intentionally withheld.

Stage 2 introduces 3094 as an unseen sibling of the same lineage and evaluates the complete family-balanced meta on new seeds.

## Promotion gate

Promote only if all conditions hold:

- Adaptive/3094 held-out win-rate gain >= +0.10 versus pure Soil;
- global robust-score delta >= -0.01 versus pure Soil;
- passive cash >= 97% of Soil;
- zero invalid games.

If no residual passes, pure Soil remains the selected next submission.

## Run

Use `notebooks/14_v3_soil_route_counter_lab.ipynb` with CPU/no accelerator and Internet ON.

Expected artifact:

`/kaggle/working/v31_soil_counter/NEXT_SUBMIT_v31.tar.gz`
