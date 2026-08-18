# V3 Frontier Transplant Lab Results

Source: uploaded Kaggle output bundle from 2026-08-17.

## Decision

The promotion gate selected **`pure_soil`**.

- Repository commit evaluated: `df23881cda684df7b8f078cb454d2253eda7202b`
- Robust score: **0.6590**
- Mean family win rate: **0.8056**
- Worst family win rate: **0.3750**
- Lower-40% CVaR: **0.6111**
- Mean margin: **+3,109.4**
- Passive cash: **$171,985**
- Invalid games: **0**
- Runner-up: **`pure_score3094`**

No transplant cleared the configured `+0.03` held-out robust-score improvement gate while retaining at least 90% of Soil passive cash.

## Held-out ranking

| Candidate | Robust | Mean family | Worst family | Mean margin | Passive cash | Delta vs Soil |
|---|---:|---:|---:|---:|---:|---:|
| `pure_soil` | 0.6590 | 0.8056 | 0.3750 | +3,109 | $171,985 | +0.0000 |
| `pure_score3094` | 0.5806 | 0.6944 | 0.4167 | +3,832 | $178,791 | -0.0785 |
| `pure_adaptive` | 0.5127 | 0.5660 | 0.4167 | +2,927 | $175,361 | -0.1464 |
| `v16_micro__soil_market` | 0.4965 | 0.7083 | 0.0833 | +1,404 | $171,985 | -0.1625 |
| `phase_soil_to_v16_d11` | 0.4313 | 0.6528 | 0.0000 | +2,041 | $172,781 | -0.2278 |
| `soil_micro__melon_market` | 0.4285 | 0.6528 | 0.0000 | +1,343 | $172,604 | -0.2306 |
| `soil_micro__ranker_market` | 0.3944 | 0.6111 | 0.0000 | +915 | $172,604 | -0.2646 |

## Soil family matrix

- `adaptive_lineage`: win rate **0.375**, mean margin **-4,949** over 24 games.
- `findings`: win rate **1.000**, mean margin **+4,494** over 12 games.
- `premium`: win rate **1.000**, mean margin **+3,917** over 12 games.
- `rank_melon`: win rate **1.000**, mean margin **+4,360** over 24 games.
- `soil`: win rate **0.458**, mean margin **-103** over 12 games.
- `strict_future`: win rate **1.000**, mean margin **+17,744** over 12 games.

## Interpretation

The experiment rejects the broad-transplant hypothesis in its current form.

`pure_score3094` produced about 4% more passive cash than Soil, but its robust score was lower by roughly 0.0785. `pure_adaptive` also had a slightly higher passive economy but a substantially lower robust score. Full market/micro and day-11 phase transplants were weaker still.

The important structure is concentrated: Soil was perfect against Findings, V16/premium, Ranker/Melon, and Strict Future in this held-out panel, while its clear weakness was the Adaptive/3094 lineage. Therefore the next experiment should **preserve Soil's exact farmer/hand execution route** and search only small market-side residuals aimed at the Adaptive lineage.

## V3.1 research direction

`V3.1 Soil Route Counter Lab` tests:
- prior-turn premium-market inventory shock detection;
- safe deferral of scheduled premium sells;
- price guards;
- premium sell slot position;
- terminal and shed-pressure safety.

Anti-overfit design:
- Stage 1 uses Adaptive as the target lineage member.
- 3094 is withheld until Stage 2.
- Stage 2 restores the complete family-balanced opponent meta.

Promotion requires:
- Adaptive/3094 held-out win-rate gain >= +0.10;
- overall robust-score delta >= -0.01 versus Soil;
- passive cash >= 97% of Soil;
- zero invalid games.

If nothing passes, pure Soil remains the correct next submission.
