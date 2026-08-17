# Kaggle Notebook Runbook

All notebooks are CPU-first.

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

## E005 — CEM Best Response

**Inputs**
- policy zoo / macro library
- current controller
- optional predictive model

**Accelerator**: None

**Internet**: Off

**Outputs**
- `cem_best.json`
- policy-by-archetype mapping

## E006 — Submission Build

**Inputs**
- promoted model/search artifacts
- `submission/` source

**Accelerator**: None

**Internet**: Off

**Outputs**
- `submission_v2.tar.gz`

Before submission, inspect the tar root and smoke-test `main.agent`.
