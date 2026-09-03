from swarm.v54_executed_sale_predictor import (
    executed_sale_quantity,
    future_effective_sale_quantity,
    queued_requested_sale,
    transition_effective_sale,
)


def _obs(step=10, price=160, shed=0, inventory=None, farmer=(4, 4)):
    return {
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "player": 0,
        "farms": [
            {"farmer": list(farmer), "hands": [], "money": 3000, "unlocked_quadrants": ["NW"], "tiles": []},
            {"farmer": [9, 9], "hands": [], "money": 3000, "unlocked_quadrants": ["NW"], "tiles": []},
        ],
        "private": {
            "shed": {"MILK": shed},
            "inventories": [inventory or {}],
            "seeds": {},
        },
        "market": {"inventory": {"MILK": 10000}, "prices": {"MILK": price}},
        "town": {"unlocked_shops": []},
    }


def _state(obs, action=None):
    return {"observation": obs, "action": action}


def test_queue_cap_ignores_sell_after_first_ten_orders():
    action = {"market": [["SELL", "WOOL", 1]] * 10 + [["SELL", "MILK", 9]]}
    assert queued_requested_sale(action, "MILK") == 0


def test_executed_sale_is_bounded_by_post_physical_shed():
    obs = _obs(shed=3, inventory={"MILK": 5})
    action = {
        "farmer": ["PLACE", "MILK", 4],
        "hands": [],
        "market": [["SELL", "MILK", 10]],
    }
    # PLACE adds 4 to the existing shed before the market queue, so 7 execute.
    assert executed_sale_quantity(obs, action, "MILK") == 7


def test_transition_above_floor_has_exact_effective_sale():
    prev = _obs(step=10, price=160, shed=6)
    curr = _obs(step=11, price=140, shed=0)
    action = {"market": [["SELL", "MILK", 4]]}
    row = transition_effective_sale(prev, curr, action, "MILK")
    assert row["requested"] == 4
    assert row["executed"] == 4
    assert row["effective"] == 4
    assert not row["floor_censored"]


def test_floor_crossing_positive_sale_is_censored_not_guessed():
    prev = _obs(step=10, price=2, shed=6)
    curr = _obs(step=11, price=1, shed=0)
    action = {"market": [["SELL", "MILK", 4]]}
    row = transition_effective_sale(prev, curr, action, "MILK")
    assert row["executed"] == 4
    assert row["effective"] is None
    assert row["floor_censored"]


def test_future_label_uses_action_row_t_plus_one():
    obs0 = _obs(step=10, price=160, shed=5)
    obs1 = _obs(step=11, price=145, shed=0)
    obs2 = _obs(step=12, price=145, shed=0)
    action_from_obs0 = {"market": [["SELL", "MILK", 5]]}
    steps = [
        [_state(obs0), _state(obs0)],
        [_state(obs1, action_from_obs0), _state(obs1, {})],
        [_state(obs2, {}), _state(obs2, {})],
    ]
    target = future_effective_sale_quantity(steps, 0, 0, "MILK", horizon=0)
    assert target["effective_quantity"] == 5
    assert target["requested_quantity"] == 5
    assert target["executed_quantity"] == 5


def test_censored_only_window_has_no_binary_label():
    obs0 = _obs(step=10, price=2, shed=5)
    obs1 = _obs(step=11, price=1, shed=0)
    steps = [
        [_state(obs0), _state(obs0)],
        [_state(obs1, {"market": [["SELL", "MILK", 5]]}), _state(obs1, {})],
    ]
    target = future_effective_sale_quantity(steps, 0, 0, "MILK", horizon=0)
    assert target["effective_quantity"] is None
    assert not target["exact_binary"]
