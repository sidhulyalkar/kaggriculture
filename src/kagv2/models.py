from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.metrics import log_loss,roc_auc_score,mean_absolute_error,r2_score
from sklearn.model_selection import GroupShuffleSplit
from .constants import PRODUCTS
from .features import public_feature_frame,checkpoint_rows

def _split(df,group="episode_id",test_size=.25,seed=20260816):
    groups=df[group].astype(str).values if group in df else np.arange(len(df))
    tr,va=next(GroupShuffleSplit(n_splits=1,test_size=test_size,random_state=seed).split(df,groups=groups))
    return tr,va

def train_win_model(turn_df):
    d=checkpoint_rows(turn_df); X=public_feature_frame(d); y=d["win_target"].to_numpy(float)
    keep=np.isin(y,[0,1]);d=d.loc[keep].reset_index(drop=True);X=X.loc[keep].reset_index(drop=True);y=y[keep]
    group="submission_id" if "submission_id" in d and d["submission_id"].nunique(dropna=True)>=12 else "episode_id"
    tr,va=_split(d,group=group);m=LogisticRegression(C=.5,max_iter=1000,class_weight="balanced").fit(X.iloc[tr],y[tr])
    pv=m.predict_proba(X.iloc[va])[:,1]
    metrics={"auc":float(roc_auc_score(y[va],pv)) if len(np.unique(y[va]))>1 else None,"logloss":float(log_loss(y[va],pv))}
    artifact={"type":"logistic","features":list(X.columns),"coef":m.coef_[0].tolist(),"intercept":float(m.intercept_[0]),"metrics":metrics}
    return artifact,metrics

def train_supply_model(turn_df,horizon=24,alpha=10.0):
    d=checkpoint_rows(turn_df); X=public_feature_frame(d); targets=[f"opp_sell_next{horizon}_{p}" for p in PRODUCTS]
    Y=d[targets].fillna(0).to_numpy(float);group="submission_id" if "submission_id" in d and d["submission_id"].nunique(dropna=True)>=12 else "episode_id"
    tr,va=_split(d,group=group);m=Ridge(alpha=alpha).fit(X.iloc[tr],Y[tr]);pred=np.maximum(0,m.predict(X.iloc[va]))
    metrics={"mae":float(mean_absolute_error(Y[va],pred)),"r2":float(r2_score(Y[va],pred,multioutput="variance_weighted"))}
    artifact={"type":"ridge_multi","features":list(X.columns),"targets":targets,"coef":m.coef_.tolist(),"intercept":np.asarray(m.intercept_).tolist(),"metrics":metrics}
    return artifact,metrics

def save_model_bundle(path, win=None, supply=None, archetype=None, macro_library=None,
                      policy_by_archetype=None, meta=None, probe=None, provenance=None):
    """Write the single tiny artifact consumed by the Kaggle runtime.

    ``meta`` contains the precomputed policy-zoo payoff table/equilibrium mix.
    ``probe`` is reserved for *promoted* active-market-probe rules; research
    output should leave it disabled until paired simulator evidence clears the
    promotion gate.
    """
    obj={
        "version":2,
        "win":win,
        "supply":supply,
        "archetype":archetype,
        "macro_library":macro_library,
        "policy_by_archetype":policy_by_archetype or {},
        "meta":meta,
        "probe":probe or {"enabled":False},
        "provenance":provenance or {},
    }
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True))
    return obj
