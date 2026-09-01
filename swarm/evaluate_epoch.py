from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config_loader import load_config
from .experiment_adapter import EvaluationRequest, evaluate_with_callable
from .models import CandidateRecord
from .promotion import promotion_decision, select_portfolio
from .registry import SwarmRegistry


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


def evaluate_epoch(
    *,
    epoch_root: str,
    config_path: str,
    evaluator: str,
    champion_path: str,
) -> dict[str, object]:
    epoch = Path(epoch_root)
    config = load_config(config_path)
    registry = SwarmRegistry(epoch / "registry")
    candidates = [_candidate_from_row(row) for row in registry.candidates.read()]
    thresholds = config["experiments"]["promotion"]

    screen_rows = []
    survivors: list[CandidateRecord] = []
    for candidate in candidates:
        request = EvaluationRequest(
            candidate_id=candidate.candidate_id,
            candidate_path=candidate.source_path,
            champion_path=champion_path,
            stage="screen",
            seeds=tuple(int(x) for x in config["experiments"]["screen"]["seeds"]),
            both_seats=bool(config["experiments"]["screen"]["both_seats"]),
        )
        evaluation = evaluate_with_callable(request, evaluator)
        registry.evaluations.append(evaluation)
        screen_rows.append(evaluation.to_dict())
        # Screen is intentionally permissive. It rejects runtime failures and severe regressions;
        # the sealed gate remains the actual promotion test.
        if evaluation.invalid_games == 0 and evaluation.paired_score_delta >= -0.01:
            survivors.append(candidate)

    heldout_rows = []
    decisions = []
    promoted_ids: set[str] = set()
    for candidate in survivors:
        request = EvaluationRequest(
            candidate_id=candidate.candidate_id,
            candidate_path=candidate.source_path,
            champion_path=champion_path,
            stage="heldout",
            seeds=tuple(int(x) for x in config["experiments"]["heldout"]["seeds"]),
            both_seats=bool(config["experiments"]["heldout"]["both_seats"]),
        )
        evaluation = evaluate_with_callable(request, evaluator)
        registry.evaluations.append(evaluation)
        heldout_rows.append(evaluation.to_dict())
        decision = promotion_decision(evaluation, thresholds)
        registry.promotions.append(decision)
        decisions.append(decision.to_dict())
        if decision.promote:
            promoted_ids.add(candidate.candidate_id)

    heldout_eval_objects = [
        evaluate_with_callable(
            EvaluationRequest(
                candidate_id="__never__",
                candidate_path="",
                champion_path="",
                stage="__never__",
                seeds=(),
                both_seats=False,
            ),
            evaluator,
        )
        for _ in ()
    ]
    # Rehydrate without triggering evaluator calls; the empty comprehension above pins type shape.
    from .experiment_adapter import normalize_evaluation

    heldout_eval_objects = [
        normalize_evaluation(str(row["candidate_id"]), "heldout", row) for row in heldout_rows
    ]
    slots = list(config["submission_portfolio"]["slots"])
    portfolio = select_portfolio(heldout_eval_objects, promoted_ids, slots)

    summary = {
        "candidate_count": len(candidates),
        "screen_survivors": len(survivors),
        "promoted_count": len(promoted_ids),
        "screen": screen_rows,
        "heldout": heldout_rows,
        "decisions": decisions,
        "portfolio": portfolio,
    }
    (epoch / "EPOCH_EVALUATION.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a Kaggriculture swarm epoch")
    parser.add_argument("epoch_root")
    parser.add_argument("--config", default="swarm/config/default.yaml")
    parser.add_argument("--evaluator", required=True, help="module:function evaluator adapter")
    parser.add_argument("--champion-path", required=True)
    args = parser.parse_args()
    summary = evaluate_epoch(
        epoch_root=args.epoch_root,
        config_path=args.config,
        evaluator=args.evaluator,
        champion_path=args.champion_path,
    )
    print(json.dumps(summary["portfolio"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
