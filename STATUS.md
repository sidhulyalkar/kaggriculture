# Project Status

Last updated: 2026-08-17

## Live ladder

- V1 submission: accepted and initialized at rating 600.
- Interpretation: 600 is the ladder starting point, not yet a performance verdict.
- Next evidence needed: hosted episode replays, opponent identities/ratings where public, final bank cash, and rating movement.

## Current champion code

- `baselines/v1/`: first submitted deterministic TournamentMind family.
- `submission/`: V2 runtime with deterministic fallback, future-supply forecasting, archetype posterior, and a confidence-gated robust meta-policy selector.

## V2.3 research stack now implemented

- `src/kagv2/equilibrium.py`: rectangular zero-sum meta solver + robust population mix.
- `src/kagv2/reactions.py`: strength-weighted conditional-reaction mining around market shocks.
- `src/kagv2/probes.py`: experimental threshold/market-probe analysis with explicit promotion gate.
- `src/kagv2/cem.py`: pure best-response CEM plus robust population CEM using expectation + worst-case + CVaR.
- `submission/meta_runtime.py`: tiny pure-stdlib hot-path selector; no live CEM.
- `submission/runtime_model.py`: soft archetype posterior, not only hard nearest-cluster classification.
- `notebooks/05_cem_best_response_search.ipynb`: exports `policy_matchups.parquet` and `policy_params.json`.
- `notebooks/07_meta_equilibrium_and_probes.ipynb`: builds reaction archetypes, probe-threshold diagnostics, and `meta_artifact.json`.
- `notebooks/06_build_v2_submission.ipynb`: embeds promoted meta artifacts and packages `meta_runtime.py`.

## Local / CI quality gates

- Existing engine mirror and runtime smoke tests retained.
- New tests cover equilibrium convergence, robust mixture validity, meta-selector hysteresis, and probe price-path semantics.
- GitHub Actions CI is enabled on every push and currently passing for the code-bearing V2 meta changes.
- Submission builder compiles all runtime Python and packages a flat `submission_v2.tar.gz` with `main.py` at root.

## Research queue

1. Run E000 on the official Kaggriculture Episodes Index.
2. Build a recent current-engine replay warehouse.
3. Quantify open-loopness of strong public submissions.
4. Mine macro archetypes **and conditional reaction archetypes**.
5. Train 24-turn opponent sell-volume + archetype-posterior models.
6. Run robust population CEM against a replay-derived policy zoo.
7. Solve the policy-zoo meta game and embed the robust mixture.
8. Evaluate market probes offline; keep them disabled unless paired tournaments show a positive lower confidence bound.
9. Promote only components that improve held-out pairwise win rate and worst-archetype performance.

## Promotion rule

The next ladder submission should be made only after it either fixes a concrete hosted failure or beats the current champion in a controlled offline tournament. Pure mean-score gains are insufficient; the candidate must also survive both seats, multiple archetypes, engine-regression tests, runtime checks, and a robustness gate.
