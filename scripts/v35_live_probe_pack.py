#!/usr/bin/env python3
from __future__ import annotations

"""Build three V35 live-learning submissions from the runtime-verified V32 anchor.

The candidates deliberately preserve V32/Soil farming mechanics. They test
market execution microstructure only:

A. shadow_priority: reorder existing premium SELLs by exact delay risk.
B. slot_race: reorder every existing SELL by exact delay risk, ahead of buys.
C. front_run_light: A plus at most one tiny premium sale when recent external
   supply pressure is large and the current price is still healthy.

Every emitted tar must pass the official Kaggle last-callable loader and a full
self-play episode before and after repacking.
"""

from pathlib import Path
import argparse
import hashlib
import json
import shutil
import tarfile


MODES = {
    "V35A_SHADOW_PRIORITY": "shadow_priority",
    "V35B_SLOT_RACE": "slot_race",
    "V35C_FRONT_RUN_LIGHT": "front_run_light",
}


def safe_extract(tar_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            rel = Path(member.name)
            if rel.is_absolute() or ".." in rel.parts or not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fh.read())


def repack(root: Path, out: Path):
    with tarfile.open(out, "w:gz") as tf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                tf.add(p, arcname=str(p.relative_to(root)))


def find_anchor(inp: Path) -> Path:
    preferred = list(inp.rglob("SUBMIT_V32_RUNTIME_VERIFIED.tar.gz"))
    if preferred:
        return preferred[0]
    mirrors = list(inp.rglob("SUBMIT_V32_PREMIUM_FRONT_SINGLEFILE.tar.gz"))
    if mirrors:
        return mirrors[0]
    raise FileNotFoundError(
        "Attach Notebook 17B output containing SUBMIT_V32_RUNTIME_VERIFIED.tar.gz "
        "or the single-file V32 production tar."
    )


def loader_gate(root: Path):
    from kaggle_environments.agent import get_last_callable

    main = root / "main.py"
    fn = get_last_callable(main.read_text(), path=str(main))
    if not callable(fn):
        raise RuntimeError("Official Kaggle loader found no callable")
    name = getattr(fn, "__name__", repr(fn))
    if not name.startswith("v35_submission_agent"):
        raise RuntimeError(f"Kaggle selected unexpected callable: {name}")
    return name


def full_env_gate(root: Path):
    from kaggle_environments import make

    main = root / "main.py"
    env = make("kaggriculture", debug=False)
    env.run([str(main), str(main)])
    statuses = [str(s.status) for s in env.state]
    rewards = [s.reward for s in env.state]
    if any(s in {"ERROR", "INVALID", "TIMEOUT"} for s in statuses):
        raise RuntimeError(f"runtime gate failed: {statuses}")
    if any(r is None for r in rewards):
        raise RuntimeError(f"runtime gate returned null reward: {rewards}")
    return statuses, rewards


