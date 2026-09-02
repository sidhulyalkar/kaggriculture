# Wave 19 CPU Notebook Plan

All notebooks use **CPU / Internet ON**.

The notebooks are intentionally orthogonal. Run them in parallel when Kaggle capacity permits.

## 19A — FarmLedger leave-one-family-out

File: `19A_ledger_leave_one_family_out.ipynb`

### Required inputs

- `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- at least 6 public opponent families

### Recommended public families

- Adaptive
- Ranker
- Soil
- V16
- Melon
- Strict
- Findings
- 3094 if available

### Output

`19A_RESULTS_SEND_BACK.zip`

### Decision question

Does hidden-state / future-sale prediction generalize to a completely unseen policy family?

---

## 19B — Ledger front-run / market-MPC tournament

File: `19B_ledger_front_run_mpc_tournament.ipynb`

### Required inputs

- `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- at least 5 public families

### Output

`19B_RESULTS_SEND_BACK.zip`

Possible live output, only after all gates pass:

`SUBMIT_NEXT_LIVE_19B.tar.gz`

### Decision question

Can a learned 4-turn opponent-sale forecast create actual paired win value through tiny premium front-running or sale-order changes while preserving V32 farming behavior?

---

## 19C — Regret-gated capital learner

File: `19C_regret_gated_capital_learner.ipynb`

### Required inputs

- `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- Adaptive
- Ranker

### Recommended guards

- Soil
- V16
- Melon
- Strict
- Findings

### Output

`19C_RESULTS_SEND_BACK.zip`

### Decision question

Can we predict when the rare high-value HIRE or strawberry-seed suppressions from Wave 18B are actually beneficial?

This notebook never submits directly. A positive result requires a separate confirmation run.

---

## 19D — Seed-regime stress lab

File: `19D_seed_regime_stress_lab.ipynb`

### Required inputs

- `SUBMIT_V32_RUNTIME_VERIFIED.tar.gz`
- Adaptive
- Ranker

### Recommended

- Soil
- Findings
- V16

### Output

`19D_RESULTS_SEND_BACK.zip`

Important generated artifact:

`hard_seed_suite.json`

### Decision question

Which town-demand, weed, seat, and early-cash regimes systematically create V32 losses?

---

# Run order

If only one CPU notebook can be run, use this priority:

1. 19B
2. 19A
3. 19D
4. 19C

If four can run, launch all four simultaneously.

# Return protocol

Upload every `*_RESULTS_SEND_BACK.zip` even when the notebook rejects its hypothesis. Negative evidence updates the experiment ledger and prevents repeated dead ends.

Do not upload a live submission merely because a tar exists elsewhere in the working directory. Only the exact `SUBMIT_NEXT_LIVE_19B.tar.gz` produced after a positive 19B decision is authorized by this wave.