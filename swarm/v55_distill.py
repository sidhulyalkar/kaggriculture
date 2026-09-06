from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from swarm.v54_executed_sale_predictor import build_rows
from swarm.v50_sale_intent_probe import _split
from swarm.v77_live_meta_route_search import fetch_top_episodes

PRODUCTS=("CARROT","STRAWBERRY","MELON","EGG","WOOL")
ACTIONABLE=frozenset({"STRAWBERRY","MELON","WOOL"})


def _matrix(rows,names):
    x=np.asarray([[float((r.get("features") or {}).get(k,0.0)) for k in names] for r in rows],dtype=np.float64)
    y=np.asarray([int(r.get("label",0)) for r in rows],dtype=np.int64)
    return x,y


def _fit(train,valid,names):
    xtr,ytr=_matrix(train,names);xva,yva=_matrix(valid,names)
    if len(np.unique(ytr))<2 or len(np.unique(yva))<2:return None
    scaler=StandardScaler().fit(xtr);ztr=scaler.transform(xtr);zva=scaler.transform(xva)
    model=LogisticRegression(class_weight="balanced",max_iter=800,C=.5,random_state=55).fit(ztr,ytr)
    prob=model.predict_proba(zva)[:,1]
    return scaler,model,prob,yva


def _precision_recall(y,p,threshold):
    pred=p>=float(threshold);tp=int(np.sum(pred & (y==1)));fp=int(np.sum(pred & (y==0)));fn=int(np.sum((~pred)&(y==1)))
    precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
    return precision,recall,tp,fp,fn


def _choose_threshold(y,prob):
    prevalence=float(np.mean(y));min_precision=max(.30,min(.60,2.5*prevalence));best=None
    for q in (.75,.80,.85,.875,.90,.925,.95,.965,.975,.985):
        t=float(np.quantile(prob,q));precision,recall,tp,fp,fn=_precision_recall(y,prob,t)
        if recall<.05 or precision<min_precision:continue
        score=precision*(recall**.5);row=(score,t,precision,recall,tp,fp,fn,q)
        if best is None or row[0]>best[0]:best=row
    if best is None:
        t=float(np.quantile(prob,.90));precision,recall,tp,fp,fn=_precision_recall(y,prob,t);best=(precision*(recall**.5),t,precision,recall,tp,fp,fn,.90)
    return {"threshold":best[1],"precision":best[2],"recall":best[3],"tp":best[4],"fp":best[5],"fn":best[6],"quantile":best[7],"prevalence":prevalence}


def distill_product(episodes,product,horizon=3,stride=2,top_k=12):
    rows,diag=build_rows(episodes,product,horizon=horizon,stride=stride)
    if not rows:return {"status":"no_rows"}
    train,valid,split=_split(rows);all_names=sorted(rows[0]["features"]);first=_fit(train,valid,all_names)
    if first is None:return {"status":"insufficient_labels"}
    scaler0,model0,prob0,yva0=first;ranked=np.argsort(np.abs(model0.coef_[0]))[::-1]
    names=[all_names[int(i)] for i in ranked[:min(int(top_k),len(all_names))]];second=_fit(train,valid,names)
    if second is None:return {"status":"insufficient_refit"}
    scaler,model,prob,yva=second;auc=float(roc_auc_score(yva,prob));gate=_choose_threshold(yva,prob)
    positives=[int(r.get("future_effective_sell_quantity",0) or 0) for r in train if int(r.get("label",0))>0]
    shock_mean=float(np.mean(positives)) if positives else 4.0;shock_p75=float(np.quantile(np.asarray(positives,dtype=float),.75)) if positives else 4.0
    useful=bool(auc>=.72 and gate["precision"]>=max(.30,2.25*gate["prevalence"]) and gate["recall"]>=.05 and int(np.sum(yva))>=20)
    return {"status":"ready","useful":useful,"rows":len(rows),"split":split,"features":names,"mean":[float(x) for x in scaler.mean_],"scale":[float(x) for x in scaler.scale_],
            "coef":[float(x) for x in model.coef_[0]],"intercept":float(model.intercept_[0]),"threshold":float(gate["threshold"]),"prevalence":float(gate["prevalence"]),
            "shock_mean":shock_mean,"shock_p75":shock_p75,"validation":{"auc":auc,**gate,"positives":int(np.sum(yva)),"samples":int(len(yva))},"diagnostics":diag}


def run(output,report,days=4,per_day=10,horizon=3,stride=2):
    out=Path(output);rep=Path(report);root=rep.parent/"episodes";shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True,exist_ok=True)
    episodes,acquisition=fetch_top_episodes(root,days=days,per_day=per_day);models={p:distill_product(episodes,p,horizon=horizon,stride=stride) for p in PRODUCTS}
    enabled=[p for p,m in models.items() if m.get("useful")];actionable=[p for p in enabled if p in ACTIONABLE];dates=[d.get("date") for d in acquisition.get("days",[]) if d.get("status")=="ready"]
    payload={"version":55,"experiment":"V55_ADAPTIVE_MARKET_DISTILL","target":"market-effective opponent sale in next four decisions","episodes":len(episodes),"source_dates":dates,
             "models":{p:m for p,m in models.items() if m.get("useful")},"enabled_products":enabled,"actionable_products":actionable,"online":{"prior_strength":12.0,"bucket_strength":4.0,"bucket_hours":4},
             "gate":"READY" if len(actionable)>=2 else "INSUFFICIENT_ACTIONABLE_MODELS"}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8")
    summary={"gate":payload["gate"],"episodes":len(episodes),"source_dates":dates,"enabled":enabled,"actionable":actionable,
             "products":{p:{"useful":m.get("useful"),"auc":(m.get("validation") or {}).get("auc"),"precision":(m.get("validation") or {}).get("precision"),"recall":(m.get("validation") or {}).get("recall"),"threshold":m.get("threshold")} for p,m in models.items()}}
    rep.parent.mkdir(parents=True,exist_ok=True);rep.write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8");return payload,summary


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default="submission/adaptive_market_model.json");ap.add_argument("--report",default="tmp/v55/V55_DISTILL.json")
    ap.add_argument("--days",type=int,default=4);ap.add_argument("--per-day",type=int,default=10);ap.add_argument("--horizon",type=int,default=3);ap.add_argument("--stride",type=int,default=2)
    a=ap.parse_args();payload,summary=run(a.output,a.report,a.days,a.per_day,a.horizon,a.stride);print(json.dumps(summary,indent=2,sort_keys=True))
    if payload["gate"]!="READY":raise SystemExit(2)

if __name__=="__main__":main()
