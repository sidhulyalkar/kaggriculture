from __future__ import annotations

import ast
from typing import Any


def _read(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def canonical_step(obs: Any, turns_per_day: int = 24) -> int:
    """Return a seat-invariant clock from fields Kaggriculture syncs to both players."""
    day = int(_read(obs, "day", 0) or 0)
    hour = int(_read(obs, "hour", 0) or 0)
    return day * int(turns_per_day) + hour


def normalize_observation_step(obs: Any, turns_per_day: int = 24) -> int:
    """Overwrite observation.step with the canonical day/hour clock and return it."""
    step = canonical_step(obs, turns_per_day)
    if isinstance(obs, dict):
        obs["step"] = step
    else:
        try:
            setattr(obs, "step", step)
        except Exception:
            pass
    return step


_SHIM = '''\ndef _v49_normalize_observation_step(obs):
    # Kaggriculture 1.32.7 does not reliably populate observation.step for every seat.
    # day/hour are synchronized by the environment, so derive the competition clock
    # before any legacy schedule, market overlay, or embedded expert sees obs.
    if isinstance(obs, dict):
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        step = day * 24 + hour
        obs["step"] = step
    else:
        day = int(getattr(obs, "day", 0) or 0)
        hour = int(getattr(obs, "hour", 0) or 0)
        step = day * 24 + hour
        try:
            obs.step = step
        except Exception:
            pass
    return step
'''


def inject_parity_shim(source: str) -> str:
    """Inject a canonical-clock call into the real top-level ``agent`` function.

    AST discovery deliberately ignores ``def agent`` text inside embedded source
    strings, which is common in the historical Soil/H6 lineage.
    """
    tree = ast.parse(source)
    agents = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "agent"]
    if len(agents) != 1:
        raise ValueError(f"expected exactly one top-level agent, found {len(agents)}")
    node = agents[0]
    lines = source.splitlines(keepends=True)
    insert_at = int(node.lineno)  # 1-based def line -> insert immediately after it.
    indent = " " * (int(node.col_offset) + 4)
    call = f"{indent}_v49_normalize_observation_step(obs)\n"
    # Helper goes immediately before the top-level entrypoint so all dependencies
    # above remain untouched and every downstream controller receives normalized obs.
    helper_at = int(node.lineno) - 1
    lines.insert(helper_at, _SHIM + "\n")
    # The helper insertion shifted the entrypoint by one list element, but the helper
    # itself is a multi-line string inside one element, so the original def is now at
    # index insert_at. Insert the call after that def element.
    lines.insert(insert_at + 1, call)
    out = "".join(lines)
    compile(out, "<v49-parity-source>", "exec")
    return out
