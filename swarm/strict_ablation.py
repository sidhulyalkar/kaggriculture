from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tarfile
from typing import Any

from .frontier_acquire import acquire_frontier
from .kaggriculture_evaluator import evaluate_candidate, smoke_candidate


STAGES: tuple[tuple[str, tuple[int, ...], int], ...] = (
    ("screen", (313, 317), 6),
    ("replication", (421, 431, 433, 439), 3),
    ("heldout", (521, 523, 541, 547, 563, 569), 2),
    ("confirmation", (653, 659, 661, 673, 677, 683, 691, 701), 1),
)

VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("demand_alpha_0", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.0"),
    ("demand_alpha_010", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.10"),
    ("demand_alpha_015", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.15"),
    ("demand_alpha_020", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.20"),
    ("demand_alpha_030", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.30"),
    ("demand_alpha_040", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.40"),
    ("demand_alpha_050", "_DEMAND_ALPHA = 0.25", "_DEMAND_ALPHA = 0.50"),
    ("weed_replay_4", "_WEED_REPLAY_STEPS = 8", "_WEED_REPLAY_STEPS = 4"),
    ("weed_replay_6", "_WEED_REPLAY_STEPS = 8", "_WEED_REPLAY_STEPS = 6"),
    ("weed_replay_10", "_WEED_REPLAY_STEPS = 8", "_WEED_REPLAY_STEPS = 10"),
    ("weed_replay_12", "_WEED_REPLAY_STEPS = 8", "_WEED_REPLAY_STEPS = 12"),
    ("urgency_days_6", ") / 10.0)", ") / 6.0)"),
    ("urgency_days_8", ") / 10.0)", ") / 8.0)"),
    ("urgency_days_12", ") / 10.0)", ") / 12.0)"),
    ("urgency_days_15", ") / 10.0)", ") / 15.0)"),
    ("regime_threshold_20", "interval >= 24", "interval >= 20"),
    ("regime_threshold_28", "interval >= 24", "interval >= 28"),
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _materialize(parent_root: Path, output_root: Path) -> list[dict[str, Any]]:
    source = (parent_root / "main.py").read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for name, before, after in VARIANTS:
        count = source.count(before)
        if count != 1:
            rows.append({"name": name, "status": "rejected", "reason": f"expected one source token, found {count}"})
            continue
        root = output_root / name
        shutil.rmtree(root, ignore_errors=True); root.mkdir(parents=True, exist_ok=True)
        for src in parent_root.rglob("*"):
            if src.is_file() and "__pycache__" not in src.parts and src.suffix != ".pyc":
                dst = root / src.relative_to(parent_root); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        main = root / "main.py"; main.write_text(source.replace(before, after, 1), encoding="utf-8")
        smoke = smoke_candidate(str(main), seed=293)
        rows.append({
            "name": name,
            "status": "ready" if smoke["ok"] else "rejected",
            "mutation": {"before": before, "after": after},
            "root": str(root), "main_path": str(main), "source_sha256": _sha(main), "smoke": smoke,
        })
    return rows


def _cash_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    meta = row.get("metadata", {})
    return (
        float(meta.get("paired_cash_relative_delta", float("-inf"))),
        float(meta.get("paired_cash_delta", float("-inf"))),
        float(meta.get("median_paired_cash_delta", float("-inf"))),
        float(meta.get("worst_family_cash_relative_delta", float("-inf"))),
    )


def _survives(evidence: dict[str, Any], stage: str) -> bool:
    meta = evidence.get("metadata", {})
    if int(evidence.get("invalid_games", 1)) != 0: return False
    paired = float(meta.get("paired_cash_delta", float("-inf")))
    relative = float(meta.get("paired_cash_relative_delta", float("-inf")))
    worst_rel = float(meta.get("worst_family_cash_relative_delta", float("-inf")))
    passive = float(evidence.get("passive_cash_ratio", 0.0))
    if stage == "screen": return paired >= -1000.0 and relative >= -0.02 and passive >= 0.95
    if stage == "replication": return paired >= -250.0 and relative >= -0.005 and worst_rel >= -0.05 and passive >= 0.97
    if stage == "heldout": return paired >= 100.0 and relative >= 0.002 and worst_rel >= -0.03 and passive >= 0.98
    return (
        paired >= 100.0
        and float(meta.get("median_paired_cash_delta", float("-inf"))) >= 0.0
        and relative >= 0.002
        and float(meta.get("worst_family_cash_delta", float("-inf"))) >= -1500.0
        and worst_rel >= -0.03
        and passive >= 0.98
    )


def _package(root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tf:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                tf.add(path, arcname=path.relative_to(root).as_posix())


def run_ablation(*, output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve(); root.mkdir(parents=True, exist_ok=True)
    acquisition = acquire_frontier(output_root=root / "frontier", keys=["strict", "barnyard", "weedslip", "moon", "soil"])
    resources = acquisition.get("resources", {}); parent = resources.get("strict", {})
    if parent.get("status") != "ready": raise RuntimeError("Strict-Future public parent did not acquire successfully")
    ready = [name for name in ("barnyard", "weedslip", "moon", "soil") if resources.get(name, {}).get("status") == "ready"]
    if len(ready) < 3: raise RuntimeError(f"insufficient public opponent coverage: {ready}")
    parent_root = Path(str(parent["agent_root"])); opponents = {name: str(resources[name]["agent_root"]) for name in ready}
    os.environ["SWARM_OPPONENTS_JSON"] = json.dumps(opponents, sort_keys=True); os.environ.setdefault("SWARM_EVAL_WORKERS", "4")

    variants = _materialize(parent_root, root / "variants"); active = [row for row in variants if row.get("status") == "ready"]
    stages: list[dict[str, Any]] = []
    for stage, seeds, keep in STAGES:
        evaluated: list[dict[str, Any]] = []
        for row in active:
            evidence = evaluate_candidate(candidate_path=str(row["main_path"]), champion_path=str(parent_root), seeds=list(seeds), both_seats=True, stage=f"strict_ablation_{stage}")
            evaluated.append({"name": row["name"], "evidence": evidence, "survives": _survives(evidence, stage)})
        evaluated.sort(key=lambda row: _cash_key(row["evidence"]), reverse=True)
        selected = [row["name"] for row in evaluated if row["survives"]][:keep]
        stages.append({"stage": stage, "seeds": list(seeds), "evaluated": evaluated, "selected": selected})
        active = [row for row in active if row["name"] in selected]
        if not active: break

    result: dict[str, Any] = {
        "parent": "strict", "published_parent_score": 3090.1,
        "parent_source_sha256": _sha(parent_root / "main.py"), "opponents": ready,
        "acquisition_scope": acquisition.get("scope"), "variants": variants, "stages": stages, "decision": "HOLD",
    }
    if stages and stages[-1]["stage"] == "confirmation" and stages[-1]["selected"]:
        winner_name = stages[-1]["selected"][0]; winner = next(row for row in variants if row["name"] == winner_name)
        final_row = next(row for row in stages[-1]["evaluated"] if row["name"] == winner_name)
        archive = root / "submission" / f"NEXT_SUBMIT_STRICT_ABLATION_{winner_name}.tar.gz"; _package(Path(str(winner["root"])), archive)
        result.update({"decision": "PROMOTE", "winner": winner_name, "winner_evidence": final_row["evidence"], "archive": str(archive), "archive_sha256": _sha(archive)})
    elif stages: result["reason"] = f"no variant survived through {stages[-1]['stage']}"
    else: result["reason"] = "no executable variants"
    (root / "STRICT_ABLATION_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic cash-aligned Strict-Future micro-ablation search")
    parser.add_argument("--output-root", default="swarm/runs/strict-ablation"); args = parser.parse_args()
    result = run_ablation(output_root=args.output_root)
    print(json.dumps({k: result.get(k) for k in ("decision", "winner", "archive", "reason")}, indent=2, sort_keys=True))


if __name__ == "__main__": main()
