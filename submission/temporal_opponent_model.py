from __future__ import annotations

"""Tiny stdlib opponent-strategy tracker for the Kaggle hot path.

The older runtime archetype model classified one public snapshot at a time.
That is useful for identity/style priors, but it cannot tell the difference
between "this opponent is animal-heavy" and "this opponent just pivoted into an
animal-heavy phase".  This module treats strategy as a latent *time varying*
state.

The tracker has two layers:

1. an online change detector built from short/long EWMA disagreement and a
   one-sided CUSUM; and
2. an optional motif posterior over replay-trained strategy segment centroids.

It never changes an action itself.  It produces a belief state for a separate
safe response selector.  Missing/weak evidence therefore defaults to the
champion policy rather than forcing a strategy switch.
"""

import math

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("COW", "SHEEP", "GOOSE")
PRODUCTS = CROPS + ("EGG", "MILK", "WOOL", "FERTILIZER")


def _sigmoid(x: float) -> float:
    if x >= 35:
        return 1.0
    if x <= -35:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _norm(xs):
    xs = [max(0.0, float(x)) for x in xs]
    total = sum(xs)
    if total > 0:
        return [x / total for x in xs]
    return [1.0 / len(xs)] * len(xs) if xs else []


def _entropy_confidence(p):
    if not p:
        return 0.0
    if len(p) == 1:
        return 1.0
    h = -sum(q * math.log(max(q, 1e-12)) for q in p) / math.log(len(p))
    return max(0.0, min(1.0, 1.0 - h))


def _scan(farm):
    counts = {x: 0 for x in CROPS + ANIMALS}
    ready = {x: 0 for x in CROPS + ANIMALS}
    pasture = coop = 0
    for row in (farm or {}).get("tiles", []) or []:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            crop = tile.get("crop")
            animal = tile.get("animal")
            if tile.get("kind") == "PLANT" and crop in CROPS:
                counts[crop] += 1
                if int(tile.get("yield_units", 0) or 0) > 0:
                    ready[crop] += 1
            if animal in ANIMALS:
                counts[animal] += 1
                if int(tile.get("yield_units", 0) or 0) > 0:
                    ready[animal] += 1
            if tile.get("kind") == "PASTURE":
                pasture += 1
            if tile.get("kind") == "COOP":
                coop += 1
    return counts, ready, pasture, coop


def opponent_snapshot(obs):
    """Return an online-safe public description of the opponent.

    No private opponent inventory is used.  All features are visible in the
    runtime observation and can therefore be reproduced in offline replays.
    """
    p = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", []) or []
    if len(farms) < 2:
        return {}
    other = 1 - p if len(farms) == 2 else next((i for i in range(len(farms)) if i != p), p)
    farm = farms[other] if other < len(farms) else {}
    counts, ready, pasture, coop = _scan(farm)
    market = obs.get("market", {}) or {}
    inv = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}
    out = {
        "money": float(farm.get("money", 0) or 0),
        "hands": float(len(farm.get("hands", []) or [])),
        "quadrants": float(len(farm.get("unlocked_quadrants", ["NW"]) or ["NW"])),
        "pasture": float(pasture),
        "coop": float(coop),
    }
    for x in CROPS + ANIMALS:
        out["count_" + x] = float(counts[x])
        out["ready_" + x] = float(ready[x])
    # Market context is not opponent-specific, but strategy pivots often become
    # visible as supply shocks.  The response model can learn whether a shock is
    # useful after conditioning on our own known previous action.
    for x in PRODUCTS:
        out["market_inv_" + x] = float(inv.get(x, 10000) or 10000)
        out["market_price_" + x] = float(prices.get(x, 0) or 0)
    return out


DEFAULT_DELTA_FEATURES = (
    "d_money", "d_hands", "d_quadrants", "d_pasture", "d_coop",
    "d_count_WHEAT", "d_count_STRAWBERRY", "d_count_MELON",
    "d_count_COW", "d_count_SHEEP", "d_count_GOOSE",
    "d_ready_STRAWBERRY", "d_ready_MELON", "d_ready_COW", "d_ready_SHEEP",
    "d_market_inv_WHEAT", "d_market_inv_STRAWBERRY", "d_market_inv_MELON",
    "d_market_inv_MILK", "d_market_inv_WOOL",
)


