from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from kaggle_environments import make

from baselines.v1.counter_agent import CounterMeta, TournamentMind
from submission.adaptive_market_agent import AdaptiveMarketMind
from submission.predictive_agent import PredictiveMind
from swarm.v77_live_meta_route_search import recover_soil_parent


def _agent_for(mind):
    def agent(obs,configuration=None):return mind.act(obs)
    return agent


def _money(last,player):
    for owner in (0,1):
        try:
            obs=last[owner].observation;farms=obs["farms"] if isinstance(obs,dict) else obs.farms;farm=farms[player]
            return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
        except Exception:pass
    try:return float(last[player].reward or 0)
    except Exception:return 0.0


def _run(candidate_name,candidate_factory,opponent_name,opponent_factory,seed,seat):
    candidate=candidate_factory();opponent=opponent_factory();env=make("kaggriculture",configuration={"seed":int(seed)},debug=False)
    ca=_agent_for(candidate);oa=_agent_for(opponent) if not isinstance(opponent,str) else opponent;agents=[ca,oa] if seat==0 else [oa,ca]
    try:
        env.run(agents);last=env.steps[-1];statuses=[str(last[i].status) for i in (0,1)];cash=_money(last,seat);opp=_money(last,1-seat)
        row={"candidate":candidate_name,"opponent":opponent_name,"seed":int(seed),"seat":int(seat),"ok":all(x=="DONE" for x in statuses),"statuses":statuses,
             "cash":cash,"opp_cash":opp,"margin":cash-opp,"score":1.0 if cash>opp else .5 if cash==opp else 0.0}
        if isinstance(candidate,AdaptiveMarketMind):row.update(interventions=int(candidate.intervention_count),intervention_units=int(candidate.intervention_units),intervention_by_product=dict(candidate.intervention_by_product))
        return row
    except BaseException as exc:return {"candidate":candidate_name,"opponent":opponent_name,"seed":int(seed),"seat":int(seat),"ok":False,"error":f"{type(exc).__name__}: {exc}"[:500]}


def _mean(xs,default=0.0):
    xs=list(xs);return statistics.mean(xs) if xs else default


def _candidate_summary(rows,name):
    valid=[r for r in rows if r.get("ok")];base={(r["opponent"],int(r["seed"]),int(r["seat"])):r for r in valid if r["candidate"]=="BASE"}
    cand={(r["opponent"],int(r["seed"]),int(r["seat"])):r for r in valid if r["candidate"]==name};keys=sorted(set(base)&set(cand));families=[]
    for opp in sorted({k[0] for k in keys}):
        kk=[k for k in keys if k[0]==opp];sd=[cand[k]["score"]-base[k]["score"] for k in kk];md=[cand[k]["margin"]-base[k]["margin"] for k in kk]
        families.append({"opponent":opp,"pairs":len(kk),"score_delta":_mean(sd),"margin_delta":_mean(md),"candidate_score":_mean(cand[k]["score"] for k in kk)})
    sd=[cand[k]["score"]-base[k]["score"] for k in keys];md=[cand[k]["margin"]-base[k]["margin"] for k in keys]
    cr=[r for r in valid if r["candidate"]==name];interventions=sum(int(r.get("interventions",0)) for r in cr);units=sum(int(r.get("intervention_units",0)) for r in cr)
    worst=min((float(f["score_delta"]) for f in families),default=-1.0);worst_margin=min((float(f["margin_delta"]) for f in families),default=-1e9)
    all_valid=len(cr)==len([r for r in rows if r["candidate"]==name]) and len(keys)>0
    passed=bool(all_valid and interventions>0 and _mean(sd)>=0.0 and _mean(md)>0.0 and worst>=-.10 and worst_margin>=-1500.0)
    return {"candidate":name,"pairs":len(keys),"all_valid":all_valid,"score_delta":_mean(sd),"margin_delta":_mean(md),"worst_family_score_delta":worst,"worst_family_margin_delta":worst_margin,
            "interventions":interventions,"intervention_units":units,"families":families,"passed":passed}


def _soil_factory(root):
    try:
        src,meta=recover_soil_parent(root,max_version=1);path=root/"soil_latest.py";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(src,encoding="utf-8");compile(src,str(path),"exec")
        return (lambda:str(path)),meta
    except Exception as exc:return None,{"status":"unavailable","error":f"{type(exc).__name__}: {exc}"[:300]}


def run(output,model_path,seeds):
    root=Path(output).parent;soil_factory,soil_meta=_soil_factory(root/"soil")
    opponents=[("INCUMBENT",PredictiveMind),("V1_TOURNAMENT",TournamentMind),("V1_COUNTER",CounterMeta)]
    if soil_factory is not None:opponents.append(("SOIL_LATEST",soil_factory))
    candidates=[("ONLINE",lambda:AdaptiveMarketMind(True,model_path)),("OFFLINE",lambda:AdaptiveMarketMind(False,model_path)),("BASE",PredictiveMind)];rows=[]
    for oname,ofactory in opponents:
        for cname,cfactory in candidates:
            for seed in seeds:
                for seat in (0,1):rows.append(_run(cname,cfactory,oname,ofactory,seed,seat))
    online=_candidate_summary(rows,"ONLINE");offline=_candidate_summary(rows,"OFFLINE");passed=[x for x in (online,offline) if x["passed"]];selected=None
    if passed:
        passed.sort(key=lambda x:(x["worst_family_score_delta"],x["score_delta"],x["margin_delta"]),reverse=True);selected=passed[0]["candidate"].lower()
        if online["passed"] and selected=="offline" and online["score_delta"]>=offline["score_delta"]-.02 and online["worst_family_score_delta"]>=offline["worst_family_score_delta"]-.02:selected="online"
    model_file=Path(model_path);model=json.loads(model_file.read_text(encoding="utf-8"));model["selected_mode"]=selected or "offline";model["qualification"]={"selected":selected,"online":online,"offline":offline,"soil":soil_meta,"seeds":list(seeds)};model_file.write_text(json.dumps(model,indent=2,sort_keys=True),encoding="utf-8")
    payload={"experiment":"V55_ADAPTIVE_MARKET_EXACT_ENGINE","seeds":list(seeds),"opponents":[x[0] for x in opponents],"soil":soil_meta,"online":online,"offline":offline,"selected_mode":selected,
             "decision":"BUILD_SUBMISSION" if selected else "HOLD_SUBMISSION","rows":rows}
    Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8");return payload


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="tmp/v55/V55_QUALIFICATION.json");ap.add_argument("--model",default="submission/adaptive_market_model.json");ap.add_argument("--seeds",default="5501,5519,5531,5557,5573")
    a=ap.parse_args();seeds=[int(x) for x in a.seeds.split(",") if x.strip()];p=run(a.output,a.model,seeds);print(json.dumps({k:p[k] for k in ("decision","selected_mode","online","offline","soil")},indent=2,sort_keys=True))
    if p["decision"]!="BUILD_SUBMISSION":raise SystemExit(3)

if __name__=="__main__":main()
