# Autonomous operating loop

V45 splits autonomy into two trust domains:

1. **Research domain** — frontier models generate independent hypotheses and complete candidate `main.py` files.
2. **Evidence domain** — deterministic code performs static checks, tournament screening, sealed evaluation, and promotion.

This separation is intentional. A research model cannot alter held-out seeds, promotion thresholds, or its own evaluation record.

## Commands

### 1. Validate orchestration without spending inference budget

```bash
python -m swarm.run_epoch --config swarm/config/default.yaml --dry-run
```

This exports all role-specific requests to `swarm/runs/<epoch>/outbox/` and validates the information firewall.

### 2. Run live research/build generation

```bash
export OPENAI_API_KEY=...
export NVIDIA_API_KEY=...
python -m swarm.run_epoch --config swarm/config/default.yaml
```

Generated candidates are quarantined under `swarm/runs/<epoch>/candidates/`. They are not copied into `submission/` and are not automatically submitted.

### 3. Evaluate candidates

```bash
python -m swarm.evaluate_epoch \
  swarm/runs/<epoch> \
  --config swarm/config/default.yaml \
  --evaluator your.module:evaluate_candidate \
  --champion-path path/to/current_champion/main.py
```

The evaluator adapter must return the normalized evidence fields described in `swarm/experiment_adapter.py`. This lets the swarm use the existing local league, Kaggle notebook tournament outputs, or a future faster simulator without changing research orchestration.

### 4. Inspect portfolio

`EPOCH_EVALUATION.json` contains the five-role portfolio: champion, counter, architecture, robust, and explorer. A slot remains null when no candidate passes the hard promotion gate.

## Autonomous cadence

A practical unattended epoch is:

- generate independent claims in parallel;
- build candidates from frozen claims;
- reject unsafe/invalid source statically;
- screen both seats on public screen seeds;
- evaluate survivors on sealed seeds;
- apply deterministic promotion gates;
- send evidence summaries to independent council reviewers;
- prioritize disagreement for replication;
- release mechanism hints to lagging research lanes in the next epoch;
- only then prepare submission artifacts.

Kaggle submission remains an explicit outer action because leaderboard submissions are scarce experimental measurements and should not be burned by an unconstrained generator.
