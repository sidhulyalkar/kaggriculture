# Architecture

## Design objective

Maximize expected pairwise ladder win probability while keeping the low-level executor deterministic, testable, and comfortably under the per-turn runtime budget.

## Modules

### 1. Replay Data Factory

`src/kagv2/replay.py` and `src/kagv2/schema.py`

Responsibilities:
- discover episode-index schema;
- parse replay JSON;
- normalize player trajectories;
- build turn-level and daily tables;
- create future-action labels;
- keep engine-era metadata.

### 2. Ladder Forensics

`src/kagv2/ladder.py`

Responsibilities:
- deduplicate matchups;
- fit Bradley-Terry opponent-adjusted strength;
- quantify macro action entropy/open-loopness;
- separate raw cash from actual win outcomes.

### 3. Strategy Miner

`src/kagv2/macros.py`

Responsibilities:
- create episode macro profiles;
- cluster recurring strategies;
- distill day-indexed target schedules;
- export macro libraries.

### 4. Predictive Models

`src/kagv2/models.py` and `src/kagv2/runtime_features.py`

Responsibilities:
- train CPU-friendly future-supply models;
- train diagnostic win/value models;
- export only runtime-safe public feature sets;
- distill models to JSON/NumPy-free arithmetic where possible.

### 5. Best-Response Search

`src/kagv2/cem.py`

Searches a low-dimensional macro parameter vector. The evaluator is external so the same optimizer can target:
- global population win rate;
- archetype-specific win rate;
- robust worst-case mixture;
- exploitative best response.

### 6. Deterministic Submission Controller

`submission/base_controller.py`

Owns mechanical correctness and should remain independently useful if all learned artifacts are deleted.

### 7. Selective Predictive Layer

`submission/predictive_agent.py`

Prediction is allowed to alter only promoted macro parameters or accelerate selling under confidence gates. It must not replace mechanical safety.

## State separation

A strict distinction is maintained between:

- **public runtime features**: legal inputs available to the agent during an episode;
- **private offline labels**: replay information that may be used as a training target but never included in live features.

This prevents accidental train/runtime leakage.
