from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config_loader import load_config
from .providers import ProviderError, build_provider


def probe_models(*, config_path: str, output_path: str, timeout_s: int = 180) -> dict[str, Any]:
    config = load_config(config_path)
    seen: set[str] = set()
    probes: list[dict[str, Any]] = []
    for role, model_cfg in config["providers"]["models"].items():
        if str(model_cfg.get("provider", "")).lower() != "nvidia":
            continue
        model = str(model_cfg["model"])
        if model in seen:
            continue
        seen.add(model)
        provider = build_provider("nvidia", manual_outbox=Path(output_path).parent / "manual")
        try:
            response = provider.complete(
                model=model,
                system="You are performing a connectivity check. Follow the user's exact reply format.",
                prompt="Reply with exactly SWARM_NIM_OK and nothing else.",
                timeout_s=timeout_s,
            )
            text = response.text.strip()
            probes.append(
                {
                    "model": model,
                    "roles": sorted(
                        key
                        for key, value in config["providers"]["models"].items()
                        if str(value.get("model")) == model
                    ),
                    "ok": "SWARM_NIM_OK" in text,
                    "response_preview": text[:160],
                    "metadata": response.metadata,
                }
            )
        except ProviderError as exc:
            probes.append({"model": model, "roles": [role], "ok": False, "error": str(exc)})

    summary = {
        "config": config_path,
        "model_count": len(probes),
        "ok_count": sum(1 for row in probes if row["ok"]),
        "all_ok": bool(probes) and all(row["ok"] for row in probes),
        "models": probes,
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe configured NVIDIA NIM models without exposing credentials")
    parser.add_argument("--config", default="swarm/config/nvidia_live.yaml")
    parser.add_argument("--output", default="swarm/runs/NVIDIA_PROBE.json")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    summary = probe_models(config_path=args.config, output_path=args.output, timeout_s=args.timeout)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.require_all and not summary["all_ok"]:
        raise SystemExit(3)
    if summary["ok_count"] == 0:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
