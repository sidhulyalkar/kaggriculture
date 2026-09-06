from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

import numpy as np

from swarm.v77_live_meta_route_search import fetch_top_episodes, winner_traces, _obs_step

SHOPS=("BAKERY","BRUNCH_SPOT","FARMERS_MARKET","ICE_CREAM_SHOP","PET_CAFE","PIZZA_SHOP","SMOOTHIE_SHOP","YARN_STORE")
PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
CHECKPOINTS=(72,120,144)
PREFIX_TURNS=120


def _get(v:Any,k:str,d=None):
    if isinstance(v,dict):return v.get(k,d)
    getter=getattr(v,"get",None)
    if callable(getter):return getter(k,d)
    return getattr(v,k,d)


def _op_skeleton(order:Any)->tuple[str,str]:
    if not isinstance(order,(list,tuple)) or not order:return ("PASS","")
    op=str(order[0])
    # Preserve the semantic first argument, including MOVE direction, while
    # intentionally discarding numeric quantities such as SELL volume.
    arg=str(order[1]) if len(order)>=2 else ""
    return op,arg


def action_skeleton(action:Any)->tuple[Any,...]:
    if not isinstance(action,dict):return (("INVALID",""),(),())
    farmer=_op_skeleton(action.get("farmer"))
    hands=tuple(_op_skeleton(x) for x in (action.get("hands") or []))
    market=tuple(_op_skeleton(x) for x in (action.get("market") or []))
    return farmer,hands,market


def _prefix_sequence(trace:dict[str,Any],turns:int=PREFIX_TURNS)->list[tuple[Any,...]]:
    amap=trace.get("action_map",{}) or {}
    return [action_skeleton(amap.get(step)) for step in range(turns)]


def _prefix_similarity(a:list[Any],b:list[Any])->float:
    n=min(len(a),len(b))
    if n<=0:return 0.0
    return sum(int(a[i]==b[i]) for i in range(n))/n


