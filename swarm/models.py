from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    epoch_id: str
    role: str
    lane: str
    model_key: str
    packet_kind: str
    information_round: str
    prompt: str
    packet_hash: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentClaim:
    claim_id: str
    task_id: str
    hypothesis: str
    mechanism: str
    code_change: str
    expected_failure_mode: str
    screen_test: str
    heldout_test: str
    predicted_effect: str
    raw_response: str = ""
    created_at: str = field(default_factory=utc_now)

    def validate(self) -> list[str]:
        required = {
            "hypothesis": self.hypothesis,
            "mechanism": self.mechanism,
            "code_change": self.code_change,
            "expected_failure_mode": self.expected_failure_mode,
            "screen_test": self.screen_test,
            "heldout_test": self.heldout_test,
            "predicted_effect": self.predicted_effect,
        }
        return [name for name, value in required.items() if not value.strip()]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claim_hash"] = stable_hash({k: v for k, v in data.items() if k != "raw_response"})
        return data


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    claim_id: str
    role: str
    lane: str
    parent_policy: str
    source_path: str
    source_hash: str
    architecture_tags: tuple[str, ...] = ()
    mechanism_tags: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["architecture_tags"] = list(self.architecture_tags)
        data["mechanism_tags"] = list(self.mechanism_tags)
        return data


@dataclass(frozen=True)
class EvaluationRecord:
    evaluation_id: str
    candidate_id: str
    stage: str
    mean_score: float
    paired_score_delta: float
    worst_family_delta: float
    passive_cash_ratio: float
    invalid_games: int
    mean_call_ms: float
    physical_divergence: float
    behavioral_fingerprint: tuple[float, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["behavioral_fingerprint"] = list(self.behavioral_fingerprint)
        return data


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    promote: bool
    reasons: tuple[str, ...]
    score: float
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data
