from experiments.v80.opponent_shadow import OpponentShadow, town_drain


def obs(step, inv, prices=None, shops=None):
    return {
        "step": step, "day": step//24, "hour": step%24,
        "market": {"inventory": inv, "prices": prices or {k: 25 for k in inv}},
        "town": {"unlocked_shops": shops or []},
    }


def test_exact_nonbuyable_flow():
    products=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
    i0={p:100 for p in products}; i1=dict(i0)
    # previous step 4: we sell 3 CARROT, rival sells 5, PET_CAFE drains 2.
    i1["CARROT"] += 3+5-2
    s=OpponentShadow(); s.observe(obs(4,i0,shops=["PET_CAFE"]), previous_action={}, private_before={})
    e=s.observe(obs(5,i1,shops=["PET_CAFE"]), previous_action={"market":[["SELL","CARROT",3]]},
                private_before={"shed":{"CARROT":3}})
    assert e is not None
    assert e.lower["CARROT"] == 5 and e.upper["CARROT"] == 5, (e.lower,e.upper)


def test_town_multiplicity_and_center():
    d=town_drain(24,["YARN_STORE","YARN_STORE","BAKERY"])
    # Two single-product yarn stores drain 4 wool; center adds 1. Bakery adds
    # one egg/wheat and center adds another one each.
    assert d["WOOL"] == 5
    assert d["WHEAT"] == 2
    assert d["EGG"] == 2
    assert d["CARROT"] == 1
    assert d["FERTILIZER"] == 0


def test_buyable_is_interval():
    products=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
    i0={p:100 for p in products}; i1=dict(i0)
    # No town drain at step 5. Shared wheat falls by 2. Our previous action
    # requested a buy of up to 2, so rival net flow is deliberately interval-valued.
    i1["WHEAT"] -= 2
    s=OpponentShadow(); s.observe(obs(5,i0), {}, {})
    e=s.observe(obs(6,i1), {"market":[["BUY_PRODUCT","WHEAT",2]]}, {"shed":{}})
    assert e.lower["WHEAT"] <= e.upper["WHEAT"]


if __name__ == '__main__':
    test_exact_nonbuyable_flow(); test_town_multiplicity_and_center(); test_buyable_is_interval()
    print('V80_SHADOW_UNIT_TESTS PASS')
