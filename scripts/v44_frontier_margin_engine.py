#!/usr/bin/env python3
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,tarfile
import numpy as np,pandas as pd

PAT={"moon":"kaggriculture-frontier-the-moon-counts-melons","soil":"kaggriculture-frontier-the-soil-remembers-rain","adaptive":"adaptive-farming-strategy-for-kaggriculture","ranker":"kaggriculture-rank-your-agent","strict":"25-27-strict-future-v27-midgame-meta-reset","score3094":"3094-score-kaggriculture","v16":"v16-rc5-high-score-8c-4s-premium-market-lead","weed_slip":"weed-slip","findings":"kaggriculture-findings-from-zero-to-top-meta"}
V32=("SUBMIT_V32_RUNTIME_VERIFIED.tar.gz","SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz")
OPPS=("v32","moon","soil","adaptive","ranker","strict","score3094","v16","weed_slip","findings")

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def extract(t,d):
 t,d=Path(t),Path(d);shutil.rmtree(d,ignore_errors=True);d.mkdir(parents=True);ms=[]
 with tarfile.open(t,'r:*') as z:
  for m in z.getmembers():
   r=Path(m.name)
   if r.is_absolute() or '..' in r.parts or not m.isfile():continue
   f=z.extractfile(m)
   if f is None:continue
   q=d/r;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(f.read())
   if r.name=='main.py':ms.append(q)
 if not ms:raise RuntimeError('no main.py in '+str(t))
 ms.sort(key=lambda p:(len(p.relative_to(d).parts),str(p)));root=d/'main.py'
 if ms[0]!=root:shutil.copy2(ms[0],root)
 return root

def copyroot(src,d):
 src,d=Path(src),Path(d);shutil.rmtree(d,ignore_errors=True);d.mkdir(parents=True)
 for p in src.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc' or p.suffix.lower() in {'.ipynb','.html','.log'}:continue
  q=d/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 if not (d/'main.py').exists():raise RuntimeError('no main.py '+str(src))
 return d/'main.py'

def discover_one(inp,work,key,pat):
 hits=[]
 for p in Path(inp).rglob('submission.tar.gz'):
  if pat in str(p.parent).lower():hits.append((0,p))
 for p in Path(inp).rglob('main.py'):
  if pat in str(p.parent).lower() and '__pycache__' not in p.parts:hits.append((1,p))
 if not hits:return None
 hits.sort(key=lambda x:(x[0],len(str(x[1])),str(x[1])));typ,p=hits[0];d=work/'agents'/key
 m=extract(p,d) if typ==0 else copyroot(p.parent,d)
 return {'root':m.parent,'main':m,'source':str(p if typ==0 else p.parent),'sha256':sha(m)}

def discover(inp,work):
 a={}
 for k,p in PAT.items():
  z=discover_one(inp,work,k,p)
  if z:a[k]=z
 for n in V32:
  h=list(Path(inp).rglob(n))
  if h:
   m=extract(h[0],work/'agents'/'v32');a['v32']={'root':m.parent,'main':m,'source':str(h[0]),'sha256':sha(m)};break
 d=work/'agents'/'passive';d.mkdir(parents=True,exist_ok=True);m=d/'main.py';m.write_text("def agent(obs,configuration=None):\n return {'farmer':['PASS'],'hands':[],'market':[]}\n");a['passive']={'root':d,'main':m,'source':'generated','sha256':sha(m)}
 return a

WORKER=r'''from pathlib import Path
import importlib.util,json,sys,time,traceback
c,o,repo,seed,seat=Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]);sys.path[:0]=[str(repo),str(repo/'src')]
from src.kagv2.simulator import Game
def load(r,n):
 old=list(sys.path);sys.path.insert(0,str(r))
 try:
  s=importlib.util.spec_from_file_location(n,str(r/'main.py'));m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);f=getattr(m,'agent',None) or getattr(m,'main',None) or getattr(m,'v40_frontier_agent',None)
  if not callable(f):
   v=[x for k,x in vars(m).items() if callable(x) and getattr(x,'__module__',None)==m.__name__ and not k.startswith('_')]
   if not v:raise RuntimeError('no callable')
   f=v[-1]
  return m,f
 finally:sys.path[:]=old
def call(f,x):
 try:return f(x)
 except TypeError:return f(x,None)
try:
 cm,C=load(c,'c');_,O=load(o,'o');tt=[]
 def A(obs,configuration=None):
  t=time.perf_counter()
  try:return call(C,obs)
  finally:tt.append(time.perf_counter()-t)
 cash=Game(seed=seed).run([A,O] if seat==0 else [O,A]);cc,oc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0]);s=getattr(cm,'_V44_STATS',{}) or {};n=max(1,int(s.get('calls',0) or 0))
 print(json.dumps({'ok':True,'cash':float(cc),'opp_cash':float(oc),'score':1.0 if cc>oc else .5 if cc==oc else 0.0,'margin':float(cc-oc),'mean_ms':1000*sum(tt)/max(1,len(tt)),'max_ms':1000*max(tt) if tt else 0.0,'market_change_rate':float(s.get('market_changed',0) or 0)/n,'physical_change_rate':float(s.get('physical_changed',0) or 0)/n}))
except BaseException as e:print(json.dumps({'ok':False,'error':repr(e),'traceback':traceback.format_exc()[-2500:]}))
'''

