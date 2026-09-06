from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from swarm.v77_live_meta_route_search import fetch_top_episodes, winner_traces
from swarm.v58_opponent_policy_compiler import _state_at, public_features, cluster_families
from swarm.v58b_macro_family_compiler import cluster_macro

CHECKPOINTS=(72,120,144)


def _farm_keys(features:dict[str,float])->list[str]:
    return sorted(k for k in features if not k.startswith("inv_") and not k.startswith("price_") and not k.startswith("shop"))


def trajectory_features(trace:dict[str,Any],checkpoint:int)->dict[str,float]:
    samples=[s for s in (24,48,72,96,120,144) if s<=checkpoint]
    result={};last_obs=None;seat=int(trace.get("winner_seat",0))
    for s in samples:
        state=_state_at(trace,s)
        if not state:continue
        obs=dict(state.get("observation",{}) or {});last_obs=obs;feat=public_features(obs,seat)
        for k in _farm_keys(feat):result[f"t{s}_{k}"]=float(feat[k])
    if last_obs is not None:
        feat=public_features(last_obs,seat)
        # World/shop context is shared by both players, but it determines which
        # branch of a route is possible. Include only the latest context once.
        for k,v in feat.items():
            if k.startswith("shop"):result[f"world_{k}"]=float(v)
    return result


def rows_at(traces,labels,checkpoint):
    rows=[]
    for i,(tr,label) in enumerate(zip(traces,labels)):
        feat=trajectory_features(tr,checkpoint)
        if feat:rows.append({"trace":i,"family":int(label),"date":str(tr.get("date","")),"team":str(tr.get("team","")),"features":feat})
    return rows


def chronological_knn(rows:list[dict[str,Any]],k:int=1):
    dates=sorted({r["date"] for r in rows if r["date"]})
    if len(dates)<2:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":0,"latest_date":dates[-1] if dates else None}
    latest=dates[-1];train=[r for r in rows if r["date"]<latest];test=[r for r in rows if r["date"]==latest]
    names=sorted(set().union(*(r["features"].keys() for r in rows)))
    families={r["family"] for r in train};eligible_test=[r for r in test if r["family"] in families]
    if not train or not eligible_test:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":len(test),"latest_date":latest}
    x=np.asarray([[float(r["features"].get(n,0)) for n in names] for r in train],float);mu=x.mean(0);sd=x.std(0);sd[sd<1e-9]=1.;x=(x-mu)/sd
    correct=0;predictions=[]
    for r in eligible_test:
        z=(np.asarray([float(r["features"].get(n,0)) for n in names])-mu)/sd;dist=np.mean((x-z)**2,axis=1);order=np.argsort(dist)[:max(1,min(k,len(train)))]
        votes=Counter(train[int(i)]["family"] for i in order);best_count=max(votes.values());cands=[fam for fam,c in votes.items() if c==best_count]
        pred=min(cands,key=lambda fam:min(float(dist[i]) for i in order if train[int(i)]["family"]==fam));correct+=int(pred==r["family"])
        predictions.append({"team":r["team"],"true":r["family"],"pred":pred,"nearest_mse":float(dist[order[0]])})
    return {"accuracy":correct/len(eligible_test),"coverage":len(eligible_test)/max(1,len(test)),"eligible":len(eligible_test),"correct":correct,"test":len(test),"latest_date":latest,"predictions":predictions}


def run(output:str,days:int=4,per_day:int=10):
    out=Path(output);root=out.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acq=fetch_top_episodes(root,days=days,per_day=per_day);traces=winner_traces(episodes)
    label_sets={"exact_086":cluster_families(traces,.86)}
    for t in (.55,.65,.72,.78,.84):label_sets[f"macro_{t:.2f}"]=cluster_macro(traces,t)
    candidates=[];details={}
    for mode,labels in label_sets.items():
        details[mode]={}
        for cp in CHECKPOINTS:
            details[mode][str(cp)]={}
            rows=rows_at(traces,labels,cp)
            for k in (1,3):
                r=chronological_knn(rows,k);details[mode][str(cp)][f"knn{k}"]=r;score=r["accuracy"]*r["coverage"]
                candidates.append({"mode":mode,"checkpoint":cp,"model":f"knn{k}","score":score,**{x:r[x] for x in ("accuracy","coverage","eligible","test","latest_date")}})
    candidates.sort(key=lambda r:(r["score"],r["accuracy"],r["coverage"],-r["checkpoint"]),reverse=True);best=candidates[0] if candidates else None
    decision="BUILD_RUNTIME_POSTERIOR" if best and best["checkpoint"]<=120 and best["accuracy"]>=.75 and best["coverage"]>=.70 else "ADD_BEHAVIORAL_FLOW_FEATURES"
    payload={"experiment":"V58D_TRAJECTORY_RECOGNITION","decision":decision,"episodes":len(episodes),"trace_count":len(traces),"best":best,"candidates":candidates,"details":details,"acquisition":acq,
             "scientific_boundary":"latest-day recognition uses only the target farm's live-public trajectory plus shared shop context; replay actions are offline labels only"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v58d/V58D_RESULT.json");ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=10)
    a=ap.parse_args();p=run(a.output,a.days,a.per_day);print(json.dumps({"decision":p["decision"],"trace_count":p["trace_count"],"best":p["best"],"candidates":p["candidates"][:12]},indent=2,sort_keys=True))

if __name__=="__main__":main()
