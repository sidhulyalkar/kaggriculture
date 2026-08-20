#!/usr/bin/env python3
"""Build and validate the standalone V33 WorkGraph Kaggle artifact.

The hosted Kaggle loader executes submitted source without defining __file__, so
this builder compiles the V32 mechanical backbone and V33 residual into one
root main.py before packaging it as a tar.gz.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "submission" / "base_controller.py"
V33 = ROOT / "submission" / "v33_workgraph_agent.py"
OUT_DIR = ROOT / "artifacts"
OUT_PY = OUT_DIR / "SUBMIT_V33_WORKGRAPH.py"
OUT_TAR = OUT_DIR / "SUBMIT_V33_WORKGRAPH.tar.gz"
OUT_META = OUT_DIR / "SUBMIT_V33_WORKGRAPH.manifest.json"


def build_source() -> str:
    base = BASE.read_text(encoding="utf-8")
    marker = "_POLICY=HarvestMind()"
    if marker not in base:
        raise RuntimeError("Could not locate base-controller runtime marker")
    base = base.split(marker, 1)[0].rstrip() + "\n\n"

    ext = V33.read_text(encoding="utf-8")
    ext_marker = "@dataclass(frozen=True)\nclass WorkGraphState"
    if ext_marker not in ext:
        raise RuntimeError("Could not locate V33 standalone extension marker")
    ext = ext[ext.index(ext_marker):]

    source = base + "from typing import Any\n\n" + ext.rstrip() + "\n"
    if "__file__" in source:
        raise RuntimeError("Final runtime source must not reference __file__")
    return source


def _last_callable(env: dict):
    callables = [(k, v) for k, v in env.items() if callable(v) and not k.startswith("__")]
    if not callables:
        raise RuntimeError("No callable found in generated submission")
    return callables[-1]


def synthetic_observation() -> dict:
    tiles = [[None for _ in range(10)] for _ in range(10)]
    tiles[0][0] = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "planted_day": 0,
        "yield_units": 0,
        "watered_today": False,
        "consecutive_unwatered": 1,
    }
    farm = {
        "money": 5000,
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
        "farmer": [4, 4],
        "hands": [],
        "tiles": tiles,
    }
    return {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": [farm, dict(farm)],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}, {}]},
        "market": {"inventory": {}, "prices": {}},
    }


def validate_source(source: str) -> dict:
    env: dict = {}
    code = compile(source, "main.py", "exec")
    exec(code, env, env)
    name, fn = _last_callable(env)
    if name != "agent":
        raise RuntimeError(f"Kaggle last-callable gate failed: {name!r} is last, not 'agent'")
    action = fn(synthetic_observation(), None)
    if not isinstance(action, dict) or not {"farmer", "hands", "market"} <= set(action):
        raise RuntimeError(f"Synthetic runtime call returned invalid action: {action!r}")
    return {"last_callable": name, "synthetic_action": action}


def build() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = build_source()
    runtime = validate_source(source)
    OUT_PY.write_text(source, encoding="utf-8")

    payload = source.encode("utf-8")
    with tarfile.open(OUT_TAR, "w:gz") as tf:
        info = tarfile.TarInfo("main.py")
        info.size = len(payload)
        info.mode = 0o644
        tf.addfile(info, io.BytesIO(payload))

    # Validate the exact archived bytes, not just the pre-pack source.
    with tarfile.open(OUT_TAR, "r:gz") as tf:
        names = tf.getnames()
        if names != ["main.py"]:
            raise RuntimeError(f"Unexpected archive members: {names}")
        archived = tf.extractfile("main.py").read().decode("utf-8")
    archive_runtime = validate_source(archived)

    meta = {
        "strategy": "V33 WorkGraph / Ephemeral Labor Option Twin",
        "control": "V32-style deterministic backbone",
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "tar_sha256": hashlib.sha256(OUT_TAR.read_bytes()).hexdigest(),
        "source_bytes": len(payload),
        "archive_bytes": OUT_TAR.stat().st_size,
        "runtime_gate": runtime,
        "archive_runtime_gate": archive_runtime,
        "contract": {
            "single_root_main_py": True,
            "contains_dunder_file": False,
            "last_callable_agent": True,
        },
    }
    OUT_META.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return meta


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
