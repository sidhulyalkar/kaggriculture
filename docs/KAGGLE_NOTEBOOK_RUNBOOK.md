# Kaggle Notebook Runbook

All notebooks are CPU-first. The intended execution order is **E000 -> E001 -> E002 -> E003 -> E004 -> E005 -> E007 -> E006**. E006 remains the final build notebook even though E007 was added later.

## E000 — Episode Index Audit

**Inputs**
- `kaggle/kaggriculture-episodes-index`
- repository source / uploaded suite

**Accelerator**: None

**Internet**: Off

**Key expected files**
- any CSV/Parquet/JSON supplied by the Episodes Index dataset; schema is discovered dynamically.

**Outputs**
- `episode_schema_report.csv`
- `episode_catalog.parquet`

## E001 — Replay Factory

**Inputs**
- E000 `episode_catalog.parquet`
- downloaded replay JSON directory

**Accelerator**: None

**Internet**: On only if downloading replays in the notebook; otherwise Off.

**Key expected files**
- `episode-<id>-replay.json`

**Outputs**
- `turns.parquet`
- `daily_macros.parquet`
- replay manifest

## E002 — Ladder Forensics

**Inputs**
- `turns.parquet`
- `daily_macros.parquet`

**Accelerator**: None

**Internet**: Off

**Outputs**
- `open_loop_report.csv`
- `bt_strength.csv`

## E003 — Macro Strategy Miner

**Inputs**
- E001 tables
- E002 strength report

**Accelerator**: None

**Internet**: Off

**Outputs**
- `archetype_profiles.parquet`
- `macro_library.json`

## E004 — Predictive Models

**Inputs**
- turn/day warehouse
- archetype artifacts

**Accelerator**: None

**Internet**: Off

**Outputs**
- `learned_model.json`
- model metrics

The runtime artifact should contain only features legal at live inference time. Opponent-private replay fields may be labels, never features.

## E005 — Robust Population CEM + Policy Zoo

**Inputs**
- repository source / current controller
- recommended E003 macro artifacts
- optional E004 predictive artifact

**Accelerator**: None

**Internet**: Off

**Outputs**
- `cem_best.json`
- `policy_params.json`
- `policy_matchups.parquet`

The serious objective is not a pure peak best response. Use `cem_optimize_population`, both seats, many seeds, and as broad a replay-derived opponent zoo as practical. The robust objective combines population expectation, worst-archetype value, and lower-tail CVaR.

## E007 — Meta Equilibrium + Conditional Reactions + Probe Audit

**Inputs**
- E001 `turns.parquet`
- E002 `bt_strength.csv`
- E005 `policy_matchups.parquet`
- optional E005 `policy_params.json`

**Accelerator**: None

**Internet**: Off

**Outputs**
- `reaction_events.parquet`
- `reaction_profiles.parquet`
- `reaction_archetypes.parquet`
- `reaction_model.json`
- `probe_thresholds.json`
- `meta_artifact.json`

This stage performs three jobs:

1. Cluster **conditional reactions** to price shocks / market floods, weighted by opponent-adjusted strength.
2. Solve the policy-zoo meta game and build a robust equilibrium prior.
3. Detect candidate hard market thresholds for possible future probes.

`probe_thresholds.json` is research output only. It does **not** activate live probing.

## E006 — Submission Build

**Inputs**
- repository `submission/` source
- E004 `learned_model.json` if promoted
- E007 `meta_artifact.json` if promoted
- E005 `cem_best.json` only as a legacy fallback when no meta artifact is available

**Accelerator**: None

**Internet**: Off

**Outputs**
- `submission_v2.tar.gz`

The archive contains:
- `main.py`
- `predictive_agent.py`
- `parametric_agent.py`
- `base_controller.py`
- `runtime_model.py`
- `meta_runtime.py`
- `learned_model.json`

Before submission:
1. inspect the flat tar root;
2. smoke-test `main.agent`;
3. run both-seat held-out tournaments;
4. require robust/worst-archetype performance, not only mean score;
5. profile runtime well below the one-second action budget;
6. keep active probes disabled unless a separate paired promotion test clears them.
