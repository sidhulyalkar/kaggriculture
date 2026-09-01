# Swarm configuration contract

`default.yaml` is the human-readable research policy for an epoch. The Python runner normalizes it into an immutable epoch manifest before any model is called.

## Required invariants

- Role counts must be positive integers.
- Research-lane budget fractions must sum to 1.0, excluding the audit lane.
- Held-out seeds may not overlap screen seeds.
- A sealed held-out evaluation can never be included in worker packets.
- `preserve_champion: true` means no generated candidate can replace the champion without a promotion record.
- Provider credentials are read from environment variables only and are never serialized into registries or packets.

## Provider environment

- OpenAI-compatible providers: `OPENAI_API_KEY`
- NVIDIA NIM: `NVIDIA_API_KEY`

The provider layer also supports a manual/offline mode so packets can be exported for models that are not exposed through an API.
