from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any

from swarm.overnight_slate import (
    _pack,
    acquire_public_opponents,
    build_route_candidate,
    evaluate_static_league,
    known_market_variants,
)
from swarm.v77_live_meta_route_search import _hash_text, recover_soil_parent


MOON_SCREEN_SEEDS = [4103, 4127, 4153, 4177, 4201]
FULL_LEAGUE_SEEDS = [5101, 5113, 5147, 5171]


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _patch_token(source: str, before: str, after: str) -> str:
    count = source.count(before)
    if count != 1:
        raise RuntimeError(f"patch token {before!r} count={count}")
    out = source.replace(before, after, 1)
    compile(out, "<moon-counter>", "exec")
    return out


def build_counter_population(parent_source: str) -> dict[str, str]:
    h6 = known_market_variants(parent_source)["MARKET_H6_AGGRO"]
    population: dict[str, str] = {
        "H6_BASE": h6,
        # Moon's public overlay activates only when the first shop is YARN_STORE.
        # The route families share the early prefix, so switch exactly when that
        # information becomes public instead of waiting for a late farm-shape signature.
        "H6_YARN_6C8S": build_route_candidate(
            h6, {("YARN_STORE",): "6c8s_3q"}, "H6_YARN_6C8S"
        ),
        "H6_YARN_8C6S": build_route_candidate(
            h6, {("YARN_STORE",): "8c6s_3q"}, "H6_YARN_8C6S"
        ),
        "H6_YARN_10C4S": build_route_candidate(
            h6, {("YARN_STORE",): "10c4s_3q"}, "H6_YARN_10C4S"
        ),
    }

    # Existing R5/Moon-like counter front-runs only half of predicted premium sales.
    # Test stronger but still bounded front-running. This branch only activates once
    # the public sheep-heavy signature is observed, so it is much safer than a global
    # increase in aggression.
    front75 = _patch_token(h6, "_V17_R5_FRACTION = 0.5", "_V17_R5_FRACTION = 0.75")
    front100 = _patch_token(h6, "_V17_R5_FRACTION = 0.5", "_V17_R5_FRACTION = 1.0")
    population["H6_R5_FRONT75"] = front75
    population["H6_R5_FRONT100"] = front100

    population["H6_YARN_8C6S_R5_100"] = _patch_token(
        population["H6_YARN_8C6S"], "_V17_R5_FRACTION = 0.5", "_V17_R5_FRACTION = 1.0"
    )
    population["H6_YARN_10C4S_R5_100"] = _patch_token(
        population["H6_YARN_10C4S"], "_V17_R5_FRACTION = 0.5", "_V17_R5_FRACTION = 1.0"
    )

    # H6 begins generic market shifting at step 96. First-Yarn information is public
    # at ~72, so test a small timing lead as a separate causal hypothesis.
    population["H6_PREEMPT72"] = _patch_token(h6, "_PREEMPT_START = 96", "_PREEMPT_START = 72")
    return population


