from __future__ import annotations

import ast
import base64
import gzip
import hashlib
import io
import json
import pathlib
import re
import tarfile
import urllib.error
import urllib.request
import zipfile
import zlib

SOURCES = {
    "top_meta": "raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta",
    "conditional_memory": "kaitofukami/177-180-fresh-top-30-v21-1-conditional-memory",
    "adaptive_guard": "reyhanksatria/kaggriculture-adaptive-shop-guard",
    "smart_lab": "flexonafft/kaggriculture-smart-farm-strategy-lab",
    "harvestforge": "salemali7/kaggriculture-2900",
}

UA = {"User-Agent": "Mozilla/5.0 V91-meta-options"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def pull_notebook(ref: str) -> tuple[dict, dict]:
    outer = json.loads(get(f"https://www.kaggle.com/api/v1/kernels/pull/{ref}"))
    source = (outer.get("blob") or {}).get("source")
    if not source:
        raise RuntimeError(f"missing blob.source for {ref}")
    return outer, json.loads(source)


def text(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def maybe_decode_string(name: str, value: str) -> list[tuple[str, bytes]]:
    out = []
    raw = value.encode("ascii", "ignore")
    attempts = []
    if len(raw) < 200:
        return out
    for label, fn in (
        ("b64", lambda b: base64.b64decode(b, validate=False)),
        ("b85", base64.b85decode),
    ):
        try:
            d = fn(raw)
            if d:
                attempts.append((label, d))
        except Exception:
            pass
    for label, d in list(attempts):
        out.append((label, d))
        for zlabel, zfn in (
            ("zlib", zlib.decompress),
            ("gzip", gzip.decompress),
        ):
            try:
                dd = zfn(d)
                if dd:
                    out.append((label + "_" + zlabel, dd))
            except Exception:
                pass
    return out


def scan_assignments(src: str, outdir: pathlib.Path, cell_idx: int) -> list[str]:
    written = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return written
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        if not isinstance(value, str):
            continue
        names = [t.id for t in targets if isinstance(t, ast.Name)] or ["literal"]
        for n in names:
            if len(value) < 200:
                continue
            interesting = any(k in n.upper() for k in ("B64", "B85", "BASE", "SUBMISSION", "MAIN", "PAYLOAD", "AGENT", "TAPE"))
            if not interesting and len(value) < 5000:
                continue
            for codec, data in maybe_decode_string(n, value):
                suffix = ".bin"
                s = data.lstrip()
                if s.startswith((b"from ", b"import ", b"def ", b"class ", b"#")):
                    suffix = ".py"
                elif data[:2] == b"\x1f\x8b":
                    suffix = ".gz"
                elif data[:4] == b"PK\x03\x04":
                    suffix = ".zip"
                p = outdir / f"decoded_c{cell_idx}_{re.sub(r'[^A-Za-z0-9_]+','_',n)[:48]}_{codec}{suffix}"
                if not p.exists() and len(data) > 100:
                    p.write_bytes(data)
                    written.append(p.name)
    return written


def safe_extract_output(ref: str, d: pathlib.Path) -> dict:
    info = {"ok": False, "members": [], "error": None}
    try:
        raw = get(f"https://www.kaggle.com/api/v1/kernels/output/{ref}")
        zpath = d / "kaggle_output.zip"
        zpath.write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            info["members"] = z.namelist()
            z.extractall(d / "output")
        info["ok"] = True
    except Exception as e:
        info["error"] = repr(e)
    return info


def inspect_files(d: pathlib.Path) -> list[dict]:
    rows = []
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(d))
        b = p.read_bytes()
        row = {"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        if p.suffix == ".py":
            try:
                compile(b.decode(), rel, "exec")
                row["python_compile"] = True
            except Exception as e:
                row["python_compile"] = False
                row["compile_error"] = repr(e)
        if p.name.endswith((".tar.gz", ".tgz")):
            try:
                with tarfile.open(p, "r:gz") as tf:
                    row["tar_members"] = tf.getnames()
            except Exception as e:
                row["tar_error"] = repr(e)
        rows.append(row)
    return rows


def main() -> None:
    root = pathlib.Path("experiments/v91/harvest")
    root.mkdir(parents=True, exist_ok=True)
    report = {}
    for key, ref in SOURCES.items():
        d = root / key
        d.mkdir(parents=True, exist_ok=True)
        rec = {"ref": ref}
        try:
            outer, nb = pull_notebook(ref)
            (d / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
            cells = [text(c) for c in nb.get("cells", [])]
            (d / "all_code.txt").write_text("\n\n# ===== CELL =====\n\n".join(cells))
            decoded = []
            for i, src in enumerate(cells):
                decoded.extend(scan_assignments(src, d, i))
            rec["cells"] = len(cells)
            rec["source_sha256"] = hashlib.sha256(json.dumps(nb, sort_keys=True).encode()).hexdigest()
            rec["decoded"] = decoded
            rec["output"] = safe_extract_output(ref, d)
            rec["files"] = inspect_files(d)
            print("HARVEST", key, ref, "cells", len(cells), "decoded", len(decoded), "output", rec["output"]["ok"])
            for f in rec["files"]:
                if f["path"].endswith(("main.py", "submission.py", ".tar.gz", ".so")) or "decoded" in f["path"]:
                    print("  ", f["path"], f["bytes"], f["sha256"][:16], f.get("tar_members", ""))
        except Exception as e:
            rec["error"] = repr(e)
            print("ERROR", key, ref, repr(e))
        report[key] = rec
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
