from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from src.kagv2.simulator import Game, SHOPS
from swarm.overnight_slate import (
    ROUTE_ARRAYS,
    _pack,
    acquire_public_opponents,
    build_route_candidate,
    evaluate_static_league,
    known_market_variants,
)
from swarm.v77_live_meta_route_search import _hash_text, recover_soil_parent


SEEDS_PER_SHOP = 3
DISCOVERY_START = 6000
FULL_LEAGUE_SEEDS = [7301, 7313, 7331, 7351, 7369, 7393]


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _passive() -> dict[str, Any]:
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _first_shop(seed: int) -> str | None:
    """Resolve the first public shop using the same dependency-free simulator."""
    game = Game(seed=seed)
    for _ in range(72):
        game.step_once([_passive(), _passive()])
    shops = list(game.town.get("unlocked_shops", []) or [])
    return str(shops[0]) if shops else None


def discover_regime_seeds(per_shop: int = SEEDS_PER_SHOP) -> dict[str, list[int]]:
    targets = sorted(SHOPS)
    found: dict[str, list[int]] = {shop: [] for shop in targets}
    seed = DISCOVERY_START
    while any(len(found[shop]) < per_shop for shop in targets):
        shop = _first_shop(seed)
        if shop in found and len(found[shop]) < per_shop:
            found[shop].append(seed)
        seed += 1
        if seed > DISCOVERY_START + 10000:
            missing = {k: v for k, v in found.items() if len(v) < per_shop}
            raise RuntimeError(f"could not discover enough first-shop seeds: {missing}")
    return found


def _materialize(root: Path, sources: dict[str, str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for label, source in sources.items():
        directory = root / label
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "main.py"
        path.write_text(source, encoding="utf-8")
        compile(source, str(path), "exec")
        paths[label] = path
    return paths


def _summary_by_name(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["candidate"]): row for row in summary}


def _route_label(shop: str, route: str) -> str:
    return f"R_{shop}_{route}".replace("-", "_")


def _family_delta(row: dict[str, Any], control: dict[str, Any]) -> dict[str, float]:
    mine = row.get("family_scores", {}) or {}
    base = control.get("family_scores", {}) or {}
    families = sorted(set(mine) | set(base))
    return {family: float(mine.get(family, 0.0)) - float(base.get(family, 0.0)) for family in families}


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(row.get("worst_family_score", -1.0)),
        float(row.get("win_score", -1.0)),
        float(row.get("cvar20_score", -1.0)),
        float(row.get("mean_margin", float("-inf"))),
    )


