# Kaggriculture: Loss-Driven Agents for a Shared Farming Economy

> **Two autonomous farmers. 30 days. 720 turns. One shared market.**
>
> Build a farm, route workers, care for crops and animals, expand land, predict the opponent, and finish with more bank cash than the agent across the market.

This repository is a CPU-first research and submission stack for Kaggle's **Kaggriculture** simulation competition.

The project began with a deterministic farming controller and replay-driven strategy mining. It has evolved into a more ambitious question:

> **Can an agent learn primarily from the games it loses, identify the earlier decisions that causally contributed to those losses, and become more adaptive without forgetting the strong strategy it already knows?**

Our current answer is the **NeuroLoss** research program: keep a proven deterministic champion as a stable behavioral backbone, then layer sparse, uncertainty-aware learning mechanisms around it.

The guiding design rule remains:

> **Do not ask machine learning to relearn deterministic mechanics. Learn when a strong strategy should break character.**

---

# 🌾 The game the agents are actually playing

Kaggriculture looks like a farming game, but strategically it behaves more like a compact two-player economy with logistics, biological deadlines, hidden inventories, and a shared market.

| | Game mechanic |
|---|---|
| **Players** | 2 autonomous agents |
| **Horizon** | 30 days × 24 turns/day = **720 turns** |
| **Farm** | 10×10 board split into four 5×5 quadrants |
| **Starting land** | Northwest quadrant only |
| **Starting cash** | 3,000 |
| **Crops** | Wheat, carrot, tomato, strawberry, melon |
| **Animals** | Goose, cow, sheep |
| **Products** | Egg, milk, wool, fertilizer |
| **Labor** | One persistent farmer + temporary daily hands |
| **Storage** | Finite central shed |
| **Economy** | Both players change the same market inventory and prices |
| **Winner** | Highest **bank cash** at the end |

Unsold inventory is not terminal wealth. A shed full of beautiful melons on turn 720 is economically a very decorative mistake.

## Why the problem is hard

A strong agent must solve several coupled problems at once:

```text
BIOLOGY
water / feed / grow
      |
      v
LOGISTICS ---> PRODUCTION
workers             |
routing             v
                INVENTORY
                    |
                    v
                MARKET <------ OPPONENT
                    |              |
                    v              |
                   CASH            |
                    |              |
                    +---- WIN / LOSS
```

The farm is not the objective. The farm is a machine for creating **timed exposure to a shared economy**.

A policy must simultaneously reason about:

- same-day watering and crop survival;
- worker routing and shed logistics;
- animal feed and care deadlines;
- nonlinear daily hiring costs;
- land-expansion opportunity cost;
- crop and animal portfolio allocation;
- shared-market price impact;
- town demand;
- opponent production and liquidation;
- terminal conversion of inventory into cash.

That mixture is why a single monolithic end-to-end learner is not our default approach.

---

# 🧠 Current research thesis: learn from losses

The strongest stable policy we have developed is the **V32** champion lineage.

Rather than replacing it every time a new model looks promising, we treat V32 as a high-value invariant: the equivalent of a well-practiced habitual controller. New learning has to earn the right to override it.

```text
                         OBSERVATION
                              |
                +-------------+-------------+
                |                           |
                v                           v
          REGIME RISK                  FARMLEDGER
       P(V32 loses here)          opponent future behavior
                |                           |
                +-------------+-------------+
                              |
                              v
                     EXACT V32 ACTION
                              |
                              v
                 SAFE ALTERNATIVE ACTIONS
                              |
                              v
                LEARNED RELATIVE VALUE
                  upside + downside
                              |
                              v
                     CONFIDENCE GATE
                     /              \
                    /                \
              override V32          keep V32
```

The central learning target is not simply "the best action." It is the **value of departing from the champion**:

```text
DeltaQ(state, action) =
    outcome after alternative action
    -
    outcome after V32 action
```

This gives us a naturally conservative learning system. Most states should still produce the champion action. Learning concentrates on the subset of states where the baseline is likely to fail and a counterfactual alternative has evidence behind it.

---

# 🧬 NeuroLoss: neuroscience-inspired learning from failure

NeuroLoss is a computational design inspired by several broad ideas from neuroscience and reinforcement learning:

- **reward prediction error:** unexpected losses should create a large teaching signal;
- **reverse replay:** after a loss, revisit earlier decisions and ask where a different action would have mattered;
- **episodic memory:** preserve unusual but important failure states without immediately rewriting the global policy;
- **complementary learning systems:** combine fast memory for exceptions with slow statistical learning across many seeds;
- **adaptive plasticity:** become more willing to deviate when the current regime strongly predicts baseline failure;
- **Go / No-Go arbitration:** model both the upside of an intervention and its potential downside.

