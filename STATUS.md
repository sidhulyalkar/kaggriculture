# Project Status

Last updated: 2026-08-17

## Live ladder

- V1 submission: accepted and initialized at rating 600.
- Interpretation: 600 is the ladder starting point, not yet a performance verdict.
- Next live calibration candidate: the V3-selected Soil reference, unless V3.1 finds a held-out Adaptive-lineage counter that passes its robustness gate.
- Hosted evidence should be interpreted by win/loss/tie and opponent strength, not cash margin alone.

## Current frontier evidence

Phase 2A built an executable public-agent league from 38 exact-unique public submissions. A both-seat finalist round robin identified `Kaggriculture Frontier | The Soil Remembers Rain` as the strongest robust public reference in that panel.

Phase 2B then evaluated the frontier against the current GitHub simulator/controller and found a large deterministic/economic gap. The public frontier commonly produced roughly 145k-180k passive cash while the then-current repository agent was around the 80k range.

The V3 Frontier Transplant Lab tested pure references, micro/market transplants, and day-7/day-11 phase transplants under a family-balanced held-out meta.

### V3 held-out decision

- Selected: `pure_soil`
- Evaluated repo commit: `df23881cda684df7b8f078cb454d2253eda7202b`
- Robust score: `0.6590`
- Mean family win rate: `0.8056`
- Worst family: Adaptive/3094 lineage at `0.375`
- Passive cash: `171985`
- Invalid games: `0`
- Runner-up: `pure_score3094`, robust score `0.5806`, passive cash `178791`

Soil was 1.000 against Findings, V16/premium, Ranker/Melon, and Strict Future in the held-out family matrix. Its clear weakness was the Adaptive/3094 lineage. Broad transplants did not clear the promotion gate and several damaged robustness badly.

Results are checked into:

- `docs/V3_FRONTIER_TRANSPLANT_RESULTS.md`
- `experiments/v3_frontier_transplant/NEXT_SUBMIT_manifest.json`
- `experiments/v3_frontier_transplant/v3_heldout_scores.csv`
- `experiments/v3_frontier_transplant/v3_family_matrix.csv`

## V3.1 active experiment

`notebooks/14_v3_soil_route_counter_lab.ipynb` and `scripts/soil_route_counter_lab.py` implement a surgical counter search.

The experiment preserves Soil's exact farmer/hand route and tests only small market residuals:

- prior-turn premium market inventory shock detection;
- safe sell deferral;
- product price guards;
- premium sell slot ordering;
- shed-pressure and terminal-liquidation safety.

Anti-overfit split:

- Stage 1 searches against Adaptive and guardrail opponents.
- 3094 is withheld until Stage 2.
- Stage 2 restores the full family-balanced meta and uses new seeds.

Promotion requires:

1. Adaptive/3094 held-out win-rate gain of at least `+0.10` versus Soil.
2. Overall robust-score delta no worse than `-0.01` versus Soil.
3. Passive cash at least 97% of Soil.
4. Zero invalid games.

If no residual passes, pure Soil remains the correct next live submission.

## Current repository architecture

- `baselines/v1/`: first submitted deterministic TournamentMind family.
- `submission/`: V2 runtime with deterministic fallback, future-supply forecasting, archetype posterior, and confidence-gated meta selection.
- `src/kagv2/equilibrium.py`: rectangular zero-sum meta solver + robust population mix.
- `src/kagv2/reactions.py`: strength-weighted conditional-reaction mining around market shocks.
- `src/kagv2/probes.py`: experimental threshold/market-probe analysis.
- `src/kagv2/cem.py`: pure best-response CEM plus robust population CEM.
- `scripts/soil_route_counter_lab.py`: current V3.1 frontier refinement search.

## Revised research queue

1. Run V3.1 Soil Route Counter Lab.
2. Submit only the automatically selected `NEXT_SUBMIT_v31.tar.gz`.
3. If V3.1 falls back to Soil, use Soil as the live frontier calibration and mine its hosted failures.
4. Quantify stream-hash open-loopness of current strong public submissions.
5. Decode/characterize the Soil route and identify minimal state-aware repairs rather than broad policy splices.
6. Build a family-normalized policy zoo so near-clone public lineages do not receive duplicate meta weight.
7. After the deterministic frontier is matched, resume robust CEM over macro parameters and small adaptive market/opponent residuals.
8. Keep DQN/RL assets research-only until their state/action contract and frontier performance are verified.

## Promotion rule

A new ladder submission is promoted only after controlled held-out evidence. Mean passive cash alone is insufficient. The candidate must survive both seats, new seeds, family-balanced opponents, runtime checks, invalid-action checks, and an explicit robustness gate. Targeted counter variants must additionally demonstrate improvement on the target family without materially regressing the frontier anchor.
