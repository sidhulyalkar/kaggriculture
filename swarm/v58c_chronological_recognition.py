from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from swarm.v77_live_meta_route_search import fetch_top_episodes, winner_traces
from swarm.v58_opponent_policy_compiler import CHECKPOINTS, _state_at, public_features, cluster_families
from swarm.v58b_macro_family_compiler import cluster_macro


def rows_at(traces,labels,checkpoint):
    rows=[]
    for i,(tr,label) in enumerate(zip(traces,labels)):
        state=_state_at(tr,checkpoint)
        if not state:continue
        obs=dict(state.get("observation",{}) or {});seat=int(tr.get("winner_seat",0))
        rows.append({"trace":i,"family":int(label),"date":str(tr.get("date","")),"team":str(tr.get("team","")),"features":public_features(obs,seat)})
    return rows


def chronological_centroid(rows:list[dict[str,Any]]):
    dates=sorted({r["date"] for r in rows if r["date"]})
    if len(dates)<2:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":0,"latest_date":dates[-1] if dates else None}
    latest=dates[-1];train=[r for r in rows if r["date"]<latest];test=[r for r in rows if r["date"]==latest]
    names=sorted(rows[0]["features"]);families=sorted({r["family"] for r in train})
    if not train or not test or not families:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":len(test),"latest_date":latest}
    x=np.asarray([[float(r["features"].get(k,0)) for k in names] for r in train],dtype=float);mu=x.mean(axis=0);sd=x.std(axis=0);sd[sd<1e-9]=1.0;x=(x-mu)/sd
    centroids={fam:x[[i for i,r in enumerate(train) if r["family"]==fam]].mean(axis=0) for fam in families}
    eligible=correct=0;distances=[]
    for r in test:
        if r["family"] not in centroids:continue
        eligible+=1;z=(np.asarray([float(r["features"].get(k,0)) for k in names])-mu)/sd
        ranked=sorted((float(np.mean((z-c)**2)),fam) for fam,c in centroids.items());pred=ranked[0][1];correct+=int(pred==r["family"])
        distances.append({"team":r["team"],"true":r["family"],"pred":pred,"best_mse":ranked[0][0],"gap":ranked[1][0]-ranked[0][0] if len(ranked)>1 else None})
    return {"accuracy":correct/max(1,eligible),"coverage":eligible/max(1,len(test)),"eligible":eligible,"correct":correct,"test":len(test),"latest_date":latest,"predictions":distances}


def evaluate(traces,labels):
    result={}
    for cp in CHECKPOINTS:result[str(cp)]=chronological_centroid(rows_at(traces,labels,cp))
    return result


def run(output:str,days:int=4,per_day:int=10):
    out=Path(output);root=out.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acq=fetch_top_episodes(root,days=days,per_day=per_day);traces=winner_traces(episodes)
    exact=cluster_families(traces,.86);modes={"exact_086":evaluate(traces,exact)}
    for threshold in (.55,.65,.72,.78,.84):modes[f"macro_{threshold:.2f}"]=evaluate(traces,cluster_macro(traces,threshold))
    candidates=[]
    for mode,rr in modes.items():
        for cp in CHECKPOINTS:
            r=rr[str(cp)];score=r["accuracy"]*r["coverage"];candidates.append({"mode":mode,"checkpoint":cp,"score":score,**{k:r[k] for k in ("accuracy","coverage","eligible","test","latest_date")}})
    candidates.sort(key=lambda r:(r["score"],r["accuracy"],r["coverage"],-r["checkpoint"]),reverse=True);best=candidates[0] if candidates else None
    decision="BUILD_KNOWN_LINEAGE_POSTERIOR" if best and best["checkpoint"]<=120 and best["accuracy"]>=.75 and best["coverage"]>=.50 else "REFINE_KNOWN_LINEAGE_MODEL"
    payload={"experiment":"V58C_CHRONOLOGICAL_RECOGNITION","decision":decision,"episodes":len(episodes),"trace_count":len(traces),"best":best,"candidates":candidates,"modes":modes,"acquisition":acq,
             "scientific_boundary":"latest-day classification uses only public-state features; older dates form the recognition prototypes; replay actions are used only to assign offline ground-truth lineage labels"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v58c/V58C_RESULT.json");ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=10)
    a=ap.parse_args();p=run(a.output,a.days,a.per_day);print(json.dumps({"decision":p["decision"],"trace_count":p["trace_count"],"best":p["best"],"candidates":p["candidates"]},indent=2,sort_keys=True))

if __name__=="__main__":main()
