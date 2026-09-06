from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from swarm.v77_live_meta_route_search import fetch_top_episodes, winner_traces
from swarm.v58_opponent_policy_compiler import (
    CHECKPOINTS,
    _loo_team_nearest_centroid,
    _vector_rows,
)

PREFIX_TURNS=120
THRESHOLDS=(.55,.65,.72,.78,.84)


def _macro_op(order:Any)->tuple[str,str]:
    if not isinstance(order,(list,tuple)) or not order:return ("PASS","")
    op=str(order[0]);arg=""
    # Economic object identity is meaningful. Exact navigation direction is not
    # used to define the macro family because different implementations can
    # realize the same economy through different paths.
    if len(order)>=2 and op in {"PLANT","PICKUP","DROP","PLACE","BUY_SEED","BUY_PRODUCT","BUY_ANIMAL","SELL"}:
        arg=str(order[1])
    return op,arg


def macro_action_skeleton(action:Any)->tuple[Any,...]:
    if not isinstance(action,dict):return (("INVALID",""),(),())
    return (
        _macro_op(action.get("farmer")),
        tuple(_macro_op(x) for x in (action.get("hands") or [])),
        tuple(_macro_op(x) for x in (action.get("market") or [])),
    )


def _sequence(trace:dict[str,Any])->list[Any]:
    amap=trace.get("action_map",{}) or {}
    return [macro_action_skeleton(amap.get(step)) for step in range(PREFIX_TURNS)]


def _similarity(a:list[Any],b:list[Any])->float:
    n=min(len(a),len(b));return sum(int(a[i]==b[i]) for i in range(n))/max(1,n)


def cluster_macro(traces:list[dict[str,Any]],threshold:float)->list[int]:
    seq=[_sequence(t) for t in traces];parent=list(range(len(traces)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    for i in range(len(traces)):
        for j in range(i):
            if _similarity(seq[i],seq[j])>=threshold:union(i,j)
    roots={};out=[]
    for i in range(len(traces)):
        r=find(i);roots.setdefault(r,len(roots));out.append(roots[r])
    return out


def family_summary(traces,labels):
    g=defaultdict(list)
    for tr,label in zip(traces,labels):g[int(label)].append(tr)
    rows=[]
    for fam,members in g.items():
        teams=sorted({str(t.get("team","")) for t in members});scores=[float(t.get("avg_score",0) or 0) for t in members]
        rows.append({"family":fam,"traces":len(members),"teams":teams,"team_count":len(teams),"mean_source_score":statistics.mean(scores) if scores else 0.0,
                     "macro_hash":sha256(json.dumps(_sequence(members[0]),sort_keys=True,default=str).encode()).hexdigest()[:16]})
    return sorted(rows,key=lambda r:(r["traces"],r["team_count"],r["mean_source_score"]),reverse=True)


def evaluate_threshold(traces,threshold):
    labels=cluster_macro(traces,threshold);families=family_summary(traces,labels);recognition={}
    for cp in CHECKPOINTS:recognition[str(cp)]=_loo_team_nearest_centroid(_vector_rows(traces,labels,cp))
    cross=[f for f in families if f["team_count"]>=2 and f["traces"]>=2]
    max_share=max((f["traces"] for f in families),default=0)/max(1,len(traces))
    best_cp=max(CHECKPOINTS,key=lambda cp:(recognition[str(cp)]["accuracy"]*recognition[str(cp)]["coverage"],recognition[str(cp)]["accuracy"]))
    best=recognition[str(best_cp)];score=best["accuracy"]*best["coverage"]
    valid_structure=bool(len(cross)>=2 and max_share<=.70 and len(families)>=3)
    return {"threshold":threshold,"family_count":len(families),"cross_team_family_count":len(cross),"max_family_share":max_share,"families":families,"recognition":recognition,
            "best_checkpoint":best_cp,"best_accuracy":best["accuracy"],"best_coverage":best["coverage"],"selection_score":score,"valid_structure":valid_structure}


def run(output:str,days:int=4,per_day:int=10):
    out=Path(output);root=out.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acq=fetch_top_episodes(root,days=days,per_day=per_day);traces=winner_traces(episodes)
    sweeps=[evaluate_threshold(traces,t) for t in THRESHOLDS];eligible=[s for s in sweeps if s["valid_structure"]]
    eligible.sort(key=lambda s:(s["selection_score"],s["best_accuracy"],s["cross_team_family_count"],-s["max_family_share"]),reverse=True)
    selected=eligible[0] if eligible else None
    decision="BUILD_RUNTIME_POSTERIOR" if selected and selected["best_accuracy"]>=.60 and selected["best_coverage"]>=.35 else "REFINE_REPRESENTATION"
    payload={"experiment":"V58B_MACRO_FAMILY_COMPILER","decision":decision,"episodes":len(episodes),"trace_count":len(traces),"selected":selected,"sweeps":sweeps,"acquisition":acq,
             "scientific_boundary":"macro labels use public replay actions offline; recognition features remain live-public-state only"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v58b/V58B_RESULT.json");ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=10)
    a=ap.parse_args();p=run(a.output,a.days,a.per_day);print(json.dumps({"decision":p["decision"],"trace_count":p["trace_count"],"selected":p["selected"],"sweeps":[{k:s[k] for k in ("threshold","family_count","cross_team_family_count","max_family_share","best_checkpoint","best_accuracy","best_coverage","selection_score","valid_structure")} for s in p["sweeps"]]},indent=2,sort_keys=True))

if __name__=="__main__":main()
