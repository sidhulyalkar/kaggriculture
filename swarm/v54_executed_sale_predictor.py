from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from swarm.market_belief import BASE_PRICE, NONBUYABLE_PRODUCTS, post_physical_shed, public_sale_features
from swarm.v50_sale_intent_probe import _fit, _split
from swarm.v77_live_meta_route_search import fetch_top_episodes

PRODUCTS = ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
POLICY_PRODUCTS = frozenset({"STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"})
MAX_MARKET_ORDERS = 10


def _state_action(state: Any) -> Any:
    return state.get("action") if isinstance(state, dict) else None


def _state_obs(state: Any) -> Any:
    return state.get("observation", {}) if isinstance(state, dict) else {}


def _episode_identity(rep: dict[str, Any], fallback: int) -> str:
    info = rep.get("info", {}) or {}
    return str(info.get("EpisodeId", rep.get("id", fallback)))


def _team_names(rep: dict[str, Any]) -> list[str]:
    return [str(x) for x in list((rep.get("info", {}) or {}).get("TeamNames") or [])]


def _price(obs: Any, product: str) -> int:
    market = (obs or {}).get("market", {}) if isinstance(obs, dict) else {}
    prices = market.get("prices", {}) if isinstance(market, dict) else {}
    try:
        return int(prices.get(product, BASE_PRICE.get(product, 1)) or 1)
    except Exception:
        return int(BASE_PRICE.get(product, 1))


def queued_requested_sale(action: Any, product: str) -> int:
    """Requested SELL quantity that reaches the engine's first-10 market queue."""
    if not isinstance(action, dict):
        return 0
    total = 0
    for order in list(action.get("market", []) or [])[:MAX_MARKET_ORDERS]:
        if not isinstance(order, (list, tuple)) or len(order) < 3:
            continue
        if str(order[0]) != "SELL" or str(order[1]) != str(product):
            continue
        try:
            total += max(0, int(order[2]))
        except Exception:
            pass
    return total


def executed_sale_quantity(obs: Any, action: Any, product: str) -> int:
    """Exact quantity removed from the target seat's shed by queued SELL orders."""
    requested = queued_requested_sale(action, product)
    if requested <= 0:
        return 0
    shed = post_physical_shed(obs, action)
    try:
        available = max(0, int(shed.get(str(product), 0) or 0))
    except Exception:
        available = 0
    return min(requested, available)


def transition_effective_sale(
    prev_obs: Any,
    curr_obs: Any,
    action: Any,
    product: str,
) -> dict[str, Any]:
    """Label one transition without pretending a floor-crossing sale is exact.

    `executed` is always exact from the acting seat's private state. `effective`
    is the supply quantity known to enter the public market only while both ends
    of the transition remain above the $1 price floor. A positive executed sale
    on a transition touching the floor is marked censored rather than guessed.
    """
    requested = queued_requested_sale(action, product)
    executed = executed_sale_quantity(prev_obs, action, product)
    prev_price = _price(prev_obs, product)
    curr_price = _price(curr_obs, product)
    floor_censored = bool(executed > 0 and (prev_price <= 1 or curr_price <= 1))
    return {
        "requested": requested,
        "executed": executed,
        "effective": None if floor_censored else executed,
        "floor_censored": floor_censored,
        "prev_price": prev_price,
        "curr_price": curr_price,
    }


