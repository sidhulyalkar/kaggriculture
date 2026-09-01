from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import csv
from hashlib import sha256
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tarfile
from typing import Any
import zlib

EXPECTED_V76_PARENT_SHA256 = "ff871d2fbf2b1123668045062677eea7f0239fc95b02d15fedce35c2c1033fd1"
SOIL_HANDLE = "prvsiyan/kaggriculture-frontier-the-soil-remembers-rain"
EPISODE_INDEX = "kaggle/kaggriculture-episodes-index"

_WORKER = r'''
import json,sys
from pathlib import Path
from kaggle_environments import make

candidate, opponent, seed, candidate_seat = Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])

def run():
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    agents=[str(candidate),str(opponent)] if candidate_seat==0 else [str(opponent),str(candidate)]
    env.run(agents)
    last=env.steps[-1]
    statuses=[str(last[i].status) for i in (0,1)]
    def money(player):
        for owner in (candidate_seat,0,1):
            try:
                obs=last[owner].observation
                farms=obs["farms"] if isinstance(obs,dict) else obs.farms
                farm=farms[player]
                return float(farm.get("money",0) if isinstance(farm,dict) else farm.money)
            except Exception:
                pass
        return float(last[player].reward or 0)
    me=money(candidate_seat); op=money(1-candidate_seat)
    return {"ok":all(x=="DONE" for x in statuses),"cash":me,"opp_cash":op,"margin":me-op,
            "score":1.0 if me>op else .5 if me==op else 0.0,"statuses":statuses}

try:
    print(json.dumps(run()))
except BaseException as exc:
    print(json.dumps({"ok":False,"error":repr(exc)}))
'''

def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()

def _extract_main_from_root(root: Path) -> str | None:
    archives=sorted(list(root.rglob("submission.tar.gz"))+list(root.rglob("*.tar.gz")),
                    key=lambda p:(0 if p.name=="submission.tar.gz" else 1,len(p.parts),str(p)))
    seen=set()
    for archive in archives:
        if archive in seen: continue
        seen.add(archive)
        try:
            with tarfile.open(archive,"r:*") as tf:
                mains=[m for m in tf.getmembers() if m.isfile() and Path(m.name).name=="main.py"]
                mains.sort(key=lambda m:(len(Path(m.name).parts),m.name))
                if mains:
                    fh=tf.extractfile(mains[0])
                    if fh:
                        return fh.read().decode("utf-8")
        except Exception:
            pass
    mains=sorted(root.rglob("main.py"),key=lambda p:(len(p.parts),str(p)))
    if mains:
        try:return mains[0].read_text(encoding="utf-8")
        except Exception:return None
    return None

def recover_soil_parent(root: Path, max_version: int = 40) -> tuple[str,dict[str,Any]]:
    import kagglehub
    attempts=[]
    latest_source=None
    latest_version=None
    for version in range(max_version,0,-1):
        dest=root/f"soil_v{version}"
        shutil.rmtree(dest,ignore_errors=True); dest.mkdir(parents=True,exist_ok=True)
        handle=f"{SOIL_HANDLE}/versions/{version}"
        try:
            got=kagglehub.notebook_output_download(handle,output_dir=str(dest),force_download=True)
            src=_extract_main_from_root(Path(got) if got else dest)
            if not src:
                attempts.append({"version":version,"status":"no_main"}); continue
            compile(src,f"<soil-v{version}>","exec")
            digest=_hash_text(src)
            attempts.append({"version":version,"status":"ready","sha256":digest,"bytes":len(src)})
            if latest_source is None:
                latest_source,latest_version=src,version
            if digest==EXPECTED_V76_PARENT_SHA256:
                return src,{"status":"exact_v76_parent","version":version,"sha256":digest,"attempts":attempts}
        except Exception as exc:
            attempts.append({"version":version,"status":"failed","error":f"{type(exc).__name__}: {exc}"[:300]})
    dest=root/"soil_latest"
    shutil.rmtree(dest,ignore_errors=True); dest.mkdir(parents=True,exist_ok=True)
    try:
        got=kagglehub.notebook_output_download(SOIL_HANDLE,output_dir=str(dest),force_download=True)
        src=_extract_main_from_root(Path(got) if got else dest)
        if src:
            compile(src,"<soil-latest>","exec")
            return src,{"status":"latest_fallback","version":latest_version,"sha256":_hash_text(src),"attempts":attempts}
    except Exception as exc:
        attempts.append({"version":"latest","status":"failed","error":f"{type(exc).__name__}: {exc}"[:300]})
    if latest_source:
        return latest_source,{"status":"versioned_fallback","version":latest_version,"sha256":_hash_text(latest_source),"attempts":attempts}
    raise RuntimeError("could not recover any usable Soil source")

