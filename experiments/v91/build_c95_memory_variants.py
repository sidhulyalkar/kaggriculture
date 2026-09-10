from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import pathlib
import textwrap
import urllib.request
import zlib

TOP_META = "raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta"
COND_MEM = "kaitofukami/177-180-fresh-top-30-v21-1-conditional-memory"
UA = {"User-Agent": "Mozilla/5.0 V91-c95-memory"}


def pull(ref: str) -> dict:
    req = urllib.request.Request(f"https://www.kaggle.com/api/v1/kernels/pull/{ref}", headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        outer = json.load(r)
    src = (outer.get("blob") or {}).get("source")
    if not src:
        raise RuntimeError(f"no notebook source: {ref}")
    return json.loads(src)


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def literal_assignment(nb: dict, name: str):
    for cell in nb.get("cells", []):
        src = cell_text(cell)
        if name not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"assignment {name!r} not found")


def extract_c95(nb: dict) -> str:
    parts = literal_assignment(nb, "_C95_AGENT_B64_PARTS")
    raw = zlib.decompress(base64.b64decode("".join(parts))).decode("utf-8")
    expected = "489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb"
    got = hashlib.sha256(raw.encode()).hexdigest()
    if got != expected:
        raise RuntimeError(f"C95 hash drift: {got}")
    compile(raw, "c95.py", "exec")
    return raw


def extract_conditional(nb: dict):
    parts = literal_assignment(nb, "_AGENT_B85_PARTS")
    raw = zlib.decompress(base64.b85decode("".join(parts).encode("ascii"))).decode("utf-8")
    ns = {"__name__": "v91_conditional_extract"}
    exec(compile(raw, "conditional_memory.py", "exec"), ns)
    protos = ns["_PROTOTYPES"]
    if len(protos) != 30:
        raise RuntimeError(f"expected 30 prototypes, got {len(protos)}")
    return raw, protos


def memory_blob(protos) -> str:
    raw = json.dumps(protos, separators=(",", ":")).encode()
    return base64.b85encode(zlib.compress(raw, 9)).decode("ascii")


