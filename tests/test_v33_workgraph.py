from __future__ import annotations

from submission.v33_workgraph_agent import LabourOptionTwin
from scripts.build_v33_workgraph_submission import build_source, validate_source


def obs(day=10, hour=0, money=5000, hands=8, tiles=None, hires_today=9):
    if tiles is None:
        tiles = [[None for _ in range(10)] for _ in range(10)]
    farm = {
        "money": money,
        "unlocked_quadrants": ["NW", "NE"],
        "hires_today": hires_today,
        "farmer": [4, 4],
        "hands": [[4, 4] for _ in range(hands)],
        "tiles": tiles,
    }
    return {
        "player": 0,
        "step": day * 24 + hour,
        "day": day,
        "hour": hour,
        "farms": [farm, dict(farm)],
        "private": {"shed": {"WHEAT": 30}, "seeds": {}, "inventories": [{} for _ in range(hands + 1)]},
        "market": {
            "inventory": {},
            "prices": {"WHEAT": 25, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200, "FERTILIZER": 100},
        },
    }


def test_cheap_hires_are_preserved():
    twin = LabourOptionTwin()
    v = twin.value_hire(obs(day=6, hires_today=0), {}, units=3, hires_today=0, cash=5000)
    assert v.keep
    assert v.reason == "cheap_growth_hire"


def test_expensive_idle_hire_is_rejected():
    twin = LabourOptionTwin()
    # 9 previous hires => the next Fibonacci cost is already expensive.  With a
    # large existing crew and no urgent work, another expiring hand has no edge.
    o = obs(day=10, hour=8, hands=12, hires_today=9)
    counts = {"COW": 0, "SHEEP": 0, "GOOSE": 0, "WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0}
    v = twin.value_hire(o, counts, units=13, hires_today=9, cash=900)
    assert not v.keep
    assert v.robust_roi < 1.0


def test_critical_feed_water_gap_protects_v32_hire():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    # Several dry planting-day crops create a genuine service emergency.
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
    counts = {"COW": 0, "SHEEP": 0, "GOOSE": 0, "WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 5, "MELON": 0}
    v = twin.value_hire(o, counts, units=1, hires_today=9, cash=5000)
    assert v.keep
    assert v.reason == "critical_service_gap"


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
    counts = {"COW": 0, "SHEEP": 0, "GOOSE": 0, "WHEAT": 4, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0}
    low_capacity = twin.value_hire(o, counts, units=3, hires_today=9, cash=5000)
    high_capacity = twin.value_hire(o, counts, units=12, hires_today=9, cash=5000)
    assert high_capacity.robust_value <= low_capacity.robust_value


def test_generated_submission_is_single_file_loader_safe():
    source = build_source()
    assert "__file__" not in source
    assert "from .base_controller" not in source
    report = validate_source(source)
    assert report["last_callable"] == "agent"
