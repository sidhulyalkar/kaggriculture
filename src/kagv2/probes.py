from __future__ import annotations

"""Active market probing research utilities.

Market feints are *experimental*.  A Kaggriculture player may SELL every
product, but can only BUY WHEAT/FERTILIZER from the product market.  Therefore
"dump then scoop back cheap strawberries" is not a legal strategy.  The useful
form of probing is narrower: spend a few units to move a shared price across a
suspected opponent threshold, observe their *next-turn* reaction, and update
the opponent model.  Nothing in this module is enabled in the live agent by
default.
"""

import numpy as np
import pandas as pd

from .constants import PRODUCTS, BASE
from .simulator import market_price


def threshold_reactivity(turn_df: pd.DataFrame, product: str, bins=24, min_bin=20):
    """Estimate discontinuities in opponent next-turn sell behavior by price band.

    Requires ``opp_sell_next1_<PRODUCT>`` labels (create them with
    ``add_future_opponent_sell_labels(..., horizon=1)``).  Large adjacent-band
    jumps are candidates for hard-coded opponent sell thresholds.
    """
    product = str(product).upper()
    if product not in PRODUCTS:
        raise ValueError(product)
    target = f"opp_sell_next1_{product}"
    price_col = f"price_{product}"
    if target not in turn_df or price_col not in turn_df:
        raise KeyError(f"need {target} and {price_col}")
    d = turn_df[[price_col, target]].copy()
    d["price_ratio"] = pd.to_numeric(d[price_col], errors="coerce") / BASE[product]
    d["opp_sell"] = pd.to_numeric(d[target], errors="coerce").fillna(0)
    d = d[np.isfinite(d["price_ratio"])].copy()
    if d.empty:
        return pd.DataFrame()
    lo, hi = float(d.price_ratio.quantile(.01)), float(d.price_ratio.quantile(.99))
    if hi <= lo:
        return pd.DataFrame()
    edges = np.linspace(lo, hi, int(bins) + 1)
    d["band"] = pd.cut(d.price_ratio, edges, include_lowest=True, duplicates="drop")
    agg = d.groupby("band", observed=True).agg(
        n=("opp_sell", "size"),
        price_ratio=("price_ratio", "mean"),
        sell_probability=("opp_sell", lambda x: float(np.mean(np.asarray(x) > 0))),
        mean_sell=("opp_sell", "mean"),
    ).reset_index(drop=True)
    agg = agg[agg.n >= int(min_bin)].sort_values("price_ratio").reset_index(drop=True)
    if agg.empty:
        return agg
    agg["prob_jump"] = agg.sell_probability.diff().fillna(0)
    agg["mean_sell_jump"] = agg.mean_sell.diff().fillna(0)
    # A threshold score favors abrupt probability changes supported by data.
    agg["threshold_score"] = (
        agg.prob_jump.abs() * np.sqrt(np.maximum(1, agg.n)) +
        .15 * agg.mean_sell_jump.abs() / np.maximum(1.0, agg.mean_sell.abs().median())
    )
    return agg


def feint_inventory_impact(product: str, inventory: int, units: int):
    """Exact public-engine price path for selling ``units`` into the market."""
    product = str(product).upper()
    if product not in PRODUCTS:
        raise ValueError(product)
    inv = int(inventory)
    units = max(0, int(units))
    prices = []
    revenue = 0
    for _ in range(units):
        p = int(market_price(product, inv))
        prices.append(p)
        revenue += p
        inv += 1
    return {
        "product": product,
        "units": units,
        "inventory_before": int(inventory),
        "inventory_after": inv,
        "price_before": int(market_price(product, int(inventory))),
        "price_after": int(market_price(product, inv)),
        "quoted_prices": prices,
        "revenue": int(revenue),
    }


def rank_probe_candidates(market_inventory: dict, shed: dict, threshold_tables: dict,
                          max_units=4, min_score=.35, max_price_move=.18):
    """Rank tiny sell probes that could cross a learned response discontinuity.

    This deliberately returns *research candidates*, not actions.  Promotion
    should require simulator A/B evidence that information value exceeds the
    opportunity cost and that the opponent actually reacts on the next turn.
    """
    rows = []
    for product, table in threshold_tables.items():
        p = str(product).upper()
        if p not in PRODUCTS or table is None or len(table) == 0:
            continue
        qty = int((shed or {}).get(p, 0) or 0)
        if qty <= 0:
            continue
        inv = int((market_inventory or {}).get(p, 10000) or 10000)
        current = market_price(p, inv) / BASE[p]
        tab = table.sort_values("threshold_score", ascending=False)
        for r in tab.itertuples():
            score = float(getattr(r, "threshold_score", 0.0))
            if score < min_score:
                continue
            target = float(getattr(r, "price_ratio"))
            for units in range(1, min(int(max_units), qty) + 1):
                impact = feint_inventory_impact(p, inv, units)
                after = impact["price_after"] / BASE[p]
                crossed = (current - target) * (after - target) <= 0 and abs(after-current) > 1e-12
                move = abs(after-current)
                if crossed and move <= max_price_move:
                    rows.append({
                        **impact,
                        "current_ratio": float(current),
                        "target_ratio": target,
                        "price_move": float(move),
                        "threshold_score": score,
                        "sell_probability_jump": float(getattr(r, "prob_jump", 0.0)),
                    })
                    break
    return pd.DataFrame(rows).sort_values(["threshold_score", "units"], ascending=[False, True]) if rows else pd.DataFrame()


def probe_promotion_decision(control_scores, probe_scores, min_games=80, min_gain=.015):
    """Simple paired promotion guard for any future active-probe experiment."""
    a = np.asarray(control_scores, dtype=float)
    b = np.asarray(probe_scores, dtype=float)
    n = min(len(a), len(b))
    if n < min_games:
        return {"promote": False, "reason": "insufficient_games", "n": int(n)}
    delta = b[:n] - a[:n]
    mean = float(np.mean(delta))
    # Normal approximation is used only as a conservative experiment gate.
    se = float(np.std(delta, ddof=1) / np.sqrt(n)) if n > 1 else float("inf")
    lcb = mean - 1.96 * se
    return {"promote": bool(lcb > min_gain), "n": int(n), "mean_gain": mean,
            "se": se, "lower95": lcb, "required_gain": float(min_gain)}
