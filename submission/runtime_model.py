from __future__ import annotations
import json,math,os
PRODUCTS=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"]
CROPS=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"];ANIMALS=["GOOSE","COW","SHEEP"]
SHOPS=["BAKERY","PIZZA_SHOP","BRUNCH_SPOT","YARN_STORE","ICE_CREAM_SHOP","PET_CAFE","SMOOTHIE_SHOP","FARMERS_MARKET"]
BASE={"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
FEATURES=(["day_norm","hour_norm","own_quadrants","opp_quadrants","own_hands","opp_hands"]+[f"price_ratio_{p}" for p in PRODUCTS]+[f"market_delta_{p}" for p in PRODUCTS]+[f"shop_{s}" for s in SHOPS]+[f"own_crop_{c}" for c in CROPS]+[f"opp_crop_{c}" for c in CROPS]+[f"own_animal_{a}" for a in ANIMALS]+[f"opp_animal_{a}" for a in ANIMALS]+["own_pasture","opp_pasture","own_coop","opp_coop"])

def _scan(f):
 c={x:0 for x in CROPS+ANIMALS};c.update(PASTURE=0,COOP=0)
 for row in (f or {}).get("tiles",[]) or []:
  for t in row:
   if not isinstance(t,dict):continue
   if t.get("kind")=="PLANT" and t.get("crop") in CROPS:c[t["crop"]]+=1
   if t.get("kind")=="PASTURE":c["PASTURE"]+=1
   if t.get("kind")=="COOP":c["COOP"]+=1
   if t.get("animal") in ANIMALS:c[t["animal"]]+=1
 return c

def feature_dict(obs):
 p=int(obs.get("player",0));fs=obs.get("farms",[]) or [];me=fs[p] if p<len(fs) else {};op=fs[1-p] if len(fs)>1 else {};a=_scan(me);b=_scan(op);m=obs.get("market",{}) or {};pr=m.get("prices",{}) or {};iv=m.get("inventory",{}) or {};shops=(obs.get("town",{}) or {}).get("unlocked_shops",[]) or []
 d={"day_norm":obs.get("day",0)/30.,"hour_norm":obs.get("hour",0)/24.,"own_quadrants":len(me.get("unlocked_quadrants",["NW"]))/4.,"opp_quadrants":len(op.get("unlocked_quadrants",["NW"]))/4.,"own_hands":len(me.get("hands",[]) or [])/16.,"opp_hands":len(op.get("hands",[]) or [])/16.}
 for x in PRODUCTS:d[f"price_ratio_{x}"]=pr.get(x,BASE[x])/BASE[x];d[f"market_delta_{x}"]=(iv.get(x,10000)-10000)/500.
 for s in SHOPS:d[f"shop_{s}"]=sum(str(x)==s for x in shops)/4.
 for c in CROPS:d[f"own_crop_{c}"]=a[c]/60.;d[f"opp_crop_{c}"]=b[c]/60.
 for x in ANIMALS:d[f"own_animal_{x}"]=a[x]/16.;d[f"opp_animal_{x}"]=b[x]/16.
 d["own_pasture"]=a["PASTURE"]/20.;d["opp_pasture"]=b["PASTURE"]/20.;d["own_coop"]=a["COOP"]/20.;d["opp_coop"]=b["COOP"]/20.;return d

def vector(obs,names=FEATURES):
 d=feature_dict(obs);return [float(d.get(n,0)) for n in names]
def dot(a,b):return sum(x*y for x,y in zip(a,b))

class ModelBundle:
 def __init__(self,path=None):
  self.obj={}
  try:
   if path and os.path.exists(path):self.obj=json.load(open(path))
  except Exception:self.obj={}
 def supply(self,obs):
  m=self.obj.get("supply")
  if not m:return {p:0. for p in PRODUCTS}
  x=vector(obs,m.get("features",FEATURES));co=m["coef"];it=m["intercept"];vals=[max(0.,dot(w,x)+b) for w,b in zip(co,it)]
  return {t.split("_")[-1]:v for t,v in zip(m["targets"],vals)}
 def archetype(self,obs):
  m=self.obj.get("archetype")
  if not m:return None,0.0
  names=m.get("runtime_features") or m.get("features")
  if not names or any(n not in FEATURES for n in names):return None,0.0
  x=vector(obs,names);mean=m.get("mean",[0]*len(x));scale=m.get("scale",[1]*len(x));z=[(a-b)/(s if abs(s)>1e-9 else 1) for a,b,s in zip(x,mean,scale)]
  ds=[sum((a-b)**2 for a,b in zip(z,c)) for c in m.get("centroids",[])];
  if not ds:return None,0.0
  order=sorted(range(len(ds)),key=ds.__getitem__);best=order[0];gap=(ds[order[1]]-ds[best]) if len(order)>1 else 1.;conf=1-math.exp(-max(0,gap));return best,conf
