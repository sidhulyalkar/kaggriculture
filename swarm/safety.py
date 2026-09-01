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

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
}


@dataclass(frozen=True)
class StaticCheck:
    ok: bool
    errors: tuple[str, ...]


def check_source(source: str) -> StaticCheck:
    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return StaticCheck(False, (f"syntax error: {exc}",))

    has_agent = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
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
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            errors.append(f"forbidden dynamic call: {node.func.id}")

    if not has_agent:
        errors.append("missing def agent(...)")
    return StaticCheck(not errors, tuple(errors))


def check_file(path: str | Path) -> StaticCheck:
    return check_source(Path(path).read_text(encoding="utf-8"))
