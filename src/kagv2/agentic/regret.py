from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder


DEFAULT_NUMERIC = (
    "base_margin",
    "base_score",
    "step",
    "day",
    "seat",
    "qty",
)
DEFAULT_CATEGORICAL = (
    "opponent",
    "op",
    "item",
    "mutation",
    "day_bucket",
)


@dataclass(frozen=True)
class RegretMetrics:
    auc_benefit: float | None
    mean_delta_mae: float
    positive_rate: float
    n_rows: int
    n_groups: int
    q10_coverage: float
    q90_coverage: float

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_vector(value) -> list[float] | None:
    if isinstance(value, (list, tuple, np.ndarray)):
        return [float(x) for x in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except Exception:
            return None
    return None


def expand_feature_vectors(df: pd.DataFrame, column: str = "features") -> pd.DataFrame:
    if column not in df.columns:
        return df.copy()
    parsed = [_parse_vector(v) for v in df[column]]
    widths = [len(v) for v in parsed if v is not None]
    if not widths:
        return df.copy()
    width = max(widths)
    out = df.copy()
    for i in range(width):
        out[f"state_{i}"] = [
            v[i] if v is not None and i < len(v) else np.nan for v in parsed
        ]
    return out


def prepare_counterfactuals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("counterfactual frame is empty")
    d = expand_feature_vectors(df).copy()
    if "ok" in d:
        d = d[d["ok"].astype(bool)]
    if "activated" in d:
        d = d[pd.to_numeric(d["activated"], errors="coerce").fillna(0) > 0]
    if "margin_delta" not in d:
        if {"margin", "base_margin"} <= set(d.columns):
            d["margin_delta"] = pd.to_numeric(d["margin"]) - pd.to_numeric(d["base_margin"])
        else:
            raise KeyError("Need margin_delta or margin/base_margin")
    d["benefit"] = (pd.to_numeric(d["margin_delta"], errors="coerce") > 0).astype(int)
    d["big_gain"] = (pd.to_numeric(d["margin_delta"], errors="coerce") >= 500).astype(int)
    event_cols = [
        c for c in ["opponent", "seed", "seat", "step", "index", "op", "item"]
        if c in d
    ]
    d["event_id"] = d[event_cols].fillna("").astype(str).agg("|".join, axis=1)
    return d.reset_index(drop=True)


def regret_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    numeric = [c for c in DEFAULT_NUMERIC if c in df]
    numeric.extend(sorted(c for c in df if c.startswith("state_")))
    categorical = [c for c in DEFAULT_CATEGORICAL if c in df]
    return list(dict.fromkeys(numeric)), list(dict.fromkeys(categorical))


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    parts = []
    if numeric:
        parts.append(("num", "passthrough", numeric))
    if categorical:
        parts.append((
            "cat",
            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            categorical,
        ))
    if not parts:
        raise ValueError("No counterfactual features available")
    return ColumnTransformer(parts, remainder="drop")


def grouped_oof_distributional_regret(
    counterfactuals: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("seed",),
    n_splits: int = 5,
    random_state: int = 20260819,
) -> tuple[pd.DataFrame, RegretMetrics]:
    """Fit OOF benefit probability and a return distribution.

    Validation is seed-isolated by default. Splitting the same seed across
    opponent families can leak regime information and make residual policies
    look substantially safer than they are.
    """
    d = prepare_counterfactuals(counterfactuals)
    numeric, categorical = regret_feature_columns(d)
    X = d[numeric + categorical]
    y_cls = d["benefit"].to_numpy(int)
    y_reg = pd.to_numeric(d["margin_delta"], errors="coerce").to_numpy(float)
    present_groups = [c for c in group_cols if c in d]
    if not present_groups:
        groups = np.arange(len(d)).astype(str)
    else:
        groups = d[present_groups].fillna("").astype(str).agg("|".join, axis=1).to_numpy()
    unique_groups = np.unique(groups)
    splits = min(int(n_splits), len(unique_groups))
    if splits < 2:
        raise ValueError("Need at least two independent groups")

    p = np.full(len(d), np.nan)
    mean = np.full(len(d), np.nan)
    q10 = np.full(len(d), np.nan)
    q50 = np.full(len(d), np.nan)
    q90 = np.full(len(d), np.nan)
    cv = GroupKFold(n_splits=splits)
    for fold, (tr, va) in enumerate(cv.split(X, y_cls, groups=groups)):
        pre = _preprocessor(numeric, categorical)
        Xtr = pre.fit_transform(X.iloc[tr])
        Xva = pre.transform(X.iloc[va])
        if np.unique(y_cls[tr]).size < 2:
            p[va] = float(np.mean(y_cls[tr]))
        else:
            clf = ExtraTreesClassifier(
                n_estimators=256,
                max_depth=12,
                min_samples_leaf=2,
                max_features=0.8,
                class_weight="balanced",
                random_state=random_state + fold,
                n_jobs=-1,
            )
            clf.fit(Xtr, y_cls[tr])
            p[va] = clf.predict_proba(Xva)[:, 1]
        reg = ExtraTreesRegressor(
            n_estimators=256,
            max_depth=12,
            min_samples_leaf=2,
            max_features=0.8,
            random_state=random_state + 100 + fold,
            n_jobs=-1,
        )
        reg.fit(Xtr, y_reg[tr])
        tree_pred = np.vstack([tree.predict(Xva) for tree in reg.estimators_])
        mean[va] = tree_pred.mean(axis=0)
        q10[va] = np.quantile(tree_pred, 0.10, axis=0)
        q50[va] = np.quantile(tree_pred, 0.50, axis=0)
        q90[va] = np.quantile(tree_pred, 0.90, axis=0)
    if any(np.isnan(x).any() for x in (p, mean, q10, q50, q90)):
        raise RuntimeError("OOF regret predictions contain NaNs")

    out = d.copy()
    out["p_benefit_oof"] = p
    out["pred_mean_delta_oof"] = mean
    out["pred_q10_oof"] = q10
    out["pred_q50_oof"] = q50
    out["pred_q90_oof"] = q90
    out["risk_adjusted_oof"] = q10 + 0.25 * mean
    auc = float(roc_auc_score(y_cls, p)) if np.unique(y_cls).size > 1 else None
    metrics = RegretMetrics(
        auc_benefit=auc,
        mean_delta_mae=float(mean_absolute_error(y_reg, mean)),
        positive_rate=float(np.mean(y_cls)),
        n_rows=len(out),
        n_groups=len(unique_groups),
        q10_coverage=float(np.mean(y_reg >= q10)),
        q90_coverage=float(np.mean(y_reg <= q90)),
    )
    return out, metrics


def residual_threshold_sweep(
    oof: pd.DataFrame,
    *,
    p_thresholds: Iterable[float] = (0.70, 0.80, 0.90, 0.95),
    mean_thresholds: Iterable[float] = (0.0, 250.0, 500.0, 1000.0),
    q10_floors: Iterable[float] = (-500.0, -100.0, 0.0),
) -> pd.DataFrame:
    """Evaluate conservative OOF intervention gates without touching the ladder."""
    rows = []
    d = oof.copy()
    for pt in p_thresholds:
        for mt in mean_thresholds:
            for qf in q10_floors:
                eligible = d[
                    (d["p_benefit_oof"] >= pt)
                    & (d["pred_mean_delta_oof"] >= mt)
                    & (d["pred_q10_oof"] >= qf)
                ].copy()
                if eligible.empty:
                    rows.append({
                        "p_threshold": pt,
                        "mean_threshold": mt,
                        "q10_floor": qf,
                        "selected_events": 0,
                        "selection_rate": 0.0,
                        "positive_rate": np.nan,
                        "mean_realized_delta": np.nan,
                        "median_realized_delta": np.nan,
                        "total_realized_delta": 0.0,
                    })
                    continue
                idx = eligible.groupby("event_id")["risk_adjusted_oof"].idxmax()
                chosen = eligible.loc[idx]
                rows.append({
                    "p_threshold": pt,
                    "mean_threshold": mt,
                    "q10_floor": qf,
                    "selected_events": int(len(chosen)),
                    "selection_rate": float(len(chosen) / max(1, d["event_id"].nunique())),
                    "positive_rate": float(np.mean(chosen["margin_delta"] > 0)),
                    "mean_realized_delta": float(chosen["margin_delta"].mean()),
                    "median_realized_delta": float(chosen["margin_delta"].median()),
                    "total_realized_delta": float(chosen["margin_delta"].sum()),
                })
    return pd.DataFrame(rows).sort_values(
        ["mean_realized_delta", "positive_rate", "selected_events"],
        ascending=[False, False, False],
    )


def residual_library(oof: pd.DataFrame, min_support: int = 4) -> pd.DataFrame:
    """Summarize intervention families using only out-of-fold predictions."""
    keys = [c for c in ["op", "item", "mutation", "day_bucket"] if c in oof]
    if not keys:
        raise ValueError("No intervention identity columns")
    g = oof.groupby(keys, dropna=False).agg(
        support=("margin_delta", "size"),
        realized_mean=("margin_delta", "mean"),
        realized_positive=("benefit", "mean"),
        predicted_mean=("pred_mean_delta_oof", "mean"),
        predicted_q10=("pred_q10_oof", "mean"),
        predicted_p=("p_benefit_oof", "mean"),
    ).reset_index()
    g = g[g["support"] >= min_support].copy()
    g["priority"] = g["predicted_q10"] + 0.25 * g["predicted_mean"]
    return g.sort_values(["priority", "support"], ascending=[False, False])
