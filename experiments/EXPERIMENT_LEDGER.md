# Kaggriculture Experiment Ledger

Last updated: 2026-08-18

This is the canonical evidence chain for competition research. It records valid negative results, infrastructure failures, learned-model validation, promotion decisions, and the reason for each next experiment.

## Status vocabulary

- **CHAMPION**: current control. Never replace without promotion evidence.
- **PROMOTED**: passed offline promotion and is eligible for live confirmation.
- **RESEARCH PASS**: mechanism is supported, but no live submission is justified yet.
- **REJECTED**: experiment was valid and candidate failed promotion.
- **INFRA INVALID**: experiment failed to measure the intended strategy.
- **INCONCLUSIVE**: insufficient activation, independent groups, or confirmation evidence.

## Current champion

### V32 Premium-First

- **Status:** CHAMPION
- **Artifact:** `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- **SHA-256:** `ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811`
- **Historical offline evidence:** 40-agent held-out zoo, robust paired delta `+0.0255`, Soil delta `+0.3828`, zero invalid games.
- **Policy rule:** future live candidates must wrap the exact V32 artifact or separately prove that replacing the backbone is superior.

---

# Historical lessons

## V33 opponent-switch / supply-shock experiment

- **Status:** REJECTED
- Opponent identification itself was strong on the measured holdout, but the selected broad counter-policy was economically wrong.
- Robust delta: `-0.16468`.
- Adaptive-lineage delta: `-0.41667`.
- Permanent lesson: classification can gate a sparse residual, but should not automatically switch the entire farm plan.

## V34 market timing

- **Status:** RESEARCH ONLY
- Narrow market-timing variants did not produce sufficient promotion evidence.
- Permanent lesson: market timing is a secondary lever unless it is tied to a reliable causal state signal.

## V35 market microstructure

- **Status:** REJECTED
- Several source-level variants produced action/outcome behavior effectively identical to V32.
- Permanent lesson: every experiment must count actual intervention activations and preferably hash action traces.

## V36 production frontier

- **Status:** INFRA INVALID
- Non-V32 candidates failed before gameplay because dynamically loaded modules were executed without being inserted into `sys.modules`, which broke dataclass initialization under Python 3.12.
- Permanent loader invariant: register the module in `sys.modules` before `exec_module`.
- V36 did **not** falsify its production hypotheses.

---

# Wave 18

## 18A Exact-Anchor Residual Tournament

- **Status:** REJECTED
- No-op exact V32 parity passed.
- Unconditional wheat/capital residuals were negative or inactive.
- `WHEAT_BUY_EMERGENCY`: robust delta about `-0.175`, direct V32 score `0.25`.
- `WHEAT_HOLD_3X`: robust delta about `-0.575`, target delta about `-0.25`, direct V32 score `0.00`.
- Permanent lesson: broad residuals need state-dependent gates.

## 18B Single-Decision Counterfactual Surgeon

- **Status:** RESEARCH PASS, underpowered for deployment
- Baseline target games: `32`.
- Baseline losses: `20`.
- Activated branches: `600`.
- Positive branches: `52 / 600`.
- Loss-to-win flips: `0`.
- Rare HIRE and strawberry-seed changes produced gains of several thousand dollars, including observations above `+$10k`, but their unconditional means were negative.
- Initial conclusion: learn the state gate, not the intervention identity.

## 18C Opponent Ledger + Forecast

- **Status:** RESEARCH PASS
- Rows: `60,396`.
- Trajectories: `84`.
- Families: `7`.
- Held-out-seed mean hidden-shed R2: about `0.933`.
- Mean 12-turn sale AUC: about `0.995`.
- Mean 24-turn sale AUC: about `0.997`.
- Permanent lesson: visible state contains powerful information about near-future opponent economic behavior.

## 18D Meta Counterexample Matrix

- **Status:** RESEARCH PASS / seed warning
- On a small fresh seed slice, V32 scored `0.75` against the target set and `1.00` against the guards.
- This contradicted earlier slices where Adaptive/Ranker dominated V32.
- Permanent lesson: matchup estimates are highly seed/regime dependent. Small arbitrary seed panels are not promotion-quality evidence.

---

# Wave 19

## 19A FarmLedger leave-one-family-out

- **Status:** RESEARCH PASS
- Rows: `60,396`.
- Families: `7`.
- Median linear 4-turn sale AUC: `0.87020`.
- Median linear 12-turn sale AUC: `0.90872`.
- Median ExtraTrees 12-turn sale AUC: `0.99587`.
- Worst held-family mean linear AUC: `0.88249`.
- `ledger_generalizes = true`.
- Strong runtime-compatible generalization is concentrated in MELON, MILK, and STRAWBERRY sales. Short-horizon WHEAT and WOOL are less universal.
- Decision: opponent forecasts are valid **context**, but must still prove causal gameplay value.

## 19B Ledger front-run / market-MPC tournament

- **Status:** REJECTED
- Embedded linear forecast held-seed AUCs: Strawberry `0.8380`, Melon `0.9687`, Milk `0.8355`, Wool `0.7569`.
- `FRONT_Q2_990`: 215 interventions, robust delta `-0.0078125`, target delta `0`, target margin delta `+7.5625`, direct V32 score `0.4375`, cash ratio `0.99990`.
- `FRONT_Q4_990`: 149 interventions, robust delta `-0.0078125`, target delta `0`, target margin delta `+1.8125`, direct V32 score `0.4375`, cash ratio `0.99986`.
- Decision: **DO NOT SUBMIT**.
- Permanent lesson: predicting an opponent sale does not imply that front-running it is profitable.

## 19D Seed-Regime Stress Lab

- **Status:** RESEARCH PASS, permanent infrastructure
- Games: `640`.
- Independent seeds: `64`.
- Hard-game grouped prediction AUC in notebook: `0.91713`.
- V32 target weakness over the large panel was confirmed:
  - Adaptive seat 0 score `0.21875`.
  - Adaptive seat 1 score `0.265625`.
  - Ranker seat 0 score `0.21875`.
  - Ranker seat 1 score `0.25`.
- Guard performance remained very strong.
- Output: fixed `hard_seeds`, `safe_control_seeds`, and `seat_asymmetry_seeds`.
- Permanent rule: all future promotion runs must include the fixed stress suite and both seats.

---

# Wave 20 sandbox validation: Loss-Driven Evolution Framework

## Framework validation

- **Status:** RESEARCH PASS as infrastructure
- Unit/integration tests: `7 passed` in the sandbox.
- Real-data inputs: Wave 18B, 19A, 19B, and 19D send-back artifacts.

### Regime model

Whole-seed grouped OOF on the 640-game 19D panel:

- AUC: `0.92096`.
- Brier: `0.09407`.
- Base loss rate: `0.32813`.
- Top-quartile predicted-risk loss rate: `0.80625`.
- Lift: `2.457x`.

**Decision:** PASS. Champion failure is strongly regime-predictable.

### Forecast generalization filter

Linear LOFO median sale AUC: `0.91248`.

Default runtime-eligible targets require median AUC >= `0.85` and worst held-family AUC >= `0.80`.

Eligible:

- `sell4_MELON`, `sell4_MILK`, `sell4_STRAWBERRY`
- `sell12_MELON`, `sell12_MILK`, `sell12_STRAWBERRY`
- `sell24_MELON`, `sell24_MILK`, `sell24_STRAWBERRY`, `sell24_WHEAT`

Rejected as universal signals:

- short-horizon WHEAT
- all tested WOOL horizons

**Decision:** PASS as context only.

### Regret learner under corrected validation

A critical correction was discovered. Grouping by `seed + opponent` allowed the same seed regime to appear in different folds via another opponent. Validation is now by **whole seed only**.

Under the corrected boundary:

- branches: `600`.
- independent loss seeds: only `5`.
- benefit AUC: `0.89444`.
- mean-delta MAE: about `$3,835.85`.
- tree q10 coverage: `0.69`.
- tree q90 coverage: `0.625`.
- no conservative gate with at least 8 selected events has positive out-of-fold realized mean value.

**Decision:** NOT READY FOR RUNTIME. The current regret dataset is underpowered at the independent-seed level.

This supersedes the earlier optimistic interpretation of the 18B regret gate. Model AUC is not enough; the induced policy must have positive seed-held-out realized EV.

### Promotion replay

The new promotion contract independently rejects both Wave 19B candidates for negative robust delta, direct V32 score below `0.50`, and missing fixed hard/safe-suite evidence.

**Decision:** keep V32 as champion.

### Population / PSRO

The Wave 19B front-run variants have essentially redundant payoff profiles and do not supply a useful specialist for a robust population mixture.

**Decision:** do not randomize among near-clones. Generate strategically distinct specialists first.

---

# Wave 20 next experiment

## Counterfactual Factory on fixed regimes

- **Status:** NEXT
- Generate a new counterfactual dataset on 19D hard, safe-control, and seat-asymmetry seeds.
- Record complete runtime-visible state at each branch.
- Use at least 12 independent seeds in each development/validation partition.
- Prioritize HIRE, strawberry-seed, land timing, wheat procurement/reserve, and only forecast targets that pass LOFO reliability.
- Evaluate all regret models by whole seed.
- Require a positive conservative out-of-fold intervention policy before building a runtime residual.

## Promotion sequence for any survivor

1. exact V32 parity
2. activation count
3. ordinary fresh seeds
4. fixed hard seeds
5. fixed safe-control seeds
6. seat-asymmetry suite
7. broad guard zoo
8. direct V32
9. independent confirmation
10. official Kaggle runtime before and after repacking
11. live leaderboard confirmation

The leaderboard remains a confirmation environment, never a training signal.
