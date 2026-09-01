from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from .frontier_acquire import acquire_frontier
from .nvidia_probe import probe_models
from .qualify_submission import qualify_campaign
from .run_campaign import run_campaign


def _tree_hash(path: str | Path) -> str:
    root = Path(path)
    if root.is_file():
        return sha256(root.read_bytes()).hexdigest()
    if not root.exists():
        raise FileNotFoundError(root)
    digest = sha256()
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    for file_path in files:
        relative = file_path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = file_path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _configure_provider_runtime(request: dict[str, Any]) -> None:
    attempts = int(request.get("provider_attempts", 2))
    if attempts < 1 or attempts > 5:
        raise ValueError("provider_attempts must be between 1 and 5")
    os.environ["SWARM_NVIDIA_ATTEMPTS"] = str(attempts)
    if "temperature" in request:
        os.environ["SWARM_NVIDIA_TEMPERATURE"] = str(float(request["temperature"]))


def _acquire_if_requested(request: dict[str, Any], root: Path) -> dict[str, Any] | None:
    if not bool(request.get("auto_frontier", False)):
        return None
    keys = request.get("frontier_keys")
    if keys is not None and not isinstance(keys, list):
        raise ValueError("frontier_keys must be a list")
    return acquire_frontier(
        output_root=root / "frontier",
        keys=[str(key) for key in keys] if keys else None,
    )


def _resolve_experiment_scope(
    request: dict[str, Any],
    root: Path,
    acquisition: dict[str, Any] | None,
) -> tuple[str, dict[str, str], str]:
    champion_path = str(request.get("champion_path", "submission"))
    opponents: dict[str, str] = {}
    scope = "repo_local_control"

    if acquisition:
        scope = str(acquisition.get("scope", "acquisition_unknown"))
        v32 = acquisition.get("resources", {}).get("v32", {})
        if v32.get("status") == "ready":
            champion_path = str(v32["agent_root"])
        for family in acquisition.get("ready_public_families", []):
            row = acquisition.get("resources", {}).get(family, {})
            if row.get("status") == "ready":
                opponents[str(family)] = str(row["agent_root"])

    requested = request.get("opponents")
    if requested:
        if not isinstance(requested, dict):
            raise ValueError("opponents must be a mapping of family name to path")
        opponents.update({str(name): str(path) for name, path in requested.items()})

    # Keep one deterministic in-repo family in the zoo as a regression sentinel.
    local_sentinel = Path("submission/base_controller.py")
    if local_sentinel.exists() and Path(champion_path).resolve() != Path("submission").resolve():
        opponents.setdefault("repo_deterministic", str(local_sentinel))

    (root / "EXPERIMENT_SCOPE.json").write_text(
        json.dumps(
            {
                "scope": scope,
                "champion_path": champion_path,
                "opponents": opponents,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return champion_path, opponents, scope


def execute_request(*, request_path: str, output_root: str) -> dict[str, Any]:
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    if not bool(request.get("enabled", False)):
        raise RuntimeError("live request is not enabled")
    request_id = str(request.get("request_id", "unnamed"))
    mode = str(request.get("mode", "probe")).lower()
    config_path = str(request.get("config", "swarm/config/nvidia_live.yaml"))
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _configure_provider_runtime(request)
    result: dict[str, Any] = {
        "request_id": request_id,
        "mode": mode,
        "config": config_path,
        "provider_attempts": int(os.environ["SWARM_NVIDIA_ATTEMPTS"]),
    }

    if mode == "probe":
        os.environ["SWARM_NVIDIA_MAX_TOKENS"] = str(int(request.get("max_tokens", 128)))
        probe_path = root / "NVIDIA_PROBE.json"
        result["probe"] = probe_models(
            config_path=config_path,
            output_path=str(probe_path),
            timeout_s=int(request.get("timeout_s", 180)),
        )
    elif mode == "frontier_probe":
        acquisition = acquire_frontier(
            output_root=root / "frontier",
            keys=[str(key) for key in request.get("frontier_keys", [])] or None,
        )
        result["frontier"] = acquisition
    elif mode in {"epoch", "campaign"}:
        acquisition = _acquire_if_requested(request, root)
        champion_path, opponents, frontier_scope = _resolve_experiment_scope(request, root, acquisition)
        champion_hash = _tree_hash(champion_path)
        expected = str(request.get("champion_sha256", "")).strip()
        if expected and expected != champion_hash:
            raise RuntimeError(f"champion hash mismatch: expected {expected}, got {champion_hash}")
        epochs = 1 if mode == "epoch" else int(request.get("epochs", 1))
        if epochs < 1 or epochs > 5:
            raise ValueError("epochs must be between 1 and 5 for live GitHub execution")
        os.environ["SWARM_NVIDIA_MAX_TOKENS"] = str(int(request.get("max_tokens", 24576)))
        if opponents:
            os.environ["SWARM_OPPONENTS_JSON"] = json.dumps(opponents, sort_keys=True)
        else:
            os.environ.pop("SWARM_OPPONENTS_JSON", None)
        campaign_root = run_campaign(
            config_path=config_path,
            repo_root=".",
            output_root=str(root),
            champion_path=champion_path,
            epochs=epochs,
            dry_run=False,
        )
        result.update(
            {
                "frontier": acquisition,
                "frontier_scope": frontier_scope,
                "champion_path": champion_path,
                "champion_tree_sha256": champion_hash,
                "opponents": opponents,
                "epochs": epochs,
                "campaign_root": str(campaign_root),
            }
        )
        if bool(request.get("qualify_submission", True)):
            qualification = qualify_campaign(
                campaign_root=campaign_root,
                config_path=config_path,
                champion_path=champion_path,
                output_root=root / "submission",
                frontier_scope=frontier_scope,
                max_confirmation_candidates=int(request.get("max_confirmation_candidates", 3)),
            )
            result["submission_qualification"] = qualification
    else:
        raise ValueError(f"unknown live request mode {mode!r}")

    result_path = root / "LIVE_REQUEST_RESULT.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute a secret-safe GitHub-hosted Kaggriculture swarm request")
    parser.add_argument("--request", default="swarm_requests/ACTIVE.json")
    parser.add_argument("--output-root", default="swarm/runs/live")
    args = parser.parse_args()
    result = execute_request(request_path=args.request, output_root=args.output_root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
