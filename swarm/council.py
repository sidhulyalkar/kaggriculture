from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any


def summarize_reviews(reviews: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Aggregate independent council scores while preserving disagreement as signal."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for review in reviews:
        candidate_id = str(review["candidate_id"])
        grouped[candidate_id].append(float(review["score"]))

    summary: dict[str, dict[str, float]] = {}
    for candidate_id, scores in grouped.items():
        summary[candidate_id] = {
            "mean": mean(scores),
            "disagreement": pstdev(scores) if len(scores) > 1 else 0.0,
            "n": float(len(scores)),
        }
    return summary


def prioritize_for_replication(
    evidence: dict[str, dict[str, float]],
    *,
    disagreement_weight: float = 0.35,
) -> list[str]:
    """High expected value plus disagreement gets replication priority."""
    return sorted(
        evidence,
        key=lambda candidate_id: (
            evidence[candidate_id]["mean"]
            + disagreement_weight * evidence[candidate_id]["disagreement"]
        ),
        reverse=True,
    )
