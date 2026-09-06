from __future__ import annotations

import copy
import os

try:
    from .predictive_agent import PredictiveMind
    from .base_controller import BASE, model_price, sellable_above
    from .market_flow_runtime import infer_external_supply
    from .market_predictor import DistilledSalePredictor
except Exception:
    from predictive_agent import PredictiveMind
    from base_controller import BASE, model_price, sellable_above
    from market_flow_runtime import infer_external_supply
    from market_predictor import DistilledSalePredictor

MODEL_PATH=os.path.join(os.path.dirname(__file__),"adaptive_market_model.json")
TRACKED=("CARROT","STRAWBERRY","MELON","EGG","WOOL")
ACTIONABLE=("STRAWBERRY","MELON","WOOL")
BASE_RESERVE={"STRAWBERRY":.52,"MELON":.78,"WOOL":.55}
MAX_DISCOUNT={"STRAWBERRY":.08,"MELON":.10,"WOOL":.09}
PRIOR_STRENGTH=12.0
BUCKET_STRENGTH=4.0


def _clip(x,lo,hi):return max(lo,min(hi,float(x)))

def normalize_observation_step(obs):
    step=int((obs or {}).get("day",0) or 0)*24+int((obs or {}).get("hour",0) or 0)
    try:
        raw=(obs or {}).get("step")
        if raw is not None and int(raw)==step:step=int(raw)
    except Exception:pass
    if isinstance(obs,dict):obs["step"]=step
    return step


class OnlineOpponentModel:
    """Bayesian per-episode adapter over the frozen population prior."""
    def __init__(self,predictor):
        self.predictor=predictor;self.state={}
        for p in TRACKED:
            prior=_clip(predictor.prevalence(p) if predictor.available(p) else .05,.005,.45)
            self.state[p]={
                "a":prior*PRIOR_STRENGTH,"b":(1-prior)*PRIOR_STRENGTH,
                "ba":[prior*BUCKET_STRENGTH for _ in range(6)],"bb":[(1-prior)*BUCKET_STRENGTH for _ in range(6)],
                "shock":max(1.0,predictor.shock_mean(p) if predictor.available(p) else 6.0),"shock_n":3.0,
                "hit":2.0,"false":1.0,"miss":1.0,
            }

    def observe(self,prev_obs,curr_obs,own_action,prev_predictions):
        if prev_obs is None or curr_obs is None:return
        bucket=(int((prev_obs or {}).get("hour",0) or 0)//4)%6
        for p in TRACKED:
            units=infer_external_supply(prev_obs,curr_obs,own_action,p)
            if units is None:continue
            s=self.state[p];event=1 if int(units)>0 else 0
            s["a"]+=event;s["b"]+=1-event;s["ba"][bucket]+=event;s["bb"][bucket]+=1-event
            if event:
                n=s["shock_n"];s["shock"]=(s["shock"]*n+float(units))/(n+1.0);s["shock_n"]=n+1.0
            pred=(prev_predictions or {}).get(p)
            if pred is not None and self.predictor.available(p):
                guessed=float(pred)>=self.predictor.threshold(p)
                if guessed and event:s["hit"]+=1.0
                elif guessed and not event:s["false"]+=1.0
                elif (not guessed) and event:s["miss"]+=1.0

    def rates(self,p,hour):
        s=self.state[p];g=s["a"]/(s["a"]+s["b"]);k=(int(hour)//4)%6;b=s["ba"][k]/(s["ba"][k]+s["bb"][k])
        trust=_clip((s["hit"]+2.0)/(s["hit"]+s["false"]+.5*s["miss"]+3.0),.35,1.0)
        return g,b,trust,float(s["shock"])


class AdaptiveMarketMind(PredictiveMind):
    """V55 selective market front-runner with within-match opponent learning."""
    def __init__(self,online_enabled=None,model_path=None):
        super().__init__();self.predictor=DistilledSalePredictor(model_path or MODEL_PATH)
        if online_enabled is None: online_enabled=str((self.predictor.obj or {}).get("selected_mode","online")).lower()!="offline"
        self.online_enabled=bool(online_enabled);self.online=OnlineOpponentModel(self.predictor)
        self.prev_obs=None;self.prev_action=None;self.prev_predictions={}
        self.intervention_count=0;self.intervention_units=0;self.intervention_by_product={p:0 for p in ACTIONABLE}

    def _predict(self,obs,p):
        if not self.predictor.available(p):return 0.0
        seat=1-int((obs or {}).get("player",0) or 0);raw=self.predictor.probability(obs,seat,p)
        if not self.online_enabled:return raw
        g,b,trust,_=self.online.rates(p,int((obs or {}).get("hour",0) or 0))
        return self.predictor.adjusted_probability(raw,p,g,b,trust)

    def _sell_orders(self,obs,counts):
        orders=super()._sell_orders(obs,counts)
        if not self.predictor.models:return orders[:10]
        shed=((obs.get("private",{}) or {}).get("shed",{}) or {});market=obs.get("market",{}) or {};inv=(market.get("inventory",{}) or {})
        by_product={}
        for i,o in enumerate(orders):
            if isinstance(o,list) and len(o)>=3 and o[0]=="SELL":by_product[str(o[1])]=i
        hour=int(obs.get("hour",0) or 0)
        for p in ACTIONABLE:
            if not self.predictor.available(p):continue
            q=max(0,int(shed.get(p,0) or 0))
            if q<=0:continue
            risk=self._predict(obs,p);threshold=self.predictor.threshold(p)
            if risk<threshold:continue
            g,b,trust,shock=self.online.rates(p,hour) if self.online_enabled else (self.predictor.prevalence(p),self.predictor.prevalence(p),.70,self.predictor.shock_mean(p))
            excess=_clip((risk-threshold)/max(.05,1.0-threshold),0.0,1.0)
            strength=(.35+.65*excess)*(.70+.30*trust)*_clip(shock/8.0,.55,1.25)
            reserve=max(.35,BASE_RESERVE[p]-MAX_DISCOUNT[p]*_clip(strength,0.0,1.0))
            market_inv=int(inv.get(p,10000) or 10000)
            target=min(q,sellable_above(p,market_inv,max(1,int(BASE[p]*reserve))))
            idx=by_product.get(p);base_n=int(orders[idx][2]) if idx is not None else 0
            if target<=base_n:continue
            projected=max(1,int(round(_clip(risk,0,1)*shock)))
            marginal_now=model_price(p,market_inv+base_n);marginal_after=model_price(p,market_inv+base_n+projected)
            if marginal_now<=marginal_after:continue
            if idx is not None:orders[idx][2]=target
            elif len(orders)<10:orders.append(["SELL",p,target]);by_product[p]=len(orders)-1
            else:continue
            extra=target-base_n;self.intervention_count+=1;self.intervention_units+=extra;self.intervention_by_product[p]+=extra
        return orders[:10]

    def act(self,obs):
        normalize_observation_step(obs)
        if self.prev_obs is not None and self.prev_action is not None and self.online_enabled:self.online.observe(self.prev_obs,obs,self.prev_action,self.prev_predictions)
        predictions={p:self._predict(obs,p) for p in TRACKED if self.predictor.available(p)}
        action=super().act(obs)
        self.prev_obs=copy.deepcopy(obs);self.prev_action=copy.deepcopy(action);self.prev_predictions=predictions
        return action


_POLICY=None
def agent(obs,configuration=None):
    global _POLICY
    step=normalize_observation_step(obs)
    if _POLICY is None or step==0:_POLICY=AdaptiveMarketMind(online_enabled=None)
    return _POLICY.act(obs)
