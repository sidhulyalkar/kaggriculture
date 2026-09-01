from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

from .config_loader import load_config
from .kaggriculture_evaluator import evaluate_candidate, smoke_candidate
from .models import EvaluationRecord
from .promotion import promotion_decision


CONFIRMATION_SEEDS = (70001, 70009, 70019, 70039, 70051, 70061, 70079, 70099)


def _evaluation_record(row: dict[str, Any], *, candidate_id: str) -> EvaluationRecord:
    return EvaluationRecord(
        evaluation_id=str(row.get("evaluation_id", f"{candidate_id}-confirmation")),
        candidate_id=candidate_id,
        stage="confirmation",
        mean_score=float(row["mean_score"]),
        paired_score_delta=float(row["paired_score_delta"]),
        worst_family_delta=float(row["worst_family_delta"]),
        passive_cash_ratio=float(row["passive_cash_ratio"]),
        invalid_games=int(row["invalid_games"]),
        mean_call_ms=float(row["mean_call_ms"]),
        physical_divergence=float(row["physical_divergence"]),
        behavioral_fingerprint=tuple(float(x) for x in row.get("behavioral_fingerprint", ())),
        metadata=dict(row.get("metadata", {})),
    )


def _promoted_candidates(campaign_root: Path) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    for epoch in sorted((campaign_root / "epochs").glob("epoch-*")):
        evaluation_path = epoch / "EPOCH_EVALUATION.json"
        candidates_path = epoch / "CANDIDATES_READY.json"
        if not evaluation_path.exists() or not candidates_path.exists():
            continue
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        candidates = {
            str(row["candidate_id"]): row
            for row in json.loads(candidates_path.read_text(encoding="utf-8"))
        }
        heldout = {str(row["candidate_id"]): row for row in evaluation.get("heldout", [])}
        for decision in evaluation.get("decisions", []):
            if not bool(decision.get("promote")):
                continue
            candidate_id = str(decision["candidate_id"])
            candidate = candidates.get(candidate_id)
            evidence = heldout.get(candidate_id)
            if not candidate or not evidence:
                continue
            promoted.append(
                {
                    "candidate_id": candidate_id,
                    "epoch": str(epoch),
                    "candidate": candidate,
                    "heldout": evidence,
                    "promotion_score": float(decision.get("score", 0.0)),
                }
            )
    promoted.sort(
        key=lambda row: (
            row["promotion_score"],
            float(row["heldout"].get("paired_score_delta", -1.0)),
            float(row["heldout"].get("worst_family_delta", -1.0)),
            float(row["heldout"].get("mean_score", -1.0)),
        ),
        reverse=True,
    )
    return promoted


def _package_tree(candidate_root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tf:
        for path in sorted(candidate_root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            tf.add(path, arcname=path.relative_to(candidate_root).as_posix())


def _verify_archive(archive: Path) -> dict[str, Any]:
    check = subprocess.run(
        [sys.executable, "scripts/check_submission.py", str(archive)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    result: dict[str, Any] = {
        "check_submission_returncode": check.returncode,
        "check_submission_stdout": check.stdout[-4000:],
        "check_submission_stderr": check.stderr[-4000:],
    }
    if check.returncode != 0:
        result["ok"] = False
        return result
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(td)
        smoke = smoke_candidate(str(Path(td) / "main.py"), seed=70123)
    result["post_pack_smoke"] = smoke
    result["ok"] = bool(smoke["ok"])
    return result


def qualify_campaign(
    *,
    campaign_root: str | Path,
    config_path: str,
    champion_path: str,
    output_root: str | Path,
    frontier_scope: str,
    max_confirmation_candidates: int = 3,
) -> dict[str, Any]:
    campaign = Path(campaign_root)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    thresholds = config["experiments"]["promotion"]
    promoted = _promoted_candidates(campaign)
    result: dict[str, Any] = {
        "frontier_scope": frontier_scope,
        "confirmation_seeds_hash_only": True,
        "confirmation_seed_count": len(CONFIRMATION_SEEDS),
        "promoted_from_heldout": len(promoted),
        "confirmation": [],
        "decision": "HOLD",
        "reason": "no heldout-promoted candidate",
    }
    if not promoted:
        (output / "SUBMISSION_DECISION.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return result

    qualified: list[dict[str, Any]] = []
    for candidate_row in promoted[: max(1, int(max_confirmation_candidates))]:
        candidate_id = candidate_row["candidate_id"]
        candidate = candidate_row["candidate"]
        source_path = Path(str(candidate["source_path"]))
        lane = str(candidate.get("lane", ""))
        raw = evaluate_candidate(
            candidate_path=str(source_path),
            champion_path=champion_path,
            seeds=list(CONFIRMATION_SEEDS),
            both_seats=True,
            stage="confirmation",
        )
        record = _evaluation_record(raw, candidate_id=candidate_id)
        decision = promotion_decision(record, thresholds, lane=lane)
        row = {
            "candidate_id": candidate_id,
            "lane": lane,
            "heldout": candidate_row["heldout"],
            "confirmation": raw,
            "confirmation_decision": decision.to_dict(),
        }
        result["confirmation"].append(row)
        if decision.promote:
            qualified.append(row)

    if not qualified:
        result["reason"] = "no candidate replicated through sealed confirmation"
        (output / "SUBMISSION_DECISION.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return result

    qualified.sort(
        key=lambda row: (
            float(row["confirmation_decision"]["score"]),
            float(row["confirmation"].get("paired_score_delta", -1.0)),
            float(row["confirmation"].get("worst_family_delta", -1.0)),
        ),
        reverse=True,
    )
    winner = qualified[0]
    candidate_id = str(winner["candidate_id"])
    source_path: Path | None = None
    for candidate_row in promoted:
        if candidate_row["candidate_id"] == candidate_id:
            source_path = Path(str(candidate_row["candidate"]["source_path"]))
            break
    if source_path is None:
        raise RuntimeError(f"qualified candidate source disappeared: {candidate_id}")

    archive = output / f"NEXT_SUBMIT_SWARM_{candidate_id}.tar.gz"
    _package_tree(source_path.parent, archive)
    archive_verification = _verify_archive(archive)
    result["winner"] = winner
    result["archive"] = str(archive)
    result["archive_verification"] = archive_verification

    if frontier_scope != "verified_v32_public_frontier":
        result["decision"] = "HOLD"
        result["reason"] = "candidate qualified locally but control scope was not verified V32 public frontier"
    elif not archive_verification.get("ok"):
        result["decision"] = "HOLD"
        result["reason"] = "candidate qualified scientifically but final packaged archive failed runtime verification"
    else:
        result["decision"] = "PROMOTE"
        result["reason"] = "heldout promotion replicated on sealed confirmation and packaged runtime passed"

    (output / "SUBMISSION_DECISION.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result
