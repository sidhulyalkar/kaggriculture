from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from swarm.market_belief import public_sale_features, sale_quantity
from swarm.v77_live_meta_route_search import fetch_top_episodes

PRODUCTS = ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER", "WHEAT")


def _dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _stable_bucket(text: str, modulo: int = 4) -> int:
    return int(sha256(text.encode("utf-8")).hexdigest()[:8], 16) % modulo


def _state_action(state: Any) -> Any:
    return state.get("action") if isinstance(state, dict) else None


def _state_obs(state: Any) -> Any:
    return state.get("observation", {}) if isinstance(state, dict) else {}


def _episode_identity(rep: dict[str, Any], fallback: int) -> str:
    info = rep.get("info", {}) or {}
    return str(info.get("EpisodeId", rep.get("id", fallback)))


def _team_names(rep: dict[str, Any]) -> list[str]:
    info = rep.get("info", {}) or {}
    names = list(info.get("TeamNames") or [])
    return [str(x) for x in names]


def future_sale_quantity(
    steps: list[Any],
    observation_index: int,
    seat: int,
    product: str,
    *,
    horizon: int,
) -> int:
    """Requested sale quantity over the next ``horizon + 1`` decisions.

    Kaggle replay row ``t`` contains observation[t] but the action attached to that
    row produced that observation.  The first decision made *from* observation[t]
    is therefore stored on replay row t+1.  Keeping this offset explicit prevents
    the probe from accidentally using a past action as a future label.
    """
    total = 0
    for dt in range(horizon + 1):
        action_index = observation_index + 1 + dt
        if action_index >= len(steps):
            break
        future = steps[action_index]
        if seat >= len(future):
            continue
        total += sale_quantity(_state_action(future[seat]), product)
    return total


def build_rows(episodes: list[dict[str, Any]], product: str, *, horizon: int = 3, stride: int = 2) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for eidx, rep in enumerate(episodes):
        steps = list(rep.get("steps", []) or [])
        if len(steps) < 100:
            continue
        eid = _episode_identity(rep, eidx)
        teams = _team_names(rep)
        for seat in (0, 1):
            team = teams[seat] if seat < len(teams) else f"seat{seat}"
            # Require the complete future decision window t+1..t+1+horizon.
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
                future_qty = future_sale_quantity(
                    steps,
                    t,
                    seat,
                    product,
                    horizon=horizon,
                )
                rows.append({
                    "episode_id": eid,
                    "team": team,
                    "seat": seat,
                    "turn": t,
                    "label": int(future_qty > 0),
                    "future_sell_quantity": future_qty,
                    "features": features,
                })
    return rows


def _split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    teams = sorted({str(r["team"]) for r in rows})
    holdout_teams = {team for team in teams if _stable_bucket(team, 4) == 0}
    if len(holdout_teams) >= 2 and len(holdout_teams) < len(teams):
        train = [r for r in rows if r["team"] not in holdout_teams]
        valid = [r for r in rows if r["team"] in holdout_teams]
        return train, valid, {"mode": "team_holdout", "holdout_teams": sorted(holdout_teams), "team_count": len(teams)}
    episodes = sorted({str(r["episode_id"]) for r in rows})
    holdout_eps = {eid for eid in episodes if _stable_bucket(eid, 4) == 0}
    if not holdout_eps or len(holdout_eps) == len(episodes):
        holdout_eps = set(episodes[::4])
    train = [r for r in rows if r["episode_id"] not in holdout_eps]
    valid = [r for r in rows if r["episode_id"] in holdout_eps]
    return train, valid, {"mode": "episode_holdout", "holdout_episodes": sorted(holdout_eps), "episode_count": len(episodes)}


