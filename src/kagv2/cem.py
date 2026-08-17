from __future__ import annotations
import json
from pathlib import Path
import numpy as np

PARAM_NAMES=[
 "hands_early","hands_mid","hands_late","cow_mid","sheep_mid","cow_late","sheep_late",
 "q1_wheat","q1_melon","mid_wheat","mid_melon","late_wheat",
 "reserve_strawberry","reserve_melon","reserve_milk","reserve_wool","reserve_fertilizer","terminal_start"
]
DEFAULT=np.array([3,8,13,6,4,8,6,7,11,7,12,19,.52,.78,.52,.55,.32,26],float)
LOW=np.array([1,3,7,2,1,4,2,3,4,3,0,8,.25,.45,.25,.30,.10,12],float)
HIGH=np.array([8,13,16,10,10,12,12,15,18,25,20,35,.85,.95,.85,.90,.70,60],float)
INT_FIELDS=set(PARAM_NAMES[:12]+["terminal_start"])

def decode(x):
    x=np.clip(np.asarray(x,float),LOW,HIGH);d={}
    for n,v in zip(PARAM_NAMES,x):d[n]=int(round(v)) if n in INT_FIELDS else float(v)
    return d

def cem_optimize(eval_fn,iterations=8,population=48,elite_frac=.2,seed=20260816,init=DEFAULT,sigma=None,callback=None):
    rng=np.random.default_rng(seed);mu=np.asarray(init,float).copy();sig=np.asarray(sigma if sigma is not None else (HIGH-LOW)*.20,float)
    hist=[];best=(-1e18,None,None)
    k=max(2,int(population*elite_frac))
    for it in range(iterations):
        pop=np.clip(rng.normal(mu,sig,size=(population,len(mu))),LOW,HIGH);scores=[]
        for x in pop:
            s=float(eval_fn(decode(x)));scores.append(s)
            if s>best[0]:best=(s,x.copy(),decode(x))
        order=np.argsort(scores)[::-1];elite=pop[order[:k]];mu=.7*mu+.3*elite.mean(0);sig=np.maximum(.03*(HIGH-LOW),.7*sig+.3*elite.std(0))
        rec={"iteration":it,"best":float(max(scores)),"mean":float(np.mean(scores)),"global_best":float(best[0]),"params":best[2]};hist.append(rec)
        if callback:callback(rec)
    return best[2],hist

def save_search(path,best,history):
    Path(path).write_text(json.dumps({"best":best,"history":history},indent=2))