def future_effective_sale_quantity(
    steps: list[Any],
    observation_index: int,
    seat: int,
    product: str,
    *,
    horizon: int,
) -> dict[str, Any]:
    """Exact future market-effective sale target using replay action offset +1.

    Replay row `t+1` stores the decision taken from observation row `t`. Each
    future transition therefore pairs observation row `i`, action row `i+1`, and
    resulting observation row `i+1`.
    """
    requested_total = 0
    executed_total = 0
    effective_total = 0
    censored_positive_transitions = 0
    transitions = 0

    for dt in range(horizon + 1):
        prev_index = observation_index + dt
        curr_index = prev_index + 1
        if curr_index >= len(steps):
            break
        prev_turn = steps[prev_index]
        curr_turn = steps[curr_index]
        if seat >= len(prev_turn) or seat >= len(curr_turn):
            continue
        prev_state = prev_turn[seat]
        curr_state = curr_turn[seat]
        prev_obs = _state_obs(prev_state)
        curr_obs = _state_obs(curr_state)
        action = _state_action(curr_state)
        row = transition_effective_sale(prev_obs, curr_obs, action, product)
        transitions += 1
        requested_total += int(row["requested"])
        executed_total += int(row["executed"])
        if row["effective"] is None:
            censored_positive_transitions += 1
        else:
            effective_total += int(row["effective"])

    # If we have a known positive effective sale, the binary target is positive
    # even if a later floor transition is censored. If no known positive exists,
    # a censored executed sale makes the binary target ambiguous, so drop it.
    exact_binary = bool(effective_total > 0 or censored_positive_transitions == 0)
    return {
        "effective_quantity": effective_total if exact_binary else None,
        "requested_quantity": requested_total,
        "executed_quantity": executed_total,
        "censored_positive_transitions": censored_positive_transitions,
        "transitions": transitions,
        "exact_binary": exact_binary,
    }


