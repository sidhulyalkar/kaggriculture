# Experiments

This directory is the durable evidence chain for Kaggriculture research.

## Canonical files

- [`EXPERIMENT_LEDGER.md`](EXPERIMENT_LEDGER.md) — chronological record of material experiments, including negative results and infrastructure failures.
- [`EXPERIMENT_TEMPLATE.md`](EXPERIMENT_TEMPLATE.md) — required fields for every new experiment record.
- `v3_frontier_transplant/` — retained historical experiment implementation.

## Required discipline

Every experiment that can influence a submission decision should record:

```text
experiment_id
status
hypothesis
exact control artifact / hash
candidate change
source branch / commit
notebook or script
input population
seed sets
both-seat protocol
integrity checks
activation count
paired win delta
paired margin delta
worst-family result
direct-champion result
learned-model validation when applicable
runtime checks
decision
next action
live submission ID / rating history / replay IDs when applicable
```

Do not overwrite historical results when tuning. Append a new experiment entry.

An infrastructure failure is recorded as **INFRA INVALID**, not as evidence against the strategy hypothesis.

The leaderboard is a confirmation environment, not a hyperparameter optimizer. Exact-byte clones, zero-activation wrappers, and candidates that failed offline promotion should not consume submission slots.