def run(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    parent, parent_info = recover_soil_parent(root / "parent_recovery", max_version=40)
    if parent_info.get("status") != "exact_v76_parent":
        raise RuntimeError(f"exact V76 parent not recovered: {parent_info}")
    h6 = known_market_variants(parent)["MARKET_H6_AGGRO"]

    public = acquire_public_opponents(root / "public_frontier")
    if not public:
        raise RuntimeError("no public opponent controllers were acquired")

    regime_seeds = discover_regime_seeds()
    regimes: dict[str, Any] = {}
    robust_route_map: dict[tuple[str, ...], str] = {}

    for shop in sorted(regime_seeds):
        sources: dict[str, str] = {"H6_BASE": h6}
        route_names: dict[str, str] = {}
        for route in sorted(ROUTE_ARRAYS):
            label = _route_label(shop, route)
            route_names[route] = label
            sources[label] = build_route_candidate(h6, {(shop,): route}, label)

        paths = _materialize(root / "regimes" / shop / "candidates", sources)
        rows, summary = evaluate_static_league(paths, public, regime_seeds[shop])
        by_name = _summary_by_name(summary)
        control = by_name["H6_BASE"]

        route_rows: list[dict[str, Any]] = []
        for route, label in route_names.items():
            row = by_name[label]
            route_rows.append({
                "route": route,
                "candidate": label,
                "source_sha256": _hash_text(sources[label]),
                "win_score": float(row["win_score"]),
                "delta_vs_h6": float(row["win_score"]) - float(control["win_score"]),
                "worst_family_score": float(row["worst_family_score"]),
                "worst_delta_vs_h6": float(row["worst_family_score"]) - float(control["worst_family_score"]),
                "cvar20_score": float(row["cvar20_score"]),
                "mean_margin": float(row["mean_margin"]),
                "family_scores": row.get("family_scores", {}),
                "family_delta_vs_h6": _family_delta(row, control),
                "invalid": int(row.get("invalid", 0)),
            })

        route_rows.sort(key=_rank_key, reverse=True)
        robust_best = route_rows[0]
        robust_route_map[(shop,)] = str(robust_best["route"])

        best_by_family: dict[str, dict[str, Any]] = {}
        for family in sorted(public):
            ordered = sorted(
                route_rows,
                key=lambda row: (
                    float((row.get("family_scores", {}) or {}).get(family, -1.0)),
                    float(row.get("win_score", -1.0)),
                    float(row.get("worst_family_score", -1.0)),
                ),
                reverse=True,
            )
            best = ordered[0]
            best_by_family[family] = {
                "route": best["route"],
                "score": float((best.get("family_scores", {}) or {}).get(family, -1.0)),
                "delta_vs_h6": float((best.get("family_delta_vs_h6", {}) or {}).get(family, 0.0)),
            }

        regimes[shop] = {
            "seeds": regime_seeds[shop],
            "h6_control": {
                "win_score": float(control["win_score"]),
                "worst_family_score": float(control["worst_family_score"]),
                "family_scores": control.get("family_scores", {}),
            },
            "robust_best_route": robust_best["route"],
            "best_by_family": best_by_family,
            "routes": route_rows,
            "raw_games": len(rows),
        }

    # Build the first-shop robust oracle discovered from the matrix, then require it
    # to survive a fresh unconditional league. This is not promoted solely because
    # it won conditioned screens.
    adaptive = build_route_candidate(h6, robust_route_map, "V47_REGIME_ROBUST")
    adaptive_sources = {"H6_BASE": h6, "V47_REGIME_ROBUST": adaptive}
    adaptive_paths = _materialize(root / "unconditional" / "candidates", adaptive_sources)
    parent_path = root / "unconditional" / "parent.py"
    parent_path.parent.mkdir(parents=True, exist_ok=True)
    parent_path.write_text(parent, encoding="utf-8")
    opponents = dict(public)
    opponents["internal:parent"] = parent_path
    opponents["internal:h6"] = adaptive_paths["H6_BASE"]
    _, full_summary = evaluate_static_league(adaptive_paths, opponents, FULL_LEAGUE_SEEDS)
    full = _summary_by_name(full_summary)
    base = full["H6_BASE"]
    candidate = full["V47_REGIME_ROBUST"]

    overall_delta = float(candidate["win_score"]) - float(base["win_score"])
    worst_delta = float(candidate["worst_family_score"]) - float(base["worst_family_score"])
    promote = (
        int(candidate.get("invalid", 1)) == 0
        and overall_delta >= 0.02
        and worst_delta >= 0.0
    )

    packaged = _pack(adaptive, root / "submissions" / "V47_REGIME_ROBUST.tar.gz")
    result = {
        "decision": "PROMOTE" if promote else "LEARN_ONLY",
        "hypothesis": (
            "The best physical route is conditional on the first public shop and opponent family. "
            "Map that interaction explicitly, then distill only robust first-shop responses into H6."
        ),
        "parent": parent_info,
        "public_opponents": sorted(public),
        "regime_seeds": regime_seeds,
        "regimes": regimes,
        "robust_route_map": {"|".join(k): v for k, v in sorted(robust_route_map.items())},
        "unconditional": {
            "seeds": FULL_LEAGUE_SEEDS,
            "h6_win_score": float(base["win_score"]),
            "candidate_win_score": float(candidate["win_score"]),
            "overall_delta": overall_delta,
            "h6_worst_family": float(base["worst_family_score"]),
            "candidate_worst_family": float(candidate["worst_family_score"]),
            "worst_delta": worst_delta,
            "h6_family_scores": base.get("family_scores", {}),
            "candidate_family_scores": candidate.get("family_scores", {}),
        },
        "submission": {**packaged, "recommendation": "PROMOTE" if promote else "DO_NOT_SUBMIT"},
    }
    _atomic_json(root / "V47_REGIME_MATRIX.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Map first-shop x opponent-family route responses")
    parser.add_argument("--output-root", default="swarm/runs/v47-regime-matrix")
    args = parser.parse_args()
    result = run(args.output_root)
    print(json.dumps({
        "decision": result["decision"],
        "robust_route_map": result["robust_route_map"],
        "unconditional": result["unconditional"],
        "submission": result["submission"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
