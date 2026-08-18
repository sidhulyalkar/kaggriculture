# Kaggle runtime submission contract

## Failure discovered on V32

The validated V32 Premium-First research policy failed hosted Kaggle validation before turn 1 because its root wrapper used `Path(__file__)`. Kaggle's Python agent loader compiles submitted source and executes it into an empty globals dictionary. It appends the submitted file's directory to `sys.path`, but does not define `__file__`.

This was a deployment failure, not a strategy/tournament failure.

## Production standard

All future promoted submissions must satisfy these gates before they are called submission-ready:

1. Prefer a single standalone Python file over a multi-file runtime wrapper.
2. Final source must not depend on `__file__` or runtime path discovery.
3. Final intended agent callable must be the last callable inserted into the execution globals, matching Kaggle's `get_last_callable` behavior.
4. Reproduce Kaggle loading locally with `compile(source, path, 'exec')`, `env = {}`, `exec(...)`, and last-callable selection.
5. When available, validate using `kaggle_environments.agent.get_last_callable` as a second loader gate.
6. Run at least one full local Kaggriculture smoke episode before emitting the production artifact.
7. Research-tournament validity and production-runtime validity are separate promotion gates. Both must pass.
8. For selectors/meta-agents, embed self-contained component sources into one final file rather than importing sibling agent files at runtime.

## V32 production path

The validated V32 strategy should be compiled from the original Soil parent source plus the stable Premium-First market-order overlay, producing a single Python file. The V32 tournament itself does not need to be rerun solely because of this packaging failure.
