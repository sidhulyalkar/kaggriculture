from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from .models import CandidateRecord, ExperimentClaim


MAIN_PY_RE = re.compile(
    r"(?is)#+\s*MAIN_PY[^\n]*\n\s*```(?:python|py)?\s*\n?(.*?)```"
)


def extract_main_py(response: str) -> str:
    match = MAIN_PY_RE.search(response)
    if not match:
        raise ValueError("Builder response did not contain ## MAIN_PY with a Python code block")
    source = match.group(1).strip() + "\n"
    if "def agent(" not in source and "agent =" not in source:
        raise ValueError("Generated main.py does not define an agent callable")
    return source


def _copy_trusted_parent(source_root: Path, candidate_dir: Path) -> None:
    if not source_root.is_dir():
        return
    for path in source_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(source_root)
        target = candidate_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _tree_hash(root: Path) -> str:
    digest = sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def materialize_candidate(
    *,
    response: str,
    claim: ExperimentClaim,
    role: str,
    lane: str,
    parent_policy: str,
    output_root: str | Path,
    architecture_tags: tuple[str, ...] = (),
    mechanism_tags: tuple[str, ...] = (),
    trusted_parent_root: str | Path | None = None,
) -> CandidateRecord:
    source = extract_main_py(response)
    candidate_id = f"cand-{uuid4().hex[:12]}"
    candidate_dir = Path(output_root) / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=False)
    if trusted_parent_root is not None:
        _copy_trusted_parent(Path(trusted_parent_root), candidate_dir)
    path = candidate_dir / "main.py"
    path.write_text(source, encoding="utf-8")
    digest = _tree_hash(candidate_dir)
    return CandidateRecord(
        candidate_id=candidate_id,
        claim_id=claim.claim_id,
        role=role,
        lane=lane,
        parent_policy=parent_policy,
        source_path=str(path),
        source_hash=digest,
        architecture_tags=architecture_tags,
        mechanism_tags=mechanism_tags,
    )


def candidate_build_prompt(
    *,
    claim: ExperimentClaim,
    packet_text: str,
    build_contract: str,
    trusted_parent_available: bool = False,
) -> str:
    claim_data: dict[str, Any] = claim.to_dict()
    claim_data.pop("raw_response", None)
    packaging = (
        "\n\n# CANDIDATE PACKAGING MODE\n"
        + (
            "TRUSTED_PARENT_WRAPPER: the exact supplied current-control directory will be copied beside generated main.py. "
            "You MAY import its local modules from main.py. Prefer a narrow wrapper around the trusted parent rather than reconstructing it. "
            "Only generated main.py is untrusted/mutable; copied parent files are preserved byte-for-byte.\n"
            if trusted_parent_available
            else "BLANK_SHEET_SINGLE_FILE: no sibling parent files will be copied. main.py must be self-contained.\n"
        )
    )
    return (
        build_contract
        + "\n\n# FROZEN RESEARCH CLAIM\n"
        + "\n".join(f"{key}: {value}" for key, value in claim_data.items())
        + packaging
        + "\n# ALLOWED IMPLEMENTATION CONTEXT\n"
        + packet_text
    )
