# V45 Autonomous Swarm Lab

V45 changes the unit of optimization from a single hand-directed agent version to an autonomous research population. The submitted Kaggriculture policy remains ordinary deterministic Python; frontier LLMs operate outside the game as researchers, adversaries, implementers, and scientific reviewers.

## Thesis

A population of independent researchers should discover more useful strategy diversity than one agent repeatedly editing the current champion. The value of the swarm is therefore not a vote among models. It is a controlled mechanism for producing different hypotheses, testing them under one deterministic evidence contract, and preserving only reproducible gains.

## Research lanes

- **Architecture**: blank-sheet controller designs. These workers receive the engine contract, architecture docs, and a basic runnable reference, but not V44 source or cross-agent implementation hints.
- **Counter-policy**: deliberately exploit the fixed current champion and expand the regression population.
- **Mechanism**: explain causal leaks in routing, markets, capital timing, shed pressure, crop maturation, animal economics, and terminal behavior.
- **Frontier residual**: retain the exact champion source and search for small state-aware repairs.
- **Explorer**: pursue underrepresented strategy families such as finite-state synthesis, evolutionary macros, mixtures, search, or compact value models.
- **Audit**: challenge evidence rather than generate production candidates.

## Information topology

The first round is independent discovery. Later rounds may receive mechanism-level feedback generated from public screen evidence. Blank-sheet architecture workers remain isolated throughout.

Sealed held-out results are never converted into research hints. V45 rotates both screen and held-out seed sets between campaign rounds so that later epochs do not repeatedly optimize against the same episodes.

## Trust boundary

LLMs control hypothesis generation and candidate source generation. They do **not** control:

- screen or held-out seeds;
- opponent-family selection;
- promotion thresholds;
- tournament results;
- promotion decisions;
- the current campaign champion;
- Kaggle submission.

Generated `main.py` files enter quarantine. Static validation rejects direct network clients, subprocess launchers, dynamic imports, `eval`, and runtime-generated `exec`. V44-style embedded parents are supported only when the executed source is statically recoverable and recursively passes the same safety policy. Every game then runs in a timeout-bounded subprocess.

## Evidence contract

Each candidate is compared against the fixed champion on the same opponents, seeds, and both seats. The evaluator records paired score delta, worst-family delta, passive-cash ratio, invalid games, latency, physical-action divergence, family-specific deltas, and a behavioral fingerprint.

Promotion is deterministic. Protected residuals retain V44-like physical-divergence gates; genuinely new architecture/counter/explorer lanes receive separate divergence limits while still requiring positive paired competitive evidence and zero invalid games.

The current champion remains the fallback champion whenever no candidate clears promotion.

## Council

After screening, independent council models review only the screen evidence. Candidate disagreement is treated as a reason to replicate rather than averaged away. The council emits:

- replication priorities;
- mechanism-level hints for the next research round;
- missing hypotheses or strategy families.

Those outputs become the only cross-epoch research feedback.

## Campaign loop

```text
fixed champion
     |
     v
independent research population
     |
     v
frozen claims -> candidate main.py
     |
     v
static quarantine
     |
     v
paired screen tournament
     |                    \
     |                     -> screen-only council -> next-round hints
     v
sealed held-out tournament
     |
     v
deterministic promotion
     |
     v
champion / counter / architecture / robust / explorer portfolio
```

One campaign can execute multiple rounds using `python -m swarm.run_campaign`. The champion is intentionally fixed for the duration of a campaign; promoted policies become evidence and submission candidates, not silently self-replacing parents.

## External inference

Provider adapters currently support OpenAI Responses and NVIDIA NIM plus a manual/offline packet exporter. Credentials are environment-only and are never written into manifests or JSONL registries.

The default role assignment is configuration, not architecture. Models can be changed as stronger or cheaper providers become available without modifying the experiment contract.
