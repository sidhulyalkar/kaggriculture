from __future__ import annotations

NONBUYABLE_PRODUCTS=frozenset({"CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL"})
SHOP_PRODUCTS={
 "BAKERY":("EGG","WHEAT"),"PIZZA_SHOP":("MILK","TOMATO","WHEAT"),"BRUNCH_SPOT":("EGG","WHEAT","STRAWBERRY"),
 "YARN_STORE":("WOOL",),"ICE_CREAM_SHOP":("STRAWBERRY","MILK","WHEAT"),"PET_CAFE":("CARROT",),
 "SMOOTHIE_SHOP":("STRAWBERRY","MILK"),"FARMERS_MARKET":("WHEAT","CARROT","TOMATO","STRAWBERRY"),
}
SHED_ACCESS=frozenset({(4,4),(5,4),(4,5),(5,5)})


def canonical_step(obs):
 raw=(obs or {}).get("step")
 if raw is not None:
  try:return int(raw)
  except Exception:pass
 return int((obs or {}).get("day",0) or 0)*24+int((obs or {}).get("hour",0) or 0)


def town_drain_for_turn(step,shops,product):
 drain=0
 if int(step)%4==0:
  for shop in shops or ():
   products=SHOP_PRODUCTS.get(str(shop),())
   if product in products:drain+=2 if len(products)==1 else 1
 if product!="FERTILIZER" and int(step)%24==0:drain+=1
 return drain


def _inventory(raw):
 out={}
 if not isinstance(raw,dict):return out
 for k,v in raw.items():
  try:out[str(k)]=max(0,int(v or 0))
  except Exception:pass
 return out


def _positions(obs):
 farms=list((obs or {}).get("farms",[]) or []);p=int((obs or {}).get("player",0) or 0);farm=farms[p] if 0<=p<len(farms) else {}
 f=farm.get("farmer");out=[tuple(map(int,f[:2])) if isinstance(f,(list,tuple)) and len(f)>=2 else None]
 for pos in list(farm.get("hands",[]) or []):out.append(tuple(map(int,pos[:2])) if isinstance(pos,(list,tuple)) and len(pos)>=2 else None)
 return out


def _actions(action,n):
 action=action if isinstance(action,dict) else {};out=[action.get("farmer",["PASS"])]
 if isinstance(action.get("hands"),list):out.extend(action["hands"])
 out.extend([["PASS"]]*max(0,n-len(out)));return out[:n]


def post_physical_shed(obs,action):
 private=(obs or {}).get("private",{}) or {};shed=_inventory(private.get("shed",{}) or {});invs=[_inventory(x) for x in list(private.get("inventories",[]) or [])]
 pos=_positions(obs);invs.extend({} for _ in range(max(0,len(pos)-len(invs))))
 def room():return max(0,100-sum(shed.values()))
 for i,(xy,a) in enumerate(zip(pos,_actions(action,len(pos)))):
  if xy not in SHED_ACCESS or not isinstance(a,(list,tuple)) or not a:continue
  op=str(a[0]);inv=invs[i]
  if op=="DROP":
   for item,q in list(inv.items()):
    take=min(max(0,int(q)),room())
    if take:shed[item]=shed.get(item,0)+take
    inv.pop(item,None)
  elif op=="PLACE" and len(a)>=2:
   item=str(a[1]);req=int(a[2]) if len(a)>=3 else 1;take=min(max(0,req),inv.get(item,0),room())
   if take:inv[item]-=take;shed[item]=shed.get(item,0)+take
  elif op=="PICKUP" and len(a)>=2:
   item=str(a[1]);req=int(a[2]) if len(a)>=3 else 1;take=min(max(0,req),shed.get(item,0))
   if take:shed[item]-=take;inv[item]=inv.get(item,0)+take
 return shed


def requested_sell(action,product):
 if not isinstance(action,dict):return 0
 total=0
 for order in list(action.get("market",[]) or [])[:10]:
  if isinstance(order,(list,tuple)) and len(order)>=3 and str(order[0])=="SELL" and str(order[1])==str(product):
   try:total+=max(0,int(order[2]))
   except Exception:pass
 return total


def executed_own_sell(obs,action,product):
 return min(requested_sell(action,product),int(post_physical_shed(obs,action).get(str(product),0) or 0))


def infer_external_supply(prev_obs,curr_obs,own_previous_action,product):
 product=str(product)
 if product not in NONBUYABLE_PRODUCTS:return None
 pm=(prev_obs or {}).get("market",{}) or {};cm=(curr_obs or {}).get("market",{}) or {}
 pi=int((pm.get("inventory",{}) or {}).get(product,10000) or 10000);ci=int((cm.get("inventory",{}) or {}).get(product,10000) or 10000)
 pp=int((pm.get("prices",{}) or {}).get(product,1) or 1);cp=int((cm.get("prices",{}) or {}).get(product,1) or 1)
 if pp<=1 or cp<=1:return None
 shops=list((((prev_obs or {}).get("town",{}) or {}).get("unlocked_shops",[]) or []))
 external=ci-pi+town_drain_for_turn(canonical_step(prev_obs),shops,product)-executed_own_sell(prev_obs,own_previous_action,product)
 return max(0,int(external))
