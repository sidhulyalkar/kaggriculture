from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable

from kagv2.simulator import Game


def _load_agent(path: str | Path, module_name: str) -> tuple[Any, Callable[..., Any]]:
    path = Path(path)
    if path.is_dir():
        path = path / "main.py"
    if not path.exists():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    old_path = list(sys.path)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_path
    agent = getattr(module, "agent", None)
    if not callable(agent):
        raise RuntimeError(f"{path} does not expose callable agent")
    return module, agent


def _call(agent: Callable[..., Any], obs: Any) -> Any:
    try:
        return agent(obs)
    except TypeError:
        return agent(obs, None)


def _passive(obs: Any, configuration: Any = None) -> dict[str, Any]:
    del obs, configuration
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _opponent_paths(champion_path: str) -> dict[str, str | None]:
    """Resolve an optional family zoo from SWARM_OPPONENTS_JSON.

    JSON may be either a mapping of family name -> main.py/directory or a path to a JSON file.
    Champion and passive controls are always included.
    """
    raw = os.environ.get("SWARM_OPPONENTS_JSON", "").strip()
    mapping: dict[str, str | None] = {"champion": champion_path, "passive": None}
    if not raw:
        return mapping
    payload = json.loads(Path(raw).read_text(encoding="utf-8")) if Path(raw).exists() else json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("SWARM_OPPONENTS_JSON must resolve to a mapping")
    for name, path in payload.items():
        mapping[str(name)] = str(path)
    return mapping


def _run(agent_a: Callable[..., Any], agent_b: Callable[..., Any], seed: int, seat: int) -> dict[str, Any]:
    timings: list[float] = []

    def timed(obs: Any, configuration: Any = None) -> Any:
        del configuration
        start = time.perf_counter()
        try:
            return _call(agent_a, obs)
        finally:
            timings.append(time.perf_counter() - start)

    agents = [timed, agent_b] if seat == 0 else [agent_b, timed]
    try:
        money = Game(seed=seed).run(agents)
        a_cash, b_cash = (money[0], money[1]) if seat == 0 else (money[1], money[0])
        return {
            "ok": True,
            "cash": float(a_cash),
            "opp_cash": float(b_cash),
            "score": 1.0 if a_cash > b_cash else 0.5 if a_cash == b_cash else 0.0,
            "margin": float(a_cash - b_cash),
            "mean_ms": 1000.0 * sum(timings) / max(1, len(timings)),
        }
    except BaseException as exc:
        return {"ok": False, "error": repr(exc), "mean_ms": 0.0}


def _family_rows(agent: Callable[..., Any], opponents: dict[str, Callable[..., Any]], seeds: list[int], both_seats: bool):
    rows: list[dict[str, Any]] = []
    seats = (0, 1) if both_seats else (0,)
    for family, opponent in opponents.items():
        for seed in seeds:
            for seat in seats:
                rows.append({"family": family, "seed": seed, "seat": seat, **_run(agent, opponent, seed, seat)})
    return rows


def _score_by_family(rows: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("ok"):
            grouped[str(row["family"])].append(float(row["score"]))
    return {family: statistics.mean(scores) for family, scores in grouped.items() if scores}


def evaluate_candidate(
    *,
    candidate_path: str,
    champion_path: str,
    seeds: list[int],
    both_seats: bool,
    stage: str,
) -> dict[str, Any]:
    candidate_module, candidate = _load_agent(candidate_path, f"swarm_candidate_{abs(hash(candidate_path))}")
    _champion_module, champion = _load_agent(champion_path, f"swarm_champion_{abs(hash(champion_path))}")

    opponent_specs = _opponent_paths(champion_path)
    opponents: dict[str, Callable[..., Any]] = {}
    for name, path in opponent_specs.items():
        if name == "passive":
            opponents[name] = _passive
        elif path is not None:
            _module, opponent = _load_agent(path, f"swarm_opp_{name}_{abs(hash(path))}")
            opponents[name] = opponent

    candidate_rows = _family_rows(candidate, opponents, seeds, both_seats)
    champion_rows = _family_rows(champion, opponents, seeds, both_seats)
    champion_key = {(r["family"], r["seed"], r["seat"]): r for r in champion_rows if r.get("ok")}

    paired_deltas: list[float] = []
    family_deltas: dict[str, list[float]] = defaultdict(list)
    for row in candidate_rows:
        if not row.get("ok"):
            continue
        control = champion_key.get((row["family"], row["seed"], row["seat"]))
        if not control:
            continue
        delta = float(row["score"]) - float(control["score"])
        paired_deltas.append(delta)
        family_deltas[str(row["family"])].append(delta)

    competitive_candidate = [r for r in candidate_rows if r.get("ok") and r["family"] != "passive"]
    candidate_family_scores = _score_by_family(competitive_candidate)
    passive_candidate = [float(r["cash"]) for r in candidate_rows if r.get("ok") and r["family"] == "passive"]
    passive_champion = [float(r["cash"]) for r in champion_rows if r.get("ok") and r["family"] == "passive"]
    passive_ratio = (
        statistics.mean(passive_candidate) / statistics.mean(passive_champion)
        if passive_candidate and passive_champion and statistics.mean(passive_champion) != 0
        else 0.0
    )

    stats = getattr(candidate_module, "_V44_STATS", {}) or {}
    calls = max(1, int(stats.get("calls", 0) or 0))
    physical_divergence = float(stats.get("physical_changed", 0) or 0) / calls if stats else 1.0
    invalid_games = sum(1 for row in candidate_rows if not row.get("ok"))
    mean_ms_values = [float(row["mean_ms"]) for row in candidate_rows if row.get("ok")]

    fingerprint = tuple(candidate_family_scores[name] for name in sorted(candidate_family_scores))
    worst_family_delta = min(
        (statistics.mean(values) for family, values in family_deltas.items() if family != "passive" and values),
        default=-1.0,
    )
    mean_score = statistics.mean(float(r["score"]) for r in competitive_candidate) if competitive_candidate else 0.0

    return {
        "evaluation_id": f"{Path(candidate_path).parent.name}-{stage}",
        "mean_score": mean_score,
        "paired_score_delta": statistics.mean(paired_deltas) if paired_deltas else -1.0,
        "worst_family_delta": worst_family_delta,
        "passive_cash_ratio": passive_ratio,
        "invalid_games": invalid_games,
        "mean_call_ms": statistics.mean(mean_ms_values) if mean_ms_values else float("inf"),
        "physical_divergence": physical_divergence,
        "behavioral_fingerprint": list(fingerprint),
        "metadata": {
            "stage": stage,
            "families": sorted(opponents),
            "family_scores": candidate_family_scores,
            "paired_games": len(paired_deltas),
            "game_count": len(candidate_rows),
        },
    }
