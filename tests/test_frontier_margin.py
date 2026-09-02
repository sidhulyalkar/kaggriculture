from kagv2.frontier_margin import build_runtime_source, candidate_configs


PARENT = '''
def agent(obs, configuration=None):
    return {
        "farmer": ["PASS"],
        "hands": [],
        "market": [["SELL", "WHEAT", 2], ["SELL", "MILK", 2]],
    }
'''


def obs(step=100):
    products = ["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"]
    return {
        "player": 0,
        "step": step,
        "day": step // 24,
        "hour": step % 24,
        "farms": [
            {"money": 3000, "farmer": [4,4], "hands": [], "tiles": [[None]*10 for _ in range(10)], "unlocked_quadrants": ["NW"]},
            {"money": 3000, "farmer": [4,4], "hands": [], "tiles": [[None]*10 for _ in range(10)], "unlocked_quadrants": ["NW"]},
        ],
        "private": {"shed": {**{p:0 for p in products}, "WHEAT":10, "MILK":10}, "inventories": [{}]},
        "market": {"inventory": {p:10000 for p in products}, "prices": {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}},
        "town": {"unlocked_shops": []},
    }


def load(cfg_name):
    source = build_runtime_source(PARENT, candidate_configs()[cfg_name], parent_label="test")
    env = {}
    exec(compile(source, "main.py", "exec"), env, env)
    return source, env


def test_compiled_control_is_parent_identical():
    _, env = load("V44_COMPILED_CONTROL")
    action = env["agent"](obs())
    assert action["farmer"] == ["PASS"]
    assert action["market"] == [["SELL", "WHEAT", 2], ["SELL", "MILK", 2]]


def test_fragility_reorders_sell_slots_without_touching_physical_route():
    _, env = load("V44_CORE")
    action = env["agent"](obs())
    assert action["farmer"] == ["PASS"]
    assert action["hands"] == []
    assert action["market"][0][1] == "MILK"
    assert env["_V44_STATS"]["physical_changed"] == 0


def test_terminal_liquidation_can_drop_and_sell_same_turn_when_safe():
    _, env = load("V44_CORE")
    state = obs(718)
    state["private"]["inventories"] = [{"MILK":3}]
    action = env["agent"](state)
    assert action["farmer"] == ["DROP"]
    milk = [o for o in action["market"] if o[0] == "SELL" and o[1] == "MILK"][0]
    assert milk[2] == 13


def test_final_agent_is_last_callable_for_kaggle_loader_contract():
    _, env = load("V44_CORE")
    callables = [v for v in env.values() if callable(v)]
    assert callables[-1] is env["agent"]
