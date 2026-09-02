from __future__ import annotations

from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from .promotion import behavioral_distance


def source_hash(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def code_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def is_code_duplicate(candidate_source: str, population_sources: Iterable[str], threshold: float) -> bool:
    return any(code_similarity(candidate_source, source) >= threshold for source in population_sources)


def novelty_score(fingerprint: Iterable[float], population: Iterable[Iterable[float]]) -> float:
    distances = [behavioral_distance(fingerprint, other) for other in population]
    return min(distances) if distances else 1.0
