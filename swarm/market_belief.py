from __future__ import annotations

import math
from typing import Any

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
ANIMAL_PRODUCT = {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}
SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
BASE_PRICE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}
MARKET_I0 = 10000
_SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def canonical_step(obs: Any) -> int:
    raw = _get(obs, "step", None)
    if raw is not None:
        try:
            return int(raw)
        except Exception:
            pass
    return int(_get(obs, "day", 0) or 0) * 24 + int(_get(obs, "hour", 0) or 0)


def shop_demand_units(unlocked_shops: list[str] | tuple[str, ...], product: str) -> int:
    """Units removed per shop-consumption tick for one product."""
    total = 0
    for shop in unlocked_shops:
        products = SHOP_PRODUCTS.get(str(shop), ())
        if product in products:
            total += 2 if len(products) == 1 else 1
    return total


def town_drain_for_turn(step: int, unlocked_shops: list[str] | tuple[str, ...], product: str) -> int:
    """Exact default-environment inventory drain applied after player market orders."""
    drain = 0
    if int(step) % 4 == 0:
        drain += shop_demand_units(unlocked_shops, product)
    if product != "FERTILIZER" and int(step) % 24 == 0:
        drain += 1
    return drain


def _positions(farm: Any) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    farmer = _get(farm, "farmer", None)
    if isinstance(farmer, (list, tuple)) and len(farmer) >= 2:
        out.append((int(farmer[0]), int(farmer[1])))
    for pos in list(_get(farm, "hands", []) or []):
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            out.append((int(pos[0]), int(pos[1])))
    return out


def _shed_distance(pos: tuple[int, int]) -> int:
    return min(abs(pos[0] - x) + abs(pos[1] - y) for x, y in _SHED_ACCESS)


def _tile_stats(farm: Any, product: str) -> dict[str, float]:
    tiles = list(_get(farm, "tiles", []) or [])
    animal_count = animal_yield = animal_ready = animal_cared = animal_fed = 0.0
    crop_count = crop_yield = crop_ready = 0.0
    all_animals = {"GOOSE": 0.0, "COW": 0.0, "SHEEP": 0.0}
    all_crops = {"WHEAT": 0.0, "CARROT": 0.0, "TOMATO": 0.0, "STRAWBERRY": 0.0, "MELON": 0.0}
    for row in tiles:
        for tile in list(row or []):
            if not isinstance(tile, dict):
                continue
            animal = str(tile.get("animal", ""))
            if animal in all_animals:
                all_animals[animal] += 1.0
                if ANIMAL_PRODUCT[animal] == product:
                    y = float(tile.get("yield_units", 0) or 0)
                    animal_count += 1.0
                    animal_yield += y
                    animal_ready += float(y > 0)
                    animal_cared += float(bool(tile.get("cared_today", False)))
                    animal_fed += float(bool(tile.get("fed_today", False)))
            crop = str(tile.get("crop", ""))
            if crop in all_crops:
                all_crops[crop] += 1.0
                if crop == product:
                    y = float(tile.get("yield_units", 0) or 0)
                    crop_count += 1.0
                    crop_yield += y
                    crop_ready += float(y > 0)
    return {
        "animal_count": animal_count,
        "animal_yield": animal_yield,
        "animal_ready": animal_ready,
        "animal_cared": animal_cared,
        "animal_fed": animal_fed,
        "crop_count": crop_count,
        "crop_yield": crop_yield,
        "crop_ready": crop_ready,
        "geese": all_animals["GOOSE"],
        "cows": all_animals["COW"],
        "sheep": all_animals["SHEEP"],
        "wheat_tiles": all_crops["WHEAT"],
        "carrot_tiles": all_crops["CARROT"],
        "tomato_tiles": all_crops["TOMATO"],
        "strawberry_tiles": all_crops["STRAWBERRY"],
        "melon_tiles": all_crops["MELON"],
    }


def public_sale_features(obs: Any, target_seat: int, product: str) -> dict[str, float]:
    """Features available to either player before simultaneous market actions.

    Deliberately ignores ``observation.private``. The returned dictionary is safe
    to use for opponent modelling because farms, town, market, day and hour are
    public observations.
    """
    product = str(product)
    farms = list(_get(obs, "farms", []) or [])
    farm = farms[int(target_seat)] if int(target_seat) < len(farms) else {}
    market = _get(obs, "market", {}) or {}
    inventory = _get(market, "inventory", {}) or {}
    prices = _get(market, "prices", {}) or {}
    town = _get(obs, "town", {}) or {}
    shops = list(_get(town, "unlocked_shops", []) or [])
    step = canonical_step(obs)
    positions = _positions(farm)
    tile = _tile_stats(farm, product)
    inv = float(_get(inventory, product, MARKET_I0) or MARKET_I0)
    price = float(_get(prices, product, BASE_PRICE.get(product, 1)) or 1)
    money = max(0.0, float(_get(farm, "money", 0) or 0))
    quadrants = list(_get(farm, "unlocked_quadrants", []) or [])
    return {
        "step_frac": step / 720.0,
        "day_frac": float(_get(obs, "day", 0) or 0) / 30.0,
        "hour_frac": float(_get(obs, "hour", 0) or 0) / 24.0,
        "money_log": math.log1p(money) / 12.0,
        "hands": float(len(list(_get(farm, "hands", []) or []))) / 16.0,
        "quadrants": float(len(quadrants)) / 4.0,
        "market_inventory_delta": (inv - MARKET_I0) / 500.0,
        "market_price_ratio": price / max(1.0, float(BASE_PRICE.get(product, 1))),
        "market_floor": float(price <= 1.0),
        "shop_demand": float(shop_demand_units(shops, product)) / 8.0,
        "town_drain_now": float(town_drain_for_turn(step, shops, product)) / 8.0,
        "units_near_shed": float(sum(_shed_distance(p) == 0 for p in positions)) / 16.0,
        "min_shed_distance": float(min((_shed_distance(p) for p in positions), default=12)) / 12.0,
        **{k: float(v) / (25.0 if k.endswith("tiles") or k in {"geese", "cows", "sheep", "animal_count", "animal_ready", "crop_count", "crop_ready"} else 100.0 if k in {"animal_yield", "crop_yield"} else 25.0) for k, v in tile.items()},
    }


def sale_quantity(action: Any, product: str) -> int:
    if not isinstance(action, dict):
        return 0
    total = 0
    for order in list(action.get("market", []) or []):
        if not isinstance(order, (list, tuple)) or len(order) < 3:
            continue
        if str(order[0]) == "SELL" and str(order[1]) == str(product):
            try:
                total += max(0, int(order[2]))
            except Exception:
                pass
    return total
