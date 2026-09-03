from __future__ import annotations

"""Tiny runtime-only opponent supply reconstruction for Kaggriculture.

The implementation intentionally mirrors the V51/V52 validated accounting
contract without importing the research stack.  It uses only information the
agent owns at inference time: two consecutive public observations plus its own
previous action/private state.
"""

NONBUYABLE_PRODUCTS = frozenset({"CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"})
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
SHED_ACCESS = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})


def canonical_step(obs):
    raw = (obs or {}).get("step")
    if raw is not None:
        return int(raw)
    return int((obs or {}).get("day", 0) or 0) * 24 + int((obs or {}).get("hour", 0) or 0)


def town_drain_for_turn(step, shops, product):
    drain = 0
    if int(step) % 4 == 0:
        for shop in shops or ():
            products = SHOP_PRODUCTS.get(str(shop), ())
            if product in products:
                drain += 2 if len(products) == 1 else 1
    if product != "FERTILIZER" and int(step) % 24 == 0:
        drain += 1
    return drain


def _inventory(raw):
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        try:
            out[str(key)] = max(0, int(value or 0))
        except Exception:
            pass
    return out


def _unit_positions(obs):
    farms = list((obs or {}).get("farms", []) or [])
    player = int((obs or {}).get("player", 0) or 0)
    farm = farms[player] if 0 <= player < len(farms) else {}
    farmer = farm.get("farmer")
    positions = [tuple(map(int, farmer[:2])) if isinstance(farmer, (list, tuple)) and len(farmer) >= 2 else None]
    for pos in list(farm.get("hands", []) or []):
        positions.append(tuple(map(int, pos[:2])) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else None)
    return positions


def _unit_actions(action, count):
    action = action if isinstance(action, dict) else {}
    result = [action.get("farmer", ["PASS"])]
    if isinstance(action.get("hands"), list):
        result.extend(action["hands"])
    result.extend([["PASS"]] * max(0, count - len(result)))
    return result[:count]


def post_physical_shed(obs, action):
    """Mirror same-turn shed mutations before the market queue executes."""
    private = (obs or {}).get("private", {}) or {}
    shed = _inventory(private.get("shed", {}) or {})
    inventories = [_inventory(x) for x in list(private.get("inventories", []) or [])]
    positions = _unit_positions(obs)
    inventories.extend({} for _ in range(max(0, len(positions) - len(inventories))))

    def room():
        return max(0, 100 - sum(shed.values()))

    for idx, (pos, unit_action) in enumerate(zip(positions, _unit_actions(action, len(positions)))):
        if pos not in SHED_ACCESS or not isinstance(unit_action, (list, tuple)) or not unit_action:
            continue
        op = str(unit_action[0])
        inv = inventories[idx]
        if op == "DROP":
            for item, quantity in list(inv.items()):
                take = min(max(0, int(quantity)), room())
                if take:
                    shed[item] = shed.get(item, 0) + take
                inv.pop(item, None)
        elif op == "PLACE" and len(unit_action) >= 2:
            item = str(unit_action[1])
            requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            take = min(max(0, requested), inv.get(item, 0), room())
            if take:
                inv[item] -= take
                shed[item] = shed.get(item, 0) + take
        elif op == "PICKUP" and len(unit_action) >= 2:
            item = str(unit_action[1])
            requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            take = min(max(0, requested), shed.get(item, 0))
            if take:
                shed[item] -= take
                inv[item] = inv.get(item, 0) + take
    return shed


def requested_sell(action, product):
    if not isinstance(action, dict):
        return 0
    total = 0
    for order in list(action.get("market", []) or []):
        if isinstance(order, (list, tuple)) and len(order) >= 3 and str(order[0]) == "SELL" and str(order[1]) == str(product):
            try:
                total += max(0, int(order[2]))
            except Exception:
                pass
    return total


def executed_own_sell(obs, action, product):
    return min(requested_sell(action, product), int(post_physical_shed(obs, action).get(str(product), 0) or 0))


def infer_external_supply(prev_obs, curr_obs, own_previous_action, product):
    """Return exact opponent effective sale units, or ``None`` when censored.

    WHEAT/FERTILIZER are intentionally unsupported because opponent BUY_PRODUCT
    is observationally confounded with selling.  Price-floor transitions are
    also fail-closed because $1 sales stop increasing public market inventory.
    """
    product = str(product)
    if product not in NONBUYABLE_PRODUCTS:
        return None
    prev_market = (prev_obs or {}).get("market", {}) or {}
    curr_market = (curr_obs or {}).get("market", {}) or {}
    prev_inv = int((prev_market.get("inventory", {}) or {}).get(product, 10000) or 10000)
    curr_inv = int((curr_market.get("inventory", {}) or {}).get(product, 10000) or 10000)
    prev_price = int((prev_market.get("prices", {}) or {}).get(product, 1) or 1)
    curr_price = int((curr_market.get("prices", {}) or {}).get(product, 1) or 1)
    if prev_price <= 1 or curr_price <= 1:
        return None
    shops = list((((prev_obs or {}).get("town", {}) or {}).get("unlocked_shops", []) or []))
    drain = town_drain_for_turn(canonical_step(prev_obs), shops, product)
    external = curr_inv - prev_inv + drain - executed_own_sell(prev_obs, own_previous_action, product)
    return max(0, int(external))
