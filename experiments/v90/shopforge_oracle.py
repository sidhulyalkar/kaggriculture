from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from typing import Any

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def _load_agent(path: str):
    p = pathlib.Path(path).resolve()
    name = "v90_" + hashlib.sha1(f"{p}:{os.getpid()}:{os.urandom(8).hex()}".encode()).hexdigest()[:20]
    parent = str(p.parent)
    sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {p}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if not callable(fn):
        raise RuntimeError(f"no agent() in {p}")
    return fn, name, parent


def _unload(name: str | None, parent: str | None) -> None:
    if name:
        sys.modules.pop(name, None)
    if parent and parent in sys.path:
        try:
            sys.path.remove(parent)
        except ValueError:
            pass


def _call(fn, obs):
    try:
        return fn(obs)
    except TypeError:
        return fn(obs, {"episodeSteps": 720})


def _tile_kind(tile: Any) -> str:
    if isinstance(tile, dict):
        if tile.get("crop"):
            return "PLANT"
        return str(tile.get("kind") or "")
    return str(tile or "")


def _farm_stats(farm: dict) -> dict:
    plants = pastures = coops = weeds = 0
    for row in farm.get("tiles") or []:
        for tile in row or []:
            kind = _tile_kind(tile)
            plants += int(kind == "PLANT")
            pastures += int(kind == "PASTURE")
            coops += int(kind == "COOP")
            weeds += int(kind == "WEED")
    uq = farm.get("unlocked_quadrants")
    if uq is None:
        uq = farm.get("unlocked_land")
    if isinstance(uq, int):
        quadrants = uq
    elif isinstance(uq, (list, tuple, set, dict)):
        quadrants = len(uq)
    else:
        quadrants = 0
    return {
        "money": float(farm.get("money", 0) or 0),
        "hands": len(farm.get("hands") or []),
        "quadrants": quadrants,
        "plants": plants,
        "pastures": pastures,
        "coops": coops,
        "weeds": weeds,
    }


def _features(obs: dict, seat: int) -> dict:
    farms = list(obs.get("farms") or [{}, {}])
    own = _farm_stats(farms[seat])
    opp = _farm_stats(farms[1 - seat])
    market = obs.get("market") or {}
    inv = market.get("inventory") or {}
    prices = market.get("prices") or {}
    shops = list((obs.get("town") or {}).get("unlocked_shops") or [])
    f = {
        "first_shop": str(shops[0]) if shops else "NONE",
        "shops": shops,
        "shop_total": len(shops),
        "own_money": own["money"], "opp_money": opp["money"], "money_diff": own["money"] - opp["money"],
        "own_hands": own["hands"], "opp_hands": opp["hands"], "hands_diff": own["hands"] - opp["hands"],
        "own_quadrants": own["quadrants"], "opp_quadrants": opp["quadrants"],
        "own_plants": own["plants"], "opp_plants": opp["plants"], "plants_diff": own["plants"] - opp["plants"],
        "own_pastures": own["pastures"], "opp_pastures": opp["pastures"],
        "own_coops": own["coops"], "opp_coops": opp["coops"],
        "own_weeds": own["weeds"], "opp_weeds": opp["weeds"],
    }
    for item in PRODUCTS:
        f[f"market_{item}"] = float(inv.get(item, 0) or 0)
        f[f"price_{item}"] = float(prices.get(item, 0) or 0)
    return f


def _run(candidate: str, opponent: str, seed: int, seat: int):
    import kagsim
    cmod = omod = cparent = oparent = None
    snap = None
    try:
        cfn, cmod, cparent = _load_agent(candidate)
        ofn, omod, oparent = _load_agent(opponent)
        g = kagsim.Game(int(seed))
        while not g.done:
            o0 = dict(g.observe(0))
            o1 = dict(g.observe(1))
            mine = o0 if seat == 0 else o1
            raw_step = mine.get("step")
            step = int(raw_step) if raw_step is not None else int(mine.get("day", 0) or 0) * 24 + int(mine.get("hour", 0) or 0)
            if step == 360 and snap is None:
                snap = _features(mine, seat)
            if seat == 0:
                a0 = _call(cfn, o0)
                a1 = _call(ofn, o1)
            else:
                a0 = _call(ofn, o0)
                a1 = _call(cfn, o1)
            g.step(a0 or PASS, a1 or PASS)
        mine_reward = float(g.reward(seat) or 0.0)
        opp_reward = float(g.reward(1 - seat) or 0.0)
        return {"margin": mine_reward - opp_reward, "reward": mine_reward, "opp_reward": opp_reward, "features": snap or {}}, None
    except Exception:
        return {}, traceback.format_exc(limit=5)
    finally:
        _unload(cmod, cparent)
        _unload(omod, oparent)


def _task(task):
    route0, route1, opp_name, opp_path, seed, seat = task
    r0, e0 = _run(route0, opp_path, seed, seat)
    r1, e1 = _run(route1, opp_path, seed, seat)
    out = {"opponent": opp_name, "seed": seed, "seat": seat}
    if e0 or e1:
        out["errors"] = {"route0": e0, "route1": e1}
        return out
    f0, f1 = r0.get("features", {}), r1.get("features", {})
    stable_keys = ["first_shop", "shops", "market_FERTILIZER", "opp_plants", "own_money", "opp_money", "own_plants"]
    prefix_equal = all(f0.get(k) == f1.get(k) for k in stable_keys)
    out.update({
        "features": f0,
        "prefix_equal": prefix_equal,
        "route0_margin": r0["margin"], "route1_margin": r1["margin"],
        "route0_reward": r0["reward"], "route1_reward": r1["reward"],
        "route0_opp_reward": r0["opp_reward"], "route1_opp_reward": r1["opp_reward"],
        "delta_margin_route1_minus_route0": r1["margin"] - r0["margin"],
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route0", required=True)
    ap.add_argument("--route1", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--start-seed", type=int, default=190001)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import kagsim
    assert getattr(kagsim, "ENGINE_VERSION", "") == "1.32.7", getattr(kagsim, "ENGINE_VERSION", None)
    idle = kagsim.Stream([])
    assert kagsim.run_episode(idle, idle, 11) == (3000.0, 3000.0)

    opponents = {p.stem: str(p.resolve()) for p in sorted(pathlib.Path(args.opponents).glob("*.py"))}
    tasks = []
    for name, path in opponents.items():
        for seed in range(args.start_seed, args.start_seed + args.seeds):
            for seat in (0, 1):
                tasks.append((str(pathlib.Path(args.route0).resolve()), str(pathlib.Path(args.route1).resolve()), name, path, seed, seat))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_task, tasks, chunksize=1))
    bad = [r for r in rows if r.get("errors") or not r.get("prefix_equal")]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    print("engine", kagsim.ENGINE_VERSION, "rows", len(rows), "bad", len(bad), "opponents", sorted(opponents))
    if bad:
        print(json.dumps(bad[:3], indent=2))
        raise SystemExit(f"oracle integrity failed: {len(bad)} rows")

if __name__ == "__main__":
    main()