class TemporalOpponentTracker:
    """Online strategy belief with change-point hysteresis.

    ``model`` is an optional JSON-compatible artifact produced offline.  Its
    minimal schema is::

        {
          "features": [...],
          "mean": [...], "scale": [...],
          "motifs": [{"name": str, "center": [...]}, ...],
          "transition": [[...], ...],
          "temperature": 1.0,
          "hazard": 0.025,
          "change_threshold": 0.78,
          "confirm_steps": 3
        }

    A motif posterior is useful, but *change probability* is a separate object.
    This prevents a very confident static classifier from hiding a real pivot.
    """

    def __init__(self, model=None):
        self.model = dict(model or {})
        self.features = list(self.model.get("features") or DEFAULT_DELTA_FEATURES)
        self.short_alpha = float(self.model.get("short_alpha", 0.45))
        self.long_alpha = float(self.model.get("long_alpha", 0.08))
        self.hazard = float(self.model.get("hazard", 0.025))
        self.change_threshold = float(self.model.get("change_threshold", 0.78))
        self.confirm_steps = int(self.model.get("confirm_steps", 3))
        self.cusum_k = float(self.model.get("cusum_k", 0.55))
        self.cusum_h = float(self.model.get("cusum_h", 3.0))
        self.temperature = max(1e-6, float(self.model.get("temperature", 1.0)))
        self.reset()

    def reset(self):
        self.last_step = -1
        self.prev = None
        self.short = {}
        self.long = {}
        self.abs_dev = {}
        self.cusum = 0.0
        self.change_probability = 0.0
        self.change_streak = 0
        self.segment_start = 0
        self.change_count = 0
        self.posterior = []
        self.current_motif = None
        self.candidate_motif = None
        self.candidate_streak = 0
        self.last_delta = {}

    def _delta(self, snap):
        if self.prev is None:
            return {"d_" + k: 0.0 for k in snap}
        return {"d_" + k: float(v) - float(self.prev.get(k, v)) for k, v in snap.items()}

    def _update_ewma(self, delta):
        for name in self.features:
            x = float(delta.get(name, 0.0))
            if name not in self.short:
                self.short[name] = self.long[name] = x
                self.abs_dev[name] = max(1.0, abs(x))
                continue
            self.short[name] += self.short_alpha * (x - self.short[name])
            self.long[name] += self.long_alpha * (x - self.long[name])
            self.abs_dev[name] += self.long_alpha * (abs(x - self.long[name]) - self.abs_dev[name])

    def _surprise(self):
        if not self.features:
            return 0.0
        terms = []
        for name in self.features:
            scale = max(0.75, float(self.abs_dev.get(name, 1.0)))
            terms.append(abs(float(self.short.get(name, 0.0)) - float(self.long.get(name, 0.0))) / scale)
        terms.sort(reverse=True)
        # Top-k aggregation lets a genuine strategic pivot in a few important
        # dimensions survive the many near-zero dimensions in the full vector.
        k = min(6, len(terms))
        return sum(terms[:k]) / max(1, k)

    def _motif_posterior(self, delta):
        motifs = list(self.model.get("motifs") or [])
        if not motifs:
            return [], 0.0
        mean = list(self.model.get("mean") or [0.0] * len(self.features))
        scale = list(self.model.get("scale") or [1.0] * len(self.features))
        x = [float(delta.get(n, 0.0)) for n in self.features]
        z = [(a - b) / (s if abs(float(s)) > 1e-9 else 1.0) for a, b, s in zip(x, mean, scale)]
        dists = []
        for motif in motifs:
            c = list(motif.get("center") or [])
            if len(c) != len(z):
                dists.append(1e9)
            else:
                dists.append(sum((a - b) ** 2 for a, b in zip(z, c)))
        md = min(dists)
        likelihood = [math.exp(-min(60.0, max(0.0, (d - md) / (2.0 * self.temperature)))) for d in dists]

        transition = self.model.get("transition") or []
        if self.posterior and len(self.posterior) == len(likelihood) and len(transition) == len(likelihood):
            prior = []
            for j in range(len(likelihood)):
                prior.append(sum(self.posterior[i] * float(transition[i][j]) for i in range(len(likelihood))))
        else:
            prior = _norm(self.model.get("prior") or [1.0] * len(likelihood))
        # When a change is likely, flatten the old-state prior so the model can
        # actually jump instead of being trapped by its own hysteresis.
        flatten = min(1.0, max(0.0, self.change_probability))
        uniform = 1.0 / max(1, len(prior))
        prior = [(1.0 - flatten) * q + flatten * uniform for q in prior]
        post = _norm([a * b for a, b in zip(prior, likelihood)])
        return post, _entropy_confidence(post)

    def update(self, obs):
        step = int(obs.get("step", 0) or 0)
        if step == 0 or step < self.last_step:
            self.reset()
        self.last_step = step
        snap = opponent_snapshot(obs)
        if not snap:
            return self.belief()
        delta = self._delta(snap)
        self.prev = snap
        self.last_delta = delta
        self._update_ewma(delta)
        surprise = self._surprise()

        # A bounded BOCPD-inspired hazard + CUSUM approximation.  It is much
        # cheaper than carrying a full run-length posterior for 719 turns, but
        # still distinguishes persistent drift from one noisy market tick.
        innovation = max(0.0, surprise - self.cusum_k)
        self.cusum = max(0.0, 0.82 * self.cusum + innovation)
        hazard_logit = math.log(max(1e-6, self.hazard) / max(1e-6, 1.0 - self.hazard))
        self.change_probability = _sigmoid(hazard_logit + 1.55 * (self.cusum - self.cusum_h))
        if self.change_probability >= self.change_threshold:
            self.change_streak += 1
        else:
            self.change_streak = max(0, self.change_streak - 1)
        confirmed_change = self.change_streak >= self.confirm_steps
        if confirmed_change:
            self.change_count += 1
            self.segment_start = step
            self.change_streak = 0
            self.cusum *= 0.30

        post, confidence = self._motif_posterior(delta)
        self.posterior = post
        if post:
            best = max(range(len(post)), key=post.__getitem__)
            if best == self.candidate_motif:
                self.candidate_streak += 1
            else:
                self.candidate_motif = best
                self.candidate_streak = 1
            needed = 2 if confirmed_change else 4
            if confidence >= float(self.model.get("motif_confidence", 0.45)) and self.candidate_streak >= needed:
                self.current_motif = best
        return self.belief(confirmed_change=confirmed_change, surprise=surprise, confidence=confidence)

    def belief(self, confirmed_change=False, surprise=0.0, confidence=None):
        motifs = list(self.model.get("motifs") or [])
        name = None
        if self.current_motif is not None and self.current_motif < len(motifs):
            name = motifs[self.current_motif].get("name", str(self.current_motif))
        if confidence is None:
            confidence = _entropy_confidence(self.posterior)
        return {
            "motif": self.current_motif,
            "motif_name": name,
            "posterior": list(self.posterior),
            "confidence": float(confidence),
            "change_probability": float(self.change_probability),
            "confirmed_change": bool(confirmed_change),
            "segment_age": max(0, int(self.last_step - self.segment_start)),
            "change_count": int(self.change_count),
            "surprise": float(surprise),
        }
