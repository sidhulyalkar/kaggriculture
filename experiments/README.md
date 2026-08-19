# Experiments

This directory is the durable evidence chain for Kaggriculture research.

## Canonical files

- [`EXPERIMENT_LEDGER.md`](EXPERIMENT_LEDGER.md) — chronological record of material experiments, including negative results and infrastructure failures.
- [`EXPERIMENT_TEMPLATE.md`](EXPERIMENT_TEMPLATE.md) — required fields for every new experiment record.
- [`neuroloss5/README.md`](neuroloss5/README.md) — first five-agent neuroscience-inspired live ablation family.
- [`wave20/SANDBOX_VALIDATION.md`](wave20/SANDBOX_VALIDATION.md) — real-artifact validation of the loss-driven evolution framework.
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

## NeuroLoss experiment philosophy

The NeuroLoss family deliberately uses several live slots as a **mechanistic ablation study**. Each agent isolates a different learning-from-loss hypothesis: minimal causal correction, episodic memory, regime-dependent plasticity, fast/slow consensus, or an integrated stack.

Live ratings should therefore be read together with replay context, activation behavior, opponent strength, and seat rather than treated as anonymous scores. The purpose is to learn which computational mechanism deserves the next round of causal data generation.