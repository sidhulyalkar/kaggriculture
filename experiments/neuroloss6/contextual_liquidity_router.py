from __future__ import annotations
import copy, math
from v32_base import agent as _V32

# Trained on Wave 18C runtime-visible public state. Positive class is the
# Adaptive/Ranker hard-matchup family. Whole-seed grouped OOF AUC: 0.9930.
_MODEL={'features': ['day', 'hour', 'our_money', 'opp_money', 'cash_diff', 'our_hands', 'opp_hands', 'our_quads', 'opp_quads', 'shop_count', 'our_crop_WHEAT', 'our_crop_CARROT', 'our_crop_TOMATO', 'our_crop_STRAWBERRY', 'our_crop_MELON', 'our_ready_WHEAT', 'our_ready_CARROT', 'our_ready_TOMATO', 'our_ready_STRAWBERRY', 'our_ready_MELON', 'our_animal_COW', 'our_animal_SHEEP', 'our_animal_GOOSE', 'our_animal_ready_COW', 'our_animal_ready_SHEEP', 'our_animal_ready_GOOSE', 'opp_crop_WHEAT', 'opp_crop_CARROT', 'opp_crop_TOMATO', 'opp_crop_STRAWBERRY', 'opp_crop_MELON', 'opp_ready_WHEAT', 'opp_ready_CARROT', 'opp_ready_TOMATO', 'opp_ready_STRAWBERRY', 'opp_ready_MELON', 'opp_animal_COW', 'opp_animal_SHEEP', 'opp_animal_GOOSE', 'opp_animal_ready_COW', 'opp_animal_ready_SHEEP', 'opp_animal_ready_GOOSE', 'market_inv_WHEAT', 'market_price_WHEAT', 'market_inv_CARROT', 'market_price_CARROT', 'market_inv_TOMATO', 'market_price_TOMATO', 'market_inv_STRAWBERRY', 'market_price_STRAWBERRY', 'market_inv_MELON', 'market_price_MELON', 'market_inv_EGG', 'market_price_EGG', 'market_inv_MILK', 'market_price_MILK', 'market_inv_WOOL', 'market_price_WOOL', 'market_inv_FERTILIZER', 'market_price_FERTILIZER'], 'mean': [14.313, 11.4522, 29547.2354, 29479.8008, 67.4346, 8.2068, 8.3234, 2.4232, 2.4164, 4.3366, 17.843, 0.0, 0.0, 19.0406, 5.534, 17.843, 0.0, 0.0, 3.5884, 5.534, 6.1964, 3.9278, 0.0, 1.356, 0.3722, 0.0, 16.8126, 0.162, 0.0, 18.1944, 5.8848, 16.8126, 0.162, 0.0, 3.2736, 5.8848, 6.2704, 3.9128, 0.0, 1.0238, 0.301, 0.0, 9772.1036, 38.8548, 9891.7062, 44.6066, 9899.3516, 85.9622, 9958.1638, 150.9662, 10064.5782, 169.5662, 9938.196, 53.7072, 9991.3196, 157.5766, 10010.8898, 135.7788, 10182.2364, 63.5648], 'scale': [8.687038102828835, 6.936751052185742, 33275.91789528257, 32479.96111793731, 5281.955740265422, 4.151100307147492, 4.090135992849138, 0.8429126645151324, 0.8367861375524812, 2.7416966352972025, 13.980155614298432, 1.0, 1.0, 14.167348080710095, 4.777116703619455, 13.980155614298432, 1.0, 1.0, 5.529537543050052, 4.777116703619455, 2.9377248067169255, 0.46667671893935314, 1.0, 1.5840656552049854, 0.9812579477385139, 1.0, 13.120285105133958, 0.73277281608968, 1.0, 13.827574213867017, 5.422207019286519, 13.120285105133958, 0.73277281608968, 1.0, 5.345347794110314, 5.422207019286519, 2.953926850820785, 1.259839735839444, 1.0, 1.5151348322839124, 0.8637123363713175, 1.0, 164.45154078645783, 5.988565517717912, 137.49333322586955, 18.065996691021503, 112.63670439710138, 64.70589749906881, 66.16367711637557, 63.26578741752923, 66.76926152624425, 108.13253172639583, 67.41720836700375, 4.090656201638069, 52.47711744979901, 77.36881110912846, 55.09224315600155, 92.78291798903503, 129.28712741429442, 25.891268817112845], 'coef': [-0.47590784804407604, 0.049106899260379304, -0.9447528251958172, -0.10393157087721616, -5.312771526579283, -0.20261407731588366, 0.09548153830800343, 0.4403366355671813, -1.002290057460072, -0.019496614566708755, -0.24712049680960493, 0.0, 0.0, 0.04782001716014802, -0.9317682886522176, -0.24712049680960493, 0.0, 0.0, 1.3284199494594038, -0.9317682886522176, -0.5410617005404277, -0.7615725672534002, 0.0, 0.21300015510865183, 0.4253572933625616, 0.0, -0.049702166568588474, 0.9945293022526911, 0.0, -2.9987860580385273, 2.173576127660349, -0.049702166568588474, 0.9945293022526911, 0.0, -1.0457175107215277, 2.173576127660349, 2.7530619831716794, 0.4489013638501276, 0.0, -0.7697632647364276, -0.2808005542219707, 0.0, -0.054818837562147345, 0.06262170508829612, 1.195694459491991, 0.22226469203292262, 0.1621978588572521, 0.18191169967914783, -0.1046812191118975, 0.6880341654180498, 2.0040473270016044, -2.2584510766076282, 0.5872507516408328, -0.7734795046908134, 1.177086751297014, 0.39946245398766794, 0.5384170310355202, 0.29795370028374746, 0.11140412847041964, -0.07036508556409561], 'intercept': -2.8009348831758576, 'auc': 0.9930047375459214}
_PRODUCTS=["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"]
_STATS={"changes":0,"hard_calls":0,"mode_counts":{},"kinds":{},"max_risk":0.0}
_EP={"last_step":-1,"hard_streak":0,"hard_mode":False}

