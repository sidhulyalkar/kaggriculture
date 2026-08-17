from __future__ import annotations

"""Kaggle input discovery helpers.

Kaggle notebook mounts are not guaranteed to be one directory below
``/kaggle/input``.  Current UI mounts can look like
``/kaggle/input/datasets/<owner>/<slug>``.  Research notebooks should locate
inputs by file signatures rather than hard-coded slugs.
"""

from pathlib import Path
from typing import Iterable


def _files(root: str | Path, name: str) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob(name) if p.is_file())


def roots_with_files(root: str | Path, required: Iterable[str]) -> list[Path]:
    """Return directories containing every required filename.

    We anchor on the rarest first filename and test siblings, which is much
    cheaper than recursively examining every directory.
    """
    names = list(required)
    if not names:
        return []
    candidates = []
    for p in _files(root, names[0]):
        parent = p.parent
        if all((parent / n).exists() for n in names[1:]):
            candidates.append(parent)
    return sorted(set(candidates))


def find_official_episode_index(root: str | Path = "/kaggle/input") -> Path | None:
    """Locate the official Kaggriculture Episodes Index dataset.

    The official dataset currently exposes ``manifest.csv``.  Prefer paths
    whose full name also mentions kaggriculture/episode, but retain a unique
    manifest fallback for forward compatibility.
    """
    hits = _files(root, "manifest.csv")
    preferred = [p.parent for p in hits if "kaggriculture" in str(p).lower() and "episode" in str(p).lower()]
    if preferred:
        return preferred[0]
    return hits[0].parent if len(hits) == 1 else None


def find_public_episode_bundle(root: str | Path = "/kaggle/input") -> Path | None:
    """Locate a pre-packed public replay corpus.

    Georgy Mamarin's public Kaggriculture Episodes dataset is identified by the
    stable sibling signature ``episodes.csv`` + ``replays.parquet``.  The code
    intentionally does not depend on the dataset owner/slug.
    """
    roots = roots_with_files(root, ["episodes.csv", "replays.parquet"])
    preferred = [p for p in roots if "kaggriculture" in str(p).lower()]
    return (preferred or roots or [None])[0]


def find_code_repo(root: str | Path = "/kaggle/input") -> Path | None:
    hits = _files(root, "__init__.py")
    for p in hits:
        if p.parent.name == "kagv2" and p.parent.parent.name == "src":
            return p.parents[2]
    return None


def describe_inputs(root: str | Path = "/kaggle/input") -> dict[str, str | None]:
    idx = find_official_episode_index(root)
    bundle = find_public_episode_bundle(root)
    repo = find_code_repo(root)
    return {
        "official_episode_index": str(idx) if idx else None,
        "public_episode_bundle": str(bundle) if bundle else None,
        "code_repo": str(repo) if repo else None,
    }
