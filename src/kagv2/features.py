from __future__ import annotations
import numpy as np
import pandas as pd
from .constants import PRODUCTS,CROPS,ANIMALS,SHOPS,PUBLIC_RUNTIME_FEATURES,BASE

def public_feature_frame(turn_df: pd.DataFrame) -> pd.DataFrame:
    d=turn_df.copy(); out=pd.DataFrame(index=d.index)
    out["day_norm"]=d["day"]/30.0; out["hour_norm"]=d["hour"]/24.0
    out["own_quadrants"]=d["quadrants"]/4.0; out["opp_quadrants"]=d["opp_quadrants"]/4.0
    out["own_hands"]=d["hands"]/16.0; out["opp_hands"]=d["opp_hands"]/16.0
    for p in PRODUCTS:
        out[f"price_ratio_{p}"]=d[f"price_{p}"]/BASE[p]
        out[f"market_delta_{p}"]=(d[f"market_inv_{p}"]-10000.0)/500.0
    for s in SHOPS: out[f"shop_{s}"]=d[f"shop_{s}"]/4.0
    for c in CROPS:
        out[f"own_crop_{c}"]=d[f"crop_{c}"]/60.0; out[f"opp_crop_{c}"]=d[f"opp_crop_{c}"]/60.0
    for a in ANIMALS:
        out[f"own_animal_{a}"]=d[f"animal_{a}"]/16.0; out[f"opp_animal_{a}"]=d[f"opp_animal_{a}"]/16.0
    out["own_pasture"]=d["pasture"]/20.0; out["opp_pasture"]=d["opp_pasture"]/20.0
    out["own_coop"]=d["coop"]/20.0; out["opp_coop"]=d["opp_coop"]/20.0
    for c in PUBLIC_RUNTIME_FEATURES:
        if c not in out: out[c]=0.0
    return out[list(PUBLIC_RUNTIME_FEATURES)].astype(np.float32)

def checkpoint_rows(df, hours=(0,6,12,18), min_day=2, max_day=27):
    return df[df["hour"].isin(hours) & df["day"].between(min_day,max_day)].copy()

def daily_macro_frame(turn_df):
    if turn_df.empty:return turn_df
    agg={"money":"last","quadrants":"last","hands":"max","final_reward":"last","final_margin":"last","win_target":"last"}
    for c in CROPS: agg[f"crop_{c}"]="last"; agg[f"plant_{c}"]="sum" if f"plant_{c}" in turn_df else "last"
    for a in ANIMALS: agg[f"animal_{a}"]="last"; agg[f"buy_animal_{a}"]="sum"
    for p in PRODUCTS: agg[f"sell_{p}"]="sum"; agg[f"price_{p}"]="mean"; agg[f"market_inv_{p}"]="last"
    for k in ["market_HIRE","market_BUY_LAND","unit_WATER","unit_HARVEST","unit_CARE","unit_FEED","unit_FERTILIZE","unit_COLLECT_FERTILIZER","unit_DIG"]:
        if k in turn_df: agg[k]="sum"
    agg={k:v for k,v in agg.items() if k in turn_df.columns}
    meta=[c for c in ["team_name","submission_id"] if c in turn_df]
    for c in meta: agg[c]="last"
    return turn_df.groupby(["episode_id","player","day"],as_index=False).agg(agg)

def macro_vector_columns(df):
    cols=[c for c in df.columns if c.startswith("crop_") or c.startswith("animal_") or c.startswith("sell_") or c.startswith("plant_")]
    cols += [c for c in ["quadrants","hands","market_HIRE","market_BUY_LAND","unit_WATER","unit_HARVEST","unit_CARE","unit_FEED","unit_FERTILIZE"] if c in df]
    return list(dict.fromkeys(cols))
