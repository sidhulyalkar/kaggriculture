# Autonomous operating loop

V45 splits autonomy into two trust domains:

1. **Research domain** — frontier models generate independent hypotheses and complete candidate `main.py` files.
2. **Evidence domain** — deterministic code performs static checks, paired tournament screening, sealed evaluation, and promotion.

This separation is intentional. A research model cannot alter held-out seeds, promotion thresholds, or its own evaluation record.

## Current research population

The default config deliberately uses different model families for different jobs:

- GPT-5.6 Sol: blank-sheet architecture and chief-scientist review.
- DeepSeek V4 Pro 0813 through NVIDIA NIM: adversarial counter-policy search and audit.
- NVIDIA Nemotron 3 Ultra 550B: mechanism research and council review.
- Kimi K3 through NVIDIA NIM: protected-frontier residual search.
- NVIDIA Nemotron 3.5 Lightning 30B A3B: high-throughput exploration.

Provider/model selection is configuration, not code. Any role can be reassigned without changing the evidence pipeline.

## Commands

### 1. Validate orchestration without spending inference budget

```bash
python -m swarm.run_epoch --config swarm/config/default.yaml --dry-run
```

This exports all role-specific requests to `swarm/runs/<epoch>/outbox/`, validates the information firewall, and is exercised in CI.

### 2. Run one live research/build epoch

```bash
export OPENAI_API_KEY=...
export NVIDIA_API_KEY=...
python -m swarm.run_epoch \
  --config swarm/config/default.yaml \
  --champion-path /agents/champion/main.py
```

The exact champion source is exposed only to champion-informed counter/mechanism/residual roles. Blank-sheet architecture workers remain isolated from it. Generated candidates are quarantined under `swarm/runs/<epoch>/candidates/`; they are not copied into `submission/` and are not automatically submitted.

### 3. Evaluate candidates with the built-in Kaggriculture adapter

```bash
export SWARM_OPPONENTS_JSON='{"soil":"/agents/soil/main.py","moon":"/agents/moon/main.py","adaptive":"/agents/adaptive/main.py"}'
python -m swarm.evaluate_epoch \
  swarm/runs/<epoch> \
  --config swarm/config/default.yaml \
  --champion-path /agents/champion/main.py
```

`SWARM_OPPONENTS_JSON` is optional. Without it, the evaluator still runs candidate/champion/passive controls. For serious qualification, point it at the family-normalized opponent zoo. Each game loads fresh agent modules in a timeout-bounded subprocess, matching the isolation philosophy of the V44 tournament worker.

### 4. Convene the independent council

```bash
python -m swarm.review_epoch swarm/runs/<epoch>
```

The council receives **screen evidence only**. Its `NEXT_EPOCH_HINTS.json` may be released to the next research round. Sealed held-out evidence is never turned into research feedback.

### 5. Run a complete autonomous campaign

```bash
python -m swarm.run_campaign \
  --champion-path /agents/champion/main.py \
  --epochs 3
```

A campaign performs, for each round:

1. independent role-specific research;
2. frozen-claim candidate generation;
3. static source quarantine;
4. paired screen evaluation;
5. sealed held-out evaluation and deterministic promotion;
6. screen-only council review;
7. controlled mechanism-hint release to the next round.

Screen and held-out seed sets are shifted by `10000 * round`, so successive epochs do not repeatedly measure the exact same episodes. Blank-sheet architects do not receive cross-agent hints and remain an explicit diversity reservoir.

## Five-slot experimental portfolio

`EPOCH_EVALUATION.json` emits a portfolio rather than five correlated variants:

- `champion`: strongest promoted candidate by overall evidence, otherwise `CURRENT_CHAMPION`;
- `counter`: strongest targeted family gain;
- `architecture`: strongest independently developed architecture;
- `robust`: strongest worst-family candidate;
- `explorer`: highest-novelty promoted candidate.

Non-champion slots stay null when no candidate clears their hard gate. `HOLD` is a valid scientific result.

## Safety and anti-overfit boundaries

- Workers never receive held-out seed values.
- Held-out results are not fed back into research prompts.
- Cross-agent information release begins at mechanism-level hints, not source copying.
- Blank-sheet architecture workers remain isolated from prior implementation hints and champion source.
- Generated source is quarantined and statically checked before execution.
- Network/LLM libraries, subprocess launchers, `eval`, dynamic imports, and runtime-generated `exec` are rejected in generated submissions.
- V44-style embedded parent code is allowed only when the executed source is statically recoverable and recursively passes the same safety policy.
- Every game executes in a timeout-bounded subprocess.
- Promotion is deterministic and lane-aware; models cannot vote themselves into the champion slot.
- The current champion is fixed as the control during a campaign.
- Kaggle submission remains an explicit outer action because leaderboard submissions are scarce experimental measurements.
