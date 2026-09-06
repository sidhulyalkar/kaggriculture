from __future__ import annotations

import copy, os

try:
    from .predictive_agent import PredictiveMind
    from .base_controller import BASE, model_price, sellable_above
    from .market_flow_runtime import infer_external_supply
    from .market_predictor import DistilledSalePredictor
    from .adaptive_market_agent import normalize_observation_step
except Exception:
    from predictive_agent import PredictiveMind
    from base_controller import BASE, model_price, sellable_above
    from market_flow_runtime import infer_external_supply
    from market_predictor import DistilledSalePredictor
    from adaptive_market_agent import normalize_observation_step

MODEL_PATH=os.path.join(os.path.dirname(__file__),"adaptive_market_model.json")


class GuardedMarketMind(PredictiveMind):
    """Incumbent-safe V56 market ambusher.

    The policy is byte-for-byte behavioral BASE until public opponent-flow
    evidence identifies a high-frequency, diffuse STRAWBERRY seller. Once the
    regime is latched, the already-qualified public-state predictor may advance
    STRAWBERRY liquidation only. No production, routing, land, animal, feed or
    other market decisions are modified.
    """
    def __init__(self,mode="safe",model_path=None):
        super().__init__();self.predictor=DistilledSalePredictor(model_path or MODEL_PATH);self.mode=str(mode)
        self.prev_obs=None;self.prev_action=None;self.exact=0;self.events=0;self.units=0;self.buckets=[0]*6
        self.regime_active=False;self.activation_step=None;self.intervention_count=0;self.intervention_units=0

    def _thresholds(self):
        if self.mode=="balanced": return (96,5,.048,.60)
        return (120,7,.058,.55)

    def _observe_regime(self,prev,curr,own_action):
        units=infer_external_supply(prev,curr,own_action,"STRAWBERRY")
        if units is None:return
        self.exact+=1
        if int(units)>0:
            self.events+=1;self.units+=int(units);self.buckets[(int((prev or {}).get("hour",0) or 0)//4)%6]+=1
        if self.regime_active:return
        min_exact,min_events,min_rate,max_conc=self._thresholds()
        rate=self.events/max(1,self.exact);conc=max(self.buckets)/max(1,self.events)
        if self.exact>=min_exact and self.events>=min_events and rate>=min_rate and conc<=max_conc:
            self.regime_active=True;self.activation_step=normalize_observation_step(curr)

    def regime_snapshot(self):
        return {"mode":self.mode,"active":self.regime_active,"activation_step":self.activation_step,"exact":self.exact,"events":self.events,"units":self.units,
                "event_rate":self.events/max(1,self.exact),"bucket_max_share":max(self.buckets)/max(1,self.events),"buckets":list(self.buckets)}

    def _sell_orders(self,obs,counts):
        # Important: bypass AdaptiveMarketMind completely until public regime
        # evidence is sufficient. This makes the pre-activation path identical
        # to the incumbent PredictiveMind.
        orders=PredictiveMind._sell_orders(self,obs,counts)
        if not self.regime_active or not self.predictor.available("STRAWBERRY"):return orders[:10]
        p="STRAWBERRY";shed=((obs.get("private",{}) or {}).get("shed",{}) or {});q=max(0,int(shed.get(p,0) or 0))
        if q<=0:return orders[:10]
        opponent=1-int((obs or {}).get("player",0) or 0);risk=self.predictor.probability(obs,opponent,p);threshold=self.predictor.threshold(p)
        if risk<threshold:return orders[:10]
        inv=int((((obs.get("market",{}) or {}).get("inventory",{}) or {}).get(p,10000)) or 10000)
        excess=max(0.0,min(1.0,(risk-threshold)/max(.05,1.0-threshold)))
        # Safe mode deliberately takes only 75% of the original V55 reserve
        # discount; balanced mode takes the full experimentally useful move.
        scale=.75 if self.mode=="safe" else 1.0
        reserve=max(.40,.52-.08*scale*(.35+.65*excess))
        target=min(q,sellable_above(p,inv,max(1,int(BASE[p]*reserve))))
        idx=None
        for i,o in enumerate(orders):
            if isinstance(o,list) and len(o)>=3 and o[0]=="SELL" and o[1]==p:idx=i;break
        base_n=int(orders[idx][2]) if idx is not None else 0
        if target<=base_n:return orders[:10]
        shock=max(1.0,float(self.predictor.shock_mean(p)));projected=max(1,int(round(max(0.0,min(1.0,risk))*shock)))
        if model_price(p,inv+base_n)<=model_price(p,inv+base_n+projected):return orders[:10]
        if idx is not None:orders[idx][2]=target
        elif len(orders)<10:orders.append(["SELL",p,target])
        else:return orders[:10]
        self.intervention_count+=1;self.intervention_units+=target-base_n
        return orders[:10]

    def act(self,obs):
        normalize_observation_step(obs)
        if self.prev_obs is not None and self.prev_action is not None:self._observe_regime(self.prev_obs,obs,self.prev_action)
        action=super().act(obs);self.prev_obs=copy.deepcopy(obs);self.prev_action=copy.deepcopy(action);return action


_SAFE=None
_BAL=None

def safe_agent(obs,configuration=None):
    global _SAFE
    step=normalize_observation_step(obs)
    if _SAFE is None or step==0:_SAFE=GuardedMarketMind("safe")
    return _SAFE.act(obs)

def balanced_agent(obs,configuration=None):
    global _BAL
    step=normalize_observation_step(obs)
    if _BAL is None or step==0:_BAL=GuardedMarketMind("balanced")
    return _BAL.act(obs)
