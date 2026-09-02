from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from swarm.market_belief import (
    ExternalSupplyEstimate,
    NONBUYABLE_PRODUCTS,
    infer_external_supply,
    sale_quantity,
)
from swarm.v77_live_meta_route_search import fetch_top_episodes

_SHED_ACCESS = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})


def _dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _state_obs(state: Any) -> dict[str, Any]:
    obs = _get(state, "observation", {}) or {}
    return obs if isinstance(obs, dict) else {}


def _state_action(state: Any) -> Any:
    return _get(state, "action", None)


def _own_farm(obs: Any) -> Any:
    farms = list(_get(obs, "farms", []) or [])
    try:
        player = int(_get(obs, "player", 0) or 0)
    except Exception:
        player = 0
    return farms[player] if 0 <= player < len(farms) else {}


def _positions(farm: Any) -> list[tuple[int, int] | None]:
    out: list[tuple[int, int] | None] = []
    farmer = _get(farm, "farmer", None)
    if isinstance(farmer, (list, tuple)) and len(farmer) >= 2:
        out.append((int(farmer[0]), int(farmer[1])))
    else:
        out.append(None)
    for pos in list(_get(farm, "hands", []) or []):
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            out.append((int(pos[0]), int(pos[1])))
        else:
            out.append(None)
    return out


def _unit_actions(action: Any, count: int) -> list[Any]:
    if not isinstance(action, dict):
        return [["PASS"] for _ in range(count)]
    actions: list[Any] = [action.get("farmer", ["PASS"])]
    hands = action.get("hands", [])
    if isinstance(hands, list):
        actions.extend(hands)
    while len(actions) < count:
        actions.append(["PASS"])
    return actions[:count]


