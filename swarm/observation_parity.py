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


def _agent_observation_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = list(node.args.posonlyargs) + list(node.args.args)
    if not args:
        raise ValueError("top-level agent has no observation argument")
    return str(args[0].arg)


def inject_parity_shim(source: str) -> str:
    """Inject a canonical-clock call into the real top-level ``agent`` function.

    Historical public agents use unusual indentation and occasionally multi-line
    function signatures.  The injector therefore uses the AST for both the first
    body statement and the observation-argument name instead of assuming four
    spaces or inserting immediately after the textual ``def`` line.
    """
    tree = ast.parse(source)
    agents = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "agent"
    ]
    if len(agents) != 1:
        raise ValueError(f"expected exactly one top-level agent, found {len(agents)}")
    node = agents[0]
    if not node.body:
        raise ValueError("top-level agent has an empty body")

    obs_name = _agent_observation_name(node)
    body_line = int(node.body[0].lineno) - 1
    body_indent = " " * int(node.body[0].col_offset)
    call = f"{body_indent}_v49_normalize_observation_step({obs_name})\n"
    helper_line = int(node.lineno) - 1

    lines = source.splitlines(keepends=True)
    # Insert from bottom to top so original AST line numbers remain valid.
    lines.insert(body_line, call)
    lines.insert(helper_line, _SHIM + "\n")
    out = "".join(lines)
    compile(out, "<v49-parity-source>", "exec")
    return out
