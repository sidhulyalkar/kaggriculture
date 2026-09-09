from __future__ import annotations

import pathlib

BASE = pathlib.Path('experiments/v85/current_shape.py')
OUT = pathlib.Path('experiments/v85/generated/v85_shape_terminal.py')

WRAP = r'''

# ---- V85 current Shape + append-only terminal portfolio ----
def _v85_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _v85_copy_action(action):
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(x or ["PASS"]) for x in (action.get("hands") or [])],
        "market": [list(x) for x in (action.get("market") or [])],
    }


def _v85_terminal(action, observation, step):
    if step != 718:
        return action
    private = _v85_get(observation, "private", {}) or {}
    shed = dict(_v85_get(private, "shed", {}) or {})
    market_state = _v85_get(observation, "market", {}) or {}
    prices = _v85_get(market_state, "prices", {}) or {}
    result = _v85_copy_action(action)
    committed = {}
    for order in result["market"]:
        if order and len(order) >= 3 and order[0] == "SELL":
            committed[str(order[1])] = committed.get(str(order[1]), 0) + max(0, int(order[2] or 0))
    candidates = []
    for item, raw in shed.items():
        qty = max(0, int(raw or 0)) - committed.get(str(item), 0)
        price = float(_v85_get(prices, item, 0) or 0)
        if qty > 0 and price > 0:
            candidates.append((price, str(item), qty))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    for _, item, qty in candidates:
        if len(result["market"]) >= 10:
            break
        result["market"].append(["SELL", item, qty])
    return result


def agent(observation, configuration=None):
    del configuration
    raw_step = _v85_get(observation, "step", None)
    step = int(raw_step) if raw_step is not None else int(_v85_get(observation, "day", 0) or 0) * 24 + int(_v85_get(observation, "hour", 0) or 0)
    action = _shape_base_agent(observation)
    return _v85_terminal(action, observation, step)
'''


def main():
    source = BASE.read_text()
    needle = 'def agent(obs):'
    if source.count(needle) != 1:
        raise RuntimeError(f'agent count={source.count(needle)}')
    source = source.replace(needle, 'def _shape_base_agent(obs):')
    out = source + WRAP
    compile(out, str(OUT), 'exec')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out)
    print(OUT, OUT.stat().st_size)

if __name__ == '__main__': main()