def _sig(z):
    if z>35:return 1.0
    if z<-35:return 0.0
    return 1.0/(1.0+math.exp(-z))

def _counts(farm):
    crops={c:0 for c in ["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"]};ready=dict(crops)
    animals={a:0 for a in ["COW","SHEEP","GOOSE"]};aready=dict(animals)
    for row in farm.get("tiles",[]) or []:
        for t in row:
            if not isinstance(t,dict):continue
            if t.get("kind")=="PLANT" and t.get("crop") in crops:
                c=t["crop"];crops[c]+=1
                if int(t.get("yield_units",0) or 0)>0:ready[c]+=1
            a=t.get("animal")
            if a in animals:
                animals[a]+=1
                if int(t.get("yield_units",0) or 0)>0:aready[a]+=1
    return crops,ready,animals,aready

def _vector(obs):
    p=int(obs.get("player",0));fs=obs.get("farms",[]) or []
    if len(fs)<2:return [0.0]*len(_MODEL["features"])
    me,op=fs[p],fs[1-p];mc,mr,ma,mar=_counts(me);oc,orr,oa,oar=_counts(op)
    market=obs.get("market",{}) or {};inv=market.get("inventory",{}) or {};prices=market.get("prices",{}) or {}
    v={"day":int(obs.get("day",0)),"hour":int(obs.get("hour",0)),"our_money":float(me.get("money",0)),"opp_money":float(op.get("money",0)),
       "cash_diff":float(me.get("money",0))-float(op.get("money",0)),"our_hands":len(me.get("hands",[]) or []),"opp_hands":len(op.get("hands",[]) or []),
       "our_quads":len(me.get("unlocked_quadrants",[]) or []),"opp_quads":len(op.get("unlocked_quadrants",[]) or []),
       "shop_count":len(((obs.get("town",{}) or {}).get("unlocked_shops",[]) or []))}
    for c in mc:
        v["our_crop_"+c]=mc[c];v["our_ready_"+c]=mr[c];v["opp_crop_"+c]=oc[c];v["opp_ready_"+c]=orr[c]
    for a in ma:
        v["our_animal_"+a]=ma[a];v["our_animal_ready_"+a]=mar[a];v["opp_animal_"+a]=oa[a];v["opp_animal_ready_"+a]=oar[a]
    for x in _PRODUCTS:
        v["market_inv_"+x]=int(inv.get(x,10000) or 10000);v["market_price_"+x]=int(prices.get(x,0) or 0)
    return [float(v.get(k,0.0)) for k in _MODEL["features"]]

