"""V33 WorkGraph: a conservative capital-allocation residual over V32.

V33 leaves the production plan, selling policy, routes, crop targets, animal
targets, and terminal mechanics untouched. It models one decision V32 treats
as a fixed schedule: whether the *marginal* temporary hand is worth its
Fibonacci cost before that hand expires at the end of the day.

The agent combines two ideas:

1. WorkGraph, a structural model of visible service demand and marginal labor
   capacity under pessimistic/neutral/optimistic execution scenarios.
2. A one-time late capital latch. At the late-game checkpoint the public bank
   lead is read once. Only a comfortably leading farm enters DEFEND mode; the
   latch never oscillates and never activates an aggressive counter-policy.

The resulting residual is deliberately tiny. Midgame it can suppress only the
single most expensive hire under strong capital pressure. In a latched late
lead it may suppress at most two clearly redundant expensive hires per day.
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
    """Structural world-model for one additional hand that expires tonight."""

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
                    planted_day = tile.get("planted_day", day)
                    planted_day = day if planted_day is None else int(planted_day)
                    age = day - planted_day
                    yld = max(0, int(tile.get("yield_units", 0) or 0))
                    dry = int(tile.get("consecutive_unwatered", 0) or 0)
                    if not tile.get("watered_today", False):
                        w = 2.35 if age == 0 or dry >= 1 else 1.25
                        backlog += w
                        econ += w * max(35.0, 0.42 * price * cd.get("max_yield", 1))
                        if age == 0 or dry >= 1:
                            critical += w
                    if yld > 0 and age >= int(cd.get("first", 0)):
                        backlog += 1.10
                        econ += max(25.0, 0.72 * yld * price)
                    fert_until = tile.get("fertilized_until_day", -1)
                    fert_until = -1 if fert_until is None else int(fert_until)
                    if crop == "STRAWBERRY" and age >= 7 and fert_until <= day + 1:
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

        animals = sum(int(counts.get(a, 0) or 0) for a in ANIMALS)
        crops = sum(int(counts.get(c, 0) or 0) for c in CROPS)
        productive_tiles = animals + crops
        if empty > 0 and day < 20:
            construction = min(4.0, empty * 0.18)
            backlog += construction
            econ += construction * (48.0 if day < 12 else 34.0)

        # Predictable task arrivals during the rest of the day. This is bounded
        # so a large farm cannot manufacture arbitrary justification for labor.
        arrival = min(5.0, 0.030 * productive_tiles * hours_left + 0.045 * animals * hours_left)
        backlog += arrival
        econ += arrival * 42.0

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

        # Cash has extra option value near V32's expansion cliffs. This penalty
        # can only affect whether a HIRE is delayed; it never creates another
        # purchase or changes its timing directly.
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

        critical_gap = max(0.0, state.critical - state.existing_capacity)
        if critical_gap >= 1.25:
            keep, reason = True, "critical_service_gap"
        else:
            hurdle = 1.10 if 7 <= day <= 13 else 1.02
            keep = roi >= hurdle
            reason = "robust_value_positive" if keep else "negative_ephemeral_option"
        return HireValuation(cost, expected, lower, robust, roi, keep, reason, state)


class V33WorkGraphMind(HarvestMind):
    """V32 backbone plus a tiny state-valued capital residual."""

    LATCH_STEP = 577
    DEFEND_LEAD = 6500.0

    def __init__(self):
        super().__init__()
        self.twin = LabourOptionTwin()
        self._budget_day = -1
        self._suppressed_today = 0
        self._capital_latch: str | None = None
        self._latched_lead: float | None = None
        self.last_valuations: list[HireValuation] = []

    @property
    def capital_latch(self) -> str | None:
        return self._capital_latch

    @property
    def latched_lead(self) -> float | None:
        return self._latched_lead

    def _update_capital_latch(self, obs: dict) -> None:
        if self._capital_latch is not None:
            return
        step = int(obs.get("step", 0) or 0)
        if step < self.LATCH_STEP:
            return
        farms = obs.get("farms", []) or []
        p = int(obs.get("player", 0) or 0)
        if len(farms) < 2 or p >= len(farms):
            self._capital_latch = "BASE"
            self._latched_lead = 0.0
            return
        other = 1 - p if len(farms) == 2 else next((i for i in range(len(farms)) if i != p), p)
        own = float((farms[p] or {}).get("money", 0) or 0)
        opp = float((farms[other] or {}).get("money", 0) or 0)
        lead = own - opp
        self._latched_lead = lead
        self._capital_latch = "DEFEND" if lead >= self.DEFEND_LEAD else "BASE"

    def _market(self, obs: dict, counts: dict):
        baseline = super()._market(obs, counts)
        self._update_capital_latch(obs)

        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if day != self._budget_day:
            self._budget_day = day
            self._suppressed_today = 0
        self.last_valuations = []

        midgame = 11 <= day <= 18
        late_defend = self._capital_latch == "DEFEND" and 24 <= day <= 27
        if not (midgame or late_defend) or hour > 20:
            return baseline
        if not any(isinstance(a, list) and a and a[0] == "HIRE" for a in baseline):
            return baseline

        # Midgame is deliberately almost inert: at most one $233 marginal hand
        # can be delayed, and only during real capital pressure. DEFEND mode is
        # allowed two expensive suppressions because the public lead is latched
        # and the primary objective becomes preserving a buffered win.
        daily_budget = 2 if late_defend else 1
        if self._suppressed_today >= daily_budget:
            return baseline

        p = int(obs.get("player", 0) or 0)
        farms = obs.get("farms", []) or []
        farm = farms[p] if p < len(farms) else {}
        cash = float(farm.get("money", 0) or 0)
        hires_today = int(farm.get("hires_today", 0) or 0)
        units = 1 + len(farm.get("hands", []) or [])
        q = len(farm.get("unlocked_quadrants", ["NW"]) or ["NW"])

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

            critical_safe = valuation.reason != "critical_service_gap"
            if late_defend:
                candidate = (
                    valuation.cost >= 144
                    and valuation.robust_roi < 0.90
                    and critical_safe
                )
            else:
                capital_pressure = cash < 3500 or q < 3
                candidate = (
                    valuation.cost >= 233
                    and valuation.robust_roi < 0.60
                    and capital_pressure
                    and critical_safe
                )

            can_suppress = self._suppressed_today + suppressed_now < daily_budget
            if can_suppress and candidate:
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