def one(w,c,o,r,s,t):
 try:x=subprocess.run([sys.executable,str(w),str(c),str(o),str(r),str(s),str(t)],capture_output=True,text=True,timeout=180)
 except subprocess.TimeoutExpired:return {'ok':False,'error':'timeout'}
 for q in reversed(x.stdout.splitlines()):
  try:return json.loads(q)
  except Exception:pass
 return {'ok':False,'error':(x.stderr or x.stdout)[-2500:]}

def tour(cands,opps,seeds,w,repo,nw):
 jobs=[(cn,cr,on,orr,s,t) for cn,cr in cands.items() for on,orr in opps.items() for s in seeds for t in (0,1)];rows=[]
 with ThreadPoolExecutor(max_workers=nw) as ex:
  fs={ex.submit(one,w,cr,orr,repo,s,t):(cn,on,s,t) for cn,cr,on,orr,s,t in jobs}
  for i,f in enumerate(as_completed(fs),1):
   cn,on,s,t=fs[f];rows.append({'candidate':cn,'opponent':on,'seed':s,'seat':t,**f.result()})
   if i%50==0 or i==len(fs):print(' completed',i,'/',len(fs))
 return pd.DataFrame(rows)

def summary(df,control=None,competitive=None):
 keys=['opponent','seed','seat'];ctl=None;rows=[]
 if control:ctl=df[(df.candidate==control)&(df.ok==True)][keys+['score','margin','cash']].rename(columns={'score':'cs','margin':'cm','cash':'cc'})
 for name,g in df.groupby('candidate'):
  q=g[g.ok==True].copy();c=q if not competitive else q[q.opponent.isin(competitive)];by=c.groupby('opponent').score.mean() if len(c) else pd.Series(dtype=float)
  z={'candidate':name,'games':len(g),'valid_games':len(q),'invalid_games':int((g.ok!=True).sum()),'mean_score':float(c.score.mean()) if len(c) else np.nan,'mean_cash':float(q.cash.mean()) if len(q) else np.nan,'mean_margin':float(c.margin.mean()) if len(c) else np.nan,'worst_family_score':float(by.min()) if len(by) else np.nan,'mean_ms':float(q.mean_ms.mean()) if len(q) else np.nan,'max_ms':float(q.max_ms.max()) if len(q) else np.nan,'market_change_rate':float(q.market_change_rate.mean()) if len(q) else 0.,'physical_change_rate':float(q.physical_change_rate.mean()) if len(q) else 0.,'passive_cash':float(q[q.opponent=='passive'].cash.mean()) if len(q[q.opponent=='passive']) else np.nan,'v32_score':float(q[q.opponent=='v32'].score.mean()) if len(q[q.opponent=='v32']) else np.nan}
  if ctl is not None:
   m=q.merge(ctl,on=keys);m=m if not competitive else m[m.opponent.isin(competitive)]
   if len(m):
    m['d']=m.score-m.cs;z.update(delta_score=float(m.d.mean()),delta_margin=float((m.margin-m.cm).mean()),worst_delta=float(m.groupby('opponent').d.mean().min()),paired_games=len(m))
  rows.append(z)
 x=pd.DataFrame(rows);cols=['mean_score','worst_family_score','mean_margin'] if not control else ['delta_score','worst_delta','mean_score','delta_margin'];return x.sort_values([c for c in cols if c in x],ascending=False,na_position='last').reset_index(drop=True)

