from __future__ import annotations

from submission.v33_workgraph_agent import LabourOptionTwin, V33WorkGraphMind
from scripts.build_v33_workgraph_submission import build_source, validate_source


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


def counts(**updates):
    out = {"COW": 0, "SHEEP": 0, "GOOSE": 0, "WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0,
           "PASTURE": 0, "COOP": 0, "WEED": 0, "EMPTY": 0}
    out.update(updates)
    return out


def hire_count(actions):
    return sum(a[0] == "HIRE" for a in actions if isinstance(a, list) and a)


def test_cheap_hires_are_preserved():
    twin = LabourOptionTwin()
    v = twin.value_hire(obs(day=6, hires_today=0), counts(), units=3, hires_today=0, cash=5000)
    assert v.keep
    assert v.reason == "cheap_growth_hire"


def test_expensive_idle_hire_is_rejected_by_value_model():
    twin = LabourOptionTwin()
    o = obs(day=10, hour=8, hands=12, hires_today=9)
    v = twin.value_hire(o, counts(), units=13, hires_today=9, cash=900)
    assert not v.keep
    assert v.robust_roi < 1.0


def test_critical_feed_water_gap_protects_v32_hire():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for x in range(5):
        tiles[0][x] = {
            "kind": "PLANT",
            "crop": "STRAWBERRY",
            "planted_day": 10,
            "yield_units": 0,
            "watered_today": False,
            "consecutive_unwatered": 1,
        }
    twin = LabourOptionTwin()
    o = obs(day=10, hour=15, hands=0, tiles=tiles, hires_today=9)
    v = twin.value_hire(o, counts(STRAWBERRY=5), units=1, hires_today=9, cash=5000)
    assert v.keep
    assert v.reason == "critical_service_gap"


def test_day_zero_planting_age_is_not_collapsed_to_zero_later():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    tiles[0][0] = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "planted_day": 0,
        "yield_units": 3,
        "watered_today": True,
        "consecutive_unwatered": 0,
    }
    twin = LabourOptionTwin()
    state = twin.work_graph(obs(day=3, tiles=tiles), counts(WHEAT=1), units=1)
    assert state.economic_weight > 0


def test_more_existing_labor_never_increases_marginal_hire_value():
    twin = LabourOptionTwin()
    tiles = [[None for _ in range(10)] for _ in range(10)]
    for x in range(4):
        tiles[0][x] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 9,
            "yield_units": 3,
            "watered_today": False,
            "consecutive_unwatered": 0,
        }
    o = obs(day=10, hour=4, hands=4, tiles=tiles, hires_today=9)
    c = counts(WHEAT=4)
    low_capacity = twin.value_hire(o, c, units=3, hires_today=9, cash=5000)
    high_capacity = twin.value_hire(o, c, units=12, hires_today=9, cash=5000)
    assert high_capacity.robust_value <= low_capacity.robust_value


def test_late_capital_latch_activates_once_on_large_public_lead():
    mind = V33WorkGraphMind()
    first = obs(day=24, hour=1, money=12000, opponent_money=5000, hands=0, hires_today=0,
                quadrants=["NW", "NE", "SW"])
    mind._update_capital_latch(first)
    assert mind.capital_latch == "DEFEND"
    assert mind.latched_lead == 7000

    later = obs(day=25, hour=0, money=6000, opponent_money=20000, hands=0, hires_today=0,
                quadrants=["NW", "NE", "SW"])
    mind._update_capital_latch(later)
    assert mind.capital_latch == "DEFEND"
    assert mind.latched_lead == 7000


def test_late_capital_latch_stays_base_below_lead_threshold():
    mind = V33WorkGraphMind()
    mind._update_capital_latch(obs(day=24, hour=1, money=11000, opponent_money=5000))
    assert mind.capital_latch == "BASE"


def test_midgame_gate_changes_only_the_last_expensive_marginal_hire():
    # After the first market turn of the day, ten hands may already exist and
    # V32 asks for the 11th/12th/13th hires. Only the $233 marginal hire is
    # eligible in BASE mode, so this state must produce exactly one suppression.
    mind = V33WorkGraphMind()
    o = obs(day=11, hour=1, money=1000, opponent_money=1000, hands=10, hires_today=10,
            quadrants=["NW", "NE"])
    base = super(V33WorkGraphMind, mind)._market(o, counts())
    changed = mind._market(o, counts())
    assert hire_count(base) - hire_count(changed) == 1
    assert mind._suppressed_today == 1


def test_late_defend_can_remove_two_redundant_expensive_hires():
    mind = V33WorkGraphMind()
    o = obs(day=24, hour=2, money=12000, opponent_money=5000, hands=10, hires_today=10,
            quadrants=["NW", "NE", "SW"])
    base = super(V33WorkGraphMind, mind)._market(o, counts())
    changed = mind._market(o, counts())
    assert mind.capital_latch == "DEFEND"
    assert hire_count(base) - hire_count(changed) == 2
    assert mind._suppressed_today == 2


def test_late_base_mode_is_exact_v32_on_same_marginal_hire_state():
    mind = V33WorkGraphMind()
    o = obs(day=24, hour=2, money=11000, opponent_money=5000, hands=10, hires_today=10,
            quadrants=["NW", "NE", "SW"])
    base = super(V33WorkGraphMind, mind)._market(o, counts())
    changed = mind._market(o, counts())
    assert mind.capital_latch == "BASE"
    assert changed == base


def test_generated_submission_is_single_file_loader_safe():
    source = build_source()
    assert "__file__" not in source
    assert "from .base_controller" not in source
    report = validate_source(source)
    assert report["last_callable"] == "agent"
