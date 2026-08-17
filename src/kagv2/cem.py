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
    """Classic scalar-objective CEM retained for controlled experiments."""
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


def robust_population_score(values, weights=None, worst_weight=.30, cvar_weight=.20, cvar_alpha=.25):
    """Score a policy against an opponent population without chasing one peak.

    ``values`` are matchup utilities, ideally win-rate minus 0.5.  The objective
    blends empirical-population expectation, worst archetype, and lower-tail
    CVaR.  This is intentionally conservative; a pure best response is still
    available by setting both risk weights to zero.
    """
    v=np.asarray(values,float).reshape(-1)
    if not len(v) or not np.isfinite(v).all():return -1e18
    if weights is None:w=np.ones(len(v))/len(v)
    else:
        w=np.maximum(0,np.asarray(weights,float).reshape(-1))
        if len(w)!=len(v):raise ValueError("weights/value length mismatch")
        w=w/w.sum() if w.sum()>0 else np.ones(len(v))/len(v)
    mean=float(np.dot(w,v));worst=float(np.min(v))
    k=max(1,int(np.ceil(float(cvar_alpha)*len(v))));cvar=float(np.mean(np.sort(v)[:k]))
    ww=max(0.,float(worst_weight));cw=max(0.,float(cvar_weight));mw=max(0.,1.-ww-cw)
    norm=max(1e-12,mw+ww+cw)
    return (mw*mean+ww*worst+cw*cvar)/norm


def cem_optimize_population(eval_vector_fn,opponent_weights=None,iterations=8,population=48,elite_frac=.2,
                            seed=20260817,init=DEFAULT,sigma=None,worst_weight=.30,cvar_weight=.20,
                            cvar_alpha=.25,callback=None):
    """CEM whose evaluator returns one utility per opponent/archetype.

    The optimizer never runs in the live Kaggle hot path.  It produces policies
    that are later distilled into the policy zoo / meta-equilibrium artifact.
    """
    rng=np.random.default_rng(seed);mu=np.asarray(init,float).copy();sig=np.asarray(sigma if sigma is not None else (HIGH-LOW)*.20,float)
    hist=[];best=(-1e18,None,None,None);k=max(2,int(population*elite_frac))
    for it in range(iterations):
        pop=np.clip(rng.normal(mu,sig,size=(population,len(mu))),LOW,HIGH);scores=[];vectors=[]
        for x in pop:
            vec=np.asarray(eval_vector_fn(decode(x)),float).reshape(-1);vectors.append(vec)
            s=robust_population_score(vec,opponent_weights,worst_weight,cvar_weight,cvar_alpha);scores.append(s)
            if s>best[0]:best=(s,x.copy(),decode(x),vec.copy())
        order=np.argsort(scores)[::-1];elite=pop[order[:k]];mu=.7*mu+.3*elite.mean(0);sig=np.maximum(.03*(HIGH-LOW),.7*sig+.3*elite.std(0))
        rec={"iteration":it,"best":float(max(scores)),"mean":float(np.mean(scores)),"global_best":float(best[0]),"params":best[2],
             "matchup_vector":best[3].tolist() if best[3] is not None else None,
             "worst_weight":float(worst_weight),"cvar_weight":float(cvar_weight),"cvar_alpha":float(cvar_alpha)};hist.append(rec)
        if callback:callback(rec)
    return best[2],hist

def save_search(path,best,history):
    Path(path).write_text(json.dumps({"best":best,"history":history},indent=2))
