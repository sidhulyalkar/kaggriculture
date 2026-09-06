from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import statistics
import tarfile

from kaggle_environments import make

from submission.predictive_agent import PredictiveMind
from swarm.v77_live_meta_route_search import _extract_main_from_root, recover_soil_parent

CANDIDATES={
    "ADAPTIVE_V16":"tetsutani/adaptive-farming-strategy-for-kaggriculture/versions/16",
    "MULTIROUTE_V59":"flexonafft/kaggriculture-adaptive-replay-agent/versions/59",
    "SHAPE_CURRENT":"tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
}


def recover(handle:str,root:Path):
    import kagglehub
    dest=root/handle.replace('/','__');shutil.rmtree(dest,ignore_errors=True);dest.mkdir(parents=True,exist_ok=True)
    got=kagglehub.notebook_output_download(handle,output_dir=str(dest),force_download=True)
    base=Path(got) if got else dest;src=_extract_main_from_root(base) or _extract_main_from_root(dest)
    if not src:raise RuntimeError(f"no main.py in {handle}")
    compile(src,f"<{handle}>","exec");path=root/(handle.replace('/','__')+".py");path.write_text(src,encoding="utf-8")
    return path,{"handle":handle,"bytes":len(src),"source_sha256":sha256(src.encode()).hexdigest()}


def _money(last,player):
    for owner in (0,1):
        try:
            obs=last[owner].observation;farms=obs["farms"] if isinstance(obs,dict) else obs.farms;farm=farms[player]
            return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
        except Exception:pass
    try:return float(last[player].reward or 0)
    except Exception:return 0.0


def _mind_agent(mind):
    def f(obs,configuration=None):return mind.act(obs)
    return f


def run_game(candidate:Path,opponent,seed:int,seat:int):
    env=make("kaggriculture",configuration={"seed":int(seed)},debug=False)
    oa=_mind_agent(opponent()) if callable(opponent) and not isinstance(opponent,str) else str(opponent)
    agents=[str(candidate),oa] if seat==0 else [oa,str(candidate)]
    try:
        env.run(agents);last=env.steps[-1];statuses=[str(last[i].status) for i in (0,1)];me=_money(last,seat);op=_money(last,1-seat)
        return {"ok":all(x=="DONE" for x in statuses),"statuses":statuses,"cash":me,"opp_cash":op,"margin":me-op,"score":1.0 if me>op else .5 if me==op else 0.0}
    except BaseException as exc:return {"ok":False,"error":f"{type(exc).__name__}: {exc}"[:500]}


def package(src:Path,out:Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(out,"w:gz") as tf:tf.add(src,arcname="main.py")
    return {"path":str(out),"bytes":out.stat().st_size,"sha256":sha256(out.read_bytes()).hexdigest()}


def run(output:str,seeds:list[int]):
    out=Path(output);root=out.parent;public=root/"public";public.mkdir(parents=True,exist_ok=True)
    sources={};provenance={};failures={}
    for name,handle in CANDIDATES.items():
        try:sources[name],provenance[name]=recover(handle,public)
        except Exception as exc:failures[name]=f"{type(exc).__name__}: {exc}"[:500]
    soil=None;soil_meta={"status":"unavailable"}
    try:
        src,soil_meta=recover_soil_parent(root/"soil",max_version=1);soil=root/"soil.py";soil.write_text(src,encoding="utf-8")
    except Exception as exc:soil_meta={"status":"unavailable","error":repr(exc)[:300]}
    rows=[]
    for cname,cpath in sources.items():
        opponents=[("INCUMBENT",PredictiveMind)]
        if soil:opponents.append(("SOIL",str(soil)))
        for oname,opath in sources.items():
            if oname!=cname:opponents.append((oname,str(opath)))
        for oname,opp in opponents:
            for seed in seeds:
                for seat in (0,1):rows.append({"candidate":cname,"opponent":oname,"seed":seed,"seat":seat,**run_game(cpath,opp,seed,seat)})
    summaries=[]
    for name in sources:
        rr=[r for r in rows if r["candidate"]==name];valid=[r for r in rr if r.get("ok")];families=[]
        for opp in sorted({r["opponent"] for r in valid}):
            q=[r for r in valid if r["opponent"]==opp];families.append({"opponent":opp,"games":len(q),"score_rate":statistics.mean(r["score"] for r in q),"mean_margin":statistics.mean(r["margin"] for r in q)})
        overall=statistics.mean(r["score"] for r in valid) if valid else 0.0;margin=statistics.mean(r["margin"] for r in valid) if valid else -1e9
        inc=next((f for f in families if f["opponent"]=="INCUMBENT"),None);shape=next((f for f in families if f["opponent"]=="SHAPE_CURRENT"),None)
        passed=bool(len(valid)==len(rr) and rr and inc and inc["score_rate"]>=.50 and overall>=.50 and (name=="SHAPE_CURRENT" or not shape or shape["score_rate"]>=.33))
        summaries.append({"candidate":name,"games":len(rr),"all_valid":len(valid)==len(rr) and bool(rr),"score_rate":overall,"mean_margin":margin,"incumbent":inc,"vs_shape":shape,"families":families,"passed":passed})
    qualified=sorted((s for s in summaries if s["passed"]),key=lambda s:(s["score_rate"],s["mean_margin"]),reverse=True);selected=[s["candidate"] for s in qualified[:2]]
    packages={name:package(sources[name],root/f"SUBMISSION_V59_{i}_{name}.tar.gz") for i,name in enumerate(selected,1)}
    payload={"experiment":"V59_HISTORICAL_FRONTIER","decision":"READY" if selected else "HOLD","seeds":seeds,"provenance":provenance,"failures":failures,"soil":soil_meta,"summaries":summaries,"selected":selected,"packages":packages,"rows":rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v59/V59_RESULT.json");ap.add_argument("--seeds",default="5901,5917,5939")
    a=ap.parse_args();p=run(a.output,[int(x) for x in a.seeds.split(',') if x.strip()]);print(json.dumps({k:p[k] for k in ("decision","selected","summaries","provenance","failures")},indent=2,sort_keys=True))
    if p["decision"]!="READY":raise SystemExit(3)

if __name__=="__main__":main()
