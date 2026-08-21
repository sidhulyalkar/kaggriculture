#!/usr/bin/env python3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile
import numpy as np
import pandas as pd

V32_NAMES=("SUBMIT_V32_RUNTIME_VERIFIED.tar.gz","SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz")
KNOWN={
 "soil":"kaggriculture-frontier-the-soil-remembers-rain",
 "melon":"kaggriculture-frontier-the-moon-counts-melons",
 "ranker":"kaggriculture-rank-your-agent",
 "adaptive":"adaptive-farming-strategy-for-kaggriculture",
 "strict":"25-27-strict-future-v27-midgame-meta-reset",
 "weed_slip":"weed-slip",
 "score3094":"3094-score-kaggriculture",
 "v16":"v16-rc5-high-score-8c-4s-premium-market-lead",
}
CHECKPOINTS=[240,264,288,312,336,360,384]
SEEDS=[41301,41309,41321,41333]


def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def safe_extract(tar_path,dest):
    tar_path,dest=Path(tar_path),Path(dest)
    if dest.exists():shutil.rmtree(dest)
    dest.mkdir(parents=True,exist_ok=True);mains=[]
    with tarfile.open(tar_path,"r:*") as tf:
        for m in tf.getmembers():
            rel=Path(m.name)
            if rel.is_absolute() or ".." in rel.parts or not m.isfile():continue
            fh=tf.extractfile(m)
            if fh is None:continue
            out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(fh.read())
            if rel.name=="main.py":mains.append(out)
    if not mains:raise RuntimeError("archive has no main.py: "+str(tar_path))
    mains.sort(key=lambda p:(len(p.relative_to(dest).parts),str(p)))
    root=dest/"main.py"
    if mains[0]!=root:shutil.copy2(mains[0],root)
    return root


def copy_agent_tree(src,dst):
    src,dst=Path(src),Path(dst)
    if dst.exists():shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in src.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix==".pyc":continue
        if p.suffix.lower() in {".ipynb",".html",".log"}:continue
        q=dst/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    if not (dst/"main.py").exists():raise RuntimeError("copied agent has no main.py")
    return dst/"main.py"


def find_v32(inp):
    for n in V32_NAMES:
        h=list(Path(inp).rglob(n))
        if h:return h[0]
    raise FileNotFoundError("exact V32 archive missing")


def discover_one(inp,key,pattern,work):
    inp=Path(inp);hits=[]
    for p in inp.rglob("submission.tar.gz"):
        if pattern in str(p.parent).lower():hits.append((0,p))
    for p in inp.rglob("main.py"):
        if pattern in str(p.parent).lower() and "__pycache__" not in p.parts:hits.append((1,p))
    if not hits:return None
    hits.sort(key=lambda x:(x[0],len(str(x[1])),str(x[1])));typ,p=hits[0];dst=work/"agents"/key
    if typ==0:main=safe_extract(p,dst);src=str(p)
    else:main=copy_agent_tree(p.parent,dst);src=str(p.parent)
    return {"root":main.parent,"main":main,"source":src}


def discover(inp,work):
    out={}
    for k,pat in KNOWN.items():
        x=discover_one(inp,k,pat,work)
        if x:out[k]=x
    return out


WORKER=r'''from pathlib import Path
import importlib.util,json,sys,time,traceback
candroot=Path(sys.argv[1]);opproot=Path(sys.argv[2]);repo=Path(sys.argv[3]);seed=int(sys.argv[4]);seat=int(sys.argv[5])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/'src'))
from src.kagv2.simulator import Game

def load(root,name):
    old=list(sys.path);sys.path.insert(0,str(root))
    try:
        path=root/'main.py';spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec)
        sys.modules[name]=m;spec.loader.exec_module(m)
        fn=getattr(m,'agent',None) or getattr(m,'main',None) or getattr(m,'v40_frontier_agent',None)
        if callable(fn):return fn
        vals=[v for k,v in vars(m).items() if callable(v) and getattr(v,'__module__',None)==m.__name__ and not k.startswith('_')]
        if not vals:raise RuntimeError('no callable '+str(path))
        return vals[-1]
    finally:sys.path[:]=old

def call(fn,obs):
    try:return fn(obs)
    except TypeError:return fn(obs,None)
try:
    C=load(candroot,'candmod');O=load(opproot,'oppmod');tt=[]
    def A(obs,configuration=None):
        t=time.perf_counter()
        try:return call(C,obs)
        finally:tt.append(time.perf_counter()-t)
    agents=[A,O] if seat==0 else [O,A];cash=Game(seed=seed).run(agents)
    cc,oc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0])
    print(json.dumps({'ok':True,'cash':float(cc),'opp_cash':float(oc),'score':1.0 if cc>oc else .5 if cc==oc else 0.0,
      'margin':float(cc-oc),'mean_ms':1000*sum(tt)/max(1,len(tt)),'max_ms':1000*max(tt) if tt else 0.0}))
except BaseException as e:
    print(json.dumps({'ok':False,'error':repr(e),'traceback':traceback.format_exc()[-2500:]}))
'''


