"""Dependency-free Kaggriculture simulator mirroring the public Kaggle environment.

It is intentionally kept close to the official interpreter semantics so strategy changes can
be regression-tested without requiring kaggle-environments to be installed.
"""
from __future__ import annotations
import math, random, copy
from submission.base_controller import CROPS as _HCROPS, ANIMALS as _HANIMALS, PRODUCTS, BASE as BASE_PRICE, FIB as FIB_HIRE

CROPS={k:{"seed":v["seed"],"first":v["first"],"max_day":v["maxday"],"interval":v["interval"],
          "max_yield":v["max_yield"],"ongoing":v["ongoing"]} for k,v in _HCROPS.items()}
ANIMALS={k:{"cost":v["cost"],"structure":v["structure"],"first":v["first"],"interval":v["interval"],
            "cap":v["cap"],"product":v["product"]} for k,v in _HANIMALS.items()}
LAND_ORDER=["NE","SW","SE"]
LAND_PRICES=[1000,2000,4000]

MARKET_I0=10000; PRICE_FLOOR=1; HINGE_GAIN=8.0
MARKET_PARAMS={
"WHEAT":{"base":25,"T":400,"below_func":"sqrt","below_target":.80,"above_func":"log","above_target":.20},
"CARROT":{"base":35,"T":450,"below_func":"hinge","below_target":1.00,"above_func":"sqrt","above_target":.70},
"TOMATO":{"base":60,"T":200,"below_func":"hinge","below_target":.40,"above_func":"sqrt","above_target":.60},
"STRAWBERRY":{"base":120,"T":100,"below_func":"sqrt","below_target":.70,"above_func":"linear","above_target":1.60},
"MELON":{"base":250,"T":300,"below_func":"log","below_target":.20,"above_func":"sq","above_target":3.60},
"EGG":{"base":50,"T":332,"below_func":"hinge","below_target":.40,"above_func":"log","above_target":.20},
"MILK":{"base":160,"T":122,"below_func":"sqrt","below_target":.60,"above_func":"linear","above_target":1.60},
"WOOL":{"base":200,"T":105,"below_func":"log","below_target":.20,"above_func":"sq","above_target":3.20},
"FERTILIZER":{"base":100,"T":200,"below_func":"linear","below_target":.40,"above_func":"linear","above_target":.40},
}
SHOPS={
"BAKERY":["EGG","WHEAT"],"PIZZA_SHOP":["MILK","TOMATO","WHEAT"],"BRUNCH_SPOT":["EGG","WHEAT","STRAWBERRY"],
"YARN_STORE":["WOOL"],"ICE_CREAM_SHOP":["STRAWBERRY","MILK","WHEAT"],"PET_CAFE":["CARROT"],
"SMOOTHIE_SHOP":["STRAWBERRY","MILK"],"FARMERS_MARKET":["WHEAT","CARROT","TOMATO","STRAWBERRY"]}
TOWN_CENTER=[p for p in PRODUCTS if p!="FERTILIZER"]
MOVES={"NORTH":(0,-1),"SOUTH":(0,1),"EAST":(1,0),"WEST":(-1,0)}

def _shape(f,x,T):
    x=max(0.0,x)
    if f=="linear": return x
    if f=="sq": return x*x
    if f=="sqrt": return math.sqrt(x)
    if f=="log": return math.log1p(x)
    if f=="log10": return math.log10(1+x)
    if f=="hinge":
        u=x/T if T else x
        return u+HINGE_GAIN*max(0,u-1)**2
    return x

def market_price(item,inv):
    p=MARKET_PARAMS[item]; base=p["base"]; T=p["T"]
    if inv<MARKET_I0:
        f=p["below_func"]; amp=p["below_target"]*base/_shape(f,T,T); price=base+amp*_shape(f,MARKET_I0-inv,T)
    else:
        f=p["above_func"]; amp=p["above_target"]*base/_shape(f,T,T); price=base-amp*_shape(f,inv-MARKET_I0,T)
    return max(1,int(round(price)))

