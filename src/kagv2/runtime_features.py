from __future__ import annotations
from .constants import PRODUCTS,CROPS,ANIMALS,SHOPS,BASE,PUBLIC_RUNTIME_FEATURES

def _scan(farm):
    c={x:0 for x in CROPS+ANIMALS}; c.update(PASTURE=0,COOP=0)
    for row in (farm or {}).get("tiles",[]) or []:
        for t in row:
            if not isinstance(t,dict): continue
            if t.get("kind")=="PLANT" and t.get("crop") in CROPS: c[t["crop"]]+=1
            if t.get("kind")=="PASTURE": c["PASTURE"]+=1
            if t.get("kind")=="COOP": c["COOP"]+=1
            if t.get("animal") in ANIMALS: c[t["animal"]]+=1
    return c

def runtime_feature_dict(obs):
    p=int(obs.get("player",0)); farms=obs.get("farms",[]) or []
    me=farms[p] if p<len(farms) else {}; opp=farms[1-p] if len(farms)>1 else {}
    mc=_scan(me); oc=_scan(opp); market=obs.get("market",{}) or {}
    prices=market.get("prices",{}) or {}; inv=market.get("inventory",{}) or {}
    shops=(obs.get("town",{}) or {}).get("unlocked_shops",[]) or []
    d={
      "day_norm":float(obs.get("day",0))/30.0,
      "hour_norm":float(obs.get("hour",0))/24.0,
      "own_quadrants":len(me.get("unlocked_quadrants",["NW"])) / 4.0,
      "opp_quadrants":len(opp.get("unlocked_quadrants",["NW"])) / 4.0,
      "own_hands":len(me.get("hands",[]) or [])/16.0,
      "opp_hands":len(opp.get("hands",[]) or [])/16.0,
    }
    for x in PRODUCTS:
        d[f"price_ratio_{x}"]=float(prices.get(x,BASE[x]))/max(1.0,BASE[x])
        d[f"market_delta_{x}"]=(float(inv.get(x,10000))-10000.0)/500.0
    for s in SHOPS: d[f"shop_{s}"]=float(sum(str(x)==s for x in shops))/4.0
    for c in CROPS:
        d[f"own_crop_{c}"]=mc[c]/60.0; d[f"opp_crop_{c}"]=oc[c]/60.0
    for a in ANIMALS:
        d[f"own_animal_{a}"]=mc[a]/16.0; d[f"opp_animal_{a}"]=oc[a]/16.0
    for k in ("PASTURE","COOP"):
        d[f"own_{k.lower()}"]=mc[k]/20.0; d[f"opp_{k.lower()}"]=oc[k]/20.0
    return d

def runtime_feature_vector(obs, names=PUBLIC_RUNTIME_FEATURES):
    d=runtime_feature_dict(obs)
    return [float(d.get(n,0.0)) for n in names]
