from __future__ import annotations

"""Risk-aware selector over a precomputed residual-policy zoo.

Opponent recognition is *not* the promotion objective.  N6 demonstrated that a
nearly perfect hard-opponent classifier can still choose a bad response.  This
selector therefore consumes a payoff/risk artifact learned from paired
counterfactual games and asks a more useful question:

    Which residual has positive conservative policy value under the current
    temporal opponent belief?

The default response must be an exact champion no-op (normally ``V32``).
"""

import math


def _norm(xs):
    xs = [max(0.0, float(x)) for x in xs]
    s = sum(xs)
    return [x / s for x in xs] if s > 0 else ([1.0 / len(xs)] * len(xs) if xs else [])


class TemporalResponseSelector:
    """Choose a residual policy with hysteresis, support, and downside gates.

    Expected artifact schema::

        {
          "responses": ["V32", "CAPITAL_HOLD", ...],
          "default": "V32",
          "win_delta": [[motif...], ...],
          "bad_flip": [[motif...], ...],
          "stderr": [[motif...], ...],
          "support": [[motif...], ...],
          "min_support": 40,
          "risk_lambda": 2.5,
          "uncertainty_z": 1.28,
          "switch_margin": 0.015,
          "max_bad_flip": 0.01,
          "cooldown": 12
        }

    Rows correspond to responses and columns to temporal opponent motifs.
    ``win_delta`` is the paired win-score gain versus V32.  ``bad_flip`` is the
    probability that V32 won but the residual lost.  These are deliberately
    policy-level labels, not classification labels.
    """

    def __init__(self, model=None):
        self.model = dict(model or {})
        self.responses = list(self.model.get("responses") or ["V32"])
        self.default = str(self.model.get("default") or (self.responses[0] if self.responses else "V32"))
        self.min_support = int(self.model.get("min_support", 40))
        self.risk_lambda = float(self.model.get("risk_lambda", 2.5))
        self.uncertainty_z = float(self.model.get("uncertainty_z", 1.28))
        self.switch_margin = float(self.model.get("switch_margin", 0.015))
        self.max_bad_flip = float(self.model.get("max_bad_flip", 0.01))
        self.cooldown = int(self.model.get("cooldown", 12))
        self.reset()

    def reset(self):
        self.current = self.default
        self.last_switch_step = -10**9
        self.pending = None
        self.pending_steps = 0

    def _matrix_row(self, key, i, n):
        mat = self.model.get(key) or []
        if i >= len(mat):
            return [0.0] * n
        row = list(mat[i])
        return [float(row[j]) if j < len(row) else 0.0 for j in range(n)]

    def score(self, belief):
        posterior = _norm(belief.get("posterior") or [])
        n = len(posterior)
        if not n or not self.responses:
            return []
        confidence = float(belief.get("confidence", 0.0) or 0.0)
        change_p = float(belief.get("change_probability", 0.0) or 0.0)
        out = []
        for i, name in enumerate(self.responses):
            gain = self._matrix_row("win_delta", i, n)
            bad = self._matrix_row("bad_flip", i, n)
            se = self._matrix_row("stderr", i, n)
            support = self._matrix_row("support", i, n)
            ev = sum(q * x for q, x in zip(posterior, gain))
            bad_ev = sum(q * x for q, x in zip(posterior, bad))
            uncertainty = math.sqrt(sum((q * s) ** 2 for q, s in zip(posterior, se)))
            effective_support = sum(q * s for q, s in zip(posterior, support))
            lower = ev - self.uncertainty_z * uncertainty - self.risk_lambda * bad_ev
            # A just-detected pivot is exactly when a brittle router is most
            # tempted to overreact.  Penalize specialization until the new motif
            # belief settles; the champion no-op pays no such penalty.
            if name != self.default:
                lower -= (1.0 - confidence) * 0.012
                lower -= change_p * 0.008
            eligible = (
                name == self.default
                or (effective_support >= self.min_support and bad_ev <= self.max_bad_flip)
            )
            out.append({
                "name": name,
                "expected_win_delta": ev,
                "bad_flip": bad_ev,
                "stderr": uncertainty,
                "lower_value": lower,
                "support": effective_support,
                "eligible": eligible,
            })
        return out

    def update(self, step, belief):
        step = int(step)
        if step == 0:
            self.reset()
        scores = self.score(belief)
        if not scores:
            return self.current, None
        eligible = [x for x in scores if x["eligible"]]
        if not eligible:
            return self.current, scores
        best = max(eligible, key=lambda x: x["lower_value"])
        current = next((x for x in scores if x["name"] == self.current), None)
        cur_value = current["lower_value"] if current else 0.0
        gain = best["lower_value"] - cur_value

        # A response must beat both the current response and an absolute
        # conservative floor.  This avoids choosing the least-bad specialist.
        absolute_ok = best["name"] == self.default or best["lower_value"] > 0.0
        switch_ok = best["name"] != self.current and gain >= self.switch_margin and absolute_ok
        cooled = step - self.last_switch_step >= self.cooldown
        if switch_ok and cooled:
            if best["name"] == self.pending:
                self.pending_steps += 1
            else:
                self.pending = best["name"]
                self.pending_steps = 1
            # Strategy switches require persistence.  Returning to the champion
            # is allowed faster than entering a specialist.
            needed = 1 if best["name"] == self.default else 3
            if self.pending_steps >= needed:
                self.current = best["name"]
                self.last_switch_step = step
                self.pending = None
                self.pending_steps = 0
        else:
            self.pending = None
            self.pending_steps = 0
        return self.current, scores