OVERLAY = r'''

# ===== V35 MARKET MICROSTRUCTURE OVERLAY =====
import math as _v35_math
_V35_MODE = __MODE__
_V35_BASE_AGENT = [v for v in list(globals().values()) if callable(v)][-1]
_V35_PREMIUM = {"STRAWBERRY", "MELON", "MILK", "WOOL"}
_V35_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
_V35_BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
_V35_PARAMS = {
 "WHEAT":(10000,400,"sqrt",.80,"log",.20),"CARROT":(10000,450,"hinge",1.0,"sqrt",.70),
 "TOMATO":(10000,200,"hinge",.40,"sqrt",.60),"STRAWBERRY":(10000,100,"sqrt",.70,"linear",1.60),
 "MELON":(10000,300,"log",.20,"sq",3.60),"EGG":(10000,332,"hinge",.40,"log",.20),
 "MILK":(10000,122,"sqrt",.60,"linear",1.60),"WOOL":(10000,105,"log",.20,"sq",3.20),
 "FERTILIZER":(10000,200,"linear",.40,"linear",.40),
}
_V35_PREV_INV = {}
_V35_OWN_LAST = {}
_V35_LAST_STEP = -1


def _v35_shape(f,x,T):
    x=max(0.0,float(x))
    if f=="linear": return x
    if f=="sq": return x*x
    if f=="sqrt": return _v35_math.sqrt(x)
    if f=="log": return _v35_math.log1p(x)
    if f=="hinge":
        u=x/T if T else x
        return u+8*max(0.0,u-1.0)**2
    return x


def _v35_price(item,inv):
    I0,T,bf,bt,af,at=_V35_PARAMS[item];base=_V35_BASE[item]
    if inv<I0:
        p=base+(bt*base/_v35_shape(bf,T,T))*_v35_shape(bf,I0-inv,T)
    else:
        p=base-(at*base/_v35_shape(af,T,T))*_v35_shape(af,inv-I0,T)
    return max(1,int(round(p)))


def _v35_revenue(item,inv,q):
    return sum(_v35_price(item,int(inv)+i) for i in range(max(0,int(q))))


def _v35_pressure(item,cur):
    if item not in _V35_PREV_INV:
        return 0
    return int(cur)-int(_V35_PREV_INV[item])-max(0,int(_V35_OWN_LAST.get(item,0)))


def _v35_urgency(item,inv,q):
    pressure=_v35_pressure(item,inv)
    stress=min(24,max(8,max(0,pressure)))
    now=_v35_revenue(item,inv,q)
    delayed=_v35_revenue(item,int(inv)+stress,q)
    loss=max(0,now-delayed)
    per=(loss/max(1,int(q)))
    return (float(loss),float(per))


def _v35_is_sell(o):
    return isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1] in _V35_PRODUCTS


def _v35_sort_key(o):
    if not _v35_is_sell(o):
        return (1,0.0,0.0,str(o))
    item=o[1]
    try:q=max(0,int(o[2]))
    except Exception:q=0
    inv=_V35_CURRENT_INV.get(item,10000)
    loss,per=_v35_urgency(item,inv,q)
    return (0,-loss,-per,item)


def _v35_call_base(observation,configuration):
    try:return _V35_BASE_AGENT(observation,configuration)
    except TypeError:return _V35_BASE_AGENT(observation)


def _v35_reset():
    global _V35_PREV_INV,_V35_OWN_LAST,_V35_LAST_STEP
    _V35_PREV_INV={};_V35_OWN_LAST={};_V35_LAST_STEP=-1


def v35_submission_agent(observation, configuration=None):
    global _V35_PREV_INV,_V35_OWN_LAST,_V35_LAST_STEP,_V35_CURRENT_INV
    obs=observation or {}
    step=int(obs.get("step",0) or 0)
    if step==0 or step<=_V35_LAST_STEP:
        _v35_reset()
    _V35_LAST_STEP=step

    action=_v35_call_base(observation,configuration)
    if not isinstance(action,dict):
        return action

    market=list(action.get("market",[]) or [])[:10]
    mkt=obs.get("market",{}) or {}
    _V35_CURRENT_INV=dict(mkt.get("inventory",{}) or {})
    private=obs.get("private",{}) or {}
    shed=dict(private.get("shed",{}) or {})

    if _V35_MODE=="shadow_priority":
        prem=[o for o in market if _v35_is_sell(o) and o[1] in _V35_PREMIUM]
        rest=[o for o in market if not (_v35_is_sell(o) and o[1] in _V35_PREMIUM)]
        prem=sorted(prem,key=_v35_sort_key)
        market=(prem+rest)[:10]

    elif _V35_MODE=="slot_race":
        sells=sorted([o for o in market if _v35_is_sell(o)],key=_v35_sort_key)
        rest=[o for o in market if not _v35_is_sell(o)]
        market=(sells+rest)[:10]

    elif _V35_MODE=="front_run_light":
        prem=[o for o in market if _v35_is_sell(o) and o[1] in _V35_PREMIUM]
        rest=[o for o in market if not (_v35_is_sell(o) and o[1] in _V35_PREMIUM)]
        prem=sorted(prem,key=_v35_sort_key)
        market=(prem+rest)[:10]
        present={o[1] for o in market if _v35_is_sell(o)}
        if 120<=step<672 and len(market)<10:
            choices=[]
            for item in _V35_PREMIUM:
                q=max(0,int(shed.get(item,0) or 0))
                if q<8 or item in present:continue
                inv=int(_V35_CURRENT_INV.get(item,10000) or 10000)
                pressure=_v35_pressure(item,inv)
                ratio=float(_v35_price(item,inv))/_V35_BASE[item]
                if pressure>=12 and ratio>=.80:
                    loss,per=_v35_urgency(item,inv,min(q,8))
                    choices.append((loss,per,item,q))
            if choices:
                _,_,item,q=max(choices)
                n=min(8,max(2,int(_v35_math.ceil(q*.25))))
                market=[["SELL",item,n]]+market
                market=market[:10]

    action["market"]=market[:10]
    own={}
    for o in action["market"]:
        if _v35_is_sell(o):
            own[o[1]]=own.get(o[1],0)+max(0,int(o[2]))
    _V35_OWN_LAST=own
    _V35_PREV_INV={p:int(_V35_CURRENT_INV.get(p,10000) or 10000) for p in _V35_PRODUCTS}
    return action
'''


