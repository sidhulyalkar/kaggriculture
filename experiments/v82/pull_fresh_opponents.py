from __future__ import annotations

import ast
import base64
import json
import pathlib
import urllib.request

SOURCES = {
    "shape_current": "tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
    "farming_math": "lynnsakurai/farming-score-a-mathematical-approach",
}


def _pull_notebook(ref: str) -> dict:
    url = f"https://www.kaggle.com/api/v1/kernels/pull/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 V82"})
    with urllib.request.urlopen(req, timeout=45) as r:
        outer = json.load(r)
    source = outer.get("blob", {}).get("source")
    if not source:
        raise RuntimeError(f"missing notebook source for {ref}")
    return json.loads(source)


def _extract_main(nb: dict) -> bytes:
    for cell in nb.get("cells", []):
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        if "MAIN_B64" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MAIN_B64":
                    payload = ast.literal_eval(node.value)
                    data = base64.b64decode(payload)
                    compile(data.decode(), "fresh_public_main.py", "exec")
                    return data
    raise RuntimeError("MAIN_B64 not found")


def main() -> None:
    out = pathlib.Path("experiments/v82/fresh_opponents")
    out.mkdir(parents=True, exist_ok=True)
    for name, ref in SOURCES.items():
        data = _extract_main(_pull_notebook(ref))
        (out / f"{name}.py").write_bytes(data)
        print(name, ref, len(data))


if __name__ == "__main__":
    main()