WRAPPER=r'''from pathlib import Path
from copy import deepcopy
import importlib.util
import sys
_SWITCH_STEP=__SWITCH_STEP__
_BASE=Path(__file__).resolve().parent
_V32=None
_SOIL=None

def _load(root,name):
    old=list(sys.path);sys.path.insert(0,str(root))
    try:
        path=root/'main.py';spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec)
        sys.modules[name]=m;spec.loader.exec_module(m)
        fn=getattr(m,'agent',None) or getattr(m,'main',None) or getattr(m,'v40_frontier_agent',None)
        if callable(fn):return fn
        vals=[v for k,v in vars(m).items() if callable(v) and getattr(v,'__module__',None)==m.__name__ and not k.startswith('_')]
        if not vals:raise RuntimeError('no callable '+str(path))
        return vals[-1]
    finally:sys.path[:]=old

def _call(fn,obs,configuration=None):
    try:return fn(obs)
    except TypeError:return fn(obs,configuration)

def agent(observation,configuration=None):
    global _V32,_SOIL
    if _V32 is None:_V32=_load(_BASE/'v32_pkg','v411_v32')
    if _SOIL is None:_SOIL=_load(_BASE/'soil_pkg','v411_soil')
    a=_call(_V32,deepcopy(observation),configuration)
    b=_call(_SOIL,deepcopy(observation),configuration)
    return a if int((observation or {}).get('step',0) or 0)<_SWITCH_STEP else b
'''


def build_hybrid(v32_root,soil_root,out_root,cp):
    out_root=Path(out_root)
    if out_root.exists():shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    shutil.copytree(v32_root,out_root/'v32_pkg');shutil.copytree(soil_root,out_root/'soil_pkg')
    (out_root/'v32_pkg'/'__init__.py').touch();(out_root/'soil_pkg'/'__init__.py').touch()
    text=WRAPPER.replace('__SWITCH_STEP__',str(int(cp)));(out_root/'main.py').write_text(text);compile(text,str(out_root/'main.py'),'exec')
    return out_root


def run_match(worker,croot,oroot,repo,seed,seat):
    try:r=subprocess.run([sys.executable,str(worker),str(croot),str(oroot),str(repo),str(seed),str(seat)],capture_output=True,text=True,timeout=180)
    except subprocess.TimeoutExpired:return {'ok':False,'error':'timeout'}
    for line in reversed(r.stdout.splitlines()):
        try:return json.loads(line)
        except Exception:pass
    return {'ok':False,'error':(r.stderr or r.stdout)[-2500:]}


def tournament(cands,opps,seeds,worker,repo,workers):
    jobs=[(cn,cr,on,orr,s,seat) for cn,cr in cands.items() for on,orr in opps.items() for s in seeds for seat in (0,1)];rows=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fs={ex.submit(run_match,worker,cr,orr,repo,s,seat):(cn,on,s,seat) for cn,cr,on,orr,s,seat in jobs}
        for i,f in enumerate(as_completed(fs),1):
            cn,on,s,seat=fs[f];rows.append({'candidate':cn,'opponent':on,'seed':s,'seat':seat,**f.result()})
            if i%50==0 or i==len(fs):print(' completed',i,'/',len(fs))
    return pd.DataFrame(rows)


def summarize(df):
    keys=['opponent','seed','seat'];ctl=df[(df.candidate=='V32_CONTROL')&(df.ok==True)][keys+['score','margin','cash']].rename(columns={'score':'ctl_score','margin':'ctl_margin','cash':'ctl_cash'});rows=[]
    for name,g in df.groupby('candidate'):
        good=g[g.ok==True].copy();m=good.merge(ctl,on=keys,how='inner');by=good.groupby('opponent').score.mean() if len(good) else pd.Series(dtype=float)
        r={'candidate':name,'games':len(g),'valid_games':len(good),'invalid_games':int((g.ok!=True).sum()),'mean_score':float(good.score.mean()) if len(good) else np.nan,
           'mean_cash':float(good.cash.mean()) if len(good) else np.nan,'mean_margin':float(good.margin.mean()) if len(good) else np.nan,'worst_family_score':float(by.min()) if len(by) else np.nan,
           'direct_v32_score':float(good[good.opponent=='v32'].score.mean()) if len(good[good.opponent=='v32']) else np.nan,'mean_ms':float(good.mean_ms.mean()) if len(good) else np.nan,'max_ms':float(good.max_ms.max()) if len(good) else np.nan}
        if len(m):
            m['d']=m.score-m.ctl_score;r.update(paired_games=len(m),delta_score=float(m.d.mean()),delta_margin=float((m.margin-m.ctl_margin).mean()),worst_delta=float(m.groupby('opponent').d.mean().min()),good_flips=int(((m.score>m.ctl_score)&(m.score>=1)).sum()),bad_flips=int(((m.score<m.ctl_score)&(m.ctl_score>=1)).sum()))
        rows.append(r)
    return pd.DataFrame(rows).sort_values(['delta_score','worst_delta','direct_v32_score','delta_margin'],ascending=False).reset_index(drop=True)


