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


def _literal_matches(node: ast.AST, trusted_source: str | None) -> bool:
    return bool(trusted_source) and isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == trusted_source


def _trusted_compile(node: ast.Call, trusted_source: str | None) -> bool:
    return (
        isinstance(node.func, ast.Name)
        and node.func.id == "compile"
        and bool(node.args)
        and _literal_matches(node.args[0], trusted_source)
    )


def _trusted_exec(node: ast.Call, trusted_source: str | None) -> bool:
    if not (isinstance(node.func, ast.Name) and node.func.id == "exec" and node.args):
        return False
    payload = node.args[0]
    if _literal_matches(payload, trusted_source):
        return True
    return isinstance(payload, ast.Call) and _trusted_compile(payload, trusted_source)


def check_source(source: str, *, trusted_source: str | None = None) -> StaticCheck:
    """Reject dangerous generated code while permitting exact champion embedding.

    `exec`/`compile` remain forbidden unless the executed literal is byte-for-byte the
    trusted champion source supplied by the orchestrator. This supports V44-style
    protected-parent wrappers without granting generated code a general dynamic-code
    escape hatch.
    """
    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return StaticCheck(False, (f"syntax error: {exc}",))

    has_agent = False
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
        elif call_name == "exec" and not _trusted_exec(node, trusted_source):
            errors.append("forbidden dynamic call: exec")
        elif call_name == "compile" and not _trusted_compile(node, trusted_source):
            errors.append("forbidden dynamic call: compile")

    if not has_agent:
        errors.append("missing def agent(...)")
    return StaticCheck(not errors, tuple(dict.fromkeys(errors)))


def check_file(path: str | Path, *, trusted_source: str | None = None) -> StaticCheck:
    return check_source(Path(path).read_text(encoding="utf-8"), trusted_source=trusted_source)
