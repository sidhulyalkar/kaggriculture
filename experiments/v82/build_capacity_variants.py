from __future__ import annotations

import argparse
import pathlib

BUNDLES = {
    88: {"name": "cow88", "qty": 1, "steps": (88, 92, 95)},
    150: {"name": "cow150", "qty": 2, "steps": (150, 152, 153, 156)},
    169: {"name": "cow169", "qty": 1, "steps": (169, 175, 177)},
    176: {"name": "cow176", "qty": 1, "steps": (176, 180, 183)},
}

WRAPPER = r'''

# ---- V82 sparse capacity-allocation wrapper ----
_V82_BUNDLES = __BUNDLES__
_V82_STEP_TO_PURCHASE = {
    s: p for p, b in _V82_BUNDLES.items() for s in b["steps"]
}
_V82_STATE = {0: {}, 1: {}}
_V82_THRESHOLD = __THRESHOLD__
_V82_REPAIR_SALES = __REPAIR__
_V82_MAX_CONVERT = 3


def _v82_pressure(observation):
    town = _get(observation, "town", {}) or {}
    shops = list(_get(town, "unlocked_shops", []) or [])
    market = _get(observation, "market", {}) or {}
    prices = _get(market, "prices", {}) or {}
    milk = float(_get(prices, "MILK", 160) or 0)
    wool = float(_get(prices, "WOOL", 200) or 0)
    yarn = sum(1 for s in shops if s == "YARN_STORE")
    dairy = sum(1 for s in shops if s in {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"})
    return 2.0 * yarn + wool / 200.0 - (dairy + milk / 160.0)


def _v82_reset():
    return {"last_step": -1, "assign": {}, "converted": 0}


def _v82_assign(observation, seat, purchase_step):
    state = _V82_STATE[seat]
    if purchase_step in state["assign"]:
        return state["assign"][purchase_step]
    bundle = _V82_BUNDLES[purchase_step]
    target = "COW"
    qty = int(bundle["qty"])
    farm = _farm(observation, seat)
    money = float(_get(farm, "money", 0) or 0)
    # Sheep cost 100 more than cow. Fail closed unless there is ample visible buffer.
    if (
        _v82_pressure(observation) >= _V82_THRESHOLD
        and state["converted"] + qty <= _V82_MAX_CONVERT
        and money >= 1000 + 100 * qty
    ):
        target = "SHEEP"
        state["converted"] += qty
    state["assign"][purchase_step] = target
    return target


def _v82_replace_bundle(action, observation, seat, step):
    purchase_step = _V82_STEP_TO_PURCHASE.get(step)
    if purchase_step is None:
        return action
    target = _v82_assign(observation, seat, purchase_step)
    if target == "COW":
        return action
    result = _copy_action(action)
    for command in [result["farmer"], *result["hands"]]:
        if command and command[0] in {"PICKUP", "PLACE"} and len(command) >= 2 and command[1] == "COW":
            command[1] = "SHEEP"
    for order in result["market"]:
        if order and order[0] == "BUY_ANIMAL" and len(order) >= 3 and order[1] == "COW":
            order[1] = "SHEEP"
    return result


def _v82_repair_animal_sales(action, observation, seat):
    if not _V82_REPAIR_SALES or _V82_STATE[seat].get("converted", 0) <= 0:
        return action
    # Avoid touching turns that may project a same-turn DROP into the shed.
    units = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    if any(cmd and cmd[0] in {"DROP", "PLACE"} for cmd in units):
        return action
    private = _get(observation, "private", {}) or {}
    shed = dict(_get(private, "shed", {}) or {})
    result = _copy_action(action)
    avail = {"MILK": max(0, int(_get(shed, "MILK", 0) or 0)),
             "WOOL": max(0, int(_get(shed, "WOOL", 0) or 0))}
    for order in result["market"]:
        if not order or len(order) < 3 or order[0] != "SELL" or order[1] not in avail:
            continue
        item = order[1]
        other = "WOOL" if item == "MILK" else "MILK"
        qty = max(0, int(order[2] or 0))
        if avail[item] >= qty:
            avail[item] -= qty
            continue
        if avail[item] == 0 and avail[other] >= qty:
            order[1] = other
            avail[other] -= qty
        else:
            avail[item] = max(0, avail[item] - min(avail[item], qty))
    return result


def agent(observation, configuration=None):
    seat = _seat(observation)
    raw_step = _get(observation, "step", None)
    step = int(raw_step) if raw_step is not None else int(_get(observation, "day", 0) or 0) * 24 + int(_get(observation, "hour", 0) or 0)
    state = _V82_STATE[seat]
    if not state or step == 0 or step <= int(state.get("last_step", -1)):
        state = _v82_reset()
        _V82_STATE[seat] = state
    action = _v81_base_agent(observation, configuration)
    action = _v82_replace_bundle(action, observation, seat, step)
    action = _v82_repair_animal_sales(action, observation, seat)
    state["last_step"] = step
    return action
'''


def build(source: str, threshold: float, repair: bool) -> str:
    needle = "def agent(observation, configuration=None):"
    if source.count(needle) != 1:
        raise RuntimeError(f"expected one agent definition, found {source.count(needle)}")
    source = source.replace(needle, "def _v81_base_agent(observation, configuration=None):")
    wrapper = WRAPPER.replace("__BUNDLES__", repr(BUNDLES))
    wrapper = wrapper.replace("__THRESHOLD__", repr(float(threshold)))
    wrapper = wrapper.replace("__REPAIR__", "True" if repair else "False")
    out = source + wrapper
    compile(out, "v82_candidate.py", "exec")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="experiments/v81/generated/v81_farming_clock.py")
    ap.add_argument("--out", default="experiments/v82/generated")
    args = ap.parse_args()
    source = pathlib.Path(args.base).read_text()
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    variants = {
        "v82_relabel_only": (1.0, False),
        "v82_relabel_repair_t05": (0.5, True),
        "v82_relabel_repair_t10": (1.0, True),
        "v82_relabel_repair_t15": (1.5, True),
    }
    for name, (threshold, repair) in variants.items():
        p = out / f"{name}.py"
        p.write_text(build(source, threshold, repair))
        print(name, p.stat().st_size)


if __name__ == "__main__":
    main()
