from swarm.v58_opponent_policy_compiler import (
    action_skeleton,
    cluster_families,
    public_features,
)


def _trace(actions, team="T"):
    return {"action_map": {i: a for i, a in enumerate(actions)}, "team": team}


def _act(op="PASS", item=None):
    farmer=[op] if item is None else [op,item]
    return {"farmer":farmer,"hands":[],"market":[]}


def test_action_skeleton_ignores_quantities_but_keeps_operation_identity():
    a={"farmer":["PASS"],"hands":[],"market":[["SELL","STRAWBERRY",3]]}
    b={"farmer":["PASS"],"hands":[],"market":[["SELL","STRAWBERRY",19]]}
    c={"farmer":["PASS"],"hands":[],"market":[["SELL","WOOL",19]]}
    assert action_skeleton(a)==action_skeleton(b)
    assert action_skeleton(a)!=action_skeleton(c)


def test_cluster_families_merges_same_prefix_and_separates_different_routes():
    a=[_act("MOVE","N") for _ in range(120)]
    b=[_act("MOVE","N") for _ in range(120)]
    c=[_act("MOVE","S") for _ in range(120)]
    labels=cluster_families([_trace(a,"A"),_trace(b,"B"),_trace(c,"C")],threshold=.90)
    assert labels[0]==labels[1]
    assert labels[2]!=labels[0]


def test_public_features_use_shared_observation_and_target_public_farm_only():
    obs={
        "farms":[
            {"money":100,"unlocked_quadrants":[0],"farmer":[0,0],"hands":[],"hires_today":0,"tiles":[[{"kind":"PLANT","crop":"WHEAT"}]]},
            {"money":250,"unlocked_quadrants":[0,1],"farmer":[4,5],"hands":[[6,5]],"hires_today":1,"tiles":[[{"kind":"PASTURE","animal":"SHEEP"}]]},
        ],
        "market":{"inventory":{"WOOL":10012},"prices":{"WOOL":89}},
        "town":{"unlocked_shops":["YARN_STORE"]},
        "private":{"shed":{"WOOL":999}},
    }
    f=public_features(obs,1)
    assert f["money"]==250
    assert f["quadrants"]==2
    assert f["units"]==2
    assert f["tile_PASTURE"]==1
    assert f["animal_SHEEP"]==1
    assert f["inv_WOOL"]==10012
    assert f["price_WOOL"]==89
    assert f["shop0_YARN_STORE"]==1
    assert all("private" not in k.lower() and "shed" not in k.lower() for k in f)