def parity(df,a,b):
 k=['opponent','seed','seat'];x=df[(df.candidate==a)&(df.ok==True)][k+['cash','score','margin']];y=df[(df.candidate==b)&(df.ok==True)][k+['cash','score','margin']].rename(columns={'cash':'bc','score':'bs','margin':'bm'});m=x.merge(y,on=k)
 return {'paired_games':len(m),'max_abs_cash_diff':float((m.cash-m.bc).abs().max()) if len(m) else None,'max_abs_margin_diff':float((m.margin-m.bm).abs().max()) if len(m) else None,'all_scores_equal':bool((m.score==m.bs).all()) if len(m) else False}

def gate(main):
 s=Path(main).read_text();e={};exec(compile(s,str(main),'exec'),e,e);cs=[v for v in e.values() if callable(v)];z={'compile_exec':True,'agent_is_callable':callable(e.get('agent')),'last_callable_is_agent':bool(cs and cs[-1] is e.get('agent')),'official_loader':None}
 try:
  from kaggle_environments.agent import get_last_callable
  z['official_loader']=callable(get_last_callable(s,path=str(main)))
 except Exception as x:z['official_loader']='unavailable:'+repr(x)
 if not z['agent_is_callable'] or not z['last_callable_is_agent']:raise RuntimeError('loader gate '+repr(z))
 return z

