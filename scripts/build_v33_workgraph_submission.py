#!/usr/bin/env python3
"""Build the standalone V33 WorkGraph artifact on top of exact V32 bytes.

Production mode refuses to build unless the supplied V32 archive has the
runtime-verified champion SHA-256. This prevents a research fallback from being
mistaken for a V32-preserving candidate.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
V33 = ROOT / "submission" / "v33_workgraph_agent.py"
CHAMPION_TAR_SHA256 = "ad54a3f9bb94d3123997887da53e71ab69785d5d14ad0f53c51b7691e21d7811"
DEFAULT_PREFIX = "SUBMIT_V33_WORKGRAPH_EXACT_V32"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def last_callable(env: dict):
    xs = [(k, v) for k, v in env.items() if callable(v) and not k.startswith("__")]
    if not xs:
        raise RuntimeError("No callable found")
    return xs[-1]


def load_base_from_tar(path: Path) -> tuple[str, dict]:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if digest != CHAMPION_TAR_SHA256:
        raise RuntimeError(
            "Refusing production build: V32 archive SHA-256 does not match the "
            f"runtime-verified champion. expected={CHAMPION_TAR_SHA256} got={digest}"
        )
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        files = [m for m in tf.getmembers() if m.isfile()]
        if len(files) != 1 or files[0].name != "main.py":
            raise RuntimeError(f"Expected exact V32 archive to contain only root main.py, got {[m.name for m in files]}")
        f = tf.extractfile(files[0])
        if f is None:
            raise RuntimeError("Could not extract V32 main.py")
        source = f.read().decode("utf-8")
    return source, {
        "base_kind": "exact_v32_runtime_verified",
        "base_archive": str(path),
        "base_archive_sha256": digest,
        "base_verified_champion": True,
    }


def load_dev_base(path: Path) -> tuple[str, dict]:
    source = path.read_text(encoding="utf-8")
    return source, {
        "base_kind": "development_only_unverified",
        "base_source": str(path),
        "base_archive_sha256": None,
        "base_verified_champion": False,
    }


def validate_base_source(source: str) -> dict:
    if "__file__" in source:
        raise RuntimeError("Base source contains __file__; it is not safe for the hosted loader")
    env: dict = {}
    exec(compile(source, "v32_base.py", "exec"), env, env)
    name, _ = last_callable(env)
    return {"base_last_callable": name, "base_source_sha256": sha256_bytes(source.encode("utf-8"))}


def overlay_core() -> str:
    text = V33.read_text(encoding="utf-8")
    marker = "# Development-only entry point."
    if marker not in text:
        raise RuntimeError("Could not locate V33 development-entry marker")
    return text.split(marker, 1)[0].rstrip() + "\n"


def build_source(base_source: str) -> str:
    core = overlay_core()
    packed = base64.b85encode(zlib.compress(base_source.encode("utf-8"), level=9)).decode("ascii")
    runtime = f'''\n# Exact base policy is isolated so its globals cannot change V33 loader order.\nimport base64 as _b64, zlib as _zlib\n_V32_PACKED = {packed!r}\n_V32_SOURCE = _zlib.decompress(_b64.b85decode(_V32_PACKED.encode("ascii"))).decode("utf-8")\n_V32_NS = {{}}\nexec(compile(_V32_SOURCE, "v32_exact.py", "exec"), _V32_NS, _V32_NS)\n_V32_CALLABLES = [(k, v) for k, v in _V32_NS.items() if callable(v) and not k.startswith("__")]\nif not _V32_CALLABLES:\n    raise RuntimeError("Embedded V32 produced no callable")\n_V32_AGENT = _V32_CALLABLES[-1][1]\n_V33_POLICY = V33WorkGraphOverlay(_V32_AGENT)\n\ndef agent(obs, configuration=None):\n    return _V33_POLICY.act(obs, configuration)\n'''
    source = core + runtime
    if "__file__" in source:
        raise RuntimeError("Final source must not depend on __file__")
    return source


def synthetic_observation() -> dict:
    tiles = [[None for _ in range(10)] for _ in range(10)]
    tiles[0][0] = {
        "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
        "yield_units": 0, "watered_today": False, "consecutive_unwatered": 1,
    }
    farm = {
        "money": 5000, "unlocked_quadrants": ["NW"], "hires_today": 0,
        "farmer": [4, 4], "hands": [], "tiles": tiles,
    }
    return {
        "player": 0, "step": 0, "day": 0, "hour": 0,
        "farms": [farm, dict(farm)],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {"inventory": {}, "prices": {}},
    }


def validate_generated_source(source: str) -> dict:
    env: dict = {}
    exec(compile(source, "main.py", "exec"), env, env)
    name, fn = last_callable(env)
    if name != "agent":
        raise RuntimeError(f"Kaggle last-callable gate failed: {name!r}")
    action = fn(synthetic_observation(), None)
    if not isinstance(action, dict) or not {"farmer", "hands", "market"} <= set(action):
        raise RuntimeError(f"Synthetic runtime call returned invalid action: {action!r}")
    if len(action.get("market", []) or []) > 10:
        raise RuntimeError("Synthetic call exceeded market-order cap")
    return {"last_callable": name, "synthetic_action_keys": sorted(action)}


def deterministic_tar(source: str) -> bytes:
    payload = source.encode("utf-8")
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tf:
        info = tarfile.TarInfo("main.py")
        info.size = len(payload)
        info.mode = 0o644
        info.mtime = 0
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        tf.addfile(info, io.BytesIO(payload))
    return gzip.compress(tar_buf.getvalue(), compresslevel=9, mtime=0)


def validate_archive(raw: bytes) -> dict:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        names = tf.getnames()
        if names != ["main.py"]:
            raise RuntimeError(f"Unexpected archive members: {names}")
        f = tf.extractfile("main.py")
        if f is None:
            raise RuntimeError("Archive main.py could not be extracted")
        source = f.read().decode("utf-8")
    return validate_generated_source(source)


def build(base_source: str, base_meta: dict, *, out_dir: Path, prefix: str) -> dict:
    base_gate = validate_base_source(base_source)
    source = build_source(base_source)
    source_gate = validate_generated_source(source)
    archive = deterministic_tar(source)
    archive_gate = validate_archive(archive)

    out_dir.mkdir(parents=True, exist_ok=True)
    py_path = out_dir / f"{prefix}.py"
    tar_path = out_dir / f"{prefix}.tar.gz"
    manifest_path = out_dir / f"{prefix}.manifest.json"
    py_path.write_text(source, encoding="utf-8")
    tar_path.write_bytes(archive)

    meta = {
        "strategy": "V33 WorkGraph Counterfactual Capital Twin",
        **base_meta,
        **base_gate,
        "source_sha256": sha256_bytes(source.encode("utf-8")),
        "tar_sha256": sha256_bytes(archive),
        "source_bytes": len(source.encode("utf-8")),
        "archive_bytes": len(archive),
        "runtime_gate": source_gate,
        "archive_runtime_gate": archive_gate,
        "contract": {
            "single_root_main_py": True,
            "contains_dunder_file": False,
            "last_callable_agent": True,
            "black_box_base_namespace": True,
        },
    }
    manifest_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--v32-tar", type=Path, help="Exact SUBMIT_V32_RUNTIME_VERIFIED.tar.gz")
    group.add_argument("--dev-base-source", type=Path, help="Unverified base for CI/development only")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "artifacts")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.v32_tar:
        base_source, base_meta = load_base_from_tar(args.v32_tar)
    else:
        base_source, base_meta = load_dev_base(args.dev_base_source)
        if args.prefix == DEFAULT_PREFIX:
            args.prefix = "DEV_V33_WORKGRAPH_UNVERIFIED"
    print(json.dumps(build(base_source, base_meta, out_dir=args.out_dir, prefix=args.prefix), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
