from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

from swarm.observation_parity import inject_parity_shim
from swarm.overnight_slate import acquire_public_opponents, evaluate_static_league, known_market_variants
from swarm.v49_parity_gate import _parity_fix_public_opponents, _write_sources
from swarm.v77_live_meta_route_search import (
    _run_game,
    fetch_top_episodes,
    recover_soil_parent,
    replay_agent_source,
    winner_traces,
)


def _dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _action_key(action: Any) -> str:
    return json.dumps(action if isinstance(action, dict) else None, sort_keys=True, separators=(",", ":"), default=str)


def _market_order_count(action: Any) -> int:
    if not isinstance(action, dict):
        return 0
    market = action.get("market", []) or []
    return len(market) if isinstance(market, list) else 0


def _run_action_trace(candidate: Path, neutral: Path, seed: int, seat: int) -> dict[str, Any]:
    """Run a candidate and return only observable action-trace diagnostics."""
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": int(seed)}, debug=False)
    agents = [str(candidate), str(neutral)] if seat == 0 else [str(neutral), str(candidate)]
    env.run(agents)
    actions: list[Any] = []
    statuses: list[str] = []
    for turn in env.steps:
        state = turn[seat]
        action = state.action if hasattr(state, "action") else state.get("action")
        actions.append(action)
    last = env.steps[-1]
    for i in (0, 1):
        state = last[i]
        statuses.append(str(state.status if hasattr(state, "status") else state.get("status")))
    keys = [_action_key(a) for a in actions]
    first = keys[0] if keys else ""
    return {
        "ok": all(x == "DONE" for x in statuses),
        "statuses": statuses,
        "actions": keys,
        "distinct_actions": len(set(keys)),
        "turn0_repeat_fraction": (sum(k == first for k in keys) / len(keys)) if keys else 1.0,
        "market_orders": sum(_market_order_count(a) for a in actions),
        "nonempty_market_turns": sum(_market_order_count(a) > 0 for a in actions),
    }


