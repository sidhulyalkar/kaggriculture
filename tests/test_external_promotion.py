from __future__ import annotations

from swarm.external_promotion import ExternalCandidate, external_promotion_decision, select_active_pair


def _candidate(name: str, ext: float, replay: float, families: dict[str, float], seats=(0.6, 0.6)) -> ExternalCandidate:
    return ExternalCandidate(
        name=name,
        external_win_score=ext,
        replay_win_score=replay,
        family_scores=families,
        seat_scores={0: seats[0], 1: seats[1]},
    )


def test_internal_metadata_cannot_rescue_external_regression():
    base = _candidate("base", 0.60, 0.60, {"moon": 0.50, "soil": 0.55})
    bad = ExternalCandidate(
        name="selfplay_star",
        external_win_score=0.55,
        replay_win_score=0.80,
        family_scores={"moon": 0.50, "soil": 0.55},
        seat_scores={0: 0.60, 1: 0.60},
        metadata={"internal_win_score": 1.0},
    )
    decision = external_promotion_decision(bad, base)
    assert not decision.promote
    assert any("external W/L" in reason for reason in decision.reasons)


def test_catastrophic_family_blocks_mean_gain():
    base = _candidate("base", 0.55, 0.55, {"moon": 0.45, "soil": 0.50})
    brittle = _candidate("brittle", 0.70, 0.60, {"moon": 0.20, "soil": 0.80}, seats=(0.70, 0.70))
    assert not external_promotion_decision(brittle, base).promote


def test_active_pair_prefers_complementary_family_coverage():
    a = _candidate("a", 0.66, 0.62, {"moon": 0.80, "soil": 0.45})
    clone = _candidate("clone", 0.67, 0.63, {"moon": 0.82, "soil": 0.44})
    complement = _candidate("complement", 0.64, 0.62, {"moon": 0.50, "soil": 0.80})
    pair = select_active_pair([a, clone, complement])
    assert pair is not None
    assert "complement" in pair
