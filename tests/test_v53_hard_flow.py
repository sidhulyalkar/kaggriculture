from submission.hard_flow_agent import HardFlowMind
from submission.market_flow_runtime import infer_external_supply
from submission.predictive_agent import normalize_observation_step


def _obs(step=5, milk_inv=10000, milk_price=160, milk_shed=0):
    return {
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "player": 0,
        "farms": [
            {"farmer": [0, 0], "hands": [], "money": 3000, "unlocked_quadrants": ["NW"], "tiles": []},
            {"farmer": [9, 9], "hands": [], "money": 3000, "unlocked_quadrants": ["NW"], "tiles": []},
        ],
        "private": {"shed": {"MILK": milk_shed}, "inventories": [{}], "seeds": {}},
        "market": {
            "inventory": {"MILK": milk_inv},
            "prices": {"MILK": milk_price},
        },
        "town": {"unlocked_shops": []},
    }


def test_runtime_flow_subtracts_our_executed_sale():
    prev = _obs(step=5, milk_inv=10000, milk_price=160, milk_shed=3)
    curr = _obs(step=6, milk_inv=10010, milk_price=145, milk_shed=0)
    own = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MILK", 3]]}
    assert infer_external_supply(prev, curr, own, "MILK") == 7


def test_runtime_flow_fails_closed_at_price_floor():
    prev = _obs(step=5, milk_inv=10100, milk_price=1, milk_shed=0)
    curr = _obs(step=6, milk_inv=10110, milk_price=1, milk_shed=0)
    assert infer_external_supply(prev, curr, {}, "MILK") is None


def test_seat_invariant_clock_ignores_missing_or_bad_raw_step():
    obs = _obs(step=5)
    obs["day"] = 4
    obs["hour"] = 7
    obs.pop("step")
    assert normalize_observation_step(obs) == 103
    assert obs["step"] == 103
    obs["step"] = 9999
    assert normalize_observation_step(obs) == 103
    assert obs["step"] == 103


def test_hard_flow_accelerates_only_bounded_inventory():
    mind = HardFlowMind()
    mind._confirmed_flow["MILK"] = 8
    obs = _obs(step=300, milk_inv=10040, milk_price=76, milk_shed=12)
    counts = {"COW": 8, "SHEEP": 6, "GOOSE": 0}
    orders = mind._sell_orders(obs, counts)
    milk = [o for o in orders if o[0] == "SELL" and o[1] == "MILK"]
    assert milk == [["SELL", "MILK", 8]]
    assert mind.intervention_count == 1
    assert mind.intervention_units == 8
    assert mind.intervention_by_product["MILK"] == 8
    assert mind.activation_funnel["positive_flow_events"] == 1
    assert mind.activation_funnel["eligible"] == 1
    assert mind.activation_funnel["blocked_shock"] == 0


def test_small_flow_does_not_change_baseline_hold_and_records_blocker():
    mind = HardFlowMind()
    mind._confirmed_flow["MILK"] = 3
    obs = _obs(step=300, milk_inv=10040, milk_price=76, milk_shed=12)
    counts = {"COW": 8, "SHEEP": 6, "GOOSE": 0}
    assert not [o for o in mind._sell_orders(obs, counts) if o[0] == "SELL" and o[1] == "MILK"]
    assert mind.intervention_count == 0
    assert mind.activation_funnel["positive_flow_events"] == 1
    assert mind.activation_funnel["positive_flow_units"] == 3
    assert mind.activation_funnel["blocked_shock"] == 1
    assert mind.activation_histograms["shock"]["3"] == 1
