from __future__ import annotations
import os
try:
    from .parametric_agent import ParametricMind,DEFAULT_PARAMS
    from .runtime_model import ModelBundle,PRODUCTS,BASE
except Exception:
    from parametric_agent import ParametricMind,DEFAULT_PARAMS
    from runtime_model import ModelBundle,PRODUCTS,BASE

MODEL_PATH=os.path.join(os.path.dirname(__file__),"learned_model.json")
class PredictiveMind(ParametricMind):
    """Selective predictive V2. No learned artifact => exact deterministic fallback."""
    def __init__(self):
        super().__init__(DEFAULT_PARAMS);self.model=ModelBundle(MODEL_PATH);self.active_cluster=None;self.cluster_conf=0.;self.last_cluster_day=-1
    def _update_cluster(self,obs):
        day=int(obs.get("day",0))
        if day==self.last_cluster_day:return
        self.last_cluster_day=day;cl,cf=self.model.archetype(obs)
        if cl is not None and (cf>=.70 or self.active_cluster is None):self.active_cluster,self.cluster_conf=cl,cf
    def _profile_params(self):
        mp=self.model.obj.get("policy_by_archetype",{}) if self.model.obj else {}
        p=mp.get(str(self.active_cluster)) if self.active_cluster is not None else None
        return p or DEFAULT_PARAMS
    def _crop_targets(self,obs,counts,day):
        self._update_cluster(obs);old=self.params;self.params=dict(DEFAULT_PARAMS);self.params.update(self._profile_params())
        try:return super()._crop_targets(obs,counts,day)
        finally:self.params=old
    def _animal_targets(self,obs,day):
        self._update_cluster(obs);old=self.params;self.params=dict(DEFAULT_PARAMS);self.params.update(self._profile_params())
        try:return super()._animal_targets(obs,day)
        finally:self.params=old
    def _sell_orders(self,obs,counts):
        orders=super()._sell_orders(obs,counts);forecast=self.model.supply(obs)
        if not forecast:return orders
        priv=obs.get("private",{}) or {};shed=priv.get("shed",{}) or {};market=obs.get("market",{}) or {};prices=market.get("prices",{}) or {}
        already={o[1] for o in orders if isinstance(o,list) and len(o)>1 and o[0]=="SELL"}
        for p in ("STRAWBERRY","MELON","MILK","WOOL"):
            q=int(shed.get(p,0) or 0)
            if p not in already and q>0 and forecast.get(p,0)>=8 and float(prices.get(p,BASE[p]))>=.72*BASE[p]:orders.append(["SELL",p,q])
        return orders[:10]
    def act(self,obs):
        self._update_cluster(obs);return super().act(obs)

_POLICY=PredictiveMind()
def agent(obs,configuration=None):return _POLICY.act(obs)
