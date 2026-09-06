from __future__ import annotations

import argparse, json, shutil, statistics, tarfile
from hashlib import sha256
from pathlib import Path

from kaggle_environments import make

from submission.predictive_agent import PredictiveMind
from swarm.v77_live_meta_route_search import _extract_main_from_root, recover_soil_parent

PUBLIC_HANDLES={
    "SHAPE_TOP10":"indarkarhana/shape-the-shop-work-the-pasture-top-10",
    "FARMING_V3":"lynnsakurai/farming-score-v3-replay-revised",
    "SHAPE_PASTURE":"tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
}


def _download_public(handle,root):
    import kagglehub
    dest=root/handle.replace('/','__'); shutil.rmtree(dest,ignore_errors=True); dest.mkdir(parents=True,exist_ok=True)
    got=kagglehub.notebook_output_download(handle,output_dir=str(dest),force_download=True)
    base=Path(got) if got else dest; src=_extract_main_from_root(base)
    if not src: src=_extract_main_from_root(dest)
    if not src: raise RuntimeError(f"no main.py recovered from {handle}")
    compile(src,f"<{handle}>","exec")
    digest=sha256(src.encode()).hexdigest(); path=root/(handle.split('/')[-1]+".py"); path.write_text(src,encoding="utf-8")
    return path,{"handle":handle,"sha256":digest,"bytes":len(src)}


def _agent_for(mind):
    def agent(obs,configuration=None): return mind.act(obs)
    return agent


def _money(last,player):
    for owner in (0,1):
        try:
            obs=last[owner].observation; farms=obs["farms"] if isinstance(obs,dict) else obs.farms; farm=farms[player]
            return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
        except Exception: pass
    try:return float(last[player].reward or 0)
    except Exception:return 0.0


def _run(candidate_path,opponent,seed,seat):
    env=make("kaggriculture",configuration={"seed":int(seed)},debug=False)
    ca=str(candidate_path); oa=_agent_for(opponent()) if callable(opponent) and opponent is not str else opponent
    agents=[ca,oa] if seat==0 else [oa,ca]
    try:
        env.run(agents); last=env.steps[-1]; statuses=[str(last[i].status) for i in (0,1)]; me=_money(last,seat); op=_money(last,1-seat)
        return {"ok":all(x=="DONE" for x in statuses),"statuses":statuses,"cash":me,"opp_cash":op,"margin":me-op,"score":1.0 if me>op else .5 if me==op else 0.0}
    except BaseException as exc:return {"ok":False,"error":f"{type(exc).__name__}: {exc}"[:500]}


def _package(source,out):
    out.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(out,"w:gz") as tf: tf.add(source,arcname="main.py")
    return {"path":str(out),"bytes":out.stat().st_size,"sha256":sha256(out.read_bytes()).hexdigest()}


def run(output,seeds):
    root=Path(output).parent; cand_root=root/"public"; cand_root.mkdir(parents=True,exist_ok=True)
    sources={}; provenance={}; failures={}
    for name,handle in PUBLIC_HANDLES.items():
        try:sources[name],provenance[name]=_download_public(handle,cand_root)
        except Exception as exc:failures[name]=f"{type(exc).__name__}: {exc}"[:500]
    soil_factory=None; soil_meta={"status":"unavailable"}
    try:
        soil_src,soil_meta=recover_soil_parent(root/"soil",max_version=1); soil_path=root/"soil_latest.py"; soil_path.write_text(soil_src,encoding="utf-8"); soil_factory=str(soil_path)
    except Exception as exc: soil_meta={"status":"unavailable","error":repr(exc)[:300]}
    rows=[]
    for cname,cpath in sources.items():
        opponents=[("INCUMBENT",PredictiveMind)]
        if soil_factory: opponents.append(("SOIL_LATEST",soil_factory))
        for oname,opp in sources.items():
            if oname!=cname: opponents.append((oname,str(opp)))
        for oname,opponent in opponents:
            for seed in seeds:
                for seat in (0,1):
                    if isinstance(opponent,str):
                        env=make("kaggriculture",configuration={"seed":int(seed)},debug=False); agents=[str(cpath),opponent] if seat==0 else [opponent,str(cpath)]
                        try:
                            env.run(agents); last=env.steps[-1]; statuses=[str(last[i].status) for i in (0,1)]; me=_money(last,seat); op=_money(last,1-seat); r={"ok":all(x=="DONE" for x in statuses),"statuses":statuses,"cash":me,"opp_cash":op,"margin":me-op,"score":1.0 if me>op else .5 if me==op else 0.0}
                        except BaseException as exc:r={"ok":False,"error":repr(exc)[:500]}
                    else:r=_run(cpath,opponent,seed,seat)
                    rows.append({"candidate":cname,"opponent":oname,"seed":int(seed),"seat":seat,**r})
    summaries=[]
    for cname in sources:
        rr=[r for r in rows if r["candidate"]==cname]; valid=[r for r in rr if r.get("ok")]; families=[]
        for oname in sorted({r["opponent"] for r in valid}):
            g=[r for r in valid if r["opponent"]==oname]; families.append({"opponent":oname,"games":len(g),"score_rate":statistics.mean(r["score"] for r in g),"mean_margin":statistics.mean(r["margin"] for r in g)})
        all_valid=len(valid)==len(rr) and len(rr)>0; overall=statistics.mean(r["score"] for r in valid) if valid else 0; margin=statistics.mean(r["margin"] for r in valid) if valid else -1e9
        incumbent=next((f for f in families if f["opponent"]=="INCUMBENT"),None)
        passed=bool(all_valid and incumbent and incumbent["score_rate"]>=.50 and overall>=.45)
        summaries.append({"candidate":cname,"all_valid":all_valid,"games":len(rr),"score_rate":overall,"mean_margin":margin,"incumbent":incumbent,"families":families,"passed":passed})
    qualified=[s for s in summaries if s["passed"]]; qualified.sort(key=lambda s:(s["score_rate"],s["mean_margin"]),reverse=True)
    selected=[s["candidate"] for s in qualified[:2]]
    packages={}
    for i,name in enumerate(selected,1): packages[name]=_package(sources[name],root/f"SUBMISSION_V57_{i}_{name}.tar.gz")
    payload={"experiment":"V57_PUBLIC_FRONTIER_SELECTOR","seeds":list(seeds),"provenance":provenance,"failures":failures,"soil":soil_meta,"summaries":summaries,"selected":selected,"packages":packages,"decision":"TWO_READY" if len(selected)>=2 else "INSUFFICIENT_QUALIFIED","rows":rows}
    Path(output).write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8"); return payload


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="tmp/v57/V57_RESULT.json"); ap.add_argument("--seeds",default="5701,5711,5723")
    a=ap.parse_args(); p=run(a.output,[int(x) for x in a.seeds.split(',') if x.strip()]); print(json.dumps({k:p[k] for k in ("decision","selected","summaries","provenance","failures")},indent=2,sort_keys=True));
    if p["decision"]!="TWO_READY": raise SystemExit(3)
if __name__=="__main__": main()