These are **computational inspirations**, not a claim that the agent literally models a mammalian brain.

The resulting research loop is:

```text
PLAY
 |
 v
LOSS / SURPRISE
 |
 v
REVERSE REPLAY
 |
 v
COUNTERFACTUAL BRANCHING
 same seed / opponent / seat
 |
 v
WHICH DECISIONS ACTUALLY CHANGED THE OUTCOME?
 |
 +----------------------+----------------------+
 |                      |                      |
 v                      v                      v
EPISODIC MEMORY      SLOW VALUE MODEL      REGIME MODEL
rare exceptions      repeated lessons      when V32 fails
 |                      |                      |
 +----------------------+----------------------+
                        |
                        v
             DISTILLED SPARSE RESIDUAL
                        |
                        v
           HARD / SAFE / SEAT STRESS TESTS
                        |
                        v
              LIVE LADDER CONFIRMATION
                        |
                        v
                  NEW LOSSES
```

For the deeper design rationale, see [`docs/NEUROLOSS_STRATEGIES.md`](docs/NEUROLOSS_STRATEGIES.md).

---

# 🧪 The first five NeuroLoss agents

The first live NeuroLoss family is deliberately an **ablation study**, not five neighboring thresholds.

Each agent starts from the exact V32 runtime artifact and adds a different learning mechanism.

| Agent | Computational idea | What changes | Research question |
|---|---|---|---|
| **N1 Dopamine** | Minimal reward-prediction-error correction | One tiny counterfactually positive residual around V32 | Can a single consistently positive causal correction improve the champion? |
| **N2 Hippocampus** | Episodic memory | Similar hard-regime memories can retrieve sparse rescue actions | Are rare failures better handled by memory than global generalization? |
| **N3 LC** | Adaptive plasticity | Learned loss risk changes how willing the policy is to deviate | Should the agent become strategically more plastic only when V32 is likely to lose? |
| **N4 CLS** | Complementary learning systems | Episodic and generalized risk estimates must agree | Does fast memory + slow generalization give safer overrides? |
| **N5 NeuroStack** | Integrated arbitration | Regime risk + episodic memory + causal residual + FarmLedger context | Does combining the useful pieces outperform the individual mechanisms? |

### Initial submission artifacts

All five were built from the exact V32 runtime archive:

`SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`

V32 SHA-256:

`ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`

Experimental artifact hashes:

| Agent | Artifact SHA-256 |
|---|---|
| **N1 Dopamine** | `5f2e723dd8f4be8589e3c1599efa242cc7d8561398afa68c40a6266108a15e25` |
| **N2 Hippocampus** | `3d22f9c34bac119850fdd67b446636f0c1b5c9cc1e22373ad75e7d20f4e4a391` |
| **N3 LC** | `6fb37f9499dbfd10fce5ca573393be117bf27b2b8b90ff1ca15ff0fb71a9c708` |
| **N4 CLS** | `d7d40365706c3b275dbcf7e87380a021d375fdd8c8053d0adc6fbfaa91db6b25` |
| **N5 NeuroStack** | `cb50ebf13ecfedc19a7fb9c1f937b9fdaf7fcea237a70b354a0b458f726d0b4b` |

The first planned live comparison uses **N1, N3, and N5** together because they form a clean experimental triangle:

```text
N1: minimal causal correction
            \
             \
              N5: integrated stack
             /
            /
N3: regime-dependent plasticity
```

N2 and N4 then test whether explicit episodic retrieval and episodic/generalized consensus add value beyond those three mechanisms.

The exact experiment record lives in [`experiments/neuroloss5/README.md`](experiments/neuroloss5/README.md).

---

# 🔬 Why we arrived here

The NeuroLoss design came from a sequence of experiments that changed our view of the problem.

## 1. Strong global heuristics were surprisingly brittle

Several production and market modifications either did not activate or hurt broad performance. The lesson was not "never adapt." It was:

> **Unconditional adaptation is dangerous.**

A rule such as "always hold more wheat" or "always suppress this hire" can be strongly positive in one regime and catastrophic in another.

## 2. Counterfactual losses contained very large local opportunities

Single-decision branch experiments found rare states where suppressing a HIRE or seed purchase changed final margin by thousands of dollars. But the same intervention had a negative average effect across all states.

That changed the question from:

> "Should V32 hire less?"

into:

> "Can we recognize the states in which *this particular hire* is a mistake?"

## 3. The opponent is highly predictable from public state

FarmLedger experiments showed that near-term opponent sale behavior can be predicted surprisingly well even when an entire policy family is held out.