def _matrix(rows: list[dict[str, Any]], keys: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray([[float(r["features"].get(k, 0.0)) for k in keys] for r in rows], dtype=np.float64)
    y = np.asarray([int(r["label"]) for r in rows], dtype=np.int64)
    return x, y


def _fit(train: list[dict[str, Any]], valid: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    xtr, ytr = _matrix(train, keys)
    xva, yva = _matrix(valid, keys)
    positives_train = int(ytr.sum())
    positives_valid = int(yva.sum())
    if len(np.unique(ytr)) < 2 or len(np.unique(yva)) < 2 or positives_train < 10 or positives_valid < 5:
        return {
            "status": "insufficient_labels",
            "train": len(train), "valid": len(valid),
            "train_positives": positives_train, "valid_positives": positives_valid,
        }
    model = Pipeline([
        ("scale", StandardScaler()),
        ("logit", LogisticRegression(class_weight="balanced", max_iter=600, C=0.5, random_state=50)),
    ])
    model.fit(xtr, ytr)
    prob = model.predict_proba(xva)[:, 1]
    auc = float(roc_auc_score(yva, prob))
    prevalence = float(yva.mean())
    n_top = max(1, int(round(0.10 * len(yva))))
    top_idx = np.argsort(prob)[-n_top:]
    top_precision = float(yva[top_idx].mean())
    lift = top_precision / prevalence if prevalence > 0 else 0.0
    brier = float(brier_score_loss(yva, prob))
    coef = model.named_steps["logit"].coef_[0]
    ranked = sorted(
        ({"feature": key, "coefficient": float(c), "abs_coefficient": abs(float(c))} for key, c in zip(keys, coef)),
        key=lambda x: x["abs_coefficient"],
        reverse=True,
    )
    return {
        "status": "ready",
        "train": len(train), "valid": len(valid),
        "train_positives": positives_train, "valid_positives": positives_valid,
        "prevalence": prevalence,
        "auc": auc,
        "top_decile_precision": top_precision,
        "top_decile_lift": lift,
        "brier": brier,
        "top_features": ranked[:12],
        "feature_count": len(keys),
    }


def evaluate_product(episodes: list[dict[str, Any]], product: str, *, horizon: int, stride: int) -> dict[str, Any]:
    rows = build_rows(episodes, product, horizon=horizon, stride=stride)
    if not rows:
        return {"product": product, "status": "no_rows"}
    train, valid, split = _split(rows)
    keys = sorted(rows[0]["features"])
    market_keys = [
        k for k in keys
        if k.startswith("market_") or k in {"step_frac", "day_frac", "hour_frac", "shop_demand", "town_drain_now", "money_log"}
    ]
    full = _fit(train, valid, keys)
    market = _fit(train, valid, market_keys)
    useful = bool(
        full.get("status") == "ready"
        and float(full.get("auc", 0)) >= 0.65
        and float(full.get("top_decile_lift", 0)) >= 2.0
        and int(full.get("valid_positives", 0)) >= 10
    )
    market_near_full = bool(
        useful
        and market.get("status") == "ready"
        and float(market.get("auc", 0)) >= float(full.get("auc", 0)) - 0.02
    )
    return {
        "product": product,
        "status": "ready",
        "rows": len(rows),
        "split": split,
        "full_model": full,
        "market_only_model": market,
        "farm_incremental_auc": (
            float(full.get("auc", 0)) - float(market.get("auc", 0))
            if full.get("status") == "ready" and market.get("status") == "ready" else None
        ),
        "useful": useful,
        "preferred_runtime_features": "market_only" if market_near_full else "full_public_state" if useful else "none",
    }


def run(output_root: str | Path, *, days: int = 3, per_day: int = 8, horizon: int = 3, stride: int = 2) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    episodes, acquisition = fetch_top_episodes(root / "episodes", days=days, per_day=per_day)
    results = [evaluate_product(episodes, product, horizon=horizon, stride=stride) for product in PRODUCTS]
    useful = [r for r in results if r.get("useful")]
    market_only = [r["product"] for r in useful if r.get("preferred_runtime_features") == "market_only"]
    decision = "BUILD_RUNTIME_BELIEF" if len(useful) >= 2 else "HOLD_BELIEF_LAYER"
    payload = {
        "experiment": "V50_SALE_INTENT_LEARNABILITY",
        "data_contract": "features use public farms/market/town/day/hour only; private state is excluded",
        "replay_contract": "action stored on replay row t+1 is the decision taken from observation row t",
        "replay_action_offset": 1,
        "prediction_target": f"opponent SELL for product over the next {horizon + 1} decisions after the current observation",
        "days": days,
        "per_day": per_day,
        "stride": stride,
        "acquisition": acquisition,
        "episode_count": len(episodes),
        "products": results,
        "useful_products": [r["product"] for r in useful],
        "market_only_products": market_only,
        "decision": decision,
        "runtime_policy": (
            "distill the simplest held-out predictive signals only; do not ship sklearn"
            if decision == "BUILD_RUNTIME_BELIEF" else
            "do not spend submission bytes on sale-intent modelling"
        ),
    }
    _dump(root / "V50_SALE_INTENT_RESULT.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Test whether public state predicts imminent opponent sales")
    parser.add_argument("--output-root", default="tmp/v50-sale-intent")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--per-day", type=int, default=8)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--stride", type=int, default=2)
    args = parser.parse_args()
    result = run(args.output_root, days=args.days, per_day=args.per_day, horizon=args.horizon, stride=args.stride)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
