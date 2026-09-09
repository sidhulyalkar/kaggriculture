from __future__ import annotations

import ast
import base64
import hashlib
import json
import pathlib
import urllib.request
import zlib

URL = "https://www.kaggle.com/api/v1/kernels/pull/lynnsakurai/farming-score-v3-replay-revised"
EXPECTED = "d36ae976ad4a6316e6c1a27a5d04e9cc8e30300f21bdd31e749127c67a9311c4"
OLD = 'step = int(_get(observation, "step", 0) or 0)'
NEW = '''raw_step = _get(observation, "step", None)\n        step = (int(raw_step) if raw_step is not None else\n                int(_get(observation, "day", 0) or 0) * 24 + int(_get(observation, "hour", 0) or 0))'''


def payload_from_code(code: str) -> str:
    tree = ast.parse(code)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PAYLOAD":
                    return ast.literal_eval(node.value)
    raise RuntimeError("PAYLOAD not found")


def pull_source() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 V81"})
    with urllib.request.urlopen(req, timeout=45) as r:
        nb = json.load(r)
    for cell in nb.get("cells", []):
        code = "".join(cell.get("source", []))
        if "EXPECTED_SOURCE_SHA256" in code and "PAYLOAD" in code:
            payload = payload_from_code(code)
            source = zlib.decompress(base64.b64decode(payload)).decode()
            got = hashlib.sha256(source.encode()).hexdigest()
            if got != EXPECTED:
                raise RuntimeError(f"unexpected upstream source {got}")
            return source
    raise RuntimeError("embedded source cell not found")


def main() -> None:
    out = pathlib.Path("experiments/v81/generated")
    out.mkdir(parents=True, exist_ok=True)
    source = pull_source()
    if source.count(OLD) != 1:
        raise RuntimeError(f"clock site count {source.count(OLD)}")
    patched = source.replace(OLD, NEW)
    compile(source, "base_farming_v3.py", "exec")
    compile(patched, "v81_farming_clock.py", "exec")
    (out / "base_farming_v3.py").write_text(source)
    (out / "v81_farming_clock.py").write_text(patched)
    manifest = {
        "upstream_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "change": "fallback to day*24+hour only when observation.step is None",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
