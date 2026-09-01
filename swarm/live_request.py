from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from .nvidia_probe import probe_models
from .run_campaign import run_campaign


def _tree_hash(path: str | Path) -> str:
    root = Path(path)
    if root.is_file():
        return sha256(root.read_bytes()).hexdigest()
    if not root.exists():
        raise FileNotFoundError(root)
    digest = sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
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
    elif mode in {"epoch", "campaign"}:
        champion_path = str(request.get("champion_path", "submission"))
        champion_hash = _tree_hash(champion_path)
        expected = str(request.get("champion_sha256", "")).strip()
        if expected and expected != champion_hash:
            raise RuntimeError(f"champion hash mismatch: expected {expected}, got {champion_hash}")
        epochs = 1 if mode == "epoch" else int(request.get("epochs", 1))
        if epochs < 1 or epochs > 5:
            raise ValueError("epochs must be between 1 and 5 for live GitHub execution")
        os.environ["SWARM_NVIDIA_MAX_TOKENS"] = str(int(request.get("max_tokens", 24576)))
        opponents = request.get("opponents")
        if opponents:
            if not isinstance(opponents, dict):
                raise ValueError("opponents must be a mapping of family name to path")
            os.environ["SWARM_OPPONENTS_JSON"] = json.dumps(opponents, sort_keys=True)
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
                "champion_path": champion_path,
                "champion_tree_sha256": champion_hash,
                "epochs": epochs,
                "campaign_root": str(campaign_root),
            }
        )
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
