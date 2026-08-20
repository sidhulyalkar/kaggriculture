from __future__ import annotations

from submission.temporal_opponent_model import TemporalOpponentTracker
from submission.temporal_response_selector import TemporalResponseSelector


def obs(step=0, opp_money=5000, opp_hands=3, opp_quads=1, crop=2, animals=0):
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for i in range(min(crop, 8)):
        tiles[0][i] = {"kind": "PLANT", "crop": "WHEAT", "yield_units": 0}
    for i in range(min(animals, 8)):
        tiles[1][i] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0}
    me = {"money": 5000, "hands": [[0, 0]], "unlocked_quadrants": ["NW"], "tiles": [[None for _ in range(10)] for _ in range(10)]}
    op = {
        "money": opp_money,
        "hands": [[0, 0] for _ in range(opp_hands)],
        "unlocked_quadrants": ["NW", "NE", "SW", "SE"][:opp_quads],
        "tiles": tiles,
    }
    return {
        "player": 0,
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "farms": [me, op],
        "market": {"inventory": {}, "prices": {}},
    }


def test_stable_opponent_does_not_create_confirmed_change():
    tracker = TemporalOpponentTracker({"change_threshold": 0.70, "confirm_steps": 2})
    confirmed = 0
    for step in range(40):
        b = tracker.update(obs(step=step, opp_money=5000 + step * 10, opp_hands=3, crop=2))
        confirmed += int(b["confirmed_change"])
    assert confirmed == 0


def test_persistent_structural_pivot_is_detectable():
    tracker = TemporalOpponentTracker({
        "change_threshold": 0.45,
        "confirm_steps": 2,
        "cusum_h": 1.2,
        "cusum_k": 0.15,
    })
    seen = False
    for step in range(18):
        tracker.update(obs(step=step, opp_money=5000 + step * 5, opp_hands=2, opp_quads=1, crop=2))
    # Persistent expansion/animal shock, not a single noisy tick.
    for step in range(18, 34):
        b = tracker.update(obs(step=step, opp_money=9000 + step * 25, opp_hands=10, opp_quads=3, crop=0, animals=6))
        seen = seen or b["confirmed_change"]
    assert seen
    assert tracker.change_count >= 1


def test_selector_defaults_to_champion_without_model_support():
    s = TemporalResponseSelector()
    response, scores = s.update(100, {"posterior": [], "confidence": 0.0, "change_probability": 0.0})
    assert response == "V32"


def test_selector_enters_specialist_only_after_persistent_positive_value():
    model = {
        "responses": ["V32", "CAPITAL_HOLD"],
        "default": "V32",
        "win_delta": [[0.0, 0.0], [0.04, 0.03]],
        "bad_flip": [[0.0, 0.0], [0.002, 0.003]],
        "stderr": [[0.0, 0.0], [0.003, 0.003]],
        "support": [[100, 100], [100, 100]],
        "min_support": 40,
        "switch_margin": 0.01,
        "max_bad_flip": 0.01,
        "cooldown": 0,
    }
    s = TemporalResponseSelector(model)
    belief = {"posterior": [0.8, 0.2], "confidence": 0.9, "change_probability": 0.05}
    assert s.update(100, belief)[0] == "V32"
    assert s.update(101, belief)[0] == "V32"
    assert s.update(102, belief)[0] == "CAPITAL_HOLD"


def test_selector_rejects_high_bad_flip_even_with_large_mean_gain():
    model = {
        "responses": ["V32", "RISKY"],
        "default": "V32",
        "win_delta": [[0.0], [0.20]],
        "bad_flip": [[0.0], [0.08]],
        "stderr": [[0.0], [0.001]],
        "support": [[100], [100]],
        "max_bad_flip": 0.01,
        "cooldown": 0,
    }
    s = TemporalResponseSelector(model)
    belief = {"posterior": [1.0], "confidence": 1.0, "change_probability": 0.0}
    for step in range(5):
        response, _ = s.update(step + 10, belief)
    assert response == "V32"
