from __future__ import annotations
try:
    from .base_controller import HarvestMind,BASE,PRODUCTS,sellable_above
except Exception:
    from base_controller import HarvestMind,BASE,PRODUCTS,sellable_above

DEFAULT_PARAMS={
 "hands_early":3,"hands_mid":8,"hands_late":13,"cow_mid":6,"sheep_mid":4,"cow_late":8,"sheep_late":6,
 "q1_wheat":7,"q1_melon":11,"mid_wheat":7,"mid_melon":12,"late_wheat":19,
 "reserve_strawberry":.52,"reserve_melon":.78,"reserve_milk":.52,"reserve_wool":.55,"reserve_fertilizer":.32,"terminal_start":26,
}
class ParametricMind(HarvestMind):
    def __init__(self,params=None,*a,**kw):
        super().__init__(*a,**kw);self.params=dict(DEFAULT_PARAMS);self.params.update(params or {});self.cfg.terminal_start=int(self.params["terminal_start"])
    def _target_hands(self,day):
        if day==0:return 5
        if day<7:return int(self.params["hands_early"])
        if day<11:return int(self.params["hands_mid"])
        if day>=28:return 10
        return int(self.params["hands_late"])
    def _animal_targets(self,obs,day):
        if day<7:return {"COW":2,"SHEEP":2,"GOOSE":0}
        if day<11:return {"COW":int(self.params["cow_mid"]),"SHEEP":int(self.params["sheep_mid"]),"GOOSE":0}
        return {"COW":int(self.params["cow_late"]),"SHEEP":int(self.params["sheep_late"]),"GOOSE":0}
    def _crop_targets(self,obs,counts,day):
        me=int(obs.get("player",0));q=len(obs["farms"][me].get("unlocked_quadrants",["NW"]));at=self._animal_targets(obs,day);slots=max(0,25*q-at["COW"]-at["SHEEP"])
        if q==1:
            w=min(slots,int(self.params["q1_wheat"]));m=min(max(0,slots-w),int(self.params["q1_melon"]));return {"WHEAT":w,"MELON":m,"STRAWBERRY":max(0,slots-w-m),"CARROT":0,"TOMATO":0}
        if day>=18:
            w=min(slots,int(self.params["late_wheat"]));return {"WHEAT":w,"MELON":0,"STRAWBERRY":max(0,slots-w),"CARROT":0,"TOMATO":0}
        w=min(slots,int(self.params["mid_wheat"]));m=min(max(0,slots-w),int(self.params["mid_melon"]));return {"WHEAT":w,"MELON":m,"STRAWBERRY":max(0,slots-w-m),"CARROT":0,"TOMATO":0}
    def _sell_orders(self,obs,counts):
        priv=obs.get("private",{}) or {};shed=priv.get("shed",{}) or {};m=obs.get("market",{}) or {};inv=m.get("inventory",{}) or {};day=int(obs.get("day",0));step=int(obs.get("step",day*24+int(obs.get("hour",0))));rem=718-step;load=sum(int(v or 0) for v in shed.values());hard=rem<=self.cfg.terminal_hard
        animals=counts["COW"]+counts["SHEEP"]+counts["GOOSE"];holds={"WHEAT":0 if hard else min(int(shed.get("WHEAT",0)),max(8,animals*2))}
        rf={"WHEAT":.52,"CARROT":.48,"TOMATO":.50,"STRAWBERRY":float(self.params["reserve_strawberry"]),"MELON":float(self.params["reserve_melon"]),"EGG":.48,"MILK":float(self.params["reserve_milk"]),"WOOL":float(self.params["reserve_wool"]),"FERTILIZER":float(self.params["reserve_fertilizer"])}
        order=["STRAWBERRY","MILK","WOOL","MELON","CARROT","TOMATO","EGG","FERTILIZER","WHEAT"];out=[]
        for item in order:
            qty=max(0,int(shed.get(item,0))-holds.get(item,0))
            if qty<=0:continue
            if hard:n=qty
            else:
                frac=rf[item]
                if load>=self.cfg.shed_hard:frac=.05
                elif load>=self.cfg.shed_soft:frac*=.60
                n=min(qty,sellable_above(item,int(inv.get(item,10000)),max(1,int(frac*BASE[item]))))
                if load>=self.cfg.shed_hard and n==0:n=qty
            if n>0:out.append(["SELL",item,n])
        return out
