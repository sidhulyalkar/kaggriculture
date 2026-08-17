from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from .constants import CROPS,ANIMALS,PRODUCTS

def episode_profiles(daily_df, days=(3,6,9,12,15,18,21,24)):
    if daily_df.empty:return pd.DataFrame()
    vec=[]
    for (e,p),g in daily_df.groupby(["episode_id","player"]):
        g=g.set_index("day").sort_index(); row={"episode_id":e,"player":p}
        for m in ["submission_id","team_name","final_reward","win_target"]:
            if m in g: row[m]=g[m].dropna().iloc[-1] if g[m].notna().any() else None
        for d in days:
            sub=g.loc[g.index<=d]
            if sub.empty:continue
            z=sub.iloc[-1]
            for c in CROPS: row[f"d{d}_crop_{c}"]=float(z.get(f"crop_{c}",0))
            for a in ANIMALS: row[f"d{d}_animal_{a}"]=float(z.get(f"animal_{a}",0))
            row[f"d{d}_quadrants"]=float(z.get("quadrants",1)); row[f"d{d}_hands"]=float(z.get("hands",0))
            for pr in ["STRAWBERRY","MELON","WHEAT","MILK","WOOL","FERTILIZER"]:
                row[f"d{d}_sell_{pr}"]=float(sub.loc[sub.index==d,f"sell_{pr}"].sum()) if f"sell_{pr}" in sub else 0
        vec.append(row)
    return pd.DataFrame(vec)

def fit_archetypes(profiles, n_clusters=6, random_state=20260816):
    meta={c for c in ["episode_id","player","submission_id","team_name","final_reward","win_target"] if c in profiles}
    feat=[c for c in profiles.columns if c not in meta and pd.api.types.is_numeric_dtype(profiles[c])]
    X=profiles[feat].fillna(0).to_numpy(float); scaler=StandardScaler(); Xs=scaler.fit_transform(X)
    k=min(n_clusters,max(2,len(profiles)//10),len(profiles))
    km=KMeans(n_clusters=k,n_init=20,random_state=random_state).fit(Xs)
    out=profiles.copy();out["archetype"]=km.labels_
    model={"features":feat,"mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),"centroids":km.cluster_centers_.tolist()}
    return out,model

def build_macro_library(clustered_profiles,daily_df):
    key=clustered_profiles[["episode_id","player","archetype"]]
    d=daily_df.merge(key,on=["episode_id","player"],how="inner")
    lib={}
    for cl,g in d.groupby("archetype"):
        days={}
        for day,x in g.groupby("day"):
            item={"n":int(len(x))}
            for c in CROPS:item[f"crop_{c}"]=float(x[f"crop_{c}"].median()) if f"crop_{c}" in x else 0
            for a in ANIMALS:item[f"animal_{a}"]=float(x[f"animal_{a}"].median()) if f"animal_{a}" in x else 0
            item["hands"]=float(x["hands"].median()) if "hands" in x else 0;item["quadrants"]=float(x["quadrants"].median()) if "quadrants" in x else 1
            for p in PRODUCTS:item[f"sell_{p}"]=float(x[f"sell_{p}"].median()) if f"sell_{p}" in x else 0
            days[str(int(day))]=item
        prof=clustered_profiles[clustered_profiles.archetype==cl]
        lib[str(int(cl))]={"episodes":int(len(prof)),"mean_reward":float(pd.to_numeric(prof.get("final_reward"),errors="coerce").mean()),
                           "win_rate":float(pd.to_numeric(prof.get("win_target"),errors="coerce").mean()),"days":days}
    return lib

def save_json(obj,path): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True))
