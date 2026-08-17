from __future__ import annotations
import json
from pathlib import Path
from collections import Counter
import pandas as pd
from .constants import PRODUCTS,CROPS,ANIMALS,SHOPS,BASE
from .runtime_features import _scan

def load_replay(path):
    with open(path,"r",encoding="utf-8") as f: return json.load(f)

def _get_obs(agent_step):
    return (agent_step or {}).get("observation",{}) or {}

def _action_stats(action):
    z=Counter(); sell={p:0 for p in PRODUCTS}; buy={p:0 for p in PRODUCTS}; seeds={c:0 for c in CROPS}; animals={a:0 for a in ANIMALS}
    if not isinstance(action,dict): action={}
    units=[action.get("farmer",["PASS"])] + (action.get("hands",[]) if isinstance(action.get("hands",[]),list) else [])
    for a in units:
        if isinstance(a,list) and a:
            op=str(a[0]); z[f"unit_{op}"]+=1
            if op=="PLANT" and len(a)>1:z[f"plant_{a[1]}"]+=1
    for o in action.get("market",[]) if isinstance(action.get("market",[]),list) else []:
        if not isinstance(o,list) or not o: continue
        op=str(o[0]); z[f"market_{op}"]+=1
        item=o[1] if len(o)>1 else None
        try:n=int(o[2]) if len(o)>2 else 1
        except Exception:n=1
        if op=="SELL" and item in sell:sell[item]+=n
        elif op=="BUY_PRODUCT" and item in buy:buy[item]+=n
        elif op=="BUY_SEED" and item in seeds:seeds[item]+=n
        elif op=="BUY_ANIMAL" and item in animals:animals[item]+=n
    return z,sell,buy,seeds,animals

def _metadata(data):
    info=data.get("info",{}) or {}; cfg=data.get("configuration",{}) or {}
    eid=info.get("EpisodeId",info.get("episodeId",data.get("id")))
    teams=info.get("TeamNames",info.get("teamNames",[])) or []
    subs=info.get("SubmissionIds",info.get("submissionIds",[])) or []
    return eid,teams,subs,cfg

