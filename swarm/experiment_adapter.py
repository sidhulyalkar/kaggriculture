from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any, Callable

from .models import EvaluationRecord


@dataclass(frozen=True)
class EvaluationRequest:
    candidate_id: str
    candidate_path: str
    champion_path: str
    stage: str
    seeds: tuple[int, ...]
    both_seats: bool


class EvaluationAdapterError(RuntimeError):
    pass


def load_callable(spec: str) -> Callable[..., Any]:
    """Load `package.module:function` without coupling swarm to one league implementation."""
    if ":" not in spec:
        raise EvaluationAdapterError(f"Invalid callable spec {spec!r}; expected module:function")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise EvaluationAdapterError(f"{spec!r} did not resolve to a callable")
    return function


def normalize_evaluation(candidate_id: str, stage: str, payload: dict[str, Any]) -> EvaluationRecord:
    required = (
        "mean_score",
        "paired_score_delta",
        "worst_family_delta",
        "passive_cash_ratio",
        "invalid_games",
        "mean_call_ms",
        "physical_divergence",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise EvaluationAdapterError(f"Evaluator missing fields: {', '.join(missing)}")
    return EvaluationRecord(
        evaluation_id=str(payload.get("evaluation_id", f"{candidate_id}-{stage}")),
        candidate_id=candidate_id,
        stage=stage,
        mean_score=float(payload["mean_score"]),
        paired_score_delta=float(payload["paired_score_delta"]),
        worst_family_delta=float(payload["worst_family_delta"]),
        passive_cash_ratio=float(payload["passive_cash_ratio"]),
        invalid_games=int(payload["invalid_games"]),
        mean_call_ms=float(payload["mean_call_ms"]),
        physical_divergence=float(payload["physical_divergence"]),
        behavioral_fingerprint=tuple(float(x) for x in payload.get("behavioral_fingerprint", ())),
        metadata=dict(payload.get("metadata", {})),
    )


def evaluate_with_callable(request: EvaluationRequest, callable_spec: str) -> EvaluationRecord:
    evaluator = load_callable(callable_spec)
    payload = evaluator(
        candidate_path=request.candidate_path,
        champion_path=request.champion_path,
        seeds=list(request.seeds),
        both_seats=request.both_seats,
        stage=request.stage,
    )
    if not isinstance(payload, dict):
        raise EvaluationAdapterError("Evaluator must return a mapping")
    return normalize_evaluation(request.candidate_id, request.stage, payload)


def import_evaluation(path: str | Path, *, candidate_id: str, stage: str) -> EvaluationRecord:
    """Manual bridge for Kaggle notebook or external tournament output."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_evaluation(candidate_id, stage, payload)
