from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResearchPacket:
    kind: str
    text: str
    files: tuple[str, ...]
    packet_hash: str


PACKET_FILES: dict[str, tuple[str, ...]] = {
    "blank_sheet": (
        "docs/ENGINE_CONTRACT.md",
        "docs/ARCHITECTURE.md",
        "baselines/v1/main.py",
        "docs/PUBLIC_APPROACHES_AND_STRATEGY.md",
    ),
    "champion_counter": (
        "docs/ENGINE_CONTRACT.md",
        "docs/V44_FRONTIER_MARGIN_ENGINE.md",
        "docs/PUBLIC_APPROACHES_AND_STRATEGY.md",
    ),
    "trace_mechanism": (
        "docs/ENGINE_CONTRACT.md",
        "docs/V44_FRONTIER_MARGIN_ENGINE.md",
        "docs/V3_FRONTIER_TRANSPLANT_RESULTS.md",
    ),
    "frontier_residual": (
        "docs/ENGINE_CONTRACT.md",
        "docs/V44_FRONTIER_MARGIN_ENGINE.md",
        "docs/EXPERIMENT_PROTOCOL.md",
    ),
    "open_exploration": (
        "docs/ENGINE_CONTRACT.md",
        "docs/ARCHITECTURE.md",
        "baselines/v1/main.py",
        "docs/PUBLIC_APPROACHES_AND_STRATEGY.md",
    ),
    "evidence_only": (
        "docs/EXPERIMENT_PROTOCOL.md",
        "docs/KAGGLE_RUNTIME_SUBMISSION_CONTRACT.md",
    ),
}

FORBIDDEN_PACKET_TOKENS = (
    "heldout.seeds",
    "sealed_seed",
    "sealed seeds",
)


def _read_optional(repo_root: Path, relative: str) -> str:
    path = repo_root / relative
    if not path.exists():
        return f"[MISSING {relative}]"
    return path.read_text(encoding="utf-8", errors="replace")


def build_packet(
    *,
    repo_root: str | Path,
    kind: str,
    public_context: dict[str, Any],
    extra_evidence: str = "",
) -> ResearchPacket:
    repo_root = Path(repo_root)
    files = PACKET_FILES.get(kind)
    if files is None:
        raise KeyError(f"Unknown packet kind {kind!r}")

    sections = [
        "# SWARM RESEARCH PACKET",
        f"packet_kind: {kind}",
        "",
        "## PUBLIC EPOCH CONTEXT",
        json.dumps(public_context, sort_keys=True, indent=2),
    ]
    for relative in files:
        sections.extend(("", f"## FILE: {relative}", _read_optional(repo_root, relative)))
    if extra_evidence.strip():
        sections.extend(("", "## ROLE-SPECIFIC EVIDENCE", extra_evidence.strip()))

    text = "\n".join(sections)
    lowered = text.lower()
    for token in FORBIDDEN_PACKET_TOKENS:
        if token.lower() in lowered:
            raise ValueError(f"Information firewall violation: packet contains forbidden token {token!r}")

    digest = sha256(text.encode("utf-8")).hexdigest()
    return ResearchPacket(kind=kind, text=text, files=files, packet_hash=digest)
