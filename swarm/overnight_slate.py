from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import tarfile
from typing import Any

from swarm.kaggle_intelligence import mirror_all
from swarm.v77_live_meta_route_search import (
    _hash_text,
    _obs_step,
    _physical,
    _run_game,
    _shops_from_state,
    recover_soil_parent,
    replay_agent_source,
    winner_traces,
)

H6_SHA = "39983a28017c66918827824e8e1e2cd842a06abcf7b4950e1e99f160b55d8575"
ROBUST_SHA = "5a049161a442648493e1d847615c2b9179654534ee6aae2a6a42c4d86c3d3fb7"
ROUTE_ARRAYS = {
    "10c4s_3q": "_ACTIONS_10C4S_3Q",
    "8c6s_3q": "_ACTIONS_8C6S_3Q",
    "6c8s_3q": "_ACTIONS_6C8S_3Q",
    "6c12s_4q_first_yarn": "_ACTIONS_6C12S_4Q_FIRST_YARN",
    "6c12s_4q_second_yarn": "_ACTIONS_6C12S_4Q_SECOND_YARN",
}


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _patch_exact(source: str, replacements: list[tuple[str, str]], expected_sha: str | None = None) -> str:
    out = source
    for old, new in replacements:
        count = out.count(old)
        if count != 1:
            raise RuntimeError(f"patch anchor {old!r} count={count}")
        out = out.replace(old, new, 1)
    compile(out, "<patched-candidate>", "exec")
    digest = _hash_text(out)
    if expected_sha and digest != expected_sha:
        raise RuntimeError(f"candidate SHA mismatch: expected {expected_sha}, got {digest}")
    return out


def known_market_variants(parent: str) -> dict[str, str]:
    h6 = _patch_exact(parent, [
        ("_PREEMPT_FRACTION = 1.0", "_PREEMPT_FRACTION = 2.0"),
        ("_PREEMPT_MAX_BATCH = 12", "_PREEMPT_MAX_BATCH = 30"),
        ("_PREEMPT_MIN_FUTURE_QUANTITY = 4", "_PREEMPT_MIN_FUTURE_QUANTITY = 3"),
        ("_PREEMPT_START = 120", "_PREEMPT_START = 96"),
        ("_ADAPT_MIN_EVIDENCE = 2.0", "_ADAPT_MIN_EVIDENCE = 1.0"),
    ], H6_SHA)
    robust = _patch_exact(parent, [
        ("_PREEMPT_FRACTION = 1.0", "_PREEMPT_FRACTION = 0.5"),
        ("_PREEMPT_MAX_BATCH = 12", "_PREEMPT_MAX_BATCH = 6"),
        ("_PREEMPT_MIN_PRICE_RATIO = 0.0", "_PREEMPT_MIN_PRICE_RATIO = 0.9"),
        ("_PREEMPT_MIN_FUTURE_QUANTITY = 4", "_PREEMPT_MIN_FUTURE_QUANTITY = 6"),
        ("_PREEMPT_START = 120", "_PREEMPT_START = 168"),
        ("_PREEMPT_STOP = 680", "_PREEMPT_STOP = 640"),
        ("_ADAPT_MIN_EVIDENCE = 2.0", "_ADAPT_MIN_EVIDENCE = 3.0"),
    ], ROBUST_SHA)
    return {"MARKET_H6_AGGRO": h6, "MARKET_ROBUST_CORE": robust}


def _load_module(source: str, root: Path, name: str):
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not build module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def route_experts(parent_source: str, root: Path) -> dict[str, list[dict[str, Any]]]:
    module = _load_module(parent_source, root, "soil_parent_experts")
    experts: dict[str, list[dict[str, Any]]] = {}
    for label, attr in ROUTE_ARRAYS.items():
        actions = getattr(module, attr, None)
        if not isinstance(actions, list) or len(actions) < 700:
            raise RuntimeError(f"missing/short route expert {attr}")
        experts[label] = actions
    return experts


