# Kaggriculture Autonomous Swarm Lab

This directory contains the research-orchestration layer that sits above the competitive Kaggriculture policy stack.

The swarm is intentionally separated from the submitted runtime. Frontier LLMs act as researchers, critics, adversaries, and experiment designers; generated policy candidates are evaluated by the existing deterministic league and promotion gates before any submission artifact is considered.

## Design principles

1. **Independent discovery before collaboration** — research roles receive different information packets so the population does not collapse onto one idea.
2. **Claims require experiments** — every proposal must define a mechanism, expected failure mode, screen, held-out test, and measurable promotion criterion.
3. **Champion is protected** — the current qualified frontier is always retained as a control. Failed swarm epochs cannot silently replace it.
4. **Novelty matters** — the orchestrator rewards behavioral and architectural diversity, not only mean score.
5. **Adversaries are first-class researchers** — counterexample discovery and exploit generation feed permanent regression suites.
6. **Sealed evaluation** — workers do not receive held-out seeds or sealed-test outcomes before their candidate is frozen.
7. **Evidence is append-only** — hypotheses, candidates, reviews, and promotion decisions are written to JSONL registries.
8. **Providers are interchangeable** — OpenAI, NVIDIA NIM, local/manual agents, and future providers implement a common request/response contract.

## First autonomous loop

```bash
python -m swarm.run_epoch --config swarm/config/default.yaml --dry-run
```

A live provider run requires provider credentials in the environment. The dry run is still useful: it builds role-specific research packets, creates the epoch manifest, validates the registry, and emits the exact tasks that should be sent to each research model.

The initial V45 orchestration loop is deliberately conservative. It does not automatically submit to Kaggle and it does not automatically merge generated code. Candidates must pass local validation and the repository promotion contract first.
