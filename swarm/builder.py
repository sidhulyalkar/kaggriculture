from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
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
) -> CandidateRecord:
    source = extract_main_py(response)
    candidate_id = f"cand-{uuid4().hex[:12]}"
    candidate_dir = Path(output_root) / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=False)
    path = candidate_dir / "main.py"
    path.write_text(source, encoding="utf-8")
    digest = sha256(source.encode("utf-8")).hexdigest()
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


def candidate_build_prompt(*, claim: ExperimentClaim, packet_text: str, build_contract: str) -> str:
    claim_data: dict[str, Any] = claim.to_dict()
    claim_data.pop("raw_response", None)
    return (
        build_contract
        + "\n\n# FROZEN RESEARCH CLAIM\n"
        + "\n".join(f"{key}: {value}" for key, value in claim_data.items())
        + "\n\n# ALLOWED IMPLEMENTATION CONTEXT\n"
        + packet_text
    )
