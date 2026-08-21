#!/usr/bin/env python3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, importlib.util, json, os, shutil, subprocess, sys, tarfile
import numpy as np
import pandas as pd

KNOWN={
 'melon':'kaggriculture-frontier-the-moon-counts-melons',
 'ranker':'kaggriculture-rank-your-agent',
 'adaptive':'adaptive-farming-strategy-for-kaggriculture',
 'soil':'kaggriculture-frontier-the-soil-remembers-rain',
 'strict':'25-27-strict-future-v27-midgame-meta-reset',
 'weed_slip':'weed-slip',
}
CHECKS=(144,216,288,360)
SEEDS=list(range(43001,43065))
V32_NAMES=('SUBMIT_V32_RUNTIME_VERIFIED.tar.gz','SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz')

def safe_extract(tar_path,dest):
    tar_path,dest=Path(tar_path),Path(dest)
    if dest.exists():shutil.rmtree(dest)
    dest.mkdir(parents=True,exist_ok=True);mains=[]
    with tarfile.open(tar_path,'r:*') as tf:
        for m in tf.getmembers():
            rel=Path(m.name)
            if rel.is_absolute() or '..' in rel.parts or not m.isfile():continue
            fh=tf.extractfile(m)
            if fh is None:continue
            out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(fh.read())
            if rel.name=='main.py':mains.append(out)
    if not mains:raise RuntimeError('archive has no main.py: '+str(tar_path))
    mains.sort(key=lambda p:(len(p.relative_to(dest).parts),str(p)));root=dest/'main.py'
    if mains[0]!=root:shutil.copy2(mains[0],root)
    return root

def copy_tree(src,dst):
    src,dst=Path(src),Path(dst)
    if dst.exists():shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in src.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if p.suffix.lower() in {'.ipynb','.html','.log'}:continue
        q=dst/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    main=dst/'main.py'
    return main if main.exists() else None

def find_v32(inp):
    for n in V32_NAMES:
        h=list(Path(inp).rglob(n))
        if h:return h[0]
    raise FileNotFoundError('exact V32 archive missing')

def discover(inp,work,key,pattern):
    roots=[]
    for p in Path(inp).rglob('submission.tar.gz'):
        if pattern in str(p.parent).lower():roots.append(('tar',p))
    for p in Path(inp).rglob('main.py'):
        if pattern in str(p.parent).lower() and '__pycache__' not in p.parts:roots.append(('main',p))
    if not roots:return None
    roots.sort(key=lambda x:(0 if x[0]=='tar' else 1,len(str(x[1])),str(x[1])));typ,p=roots[0]
    main=safe_extract(p,work/'agents'/key) if typ=='tar' else copy_tree(p.parent,work/'agents'/key)
    return main.parent if main and main.exists() else None

