"""V33 WorkGraph: conservative black-box residual for the exact V32 champion.

The production builder injects the exact runtime-verified V32 callable into
``V33WorkGraphOverlay``. The overlay never needs V32 internals. It first asks
V32 for its complete action, then may remove only a narrowly certified HIRE.
Every non-HIRE action and every inactive state is byte-for-behavior inherited
from the champion.

For repository tests only, ``agent`` at the bottom wraps the local deterministic
controller. A promoted Kaggle artifact MUST be built from the exact V32 archive
and its known SHA-256, not from that development fallback.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

FIB = (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181)
CROPS = {
    "WHEAT": {"first": 2, "max_yield": 6},
    "CARROT": {"first": 2, "max_yield": 4},
    "TOMATO": {"first": 8, "max_yield": 4},
    "STRAWBERRY": {"first": 10, "max_yield": 4},
    "MELON": {"first": 10, "max_yield": 6},
}
ANIMAL_PRODUCTS = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}
BASE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
    "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200,
    "FERTILIZER": 100,
}


@dataclass(frozen=True)
class WorkGraphState:
    backlog: float
    economic_weight: float
    critical: float
    existing_capacity: float
    hand_capacity: float
    hours_left: int


@dataclass(frozen=True)
class HireValuation:
    cost: float
    expected_value: float
    lower_value: float
    robust_value: float
    robust_roi: float
    keep: bool
    reason: str
    state: WorkGraphState


class LabourOptionTwin:
    """Price one extra hand as an option that expires at end of day."""

    SCENARIOS = ((0.52, 0.82), (0.70, 1.00), (0.86, 1.10))

    @staticmethod
    def _counts(farm: dict) -> dict:
        out = {k: 0 for k in tuple(CROPS) + tuple(ANIMAL_PRODUCTS)}
        for row in farm.get("tiles", []) or []:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                crop = tile.get("crop")
                animal = tile.get("animal")
                if tile.get("kind") == "PLANT" and crop in CROPS:
                    out[crop] += 1
                if animal in ANIMAL_PRODUCTS:
                    out[animal] += 1
        return out

    def _market_price(self, obs: dict, item: str) -> float:
        prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
        try:
            return float(prices.get(item, BASE.get(item, 50)) or BASE.get(item, 50))
        except Exception:
            return float(BASE.get(item, 50))

    def work_graph(self, obs: dict, *, units: int) -> WorkGraphState:
        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
        counts = self._counts(farm)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        hours_left = max(0, 23 - hour)

        backlog = 0.0
        econ = 0.0
        critical = 0.0
        empty = 0

        for row in farm.get("tiles", []) or []:
            for tile in row:
                if tile is None:
                    empty += 1
                    continue
                if not isinstance(tile, dict):
                    continue
                kind = tile.get("kind")
                if kind == "WEED":
                    backlog += 0.75
                    econ += 22.0
                    continue
                if kind == "PLANT":
                    crop = tile.get("crop")
                    meta = CROPS.get(crop)
                    if meta is None:
                        continue
                    price = self._market_price(obs, crop)
                    planted = tile.get("planted_day", day)
                    planted = day if planted is None else int(planted)
                    age = day - planted
                    yld = max(0, int(tile.get("yield_units", 0) or 0))
                    dry = int(tile.get("consecutive_unwatered", 0) or 0)
                    if not tile.get("watered_today", False):
                        w = 2.35 if age == 0 or dry >= 1 else 1.25
                        backlog += w
                        econ += w * max(35.0, 0.42 * price * meta["max_yield"])
                        if age == 0 or dry >= 1:
                            critical += w
                    if yld > 0 and age >= meta["first"]:
                        backlog += 1.10
                        econ += max(25.0, 0.72 * yld * price)
                    fert_until = tile.get("fertilized_until_day", -1)
                    fert_until = -1 if fert_until is None else int(fert_until)
                    if crop == "STRAWBERRY" and age >= 7 and fert_until <= day + 1:
                        backlog += 0.45
                        econ += max(18.0, 0.18 * price * meta["max_yield"])
                    continue

                animal = tile.get("animal")
                if animal in ANIMAL_PRODUCTS:
                    price = self._market_price(obs, ANIMAL_PRODUCTS[animal])
                    unfed = int(tile.get("consecutive_unfed", 0) or 0)
                    if not tile.get("fed_today", False):
                        w = 2.70 if unfed >= 1 else 1.55
                        backlog += w
                        econ += w * max(55.0, 0.80 * price)
                        critical += w
                    yld = max(0, int(tile.get("yield_units", 0) or 0))
                    if yld > 0:
                        backlog += 1.15
                        econ += max(30.0, 0.78 * yld * price)
                    if tile.get("fertilizer_available", False):
                        backlog += 0.55
                        econ += max(20.0, 0.55 * self._market_price(obs, "FERTILIZER"))
                    if not tile.get("cared_today", False):
                        backlog += 0.55
                        econ += max(16.0, 0.16 * price)

        animals = sum(counts[a] for a in ANIMAL_PRODUCTS)
        crops = sum(counts[c] for c in CROPS)
        productive = animals + crops
        if empty > 0 and day < 20:
            construction = min(4.0, empty * 0.18)
            backlog += construction
            econ += construction * (48.0 if day < 12 else 34.0)

        arrival = min(5.0, 0.030 * productive * hours_left + 0.045 * animals * hours_left)
        backlog += arrival
        econ += arrival * 42.0

        existing_capacity = max(0.0, units * hours_left * 0.70 / 4.0)
        hand_capacity = max(0.0, hours_left * 0.70 / 4.0)
        return WorkGraphState(
            backlog=float(backlog), economic_weight=float(econ),
            critical=float(critical), existing_capacity=float(existing_capacity),
            hand_capacity=float(hand_capacity), hours_left=hours_left,
        )

    def value_hire(self, obs: dict, *, units: int, hires_today: int, cash: float) -> HireValuation:
        state = self.work_graph(obs, units=units)
        idx = min(max(0, int(hires_today)), len(FIB) - 1)
        cost = float(FIB[idx])
        day = int(obs.get("day", 0) or 0)

        if cost <= 34:
            return HireValuation(cost, cost * 3, cost * 2, cost * 2, 2.0, True, "cheap_growth_hire", state)
        if state.hours_left <= 2:
            return HireValuation(cost, 0.0, 0.0, 0.0, 0.0, False, "labor_expires_too_soon", state)

        value_per_task = state.economic_weight / max(1.0, state.backlog)
        residual_queue = max(0.0, state.backlog - state.existing_capacity)
        values = []
        for efficiency, value_scale in self.SCENARIOS:
            capacity = max(0.0, state.hours_left * efficiency / 4.0)
            values.append(min(residual_queue, capacity) * value_per_task * value_scale)
        expected = 0.25 * values[0] + 0.50 * values[1] + 0.25 * values[2]
        lower = min(values)
        robust = 0.55 * expected + 0.45 * lower

        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
        quadrants = len(farm.get("unlocked_quadrants", ["NW"]) or ["NW"])
        if quadrants < 2 and 5 <= day <= 8:
            robust -= 90.0
        elif quadrants < 3 and 9 <= day <= 12:
            robust -= 150.0
        if cash < 1100:
            robust -= 0.08 * max(0.0, 1100.0 - cash)
        robust = max(0.0, robust)
        roi = robust / max(1.0, cost)

        critical_gap = max(0.0, state.critical - state.existing_capacity)
        if critical_gap >= 1.25:
            keep, reason = True, "critical_service_gap"
        else:
            hurdle = 1.10 if 7 <= day <= 13 else 1.02
            keep = roi >= hurdle
            reason = "robust_value_positive" if keep else "negative_ephemeral_option"
        return HireValuation(cost, expected, lower, robust, roi, keep, reason, state)


class V33WorkGraphOverlay:
    """Black-box V32 wrapper. Only certified HIRE removals are permitted."""

    LATCH_STEP = 577
    DEFEND_LEAD = 6500.0

    def __init__(self, base_agent: Callable):
        self.base_agent = base_agent
        self.twin = LabourOptionTwin()
        self._budget_day = -1
        self._suppressed_today = 0
        self._capital_latch: str | None = None
        self._latched_lead: float | None = None
        self.last_valuations: list[HireValuation] = []
        self.total_suppressions = 0

    @property
    def capital_latch(self) -> str | None:
        return self._capital_latch

    @property
    def latched_lead(self) -> float | None:
        return self._latched_lead

    def _reset(self) -> None:
        self._budget_day = -1
        self._suppressed_today = 0
        self._capital_latch = None
        self._latched_lead = None
        self.last_valuations = []
        self.total_suppressions = 0

    def _update_capital_latch(self, obs: dict) -> None:
        if self._capital_latch is not None:
            return
        if int(obs.get("step", 0) or 0) < self.LATCH_STEP:
            return
        farms = obs.get("farms", []) or []
        p = int(obs.get("player", 0) or 0)
        if len(farms) < 2 or p >= len(farms):
            self._capital_latch, self._latched_lead = "BASE", 0.0
            return
        other = 1 - p if len(farms) == 2 else next((i for i in range(len(farms)) if i != p), p)
        own = float((farms[p] or {}).get("money", 0) or 0)
        opp = float((farms[other] or {}).get("money", 0) or 0)
        self._latched_lead = own - opp
        self._capital_latch = "DEFEND" if self._latched_lead >= self.DEFEND_LEAD else "BASE"

    def _filter_market(self, obs: dict, market: list) -> list:
        self._update_capital_latch(obs)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if day != self._budget_day:
            self._budget_day, self._suppressed_today = day, 0
        self.last_valuations = []

        midgame = 11 <= day <= 18
        late_defend = self._capital_latch == "DEFEND" and 24 <= day <= 27
        if not (midgame or late_defend) or hour > 20:
            return market
        if not any(isinstance(a, list) and a and a[0] == "HIRE" for a in market):
            return market

        daily_budget = 2 if late_defend else 1
        if self._suppressed_today >= daily_budget:
            return market

        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
        cash = float(farm.get("money", 0) or 0)
        hires_today = int(farm.get("hires_today", 0) or 0)
        units = 1 + len(farm.get("hands", []) or [])
        quadrants = len(farm.get("unlocked_quadrants", ["NW"]) or ["NW"])

        out, kept_hires, suppressed_now = [], 0, 0
        for action in market:
            if not (isinstance(action, list) and action and action[0] == "HIRE"):
                out.append(action)
                continue
            valuation = self.twin.value_hire(
                obs, units=units + kept_hires,
                hires_today=hires_today + kept_hires, cash=cash,
            )
            self.last_valuations.append(valuation)
            critical_safe = valuation.reason != "critical_service_gap"
            if late_defend:
                candidate = valuation.cost >= 144 and valuation.robust_roi < 0.90 and critical_safe
            else:
                capital_pressure = cash < 3500 or quadrants < 3
                candidate = (
                    valuation.cost >= 233 and valuation.robust_roi < 0.60
                    and capital_pressure and critical_safe
                )
            if self._suppressed_today + suppressed_now < daily_budget and candidate:
                suppressed_now += 1
                continue
            out.append(action)
            kept_hires += 1
            cash -= valuation.cost

        self._suppressed_today += suppressed_now
        self.total_suppressions += suppressed_now
        return out[:10]

    def act(self, obs: dict, configuration=None):
        if int((obs or {}).get("step", 0) or 0) == 0:
            self._reset()
        try:
            baseline = self.base_agent(obs, configuration)
        except TypeError:
            baseline = self.base_agent(obs)
        if not isinstance(baseline, dict):
            return baseline
        action = copy.deepcopy(baseline)
        market = list(action.get("market", []) or [])
        action["market"] = self._filter_market(obs, market)
        return action


# Development-only entry point. The production builder replaces this section
# with the exact V32 source isolated inside its own namespace.
try:
    from .base_controller import agent as _DEV_BASE
except Exception:
    from base_controller import agent as _DEV_BASE

_DEV_POLICY = V33WorkGraphOverlay(_DEV_BASE)

def agent(obs: dict[str, Any], configuration=None):
    return _DEV_POLICY.act(obs, configuration)
