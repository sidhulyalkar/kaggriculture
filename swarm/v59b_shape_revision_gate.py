from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import statistics
import tarfile

from kaggle_environments import make

from swarm.v59_historical_frontier import recover

SHAPE_HANDLE="tetsutani/shape-the-shop-work-the-pasture-kaggriculture"


def extract_main(archive:Path,dest:Path)->Path:
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive,"r:*") as tf:
        mains=[m for m in tf.getmembers() if m.isfile() and Path(m.name).name=="main.py"]
        if not mains:raise RuntimeError(f"no main.py in {archive}")
        mains.sort(key=lambda m:(len(Path(m.name).parts),m.name));fh=tf.extractfile(mains[0])
        if fh is None:raise RuntimeError("main.py unreadable")
        dest.write_bytes(fh.read())
    compile(dest.read_text(encoding="utf-8"),str(dest),"exec");return dest


def money(last,player):
    for owner in (0,1):
        try:
            obs=last[owner].observation;farms=obs["farms"] if isinstance(obs,dict) else obs.farms;farm=farms[player]
            return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
        except Exception:pass
    try:return float(last[player].reward or 0)
    except Exception:return 0.0


def game(candidate:Path,opponent:Path,seed:int,seat:int):
    env=make("kaggriculture",configuration={"seed":int(seed)},debug=False);agents=[str(candidate),str(opponent)] if seat==0 else [str(opponent),str(candidate)]
    try:
        env.run(agents);last=env.steps[-1];statuses=[str(last[i].status) for i in (0,1)];me=money(last,seat);op=money(last,1-seat)
        return {"ok":all(x=="DONE" for x in statuses),"statuses":statuses,"cash":me,"opp_cash":op,"margin":me-op,"score":1.0 if me>op else .5 if me==op else 0.0}
    except BaseException as exc:return {"ok":False,"error":f"{type(exc).__name__}: {exc}"[:500]}


def pack(src:Path,out:Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(out,"w:gz") as tf:tf.add(src,arcname="main.py")
    return {"path":str(out),"bytes":out.stat().st_size,"sha256":sha256(out.read_bytes()).hexdigest()}


def run(old_archive:str,output:str,seeds:list[int]):
    out=Path(output);root=out.parent;old=extract_main(Path(old_archive),root/"old_v57_shape.py");current,prov=recover(SHAPE_HANDLE,root/"current")
    rows=[]
    for seed in seeds:
        for seat in (0,1):rows.append({"seed":seed,"seat":seat,**game(current,old,seed,seat)})
    valid=[r for r in rows if r.get("ok")];score=statistics.mean(r["score"] for r in valid) if valid else 0.0;margin=statistics.mean(r["margin"] for r in valid) if valid else -1e9
    old_sha=sha256(old.read_bytes()).hexdigest();new_sha=sha256(current.read_bytes()).hexdigest();changed=old_sha!=new_sha
    promote=bool(changed and len(valid)==len(rows) and score>=.625 and margin>0)
    package=pack(current,root/"SUBMISSION_V59B_CURRENT_SHAPE.tar.gz") if promote else None
    payload={"experiment":"V59B_SHAPE_REVISION_GATE","decision":"PROMOTE_CURRENT_SHAPE" if promote else "KEEP_V57_SHAPE","seeds":seeds,"old_source_sha256":old_sha,"current_source_sha256":new_sha,"changed":changed,"current_provenance":prov,"games":len(rows),"all_valid":len(valid)==len(rows),"current_score_rate":score,"current_mean_margin":margin,"rows":rows,"package":package,
             "promotion_contract":{"min_score_rate":.625,"positive_mean_margin":True,"both_seats":True,"all_valid":True}}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--old-archive",required=True);ap.add_argument("--output",default="tmp/v59b/V59B_RESULT.json");ap.add_argument("--seeds",default="5951,5963,5977,5987")
    a=ap.parse_args();p=run(a.old_archive,a.output,[int(x) for x in a.seeds.split(',') if x.strip()]);print(json.dumps({k:p[k] for k in ("decision","changed","old_source_sha256","current_source_sha256","games","all_valid","current_score_rate","current_mean_margin","package")},indent=2,sort_keys=True))

if __name__=="__main__":main()
