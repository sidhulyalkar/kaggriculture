from __future__ import annotations

"""Population-level strategy mixing for Kaggriculture.

The ladder is non-stationary, so a single CEM best response can overfit the
current opponent sample.  This module treats a policy-zoo payoff table as a
small zero-sum game and computes a low-exploitability mixture using no-regret
mirror descent.  It also exposes a population-aware blend that can trade a
little current-meta EV for robustness against an adversarial meta shift.
"""

import json
from pathlib import Path
import numpy as np


def _simplex(x):
    x = np.asarray(x, dtype=float)
    x = np.maximum(x, 0.0)
    s = float(x.sum())
    return x / s if s > 0 else np.ones(len(x), dtype=float) / max(1, len(x))


def _softmax(logits):
    z = np.asarray(logits, dtype=float)
    z = z - np.max(z)
    ez = np.exp(np.clip(z, -60, 60))
    return _simplex(ez)


def solve_zero_sum(payoff, iterations=12000, eta=None, row_prior=None, col_prior=None):
    """Approximate a rectangular zero-sum equilibrium.

    Parameters
    ----------
    payoff:
        Matrix A where A[i,j] is row-policy utility against opponent column j.
        Win-rate tables should normally be centered as ``win_rate - 0.5``.
    iterations:
        Number of multiplicative-weights updates.  Even 3k is usually enough
        for the tiny policy zoos used here; 12k is still trivial on CPU.
    eta:
        Learning rate.  Defaults to a scale-aware O(1/sqrt(T)) schedule.

    Returns a dictionary containing average row/column mixtures and a duality
    gap (our practical exploitability diagnostic).
    """
    A = np.asarray(payoff, dtype=float)
    if A.ndim != 2 or min(A.shape) < 1:
        raise ValueError("payoff must be a non-empty 2D matrix")
    if not np.isfinite(A).all():
        raise ValueError("payoff contains NaN/Inf")

    nr, nc = A.shape
    scale = max(1e-6, float(np.max(np.abs(A))))
    if eta is None:
        eta = min(1.0, np.sqrt(2.0 * np.log(max(2, nr + nc)) / max(1, iterations))) / scale

    rp = _simplex(np.ones(nr) if row_prior is None else row_prior)
    cp = _simplex(np.ones(nc) if col_prior is None else col_prior)
    log_r = np.log(np.maximum(rp, 1e-15))
    log_c = np.log(np.maximum(cp, 1e-15))
    avg_r = np.zeros(nr)
    avg_c = np.zeros(nc)

    for t in range(1, int(iterations) + 1):
        r = _softmax(log_r)
        c = _softmax(log_c)
        avg_r += r
        avg_c += c

        row_values = A @ c
        col_row_values = r @ A
        # Row player maximizes A, column player minimizes A.
        log_r += eta * row_values
        log_c -= eta * col_row_values
        # Translation does not alter softmax, but prevents numerical drift.
        log_r -= np.max(log_r)
        log_c -= np.max(log_c)

    row_mix = _simplex(avg_r)
    col_mix = _simplex(avg_c)
    lower = float(np.min(row_mix @ A))
    upper = float(np.max(A @ col_mix))
    value = 0.5 * (lower + upper)
    return {
        "row_mix": row_mix.tolist(),
        "col_mix": col_mix.tolist(),
        "value": value,
        "lower_bound": lower,
        "upper_bound": upper,
        "duality_gap": max(0.0, upper - lower),
        "iterations": int(iterations),
        "eta": float(eta),
    }


def robust_population_mix(payoff, opponent_prior=None, equilibrium_weight=0.40, temperature=0.03,
                          iterations=12000):
    """Blend current-population exploitation with a maximin equilibrium prior.

    ``equilibrium_weight=0`` is aggressively exploitative.  Values near 1 are
    increasingly meta-shift resistant.  The returned policy mixture is meant
    to become the *prior* used by the live confidence-gated selector, not a
    requirement to randomize low-level actions every turn.
    """
    A = np.asarray(payoff, dtype=float)
    nr, nc = A.shape
    q = _simplex(np.ones(nc) if opponent_prior is None else opponent_prior)
    eq = solve_zero_sum(A, iterations=iterations, col_prior=q)
    eq_mix = np.asarray(eq["row_mix"], dtype=float)

    expected = A @ q
    tau = max(1e-6, float(temperature))
    exploit_mix = _softmax((expected - np.max(expected)) / tau)
    lam = float(np.clip(equilibrium_weight, 0.0, 1.0))
    mix = _simplex((1.0 - lam) * exploit_mix + lam * eq_mix)

    worst = float(np.min(mix @ A))
    mean = float(mix @ A @ q)
    return {
        "policy_mixture": mix.tolist(),
        "opponent_prior": q.tolist(),
        "expected_meta_value": mean,
        "worst_archetype_value": worst,
        "equilibrium_weight": lam,
        "equilibrium": eq,
        "per_policy_expected_value": expected.tolist(),
    }


def payoff_from_results(results, policy_col="policy", opponent_col="opponent_archetype",
                        score_col="score", shrink=8.0):
    """Create a smoothed policy x archetype payoff matrix from episode results.

    ``score`` should be 1 for win, .5 tie, 0 loss.  A Beta prior centered at
    .5 prevents tiny matchup cells from looking absurdly strong.  Returned
    payoffs are centered around zero so +.1 means roughly 60% win rate.
    """
    import pandas as pd

    if results.empty:
        raise ValueError("results is empty")
    policies = sorted(results[policy_col].dropna().astype(str).unique())
    opponents = sorted(results[opponent_col].dropna().astype(str).unique())
    A = np.zeros((len(policies), len(opponents)), dtype=float)
    N = np.zeros_like(A)
    for i, p in enumerate(policies):
        for j, o in enumerate(opponents):
            x = results[(results[policy_col].astype(str) == p) &
                        (results[opponent_col].astype(str) == o)]
            vals = pd.to_numeric(x[score_col], errors="coerce").dropna().to_numpy(float)
            n = len(vals)
            wr = (float(vals.sum()) + 0.5 * shrink) / (n + shrink)
            A[i, j] = wr - 0.5
            N[i, j] = n
    return policies, opponents, A, N


def save_meta_artifact(path, policy_names, archetype_names, payoff, result):
    obj = {
        "policy_names": list(map(str, policy_names)),
        "archetype_names": list(map(str, archetype_names)),
        "payoff": np.asarray(payoff, dtype=float).tolist(),
        **result,
    }
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True))
    return obj
