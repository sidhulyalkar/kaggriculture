from __future__ import annotations

"""V44 Frontier Margin runtime compiler.

The compiler embeds one already-qualified frontier parent unchanged and adds a
small public-state market residual. Physical actions remain parent-authored
except for a final-turn safe DROP when the carrier is already standing on a
shed tile and the whole carried inventory fits.
"""

from copy import deepcopy
from hashlib import sha256
import json


BASE_CONFIG = {
    "name": "V44_CORE",
    "fragility_ordering": True,
    "pressure_forecast": True,
    "mirror_sale_qty": 0,
    "mirror_streak": 3,
    "mirror_cooldown": 24,
    "mirror_min_price_ratio": 0.92,
    "one_turn_defer": False,
    "defer_pressure": 12,
    "defer_min_gain": 20,
    "defer_shed_hard": 84,
    "defer_cash_buffer": 2500,
    "late_latch": False,
    "late_latch_step": 576,
    "protect_edge": 7000,
    "protect_streak": 3,
    "terminal_liquidation": True,
    "terminal_step": 718,
    "ordering_start": 96,
    "ordering_end": 707,
    "stress_floor": 8,
    "stress_cap": 28,
}


def candidate_configs() -> dict[str, dict]:
    """Small causal portfolio, deliberately not a combinatorial soup."""
    def c(name: str, **updates):
        z = deepcopy(BASE_CONFIG)
        z.update(name=name, **updates)
        return z

    return {
        "V44_COMPILED_CONTROL": c(
            "V44_COMPILED_CONTROL",
            fragility_ordering=False,
            pressure_forecast=False,
            terminal_liquidation=False,
        ),
        "V44_CORE": c("V44_CORE"),
        "V44_MIRROR": c("V44_MIRROR", mirror_sale_qty=1),
        "V44_LATCH": c("V44_LATCH", late_latch=True),
        "V44_FULL_SAFE": c("V44_FULL_SAFE", mirror_sale_qty=1, late_latch=True),
        "V44_FULL_TIMING": c(
            "V44_FULL_TIMING",
            mirror_sale_qty=1,
            late_latch=True,
            one_turn_defer=True,
        ),
        "V44_MIRROR_2": c("V44_MIRROR_2", mirror_sale_qty=2),
    }


def source_sha256(source: str) -> str:
    return sha256(source.encode("utf-8")).hexdigest()


