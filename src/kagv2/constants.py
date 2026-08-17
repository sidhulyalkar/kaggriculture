from __future__ import annotations

PRODUCTS = ["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"]
CROPS = ["WHEAT","CARROT","TOMATO","STRAWBERRY","MELON"]
ANIMALS = ["GOOSE","COW","SHEEP"]
SHOPS = ["BAKERY","PIZZA_SHOP","BRUNCH_SPOT","YARN_STORE","ICE_CREAM_SHOP","PET_CAFE","SMOOTHIE_SHOP","FARMERS_MARKET"]
BASE = {"WHEAT":25,"CARROT":35,"TOMATO":60,"STRAWBERRY":120,"MELON":250,"EGG":50,"MILK":160,"WOOL":200,"FERTILIZER":100}
CURRENT_ENGINE_CUTOFF = "2026-08-07T00:00:00Z"

PUBLIC_RUNTIME_FEATURES = (
    ["day_norm","hour_norm","own_quadrants","opp_quadrants","own_hands","opp_hands"]
    + [f"price_ratio_{p}" for p in PRODUCTS]
    + [f"market_delta_{p}" for p in PRODUCTS]
    + [f"shop_{s}" for s in SHOPS]
    + [f"own_crop_{c}" for c in CROPS]
    + [f"opp_crop_{c}" for c in CROPS]
    + [f"own_animal_{a}" for a in ANIMALS]
    + [f"opp_animal_{a}" for a in ANIMALS]
    + ["own_pasture","opp_pasture","own_coop","opp_coop"]
)