WORKER=r'''from pathlib import Path
import importlib.util,json,sys,traceback
croot=Path(sys.argv[1]);oroot=Path(sys.argv[2]);repo=Path(sys.argv[3]);seed=int(sys.argv[4]);seat=int(sys.argv[5])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/'src'))
from src.kagv2.simulator import Game
CHECKS={144,216,288,360}
def load(root,name):
    old=list(sys.path);sys.path.insert(0,str(root))
    try:
        p=root/'main.py';spec=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
        fn=getattr(m,'agent',None) or getattr(m,'main',None) or getattr(m,'v40_frontier_agent',None)
        if callable(fn):return fn
        vals=[v for k,v in vars(m).items() if callable(v) and getattr(v,'__module__',None)==m.__name__ and not k.startswith('_')]
        if not vals:raise RuntimeError('no callable '+str(p))
        return vals[-1]
    finally:sys.path[:]=old
def call(fn,obs):
    try:return fn(obs)
    except TypeError:return fn(obs,None)
def feats(g,p,step):
    f=g.farms[p];o=g.farms[1-p];pr=g.priv[p];tiles=[t for row in f['tiles'] for t in row]
    crops={};animals={};weeds=0;empty=0
    for t in tiles:
        if t is None:empty+=1
        elif isinstance(t,dict):
            if t.get('kind')=='WEED':weeds+=1
            if t.get('kind')=='PLANT':c=t.get('crop','?');crops[c]=crops.get(c,0)+1
            if 'animal' in t:a=t['animal'];animals[a]=animals.get(a,0)+1
    prices=g.market.get('prices',{})
    return {f's{step}_cash':float(f['money']),f's{step}_opp_cash':float(o['money']),f's{step}_cash_gap':float(f['money']-o['money']),
      f's{step}_hands':len(f.get('hands',[])),f's{step}_opp_hands':len(o.get('hands',[])),f's{step}_land':len(f.get('unlocked_quadrants',[])),f's{step}_opp_land':len(o.get('unlocked_quadrants',[])),
      f's{step}_weeds':weeds,f's{step}_empty':empty,f's{step}_shed_total':sum((pr.get('shed',{}) or {}).values()),
      f's{step}_wheat':crops.get('WHEAT',0),f's{step}_strawberry':crops.get('STRAWBERRY',0),f's{step}_melon':crops.get('MELON',0),
      f's{step}_cow':animals.get('COW',0),f's{step}_sheep':animals.get('SHEEP',0),f's{step}_chicken':animals.get('CHICKEN',0),
      f's{step}_p_wheat':float(prices.get('WHEAT',0)),f's{step}_p_strawberry':float(prices.get('STRAWBERRY',0)),f's{step}_p_melon':float(prices.get('MELON',0)),f's{step}_p_milk':float(prices.get('MILK',0)),f's{step}_p_wool':float(prices.get('WOOL',0)),
      f's{step}_shops_n':len(g.town.get('unlocked_shops',[])),f's{step}_shops':'|'.join(sorted(g.town.get('unlocked_shops',[])))}
try:
    C=load(croot,'cand');O=load(oroot,'opp');g=Game(seed=seed);trace={}
    for _ in range(g.episode_steps-1):
        obs0=g.obs(0);obs1=g.obs(1);acts=[None,None]
        if seat==0:acts[0]=call(C,obs0);acts[1]=call(O,obs1)
        else:acts[0]=call(O,obs0);acts[1]=call(C,obs1)
        g.step_once(acts)
        if g.step in CHECKS:trace.update(feats(g,seat,g.step))
    cash=[f['money'] for f in g.farms];cc,oc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0])
    print(json.dumps({'ok':True,'cash':float(cc),'opp_cash':float(oc),'score':1.0 if cc>oc else .5 if cc==oc else 0.0,'margin':float(cc-oc),**trace}))
except BaseException as e:print(json.dumps({'ok':False,'error':repr(e),'traceback':traceback.format_exc()[-2500:]}))
'''