def _risk(obs):
    z=float(_MODEL["intercept"])
    for a,mu,sc,c in zip(_vector(obs),_MODEL["mean"],_MODEL["scale"],_MODEL["coef"]):z+=((a-mu)/(sc if sc else 1.0))*c
    return _sig(z)

def _record(k):
    _STATS["changes"]+=1;_STATS["kinds"][k]=_STATS["kinds"].get(k,0)+1

def _reset(obs):
    s=int(obs.get("step",0))
    if s==0 or s<int(_EP["last_step"]):
        _EP["hard_streak"]=0;_EP["hard_mode"]=False
    _EP["last_step"]=s

def _update_hard_mode(obs,r):
    day=int(obs.get("day",0))
    if day<4:return False
    if r>=0.97:_EP["hard_streak"]+=1
    elif r<0.85:_EP["hard_streak"]=0
    if _EP["hard_streak"]>=3:_EP["hard_mode"]=True
    return _EP["hard_mode"]

def _farm_state(obs):
    p=int(obs.get("player",0));me=obs.get("farms",[])[p];op=obs.get("farms",[])[1-p]
    _,_,ma,_=_counts(me);_,orr,oa,oar=_counts(op)
    shed=(obs.get("private",{}) or {}).get("shed",{}) or {}
    animals=sum(ma.values());opp_animals=sum(oa.values())
    return {"animals":animals,"opp_animals":opp_animals,"wheat":int(shed.get("WHEAT",0) or 0),
            "cash_diff":float(me.get("money",0))-float(op.get("money",0)),"opp_ready":orr,"opp_animal_ready":oar}

def _rpe(m,step):
    if step!=262:return
    for i,o in enumerate(m):
        if isinstance(o,list) and len(o)>=3 and o[0]=="BUY_SEED" and o[1]=="WHEAT" and int(o[2])==1:
            m.pop(i);_record("rpe_wheat_seed");return

def _feed_first(m,state):
    if state["animals"]<=0 or state["wheat"]>=2*state["animals"]:return
    bi=next((i for i,o in enumerate(m) if isinstance(o,list) and len(o)>=3 and o[0]=="BUY_PRODUCT" and o[1]=="WHEAT"),None)
    hi=next((i for i,o in enumerate(m) if isinstance(o,list) and o and o[0]=="HIRE"),None)
    if bi is not None and hi is not None and bi>hi:
        o=m.pop(bi);m.insert(hi,o);_record("feed_first")

def _mode(obs,hard,state):
    if not hard:return "V32"
    if state["animals"] and state["wheat"]<2*state["animals"]:return "FEED_FORTRESS"
    if state["cash_diff"]<-5000:return "CASH_DEFENSE"
    if state["opp_animals"]>=12:return "ANIMAL_HEAVY"
    return "HARD_OBSERVE"

def agent(obs,configuration=None):
    _reset(obs)
    try:a=copy.deepcopy(_V32(obs,configuration))
    except TypeError:a=copy.deepcopy(_V32(obs))
    if not isinstance(a,dict):return a
    m=list(a.get("market",[]) or []);step=int(obs.get("step",0));r=_risk(obs);_STATS["max_risk"]=max(_STATS["max_risk"],r)
    hard=_update_hard_mode(obs,r);state=_farm_state(obs);mode=_mode(obs,hard,state)
    _STATS["mode_counts"][mode]=_STATS["mode_counts"].get(mode,0)+1
    _rpe(m,step)
    if hard:
        _STATS["hard_calls"]+=1
        if mode in ("FEED_FORTRESS","ANIMAL_HEAVY","CASH_DEFENSE"):_feed_first(m,state)
    a["market"]=m[:10]
    return a
