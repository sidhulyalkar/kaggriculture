from __future__ import annotations

import copy

try:
    from .predictive_agent import PredictiveMind, normalize_observation_step
    from .base_controller import BASE, model_price
    from .market_flow_runtime import NONBUYABLE_PRODUCTS, infer_external_supply
except Exception:
    from predictive_agent import PredictiveMind, normalize_observation_step
    from base_controller import BASE, model_price
    from market_flow_runtime import NONBUYABLE_PRODUCTS, infer_external_supply

# Keep V53 deliberately narrow. These products have meaningful downside from
# another supply wave and are not observationally confounded by BUY_PRODUCT.
FLOW_PRODUCTS = ("STRAWBERRY", "MELON", "MILK", "WOOL")
FLOW_MIN_UNITS = 4
FLOW_MIN_PRICE_RATIO = 0.42
FLOW_MIN_LOSS_FRAC = 0.08
FLOW_MIN_LOSS_ABS = 40
FLOW_STRESS_CAP = 24

_FUNNEL_KEYS = (
    "positive_flow_events",
    "positive_flow_units",
    "baseline_already_selling_events",
    "shock_ge_min_events",
    "inventory_positive_events",
    "price_ge_min_events",
    "loss_abs_ge_min_events",
    "loss_frac_ge_min_events",
    "all_thresholds_pass_events",
    "blocked_baseline_sell",
    "blocked_shock",
    "blocked_inventory",
    "blocked_price",
    "blocked_loss_abs",
    "blocked_loss_frac",
    "eligible",
)
_HISTOGRAM_KEYS = {
    "shock": ("1", "2", "3", "4_7", "8_15", "16_plus"),
    "price_ratio": ("lt_0p25", "0p25_0p419", "0p42_0p599", "0p60_0p799", "ge_0p80"),
    "loss_abs": ("lt_10", "10_39", "40_99", "100_249", "ge_250"),
    "loss_frac": ("lt_0p02", "0p02_0p079", "0p08_0p149", "0p15_0p299", "ge_0p30"),
}


def _sale_revenue(product, inventory, quantity):
    return sum(int(model_price(product, int(inventory) + i)) for i in range(max(0, int(quantity))))


def _shock_bin(value):
    value = int(value)
    if value <= 1:
        return "1"
    if value == 2:
        return "2"
    if value == 3:
        return "3"
    if value <= 7:
        return "4_7"
    if value <= 15:
        return "8_15"
    return "16_plus"


def _ratio_bin(value):
    value = float(value)
    if value < 0.25:
        return "lt_0p25"
    if value < 0.42:
        return "0p25_0p419"
    if value < 0.60:
        return "0p42_0p599"
    if value < 0.80:
        return "0p60_0p799"
    return "ge_0p80"


def _loss_abs_bin(value):
    value = float(value)
    if value < 10:
        return "lt_10"
    if value < 40:
        return "10_39"
    if value < 100:
        return "40_99"
    if value < 250:
        return "100_249"
    return "ge_250"


def _loss_frac_bin(value):
    value = float(value)
    if value < 0.02:
        return "lt_0p02"
    if value < 0.08:
        return "0p02_0p079"
    if value < 0.15:
        return "0p08_0p149"
    if value < 0.30:
        return "0p15_0p299"
    return "ge_0p30"


