from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .builder import candidate_build_prompt, materialize_candidate
from .config_loader import load_config
from .models import ResearchTask
from .packet import build_packet
from .parser import parse_claim
from .providers import ProviderError, build_provider
from .registry import SwarmRegistry
from .safety import check_file


CHAMPION_INFORMED_PACKETS = {"champion_counter", "trace_mechanism", "frontier_residual"}


def _epoch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"epoch-{stamp}-{uuid4().hex[:6]}"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_agent_source(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if p.is_dir():
        p = p / "main.py"
    if not p.exists():
        raise FileNotFoundError(f"champion source not found: {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def _public_context(config: dict[str, Any], epoch_id: str) -> dict[str, Any]:
    return {
        "epoch_id": epoch_id,
        "swarm": config["name"],
        "frontier_branch": config["frontier"]["branch"],
        "champion_policy": config["frontier"]["champion_policy"],
        "screen": {
            "both_seats": bool(config["experiments"]["screen"]["both_seats"]),
            "seed_count": len(config["experiments"]["screen"]["seeds"]),
        },
        "heldout": {
            "both_seats": bool(config["experiments"]["heldout"]["both_seats"]),
            "sealed": True,
            "seed_count": len(config["experiments"]["heldout"]["seeds"]),
        },
        "promotion_thresholds": config["experiments"]["promotion"],
    }


def _tasks(
    config: dict[str, Any],
    epoch_id: str,
    repo_root: Path,
    *,
    feedback: str,
    champion_source: str,
    round_index: int,
) -> list[tuple[ResearchTask, str]]:
    tasks: list[tuple[ResearchTask, str]] = []
    context = _public_context(config, epoch_id)
    rounds = list(config["information_release"]["rounds"])
    info_round = rounds[min(round_index, len(rounds) - 1)]
    for role in config["roles"]:
        role_id = str(role["id"])
        model_cfg = config["providers"]["models"].get(role_id)
        if model_cfg is None:
            raise KeyError(f"No provider model configured for role {role_id!r}")
        packet_kind = str(role["packet"])
        evidence_sections: list[str] = []
        if packet_kind != "blank_sheet" and feedback:
            evidence_sections.extend(("### PRIOR SCREEN-ONLY COUNCIL FEEDBACK", feedback))
        if packet_kind in CHAMPION_INFORMED_PACKETS and champion_source:
            evidence_sections.extend(("### EXACT CURRENT CHAMPION SOURCE", "```python", champion_source, "```"))
        role_evidence = "\n\n".join(evidence_sections)
        for index in range(int(role["count"])):
            packet = build_packet(
                repo_root=repo_root,
                kind=packet_kind,
                public_context=context,
                extra_evidence=role_evidence,
            )
            task_id = f"task-{role_id}-{index:02d}-{uuid4().hex[:8]}"
            prompt = (
                f"# ASSIGNED ROLE\n{role_id}\n\n"
                f"# RESEARCH LANE\n{role['lane']}\n\n"
                f"# INFORMATION ROUND\n{info_round}\n\n"
                + packet.text
            )
            task = ResearchTask(
                task_id=task_id,
                epoch_id=epoch_id,
                role=role_id,
                lane=str(role["lane"]),
                model_key=role_id,
                packet_kind=packet_kind,
                information_round=info_round,
                prompt=prompt,
                packet_hash=packet.packet_hash,
            )
            tasks.append((task, packet.text))
    return tasks


def _call_researcher(
    *,
    task: ResearchTask,
    config: dict[str, Any],
    system: str,
    outbox: Path,
    dry_run: bool,
) -> tuple[ResearchTask, str, dict[str, Any]]:
    model_cfg = config["providers"]["models"][task.model_key]
    provider_name = "manual" if dry_run else str(model_cfg["provider"])
    provider = build_provider(provider_name, manual_outbox=outbox)
    response = provider.complete(
        model=str(model_cfg["model"]),
        system=system,
        prompt=task.prompt,
        timeout_s=int(config["providers"]["default_timeout_s"]),
    )
    return task, response.text, response.metadata


def run_epoch(
    *,
    config_path: str,
    repo_root: str,
    output_root: str,
    dry_run: bool,
    feedback_path: str | None = None,
    round_index: int = 0,
    champion_path: str | None = None,
) -> Path:
    repo_root_path = Path(repo_root).resolve()
    config = load_config(config_path)
    role_config = {str(role["id"]): role for role in config["roles"]}
    feedback = Path(feedback_path).read_text(encoding="utf-8") if feedback_path else ""
    champion_source = _read_agent_source(champion_path)
    epoch_id = _epoch_id()
    epoch_root = Path(output_root).resolve() / epoch_id
    epoch_root.mkdir(parents=True, exist_ok=False)
    registry = SwarmRegistry(epoch_root / "registry")
    outbox = epoch_root / "outbox"
    candidates_root = epoch_root / "candidates"
    candidates_root.mkdir(parents=True, exist_ok=True)

    system = _read(repo_root_path / "swarm/prompts/base.md") + "\n\n" + _read(
        repo_root_path / "swarm/prompts/roles.md"
    )
    build_contract = _read(repo_root_path / "swarm/prompts/build.md")
    tasks = _tasks(
        config,
        epoch_id,
        repo_root_path,
        feedback=feedback,
        champion_source=champion_source,
        round_index=round_index,
    )
    for task, _packet in tasks:
        registry.tasks.append(task)

    manifest = {
        "epoch_id": epoch_id,
        "config_path": str(Path(config_path).resolve()),
        "config_hash": sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest(),
        "dry_run": dry_run,
        "task_count": len(tasks),
        "round_index": round_index,
        "feedback_hash": sha256(feedback.encode("utf-8")).hexdigest() if feedback else None,
        "champion_source_hash": sha256(champion_source.encode("utf-8")).hexdigest() if champion_source else None,
        "screen_seed_hash": sha256(
            json.dumps(config["experiments"]["screen"]["seeds"], sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "heldout_seed_hash": sha256(
            json.dumps(config["experiments"]["heldout"]["seeds"], sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    (epoch_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    max_workers = int(config["providers"]["max_parallel_requests"])
    research_results: dict[str, tuple[str, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _call_researcher,
                task=task,
                config=config,
                system=system,
                outbox=outbox,
                dry_run=dry_run,
            ): task
            for task, _packet in tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            try:
                _task, text, metadata = future.result()
            except ProviderError as exc:
                registry.reviews.append(
                    {"task_id": task.task_id, "stage": "research", "status": "provider_error", "error": str(exc)}
                )
                continue
            research_results[task.task_id] = (text, metadata)
            registry.reviews.append(
                {"task_id": task.task_id, "stage": "research", "status": "complete", "metadata": metadata}
            )

    if dry_run:
        errors = registry.validate()
        (epoch_root / "DRY_RUN_READY.txt").write_text(
            "Research packets exported successfully.\n" + ("\n".join(errors) if errors else "Registry valid.\n"),
            encoding="utf-8",
        )
        return epoch_root

    packet_by_task = {task.task_id: packet for task, packet in tasks}
    task_by_id = {task.task_id: task for task, _packet in tasks}
    for task_id, (response, _metadata) in research_results.items():
        task = task_by_id[task_id]
        try:
            claim = parse_claim(task_id=task_id, response=response)
        except ValueError as exc:
            registry.reviews.append(
                {"task_id": task_id, "stage": "parse", "status": "rejected", "error": str(exc)}
            )
            continue
        registry.claims.append(claim)

        if not bool(role_config[task.role].get("build_candidate", True)):
            registry.reviews.append(
                {"task_id": task_id, "stage": "build", "status": "skipped_research_only_role"}
            )
            continue

        model_cfg = config["providers"]["models"][task.model_key]
        provider = build_provider(str(model_cfg["provider"]), manual_outbox=outbox)
        build_prompt = candidate_build_prompt(
            claim=claim,
            packet_text=packet_by_task[task_id],
            build_contract=build_contract,
        )
        try:
            built = provider.complete(
                model=str(model_cfg["model"]),
                system="Implement the frozen Kaggriculture research claim exactly and conservatively.",
                prompt=build_prompt,
                timeout_s=int(config["providers"]["default_timeout_s"]),
            )
            candidate = materialize_candidate(
                response=built.text,
                claim=claim,
                role=task.role,
                lane=task.lane,
                parent_policy=str(config["frontier"]["champion_policy"]),
                output_root=candidates_root,
                architecture_tags=(task.role,) if task.lane == "architecture" else (),
                mechanism_tags=(task.lane,),
            )
        except (ProviderError, ValueError) as exc:
            registry.reviews.append(
                {"task_id": task_id, "stage": "build", "status": "rejected", "error": str(exc)}
            )
            continue

        static = check_file(candidate.source_path)
        registry.reviews.append(
            {
                "task_id": task_id,
                "candidate_id": candidate.candidate_id,
                "stage": "static_check",
                "status": "pass" if static.ok else "reject",
                "errors": list(static.errors),
            }
        )
        if static.ok:
            registry.candidates.append(candidate)

    validation_errors = registry.validate()
    if validation_errors:
        (epoch_root / "REGISTRY_ERRORS.txt").write_text("\n".join(validation_errors) + "\n", encoding="utf-8")
        raise RuntimeError("Swarm registry validation failed")

    (epoch_root / "CANDIDATES_READY.json").write_text(
        json.dumps(registry.candidates.read(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return epoch_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Kaggriculture autonomous research epoch")
    parser.add_argument("--config", default="swarm/config/default.yaml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-root", default="swarm/runs")
    parser.add_argument("--feedback", default=None, help="screen-only feedback JSON from the previous epoch")
    parser.add_argument("--round-index", type=int, default=0)
    parser.add_argument("--champion-path", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = run_epoch(
        config_path=args.config,
        repo_root=args.repo_root,
        output_root=args.output_root,
        dry_run=args.dry_run,
        feedback_path=args.feedback,
        round_index=args.round_index,
        champion_path=args.champion_path,
    )
    print(root)


if __name__ == "__main__":
    main()
