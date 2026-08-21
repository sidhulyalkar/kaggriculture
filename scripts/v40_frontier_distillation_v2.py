#!/usr/bin/env python3
"""Reliability wrapper for V40 Frontier Distillation.

This wrapper fixes the first Kaggle run's tournament infrastructure failure
without changing any V40 candidate economics. The original worker imported
candidate files without putting each extracted submission root on sys.path.
That made exact V32 fail on every game because its nested runtime package could
not be resolved. Every other candidate then failed exactly the eight games in
which V32 was the opponent, so paired comparisons were impossible.

V2 patches only the tournament harness:
- insert candidate/opponent roots on sys.path before module execution;
- tag failures by candidate-load/opponent-load/game stage;
- run a tiny core-control preflight before the 448-game screen;
- probe optional public opponents and drop only broken optional families;
- preserve V32 and the frontier parent as mandatory controls.

The V40 policy family, promotion thresholds, seeds, and final runtime gates stay
unchanged.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import v40_frontier_distillation as base


FIXED_MATCH_WORKER = r'''from pathlib import Path
import importlib.util,json,sys,time,traceback
c=Path(sys.argv[1]);o=Path(sys.argv[2]);repo=Path(sys.argv[3]);seed=int(sys.argv[4]);seat=int(sys.argv[5])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/"src"))
from src.kagv2.simulator import Game

def load(path,name,stage):
    path=Path(path)
    # Critical V2 fix: exact V32 contains nested runtime files. Python must be
    # able to resolve imports relative to the extracted submission root.
    sys.path.insert(0,str(path.parent))
    try:
        spec=importlib.util.spec_from_file_location(name,str(path))
        if spec is None or spec.loader is None:
            raise RuntimeError("no import spec for "+str(path))
        m=importlib.util.module_from_spec(spec)
        sys.modules[name]=m
        spec.loader.exec_module(m)
        f=getattr(m,"v40_frontier_agent",None) or getattr(m,"agent",None) or getattr(m,"main",None)
        if callable(f):return f
        vals=[x for k,x in vars(m).items() if callable(x) and getattr(x,"__module__",None)==m.__name__ and not k.startswith("_")]
        if not vals:raise RuntimeError("no callable in "+str(path))
        return vals[-1]
    except BaseException as e:
        print(json.dumps({"ok":False,"stage":stage,"error":repr(e),"traceback":traceback.format_exc()[-2500:]}))
        raise SystemExit(0)

try:
    a=load(c,"v40c","candidate_load")
    b=load(o,"v40o","opponent_load")
    tt=[]
    def call(fn,obs,configuration=None):
        try:return fn(obs,configuration)
        except TypeError:return fn(obs)
    def A(obs,configuration=None):
        t=time.perf_counter()
        try:return call(a,obs,configuration)
        finally:tt.append(time.perf_counter()-t)
    def B(obs,configuration=None):
        return call(b,obs,configuration)
    agents=[A,B] if seat==0 else [B,A]
    cash=Game(seed=seed).run(agents)
    ac,bc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0])
    print(json.dumps({"ok":True,"stage":"complete","cash":float(ac),"opp_cash":float(bc),
      "score":1.0 if ac>bc else .5 if ac==bc else 0.0,"margin":float(ac-bc),
      "mean_ms":1000*sum(tt)/max(1,len(tt)),"max_ms":1000*max(tt) if tt else 0.0}))
except SystemExit:
    raise
except BaseException as e:
    print(json.dumps({"ok":False,"stage":"game","error":repr(e),"traceback":traceback.format_exc()[-2500:]}))
'''

base.MATCH_WORKER = FIXED_MATCH_WORKER
_original_tournament = base.tournament
_preflight_done = False


def _pretty_failure(label, result):
    return {
        "label": label,
        "stage": result.get("stage"),
        "error": result.get("error"),
        "traceback": result.get("traceback", "")[-1200:],
    }


def guarded_tournament(cands, opponents, names, opp_names, seeds, worker, repo, workers):
    """Fail fast on control infrastructure and quarantine broken optional bots."""
    global _preflight_done
    active = list(opp_names)
    if not _preflight_done:
        _preflight_done = True
        seed = int(seeds[0]) if seeds else 40001
        checks = [
            ("V32 candidate -> frontier", cands["V32_CONTROL"], opponents["frontier_parent"], 0),
            ("V32 opponent <- frontier", cands["FRONTIER_PARENT"], opponents["v32"], 0),
            ("V40 child -> V32", cands["V40_FERT_FLYWHEEL"], opponents["v32"], 1),
        ]
        failures = []
        print("=== V40 V2 CORE PREFLIGHT ===")
        for label, cand, opp, seat in checks:
            r = base.run_match(worker, cand, opp, repo, seed, seat, timeout=180)
            print(label, "PASS" if r.get("ok") else "FAIL", r.get("stage", ""), r.get("error", ""))
            if not r.get("ok"):
                failures.append(_pretty_failure(label, r))
        if failures:
            out = Path(worker).parent / "V40_INFRA_FAILURE.json"
            out.write_text(json.dumps({"core_preflight": failures}, indent=2))
            raise RuntimeError("V40 core preflight failed; see "+str(out))

        # Optional public agents should never poison the whole research run.
        mandatory = {"v32", "frontier_parent"}
        quarantined = []
        for opp_name in list(active):
            if opp_name in mandatory:
                continue
            r = base.run_match(worker, cands["FRONTIER_PARENT"], opponents[opp_name], repo, seed, 0, timeout=180)
            if not r.get("ok"):
                quarantined.append(_pretty_failure(opp_name, r))
                active.remove(opp_name)
        qpath = Path(worker).parent / "opponent_preflight.json"
        qpath.write_text(json.dumps({"active": active, "quarantined": quarantined}, indent=2))
        print("active opponents after preflight:", active)
        if quarantined:
            print("quarantined optional opponents:", [x["label"] for x in quarantined])

    return _original_tournament(cands, opponents, names, active, seeds, worker, repo, workers)


base.tournament = guarded_tournament

if __name__ == "__main__":
    base.main()