class HardFlowMind(PredictiveMind):
    """V53: react only to confirmed opponent supply already visible in public state.

    The base route is untouched. When a fresh, exactly identifiable opponent
    supply shock makes continued holding economically fragile, V53 may accelerate
    a bounded portion of inventory that the baseline would otherwise hold. The
    intervention is capped by the observed shock size and never touches WHEAT,
    feed reserves, crop targets, animals, land, labor, or movement.

    V53B adds behavior-neutral activation telemetry so exact-engine runs can
    identify which guard suppresses otherwise valid hard-flow opportunities.
    """

    def __init__(self):
        super().__init__()
        self._previous_obs = None
        self._previous_action = None
        self._confirmed_flow = {p: 0 for p in NONBUYABLE_PRODUCTS}
        self.intervention_count = 0
        self.intervention_units = 0
        self.intervention_by_product = {p: 0 for p in FLOW_PRODUCTS}
        self.activation_funnel = {key: 0 for key in _FUNNEL_KEYS}
        self.activation_by_product = {
            product: {key: 0 for key in _FUNNEL_KEYS}
            for product in FLOW_PRODUCTS
        }
        self.activation_histograms = {
            name: {key: 0 for key in keys}
            for name, keys in _HISTOGRAM_KEYS.items()
        }
        self.activation_extrema = {
            "max_shock": 0,
            "max_inventory": 0,
            "max_price_ratio": 0.0,
            "max_loss_abs": 0.0,
            "max_loss_frac": 0.0,
        }

    def _bump(self, product, key, value=1):
        self.activation_funnel[key] += value
        self.activation_by_product[product][key] += value

    def _hist(self, name, key):
        self.activation_histograms[name][key] += 1

    def activation_snapshot(self):
        return {
            "funnel": dict(self.activation_funnel),
            "by_product": {product: dict(values) for product, values in self.activation_by_product.items()},
            "histograms": {name: dict(values) for name, values in self.activation_histograms.items()},
            "extrema": dict(self.activation_extrema),
        }

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
            if len(orders) >= 10:
                break

            shock = int(self._confirmed_flow.get(product, 0) or 0)
            if shock <= 0:
                continue

            quantity = int(shed.get(product, 0) or 0)
            inv = int(inventory.get(product, 10000) or 10000)
            price = float(prices.get(product, model_price(product, inv)) or 0)
            price_ratio = price / max(1.0, float(BASE[product]))
            stress = min(FLOW_STRESS_CAP, shock)
            sell_now = min(max(0, quantity), shock)
            now = _sale_revenue(product, inv, sell_now) if sell_now > 0 else 0
            later = _sale_revenue(product, inv + stress, sell_now) if sell_now > 0 else 0
            loss = max(0, now - later)
            loss_frac = loss / max(1, now)

            self._bump(product, "positive_flow_events")
            self._bump(product, "positive_flow_units", shock)
            if product in already:
                self._bump(product, "baseline_already_selling_events")
            if shock >= FLOW_MIN_UNITS:
                self._bump(product, "shock_ge_min_events")
            if quantity > 0:
                self._bump(product, "inventory_positive_events")
            if price_ratio >= FLOW_MIN_PRICE_RATIO:
                self._bump(product, "price_ge_min_events")
            if sell_now > 0 and loss >= FLOW_MIN_LOSS_ABS:
                self._bump(product, "loss_abs_ge_min_events")
            if sell_now > 0 and loss_frac >= FLOW_MIN_LOSS_FRAC:
                self._bump(product, "loss_frac_ge_min_events")
            if (
                shock >= FLOW_MIN_UNITS
                and quantity > 0
                and price_ratio >= FLOW_MIN_PRICE_RATIO
                and loss >= FLOW_MIN_LOSS_ABS
                and loss_frac >= FLOW_MIN_LOSS_FRAC
            ):
                self._bump(product, "all_thresholds_pass_events")

            self._hist("shock", _shock_bin(shock))
            self._hist("price_ratio", _ratio_bin(price_ratio))
            if sell_now > 0:
                self._hist("loss_abs", _loss_abs_bin(loss))
                self._hist("loss_frac", _loss_frac_bin(loss_frac))

            self.activation_extrema["max_shock"] = max(self.activation_extrema["max_shock"], shock)
            self.activation_extrema["max_inventory"] = max(self.activation_extrema["max_inventory"], quantity)
            self.activation_extrema["max_price_ratio"] = max(self.activation_extrema["max_price_ratio"], price_ratio)
            self.activation_extrema["max_loss_abs"] = max(self.activation_extrema["max_loss_abs"], float(loss))
            self.activation_extrema["max_loss_frac"] = max(self.activation_extrema["max_loss_frac"], float(loss_frac))

            # First-blocker accounting follows the exact V53 decision order.
            if product in already:
                self._bump(product, "blocked_baseline_sell")
                continue
            if shock < FLOW_MIN_UNITS:
                self._bump(product, "blocked_shock")
                continue
            if quantity <= 0:
                self._bump(product, "blocked_inventory")
                continue
            if price_ratio < FLOW_MIN_PRICE_RATIO:
                self._bump(product, "blocked_price")
                continue
            if loss < FLOW_MIN_LOSS_ABS:
                self._bump(product, "blocked_loss_abs")
                continue
            if loss_frac < FLOW_MIN_LOSS_FRAC:
                self._bump(product, "blocked_loss_frac")
                continue

            orders.append(["SELL", product, sell_now])
            self._bump(product, "eligible")
            self.intervention_count += 1
            self.intervention_units += sell_now
            self.intervention_by_product[product] += sell_now

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
    step = normalize_observation_step(obs)
    if _POLICY is None or step == 0:
        _POLICY = HardFlowMind()
    return _POLICY.act(obs)
