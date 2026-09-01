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
    ("screen", (301, 307), 5),
    ("replication", (401, 409, 419, 431), 3),
    ("heldout", (503, 509, 521, 541, 547, 557), 2),
    ("confirmation", (601, 607, 613, 617, 619, 631, 641, 647), 1),
)

# One-factor perturbations around the empirically selected public Moon parent.
# All replacements are exact and fail closed if the expected source token is absent.
VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("switches_3", "_MAX_SWITCHES=5", "_MAX_SWITCHES=3"),
    ("switches_4", "_MAX_SWITCHES=5", "_MAX_SWITCHES=4"),
    ("switches_6", "_MAX_SWITCHES=5", "_MAX_SWITCHES=6"),
    ("switches_7", "_MAX_SWITCHES=5", "_MAX_SWITCHES=7"),
    ("wool_price_150", "price>=180", "price>=150"),
    ("wool_price_165", "price>=180", "price>=165"),
    ("wool_price_195", "price>=180", "price>=195"),
    ("wool_price_210", "price>=180", "price>=210"),
    ("liquidate_620", "step>=680", "step>=620"),
    ("liquidate_650", "step>=680", "step>=650"),
    ("liquidate_710", "step>=680", "step>=710"),
    ("yarn_start_48", "72<=step<712", "48<=step<712"),
    ("yarn_start_96", "72<=step<712", "96<=step<712"),
    ("yarn_end_680", "72<=step<712", "72<=step<680"),
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _materialize_variants(moon_root: Path, output_root: Path) -> list[dict[str, Any]]:
    parent_source = (moon_root / "main.py").read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for name, before, after in VARIANTS:
        count = parent_source.count(before)
        if count != 1:
            rows.append({"name": name, "status": "rejected", "reason": f"expected one source token, found {count}"})
            continue
        root = output_root / name
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        for source in moon_root.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                target = root / source.relative_to(moon_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        main = root / "main.py"
        main.write_text(parent_source.replace(before, after, 1), encoding="utf-8")
        smoke = smoke_candidate(str(main), seed=277)
        rows.append(
            {
                "name": name,
                "status": "ready" if smoke["ok"] else "rejected",
                "mutation": {"before": before, "after": after},
                "root": str(root),
                "main_path": str(main),
                "source_sha256": _sha(main),
                "smoke": smoke,
            }
        )
    return rows


def _cash_key(evidence: dict[str, Any]) -> tuple[float, float, float, float]:
    meta = evidence.get("metadata", {})
    return (
        float(meta.get("paired_cash_relative_delta", float("-inf"))),
        float(meta.get("paired_cash_delta", float("-inf"))),
        float(meta.get("median_paired_cash_delta", float("-inf"))),
        float(meta.get("worst_family_cash_relative_delta", float("-inf"))),
    )


def _stage_survives(evidence: dict[str, Any], stage: str) -> bool:
    meta = evidence.get("metadata", {})
    if int(evidence.get("invalid_games", 1)) != 0:
        return False
    paired = float(meta.get("paired_cash_delta", float("-inf")))
    relative = float(meta.get("paired_cash_relative_delta", float("-inf")))
    worst_relative = float(meta.get("worst_family_cash_relative_delta", float("-inf")))
    passive = float(evidence.get("passive_cash_ratio", 0.0))
    if stage == "screen":
        return paired >= -1000.0 and relative >= -0.02 and passive >= 0.90
    if stage == "replication":
        return paired >= -250.0 and relative >= -0.005 and worst_relative >= -0.05 and passive >= 0.94
    if stage == "heldout":
        return paired >= 100.0 and relative >= 0.002 and worst_relative >= -0.03 and passive >= 0.97
    return (
        paired >= 100.0
        and float(meta.get("median_paired_cash_delta", float("-inf"))) >= 0.0
        and relative >= 0.002
        and float(meta.get("worst_family_cash_delta", float("-inf"))) >= -1500.0
        and worst_relative >= -0.03
        and passive >= 0.97
    )


def _package(root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tf:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                tf.add(path, arcname=path.relative_to(root).as_posix())


def run_ablation(*, output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    acquisition = acquire_frontier(
        output_root=root / "frontier",
        keys=["strict", "barnyard", "weedslip", "moon", "soil"],
    )
    resources = acquisition.get("resources", {})
    moon = resources.get("moon", {})
    if moon.get("status") != "ready":
        raise RuntimeError("Moon public parent did not acquire successfully")
    ready = [name for name in ("strict", "barnyard", "weedslip", "soil") if resources.get(name, {}).get("status") == "ready"]
    if len(ready) < 3:
        raise RuntimeError(f"insufficient public opponent coverage: {ready}")

    champion_root = Path(str(moon["agent_root"]))
    opponents = {name: str(resources[name]["agent_root"]) for name in ready}
    os.environ["SWARM_OPPONENTS_JSON"] = json.dumps(opponents, sort_keys=True)
    os.environ.setdefault("SWARM_EVAL_WORKERS", "4")

    variants = _materialize_variants(champion_root, root / "variants")
    active = [row for row in variants if row.get("status") == "ready"]
    stages: list[dict[str, Any]] = []
    for stage, seeds, keep in STAGES:
        evidence_rows: list[dict[str, Any]] = []
        for row in active:
            evidence = evaluate_candidate(
                candidate_path=str(row["main_path"]),
                champion_path=str(champion_root),
                seeds=list(seeds),
                both_seats=True,
                stage=f"moon_ablation_{stage}",
            )
            evidence_rows.append({"name": row["name"], "evidence": evidence, "survives": _stage_survives(evidence, stage)})
        evidence_rows.sort(key=lambda row: _cash_key(row["evidence"]), reverse=True)
        survivors = [row for row in evidence_rows if row["survives"]]
        selected_names = [row["name"] for row in survivors[:keep]]
        stages.append(
            {
                "stage": stage,
                "seeds": list(seeds),
                "evaluated": evidence_rows,
                "selected": selected_names,
            }
        )
        active = [row for row in active if row["name"] in selected_names]
        if not active:
            break

    result: dict[str, Any] = {
        "parent": "moon",
        "parent_source_sha256": _sha(champion_root / "main.py"),
        "opponents": ready,
        "acquisition_scope": acquisition.get("scope"),
        "variants": variants,
        "stages": stages,
        "decision": "HOLD",
    }
    if stages and stages[-1]["stage"] == "confirmation" and stages[-1]["selected"]:
        winner_name = stages[-1]["selected"][0]
        winner = next(row for row in variants if row["name"] == winner_name)
        final_row = next(row for row in stages[-1]["evaluated"] if row["name"] == winner_name)
        archive = root / "submission" / f"NEXT_SUBMIT_MOON_ABLATION_{winner_name}.tar.gz"
        _package(Path(str(winner["root"])), archive)
        result.update(
            {
                "decision": "PROMOTE",
                "winner": winner_name,
                "winner_evidence": final_row["evidence"],
                "archive": str(archive),
                "archive_sha256": _sha(archive),
            }
        )
    elif stages:
        result["reason"] = f"no variant survived through {stages[-1]['stage']}"
    else:
        result["reason"] = "no executable variants"

    (root / "MOON_ABLATION_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic cash-aligned Moon micro-ablation search")
    parser.add_argument("--output-root", default="swarm/runs/moon-ablation")
    args = parser.parse_args()
    result = run_ablation(output_root=args.output_root)
    print(json.dumps({k: result.get(k) for k in ("decision", "winner", "archive", "reason")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
