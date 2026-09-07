"""Active opponent system identification for Kaggriculture.

The goal is not to fingerprint a known replay.  We deliberately create tiny,
legal public-market perturbations and estimate how the rival's reconstructed
market flow responds on the following turn.  This identifies behavioral
elasticity of *unseen* policies.

WHEAT is the preferred instrument: it is buyable, useful rather than dead
capital, and near equilibrium a one-unit buy can visibly move price because the
scarcity branch is sqrt-shaped.  The controller never probes if doing so would
interfere with an imminent capital purchase or terminal liquidation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from math import sqrt
from typing import Dict, List, Optional, Tuple


@dataclass
class ProbeSample:
    step: int
    shock: float
    rival_flow_next: float
    price_before: float
    price_after: float


@dataclass
class ElasticityEstimate:
    n: int
    beta: float
    response_mean_probe: float
    response_mean_control: float
    confidence: float
    kind: str


@dataclass
class WheatPolicyProbe:
    # Probe cadence is deliberately sparse.  This is a measurement instrument,
    # not a strategy that burns market orders every turn.
    start_step: int = 96
    stop_step: int = 520
    period: int = 16
    probe_units: int = 1
    min_cash_cushion: float = 1800.0
    samples: List[ProbeSample] = field(default_factory=list)
    _pending: Optional[Tuple[int, float, float]] = None  # step, price, intended shock
    _control_pending: Optional[Tuple[int, float]] = None

    def should_probe(self, step: int, money: float, wheat_price: float,
                     market_slots_used: int, terminal_risk: bool = False) -> bool:
        if terminal_risk or not (self.start_step <= step <= self.stop_step):
            return False
        if money < self.min_cash_cushion or market_slots_used >= 9:
            return False
        # Alternating paired design: probe at phase 0, matched control at phase 8.
        return (step - self.start_step) % self.period == 0 and wheat_price > 0

    def is_control_turn(self, step: int) -> bool:
        return self.start_step <= step <= self.stop_step and (step - self.start_step) % self.period == self.period // 2

    def append_probe_order(self, market_orders: List[list], step: int, money: float,
                           wheat_price: float, terminal_risk: bool = False) -> List[list]:
        out = list(market_orders or [])
        if self.should_probe(step, money, wheat_price, len(out), terminal_risk):
            out.append(["BUY_PRODUCT", "WHEAT", self.probe_units])
            # Exact inventory shock is negative on the public market if executed.
            self._pending = (step, wheat_price, -float(self.probe_units))
        elif self.is_control_turn(step):
            self._control_pending = (step, wheat_price)
        return out

    def observe_next(self, step: int, wheat_price: float, inferred_rival_wheat_flow: float) -> None:
        if self._pending and step == self._pending[0] + 1:
            s, p0, shock = self._pending
            self.samples.append(ProbeSample(s, shock, inferred_rival_wheat_flow, p0, wheat_price))
            self._pending = None
        elif self._pending and step > self._pending[0] + 1:
            self._pending = None

        if self._control_pending and step == self._control_pending[0] + 1:
            s, p0 = self._control_pending
            self.samples.append(ProbeSample(s, 0.0, inferred_rival_wheat_flow, p0, wheat_price))
            self._control_pending = None
        elif self._control_pending and step > self._control_pending[0] + 1:
            self._control_pending = None

    def estimate(self) -> ElasticityEstimate:
        probe = [s for s in self.samples if s.shock != 0]
        ctrl = [s for s in self.samples if s.shock == 0]
        if not probe or not ctrl:
            return ElasticityEstimate(len(self.samples), 0.0, 0.0, 0.0, 0.0, "UNKNOWN")
        mp = sum(s.rival_flow_next for s in probe) / len(probe)
        mc = sum(s.rival_flow_next for s in ctrl) / len(ctrl)
        # Our probe shock is -inventory (scarcity/up-price).  Define beta positive
        # when the rival sells *more* following our scarcity probe.
        beta = mp - mc
        # Confidence rises with paired evidence and effect size, but remains bounded.
        pairs = min(len(probe), len(ctrl))
        conf = min(1.0, pairs / 5.0) * min(1.0, abs(beta) / 2.0)
        if conf < 0.25:
            kind = "UNRESOLVED"
        elif beta >= 0.75:
            kind = "PRICE_ELASTIC_SELLER"
        elif beta <= -0.75:
            kind = "SCARCITY_AVOIDER"
        else:
            kind = "LOW_ELASTICITY"
        return ElasticityEstimate(len(self.samples), beta, mp, mc, conf, kind)


def counter_mode(elasticity: ElasticityEstimate, cash_lead: float) -> str:
    """Map identified rival response into a high-level counter regime."""
    if elasticity.confidence < 0.25:
        return "ROBUST"
    if elasticity.kind == "PRICE_ELASTIC_SELLER":
        # Avoid creating scarcity before our own sale; prefer front-running and,
        # when ahead, small glut signals that discourage threshold sellers.
        return "FRONTRUN" if cash_lead <= 0 else "SUPPRESS"
    if elasticity.kind == "SCARCITY_AVOIDER":
        # Scarcity shocks push them away; exploit orthogonal demand pockets.
        return "SCARCITY_PRESS"
    if elasticity.kind == "LOW_ELASTICITY":
        # They behave nearly open-loop, so supply-timing forecasts become reliable.
        return "PREDICTIVE_FRONTRUN"
    return "ROBUST"
