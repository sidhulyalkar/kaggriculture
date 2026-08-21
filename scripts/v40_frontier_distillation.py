#!/usr/bin/env python3
from __future__ import annotations

# Kaggriculture V40 Frontier Distillation.
#
# V40 deliberately stops treating V32 as the economic backbone. It starts from
# the public MIT-licensed lonespear/kaggriculture main_v20.py closed-loop
# workforce/economic controller, then searches a narrow family of mechanistic
# extensions: fertilizer shadow-price buying, quantity-preserving market
# execution risk ordering, and re-opening scale ceilings after the new
# productivity channel exists.
#
# Run inside a Kaggle CPU notebook with Internet ON. The builder clones pinned
# public source, discovers the exact V32 archive and public-agent guards, runs
# both-seat paired screens, and emits a single-file tar only after loader/runtime
# and held-out gates.

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, tarfile, time
import numpy as np
import pandas as pd

FRONTIER_REPO = "https://github.com/lonespear/kaggriculture.git"
FRONTIER_COMMIT = "774b26093ccf4246525517d48420349b841b6e50"
FRONTIER_FILE = "main_v20.py"
FRONTIER_LICENSE = "MIT"

V32_NAMES = ("SUBMIT_V32_RUNTIME_VERIFIED.tar.gz",
             "SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz")

PUBLIC_PATTERNS = {
    "soil": "kaggriculture-frontier-the-soil-remembers-rain",
    "adaptive": "adaptive-farming-strategy-for-kaggriculture",
    "score3094": "3094-score-kaggriculture",
    "v16": "v16-rc5-high-score-8c-4s-premium-market-lead",
    "ranker": "kaggriculture-rank-your-agent",
    "melon": "kaggriculture-frontier-the-moon-counts-melons",
    "strict": "25-27-strict-future-v27-midgame-meta-reset",
    "findings": "kaggriculture-findings-from-zero-to-top-meta",
    "weed_slip": "weed-slip",
}

CANDIDATES = {
    # Smallest causal move first.
    "V40_FERT_FLYWHEEL": dict(
        strawberry_max=24, max_hands=11, max_quadrants=2,
        fert_enabled=True, fert_price_cap=42.0, fert_min_straw=10,
        fert_shed_target=8, fert_max_buy=8, fert_cash_floor=1900.0,
        market_risk_sort=True, milk_crash_boost=False),
    # Re-open ceilings only after fertilizer supply is present.
    "V40_FERT_SCALE28": dict(
        strawberry_max=28, max_hands=12, max_quadrants=2,
        fert_enabled=True, fert_price_cap=42.0, fert_min_straw=12,
        fert_shed_target=10, fert_max_buy=10, fert_cash_floor=2100.0,
        market_risk_sort=True, milk_crash_boost=False),
    "V40_FERT_SCALE32": dict(
        strawberry_max=32, max_hands=12, max_quadrants=3,
        fert_enabled=True, fert_price_cap=45.0, fert_min_straw=14,
        fert_shed_target=12, fert_max_buy=12, fert_cash_floor=2400.0,
        market_risk_sort=True, milk_crash_boost=False),
    "V40_FERT_SCALE36": dict(
        strawberry_max=36, max_hands=13, max_quadrants=3,
        fert_enabled=True, fert_price_cap=45.0, fert_min_straw=16,
        fert_shed_target=14, fert_max_buy=12, fert_cash_floor=2800.0,
        market_risk_sort=True, milk_crash_boost=False),
    # Diversification arm for the known high-combined-cow milk crash regime.
    "V40_FERT_MILK_HEDGE": dict(
        strawberry_max=30, max_hands=12, max_quadrants=3,
        cow_max=7, sheep_max=7,
        fert_enabled=True, fert_price_cap=45.0, fert_min_straw=12,
        fert_shed_target=10, fert_max_buy=10, fert_cash_floor=2200.0,
        market_risk_sort=True, milk_crash_boost=True),
    # Attribution control. No new volume, only existing SELL slot ordering.
    "V40_MARKET_ONLY": dict(
        strawberry_max=24, max_hands=11, max_quadrants=2,
        fert_enabled=False, market_risk_sort=True, milk_crash_boost=True),
}


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_extract(tar_path, dest):
    tar_path, dest = Path(tar_path), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    mains = []
    with tarfile.open(tar_path, "r:*") as tf:
        for m in tf.getmembers():
            rel = Path(m.name)
            if rel.is_absolute() or ".." in rel.parts or not m.isfile():
                continue
            fh = tf.extractfile(m)
            if fh is None:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fh.read())
            if rel.name == "main.py":
                mains.append(out)
    if not mains:
        return None
    mains.sort(key=lambda p: (len(p.relative_to(dest).parts), str(p)))
    root = dest / "main.py"
    if mains[0] != root:
        shutil.copy2(mains[0], root)
    return root


