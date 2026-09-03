from __future__ import annotations

import copy

try:
    from .predictive_agent import PredictiveMind
    from .base_controller import BASE, model_price
    from .market_flow_runtime import NONBUYABLE_PRODUCTS, infer_external_supply
except Exception:
    from predictive_agent import PredictiveMind
    from base_controller import BASE, model_price
    from market_flow_runtime import NONBUYABLE_PRODUCTS, infer_external_supply

# Keep V53 deliberately narrow.  These products have meaningful downside from
# another supply wave and are not observationally confounded by BUY_PRODUCT.
FLOW_PRODUCTS = ("STRAWBERRY", "MELON", "MILK", "WOOL")
FLOW_MIN_UNITS = 4
FLOW_MIN_PRICE_RATIO = 0.42
FLOW_MIN_LOSS_FRAC = 0.08
FLOW_MIN_LOSS_ABS = 40
FLOW_STRESS_CAP = 24


def _sale_revenue(product, inventory, quantity):
    return sum(int(model_price(product, int(inventory) + i)) for i in range(max(0, int(quantity))))


class HardFlowMind(PredictiveMind):
    """V53: react only to confirmed opponent supply already visible in public state.

    The base route is untouched.  When a fresh, exactly identifiable opponent
    supply shock makes continued holding economically fragile, V53 may accelerate
    a bounded portion of inventory that the baseline would otherwise hold.  The
    intervention is capped by the observed shock size and never touches WHEAT,
    feed reserves, crop targets, animals, land, labor, or movement.
    """

    def __init__(self):
        super().__init__()
        self._previous_obs = None
        self._previous_action = None
        self._confirmed_flow = {p: 0 for p in NONBUYABLE_PRODUCTS}

    def _observe_confirmed_flow(self, obs):
        self._confirmed_flow = {p: 0 for p in NONBUYABLE_PRODUCTS}
        if self._previous_obs is None or self._previous_action is None:
            return
        for product in NONBUYABLE_PRODUCTS:
            units = infer_external_supply(self._previous_obs, obs, self._previous_action, product)
            if units is not None:
                self._confirmed_flow[product] = max(0, int(units))

    def _sell_orders(self, obs, counts):
        orders = super()._sell_orders(obs, counts)
        if len(orders) >= 10:
            return orders[:10]

        shed = ((obs.get("private", {}) or {}).get("shed", {}) or {})
        market = obs.get("market", {}) or {}
        inventory = market.get("inventory", {}) or {}
        prices = market.get("prices", {}) or {}
        already = {
            str(order[1])
            for order in orders
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"
        }

        for product in FLOW_PRODUCTS:
            if product in already or len(orders) >= 10:
                continue
            shock = int(self._confirmed_flow.get(product, 0) or 0)
            quantity = int(shed.get(product, 0) or 0)
            if shock < FLOW_MIN_UNITS or quantity <= 0:
                continue
            price = float(prices.get(product, model_price(product, int(inventory.get(product, 10000) or 10000))) or 0)
            if price < FLOW_MIN_PRICE_RATIO * BASE[product]:
                continue

            # We do not assume the opponent repeats the entire shock.  Stress is
            # bounded to the smaller of the confirmed shock and a conservative cap.
            stress = min(FLOW_STRESS_CAP, shock)
            sell_now = min(quantity, shock)
            inv = int(inventory.get(product, 10000) or 10000)
            now = _sale_revenue(product, inv, sell_now)
            later = _sale_revenue(product, inv + stress, sell_now)
            loss = max(0, now - later)
            if loss < FLOW_MIN_LOSS_ABS or loss < FLOW_MIN_LOSS_FRAC * max(1, now):
                continue
            orders.append(["SELL", product, sell_now])

        return orders[:10]

    def act(self, obs):
        self._observe_confirmed_flow(obs)
        action = super().act(obs)
        self._previous_obs = copy.deepcopy(obs)
        self._previous_action = copy.deepcopy(action)
        return action


_POLICY = None


def agent(obs, configuration=None):
    global _POLICY
    step = int((obs or {}).get("step", 0) or 0)
    if _POLICY is None or step == 0:
        _POLICY = HardFlowMind()
    return _POLICY.act(obs)
