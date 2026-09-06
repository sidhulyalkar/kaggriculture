from __future__ import annotations

import argparse, copy, json, statistics
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make

from baselines.v1.counter_agent import CounterMeta, TournamentMind
from submission.predictive_agent import PredictiveMind
from submission.market_flow_runtime import infer_external_supply
from swarm.v77_live_meta_route_search import recover_soil_parent

PRODUCTS=("STRAWBERRY","MELON","WOOL")

class FlowProfiler(PredictiveMind):
    def __init__(self):
        super().__init__(); self.prev_obs=None; self.prev_action=None
        self.events={p:0 for p in PRODUCTS}; self.units={p:0 for p in PRODUCTS}; self.exact={p:0 for p in PRODUCTS}
        self.buckets={p:[0]*6 for p in PRODUCTS}
    def act(self,obs):
        if self.prev_obs is not None and self.prev_action is not None:
            bucket=(int((self.prev_obs or {}).get("hour",0) or 0)//4)%6
            for p in PRODUCTS:
                u=infer_external_supply(self.prev_obs,obs,self.prev_action,p)
                if u is None: continue
                self.exact[p]+=1
                if int(u)>0:
                    self.events[p]+=1; self.units[p]+=int(u); self.buckets[p][bucket]+=1
        a=super().act(obs); self.prev_obs=copy.deepcopy(obs); self.prev_action=copy.deepcopy(a); return a
    def snapshot(self):
        out={}
        for p in PRODUCTS:
            e=self.events[p]; x=self.exact[p]; b=self.buckets[p]
            out[p]={"events":e,"units":self.units[p],"exact":x,"event_rate":e/max(1,x),"mean_shock":self.units[p]/max(1,e),"bucket_max_share":max(b)/max(1,e),"buckets":b}
        total_e=sum(self.events.values()); total_u=sum(self.units.values()); total_x=sum(self.exact.values())
        out["ALL"]={"events":total_e,"units":total_u,"exact":total_x,"event_rate":total_e/max(1,total_x),"mean_shock":total_u/max(1,total_e)}
        return out

def _agent(m):
    def f(obs,configuration=None): return m.act(obs)
    return f

def _soil(root):
    try:
        src,meta=recover_soil_parent(root,max_version=1); p=root/"soil_latest.py"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(src,encoding="utf-8"); compile(src,str(p),"exec"); return (lambda:str(p)),meta
    except Exception as exc: return None,{"status":"unavailable","error":f"{type(exc).__name__}: {exc}"[:300]}

def run(output,seeds):
    root=Path(output).parent; sf,sm=_soil(root/"soil")
    opponents=[("INCUMBENT",PredictiveMind),("V1_TOURNAMENT",TournamentMind),("V1_COUNTER",CounterMeta)]
    if sf: opponents.append(("SOIL_LATEST",sf))
    rows=[]
    for oname,ofactory in opponents:
        for seed in seeds:
            for seat in (0,1):
                prof=FlowProfiler(); opp=ofactory(); env=make("kaggriculture",configuration={"seed":int(seed)},debug=False)
                pa=_agent(prof); oa=_agent(opp) if not isinstance(opp,str) else opp; agents=[pa,oa] if seat==0 else [oa,pa]
                try:
                    env.run(agents); last=env.steps[-1]; statuses=[str(last[i].status) for i in (0,1)]
                    rows.append({"opponent":oname,"seed":int(seed),"seat":int(seat),"ok":all(x=="DONE" for x in statuses),"profile":prof.snapshot()})
                except BaseException as exc: rows.append({"opponent":oname,"seed":int(seed),"seat":int(seat),"ok":False,"error":repr(exc)[:500]})
    fam={}
    for oname,_ in opponents:
        rr=[r for r in rows if r.get("ok") and r["opponent"]==oname]
        by={}
        for p in PRODUCTS+("ALL",):
            vals=[r["profile"][p] for r in rr]
            by[p]={k:statistics.mean(v[k] for v in vals) for k in ("events","units","event_rate","mean_shock")}
            if p!="ALL": by[p]["bucket_max_share"]=statistics.mean(v["bucket_max_share"] for v in vals)
        fam[oname]={"games":len(rr),"products":by}
    payload={"experiment":"V56_FLOW_FINGERPRINT","seeds":list(seeds),"soil":sm,"families":fam,"rows":rows}
    Path(output).parent.mkdir(parents=True,exist_ok=True); Path(output).write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8"); return payload

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="tmp/v56/V56_FLOW_PROFILE.json"); ap.add_argument("--seeds",default="5603,5623,5641")
    a=ap.parse_args(); p=run(a.output,[int(x) for x in a.seeds.split(",") if x.strip()]); print(json.dumps(p["families"],indent=2,sort_keys=True))
if __name__=="__main__": main()