def copy_tree(src, dst):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for p in src.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            q = dst / p.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)


def find_v32(input_root):
    input_root = Path(input_root)
    for name in V32_NAMES:
        hits = list(input_root.rglob(name))
        if hits:
            return hits[0]
    raise FileNotFoundError("Attach SUBMIT_V32_RUNTIME_VERIFIED.tar.gz")


def discover_public(input_root, work):
    input_root, work = Path(input_root), Path(work)
    roots = []
    for p in input_root.rglob("submission.tar.gz"):
        roots.append(p.parent)
    for p in input_root.rglob("main.py"):
        if "__pycache__" not in p.parts:
            roots.append(p.parent)
    roots = list(dict.fromkeys(roots))
    out = {}
    for key, pattern in PUBLIC_PATTERNS.items():
        ms = [r for r in roots if pattern in str(r).lower()]
        if not ms:
            continue
        src, dst = ms[0], work / "public" / key
        main = None
        if (src / "submission.tar.gz").exists():
            try:
                main = safe_extract(src / "submission.tar.gz", dst)
            except Exception:
                main = None
        if main is None and (src / "main.py").exists():
            copy_tree(src, dst)
            main = dst / "main.py"
        if main and main.exists():
            out[key] = dict(root=dst, main=main, source=str(src))
    return out


