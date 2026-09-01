# Autonomous Kaggriculture Competition Loop

The objective is not to maximize local cash. It is to maximize robust episode win probability against the population that will actually rate the submission.

## Data plane

`python -m swarm.kaggle_intelligence` maintains a resumable mirror with two layers.

1. **Public meta:** the official daily episode index, fresh day manifests, the highest-rated episodes, and a spaced sample from the upper Elo band. Episode JSONs are content-hashed and cached; subsequent runs refresh manifests but reuse unchanged episode files.
2. **Authenticated transfer evidence:** when `KAGGLE_API_TOKEN` is available, the mirror also captures our current submission limits, submission history, the exact rated episodes for recent submissions, replay files for those episodes, the visible leaderboard, active public submissions for top teams, and recent/top discussion indexes. If credentials are absent this lane is skipped without breaking public research.

The Kaggle CLI's simulation-specific `episodes`, `replay`, and `logs` interfaces are intentionally preferred for our own transfer diagnosis. They tell us what the ladder actually evaluated instead of relying on a historical public notebook Elo.

## Candidate plane

`python -m swarm.overnight_slate` recovers the exact historical Soil parent by SHA-256 and creates a causal population rather than arbitrary rewrites:

- frozen exact parent;
- previously hash-verified H6 aggressive market policy;
- previously hash-verified robust market policy;
- route selectors distilled from fresh winner traces across the parent's five existing physical route schedules;
- bounded council hypotheses, when supplied.

Winner replays are **teachers**, not the sole promotion arena. The route learner asks which existing deterministic physical schedule most closely explains each winner under each observed shop prefix. The candidate then changes only `_kawa_route_label`; routing, farming, market guards and the rest of the 719-turn controller remain untouched.

## Evaluation plane

Replay teachers are held out by team. Final ranking also uses executable both-seat cross-play against:

- the exact parent;
- aggressive and robust internal policies;
- downloadable public frontier controllers (Strict, Barnyard, WeedSlip, Moon, Soil) when available.

The primary statistic is win score. Cash margin is retained for diagnostics but cannot buy promotion. A diversity-aware slate prevents all five daily slots from becoming near-clones of one route family.

## NVIDIA council

`python -m swarm.overnight_council` is deliberately bounded. Nemotron reviewers may propose exactly one of:

- a shop-prefix to existing-route change;
- a bounded mutation to one registered market/preemption parameter.

Arbitrary source code and dependency changes are rejected before compilation. The second sweep compiles each accepted hypothesis as a separate causal candidate and makes it survive the same executable tournament before it can reach the final slate.

## Scheduled loop

`.github/workflows/overnight-swarm.yml` runs two research waves after merge to the default branch:

- 09:15 UTC, roughly 02:15 Pacific during PDT: broad overnight refresh;
- 19:30 UTC, roughly 12:30 Pacific during PDT: pre-reset refresh using the newest episodes.

Each wave:

1. restores the cached Kaggle mirror;
2. refreshes only new metadata/replays;
3. builds an evidence-only slate;
4. asks the bounded NVIDIA council for sparse counter hypotheses;
5. compiles and tournaments those hypotheses;
6. verifies every generated tarball;
7. uploads only compact evidence plus the final submission archives, not gigabytes of raw cached episodes.

## Secrets

`NVIDIA_API_KEY` enables the council. `KAGGLE_API_TOKEN` is optional but strongly recommended because it unlocks exact live transfer evidence from our own rated submissions. Neither secret is written to artifacts or logs by these scripts.

## Morning decision rule

Use `TOMORROW_SLATE.json`, not model prose, as the submission source of truth. Prefer `PROMOTE` candidates. `PROBE` candidates are useful only when their behavioral family adds information not already represented by the two active submissions. `HOLD` candidates should not consume a slot.
