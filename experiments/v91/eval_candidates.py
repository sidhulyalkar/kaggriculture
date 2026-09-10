from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import statistics
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PASS={"farmer":["PASS"],"hands":[],"market":[]}


def load(path):
    p=Path(path).resolve(); name="v91_"+hashlib.sha1(f"{p}:{os.getpid()}:{os.urandom(6).hex()}".encode()).hexdigest()[:16]
    if str(p.parent) not in sys.path: sys.path.insert(0,str(p.parent))
    spec=importlib.util.spec_from_file_location(name,p); mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod)
    fn=getattr(mod,"agent",None)
    if not callable(fn): raise RuntimeError(f"no agent: {p}")
    return fn,name


def call(fn,obs):
    try: return fn(obs)
    except TypeError: return fn(obs,{})


def one(task):
    cand_name,cand_path,opp_name,opp_path,seed,seat,clock_fault=task
    import kagsim
    cm=om=None
    try:
        cf,cm=load(cand_path); of,om=load(opp_path)
        g=kagsim.Game(int(seed)); errors=0
        while not g.done:
            o0=dict(g.observe(0)); o1=dict(g.observe(1))
            if clock_fault:
                (o0 if seat==0 else o1)["step"]=None
            try:
                if seat==0: a0,a1=call(cf,o0),call(of,o1)
                else: a0,a1=call(of,o0),call(cf,o1)
            except Exception:
                errors+=1
                if seat==0: a0,a1=PASS,PASS if of is None else call(of,o1)
                else: a0,a1=PASS if of is None else call(of,o0),PASS
            g.step(a0 or PASS,a1 or PASS)
        mine=float(g.reward(seat) or 0); theirs=float(g.reward(1-seat) or 0)
        return {"candidate":cand_name,"opponent":opp_name,"seed":int(seed),"seat":seat,"clock_fault":clock_fault,"margin":mine-theirs,"mine":mine,"theirs":theirs,"errors":errors}
    except Exception:
        return {"candidate":cand_name,"opponent":opp_name,"seed":int(seed),"seat":seat,"clock_fault":clock_fault,"margin":-1e12,"mine":0,"theirs":0,"errors":999999,"fatal":traceback.format_exc(limit=4)}
    finally:
        if cm: sys.modules.pop(cm,None)
        if om: sys.modules.pop(om,None)


def bt(rows):
    if not rows:return 0.0
    return sum(1.0 if r["margin"]>0 else 0.5 if r["margin"]==0 else 0.0 for r in rows)/len(rows)


def summarize(rows,names,base="c95_clock"):
    out={}
    bykey={(r["candidate"],r["opponent"],r["seed"],r["seat"],r["clock_fault"]):r for r in rows}
    for name in names:
        rr=[r for r in rows if r["candidate"]==name]
        std=[r for r in rr if not r["clock_fault"]]
        per={opp:bt([r for r in std if r["opponent"]==opp]) for opp in sorted({r["opponent"] for r in std})}
        margins=[r["margin"] for r in std]
        rescues=sacrifices=changed=0
        if name!=base:
            for r in std:
                b=bykey.get((base,r["opponent"],r["seed"],r["seat"],False))
                if not b: continue
                bs=1 if b["margin"]>0 else .5 if b["margin"]==0 else 0
                cs=1 if r["margin"]>0 else .5 if r["margin"]==0 else 0
                if abs(r["margin"]-b["margin"])>1e-9: changed+=1
                if bs<1 and cs==1: rescues+=1
                if bs==1 and cs<1: sacrifices+=1
        out[name]={
            "n":len(std),"bt":bt(std),"mean_margin":statistics.mean(margins) if margins else 0,"median_margin":statistics.median(margins) if margins else 0,
            "worst_opponent_bt":min(per.values()) if per else 0,"per_opponent_bt":per,
            "seat0_bt":bt([r for r in std if r["seat"]==0]),"seat1_bt":bt([r for r in std if r["seat"]==1]),
            "errors":sum(r["errors"] for r in rr),"paired_changed":changed,"rescued_base_nonwins":rescues,"sacrificed_base_wins":sacrifices,
            "clock_fault_bt":bt([r for r in rr if r["clock_fault"]]),
        }
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidates',required=True); ap.add_argument('--opponents',required=True); ap.add_argument('--seeds',type=int,default=10); ap.add_argument('--start-seed',type=int,default=310001); ap.add_argument('--workers',type=int,default=4); ap.add_argument('--clock-seeds',type=int,default=2); ap.add_argument('--out',required=True); a=ap.parse_args()
    import kagsim
    assert getattr(kagsim,'ENGINE_VERSION','')=='1.32.7'
    cands={p.parent.name:str(p.resolve()) for p in Path(a.candidates).glob('*/main.py')}
    opps={p.stem:str(p.resolve()) for p in Path(a.opponents).glob('*.py')}
    if 'c95_clock' not in cands: raise SystemExit('c95_clock control missing')
    tasks=[]
    for name,path in cands.items():
        for opp,op in opps.items():
            for seed in range(a.start_seed,a.start_seed+a.seeds):
                for seat in (0,1): tasks.append((name,path,opp,op,seed,seat,False))
            for seed in range(a.start_seed+9000,a.start_seed+9000+a.clock_seeds):
                for seat in (0,1): tasks.append((name,path,opp,op,seed,seat,True))
    print('engine',kagsim.ENGINE_VERSION,'candidates',sorted(cands),'opponents',sorted(opps),'tasks',len(tasks))
    with ProcessPoolExecutor(max_workers=a.workers) as ex: rows=list(ex.map(one,tasks,chunksize=1))
    summary=summarize(rows,sorted(cands))
    payload={'engine':kagsim.ENGINE_VERSION,'start_seed':a.start_seed,'seeds':a.seeds,'opponents':sorted(opps),'summary':summary}
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2)+'\n'); out.with_suffix('.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
    for n,s in sorted(summary.items(),key=lambda kv:(kv[1]['bt'],kv[1]['worst_opponent_bt'],kv[1]['mean_margin']),reverse=True):
        print(f"{n:18s} BT={s['bt']:.3f} worst={s['worst_opponent_bt']:.3f} margin={s['mean_margin']:+.0f} seat={s['seat0_bt']:.3f}/{s['seat1_bt']:.3f} changed={s['paired_changed']} rescue={s['rescued_base_nonwins']} sacrifice={s['sacrificed_base_wins']} clock={s['clock_fault_bt']:.3f} err={s['errors']}")

if __name__=='__main__': main()
