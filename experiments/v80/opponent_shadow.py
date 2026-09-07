"""Opponent shadow ledger for Kaggriculture.

The shared market is a conservation meter. Between two observations, market
inventory changes by our executed market flow + opponent market flow - town
consumption. Town consumption is deterministic from the previous step and the
previous unlocked-shop multiset, so the remaining flow constrains the hidden
opponent market action.

This module intentionally tracks *intervals*, not fake point certainty. Our own
requested orders can partially fail (money/shed/capacity) and $1 sales do not
increase market inventory, so an interval is the correct primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
BUYABLE_PRODUCTS = {"WHEAT", "FERTILIZER"}
SHOPS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, Mapping):
        return dict(obj)
    return obj or {}


def town_drain(step: int, unlocked_shops: Iterable[str], shop_interval: int = 4,
               center_interval: int = 24) -> Dict[str, int]:
    """Exact units removed by the town after market processing on `step`."""
    out = {p: 0 for p in PRODUCTS}
    if step % max(1, shop_interval) == 0:
        for shop in unlocked_shops or ():
            products = SHOPS.get(shop, ())
            mult = 2 if len(products) == 1 else 1
            for p in products:
                out[p] += mult
    if step % max(1, center_interval) == 0:
        for p in PRODUCTS:
            if p != "FERTILIZER":
                out[p] += 1
    return out


def own_market_flow_bounds(action: Mapping[str, Any], private_before: Mapping[str, Any],
                           market_before: Mapping[str, Any], shed_capacity: int = 100,
                           max_orders: int = 10) -> Dict[str, Tuple[int, int]]:
    """Bounds on our market-inventory contribution from the previous action.

    Positive means we could have added units through SELL. Negative means we
    could have removed units through BUY_PRODUCT. Seed/animal/land/hire orders
    do not directly change shared market inventory.
    """
    bounds = {p: [0, 0] for p in PRODUCTS}
    if not isinstance(action, Mapping):
        return {p: (0, 0) for p in PRODUCTS}
    shed = _dict(_get(private_before, "shed", {}))
    prices = _dict(_get(market_before, "prices", {}))
    money = float(_get(private_before, "money", 1e30) or 1e30)  # normally farm money is supplied separately
    capacity_used = sum(max(0, int(v or 0)) for v in shed.values() if isinstance(v, (int, float)))
    sell_left = {p: max(0, int(shed.get(p, 0) or 0)) for p in PRODUCTS}
    room = max(0, int(shed_capacity) - capacity_used)

    orders = action.get("market", [])
    if not isinstance(orders, list):
        orders = []
    for order in orders[:max_orders]:
        if not isinstance(order, list) or len(order) < 3:
            continue
        op, item = order[0], order[1]
        if item not in bounds:
            continue
        try:
            n = max(0, int(order[2]))
        except Exception:
            continue
        if op == "SELL":
            nmax = min(n, sell_left[item])
            sell_left[item] -= nmax
            # At a visible $1 floor, sales may contribute zero supply. Otherwise
            # successful units normally add one each; retain uncertainty because
            # lockstep opponent flow can change later quotes.
            lo = 0 if int(prices.get(item, 2) or 2) <= 1 else nmax
            bounds[item][0] += lo
            bounds[item][1] += nmax
        elif op == "BUY_PRODUCT" and item in BUYABLE_PRODUCTS:
            nmax = min(n, room)
            # Affordability is deliberately left conservative because unit prices
            # can move in the opponent lockstep queue.
            bounds[item][0] -= nmax
            bounds[item][1] += 0
            room -= nmax

    return {p: (int(v[0]), int(v[1])) for p, v in bounds.items()}


@dataclass
class FlowEstimate:
    step: int
    lower: Dict[str, float]
    upper: Dict[str, float]
    point: Dict[str, float]
    town: Dict[str, int]


@dataclass
class OpponentShadow:
    shop_interval: int = 4
    center_interval: int = 24
    shed_capacity: int = 100
    max_orders: int = 10
    prev_step: Optional[int] = None
    prev_inventory: Dict[str, float] = field(default_factory=dict)
    prev_prices: Dict[str, float] = field(default_factory=dict)
    prev_shops: List[str] = field(default_factory=list)
    prev_private: Dict[str, Any] = field(default_factory=dict)
    prev_action: Dict[str, Any] = field(default_factory=dict)
    cumulative_sell_lb: Dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in PRODUCTS})
    cumulative_sell_ub: Dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in PRODUCTS})
    ema_flow: Dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in PRODUCTS})
    history: List[FlowEstimate] = field(default_factory=list)

    def reset(self) -> None:
        self.prev_step = None
        self.prev_inventory.clear(); self.prev_prices.clear(); self.prev_shops.clear()
        self.prev_private.clear(); self.prev_action.clear(); self.history.clear()
        self.cumulative_sell_lb = {p: 0.0 for p in PRODUCTS}
        self.cumulative_sell_ub = {p: 0.0 for p in PRODUCTS}
        self.ema_flow = {p: 0.0 for p in PRODUCTS}

    def observe(self, obs: Mapping[str, Any], previous_action: Optional[Mapping[str, Any]] = None,
                private_before: Optional[Mapping[str, Any]] = None) -> Optional[FlowEstimate]:
        market = _get(obs, "market", {}) or {}
        inv = _dict(_get(market, "inventory", {}))
        prices = _dict(_get(market, "prices", {}))
        town = _get(obs, "town", {}) or {}
        shops = list(_get(town, "unlocked_shops", []) or [])
        day = int(_get(obs, "day", 0) or 0); hour = int(_get(obs, "hour", 0) or 0)
        step = int(_get(obs, "step", day * 24 + hour) or (day * 24 + hour))

        estimate = None
        if self.prev_step is not None and step > self.prev_step:
            own_bounds = own_market_flow_bounds(
                previous_action if previous_action is not None else self.prev_action,
                private_before if private_before is not None else self.prev_private,
                {"prices": self.prev_prices},
                shed_capacity=self.shed_capacity,
                max_orders=self.max_orders,
            )
            drain = town_drain(self.prev_step, self.prev_shops, self.shop_interval, self.center_interval)
            lower: Dict[str, float] = {}; upper: Dict[str, float] = {}; point: Dict[str, float] = {}
            for p in PRODUCTS:
                delta = float(inv.get(p, 0) or 0) - float(self.prev_inventory.get(p, 0) or 0)
                own_lo, own_hi = own_bounds[p]
                # delta = own + opponent - town_drain
                lo = delta - own_hi + drain[p]
                hi = delta - own_lo + drain[p]
                if p not in BUYABLE_PRODUCTS:
                    # Opponent cannot BUY these products. A negative residual is
                    # therefore inference noise from our uncertain execution.
                    lo = max(0.0, lo); hi = max(lo, hi)
                    self.cumulative_sell_lb[p] += lo
                    self.cumulative_sell_ub[p] += hi
                pt = 0.5 * (lo + hi)
                lower[p], upper[p], point[p] = lo, hi, pt
                self.ema_flow[p] = 0.75 * self.ema_flow[p] + 0.25 * pt
            estimate = FlowEstimate(self.prev_step, lower, upper, point, drain)
            self.history.append(estimate)

        self.prev_step = step
        self.prev_inventory = {p: float(inv.get(p, 0) or 0) for p in PRODUCTS}
        self.prev_prices = {p: float(prices.get(p, 0) or 0) for p in PRODUCTS}
        self.prev_shops = shops
        self.prev_action = dict(previous_action or {})
        self.prev_private = dict(private_before or {})
        return estimate

    def collision_pressure(self, item: str) -> float:
        """Smoothed inferred rival supply pressure; positive => likely price collision."""
        return max(0.0, float(self.ema_flow.get(item, 0.0)))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "cumulative_sell_lb": dict(self.cumulative_sell_lb),
            "cumulative_sell_ub": dict(self.cumulative_sell_ub),
            "ema_flow": dict(self.ema_flow),
            "observations": len(self.history),
        }
