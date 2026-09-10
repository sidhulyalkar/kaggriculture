from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SHOP_NAMES = ("YARN_STORE", "FARMERS_MARKET", "BAKERY", "PET_CAFE", "ICE_CREAM_SHOP", "PIZZA_SHOP")
LEAVES = ("main", "yarn", "yarn_carrot", "milk_glut")
PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _load_agent(path: str):
    p = Path(path).resolve()
    name = "v87_" + hashlib.sha1(f"{p}:{os.getpid()}:{os.urandom(6).hex()}".encode()).hexdigest()[:16]
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {p}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if not callable(fn):
        raise RuntimeError(f"no agent in {p}")
    return fn, name


def _call(fn, obs):
    try:
        return fn(obs)
    except TypeError:
        return fn(obs, {})


def _count_land(v) -> int:
    if isinstance(v, int):
        return int(v)
    if isinstance(v, (list, tuple, set, dict)):
        return len(v)
    return 0


def _farm_stats(farm: dict) -> dict:
    out = {
        "money": float(farm.get("money", 0) or 0),
        "hands": len(farm.get("hands") or []),
        "land": _count_land(farm.get("unlocked_land")),
        "plants": 0, "pastures": 0, "coops": 0, "weeds": 0,
        "cows": 0, "sheep": 0, "geese": 0,
    }
    for row in farm.get("tiles") or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind") or "")
            if kind == "PLANT": out["plants"] += 1
            elif kind == "PASTURE": out["pastures"] += 1
            elif kind == "COOP": out["coops"] += 1
            elif kind == "WEED": out["weeds"] += 1
            animal = str(tile.get("animal") or "")
            if animal == "COW": out["cows"] += 1
            elif animal == "SHEEP": out["sheep"] += 1
            elif animal == "GOOSE": out["geese"] += 1
    return out


def _features(obs: dict, seat: int) -> dict:
    farms = obs.get("farms") or [{}, {}]
    me = int(obs.get("player", seat) or seat)
    if me not in (0, 1): me = seat
    own = _farm_stats(farms[me])
    opp = _farm_stats(farms[1 - me])
    market = obs.get("market") or {}
    prices = market.get("prices") or {}
    inventory = market.get("inventory") or {}
    private = obs.get("private") or {}
    shed = private.get("shed") or {}
    seeds = private.get("seeds") or {}
    shops = (obs.get("town") or {}).get("unlocked_shops") or []

    f = {
        "own_money": own["money"], "opp_money": opp["money"], "money_diff": own["money"] - opp["money"],
        "own_hands": own["hands"], "opp_hands": opp["hands"], "hands_diff": own["hands"] - opp["hands"],
        "own_land": own["land"], "opp_land": opp["land"], "land_diff": own["land"] - opp["land"],
        "own_plants": own["plants"], "opp_plants": opp["plants"], "plants_diff": own["plants"] - opp["plants"],
        "own_pastures": own["pastures"], "opp_pastures": opp["pastures"], "pastures_diff": own["pastures"] - opp["pastures"],
        "own_coops": own["coops"], "opp_coops": opp["coops"], "coops_diff": own["coops"] - opp["coops"],
        "own_cows": own["cows"], "opp_cows": opp["cows"], "cows_diff": own["cows"] - opp["cows"],
        "own_sheep": own["sheep"], "opp_sheep": opp["sheep"], "sheep_diff": own["sheep"] - opp["sheep"],
        "own_geese": own["geese"], "opp_geese": opp["geese"], "geese_diff": own["geese"] - opp["geese"],
        "shop_total": len(shops),
    }
    for name in SHOP_NAMES:
        f[f"shop_{name}"] = shops.count(name)
    for item in PRODUCTS:
        f[f"price_{item}"] = float(prices.get(item, 0) or 0)
        f[f"market_{item}"] = float(inventory.get(item, 0) or 0)
        f[f"shed_{item}"] = float(shed.get(item, 0) or 0)
    for item in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        f[f"seed_{item}"] = float(seeds.get(item, 0) or 0)
    return f


def _run_one(agent_path: str, opp_path: str, seed: int, seat: int):
    import kagsim
    afn = ofn = None
    amod = omod = None
    snapshots = {}
    try:
        afn, amod = _load_agent(agent_path)
        ofn, omod = _load_agent(opp_path)
        g = kagsim.Game(int(seed))
        while not g.done:
            o0 = dict(g.observe(0)); o1 = dict(g.observe(1))
            mine = o0 if seat == 0 else o1
            raw = mine.get("step")
            step = int(raw) if raw is not None else int(mine.get("day", 0) or 0) * 24 + int(mine.get("hour", 0) or 0)
            if step in (226, 360, 433) and step not in snapshots:
                snapshots[step] = _features(mine, seat)
            if seat == 0:
                a0, a1 = _call(afn, o0), _call(ofn, o1)
            else:
                a0, a1 = _call(ofn, o0), _call(afn, o1)
            g.step(a0 or PASS, a1 or PASS)
        mine_r = float(g.reward(seat) or 0.0)
        opp_r = float(g.reward(1 - seat) or 0.0)
        return mine_r - opp_r, snapshots, None
    except Exception:
        return -1e12, snapshots, traceback.format_exc(limit=4)
    finally:
        if amod: sys.modules.pop(amod, None)
        if omod: sys.modules.pop(omod, None)


def _task(task):
    expert_dir, opp_name, opp_path, seed, seat = task
    results = {}
    snaps = {}
    errors = {}
    for leaf in LEAVES:
        margin, ss, err = _run_one(str(Path(expert_dir) / f"expert_{leaf}.py"), opp_path, seed, seat)
        results[leaf] = margin
        snaps[leaf] = ss
        if err: errors[leaf] = err
    if errors:
        return {"opponent": opp_name, "seed": seed, "seat": seat, "errors": errors}

    # These reference states are guaranteed to have identical prefixes within each
    # counterfactual comparison by construction of the expert leaves.
    f226 = snaps["main"].get(226) or {}
    f360 = snaps["yarn"].get(360) or {}
    f433 = snaps["main"].get(433) or {}
    return {
        "opponent": opp_name, "seed": seed, "seat": seat,
        "features_226": f226,
        "features_360": f360,
        "features_433": f433,
        "margins": results,
        "delta_226": max(results["yarn"], results["yarn_carrot"]) - max(results["main"], results["milk_glut"]),
        "delta_360": results["yarn_carrot"] - results["yarn"],
        "delta_433": results["milk_glut"] - results["main"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experts", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--start-seed", type=int, default=170001)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import kagsim
    assert getattr(kagsim, "ENGINE_VERSION", "") == "1.32.7"
    opponents = {p.stem: str(p.resolve()) for p in sorted(Path(args.opponents).glob("*.py"))}
    tasks = []
    for opp_name, opp_path in opponents.items():
        for seed in range(args.start_seed, args.start_seed + args.seeds):
            for seat in (0, 1):
                tasks.append((args.experts, opp_name, opp_path, seed, seat))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_task, tasks, chunksize=1))
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    bad = sum(bool(r.get("errors")) for r in rows)
    print("rows", len(rows), "errors", bad, "opponents", sorted(opponents))
    if bad:
        raise SystemExit(f"oracle dataset has {bad} failed tasks")


if __name__ == "__main__":
    main()