def build_candidate(anchor: Path, work: Path, label: str, mode: str):
    root = work / label
    if root.exists():
        shutil.rmtree(root)
    safe_extract(anchor, root)
    main = root / "main.py"
    if not main.exists():
        raise RuntimeError(f"{anchor} has no root main.py")
    source = main.read_text()
    if "__file__" in source:
        raise RuntimeError(
            "V32 root main.py contains __file__; attach the runtime-verified V32 artifact, not the old research tar."
        )
    source = source.rstrip() + "\n" + OVERLAY.replace("__MODE__", repr(mode)).lstrip()
    main.write_text(source)
    for p in root.rglob("*.py"):
        compile(p.read_text(), str(p), "exec")
    selected = loader_gate(root)
    statuses_a, rewards_a = full_env_gate(root)

    out = work / f"SUBMIT_{label}.tar.gz"
    repack(root, out)
    verify = work / f"verify_{label}"
    if verify.exists():
        shutil.rmtree(verify)
    safe_extract(out, verify)
    selected_b = loader_gate(verify)
    statuses_b, rewards_b = full_env_gate(verify)
    return out, {
        "label": label,
        "mode": mode,
        "archive": str(out),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "selected_callable_before_pack": selected,
        "selected_callable_after_pack": selected_b,
        "statuses_before_pack": statuses_a,
        "rewards_before_pack": rewards_a,
        "statuses_after_pack": statuses_b,
        "rewards_after_pack": rewards_b,
        "runtime_verified": True,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default="/kaggle/input")
    ap.add_argument("--work", default="/kaggle/working/v35_live_probes")
    args = ap.parse_args()

    inp = Path(args.input_root)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    anchor = find_anchor(inp)
    print("V32 anchor:", anchor)
    print("V32 sha256:", hashlib.sha256(anchor.read_bytes()).hexdigest())

    manifests = []
    for label, mode in MODES.items():
        print("\nBUILDING", label, mode)
        out, manifest = build_candidate(anchor, work, label, mode)
        manifests.append(manifest)
        print(json.dumps(manifest, indent=2))

    final = {
        "version": 35,
        "anchor": str(anchor),
        "anchor_sha256": hashlib.sha256(anchor.read_bytes()).hexdigest(),
        "candidates": manifests,
        "recommended_live_order": [
            "SUBMIT_V35A_SHADOW_PRIORITY.tar.gz",
            "SUBMIT_V35B_SLOT_RACE.tar.gz",
            "SUBMIT_V35C_FRONT_RUN_LIGHT.tar.gz",
        ],
        "note": "These are learning probes, not automatic replacements for V32. Compare stabilized ratings and opponent episodes before promotion.",
    }
    (work / "V35_LIVE_PROBE_MANIFEST.json").write_text(json.dumps(final, indent=2))
    print("\n=== LIVE PROBE PACK ===")
    print(json.dumps(final, indent=2))


if __name__ == "__main__":
    main()
