#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile

import numpy as np
import pandas as pd

KNOWN = {
    "soil": "kaggriculture-frontier-the-soil-remembers-rain",
    "adaptive": "adaptive-farming-strategy-for-kaggriculture",
    "ranker": "kaggriculture-rank-your-agent",
    "score3094": "3094-score-kaggriculture",
    "v16": "v16-rc5-high-score-8c-4s-premium-market-lead",
    "melon": "kaggriculture-frontier-the-moon-counts-melons",
    "strict": "25-27-strict-future-v27-midgame-meta-reset",
    "findings": "kaggriculture-findings-from-zero-to-top-meta",
    "weed_slip": "weed-slip",
}
V32_NAMES = (
    "SUBMIT_V32_RUNTIME_VERIFIED.tar.gz",
    "SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz",
)
CHECKPOINTS = [96, 192, 288, 384, 480, 576]


def safe_extract(tar_path, dest):
    tar_path, dest = Path(tar_path), Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    mains = []
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            rel = Path(member.name)
            if rel.is_absolute() or ".." in rel.parts or not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fh.read())
            if rel.name == "main.py":
                mains.append(out)
    if not mains:
        return None
    mains.sort(key=lambda p: (len(p.relative_to(dest).parts), str(p)))
    root = dest / "main.py"
    if mains[0] != root:
        shutil.copy2(mains[0], root)
    return root


def copy_tree(src, dst):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in src.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            q = dst / p.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
    main = dst / "main.py"
    return main if main.exists() else None


def find_v32(input_root):
    for name in V32_NAMES:
        hits = list(Path(input_root).rglob(name))
        if hits:
            return hits[0]
    raise FileNotFoundError("Exact V32 archive not found")


def discover(input_root, work):
    input_root, work = Path(input_root), Path(work)
    roots = []
    for p in input_root.rglob("submission.tar.gz"):
        roots.append(p.parent)
    for p in input_root.rglob("main.py"):
        if "__pycache__" not in p.parts:
            roots.append(p.parent)
    roots = list(dict.fromkeys(roots))
    out = {}
    for key, pattern in KNOWN.items():
        matches = [r for r in roots if pattern in str(r).lower()]
        if not matches:
            continue
        src = matches[0]
        dst = work / "agents" / key
        main = None
        if (src / "submission.tar.gz").exists():
            try:
                main = safe_extract(src / "submission.tar.gz", dst)
            except Exception:
                main = None
        if main is None and (src / "main.py").exists():
            main = copy_tree(src, dst)
        if main and main.exists():
            out[key] = {"main": main, "root": main.parent, "source": str(src)}
    return out


WORKER = r'''from pathlib import Path
import importlib.util,json,sys,time,traceback
from copy import deepcopy
mode=sys.argv[1]
aroot=Path(sys.argv[2])
broot=None if sys.argv[3]=='-' else Path(sys.argv[3])
oroot=Path(sys.argv[4])
repo=Path(sys.argv[5])
seed=int(sys.argv[6])
seat=int(sys.argv[7])
cp=int(sys.argv[8])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/'src'))
from src.kagv2.simulator import Game

def load(root,name):
    old=list(sys.path);sys.path.insert(0,str(root))
    try:
        path=root/'main.py'
        spec=importlib.util.spec_from_file_location(name,str(path))
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
        fn=getattr(mod,'agent',None) or getattr(mod,'main',None) or getattr(mod,'v40_frontier_agent',None)
        if callable(fn):return fn
        vals=[v for k,v in vars(mod).items() if callable(v) and getattr(v,'__module__',None)==mod.__name__ and not k.startswith('_')]
        if not vals:raise RuntimeError('no callable '+str(path))
        return vals[-1]
    finally:
        sys.path[:]=old

def call(fn,obs):
    try:return fn(obs)
    except TypeError:return fn(obs,None)

try:
    A=load(aroot,'genome_a')
    B=load(broot,'genome_b') if broot else None
    O=load(oroot,'genome_opp')
    timing=[]
    if mode=='base':
        def C(obs,configuration=None):
            t=time.perf_counter()
            try:return call(A,obs)
            finally:timing.append(time.perf_counter()-t)
    else:
        def C(obs,configuration=None):
            t=time.perf_counter()
            try:
                aa=call(A,deepcopy(obs))
                bb=call(B,deepcopy(obs))
                step=int(obs.get('step',0) or 0)
                return aa if step<cp else bb
            finally:timing.append(time.perf_counter()-t)
    agents=[C,O] if seat==0 else [O,C]
    cash=Game(seed=seed).run(agents)
    cc,oc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0])
    print(json.dumps({'ok':True,'cash':float(cc),'opp_cash':float(oc),
      'score':1.0 if cc>oc else .5 if cc==oc else 0.0,'margin':float(cc-oc),
      'mean_ms':1000*sum(timing)/max(1,len(timing)),
      'max_ms':1000*max(timing) if timing else 0.0}))
except BaseException as e:
    print(json.dumps({'ok':False,'error':repr(e),'traceback':traceback.format_exc()[-2500:]}))
'''