def _materialize(root: Path, sources: dict[str, str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for label, source in sources.items():
        d = root / label
        d.mkdir(parents=True, exist_ok=True)
        p = d / "main.py"
        p.write_text(source, encoding="utf-8")
        compile(source, str(p), "exec")
        paths[label] = p
    return paths


def _by_candidate(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["candidate"]): row for row in summary}


def _moon_score(row: dict[str, Any]) -> float:
    family = row.get("family_scores", {}) or {}
    if "public:moon" in family:
        return float(family["public:moon"])
    return float(row.get("win_score", -1.0))


def run(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    parent, parent_info = recover_soil_parent(root / "parent_recovery", max_version=40)
    if parent_info.get("status") != "exact_v76_parent":
        raise RuntimeError(f"exact V76 parent not recovered: {parent_info}")

    population = build_counter_population(parent)
    candidate_paths = _materialize(root / "candidates", population)
    public = acquire_public_opponents(root / "public_frontier")
    moon_path = public.get("public:moon")
    if moon_path is None:
        raise RuntimeError("public Moon controller unavailable")

    # Phase 1: a deliberately adversarial screen. Do not average Moon weakness away.
    _, moon_summary = evaluate_static_league(
        candidate_paths,
        {"public:moon": moon_path},
        MOON_SCREEN_SEEDS,
    )
    moon_by = _by_candidate(moon_summary)
    h6_moon = _moon_score(moon_by["H6_BASE"])

    ordered = sorted(
        population,
        key=lambda name: (
            int(moon_by[name].get("invalid", 999)) == 0,
            _moon_score(moon_by[name]),
            float(moon_by[name].get("cvar20_score", -1.0)),
            float(moon_by[name].get("mean_margin", float("-inf"))),
        ),
        reverse=True,
    )
    # Always keep H6 as the control; spend full-league compute on the best counters.
    survivors = ["H6_BASE"]
    for name in ordered:
        if name == "H6_BASE":
            continue
        if int(moon_by[name].get("invalid", 1)) != 0:
            continue
        survivors.append(name)
        if len(survivors) >= 5:
            break

    survivor_paths = {name: candidate_paths[name] for name in survivors}
    opponents = dict(public)
    opponents["internal:parent"] = root / "parent.py"
    opponents["internal:h6"] = candidate_paths["H6_BASE"]
    (root / "parent.py").write_text(parent, encoding="utf-8")

    _, full_summary = evaluate_static_league(survivor_paths, opponents, FULL_LEAGUE_SEEDS)
    full_by = _by_candidate(full_summary)
    h6_full = full_by["H6_BASE"]
    h6_overall = float(h6_full["win_score"])
    h6_worst = float(h6_full["worst_family_score"])
    h6_full_moon = _moon_score(h6_full)

    ranked: list[dict[str, Any]] = []
    for name in survivors:
        moon = moon_by[name]
        full = full_by[name]
        moon_score = _moon_score(moon)
        overall = float(full["win_score"])
        worst = float(full["worst_family_score"])
        robust_score = 0.45 * overall + 0.35 * moon_score + 0.20 * worst
        moon_delta = moon_score - h6_moon
        overall_delta = overall - h6_overall
        worst_delta = worst - h6_worst
        promote = (
            name != "H6_BASE"
            and int(moon.get("invalid", 1)) == 0
            and int(full.get("invalid", 1)) == 0
            and moon_score >= max(0.50, h6_moon + 0.15)
            and overall >= h6_overall - 0.04
            and worst >= h6_worst
        )
        ranked.append({
            "candidate": name,
            "source_sha256": _hash_text(population[name]),
            "moon_screen_win_score": moon_score,
            "moon_delta_vs_h6": moon_delta,
            "overall_win_score": overall,
            "overall_delta_vs_h6": overall_delta,
            "worst_family_score": worst,
            "worst_delta_vs_h6": worst_delta,
            "full_moon_win_score": _moon_score(full),
            "robust_score": robust_score,
            "invalid_games": int(moon.get("invalid", 0)) + int(full.get("invalid", 0)),
            "family_scores": full.get("family_scores", {}),
            "recommendation": "PROMOTE" if promote else ("CONTROL" if name == "H6_BASE" else "PROBE"),
        })

    ranked.sort(
        key=lambda row: (
            row["recommendation"] == "PROMOTE",
            row["robust_score"],
            row["moon_screen_win_score"],
            row["overall_win_score"],
        ),
        reverse=True,
    )

    # Package the two best non-control strategies. They remain probes unless gates pass.
    packaged: list[dict[str, Any]] = []
    non_control = [row for row in ranked if row["candidate"] != "H6_BASE"][:2]
    for slot, row in enumerate(non_control, start=1):
        archive = root / "submissions" / f"P{slot}_MOON_COUNTER_{row['candidate']}.tar.gz"
        pack = _pack(population[row["candidate"]], archive)
        packaged.append({**row, **pack, "slot": slot})

    result = {
        "decision": "PROMOTE" if any(row["recommendation"] == "PROMOTE" for row in packaged) else "PROBE_ONLY",
        "parent": parent_info,
        "hypothesis": (
            "Moon's first-YARN sheep overlay creates wool crowding. Counter by pivoting H6 "
            "into cow-heavier routes at the first public shop signal and/or front-running its "
            "observable sheep-heavy premium sales more aggressively."
        ),
        "h6_control": {
            "moon_screen_win_score": h6_moon,
            "overall_win_score": h6_overall,
            "worst_family_score": h6_worst,
            "full_moon_win_score": h6_full_moon,
        },
        "moon_screen_seeds": MOON_SCREEN_SEEDS,
        "full_league_seeds": FULL_LEAGUE_SEEDS,
        "survivors": survivors,
        "ranked": ranked,
        "submissions": packaged,
    }
    _atomic_json(root / "MOON_COUNTER_RESULT.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Search H6 for targeted public-Moon counters")
    parser.add_argument("--output-root", default="swarm/runs/moon-counter")
    args = parser.parse_args()
    result = run(args.output_root)
    print(json.dumps({
        "decision": result["decision"],
        "h6_control": result["h6_control"],
        "submissions": [
            {
                "slot": row["slot"],
                "candidate": row["candidate"],
                "recommendation": row["recommendation"],
                "moon": row["moon_screen_win_score"],
                "overall": row["overall_win_score"],
                "worst": row["worst_family_score"],
                "path": row["path"],
            }
            for row in result["submissions"]
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
