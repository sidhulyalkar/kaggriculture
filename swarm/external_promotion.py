from __future__ import annotations

from dataclasses import dataclass
import itertools
import statistics
from typing import Any


@dataclass(frozen=True)
class ExternalCandidate:
    name: str
    external_win_score: float
    replay_win_score: float
    family_scores: dict[str, float]
    seat_scores: dict[int, float]
    invalid_games: int = 0
    metadata: dict[str, Any] | None = None

    @property
    def worst_family(self) -> float:
        return min(self.family_scores.values(), default=-1.0)


@dataclass(frozen=True)
class ExternalDecision:
    name: str
    promote: bool
    reasons: tuple[str, ...]
    external_delta: float
    replay_delta: float
    worst_family_delta: float


def external_promotion_decision(candidate: ExternalCandidate, incumbent: ExternalCandidate) -> ExternalDecision:
    """External-first promotion gate.

    Internal/self-play results intentionally do not appear in this interface. They
    may be recorded in metadata for debugging but cannot contribute to promotion.
    """
    external_delta = candidate.external_win_score - incumbent.external_win_score
    replay_delta = candidate.replay_win_score - incumbent.replay_win_score
    worst_delta = candidate.worst_family - incumbent.worst_family
    reasons: list[str] = []
    if candidate.invalid_games:
        reasons.append("invalid external games")
    if external_delta < 0.02:
        reasons.append("external W/L gain below +0.02")
    if replay_delta < -0.01:
        reasons.append("recent replay regression")
    if worst_delta < -0.02:
        reasons.append("worst-family regression")
    if candidate.worst_family < 0.35:
        reasons.append("catastrophic family below 0.35")
    for seat in (0, 1):
        cand = float(candidate.seat_scores.get(seat, -1.0))
        base = float(incumbent.seat_scores.get(seat, -1.0))
        if cand < base - 0.03:
            reasons.append(f"seat {seat} regression")
    return ExternalDecision(
        name=candidate.name,
        promote=not reasons,
        reasons=tuple(reasons) if reasons else ("all external hard gates passed",),
        external_delta=external_delta,
        replay_delta=replay_delta,
        worst_family_delta=worst_delta,
    )


def pair_coverage(a: ExternalCandidate, b: ExternalCandidate) -> dict[str, float]:
    """Score a two-policy research/deployment pair by complementary external coverage."""
    families = sorted(set(a.family_scores) | set(b.family_scores))
    covered = {family: max(float(a.family_scores.get(family, 0.0)), float(b.family_scores.get(family, 0.0))) for family in families}
    return {
        "coverage_mean": statistics.mean(covered.values()) if covered else -1.0,
        "coverage_floor": min(covered.values(), default=-1.0),
        "individual_mean": statistics.mean([a.external_win_score, b.external_win_score]),
        "replay_mean": statistics.mean([a.replay_win_score, b.replay_win_score]),
    }


def select_active_pair(candidates: list[ExternalCandidate]) -> tuple[str, str] | None:
    """Choose two strong but complementary policies after external promotion.

    The objective favors the weaker covered family first, then overall family
    coverage, while retaining pressure on both candidates' own external strength.
    """
    if len(candidates) < 2:
        return None
    ranked = []
    for a, b in itertools.combinations(candidates, 2):
        metrics = pair_coverage(a, b)
        key = (
            metrics["coverage_floor"],
            metrics["coverage_mean"],
            metrics["individual_mean"],
            metrics["replay_mean"],
        )
        ranked.append((key, a.name, b.name))
    ranked.sort(reverse=True)
    _, a, b = ranked[0]
    return a, b
