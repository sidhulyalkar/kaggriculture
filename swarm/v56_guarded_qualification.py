from __future__ import annotations

import argparse,json,statistics
from pathlib import Path

from kaggle_environments import make
from baselines.v1.counter_agent import CounterMeta,TournamentMind
from submission.guarded_market_agent import GuardedMarketMind
from submission.predictive_agent import PredictiveMind
from swarm.v77_live_meta_route_search import recover_soil_parent


def _agent(m):
    def f(obs,configuration=None):return m.act(obs)
    return f

def _money(last,p):
    for owner in (0,1):
        try:
            obs=last[owner].observation;fs=obs["farms"] if isinstance(obs,dict) else obs.farms;farm=fs[p];return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
        except Exception:pass
    return float(last[p].reward or 0)

def _run(name,factory,oname,ofactory,seed,seat):
    cand=factory();opp=ofactory();env=make("kaggriculture",configuration={"seed":int(seed)},debug=False);ca=_agent(cand);oa=_agent(opp) if not isinstance(opp,str) else opp;agents=[ca,oa] if seat==0 else [oa,ca]
    try:
        env.run(agents);last=env.steps[-1];st=[str(last[i].status) for i in (0,1)];me=_money(last,seat);op=_money(last,1-seat);r={"ok":all(x=="DONE" for x in st),"cash":me,"opp_cash":op,"margin":me-op,"score":1. if me>op else .5 if me==op else 0.}
        if isinstance(cand,GuardedMarketMind):r.update(interventions=cand.intervention_count,intervention_units=cand.intervention_units,regime=cand.regime_snapshot())
        return {"candidate":name,"opponent":oname,"seed":int(seed),"seat":int(seat),**r}
    except BaseException as exc:return {"candidate":name,"opponent":oname,"seed":int(seed),"seat":int(seat),"ok":False,"error":repr(exc)[:500]}

def _summary(rows,name):
    valid=[r for r in rows if r.get("ok")];base={(r["opponent"],r["seed"],r["seat"]):r for r in valid if r["candidate"]=="BASE"};cand={(r["opponent"],r["seed"],r["seat"]):r for r in valid if r["candidate"]==name};keys=sorted(set(base)&set(cand));families=[]
    for opp in sorted({k[0] for k in keys}):
        kk=[k for k in keys if k[0]==opp];families.append({"opponent":opp,"pairs":len(kk),"score_delta":statistics.mean(cand[k]["score"]-base[k]["score"] for k in kk),"margin_delta":statistics.mean(cand[k]["margin"]-base[k]["margin"] for k in kk),"candidate_score":statistics.mean(cand[k]["score"] for k in kk),"activations":sum(1 for k in kk if (cand[k].get("regime") or {}).get("active"))})
    sd=[cand[k]["score"]-base[k]["score"] for k in keys];md=[cand[k]["margin"]-base[k]["margin"] for k in keys];cr=[r for r in valid if r["candidate"]==name];all_valid=len(cr)==len([r for r in rows if r["candidate"]==name]) and bool(keys)
    worst_score=min((f["score_delta"] for f in families),default=-1);worst_margin=min((f["margin_delta"] for f in families),default=-1e9);ints=sum(int(r.get("interventions",0)) for r in cr);acts=sum(1 for r in cr if (r.get("regime") or {}).get("active"))
    score_delta=statistics.mean(sd) if sd else -1;margin_delta=statistics.mean(md) if md else -1e9
    # Guard is only qualified if it never loses a win-rate family relative to
    # BASE and the mean economic effect is positive. A tiny negative margin in
    # a non-activated family is impossible by construction and flags a bug.
    passed=bool(all_valid and ints>0 and acts>0 and score_delta>=0 and margin_delta>0 and worst_score>=0 and worst_margin>=-50)
    return {"candidate":name,"pairs":len(keys),"all_valid":all_valid,"score_delta":score_delta,"margin_delta":margin_delta,"worst_family_score_delta":worst_score,"worst_family_margin_delta":worst_margin,"interventions":ints,"activations":acts,"families":families,"passed":passed}

def _soil(root):
    try:
        src,meta=recover_soil_parent(root,max_version=1);p=root/"soil.py";p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src,encoding="utf-8");return (lambda:str(p)),meta
    except Exception as exc:return None,{"status":"unavailable","error":repr(exc)[:300]}

def run(output,model,seeds):
    root=Path(output).parent;sf,sm=_soil(root/"soil");opps=[("INCUMBENT",PredictiveMind),("V1_COUNTER",CounterMeta),("V1_TOURNAMENT",TournamentMind)];
    if sf:opps.append(("SOIL_LATEST",sf))
    cands=[("SAFE",lambda:GuardedMarketMind("safe",model)),("BALANCED",lambda:GuardedMarketMind("balanced",model)),("BASE",PredictiveMind)];rows=[]
    for on,of in opps:
        for cn,cf in cands:
            for s in seeds:
                for seat in (0,1):rows.append(_run(cn,cf,on,of,s,seat))
    safe=_summary(rows,"SAFE");bal=_summary(rows,"BALANCED");payload={"experiment":"V56_GUARDED_DUAL","seeds":list(seeds),"soil":sm,"safe":safe,"balanced":bal,"decision":"READY" if safe["passed"] or bal["passed"] else "HOLD","rows":rows};Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(payload,indent=2,sort_keys=True));return payload

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v56/V56_QUALIFICATION.json");ap.add_argument("--model",default="submission/adaptive_market_model.json");ap.add_argument("--seeds",default="5651,5669,5683,5699,5717");a=ap.parse_args();p=run(a.output,a.model,[int(x) for x in a.seeds.split(',') if x.strip()]);print(json.dumps({"decision":p["decision"],"safe":p["safe"],"balanced":p["balanced"]},indent=2,sort_keys=True));
    if p["decision"]!="READY":raise SystemExit(3)
if __name__=="__main__":main()