def clone_frontier(work):
    work = Path(work)
    root = work / "frontier_source"
    if root.exists():
        shutil.rmtree(root)
    r = subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout",
                        FRONTIER_REPO, str(root)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError("frontier clone failed:\n" + r.stderr[-3000:])
    r = subprocess.run(["git", "-C", str(root), "checkout", "--detach", FRONTIER_COMMIT],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError("frontier checkout failed:\n" + r.stderr[-3000:])
    if not (root / FRONTIER_FILE).exists():
        raise FileNotFoundError(root / FRONTIER_FILE)
    return root


def replace_constant(source, name, value):
    pat = re.compile(rf"(?m)^({re.escape(name)}\s*=\s*)[^\n#]+")
    if not pat.search(source):
        raise RuntimeError("frontier source missing tunable " + name)
    return pat.sub(lambda m: m.group(1) + repr(value) + " ", source, count=1)


OVERLAY_TEMPLATE = r'''
# ===== V40 FRONTIER DISTILLATION OVERLAY =====
# Parent: lonespear/kaggriculture main_v20.py, MIT licensed.
# No dataclasses or dynamic imports in the hot path, specifically avoiding the
# loader failure class that invalidated the earlier V33 artifact.
_V40_PARENT_AGENT = agent
_V40_CFG = __V40_CFG__
_V40_BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,
             "MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
_V40_PREMIUM = {"STRAWBERRY","MELON","MILK","WOOL"}
_V40_PRODUCTS = ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON",
                 "EGG","MILK","WOOL","FERTILIZER")


def _v40_scan(obs):
    p = int(obs.get("player",0) or 0)
    farms = obs.get("farms",[]) or []
    me = farms[p] if p < len(farms) else {}
    opp = farms[1-p] if len(farms) == 2 else {}
    own = {"COW":0,"SHEEP":0,"GOOSE":0,"STRAWBERRY":0,"MELON":0,"WHEAT":0}
    rival = {"COW":0,"SHEEP":0,"GOOSE":0,"STRAWBERRY":0,"MELON":0,"WHEAT":0}
    unfert = 0
    for farm,dst,is_me in ((me,own,True),(opp,rival,False)):
        for row in farm.get("tiles",[]) or []:
            for t in row:
                if not isinstance(t,dict):
                    continue
                a=t.get("animal")
                if a in ("COW","SHEEP","GOOSE"):
                    dst[a]=dst.get(a,0)+1
                c=t.get("crop")
                if t.get("kind")=="PLANT" and c in dst:
                    dst[c]=dst.get(c,0)+1
                if is_me and t.get("kind")=="PLANT" and c=="STRAWBERRY":
                    fu=t.get("fertilized_until_day",-1)
                    fu=-1 if fu is None else int(fu)
                    if fu <= int(obs.get("day",0) or 0):
                        unfert += 1
    return me,opp,own,rival,unfert


def _v40_is_sell(o):
    return isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1] in _V40_PRODUCTS


def _v40_supply_exposure(item,r):
    return {
        "WHEAT":r.get("WHEAT",0),
        "STRAWBERRY":r.get("STRAWBERRY",0)*1.4,
        "MELON":r.get("MELON",0),
        "MILK":r.get("COW",0)*2.0,
        "WOOL":r.get("SHEEP",0)*1.8,
        "EGG":r.get("GOOSE",0)*1.5,
        "FERTILIZER":(r.get("COW",0)+r.get("SHEEP",0)+r.get("GOOSE",0))*.6,
    }.get(item,0.0)


def _v40_risk(o,obs,rival):
    item=o[1]
    try:q=max(0,int(o[2]))
    except Exception:q=0
    px=float(((obs.get("market",{}) or {}).get("prices",{}) or {}).get(item,_V40_BASE[item]) or _V40_BASE[item])
    premium=1.25 if item in _V40_PREMIUM else 1.0
    return q*px*premium*(1.0+.12*_v40_supply_exposure(item,rival))


def _v40_reorder_existing_sells(market,obs,rival):
    pos=[i for i,o in enumerate(market) if _v40_is_sell(o)]
    if len(pos)<2:return market
    sells=[market[i] for i in pos]
    sells.sort(key=lambda o:_v40_risk(o,obs,rival),reverse=True)
    out=[list(x) if isinstance(x,list) else x for x in market]
    for i,o in zip(pos,sells):out[i]=o
    return out


def _v40_inject_fertilizer(market,obs,me,own,unfert):
    if not _V40_CFG.get("fert_enabled",False):return market
    day=int(obs.get("day",0) or 0)
    if day<8 or day>23:return market
    straw=int(own.get("STRAWBERRY",0))
    if straw<int(_V40_CFG.get("fert_min_straw",10)) or unfert<5:return market
    priv=obs.get("private",{}) or {}
    shed=dict(priv.get("shed",{}) or {})
    shed_total=sum(max(0,int(v or 0)) for v in shed.values())
    if shed_total>=78:return market
    have=max(0,int(shed.get("FERTILIZER",0) or 0))
    target=int(_V40_CFG.get("fert_shed_target",8))
    if have>=target:return market
    prices=((obs.get("market",{}) or {}).get("prices",{}) or {})
    fert_px=float(prices.get("FERTILIZER",100) or 100)
    straw_px=float(prices.get("STRAWBERRY",120) or 120)
    # Conservative shadow value. We only purchase at <=25% of one extra
    # strawberry unit's current value, leaving a large execution-risk haircut.
    if fert_px>min(float(_V40_CFG.get("fert_price_cap",42.0)),straw_px*.25):
        return market
    animals=int(own.get("COW",0)+own.get("SHEEP",0)+own.get("GOOSE",0))
    wheat_px=float(prices.get("WHEAT",25) or 25)
    wheat_have=max(0,int(shed.get("WHEAT",0) or 0))
    feed_runway=max(0.0,1.25*animals-wheat_have)*wheat_px
    money=float(me.get("money",0) or 0)
    floor=max(float(_V40_CFG.get("fert_cash_floor",1900.0)),500.0+feed_runway)
    if money<=floor:return market
    q=min(int(_V40_CFG.get("fert_max_buy",8)),target-have,max(0,78-shed_total))
    q=min(q,int(max(0.0,(money-floor)//max(1.0,fert_px))))
    if q<=0:return market
    if any(isinstance(o,list) and len(o)>=2 and o[0]=="BUY_PRODUCT" and o[1]=="FERTILIZER" for o in market):
        return market
    if len(market)>=10:return market
    order=["BUY_PRODUCT","FERTILIZER",int(q)]
    insert=len(market)
    for i,o in enumerate(market):
        if not isinstance(o,list) or not o:continue
        if o[0] in ("BUY_ANIMAL","BUY_LAND") or (o[0]=="BUY_SEED" and len(o)>1 and o[1]!="WHEAT"):
            insert=i;break
    return (market[:insert]+[order]+market[insert:])[:10]


def _v40_milk_crash_reorder(market,obs,own,rival):
    if not _V40_CFG.get("milk_crash_boost",False):return market
    if int(own.get("COW",0)+rival.get("COW",0))<17:return market
    milk_px=float(((obs.get("market",{}) or {}).get("prices",{}) or {}).get("MILK",160) or 160)
    if milk_px>176:return market
    pos=[i for i,o in enumerate(market) if _v40_is_sell(o)]
    milk=[market[i] for i in pos if market[i][1]=="MILK"]
    if not milk:return market
    rest=[market[i] for i in pos if market[i][1]!="MILK"]
    out=[list(x) if isinstance(x,list) else x for x in market]
    for i,o in zip(pos,milk+rest):out[i]=o
    return out


def v40_frontier_agent(observation,configuration=None):
    obs=observation or {}
    try:action=_V40_PARENT_AGENT(obs)
    except TypeError:action=_V40_PARENT_AGENT(obs,configuration)
    if not isinstance(action,dict):return action
    action={
        "farmer":list(action.get("farmer",["PASS"]) or ["PASS"]),
        "hands":[list(a) if isinstance(a,list) else ["PASS"] for a in (action.get("hands",[]) or [])],
        "market":[list(o) if isinstance(o,list) else o for o in (action.get("market",[]) or [])][:10],
    }
    me,opp,own,rival,unfert=_v40_scan(obs)
    n=len(me.get("hands",[]) or [])
    if len(action["hands"])<n:action["hands"] += [["PASS"]]*(n-len(action["hands"]))
    elif len(action["hands"])>n:action["hands"]=action["hands"][:n]
    market=_v40_inject_fertilizer(action["market"],obs,me,own,unfert)
    if _V40_CFG.get("market_risk_sort",False):
        market=_v40_reorder_existing_sells(market,obs,rival)
    market=_v40_milk_crash_reorder(market,obs,own,rival)
    action["market"]=market[:10]
    return action
'''


def build_candidate(frontier_source, cfg, out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    src = frontier_source
    src = replace_constant(src, "STRAWBERRY_MAX", cfg.get("strawberry_max",24))
    src = replace_constant(src, "MAX_HANDS", cfg.get("max_hands",11))
    src = replace_constant(src, "MAX_QUADRANTS", cfg.get("max_quadrants",2))
    if "cow_max" in cfg: src = replace_constant(src,"COW_MAX",cfg["cow_max"])
    if "sheep_max" in cfg: src = replace_constant(src,"SHEEP_MAX",cfg["sheep_max"])
    text = src.rstrip()+"\n"+OVERLAY_TEMPLATE.replace("__V40_CFG__",repr(cfg)).lstrip()
    compile(text, str(out_dir/"main.py"), "exec")
    (out_dir/"main.py").write_text(text, encoding="utf-8")
    return out_dir/"main.py"


def package_single(main, out):
    with tarfile.open(out,"w:gz") as tf:tf.add(main,arcname="main.py")


def load_agent(path,label):
    path=Path(path);old=list(sys.path);sys.path.insert(0,str(path.parent))
    try:
        spec=importlib.util.spec_from_file_location(label,str(path))
        mod=importlib.util.module_from_spec(spec);sys.modules[label]=mod;spec.loader.exec_module(mod)
        fn=getattr(mod,"v40_frontier_agent",None) or getattr(mod,"agent",None) or getattr(mod,"main",None)
        if callable(fn):return fn
        vals=[v for k,v in vars(mod).items() if callable(v) and getattr(v,"__module__",None)==mod.__name__ and not k.startswith("_")]
        if vals:return vals[-1]
        raise RuntimeError("no callable "+str(path))
    finally:sys.path[:]=old


MATCH_WORKER = r'''from pathlib import Path
import importlib.util,json,sys,time,traceback
c=Path(sys.argv[1]);o=Path(sys.argv[2]);repo=Path(sys.argv[3]);seed=int(sys.argv[4]);seat=int(sys.argv[5])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/"src"))
from src.kagv2.simulator import Game
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m)
    f=getattr(m,"v40_frontier_agent",None) or getattr(m,"agent",None) or getattr(m,"main",None)
    if callable(f):return f
    v=[x for k,x in vars(m).items() if callable(x) and getattr(x,"__module__",None)==m.__name__ and not k.startswith("_")]
    if not v:raise RuntimeError("no callable")
    return v[-1]
try:
    a=load(c,"v40c");b=load(o,"v40o");tt=[]
    def A(obs,configuration=None):
        t=time.perf_counter()
        try:
            try:return a(obs,configuration)
            except TypeError:return a(obs)
        finally:tt.append(time.perf_counter()-t)
    agents=[A,b] if seat==0 else [b,A];cash=Game(seed=seed).run(agents)
    ac,bc=(cash[0],cash[1]) if seat==0 else (cash[1],cash[0])
    print(json.dumps({"ok":True,"cash":float(ac),"opp_cash":float(bc),
      "score":1.0 if ac>bc else .5 if ac==bc else 0.0,"margin":float(ac-bc),
      "mean_ms":1000*sum(tt)/max(1,len(tt)),"max_ms":1000*max(tt) if tt else 0.0}))
except BaseException as e:
    print(json.dumps({"ok":False,"error":repr(e),"traceback":traceback.format_exc()[-2500:]}))
'''


def run_match(worker,cand,opp,repo,seed,seat,timeout=180):
    try:r=subprocess.run([sys.executable,str(worker),str(cand),str(opp),str(repo),str(seed),str(seat)],
                         capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:return {"ok":False,"error":"timeout"}
    for line in reversed(r.stdout.splitlines()):
        try:return json.loads(line)
        except Exception:pass
    return {"ok":False,"error":(r.stderr or r.stdout)[-2500:]}


def tournament(cands,opponents,names,opp_names,seeds,worker,repo,workers):
    jobs=[(n,o,s,seat) for n in names for o in opp_names if o in opponents for s in seeds for seat in (0,1)]
    rows=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fs={ex.submit(run_match,worker,cands[n],opponents[o],repo,s,seat):(n,o,s,seat) for n,o,s,seat in jobs}
        for i,f in enumerate(as_completed(fs),1):
            n,o,s,seat=fs[f];rows.append({"candidate":n,"opponent":o,"seed":s,"seat":seat,**f.result()})
            if i%50==0 or i==len(fs):print(" completed",i,"/",len(fs))
    return pd.DataFrame(rows)


def paired_summary(df,control):
    keys=["opponent","seed","seat"]
    ctl=df[(df.candidate==control)&(df.ok==True)][keys+["score","margin","cash"]].rename(
        columns={"score":"control_score","margin":"control_margin","cash":"control_cash"})
    rows=[]
    for name,g in df.groupby("candidate"):
        good=g[g.ok==True].copy();m=good.merge(ctl,on=keys,how="inner")
        if len(m):
            m["delta"]=m.score-m.control_score;m["margin_delta"]=m.margin-m.control_margin
            byopp=m.groupby("opponent").delta.mean();direct=m[m.opponent=="v32"]
            rows.append(dict(candidate=name,games=len(g),valid_games=len(good),invalid_games=int((g.ok!=True).sum()),
              paired_games=len(m),mean_score=float(good.score.mean()),mean_cash=float(good.cash.mean()),
              robust_delta=float(m.delta.mean()),mean_margin_delta=float(m.margin_delta.mean()),
              worst_opponent_delta=float(byopp.min()),direct_v32_score=float(direct.score.mean()) if len(direct) else np.nan,
              mean_ms=float(good.mean_ms.mean()),max_ms=float(good.max_ms.max())))
        else:rows.append(dict(candidate=name,games=len(g),valid_games=len(good),invalid_games=int((g.ok!=True).sum()),
              paired_games=0,mean_score=np.nan,mean_cash=np.nan,robust_delta=np.nan,mean_margin_delta=np.nan,
              worst_opponent_delta=np.nan,direct_v32_score=np.nan,mean_ms=np.nan,max_ms=np.nan))
    z=pd.DataFrame(rows)
    z["utility"]=1.7*z.robust_delta.fillna(-1)+.8*np.minimum(z.worst_opponent_delta.fillna(-1),0)+.5*(z.direct_v32_score.fillna(.5)-.5)+.00001*z.mean_margin_delta.fillna(0)
    return z.sort_values(["utility","robust_delta","mean_margin_delta"],ascending=False).reset_index(drop=True)


def exec_style_gate(main):
    # Reproduces the bare exec loader shape that exposed V33's dataclass issue.
    source=Path(main).read_text();ns={"__name__":"__kaggle_agent__"}
    exec(compile(source,str(main),"exec"),ns,ns)
    fn=ns.get("v40_frontier_agent") or ns.get("agent")
    if not callable(fn):raise RuntimeError("exec-style loader found no callable")
    return getattr(fn,"__name__",repr(fn))


def official_runtime_gate(main):
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments import make
    main=Path(main);source=main.read_text()
    fn=get_last_callable(source,path=str(main))
    if not callable(fn):raise RuntimeError("official loader found no callable")
    selected=getattr(fn,"__name__",repr(fn))
    if "v40_frontier_agent" not in selected:raise RuntimeError("unexpected final callable "+selected)
    env=make("kaggriculture",debug=False);env.run([str(main),str(main)])
    states=env.steps[-1];statuses=[str(s.status) for s in states];rewards=[s.reward for s in states]
    if any(s in {"ERROR","INVALID","TIMEOUT"} for s in statuses) or any(r is None for r in rewards):
        raise RuntimeError("runtime failed "+repr((statuses,rewards)))
    return dict(selected_callable=selected,statuses=statuses,rewards=rewards)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-root",default="/kaggle/input")
    ap.add_argument("--work",default="/kaggle/working/v40_frontier_distillation")
    ap.add_argument("--repo",default=None)
    ap.add_argument("--workers",type=int,default=min(4,os.cpu_count() or 2))
    ap.add_argument("--screen-seeds",default="40001,40007,40013,40031")
    ap.add_argument("--holdout-seeds",default="40111,40123,40141,40151,40163,40177")
    a=ap.parse_args();inp=Path(a.input_root);work=Path(a.work)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)

    if a.repo:repo=Path(a.repo)
    else:
        repo=work/"our_repo"
        r=subprocess.run(["git","clone","--depth","1","https://github.com/sidhulyalkar/kaggriculture.git",str(repo)],
                         capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError(r.stderr[-3000:])

    fr=clone_frontier(work);front=fr/FRONTIER_FILE;src=front.read_text()
    lic=(fr/"LICENSE").read_text(errors="replace")
    if "MIT" not in lic.upper():raise RuntimeError("frontier license changed")

    v32tar=find_v32(inp);v32=safe_extract(v32tar,work/"control_v32")
    public=discover_public(inp,work);print("public:",sorted(public))

    cands={"V32_CONTROL":v32}
    pd0=work/"candidates"/"FRONTIER_PARENT";pd0.mkdir(parents=True);shutil.copy2(front,pd0/"main.py")
    cands["FRONTIER_PARENT"]=pd0/"main.py"
    for name,cfg in CANDIDATES.items():cands[name]=build_candidate(src,cfg,work/"candidates"/name)

    gates=[]
    for name,path in cands.items():
        try:
            compile(path.read_text(),str(path),"exec");load_agent(path,"gate_"+re.sub("[^A-Za-z0-9_]","_",name))
            ex=exec_style_gate(path) if name.startswith("V40_") else "n/a"
            gates.append(dict(candidate=name,ok=True,exec_callable=ex))
        except Exception as e:gates.append(dict(candidate=name,ok=False,error=repr(e)))
    pd.DataFrame(gates).to_csv(work/"static_gates.csv",index=False)
    bad=[x for x in gates if not x["ok"]]
    if bad:raise RuntimeError("static gate failures "+repr(bad))

    opp={"v32":v32,"frontier_parent":cands["FRONTIER_PARENT"]}
    for k,m in public.items():opp[k]=m["main"]
    sop=["v32","frontier_parent"]+[k for k in ("soil","adaptive","ranker","score3094","v16","melon","weed_slip") if k in opp]
    worker=work/"match_worker.py";worker.write_text(MATCH_WORKER)
    ss=[int(x) for x in a.screen_seeds.split(",")];hs=[int(x) for x in a.holdout_seeds.split(",")]
    names=["V32_CONTROL","FRONTIER_PARENT",*CANDIDATES]

    print("=== STAGE 1 ===")
    screen=tournament(cands,opp,names,sop,ss,worker,repo,a.workers);screen.to_csv(work/"screen_games.csv",index=False)
    st=paired_summary(screen,"V32_CONTROL");st.to_csv(work/"screen_vs_v32.csv",index=False);print(st.to_string(index=False))
    elig=st[(st.candidate.str.startswith("V40_"))&(st.invalid_games==0)&(st.direct_v32_score>=.45)&(st.worst_opponent_delta>=-.12)].head(3).candidate.tolist()
    if not elig:elig=st[(st.candidate.str.startswith("V40_"))&(st.invalid_games==0)].head(2).candidate.tolist()
    if not elig:raise RuntimeError("all children failed")

    print("=== STAGE 2 ===")
    hn=["V32_CONTROL","FRONTIER_PARENT",*elig];hop=list(opp)
    held=tournament(cands,opp,hn,hop,hs,worker,repo,a.workers);held.to_csv(work/"heldout_games.csv",index=False)
    hv=paired_summary(held,"V32_CONTROL");hp=paired_summary(held,"FRONTIER_PARENT")
    hv.to_csv(work/"heldout_vs_v32.csv",index=False);hp.to_csv(work/"heldout_vs_parent.csv",index=False)
    z=hv.merge(hp[["candidate","robust_delta","worst_opponent_delta","mean_margin_delta"]],on="candidate",how="left",suffixes=("_vs_v32","_vs_parent"))
    z["promotion_utility"]=1.6*z.robust_delta_vs_parent.fillna(-1)+.9*z.robust_delta_vs_v32.fillna(-1)+.5*np.minimum(z.worst_opponent_delta_vs_parent.fillna(-1),0)+.00001*z.mean_margin_delta_vs_parent.fillna(0)
    z=z.sort_values(["promotion_utility","robust_delta_vs_parent"],ascending=False);z.to_csv(work/"V40_FINAL_TABLE.csv",index=False);print(z.to_string(index=False))
    ch=z[(z.candidate.str.startswith("V40_"))&(z.invalid_games==0)]
    passed=ch[(ch.robust_delta_vs_parent>=0)&(ch.worst_opponent_delta_vs_parent>=-.06)&(ch.direct_v32_score>=.50)&(ch.robust_delta_vs_v32>=-.01)]
    if len(passed):selected=str(passed.iloc[0].candidate);decision="PROMOTE";reason="held-out frontier-parent and V32 gates passed"
    else:
        near=ch[(ch.robust_delta_vs_parent>=-.015)&(ch.worst_opponent_delta_vs_parent>=-.08)&(ch.direct_v32_score>=.50)]
        if len(near):selected=str(near.iloc[0].candidate);decision="LIVE_PROBE";reason="near-neutral frontier derivative; high-information live test"
        else:selected=None;decision="HOLD";reason="no novel child survived; refuse to spend a live slot"

    man=dict(version=40,name="Frontier Distillation / Fertilizer Flywheel",decision=decision,reason=reason,
      selected_candidate=selected,frontier_source=dict(repo=FRONTIER_REPO,commit=FRONTIER_COMMIT,file=FRONTIER_FILE,license=FRONTIER_LICENSE,sha256=sha256_file(front)),
      v32_anchor=dict(path=str(v32tar),sha256=sha256_file(v32tar)),screen_opponents=sop,heldout_opponents=hop,screen_seeds=ss,holdout_seeds=hs,candidate_configs=CANDIDATES)
    if selected:
        fm=cands[selected];official=official_runtime_gate(fm);out=work/"SUBMIT_V40_FRONTIER_DISTILLED.tar.gz";package_single(fm,out)
        vm=safe_extract(out,work/"verify_final");ex=exec_style_gate(vm);official2=official_runtime_gate(vm)
        man.update(submission_ready=True,archive=str(out),archive_sha256=sha256_file(out),archive_bytes=out.stat().st_size,
                   exec_style_callable=ex,official_runtime_gate=official,official_runtime_gate_repacked=official2)
        print("SUBMISSION READY",out)
    else:man["submission_ready"]=False
    (work/"V40_DECISION.json").write_text(json.dumps(man,indent=2,sort_keys=True,default=str))
    print(json.dumps(man,indent=2,default=str))


if __name__=="__main__":main()
