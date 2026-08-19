from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder


@dataclass(frozen=True)
class RegimeMetrics:
    auc: float | None
    brier: float
    loss_rate: float
    top_quartile_loss_rate: float
    lift_at_quartile: float
    n_rows: int
    n_groups: int

    def to_dict(self) -> dict:
        return asdict(self)


def regime_feature_columns(
    df: pd.DataFrame,
    *,
    include_opponent: bool = True,
    include_early_state: bool = True,
) -> tuple[list[str], list[str]]:
    """Return runtime-legal regime features and exclude terminal identifiers."""
    numeric: list[str] = []
    categorical: list[str] = []
    if "seat" in df.columns:
        numeric.append("seat")
    for col in df.columns:
        if col.startswith("demand_"):
            numeric.append(col)
        elif include_early_state and (
            col.startswith("cash_margin_")
            or col.startswith("our_weeds_")
            or col.startswith("opp_weeds_")
        ):
            numeric.append(col)
        elif col.startswith("shop_") and col != "shop_sequence":
            categorical.append(col)
    if include_opponent and "opponent" in df.columns:
        categorical.insert(0, "opponent")
    return list(dict.fromkeys(numeric)), list(dict.fromkeys(categorical))


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    transformers = []
    if numeric:
        transformers.append(("num", "passthrough", numeric))
    if categorical:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical))
    if not transformers:
        raise ValueError("No regime features were found")
    return ColumnTransformer(transformers, remainder="drop")


def grouped_oof_regime_predictions(
    games: pd.DataFrame,
    *,
    group_col: str = "seed",
    score_col: str = "score",
    n_splits: int = 8,
    random_state: int = 20260819,
    include_opponent: bool = True,
    include_early_state: bool = True,
) -> tuple[pd.DataFrame, RegimeMetrics]:
    """Estimate loss risk with entire seeds held out from every training fold."""
    if games.empty:
        raise ValueError("games is empty")
    if group_col not in games or score_col not in games:
        raise KeyError(f"Need {group_col!r} and {score_col!r}")
    d = games.copy().reset_index(drop=True)
    d["loss_target"] = (pd.to_numeric(d[score_col], errors="coerce") < 0.5).astype(int)
    numeric, categorical = regime_feature_columns(
        d,
        include_opponent=include_opponent,
        include_early_state=include_early_state,
    )
    groups = d[group_col].astype(str).to_numpy()
    unique_groups = np.unique(groups)
    splits = min(int(n_splits), len(unique_groups))
    if splits < 2:
        raise ValueError("Need at least two unique groups for OOF validation")
    pred = np.full(len(d), np.nan, dtype=float)
    cv = GroupKFold(n_splits=splits)
    X = d[numeric + categorical]
    y = d["loss_target"].to_numpy(int)
    for fold, (tr, va) in enumerate(cv.split(X, y, groups=groups)):
        pre = _preprocessor(numeric, categorical)
        Xtr = pre.fit_transform(X.iloc[tr])
        Xva = pre.transform(X.iloc[va])
        ytr = y[tr]
        if np.unique(ytr).size < 2:
            pred[va] = float(np.mean(ytr))
            continue
        model = ExtraTreesClassifier(
            n_estimators=192,
            max_depth=12,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=random_state + fold,
            n_jobs=-1,
        )
        model.fit(Xtr, ytr)
        pred[va] = model.predict_proba(Xva)[:, 1]
    if np.isnan(pred).any():
        raise RuntimeError("OOF regime predictions contain NaNs")
    d["loss_prob_oof"] = pred
    auc = float(roc_auc_score(y, pred)) if np.unique(y).size > 1 else None
    brier = float(brier_score_loss(y, pred))
    loss_rate = float(np.mean(y))
    cutoff = float(np.quantile(pred, 0.75))
    top = y[pred >= cutoff]
    top_rate = float(np.mean(top)) if len(top) else loss_rate
    metrics = RegimeMetrics(
        auc=auc,
        brier=brier,
        loss_rate=loss_rate,
        top_quartile_loss_rate=top_rate,
        lift_at_quartile=float(top_rate / max(loss_rate, 1e-12)),
        n_rows=len(d),
        n_groups=len(unique_groups),
    )
    return d, metrics


def hard_seed_table(
    games_with_predictions: pd.DataFrame,
    *,
    seed_col: str = "seed",
    score_col: str = "score",
    prediction_col: str = "loss_prob_oof",
) -> pd.DataFrame:
    d = games_with_predictions.copy()
    agg = d.groupby(seed_col).agg(
        score=(score_col, "mean"),
        mean_loss_risk=(prediction_col, "mean"),
        losses=(score_col, lambda x: int((pd.to_numeric(x) < 0.5).sum())),
        games=(score_col, "size"),
    )
    return agg.reset_index().sort_values(["score", "mean_loss_risk"], ascending=[True, False])