def run_one(worker, cand, opp_root, repo, seed, seat):
    cmd = [
        sys.executable,
        str(worker),
        cand["mode"],
        str(cand["a"]),
        str(cand.get("b") or "-"),
        str(opp_root),
        str(repo),
        str(seed),
        str(seat),
        str(int(cand.get("cp", 0))),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    for line in reversed(r.stdout.splitlines()):
        try:
            return json.loads(line)
        except Exception:
            pass
    return {"ok": False, "error": (r.stderr or r.stdout)[-2500:]}


def tournament(candidates, opponents, seeds, worker, repo, workers):
    jobs = [
        (cn, c, on, oroot, seed, seat)
        for cn, c in candidates.items()
        for on, oroot in opponents.items()
        for seed in seeds
        for seat in (0, 1)
    ]
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {
            ex.submit(run_one, worker, c, oroot, repo, seed, seat): (cn, on, seed, seat)
            for cn, c, on, oroot, seed, seat in jobs
        }
        for i, f in enumerate(as_completed(fut), 1):
            cn, on, seed, seat = fut[f]
            rows.append({"candidate": cn, "opponent": on, "seed": seed, "seat": seat, **f.result()})
            if i % 50 == 0 or i == len(fut):
                print(" completed", i, "/", len(fut))
    return pd.DataFrame(rows)


def summarize(df, control=None):
    keys = ["opponent", "seed", "seat"]
    ctl = None
    rows = []
    if control and control in set(df.candidate):
        ctl = df[(df.candidate == control) & (df.ok == True)][keys + ["score", "margin", "cash"]].rename(
            columns={"score": "ctl_score", "margin": "ctl_margin", "cash": "ctl_cash"}
        )
    for name, g in df.groupby("candidate"):
        good = g[g.ok == True].copy()
        r = {
            "candidate": name,
            "games": len(g),
            "valid_games": len(good),
            "invalid_games": int((g.ok != True).sum()),
            "mean_score": float(good.score.mean()) if len(good) else np.nan,
            "mean_cash": float(good.cash.mean()) if len(good) else np.nan,
            "mean_margin": float(good.margin.mean()) if len(good) else np.nan,
            "mean_ms": float(good.mean_ms.mean()) if len(good) else np.nan,
            "max_ms": float(good.max_ms.max()) if len(good) else np.nan,
        }
        if len(good):
            by = good.groupby("opponent").score.mean()
            r["worst_family_score"] = float(by.min())
            direct = good[good.opponent == "v32"]
            r["direct_v32_score"] = float(direct.score.mean()) if len(direct) else np.nan
        else:
            r["worst_family_score"] = np.nan
            r["direct_v32_score"] = np.nan
        if ctl is not None:
            m = good.merge(ctl, on=keys, how="inner")
            if len(m):
                r["paired_games"] = len(m)
                r["delta_score"] = float((m.score - m.ctl_score).mean())
                r["delta_margin"] = float((m.margin - m.ctl_margin).mean())
                r["worst_delta"] = float(
                    m.assign(d=m.score - m.ctl_score).groupby("opponent").d.mean().min()
                )
            else:
                r["paired_games"] = 0
                r["delta_score"] = np.nan
                r["delta_margin"] = np.nan
                r["worst_delta"] = np.nan
        rows.append(r)
    z = pd.DataFrame(rows)
    sort = ["mean_score", "mean_margin"] if ctl is None else ["delta_score", "mean_score", "delta_margin"]
    return z.sort_values(sort, ascending=False).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default="/kaggle/input")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work", default="/kaggle/working/v41_frontier_genome")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 2))
    args = ap.parse_args()
    work, repo = Path(args.work), Path(args.repo)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    v32tar = find_v32(args.input_root)
    v32main = safe_extract(v32tar, work / "agents" / "v32")
    agents = discover(args.input_root, work)
    agents["v32"] = {"main": v32main, "root": v32main.parent, "source": str(v32tar)}
    print("discovered:", sorted(agents))
    (work / "V41_INPUT_MANIFEST.json").write_text(
        json.dumps({k: {"source": v["source"], "root": str(v["root"])} for k, v in agents.items()}, indent=2)
    )
    worker = work / "genome_worker.py"
    worker.write_text(WORKER)

    for name, value in agents.items():
        if name == "v32":
            continue
        r = run_one(worker, {"mode": "base", "a": value["root"]}, agents["v32"]["root"], repo, 41001, 0)
        print("preflight", name, r.get("ok"), r.get("score"), r.get("error", ""))

    base_names = ["v32"] + [
        x for x in ("weed_slip", "score3094", "melon", "soil", "ranker", "strict", "adaptive", "v16", "findings")
        if x in agents
    ]
    base_candidates = {n: {"mode": "base", "a": agents[n]["root"]} for n in base_names}
    base_opponents = {n: agents[n]["root"] for n in base_names}

    print("=== V41 STAGE A: FRONTIER PARENT QUALIFICATION ===")
    parent_games = tournament(base_candidates, base_opponents, [41011, 41017], worker, repo, args.workers)
    parent_games.to_csv(work / "V41_PARENT_GAMES.csv", index=False)
    parent_table = summarize(parent_games)
    parent_table.to_csv(work / "V41_PARENT_TABLE.csv", index=False)
    print(parent_table.to_string(index=False))
    frontier = parent_table[(parent_table.candidate != "v32") & (parent_table.invalid_games == 0)].head(3).candidate.tolist()
    print("selected frontier parents:", frontier)
    if not frontier:
        raise RuntimeError("No valid external frontier parent")

    genome = {}
    for parent in frontier:
        for cp in CHECKPOINTS:
            genome[f"{parent.upper()}_TO_V32_T{cp}"] = {
                "mode": "a_to_b", "a": agents[parent]["root"], "b": agents["v32"]["root"], "cp": cp
            }
            genome[f"V32_TO_{parent.upper()}_T{cp}"] = {
                "mode": "a_to_b", "a": agents["v32"]["root"], "b": agents[parent]["root"], "cp": cp
            }

    control = {"V32_CONTROL": {"mode": "base", "a": agents["v32"]["root"]}}
    screen_opponents = {n: agents[n]["root"] for n in ["v32", *frontier]}
    print("=== V41 STAGE B: CAUSAL EPOCH TRANSPLANTS ===")
    screen_games = tournament({**control, **genome}, screen_opponents, [41101, 41107], worker, repo, args.workers)
    screen_games.to_csv(work / "V41_GENOME_SCREEN_GAMES.csv", index=False)
    screen = summarize(screen_games, "V32_CONTROL")
    screen.to_csv(work / "V41_GENOME_SCREEN.csv", index=False)
    print(screen.head(20).to_string(index=False))
    eligible = screen[(screen.candidate != "V32_CONTROL") & (screen.invalid_games == 0)].head(4).candidate.tolist()
    if not eligible:
        raise RuntimeError("No valid genome hybrids")

    broad = ["v32"] + [
        x for x in ("weed_slip", "score3094", "melon", "soil", "ranker", "strict", "adaptive", "v16", "findings")
        if x in agents
    ]
    held_opponents = {n: agents[n]["root"] for n in broad}
    held_candidates = {"V32_CONTROL": control["V32_CONTROL"], **{n: genome[n] for n in eligible}}
    print("=== V41 STAGE C: HELD-OUT BROAD ZOO ===")
    held_games = tournament(held_candidates, held_opponents, [41201, 41209, 41221], worker, repo, args.workers)
    held_games.to_csv(work / "V41_GENOME_HELDOUT_GAMES.csv", index=False)
    held = summarize(held_games, "V32_CONTROL")
    held.to_csv(work / "V41_GENOME_HELDOUT.csv", index=False)
    print(held.to_string(index=False))

    children = held[(held.candidate != "V32_CONTROL") & (held.invalid_games == 0)]
    best = children.iloc[0] if len(children) else None
    if (
        best is not None
        and best.get("direct_v32_score", 0) >= 0.55
        and best.get("delta_score", -9) >= 0.02
        and best.get("worst_family_score", 0) >= 0.40
    ):
        decision = "BUILD_V41_1"
        reason = "epoch transplant beats V32 broadly enough for a submission-builder follow-up"
    elif best is not None and best.get("delta_score", -9) > 0:
        decision = "REFINE_GENOME"
        reason = "positive broad held-out signal, but promotion gates are not yet strong enough"
    else:
        decision = "MINE_PARENT"
        reason = "no epoch transplant beat V32 broadly; target within-parent mechanisms rather than switches"

    report = {
        "version": 41,
        "name": "Frontier Genome",
        "decision": decision,
        "reason": reason,
        "frontier_parents": frontier,
        "screen_checkpoints": CHECKPOINTS,
        "best_candidate": None if best is None else str(best.candidate),
        "best_metrics": {} if best is None else {k: (None if pd.isna(v) else v) for k, v in best.to_dict().items()},
        "v32_archive": str(v32tar),
    }
    (work / "V41_DECISION.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