def run_one(worker,croot,oroot,repo,seed,seat):
    try:r=subprocess.run([sys.executable,str(worker),str(croot),str(oroot),str(repo),str(seed),str(seat)],capture_output=True,text=True,timeout=180)
    except subprocess.TimeoutExpired:return {'ok':False,'error':'timeout'}
    for line in reversed(r.stdout.splitlines()):
        try:return json.loads(line)
        except Exception:pass
    return {'ok':False,'error':(r.stderr or r.stdout)[-2000:]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',default='/kaggle/input');ap.add_argument('--repo',required=True);ap.add_argument('--work',default='/kaggle/working/v43_regime_atlas');ap.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 2));a=ap.parse_args()
    inp=Path(a.input_root);repo=Path(a.repo);work=Path(a.work)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    v32=safe_extract(find_v32(inp),work/'agents'/'v32');agents={'v32':v32.parent}
    for k,p in KNOWN.items():
        root=discover(inp,work,k,p)
        if root:agents[k]=root
    core=[x for x in ('melon','ranker','adaptive') if x in agents]
    if not core:raise RuntimeError('Attach Melon, Ranker, or Adaptive')
    print('frontier family:',core)
    worker=work/'regime_worker.py';worker.write_text(WORKER)
    jobs=[(o,s,t) for o in core for s in SEEDS for t in (0,1)];rows=[]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        fs={ex.submit(run_one,worker,agents['v32'],agents[o],repo,s,t):(o,s,t) for o,s,t in jobs}
        for i,f in enumerate(as_completed(fs),1):
            o,s,t=fs[f];rows.append({'opponent':o,'seed':s,'seat':t,**f.result()})
            if i%50==0 or i==len(fs):print(' completed',i,'/',len(fs))
    games=pd.DataFrame(rows);games.to_csv(work/'V43_REGIME_GAMES.csv',index=False);good=games[games.ok==True].copy()
    seed_out=good.groupby('seed').agg(family_score=('score','mean'),family_margin=('margin','mean'),family_cash=('cash','mean'),n_games=('score','size')).reset_index();seed_out['hard_regime']=(seed_out.family_score<.34).astype(int)
    exclude={'ok','cash','opp_cash','score','margin','seed','seat','opponent','error','traceback'};numcols=[c for c in good.columns if c not in exclude and pd.api.types.is_numeric_dtype(good[c])];feat=good.groupby('seed')[numcols].mean().reset_index()
    for step in CHECKS:
        col=f's{step}_shops'
        if col in good.columns:
            allshops=sorted({x for s in good[col].dropna().astype(str) for x in s.split('|') if x})
            for shop in allshops:
                q=good[['seed',col]].copy();q['v']=q[col].astype(str).str.split('|').apply(lambda z:int(shop in z));feat=feat.merge(q.groupby('seed').v.mean().reset_index(name=f's{step}_shop_{shop}'),on='seed',how='left')
    data=seed_out.merge(feat,on='seed',how='left');data.to_csv(work/'V43_REGIME_FEATURES.csv',index=False)
    from sklearn.tree import DecisionTreeClassifier,export_text
    from sklearn.model_selection import StratifiedKFold,cross_val_score
    y=data.hard_regime.values;feature_cols=[c for c in data.columns if c not in {'seed','family_score','family_margin','family_cash','n_games','hard_regime'}];X=data[feature_cols].replace([np.inf,-np.inf],np.nan).fillna(0)
    if len(np.unique(y))>=2 and min(np.bincount(y))>=3:
        folds=min(5,int(min(np.bincount(y))));cv=StratifiedKFold(n_splits=folds,shuffle=True,random_state=43000);rr=[]
        for d in (1,2,3,4):
            m=DecisionTreeClassifier(max_depth=d,min_samples_leaf=max(3,len(data)//16),class_weight='balanced',random_state=43000);rr.append({'depth':d,'cv_auc':float(cross_val_score(m,X,y,cv=cv,scoring='roc_auc').mean()),'cv_balanced_accuracy':float(cross_val_score(m,X,y,cv=cv,scoring='balanced_accuracy').mean())})
        cvtab=pd.DataFrame(rr).sort_values(['cv_auc','cv_balanced_accuracy'],ascending=False);bd=int(cvtab.iloc[0].depth);m=DecisionTreeClassifier(max_depth=bd,min_samples_leaf=max(3,len(data)//16),class_weight='balanced',random_state=43000);m.fit(X,y);rules=export_text(m,feature_names=list(X.columns),decimals=2)
    else:cvtab=pd.DataFrame([{'depth':None,'cv_auc':None,'cv_balanced_accuracy':None}]);rules='Insufficient class balance.'
    cvtab.to_csv(work/'V43_REGIME_MODEL_CV.csv',index=False);(work/'V43_REGIME_RULES.txt').write_text(rules)
    hard=data[data.hard_regime==1];easy=data[data.hard_regime==0];rr=[]
    for c in feature_cols:
        hm=float(hard[c].mean()) if len(hard) else np.nan;em=float(easy[c].mean()) if len(easy) else np.nan;sd=float(data[c].std());sd=sd if np.isfinite(sd) and sd else 1.0;rr.append({'feature':c,'hard_mean':hm,'easy_mean':em,'standardized_gap':(hm-em)/sd})
    diff=pd.DataFrame(rr);diff['abs_gap']=diff.standardized_gap.abs();diff=diff.sort_values('abs_gap',ascending=False);diff.to_csv(work/'V43_REGIME_DIFFERENCES.csv',index=False)
    decision={'version':'43R','name':'Hard-Regime Atlas','frontier_family':core,'seeds':SEEDS,'games':int(len(games)),'valid_games':int((games.ok==True).sum()),'hard_seeds':int(data.hard_regime.sum()),'easy_seeds':int((1-data.hard_regime).sum()),'hard_definition':'mean V32 score vs attached Melon/Ranker/Adaptive family < 0.34','best_tree_cv':cvtab.iloc[0].to_dict(),'top_regime_features':diff.head(12)[['feature','hard_mean','easy_mean','standardized_gap']].to_dict('records'),'next_use':'Use earliest stable features to define shared-prefix V43 branches; do not directly switch into incompatible parent state.'}
    (work/'V43_REGIME_DECISION.json').write_text(json.dumps(decision,indent=2,default=str));print(json.dumps(decision,indent=2,default=str));print(rules)
if __name__=='__main__':main()
