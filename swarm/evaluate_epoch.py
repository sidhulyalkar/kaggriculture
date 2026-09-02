from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from .config_loader import load_config
from .experiment_adapter import EvaluationRequest, evaluate_with_callable
from .models import CandidateRecord, EvaluationRecord
from .novelty import novelty_score
from .promotion import promotion_decision, select_portfolio
from .registry import SwarmRegistry


DEFAULT_SUBMISSION_SLOTS = ["champion", "counter", "architecture", "robust", "explorer"]


def _candidate_from_row(row: dict) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=str(row["candidate_id"]),
        claim_id=str(row["claim_id"]),
        role=str(row["role"]),
        lane=str(row["lane"]),
        parent_policy=str(row["parent_policy"]),
        source_path=str(row["source_path"]),
        source_hash=str(row["source_hash"]),
        architecture_tags=tuple(row.get("architecture_tags", ())),
        mechanism_tags=tuple(row.get("mechanism_tags", ())),
        created_at=str(row.get("created_at", "")),
    )


def _with_metadata(evaluation: EvaluationRecord, candidate: CandidateRecord, **extra) -> EvaluationRecord:
    metadata = dict(evaluation.metadata)
    metadata.update({"lane": candidate.lane, "role": candidate.role, **extra})
    return replace(evaluation, metadata=metadata)


def _shifted(values: list[int], offset: int) -> tuple[int, ...]:
    return tuple(int(value) + int(offset) for value in values)


def _submission_slots(config: dict) -> list[str]:
    legacy = config.get("submission_portfolio", {})
    slots = legacy.get("slots") if isinstance(legacy, dict) else None
    if not slots:
        slots = config.get("submission_slots")
    if not slots:
        slots = DEFAULT_SUBMISSION_SLOTS
    return [str(slot) for slot in slots]


def _screen_survives(evaluation: EvaluationRecord, screen_cfg: dict) -> bool:
    if evaluation.invalid_games != 0:
        return False
    min_score = float(screen_cfg.get("min_paired_score_delta", -0.05))
    min_cash = float(screen_cfg.get("min_paired_cash_delta", float("-inf")))
    min_cash_relative = float(screen_cfg.get("min_paired_cash_relative_delta", float("-inf")))
    paired_cash = float(evaluation.metadata.get("paired_cash_delta", float("-inf")))
    paired_cash_relative = float(evaluation.metadata.get("paired_cash_relative_delta", float("-inf")))
    return (
        evaluation.paired_score_delta >= min_score
        and paired_cash >= min_cash
        and paired_cash_relative >= min_cash_relative
    )


def evaluate_epoch(
    *,
    epoch_root: str,
    config_path: str,
    evaluator: str,
    champion_path: str,
    seed_offset: int = 0,
) -> dict[str, object]:
    epoch = Path(epoch_root)
    config = load_config(config_path)
    registry = SwarmRegistry(epoch / "registry")
    candidates = [_candidate_from_row(row) for row in registry.candidates.read()]
    thresholds = config["experiments"]["promotion"]
    screen_cfg = config["experiments"]["screen"]
    screen_seeds = _shifted(screen_cfg["seeds"], seed_offset)
    heldout_seeds = _shifted(config["experiments"]["heldout"]["seeds"], seed_offset)

    screen_objects: list[EvaluationRecord] = []
    survivors: list[CandidateRecord] = []
    for candidate in candidates:
        request = EvaluationRequest(
            candidate_id=candidate.candidate_id,
            candidate_path=candidate.source_path,
            champion_path=champion_path,
            stage="screen",
            seeds=screen_seeds,
            both_seats=bool(screen_cfg["both_seats"]),
        )
        evaluation = _with_metadata(evaluate_with_callable(request, evaluator), candidate)
        registry.evaluations.append(evaluation)
        screen_objects.append(evaluation)
        if _screen_survives(evaluation, screen_cfg):
            survivors.append(candidate)

    heldout_objects: list[EvaluationRecord] = []
    decisions = []
    promoted_ids: set[str] = set()
    for candidate in survivors:
        request = EvaluationRequest(
            candidate_id=candidate.candidate_id,
            candidate_path=candidate.source_path,
            champion_path=champion_path,
            stage="heldout",
            seeds=heldout_seeds,
            both_seats=bool(config["experiments"]["heldout"]["both_seats"]),
        )
        evaluation = _with_metadata(evaluate_with_callable(request, evaluator), candidate)
        population = [row.behavioral_fingerprint for row in heldout_objects if row.behavioral_fingerprint]
        novelty = novelty_score(evaluation.behavioral_fingerprint, population) if evaluation.behavioral_fingerprint else 0.0
        evaluation = _with_metadata(evaluation, candidate, novelty=novelty)
        registry.evaluations.append(evaluation)
        heldout_objects.append(evaluation)
        decision = promotion_decision(evaluation, thresholds, lane=candidate.lane)
        registry.promotions.append(decision)
        decisions.append(decision.to_dict())
        if decision.promote:
            promoted_ids.add(candidate.candidate_id)

    slots = _submission_slots(config)
    portfolio = select_portfolio(heldout_objects, promoted_ids, slots)
    if not portfolio.get("champion"):
        portfolio["champion"] = "CURRENT_CHAMPION"

    summary = {
        "candidate_count": len(candidates),
        "screen_survivors": len(survivors),
        "promoted_count": len(promoted_ids),
        "seed_offset": seed_offset,
        "screen_gate": {
            "min_paired_score_delta": float(screen_cfg.get("min_paired_score_delta", -0.05)),
            "min_paired_cash_delta": screen_cfg.get("min_paired_cash_delta"),
            "min_paired_cash_relative_delta": screen_cfg.get("min_paired_cash_relative_delta"),
        },
        "screen": [row.to_dict() for row in screen_objects],
        "heldout": [row.to_dict() for row in heldout_objects],
        "decisions": decisions,
        "portfolio": portfolio,
    }
    (epoch / "EPOCH_EVALUATION.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a Kaggriculture swarm epoch")
    parser.add_argument("epoch_root")
    parser.add_argument("--config", default="swarm/config/default.yaml")
    parser.add_argument(
        "--evaluator",
        default="swarm.kaggriculture_evaluator:evaluate_candidate",
        help="module:function evaluator adapter",
    )
    parser.add_argument("--champion-path", required=True)
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()
    summary = evaluate_epoch(
        epoch_root=args.epoch_root,
        config_path=args.config,
        evaluator=args.evaluator,
        champion_path=args.champion_path,
        seed_offset=args.seed_offset,
    )
    print(json.dumps(summary["portfolio"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
