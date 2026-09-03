from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Any, Callable

from kaggle_environments import make

from baselines.v1.counter_agent import CounterMeta, TournamentMind
from submission.hard_flow_agent import HardFlowMind
from submission.predictive_agent import PredictiveMind, normalize_observation_step


def _agent_for(mind):
    def agent(obs, configuration=None):
        normalize_observation_step(obs)
        return mind.act(obs)
    return agent


def _mean(values, default=-1.0):
    values = list(values)
    return statistics.mean(values) if values else default


def _money(last, player: int) -> float:
    for owner in (0, 1):
        try:
            obs = last[owner].observation
            farms = obs["farms"] if isinstance(obs, dict) else obs.farms
            farm = farms[player]
            return float(farm.get("money", 0) if isinstance(farm, dict) else farm.money)
        except Exception:
            pass
    try:
        return float(last[player].reward or 0)
    except Exception:
        return 0.0


def _run_game(candidate_cls, opponent_cls, seed: int, candidate_seat: int, candidate_name: str, opponent_name: str) -> dict[str, Any]:
    candidate = candidate_cls()
    opponent = opponent_cls()
    env = make("kaggriculture", configuration={"seed": int(seed)}, debug=False)
    candidate_agent = _agent_for(candidate)
    opponent_agent = _agent_for(opponent)
    agents = [candidate_agent, opponent_agent] if candidate_seat == 0 else [opponent_agent, candidate_agent]
    try:
        env.run(agents)
        last = env.steps[-1]
        statuses = [str(last[i].status) for i in (0, 1)]
        cash = _money(last, candidate_seat)
        opp_cash = _money(last, 1 - candidate_seat)
        row = {
            "candidate": candidate_name,
            "opponent": opponent_name,
            "seed": int(seed),
            "seat": int(candidate_seat),
            "ok": all(x == "DONE" for x in statuses),
            "statuses": statuses,
            "cash": cash,
            "opp_cash": opp_cash,
            "margin": cash - opp_cash,
            "score": 1.0 if cash > opp_cash else 0.5 if cash == opp_cash else 0.0,
        }
        if isinstance(candidate, HardFlowMind):
            row.update({
                "intervention_count": int(candidate.intervention_count),
                "intervention_units": int(candidate.intervention_units),
                "intervention_by_product": dict(candidate.intervention_by_product),
            })
        return row
    except BaseException as exc:
        return {
            "candidate": candidate_name,
            "opponent": opponent_name,
            "seed": int(seed),
            "seat": int(candidate_seat),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in rows if r.get("ok")]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in valid:
        grouped[(str(row["candidate"]), str(row["opponent"]))].append(row)

    table = []
    for (candidate, opponent), group in sorted(grouped.items()):
        table.append({
            "candidate": candidate,
            "opponent": opponent,
            "games": len(group),
            "score_rate": _mean(float(r["score"]) for r in group),
            "mean_margin": _mean(float(r["margin"]) for r in group),
            "median_margin": statistics.median(float(r["margin"]) for r in group) if group else -1.0,
            "seat0_score": _mean(float(r["score"]) for r in group if int(r["seat"]) == 0),
            "seat1_score": _mean(float(r["score"]) for r in group if int(r["seat"]) == 1),
        })

    paired = []
    for opponent in sorted({str(r["opponent"]) for r in valid}):
        v53 = {(int(r["seed"]), int(r["seat"])): r for r in valid if r["candidate"] == "V53" and r["opponent"] == opponent}
        base = {(int(r["seed"]), int(r["seat"])): r for r in valid if r["candidate"] == "BASE" and r["opponent"] == opponent}
        keys = sorted(set(v53) & set(base))
        if not keys:
            continue
        score_delta = [float(v53[k]["score"]) - float(base[k]["score"]) for k in keys]
        margin_delta = [float(v53[k]["margin"]) - float(base[k]["margin"]) for k in keys]
        paired.append({
            "opponent": opponent,
            "pairs": len(keys),
            "mean_score_delta": _mean(score_delta),
            "mean_margin_delta": _mean(margin_delta),
            "median_margin_delta": statistics.median(margin_delta),
        })

    all_pair_deltas = []
    all_margin_deltas = []
    for p in paired:
        opponent = p["opponent"]
        v53 = {(int(r["seed"]), int(r["seat"])): r for r in valid if r["candidate"] == "V53" and r["opponent"] == opponent}
        base = {(int(r["seed"]), int(r["seat"])): r for r in valid if r["candidate"] == "BASE" and r["opponent"] == opponent}
        for key in sorted(set(v53) & set(base)):
            all_pair_deltas.append(float(v53[key]["score"]) - float(base[key]["score"]))
            all_margin_deltas.append(float(v53[key]["margin"]) - float(base[key]["margin"]))

    v53_rows = [r for r in valid if r["candidate"] == "V53"]
    interventions = sum(int(r.get("intervention_count", 0)) for r in v53_rows)
    intervention_units = sum(int(r.get("intervention_units", 0)) for r in v53_rows)
    worst_family = min((float(p["mean_score_delta"]) for p in paired), default=-1.0)
    overall_score_delta = _mean(all_pair_deltas)
    overall_margin_delta = _mean(all_margin_deltas)
    all_valid = len(valid) == len(rows)
    preliminary_pass = bool(
        all_valid
        and interventions > 0
        and overall_score_delta >= 0.0
        and overall_margin_delta > 0.0
        and worst_family >= -0.125
    )
    return {
        "games": len(rows),
        "valid_games": len(valid),
        "invalid_games": len(rows) - len(valid),
        "all_valid": all_valid,
        "table": table,
        "paired": paired,
        "overall": {
            "paired_score_delta": overall_score_delta,
            "paired_margin_delta": overall_margin_delta,
            "worst_family_score_delta": worst_family,
            "interventions": interventions,
            "intervention_units": intervention_units,
        },
        "decision": "ADVANCE_TO_HOSTED_OR_LARGER_GATE" if preliminary_pass else "DO_NOT_PROMOTE_YET",
    }


def run(output: str | Path, seeds: list[int]) -> dict[str, Any]:
    opponents: list[tuple[str, Callable[[], Any]]] = [
        ("INCUMBENT", PredictiveMind),
        ("V1_TOURNAMENT", TournamentMind),
        ("V1_COUNTER", CounterMeta),
    ]
    candidates = [("V53", HardFlowMind), ("BASE", PredictiveMind)]
    rows: list[dict[str, Any]] = []
    for opponent_name, opponent_cls in opponents:
        for candidate_name, candidate_cls in candidates:
            for seed in seeds:
                for seat in (0, 1):
                    rows.append(_run_game(candidate_cls, opponent_cls, seed, seat, candidate_name, opponent_name))
    payload = {
        "experiment": "V53_HARD_FLOW_EXACT_ENGINE",
        "environment": "kaggle_environments kaggriculture",
        "seeds": list(seeds),
        "summary": _summary(rows),
        "rows": rows,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact-engine paired qualification for V53 hard-flow response")
    parser.add_argument("--output", default="tmp/v53/V53_QUALIFICATION.json")
    parser.add_argument("--seeds", default="5301,5311,5323,5333")
    args = parser.parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    result = run(args.output, seeds)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