def quadrant(x,y,n=10): return ("N" if y<n//2 else "S")+("W" if x<n//2 else "E")
def shed_tiles(n=10):
    h=n//2; return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]
def default_spawn(n=10): return list(shed_tiles(n)[0])

def new_farm(n=10,money=3000):
    tiles=[[None if quadrant(x,y,n)=="NW" else "LOCKED" for x in range(n)] for y in range(n)]
    return {"money":float(money),"tiles":tiles,"farmer":default_spawn(n),"hands":[],"unlocked_quadrants":["NW"],"hires_today":0}
def new_private():
    return {"shed":{item:0 for item in PRODUCTS+list(ANIMALS)},"seeds":{c:0 for c in CROPS},"inventories":[{}]}

def new_plant(crop,day,tpd=24):
    cd=CROPS[crop]
    return {"kind":"PLANT","crop":crop,"planted_day":day,"watered_today":False,"consecutive_unwatered":1,
            "yield_units":0 if cd["ongoing"] else 1,
            "max_lifespan_step":-1 if cd["ongoing"] else (day+cd["max_day"]+1)*tpd,"fertilized_until_day":-1}
def new_animal(a,day):
    d=ANIMALS[a]
    return {"kind":d["structure"],"animal":a,"placed_day":day,"yield_units":0,"consecutive_unfed":0,
            "fed_today":False,"cared_today":False,"fertilizer_available":False,"pending_care_bonus":0}

def inv_add(inv,item,n=1): inv[item]=inv.get(item,0)+n
def inv_take(inv,item,n=1):
    if inv.get(item,0)<n: return False
    inv[item]-=n
    if inv[item]==0: del inv[item]
    return True

class Game:
    def __init__(self, seed=0, episode_steps=720, board_size=10, weed_chance=.005):
        self.seed=seed; self.episode_steps=episode_steps; self.board_size=board_size; self.weed_chance=weed_chance; self.tpd=24
        self.farms=[new_farm(board_size),new_farm(board_size)]; self.priv=[new_private(),new_private()]
        self.market={"inventory":{p:MARKET_I0 for p in PRODUCTS},"prices":{p:BASE_PRICE[p] for p in PRODUCTS}}
        self.town={"unlocked_shops":[]}; self.step=0; self.day=0; self.hour=0

    def obs(self,p):
        return {"player":p,"step":self.step,"day":self.day,"hour":self.hour,"farms":copy.deepcopy(self.farms),
                "private":copy.deepcopy(self.priv[p]),"market":copy.deepcopy(self.market),"town":copy.deepcopy(self.town)}

    def _unit_pos(self,f,idx): return f["farmer"] if idx==0 else (f["hands"][idx-1] if idx-1<len(f["hands"]) else None)
    def _set_pos(self,f,idx,pos):
        if idx==0:f["farmer"]=list(pos)
        else:f["hands"][idx-1]=list(pos)
    def _uinv(self,p,idx):
        while len(self.priv[p]["inventories"])<=idx:self.priv[p]["inventories"].append({})
        return self.priv[p]["inventories"][idx]

    def _apply_unit(self,p,idx,a):
        f=self.farms[p]; pr=self.priv[p]; pos=self._unit_pos(f,idx)
        if pos is None or not isinstance(a,list) or not a:return
        op=a[0]; x,y=pos; inv=self._uinv(p,idx); n=self.board_size
        if op in MOVES:
            dx,dy=MOVES[op]; nx,ny=x+dx,y+dy
            if 0<=nx<n and 0<=ny<n:self._set_pos(f,idx,(nx,ny))
            return
        if op=="PASS":return
        tile=f["tiles"][y][x]
        is_shed=(x,y) in set(shed_tiles(n))
        if op=="DROP":
            if not is_shed:return
            shed=pr["shed"]
            for item,q in list(inv.items()):
                room=max(0,100-sum(shed.values())); take=min(q,room)
                if take:shed[item]=shed.get(item,0)+take
                del inv[item]
            return
        if op=="PICKUP":
            if not is_shed or len(a)<2:return
            item=a[1]; q=int(a[2]) if len(a)>=3 else 1; q=min(q,pr["shed"].get(item,0))
            if q>0:pr["shed"][item]-=q; inv_add(inv,item,q)
            return
        if op=="PLACE":
            if len(a)<2:return
            item=a[1]
            if item in ANIMALS and isinstance(tile,dict) and tile.get("kind")==ANIMALS[item]["structure"] and "animal" not in tile:
                if inv_take(inv,item,1):f["tiles"][y][x]=new_animal(item,self.day)
                return
            if is_shed:
                q=int(a[2]) if len(a)>=3 else 1; q=min(q,inv.get(item,0),max(0,100-sum(pr["shed"].values())))
                if q>0:
                    inv[item]-=q
                    if inv[item]==0:del inv[item]
                    pr["shed"][item]=pr["shed"].get(item,0)+q
            return
        if tile=="LOCKED":return
        if op=="PLANT":
            if len(a)>=2 and a[1] in CROPS and tile is None and pr["seeds"].get(a[1],0)>0:
                pr["seeds"][a[1]]-=1; f["tiles"][y][x]=new_plant(a[1],self.day,self.tpd)
            return
        if op=="WATER":
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and not tile["watered_today"]:
                tile["watered_today"]=True; cd=CROPS[tile["crop"]]
                if not cd["ongoing"]:
                    age=self.day-tile["planted_day"]; ws=(cd["max_day"]+1)//2
                    if ws<=age<=cd["max_day"]:
                        b=2 if tile.get("fertilized_until_day",-1)>=self.day else 1
                        tile["yield_units"]=min(cd["max_yield"],tile["yield_units"]+b)
            return
        if op=="HARVEST":
            if not isinstance(tile,dict) or tile.get("yield_units",0)<=0:return
            if tile.get("kind")=="PLANT":
                cd=CROPS[tile["crop"]]
                if self.day-tile["planted_day"]<cd["first"]:return
                q=tile["yield_units"]; inv_add(inv,tile["crop"],q); tile["yield_units"]=0
                if not cd["ongoing"]:f["tiles"][y][x]=None
            elif "animal" in tile:
                q=tile["yield_units"]; inv_add(inv,ANIMALS[tile["animal"]]["product"],q); tile["yield_units"]=0
            return
        if op=="FERTILIZE":
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and inv_take(inv,"FERTILIZER",1):tile["fertilized_until_day"]=max(tile.get("fertilized_until_day",-1),self.day+2)
            return
        if op=="DIG":
            if tile is not None and not (isinstance(tile,dict) and "animal" in tile):f["tiles"][y][x]=None
            return
        if op=="BUILD_COOP":
            if tile is None:f["tiles"][y][x]={"kind":"COOP"}
            return
        if op=="BUILD_PASTURE":
            if tile is None:f["tiles"][y][x]={"kind":"PASTURE"}
            return
        if op=="FEED":
            if isinstance(tile,dict) and "animal" in tile and not tile["fed_today"] and inv_take(inv,"WHEAT",1):tile["fed_today"]=True
            return
        if op=="COLLECT_FERTILIZER":
            if isinstance(tile,dict) and "animal" in tile and tile.get("fertilizer_available",False):tile["fertilizer_available"]=False; inv_add(inv,"FERTILIZER",1)
            return
        if op=="CARE":
            if isinstance(tile,dict) and "animal" in tile and not tile["cared_today"]:tile["cared_today"]=True
            return

    def _refresh_prices(self):
        for p in PRODUCTS:self.market["prices"][p]=market_price(p,self.market["inventory"][p])

    def _market(self,actions):
        qs=[]
        for a in actions:
            m=a.get("market",[]) if isinstance(a,dict) else []
            qs.append(list(m)[:10] if isinstance(m,list) else [])
        maxlen=max(map(len,qs),default=0)
        for i in range(maxlen):
            states=[]
            for p in range(2):
                if i>=len(qs[p]) or not isinstance(qs[p][i],list) or not qs[p][i]:states.append(None);continue
                o=qs[p][i]; op=o[0]
                if op in ("HIRE","BUY_LAND"):states.append({"type":op});continue
                if op in ("BUY_SEED","BUY_PRODUCT","BUY_ANIMAL","SELL") and len(o)>=3:
                    try:q=int(o[2])
                    except:q=0
                    states.append({"type":op,"item":o[1],"rem":q} if q>0 else None)
                else:states.append(None)
            for p,s in enumerate(states):
                if not s:continue
                if s["type"]=="HIRE":
                    f=self.farms[p]; cost=FIB_HIRE[min(f["hires_today"],len(FIB_HIRE)-1)]
                    if f["money"]>=cost:
                        f["money"]-=cost; f["hires_today"]+=1
                        occ={tuple(z):0 for z in shed_tiles(self.board_size)}
                        for z in [f["farmer"],*f["hands"]]:
                            if tuple(z) in occ:occ[tuple(z)]+=1
                        best=min(occ,key=lambda z:(occ[z],shed_tiles(self.board_size).index(z)))
                        f["hands"].append(list(best)); self.priv[p]["inventories"].append({})
                    states[p]=None
                elif s["type"]=="BUY_LAND":
                    f=self.farms[p]; k=len(f["unlocked_quadrants"])-1
                    if k<3 and f["money"]>=LAND_PRICES[k]:
                        f["money"]-=LAND_PRICES[k]; q=LAND_ORDER[k]; f["unlocked_quadrants"].append(q)
                        for y in range(self.board_size):
                            for x in range(self.board_size):
                                if quadrant(x,y,self.board_size)==q and f["tiles"][y][x]=="LOCKED":f["tiles"][y][x]=None
                    states[p]=None
            while True:
                quoted=[None,None]
                for p,s in enumerate(states):
                    if not s or s.get("rem",0)<=0:continue
                    op=s["type"]; item=s.get("item")
                    if op=="SELL" and item in PRODUCTS:quoted[p]=(op,item,market_price(item,self.market["inventory"][item]),s)
                    elif op=="BUY_PRODUCT" and item in ("WHEAT","FERTILIZER"):quoted[p]=(op,item,market_price(item,self.market["inventory"][item]-1),s)
                    elif op=="BUY_SEED" and item in CROPS:quoted[p]=(op,item,CROPS[item]["seed"],s)
                    elif op=="BUY_ANIMAL" and item in ANIMALS:quoted[p]=(op,item,ANIMALS[item]["cost"],s)
                    else:states[p]=None
                if all(q is None for q in quoted):break
                anyok=False
                for p,q in enumerate(quoted):
                    if q is None:continue
                    op,item,price,s=q; f=self.farms[p]; pr=self.priv[p]; ok=False
                    if op=="SELL" and pr["shed"].get(item,0)>0:
                        pr["shed"][item]-=1;f["money"]+=price
                        if price>1:self.market["inventory"][item]+=1
                        ok=True
                    elif op=="BUY_PRODUCT" and f["money"]>=price and sum(pr["shed"].values())<100:
                        f["money"]-=price;pr["shed"][item]+=1;self.market["inventory"][item]-=1;ok=True
                    elif op=="BUY_SEED" and f["money"]>=price:
                        f["money"]-=price;pr["seeds"][item]+=1;ok=True
                    elif op=="BUY_ANIMAL" and f["money"]>=price and sum(pr["shed"].values())<100:
                        f["money"]-=price;pr["shed"][item]+=1;ok=True
                    if ok:s["rem"]-=1;anyok=True
                    else:states[p]=None
                if not anyok:break
            self._refresh_prices()

    def _town_consume(self):
        if self.step%4==0:
            for shop in self.town["unlocked_shops"]:
                ps=SHOPS[shop]; mult=2 if len(ps)==1 else 1
                for item in ps:self.market["inventory"][item]-=mult
        if self.step%24==0:
            for item in TOWN_CENTER:self.market["inventory"][item]-=1
        self._refresh_prices()

    def _decay(self):
        for f in self.farms:
            for y,row in enumerate(f["tiles"]):
                for x,t in enumerate(row):
                    if isinstance(t,dict) and t.get("kind")=="PLANT":
                        m=t.get("max_lifespan_step",-1)
                        if m>=0 and self.step>=m and (self.step-m)%2==0:
                            t["yield_units"]-=1
                            if t["yield_units"]<=0:f["tiles"][y][x]={"kind":"WEED"}

    def _eod(self):
        rng=random.Random((self.seed*1_000_003)^self.day); next_day=self.day+1
        for p,f in enumerate(self.farms):
            for y,row in enumerate(f["tiles"]):
                for x,t in enumerate(row):
                    if isinstance(t,dict) and t.get("kind")=="PLANT":
                        watered=t["watered_today"]; t["consecutive_unwatered"]=0 if watered else t["consecutive_unwatered"]+1; t["watered_today"]=False
                        if t["consecutive_unwatered"]>=2:f["tiles"][y][x]={"kind":"WEED"};continue
                        cd=CROPS[t["crop"]]
                        if cd["ongoing"]:
                            ds=next_day-t["planted_day"]-cd["first"]
                            if ds>=0 and ds%cd["interval"]==0:
                                pc=ds//cd["interval"]+1
                                if pc<=cd["max_yield"]:
                                    fert=watered and t.get("fertilized_until_day",-1)>=self.day
                                    t["yield_units"]=min(cd["max_yield"],t["yield_units"]+(2 if fert else 1))
                                    if pc==cd["max_yield"]:t["max_lifespan_step"]=(next_day+1)*self.tpd
                    elif isinstance(t,dict) and "animal" in t:
                        if t["fed_today"]:t["consecutive_unfed"]=0
                        else:t["consecutive_unfed"]+=1
                        if t["consecutive_unfed"]>=2:f["tiles"][y][x]={"kind":ANIMALS[t["animal"]]["structure"]};continue
                        a=ANIMALS[t["animal"]]; ds=next_day-t["placed_day"]-a["first"]
                        if ds>=0 and ds%a["interval"]==0:
                            bonus=t.pop("pending_care_bonus",0) if t["fed_today"] else 0
                            t["yield_units"]=min(a["cap"],t["yield_units"]+1+bonus); t["pending_care_bonus"]=0
                        if t["cared_today"] and t["fed_today"]:t["pending_care_bonus"]=t.get("pending_care_bonus",0)+1
                        t["fertilizer_available"]=True;t["fed_today"]=False;t["cared_today"]=False
            for y,row in enumerate(f["tiles"]):
                for x,t in enumerate(row):
                    if t is None and rng.random()<self.weed_chance:f["tiles"][y][x]={"kind":"WEED"}
            shed=self.priv[p]["shed"]
            for inv in self.priv[p]["inventories"]:
                for item,q in list(inv.items()):
                    room=max(0,100-sum(shed.values()));take=min(q,room)
                    if take:shed[item]=shed.get(item,0)+take
                    del inv[item]
            f["farmer"]=default_spawn(self.board_size);f["hands"]=[];f["hires_today"]=0;self.priv[p]["inventories"]=[{}]
        if next_day>0 and next_day%3==0 and len(self.town["unlocked_shops"])<8:
            self.town["unlocked_shops"].append(rng.choice(sorted(SHOPS)))

    def step_once(self, actions):
        for p,a in enumerate(actions):
            a=a if isinstance(a,dict) else {}; fa=a.get("farmer",["PASS"]); ha=a.get("hands",[]) if isinstance(a.get("hands",[]),list) else []
            allacts=[fa,*ha]; dem={}
            for u in allacts:
                if isinstance(u,list) and len(u)>=2 and u[0]=="PLANT":dem[u[1]]=dem.get(u[1],0)+1
            blocked={c for c,n in dem.items() if n>self.priv[p]["seeds"].get(c,0)}
            def ok(u):return ["PASS"] if isinstance(u,list) and len(u)>=2 and u[0]=="PLANT" and u[1] in blocked else u
            self._apply_unit(p,0,ok(fa))
            for i,u in enumerate(ha):self._apply_unit(p,i+1,ok(u))
        self._market(actions);self._town_consume();self._decay()
        if (self.step+1)%24==0:self._eod()
        self.step+=1;self.day=self.step//24;self.hour=self.step%24

    def run(self, agents):
        for _ in range(self.episode_steps-1):
            acts=[agents[p](self.obs(p)) for p in range(2)]
            self.step_once(acts)
        return [f["money"] for f in self.farms]

    def summary(self):
        return {"step":self.step,"money":[f["money"] for f in self.farms],"shops":self.town["unlocked_shops"],"prices":dict(self.market["prices"])}
