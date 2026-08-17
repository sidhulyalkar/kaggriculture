from src.kagv2.simulator import Game, new_plant, new_animal


def test_planting_day_unwatered_dies():
    g = Game(seed=0)
    g.farms[0]["tiles"][4][4] = new_plant("WHEAT", 0)
    g._eod()
    assert g.farms[0]["tiles"][4][4]["kind"] == "WEED"


def test_care_bonus_is_one():
    g = Game(seed=0)
    t = new_animal("COW", 0)
    t["fed_today"] = True
    t["cared_today"] = True
    g.farms[0]["tiles"][4][4] = t
    g._eod()
    assert g.farms[0]["tiles"][4][4].get("pending_care_bonus") == 1


def test_occupied_dig_noop():
    g = Game(seed=0)
    g.farms[0]["tiles"][4][4] = new_animal("COW", 0)
    g._apply_unit(0, 0, ["DIG"])
    assert g.farms[0]["tiles"][4][4].get("animal") == "COW"


def test_locked_movement_allowed():
    g = Game(seed=0)
    g.farms[0]["farmer"] = [4, 4]
    g._apply_unit(0, 0, ["EAST"])
    assert g.farms[0]["farmer"] == [5, 4]
