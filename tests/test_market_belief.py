from __future__ import annotations

from swarm.market_belief import public_sale_features, sale_quantity, shop_demand_units, town_drain_for_turn


def _obs():
    return {
        "day": 3,
        "hour": 0,
        "farms": [
            {"money": 3000, "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"], "tiles": [[None] * 10 for _ in range(10)]},
            {"money": 2500, "farmer": [3, 4], "hands": [[4, 4]], "unlocked_quadrants": ["NW", "NE"], "tiles": [[None] * 10 for _ in range(10)]},
        ],
        "market": {"inventory": {"WOOL": 9990}, "prices": {"WOOL": 220}},
        "town": {"unlocked_shops": ["YARN_STORE", "YARN_STORE", "FARMERS_MARKET"]},
        "private": {"shed": {"WOOL": 99}},
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