def overlay(blob: str, threshold: float, mode: str) -> str:
    # Prefix every symbol to avoid colliding with the donor implementation.
    return textwrap.dedent(f'''

# ===== V91 identity-free conditional market memory =====
# This overlay NEVER changes farmer/hands, product quantities, BUYs, or which
# products are sold.  It only reorders existing same-turn SELL orders.
_V91_MEMORY_THRESHOLD = {threshold!r}
_V91_MEMORY_MODE = {mode!r}
_V91_CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
_V91_ANIMALS = ("COW", "SHEEP", "GOOSE")
_V91_KINDS = ("PASTURE", "COOP")
_V91_QUADRANTS = ("NW", "NE", "SW", "SE")
_V91_MAX_ACTORS = 13
_V91_PROTOTYPES = json.loads(zlib.decompress(base64.b85decode({blob!r}.encode("ascii"))))
_V91_HOST_AGENT = agent
_V91_LAST = {{0: -1, 1: -1}}
_V91_ACTIVATIONS = {{0: 0, 1: 0}}


def _v91_position(value):
    try:
        return (int(value[0]), int(value[1]))
    except Exception:
        return (-1, -1)


def _v91_signature(farm):
    farm = farm or {{}}
    hands = list(farm.get("hands") or [])
    unlocks = set(farm.get("unlocked_quadrants") or [])
    positions = [_v91_position(farm.get("farmer", (-1, -1)))]
    positions.extend(_v91_position(item) for item in hands)
    positions = (positions + [(-1, -1)] * _V91_MAX_ACTORS)[:_V91_MAX_ACTORS]
    keys = (*_V91_CROPS, *_V91_ANIMALS, *_V91_KINDS, "WEED")
    counts = {{key: 0 for key in keys}}
    yields = {{key: 0 for key in (*_V91_CROPS, *_V91_ANIMALS)}}
    for row in (farm.get("tiles") or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            crop = str(tile.get("crop", "") or "").upper()
            animal = str(tile.get("animal", "") or "").upper()
            kind = str(tile.get("kind", "") or "").upper()
            if crop in counts:
                counts[crop] += 1
                yields[crop] += max(0, int(tile.get("yield_units", 0) or 0))
            if animal in counts:
                counts[animal] += 1
                yields[animal] += max(0, int(tile.get("yield_units", 0) or 0))
            if kind in _V91_KINDS:
                counts[kind] += 1
            if kind == "WEED":
                counts["WEED"] += 1
    return {{
        "workers": len(hands),
        "unlocks": sum(1 << i for i, q in enumerate(_V91_QUADRANTS) if q in unlocks),
        "positions": [c for p in positions for c in p],
        "counts": [counts[k] for k in keys],
        "yields": [yields[k] for k in (*_V91_CROPS, *_V91_ANIMALS)],
    }}


def _v91_distance(a, b):
    total = 12.0 * abs(int(a["workers"]) - int(b["workers"]))
    total += 7.0 * (int(a["unlocks"]) ^ int(b["unlocks"])).bit_count()
    ap, bp = list(a["positions"]), list(b["positions"])
    for actor in range(_V91_MAX_ACTORS):
        o = 2 * actor
        aa, bb = ap[o:o+2], bp[o:o+2]
        if aa == [-1, -1] and bb == [-1, -1]:
            continue
        w = 0.8 if actor == 0 else 0.25
        total += w * sum(abs(x-y) for x,y in zip(aa,bb))
    for i,(x,y) in enumerate(zip(a["counts"], b["counts"])):
        total += (0.25 if i == len(a["counts"])-1 else 3.0) * abs(x-y)
    total += 0.15 * sum(abs(x-y) for x,y in zip(a["yields"], b["yields"]))
    return total


def _v91_predicted_items(obs, step):
    seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farms = list(obs.get("farms") or [])
    opponent = farms[1-seat] if len(farms) >= 2 else {{}}
    observed = _v91_signature(opponent)
    ranked = []
    for i, proto in enumerate(_V91_PROTOTYPES):
        sigs = proto.get("signatures") or []
        if step < len(sigs):
            ranked.append((_v91_distance(observed, sigs[step]), i))
    if not ranked:
        return set()
    ranked.sort()
    if _V91_MEMORY_MODE == "nearest":
        d, i = ranked[0]
        if d > _V91_MEMORY_THRESHOLD:
            return set()
        sales = _V91_PROTOTYPES[i].get("sales") or []
        return set((sales[step] if step < len(sales) else {{}}).keys())
    # consensus2: at least two of the three nearest in-threshold memories agree.
    votes = {{}}
    used = 0
    for d, i in ranked[:3]:
        if d > _V91_MEMORY_THRESHOLD:
            continue
        sales = _V91_PROTOTYPES[i].get("sales") or []
        predicted = sales[step] if step < len(sales) else {{}}
        used += 1
        for item in predicted:
            votes[item] = votes.get(item, 0) + 1
    if used < 2:
        return set()
    return {{item for item, n in votes.items() if n >= 2}}


def _v91_reorder(obs, action, step):
    market = [list(o) for o in (action.get("market") or [])]
    sell_indices = [i for i,o in enumerate(market) if len(o) >= 3 and o[0] == "SELL"]
    if len(sell_indices) < 1:
        return action
    predicted = _v91_predicted_items(obs, step)
    if not predicted:
        return action
    front = [o for o in market if len(o) >= 3 and o[0] == "SELL" and o[1] in predicted]
    if not front:
        return action
    rest = [o for o in market if not (len(o) >= 3 and o[0] == "SELL" and o[1] in predicted)]
    new_market = (front + rest)[:10]
    if new_market != market:
        seat = 1 if int(obs.get("player", 0) or 0) == 1 else 0
        _V91_ACTIVATIONS[seat] += 1
        action["market"] = new_market
    return action


def agent(obs, config=None):
    try:
        # Canonicalize the live clock without altering normal observations.
        if obs.get("step") is None:
            obs = dict(obs)
            obs["step"] = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
        step = min(max(0, int(obs.get("step", 0) or 0)), 718)
        action = _V91_HOST_AGENT(obs, config)
        if not isinstance(action, dict):
            return action
        return _v91_reorder(obs, action, step)
    except Exception:
        return _V91_HOST_AGENT(obs, config)


def v91_submission_agent(obs, config=None):
    return agent(obs, config)
''')


def clock_only_overlay() -> str:
    return textwrap.dedent('''

# ===== V91 canonical clock only =====
_V91_HOST_AGENT = agent

def agent(obs, config=None):
    if obs.get("step") is None:
        obs = dict(obs)
        obs["step"] = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
    return _V91_HOST_AGENT(obs, config)

def v91_submission_agent(obs, config=None):
    return agent(obs, config)
''')


def write_variant(root: pathlib.Path, name: str, source: str):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "main.py"
    p.write_text(source)
    compile(source, str(p), "exec")
    return {"name": name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/v91/generated")
    args = ap.parse_args()
    root = pathlib.Path(args.out); root.mkdir(parents=True, exist_ok=True)
    c95 = extract_c95(pull(TOP_META))
    _, protos = extract_conditional(pull(COND_MEM))
    blob = memory_blob(protos)
    rows = []
    rows.append(write_variant(root, "c95_clock", c95 + clock_only_overlay()))
    rows.append(write_variant(root, "mem_near24", c95 + overlay(blob, 24.0, "nearest")))
    rows.append(write_variant(root, "mem_near48", c95 + overlay(blob, 48.0, "nearest")))
    rows.append(write_variant(root, "mem_consensus48", c95 + overlay(blob, 48.0, "consensus2")))
    manifest = {
        "top_meta": TOP_META,
        "conditional_memory": COND_MEM,
        "c95_upstream_sha256": hashlib.sha256(c95.encode()).hexdigest(),
        "prototype_count": len(protos),
        "variants": rows,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
