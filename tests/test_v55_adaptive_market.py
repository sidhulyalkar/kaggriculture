import json

from submission.adaptive_market_agent import AdaptiveMarketMind, OnlineOpponentModel
from submission.market_flow_runtime import requested_sell, infer_external_supply
from submission.market_predictor import DistilledSalePredictor, public_sale_features as runtime_features
from swarm.market_belief import public_sale_features as research_features


def _obs(step=25,player=0,straw_inv=10029,straw_price=64,straw_shed=10):
    return {
        "step":step,"day":step//24,"hour":step%24,"player":player,
        "farms":[
            {"farmer":[4,4],"hands":[[4,5]],"money":4200,"unlocked_quadrants":["NW","NE"],"tiles":[[]]},
            {"farmer":[5,5],"hands":[[5,4],[8,8]],"money":5000,"unlocked_quadrants":["NW","SW"],"tiles":[[]]},
        ],
        "private":{"shed":{"STRAWBERRY":straw_shed},"inventories":[{},{}],"seeds":{}},
        "market":{"inventory":{"STRAWBERRY":straw_inv},"prices":{"STRAWBERRY":straw_price}},
        "town":{"unlocked_shops":[]},
    }


def _model(tmp_path):
    path=tmp_path/"model.json"
    path.write_text(json.dumps({"models":{"STRAWBERRY":{"features":["market_price_ratio"],"mean":[0.0],"scale":[1.0],"coef":[10.0],"intercept":-5.0,"threshold":0.5,"prevalence":0.08,"shock_mean":8.0}}}),encoding="utf-8")
    return path


def test_runtime_feature_contract_matches_research_extractor():
    obs=_obs();a=runtime_features(obs,1,"STRAWBERRY");b=research_features(obs,1,"STRAWBERRY")
    assert set(a)==set(b)
    for key in a:assert abs(float(a[key])-float(b[key]))<1e-9,key


def test_runtime_market_queue_respects_first_ten_orders():
    action={"market":[["SELL","WOOL",1]]*10+[["SELL","STRAWBERRY",9]]}
    assert requested_sell(action,"STRAWBERRY")==0


def test_online_opponent_model_updates_exact_dump_posterior(tmp_path):
    predictor=DistilledSalePredictor(str(_model(tmp_path)));online=OnlineOpponentModel(predictor)
    before=online.rates("STRAWBERRY",1)[0];prev=_obs(step=25,straw_inv=10000,straw_price=120,straw_shed=0);curr=_obs(step=26,straw_inv=10006,straw_price=108,straw_shed=0)
    assert infer_external_supply(prev,curr,{},"STRAWBERRY")==6
    online.observe(prev,curr,{}, {"STRAWBERRY":.9});after=online.rates("STRAWBERRY",1)[0]
    assert after>before


def test_high_risk_prediction_extends_incumbent_sale_not_replaces_it(tmp_path):
    mind=AdaptiveMarketMind(False,str(_model(tmp_path)));obs=_obs();counts={"COW":0,"SHEEP":0,"GOOSE":0}
    base=super(AdaptiveMarketMind,mind)._sell_orders(obs,counts);base_n=next((int(o[2]) for o in base if o[0]=="SELL" and o[1]=="STRAWBERRY"),0)
    adaptive=mind._sell_orders(obs,counts);new_n=next((int(o[2]) for o in adaptive if o[0]=="SELL" and o[1]=="STRAWBERRY"),0)
    assert new_n>base_n
    assert new_n<=10
    assert mind.intervention_count==1
    assert mind.intervention_units==new_n-base_n
