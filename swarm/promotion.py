from __future__ import annotations

from math import sqrt
from typing import Any, Iterable

from .models import EvaluationRecord, PromotionDecision


def behavioral_distance(a: Iterable[float], b: Iterable[float]) -> float:
    aa = tuple(float(x) for x in a)
    bb = tuple(float(x) for x in b)
    if len(aa) != len(bb):
        raise ValueError("Behavioral fingerprints must have equal length")
    if not aa:
        return 0.0
    return sqrt(sum((x - y) ** 2 for x, y in zip(aa, bb)) / len(aa))


def promotion_decision(evaluation: EvaluationRecord, thresholds: dict[str, Any]) -> PromotionDecision:
    reasons: list[str] = []
    checks = (
        (evaluation.paired_score_delta >= float(thresholds["min_paired_score_delta"]), "paired score delta"),
        (evaluation.worst_family_delta >= float(thresholds["min_worst_family_delta"]), "worst-family delta"),
        (evaluation.passive_cash_ratio >= float(thresholds["min_passive_cash_ratio"]), "passive cash ratio"),
        (evaluation.invalid_games <= int(thresholds["max_invalid_games"]), "invalid games"),
        (evaluation.mean_call_ms <= float(thresholds["max_mean_call_ms"]), "mean call time"),
        (evaluation.physical_divergence <= float(thresholds["max_physical_divergence"]), "physical divergence"),
    )
    for passed, label in checks:
        if not passed:
            reasons.append(f"failed {label}")

    # The scalar is for ranking only. Promotion still requires every hard gate.
    score = (
        evaluation.paired_score_delta
        + 0.35 * evaluation.worst_family_delta
        + 0.10 * (evaluation.passive_cash_ratio - 1.0)
        - 0.001 * evaluation.invalid_games
        - 0.001 * max(0.0, evaluation.mean_call_ms - 25.0)
        - 0.25 * evaluation.physical_divergence
    )
    return PromotionDecision(
        candidate_id=evaluation.candidate_id,
        promote=not reasons,
        reasons=tuple(reasons) if reasons else ("all hard gates passed",),
        score=score,
    )


def select_portfolio(
    evaluations: list[EvaluationRecord],
    promoted_ids: set[str],
    slots: list[str],
) -> dict[str, str | None]:
    eligible = [row for row in evaluations if row.candidate_id in promoted_ids]
    by_mean = sorted(eligible, key=lambda row: row.mean_score, reverse=True)
    by_robust = sorted(eligible, key=lambda row: row.worst_family_delta, reverse=True)
    by_counter = sorted(eligible, key=lambda row: row.metadata.get("target_family_gain", float("-inf")), reverse=True)
    by_novelty = sorted(eligible, key=lambda row: row.metadata.get("novelty", float("-inf")), reverse=True)
    by_architecture = [row for row in by_mean if row.metadata.get("lane") == "architecture"]

    result: dict[str, str | None] = {}
    used: set[str] = set()
    pools = {
        "champion": by_mean,
        "counter": by_counter,
        "architecture": by_architecture,
        "robust": by_robust,
        "explorer": by_novelty,
    }
    for slot in slots:
        pick = next((row.candidate_id for row in pools.get(slot, by_mean) if row.candidate_id not in used), None)
        result[slot] = pick
        if pick:
            used.add(pick)
    return result