def route_match_table(parent_source: str, traces: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    experts = route_experts(parent_source, root)
    rows: list[dict[str, Any]] = []
    for tid, tr in enumerate(traces):
        for level, low, high in ((1, 72, 144), (2, 144, 216), (3, 216, 720)):
            counts = {label: 0 for label in experts}
            eligible = 0
            prefix: tuple[str, ...] | None = None
            for state in tr["states"]:
                step = _obs_step(state)
                if step < low or step >= high or step >= 719:
                    continue
                act = state.get("action")
                if not isinstance(act, dict):
                    continue
                shops = _shops_from_state(state)
                if len(shops) < level:
                    continue
                prefix = tuple(shops[:level])
                target = _physical(act)
                eligible += 1
                for label, actions in experts.items():
                    if _physical(actions[step]) == target:
                        counts[label] += 1
            if eligible <= 0 or prefix is None:
                continue
            scores = {label: count / eligible for label, count in counts.items()}
            ordered = sorted(scores.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
            best_label, best_score = ordered[0]
            runner_score = ordered[1][1] if len(ordered) > 1 else 0.0
            rows.append({
                "trace": tid,
                "episode_id": tr["episode_id"],
                "date": tr["date"],
                "team": tr["team"],
                "level": level,
                "prefix": list(prefix),
                "n": eligible,
                "scores": scores,
                "best_route": best_label,
                "best_score": best_score,
                "confidence": best_score - runner_score,
                "avg_score": tr["avg_score"],
            })
    return rows


def _default_route(prefix: tuple[str, ...]) -> str:
    shops = list(prefix)
    if shops[:1] == ["YARN_STORE"]:
        return "6c12s_4q_first_yarn"
    if "YARN_STORE" in shops[:2]:
        if shops[:1] in (["BRUNCH_SPOT"], ["SMOOTHIE_SHOP"]):
            return "6c8s_3q"
        return "6c12s_4q_second_yarn"
    if "YARN_STORE" in shops[:3]:
        return "6c8s_3q"
    if {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.intersection(shops[:3]):
        return "10c4s_3q"
    return "8c6s_3q"


def learn_route_map(
    rows: list[dict[str, Any]],
    train_ids: set[int],
    *,
    min_count: int,
    min_advantage: float,
    min_match: float,
) -> dict[tuple[str, ...], str]:
    agg: dict[tuple[str, ...], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[tuple[str, ...], int] = defaultdict(int)
    for row in rows:
        if int(row["trace"]) not in train_ids:
            continue
        prefix = tuple(row["prefix"])
        weight = 1.0 + max(0.0, (float(row.get("avg_score", 0)) - 2500.0) / 1500.0)
        confidence = max(0.05, float(row.get("confidence", 0)))
        for route, score in row["scores"].items():
            agg[prefix][route] += weight * confidence * float(score)
        counts[prefix] += 1

    learned: dict[tuple[str, ...], str] = {}
    for prefix, route_scores in agg.items():
        if counts[prefix] < min_count:
            continue
        ordered = sorted(route_scores.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        best, best_value = ordered[0]
        second = ordered[1][1] if len(ordered) > 1 else 0.0
        total = sum(route_scores.values()) or 1.0
        normalized_best = best_value / total
        advantage = (best_value - second) / total
        if normalized_best < min_match or advantage < min_advantage:
            continue
        if best != _default_route(prefix):
            learned[prefix] = best
    return learned


def build_route_candidate(parent_source: str, route_map: dict[tuple[str, ...], str], label: str) -> str:
    start = parent_source.find("def _kawa_route_label(obs):")
    end = parent_source.find("\n\n_KAWA_LAYOUT_FALLBACK", start)
    if start < 0 or end < 0:
        raise RuntimeError("could not locate _kawa_route_label block")
    encoded = {"|".join(prefix): route for prefix, route in sorted(route_map.items())}
    replacement = f'''def _kawa_route_label(obs):
    # {label}: fresh winner traces choose among existing physical routes only.
    shops = list(((_get(obs, "town", {{}}) or {{}}).get("unlocked_shops", []) or []))
    learned = {encoded!r}
    for width in (3, 2, 1):
        if len(shops) >= width:
            route = learned.get("|".join(str(x) for x in shops[:width]))
            if route:
                return route
    if shops[:1] == ["YARN_STORE"]:
        return "6c12s_4q_first_yarn"
    if "YARN_STORE" in shops[:2]:
        if shops[:1] in (["BRUNCH_SPOT"], ["SMOOTHIE_SHOP"]):
            return "6c8s_3q"
        return "6c12s_4q_second_yarn"
    if "YARN_STORE" in shops[:3]:
        return "6c8s_3q"
    if _KAWA_MILK_SUPPORT.intersection(shops[:3]):
        return "10c4s_3q"
    return "8c6s_3q"
'''
    out = parent_source[:start] + replacement.rstrip() + parent_source[end:]
    compile(out, f"<{label}>", "exec")
    return out


def _patch_assignment(source: str, field: str, value: int | float) -> str:
    import re

    pattern = rf"(?m)^({re.escape(field)}\s*=\s*)([^#\n]+)"
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise RuntimeError(f"assignment anchor {field} count={len(matches)}")
    rendered = repr(value) if isinstance(value, float) else str(value)
    out = re.sub(pattern, lambda m: m.group(1) + rendered, source, count=1)
    compile(out, f"<council-{field}>", "exec")
    return out


def council_candidates(parent: str, proposal_file: str | Path | None) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if not proposal_file:
        return {}, []
    path = Path(proposal_file)
    if not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    accepted: list[dict[str, Any]] = []
    allowed_fields = {
        "_PREEMPT_FRACTION", "_PREEMPT_MAX_BATCH", "_PREEMPT_MIN_PRICE_RATIO",
        "_PREEMPT_MIN_FUTURE_QUANTITY", "_PREEMPT_START", "_PREEMPT_STOP", "_ADAPT_MIN_EVIDENCE",
    }
    allowed_routes = set(ROUTE_ARRAYS)
    for index, proposal in enumerate(payload.get("proposals", [])[:6], start=1):
        try:
            kind = proposal.get("mutation_type")
            if kind == "route":
                prefix = tuple(str(x) for x in proposal.get("prefix", []))
                route = str(proposal.get("route", ""))
                if not (1 <= len(prefix) <= 3) or route not in allowed_routes:
                    continue
                source = build_route_candidate(parent, {prefix: route}, f"COUNCIL_ROUTE_{index}")
                label = f"COUNCIL_ROUTE_{index}"
            elif kind == "parameter":
                field = str(proposal.get("field", ""))
                if field not in allowed_fields:
                    continue
                value = proposal.get("value")
                if not isinstance(value, (int, float)):
                    continue
                source = _patch_assignment(parent, field, value)
                label = f"COUNCIL_PARAM_{index}_{field.lstrip('_')}"
            else:
                continue
            out[label] = source
            accepted.append({**proposal, "candidate": label, "source_sha256": _hash_text(source)})
        except Exception as exc:
            accepted.append({**proposal, "status": "rejected", "error": f"{type(exc).__name__}: {exc}"[:500]})
    return out, accepted


def _materialize_sources(root: Path, candidates: dict[str, str], traces: list[dict[str, Any]]) -> tuple[dict[str, Path], dict[int, Path]]:
    candidate_paths: dict[str, Path] = {}
    replay_paths: dict[int, Path] = {}
    for name, source in candidates.items():
        d = root / "candidates" / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "main.py"
        p.write_text(source, encoding="utf-8")
        candidate_paths[name] = p
    for tid, tr in enumerate(traces):
        d = root / "replays" / str(tid)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "main.py"
        p.write_text(replay_agent_source(tr["action_map"]), encoding="utf-8")
        replay_paths[tid] = p
    return candidate_paths, replay_paths


def _summary(rows: list[dict[str, Any]], candidates: list[str], family_key: str = "family") -> list[dict[str, Any]]:
    result = []
    for name in candidates:
        mine = [r for r in rows if r["candidate"] == name]
        valid = [r for r in mine if r.get("ok")]
        scores = [float(r["score"]) for r in valid]
        margins = [float(r["margin"]) for r in valid]
        by_family: dict[str, list[float]] = defaultdict(list)
        for row in valid:
            by_family[str(row.get(family_key, "unknown"))].append(float(row["score"]))
        family_scores = {k: statistics.mean(v) for k, v in by_family.items() if v}
        k = max(1, int(math.ceil(0.2 * len(scores)))) if scores else 1
        result.append({
            "candidate": name,
            "games": len(mine),
            "valid": len(valid),
            "invalid": len(mine) - len(valid),
            "win_score": statistics.mean(scores) if scores else -1.0,
            "cvar20_score": statistics.mean(sorted(scores)[:k]) if scores else -1.0,
            "mean_margin": statistics.mean(margins) if margins else float("-inf"),
            "worst_family_score": min(family_scores.values(), default=-1.0),
            "family_scores": family_scores,
        })
    return result


def evaluate_replay_teachers(candidate_paths: dict[str, Path], replay_paths: dict[int, Path], traces: list[dict[str, Any]], ids: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows: list[dict[str, Any]] = []
    jobs = [(name, tid) for name in candidate_paths for tid in ids]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {
            ex.submit(_run_game, candidate_paths[name], replay_paths[tid], traces[tid]["seed"], traces[tid]["candidate_seat"]): (name, tid)
            for name, tid in jobs
        }
        for future in as_completed(futures):
            name, tid = futures[future]
            tr = traces[tid]
            rows.append({"candidate": name, "trace": tid, "family": f"replay:{tr['team']}", "episode_id": tr["episode_id"], **future.result()})
    return rows, _summary(rows, list(candidate_paths))


def acquire_public_opponents(root: Path, keys: tuple[str, ...] = ("strict", "barnyard", "weedslip", "moon", "soil")) -> dict[str, Path]:
    import kagglehub
    from swarm.frontier_acquire import PUBLIC_SPECS, _materialize_public_agent

    out: dict[str, Path] = {}
    for key in keys:
        spec = PUBLIC_SPECS[key]
        download = root / "downloads" / key
        agents = root / "agents" / key
        shutil.rmtree(download, ignore_errors=True)
        download.mkdir(parents=True, exist_ok=True)
        try:
            got = kagglehub.notebook_output_download(str(spec["handle"]), output_dir=str(download), force_download=True)
            downloaded = Path(got) if got else download
            agent_root, _, _ = _materialize_public_agent(key, downloaded, agents)
            out[f"public:{key}"] = agent_root / "main.py"
        except Exception:
            continue
    return out


def evaluate_static_league(candidate_paths: dict[str, Path], opponents: dict[str, Path], seeds: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows: list[dict[str, Any]] = []
    jobs = [(name, family, seed, seat) for name in candidate_paths for family in opponents for seed in seeds for seat in (0, 1)]
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_run_game, candidate_paths[name], opponents[family], seed, seat): (name, family, seed, seat)
            for name, family, seed, seat in jobs
        }
        for future in as_completed(futures):
            name, family, seed, seat = futures[future]
            rows.append({"candidate": name, "family": family, "seed": seed, "seat": seat, **future.result()})
    return rows, _summary(rows, list(candidate_paths))


def _pack(source: str, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = source.encode("utf-8")
    info = tarfile.TarInfo("main.py")
    info.size = len(data)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    with tarfile.open(path, "w:gz") as tf:
        tf.addfile(info, io.BytesIO(data))
    with tarfile.open(path, "r:gz") as tf:
        extracted = tf.extractfile(tf.getmember("main.py")).read().decode("utf-8")
    compile(extracted, "<packed-main>", "exec")
    if extracted != source:
        raise RuntimeError("archive source mismatch")
    return {
        "path": str(path),
        "archive_sha256": sha256(path.read_bytes()).hexdigest(),
        "source_sha256": _hash_text(source),
        "bytes": path.stat().st_size,
    }


def _load_public_episodes(public_meta_path: Path) -> list[dict[str, Any]]:
    meta = json.loads(public_meta_path.read_text(encoding="utf-8"))
    episodes: list[dict[str, Any]] = []
    for day in meta.get("days", []):
        for row in day.get("episodes", []):
            path = row.get("path")
            if not path or not row.get("sha256"):
                continue
            p = Path(path)
            if not p.exists():
                continue
            rep = json.loads(p.read_text(encoding="utf-8"))
            rep["_meta_date"] = day.get("date")
            rep["_meta_avg_score"] = row.get("avg_score", 0)
            episodes.append(rep)
    return episodes


def _load_authenticated_loss_episodes(auth_meta_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not auth_meta_path.exists():
        return [], {"available": False, "reason": "AUTH_META missing"}
    auth = json.loads(auth_meta_path.read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    team_counts: dict[str, int] = defaultdict(int)
    seen_files: set[str] = set()
    for submission in auth.get("submissions", []):
        for replay in submission.get("replays", []) or []:
            file_rows = list(replay.get("files", []) or [])
            cached_root = replay.get("path")
            if cached_root:
                file_rows.extend({"path": str(p)} for p in Path(cached_root).rglob("*.json"))
            for file_row in file_rows:
                path = str(file_row.get("path", ""))
                if not path.endswith(".json") or path in seen_files:
                    continue
                seen_files.add(path)
                p = Path(path)
                if not p.exists():
                    continue
                try:
                    rep = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(rep, dict) or not rep.get("steps"):
                    continue
                names = list((rep.get("info") or {}).get("TeamNames") or [])
                if len(names) < 2:
                    continue
                for name in names[:2]:
                    team_counts[str(name)] += 1
                candidates.append(rep)
    if not candidates or not team_counts:
        return [], {"available": bool(auth.get("available")), "replay_count": 0}
    own_team = max(team_counts.items(), key=lambda kv: kv[1])[0]
    losses: list[dict[str, Any]] = []
    for rep in candidates:
        names = list((rep.get("info") or {}).get("TeamNames") or ["p0", "p1"])
        steps = rep.get("steps") or []
        try:
            rewards = rep.get("rewards")
            if not isinstance(rewards, list) or len(rewards) < 2:
                rewards = [steps[-1][0].get("reward"), steps[-1][1].get("reward")]
            vals = [float(rewards[0] or 0), float(rewards[1] or 0)]
        except Exception:
            continue
        winner = 0 if vals[0] >= vals[1] else 1
        if own_team not in names or str(names[winner]) == own_team:
            continue
        rep["_meta_date"] = "OWN_RATED_LOSS"
        rep["_meta_avg_score"] = 4200.0
        losses.append(rep)
    return losses, {
        "available": bool(auth.get("available")),
        "inferred_own_team": own_team,
        "all_replays": len(candidates),
        "loss_teacher_count": len(losses),
        "team_counts": team_counts,
    }


def run(
    output_root: str | Path,
    *,
    days: int = 3,
    top_per_day: int = 8,
    diverse_per_day: int = 4,
    max_parent_version: int = 40,
    mirror_root: str | Path | None = None,
    proposal_file: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    if mirror_root and (Path(mirror_root) / "MIRROR_MANIFEST.json").exists():
        mirror = json.loads((Path(mirror_root) / "MIRROR_MANIFEST.json").read_text(encoding="utf-8"))
    else:
        mirror = mirror_all(
            root / "mirror",
            days=days,
            top_per_day=top_per_day,
            diverse_per_day=diverse_per_day,
            refresh_manifests=True,
            include_authenticated=True,
        )
    parent, parent_info = recover_soil_parent(root / "parent_recovery", max_version=max_parent_version)
    candidates: dict[str, str] = {"BASE_PARENT": parent, **known_market_variants(parent)}
    council_built, council_accepted = council_candidates(parent, proposal_file)
    candidates.update(council_built)

    episodes = _load_public_episodes(Path(mirror["public"]["path"]))
    live_loss_episodes, live_loss_info = _load_authenticated_loss_episodes(Path(mirror["authenticated"]["path"]))
    episodes.extend(live_loss_episodes)
    traces = winner_traces(episodes)
    teams = sorted({tr["team"] for tr in traces})
    holdout_teams = {team for i, team in enumerate(teams) if i % 3 == 0}
    heldout = [i for i, tr in enumerate(traces) if tr["team"] in holdout_teams]
    train = [i for i in range(len(traces)) if i not in heldout]
    if len(heldout) < 3:
        split = max(1, len(traces) * 2 // 3)
        train, heldout = list(range(split)), list(range(split, len(traces)))

    route_rows = route_match_table(parent, traces, root / "route_probe")
    settings = [
        ("ROUTE_LOOSE", 1, 0.01, 0.16),
        ("ROUTE_MED", 2, 0.025, 0.18),
        ("ROUTE_STRICT", 2, 0.05, 0.20),
    ]
    learned_maps: dict[str, dict[str, str]] = {}
    for label, min_count, advantage, min_match in settings:
        learned = learn_route_map(
            route_rows,
            set(train),
            min_count=min_count,
            min_advantage=advantage,
            min_match=min_match,
        )
        learned_maps[label] = {"|".join(k): v for k, v in learned.items()}
        candidates[label] = build_route_candidate(parent, learned, label)
    if learned_maps.get("ROUTE_MED"):
        med_map = {tuple(k.split("|")): v for k, v in learned_maps["ROUTE_MED"].items()}
        candidates["ROUTE_MED_H6"] = build_route_candidate(candidates["MARKET_H6_AGGRO"], med_map, "ROUTE_MED_H6")
        candidates["ROUTE_MED_ROBUST"] = build_route_candidate(candidates["MARKET_ROBUST_CORE"], med_map, "ROUTE_MED_ROBUST")

    candidate_paths, replay_paths = _materialize_sources(root / "arena", candidates, traces)
    _, replay_summary = evaluate_replay_teachers(candidate_paths, replay_paths, traces, heldout)

    public_opponents = acquire_public_opponents(root / "public_frontier")
    static_opponents = {
        "internal:base": candidate_paths["BASE_PARENT"],
        "internal:h6": candidate_paths["MARKET_H6_AGGRO"],
        "internal:robust": candidate_paths["MARKET_ROBUST_CORE"],
        **public_opponents,
    }
    _, static_summary = evaluate_static_league(candidate_paths, static_opponents, [3301, 3313, 3331])

    replay_by = {r["candidate"]: r for r in replay_summary}
    static_by = {r["candidate"]: r for r in static_summary}
    base_replay = replay_by["BASE_PARENT"]
    base_static = static_by["BASE_PARENT"]
    base_composite = (
        0.20 * base_replay["win_score"]
        + 0.65 * base_static["win_score"]
        + 0.15 * base_static["worst_family_score"]
    )
    ranking = []
    for name in candidates:
        rr = replay_by[name]
        sr = static_by[name]
        composite = 0.20 * rr["win_score"] + 0.65 * sr["win_score"] + 0.15 * sr["worst_family_score"]
        family = (
            "baseline" if name == "BASE_PARENT"
            else "market" if name.startswith("MARKET")
            else "council" if name.startswith("COUNCIL")
            else "hybrid" if "_H6" in name or "_ROBUST" in name
            else "route"
        )
        row = {
            "candidate": name,
            "family": family,
            "source_sha256": _hash_text(candidates[name]),
            "replay_win_score": rr["win_score"],
            "replay_delta_vs_base": rr["win_score"] - base_replay["win_score"],
            "static_win_score": sr["win_score"],
            "static_delta_vs_base": sr["win_score"] - base_static["win_score"],
            "worst_static_family_score": sr["worst_family_score"],
            "invalid_games": rr["invalid"] + sr["invalid"],
            "composite": composite,
            "delta_composite_vs_base": composite - base_composite,
        }
        row["recommendation"] = (
            "PROMOTE"
            if row["invalid_games"] == 0
            and row["delta_composite_vs_base"] >= 0.03
            and row["static_delta_vs_base"] >= -0.03
            and row["replay_delta_vs_base"] >= -0.08
            else "PROBE"
            if row["invalid_games"] == 0 and row["delta_composite_vs_base"] >= -0.03
            else "HOLD"
        )
        ranking.append(row)
    ranking.sort(
        key=lambda r: (
            r["recommendation"] == "PROMOTE",
            r["composite"],
            r["worst_static_family_score"],
        ),
        reverse=True,
    )

    slate = []
    family_counts: dict[str, int] = defaultdict(int)
    for row in ranking:
        if row["recommendation"] == "HOLD":
            continue
        if family_counts[row["family"]] >= 2:
            continue
        slate.append(row)
        family_counts[row["family"]] += 1
        if len(slate) >= 5:
            break
    if not any(row["candidate"] == "BASE_PARENT" for row in slate):
        base_row = next(row for row in ranking if row["candidate"] == "BASE_PARENT")
        if len(slate) >= 5:
            slate[-1] = base_row
        else:
            slate.append(base_row)

    packages = []
    for slot, row in enumerate(slate, start=1):
        package = _pack(candidates[row["candidate"]], root / "submissions" / f"P{slot}_{row['candidate']}.tar.gz")
        packages.append({"slot": slot, **row, **package})

    result = {
        "decision": "PROMOTE" if any(r["recommendation"] == "PROMOTE" for r in slate) else "PROBE_ONLY",
        "parent": parent_info,
        "mirror": mirror,
        "live_loss_teachers": live_loss_info,
        "train_trace_count": len(train),
        "heldout_trace_count": len(heldout),
        "heldout_teams": sorted(holdout_teams),
        "learned_maps": learned_maps,
        "council_candidates": council_accepted,
        "route_match_rows": route_rows,
        "replay_summary": replay_summary,
        "static_opponents": sorted(static_opponents),
        "static_summary": static_summary,
        "ranking": ranking,
        "slate": packages,
    }
    _atomic_json(root / "TOMORROW_SLATE.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Kaggriculture overnight meta mirror + diversified submission slate")
    ap.add_argument("--output-root", default="artifacts/overnight")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--top-per-day", type=int, default=8)
    ap.add_argument("--diverse-per-day", type=int, default=4)
    ap.add_argument("--max-parent-version", type=int, default=40)
    ap.add_argument("--mirror-root", default=None, help="Reuse an existing mirror directory instead of downloading again")
    ap.add_argument("--proposal-file", default=None, help="Bounded council proposal JSON to compile into candidates")
    args = ap.parse_args()
    result = run(
        args.output_root,
        days=args.days,
        top_per_day=args.top_per_day,
        diverse_per_day=args.diverse_per_day,
        max_parent_version=args.max_parent_version,
        mirror_root=args.mirror_root,
        proposal_file=args.proposal_file,
    )
    print(json.dumps({"decision": result["decision"], "slate": result["slate"], "parent": result["parent"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