def package(main,out):
 with tarfile.open(out,'w:gz') as t:t.add(main,arcname='main.py')
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input-root',default='/kaggle/input');ap.add_argument('--repo',required=True);ap.add_argument('--work',default='/kaggle/working/v44_frontier_margin');ap.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 2));ap.add_argument('--screen-seeds',type=int,default=4);ap.add_argument('--heldout-seeds',type=int,default=8);a=ap.parse_args()
 repo=Path(a.repo);work=Path(a.work);shutil.rmtree(work,ignore_errors=True);work.mkdir(parents=True);sys.path[:0]=[str(repo),str(repo/'src')]
 from src.kagv2.frontier_margin import candidate_configs,build_runtime_source,source_sha256
 ag=discover(a.input_root,work);parents=[x for x in ('moon','soil') if x in ag];comp=[x for x in OPPS if x in ag]
 if not parents:raise RuntimeError('Attach current Moon and/or Soil source/output')
 if len(comp)<2:raise RuntimeError('Attach at least two competitive agents (Moon+Soil is sufficient; broader zoo preferred)')
 opp={x:ag[x]['root'] for x in comp};opp['passive']=ag['passive']['root'];competitive=set(comp);(work/'V44_INPUT_MANIFEST.json').write_text(json.dumps({'agents':{k:{'source':v['source'],'sha256':v['sha256']} for k,v in ag.items()},'parents':parents,'competitive':comp},indent=2));print('discovered',sorted(ag))
 w=work/'worker.py';w.write_text(WORKER)
 print('=== STAGE A: PARENT ===');pg=tour({x.upper()+'_DIRECT':ag[x]['root'] for x in parents},opp,[44001+2*i for i in range(max(3,a.screen_seeds))],w,repo,a.workers);pg.to_csv(work/'V44_PARENT_GAMES.csv',index=False);pt=summary(pg,competitive=competitive);pt['robust_score']=.7*pt.mean_score+.3*pt.worst_family_score;pt=pt.sort_values(['robust_score','mean_score','mean_margin'],ascending=False);pt.to_csv(work/'V44_PARENT_TABLE.csv',index=False);print(pt.to_string(index=False));vp=pt[pt.invalid_games==0]
 if vp.empty:raise RuntimeError('no valid parent')
 pn=str(vp.iloc[0].candidate).replace('_DIRECT','').lower();parent=ag[pn];ps=parent['main'].read_text();print('selected parent',pn,parent['source'])
 roots={'PARENT_DIRECT':parent['root']};cfgs=candidate_configs()
 for n,c in cfgs.items():
  d=work/'candidates'/n;d.mkdir(parents=True,exist_ok=True);s=build_runtime_source(ps,c,parent_label=pn);compile(s,str(d/'main.py'),'exec');(d/'main.py').write_text(s);gate(d/'main.py');roots[n]=d
 print('=== STAGE B: SCREEN ===');sg=tour(roots,opp,[44101+2*i for i in range(a.screen_seeds)],w,repo,a.workers);sg.to_csv(work/'V44_SCREEN_GAMES.csv',index=False);pa=parity(sg,'PARENT_DIRECT','V44_COMPILED_CONTROL');(work/'V44_COMPILED_PARENT_PARITY.json').write_text(json.dumps(pa,indent=2))
 if not pa['paired_games'] or pa['max_abs_cash_diff']!=0.0 or not pa['all_scores_equal']:raise RuntimeError('compiled parent parity failed '+repr(pa))
 st=summary(sg,'V44_COMPILED_CONTROL',competitive);st.to_csv(work/'V44_SCREEN_TABLE.csv',index=False);print(st.to_string(index=False));e=st[(st.candidate.str.startswith('V44_'))&(st.candidate!='V44_COMPILED_CONTROL')&(st.invalid_games==0)&(st.delta_score>=-.01)&(st.worst_delta>=-.08)&(st.physical_change_rate<=.02)].head(3);control=package(roots['V44_COMPILED_CONTROL']/'main.py',work/'CONTROL_CURRENT_FRONTIER.tar.gz')
 if e.empty:
  d={'version':'44.0','decision':'HOLD','reason':'No residual survived screen','selected_parent':pn,'parent_sha256':source_sha256(ps),'parity':pa,'control_archive':str(control),'loader_gate':gate(roots['V44_COMPILED_CONTROL']/'main.py')};(work/'HOLD_V44_DO_NOT_SUBMIT.txt').write_text('No V44 residual survived screen.\n');(work/'V44_DECISION.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2));return
 finals=e.candidate.tolist();hr={'PARENT_DIRECT':parent['root'],'V44_COMPILED_CONTROL':roots['V44_COMPILED_CONTROL'],**{x:roots[x] for x in finals}};hs=[44201+2*i for i in range(a.heldout_seeds)];print('=== STAGE C: HELDOUT ===');hg=tour(hr,opp,hs,w,repo,a.workers);hg.to_csv(work/'V44_HELDOUT_GAMES.csv',index=False);hp=parity(hg,'PARENT_DIRECT','V44_COMPILED_CONTROL');ht=summary(hg,'V44_COMPILED_CONTROL',competitive);ht.to_csv(work/'V44_HELDOUT_TABLE.csv',index=False);print(ht.to_string(index=False));cr=ht[ht.candidate=='V44_COMPILED_CONTROL'].iloc[0];good=[]
 for _,r in ht.iterrows():
  if str(r.candidate) not in finals:continue
  pf=pd.isna(cr.passive_cash) or pd.isna(r.passive_cash) or float(r.passive_cash)>=.97*float(cr.passive_cash);v32=pd.isna(cr.v32_score) or pd.isna(r.v32_score) or float(r.v32_score)>=float(cr.v32_score)-.02
  if r.invalid_games==0 and r.delta_score>=.02 and r.worst_delta>=-.03 and r.physical_change_rate<=.02 and r.mean_ms<100 and pf and v32:good.append(r)
 out={'version':'44.0','name':'Frontier Margin Engine','selected_parent':pn,'parent_source':parent['source'],'parent_sha256':source_sha256(ps),'screen_seeds':[44101+2*i for i in range(a.screen_seeds)],'heldout_seeds':hs,'competitive_opponents':comp,'compiled_parent_parity_screen':pa,'compiled_parent_parity_heldout':hp,'control_archive':str(control)}
 if good:
  good.sort(key=lambda r:(float(r.delta_score),float(r.worst_delta),float(r.mean_score),float(r.delta_margin)),reverse=True);r=good[0];sel=str(r.candidate);arc=package(roots[sel]/'main.py',work/'SUBMIT_V44_FRONTIER_MARGIN.tar.gz');att={'v44':sel,'embedded_parent':pn,'parent_source':parent['source'],'parent_main_sha256':parent['sha256'],'compiled_main_sha256':sha(roots[sel]/'main.py')};(work/'V44_ATTRIBUTION.json').write_text(json.dumps(att,indent=2));out.update(decision='PROMOTE',selected_candidate=sel,selected_config=cfgs[sel],selected_metrics={k:(None if pd.isna(v) else v) for k,v in r.to_dict().items()},loader_gate=gate(roots[sel]/'main.py'),submission_archive=str(arc),submission_sha256=sha(arc))
 else:
  out.update(decision='HOLD',reason='No finalist cleared +0.02 paired score / -0.03 worst-family / passive / V32 / physical / runtime gates',finalists=finals);(work/'HOLD_V44_DO_NOT_SUBMIT.txt').write_text('V44 failed held-out promotion.\n')
 (work/'V44_DECISION.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,indent=2,default=str))
if __name__=='__main__':main()