def build_runtime_source(parent_source: str, config: dict | None = None, *, parent_label: str = "frontier") -> str:
    """Compile a self-contained single-file Kaggle agent.

    Parent source is executed inside a private globals dictionary, so its
    callables never interfere with Kaggle's last-callable selection. The final
    top-level callable defined by this generated file is always ``agent``.
    """
    cfg = deepcopy(BASE_CONFIG)
    if config:
        cfg.update(config)
    cfg_text = repr(cfg)
    parent_text = repr(str(parent_source))
    label_text = repr(str(parent_label))

    template = r'''# Generated V44 Frontier Margin Engine
# Parent label: __PARENT_LABEL__
# Parent source is embedded verbatim below; preserve its original license notices.
from copy import deepcopy as _v44_deepcopy
import math as _v44_math

_V44_CFG = __CFG__
_V44_PARENT_SOURCE = __PARENT_SOURCE__
_V44_PARENT = None
_V44_PARENT_NS = None
_V44_STATE = {}
_V44_STATS = {}

_V44_PRODUCTS = ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
_V44_PREMIUM = ("STRAWBERRY","MELON","MILK","WOOL")
_V44_BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
_V44_PARAMS = {
 "WHEAT":(400,"sqrt",.80,"log",.20),"CARROT":(450,"hinge",1.00,"sqrt",.70),
 "TOMATO":(200,"hinge",.40,"sqrt",.60),"STRAWBERRY":(100,"sqrt",.70,"linear",1.60),
 "MELON":(300,"log",.20,"sq",3.60),"EGG":(332,"hinge",.40,"log",.20),
 "MILK":(122,"sqrt",.60,"linear",1.60),"WOOL":(105,"log",.20,"sq",3.20),
 "FERTILIZER":(200,"linear",.40,"linear",.40),
}
_V44_SHOPS = {
 "BAKERY":("EGG","WHEAT"),"PIZZA_SHOP":("MILK","TOMATO","WHEAT"),
 "BRUNCH_SPOT":("EGG","WHEAT","STRAWBERRY"),"YARN_STORE":("WOOL",),
 "ICE_CREAM_SHOP":("STRAWBERRY","MILK","WHEAT"),"PET_CAFE":("CARROT",),
 "SMOOTHIE_SHOP":("STRAWBERRY","MILK"),"FARMERS_MARKET":("WHEAT","CARROT","TOMATO","STRAWBERRY"),
}
_V44_ANIMAL_PRODUCT = {"GOOSE":"EGG","COW":"MILK","SHEEP":"WOOL"}
_V44_CROP_FIRST = {"WHEAT":2,"CARROT":2,"TOMATO":8,"STRAWBERRY":10,"MELON":10}
_V44_SHED = ((4,4),(5,4),(4,5),(5,5))


def _v44_shape(kind, x, T):
    x=max(0.0,float(x))
    if kind=="linear": return x
    if kind=="sq": return x*x
    if kind=="sqrt": return _v44_math.sqrt(x)
    if kind=="log": return _v44_math.log1p(x)
    if kind=="hinge":
        u=x/T if T else x
        return u+8.0*max(0.0,u-1.0)**2
    return x


def _v44_price(item, inv):
    T,bf,bt,af,at=_V44_PARAMS[item];base=_V44_BASE[item];inv=int(inv)
    if inv<10000:
        den=_v44_shape(bf,T,T) or 1.0
        p=base+(bt*base/den)*_v44_shape(bf,10000-inv,T)
    else:
        den=_v44_shape(af,T,T) or 1.0
        p=base-(at*base/den)*_v44_shape(af,inv-10000,T)
    return max(1,int(round(p)))


def _v44_revenue(item, inv, qty):
    inv=int(inv);qty=max(0,int(qty));return sum(_v44_price(item,inv+i) for i in range(qty))


def _v44_reset(load_parent=False):
    global _V44_PARENT,_V44_PARENT_NS,_V44_STATE,_V44_STATS
    _V44_STATE={
        "last_step":-1,"prev_market":{},"prev_town":[],"prev_own_sell":{},"deferred":{},
        "mirror_streak":0,"last_mirror_sale":-10000,"protect_streak":0,"protect_latched":False,
    }
    _V44_STATS={
        "calls":0,"market_changed":0,"physical_changed":0,"defer_events":0,"defer_releases":0,
        "mirror_sales":0,"protect_cancels":0,"terminal_forced_drops":0,"terminal_sell_orders":0,
    }
    if load_parent or _V44_PARENT is None:
        ns={"__name__":"v44_embedded_parent","__file__":"main.py"}
        exec(compile(_V44_PARENT_SOURCE,"<v44-parent>","exec"),ns,ns)
        fn=ns.get("agent") or ns.get("main") or ns.get("v40_frontier_agent")
        if not callable(fn):
            vals=[v for k,v in ns.items() if callable(v) and not str(k).startswith("_")]
            if not vals: raise RuntimeError("V44 embedded parent exposes no callable agent")
            fn=vals[-1]
        _V44_PARENT_NS=ns;_V44_PARENT=fn


def _v44_call_parent(obs, configuration=None):
    try: return _V44_PARENT(obs,configuration)
    except TypeError: return _V44_PARENT(obs)


def _v44_market_inv(obs):
    return ((obs.get("market",{}) or {}).get("inventory",{}) or {})


def _v44_shed(obs):
    return ((obs.get("private",{}) or {}).get("shed",{}) or {})


def _v44_town_demand(step, shops, item):
    n=0
    if int(step)%4==0:
        for shop in shops or ():
            ps=_V44_SHOPS.get(shop,())
            if item in ps: n += 2 if len(ps)==1 else 1
    if int(step)%24==0 and item!="FERTILIZER": n+=1
    return n


def _v44_requested_sells(market, shed):
    out={}
    for o in market or ():
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1] in _V44_PRODUCTS:
            try:q=max(0,int(o[2]))
            except Exception:q=0
            out[o[1]]=out.get(o[1],0)+q
    return {k:min(v,max(0,int(shed.get(k,0) or 0))) for k,v in out.items()}


def _v44_pressure(obs, item):
    cur=int(_v44_market_inv(obs).get(item,10000) or 10000)
    prev=_V44_STATE["prev_market"].get(item)
    if prev is None:return 0
    own=int(_V44_STATE["prev_own_sell"].get(item,0) or 0)
    demand=_v44_town_demand(_V44_STATE["last_step"],_V44_STATE["prev_town"],item)
    return cur-int(prev)-own+demand


def _v44_visible_supply(farm):
    out={k:0 for k in _V44_PRODUCTS}
    for row in (farm or {}).get("tiles",[]) or []:
        for t in row or []:
            if not isinstance(t,dict):continue
            q=max(0,int(t.get("yield_units",0) or 0))
            if q<=0:continue
            if t.get("kind")=="PLANT" and t.get("crop") in out:out[t["crop"]]+=q
            a=t.get("animal")
            if a in _V44_ANIMAL_PRODUCT:out[_V44_ANIMAL_PRODUCT[a]]+=q
    return out


def _v44_stress(obs,item):
    p=max(0,_v44_pressure(obs,item)) if _V44_CFG.get("pressure_forecast") else 0
    player=int(obs.get("player",0) or 0);farms=obs.get("farms",[]) or []
    opp=farms[1-player] if len(farms)>1 else {}
    vis=_v44_visible_supply(opp).get(item,0)
    floor=int(_V44_CFG.get("stress_floor",8));cap=int(_V44_CFG.get("stress_cap",28))
    return min(cap,max(floor,p+min(12,max(0,int(vis))//2)))


def _v44_priority(obs, order):
    item=order[1]
    try:q=max(0,int(order[2]))
    except Exception:q=0
    inv=int(_v44_market_inv(obs).get(item,10000) or 10000);stress=_v44_stress(obs,item)
    now=_v44_revenue(item,inv,q);later=_v44_revenue(item,inv+stress,q);loss=max(0,now-later)
    premium=0 if item in _V44_PREMIUM else 1
    return (premium,-loss,-(loss/max(1,q)),-q,item)


def _v44_reorder_sell_slots(obs, market):
    if not _V44_CFG.get("fragility_ordering"):return list(market)
    step=int(obs.get("step",0) or 0)
    if not int(_V44_CFG.get("ordering_start",0))<=step<=int(_V44_CFG.get("ordering_end",707)):return list(market)
    z=list(market);idx=[];orders=[]
    for i,o in enumerate(z):
        if isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1] in _V44_PRODUCTS:
            idx.append(i);orders.append(o)
    if len(orders)<2:return z
    orders=sorted(orders,key=lambda o:_v44_priority(obs,o))
    for i,o in zip(idx,orders):z[i]=o
    return z


def _v44_has_capital_dependency(market):
    for o in market:
        if isinstance(o,list) and o and o[0] in ("HIRE","BUY_LAND","BUY_ANIMAL"):return True
    return False


def _v44_apply_defer(obs, market):
    if not _V44_CFG.get("one_turn_defer"):return market
    step=int(obs.get("step",0) or 0);shed=_v44_shed(obs);shed_total=sum(max(0,int(v or 0)) for v in shed.values())
    player=int(obs.get("player",0) or 0);farms=obs.get("farms",[]) or []
    cash=float((farms[player] if len(farms)>player else {}).get("money",0) or 0)
    if step<144 or step>=690 or step%4!=0 or shed_total>=int(_V44_CFG.get("defer_shed_hard",84)):
        return market
    if cash<float(_V44_CFG.get("defer_cash_buffer",2500)) or _v44_has_capital_dependency(market):return market
    z=list(market);shops=((obs.get("town",{}) or {}).get("unlocked_shops",[]) or [])
    opp=(farms[1-player] if len(farms)>1 else {});visible=_v44_visible_supply(opp)
    for i,o in enumerate(z):
        if not (isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1] in _V44_PREMIUM):continue
        item=o[1]
        try:q=max(0,int(o[2]))
        except Exception:continue
        if q<=0 or _v44_pressure(obs,item)<int(_V44_CFG.get("defer_pressure",12)):continue
        inv=int(_v44_market_inv(obs).get(item,10000) or 10000);demand=_v44_town_demand(step,shops,item)
        if demand<=0:continue
        now=_v44_revenue(item,inv,q)
        stressed=max(0,int(visible.get(item,0) or 0)//4)
        wait=_v44_revenue(item,max(0,inv-demand+stressed),q)
        if wait-now<int(_V44_CFG.get("defer_min_gain",20)):continue
        _V44_STATE["deferred"][item]={"qty":q,"release":step+1}
        z[i]=["PASS"]
        _V44_STATS["defer_events"]+=1
        break
    return z


def _v44_release_deferred(obs, market):
    step=int(obs.get("step",0) or 0);z=list(market)
    for item,rec in list(_V44_STATE["deferred"].items()):
        if int(rec.get("release",10**9))>step:continue
        q=max(0,int(rec.get("qty",0) or 0));done=False
        for i,o in enumerate(z):
            if isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1]==item:
                try:old=max(0,int(o[2]))
                except Exception:old=0
                z[i]=["SELL",item,old+q];done=True;break
        if not done:
            for i,o in enumerate(z):
                if isinstance(o,list) and o and o[0]=="PASS":z[i]=["SELL",item,q];done=True;break
        if not done and len(z)<10:z.append(["SELL",item,q]);done=True
        if done:
            del _V44_STATE["deferred"][item];_V44_STATS["defer_releases"]+=1
    return z


def _v44_farm_signature(farm):
    c={"COW":0,"SHEEP":0,"GOOSE":0,"WHEAT":0,"CARROT":0,"TOMATO":0,"STRAWBERRY":0,"MELON":0}
    for row in (farm or {}).get("tiles",[]) or []:
        for t in row or []:
            if not isinstance(t,dict):continue
            if t.get("kind")=="PLANT" and t.get("crop") in c:c[t["crop"]]+=1
            if t.get("animal") in c:c[t["animal"]]+=1
    return c


def _v44_is_mirror(obs):
    player=int(obs.get("player",0) or 0);farms=obs.get("farms",[]) or []
    if len(farms)<2:return False
    a=farms[player];b=farms[1-player]
    if len(a.get("unlocked_quadrants",[]) or [])!=len(b.get("unlocked_quadrants",[]) or []):return False
    if abs(len(a.get("hands",[]) or [])-len(b.get("hands",[]) or []))>1:return False
    sa=_v44_farm_signature(a);sb=_v44_farm_signature(b)
    if abs(sa["COW"]-sb["COW"])>1 or abs(sa["SHEEP"]-sb["SHEEP"])>1:return False
    cropdiff=sum(abs(sa[k]-sb[k]) for k in ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"))
    if cropdiff>5:return False
    ca=float(a.get("money",0) or 0);cb=float(b.get("money",0) or 0)
    return abs(ca-cb)<=max(1500.0,.06*max(ca,cb,1.0))


def _v44_mirror_break(obs, market):
    qty=int(_V44_CFG.get("mirror_sale_qty",0) or 0)
    if qty<=0:return market
    step=int(obs.get("step",0) or 0)
    if step<192 or step>660:return market
    if _v44_is_mirror(obs):_V44_STATE["mirror_streak"]+=1
    else:_V44_STATE["mirror_streak"]=0
    if _V44_STATE["mirror_streak"]<int(_V44_CFG.get("mirror_streak",3)):return market
    if step-_V44_STATE["last_mirror_sale"]<int(_V44_CFG.get("mirror_cooldown",24)):return market
    if len(market)>=10:return market
    sold={o[1] for o in market if isinstance(o,list) and len(o)>=3 and o[0]=="SELL"}
    shed=_v44_shed(obs);cands=[]
    for item in _V44_PREMIUM:
        have=max(0,int(shed.get(item,0) or 0))
        if item in sold or have<qty:continue
        inv=int(_v44_market_inv(obs).get(item,10000) or 10000);price=_v44_price(item,inv)
        if price<float(_V44_BASE[item])*float(_V44_CFG.get("mirror_min_price_ratio",.92)):continue
        probe=["SELL",item,qty];cands.append((_v44_priority(obs,probe),item))
    if not cands:return market
    cands.sort();item=cands[0][1];z=list(market);z.append(["SELL",item,qty])
    _V44_STATE["last_mirror_sale"]=step;_V44_STATS["mirror_sales"]+=1
    return z


def _v44_estimated_edge(obs):
    player=int(obs.get("player",0) or 0);farms=obs.get("farms",[]) or []
    if len(farms)<2:return 0.0
    a=farms[player];b=farms[1-player];prices=((obs.get("market",{}) or {}).get("prices",{}) or {})
    shed=_v44_shed(obs);own_shed=sum(max(0,int(shed.get(k,0) or 0))*float(prices.get(k,_V44_BASE[k]) or 0) for k in _V44_PRODUCTS)
    va=_v44_visible_supply(a);vb=_v44_visible_supply(b)
    own_vis=sum(va[k]*float(prices.get(k,_V44_BASE[k]) or 0) for k in _V44_PRODUCTS)
    opp_vis=sum(vb[k]*float(prices.get(k,_V44_BASE[k]) or 0) for k in _V44_PRODUCTS)
    return float(a.get("money",0) or 0)-float(b.get("money",0) or 0)+.65*(own_shed+own_vis)-.50*opp_vis


def _v44_late_latch(obs, market):
    if not _V44_CFG.get("late_latch"):return market
    step=int(obs.get("step",0) or 0)
    if step<int(_V44_CFG.get("late_latch_step",576)):return market
    edge=_v44_estimated_edge(obs)
    if edge>=float(_V44_CFG.get("protect_edge",7000)):_V44_STATE["protect_streak"]+=1
    else:_V44_STATE["protect_streak"]=0
    if _V44_STATE["protect_streak"]>=int(_V44_CFG.get("protect_streak",3)):_V44_STATE["protect_latched"]=True
    if not _V44_STATE["protect_latched"]:return market
    day=int(obs.get("day",step//24) or step//24);z=[]
    for o in market:
        cancel=False
        if isinstance(o,list) and o:
            if o[0]=="BUY_ANIMAL" and step>=600:cancel=True
            elif o[0]=="BUY_LAND" and step>=672:cancel=True
            elif o[0]=="BUY_SEED" and len(o)>=2 and o[1] in _V44_CROP_FIRST:
                if day+_V44_CROP_FIRST[o[1]]>=30:cancel=True
        if cancel:z.append(["PASS"]);_V44_STATS["protect_cancels"]+=1
        else:z.append(o)
    return z


def _v44_terminal(obs, action):
    if not _V44_CFG.get("terminal_liquidation"):return action
    step=int(obs.get("step",0) or 0)
    if step<int(_V44_CFG.get("terminal_step",718)):return action
    player=int(obs.get("player",0) or 0);farms=obs.get("farms",[]) or []
    farm=farms[player] if len(farms)>player else {};priv=obs.get("private",{}) or {};invs=priv.get("inventories",[]) or []
    shed=dict(_v44_shed(obs));shed_total=sum(max(0,int(v or 0)) for v in shed.values())
    positions=[farm.get("farmer")]+list(farm.get("hands",[]) or [])
    farmer=action.get("farmer",["PASS"]);hands=list(action.get("hands",[]) or [])
    allacts=[farmer]+hands;will_add={k:0 for k in _V44_PRODUCTS};physical=False
    for i,pos in enumerate(positions):
        if i>=len(allacts) or pos is None or tuple(pos) not in _V44_SHED or i>=len(invs):continue
        inv=invs[i] or {};carried=sum(max(0,int(v or 0)) for v in inv.values())
        if carried<=0 or shed_total+carried>100:continue
        allacts[i]=["DROP"];shed_total+=carried;physical=True;_V44_STATS["terminal_forced_drops"]+=1
        for item,q in inv.items():
            if item in will_add:will_add[item]+=max(0,int(q or 0))
    if allacts:
        action["farmer"]=allacts[0];action["hands"]=allacts[1:]
    if physical:_V44_STATS["physical_changed"]+=1
    orders=[]
    for item in _V44_PRODUCTS:
        q=max(0,int(shed.get(item,0) or 0))+will_add[item]
        if q>0:orders.append(["SELL",item,q])
    orders.sort(key=lambda o:_v44_priority(obs,o))
    action["market"]=orders[:10];_V44_STATS["terminal_sell_orders"]+=len(action["market"])
    return action


def _v44_overlay(obs, action):
    before_market=_v44_deepcopy(action.get("market",[]) or [])
    market=list(before_market)
    market=_v44_release_deferred(obs,market)
    market=_v44_apply_defer(obs,market)
    market=_v44_reorder_sell_slots(obs,market)
    market=_v44_mirror_break(obs,market)
    market=_v44_late_latch(obs,market)
    action["market"]=market[:10]
    if action.get("market",[])!=before_market:_V44_STATS["market_changed"]+=1
    return _v44_terminal(obs,action)


def agent(observation, configuration=None):
    global _V44_PARENT
    obs=observation if isinstance(observation,dict) else {}
    step=int(obs.get("step",0) or 0)
    if _V44_PARENT is None or step==0 or step<=int(_V44_STATE.get("last_step",-1)):_v44_reset(load_parent=True)
    _V44_STATS["calls"]+=1
    base=_v44_call_parent(_v44_deepcopy(obs),configuration)
    if not isinstance(base,dict):
        _V44_STATE["last_step"]=step
        return base
    action=_v44_deepcopy(base)
    action=_v44_overlay(obs,action)
    market=action.get("market",[]) or [];shed=_v44_shed(obs)
    _V44_STATE["prev_market"]={k:int(_v44_market_inv(obs).get(k,10000) or 10000) for k in _V44_PRODUCTS}
    _V44_STATE["prev_town"]=list(((obs.get("town",{}) or {}).get("unlocked_shops",[]) or []))
    _V44_STATE["prev_own_sell"]=_v44_requested_sells(market,shed)
    _V44_STATE["last_step"]=step
    return action
'''
    return template.replace("__CFG__", cfg_text).replace("__PARENT_SOURCE__", parent_text).replace("__PARENT_LABEL__", label_text)


__all__ = ["BASE_CONFIG", "candidate_configs", "build_runtime_source", "source_sha256"]
