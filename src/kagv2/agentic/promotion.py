from __future__ import annotations

from dataclasses import dataclass, asdict
import pandas as pd


@dataclass(frozen=True)
class PromotionThresholds:
    min_robust_delta: float = 0.015
    min_hard_delta: float = 0.030
    min_target_delta: float = 0.020
    min_safe_delta: float = -0.010
    min_worst_guard_delta: float = -0.030
    min_direct_score: float = 0.50
    min_cash_ratio: float = 0.995
    min_activations: int = 1
    max_invalid: int = 0


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    candidate: str
    reasons: tuple[str, ...]
    metrics: dict
    thresholds: dict

    def to_dict(self) -> dict:
        return {
            "promoted": self.promoted,
            "candidate": self.candidate,
            "reasons": list(self.reasons),
            "metrics": self.metrics,
            "thresholds": self.thresholds,
        }


def paired_candidate_metrics(
    games: pd.DataFrame,
    *,
    candidate: str,
    control: str,
    target_opponents: set[str] | None = None,
    guard_opponents: set[str] | None = None,
    hard_seeds: set[int] | None = None,
    safe_seeds: set[int] | None = None,
    direct_opponent: str = "v32_direct",
) -> dict:
    """Compute paired candidate-control deltas on identical opponent/seed/seat rows."""
    required = {"candidate", "opponent", "seed", "seat", "score", "margin", "cash"}
    missing = required - set(games.columns)
    if missing:
        raise KeyError(f"Missing game columns: {sorted(missing)}")
    keys = ["opponent", "seed", "seat"]
    ctl = games[games["candidate"] == control][keys + ["score", "margin", "cash"]].copy()
    ctl = ctl.rename(columns={"score": "control_score", "margin": "control_margin", "cash": "control_cash"})
    cand = games[games["candidate"] == candidate].copy()
    paired = cand.merge(ctl, on=keys, how="inner")
    if paired.empty:
        raise ValueError(f"No paired rows for {candidate!r} vs {control!r}")
    paired["score_delta"] = paired["score"] - paired["control_score"]
    paired["margin_delta"] = paired["margin"] - paired["control_margin"]

    def mean_delta(mask):
        x = paired.loc[mask, "score_delta"]
        return float(x.mean()) if len(x) else None

    target_opponents = target_opponents or set()
    guard_opponents = guard_opponents or set()
    target_mask = paired["opponent"].isin(target_opponents)
    guard_mask = paired["opponent"].isin(guard_opponents)
    hard_mask = paired["seed"].isin(hard_seeds or set())
    safe_mask = paired["seed"].isin(safe_seeds or set())
    per_guard = paired.loc[guard_mask].groupby("opponent")["score_delta"].mean() if guard_mask.any() else pd.Series(dtype=float)
    direct = paired[paired["opponent"] == direct_opponent]
    invalid = int((~cand["ok"].astype(bool)).sum()) if "ok" in cand else 0
    activations = 0
    for col in ("changes", "activations", "activated"):
        if col in cand:
            activations = int(pd.to_numeric(cand[col], errors="coerce").fillna(0).sum())
            break
    return {
        "candidate": candidate,
        "paired_games": int(len(paired)),
        "invalid": invalid,
        "activations": activations,
        "robust_delta": float(paired["score_delta"].mean()),
        "target_delta": mean_delta(target_mask),
        "hard_delta": mean_delta(hard_mask),
        "safe_delta": mean_delta(safe_mask),
        "worst_guard_delta": float(per_guard.min()) if len(per_guard) else None,
        "direct_score": float(direct["score"].mean()) if len(direct) else None,
        "cash_ratio": float(paired["cash"].sum() / max(1.0, paired["control_cash"].sum())),
        "mean_margin_delta": float(paired["margin_delta"].mean()),
        "target_margin_delta": float(paired.loc[target_mask, "margin_delta"].mean()) if target_mask.any() else None,
    }


def evaluate_promotion(metrics: dict, thresholds: PromotionThresholds | None = None) -> PromotionDecision:
    t = thresholds or PromotionThresholds()
    reasons: list[str] = []

    def gate(name, value, predicate, message):
        if value is None:
            reasons.append(f"missing {name}")
        elif not predicate(value):
            reasons.append(message)

    gate("invalid", metrics.get("invalid"), lambda x: x <= t.max_invalid, f"invalid games > {t.max_invalid}")
    gate("activations", metrics.get("activations"), lambda x: x >= t.min_activations, f"activations < {t.min_activations}")
    gate("robust_delta", metrics.get("robust_delta"), lambda x: x >= t.min_robust_delta, f"robust delta < {t.min_robust_delta:+.3f}")
    gate("hard_delta", metrics.get("hard_delta"), lambda x: x >= t.min_hard_delta, f"hard-seed delta < {t.min_hard_delta:+.3f}")
    gate("target_delta", metrics.get("target_delta"), lambda x: x >= t.min_target_delta, f"target delta < {t.min_target_delta:+.3f}")
    gate("safe_delta", metrics.get("safe_delta"), lambda x: x >= t.min_safe_delta, f"safe-seed delta < {t.min_safe_delta:+.3f}")
    gate("worst_guard_delta", metrics.get("worst_guard_delta"), lambda x: x >= t.min_worst_guard_delta, f"worst guard delta < {t.min_worst_guard_delta:+.3f}")
    gate("direct_score", metrics.get("direct_score"), lambda x: x >= t.min_direct_score, f"direct champion score < {t.min_direct_score:.3f}")
    gate("cash_ratio", metrics.get("cash_ratio"), lambda x: x >= t.min_cash_ratio, f"cash ratio < {t.min_cash_ratio:.4f}")
    return PromotionDecision(
        promoted=not reasons,
        candidate=str(metrics.get("candidate", "unknown")),
        reasons=tuple(reasons),
        metrics=dict(metrics),
        thresholds=asdict(t),
    )
