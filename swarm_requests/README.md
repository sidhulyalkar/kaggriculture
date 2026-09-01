# Live swarm requests

`ACTIVE.json` is the only request file watched by the NVIDIA live workflow on `agent/v45-autonomous-swarm-lab`.

The file must never contain credentials. GitHub Actions injects `NVIDIA_API_KEY` from repository secrets.

Supported modes:

- `probe`: call each distinct NVIDIA model configured in `swarm/config/nvidia_live.yaml` with a tiny connectivity prompt and upload the evidence.
- `epoch`: run one live research/build/evaluation/council round.
- `campaign`: run 1-5 autonomous rounds with screen-only feedback between rounds.

A competitive request may pin `champion_sha256`; the workflow computes a deterministic tree hash and refuses to execute when it differs. Until the true leaderboard champion artifact is present, `submission/` may be used only as a labeled repo-local control.
