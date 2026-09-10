from __future__ import annotations

import json
import pathlib

BASE = pathlib.Path("experiments/v87/current_shape.py")
MODEL = pathlib.Path("experiments/v87/results/router_model.json")
OUT = pathlib.Path("experiments/v87/generated/v87_counterfactual_shape.py")

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SHOP_NAMES = ("YARN_STORE", "FARMERS_MARKET", "BAKERY", "PET_CAFE", "ICE_CREAM_SHOP", "PIZZA_SHOP")

OLD_LOOP = '''        for (turn, feat, thr, target) in DECISIONS:\n            if turn == step and target != self.cur and self._switch_ok(target, turn):\n                if _feature(obs, feat) >= thr:\n                    self.cur = target\n'''

NEW_LOOP = '''        for (turn, feat, thr, target) in DECISIONS:\n            if turn != step or target == self.cur or not self._switch_ok(target, turn):\n                continue\n            take = _feature(obs, feat) >= thr\n            cfg = V87_MODEL.get(str(turn))\n            if cfg and cfg.get("enabled"):\n                take = _v87_tree_take(cfg["tree"], _v87_features(obs, me))\n            if take:\n                self.cur = target\n'''

HELPER_TEMPLATE = r'''

# ---- V87 lineage-held-out counterfactual route router ----
V87_MODEL = __MODEL__
V87_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
V87_SHOPS = ("YARN_STORE", "FARMERS_MARKET", "BAKERY", "PET_CAFE", "ICE_CREAM_SHOP", "PIZZA_SHOP")


def _v87_count_land(v):
    if isinstance(v, int):
        return int(v)
    if isinstance(v, (list, tuple, set, dict)):
        return len(v)
    return 0


def _v87_farm_stats(farm):
    out = {"money": float(farm.get("money", 0) or 0), "hands": len(farm.get("hands") or []),
           "land": _v87_count_land(farm.get("unlocked_land")), "plants": 0, "pastures": 0,
           "coops": 0, "weeds": 0, "cows": 0, "sheep": 0, "geese": 0}
    for row in farm.get("tiles") or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind") or "")
            if kind == "PLANT": out["plants"] += 1
            elif kind == "PASTURE": out["pastures"] += 1
            elif kind == "COOP": out["coops"] += 1
            elif kind == "WEED": out["weeds"] += 1
            animal = str(tile.get("animal") or "")
            if animal == "COW": out["cows"] += 1
            elif animal == "SHEEP": out["sheep"] += 1
            elif animal == "GOOSE": out["geese"] += 1
    return out


def _v87_features(obs, seat):
    farms = obs.get("farms") or [{}, {}]
    me = int(obs.get("player", seat) or seat)
    if me not in (0, 1): me = seat
    own = _v87_farm_stats(farms[me]); opp = _v87_farm_stats(farms[1-me])
    market = obs.get("market") or {}; prices = market.get("prices") or {}; inventory = market.get("inventory") or {}
    private = obs.get("private") or {}; shed = private.get("shed") or {}; seeds = private.get("seeds") or {}
    shops = (obs.get("town") or {}).get("unlocked_shops") or []
    f = {
        "own_money": own["money"], "opp_money": opp["money"], "money_diff": own["money"]-opp["money"],
        "own_hands": own["hands"], "opp_hands": opp["hands"], "hands_diff": own["hands"]-opp["hands"],
        "own_land": own["land"], "opp_land": opp["land"], "land_diff": own["land"]-opp["land"],
        "own_plants": own["plants"], "opp_plants": opp["plants"], "plants_diff": own["plants"]-opp["plants"],
        "own_pastures": own["pastures"], "opp_pastures": opp["pastures"], "pastures_diff": own["pastures"]-opp["pastures"],
        "own_coops": own["coops"], "opp_coops": opp["coops"], "coops_diff": own["coops"]-opp["coops"],
        "own_cows": own["cows"], "opp_cows": opp["cows"], "cows_diff": own["cows"]-opp["cows"],
        "own_sheep": own["sheep"], "opp_sheep": opp["sheep"], "sheep_diff": own["sheep"]-opp["sheep"],
        "own_geese": own["geese"], "opp_geese": opp["geese"], "geese_diff": own["geese"]-opp["geese"],
        "shop_total": len(shops),
    }
    for name in V87_SHOPS: f["shop_"+name] = shops.count(name)
    for item in V87_PRODUCTS:
        f["price_"+item] = float(prices.get(item, 0) or 0)
        f["market_"+item] = float(inventory.get(item, 0) or 0)
        f["shed_"+item] = float(shed.get(item, 0) or 0)
    for item in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        f["seed_"+item] = float(seeds.get(item, 0) or 0)
    return f


def _v87_tree_take(tree, f):
    node = 0
    left, right = tree["left"], tree["right"]
    while left[node] != right[node]:
        idx = tree["feature"][node]
        name = tree["feature_names"][idx]
        node = left[node] if float(f.get(name, 0.0)) <= tree["threshold"][node] else right[node]
    return tree["value"][node] > 0.0
'''


def main():
    source = BASE.read_text()
    model = json.loads(MODEL.read_text())["checkpoints"]
    if source.count(OLD_LOOP) != 1:
        raise RuntimeError("upstream Shape decision loop changed")
    helper = HELPER_TEMPLATE.replace("__MODEL__", repr(model))
    source = source.replace("class Agent:", helper + "\n\nclass Agent:", 1)
    source = source.replace(OLD_LOOP, NEW_LOOP, 1)
    compile(source, str(OUT), "exec")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(source)
    print(OUT, OUT.stat().st_size)
    print("enabled", {k: v.get("enabled") for k, v in model.items()})


if __name__ == "__main__":
    main()
