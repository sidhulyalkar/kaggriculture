# Winning Research Roadmap

Last updated: 2026-08-18

This document defines how the project should allocate compute, choose experiments, and decide which agents deserve leaderboard slots.

## Objective

Build an agent that wins by combining a strong production backbone with sparse, learned, opponent-aware residual decisions. The project should not chase leaderboard noise or repeatedly clone public tapes.

The current control is V32. Until evidence says otherwise, V32 is treated as a high-value invariant rather than a disposable baseline.

## Current strategic thesis

The public field has converged on strong 30-day production programs, replay/tape backbones, stable routing, and modest market corrections. Our durable edge should come from capabilities that static tapes do not have:

1. reconstruct hidden opponent economic state from public observations;
2. forecast near-term opponent supply and liquidity decisions;
3. branch counterfactually from exact V32 decisions and learn state-dependent regret;
4. identify exogenous seed/town regimes where V32 becomes vulnerable;
5. apply only sparse, confidence-gated residuals unless a replacement backbone proves itself independently.

## Research stack

```text
                 LIVE LADDER
                     ^
                     |
        runtime-verified promoted agent
                     ^
                     |
          independent confirmation
                     ^
                     |
     ordinary held-out + hard-seed suite
                     ^
                     |
      causal residual / learned subsystem
                     ^
                     |
              exact V32 anchor

Offline intelligence layers:

public agents + replay population
            |
            +--> FarmLedger hidden-state estimator
            +--> opponent 4/12/24-turn supply forecast
            +--> counterfactual regret database
            +--> seed-regime difficulty model
```

## Wave-19 lanes

### Lane A — generalization science

Notebook: `19A_ledger_leave_one_family_out.ipynb`

Purpose: verify whether the Wave-18C FarmLedger result survives complete opponent-family holdout.

Success means the estimator is learning transferable game structure rather than merely memorizing public deterministic routes.

### Lane B — immediate submission research

Notebook: `19B_ledger_front_run_mpc_tournament.ipynb`

Purpose: turn opponent-sale forecasting into a tiny market residual around exact V32.

Only this lane may mint a Wave-19 live tar without another notebook. Promotion requires:

- exact V32 wrapper parity;
- learned forecast held-seed quality;
- nonzero residual activation;
- positive fresh paired robust delta;
- bounded worst guard regression;
- non-negative direct V32 head-to-head;
- successful official Kaggle loader/full-episode runtime before and after packing.

### Lane C — counterfactual advantage learning

Notebook: `19C_regret_gated_capital_learner.ipynb`

Purpose: learn when suppressing a HIRE or strawberry-seed purchase has positive final-game value.

This lane cannot directly submit. A positive result creates a frozen candidate that must survive an independent confirmation notebook.

### Lane D — adversarial validation infrastructure

Notebook: `19D_seed_regime_stress_lab.ipynb`

Purpose: explain the large seed-to-seed variability seen in V32 vs Adaptive/Ranker and create a permanent hard-seed stress suite.

The hard suite should become part of every future promotion protocol.

## Promotion pipeline

### Gate 0: experiment integrity

Before strategic conclusions:

- dynamic imports registered in `sys.modules`;
- zero unexpected invalid games;
- exact source/artifact hashes recorded;
- no-op wrapper parity when an exact-anchor residual is claimed;
- actual intervention activation count reported.

Failure here means **INFRA INVALID**, not strategy rejection.

### Gate 1: mechanism evidence

A subsystem must show the mechanism exists.

Examples:

- forecast model: group-held-out AUC/R²;
- regret model: grouped out-of-fold discrimination/calibration;
- scheduler: lower idle/travel without FEED/CARE regressions;
- market residual: actual order changes and local predicted economic advantage.

### Gate 2: paired gameplay screen

Use same seed, both seats, exact control.

Kill candidates that:

- have invalid actions;
- do not actually activate;
- materially reduce target or robust performance;
- reduce aggregate cash dramatically even if a small win-rate sample is lucky.

### Gate 3: broad fresh holdout

Use fresh seeds and every available opponent family.

Primary metric: paired win delta.

Secondary metrics:

- paired final-margin delta;
- direct V32 score;
- worst-family delta;
- activation count;
- own cash ratio;
- per-turn latency.

### Gate 4: adversarial hard-seed suite

Once 19D exists, every candidate must be tested on:

- hard seeds;
- safe-control seeds;
- seat-asymmetry seeds;
- both seats.

This is specifically intended to prevent a candidate from looking strong only because its ordinary fresh seed sample was easy.

### Gate 5: independent confirmation

Freeze code and thresholds before this gate.

Use unseen seeds. Do not retune after reading the result. A failure sends the mechanism back to research rather than prompting threshold surgery on the confirmation set.

### Gate 6: runtime contract

Exact archive must pass:

1. official last-callable loader;
2. full Kaggriculture episode;
3. pack archive;
4. unpack exact archive;
5. loader again;
6. full episode again;
7. SHA-256 recorded.

### Gate 7: live ladder

The live ladder confirms offline evidence. It is not the optimizer.

For every official submission record:

- artifact hash;
- git branch/commit;
- exact offline decision record;
- submission timestamp;
- rating snapshots and episode count;
- replay IDs for informative wins/losses;
- execution logs for failures.

## Compute allocation

When multiple Kaggle CPU notebooks can run simultaneously, prefer orthogonal lanes:

- 25% submission-candidate tournament;
- 25% opponent modeling/generalization;
- 25% counterfactual regret mining;
- 25% adversarial seed/meta mapping.

Do not spend four notebooks on neighboring thresholds of the same mechanism.

## Submission-slot policy

A daily slot should represent a distinct hypothesis with offline support.

Never spend a slot on:

- exact-byte clones;
- zero-activation wrappers;
- candidates that failed held-out promotion;
- candidates created solely because an early rating snapshot is noisy;
- infrastructure-invalid experiments.

Prefer one strong submission with a known causal reason over four speculative variants.

## Medium-term architecture

If Wave 19 supports the current thesis, evolve toward:

```text
Exact V32 / stronger validated backbone
        |
        v
FarmLedger belief state
        |
        v
Opponent 4/12/24-turn forecast
        |
        v
Relative-value market/capital residual
        |
        v
Confidence gate + deterministic fallback
        |
        v
Persistent validated agent
```

Later research can add:

- persistent worker ownership / route hysteresis;
- short-horizon economic MPC for crop/animal allocation;
- population payoff matrix / PSRO or fictitious-play mixtures;
- adversarial camouflage against public-state routers;
- online opponent-state updates that do not require identifying a named public family.

## Definition of real progress

A version number is not progress. Real progress is one of:

- a new causal mechanism with held-out support;
- a substantial reduction in a known failure mode;
- a new adversarial evaluation set that changes promotion quality;
- a promoted agent that beats the champion on fresh paired games without sacrificing robustness;
- a reproducible live rating improvement consistent with offline evidence.

Everything else belongs in diagnostics, not in the champion.