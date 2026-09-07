"""Zero-sum market valuation for V80.

Kaggriculture ranks match wins, not social surplus.  A unit we sell has two
components of value:
  1) our realized sale revenue;
  2) the reduction in the rival's later realizable revenue caused by the shared
     inventory/price impact.

This module evaluates that second term exactly under the public price curves.
It is deliberately a local market model; production, town drain and timing are
handled by the higher-level MPC.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import log, log10, sqrt
from typing import Dict, List, Tuple

I0=10000
PRICE_FLOOR=1
PARAMS={
 "WHEAT":dict(base=25,T=400,below_func="sqrt",below_target=.80,above_func="log",above_target=.20),
 "CARROT":dict(base=35,T=450,below_func="hinge",below_target=1.00,above_func="sqrt",above_target=.70),
 "TOMATO":dict(base=60,T=200,below_func="hinge",below_target=.40,above_func="sqrt",above_target=.60),
 "STRAWBERRY":dict(base=120,T=100,below_func="sqrt",below_target=.70,above_func="linear",above_target=1.60),
 "MELON":dict(base=250,T=300,below_func="log",below_target=.20,above_func="sq",above_target=3.60),
 "EGG":dict(base=50,T=332,below_func="hinge",below_target=.40,above_func="log",above_target=.20),
 "MILK":dict(base=160,T=122,below_func="sqrt",below_target=.60,above_func="linear",above_target=1.60),
 "WOOL":dict(base=200,T=105,below_func="log",below_target=.20,above_func="sq",above_target=3.20),
 "FERTILIZER":dict(base=100,T=200,below_func="linear",below_target=.40,above_func="linear",above_target=.40),
}
HINGE_GAIN=8.0

def _shape(f:str,x:float,T:float)->float:
    x=max(0.0,float(x))
    if f=="linear": return x
    if f=="sq": return x*x
    if f=="sqrt": return sqrt(x)
    if f=="log": return log(1+x)
    if f=="log10": return log10(1+x)
    if f=="hinge":
        u=x/T if T>0 else x
        return u + HINGE_GAIN*max(0.0,u-1.0)**2
    return x

def price(item:str,inventory:float)->int:
    p=PARAMS[item]; T=p["T"]; base=p["base"]
    if inventory<I0:
        f=p["below_func"]; amp=p["below_target"]*base/_shape(f,T,T)
        x=base + amp*_shape(f,I0-inventory,T)
    else:
        f=p["above_func"]; amp=p["above_target"]*base/_shape(f,T,T)
        x=base - amp*_shape(f,inventory-I0,T)
    return max(PRICE_FLOOR,int(round(x)))

def sell_path(item:str,inventory:float,qty:int)->Tuple[float,float]:
    """Return (revenue, ending inventory) for one player's isolated SELL order."""
    inv=float(inventory); revenue=0.0
    for _ in range(max(0,int(qty))):
        px=price(item,inv); revenue += px
        # Engine keeps inventory frozen at the $1 floor for sells.
        if px>PRICE_FLOOR: inv += 1.0
    return revenue,inv

@dataclass(frozen=True)
class DumpValue:
    qty:int
    own_revenue:float
    rival_revenue_without:float
    rival_revenue_after:float
    denial_value:float
    relative_value:float
    ending_inventory:float


def dump_value(item:str,inventory:float,our_qty:int,rival_future_qty:int)->DumpValue:
    rival0,_=sell_path(item,inventory,rival_future_qty)
    ours,inv1=sell_path(item,inventory,our_qty)
    rival1,inv2=sell_path(item,inv1,rival_future_qty)
    denial=rival0-rival1
    return DumpValue(int(our_qty),ours,rival0,rival1,denial,ours+denial,inv2)


def choose_dump(item:str,inventory:float,held:int,rival_future_qty:int,
                reserve_value_per_unit:float=0.0,max_dump:int=40)->DumpValue:
    """Choose q maximizing local terminal-margin value.

    reserve_value_per_unit is the higher-level planner's estimate of the option
    value of keeping a unit for a later scarcity window.  Setting it to zero is
    the terminal/commitment-trap case.
    """
    lim=min(max(0,int(held)),max(0,int(max_dump)))
    best=dump_value(item,inventory,0,rival_future_qty)
    best_score=best.relative_value + held*reserve_value_per_unit
    for q in range(1,lim+1):
        v=dump_value(item,inventory,q,rival_future_qty)
        score=v.relative_value + (held-q)*reserve_value_per_unit
        if score>best_score:
            best,best_score=v,score
    return best


def denial_curve(item:str,inventory:float,held:int,rival_future_qty:int,max_dump:int=40)->List[DumpValue]:
    return [dump_value(item,inventory,q,rival_future_qty) for q in range(min(held,max_dump)+1)]
