from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "httpx",
    "socket",
    "subprocess",
    "multiprocessing",
    "openai",
    "anthropic",
}

ALWAYS_FORBIDDEN_CALLS = {"eval", "__import__"}


@dataclass(frozen=True)
class StaticCheck:
    ok: bool
    errors: tuple[str, ...]


def _string_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def _resolve_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _embedded_payload(node: ast.Call, constants: dict[str, str]) -> str | None:
    """Return statically recoverable code executed by exec/compile, otherwise None."""
    if not isinstance(node.func, ast.Name) or not node.args:
        return None
    if node.func.id == "compile":
        return _resolve_string(node.args[0], constants)
    if node.func.id != "exec":
        return None
    payload = node.args[0]
    direct = _resolve_string(payload, constants)
    if direct is not None:
        return direct
    if isinstance(payload, ast.Call) and isinstance(payload.func, ast.Name) and payload.func.id == "compile":
        return _embedded_payload(payload, constants)
    return None


def check_source(source: str, *, require_agent: bool = True, _depth: int = 0) -> StaticCheck:
    """Static quarantine for generated submissions.

    Dynamic execution is accepted only when its payload is statically recoverable as a
    literal/module-level string and that embedded source recursively passes this same
    safety check. This supports V44-style protected-parent embedding while rejecting
    arbitrary runtime-generated `exec`, `eval`, dynamic imports, network clients, and
    subprocess launchers.
    """
    if _depth > 4:
        return StaticCheck(False, ("embedded dynamic-code nesting exceeds safety limit",))

    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return StaticCheck(False, (f"syntax error: {exc}",))

    constants = _string_constants(tree)
    has_agent = False
    validated_embedded: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif node.module:
                names = [node.module]
            for name in names:
                root = name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    errors.append(f"forbidden import: {name}")

        if isinstance(node, ast.FunctionDef) and node.name == "agent":
            has_agent = True

        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        call_name = node.func.id
        if call_name in ALWAYS_FORBIDDEN_CALLS:
            errors.append(f"forbidden dynamic call: {call_name}")
            continue
        if call_name not in {"exec", "compile"}:
            continue

        payload = _embedded_payload(node, constants)
        if payload is None:
            errors.append(f"non-static dynamic call: {call_name}")
            continue
        if payload in validated_embedded:
            continue
        nested = check_source(payload, require_agent=False, _depth=_depth + 1)
        if not nested.ok:
            errors.extend(f"embedded {call_name}: {error}" for error in nested.errors)
        validated_embedded.add(payload)

    if require_agent and not has_agent:
        errors.append("missing def agent(...)")
    return StaticCheck(not errors, tuple(dict.fromkeys(errors)))


def check_file(path: str | Path) -> StaticCheck:
    return check_source(Path(path).read_text(encoding="utf-8"))
