from __future__ import annotations

from dataclasses import dataclass, asdict
import re

import pandas as pd


@dataclass(frozen=True)
class ForecastGeneralizationReport:
    model: str
    median_auc: float
    worst_target_family_auc: float
    eligible_targets: tuple[str, ...]
    rejected_targets: tuple[str, ...]
    min_median_auc: float
    min_family_auc: float

    def to_dict(self) -> dict:
        return asdict(self)


def generalization_report(
    lofo_metrics: pd.DataFrame,
    *,
    model: str = "linear",
    target_prefix: str = "sell",
    min_median_auc: float = 0.85,
    min_family_auc: float = 0.80,
) -> ForecastGeneralizationReport:
    """Select forecast targets that generalize across unseen policy families."""
    d = lofo_metrics.copy()
    if not {"held_family", "target", "model", "auc"} <= set(d.columns):
        raise KeyError("LOFO metrics must contain held_family,target,model,auc")
    d = d[(d["model"].astype(str) == model) & d["target"].astype(str).str.startswith(target_prefix)]
    d = d[pd.to_numeric(d["auc"], errors="coerce").notna()].copy()
    if d.empty:
        raise ValueError(f"No {model!r} {target_prefix!r} LOFO rows")
    d["auc"] = pd.to_numeric(d["auc"], errors="coerce")
    by_target = d.groupby("target")["auc"].agg(["median", "min"]).reset_index()
    good = by_target[(by_target["median"] >= min_median_auc) & (by_target["min"] >= min_family_auc)]
    bad = by_target[~by_target["target"].isin(good["target"])]
    return ForecastGeneralizationReport(
        model=model,
        median_auc=float(d["auc"].median()),
        worst_target_family_auc=float(by_target["min"].min()),
        eligible_targets=tuple(sorted(good["target"].astype(str))),
        rejected_targets=tuple(sorted(bad["target"].astype(str))),
        min_median_auc=float(min_median_auc),
        min_family_auc=float(min_family_auc),
    )


def target_horizon(target: str) -> int | None:
    m = re.match(r"sell(\d+)_", str(target))
    return int(m.group(1)) if m else None