def cluster_families(traces:list[dict[str,Any]],threshold:float=.86)->list[int]:
    seq=[_prefix_sequence(t) for t in traces];parent=list(range(len(traces)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:parent[rb]=ra
    for i in range(len(traces)):
        for j in range(i):
            if _prefix_similarity(seq[i],seq[j])>=threshold:union(i,j)
    roots={};labels=[]
    for i in range(len(traces)):
        r=find(i)
        if r not in roots:roots[r]=len(roots)
        labels.append(roots[r])
    return labels


def _xy(v:Any)->tuple[float,float]:
    if isinstance(v,(list,tuple)) and len(v)>=2:
        try:return float(v[0]),float(v[1])
        except Exception:return 0.0,0.0
    return 0.0,0.0


def _tile_features(farm:Any)->dict[str,float]:
    counts=Counter();crops=Counter();animals=Counter()
    for row in (_get(farm,"tiles",[]) or []):
        for tile in row or []:
            if tile is None:continue
            if isinstance(tile,str):counts[str(tile)]+=1;continue
            kind=str(_get(tile,"kind","") or "")
            crop=str(_get(tile,"crop","") or "")
            animal=str(_get(tile,"animal","") or "")
            if kind:counts[kind]+=1
            if crop:crops[crop]+=1
            if animal:animals[animal]+=1
    out={f"tile_{k}":float(counts.get(k,0)) for k in ("PLANT","COOP","PASTURE","WEED")}
    for p in ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"):out[f"crop_{p}"]=float(crops.get(p,0))
    for a in ("GOOSE","COW","SHEEP"):out[f"animal_{a}"]=float(animals.get(a,0))
    return out


def public_features(obs:dict[str,Any],target_seat:int)->dict[str,float]:
    farms=list(obs.get("farms",[]) or []);farm=farms[target_seat] if target_seat<len(farms) else {}
    positions=[_get(farm,"farmer",[0,0]),*list(_get(farm,"hands",[]) or [])];xy=[_xy(p) for p in positions]
    xs=[p[0] for p in xy] or [0.0];ys=[p[1] for p in xy] or [0.0]
    f={
        "money":float(_get(farm,"money",0) or 0),
        "quadrants":float(len(list(_get(farm,"unlocked_quadrants",[]) or []))),
        "units":float(len(positions)),
        "hires_today":float(_get(farm,"hires_today",0) or 0),
        "mean_x":float(statistics.mean(xs)),"mean_y":float(statistics.mean(ys)),
        "spread_x":float(max(xs)-min(xs)),"spread_y":float(max(ys)-min(ys)),
    }
    f.update(_tile_features(farm))
    market=obs.get("market",{}) or {};inv=market.get("inventory",{}) or {};prices=market.get("prices",{}) or {}
    for p in PRODUCTS:
        f[f"inv_{p}"]=float(inv.get(p,0) or 0);f[f"price_{p}"]=float(prices.get(p,0) or 0)
    shops=list(((obs.get("town",{}) or {}).get("unlocked_shops",[]) or []))
    for pos in range(3):
        for s in SHOPS:f[f"shop{pos}_{s}"]=1.0 if pos<len(shops) and str(shops[pos])==s else 0.0
    return f


def _state_at(trace:dict[str,Any],cutoff:int)->dict[str,Any]|None:
    best=None;best_step=-1
    for state in trace.get("states",[]) or []:
        step=_obs_step(state)
        if step<=cutoff and step>best_step:
            best=state;best_step=step
    return best


def _vector_rows(traces,labels,cutoff):
    rows=[]
    for i,(tr,label) in enumerate(zip(traces,labels)):
        state=_state_at(tr,cutoff)
        if not state:continue
        obs=dict(state.get("observation",{}) or {});seat=int(tr.get("winner_seat",0))
        feat=public_features(obs,seat);rows.append({"trace":i,"team":tr.get("team",""),"family":int(label),"features":feat})
    return rows


def _loo_team_nearest_centroid(rows:list[dict[str,Any]]):
    if not rows:return {"accuracy":0.0,"coverage":0.0,"eligible":0,"correct":0,"names":[]}
    names=sorted(rows[0]["features"]);preds=[]
    for target in rows:
        train=[r for r in rows if r["team"]!=target["team"]]
        families=sorted({r["family"] for r in train})
        if target["family"] not in families or len(families)<2:continue
        x=np.asarray([[float(r["features"].get(k,0)) for k in names] for r in train],dtype=float)
        mu=x.mean(axis=0);sd=x.std(axis=0);sd[sd<1e-9]=1.0;x=(x-mu)/sd
        centroids={fam:x[[i for i,r in enumerate(train) if r["family"]==fam]].mean(axis=0) for fam in families}
        z=(np.asarray([float(target["features"].get(k,0)) for k in names])-mu)/sd
        ranked=sorted((float(np.mean((z-c)**2)),fam) for fam,c in centroids.items())
        pred=ranked[0][1];preds.append((pred,target["family"]))
    correct=sum(int(a==b) for a,b in preds);eligible=len(preds)
    return {"accuracy":correct/max(1,eligible),"coverage":eligible/max(1,len(rows)),"eligible":eligible,"correct":correct,"names":names}


def _family_summary(traces,labels):
    groups=defaultdict(list)
    for i,(tr,label) in enumerate(zip(traces,labels)):groups[int(label)].append((i,tr))
    out=[]
    for fam,members in groups.items():
        teams=sorted({str(t.get("team","")) for _,t in members});scores=[float(t.get("avg_score",0) or 0) for _,t in members]
        prefix_hash=sha256(json.dumps(_prefix_sequence(members[0][1]),sort_keys=True,default=str).encode()).hexdigest()[:16]
        out.append({"family":fam,"traces":len(members),"teams":teams,"team_count":len(teams),"mean_source_score":statistics.mean(scores) if scores else 0.0,"prefix_hash":prefix_hash})
    return sorted(out,key=lambda r:(r["traces"],r["mean_source_score"]),reverse=True)


def run(output:str,days:int=4,per_day:int=14,threshold:float=.86):
    out=Path(output);root=out.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acquisition=fetch_top_episodes(root,days=days,per_day=per_day);traces=winner_traces(episodes);labels=cluster_families(traces,threshold)
    families=_family_summary(traces,labels);recognition={}
    for cp in CHECKPOINTS:recognition[str(cp)]=_loo_team_nearest_centroid(_vector_rows(traces,labels,cp))
    cross_team=[f for f in families if f["team_count"]>=2 and f["traces"]>=2]
    best=max((recognition[str(cp)]["accuracy"] for cp in CHECKPOINTS),default=0.0);coverage=max((recognition[str(cp)]["coverage"] for cp in CHECKPOINTS),default=0.0)
    decision="BUILD_RUNTIME_POSTERIOR" if len(cross_team)>=2 and best>=.60 and coverage>=.35 else "MORE_DATA"
    payload={"experiment":"V58_OPPONENT_POLICY_COMPILER","decision":decision,"episodes":len(episodes),"trace_count":len(traces),"family_threshold":threshold,"family_count":len(families),"cross_team_family_count":len(cross_team),"families":families,"recognition":recognition,"acquisition":acquisition,
             "scientific_boundary":"family labels may use public replay actions offline; classifier inputs are restricted to fields available in the live public observation"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v58/V58_POLICY_COMPILER.json");ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=14);ap.add_argument("--family-threshold",type=float,default=.86)
    a=ap.parse_args();p=run(a.output,a.days,a.per_day,a.family_threshold);print(json.dumps({k:p[k] for k in ("decision","episodes","trace_count","family_count","cross_team_family_count","recognition","families")},indent=2,sort_keys=True))

if __name__=="__main__":main()
