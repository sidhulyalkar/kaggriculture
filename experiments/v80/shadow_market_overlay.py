"""Conservative V80 overlay: change SELL *order*, never the physical route or quantities.

This is the first causal screen for the shadow-ledger idea. It observes rival net
market flow via shared-inventory conservation and front-runs products with recent
rival supply pressure. If this cannot beat the same base policy with identical
physical actions, the signal does not deserve a larger planner.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

try:
    from .opponent_shadow import OpponentShadow
except Exception:
    from opponent_shadow import OpponentShadow


def _get(obj: Any, key: str, default=None):
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


class ShadowMarketOverlay:
    def __init__(self, base_agent):
        self.base_agent = base_agent
        self.shadow = OpponentShadow()
        self.last_action: Dict[str, Any] = {}
        self.last_private: Dict[str, Any] = {}
        self.last_step = -1

    def _step(self, obs) -> int:
        day = int(_get(obs, "day", 0) or 0); hour = int(_get(obs, "hour", 0) or 0)
        return int(_get(obs, "step", day * 24 + hour) or (day * 24 + hour))

    def __call__(self, obs):
        step = self._step(obs)
        if step <= self.last_step or step == 0:
            self.shadow.reset(); self.last_action = {}; self.last_private = {}
        self.shadow.observe(obs, previous_action=self.last_action, private_before=self.last_private)

        base = self.base_agent(obs)
        action = deepcopy(base if isinstance(base, Mapping) else {})
        market = action.get("market", [])
        if not isinstance(market, list) or len(market) < 2:
            self._remember(obs, action, step)
            return action

        public_market = _get(obs, "market", {}) or {}
        prices = _get(public_market, "prices", {}) or {}
        farms = _get(obs, "farms", []) or []
        player = int(_get(obs, "player", 0) or 0)
        me = farms[player] if player < len(farms) else {}
        opp = farms[1-player] if len(farms) > 1 else {}
        cash_lead = float(_get(me, "money", 0) or 0) - float(_get(opp, "money", 0) or 0)

        # Stable partition: atomic/buy orders retain their exact positions relative
        # to one another. Only contiguous SELL runs are reordered, avoiding semantic
        # changes such as moving a HIRE or land purchase across another operation.
        out = list(market)
        i = 0
        while i < len(out):
            if not (isinstance(out[i], list) and out[i] and out[i][0] == "SELL"):
                i += 1; continue
            j = i
            run = []
            while j < len(out) and isinstance(out[j], list) and out[j] and out[j][0] == "SELL":
                run.append(out[j]); j += 1
            def rank(order):
                item = order[1] if len(order) > 1 else ""
                price = float(prices.get(item, 0) or 0)
                pressure = self.shadow.collision_pressure(item)
                # Leading agents care more about securing current realizable value;
                # trailing agents put slightly more weight on escaping predicted
                # collisions. Both effects are bounded and alter order only.
                pressure_weight = 10.0 if cash_lead >= 0 else 16.0
                return pressure_weight * min(8.0, pressure) + 0.05 * price
            out[i:j] = sorted(run, key=rank, reverse=True)
            i = j
        action["market"] = out
        self._remember(obs, action, step)
        return action

    def _remember(self, obs, action, step):
        private = _get(obs, "private", {}) or {}
        # Deep-copy only the small private dictionaries needed to bound our own
        # previous execution; do not retain the whole observation graph.
        self.last_private = {
            "shed": dict(_get(private, "shed", {}) or {}),
            "seeds": dict(_get(private, "seeds", {}) or {}),
        }
        self.last_action = deepcopy(action)
        self.last_step = step
