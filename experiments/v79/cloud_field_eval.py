from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import statistics
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _load_agent(path: str):
    """Fresh module per episode so module globals cannot leak between games."""
    p = Path(path).resolve()
    key = f"{p}:{os.getpid()}:{os.urandom(6).hex()}"
    name = "v79_agent_" + hashlib.sha1(key.encode()).hexdigest()[:16]
    parent = str(p.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {p}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if not callable(fn):
        raise RuntimeError(f"{p} has no callable agent")
    return fn, name


def _call(fn, obs):
    try:
        return fn(obs), None
    except TypeError:
        # Some Kaggle submissions retain the optional configuration argument.
        try:
            return fn(obs, {}), None
        except Exception:
            return PASS, traceback.format_exc(limit=2)
    except Exception:
        return PASS, traceback.format_exc(limit=2)


def _clean_telemetry(t):
    if not isinstance(t, dict):
        return {}
    out = {}
    for k, v in t.items():
        if isinstance(v, (int, float)):
            out[str(k)] = float(v)
    return out


def _game(task):
    a_name, a_path, b_name, b_path, seed, mode = task
    import kagsim

    a_fn = b_fn = None
    a_mod = b_mod = None
    errors = [0, 0]
    first_error = [None, None]
    try:
        a_fn, a_mod = _load_agent(a_path)
        b_fn, b_mod = _load_agent(b_path)
        g = kagsim.Game(int(seed))
        while not g.done:
            o0 = dict(g.observe(0))
            o1 = dict(g.observe(1))
            if mode == "ladder_real":
                # Public ladder audit: seat 1 can receive an unset step field.
                # day/hour remain valid, so robust agents should derive clock from them.
                o1["step"] = None
            a, ea = _call(a_fn, o0)
            b, eb = _call(b_fn, o1)
            if ea:
                errors[0] += 1
                first_error[0] = first_error[0] or ea
            if eb:
                errors[1] += 1
                first_error[1] = first_error[1] or eb
            g.step(a or PASS, b or PASS)
        r0 = float(g.reward(0) or 0.0)
        r1 = float(g.reward(1) or 0.0)
        try:
            t0 = _clean_telemetry(g.telemetry(0))
            t1 = _clean_telemetry(g.telemetry(1))
        except Exception:
            t0 = t1 = {}
        return {
            "a": a_name, "b": b_name, "seed": int(seed), "mode": mode,
            "r0": r0, "r1": r1,
            "errors0": errors[0], "errors1": errors[1],
            "first_error0": first_error[0], "first_error1": first_error[1],
            "telemetry0": t0, "telemetry1": t1,
        }
    except Exception:
        return {
            "a": a_name, "b": b_name, "seed": int(seed), "mode": mode,
            "r0": 0.0, "r1": 0.0,
            "errors0": 999999, "errors1": 999999,
            "fatal": traceback.format_exc(limit=4),
            "telemetry0": {}, "telemetry1": {},
        }
    finally:
        if a_mod:
            sys.modules.pop(a_mod, None)
        if b_mod:
            sys.modules.pop(b_mod, None)


def _quantile(xs, q):
    if not xs:
        return 0.0
    ys = sorted(xs)
    if len(ys) == 1:
        return float(ys[0])
    pos = (len(ys) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return float(ys[lo])
    w = pos - lo
    return float(ys[lo] * (1 - w) + ys[hi] * w)


def _cvar(xs, q=0.10):
    if not xs:
        return 0.0
    ys = sorted(xs)
    n = max(1, int(math.ceil(len(ys) * q)))
    return float(statistics.mean(ys[:n]))


def _safe_mean(xs):
    return float(statistics.mean(xs)) if xs else 0.0


def _summarize(rows, names):
    acc = {n: {
        "margins": [], "wins": 0, "losses": 0, "ties": 0,
        "seat": {0: [0, 0, []], 1: [0, 0, []]},
        "mode": defaultdict(lambda: [0, 0, []]),
        "per_opp": defaultdict(lambda: [0, 0, []]),
        "errors": 0,
        "telemetry": defaultdict(float),
    } for n in names}

    def add(me, opp, seat, mode, mine, theirs, errors, telem):
        a = acc[me]
        m = mine - theirs
        a["margins"].append(m)
        if m > 0:
            a["wins"] += 1
        elif m < 0:
            a["losses"] += 1
        else:
            a["ties"] += 1
        a["seat"][seat][0] += int(m > 0)
        a["seat"][seat][1] += 1
        a["seat"][seat][2].append(m)
        a["mode"][mode][0] += int(m > 0)
        a["mode"][mode][1] += 1
        a["mode"][mode][2].append(m)
        a["per_opp"][opp][0] += int(m > 0)
        a["per_opp"][opp][1] += 1
        a["per_opp"][opp][2].append(m)
        a["errors"] += int(errors)
        for k, v in (telem or {}).items():
            a["telemetry"][k] += float(v)

    for r in rows:
        add(r["a"], r["b"], 0, r["mode"], r["r0"], r["r1"], r.get("errors0", 0), r.get("telemetry0", {}))
        add(r["b"], r["a"], 1, r["mode"], r["r1"], r["r0"], r.get("errors1", 0), r.get("telemetry1", {}))

    out = {}
    for name, a in acc.items():
        games = a["wins"] + a["losses"] + a["ties"]
        wr = a["wins"] / max(1, games)
        opp_wrs = []
        per_opp = {}
        for opp, (w, g, ms) in a["per_opp"].items():
            owr = w / max(1, g)
            opp_wrs.append(owr)
            per_opp[opp] = {
                "wins": w, "games": g, "win_rate": owr,
                "margin_mean": _safe_mean(ms), "margin_median": float(statistics.median(ms)) if ms else 0.0,
            }
        s0 = a["seat"][0][0] / max(1, a["seat"][0][1])
        s1 = a["seat"][1][0] / max(1, a["seat"][1][1])
        worst_opp = min(opp_wrs) if opp_wrs else 0.0
        mean_margin = _safe_mean(a["margins"])
        p10 = _quantile(a["margins"], 0.10)
        cvar10 = _cvar(a["margins"], 0.10)
        error_rate = a["errors"] / max(1, games * 719)
        # Composite only ranks the arena. Raw metrics remain authoritative.
        margin_term = math.tanh(mean_margin / 25000.0)
        downside_term = math.tanh(cvar10 / 35000.0)
        seat_balance = 1.0 - abs(s0 - s1)
        robust_score = (
            0.52 * wr +
            0.16 * worst_opp +
            0.10 * seat_balance +
            0.12 * (margin_term + 1.0) / 2.0 +
            0.10 * (downside_term + 1.0) / 2.0 -
            min(0.25, 20.0 * error_rate)
        )
        out[name] = {
            "games": games,
            "wins": a["wins"], "losses": a["losses"], "ties": a["ties"],
            "win_rate": wr,
            "margin_mean": mean_margin,
            "margin_median": float(statistics.median(a["margins"])) if a["margins"] else 0.0,
            "margin_p10": p10,
            "margin_cvar10": cvar10,
            "margin_min": min(a["margins"]) if a["margins"] else 0.0,
            "seat0_win_rate": s0, "seat1_win_rate": s1,
            "seat_gap": abs(s0 - s1),
            "worst_opponent_win_rate": worst_opp,
            "errors": a["errors"], "error_rate_per_turn": error_rate,
            "robust_score": robust_score,
            "modes": {
                mode: {"wins": x[0], "games": x[1], "win_rate": x[0] / max(1, x[1]), "margin_mean": _safe_mean(x[2])}
                for mode, x in a["mode"].items()
            },
            "per_opponent": per_opp,
            "telemetry_totals": dict(a["telemetry"]),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena", required=True, help="directory of self-contained *.py agents")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start-seed", type=int, default=91001)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--modes", default="standard,ladder_real")
    ap.add_argument("--out", default="experiments/v79/results")
    args = ap.parse_args()

    import kagsim
    assert getattr(kagsim, "ENGINE_VERSION", "") == "1.32.7", getattr(kagsim, "ENGINE_VERSION", None)
    idle = kagsim.Stream([])
    assert kagsim.run_episode(idle, idle, 11) == (3000.0, 3000.0)

    arena = Path(args.arena)
    agents = {p.stem: str(p.resolve()) for p in sorted(arena.glob("*.py")) if not p.name.startswith("_")}
    if len(agents) < 2:
        raise SystemExit(f"need >=2 agents in {arena}; found {list(agents)}")
    names = sorted(agents)
    seeds = list(range(args.start_seed, args.start_seed + args.seeds))
    modes = [x.strip() for x in args.modes.split(",") if x.strip()]

    # Ordered pairs means every agent appears in both seats on every seed.
    tasks = []
    for mode in modes:
        for seed in seeds:
            for a in names:
                for b in names:
                    if a != b:
                        tasks.append((a, agents[a], b, agents[b], seed, mode))

    print(f"engine={kagsim.ENGINE_VERSION} agents={len(names)} seeds={len(seeds)} modes={modes} games={len(tasks)} workers={args.workers}")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(_game, tasks, chunksize=2))

    summary = _summarize(rows, names)
    ranked = sorted(summary.items(), key=lambda kv: kv[1]["robust_score"], reverse=True)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "games.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    payload = {
        "engine": kagsim.ENGINE_VERSION,
        "seeds": seeds,
        "modes": modes,
        "agents": names,
        "ranking": [n for n, _ in ranked],
        "summary": summary,
    }
    (outdir / "field_results.json").write_text(json.dumps(payload, indent=2) + "\n")

    fields = [
        "rank", "agent", "robust_score", "win_rate", "worst_opponent_win_rate",
        "seat0_win_rate", "seat1_win_rate", "seat_gap", "margin_mean",
        "margin_median", "margin_p10", "margin_cvar10", "errors",
    ]
    with (outdir / "summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, (name, s) in enumerate(ranked, 1):
            w.writerow({"rank": i, "agent": name, **{k: s.get(k) for k in fields if k not in ("rank", "agent")}})

    print("\n=== ROBUST FIELD RANKING ===")
    for i, (name, s) in enumerate(ranked, 1):
        modes_txt = " ".join(f"{m}:{d['win_rate']:.3f}" for m, d in sorted(s["modes"].items()))
        print(
            f"{i:2d} {name[:45]:45s} score={s['robust_score']:.4f} "
            f"WR={s['win_rate']:.3f} worst={s['worst_opponent_win_rate']:.3f} "
            f"seat={s['seat0_win_rate']:.3f}/{s['seat1_win_rate']:.3f} "
            f"margin={s['margin_mean']:+.0f} cvar10={s['margin_cvar10']:+.0f} "
            f"errors={s['errors']} {modes_txt}"
        )


if __name__ == "__main__":
    main()
