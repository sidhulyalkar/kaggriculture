from __future__ import annotations

from pathlib import Path

from submission.v33_workgraph_agent import LabourOptionTwin, V33WorkGraphOverlay
from scripts.build_v33_workgraph_submission import build_source, validate_generated_source


def obs(day=10, hour=0, money=5000, opponent_money=None, hands=8, tiles=None, hires_today=9, quadrants=None):
    if tiles is None:
        tiles = [[None for _ in range(10)] for _ in range(10)]
    if quadrants is None:
        quadrants = ["NW", "NE"]
    farm = {
        "money": money,
        "unlocked_quadrants": list(quadrants),
        "hires_today": hires_today,
        "farmer": [4, 4],
        "hands": [[4, 4] for _ in range(hands)],
        "tiles": tiles,
    }
    rival = dict(farm)
    rival["money"] = money if opponent_money is None else opponent_money
    return {
        "player": 0,
        "step": day * 24 + hour,
        "day": day,
        "hour": hour,
        "farms": [farm, rival],
        "private": {"shed": {"WHEAT": 30}, "seeds": {}, "inventories": [{} for _ in range(hands + 1)]},
        "market": {
            "inventory": {},
            "prices": {"WHEAT": 25, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200, "FERTILIZER": 100},
        },
    }


def base_agent_with_market(market):
    def base_agent(observation, configuration=None):
        hands = (observation.get("farms", [{}])[0].get("hands", []) or [])
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": [list(x) for x in market]}
    return base_agent


def hire_count(actions):
    return sum(a[0] == "HIRE" for a in actions if isinstance(a, list) and a)


def test_cheap_hires_are_preserved():
    twin = LabourOptionTwin()
    v = twin.value_hire(obs(day=6, hires_today=0), units=3, hires_today=0, cash=5000)
    assert v.keep
    assert v.reason == "cheap_growth_hire"


def test_expensive_idle_hire_is_rejected_by_value_model():
    twin = LabourOptionTwin()
    v = twin.value_hire(obs(day=10, hour=8, hands=12, hires_today=9), units=13, hires_today=9, cash=900)
    assert not v.keep
    assert v.robust_roi < 1.0


def test_critical_feed_water_gap_protects_hire():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for x in range(5):
        tiles[0][x] = {
            "kind": "PLANT", "crop": "STRAWBERRY", "planted_day": 10,
            "yield_units": 0, "watered_today": False, "consecutive_unwatered": 1,
        }
    twin = LabourOptionTwin()
    v = twin.value_hire(obs(day=10, hour=15, hands=0, tiles=tiles, hires_today=9), units=1, hires_today=9, cash=5000)
    assert v.keep
    assert v.reason == "critical_service_gap"


def test_day_zero_planting_age_is_preserved():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    tiles[0][0] = {
        "kind": "PLANT", "crop": "WHEAT", "planted_day": 0,
        "yield_units": 3, "watered_today": True, "consecutive_unwatered": 0,
    }
    state = LabourOptionTwin().work_graph(obs(day=3, tiles=tiles), units=1)
    assert state.economic_weight > 0


def test_more_existing_labor_never_increases_marginal_hire_value():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for x in range(4):
        tiles[0][x] = {
            "kind": "PLANT", "crop": "WHEAT", "planted_day": 9,
            "yield_units": 3, "watered_today": False, "consecutive_unwatered": 0,
        }
    o = obs(day=10, hour=4, hands=4, tiles=tiles, hires_today=9)
    twin = LabourOptionTwin()
    low = twin.value_hire(o, units=3, hires_today=9, cash=5000)
    high = twin.value_hire(o, units=12, hires_today=9, cash=5000)
    assert high.robust_value <= low.robust_value


def test_late_capital_latch_is_one_time_and_persistent():
    overlay = V33WorkGraphOverlay(base_agent_with_market([]))
    first = obs(day=24, hour=1, money=12000, opponent_money=5000, hands=0, hires_today=0, quadrants=["NW", "NE", "SW"])
    overlay._update_capital_latch(first)
    assert overlay.capital_latch == "DEFEND"
    assert overlay.latched_lead == 7000
    later = obs(day=25, hour=0, money=6000, opponent_money=20000, hands=0, hires_today=0, quadrants=["NW", "NE", "SW"])
    overlay._update_capital_latch(later)
    assert overlay.capital_latch == "DEFEND"
    assert overlay.latched_lead == 7000


def test_late_latch_stays_base_below_threshold():
    overlay = V33WorkGraphOverlay(base_agent_with_market([]))
    overlay._update_capital_latch(obs(day=24, hour=1, money=11000, opponent_money=5000))
    assert overlay.capital_latch == "BASE"


def test_inactive_overlay_is_exact_black_box_parity():
    market = [["SELL", "MILK", 4], ["HIRE"], ["BUY_LAND"]]
    base = base_agent_with_market(market)
    overlay = V33WorkGraphOverlay(base)
    o = obs(day=5, hour=7, hands=1, hires_today=0)
    assert overlay.act(o) == base(o)


def test_midgame_gate_removes_at_most_one_expensive_marginal_hire():
    market = [["HIRE"], ["HIRE"], ["HIRE"], ["BUY_SEED", "STRAWBERRY", 2]]
    overlay = V33WorkGraphOverlay(base_agent_with_market(market))
    o = obs(day=11, hour=1, money=1000, opponent_money=1000, hands=10, hires_today=10, quadrants=["NW", "NE"])
    changed = overlay.act(o)["market"]
    assert hire_count(market) - hire_count(changed) == 1
    assert changed[-1] == ["BUY_SEED", "STRAWBERRY", 2]


def test_late_defend_can_remove_two_redundant_expensive_hires():
    market = [["SELL", "MILK", 4], ["HIRE"], ["HIRE"], ["HIRE"]]
    overlay = V33WorkGraphOverlay(base_agent_with_market(market))
    o = obs(day=24, hour=2, money=12000, opponent_money=5000, hands=10, hires_today=10, quadrants=["NW", "NE", "SW"])
    changed = overlay.act(o)["market"]
    assert overlay.capital_latch == "DEFEND"
    assert hire_count(market) - hire_count(changed) == 2
    assert changed[0] == ["SELL", "MILK", 4]


def test_late_base_mode_is_exact_parity():
    market = [["HIRE"], ["HIRE"], ["HIRE"]]
    base = base_agent_with_market(market)
    overlay = V33WorkGraphOverlay(base)
    o = obs(day=24, hour=2, money=11000, opponent_money=5000, hands=10, hires_today=10, quadrants=["NW", "NE", "SW"])
    assert overlay.act(o) == base(o)
    assert overlay.capital_latch == "BASE"


def test_generated_submission_is_single_file_loader_safe_on_dev_base():
    root = Path(__file__).resolve().parents[1]
    base_source = (root / "submission" / "base_controller.py").read_text(encoding="utf-8")
    source = build_source(base_source)
    assert "__file__" not in source
    assert "from .base_controller" not in source
    report = validate_generated_source(source)
    assert report["last_callable"] == "agent"
