from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROL_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

_WORKER = r'''
from pathlib import Path
import importlib.util,json,sys,time
subject_path,opponent_path,repo_root,seed,seat=sys.argv[1],sys.argv[2],Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
sys.path[:0]=[str(repo_root),str(repo_root/'src')]
from kagv2.simulator import Game

def load(path,name):
 p=Path(path)
 if p.is_dir():p=p/'main.py'
 old=list(sys.path);sys.path.insert(0,str(p.parent))
 try:
  spec=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 finally:sys.path[:]=old
 f=getattr(m,'agent',None)
 if not callable(f):raise RuntimeError('no callable agent in '+str(p))
 return m,f

def call(f,obs):
 try:return f(obs)
 except TypeError:return f(obs,None)

def passive(obs,configuration=None):
 return {'farmer':['PASS'],'hands':[],'market':[]}

try:
 sm,S=load(subject_path,'subject')
 if opponent_path=='__PASSIVE__':O=passive
 else:_,O=load(opponent_path,'opponent')
 timings=[]
 def timed(obs,configuration=None):
  t=time.perf_counter()
  try:return call(S,obs)
  finally:timings.append(time.perf_counter()-t)
 agents=[timed,O] if seat==0 else [O,timed]
 money=Game(seed=seed).run(agents);sc,oc=(money[0],money[1]) if seat==0 else (money[1],money[0])
 stats=getattr(sm,'_V44_STATS',{}) or {};calls=max(1,int(stats.get('calls',0) or 0))
 physical=float(stats.get('physical_changed',0) or 0)/calls if stats else 1.0
 print(json.dumps({'ok':True,'cash':float(sc),'opp_cash':float(oc),'score':1.0 if sc>oc else .5 if sc==oc else 0.0,'margin':float(sc-oc),'mean_ms':1000*sum(timings)/max(1,len(timings)),'physical_change_rate':physical}))
except BaseException as exc:
 print(json.dumps({'ok':False,'error':repr(exc),'mean_ms':0.0,'physical_change_rate':1.0}))
'''


def _main_path(path: str | Path) -> str:
    p = Path(path)
    return str(p / "main.py" if p.is_dir() else p)


def _opponent_paths(champion_path: str) -> dict[str, str | None]:
    """Resolve optional family zoo from SWARM_OPPONENTS_JSON."""
    raw = os.environ.get("SWARM_OPPONENTS_JSON", "").strip()
    mapping: dict[str, str | None] = {"champion": _main_path(champion_path), "passive": None}
    if not raw:
        return mapping
    raw_path = Path(raw)
    payload = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("SWARM_OPPONENTS_JSON must resolve to a mapping")
    for name, path in payload.items():
        mapping[str(name)] = _main_path(str(path))
    return mapping


def _run_paths(subject_path: str, opponent_path: str | None, seed: int, seat: int) -> dict[str, Any]:
    opponent_arg = "__PASSIVE__" if opponent_path is None else opponent_path
    timeout_s = int(os.environ.get("SWARM_GAME_TIMEOUT_S", "180"))
    try:
        process = subprocess.run(
            [
                sys.executable,
                "-c",
                _WORKER,
                _main_path(subject_path),
                opponent_arg,
                str(_REPO_ROOT),
                str(seed),
                str(seat),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "mean_ms": 0.0, "physical_change_rate": 1.0}
    for line in reversed(process.stdout.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {
        "ok": False,
        "error": (process.stderr or process.stdout)[-2000:],
        "mean_ms": 0.0,
        "physical_change_rate": 1.0,
    }


def _family_rows(
    subject_path: str,
    opponents: dict[str, str | None],
    seeds: list[int],
    both_seats: bool,
) -> list[dict[str, Any]]:
    seats = (0, 1) if both_seats else (0,)
    jobs = [(family, opponent, seed, seat) for family, opponent in opponents.items() for seed in seeds for seat in seats]
    rows: list[dict[str, Any]] = []
    workers = max(1, int(os.environ.get("SWARM_EVAL_WORKERS", "4")))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run_paths, subject_path, opponent, seed, seat): (family, seed, seat)
            for family, opponent, seed, seat in jobs
        }
        for future in as_completed(futures):
            family, seed, seat = futures[future]
            rows.append({"family": family, "seed": seed, "seat": seat, **future.result()})
    return rows


def _control_rows(
    champion_path: str,
    opponents: dict[str, str | None],
    seeds: list[int],
    both_seats: bool,
) -> list[dict[str, Any]]:
    key = (
        _main_path(champion_path),
        tuple(sorted((name, path or "__PASSIVE__") for name, path in opponents.items())),
        tuple(seeds),
        both_seats,
    )
    if key not in _CONTROL_CACHE:
        _CONTROL_CACHE[key] = _family_rows(champion_path, opponents, seeds, both_seats)
    return _CONTROL_CACHE[key]


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
    opponents = _opponent_paths(champion_path)
    candidate_rows = _family_rows(candidate_path, opponents, seeds, both_seats)
    champion_rows = _control_rows(champion_path, opponents, seeds, both_seats)
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
    mean_family_deltas = {
        family: statistics.mean(values)
        for family, values in family_deltas.items()
        if family != "passive" and values
    }
    passive_candidate = [float(r["cash"]) for r in candidate_rows if r.get("ok") and r["family"] == "passive"]
    passive_champion = [float(r["cash"]) for r in champion_rows if r.get("ok") and r["family"] == "passive"]
    passive_ratio = (
        statistics.mean(passive_candidate) / statistics.mean(passive_champion)
        if passive_candidate and passive_champion and statistics.mean(passive_champion) != 0
        else 0.0
    )

    invalid_games = sum(1 for row in candidate_rows if not row.get("ok"))
    mean_ms_values = [float(row["mean_ms"]) for row in candidate_rows if row.get("ok")]
    physical_values = [float(row["physical_change_rate"]) for row in candidate_rows if row.get("ok")]
    physical_divergence = statistics.mean(physical_values) if physical_values else 1.0
    fingerprint = tuple(candidate_family_scores[name] for name in sorted(candidate_family_scores))
    worst_family_delta = min(mean_family_deltas.values(), default=-1.0)
    target_family = max(mean_family_deltas, key=mean_family_deltas.get) if mean_family_deltas else None
    target_family_gain = mean_family_deltas.get(target_family, -1.0) if target_family else -1.0
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
            "family_deltas": mean_family_deltas,
            "target_family": target_family,
            "target_family_gain": target_family_gain,
            "paired_games": len(paired_deltas),
            "game_count": len(candidate_rows),
        },
    }
