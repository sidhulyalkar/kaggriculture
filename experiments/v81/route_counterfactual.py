from __future__ import annotations

import argparse
import importlib.util
import json
import math
import pathlib
import statistics
from concurrent.futures import ProcessPoolExecutor

PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
SHOPS=("BAKERY","BRUNCH_SPOT","FARMERS_MARKET","ICE_CREAM_SHOP","PET_CAFE","PIZZA_SHOP","SMOOTHIE_SHOP","YARN_STORE")


def _load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def _get(v,k,d=None):
    if isinstance(v,dict): return v.get(k,d)
    g=getattr(v,'get',None)
    return g(k,d) if callable(g) else getattr(v,k,d)

def _farm(obs,seat): return list(_get(obs,'farms',[]) or [])[seat]

def _tile_stats(farm):
    plants=pastures=coops=0
    for row in (_get(farm,'tiles',[]) or []):
        for t in row or []:
            if isinstance(t,str): kind=t
            else: kind=_get(t,'kind','') if t is not None else ''
            if kind=='PLANT' or (t is not None and not isinstance(t,str) and _get(t,'crop')): plants+=1
            elif kind=='PASTURE': pastures+=1
            elif kind=='COOP': coops+=1
    return plants,pastures,coops

def features(obs,seat):
    me,op=_farm(obs,seat),_farm(obs,1-seat)
    pm,psm,cm=_tile_stats(me); po,pso,co=_tile_stats(op)
    market=_get(obs,'market',{}) or {}; inv=_get(market,'inventory',{}) or {}; px=_get(market,'prices',{}) or {}
    shops=list(_get(_get(obs,'town',{}) or {},'unlocked_shops',[]) or [])
    priv=_get(obs,'private',{}) or {}; shed=_get(priv,'shed',{}) or {}
    f={
      'money_diff':float(_get(me,'money',0) or 0)-float(_get(op,'money',0) or 0),
      'plants_me':pm,'plants_opp':po,'plant_diff':pm-po,
      'pastures_me':psm,'pastures_opp':pso,'pasture_diff':psm-pso,
      'coops_me':cm,'coops_opp':co,'coop_diff':cm-co,
      'hands_me':len(_get(me,'hands',[]) or []),'hands_opp':len(_get(op,'hands',[]) or []),
      'quadrants_me':len(_get(me,'unlocked_quadrants',[]) or []),'quadrants_opp':len(_get(op,'unlocked_quadrants',[]) or []),
    }
    for p in PRODUCTS:
      f['px_'+p]=float(_get(px,p,0) or 0);f['inv_'+p]=float(_get(inv,p,0) or 0);f['shed_'+p]=float(_get(shed,p,0) or 0)
    for s in SHOPS:
      f['shop_'+s]=shops.count(s)
      f['first_'+s]=1 if shops and shops[0]==s else 0
    return f

def _run_one(args):
    import kagsim
    base_path,opp_path,seed,seat,forced=args
    ours=_load(base_path,f'ours_{seed}_{seat}_{forced}_{id(args)}')
    opp=_load(opp_path,f'opp_{seed}_{seat}_{forced}_{id(args)}')
    ours._select_route=lambda observation,s: forced
    captured={}
    def a(obs):
      st=_get(obs,'step',None); st=int(st) if st is not None else int(_get(obs,'day',0) or 0)*24+int(_get(obs,'hour',0) or 0)
      if st==360 and not captured: captured.update(features(obs,seat))
      return ours.agent(obs)
    g=kagsim.Game(seed)
    while not g.done:
      if seat==0:g.step(a(g.observe(0)),opp.agent(g.observe(1)))
      else:g.step(opp.agent(g.observe(0)),a(g.observe(1)))
    return {'seed':seed,'seat':seat,'opponent':pathlib.Path(opp_path).stem,'route':forced,
            'margin':float(g.reward(seat)-g.reward(1-seat)),'features':captured}

def paired_rows(base,opponents,seeds,workers):
    tasks=[]
    for opp in opponents:
      for seed in seeds:
       for seat in (0,1):
        tasks.extend([(base,opp,seed,seat,0),(base,opp,seed,seat,1)])
    with ProcessPoolExecutor(max_workers=workers) as ex: raw=list(ex.map(_run_one,tasks,chunksize=1))
    by={}
    for r in raw: by.setdefault((r['seed'],r['seat'],r['opponent']),{})[r['route']]=r
    out=[]
    for key,d in by.items():
      if 0 not in d or 1 not in d:continue
      f=d[0]['features'];out.append({**{'seed':key[0],'seat':key[1],'opponent':key[2]},**f,
        'margin0':d[0]['margin'],'margin1':d[1]['margin'],'delta':d[1]['margin']-d[0]['margin']})
    return out

def _thresholds(vals):
    u=sorted(set(float(x) for x in vals))
    if len(u)<=1:return []
    if len(u)>20:
      qs=[]
      for i in range(1,20):qs.append(u[min(len(u)-1,round(i*(len(u)-1)/20))])
      u=sorted(set(qs))
    return [(a+b)/2 for a,b in zip(u,u[1:])]

def _sse(rows):
    if not rows:return 0.0
    ys=[r['delta'] for r in rows];m=sum(ys)/len(ys);return sum((y-m)**2 for y in ys)

