# Next Ladder Submissions

The next leaderboard wave should answer **which layer actually adds value** rather than uploading several entangled V2 variants.

All five archives are built by `scripts/build_experiment_submissions.py`. They use identical Python runtime code. Only `runtime_flags` inside `learned_model.json` change.

## Panel

| Variant | Meta selection | Predictive selling | Fixed robust policy | Question |
|---|---:|---:|---:|---|
| `S0_control` | off | off | no | Fresh deterministic control / matchmaking variance |
| `S1_robust_fixed` | off | off | yes | Did offline CEM/macroeconomic search improve the base farm? |
| `S2_market_only` | off | on | no | Does future opponent-supply forecasting improve sell timing? |
| `S3_meta_only` | on | off | no | Does opponent belief + policy selection improve matchups? |
| `S4_full` | on | on | no | Do market prediction and meta selection interact constructively? |

## Recommended use of a five-submission day

The existing V1 remains a historical control, so the default experiment day is:

1. submit `S1_robust_fixed`;
2. submit `S2_market_only`;
3. submit `S3_meta_only`;
4. submit `S4_full`;
5. keep one slot reserved.

Use `S0_control` only when a fresh same-day control is more valuable than the reserve, for example when the ladder population appears to have shifted materially.

## Interpretation

The four main variants form a useful attribution ladder:

- If S1 wins and S2/S3 do not, the edge is mostly better open-loop macro economics.
- If S2 wins, market forecasting is independently valuable.
- If S3 wins, opponent-conditioned policy selection is independently valuable.
- If S4 beats both S2 and S3, the two learned components have positive interaction.
- If S4 loses to both, the interaction is harmful or the confidence gates are too permissive.
- If all variants move together, leaderboard matchmaking noise is dominating and more episodes/replays are required before changing code.

## Evidence to record

For each submission record:
- submission ID and artifact SHA-256;
- current rating and number of rated episodes;
- opponents and their public strength where exposed;
- seat;
- final bank cash and margin;
- inferred opponent archetype;
- selected macro policy by day;
- whether predictive selling fired, product, quantity, and price;
- shed overflow / weeds / escaped animals / terminal unsold inventory;
- runtime or invalid-action errors.

Do not promote based on one or two games. The first purpose of hosted episodes is to identify execution failures and calibrate the local simulator against the live engine. The second purpose is to estimate component-level win-rate effects against the actual ladder population.

## Promotion order

A component becomes part of the next champion only if:
1. the corresponding controlled variant survives local both-seat policy-zoo evaluation;
2. hosted replays show the component behaving as intended;
3. it improves results across more than one opponent archetype;
4. it introduces no mechanical/runtime regression;
5. the observed effect survives enough episodes to be distinguishable from ladder noise.
