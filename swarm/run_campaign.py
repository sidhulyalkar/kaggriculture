from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .evaluate_epoch import evaluate_epoch
from .review_epoch import review_epoch
from .run_epoch import run_epoch


def run_campaign(
    *,
    config_path: str,
    repo_root: str,
    output_root: str,
    champion_path: str,
    epochs: int,
    dry_run: bool,
    evaluator: str = "swarm.kaggriculture_evaluator:evaluate_candidate",
) -> Path:
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    campaign_id = datetime.now(timezone.utc).strftime("campaign-%Y%m%dT%H%M%SZ-") + uuid4().hex[:6]
    campaign_root = Path(output_root).resolve() / campaign_id
    campaign_root.mkdir(parents=True, exist_ok=False)
    epoch_output = campaign_root / "epochs"
    epoch_output.mkdir()

    feedback_path: str | None = None
    rows: list[dict[str, object]] = []
    for index in range(epochs):
        epoch = run_epoch(
            config_path=config_path,
            repo_root=repo_root,
            output_root=str(epoch_output),
            dry_run=dry_run,
            feedback_path=feedback_path,
            round_index=index,
            champion_path=champion_path,
        )
        row: dict[str, object] = {"round": index, "epoch": str(epoch)}
        if dry_run:
            rows.append(row)
            break

        seed_offset = index * 10000
        evaluation = evaluate_epoch(
            epoch_root=str(epoch),
            config_path=config_path,
            evaluator=evaluator,
            champion_path=champion_path,
            seed_offset=seed_offset,
        )
        council = review_epoch(epoch_root=str(epoch), config_path=config_path, repo_root=repo_root)
        feedback_path = str(epoch / "NEXT_EPOCH_HINTS.json")
        row.update(
            {
                "seed_offset": seed_offset,
                "candidate_count": evaluation["candidate_count"],
                "screen_survivors": evaluation["screen_survivors"],
                "promoted_count": evaluation["promoted_count"],
                "portfolio": evaluation["portfolio"],
                "replication_order": council["replication_order"],
                "feedback_path": feedback_path,
            }
        )
        rows.append(row)

    summary = {
        "campaign_id": campaign_id,
        "epochs_requested": epochs,
        "dry_run": dry_run,
        "champion_path": champion_path,
        "evaluator": evaluator,
        "research_feedback_boundary": "screen_only",
        "seed_rotation": "base_seed + 10000 * round",
        "rounds": rows,
    }
    (campaign_root / "CAMPAIGN_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return campaign_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a multi-epoch Kaggriculture autonomous swarm campaign")
    parser.add_argument("--config", default="swarm/config/default.yaml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-root", default="swarm/runs")
    parser.add_argument("--champion-path", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--evaluator", default="swarm.kaggriculture_evaluator:evaluate_candidate")
    args = parser.parse_args()
    root = run_campaign(
        config_path=args.config,
        repo_root=args.repo_root,
        output_root=args.output_root,
        champion_path=args.champion_path,
        epochs=args.epochs,
        dry_run=args.dry_run,
        evaluator=args.evaluator,
    )
    print(root)


if __name__ == "__main__":
    main()
