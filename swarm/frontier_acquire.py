from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tarfile
from typing import Any


EXPECTED_V32_ARCHIVE_SHA256 = "ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811"

# Public notebook outputs used by the historical Kaggriculture research stack.
# Acquisition is evidence only: historical leaderboard priors are intentionally
# not encoded here because they can become stale.
PUBLIC_SPECS: dict[str, dict[str, Any]] = {
    "v32": {
        "handle": "sidharthhulyalkar21/kaggri-v32-production-compiler",
        "archive_names": ("SUBMIT_V32_RUNTIME_VERIFIED.tar.gz", "SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz"),
        "required_sha256": EXPECTED_V32_ARCHIVE_SHA256,
    },
    "strict": {
        "handle": "kaitofukami/25-27-strict-future-v27-midgame-meta-reset",
    },
    "barnyard": {
        "handle": "romanrozen/strong-barnyard-economist",
    },
    "weedslip": {
        "handle": "kaitofukami/159-160-vs-frontier-v20-weed-slip-recovery",
    },
    "moon": {
        "handle": "prvsiyan/kaggriculture-frontier-the-moon-counts-melons",
    },
    "soil": {
        "handle": "prvsiyan/kaggriculture-frontier-the-soil-remembers-rain",
    },
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(archive: Path, destination: Path) -> Path:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    mains: list[Path] = []
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or not member.isfile():
                continue
            source = tf.extractfile(member)
            if source is None:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
            if relative.name == "main.py":
                mains.append(target)
    if not mains:
        raise RuntimeError(f"archive contains no main.py: {archive}")
    mains.sort(key=lambda path: (len(path.relative_to(destination).parts), str(path)))
    root_main = destination / "main.py"
    if mains[0] != root_main:
        shutil.copy2(mains[0], root_main)
    return root_main


def _copy_agent_tree(main: Path, destination: Path) -> Path:
    source_root = main.parent
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    for path in source_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        target = destination / path.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    if not (destination / "main.py").exists():
        raise RuntimeError(f"copied public output has no root main.py: {source_root}")
    return destination / "main.py"


def _find_named_archive(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        hits = sorted(root.rglob(name), key=lambda path: (len(path.parts), str(path)))
        if hits:
            return hits[0]
    return None


def _materialize_public_agent(key: str, downloaded: Path, destination: Path) -> tuple[Path, str, str | None]:
    spec = PUBLIC_SPECS[key]
    names = tuple(spec.get("archive_names", ()))
    if names:
        archive = _find_named_archive(downloaded, names)
        if archive is None:
            raise FileNotFoundError(f"{key}: expected archive not found in {downloaded}")
        archive_sha = _sha256(archive)
        expected = spec.get("required_sha256")
        if expected and archive_sha != expected:
            raise RuntimeError(f"{key}: archive SHA mismatch: expected {expected}, got {archive_sha}")
        _safe_extract(archive, destination)
        return destination, str(archive), archive_sha

    tar_candidates = sorted(
        list(downloaded.rglob("submission.tar.gz")) + list(downloaded.rglob("*.tar.gz")),
        key=lambda path: (0 if path.name == "submission.tar.gz" else 1, len(path.parts), str(path)),
    )
    seen: set[Path] = set()
    for archive in tar_candidates:
        if archive in seen:
            continue
        seen.add(archive)
        try:
            _safe_extract(archive, destination)
            return destination, str(archive), _sha256(archive)
        except Exception:
            continue

    mains = sorted(downloaded.rglob("main.py"), key=lambda path: (len(path.parts), str(path)))
    if not mains:
        raise FileNotFoundError(f"{key}: no submission archive or main.py found in {downloaded}")
    _copy_agent_tree(mains[0], destination)
    return destination, str(mains[0].parent), None


def acquire_frontier(*, output_root: str | Path, keys: list[str] | None = None) -> dict[str, Any]:
    root = Path(output_root).resolve()
    downloads = root / "downloads"
    agents = root / "agents"
    downloads.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)
    selected = keys or list(PUBLIC_SPECS)

    try:
        import kagglehub
    except Exception as exc:  # pragma: no cover - exercised in live runner
        raise RuntimeError("kagglehub is required for frontier acquisition") from exc

    rows: dict[str, dict[str, Any]] = {}
    for key in selected:
        if key not in PUBLIC_SPECS:
            rows[key] = {"status": "unknown_spec"}
            continue
        spec = PUBLIC_SPECS[key]
        handle = str(spec["handle"])
        download_dir = downloads / key
        shutil.rmtree(download_dir, ignore_errors=True)
        download_dir.mkdir(parents=True, exist_ok=True)
        try:
            got = kagglehub.notebook_output_download(handle, output_dir=str(download_dir))
            downloaded = Path(got) if got else download_dir
            if not downloaded.exists():
                downloaded = download_dir
            destination = agents / key
            agent_root, source, archive_sha = _materialize_public_agent(key, downloaded, destination)
            row = {
                "status": "ready",
                "handle": handle,
                "agent_root": str(agent_root),
                "main_path": str(agent_root / "main.py"),
                "source": source,
            }
            if archive_sha:
                row["archive_sha256"] = archive_sha
            rows[key] = row
        except Exception as exc:
            rows[key] = {
                "status": "failed",
                "handle": handle,
                "error": f"{type(exc).__name__}: {exc}"[:1200],
            }

    v32 = rows.get("v32", {})
    public_ready = [key for key, row in rows.items() if key != "v32" and row.get("status") == "ready"]
    result = {
        "scope": "verified_v32_public_frontier" if v32.get("status") == "ready" else "public_frontier_without_verified_v32",
        "verified_v32": v32.get("status") == "ready",
        "expected_v32_archive_sha256": EXPECTED_V32_ARCHIVE_SHA256,
        "ready_public_families": public_ready,
        "resources": rows,
    }
    (root / "FRONTIER_ACQUISITION.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire reproducible public Kaggriculture frontier agents")
    parser.add_argument("--output-root", default="swarm/runs/frontier")
    parser.add_argument("--keys", nargs="*", default=None)
    parser.add_argument("--require-v32", action="store_true")
    args = parser.parse_args()
    result = acquire_frontier(output_root=args.output_root, keys=args.keys)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_v32 and not result["verified_v32"]:
        raise SystemExit(7)


if __name__ == "__main__":
    main()
