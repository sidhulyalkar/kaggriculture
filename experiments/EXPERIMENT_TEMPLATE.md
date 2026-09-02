# Experiment Record Template

Copy this section into `EXPERIMENT_LEDGER.md` for every material experiment.

## <ID> <short name>

- **Date:** YYYY-MM-DD
- **Status:** QUEUED / RUNNING / RESEARCH PASS / PROMOTED / REJECTED / INFRA INVALID / INCONCLUSIVE
- **Hypothesis:** one falsifiable sentence.
- **Control:** exact artifact or commit.
- **Candidate change:** one coherent subsystem only.
- **Inputs:** public agents, replay set, model artifact, or other data.
- **Source branch/commit:** exact Git reference.
- **Notebook/script:** exact filename.
- **Seeds:** development / held-out / confirmation / hard-seed sets.
- **Seats:** both unless a diagnostic explicitly says otherwise.
- **Runtime environment:** Python version, CPU count, accelerator, Internet setting where relevant.

### Integrity checks

- [ ] dynamic imports registered in `sys.modules`
- [ ] exact-anchor parity if applicable
- [ ] candidate intervention activated at least once
- [ ] zero unexpected invalid games
- [ ] exact artifact hash recorded
- [ ] no tuning performed on confirmation set

### Primary result

- paired win delta:
- target-family delta:
- worst-family delta:
- direct-champion score:
- paired margin delta:
- own-cash ratio:
- activation count:
- latency:

### Learned-model result, if applicable

- grouping unit for validation:
- held-out actors/families:
- held-out seeds:
- metric(s):
- calibration / uncertainty note:

### Decision

State whether the hypothesis was supported and whether the candidate can advance.

### Interpretation

Record the causal lesson, including negative results and infrastructure failures.

### Next action

Specify exactly one next experiment or state that the branch is closed.

### Live confirmation, if submitted

- submission ID:
- archive SHA-256:
- ladder rating snapshots:
- episodes played:
- informative replay IDs:
- execution failures:
