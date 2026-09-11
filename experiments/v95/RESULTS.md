# V95 live-calibrated gate results

Engine: `kagsim 1.32.7`

Live calibration supplied by the user on 2026-09-10:

- `Kaggriculture_V85_SHAPE_CURRENT_HEDGE.tar.gz`: 1782.0 after ~1 day
- `Kaggriculture_V81_1_FARMING_V3_CLOCK_HARDENED_CLOUD_QUALIFIED.tar.gz`: 1580.4 after ~1 day

The workflow recovered the prior V85 workflow artifact and pinned its `main.py` SHA-256 as:

`02d15d4ebb69fb077a131529aab609b2b8bb992cc5582b82fc46fa3d3eb0dcad`

Note: the recovered workflow package was named `V85_SHAPE_TERMINAL`; it is used as the exact archived V85-family calibration control, but this record does not claim byte identity with the separately named live `V85_SHAPE_CURRENT_HEDGE` upload unless that upload is independently fingerprinted.

## Independent holdout field

12 unseen seeds, both seats, seven opponent families, 168 normal games per candidate.

| candidate | BT | mean margin | worst-opponent BT | seat0 / seat1 | errors |
|---|---:|---:|---:|---:|---:|
| smart_t50 | 0.9286 | +18,128 | 0.5000 | 0.9226 / 0.9345 | 0 |
| smart_t52 | 0.9286 | +18,088 | 0.5000 | 0.9226 / 0.9345 | 0 |
| smart_t54 | 0.9286 | +18,065 | 0.5000 | 0.9226 / 0.9345 | 0 |
| smart_t56 | 0.9226 | +18,037 | 0.4583 | 0.9167 / 0.9286 | 0 |
| smart_t58 | 0.9226 | +18,037 | 0.4583 | 0.9167 / 0.9286 | 0 |
| smart_t46 | 0.9167 | +17,936 | 0.4167 | 0.9107 / 0.9226 | 0 |
| smart_t62 | 0.9167 | +17,921 | 0.4167 | 0.9107 / 0.9226 | 0 |
| v85_exact | 0.7143 | +11,470 | 0.0000 | 0.7024 / 0.7262 | 0 |
| sparse_v43_exact | 0.2738 | -3,340 | 0.0000 | 0.2440 / 0.3036 | 0 |

`smart_t54` was 1.000 BT against the exact archived V85-family control, Shape, Adaptive Guard, HarvestForge, Conditional Memory, and the harvested Sparse V43 executable; it tied its own control at 0.500.

The same qualitative result held on the independent discovery field: Smart Lab variants were ~0.92-0.93 BT, V85-family control was 0.7143, and Sparse V43 was 0.3000.

## Late CARROT threshold ablation

Public Smart Lab uses a turn-576 CARROT-price threshold of `$54` to choose between its two legal late continuations.

The promotion script selected `$52`, because it tied `$54` on discovery/holdout BT while slightly improving the ranking objective. The effect is very small:

- discovery vs T54: +4.43 mean paired margin, 2 better / 0 worse margins, no win flips
- holdout vs T54: +23.27 mean paired margin, 10 better / 9 worse margins, 1 rescued non-win and 1 sacrificed win

Therefore `$52` is **not** considered strong enough evidence to replace the public T54 route for the first live calibration submission.

## Clock hardening

Raw Smart Lab failed the synthetic `step=None` clock-fault test. The hardened variants use `day * 24 + hour` when `step` is absent or `None` and had zero runtime errors. The hardening does not change valid-step behavior.

## Recommendation

1. First live probe: `Kaggriculture_V95_2_SMARTLAB_T54_CLOCK_HARDENED.tar.gz`.
2. Keep V85 active as the second live hedge while V95 accumulates rating evidence.
3. Do not submit Sparse V43 from this harvest: it lost every tested game to the archived V85-family control on the holdout field.
4. Do not spend a slot on T52 yet: its advantage over T54 is too small and unstable to justify the confound.
5. Next research layer: a causal three-way oracle at Smart Lab's turn-144 common checkpoint, where the legal seasonal routes reconverge at turn 288. Only learn a router if oracle headroom is materially larger than the existing public rule.
