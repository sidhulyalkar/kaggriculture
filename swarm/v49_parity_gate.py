from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from swarm.observation_parity import inject_parity_shim
from swarm.overnight_slate import (
    _pack,
    acquire_public_opponents,
    evaluate_static_league,
    known_market_variants,
)
from swarm.v77_live_meta_route_search import recover_soil_parent


def _json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def reproduce_official_step_asymmetry() -> dict[str, Any]:
    """Probe the installed official environment before trusting any benchmark."""
    from kaggle_environments import make

    def probe(obs, configuration=None):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    env = make("kaggriculture", configuration={"episodeSteps": 8, "seed": 49001}, debug=False)
    env.run([probe, probe])
    samples = []
    for i, turn in enumerate(env.steps[:8]):
        def read(state, key):
            obs = state.observation
            if isinstance(obs, dict):
                return obs.get(key)
            return getattr(obs, key, None)
        samples.append({
            "turn": i,
            "seat0_step": read(turn[0], "step"),
            "seat1_step": read(turn[1], "step"),
            "seat0_day": read(turn[0], "day"),
            "seat1_day": read(turn[1], "day"),
            "seat0_hour": read(turn[0], "hour"),
            "seat1_hour": read(turn[1], "hour"),
        })
    seat0_advances = all(row["seat0_step"] == row["turn"] for row in samples)
    seat1_missing = all(row["seat1_step"] is None for row in samples)
    day_hour_equal = all(
        row["seat0_day"] == row["seat1_day"] and row["seat0_hour"] == row["seat1_hour"]
        for row in samples
    )
    return {
        "samples": samples,
        "seat0_step_advances": seat0_advances,
        "seat1_step_missing": seat1_missing,
        "day_hour_equal_across_seats": day_hour_equal,
        "bug_reproduced": bool(seat0_advances and seat1_missing and day_hour_equal),
    }


def _write_sources(root: Path, sources: dict[str, str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for name, source in sources.items():
        target = root / name / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        compile(source, f"<{name}>", "exec")
        out[name] = target
    return out


def _parity_fix_public_opponents(root: Path, opponents: dict[str, Path]) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    fixed: dict[str, Path] = {}
    report: list[dict[str, Any]] = []
    for family, path in sorted(opponents.items()):
        source = path.read_text(encoding="utf-8")
        uses_step = '"step"' in source or "'step'" in source
        try:
            patched = inject_parity_shim(source)
            target = root / family.replace(":", "_") / "main.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patched, encoding="utf-8")
            fixed[f"{family}:parity"] = target
            report.append({"family": family, "status": "parity_fixed", "uses_step_text": uses_step})
        except Exception as exc:
            # A strategy that never reads step does not need the shim. A step-reading
            # strategy that cannot be patched is excluded rather than silently biasing
            # the external benchmark.
            if not uses_step:
                fixed[f"{family}:step_independent"] = path
                report.append({"family": family, "status": "step_independent", "uses_step_text": False})
            else:
                report.append({"family": family, "status": "excluded", "uses_step_text": True, "error": repr(exc)[:300]})
    return fixed, report


def _seat_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("ok"):
            grouped[str(row["candidate"])][int(row["seat"])].append(float(row["score"]))
    out: dict[str, dict[str, float]] = {}
    for candidate, seats in grouped.items():
        out[candidate] = {
            f"seat{seat}": statistics.mean(vals) if vals else -1.0
            for seat, vals in sorted(seats.items())
        }
    return out


def _by_name(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["candidate"]): row for row in summary}


def run(output_root: str | Path, *, seeds: list[int] | None = None) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    seeds = seeds or [4901, 4919, 4931, 4951]

    env_probe = reproduce_official_step_asymmetry()

    parent, parent_info = recover_soil_parent(root / "parent_recovery", max_version=40)
    h6 = known_market_variants(parent)["MARKET_H6_AGGRO"]
    fixed_parent = inject_parity_shim(parent)
    fixed_h6 = inject_parity_shim(h6)

    sources = {
        "PARENT_ORIGINAL": parent,
        "PARENT_PARITY": fixed_parent,
        "H6_ORIGINAL": h6,
        "H6_PARITY": fixed_h6,
    }
    candidate_paths = _write_sources(root / "candidates", sources)

    public = acquire_public_opponents(root / "public_downloads")
    external, opponent_report = _parity_fix_public_opponents(root / "parity_opponents", public)
    if len(external) < 3:
        raise RuntimeError(f"only {len(external)} parity-safe external opponents available")

    rows, summary = evaluate_static_league(candidate_paths, external, seeds)
    seat_summary = _seat_summary(rows)
    indexed = _by_name(summary)

    def score(name: str) -> float:
        return float(indexed.get(name, {}).get("win_score", -1.0))

    h6_seat0 = float(seat_summary.get("H6_ORIGINAL", {}).get("seat0", -1.0))
    h6_seat1 = float(seat_summary.get("H6_ORIGINAL", {}).get("seat1", -1.0))
    fixed_seat0 = float(seat_summary.get("H6_PARITY", {}).get("seat0", -1.0))
    fixed_seat1 = float(seat_summary.get("H6_PARITY", {}).get("seat1", -1.0))

    # Causal signature: the fix should primarily rescue seat 1 without materially
    # damaging seat 0. The aggregate threshold is intentionally secondary.
    seat1_rescue = fixed_seat1 - h6_seat1
    seat0_delta = fixed_seat0 - h6_seat0
    aggregate_delta = score("H6_PARITY") - score("H6_ORIGINAL")
    parity_effect_confirmed = bool(
        env_probe["bug_reproduced"]
        and seat1_rescue >= 0.15
        and seat0_delta >= -0.05
        and aggregate_delta >= 0.05
    )

    packages = {
        "H6_PARITY": _pack(fixed_h6, root / "packages" / "SUBMIT_V49_H6_PARITY_FIXED.tar.gz"),
        "PARENT_PARITY": _pack(fixed_parent, root / "packages" / "SUBMIT_V49_SOIL_PARENT_PARITY_FIXED.tar.gz"),
    }

    payload = {
        "experiment": "V49_PARITY_FIRST",
        "principle": "fix execution parity before strategic mutation",
        "environment_probe": env_probe,
        "parent": parent_info,
        "external_opponents": opponent_report,
        "external_opponent_count": len(external),
        "seeds": seeds,
        "games": len(rows),
        "summary": summary,
        "seat_summary": seat_summary,
        "causal_effect": {
            "h6_seat1_rescue": seat1_rescue,
            "h6_seat0_delta": seat0_delta,
            "h6_aggregate_delta": aggregate_delta,
            "confirmed": parity_effect_confirmed,
        },
        "packages": packages,
        "decision": "PARITY_ROOT_CAUSE_CONFIRMED" if parity_effect_confirmed else "PARITY_EFFECT_NOT_YET_CONFIRMED",
        "submission_policy": (
            "At most one minimal parity-fixed live probe; do not bundle new strategy changes."
            if parity_effect_confirmed
            else "Do not submit; investigate benchmark/environment mismatch."
        ),
    }
    _json(root / "V49_PARITY_RESULT.json", payload)
    _json(root / "rows.json", rows)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="V49 seat-parity causal gate")
    parser.add_argument("--output-root", default="tmp/v49-parity")
    parser.add_argument("--seeds", default="4901,4919,4931,4951")
    args = parser.parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    result = run(args.output_root, seeds=seeds)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