A compact linear leave-one-family-out sale model reached a median AUC around **0.91** across the tested targets.

However, a crucial negative result followed: directly front-running predicted opponent sales did **not** improve paired gameplay.

So:

> **Prediction is context, not automatically an action.**

The forecast should help value alternative decisions rather than directly trigger them.

## 4. Seed / town regimes strongly predict V32 failure

A 640-game stress experiment across 64 independent seeds found that the exogenous game regime is highly informative about when V32 loses.

The later whole-seed grouped model reached roughly:

- OOF AUC: **0.921**
- Brier score: **0.094**
- top-risk-quartile loss rate: **~0.81**
- lift over the base loss rate: **~2.46×**

This is the foundation of N3 and part of N5.

## 5. AUC alone can lie about policy quality

A first regret learner looked excellent until we tightened the validation boundary.

When the same seed was allowed to appear across opponent-specific folds, the model could partially learn the seed regime rather than the intervention's transferable value.

After changing validation to hold out **entire seeds**, the current counterfactual dataset had only five independent loss seeds. Benefit classification remained strong, but margin prediction became too uncertain and no conservative residual policy had enough positive out-of-seed realized value to promote.

That produced a permanent rule:

> **A predictive model is not promoted because its AUC is good. The policy induced by that model must itself have positive out-of-seed value.**

---

# 🤖 Agentic evolution framework

The repository now treats strategy research as a closed-loop evolutionary process:

```text
             CHAMPION POLICY
                   |
                   v
             PLAY POPULATION
                   |
                   v
            PRIORITIZE LOSSES
            /              \
           /                \
     known-hard          surprise
           \                /
            \              /
             v            v
         COUNTERFACTUAL FACTORY
                   |
                   v
          DISTRIBUTIONAL REGRET
                   |
                   v
          SPECIALIST CANDIDATES
                   |
                   v
        ADVERSARIAL PROMOTION GATES
                   |
                   v
              POLICY POPULATION
                   |
                   v
             PSRO / META GAME
                   |
                   v
            LIVE CONFIRMATION
                   |
                   v
                NEW DATA
```

Implemented modules under `src/kagv2/agentic/` include:

- `regime.py` — whole-seed champion-loss risk modeling;
- `forecast.py` — unseen-family forecast reliability gates;
- `losses.py` — known-hard and surprise loss prioritization;
- `interventions.py` — bounded intervention grammar;
- `counterfactual.py` — deterministic one-decision branch factory;
- `regret.py` — distributional residual-value learning;
- `promotion.py` — hard/safe/seat/direct-champion promotion gates;
- `population.py` — robust policy-population analysis / PSRO support;
- `loop.py` — end-to-end offline evolution orchestration.

See [`docs/AGENTIC_EVOLUTION_FRAMEWORK.md`](docs/AGENTIC_EVOLUTION_FRAMEWORK.md).

---

# 🧱 Why we keep deterministic mechanics separate

Routing, watering, feeding, harvesting, shed handling, market-order limits, and terminal liquidation have hard mechanics. A learner does not get extra credit for rediscovering them badly.

The deterministic controller therefore owns:

- worker routing;
- same-day watering;
- harvest timing;
- animal feed/care;
- pickup/drop/place;
- daily hand hiring;
- seed and animal acquisition;
- land expansion;
- shed-capacity protection;
- market-order legality;
- terminal liquidation.

Learning focuses on uncertain strategic questions:

- Is this a regime where the champion usually fails?
- What is the opponent likely to produce or sell next?
- Which current decision has high counterfactual regret?
- Is there a similar historical failure state?
- Does the expected upside justify the downside risk of an override?

This division is one of the central engineering choices in the project.

---

# ⚖️ Promotion philosophy

The live ladder is a **confirmation environment**, not our hyperparameter optimizer.

A serious candidate should eventually pass:

```text
exact champion parity when no residual fires
        |
        v
actual intervention activation
        |
        v
ordinary fresh seeds
        |
        v
fixed hard seeds
        |
        v
safe-control seeds
        |
        v
seat-asymmetry seeds
        |
        v
broad opponent guards
        |
        v
direct champion matchup
        |
        v
independent confirmation
        |
        v
runtime / packaging contract
        |
        v
LIVE LADDER
```

Important permanent rules:

1. **Both seats.** A strategy is not validated from one seat.
2. **Same-seed paired comparisons.** Reduce environmental noise.
3. **Whole-seed validation for learned residuals.** Never leak a seed regime across folds.
4. **Hold out opponent families where relevant.** Distinguish transferable game structure from tape memorization.
5. **Count actual activations.** A source-code change that never changes an action is not evidence.
6. **Hard seeds are first-class tests.** Random easy seeds can hide the real weakness.
7. **Protect safe regimes.** Improving losing states is not useful if we destroy games V32 already wins.
8. **Prediction must improve policy value.** AUC is diagnostic, not a leaderboard metric.
9. **Record every artifact SHA.** Every live result must map back to exact code.
10. **Negative results stay in the ledger.** A rejected mechanism still teaches us where not to search.

The durable experiment history is kept in [`experiments/EXPERIMENT_LEDGER.md`](experiments/EXPERIMENT_LEDGER.md).

---

# 📁 Repository layout

```text
.
├── README.md
├── STATUS.md
├── RESEARCH_NOTES.md
│
├── docs/
│   ├── AGENTIC_EVOLUTION_FRAMEWORK.md
│   ├── NEUROLOSS_STRATEGIES.md
│   ├── WINNING_RESEARCH_ROADMAP.md
│   ├── ARCHITECTURE.md
│   ├── ENGINE_CONTRACT.md
│   ├── EXPERIMENT_PROTOCOL.md
│   └── KAGGLE_NOTEBOOK_RUNBOOK.md
│
├── experiments/
│   ├── EXPERIMENT_LEDGER.md
│   ├── EXPERIMENT_TEMPLATE.md
│   ├── neuroloss5/
│   │   └── README.md
│   └── wave20/
│       └── SANDBOX_VALIDATION.md
│
├── src/kagv2/
│   ├── simulator.py
│   ├── replay.py
│   ├── models.py
│   ├── equilibrium.py
│   └── agentic/
│       ├── regime.py
│       ├── forecast.py
│       ├── losses.py
│       ├── interventions.py
│       ├── counterfactual.py
│       ├── regret.py
│       ├── promotion.py
│       ├── population.py
│       └── loop.py
│
├── submission/
│   ├── main.py
│   ├── base_controller.py
│   └── ...
│
├── scripts/
│   ├── run_agentic_evolution.py
│   ├── tournament.py
│   └── ...
│
└── tests/
    ├── test_agentic_evolution.py
    └── ...
```

---

# 🧭 Current research state

### Stable control

**V32** remains the champion/control until live and offline evidence supports replacement.

### Active experimental family

**NeuroLoss-5** tests five different ways of learning from loss while preserving V32 as the default policy.

### Most promising established signals

- exogenous regime state is highly predictive of V32 failure;
- near-term opponent liquidation is predictable from public state;
- rare large counterfactual mistakes exist;
- those mistakes require state-dependent gating;
- naive direct use of a good opponent forecast can still hurt gameplay.

### Current bottleneck

The limiting resource is not model sophistication. It is **independent causal data**.

The next major data-generation wave should create many more counterfactual branches across independent hard, safe, and seat-asymmetric seeds. The goal is to learn a residual-value function that remains positive under whole-seed validation.

Longer term, strategically distinct specialists can enter a policy population and support PSRO / double-oracle style best-response iteration.

---

# 🧠 Long-term vision

The target is not an agent that endlessly accumulates heuristics.

It is an agentic research system that can ask:

```text
Why did the champion lose?

Which earlier decisions had causal responsibility?

Was the failure familiar or surprising?

What alternative would have helped?

Will this situation recur?

How certain are we that the lesson transfers?

Should the lesson remain episodic,
or is there enough evidence to consolidate it into the global policy?
```

That creates a natural progression:

```text
strong habit
    +
fast memory for exceptions
    +
slow learning across repeated experience
    +
opponent forecasting
    +
uncertainty-aware arbitration
    +
population-level robustness
```

The ambition is to turn each loss into **structured information that makes the next generation harder to exploit**.

---

# Local development

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
```

Run the agentic evolution CLI:

```bash
python scripts/run_agentic_evolution.py --help
```

Run tests:

```bash
pytest -q tests/test_agentic_evolution.py
```

---

## Reproducibility and safety

- version experiments by engine era;
- preserve exact champion artifacts and SHA-256 hashes;
- never train on stale mechanics without explicit tagging;
- never include private replay labels as runtime features;
- never commit Kaggle credentials;
- keep deterministic fallback operational;
- keep development, holdout, hard-seed, and confirmation sets separate;
- treat community claims as hypotheses until reproduced;
- record infrastructure failures separately from strategy failures.

## Disclaimer

This repository is designed to maximize the chance of producing a strong Kaggriculture submission through disciplined engineering, causal experimentation, and empirical iteration. The neuroscience language describes computational inspiration and research organization, not biological equivalence. No strategy can honestly guarantee first place against an evolving live population before it is tested there.