def _compare_traces(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    aa = list(a.get("actions", []))
    bb = list(b.get("actions", []))
    n = min(len(aa), len(bb))
    equal = [aa[i] == bb[i] for i in range(n)]
    first_divergence = next((i for i, same in enumerate(equal) if not same), None)
    return {
        "turns_compared": n,
        "action_equality": (sum(equal) / n) if n else 0.0,
        "first_divergence": first_divergence,
        "original_distinct_actions": a.get("distinct_actions", 0),
        "parity_distinct_actions": b.get("distinct_actions", 0),
        "original_turn0_repeat_fraction": a.get("turn0_repeat_fraction", 1.0),
        "parity_turn0_repeat_fraction": b.get("turn0_repeat_fraction", 1.0),
        "original_market_orders": a.get("market_orders", 0),
        "parity_market_orders": b.get("market_orders", 0),
    }


def behavioral_sensitivity(root: Path, original: Path, parity: Path, seeds: list[int]) -> dict[str, Any]:
    neutral = root / "neutral" / "main.py"
    neutral.parent.mkdir(parents=True, exist_ok=True)
    neutral.write_text(
        'def agent(obs, configuration=None):\n    return {"farmer":["PASS"],"hands":[],"market":[]}\n',
        encoding="utf-8",
    )
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        for seat in (0, 1):
            before = _run_action_trace(original, neutral, seed, seat)
            after = _run_action_trace(parity, neutral, seed, seat)
            rows.append({"seed": seed, "seat": seat, **_compare_traces(before, after)})
    by_seat: dict[str, Any] = {}
    for seat in (0, 1):
        q = [r for r in rows if r["seat"] == seat]
        by_seat[f"seat{seat}"] = {
            "games": len(q),
            "mean_action_equality": statistics.mean(r["action_equality"] for r in q),
            "median_first_divergence": statistics.median(
                r["first_divergence"] if r["first_divergence"] is not None else r["turns_compared"] for r in q
            ),
            "mean_original_turn0_repeat_fraction": statistics.mean(r["original_turn0_repeat_fraction"] for r in q),
            "mean_parity_turn0_repeat_fraction": statistics.mean(r["parity_turn0_repeat_fraction"] for r in q),
            "mean_original_market_orders": statistics.mean(r["original_market_orders"] for r in q),
            "mean_parity_market_orders": statistics.mean(r["parity_market_orders"] for r in q),
        }
    return {"rows": rows, "by_seat": by_seat}


def _seat_public_summary(rows: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in names:
        mine = [r for r in rows if r.get("candidate") == name and r.get("ok")]
        item: dict[str, Any] = {}
        for seat in (0, 1):
            vals = [float(r["score"]) for r in mine if int(r.get("seat", -1)) == seat]
            item[f"seat{seat}"] = statistics.mean(vals) if vals else -1.0
        vals = [float(r["score"]) for r in mine]
        item["overall"] = statistics.mean(vals) if vals else -1.0
        out[name] = item
    return out


def replay_panel(root: Path, candidates: dict[str, Path], *, days: int, per_day: int) -> dict[str, Any]:
    episodes, acquisition = fetch_top_episodes(root / "episodes", days=days, per_day=per_day)
    traces = winner_traces(episodes)
    traces.sort(key=lambda x: float(x.get("avg_score", 0)), reverse=True)
    traces = traces[: max(6, days * per_day)]

    rows: list[dict[str, Any]] = []
    for tid, trace in enumerate(traces):
        opp = root / "replay_opponents" / str(tid) / "main.py"
        opp.parent.mkdir(parents=True, exist_ok=True)
        opp.write_text(replay_agent_source(trace["action_map"]), encoding="utf-8")
        # Preserve the replay winner's historical seat. This keeps its physical action
        # script meaningful while naturally exposing our candidate to both seats across
        # a diverse replay panel.
        candidate_seat = int(trace["candidate_seat"])
        for name, path in candidates.items():
            result = _run_game(path, opp, int(trace["seed"]), candidate_seat)
            rows.append({
                "candidate": name,
                "trace": tid,
                "candidate_seat": candidate_seat,
                "team": trace["team"],
                "episode_id": trace["episode_id"],
                "avg_score": trace["avg_score"],
                **result,
            })

    summary: dict[str, Any] = {}
    for name in candidates:
        mine = [r for r in rows if r["candidate"] == name and r.get("ok")]
        scores = [float(r["score"]) for r in mine]
        by_seat = {}
        for seat in (0, 1):
            vals = [float(r["score"]) for r in mine if int(r["candidate_seat"]) == seat]
            by_seat[f"seat{seat}"] = statistics.mean(vals) if vals else -1.0
        summary[name] = {
            "valid": len(mine),
            "win_score": statistics.mean(scores) if scores else -1.0,
            "seat_scores": by_seat,
            "mean_teacher_score": statistics.mean(float(r["avg_score"]) for r in mine) if mine else -1.0,
        }
    return {"acquisition": acquisition, "traces": [{k: t[k] for k in ("episode_id", "team", "seed", "candidate_seat", "avg_score")} for t in traces], "rows": rows, "summary": summary}


def run(output_root: str | Path, *, seeds: list[int] | None = None, days: int = 2, per_day: int = 6) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    seeds = seeds or [4901, 4919, 4931, 4951]

    parent, parent_info = recover_soil_parent(root / "parent", max_version=40)
    h6 = known_market_variants(parent)["MARKET_H6_AGGRO"]
    h6_parity = inject_parity_shim(h6)
    candidate_paths = _write_sources(root / "candidates", {"H6_ORIGINAL": h6, "H6_PARITY": h6_parity})

    behavior = behavioral_sensitivity(root / "behavior", candidate_paths["H6_ORIGINAL"], candidate_paths["H6_PARITY"], seeds[:3])

    public = acquire_public_opponents(root / "public")
    external, opponent_report = _parity_fix_public_opponents(root / "public_parity", public)
    excluded = [r for r in opponent_report if r.get("status") == "excluded"]
    public_rows, public_summary_rows = evaluate_static_league(candidate_paths, external, seeds)
    public_seats = _seat_public_summary(public_rows, list(candidate_paths))

    replay = replay_panel(root / "live_replays", candidate_paths, days=days, per_day=per_day)

    b0 = behavior["by_seat"]["seat0"]
    b1 = behavior["by_seat"]["seat1"]
    p0 = public_seats["H6_ORIGINAL"]
    p1 = public_seats["H6_PARITY"]
    r0 = replay["summary"]["H6_ORIGINAL"]
    r1 = replay["summary"]["H6_PARITY"]

    behavior_control_ok = float(b0["mean_action_equality"]) >= 0.98
    seat1_behavior_changed = float(b1["mean_action_equality"]) <= 0.90
    competitive_delta = 0.5 * (float(p1["overall"]) - float(p0["overall"])) + 0.5 * (float(r1["win_score"]) - float(r0["win_score"]))
    benchmark_discriminative = bool(
        len(external) >= 4
        and not excluded
        and (
            abs(float(p1["overall"]) - float(p0["overall"])) > 1e-9
            or abs(float(r1["win_score"]) - float(r0["win_score"])) > 1e-9
            or float(b1["mean_action_equality"]) < 0.999
        )
    )
    parity_competitive_rescue = bool(
        behavior_control_ok
        and seat1_behavior_changed
        and benchmark_discriminative
        and competitive_delta >= 0.04
        and float(p1["seat0"]) >= float(p0["seat0"]) - 0.03
    )

    decision = "PARITY_COMPETITIVE_RESCUE" if parity_competitive_rescue else "NO_PARITY_SUBMISSION"
    payload = {
        "experiment": "V49B_PARITY_SENSITIVITY",
        "parent": parent_info,
        "seeds": seeds,
        "behavior": behavior,
        "public_opponents": opponent_report,
        "public_summary": public_summary_rows,
        "public_seat_summary": public_seats,
        "replay_panel": replay,
        "gates": {
            "behavior_control_ok": behavior_control_ok,
            "seat1_behavior_changed": seat1_behavior_changed,
            "benchmark_discriminative": benchmark_discriminative,
            "competitive_delta": competitive_delta,
            "parity_competitive_rescue": parity_competitive_rescue,
        },
        "decision": decision,
        "submission_policy": "one parity-only probe" if parity_competitive_rescue else "do not submit parity-only candidate",
    }
    _dump(root / "V49B_RESULT.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="V49B behavioral and current-meta parity gate")
    parser.add_argument("--output-root", default="tmp/v49b")
    parser.add_argument("--seeds", default="4901,4919,4931,4951")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--per-day", type=int, default=6)
    args = parser.parse_args()
    result = run(
        args.output_root,
        seeds=[int(x) for x in args.seeds.split(",") if x.strip()],
        days=args.days,
        per_day=args.per_day,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
