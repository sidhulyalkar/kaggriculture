from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from swarm.market_belief import NONBUYABLE_PRODUCTS, infer_external_supply, sale_quantity
from swarm.v77_live_meta_route_search import fetch_top_episodes


def _dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _state_obs(state: Any) -> dict[str, Any]:
    return state.get("observation", {}) if isinstance(state, dict) else {}


def _state_action(state: Any) -> Any:
    return state.get("action") if isinstance(state, dict) else None


def _executed_sell_upper(state: Any, product: str) -> int:
    """Ground-truth non-floor execution from replay-private state, evaluator only."""
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


def run(output_root: str | Path, *, days: int = 3, per_day: int = 8) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    episodes, acquisition = fetch_top_episodes(root / "episodes", days=days, per_day=per_day)

    rows: list[dict[str, Any]] = []
    for eidx, rep in enumerate(episodes):
        steps = list(rep.get("steps", []) or [])
        if len(steps) < 100:
            continue
        eid = str((rep.get("info", {}) or {}).get("EpisodeId", rep.get("id", eidx)))
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
                own_action = _state_action(turn[observer])
                for product in sorted(NONBUYABLE_PRODUCTS):
                    try:
                        estimate = infer_external_supply(prev_obs, curr_obs, own_action, product)
                    except Exception as exc:
                        rows.append({"episode_id": eid, "turn": t, "observer": observer, "product": product, "status": "error", "error": repr(exc)[:300]})
                        continue
                    truth = _executed_sell_upper(turn[target], product)
                    rows.append({
                        "episode_id": eid,
                        "turn": t,
                        "observer": observer,
                        "product": product,
                        "status": "exact" if estimate.exact else "censored",
                        "estimated": estimate.effective_units,
                        "truth": truth,
                        "abs_error": abs(int(estimate.effective_units or 0) - truth) if estimate.exact else None,
                        "floor_censored": estimate.floor_censored,
                        "market_delta": estimate.market_delta,
                        "town_drain": estimate.town_drain,
                        "note": estimate.note,
                    })

    by_product: dict[str, Any] = {}
    exact_all: list[dict[str, Any]] = []
    for product in sorted(NONBUYABLE_PRODUCTS):
        q = [r for r in rows if r.get("product") == product]
        exact = [r for r in q if r.get("status") == "exact"]
        exact_all.extend(exact)
        errors = [int(r["abs_error"]) for r in exact if r.get("abs_error") is not None]
        matches = [int(r.get("estimated") or 0) == int(r.get("truth") or 0) for r in exact]
        sale_rows = [r for r in exact if int(r.get("truth") or 0) > 0]
        sale_matches = [int(r.get("estimated") or 0) == int(r.get("truth") or 0) for r in sale_rows]
        by_product[product] = {
            "rows": len(q),
            "exact_rows": len(exact),
            "censored_rows": len(q) - len(exact),
            "exact_match_rate": statistics.mean(matches) if matches else -1.0,
            "mean_abs_error": statistics.mean(errors) if errors else -1.0,
            "sale_rows": len(sale_rows),
            "sale_exact_match_rate": statistics.mean(sale_matches) if sale_matches else -1.0,
        }

    all_matches = [int(r.get("estimated") or 0) == int(r.get("truth") or 0) for r in exact_all]
    all_errors = [int(r["abs_error"]) for r in exact_all if r.get("abs_error") is not None]
    sale_exact = [r for r in exact_all if int(r.get("truth") or 0) > 0]
    sale_matches = [int(r.get("estimated") or 0) == int(r.get("truth") or 0) for r in sale_exact]
    exact_match_rate = statistics.mean(all_matches) if all_matches else -1.0
    sale_match_rate = statistics.mean(sale_matches) if sale_matches else -1.0
    accounting_valid = bool(len(exact_all) >= 500 and exact_match_rate >= 0.98 and len(sale_exact) >= 30 and sale_match_rate >= 0.95)
    payload = {
        "experiment": "V51_MARKET_FLOW_VALIDATION",
        "contract": "inference uses observer public market/town plus observer's own private shed/action; target private state is ground truth only",
        "episodes": len(episodes),
        "acquisition": acquisition,
        "overall": {
            "exact_rows": len(exact_all),
            "sale_rows": len(sale_exact),
            "exact_match_rate": exact_match_rate,
            "sale_exact_match_rate": sale_match_rate,
            "mean_abs_error": statistics.mean(all_errors) if all_errors else -1.0,
        },
        "by_product": by_product,
        "accounting_valid": accounting_valid,
        "decision": "USE_HARD_FLOW_SIGNAL" if accounting_valid else "FIX_ALIGNMENT_BEFORE_RUNTIME",
    }
    _dump(root / "V51_MARKET_FLOW_RESULT.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate public market-flow opponent inference against replay-private labels")
    parser.add_argument("--output-root", default="tmp/v51-market-flow")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--per-day", type=int, default=8)
    args = parser.parse_args()
    result = run(args.output_root, days=args.days, per_day=args.per_day)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
