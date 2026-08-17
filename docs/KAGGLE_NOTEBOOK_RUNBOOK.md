# Kaggle Notebook Runbook

The recommended Kaggle workflow is now **three consolidated CPU notebooks**. The granular E000/E001A/E001B/E002/... notebooks remain in the repository as debugging fallbacks, but normal research should use the consolidated path to reduce repeated imports, serialization, and artifact shuffling.

## Primary 10 — Replay Warehouse + Ladder Forensics

**Notebook**: `notebooks/10_replay_warehouse_forensics_cpu.ipynb`

Combines: **E000 + E001A + E001B + E002**.

**Inputs**
- required: `kaggle/kaggriculture-episodes-index`
- optional: repository/code Dataset. If absent, the notebook clones `sidhulyalkar/kaggriculture` when Internet is enabled.

**Accelerator**: None / CPU

**Internet**: **On**, because public replay acquisition uses Kaggle's official simulation CLI.

**CPU strategy**
- schema-first discovery;
- current-engine filtering when timestamps exist;
- stratified episode sampling;
- up to four concurrent replay downloads;
- process-parallel replay parsing via Parquet shards;
- restart-safe manifests;
- one-time construction of the turn/day warehouse;
- Bradley–Terry strength and open-loop analysis in the same job.

**Default scale**: 300 episodes. After the entire pipeline is green, increase to roughly 1,000–3,000+ while monitoring runtime/storage.

**Outputs**
- `episode_schema_report.csv`
- `selected_episodes.csv`
- `replay_download_manifest.csv`
- `replay_parse_manifest.csv`
- `turns.parquet`
- `daily_macros.parquet`
- `matchups.parquet`
- `bt_strength.csv`
- `open_loop_report.csv`
- `warehouse_summary.json`
- `repo_commit.txt`

Save the notebook output as a Dataset. Later stages do not need to download or parse those raw replays again.

## Primary 11 — Strategy Mining + Predictive Models

**Notebook**: `notebooks/11_strategy_models_cpu.ipynb`

Combines: **E003 + E004 + replay-derived reaction research from E007**.

**Inputs**
- required: output Dataset from notebook 10
- optional code Dataset; otherwise enable Internet and the recorded Git commit is cloned/checked out.

**Accelerator**: None / CPU

**Internet**: Off with a code Dataset; otherwise On only for repo bootstrap.

**Jobs**
- mine replay-derived macro archetypes;
- build `macro_library.json`;
- train the actor-grouped win diagnostic;
- train 24-turn opponent sell/supply forecasting;
- distill a tiny nearest-centroid opponent model;
- mine conditional reactions around price/inventory shocks;
- detect candidate market thresholds without enabling active probes.

**Outputs**
- `archetype_profiles.parquet`
- `macro_library.json`
- `offline_archetype_model.json`
- `learned_model.json`
- `model_metrics.json`
- `reaction_events.parquet`
- `reaction_profiles.parquet`
- optional `reaction_archetypes.parquet` / `reaction_model.json`
- `probe_thresholds.json`
- `model_promotion_diagnostics.json`
- `repo_commit.txt`

Save this output as a Dataset for notebook 12.

## Primary 12 — Robust Search + Meta Equilibrium + Submission Panel

**Notebook**: `notebooks/12_search_meta_submit_cpu.ipynb`

Combines: **robust E005 + equilibrium E007 + E006**.

**Inputs**
- required: notebook 11 output Dataset
- recommended: notebook 10 output Dataset for provenance/diagnostics
- optional code Dataset; otherwise enable Internet for pinned repo bootstrap.

**Accelerator**: None / CPU

**CPU strategy**
- translate mined replay archetypes into approximate ParametricMind opponents;
- combine them with hand-authored V1/counter baselines;
- parallelize CEM candidate evaluation across Kaggle CPU cores;
- optimize expectation + worst-case + lower-tail CVaR rather than one brittle best response;
- evaluate a policy zoo in both seats;
- solve a robust meta-equilibrium;
- build byte-identical-code experiment archives whose only controlled change is `runtime_flags` in the model artifact.

**Default search budget**
- CEM iterations: 4
- population: 20
- seeds: 4
- both seats
- up to four worker processes

This is intentionally a balanced first production pass. Increase the budget only after end-to-end completion.

**Outputs**
- `cem_best.json`
- `policy_params.json`
- `policy_matchups.parquet`
- `meta_artifact.json`
- `learned_model_promoted.json`
- `final_search_summary.json`
- `experiments/S0_control.tar.gz`
- `experiments/S1_robust_fixed.tar.gz`
- `experiments/S2_market_only.tar.gz`
- `experiments/S3_meta_only.tar.gz`
- `experiments/S4_full.tar.gz`
- `experiments/experiment_manifest.json`

## Recommended next ladder experiment

Use the current V1 submission as the historical control and spend the next four slots on orthogonal interventions:

1. `S1_robust_fixed`: tests whether offline macro optimization itself improves the agent.
2. `S2_market_only`: tests only future-supply/predictive selling.
3. `S3_meta_only`: tests only opponent belief + dynamic macro-policy selection.
4. `S4_full`: tests their interaction.

Keep the fifth daily slot in reserve for a packaging/runtime failure or a refinement of the early winner. `S0_control` is available when a fresh same-day control is more valuable than that reserve.

Do not crown a variant from one or two hosted games. Compare rating movement together with episode count, opponent strength, final cash, replay failure modes, and whether the intended component actually changed behavior.

## Runtime safety

The submission runtime now supports explicit feature gates in `learned_model.json`:
- `meta_selection`
- `predictive_selling`
- `fixed_policy`

All experiment archives use the same Python runtime code. The module-global policy is reset explicitly on step 0 so belief/meta state cannot leak across episodes.

## Granular fallback workflow

For debugging a single stage, the older notebooks remain valid:

`E000 -> E001A -> E001B -> E002 -> E003 -> E004 -> E005 -> E007 -> E006`.

The Episodes Index contains metadata/IDs, not replay JSON itself. If a granular replay factory reports `replays found: 0`, run/attach E001A first.
