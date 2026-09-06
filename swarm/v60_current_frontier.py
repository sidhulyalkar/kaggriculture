from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import statistics
import tarfile
from hashlib import sha256

from kaggle_environments import make

from swarm.v57_public_frontier_selector import _download_public, _money

HANDLES = {
    "MULTI_ROUTE": "flexonafft/kaggriculture-adaptive-replay-agent",
    "SHAPE_PASTURE": "tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
    "FARMING_V3": "lynnsakurai/farming-score-v3-replay-revised",
}


def _game(a: Path, b: Path, seed: int, seat: int):
    env = make("kaggriculture", configuration={"seed": int(seed)}, debug=False)
    agents = [str(a), str(b)] if seat == 0 else [str(b), str(a)]
    try:
        env.run(agents)
        last = env.steps[-1]
        statuses = [str(last[i].status) for i in (0, 1)]
        me = _money(last, seat); opp = _money(last, 1-seat)
        return {"ok": all(x == "DONE" for x in statuses), "statuses": statuses, "cash": me, "opp_cash": opp,
                "margin": me-opp, "score": 1.0 if me > opp else 0.5 if me == opp else 0.0}
    except BaseException as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}


def _pack(src: Path, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tf: tf.add(src, arcname="main.py")
    return {"path": str(out), "bytes": out.stat().st_size, "sha256": sha256(out.read_bytes()).hexdigest()}


def run(output: str, seeds: list[int]):
    out = Path(output); root = out.parent; public = root / "public"
    shutil.rmtree(public, ignore_errors=True); public.mkdir(parents=True, exist_ok=True)
    sources = {}; provenance = {}; failures = {}
    for name, handle in HANDLES.items():
        try: sources[name], provenance[name] = _download_public(handle, public)
        except Exception as exc: failures[name] = f"{type(exc).__name__}: {exc}"[:500]
    rows=[]
    for cname, cpath in sources.items():
        for oname, opath in sources.items():
            if cname == oname: continue
            for seed in seeds:
                for seat in (0,1): rows.append({"candidate": cname, "opponent": oname, "seed": seed, "seat": seat, **_game(cpath, opath, seed, seat)})
    summaries=[]
    for cname in sources:
        rr=[r for r in rows if r["candidate"]==cname]; valid=[r for r in rr if r.get("ok")]
        fam=[]
        for oname in sorted({r["opponent"] for r in valid}):
            g=[r for r in valid if r["opponent"]==oname]
            fam.append({"opponent":oname,"games":len(g),"score_rate":statistics.mean(r["score"] for r in g),"mean_margin":statistics.mean(r["margin"] for r in g)})
        summaries.append({"candidate":cname,"all_valid":len(valid)==len(rr) and bool(rr),"games":len(rr),
                          "score_rate":statistics.mean(r["score"] for r in valid) if valid else 0.0,
                          "mean_margin":statistics.mean(r["margin"] for r in valid) if valid else -1e9,"families":fam})
    multi=next((s for s in summaries if s["candidate"]=="MULTI_ROUTE"),None)
    vs_shape=next((f for f in (multi or {}).get("families",[]) if f["opponent"]=="SHAPE_PASTURE"),None)
    qualified=bool(multi and multi["all_valid"] and vs_shape and vs_shape["score_rate"]>=0.55 and multi["score_rate"]>=0.55 and multi["mean_margin"]>0)
    package=_pack(sources["MULTI_ROUTE"], root/"SUBMISSION_V60_MULTI_ROUTE.tar.gz") if qualified and "MULTI_ROUTE" in sources else None
    payload={"experiment":"V60_CURRENT_FRONTIER","seeds":seeds,"provenance":provenance,"failures":failures,"summaries":summaries,
             "decision":"SUBMIT_MULTI_ROUTE" if qualified else "KEEP_V57","package":package,"rows":rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v60/V60_RESULT.json");ap.add_argument("--seeds",default="6001,6011,6023,6037,6043")
    a=ap.parse_args();p=run(a.output,[int(x) for x in a.seeds.split(',') if x.strip()]);print(json.dumps({"decision":p["decision"],"summaries":p["summaries"],"provenance":p["provenance"],"failures":p["failures"],"package":p["package"]},indent=2,sort_keys=True))
    if p["decision"]!="SUBMIT_MULTI_ROUTE": raise SystemExit(3)

if __name__=="__main__":main()
