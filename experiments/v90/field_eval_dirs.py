from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import statistics
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _discover(root: pathlib.Path):
    agents = {}
    for p in sorted(root.glob("*.py")):
        if not p.name.startswith("_"):
            agents[p.stem] = str(p.resolve())
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        p = d / "main.py"
        if p.exists():
            agents[d.name] = str(p.resolve())
    return agents


def _load(path: str):
    p = pathlib.Path(path).resolve()
    parent = str(p.parent)
    name = "v90f_" + hashlib.sha1(f"{p}:{os.getpid()}:{os.urandom(8).hex()}".encode()).hexdigest()[:20]
    sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, p)
    if not spec or not spec.loader:
        raise RuntimeError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if not callable(fn):
        raise RuntimeError(f"{path}: missing agent")
    return fn, name, parent


def _unload(name, parent):
    if name:
        sys.modules.pop(name, None)
    if parent:
        try:
            sys.path.remove(parent)
        except ValueError:
            pass


def _call(fn, obs):
    try:
        return fn(obs)
    except TypeError:
        return fn(obs, {"episodeSteps": 720})


def _game(task):
    a_name, a_path, b_name, b_path, seed = task
    import kagsim
    am = bm = ap = bp = None
    try:
        af, am, ap = _load(a_path)
        bf, bm, bp = _load(b_path)
        g = kagsim.Game(int(seed))
        while not g.done:
            o0 = dict(g.observe(0))
            o1 = dict(g.observe(1))
            g.step(_call(af, o0) or PASS, _call(bf, o1) or PASS)
        return {"a": a_name, "b": b_name, "seed": seed, "r0": float(g.reward(0) or 0), "r1": float(g.reward(1) or 0), "error": None}
    except Exception:
        return {"a": a_name, "b": b_name, "seed": seed, "r0": 0.0, "r1": 0.0, "error": traceback.format_exc(limit=4)}
    finally:
        _unload(am, ap)
        _unload(bm, bp)


def _score(m):
    return 1.0 if m > 0 else 0.5 if m == 0 else 0.0


def _summarize(rows, names):
    acc = {n: {"wins": 0, "losses": 0, "ties": 0, "margins": [], "per": defaultdict(list), "seat": {0: [], 1: []}, "errors": 0} for n in names}

    def add(me, opp, seat, margin, err):
        x = acc[me]
        x["margins"].append(margin)
        x["per"][opp].append(margin)
        x["seat"][seat].append(margin)
        x["errors"] += int(bool(err))
        x["wins"] += int(margin > 0)
        x["losses"] += int(margin < 0)
        x["ties"] += int(margin == 0)

    for r in rows:
        m = r["r0"] - r["r1"]
        add(r["a"], r["b"], 0, m, r["error"])
        add(r["b"], r["a"], 1, -m, r["error"])

    out = {}
    for n, x in acc.items():
        games = len(x["margins"])
        bt_score = (x["wins"] + 0.5 * x["ties"]) / max(1, games)
        per = {
            opp: {
                "n": len(ms),
                "bt": sum(_score(m) for m in ms) / len(ms),
                "mean_margin": statistics.mean(ms),
            }
            for opp, ms in x["per"].items()
        }
        worst = min((v["bt"] for v in per.values()), default=0.0)
        mean_margin = statistics.mean(x["margins"]) if x["margins"] else 0.0
        seat0 = sum(_score(m) for m in x["seat"][0]) / max(1, len(x["seat"][0]))
        seat1 = sum(_score(m) for m in x["seat"][1]) / max(1, len(x["seat"][1]))
        out[n] = {
            "games": games,
            "wins": x["wins"],
            "losses": x["losses"],
            "ties": x["ties"],
            "bt_score": bt_score,
            "mean_margin": mean_margin,
            "median_margin": statistics.median(x["margins"]) if x["margins"] else 0.0,
            "worst_opponent_bt": worst,
            "seat0_bt": seat0,
            "seat1_bt": seat1,
            "seat_gap": abs(seat0 - seat1),
            "errors": x["errors"],
            "per_opponent": per,
            "robust_score": 0.68 * bt_score + 0.20 * worst + 0.06 * (1 - abs(seat0 - seat1)) + 0.06 * ((math.tanh(mean_margin / 25000) + 1) / 2),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena", required=True)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start-seed", type=int, default=210001)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import kagsim
    assert getattr(kagsim, "ENGINE_VERSION", "") == "1.32.7"
    agents = _discover(pathlib.Path(args.arena))
    names = sorted(agents)
    if len(names) < 2:
        raise SystemExit(names)
    tasks = []
    for seed in range(args.start_seed, args.start_seed + args.seeds):
        for a in names:
            for b in names:
                if a != b:
                    tasks.append((a, agents[a], b, agents[b], seed))
    print("engine", kagsim.ENGINE_VERSION, "agents", names, "games", len(tasks))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_game, tasks, chunksize=2))
    summary = _summarize(rows, names)
    ranked = sorted(summary, key=lambda n: summary[n]["robust_score"], reverse=True)
    payload = {
        "engine": kagsim.ENGINE_VERSION,
        "seeds": [args.start_seed, args.start_seed + args.seeds - 1],
        "ranking": ranked,
        "summary": summary,
        "errors": sum(bool(r["error"]) for r in rows),
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    out.with_suffix(".jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    for i, n in enumerate(ranked, 1):
        s = summary[n]
        print(f"{i:2d} {n:28s} BT={s['bt_score']:.3f} worst={s['worst_opponent_bt']:.3f} margin={s['mean_margin']:+.0f} seat={s['seat0_bt']:.3f}/{s['seat1_bt']:.3f} err={s['errors']}")
    if payload["errors"]:
        raise SystemExit(f"field had {payload['errors']} game errors")

if __name__ == "__main__":
    main()
