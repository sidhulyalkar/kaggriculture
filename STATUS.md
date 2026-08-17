# Project Status

Last updated: 2026-08-16

## Live ladder

- V1 submission: accepted and initialized at rating 600.
- Interpretation: 600 is the ladder starting point, not yet a performance verdict.
- Next evidence needed: hosted episode replays, opponent identities/ratings where public, final bank cash, and rating movement.

## Current champion code

- `baselines/v1/`: first submitted deterministic TournamentMind family.
- `submission/`: V2 scaffold with deterministic fallback and optional predictive runtime model.

## Local quality gates

- Unit/regression suite: 6 tests passing.
- Submission package builder: implemented.
- Exact-engine invariant coverage: planting-day water, +1 animal care bonus, occupied DIG, locked movement, runtime feature construction.

## Research queue

1. Run E000 on the official Kaggriculture Episodes Index.
2. Build a recent current-engine replay warehouse.
3. Quantify open-loopness of strong public submissions.
4. Mine macro archetypes.
5. Train 24-turn opponent sell-volume model.
6. Run CEM against replay-derived policy zoo.
7. Promote only components that improve held-out pairwise win rate.

## Promotion rule

The next ladder submission should be made only after it either fixes a concrete hosted failure or beats the current champion in a controlled offline tournament.
