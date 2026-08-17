# Kaggriculture Kaggle CPU Runbook v4.2

## Why v4.1 died

The previous public-population warehouse used the generic schema auditor. That helper reads each table into pandas. On the packed public corpus this can materialize `replays.parquet` solely to inspect its schema, which can exceed Kaggle notebook RAM and cause a hard kernel death rather than a Python exception.

## v4.2 memory policy

Run `notebooks/10_public_population_warehouse_cpu_v42.ipynb` first.

Inputs:

- Kaggriculture Episodes public bundle
- Kaggriculture Episodes Index
- code repo is optional
- Accelerator: None
- Internet: Off

The notebook obeys these rules:

- `episodes.csv`: full load, because it is the compact matchup table.
- `replays.parquet`: PyArrow metadata only, never `pd.read_parquet`.
- `stream_hashes.csv`: chunked reduction.
- `daily_stats.csv`: 25k-row schema/sample only.
- `episode_features.csv`: 25k-row schema/sample only.
- official `manifest.csv`: header/row-count audit only.

Outputs to inspect before designing the next aggregation notebook:

- `public_warehouse_summary.json`
- `public_corpus_schema.csv`
- `large_table_samples.json`
- `replays_schema.csv`
- `bt_strength.csv`
- `strategy_hash_frequency.csv` when a hash field is present
- `episodes_master.parquet`
- `episode_players.parquet`

## Why notebook 11 should wait

The older notebook 11 was built around a raw-replay warehouse containing `turns.parquet` and `daily_macros.parquet`. The packed public dataset already exposes `daily_stats.csv`, `episode_features.csv`, and `replays.parquet`, so blindly recreating that raw warehouse wastes RAM and CPU.

Use notebook 10 v4.2 to reveal the exact packed schemas and freshness first. Then build notebook 11 around chunked aggregation of the actual fields, with raw replay expansion restricted to representative/high-value episodes.

## Final submission experiments

The controlled submission panel remains the target after the data/model stages:

- `S0_control`: learned components disabled.
- `S1_robust_fixed`: fixed robust-CEM macro strategy.
- `S2_market_only`: predictive selling only.
- `S3_meta_only`: opponent/meta selection only.
- `S4_full`: both learned components.

Normally submit S1-S4 and keep the fifth daily slot available for a repair or evidence-driven refinement.
