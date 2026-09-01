from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for swarm YAML configs. Install project requirements or use a JSON config."
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at config root: {path}")
    return data


def load_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = _load_yaml(path)
    validate_config(data)
    return data


def validate_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    budget = config.get("budget", {})
    if not isinstance(budget, dict):
        errors.append("budget must be a mapping")
    else:
        total = sum(float(v) for v in budget.values())
        if abs(total - 1.0) > 1e-9:
            errors.append(f"research budget must sum to 1.0, got {total:.6f}")

    roles = config.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty list")
    else:
        for role in roles:
            if int(role.get("count", 0)) < 1:
                errors.append(f"role {role.get('id')} must have count >= 1")

    experiments = config.get("experiments", {})
    screen = set(experiments.get("screen", {}).get("seeds", []))
    heldout = set(experiments.get("heldout", {}).get("seeds", []))
    overlap = screen & heldout
    if overlap:
        errors.append(f"screen and held-out seeds overlap: {sorted(overlap)}")
    if experiments.get("heldout", {}).get("sealed") is not True:
        errors.append("heldout.sealed must be true")

    frontier = config.get("frontier", {})
    if frontier.get("preserve_champion") is not True:
        errors.append("frontier.preserve_champion must be true")

    if errors:
        raise ValueError("Invalid swarm config:\n- " + "\n- ".join(errors))
