from __future__ import annotations

import json
import math
import os

BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
ANIMAL_PRODUCT = {"GOOSE":"EGG","COW":"MILK","SHEEP":"WOOL"}
SHED_ACCESS = ((4,4),(5,4),(4,5),(5,5))


def _step(obs):
    raw=(obs or {}).get("step")
    if raw is not None:
        try:return int(raw)
        except Exception:pass
    return int((obs or {}).get("day",0) or 0)*24+int((obs or {}).get("hour",0) or 0)


def _shop_demand(shops, product):
    total=0
    for shop in shops or ():
        products=SHOP_PRODUCTS.get(str(shop),())
        if product in products: total += 2 if len(products)==1 else 1
    return total


def _town_drain(step, shops, product):
    out=_shop_demand(shops,product) if int(step)%4==0 else 0
    if product!="FERTILIZER" and int(step)%24==0: out+=1
    return out


def _positions(farm):
    out=[]
    farmer=(farm or {}).get("farmer")
    if isinstance(farmer,(list,tuple)) and len(farmer)>=2: out.append((int(farmer[0]),int(farmer[1])))
    for pos in list((farm or {}).get("hands",[]) or []):
        if isinstance(pos,(list,tuple)) and len(pos)>=2: out.append((int(pos[0]),int(pos[1])))
    return out


def _shed_distance(pos):
    return min(abs(pos[0]-x)+abs(pos[1]-y) for x,y in SHED_ACCESS)


def _tile_stats(farm, product):
    animal_count=animal_yield=animal_ready=animal_cared=animal_fed=0.0
    crop_count=crop_yield=crop_ready=0.0
    animals={"GOOSE":0.0,"COW":0.0,"SHEEP":0.0}
    crops={"WHEAT":0.0,"CARROT":0.0,"TOMATO":0.0,"STRAWBERRY":0.0,"MELON":0.0}
    for row in list((farm or {}).get("tiles",[]) or []):
        for tile in list(row or []):
            if not isinstance(tile,dict): continue
            animal=str(tile.get("animal",""))
            if animal in animals:
                animals[animal]+=1.0
                if ANIMAL_PRODUCT[animal]==product:
                    y=float(tile.get("yield_units",0) or 0)
                    animal_count+=1.0; animal_yield+=y; animal_ready+=float(y>0)
                    animal_cared+=float(bool(tile.get("cared_today",False)))
                    animal_fed+=float(bool(tile.get("fed_today",False)))
            crop=str(tile.get("crop",""))
            if crop in crops:
                crops[crop]+=1.0
                if crop==product:
                    y=float(tile.get("yield_units",0) or 0)
                    crop_count+=1.0; crop_yield+=y; crop_ready+=float(y>0)
    return {
        "animal_count":animal_count/25.0,"animal_yield":animal_yield/100.0,"animal_ready":animal_ready/25.0,
        "animal_cared":animal_cared/25.0,"animal_fed":animal_fed/25.0,
        "crop_count":crop_count/25.0,"crop_yield":crop_yield/100.0,"crop_ready":crop_ready/25.0,
        "geese":animals["GOOSE"]/25.0,"cows":animals["COW"]/25.0,"sheep":animals["SHEEP"]/25.0,
        "wheat_tiles":crops["WHEAT"]/25.0,"carrot_tiles":crops["CARROT"]/25.0,
        "tomato_tiles":crops["TOMATO"]/25.0,"strawberry_tiles":crops["STRAWBERRY"]/25.0,
        "melon_tiles":crops["MELON"]/25.0,
    }


def public_sale_features(obs, target_seat, product):
    product=str(product); farms=list((obs or {}).get("farms",[]) or [])
    farm=farms[int(target_seat)] if int(target_seat)<len(farms) else {}
    market=(obs or {}).get("market",{}) or {}; invs=market.get("inventory",{}) or {}; prices=market.get("prices",{}) or {}
    shops=list((((obs or {}).get("town",{}) or {}).get("unlocked_shops",[]) or [])); step=_step(obs)
    positions=_positions(farm); inv=float(invs.get(product,10000) or 10000); price=float(prices.get(product,BASE.get(product,1)) or 1)
    money=max(0.0,float((farm or {}).get("money",0) or 0)); quadrants=list((farm or {}).get("unlocked_quadrants",[]) or [])
    out={
        "step_frac":step/720.0,"day_frac":float((obs or {}).get("day",0) or 0)/30.0,"hour_frac":float((obs or {}).get("hour",0) or 0)/24.0,
        "money_log":math.log1p(money)/12.0,"hands":float(len(list((farm or {}).get("hands",[]) or [])))/16.0,"quadrants":float(len(quadrants))/4.0,
        "market_inventory_delta":(inv-10000.0)/500.0,"market_price_ratio":price/max(1.0,float(BASE.get(product,1))),"market_floor":float(price<=1.0),
        "shop_demand":float(_shop_demand(shops,product))/8.0,"town_drain_now":float(_town_drain(step,shops,product))/8.0,
        "units_near_shed":float(sum(_shed_distance(p)==0 for p in positions))/16.0,
        "min_shed_distance":float(min((_shed_distance(p) for p in positions),default=12))/12.0,
    }
    out.update(_tile_stats(farm,product)); return out


def _sigmoid(x):
    if x>=0:
        z=math.exp(-min(60.0,x)); return 1.0/(1.0+z)
    z=math.exp(max(-60.0,x)); return z/(1.0+z)


def _clip01(x): return max(1e-5,min(1.0-1e-5,float(x)))
def _logit(p):
    p=_clip01(p); return math.log(p/(1.0-p))


class DistilledSalePredictor:
    def __init__(self,path=None):
        self.path=path; self.obj={}; self.models={}
        try:
            if path and os.path.exists(path):
                with open(path,encoding="utf-8") as fh:self.obj=json.load(fh)
        except Exception:self.obj={}
        self.models=dict((self.obj or {}).get("models") or {})

    def available(self,product): return str(product) in self.models
    def model(self,product): return self.models.get(str(product)) or {}
    def threshold(self,product): return float(self.model(product).get("threshold",1.0))
    def prevalence(self,product): return float(self.model(product).get("prevalence",0.05))
    def shock_mean(self,product): return float(self.model(product).get("shock_mean",6.0))

    def probability(self,obs,target_seat,product):
        m=self.model(product)
        if not m:return 0.0
        f=public_sale_features(obs,target_seat,product); names=list(m.get("features") or [])
        mean=list(m.get("mean") or []); scale=list(m.get("scale") or []); coef=list(m.get("coef") or [])
        score=float(m.get("intercept",0.0))
        for i,name in enumerate(names):
            x=float(f.get(name,0.0)); mu=float(mean[i]) if i<len(mean) else 0.0; sd=float(scale[i]) if i<len(scale) else 1.0
            if abs(sd)<1e-9:sd=1.0
            score += (float(coef[i]) if i<len(coef) else 0.0)*((x-mu)/sd)
        return _sigmoid(score)

    def adjusted_probability(self,raw,product,global_rate=None,bucket_rate=None,trust=1.0):
        prior=_clip01(self.prevalence(product)); score=_logit(raw)
        w=max(0.0,min(1.0,float(trust)))
        if global_rate is not None: score += 0.55*w*(_logit(global_rate)-_logit(prior))
        if bucket_rate is not None: score += 0.30*w*(_logit(bucket_rate)-_logit(prior))
        return _sigmoid(score)
