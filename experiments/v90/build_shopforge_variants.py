from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import pathlib
import re
import shutil
import subprocess
import tarfile
import urllib.request
import zlib

THREE_DAY_REF = "yhay81/three-day-shop-router"
ADAPTIVE_REF = "reyhanksatria/adaptive-route-agent-v2"
PUBLIC_ARCHIVE_SHA = "b650a31d091323f2510aede0265937d3193a82a99109eadc8ab39c6e85db278d"


def pull_notebook(ref: str) -> dict:
    url = f"https://www.kaggle.com/api/v1/kernels/pull/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 V90"})
    with urllib.request.urlopen(req, timeout=60) as r:
        outer = json.load(r)
    source = (outer.get("blob") or {}).get("source")
    if not source:
        raise RuntimeError(f"missing notebook source for {ref}")
    return json.loads(source)


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def extract_writefiles(nb: dict, root: pathlib.Path) -> None:
    for cell in nb.get("cells", []):
        src = cell_text(cell)
        if not src.startswith("%%writefile "):
            continue
        first, body = src.split("\n", 1)
        rel = first[len("%%writefile "):].strip()
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def patch_select_route(text: str, mode: str, bakery: float = 10232.5, pet: float = 64.5) -> str:
    if mode == "threshold":
        text = text.replace("<= 10232.5", f"<= {bakery:.1f}")
        text = text.replace("<= 64.5", f"<= {pet:.1f}")
        return text
    start = text.index("int select_route(const kag::State& state, int seat) {")
    marker = "\n}\n\nstruct Context"
    end = text.index(marker, start)
    if mode == "route0":
        body = "int select_route(const kag::State& state, int seat) {\n    static_cast<void>(state); static_cast<void>(seat); return 0;"
    elif mode == "route1":
        body = "int select_route(const kag::State& state, int seat) {\n    static_cast<void>(state); static_cast<void>(seat); return 1;"
    else:
        raise ValueError(mode)
    return text[:start] + body + text[end:]


def compile_variant(base: pathlib.Path, dest: pathlib.Path, mode: str, bakery: float = 10232.5, pet: float = 64.5) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(base, dest)
    policy = dest / "source/policy.cpp"
    policy.write_text(patch_select_route(policy.read_text(), mode, bakery, pet))
    subprocess.run([
        "g++", "-O3", "-std=c++17", "-Wall", "-Wextra", "-pedantic",
        "-shared", "-fPIC", "-Isource/include", "-o", "agent.so",
        "source/policy.cpp", "submission_bridge.cpp",
    ], cwd=dest, check=True)
    compile((dest / "main.py").read_text(), str(dest / "main.py"), "exec")


def extract_public_control(root: pathlib.Path) -> dict:
    nb = pull_notebook(ADAPTIVE_REF)
    src = "\n".join(cell_text(c) for c in nb.get("cells", []))
    expected = re.search(r'EXPECTED_ARCHIVE_SHA\s*=\s*[\'\"]([^\'\"]+)', src)
    payload = re.search(r'PAYLOAD\s*=\s*[\'\"]([^\'\"]+)', src)
    if not expected or not payload:
        raise RuntimeError("adaptive payload markers missing")
    raw = zlib.decompress(base64.b64decode(payload.group(1)))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected.group(1) or digest != PUBLIC_ARCHIVE_SHA:
        raise RuntimeError(f"public archive hash mismatch {digest}")
    out = root / "public_control.tar.gz"
    out.write_bytes(raw)
    d = root / "public_control"
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        names = tf.getnames()
        if sorted(names) != ["agent.so", "main.py"]:
            raise RuntimeError(names)
        tf.extractall(d)
    return {"sha256": digest, "bytes": len(raw), "members": names}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/v90/generated")
    ap.add_argument("--bakery", type=float, default=10232.5)
    ap.add_argument("--pet", type=float, default=64.5)
    args = ap.parse_args()
    root = pathlib.Path(args.out)
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)

    nb = pull_notebook(THREE_DAY_REF)
    base = root / "source_base"
    extract_writefiles(nb, base)
    required = [
        "source/policy.cpp", "source/tape.inc", "source/include/six_day_budget_guard.hpp",
        "source/include/policy_plugin_abi.hpp", "source/include/runtime_types.hpp",
        "submission_bridge.cpp", "main.py",
    ]
    for rel in required:
        if not (base / rel).exists(): raise RuntimeError(f"missing {rel}")

    compile_variant(base, root / "route0", "route0")
    compile_variant(base, root / "route1", "route1")
    compile_variant(base, root / "public_rebuild", "threshold", 10232.5, 64.5)
    compile_variant(base, root / "selected", "threshold", args.bakery, args.pet)
    public = extract_public_control(root)

    info = {
        "three_day_ref": THREE_DAY_REF,
        "adaptive_ref": ADAPTIVE_REF,
        "selected": {"bakery_fert_threshold": args.bakery, "pet_rival_plants_threshold": args.pet},
        "public_control": public,
        "files": {},
    }
    for name in ["route0", "route1", "public_rebuild", "selected"]:
        info["files"][name] = {
            "main_sha256": hashlib.sha256((root/name/"main.py").read_bytes()).hexdigest(),
            "so_sha256": hashlib.sha256((root/name/"agent.so").read_bytes()).hexdigest(),
        }
    (root / "build_manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))

if __name__ == "__main__":
    main()
