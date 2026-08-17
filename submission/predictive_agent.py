from __future__ import annotations
import os
try:
    from .parametric_agent import ParametricMind,DEFAULT_PARAMS
    from .runtime_model import ModelBundle,PRODUCTS,BASE
    from .meta_runtime import MetaPolicySelector
except Exception:
    from parametric_agent import ParametricMind,DEFAULT_PARAMS
    from runtime_model import ModelBundle,PRODUCTS,BASE
    from meta_runtime import MetaPolicySelector

MODEL_PATH=os.path.join(os.path.dirname(__file__),"learned_model.json")

class PredictiveMind(ParametricMind):
    """Selective predictive V2.

    Learned components may choose among *precomputed macro policies* and may
    accelerate selling ahead of predicted supply floods.  Mechanical execution
    remains inside the deterministic HarvestMind controller.  If no promoted
    artifact exists, behavior is exactly the deterministic parametric fallback.
    """
    def __init__(self):
        super().__init__(DEFAULT_PARAMS)
        self.model=ModelBundle(MODEL_PATH)
        self.selector=MetaPolicySelector(self.model.obj)
        self.active_cluster=None
        self.cluster_conf=0.0
        self.posterior=[]
        self.last_belief_day=-1
        self.selected_policy=self.selector.current

    def _legacy_archetype_params(self):
        mp=self.model.obj.get("policy_by_archetype",{}) if self.model.obj else {}
        p=mp.get(str(self.active_cluster)) if self.active_cluster is not None else None
        return dict(p or {})

    def _update_belief(self,obs):
        day=int(obs.get("day",0))
        if day==self.last_belief_day:return
        self.last_belief_day=day
        posterior,conf=self.model.archetype_distribution(obs)
        self.posterior=posterior
        self.cluster_conf=float(conf)
        if posterior:
            self.active_cluster=max(range(len(posterior)),key=posterior.__getitem__)

        # Preferred path: robust equilibrium/CEM policy zoo distilled offline.
        selected=self.selector.update(day,posterior,self.cluster_conf)
        self.selected_policy=selected
        chosen=self.selector.current_params() if self.selector.available() else {}

        # Backward-compatible path for E005 artifacts produced before the meta
        # equilibrium layer existed.
        if not chosen and self.active_cluster is not None and self.cluster_conf>=.60:
            chosen=self._legacy_archetype_params()

        self.params=dict(DEFAULT_PARAMS)
        self.params.update(chosen or {})
        self.cfg.terminal_start=int(self.params.get("terminal_start",DEFAULT_PARAMS["terminal_start"]))

    def _sell_orders(self,obs,counts):
        orders=super()._sell_orders(obs,counts)
        forecast=self.model.supply(obs)
        if not forecast:return orders
        priv=obs.get("private",{}) or {};shed=priv.get("shed",{}) or {};market=obs.get("market",{}) or {};prices=market.get("prices",{}) or {}
        already={o[1] for o in orders if isinstance(o,list) and len(o)>1 and o[0]=="SELL"}
        # Predictive selling is intentionally restricted to premium products.
        # It can move a sale earlier, but never alters feed reserves or mechanics.
        for p in ("STRAWBERRY","MELON","MILK","WOOL"):
            q=int(shed.get(p,0) or 0)
            if p not in already and q>0 and forecast.get(p,0)>=8 and float(prices.get(p,BASE[p]))>=.72*BASE[p]:
                orders.append(["SELL",p,q])
        return orders[:10]

    def act(self,obs):
        self._update_belief(obs)
        return super().act(obs)

_POLICY=PredictiveMind()
def agent(obs,configuration=None):return _POLICY.act(obs)
