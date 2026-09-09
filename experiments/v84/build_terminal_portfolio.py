from __future__ import annotations

import pathlib

BASE = pathlib.Path('experiments/v81/generated/v81_farming_clock.py')
OUT = pathlib.Path('experiments/v84/generated/v84_terminal_portfolio.py')

WRAP = r'''

# ---- V84 append-only terminal portfolio ----
def _v84_terminal(action, observation, seat, step):
    if step != 718:
        return action
    private = _get(observation, "private", {}) or {}
    shed = dict(_get(private, "shed", {}) or {})
    market = _get(observation, "market", {}) or {}
    prices = _get(market, "prices", {}) or {}
    result = _copy_action(action)
    committed = {}
    for order in result.get("market") or []:
        if order and len(order) >= 3 and order[0] == "SELL":
            committed[order[1]] = committed.get(order[1], 0) + max(0, int(order[2] or 0))
    candidates = []
    for item, raw in shed.items():
        qty = max(0, int(raw or 0)) - committed.get(item, 0)
        price = float(_get(prices, item, 0) or 0)
        if qty > 0 and price > 0:
            candidates.append((price, str(item), qty))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    for _, item, qty in candidates:
        if len(result["market"]) >= 10:
            break
        result["market"].append(["SELL", item, qty])
    return result


def agent(observation, configuration=None):
    seat = _seat(observation)
    raw_step = _get(observation, "step", None)
    step = int(raw_step) if raw_step is not None else int(_get(observation, "day", 0) or 0) * 24 + int(_get(observation, "hour", 0) or 0)
    action = _v81_base_agent(observation, configuration)
    return _v84_terminal(action, observation, seat, step)
'''


def main():
    source = BASE.read_text()
    needle = 'def agent(observation, configuration=None):'
    if source.count(needle) != 1:
        raise RuntimeError(source.count(needle))
    source = source.replace(needle, 'def _v81_base_agent(observation, configuration=None):')
    out = source + WRAP
    compile(out, str(OUT), 'exec')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out)
    print(OUT, OUT.stat().st_size)

if __name__ == '__main__': main()
