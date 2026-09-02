from __future__ import annotations

from copy import deepcopy

from swarm.v52_market_flow_alignment import (
    executed_sell_units,
    infer_external_supply_physical,
    post_physical_shed,
)


def _obs(*, player: int = 0):
    farms = [
        {
            "money": 3000,
            "farmer": [4, 4],
            "hands": [[5, 4]],
            "unlocked_quadrants": ["NW"],
            "tiles": [[None] * 10 for _ in range(10)],
        },
        {
            "money": 2500,
            "farmer": [3, 3],
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "tiles": [[None] * 10 for _ in range(10)],
        },
    ]
    return {
        "player": player,
        "step": 73,
        "day": 3,
        "hour": 1,
        "farms": farms,
        "market": {
            "inventory": {"WOOL": 10000, "MILK": 10000},
            "prices": {"WOOL": 200, "MILK": 160},
        },
        "town": {"unlocked_shops": []},
        "private": {
            "shed": {"WOOL": 2, "MILK": 0},
            "inventories": [
                {"WOOL": 5, "MILK": 1},
                {"WOOL": 4},
            ],
        },
    }


def test_drop_then_sell_uses_same_turn_shed_stock():
    obs = _obs()
    action = {
        "farmer": ["DROP"],
        "hands": [["PASS"]],
        "market": [["SELL", "WOOL", 7]],
    }
    shed = post_physical_shed(obs, action)
    assert shed["WOOL"] == 7
    assert executed_sell_units(obs, action, "WOOL") == 7
    # The diagnostic must not mutate the replay observation.
    assert obs["private"]["shed"]["WOOL"] == 2
    assert obs["private"]["inventories"][0]["WOOL"] == 5


def test_place_then_sell_respects_requested_quantity():
    obs = _obs()
    action = {
        "farmer": ["PLACE", "WOOL", 3],
        "hands": [["PASS"]],
        "market": [["SELL", "WOOL", 8]],
    }
    assert post_physical_shed(obs, action)["WOOL"] == 5
    assert executed_sell_units(obs, action, "WOOL") == 5


def test_pickup_before_market_reduces_sellable_stock():
    obs = _obs()
    obs["private"]["shed"]["WOOL"] = 8
    action = {
        "farmer": ["PICKUP", "WOOL", 5],
        "hands": [["PASS"]],
        "market": [["SELL", "WOOL", 8]],
    }
    assert post_physical_shed(obs, action)["WOOL"] == 3
    assert executed_sell_units(obs, action, "WOOL") == 3


def test_farmer_then_hand_order_respects_shed_capacity():
    obs = _obs()
    obs["private"]["shed"] = {"WOOL": 96}
    obs["private"]["inventories"] = [{"MILK": 3}, {"WOOL": 4}]
    action = {
        "farmer": ["DROP"],
        "hands": [["DROP"]],
        "market": [],
    }
    shed = post_physical_shed(obs, action)
    assert shed["MILK"] == 3
    assert shed["WOOL"] == 97
    assert sum(shed.values()) == 100


def test_physical_inference_removes_newly_dropped_own_sell():
    prev = _obs()
    curr = deepcopy(prev)
    own_action = {
        "farmer": ["DROP"],
        "hands": [["PASS"]],
        "market": [["SELL", "WOOL", 7]],
    }
    # At step 73 there is no town drain. Our 7-unit sale and an opponent 4-unit
    # sale increase public inventory by 11.
    curr["market"]["inventory"]["WOOL"] += 11
    estimate = infer_external_supply_physical(prev, curr, own_action, "WOOL")
    assert estimate.exact
    assert estimate.own_sell_units == 7
    assert estimate.effective_units == 4


def test_physical_inference_matches_legacy_when_no_shed_mutation():
    prev = _obs()
    prev["private"]["shed"]["WOOL"] = 6
    curr = deepcopy(prev)
    own_action = {
        "farmer": ["PASS"],
        "hands": [["PASS"]],
        "market": [["SELL", "WOOL", 3]],
    }
    curr["market"]["inventory"]["WOOL"] += 8
    estimate = infer_external_supply_physical(prev, curr, own_action, "WOOL")
    assert estimate.exact
    assert estimate.own_sell_units == 3
    assert estimate.effective_units == 5
