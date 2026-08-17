"""Deterministic Kaggriculture farm controller.

This module owns mechanics and low-level execution. Strategy variants subclass
HarvestMind and override target/sell methods rather than movement rules.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

CROPS={
 "WHEAT":dict(seed=10,first=2,maxday=4,interval=0,max_yield=6,ongoing=False),
 "CARROT":dict(seed=20,first=2,maxday=3,interval=0,max_yield=4,ongoing=False),
 "TOMATO":dict(seed=50,first=8,maxday=8,interval=1,max_yield=4,ongoing=True),
 "STRAWBERRY":dict(seed=100,first=10,maxday=10,interval=2,max_yield=4,ongoing=True),
 "MELON":dict(seed=80,first=10,maxday=12,interval=0,max_yield=6,ongoing=False),
}
ANIMALS={
 "GOOSE":dict(cost=300,structure="COOP",product="EGG",first=4,interval=1,cap=4),
 "COW":dict(cost=400,structure="PASTURE",product="MILK",first=8,interval=2,cap=6),
 "SHEEP":dict(cost=500,structure="PASTURE",product="WOOL",first=6,interval=3,cap=6),
}
PRODUCTS=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"]
BASE={"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
PARAMS={
 "WHEAT":(10000,400,"sqrt",.80,"log",.20),"CARROT":(10000,450,"hinge",1.0,"sqrt",.70),
 "TOMATO":(10000,200,"hinge",.40,"sqrt",.60),"STRAWBERRY":(10000,100,"sqrt",.70,"linear",1.60),
 "MELON":(10000,300,"log",.20,"sq",3.60),"EGG":(10000,332,"hinge",.40,"log",.20),
 "MILK":(10000,122,"sqrt",.60,"linear",1.60),"WOOL":(10000,105,"log",.20,"sq",3.20),
 "FERTILIZER":(10000,200,"linear",.40,"linear",.40),
}
SHOPS={"BAKERY":{"EGG":1,"WHEAT":1},"PIZZA_SHOP":{"MILK":1,"TOMATO":1,"WHEAT":1},"BRUNCH_SPOT":{"EGG":1,"WHEAT":1,"STRAWBERRY":1},"YARN_STORE":{"WOOL":2},"ICE_CREAM_SHOP":{"STRAWBERRY":1,"MILK":1,"WHEAT":1},"PET_CAFE":{"CARROT":2},"SMOOTHIE_SHOP":{"STRAWBERRY":1,"MILK":1},"FARMERS_MARKET":{"WHEAT":1,"CARROT":1,"TOMATO":1,"STRAWBERRY":1}}
FIB=[1,1,2,3,5,8,13,21,34,55,89,144,233,377,610,987,1597,2584,4181]
SHED=((4,4),(5,4),(4,5),(5,5))
LAND_PRICES=(1000,2000,4000)


def _shape(f,x,T):
 x=max(0.,float(x))
 if f=="linear":return x
 if f=="sq":return x*x
 if f=="sqrt":return math.sqrt(x)
 if f=="log":return math.log1p(x)
 if f=="hinge":
  u=x/T if T else x
  return u+8*max(0.,u-1)**2
 return x

def model_price(item,inv):
 I0,T,bf,bt,af,at=PARAMS[item];base=BASE[item]
 if inv<I0:p=base+(bt*base/_shape(bf,T,T))*_shape(bf,I0-inv,T)
 else:p=base-(at*base/_shape(af,T,T))*_shape(af,inv-I0,T)
 return max(1,int(round(p)))
def sellable_above(item,inv,reserve,max_n=1000):
 n=0
 while n<max_n:
  p=model_price(item,inv)
  if p<reserve:break
  n+=1
  if p>1:inv+=1
 return n

@dataclass
class Config:
 cash_floor:int=300
 shed_soft:int=76
 shed_hard:int=90
 terminal_start:int=26
 terminal_hard:int=9
 max_land:int=3

class HarvestMind:
 def __init__(self,cfg=None):
  self.cfg=cfg or Config();self.last_step=-1
 @staticmethod
 def dist(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])
 @staticmethod
 def move(a,b):
  x,y=a;tx,ty=b
  if (x+y)&1:
   if y<ty:return ["SOUTH"]
   if y>ty:return ["NORTH"]
   if x<tx:return ["EAST"]
   if x>tx:return ["WEST"]
  else:
   if x<tx:return ["EAST"]
   if x>tx:return ["WEST"]
   if y<ty:return ["SOUTH"]
   if y>ty:return ["NORTH"]
  return ["PASS"]
 def _counts(self,farm):
  c={x:0 for x in list(CROPS)+list(ANIMALS)};c.update(PASTURE=0,COOP=0,WEED=0,EMPTY=0)
  for row in farm.get("tiles",[]) or []:
   for t in row:
    if t is None:c["EMPTY"]+=1
    elif isinstance(t,dict):
     if t.get("kind")=="PLANT" and t.get("crop") in CROPS:c[t["crop"]]+=1
     elif t.get("kind")=="WEED":c["WEED"]+=1
     if t.get("kind") in ("PASTURE","COOP"):c[t["kind"]]+=1
     if t.get("animal") in ANIMALS:c[t["animal"]]+=1
  return c
 def _target_hands(self,day):
  if day==0:return 5
  if day<7:return 3
  if day<11:return 8
  if day>=28:return 10
  return 13
 def _animal_targets(self,obs,day):
  if day<7:return {"COW":2,"SHEEP":2,"GOOSE":0}
  if day<11:return {"COW":6,"SHEEP":4,"GOOSE":0}
  return {"COW":8,"SHEEP":6,"GOOSE":0}
 def _crop_targets(self,obs,counts,day):
  p=int(obs.get("player",0));q=len(obs["farms"][p].get("unlocked_quadrants",["NW"]));a=self._animal_targets(obs,day)
  slots=max(0,25*q-a["COW"]-a["SHEEP"]-a["GOOSE"])
  if q==1:w,m=7,11
  elif day>=18:w,m=19,0
  else:w,m=7,12
  w=min(w,slots);m=min(m,max(0,slots-w))
  return {"WHEAT":w,"MELON":m,"STRAWBERRY":max(0,slots-w-m),"CARROT":0,"TOMATO":0}
 def _sell_orders(self,obs,counts):
  pr=obs.get("private",{}) or {};shed=pr.get("shed",{}) or {};m=obs.get("market",{}) or {};inv=m.get("inventory",{}) or {}
  step=int(obs.get("step",int(obs.get("day",0))*24+int(obs.get("hour",0))));rem=718-step;hard=rem<=self.cfg.terminal_hard
  load=sum(int(v or 0) for v in shed.values());animals=counts["COW"]+counts["SHEEP"]+counts["GOOSE"]
  hold_w=0 if hard else min(int(shed.get("WHEAT",0)),max(8,2*animals))
  rf={"WHEAT":.52,"CARROT":.48,"TOMATO":.50,"STRAWBERRY":.52,"MELON":.78,"EGG":.48,"MILK":.52,"WOOL":.55,"FERTILIZER":.32}
  out=[]
  for item in ["STRAWBERRY","MILK","WOOL","MELON","CARROT","TOMATO","EGG","FERTILIZER","WHEAT"]:
   q=int(shed.get(item,0))-(hold_w if item=="WHEAT" else 0)
   if q<=0:continue
   if hard:n=q
   else:
    frac=rf[item]
    if load>=self.cfg.shed_hard:frac=.05
    elif load>=self.cfg.shed_soft:frac*=.6
    n=min(q,sellable_above(item,int(inv.get(item,10000)),max(1,int(BASE[item]*frac))))
    if load>=self.cfg.shed_hard and n<=0:n=q
   if n>0:out.append(["SELL",item,n])
  return out
 def _market(self,obs,c):
  p=int(obs.get("player",0));farm=obs["farms"][p];priv=obs.get("private",{}) or {};shed=priv.get("shed",{}) or {};seeds=priv.get("seeds",{}) or {}
  day=int(obs.get("day",0));hour=int(obs.get("hour",0));money=float(farm.get("money",0));q=len(farm.get("unlocked_quadrants",["NW"]));out=[]
  out.extend(self._sell_orders(obs,c))
  if len(out)>=10:return out[:10]
  target=self._target_hands(day)
  hires=int(farm.get("hires_today",0));have=len(farm.get("hands",[]) or [])
  for _ in range(max(0,target-have)):
   if len(out)>=10:break
   cost=FIB[min(hires,len(FIB)-1)]
   if money-cost<self.cfg.cash_floor:break
   out.append(["HIRE"]);money-=cost;hires+=1
  land_days=(7,11)
  if q<self.cfg.max_land and q-1<len(land_days) and day>=land_days[q-1] and len(out)<10:
   price=LAND_PRICES[q-1]
   if money-price>=self.cfg.cash_floor+500:out.append(["BUY_LAND"]);money-=price;q+=1
  at=self._animal_targets(obs,day)
  animals=sum(c[a] for a in ANIMALS);feed=max(10,2*animals)
  need=max(0,feed-int(shed.get("WHEAT",0)))
  if need and len(out)<10 and money>self.cfg.cash_floor:
   n=min(need,30);out.append(["BUY_PRODUCT","WHEAT",n])
  if day<22:
   for a in ("COW","SHEEP","GOOSE"):
    total=c[a]+int(shed.get(a,0));need=max(0,at[a]-total)
    if need and len(out)<10 and money-ANIMALS[a]["cost"]>=self.cfg.cash_floor:
     n=min(need,2);out.append(["BUY_ANIMAL",a,n]);money-=ANIMALS[a]["cost"]*n
  tg=self._crop_targets(obs,c,day)
  for crop in ("STRAWBERRY","MELON","WHEAT","CARROT","TOMATO"):
   if len(out)>=10:break
   deficit=max(0,tg.get(crop,0)-c.get(crop,0)-int(seeds.get(crop,0)))
   if deficit and day+CROPS[crop]["first"]<30:
    n=min(deficit,12);cost=CROPS[crop]["seed"]*n
    if money-cost>=self.cfg.cash_floor:out.append(["BUY_SEED",crop,n]);money-=cost
  return out[:10]
 def _tasks(self,obs,c):
  p=int(obs.get("player",0));farm=obs["farms"][p];day=int(obs.get("day",0));hour=int(obs.get("hour",0));step=int(obs.get("step",day*24+hour));rem=718-step
  tg=self._crop_targets(obs,c,day);at=self._animal_targets(obs,day);tasks=[]
  for y,row in enumerate(farm.get("tiles",[]) or []):
   for x,t in enumerate(row):
    pos=(x,y)
    if t is None:
     need_p=max(0,at["COW"]+at["SHEEP"]-c["PASTURE"])
     need_c=max(0,at["GOOSE"]-c["COOP"])
     if need_p:tasks.append((82,pos,["BUILD_PASTURE"],None,"build"));continue
     if need_c:tasks.append((80,pos,["BUILD_COOP"],None,"build"));continue
     for crop in ("STRAWBERRY","MELON","WHEAT","CARROT","TOMATO"):
      if c[crop]<tg.get(crop,0) and day+CROPS[crop]["first"]<30:
       tasks.append((72,pos,["PLANT",crop],None,f"plant:{crop}"));break
     continue
    if not isinstance(t,dict):continue
    if t.get("kind")=="WEED":tasks.append((60,pos,["DIG"],None,"dig"));continue
    if t.get("kind")=="PLANT":
     crop=t.get("crop");cd=CROPS.get(crop);age=day-int(t.get("planted_day",day));yl=int(t.get("yield_units",0))
     if cd and yl>0 and age>=cd["first"]:
      ready=cd["ongoing"] or age>=cd["maxday"] or yl>=cd["max_yield"] or rem<48
      if ready:tasks.append((112,pos,["HARVEST"],None,"harvest"))
     if not t.get("watered_today",False):
      dry=int(t.get("consecutive_unwatered",0));urg=126 if dry>=1 else 88
      if age==0:urg=130
      tasks.append((urg,pos,["WATER"],None,"water"))
     if crop=="STRAWBERRY" and age>=7 and int(t.get("fertilized_until_day",-1))<=day+1:
      tasks.append((70,pos,["FERTILIZE"],"FERTILIZER","fert"))
     continue
    if "animal" in t:
     if not t.get("fed_today",False):tasks.append((124 if int(t.get("consecutive_unfed",0))>=1 else 98,pos,["FEED"],"WHEAT","feed"))
     if int(t.get("yield_units",0))>0:tasks.append((116,pos,["HARVEST"],None,"animal_harvest"))
     if t.get("fertilizer_available",False):tasks.append((84,pos,["COLLECT_FERTILIZER"],None,"collect"))
     if not t.get("cared_today",False):tasks.append((76,pos,["CARE"],None,"care"))
  return tasks
 def _unit(self,pos,inv,obs,tasks,claimed):
  p=int(obs.get("player",0));farm=obs["farms"][p];priv=obs.get("private",{}) or {};shed=priv.get("shed",{}) or {};day=int(obs.get("day",0));hour=int(obs.get("hour",0));step=int(obs.get("step",day*24+hour));rem=718-step
  pos=tuple(pos);inv=inv or {};carrying=sum(int(v or 0) for v in inv.values());nearest=min(SHED,key=lambda s:self.dist(pos,s));ds=self.dist(pos,nearest)
  haul=sum(int(v or 0) for k,v in inv.items() if k in PRODUCTS and k not in ("WHEAT","FERTILIZER"))
  if carrying and (rem<=ds+4 or (day>=29 and hour>=15) or haul>=8 or (hour>=20 and haul)):
   return ["DROP"] if pos in SHED else self.move(pos,nearest)
  for a in ("COW","SHEEP","GOOSE"):
   if int(inv.get(a,0))>0:
    candidates=[]
    for y,row in enumerate(farm.get("tiles",[]) or []):
     for x,t in enumerate(row):
      if isinstance(t,dict) and t.get("kind")==ANIMALS[a]["structure"] and "animal" not in t:candidates.append((x,y))
    if candidates:
     trg=min(candidates,key=lambda z:self.dist(pos,z));return ["PLACE",a] if pos==trg else self.move(pos,trg)
  feed=sum(1 for t in tasks if t[4]=="feed");fert=sum(1 for t in tasks if t[4]=="fert")
  if pos in SHED and not int(inv.get("WHEAT",0)) and feed and int(shed.get("WHEAT",0))>0:
   loaders=sum(1 for _,tag in claimed if str(tag).startswith("feed_loader"));target=min(4,max(1,math.ceil(feed/5)))
   if loaders<target:claimed.add((pos,f"feed_loader:{loaders}"));return ["PICKUP","WHEAT",min(8,int(shed.get("WHEAT",0)))]
  if pos in SHED and not int(inv.get("FERTILIZER",0)) and fert and int(shed.get("FERTILIZER",0))>0:
   loaders=sum(1 for _,tag in claimed if str(tag).startswith("fert_loader"))
   if loaders<2:claimed.add((pos,f"fert_loader:{loaders}"));return ["PICKUP","FERTILIZER",min(8,int(shed.get("FERTILIZER",0)))]
  if pos in SHED and carrying==0:
   for a in ("COW","SHEEP","GOOSE"):
    if int(shed.get(a,0))>0:return ["PICKUP",a,1]
  best=None;bestscore=-1e18
  for pri,trg,act,need,tag in tasks:
   key=(trg,tag)
   if key in claimed:continue
   if need and int(inv.get(need,0))<=0:continue
   d=self.dist(pos,trg);score=pri-4*d+(28 if d==0 else 0)
   if int(inv.get("WHEAT",0))>0 and tag=="feed":score+=20
   if int(inv.get("FERTILIZER",0))>0 and tag=="fert":score+=20
   if score>bestscore:bestscore=score;best=(trg,act,tag)
  if best:
   trg,act,tag=best;claimed.add((trg,tag));return act if pos==trg else self.move(pos,trg)
  if carrying and hour>=21:return ["DROP"] if pos in SHED else self.move(pos,nearest)
  return ["PASS"]
 def act(self,obs):
  try:
   p=int(obs.get("player",0));farms=obs.get("farms",[]) or []
   if p>=len(farms):return {"farmer":["PASS"],"hands":[],"market":[]}
   farm=farms[p];priv=obs.get("private",{}) or {};c=self._counts(farm);market=self._market(obs,c);tasks=self._tasks(obs,c)
   positions=[farm.get("farmer",[4,4]),*(farm.get("hands",[]) or [])];invs=priv.get("inventories",[]) or [{}];claimed=set();acts=[]
   for i,pos in enumerate(positions):
    inv=invs[i] if i<len(invs) and isinstance(invs[i],dict) else {}
    acts.append(self._unit(pos,inv,obs,tasks,claimed))
   return {"farmer":acts[0] if acts else ["PASS"],"hands":acts[1:1+len(farm.get("hands",[]) or [])],"market":market}
  except Exception:
   farms=obs.get("farms",[]) or [];p=int(obs.get("player",0));farm=farms[p] if p<len(farms) else {}
   return {"farmer":["PASS"],"hands":[["PASS"] for _ in farm.get("hands",[])],"market":[]}

_POLICY=HarvestMind()
def agent(obs,configuration=None):return _POLICY.act(obs)
