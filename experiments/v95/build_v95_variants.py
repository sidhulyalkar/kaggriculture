from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import pathlib
import tarfile
import urllib.request
import zlib

SMART_REF = "flexonafft/kaggriculture-smart-farm-strategy-lab"
SMART_SHA256 = "c89d3dd2e9cbdb97f95f2d51bbe2de687d64329069443da7c2ea788ce47fdb5c"
SPARSE_REF = "kaitofukami/103-128-fresh-public-v43-sparse-shop-hybrid"
SPARSE_SHA256 = "69f06a802b62aa08f28705dab5728eb924bb6a7c23ffe0164f65b104cc3dadf3"
V85_SHA256 = "02d15d4ebb69fb077a131529aab609b2b8bb992cc5582b82fc46fa3d3eb0dcad"
UA = {"User-Agent": "Mozilla/5.0 V95-live-calibration"}
THRESHOLDS = (46, 50, 52, 54, 56, 58, 62)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pull_notebook(ref: str) -> dict:
    req = urllib.request.Request(f"https://www.kaggle.com/api/v1/kernels/pull/{ref}", headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        outer = json.load(r)
    src = (outer.get("blob") or {}).get("source")
    if not src:
        raise RuntimeError(f"missing notebook source for {ref}")
    return json.loads(src)


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def smart_source(nb: dict) -> str:
    for cell in nb.get("cells", []):
        src = cell_text(cell)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "AGENT_SOURCE" for t in node.targets):
                continue
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                continue
            if sha(value.encode()) != SMART_SHA256:
                raise RuntimeError(f"Smart Lab source drift: {sha(value.encode())}")
            compile(value, "smart_lab.py", "exec")
            return value
    raise RuntimeError("Smart Lab AGENT_SOURCE not found")


def decoded_literals(src: str):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        values = []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, (list, tuple)) and value and all(isinstance(x, str) for x in value):
            values = ["".join(value)]
        for text in values:
            if len(text) < 500:
                continue
            raw = text.encode("ascii", "ignore")
            for decoder in (lambda x: base64.b64decode(x, validate=False), base64.b85decode):
                try:
                    decoded = decoder(raw)
                except Exception:
                    continue
                yield decoded
                try:
                    yield zlib.decompress(decoded)
                except Exception:
                    pass


def sparse_source(nb: dict) -> str:
    for cell in nb.get("cells", []):
        for data in decoded_literals(cell_text(cell)) or ():
            if sha(data) != SPARSE_SHA256:
                continue
            source = data.decode("utf-8")
            compile(source, "sparse_v43.py", "exec")
            return source
    raise RuntimeError("pinned Sparse Hybrid source not found")


def harden_smart_clock(source: str) -> str:
    old = "    t = int(observation.get('step',observation['day']*24+observation['hour']))"
    new = (
        "    raw_step = observation.get('step', None)\n"
        "    t = int(raw_step) if raw_step is not None else int(observation['day'])*24+int(observation['hour'])"
    )
    if source.count(old) != 1:
        raise RuntimeError(f"Smart clock needle count={source.count(old)}")
    return source.replace(old, new)


def set_late_threshold(source: str, threshold: int) -> str:
    needle = "_SESSIONS = {}\n"
    if source.count(needle) != 1:
        raise RuntimeError(f"session needle count={source.count(needle)}")
    patch = needle + f"# V95 causal late-route ablation; public Smart Lab uses 54.\n_TREES[4][0][4] = {float(threshold)!r}\n"
    return source.replace(needle, patch, 1)


def write_agent(root: pathlib.Path, name: str, source: str) -> dict:
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    path = out / "main.py"
    compile(source, str(path), "exec")
    path.write_text(source)
    return {"name": name, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}


def package(root: pathlib.Path, name: str, out_path: pathlib.Path) -> None:
    main = root / name / "main.py"
    with tarfile.open(out_path, "w:gz") as tf:
        tf.add(main, arcname="main.py")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/v95/generated")
    ap.add_argument("--v85-main", required=True)
    args = ap.parse_args()
    root = pathlib.Path(args.out)
    root.mkdir(parents=True, exist_ok=True)

    v85 = pathlib.Path(args.v85_main).read_bytes()
    if sha(v85) != V85_SHA256:
        raise RuntimeError(f"V85 source mismatch: {sha(v85)}")
    smart = smart_source(pull_notebook(SMART_REF))
    sparse = sparse_source(pull_notebook(SPARSE_REF))

    records = []
    records.append(write_agent(root, "v85_exact", v85.decode("utf-8")))
    records.append(write_agent(root, "smart_public_raw", smart))
    records.append(write_agent(root, "sparse_v43_exact", sparse))

    hardened = harden_smart_clock(smart)
    for threshold in THRESHOLDS:
        records.append(write_agent(root, f"smart_t{threshold}", set_late_threshold(hardened, threshold)))

    manifest = {
        "v85_exact_sha256": V85_SHA256,
        "smart_public_ref": SMART_REF,
        "smart_public_sha256": SMART_SHA256,
        "sparse_public_ref": SPARSE_REF,
        "sparse_public_sha256": SPARSE_SHA256,
        "thresholds": list(THRESHOLDS),
        "agents": records,
    }
    (root.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    packages = root.parent / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    package(root, "sparse_v43_exact", packages / "Kaggriculture_V95_1_SPARSE_V43_EXACT_CALIBRATION.tar.gz")
    package(root, "smart_t54", packages / "Kaggriculture_V95_2_SMARTLAB_T54_CLOCK_HARDENED.tar.gz")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
