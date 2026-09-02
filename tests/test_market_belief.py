from __future__ import annotations

from copy import deepcopy

from swarm.market_belief import (
    executed_sell_quantity,
    infer_external_supply,
    post_physical_shed,
    public_sale_features,
    sale_quantity,
    shop_demand_units,
    town_drain_for_turn,
)


def _obs():
    return {
        "player": 0,
        "day": 3,
        "hour": 0,
        "farms": [
            {"money": 3000, "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"], "tiles": [[None] * 10 for _ in range(10)]},
            {"money": 2500, "farmer": [3, 4], "hands": [[4, 4]], "unlocked_quadrants": ["NW", "NE"], "tiles": [[None] * 10 for _ in range(10)]},
        ],
        "market": {"inventory": {"WOOL": 9990, "MILK": 10000, "WHEAT": 10000}, "prices": {"WOOL": 220, "MILK": 160, "WHEAT": 25}},
        "town": {"unlocked_shops": ["YARN_STORE", "YARN_STORE", "FARMERS_MARKET"]},
        "private": {
            "shed": {"WOOL": 99, "MILK": 5, "WHEAT": 10},
            "inventories": [{}],
        },
    }


def test_shop_demand_counts_duplicate_single_product_shops_twice():
    assert shop_demand_units(["YARN_STORE", "YARN_STORE"], "WOOL") == 4
    assert shop_demand_units(["FARMERS_MARKET"], "CARROT") == 1


def test_town_drain_matches_default_intervals():
    shops = ["YARN_STORE", "FARMERS_MARKET"]
    assert town_drain_for_turn(72, shops, "WOOL") == 3  # 2 from yarn + 1 town center
    assert town_drain_for_turn(73, shops, "WOOL") == 0
    assert town_drain_for_turn(76, shops, "CARROT") == 1


def test_public_features_ignore_private_inventory():
    obs = _obs()
    a = public_sale_features(obs, 1, "WOOL")
    obs["private"]["shed"]["WOOL"] = 0
    b = public_sale_features(obs, 1, "WOOL")
    assert a == b
    assert not any("private" in key or "shed_stock" in key for key in a)


def test_sale_quantity_sums_orders_for_product_only():
    action = {"market": [["SELL", "WOOL", 3], ["SELL", "MILK", 8], ["SELL", "WOOL", 2]]}
    assert sale_quantity(action, "WOOL") == 5
    assert sale_quantity(action, "EGG") == 0


def test_external_supply_accounting_removes_own_sell_and_town_drain():
    prev = _obs()
    curr = deepcopy(prev)
    # step 72 drains five wool units: two Yarn Stores * 2 plus town center * 1.
    # We sell 3 and the opponent sells 7, so net public inventory change is +5.
    curr["market"]["inventory"]["WOOL"] = prev["market"]["inventory"]["WOOL"] + 5
    estimate = infer_external_supply(prev, curr, {"market": [["SELL", "WOOL", 3]]}, "WOOL")
    assert estimate.exact
    assert estimate.own_sell_units == 3
    assert estimate.town_drain == 5
    assert estimate.effective_units == 7
    assert estimate.lower_bound == estimate.upper_bound == 7


def test_external_supply_caps_our_requested_sell_by_known_shed_stock():
    prev = _obs()
    prev["private"]["shed"]["MILK"] = 2
    curr = deepcopy(prev)
    # no milk shop demand here at step 72 except town center one. We request 10,
    # only 2 can execute, opponent sells 4 => delta = +2 +4 -1 = +5.
    curr["market"]["inventory"]["MILK"] += 5
    estimate = infer_external_supply(prev, curr, {"market": [["SELL", "MILK", 10]]}, "MILK")
    assert estimate.exact
    assert estimate.own_sell_units == 2
    assert estimate.effective_units == 4


def test_drop_then_sell_uses_same_turn_inventory_before_market():
    prev = _obs()
    prev["private"]["shed"] = {"WOOL": 2}
    prev["private"]["inventories"] = [{"WOOL": 5}]
    action = {
        "farmer": ["DROP"],
        "hands": [],
        "market": [["SELL", "WOOL", 7]],
    }
    assert post_physical_shed(prev, action)["WOOL"] == 7
    assert executed_sell_quantity(prev, action, "WOOL") == 7


def test_pickup_before_sell_reduces_same_turn_executable_stock():
    prev = _obs()
    prev["private"]["shed"] = {"MILK": 8}
    prev["private"]["inventories"] = [{}]
    action = {
        "farmer": ["PICKUP", "MILK", 5],
        "hands": [],
        "market": [["SELL", "MILK", 8]],
    }
    assert post_physical_shed(prev, action)["MILK"] == 3
    assert executed_sell_quantity(prev, action, "MILK") == 3


def test_drop_respects_total_shed_capacity_and_engine_item_order():
    prev = _obs()
    prev["private"]["shed"] = {"WOOL": 96}
    # Insertion order matters: MILK fills three slots, then only one CARROT fits.
    prev["private"]["inventories"] = [{"MILK": 3, "CARROT": 4}]
    action = {"farmer": ["DROP"], "hands": [], "market": []}
    shed = post_physical_shed(prev, action)
    assert shed["MILK"] == 3
    assert shed["CARROT"] == 1
    assert sum(shed.values()) == 100


def test_external_supply_removes_same_turn_drop_then_sell():
    prev = _obs()
    prev["hour"] = 1  # step 73: no deterministic drain
    prev["private"]["shed"] = {"WOOL": 2}
    prev["private"]["inventories"] = [{"WOOL": 5}]
    curr = deepcopy(prev)
    own_action = {
        "farmer": ["DROP"],
        "hands": [],
        "market": [["SELL", "WOOL", 7]],
    }
    # Own sale 7 + external sale 4.
    curr["market"]["inventory"]["WOOL"] += 11
    estimate = infer_external_supply(prev, curr, own_action, "WOOL")
    assert estimate.exact
    assert estimate.own_sell_units == 7
    assert estimate.effective_units == 4


def test_floor_censoring_refuses_false_exact_inventory_claim():
    prev = _obs()
    curr = deepcopy(prev)
    curr["market"]["prices"]["WOOL"] = 1
    estimate = infer_external_supply(prev, curr, {"market": []}, "WOOL")
    assert not estimate.exact
    assert estimate.floor_censored
    assert estimate.upper_bound is None


def test_buyable_products_are_net_flow_confounded():
    prev = _obs()
    curr = deepcopy(prev)
    estimate = infer_external_supply(prev, curr, {"market": []}, "WHEAT")
    assert not estimate.exact
    assert "BUY_PRODUCT" in estimate.note
