from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from submission.market_flow_runtime import NONBUYABLE_PRODUCTS, infer_external_supply
from swarm.v77_live_meta_route_search import fetch_top_episodes, winner_traces
from swarm.v58_opponent_policy_compiler import cluster_families
from swarm.v58b_macro_family_compiler import cluster_macro
from swarm.v58d_trajectory_recognition import trajectory_features

CHECKPOINTS=(72,120,144)
PRODUCTS=tuple(sorted(NONBUYABLE_PRODUCTS))


def _episode_id(rep:dict[str,Any])->str:
    info=rep.get("info",{}) or {}
    return str(info.get("EpisodeId",rep.get("id","unknown")))


def flow_features(rep:dict[str,Any],target_seat:int,checkpoint:int)->dict[str,float]:
    """Reconstruct target-seat market supply using only observer-visible state.

    Runtime analogue: the agent knows its own previous action and observes the
    shared market before/after the transition. Replay row t+1 stores the action
    selected from observation row t, so observer action comes from curr_state.
    """
    steps=list(rep.get("steps",[]) or []);observer=1-int(target_seat);stats={p:{"valid":0,"events":0,"units":0,"max":0,"last":-999,"buckets":[0,0,0,0,0,0]} for p in PRODUCTS}
    max_i=min(max(0,int(checkpoint)),len(steps)-1)
    for i in range(max_i):
        j=i+1
        if observer>=len(steps[i]) or observer>=len(steps[j]):continue
        prev=steps[i][observer] if isinstance(steps[i][observer],dict) else {};curr=steps[j][observer] if isinstance(steps[j][observer],dict) else {}
        prev_obs=prev.get("observation",{}) or {};curr_obs=curr.get("observation",{}) or {};own_action=curr.get("action")
        step=int(prev_obs.get("step",int(prev_obs.get("day",0) or 0)*24+int(prev_obs.get("hour",0) or 0)) or 0)
        for p in PRODUCTS:
            units=infer_external_supply(prev_obs,curr_obs,own_action,p)
            if units is None:continue
            s=stats[p];s["valid"]+=1
            if int(units)>0:
                s["events"]+=1;s["units"]+=int(units);s["max"]=max(s["max"],int(units));s["last"]=step;s["buckets"][(step//24)%6]+=1
    out={}
    for p,s in stats.items():
        valid=max(1,s["valid"]);out[f"flow_{p}_event_rate"]=s["events"]/valid;out[f"flow_{p}_units_per_valid"]=s["units"]/valid;out[f"flow_{p}_max"]=float(s["max"])
        out[f"flow_{p}_since_last"]=float(checkpoint-s["last"] if s["last"]>=0 else checkpoint+24)
        for b,n in enumerate(s["buckets"]):out[f"flow_{p}_day{b}_events"]=float(n)
    return out


def combined_features(trace:dict[str,Any],rep:dict[str,Any],checkpoint:int)->dict[str,float]:
    f=trajectory_features(trace,checkpoint);f.update(flow_features(rep,int(trace.get("winner_seat",0)),checkpoint));return f


def chronological_knn(rows:list[dict[str,Any]],k:int=1):
    dates=sorted({r["date"] for r in rows if r["date"]})
    if len(dates)<2:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":0,"latest_date":dates[-1] if dates else None}
    latest=dates[-1];train=[r for r in rows if r["date"]<latest];test=[r for r in rows if r["date"]==latest];families={r["family"] for r in train};eligible=[r for r in test if r["family"] in families]
    if not train or not eligible:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"test":len(test),"latest_date":latest}
    names=sorted(set().union(*(r["features"].keys() for r in rows)));x=np.asarray([[float(r["features"].get(n,0)) for n in names] for r in train],float);mu=x.mean(0);sd=x.std(0);sd[sd<1e-9]=1.;x=(x-mu)/sd
    correct=0;predictions=[]
    for r in eligible:
        z=(np.asarray([float(r["features"].get(n,0)) for n in names])-mu)/sd;dist=np.mean((x-z)**2,axis=1);order=np.argsort(dist)[:max(1,min(k,len(train)))];votes=Counter(train[int(i)]["family"] for i in order);mx=max(votes.values());cands=[fam for fam,c in votes.items() if c==mx]
        pred=min(cands,key=lambda fam:min(float(dist[i]) for i in order if train[int(i)]["family"]==fam));correct+=int(pred==r["family"]);predictions.append({"team":r["team"],"true":r["family"],"pred":pred,"nearest_mse":float(dist[order[0]])})
    return {"accuracy":correct/len(eligible),"coverage":len(eligible)/max(1,len(test)),"eligible":len(eligible),"correct":correct,"test":len(test),"latest_date":latest,"predictions":predictions}


def run(output:str,days:int=4,per_day:int=10):
    out=Path(output);root=out.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acq=fetch_top_episodes(root,days=days,per_day=per_day);traces=winner_traces(episodes);rep_by_id={_episode_id(rep):rep for rep in episodes}
    labels={"exact_086":cluster_families(traces,.86)}
    for t in (.55,.65,.72,.78,.84):labels[f"macro_{t:.2f}"]=cluster_macro(traces,t)
    candidates=[];details={}
    for mode,labs in labels.items():
        details[mode]={}
        for cp in CHECKPOINTS:
            rows=[]
            for i,(tr,fam) in enumerate(zip(traces,labs)):
                rep=rep_by_id.get(str(tr.get("episode_id")))
                if not rep:continue
                rows.append({"trace":i,"family":int(fam),"date":str(tr.get("date","")),"team":str(tr.get("team","")),"features":combined_features(tr,rep,cp)})
            details[mode][str(cp)]={}
            for k in (1,3):
                r=chronological_knn(rows,k);details[mode][str(cp)][f"knn{k}"]=r;score=r["accuracy"]*r["coverage"];candidates.append({"mode":mode,"checkpoint":cp,"model":f"knn{k}","score":score,**{x:r[x] for x in ("accuracy","coverage","eligible","test","latest_date")}})
    candidates.sort(key=lambda r:(r["score"],r["accuracy"],r["coverage"],-r["checkpoint"]),reverse=True);best=candidates[0] if candidates else None
    decision="BUILD_RUNTIME_POSTERIOR" if best and best["checkpoint"]<=120 and best["accuracy"]>=.75 and best["coverage"]>=.70 else "BEHAVIOR_FIRST_NO_LINEAGE_SWITCH"
    payload={"experiment":"V58E_BEHAVIORAL_FLOW_RECOGNITION","decision":decision,"episodes":len(episodes),"trace_count":len(traces),"best":best,"candidates":candidates,"details":details,"acquisition":acq,
             "scientific_boundary":"target flow is reconstructed from shared public market transitions while subtracting the observer's own known action; replay-private actions are not runtime inputs"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v58e/V58E_RESULT.json");ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=10)
    a=ap.parse_args();p=run(a.output,a.days,a.per_day);print(json.dumps({"decision":p["decision"],"trace_count":p["trace_count"],"best":p["best"],"candidates":p["candidates"][:12]},indent=2,sort_keys=True))

if __name__=="__main__":main()
