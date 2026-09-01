from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tarfile
from typing import Any

from .frontier_acquire import acquire_frontier


STRICT_MAIN_SHA256 = "f48c21166eac68d1b05a401f04f94a2eb6154e65415af64893672365ff33c7b8"
STRICT_ARCHIVE_SHA256 = "9a158d0b251d18d042386d33fb31a4f4096005637c80953162e329d2eb7ff072"

_OLD_CLOCK = 'step = min(max(0, int(_get(obs, "step", 0) or 0)), len(actions) - 1)'
_NEW_CLOCK = '''raw_step = _get(obs, "step", None)
        if raw_step is None:
            turns_per_day = int(_get(configuration, "turnsPerDay", 24) or 24)
            raw_step = int(_get(obs, "day", 0) or 0) * turns_per_day + int(_get(obs, "hour", 0) or 0)
        step = min(max(0, int(raw_step or 0)), len(actions) - 1)'''


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_clock_fix(*, output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    acquisition = acquire_frontier(output_root=root / "frontier", keys=["strict"])
    row = acquisition.get("resources", {}).get("strict", {})
    if row.get("status") != "ready":
        raise RuntimeError(f"Strict V4 acquisition failed: {row}")
    archive_sha = str(row.get("archive_sha256", ""))
    if archive_sha != STRICT_ARCHIVE_SHA256:
        raise RuntimeError(f"Strict archive provenance mismatch: {archive_sha}")

    parent_root = Path(str(row["agent_root"]))
    parent_main = parent_root / "main.py"
    parent_sha = _sha(parent_main)
    if parent_sha != STRICT_MAIN_SHA256:
        raise RuntimeError(f"Strict main.py provenance mismatch: {parent_sha}")

    source = parent_main.read_text(encoding="utf-8")
    count = source.count(_OLD_CLOCK)
    if count != 1:
        raise RuntimeError(f"Expected exactly one Strict clock expression, found {count}")

    candidate_root = root / "candidate"
    shutil.rmtree(candidate_root, ignore_errors=True)
    shutil.copytree(parent_root, candidate_root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    candidate_main = candidate_root / "main.py"
    candidate_source = source.replace(_OLD_CLOCK, _NEW_CLOCK, 1)
    candidate_main.write_text(candidate_source, encoding="utf-8")

    # Fail closed on anything except the intended clock replacement.
    restored = candidate_source.replace(_NEW_CLOCK, _OLD_CLOCK, 1)
    if restored != source:
        raise RuntimeError("Clock patch changed source outside the intended replacement")
    compile(candidate_source, str(candidate_main), "exec")

    archive = root / "submission" / "NEXT_SUBMIT_STRICT_V4_CLOCK_RECOVERY.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tf:
        for path in sorted(candidate_root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                tf.add(path, arcname=path.relative_to(candidate_root).as_posix())

    result = {
        "parent": "Strict-Future V4",
        "published_parent_score": 3090.1,
        "parent_main_sha256": parent_sha,
        "parent_archive_sha256": archive_sha,
        "candidate_main_sha256": _sha(candidate_main),
        "candidate_archive_sha256": _sha(archive),
        "candidate_main": str(candidate_main),
        "archive": str(archive),
        "mutation": "recover missing obs.step from day * turnsPerDay + hour",
        "conditional_noop_when_step_present": True,
    }
    (root / "STRICT_CLOCK_FIX.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact Strict V4 clock-recovery candidate")
    parser.add_argument("--output-root", default="swarm/runs/strict-clock-fix")
    args = parser.parse_args()
    print(json.dumps(build_clock_fix(output_root=args.output_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
