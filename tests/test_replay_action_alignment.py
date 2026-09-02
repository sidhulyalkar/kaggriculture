from __future__ import annotations

from swarm.v50_sale_intent_probe import future_sale_quantity
from swarm.v51_market_flow_validation import _executed_sell_upper


def _state(*, action=None, shed=None):
    return {
        "observation": {
            "private": {"shed": dict(shed or {})},
        },
        "action": action,
    }


def test_v50_future_label_begins_on_next_replay_row():
    steps = [
        [
            _state(action={"market": [["SELL", "WOOL", 99]]}),
            _state(),
        ],
        [
            _state(action={"market": [["SELL", "WOOL", 2]]}),
            _state(),
        ],
        [
            _state(action={"market": [["SELL", "WOOL", 3]]}),
            _state(),
        ],
        [
            _state(action={"market": [["SELL", "WOOL", 5]]}),
            _state(),
        ],
    ]
    # The 99-unit action on row 0 produced observation[0] and must not leak into
    # a label computed from observation[0].  Horizon 1 means rows 1 and 2.
    assert future_sale_quantity(steps, 0, 0, "WOOL", horizon=1) == 5


def test_v51_truth_caps_next_row_action_with_current_row_shed():
    pre_state = _state(
        action={"market": [["SELL", "WOOL", 50]]},
        shed={"WOOL": 4},
    )
    next_state = _state(
        action={"market": [["SELL", "WOOL", 7]]},
        shed={"WOOL": 999},
    )
    # The action is read from row t+1 while availability comes from observation t.
    assert _executed_sell_upper(pre_state, next_state, "WOOL") == 4


def test_v51_does_not_use_stale_action_from_pre_state():
    pre_state = _state(
        action={"market": [["SELL", "MILK", 12]]},
        shed={"MILK": 12},
    )
    next_state = _state(action={"market": []}, shed={"MILK": 12})
    assert _executed_sell_upper(pre_state, next_state, "MILK") == 0
