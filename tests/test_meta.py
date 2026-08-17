import numpy as np

from src.kagv2.equilibrium import solve_zero_sum, robust_population_mix
from src.kagv2.probes import feint_inventory_impact
from submission.meta_runtime import MetaPolicySelector


def test_rps_equilibrium_is_near_uniform():
    A=np.array([[0,-1,1],[1,0,-1],[-1,1,0]],float)
    r=solve_zero_sum(A,iterations=5000)
    p=np.array(r["row_mix"])
    assert np.max(np.abs(p-1/3))<0.05
    assert r["duality_gap"]<0.08


def test_robust_population_mix_is_simplex():
    A=np.array([[.10,-.05],[.02,.04],[-.10,.12]],float)
    r=robust_population_mix(A,opponent_prior=[.8,.2],iterations=3000)
    p=np.array(r["policy_mixture"])
    assert np.all(p>=0)
    assert abs(p.sum()-1)<1e-9


def test_meta_selector_confidence_gate_and_params():
    obj={"meta":{
        "policy_names":["safe","counter"],
        "policy_mixture":[.7,.3],
        "opponent_prior":[.5,.5],
        "payoff":[[0.01,0.01],[0.12,-0.15]],
        "policy_params":{"safe":{"late_wheat":19},"counter":{"late_wheat":28}},
        "default_policy":"safe","switch_margin":.02,"prior_strength":0.0,
    }}
    s=MetaPolicySelector(obj)
    assert s.update(3,[.5,.5],.2)=="safe"
    assert s.update(4,[.95,.05],.95)=="counter"
    assert s.current_params()["late_wheat"]==28


def test_feint_impact_only_sells_and_moves_inventory_forward():
    r=feint_inventory_impact("STRAWBERRY",10000,3)
    assert r["inventory_after"]==10003
    assert r["units"]==3
    assert len(r["quoted_prices"])==3
    assert r["revenue"]>0
