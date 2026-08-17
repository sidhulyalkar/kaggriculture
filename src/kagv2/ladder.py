from __future__ import annotations
import math
import numpy as np
import pandas as pd
from collections import Counter

def action_macro_signature(action_json: str) -> str:
    import json
    try:a=json.loads(action_json)
    except Exception:return "bad"
    counts=Counter()
    units=[a.get("farmer",["PASS"])] + (a.get("hands",[]) if isinstance(a.get("hands",[]),list) else [])
    for u in units:
        if isinstance(u,list) and u: counts[f"u:{u[0]}"]+=1
    for m in a.get("market",[]) if isinstance(a.get("market",[]),list) else []:
        if isinstance(m,list) and m:
            item=m[1] if len(m)>1 else ""; counts[f"m:{m[0]}:{item}"]+=1
    return "|".join(f"{k}={v}" for k,v in sorted(counts.items()))

def entropy(values):
    c=Counter(values); n=sum(c.values())
    if n<=1:return 0.0
    h=-sum((v/n)*math.log(max(v/n,1e-12)) for v in c.values())
    return h/math.log(max(2,len(c)))

def open_loop_report(turn_df, actor_col="submission_id", min_episodes=3):
    d=turn_df.copy()
    if actor_col not in d or d[actor_col].isna().all(): actor_col="team_name" if "team_name" in d else "player"
    d["macro_sig"]=[action_macro_signature(x) for x in d["action_json"].astype(str)]
    rows=[]
    for actor,g in d.groupby(actor_col,dropna=False):
        ne=g["episode_id"].nunique()
        if ne<min_episodes:continue
        hs=[]; weights=[]
        for _,x in g.groupby(["day","hour"]):
            if x["episode_id"].nunique()<2:continue
            hs.append(entropy(x["macro_sig"]));weights.append(len(x))
        mean_h=np.average(hs,weights=weights) if hs else np.nan
        rows.append({actor_col:actor,"episodes":ne,"macro_entropy":mean_h,"open_loop_score":1-mean_h if mean_h==mean_h else np.nan,
                     "mean_reward":pd.to_numeric(g["final_reward"],errors="coerce").mean(),
                     "win_rate":pd.to_numeric(g.get("win_target"),errors="coerce").mean() if "win_target" in g else np.nan})
    return pd.DataFrame(rows).sort_values(["open_loop_score","mean_reward"],ascending=False)

def deduplicated_matchups(turn_df):
    finals=turn_df.sort_values("step").groupby(["episode_id","player"],as_index=False).tail(1)
    if "submission_id" not in finals: finals["submission_id"]=finals.get("team_name",finals["player"])
    a=finals[finals.player==0].set_index("episode_id"); b=finals[finals.player==1].set_index("episode_id"); idx=a.index.intersection(b.index)
    rows=[]
    for e in idx:
        x,y=a.loc[e],b.loc[e]; r0=float(x.final_reward); r1=float(y.final_reward)
        rows.append({"episode_id":e,"a":x.submission_id,"b":y.submission_id,"reward_a":r0,"reward_b":r1,"y":1.0 if r0>r1 else .5 if r0==r1 else 0.0})
    return pd.DataFrame(rows)

def bradley_terry(matchups, l2=2.0, iters=50):
    """Small dependency-free Bradley-Terry fit via Newton updates with reference mean=0."""
    if matchups.empty:return pd.DataFrame(columns=["actor","bt_strength"])
    actors=sorted(set(matchups.a).union(matchups.b)); ix={a:i for i,a in enumerate(actors)}; n=len(actors); w=np.zeros(n)
    for _ in range(iters):
        g=np.zeros(n); h=np.ones(n)*l2
        for r in matchups.itertuples():
            i,j=ix[r.a],ix[r.b]; z=np.clip(w[i]-w[j],-20,20); p=1/(1+np.exp(-z)); y=float(r.y)
            g[i]+=y-p;g[j]-=y-p; q=max(1e-6,p*(1-p));h[i]+=q;h[j]+=q
        step=g/h; w+=step; w-=w.mean()
        if np.max(np.abs(step))<1e-5:break
    return pd.DataFrame({"actor":actors,"bt_strength":w}).sort_values("bt_strength",ascending=False)
