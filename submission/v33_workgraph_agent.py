"""V33 WorkGraph: a conservative labor-option residual over the V32 backbone.

The design intentionally leaves V32's production plan, market selling, routing,
crop targets, animal targets, and terminal behavior untouched.  It models only
one thing V32 currently treats as a fixed schedule: the value of another hand
that expires at the end of the current day.

A hand is viewed as a short-dated option on the visible work queue.  The model
prices that option from task urgency, estimated economic consequence, remaining
hours, travel/service efficiency, existing labor capacity, and the Fibonacci
hire cost.  Expensive marginal hires are suppressed only when every robust
scenario says the remaining work cannot justify them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .base_controller import HarvestMind, FIB, CROPS, ANIMALS, BASE
except Exception:
    from base_controller import HarvestMind, FIB, CROPS, ANIMALS, BASE


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
    """Small structural world-model for one ephemeral additional hand.

    This is not a learned opponent classifier.  It is an explicit model of the
    farm's currently visible service queue.  Uncertainty is represented by
    three efficiency/value scenarios and the decision uses a lower-tail blend.
    """

    # Average task completions per available hour under pessimistic/neutral/
    # optimistic routing efficiency.  The neutral value corresponds to roughly
    # 3.5-4 moves/actions per useful task on the compact farm grid.
    SCENARIOS = (
        (0.52, 0.82),
        (0.70, 1.00),
        (0.86, 1.10),
    )

    def _market_price(self, obs: dict, item: str) -> float:
        market = obs.get("market", {}) or {}
        prices = market.get("prices", {}) or {}
        try:
            return float(prices.get(item, BASE.get(item, 50)) or BASE.get(item, 50))
        except Exception:
            return float(BASE.get(item, 50))

    def work_graph(self, obs: dict, counts: dict, *, units: int) -> WorkGraphState:
        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
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
                    cd = CROPS.get(crop)
                    if cd is None:
                        continue
                    price = self._market_price(obs, crop)
                    age = day - int(tile.get("planted_day", day) or day)
                    yld = max(0, int(tile.get("yield_units", 0) or 0))
                    dry = int(tile.get("consecutive_unwatered", 0) or 0)
                    if not tile.get("watered_today", False):
                        # Planting-day watering and an existing dry streak carry
                        # asymmetric downside, so they dominate the queue.
                        w = 2.35 if age == 0 or dry >= 1 else 1.25
                        backlog += w
                        econ += w * max(35.0, 0.42 * price * cd.get("max_yield", 1))
                        if age == 0 or dry >= 1:
                            critical += w
                    if yld > 0 and age >= int(cd.get("first", 0)):
                        backlog += 1.10
                        econ += max(25.0, 0.72 * yld * price)
                    if crop == "STRAWBERRY" and age >= 7 and int(tile.get("fertilized_until_day", -1) or -1) <= day + 1:
                        backlog += 0.45
                        econ += max(18.0, 0.18 * price * cd.get("max_yield", 1))
                    continue
                animal = tile.get("animal")
                if animal in ANIMALS:
                    ad = ANIMALS[animal]
                    product = ad["product"]
                    price = self._market_price(obs, product)
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

        # Add a bounded estimate for constructive work that is not represented
        # by an existing tile task yet.  This prevents the model from declaring
        # a newly expanded but empty farm "idle".
        animals = sum(int(counts.get(a, 0) or 0) for a in ANIMALS)
        crops = sum(int(counts.get(c, 0) or 0) for c in CROPS)
        productive_tiles = animals + crops
        if empty > 0 and day < 20:
            construction = min(4.0, empty * 0.18)
            backlog += construction
            econ += construction * (48.0 if day < 12 else 34.0)

        # Existing labor also has to absorb predictable within-day arrivals.
        arrival = min(5.0, 0.030 * productive_tiles * hours_left + 0.045 * animals * hours_left)
        backlog += arrival
        econ += arrival * 42.0

        # Capacity is intentionally conservative: a unit rarely converts every
        # hour into productive work because it must walk, load, and unload.
        existing_capacity = max(0.0, units * hours_left * 0.70 / 4.0)
        hand_capacity = max(0.0, hours_left * 0.70 / 4.0)
        return WorkGraphState(
            backlog=float(backlog),
            economic_weight=float(econ),
            critical=float(critical),
            existing_capacity=float(existing_capacity),
            hand_capacity=float(hand_capacity),
            hours_left=hours_left,
        )

    def value_hire(
        self,
        obs: dict,
        counts: dict,
        *,
        units: int,
        hires_today: int,
        cash: float,
    ) -> HireValuation:
        state = self.work_graph(obs, counts, units=units)
        idx = min(max(0, int(hires_today)), len(FIB) - 1)
        cost = float(FIB[idx])
        day = int(obs.get("day", 0) or 0)

        if cost <= 34:
            return HireValuation(cost, cost * 3, cost * 2, cost * 2, 2.0, True, "cheap_growth_hire", state)
        if state.hours_left <= 2:
            return HireValuation(cost, 0.0, 0.0, 0.0, 0.0, False, "labor_expires_too_soon", state)

        value_per_task = state.economic_weight / max(1.0, state.backlog)
        scenario_values = []
        residual_queue = max(0.0, state.backlog - state.existing_capacity)
        for efficiency, value_scale in self.SCENARIOS:
            marginal_capacity = max(0.0, state.hours_left * efficiency / 4.0)
            useful = min(residual_queue, marginal_capacity)
            scenario_values.append(useful * value_per_task * value_scale)

        expected = 0.25 * scenario_values[0] + 0.50 * scenario_values[1] + 0.25 * scenario_values[2]
        lower = min(scenario_values)
        robust = 0.55 * expected + 0.45 * lower

        # Cash saved today has option value around the two V32 land-expansion
        # cliffs and when liquid reserves are thin.  We do not invent a land
        # purchase; this only raises the hurdle for an expiring hand.
        q = 1
        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        if p < len(farms):
            q = len((farms[p] or {}).get("unlocked_quadrants", ["NW"]) or ["NW"])
        option_penalty = 0.0
        if q < 2 and 5 <= day <= 8:
            option_penalty += 90.0
        elif q < 3 and 9 <= day <= 12:
            option_penalty += 150.0
        if cash < 1100:
            option_penalty += 0.08 * max(0.0, 1100.0 - cash)
        robust = max(0.0, robust - option_penalty)
        roi = robust / max(1.0, cost)

        # Critical feed/water work is a hard safety exception.  If the current
        # crew cannot cover most critical work, preserve V32's hire even when
        # the pure dollar model is pessimistic.
        critical_gap = max(0.0, state.critical - state.existing_capacity)
        if critical_gap >= 1.25:
            keep, reason = True, "critical_service_gap"
        else:
            hurdle = 1.10 if 7 <= day <= 13 else 1.02
            keep = roi >= hurdle
            reason = "robust_value_positive" if keep else "negative_ephemeral_option"
        return HireValuation(cost, expected, lower, robust, roi, keep, reason, state)


class V33WorkGraphMind(HarvestMind):
    """Exact V32-style backbone with a sparse marginal-hire value gate."""

    def __init__(self):
        super().__init__()
        self.twin = LabourOptionTwin()
        self._budget_day = -1
        self._suppressed_today = 0
        self.last_valuations: list[HireValuation] = []

    def _market(self, obs: dict, counts: dict):
        baseline = super()._market(obs, counts)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if day != self._budget_day:
            self._budget_day = day
            self._suppressed_today = 0
        self.last_valuations = []

        # Preserve V32 exactly in the opening, late game, and late-night cleanup.
        if day < 5 or day > 18 or hour > 20 or self._suppressed_today >= 2:
            return baseline
        if not any(isinstance(a, list) and a and a[0] == "HIRE" for a in baseline):
            return baseline

        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
        cash = float(farm.get("money", 0) or 0)
        hires_today = int(farm.get("hires_today", 0) or 0)
        units = 1 + len(farm.get("hands", []) or [])

        out = []
        kept_hires = 0
        suppressed_now = 0
        for action in baseline:
            if not (isinstance(action, list) and action and action[0] == "HIRE"):
                out.append(action)
                continue
            valuation = self.twin.value_hire(
                obs,
                counts,
                units=units + kept_hires,
                hires_today=hires_today + kept_hires,
                cash=cash,
            )
            self.last_valuations.append(valuation)
            can_suppress = self._suppressed_today + suppressed_now < 2
            if can_suppress and not valuation.keep:
                suppressed_now += 1
                continue
            out.append(action)
            kept_hires += 1
            cash -= valuation.cost

        self._suppressed_today += suppressed_now
        return out[:10]


_POLICY = None

def agent(obs: dict[str, Any], configuration=None):
    """Kaggle entry point with per-episode state reset."""
    global _POLICY
    step = int((obs or {}).get("step", 0) or 0)
    if _POLICY is None or step == 0:
        _POLICY = V33WorkGraphMind()
    return _POLICY.act(obs)