def replay_to_turn_frame(data, source_path=None, stride=1):
    steps=data.get("steps",[]) or []; eid,teams,subs,cfg=_metadata(data); rows=[]
    final_rewards=[]
    if steps:
        for p in range(len(steps[-1])):
            final_rewards.append(steps[-1][p].get("reward"))
    for step_idx,step in enumerate(steps):
        if step_idx % max(1,int(stride)): continue
        for p,ast in enumerate(step):
            obs=_get_obs(ast); farms=obs.get("farms",[]) or []
            if p>=len(farms): continue
            me=farms[p]; opp=farms[1-p] if len(farms)>1 else {}; mc=_scan(me); oc=_scan(opp)
            priv=obs.get("private",{}) or {}; shed=priv.get("shed",{}) or {}; seedinv=priv.get("seeds",{}) or {}
            market=obs.get("market",{}) or {}; mi=market.get("inventory",{}) or {}; mp=market.get("prices",{}) or {}
            shops=(obs.get("town",{}) or {}).get("unlocked_shops",[]) or []
            zs,sell,buy,bseeds,banimals=_action_stats(ast.get("action",{}))
            row={
              "episode_id":eid if eid is not None else Path(source_path).stem if source_path else None,
              "source_path":str(source_path) if source_path else "", "player":p,"step":step_idx,
              "day":int(obs.get("day",step_idx//24)),"hour":int(obs.get("hour",step_idx%24)),
              "money":float(me.get("money",0)),"final_reward":final_rewards[p] if p<len(final_rewards) else None,
              "team_name":teams[p] if p<len(teams) else None,"submission_id":subs[p] if p<len(subs) else None,
              "quadrants":len(me.get("unlocked_quadrants",["NW"])),"hands":len(me.get("hands",[]) or []),
              "opp_quadrants":len(opp.get("unlocked_quadrants",["NW"])),"opp_hands":len(opp.get("hands",[]) or []),
              "action_json":json.dumps(ast.get("action",{}),sort_keys=True,separators=(",",":")),
            }
            for c in CROPS: row[f"crop_{c}"]=mc[c]; row[f"opp_crop_{c}"]=oc[c]; row[f"seed_{c}"]=int(seedinv.get(c,0) or 0); row[f"buy_seed_{c}"]=bseeds[c]
            for a in ANIMALS: row[f"animal_{a}"]=mc[a]; row[f"opp_animal_{a}"]=oc[a]; row[f"shed_{a}"]=int(shed.get(a,0) or 0); row[f"buy_animal_{a}"]=banimals[a]
            row["pasture"]=mc["PASTURE"]; row["coop"]=mc["COOP"]; row["opp_pasture"]=oc["PASTURE"]; row["opp_coop"]=oc["COOP"]
            for x in PRODUCTS:
                row[f"price_{x}"]=int(mp.get(x,BASE[x]) or BASE[x]); row[f"market_inv_{x}"]=int(mi.get(x,10000) or 10000)
                row[f"shed_{x}"]=int(shed.get(x,0) or 0); row[f"sell_{x}"]=sell[x]; row[f"buy_product_{x}"]=buy[x]
            for s in SHOPS: row[f"shop_{s}"]=sum(str(q)==s for q in shops)
            for k,v in zs.items(): row[k]=v
            rows.append(row)
    df=pd.DataFrame(rows).fillna({}) if rows else pd.DataFrame()
    for c in df.columns:
        if c.startswith(("unit_","market_","plant_")): df[c]=df[c].fillna(0).astype(int)
    return df

def paths_to_turn_frame(paths, stride=1, limit=None):
    frames=[]
    for i,p in enumerate(paths):
        if limit is not None and i>=limit: break
        try: frames.append(replay_to_turn_frame(load_replay(p),p,stride=stride))
        except Exception as e: print(f"WARN replay {p}: {e}")
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()

def add_outcome_labels(df):
    if df.empty:return df
    out=df.copy(); final=out.groupby(["episode_id","player"])["final_reward"].last().unstack("player")
    if 0 in final.columns and 1 in final.columns:
        maps={0:(final[0]>final[1]).astype(float)+(final[0]==final[1]).astype(float)*.5,
              1:(final[1]>final[0]).astype(float)+(final[0]==final[1]).astype(float)*.5}
        out["win_target"]=[maps[int(p)].get(e,.5) for e,p in zip(out.episode_id,out.player)]
        margin0=(final[0]-final[1]).to_dict(); out["final_margin"]=[margin0.get(e,0)*(1 if int(p)==0 else -1) for e,p in zip(out.episode_id,out.player)]
    return out

def add_future_opponent_sell_labels(df,horizon=24):
    if df.empty:return df
    out=df.sort_values(["episode_id","player","step"]).copy()
    key=["episode_id","step","player"]
    opp=out[["episode_id","step","player"]+[f"sell_{p}" for p in PRODUCTS]].copy(); opp["player"]=1-opp["player"]
    opp=opp.rename(columns={f"sell_{p}":f"opp_sell_now_{p}" for p in PRODUCTS})
    out=out.merge(opp,on=key,how="left")
    for prod in PRODUCTS:
        src=f"opp_sell_now_{prod}"; dst=f"opp_sell_next{horizon}_{prod}"
        out[dst]=0.0
        for _,idx in out.groupby(["episode_id","player"],sort=False).groups.items():
            vals=out.loc[idx,src].fillna(0).to_numpy(float); n=len(vals); fut=[0.0]*n
            s=0.0
            for i in range(n-1,-1,-1):
                if i+1<n:s+=vals[i+1]
                if i+horizon+1<n:s-=vals[i+horizon+1]
                fut[i]=s
            out.loc[idx,dst]=fut
    return out
