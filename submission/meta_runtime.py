from __future__ import annotations

"""Pure-stdlib robust macro-policy selection for the Kaggle hot path."""

import math


def _norm(xs):
    xs=[max(0.0,float(x)) for x in xs]
    s=sum(xs)
    return [x/s for x in xs] if s>0 else ([1.0/len(xs)]*len(xs) if xs else [])


class MetaPolicySelector:
    """Select among precomputed macro policies with confidence and hysteresis.

    The expensive policy-zoo/CEM/equilibrium work happens offline.  Live play
    only multiplies a tiny payoff matrix by an archetype posterior once per day.
    """
    def __init__(self, model_obj):
        self.meta=(model_obj or {}).get("meta") or {}
        self.names=list(self.meta.get("policy_names") or [])
        self.payoff=self.meta.get("payoff") or []
        self.prior=_norm(self.meta.get("policy_mixture") or ([1.0]*len(self.names)))
        self.opp_prior=_norm(self.meta.get("opponent_prior") or [])
        self.params=self.meta.get("policy_params") or {}
        self.current=self.meta.get("default_policy") or (self.names[0] if self.names else None)
        self.last_day=-1
        self.min_conf=float(self.meta.get("min_archetype_confidence",.62))
        self.switch_margin=float(self.meta.get("switch_margin",.025))
        self.prior_strength=float(self.meta.get("prior_strength",.018))

    def available(self):
        return bool(self.names and len(self.payoff)==len(self.names))

    def _score(self, posterior):
        if not self.available(): return []
        nopp=max((len(r) for r in self.payoff),default=0)
        q=_norm(posterior if posterior and len(posterior)==nopp else self.opp_prior)
        if not q: q=[1.0/nopp]*nopp if nopp else []
        out=[]
        for i,row in enumerate(self.payoff):
            ev=sum(float(a)*b for a,b in zip(row,q))
            prior=self.prior[i] if i<len(self.prior) else 1.0/max(1,len(self.names))
            # Log-prior preserves the equilibrium mix as a robustness regularizer
            # without forcing random strategy changes inside a single episode.
            ev += self.prior_strength*math.log(max(1e-9,prior))
            out.append(ev)
        return out

    def update(self, day, posterior=None, confidence=0.0):
        day=int(day)
        if day==self.last_day or not self.available(): return self.current
        self.last_day=day
        scores=self._score(posterior)
        if not scores: return self.current
        best=max(range(len(scores)),key=scores.__getitem__)
        candidate=self.names[best]
        if self.current not in self.names:
            self.current=candidate
            return self.current
        cur=self.names.index(self.current); gain=scores[best]-scores[cur]
        # Low-confidence beliefs are deliberately sticky.  The equilibrium prior
        # still influences scores, but specialization needs actual evidence.
        needed=self.switch_margin*(1.6 if float(confidence)<self.min_conf else 1.0)
        if candidate!=self.current and gain>=needed:
            self.current=candidate
        return self.current

    def current_params(self):
        p=self.params.get(str(self.current)) if self.current is not None else None
        return dict(p or {})