def _int_inventory(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = max(0, int(value or 0))
        except Exception:
            continue
    return out


def post_physical_shed(obs: Any, action: Any) -> dict[str, int]:
    """Reconstruct our shed immediately before market execution.

    Kaggriculture applies farmer/hand physical actions before processing the market
    queue.  For non-buyable products, DROP/PLACE/PICKUP are therefore the only
    same-turn operations that can change sellable shed stock before a SELL order.
    The simulation intentionally mirrors the default 100-unit shed and unit order.
    """
    private = _get(obs, "private", {}) or {}
    shed = _int_inventory(_get(private, "shed", {}) or {})
    raw_inventories = list(_get(private, "inventories", []) or [])
    inventories = [_int_inventory(inv) for inv in raw_inventories]
    farm = _own_farm(obs)
    positions = _positions(farm)
    while len(inventories) < len(positions):
        inventories.append({})
    actions = _unit_actions(action, len(positions))

    def room() -> int:
        return max(0, 100 - sum(shed.values()))

    for idx, (pos, unit_action) in enumerate(zip(positions, actions)):
        if pos not in _SHED_ACCESS or not isinstance(unit_action, (list, tuple)) or not unit_action:
            continue
        op = str(unit_action[0])
        inv = inventories[idx]
        if op == "DROP":
            # The engine iterates insertion-ordered inventory entries and transfers
            # each item until shed capacity is exhausted.
            for item, quantity in list(inv.items()):
                take = min(max(0, int(quantity)), room())
                if take:
                    shed[item] = shed.get(item, 0) + take
                    inv[item] = quantity - take
                    if inv[item] <= 0:
                        inv.pop(item, None)
        elif op == "PLACE" and len(unit_action) >= 2:
            item = str(unit_action[1])
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except Exception:
                requested = 0
            take = min(max(0, requested), max(0, inv.get(item, 0)), room())
            if take:
                shed[item] = shed.get(item, 0) + take
                inv[item] = inv.get(item, 0) - take
                if inv[item] <= 0:
                    inv.pop(item, None)
        elif op == "PICKUP" and len(unit_action) >= 2:
            item = str(unit_action[1])
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except Exception:
                requested = 0
            take = min(max(0, requested), max(0, shed.get(item, 0)))
            if take:
                shed[item] = shed.get(item, 0) - take
                inv[item] = inv.get(item, 0) + take
    return shed


def executed_sell_units(obs: Any, action: Any, product: str) -> int:
    """Exact executed SELL quantity for a non-buyable product before floor censoring."""
    requested = sale_quantity(action, product)
    shed = post_physical_shed(obs, action)
    return min(requested, max(0, int(shed.get(str(product), 0) or 0)))


def infer_external_supply_physical(
    prev_obs: Any,
    curr_obs: Any,
    own_previous_action: Any,
    product: str,
) -> ExternalSupplyEstimate:
    """V51 accounting with exact same-turn own shed mutation applied."""
    base = infer_external_supply(prev_obs, curr_obs, own_previous_action, product)
    if not base.exact:
        return base
    corrected_own = executed_sell_units(prev_obs, own_previous_action, product)
    old_own = int(base.own_sell_units or 0)
    signed_external = int(base.effective_units or 0) + old_own - corrected_own
    exact_units = max(0, signed_external)
    note_parts = [base.note] if base.note else []
    if corrected_own != old_own:
        note_parts.append(f"physical shed correction own_sell {old_own}->{corrected_own}")
    if signed_external < 0:
        note_parts.append(f"negative corrected residual {signed_external}")
    return ExternalSupplyEstimate(
        product=base.product,
        exact=True,
        effective_units=exact_units,
        lower_bound=exact_units,
        upper_bound=exact_units,
        floor_censored=False,
        market_delta=base.market_delta,
        town_drain=base.town_drain,
        own_sell_units=corrected_own,
        note="; ".join(note_parts),
    )


def _legacy_truth(state: Any, product: str) -> int:
    action = _state_action(state)
    requested = sale_quantity(action, product)
    obs = _state_obs(state)
    private = obs.get("private", {}) if isinstance(obs, dict) else {}
    shed = private.get("shed", {}) if isinstance(private, dict) else {}
    try:
        available = max(0, int(shed.get(product, 0) or 0))
    except Exception:
        available = 0
    return min(requested, available)


def _transition_truth(pre_obs: Any, action: Any, product: str) -> int:
    return executed_sell_units(pre_obs, action, product)


def _has_shed_mutation(obs: Any, action: Any) -> bool:
    farm = _own_farm(obs)
    positions = _positions(farm)
    actions = _unit_actions(action, len(positions))
    return any(
        pos in _SHED_ACCESS
        and isinstance(unit_action, (list, tuple))
        and bool(unit_action)
        and str(unit_action[0]) in {"DROP", "PLACE", "PICKUP"}
        for pos, unit_action in zip(positions, actions)
    )


def _counter() -> dict[str, float]:
    return {
        "exact_rows": 0.0,
        "matches": 0.0,
        "abs_error": 0.0,
        "sale_rows": 0.0,
        "sale_matches": 0.0,
        "sale_abs_error": 0.0,
    }


def _record(counter: dict[str, float], estimate: ExternalSupplyEstimate, truth: int) -> None:
    if not estimate.exact or estimate.effective_units is None:
        return
    predicted = int(estimate.effective_units)
    error = abs(predicted - int(truth))
    counter["exact_rows"] += 1
    counter["matches"] += float(predicted == int(truth))
    counter["abs_error"] += float(error)
    if int(truth) > 0:
        counter["sale_rows"] += 1
        counter["sale_matches"] += float(predicted == int(truth))
        counter["sale_abs_error"] += float(error)


def _summary(counter: dict[str, float]) -> dict[str, Any]:
    n = int(counter["exact_rows"])
    sales = int(counter["sale_rows"])
    return {
        "exact_rows": n,
        "exact_match_rate": counter["matches"] / n if n else -1.0,
        "mean_abs_error": counter["abs_error"] / n if n else -1.0,
        "sale_rows": sales,
        "sale_exact_match_rate": counter["sale_matches"] / sales if sales else -1.0,
        "sale_mean_abs_error": counter["sale_abs_error"] / sales if sales else -1.0,
    }


def run(output_root: str | Path, *, days: int = 3, per_day: int = 8) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    episodes, acquisition = fetch_top_episodes(root / "episodes", days=days, per_day=per_day)

    aggregate: dict[str, dict[str, float]] = defaultdict(_counter)
    by_product: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(_counter))
    strata: dict[str, dict[str, float]] = defaultdict(_counter)
    lag_grid: dict[tuple[int, int], dict[str, float]] = defaultdict(_counter)

    for rep in episodes:
        steps = list(rep.get("steps", []) or [])
        if len(steps) < 100:
            continue
        for t in range(1, len(steps) - 1):
            turn = steps[t]
            nxt = steps[t + 1]
            if len(turn) < 2 or len(nxt) < 2:
                continue
            for observer in (0, 1):
                target = 1 - observer
                if not isinstance(turn[observer], dict) or not isinstance(turn[target], dict) or not isinstance(nxt[observer], dict):
                    continue
                prev_obs = _state_obs(turn[observer])
                curr_obs = _state_obs(nxt[observer])
                target_pre_obs = _state_obs(turn[target])
                own_action = _state_action(turn[observer])
                target_action = _state_action(turn[target])
                own_mutation = _has_shed_mutation(prev_obs, own_action)
                target_mutation = _has_shed_mutation(target_pre_obs, target_action)

                for product in sorted(NONBUYABLE_PRODUCTS):
                    legacy_est = infer_external_supply(prev_obs, curr_obs, own_action, product)
                    physical_est = infer_external_supply_physical(prev_obs, curr_obs, own_action, product)
                    legacy_truth = _legacy_truth(turn[target], product)
                    physical_truth = _transition_truth(target_pre_obs, target_action, product)

                    _record(aggregate["legacy"], legacy_est, legacy_truth)
                    _record(aggregate["physical"], physical_est, physical_truth)
                    _record(by_product[product]["legacy"], legacy_est, legacy_truth)
                    _record(by_product[product]["physical"], physical_est, physical_truth)
                    if own_mutation or target_mutation:
                        _record(strata["shed_mutation"], physical_est, physical_truth)
                    else:
                        _record(strata["no_shed_mutation"], physical_est, physical_truth)

                    # Action logging can be shifted relative to the observation stored
                    # in a replay. Sweep offsets independently, but always simulate
                    # candidate actions against the transition's pre-state at t.
                    for own_offset in (-1, 0, 1):
                        own_state = steps[t + own_offset][observer]
                        own_candidate_action = _state_action(own_state)
                        estimate = infer_external_supply_physical(
                            prev_obs, curr_obs, own_candidate_action, product
                        )
                        for target_offset in (-1, 0, 1):
                            target_state = steps[t + target_offset][target]
                            truth = _transition_truth(
                                target_pre_obs, _state_action(target_state), product
                            )
                            _record(lag_grid[(own_offset, target_offset)], estimate, truth)

    aggregate_summary = {name: _summary(counter) for name, counter in aggregate.items()}
    product_summary = {
        product: {name: _summary(counter) for name, counter in variants.items()}
        for product, variants in sorted(by_product.items())
    }
    strata_summary = {name: _summary(counter) for name, counter in sorted(strata.items())}
    lag_summary = {
        f"own{own:+d}_target{target:+d}": {
            "own_action_offset": own,
            "target_action_offset": target,
            **_summary(counter),
        }
        for (own, target), counter in sorted(lag_grid.items())
    }
    eligible_lags = [
        row for row in lag_summary.values()
        if int(row["sale_rows"]) >= 30
    ]
    best_lag = max(
        eligible_lags,
        key=lambda row: (
            float(row["sale_exact_match_rate"]),
            float(row["exact_match_rate"]),
            -abs(int(row["own_action_offset"])),
            -abs(int(row["target_action_offset"])),
        ),
        default=None,
    )

    legacy = aggregate_summary.get("legacy", {})
    physical = aggregate_summary.get("physical", {})
    legacy_sale = float(legacy.get("sale_exact_match_rate", -1.0))
    physical_sale = float(physical.get("sale_exact_match_rate", -1.0))
    physical_exact = float(physical.get("exact_match_rate", -1.0))
    physical_pass = bool(
        int(physical.get("exact_rows", 0)) >= 500
        and physical_exact >= 0.98
        and int(physical.get("sale_rows", 0)) >= 30
        and physical_sale >= 0.95
    )
    best_is_zero = bool(
        best_lag
        and int(best_lag["own_action_offset"]) == 0
        and int(best_lag["target_action_offset"]) == 0
    )
    lag_pass = bool(
        best_lag
        and float(best_lag["exact_match_rate"]) >= 0.98
        and int(best_lag["sale_rows"]) >= 30
        and float(best_lag["sale_exact_match_rate"]) >= 0.95
    )

    if physical_pass and physical_sale >= legacy_sale + 0.10:
        decision = "PHYSICAL_SHED_ALIGNMENT_CONFIRMED"
    elif lag_pass and not best_is_zero:
        decision = "ACTION_OFFSET_IDENTIFIED"
    elif physical_pass:
        decision = "ACCOUNTING_VALID_AFTER_PHYSICAL_SIM"
    else:
        decision = "MORE_ALIGNMENT_WORK"

    payload = {
        "experiment": "V52_MARKET_FLOW_ALIGNMENT",
        "hypotheses": {
            "H1": "same-turn DROP/PLACE/PICKUP changes sellable shed stock before market execution",
            "H2": "replay action fields may be offset from the market transition observation",
        },
        "episodes": len(episodes),
        "acquisition": acquisition,
        "aggregate": aggregate_summary,
        "by_product": product_summary,
        "strata": strata_summary,
        "lag_grid": lag_summary,
        "best_lag": best_lag,
        "physical_gate_passed": physical_pass,
        "decision": decision,
        "next_action": (
            "promote physical shed execution into canonical accounting, rerun V51, then test one strategy intervention"
            if decision in {"PHYSICAL_SHED_ALIGNMENT_CONFIRMED", "ACCOUNTING_VALID_AFTER_PHYSICAL_SIM"}
            else "fix replay action alignment and rerun canonical accounting"
            if decision == "ACTION_OFFSET_IDENTIFIED"
            else "inspect residual mismatches by product/stratum before any runtime strategy change"
        ),
    }
    _dump(root / "V52_MARKET_FLOW_ALIGNMENT_RESULT.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="V52 market-flow transition alignment diagnostic")
    parser.add_argument("--output-root", default="tmp/v52-market-flow-alignment")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--per-day", type=int, default=8)
    args = parser.parse_args()
    result = run(args.output_root, days=args.days, per_day=args.per_day)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