def fit_tree(rows,depth=2,min_leaf=6):
    def rec(rs,d):
      mean=sum(r['delta'] for r in rs)/len(rs)
      node={'n':len(rs),'mean_delta':mean}
      if d<=0 or len(rs)<2*min_leaf:return node
      best=None
      feature_names=[k for k in rs[0] if k not in {'seed','seat','opponent','margin0','margin1','delta'}]
      parent=_sse(rs)
      for f in feature_names:
        for thr in _thresholds([r[f] for r in rs]):
          left=[r for r in rs if float(r[f])<=thr];right=[r for r in rs if float(r[f])>thr]
          if len(left)<min_leaf or len(right)<min_leaf:continue
          loss=_sse(left)+_sse(right);gain=parent-loss
          if best is None or gain>best[0]:best=(gain,f,thr,left,right)
      if best and best[0]>0:
        _,f,thr,left,right=best
        node.update({'feature':f,'threshold':thr,'left':rec(left,d-1),'right':rec(right,d-1),'gain':best[0]})
      return node
    return rec(rows,depth)

def predict(tree,row):
    n=tree
    while 'feature' in n:n=n['left'] if float(row[n['feature']])<=n['threshold'] else n['right']
    return n['mean_delta']

def emit_expr(tree):
    if 'feature' not in tree:
      m=tree['mean_delta']
      if m>500:return '1'
      if m<-500:return '0'
      return '_v81_original(observation, seat)'
    f=tree['feature'];thr=tree['threshold']
    return f"({emit_expr(tree['left'])} if _v81_f(observation, seat, {f!r}) <= {thr!r} else {emit_expr(tree['right'])})"

def append_router(source,tree):
    expr=emit_expr(tree)
    extra='''\n\n# V81 counterfactual three-day router. Learned only over the existing prefix-compatible\n# 360..431 continuations; physical execution and all other turns remain unchanged.\n_v81_original = _select_route\ndef _v81_f(observation, seat, name):\n    return _v81_features(observation, seat).get(name, 0.0)\ndef _v81_features(observation, seat):\n    market=_get(observation, "market", {}) or {}; inv=_get(market,"inventory",{}) or {}; px=_get(market,"prices",{}) or {}\n    town=_get(observation,"town",{}) or {}; shops=list(_get(town,"unlocked_shops",[]) or [])\n    me=_farm(observation,seat); op=_farm(observation,1-seat)\n    def ts(farm):\n        plants=pastures=coops=0\n        for row in (_get(farm,"tiles",[]) or []):\n            for t in row or []:\n                kind=t if isinstance(t,str) else (_get(t,"kind","") if t is not None else "")\n                if kind=="PLANT" or (t is not None and not isinstance(t,str) and _get(t,"crop")): plants+=1\n                elif kind=="PASTURE": pastures+=1\n                elif kind=="COOP": coops+=1\n        return plants,pastures,coops\n    pm,psm,cm=ts(me);po,pso,co=ts(op);priv=_get(observation,"private",{}) or {};shed=_get(priv,"shed",{}) or {}\n    f={"money_diff":float(_get(me,"money",0) or 0)-float(_get(op,"money",0) or 0),"plants_me":pm,"plants_opp":po,"plant_diff":pm-po,"pastures_me":psm,"pastures_opp":pso,"pasture_diff":psm-pso,"coops_me":cm,"coops_opp":co,"coop_diff":cm-co,"hands_me":len(_get(me,"hands",[]) or []),"hands_opp":len(_get(op,"hands",[]) or []),"quadrants_me":len(_get(me,"unlocked_quadrants",[]) or []),"quadrants_opp":len(_get(op,"unlocked_quadrants",[]) or [])}\n    for p in _PRODUCTS: f["px_"+p]=float(_get(px,p,0) or 0);f["inv_"+p]=float(_get(inv,p,0) or 0);f["shed_"+p]=float(_get(shed,p,0) or 0)\n    for s in ("BAKERY","BRUNCH_SPOT","FARMERS_MARKET","ICE_CREAM_SHOP","PET_CAFE","PIZZA_SHOP","SMOOTHIE_SHOP","YARN_STORE"):\n        f["shop_"+s]=shops.count(s);f["first_"+s]=1 if shops and shops[0]==s else 0\n    return f\ndef _select_route(observation, seat):\n    return EXPR\n'''.replace('EXPR',expr)
    return source+extra

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--opponents',nargs='+',required=True);ap.add_argument('--out',required=True);ap.add_argument('--start-seed',type=int,default=97001);ap.add_argument('--seeds',type=int,default=8);ap.add_argument('--workers',type=int,default=4)
    a=ap.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    rows=paired_rows(a.base,a.opponents,range(a.start_seed,a.start_seed+a.seeds),a.workers)
    tree=fit_tree(rows,depth=2,min_leaf=max(4,len(rows)//12))
    source=pathlib.Path(a.base).read_text();candidate=append_router(source,tree);compile(candidate,'v81_counterfactual.py','exec')
    (out/'train_rows.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'tree.json').write_text(json.dumps(tree,indent=2)+'\n');(out/'v81_counterfactual.py').write_text(candidate)
    base_correct=sum((r['delta']>0)==(0<0) for r in [])
    pred=sum((predict(tree,r)>0)==(r['delta']>0) for r in rows)/len(rows)
    print('ROWS',len(rows),'TREE_ACCURACY',round(pred,4));print(json.dumps(tree,indent=2));print('EXPR',emit_expr(tree))

if __name__=='__main__':main()