def package_tree(root,out):
    with tarfile.open(out,'w:gz') as tf:
        for p in sorted(Path(root).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':tf.add(p,arcname=str(p.relative_to(root)))


def exec_gate(root):
    main=Path(root)/'main.py';ns={'__name__':'__kaggle_agent__','__file__':str(main)};exec(compile(main.read_text(),str(main),'exec'),ns,ns)
    if not callable(ns.get('agent')):raise RuntimeError('exec loader found no agent')


def official_gate(root):
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments import make
    main=Path(root)/'main.py';fn=get_last_callable(main.read_text(),path=str(main))
    if not callable(fn):raise RuntimeError('official loader found no callable')
    env=make('kaggriculture',debug=False);env.run([str(main),str(main)]);st=env.steps[-1]
    statuses=[str(x.status) for x in st];rewards=[x.reward for x in st]
    if any(x in {'ERROR','INVALID','TIMEOUT'} for x in statuses) or any(x is None for x in rewards):raise RuntimeError('official gate failed '+repr((statuses,rewards)))
    return {'statuses':statuses,'rewards':rewards}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',default='/kaggle/input');ap.add_argument('--repo',required=True);ap.add_argument('--work',default='/kaggle/working/v41_1_soil_switch');ap.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 2));a=ap.parse_args()
    inp=Path(a.input_root);repo=Path(a.repo);work=Path(a.work)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    v32tar=find_v32(inp);v32main=safe_extract(v32tar,work/'agents'/'v32');found=discover(inp,work)
    if 'soil' not in found:raise RuntimeError('Soil input not found')
    soil=found['soil'];found['v32']={'root':v32main.parent,'main':v32main,'source':str(v32tar)};print('discovered',sorted(found))
    cands={'V32_CONTROL':found['v32']['root'],'SOIL_CONTROL':soil['root']}
    for cp in CHECKPOINTS:cands[f'V41_1_T{cp}']=build_hybrid(found['v32']['root'],soil['root'],work/'candidates'/f'T{cp}',cp)
    order=['v32','soil','melon','ranker','adaptive','strict','weed_slip','score3094','v16'];opps={k:found[k]['root'] for k in order if k in found}
    worker=work/'match_worker.py';worker.write_text(WORKER)
    print('=== V41.1 DENSE CHECKPOINT HELDOUT ===');games=tournament(cands,opps,SEEDS,worker,repo,a.workers);games.to_csv(work/'V41_1_GAMES.csv',index=False);tab=summarize(games);tab.to_csv(work/'V41_1_TABLE.csv',index=False);print(tab.to_string(index=False))
    eligible=tab[(tab.candidate.str.startswith('V41_1_'))&(tab.invalid_games==0)&(tab.delta_score>=.03)&(tab.direct_v32_score>=.75)&(tab.worst_family_score>=.45)&(tab.worst_delta>=0)&(tab.bad_flips==0)]
    if len(eligible):
        top=float(eligible.delta_score.max());near=eligible[eligible.delta_score>=top-.02].copy();near['cp']=near.candidate.str.extract(r'T(\d+)')[0].astype(int);best=near.sort_values(['cp','delta_score','delta_margin'],ascending=False).iloc[0];decision='PROMOTE';selected=str(best.candidate);cp=int(best.cp)
    else:best=None;decision='HOLD';selected=None;cp=None
    report={'version':'41.1','name':'Minimal Soil Switch','decision':decision,'selected_candidate':selected,'switch_step':cp,'checkpoints':CHECKPOINTS,'seeds':SEEDS,'opponents':list(opps),'v32_sha256':sha256_file(v32tar),'soil_source':soil['source'],'best_metrics':{} if best is None else {k:(None if pd.isna(v) else v) for k,v in best.to_dict().items()}}
    if decision=='PROMOTE':
        root=cands[selected];exec_gate(root);off=official_gate(root);out=work/'SUBMIT_V41_1_V32_TO_SOIL.tar.gz';package_tree(root,out);verify=work/'verify';safe_extract(out,verify);exec_gate(verify);off2=official_gate(verify);report.update(submission_ready=True,archive=str(out),archive_sha256=sha256_file(out),archive_bytes=out.stat().st_size,official_gate=off,official_gate_repacked=off2);print('SUBMISSION READY',out)
    else:report['submission_ready']=False
    (work/'V41_1_DECISION.json').write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report,indent=2,default=str))

if __name__=='__main__':main()
