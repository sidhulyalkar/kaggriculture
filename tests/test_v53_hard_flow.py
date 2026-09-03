from submission.hard_flow_agent import HardFlowMind
from submission.market_flow_runtime import infer_external_supply


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


def test_hard_flow_accelerates_only_bounded_inventory():
    mind = HardFlowMind()
    mind._confirmed_flow["MILK"] = 8
    obs = _obs(step=300, milk_inv=10040, milk_price=76, milk_shed=12)
    counts = {"COW": 8, "SHEEP": 6, "GOOSE": 0}
    orders = mind._sell_orders(obs, counts)
    milk = [o for o in orders if o[0] == "SELL" and o[1] == "MILK"]
    assert milk == [["SELL", "MILK", 8]]


def test_small_flow_does_not_change_baseline_hold():
    mind = HardFlowMind()
    mind._confirmed_flow["MILK"] = 3
    obs = _obs(step=300, milk_inv=10040, milk_price=76, milk_shed=12)
    counts = {"COW": 8, "SHEEP": 6, "GOOSE": 0}
    assert not [o for o in mind._sell_orders(obs, counts) if o[0] == "SELL" and o[1] == "MILK"]
