from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
from typing import Any

from .config_loader import load_config
from .council import prioritize_for_replication, summarize_reviews
from .providers import ProviderError, build_provider
from .registry import SwarmRegistry


def _json_payload(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Council response must be a JSON object")
    return payload


def _screen_evidence(epoch: Path, registry: SwarmRegistry) -> dict[str, Any]:
    evaluation_path = epoch / "EPOCH_EVALUATION.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    claims = {
        str(row["claim_id"]): {
            key: value
            for key, value in row.items()
            if key in {"claim_id", "hypothesis", "mechanism", "expected_failure_mode", "predicted_effect"}
        }
        for row in registry.claims.read()
    }
    candidates = {str(row["candidate_id"]): row for row in registry.candidates.read()}
    evidence = []
    for row in evaluation.get("screen", []):
        candidate = candidates.get(str(row.get("candidate_id")), {})
        evidence.append(
            {
                "candidate_id": row.get("candidate_id"),
                "role": candidate.get("role"),
                "lane": candidate.get("lane"),
                "claim": claims.get(str(candidate.get("claim_id"))),
                "metrics": {
                    "mean_score": row.get("mean_score"),
                    "paired_score_delta": row.get("paired_score_delta"),
                    "worst_family_delta": row.get("worst_family_delta"),
                    "passive_cash_ratio": row.get("passive_cash_ratio"),
                    "invalid_games": row.get("invalid_games"),
                    "mean_call_ms": row.get("mean_call_ms"),
                    "physical_divergence": row.get("physical_divergence"),
                    "family_scores": row.get("metadata", {}).get("family_scores", {}),
                    "family_deltas": row.get("metadata", {}).get("family_deltas", {}),
                },
            }
        )
    return {"screen_candidates": evidence}


def review_epoch(*, epoch_root: str, config_path: str, repo_root: str = ".") -> dict[str, Any]:
    epoch = Path(epoch_root)
    config = load_config(config_path)
    registry = SwarmRegistry(epoch / "registry")
    contract = (Path(repo_root) / "swarm/prompts/council.md").read_text(encoding="utf-8")
    evidence = _screen_evidence(epoch, registry)
    prompt = contract + "\n\n# SCREEN EVIDENCE\n" + json.dumps(evidence, indent=2, sort_keys=True)
    reviewer_keys = list(config.get("council", {}).get("reviewers", ["chief_scientist", "auditor", "mechanism"]))
    outbox = epoch / "council_outbox"

    responses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(len(reviewer_keys), int(config["providers"]["max_parallel_requests"]))) as executor:
        futures = {}
        for key in reviewer_keys:
            model_cfg = config["providers"]["models"][key]
            provider = build_provider(str(model_cfg["provider"]), manual_outbox=outbox)
            future = executor.submit(
                provider.complete,
                model=str(model_cfg["model"]),
                system="Act as an independent scientific reviewer. Use screen evidence only.",
                prompt=prompt,
                timeout_s=int(config["providers"]["default_timeout_s"]),
            )
            futures[future] = key

        for future in as_completed(futures):
            reviewer = futures[future]
            try:
                response = future.result()
                payload = _json_payload(response.text)
            except (ProviderError, ValueError, json.JSONDecodeError) as exc:
                registry.reviews.append(
                    {"stage": "council", "reviewer": reviewer, "status": "rejected", "error": str(exc)}
                )
                continue
            responses.append({"reviewer": reviewer, "payload": payload})
            for review in payload.get("reviews", []):
                if not isinstance(review, dict) or "candidate_id" not in review or "score" not in review:
                    continue
                registry.reviews.append({"stage": "council", "reviewer": reviewer, "status": "complete", **review})

    flat_reviews = [
        {"candidate_id": review["candidate_id"], "score": review["score"]}
        for response in responses
        for review in response["payload"].get("reviews", [])
        if isinstance(review, dict) and "candidate_id" in review and "score" in review
    ]
    summary = summarize_reviews(flat_reviews) if flat_reviews else {}
    replication_order = prioritize_for_replication(summary) if summary else []
    hints: list[str] = []
    missing: list[str] = []
    for response in responses:
        hints.extend(str(x) for x in response["payload"].get("next_hints", []) if str(x).strip())
        missing.extend(str(x) for x in response["payload"].get("missing_hypotheses", []) if str(x).strip())

    result = {
        "reviewers": reviewer_keys,
        "responses": responses,
        "candidate_summary": summary,
        "replication_order": replication_order,
        "next_hints": list(dict.fromkeys(hints)),
        "missing_hypotheses": list(dict.fromkeys(missing)),
        "evidence_boundary": "screen_only",
    }
    (epoch / "COUNCIL_SCREEN.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    (epoch / "NEXT_EPOCH_HINTS.json").write_text(
        json.dumps(
            {
                "source_epoch": epoch.name,
                "evidence_boundary": "screen_only",
                "replication_order": replication_order,
                "hints": result["next_hints"],
                "missing_hypotheses": result["missing_hypotheses"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run independent council review on screen evidence")
    parser.add_argument("epoch_root")
    parser.add_argument("--config", default="swarm/config/default.yaml")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    result = review_epoch(epoch_root=args.epoch_root, config_path=args.config, repo_root=args.repo_root)
    print(json.dumps({"replication_order": result["replication_order"], "next_hints": result["next_hints"]}, indent=2))


if __name__ == "__main__":
    main()
