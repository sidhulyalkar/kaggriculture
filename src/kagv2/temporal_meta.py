from __future__ import annotations

"""Offline temporal-opponent training utilities.

The goal is not to identify a player once.  It is to learn *strategy segments*
inside an episode and a runtime model that can notice when an opponent moves
from one segment to another.

Runtime features are restricted to public opponent state deltas.  Opponent
actual actions are used only offline as an oracle for discovering interpretable
motifs and are never required by the submitted agent.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from .constants import PRODUCTS, CROPS, ANIMALS


PUBLIC_BASE = ["money", "hands", "quadrants", "pasture", "coop"]
PUBLIC_BASE += [f"crop_{c}" for c in CROPS]
PUBLIC_BASE += [f"animal_{a}" for a in ANIMALS]
PUBLIC_BASE += [f"market_inv_{p}" for p in PRODUCTS]

# These are true opponent actions available in replay files.  They define the
# latent motif more cleanly than public state alone, but are never exported as
# runtime features.
ORACLE_ACTIONS = ["market_HIRE", "market_BUY_LAND"]
ORACLE_ACTIONS += [f"buy_seed_{c}" for c in CROPS]
ORACLE_ACTIONS += [f"buy_animal_{a}" for a in ANIMALS]
ORACLE_ACTIONS += [f"sell_{p}" for p in PRODUCTS]
ORACLE_ACTIONS += [f"buy_product_{p}" for p in PRODUCTS]
ORACLE_ACTIONS += ["unit_WATER", "unit_FEED", "unit_HARVEST", "unit_CARE", "unit_PLANT"]


@dataclass
class TemporalTrainingResult:
    artifact: dict
    segment_frame: pd.DataFrame
    metrics: dict


def _opp_join(turn_df: pd.DataFrame) -> pd.DataFrame:
    """Attach the opponent row from the same replay turn.

    The returned frame is still from the current player's perspective, but now
    contains `opp_action_*` columns that are legal for offline motif discovery.
    """
    d = turn_df.copy()
    keys = ["episode_id", "step", "player"]
    cols = [c for c in ORACLE_ACTIONS if c in d.columns]
    meta = [c for c in ("submission_id", "team_name") if c in d.columns]
    opp = d[keys + cols + meta].copy()
    opp["player"] = 1 - opp["player"].astype(int)
    ren = {c: "opp_action_" + c for c in cols}
    ren.update({c: "opp_" + c for c in meta})
    opp = opp.rename(columns=ren)
    return d.merge(opp, on=keys, how="left")


def temporal_runtime_frame(turn_df: pd.DataFrame, smooth: int = 8) -> pd.DataFrame:
    """Build public temporal features that can be reproduced online."""
    d = _opp_join(turn_df).sort_values(["episode_id", "player", "step"]).copy()
    groups = d.groupby(["episode_id", "player"], sort=False)
    runtime = []
    for base in PUBLIC_BASE:
        src = "opp_" + base if "opp_" + base in d.columns else base
        if src not in d.columns:
            continue
        delta = groups[src].diff().fillna(0.0).astype(float)
        # Money has a much larger natural scale than structural counts.
        if base == "money":
            delta = delta / 1000.0
        elif base.startswith("market_inv_"):
            delta = delta / 25.0
        name = "d_" + base.replace("crop_", "count_").replace("animal_", "count_")
        d[name] = delta
        d[name + "_ewm"] = groups[name].transform(lambda s: s.ewm(alpha=2.0 / (smooth + 1.0), adjust=False).mean())
        runtime.append(name + "_ewm")
    d.attrs["runtime_features"] = runtime
    return d


def _oracle_frame(d: pd.DataFrame, smooth: int = 8) -> list[str]:
    groups = d.groupby(["episode_id", "player"], sort=False)
    cols = []
    for c in [x for x in d.columns if x.startswith("opp_action_")]:
        name = c + "_ewm"
        d[name] = groups[c].transform(lambda s: s.fillna(0.0).astype(float).ewm(alpha=2.0 / (smooth + 1.0), adjust=False).mean())
        cols.append(name)
    return cols


def _change_points_one(x: np.ndarray, threshold: float = 3.2, min_gap: int = 12) -> np.ndarray:
    """Robust multivariate CUSUM segmentation used as an offline teacher.

    This is intentionally dependency-light.  It finds persistent departures in
    the smoothed opponent trajectory and creates candidate segment boundaries.
    """
    if len(x) == 0:
        return np.zeros(0, dtype=int)
    med = np.nanmedian(x, axis=0)
    mad = np.nanmedian(np.abs(x - med), axis=0)
    scale = np.where(mad > 1e-5, 1.4826 * mad, 1.0)
    z = np.nan_to_num((x - med) / scale)
    seg = np.zeros(len(x), dtype=int)
    center = z[0].copy()
    cusum = 0.0
    last = 0
    sid = 0
    for i in range(1, len(z)):
        dist = float(np.mean(np.sort(np.abs(z[i] - center))[-min(6, z.shape[1]):]))
        cusum = max(0.0, 0.84 * cusum + max(0.0, dist - 0.65))
        if cusum >= threshold and i - last >= min_gap:
            sid += 1
            last = i
            center = z[i].copy()
            cusum = 0.0
        else:
            center = 0.94 * center + 0.06 * z[i]
        seg[i] = sid
    return seg


def discover_segments(turn_df: pd.DataFrame, smooth: int = 8, threshold: float = 3.2, min_gap: int = 12) -> pd.DataFrame:
    d = temporal_runtime_frame(turn_df, smooth=smooth)
    runtime = list(d.attrs.get("runtime_features") or [])
    oracle = _oracle_frame(d, smooth=smooth)
    d["segment_local"] = 0
    for _, idx in d.groupby(["episode_id", "player"], sort=False).groups.items():
        ix = list(idx)
        x = d.loc[ix, runtime].fillna(0.0).to_numpy(float)
        d.loc[ix, "segment_local"] = _change_points_one(x, threshold=threshold, min_gap=min_gap)
    d["segment_id"] = (
        d["episode_id"].astype(str) + ":" + d["player"].astype(str) + ":" + d["segment_local"].astype(int).astype(str)
    )
    d.attrs["runtime_features"] = runtime
    d.attrs["oracle_features"] = oracle
    return d


def segment_summaries(segmented: pd.DataFrame) -> pd.DataFrame:
    runtime = list(segmented.attrs.get("runtime_features") or [])
    oracle = list(segmented.attrs.get("oracle_features") or [])
    agg = {c: "mean" for c in runtime + oracle}
    agg.update({"step": ["min", "max", "count"]})
    if "opp_submission_id" in segmented.columns:
        agg["opp_submission_id"] = "first"
    if "opp_team_name" in segmented.columns:
        agg["opp_team_name"] = "first"
    out = segmented.groupby("segment_id", sort=False).agg(agg)
    out.columns = ["_".join(x).rstrip("_") if isinstance(x, tuple) else x for x in out.columns]
    return out.reset_index()


def _transition_matrix(segmented: pd.DataFrame, labels: dict[str, int], n: int, smoothing: float = 0.5):
    mat = np.full((n, n), float(smoothing))
    first = np.full(n, float(smoothing))
    for _, g in segmented.groupby(["episode_id", "player"], sort=False):
        ids = g.sort_values("step")["segment_id"].drop_duplicates().tolist()
        ys = [labels[x] for x in ids if x in labels]
        if ys:
            first[ys[0]] += 1
        for a, b in zip(ys, ys[1:]):
            mat[a, b] += 1
    mat /= mat.sum(axis=1, keepdims=True)
    first /= first.sum()
    return mat, first


def _name_motif(row: pd.Series) -> str:
    """Give clusters readable names from offline action composition."""
    def v(fragment):
        vals = [float(row[c]) for c in row.index if fragment in str(c)]
        return sum(vals)
    hire = v("opp_action_market_HIRE")
    land = v("opp_action_market_BUY_LAND")
    seed = v("opp_action_buy_seed_")
    animal = v("opp_action_buy_animal_")
    sell = v("opp_action_sell_")
    buy = v("opp_action_buy_product_")
    if land > 0.08 or hire > 0.65:
        return "EXPANSION"
    if animal > 0.20:
        return "ANIMAL_BUILD"
    if seed > 0.55:
        return "CROP_BUILD"
    if sell > 2.0:
        return "LIQUIDATION"
    if buy > 0.8:
        return "INPUT_ACCUMULATION"
    return "OPERATIONS"


def train_temporal_motifs(turn_df: pd.DataFrame, n_motifs: int = 8, smooth: int = 8, seed: int = 20260820) -> TemporalTrainingResult:
    segmented = discover_segments(turn_df, smooth=smooth)
    runtime = list(segmented.attrs.get("runtime_features") or [])
    oracle = list(segmented.attrs.get("oracle_features") or [])
    summaries = segment_summaries(segmented)
    runtime_cols = [c + "_mean" for c in runtime if c + "_mean" in summaries]
    oracle_cols = [c + "_mean" for c in oracle if c + "_mean" in summaries]
    if len(summaries) < max(12, n_motifs * 2):
        raise ValueError(f"Need more strategy segments; got {len(summaries)}")

    # Discover motifs from both public trajectory and replay-only action style.
    discovery_cols = runtime_cols + oracle_cols
    scaler = StandardScaler().fit(summaries[discovery_cols].fillna(0.0))
    Z = scaler.transform(summaries[discovery_cols].fillna(0.0))
    km = KMeans(n_clusters=n_motifs, random_state=seed, n_init=30).fit(Z)
    summaries["motif"] = km.labels_

    # Runtime centroids use only legal online features.  Standardization is
    # exported so submission code can stay dependency-free.
    runtime_scaler = StandardScaler().fit(summaries[runtime_cols].fillna(0.0))
    R = runtime_scaler.transform(summaries[runtime_cols].fillna(0.0))
    centers = []
    motifs = []
    for k in range(n_motifs):
        mask = summaries["motif"].to_numpy() == k
        centers.append(R[mask].mean(axis=0).tolist())
        oracle_mean = summaries.loc[mask, oracle_cols].mean(axis=0) if oracle_cols else pd.Series(dtype=float)
        motifs.append({"name": _name_motif(oracle_mean), "center": centers[-1], "segments": int(mask.sum())})

    label_map = dict(zip(summaries["segment_id"], summaries["motif"].astype(int)))
    transition, prior = _transition_matrix(segmented, label_map, n_motifs)

    # Actor-held-out stability diagnostic.  We do not expect perfect identity
    # classification; we want the discovered phase vocabulary to remain useful
    # when entire opponent submissions are withheld.
    actor_col = "opp_submission_id_first" if "opp_submission_id_first" in summaries else None
    stability = None
    if actor_col and summaries[actor_col].nunique(dropna=True) >= 8:
        groups = summaries[actor_col].astype(str).to_numpy()
        tr, va = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=seed).split(summaries, groups=groups))
        km2 = KMeans(n_clusters=n_motifs, random_state=seed + 1, n_init=20).fit(Z[tr])
        # ARI is label-permutation invariant and is used only as a vocabulary
        # stability diagnostic, not as the promotion objective.
        y2 = km2.predict(Z[va])
        stability = float(adjusted_rand_score(km.labels_[va], y2))

    artifact = {
        "version": 1,
        "kind": "temporal_opponent_motifs",
        "features": [c[:-5] if c.endswith("_mean") else c for c in runtime_cols],
        "mean": runtime_scaler.mean_.tolist(),
        "scale": runtime_scaler.scale_.tolist(),
        "motifs": motifs,
        "transition": transition.tolist(),
        "prior": prior.tolist(),
        "temperature": 1.0,
        "short_alpha": 0.45,
        "long_alpha": 0.08,
        "hazard": 0.025,
        "change_threshold": 0.78,
        "confirm_steps": 3,
        "motif_confidence": 0.45,
        "training": {
            "segments": int(len(summaries)),
            "episodes": int(segmented["episode_id"].nunique()),
            "smooth": int(smooth),
            "n_motifs": int(n_motifs),
            "actor_holdout_vocab_ari": stability,
        },
    }
    metrics = dict(artifact["training"])
    return TemporalTrainingResult(artifact=artifact, segment_frame=summaries, metrics=metrics)


def save_temporal_artifact(path, result: TemporalTrainingResult):
    Path(path).write_text(json.dumps(result.artifact, indent=2, sort_keys=True))
    return result.artifact
