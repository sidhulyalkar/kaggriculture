from __future__ import annotations

"""Behavioral event mining for ladder archetypes.

Raw 720-turn action traces are dominated by routing noise.  This module instead
extracts *conditional reactions* around economically meaningful events: price
crashes/spikes and abrupt market inventory changes.  The resulting profiles
answer questions like "when strawberry crashes, does this submission hold,
dump, replant, hire, or change land composition?"
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .constants import PRODUCTS, CROPS, ANIMALS, BASE


def _actor_column(df):
    for c in ("submission_id", "team_name"):
        if c in df and df[c].notna().any():
            return c
    return "player"


def attach_strength_weights(events: pd.DataFrame, bt_strength: pd.DataFrame | None,
                            actor_col: str | None = None) -> pd.DataFrame:
    out = events.copy()
    actor_col = actor_col or _actor_column(out)
    out["strength_weight"] = 1.0
    if bt_strength is None or bt_strength.empty or actor_col not in out:
        return out
    b = bt_strength.copy()
    key = "actor" if "actor" in b else actor_col if actor_col in b else None
    if key is None or "bt_strength" not in b:
        return out
    m = dict(zip(b[key].astype(str), pd.to_numeric(b["bt_strength"], errors="coerce").fillna(0)))
    s = out[actor_col].astype(str).map(m).fillna(0).to_numpy(float)
    # Smoothly emphasize strong actors without letting one giant rating own a cluster.
    out["strength_weight"] = np.clip(np.exp(np.clip(s, -3, 3)), 0.15, 12.0)
    return out


def extract_reaction_events(turn_df: pd.DataFrame, price_threshold=0.12,
                            inventory_threshold=35, post_turns=12) -> pd.DataFrame:
    """Extract state -> reaction summaries around high-variance market events."""
    if turn_df.empty:
        return pd.DataFrame()
    d = turn_df.sort_values(["episode_id", "player", "step"]).copy()
    actor_col = _actor_column(d)
    rows = []

    for (episode_id, player), g in d.groupby(["episode_id", "player"], sort=False):
        g = g.sort_values("step").reset_index(drop=True)
        actor = g[actor_col].iloc[0] if actor_col in g else player
        for prod in PRODUCTS:
            pc = f"price_{prod}"
            ic = f"market_inv_{prod}"
            if pc not in g or ic not in g:
                continue
            price = pd.to_numeric(g[pc], errors="coerce").ffill().fillna(BASE[prod]).to_numpy(float)
            inv = pd.to_numeric(g[ic], errors="coerce").ffill().fillna(10000).to_numpy(float)
            prev = np.r_[price[0], price[:-1]]
            pct = (price - prev) / np.maximum(1.0, prev)
            dinv = np.r_[0.0, np.diff(inv)]

            candidates = []
            candidates.extend((i, "price_crash", abs(float(pct[i]))) for i in np.where(pct <= -price_threshold)[0])
            candidates.extend((i, "price_spike", abs(float(pct[i]))) for i in np.where(pct >= price_threshold)[0])
            candidates.extend((i, "market_flood", float(dinv[i]) / max(1.0, inventory_threshold))
                              for i in np.where(dinv >= inventory_threshold)[0])
            candidates.extend((i, "market_drain", float(-dinv[i]) / max(1.0, inventory_threshold))
                              for i in np.where(dinv <= -inventory_threshold)[0])

            # De-duplicate adjacent detections from the same shock; keep the strongest.
            last_by_kind = {}
            for i, kind, sev in sorted(candidates, key=lambda z: (z[0], z[1])):
                last = last_by_kind.get(kind)
                if last is not None and i - last < 3:
                    continue
                last_by_kind[kind] = i
                end = min(len(g), i + 1 + int(post_turns))
                future = g.iloc[i + 1:end]
                if future.empty:
                    continue
                r = {
                    "episode_id": episode_id,
                    "player": int(player),
                    actor_col: actor,
                    "step": int(g.iloc[i]["step"]),
                    "day": int(g.iloc[i].get("day", 0)),
                    "hour": int(g.iloc[i].get("hour", 0)),
                    "event_type": f"{kind}:{prod}",
                    "event_product": prod,
                    "event_kind": kind,
                    "severity": float(sev),
                    "pre_price_ratio": float(price[i] / BASE[prod]),
                    "pre_market_delta": float((inv[i] - 10000) / 500.0),
                    "post_turns": int(len(future)),
                }
                for p in PRODUCTS:
                    c = f"sell_{p}"
                    r[f"react_sell_{p}"] = float(pd.to_numeric(future.get(c, 0), errors="coerce").fillna(0).sum()) if c in future else 0.0
                for c in CROPS:
                    pcrop = f"plant_{c}"
                    r[f"react_plant_{c}"] = float(pd.to_numeric(future.get(pcrop, 0), errors="coerce").fillna(0).sum()) if pcrop in future else 0.0
                    statec = f"crop_{c}"
                    if statec in g:
                        r[f"delta_crop_{c}"] = float(future[statec].iloc[-1] - g.iloc[i][statec])
                for a in ANIMALS:
                    bac = f"buy_animal_{a}"
                    r[f"react_buy_animal_{a}"] = float(pd.to_numeric(future.get(bac, 0), errors="coerce").fillna(0).sum()) if bac in future else 0.0
                for c in ("market_HIRE", "market_BUY_LAND", "unit_WATER", "unit_HARVEST", "unit_FEED", "unit_CARE"):
                    r[f"react_{c}"] = float(pd.to_numeric(future.get(c, 0), errors="coerce").fillna(0).sum()) if c in future else 0.0
                r["delta_quadrants"] = float(future["quadrants"].iloc[-1] - g.iloc[i]["quadrants"]) if "quadrants" in g else 0.0
                r["peak_hands"] = float(pd.to_numeric(future.get("hands", 0), errors="coerce").fillna(0).max()) if "hands" in future else 0.0
                if "win_target" in g:
                    r["win_target"] = float(g.iloc[i].get("win_target", np.nan))
                if "final_reward" in g:
                    r["final_reward"] = float(g.iloc[i].get("final_reward", np.nan))
                rows.append(r)
    return pd.DataFrame(rows)


def reaction_profiles(events: pd.DataFrame, bt_strength: pd.DataFrame | None = None,
                      min_events=3) -> pd.DataFrame:
    """Aggregate event-conditioned response signatures per submission/team."""
    if events.empty:
        return pd.DataFrame()
    actor_col = _actor_column(events)
    e = attach_strength_weights(events, bt_strength, actor_col)
    response_cols = [c for c in e.columns if c.startswith(("react_", "delta_", "peak_"))]
    rows = []
    for actor, g in e.groupby(actor_col, dropna=False):
        if len(g) < min_events:
            continue
        row = {actor_col: actor, "reaction_events": int(len(g)),
               "strength_weight": float(g["strength_weight"].mean())}
        for et, x in g.groupby("event_type"):
            if len(x) < 2:
                continue
            w = x["strength_weight"].to_numpy(float)
            for c in response_cols:
                vals = pd.to_numeric(x[c], errors="coerce").fillna(0).to_numpy(float)
                row[f"{et}|{c}"] = float(np.average(vals, weights=w))
        rows.append(row)
    return pd.DataFrame(rows)


def fit_reaction_archetypes(profiles: pd.DataFrame, n_clusters=6, random_state=20260817):
    """Strength-weighted KMeans over conditional reaction signatures."""
    if profiles.empty:
        raise ValueError("reaction profiles are empty")
    actor_col = _actor_column(profiles)
    meta = {actor_col, "reaction_events", "strength_weight"}
    feat = [c for c in profiles.columns if c not in meta and pd.api.types.is_numeric_dtype(profiles[c])]
    if not feat:
        raise ValueError("no numeric reaction features")
    X = profiles[feat].fillna(0).to_numpy(float)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    k = min(int(n_clusters), len(profiles))
    if k < 2:
        raise ValueError("need at least two profiles to cluster")
    km = KMeans(n_clusters=k, n_init=30, random_state=random_state)
    weights = np.maximum(0.05, pd.to_numeric(profiles["strength_weight"], errors="coerce").fillna(1).to_numpy(float))
    km.fit(Xs, sample_weight=weights)
    out = profiles.copy()
    out["reaction_archetype"] = km.labels_
    model = {
        "features": feat,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "centroids": km.cluster_centers_.tolist(),
        "actor_col": actor_col,
    }
    return out, model