def build_rows(
    episodes: list[dict[str, Any]],
    product: str,
    *,
    horizon: int = 3,
    stride: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    diagnostics = {
        "candidate_windows": 0,
        "exact_windows": 0,
        "censored_windows": 0,
        "requested_units": 0,
        "executed_units": 0,
        "effective_units": 0,
    }
    for eidx, rep in enumerate(episodes):
        steps = list(rep.get("steps", []) or [])
        if len(steps) < 100:
            continue
        eid = _episode_identity(rep, eidx)
        teams = _team_names(rep)
        for seat in (0, 1):
            team = teams[seat] if seat < len(teams) else f"seat{seat}"
            last_start_exclusive = max(0, len(steps) - horizon - 1)
            for t in range(0, last_start_exclusive, max(1, stride)):
                turn = steps[t]
                if seat >= len(turn) or not isinstance(turn[seat], dict):
                    continue
                obs = _state_obs(turn[seat])
                farms = obs.get("farms", []) if isinstance(obs, dict) else []
                if not isinstance(farms, list) or len(farms) < 2:
                    continue
                try:
                    features = public_sale_features(obs, seat, product)
                except Exception:
                    continue
                target = future_effective_sale_quantity(
                    steps, t, seat, product, horizon=horizon
                )
                diagnostics["candidate_windows"] += 1
                diagnostics["requested_units"] += int(target["requested_quantity"])
                diagnostics["executed_units"] += int(target["executed_quantity"])
                effective = target["effective_quantity"]
                if effective is None:
                    diagnostics["censored_windows"] += 1
                    continue
                diagnostics["exact_windows"] += 1
                diagnostics["effective_units"] += int(effective)
                rows.append({
                    "episode_id": eid,
                    "team": team,
                    "seat": seat,
                    "turn": t,
                    "label": int(int(effective) > 0),
                    "future_effective_sell_quantity": int(effective),
                    "future_requested_sell_quantity": int(target["requested_quantity"]),
                    "future_executed_sell_quantity": int(target["executed_quantity"]),
                    "features": features,
                })
    return rows, diagnostics


def evaluate_product(
    episodes: list[dict[str, Any]],
    product: str,
    *,
    horizon: int,
    stride: int,
) -> dict[str, Any]:
    rows, diagnostics = build_rows(episodes, product, horizon=horizon, stride=stride)
    if not rows:
        return {"product": product, "status": "no_rows", "diagnostics": diagnostics}
    train, valid, split = _split(rows)
    keys = sorted(rows[0]["features"])
    market_keys = [
        k for k in keys
        if k.startswith("market_")
        or k in {"step_frac", "day_frac", "hour_frac", "shop_demand", "town_drain_now", "money_log"}
    ]
    full = _fit(train, valid, keys)
    market = _fit(train, valid, market_keys)
    useful = bool(
        full.get("status") == "ready"
        and float(full.get("auc", 0.0)) >= 0.68
        and float(full.get("top_decile_lift", 0.0)) >= 2.0
        and int(full.get("valid_positives", 0)) >= 20
    )
    market_near_full = bool(
        useful
        and market.get("status") == "ready"
        and float(market.get("auc", 0.0)) >= float(full.get("auc", 0.0)) - 0.02
        and float(market.get("top_decile_lift", 0.0)) >= 2.0
    )
    requested = int(diagnostics["requested_units"])
    executed = int(diagnostics["executed_units"])
    effective = int(diagnostics["effective_units"])
    return {
        "product": product,
        "status": "ready",
        "rows": len(rows),
        "split": split,
        "diagnostics": {
            **diagnostics,
            "execution_fill_rate": executed / requested if requested else 1.0,
            "effective_share_of_executed": effective / executed if executed else 1.0,
            "censor_fraction": diagnostics["censored_windows"] / max(1, diagnostics["candidate_windows"]),
        },
        "full_model": full,
        "market_only_model": market,
        "farm_incremental_auc": (
            float(full.get("auc", 0.0)) - float(market.get("auc", 0.0))
            if full.get("status") == "ready" and market.get("status") == "ready"
            else None
        ),
        "useful": useful,
        "preferred_runtime_features": "market_only" if market_near_full else "full_public_state" if useful else "none",
    }


def run(
    output_root: str | Path,
    *,
    days: int = 3,
    per_day: int = 8,
    horizon: int = 3,
    stride: int = 2,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    episodes, acquisition = fetch_top_episodes(root / "episodes", days=days, per_day=per_day)
    results = [evaluate_product(episodes, product, horizon=horizon, stride=stride) for product in PRODUCTS]
    useful = [r for r in results if r.get("useful")]
    policy_useful = [r for r in useful if r.get("product") in POLICY_PRODUCTS]
    decision = "BUILD_V54_RUNTIME_BELIEF" if len(policy_useful) >= 2 else "HOLD_V54_RUNTIME_BELIEF"
    payload = {
        "experiment": "V54_EXECUTED_SALE_LEARNABILITY",
        "data_contract": "features use public farms/market/town/day/hour only; private state is used only to construct offline labels",
        "replay_contract": "action on replay row t+1 is the decision taken from observation row t",
        "market_contract": "only the first 10 market orders are eligible; same-turn shed mutations occur before market orders",
        "floor_contract": "positive sales on transitions touching the $1 floor are censored unless an earlier exact positive already makes the window label positive",
        "prediction_target": f"any exact market-effective opponent SELL over the next {horizon + 1} decisions",
        "days": days,
        "per_day": per_day,
        "stride": stride,
        "horizon": horizon,
        "acquisition": acquisition,
        "episode_count": len(episodes),
        "products": results,
        "useful_products": [r["product"] for r in useful],
        "policy_useful_products": [r["product"] for r in policy_useful],
        "decision": decision,
        "runtime_policy": (
            "distill only held-out useful public-state signals; do not ship sklearn"
            if decision == "BUILD_V54_RUNTIME_BELIEF"
            else "do not alter runtime policy from this experiment"
        ),
    }
    out = root / "V54_EXECUTED_SALE_RESULT.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict exact market-effective opponent sales from public state")
    parser.add_argument("--output-root", default="tmp/v54-executed-sale")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--per-day", type=int, default=8)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--stride", type=int, default=2)
    args = parser.parse_args()
    result = run(
        args.output_root,
        days=args.days,
        per_day=args.per_day,
        horizon=args.horizon,
        stride=args.stride,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
