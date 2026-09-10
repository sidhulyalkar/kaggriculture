from __future__ import annotations

import ast
import base64
import json
import pathlib
import urllib.request

REF = "reyhanksatria/adaptive-route-agent-v2"
OUT = pathlib.Path("experiments/v87/opponents/adaptive_v2.py")


def main():
    url = f"https://www.kaggle.com/api/v1/kernels/pull/{REF}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 V87"})
    with urllib.request.urlopen(req, timeout=45) as r:
        outer = json.load(r)
    source = outer.get("blob", {}).get("source")
    if not source:
        raise SystemExit("no notebook source")
    nb = json.loads(source)
    for cell in nb.get("cells", []):
        src = cell.get("source", "")
        if isinstance(src, list): src = "".join(src)
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
                    compile(data.decode(), str(OUT), "exec")
                    OUT.parent.mkdir(parents=True, exist_ok=True)
                    OUT.write_bytes(data)
                    print(REF, len(data), OUT)
                    return
    raise SystemExit("MAIN_B64 not found in Adaptive Route V2")


if __name__ == "__main__":
    main()