def _download_file(handle: str, path: str, dest: Path) -> Path:
    import kagglehub
    dest.mkdir(parents=True,exist_ok=True)
    got=kagglehub.dataset_download(handle,path=path,output_dir=str(dest),force_download=True)
    p=Path(got)
    if p.is_dir():
        candidate=p/path
        if candidate.exists(): return candidate
        hits=list(p.rglob(Path(path).name))
        if hits:return hits[0]
    if p.exists(): return p
    hits=list(dest.rglob(Path(path).name))
    if hits:return hits[0]
    raise FileNotFoundError(f"{handle}:{path}")

def fetch_top_episodes(root: Path, *, days: int = 2, per_day: int = 8) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    idx=_download_file(EPISODE_INDEX,"manifest.csv",root/"index")
    rows=list(csv.DictReader(idx.open(encoding="utf-8")))
    if not rows: raise RuntimeError("episode index manifest is empty")
    dated=[r for r in rows if r.get("date")]
    dated.sort(key=lambda r:r["date"],reverse=True)
    selected_days=dated[:max(1,days)]
    episodes=[]
    report={"index_rows":len(rows),"days":[]}
    for drow in selected_days:
        date=drow["date"]; handle=f"kaggle/kaggriculture-episodes-{date}"
        day_root=root/date
        try:
            manifest=_download_file(handle,"manifest.csv",day_root/"manifest")
            mrows=list(csv.DictReader(manifest.open(encoding="utf-8")))
            mrows.sort(key=lambda r:float(r.get("avg_score",0) or 0),reverse=True)
        except Exception as exc:
            report["days"].append({"date":date,"status":"manifest_failed","error":f"{type(exc).__name__}: {exc}"}); continue
        picked=mrows[:per_day]
        day_info={"date":date,"handle":handle,"manifest_rows":len(mrows),"picked":[]}
        for row in picked:
            eid=str(row.get("episode_id","")).strip()
            if not eid: continue
            try:
                fp=_download_file(handle,f"{eid}.json",day_root/"episodes")
                rep=json.loads(fp.read_text(encoding="utf-8"))
                rep["_meta_date"]=date
                rep["_meta_avg_score"]=float(row.get("avg_score",0) or 0)
                rep["_meta_size_bytes"]=int(float(row.get("size_bytes",0) or 0))
                episodes.append(rep)
                day_info["picked"].append({"episode_id":eid,"avg_score":rep["_meta_avg_score"],"bytes":rep["_meta_size_bytes"]})
            except Exception as exc:
                day_info["picked"].append({"episode_id":eid,"status":"failed","error":f"{type(exc).__name__}: {exc}"[:200]})
        day_info["status"]="ready" if any("avg_score" in x for x in day_info["picked"]) else "empty"
        report["days"].append(day_info)
    if len(episodes)<6: raise RuntimeError(f"only {len(episodes)} top episodes were acquired")
    return episodes,report

def _obs_step(state: dict[str,Any]) -> int:
    obs=state.get("observation",{}) if isinstance(state,dict) else {}
    raw=obs.get("step")
    if raw is not None:
        try:return int(raw)
        except Exception:pass
    try:return int(obs.get("day",0) or 0)*24+int(obs.get("hour",0) or 0)
    except Exception:return 0

