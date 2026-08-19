# Kaggriculture Experiment Ledger

Last updated: 2026-08-18

This is the durable record of competition experiments. The goal is to preserve not only what won, but why each idea was tested, what evidence it produced, whether the experiment itself was valid, and what the result implies for the next research step.

## Status vocabulary

- **CHAMPION**: current live control; do not replace without promotion evidence.
- **PROMOTED**: passed offline promotion and is eligible for a live confirmation.
- **RESEARCH PASS**: mechanism is supported, but no submission is yet justified.
- **REJECTED**: valid experiment; candidate did not clear its promotion gate.
- **INFRA INVALID**: experiment did not measure the intended strategy because infrastructure failed.
- **INCONCLUSIVE**: insufficient activation, sample size, or contradictory evidence.

## Current control

### V32 Premium-First / production anchor

- **Status:** CHAMPION
- **Runtime artifact:** `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- **Artifact SHA-256:** `ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`
- **Offline evidence:** 40-agent held-out zoo; robust paired delta `+0.0255`; Soil delta `+0.3828`; zero invalid games.
- **Live snapshot:** user-reported rating approximately `2030.5` and rank around `750` on 2026-08-18. Treat live rating as time-dependent rather than a stable model metric.
- **Rule:** all future live candidates must either wrap this exact artifact or explicitly prove that replacing the backbone is superior.

---

## Pre-Wave-18 lessons

### V33 supply-shock / opponent-switch experiment

- **Status:** REJECTED
- **Classifier:** strong diagnostic result. On the 3094 holdout, recall `1.0` and false-positive rate `0` were observed.
- **Strategy effect:** robust delta `-0.16468`; adaptive-lineage delta `-0.41667`; worst-family delta `0`; passive ratio `1.0`; zero invalid games.
- **Interpretation:** opponent recognition can be accurate while a wholesale counter-policy is still economically wrong.
- **Permanent lesson:** classification should gate small, causally supported residuals, not switch the entire farm plan.

### V34 market-timing lab

- **Status:** RESEARCH / not promoted
- **Purpose:** test narrow market-timing interventions while preserving V32 mechanics.
- **Disposition:** retained as a research branch; no live promotion was justified.

### V35 market-microstructure probes

- **Status:** REJECTED as a live improvement; useful diagnostic.
- **Candidates:** Shadow Priority, Slot Race, Front-Run Light.
- **Key result:** V35A matched V32 exactly in all evaluated terminal outcomes across the screen and held-out set. V35B was also outcome-identical in its evaluated games, and V35C was outcome-identical in the screen.
- **Interpretation:** changing source code is not evidence of a strategy change. Future experiments must record actual intervention activation counts and, where possible, action-trace hashes.
- **Permanent lesson:** market microstructure can only be promoted if the residual measurably fires and produces paired outcome changes.

### V36 production-frontier lab

- **Status:** INFRA INVALID
- **Original notebook decision:** `DO_NOT_SUBMIT_V36`.
- **Root cause discovered after send-back inspection:** every non-V32 production candidate was invalid in the targeted screen because the isolated Python 3.12 loader executed a dynamically imported module without first registering it in `sys.modules`. `@dataclass` initialization then failed before gameplay.
- **Interpretation:** V36 did **not** falsify the 12-hand, day-10 land, wheat-autarky, rolling-melon, or late-wheat hypotheses.
- **Permanent loader rule:** for dynamic imports use `sys.modules[module_name] = module` before `spec.loader.exec_module(module)`.

---

# Wave 18: exact-anchor and learning diagnostics

## 18A Exact-Anchor Residual Tournament

- **Status:** REJECTED
- **Experiment validity:** exact no-op wrapper parity passed before candidate evaluation.
- **Control:** exact V32 runtime artifact.
- **Notable candidate results:**
  - `HAND_CAP_12`, `LAND_DAY10`, and `HAND12_LAND10` produced zero action changes in the tested games and therefore supplied no evidence.
  - `WHEAT_BUY_EMERGENCY`: robust delta about `-0.175`, direct V32 score `0.25`.
  - `WHEAT_HOLD_3X`: robust delta about `-0.575`, Adaptive/Ranker delta about `-0.25`, direct V32 score `0.00`.
  - `WHEAT_AUTARKY`: robust delta about `-0.475`.
- **Decision:** no sparse unconditional residual survived the targeted screen.
- **Interpretation:** broad wheat or capital overrides are too dangerous without a state-dependent gate.

## 18B Single-Decision Counterfactual Surgeon

- **Status:** RESEARCH PASS
- **Baseline target games:** `32` V32-vs-Target games.
- **Baseline losses:** `20`.
- **Counterfactual branches:** `600`, with `600` activated branches.
- **Branches with positive final-margin delta:** `52 / 600`.
- **Loss-to-win flips:** `0`.
- **Stable but tiny pattern:** suppressing one wheat-seed purchase near step `262` was positive in `20 / 20` observed branches but only about `+$10` mean margin, too small for a live intervention.
- **Large conditional effects:** individual HIRE or strawberry-seed suppressions occasionally improved final margin by several thousand dollars, including observed effects above `+$10k`, while their unconditional average remained negative.
- **Interpretation:** high-value mistakes exist, but the action itself is not the rule. The research problem is to learn the state gate that separates rare large benefits from common large regressions.
- **Next action:** train grouped, seed/opponent-held-out regret models for HIRE and strawberry-seed suppression only.

## 18C Opponent Ledger + Forecast Lab

- **Status:** RESEARCH PASS, highest-priority mechanism from Wave 18.
- **Rows:** `60,396` turn-level observations.
- **Trajectories:** `84` complete games.
- **Opponent families:** `7`.
- **Split:** held-out whole seeds; adjacent turns from a trajectory were never randomly split.
- **Hidden-shed reconstruction:** mean R² approximately `0.933`.
- **Representative hidden-state R²:** wheat `0.973`, strawberry `0.896`, milk `0.925`, wool `0.922`.
- **Future-sale prediction:** mean 12-turn AUC approximately `0.995`; mean 24-turn AUC approximately `0.997`.
- **Representative 12-turn sale AUC:** wheat `0.989`, strawberry `0.996`, melon `~1.000`, milk `0.998`, wool `0.992`.
- **Caveat:** training and test contained the same policy families. Performance may partially reflect deterministic family/tape recognition.
- **Interpretation:** the visible game state contains enough information to infer hidden opponent economics extremely well on new seeds. This is the strongest novel mechanism currently observed.
- **Next action:** leave-one-policy-family-out validation, then convert prediction into a sparse exact-V32 market residual and measure causal gameplay value.

## 18D Meta Counterexample Matrix

- **Status:** RESEARCH PASS / seed-regime warning.
- **Games:** `336` valid games in the public-agent matrix.
- **V32:** target score `0.75`, target margin `+1,868.25`, guard score `1.00`, worst guard `1.00`, overall score `0.9167`, overall margin `+5,409.17` on this seed set.
- **Soil:** target score `0.75`, target margin `+1,861.63`, overall score `0.8333`.
- **Observation:** V32 and Soil daily trajectories were nearly identical across the traced target games; Soil differed mainly by about `-$11` terminal cash on days 28-29 in the observed comparison.
- **Ranker:** target score `0.75` within the matrix but much weaker guard robustness.
- **Important contradiction:** earlier Wave-18 slices showed V32 losing heavily to Adaptive/Ranker, while 18D showed V32 scoring `0.75` against both on different fresh seeds.
- **Interpretation:** Adaptive/Ranker are not universally dominant against V32. Losses are strongly seed/regime dependent. Future promotion tests need a fixed hard-seed suite rather than relying on a small arbitrary fresh-seed sample.
- **Next action:** map town-shop sequence, demand composition, weeds, seat, and early cash trajectory over a much larger seed panel and save the hardest regimes as a permanent stress suite.

---

# Wave 19 plan

## 19A FarmLedger leave-one-family-out

- **Question:** does FarmLedger generalize to completely unseen policy families?
- **Primary gates:** median unseen-family 4-turn sale AUC `>= 0.80`; median unseen-family 12-turn AUC `>= 0.85`; no systematic collapse to random across an entire held-out family.
- **Status:** queued.

## 19B Ledger front-run / market-MPC tournament

- **Question:** can an embedded lightweight opponent-sale forecast improve actual paired gameplay while retaining exact V32 farming behavior?
- **Candidate family:** tiny forecast-gated premium front-run quantities, forecast-aware ordering of already-planned sales, conservative hybrid.
- **Submission authority:** yes, but only if parity, forecast, activation, held-out, guard, direct-V32, and runtime gates all pass.
- **Status:** queued.

## 19C Regret-gated capital learner

- **Question:** can the rare high-value HIRE / strawberry-seed suppressions from 18B be predicted without triggering the common harmful cases?
- **Validation:** grouped by seed/opponent; lightweight classifier + expected-margin model; fresh broad gameplay evaluation.
- **Submission authority:** no. A passing candidate must survive a separate confirmation experiment first.
- **Status:** queued.

## 19D Seed-regime stress lab

- **Question:** which exogenous regimes create V32 losses, and how reproducible is difficulty across opponents and seats?
- **Output:** `hard_seed_suite.json` containing hard, safe-control, and seat-asymmetry seed sets.
- **Permanent use:** future promotion notebooks should run both ordinary held-out seeds and this adversarial suite.
- **Status:** queued.

---

# Promotion invariants learned so far

1. **Exact-anchor parity before residual research.** If a no-op wrapper does not hash to the same action trace and cash as V32, stop.
2. **Register dynamic modules in `sys.modules` before execution.** Python 3.12 dataclass imports otherwise invalidate experiments.
3. **Count actual intervention activations.** A source-code difference with zero activations is not evidence.
4. **Both seats, paired same-seed comparisons.** Never compare unpaired aggregates when a paired control is available.
5. **Separate development, held-out, confirmation, and hard-seed suites.** Do not tune against the final promotion set.
6. **Learned components require group validation.** Hold out entire seeds and, where applicable, entire opponent families.
7. **Optimize win probability and relative margin, not isolated farm cash.** Shared-market changes can help the opponent more than us.
8. **Leaderboard slots are confirmation experiments.** Never submit exact-byte clones or candidates that failed offline promotion.
9. **Preserve V32 by default.** Replace or override it only when a coherent subsystem has independently demonstrated positive causal value.
10. **Every live submission must be reproducible.** Record artifact SHA-256, source commit/branch, exact promotion evidence, runtime gate, and live result.