"""Infer likely private seed/animal purchases from public cash conservation.

This is intentionally a hypothesis generator. Multiple purchase baskets share the
same cost, market SELL revenue is path-dependent, and WHEAT/FERTILIZER buys have
dynamic prices. We therefore emit ranked baskets inside a spend interval rather
than claiming exact hidden state.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

FIXED_COSTS = {
    "SEED_WHEAT": 10,
    "SEED_CARROT": 20,
    "SEED_TOMATO": 50,
    "SEED_STRAWBERRY": 100,
    "SEED_MELON": 80,
    "ANIMAL_GOOSE": 300,
    "ANIMAL_COW": 400,
    "ANIMAL_SHEEP": 500,
}

SHOP_PRODUCTS = {
    "BAKERY": {"EGG", "WHEAT"},
    "PIZZA_SHOP": {"MILK", "TOMATO", "WHEAT"},
    "BRUNCH_SPOT": {"EGG", "WHEAT", "STRAWBERRY"},
    "YARN_STORE": {"WOOL"},
    "ICE_CREAM_SHOP": {"STRAWBERRY", "MILK", "WHEAT"},
    "PET_CAFE": {"CARROT"},
    "SMOOTHIE_SHOP": {"STRAWBERRY", "MILK"},
    "FARMERS_MARKET": {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY"},
}
KEY_PRODUCT = {
    "SEED_WHEAT":"WHEAT", "SEED_CARROT":"CARROT", "SEED_TOMATO":"TOMATO",
    "SEED_STRAWBERRY":"STRAWBERRY", "SEED_MELON":"MELON",
    "ANIMAL_GOOSE":"EGG", "ANIMAL_COW":"MILK", "ANIMAL_SHEEP":"WOOL",
}

@dataclass(frozen=True)
class PurchaseHypothesis:
    basket: Dict[str, int]
    cost: int
    score: float
    interval_error: float


def shop_weights(unlocked_shops: Iterable[str]) -> Dict[str, float]:
    counts = {p: 0.0 for p in set(KEY_PRODUCT.values())}
    for shop in unlocked_shops or ():
        for p in SHOP_PRODUCTS.get(shop, ()):
            counts[p] = counts.get(p, 0.0) + 1.0
    m = max(counts.values(), default=0.0)
    return {p:(v / m if m else 0.0) for p,v in counts.items()}


def _distance_to_interval(x: float, lo: float, hi: float) -> float:
    if x < lo: return lo-x
    if x > hi: return x-hi
    return 0.0


def infer_fixed_purchases(spend_lo: float, spend_hi: float, unlocked_shops: Sequence[str] = (),
                          max_items: int = 20, max_distinct: int = 3,
                          tolerance: float = 80.0, top_k: int = 24) -> List[PurchaseHypothesis]:
    """Return ranked fixed-cost purchase baskets compatible with hidden spend.

    The search is intentionally sparse: rational one-turn purchase baskets usually
    concentrate on a few product families, while broad baskets are highly
    non-identifiable from cash alone. Dynamic WHEAT/FERTILIZER spend is absorbed by
    `tolerance` and the interval uncertainty supplied by the caller.
    """
    lo=max(0.0,float(spend_lo)); hi=max(lo,float(spend_hi)); mid=0.5*(lo+hi)
    weights=shop_weights(unlocked_shops)
    keys=list(FIXED_COSTS)
    candidates: List[PurchaseHypothesis] = [PurchaseHypothesis({},0,_distance_to_interval(0,lo,hi),_distance_to_interval(0,lo,hi))]
    max_cost=int(hi+tolerance)

    for d in range(1, max_distinct+1):
        for subset in combinations(keys,d):
            costs=[FIXED_COSTS[k] for k in subset]
            # Depth-first enumeration with an explicit total-item and cost cap.
            def rec(idx:int,left:int,cost:int,basket:Dict[str,int]):
                if idx==len(subset):
                    err=_distance_to_interval(cost,lo,hi)
                    if err>tolerance: return
                    demand=sum(weights.get(KEY_PRODUCT[k],0.0)*n for k,n in basket.items())
                    complexity=0.6*(len(basket)-1)+0.04*sum(basket.values())
                    midpoint=abs(cost-mid)/(max(50.0,hi-lo+50.0))
                    score=err/25.0 + midpoint + complexity - 0.20*demand
                    candidates.append(PurchaseHypothesis(dict(basket),cost,score,err)); return
                k=subset[idx]; c=costs[idx]
                nmax=min(left, max(0,(max_cost-cost)//c))
                for n in range(1,nmax+1):
                    basket[k]=n; rec(idx+1,left-n,cost+n*c,basket)
                basket.pop(k,None)
            rec(0,max_items,0,{})
    candidates.sort(key=lambda h:(h.score,h.interval_error,abs(h.cost-mid),len(h.basket)))
    # Dedupe equivalent vectors defensively.
    out=[]; seen=set()
    for h in candidates:
        sig=tuple(sorted(h.basket.items()))
        if sig in seen: continue
        seen.add(sig); out.append(h)
        if len(out)>=top_k: break
    return out


def exact_public_capex(prev_farm: Mapping, cur_farm: Mapping, same_day: bool = True) -> int:
    """Exact visible land + hire spend when it is identifiable from consecutive states."""
    land_prices=(1000,2000,4000)
    a=max(1,len(prev_farm.get("unlocked_quadrants",[]) or [])); b=max(a,len(cur_farm.get("unlocked_quadrants",[]) or []))
    land=sum(land_prices[i-1] for i in range(a,b) if 0 <= i-1 < len(land_prices))
    hires=0
    if same_day:
        h0=int(prev_farm.get("hires_today",0) or 0); h1=int(cur_farm.get("hires_today",0) or 0)
        # hire cost uses fib(index) with 1,1,2,3,5,...
        x,y=1,1; fib=[]
        for _ in range(max(h1,1)+2): fib.append(x); x,y=y,x+y
        if h1>=h0: hires=sum(fib[i] for i in range(h0,h1))
    return int(land+hires)