def _plain(obj: Any) -> Any:
    if isinstance(obj,dict):return {str(k):_plain(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [_plain(v) for v in obj]
    return obj

def _physical(action: Any) -> tuple[str,str]:
    if not isinstance(action,dict):return ("INVALID","INVALID")
    return (json.dumps(_plain(action.get("farmer",[])),sort_keys=True,separators=(",",":")),
            json.dumps(_plain(action.get("hands",[])),sort_keys=True,separators=(",",":")))

def _shops_from_state(state: dict[str,Any]) -> tuple[str,...]:
    obs=state.get("observation",{}) if isinstance(state,dict) else {}
    town=obs.get("town",{}) or {}
    return tuple(str(x) for x in (town.get("unlocked_shops",[]) or []))

def winner_traces(episodes: list[dict[str,Any]]) -> list[dict[str,Any]]:
    out=[]
    for rep in episodes:
        steps=rep.get("steps",[]) or []
        if len(steps)<600: continue
        rewards=rep.get("rewards")
        if not isinstance(rewards,list) or len(rewards)<2:
            try: rewards=[steps[-1][0].get("reward"),steps[-1][1].get("reward")]
            except Exception: continue
        try:r0=float(rewards[0] or 0);r1=float(rewards[1] or 0)
        except Exception:continue
        seat=0 if r0>=r1 else 1
        info=rep.get("info",{}) or {};teams=info.get("TeamNames") or ["p0","p1"]
        seed=info.get("seed",rep.get("configuration",{}).get("seed"))
        if seed is None:continue
        amap={};shops={};states=[]
        for turn in steps:
            if seat>=len(turn) or not isinstance(turn[seat],dict):continue
            state=turn[seat];act=state.get("action");step=_obs_step(state)
            if isinstance(act,dict):amap[step]=_plain(act)
            shops[step]=_shops_from_state(state);states.append(state)
        if len(amap)<500:continue
        out.append({"episode_id":str(info.get("EpisodeId",rep.get("id","unknown"))),"date":rep.get("_meta_date","unknown"),
                    "avg_score":float(rep.get("_meta_avg_score",0) or 0),"team":str(teams[seat]) if seat<len(teams) else f"p{seat}",
                    "winner_seat":seat,"candidate_seat":1-seat,"seed":int(seed),"winner_cash":max(r0,r1),"loser_cash":min(r0,r1),
                    "action_map":amap,"shops":shops,"states":states})
    if len(out)<6:raise RuntimeError(f"only {len(out)} usable winner traces")
    return out

def _load_source(source: str, root: Path, name: str):
    root.mkdir(parents=True,exist_ok=True)
    path=root/f"{name}.py";path.write_text(source,encoding="utf-8")
    spec=importlib.util.spec_from_file_location(name,str(path));mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

def route_match_table(parent_source: str, traces: list[dict[str,Any]], root: Path) -> list[dict[str,Any]]:
    if "_V174_NS" not in parent_source or "_KAITO_NS" not in parent_source:raise RuntimeError("Soil parent does not expose _V174_NS/_KAITO_NS")
    rows=[]
    for i,tr in enumerate(traces):
        vm=_load_source(parent_source,root/f"trace_{i}","vmod_"+str(i));km=_load_source(parent_source,root/f"trace_{i}","kmod_"+str(i))
        vf=vm._V174_NS["agent"];kf=km._KAITO_NS["agent"]
        windows={1:[0,0],2:[0,0],3:[0,0]};eligible={1:0,2:0,3:0};prefix={}
        for state in tr["states"]:
            step=_obs_step(state);act=state.get("action")
            if not isinstance(act,dict):continue
            shops=_shops_from_state(state);level=1 if 72<=step<144 else 2 if 144<=step<216 else 3 if step>=216 else 0
            if not level or len(shops)<level:continue
            obs=dict(state.get("observation",{}) or {});obs.setdefault("step",step)
            try:va=vf(obs)
            except TypeError:va=vf(obs,None)
            try:ka=kf(obs)
            except TypeError:ka=kf(obs,None)
            target=_physical(act);windows[level][0]+=int(_physical(va)==target);windows[level][1]+=int(_physical(ka)==target);eligible[level]+=1;prefix[level]=tuple(shops[:level])
        for level in (1,2,3):
            n=eligible[level]
            if n<=0 or level not in prefix:continue
            v,k=windows[level]
            rows.append({"trace":i,"episode_id":tr["episode_id"],"date":tr["date"],"team":tr["team"],"level":level,
                         "prefix":list(prefix[level]),"n":n,"v_match":v/n,"k_match":k/n,"delta_k_minus_v":(k-v)/n,"avg_score":tr["avg_score"]})
    return rows

def learn_maps(rows: list[dict[str,Any]], train_trace_ids: set[int], threshold: float, min_count: int) -> dict[int,dict[tuple[str,...],str]]:
    agg=defaultdict(list)
    for row in rows:
        if int(row["trace"]) not in train_trace_ids:continue
        key=(int(row["level"]),tuple(row["prefix"]));weight=1.0+max(0.0,(float(row.get("avg_score",0))-2500.0)/1500.0)
        agg[key].extend([float(row["delta_k_minus_v"])]*max(1,int(round(weight))))
    maps={1:{},2:{},3:{}}
    for (level,prefix),vals in agg.items():
        if len(vals)<min_count:continue
        mean=statistics.mean(vals)
        if abs(mean)>=threshold:maps[level][prefix]="K" if mean>0 else "V"
    return maps

def build_candidate(parent_source: str, *, maps: dict[int,dict[tuple[str,...],str]], label: str, lock_level: int = 2, opponent_gate: bool = False) -> str:
    first={"SMOOTHIE_SHOP":"K","YARN_STORE":"K","FARMERS_MARKET":"K"}
    second={("PET_CAFE","YARN_STORE"):"K",("BRUNCH_SPOT","YARN_STORE"):"K"};third={}
    first.update({k[0]:v for k,v in maps.get(1,{}).items() if len(k)==1});second.update(maps.get(2,{}));third.update(maps.get(3,{}))
    ext=f'''
# V77 live-meta route distillation: {label}
_V77_FIRST={first!r}
_V77_SECOND={second!r}
_V77_THIRD={third!r}
_V77_LOCK_LEVEL={int(lock_level)}
_V77_OPP_GATE={bool(opponent_gate)!r}
_V77_ROUTE={{0:None,1:None}}

def _v77_money(obs,seat):
    try:return float(_get((_get(obs,"farms",[]) or [])[seat],"money",0) or 0)
    except Exception:return 0.0

def _v77_route(obs):
    seat=_seat(obs)
    raw=_get(obs,"step",None)
    step=max(0,int(raw if raw is not None else int(_get(obs,"day",0) or 0)*24+int(_get(obs,"hour",0) or 0)))
    shops=tuple(str(x) for x in (list(_get(_get(obs,"town",{{}}) or {{}},"unlocked_shops",[]) or [])))
    if step<72 or not shops:return "V"
    route=_V77_FIRST.get(shops[0],"V");level=1
    if step>=144 and len(shops)>=2:route=_V77_SECOND.get(tuple(shops[:2]),route);level=2
    if step>=216 and len(shops)>=3:route=_V77_THIRD.get(tuple(shops[:3]),route);level=3
    if level>=_V77_LOCK_LEVEL:
        if _V77_ROUTE.get(seat) is None:_V77_ROUTE[seat]=route
        route=_V77_ROUTE[seat]
    if _V77_OPP_GATE and route=="K":
        me=_v77_money(obs,seat);op=_v77_money(obs,1-seat)
        if step<216 and op<me+250:route="V"
    return route

def agent(obs,configuration=None):
    fn=_KAITO_NS["agent"] if _v77_route(obs)=="K" else _V174_NS["agent"]
    try:return fn(obs)
    except TypeError:return fn(obs,configuration)
'''
    source=parent_source.rstrip()+"\n\n"+ext
    compile(source,f"<{label}>","exec")
    return source

def replay_agent_source(action_map: dict[int,Any]) -> str:
    raw=json.dumps({str(k):v for k,v in action_map.items()},separators=(",",":")).encode();blob=base64.b85encode(zlib.compress(raw,9)).decode()
    return f'''import base64,json,zlib
_A=json.loads(zlib.decompress(base64.b85decode({blob!r})).decode())
def agent(obs,configuration=None):
    raw=obs.get("step") if isinstance(obs,dict) else None
    step=int(raw) if raw is not None else int((obs.get("day",0) if isinstance(obs,dict) else 0) or 0)*24+int((obs.get("hour",0) if isinstance(obs,dict) else 0) or 0)
    return _A.get(str(step),{{"farmer":["PASS"],"hands":[],"market":[]}})
'''

def materialize_sources(root: Path, candidates: dict[str,str], traces: list[dict[str,Any]]) -> tuple[dict[str,Path],dict[int,Path]]:
    cp={};op={}
    for name,source in candidates.items():
        d=root/"candidates"/name;d.mkdir(parents=True,exist_ok=True);p=d/"main.py";p.write_text(source,encoding="utf-8");cp[name]=p
    for i,tr in enumerate(traces):
        d=root/"opponents"/str(i);d.mkdir(parents=True,exist_ok=True);p=d/"main.py";p.write_text(replay_agent_source(tr["action_map"]),encoding="utf-8");op[i]=p
    return cp,op

def _run_game(candidate: Path, opponent: Path, seed: int, candidate_seat: int, timeout: int = 180) -> dict[str,Any]:
    try:r=subprocess.run([sys.executable,"-c",_WORKER,str(candidate),str(opponent),str(seed),str(candidate_seat)],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:return {"ok":False,"error":"timeout"}
    for line in reversed(r.stdout.splitlines()):
        try:return json.loads(line)
        except Exception:pass
    return {"ok":False,"error":(r.stderr or r.stdout)[-800:]}

def evaluate_panel(candidates: dict[str,Path], opponent_paths: dict[int,Path], traces: list[dict[str,Any]], ids: list[int], workers: int = 6):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    jobs=[(name,tid) for name in candidates for tid in ids];rows=[]
    with ThreadPoolExecutor(max_workers=max(1,workers)) as ex:
        futs={ex.submit(_run_game,candidates[name],opponent_paths[tid],traces[tid]["seed"],traces[tid]["candidate_seat"]):(name,tid) for name,tid in jobs}
        for f in as_completed(futs):
            name,tid=futs[f];tr=traces[tid];rows.append({"candidate":name,"trace":tid,"team":tr["team"],"episode_id":tr["episode_id"],**f.result()})
    summary=[]
    for name in candidates:
        q=[r for r in rows if r["candidate"]==name];valid=[r for r in q if r.get("ok")];scores=[float(r["score"]) for r in valid];margins=[float(r["margin"]) for r in valid]
        k=max(1,int(math.ceil(.2*len(scores)))) if scores else 1
        summary.append({"candidate":name,"games":len(q),"valid":len(valid),"invalid":len(q)-len(valid),
                        "win_score":statistics.mean(scores) if scores else -1.0,"cvar20_score":statistics.mean(sorted(scores)[:k]) if scores else -1.0,
                        "mean_margin":statistics.mean(margins) if margins else float("-inf"),"worst_margin":min(margins) if margins else float("-inf")})
    summary.sort(key=lambda r:(r["win_score"],r["cvar20_score"],r["mean_margin"]),reverse=True)
    return rows,summary

def _pack(source: str, path: Path) -> str:
    path.parent.mkdir(parents=True,exist_ok=True);data=source.encode("utf-8");info=tarfile.TarInfo("main.py");info.size=len(data);info.mtime=0
    with tarfile.open(path,"w:gz") as tf:tf.addfile(info,io.BytesIO(data))
    return sha256(path.read_bytes()).hexdigest()

def run(output_root: str, days: int = 2, per_day: int = 8, max_version: int = 40, workers: int = 6) -> dict[str,Any]:
    root=Path(output_root).resolve();shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    parent,parent_info=recover_soil_parent(root/"parent_recovery",max_version=max_version)
    episodes,episode_report=fetch_top_episodes(root/"episode_data",days=days,per_day=per_day);traces=winner_traces(episodes)
    teams=sorted({tr["team"] for tr in traces});holdout_teams={team for i,team in enumerate(teams) if i%3==0}
    heldout=[i for i,tr in enumerate(traces) if tr["team"] in holdout_teams];train=[i for i in range(len(traces)) if i not in heldout]
    if len(heldout)<3:
        heldout=list(range(max(1,len(traces)//3),len(traces)));train=[i for i in range(len(traces)) if i not in heldout]
    match_rows=route_match_table(parent,traces,root/"route_probe")
    variants={"BASE_PARENT":parent};learned={}
    settings=[("DISTILL_LOOSE",0.01,1,2,False),("DISTILL_MED",0.03,1,2,False),("DISTILL_STRICT",0.06,2,2,False),("DISTILL_LATELOCK",0.03,1,3,False),("DISTILL_OPP_GATED",0.03,1,2,True)]
    for label,threshold,min_count,lock_level,opp_gate in settings:
        maps=learn_maps(match_rows,set(train),threshold,min_count);learned[label]={str(k):{"|".join(p):v for p,v in m.items()} for k,m in maps.items()}
        variants[label]=build_candidate(parent,maps=maps,label=label,lock_level=lock_level,opponent_gate=opp_gate)
    cp,op=materialize_sources(root/"arena",variants,traces)
    screen_ids=train[:min(6,len(train))];screen_rows,screen_summary=evaluate_panel(cp,op,traces,screen_ids,workers=workers)
    top_names=[r["candidate"] for r in screen_summary if r["invalid"]==0][:4]
    if "BASE_PARENT" not in top_names:top_names.append("BASE_PARENT")
    held_cp={n:cp[n] for n in top_names};held_rows,held_summary=evaluate_panel(held_cp,op,traces,heldout,workers=workers)
    base=next((r for r in held_summary if r["candidate"]=="BASE_PARENT"),None)
    if not base:raise RuntimeError("baseline missing from heldout")
    for row in held_summary:
        row["delta_win_vs_base"]=row["win_score"]-base["win_score"];row["delta_cvar_vs_base"]=row["cvar20_score"]-base["cvar20_score"];row["delta_margin_vs_base"]=row["mean_margin"]-base["mean_margin"]
    promoted=[r for r in held_summary if r["candidate"]!="BASE_PARENT" and r["invalid"]==0 and r["win_score"]>=0.55 and r["delta_win_vs_base"]>=0.05 and r["cvar20_score"]>=base["cvar20_score"]-0.10]
    promoted.sort(key=lambda r:(r["delta_win_vs_base"],r["cvar20_score"],r["mean_margin"]),reverse=True)
    decision="PROMOTE" if promoted else "HOLD";archive=None;archive_sha=None;source_sha=None;winner=None
    if promoted:
        winner=promoted[0]["candidate"];source=variants[winner];source_sha=_hash_text(source);archive=root/"submission"/f"NEXT_SUBMIT_V77_LIVE_META_{winner}.tar.gz";archive_sha=_pack(source,archive)
    result={"decision":decision,"winner":winner,"parent":parent_info,"episode_acquisition":episode_report,"trace_count":len(traces),
            "train_trace_ids":train,"heldout_trace_ids":heldout,"holdout_teams":sorted(holdout_teams),"route_match_rows":match_rows,"learned_maps":learned,
            "screen_summary":screen_summary,"heldout_summary":held_summary,
            "promotion_contract":{"min_absolute_win_score":0.55,"min_delta_win_vs_base":0.05,"max_cvar_regression":0.10,"invalid_games":0},
            "archive":str(archive) if archive else None,"archive_sha256":archive_sha,"source_sha256":source_sha}
    (root/"V77_LIVE_META_RESULT.json").write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    compact={"decision":decision,"winner":winner,"parent":{k:v for k,v in parent_info.items() if k!="attempts"},"trace_count":len(traces),
             "train_count":len(train),"heldout_count":len(heldout),"screen_summary":screen_summary,"heldout_summary":held_summary,
             "archive":str(archive) if archive else None,"archive_sha256":archive_sha,"source_sha256":source_sha}
    (root/"V77_LIVE_META_SUMMARY.json").write_text(json.dumps(compact,indent=2,sort_keys=True),encoding="utf-8")
    return compact

def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument("--output-root",default="/tmp/v77-live-meta");ap.add_argument("--days",type=int,default=2);ap.add_argument("--per-day",type=int,default=8);ap.add_argument("--max-version",type=int,default=40);ap.add_argument("--workers",type=int,default=6);args=ap.parse_args()
    print(json.dumps(run(args.output_root,args.days,args.per_day,args.max_version,args.workers),indent=2,sort_keys=True))

if __name__=="__main__":main()
