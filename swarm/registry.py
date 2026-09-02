from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable


class JsonlRegistry:
    """Small append-only evidence ledger with fsync durability."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize(record: Any) -> dict[str, Any]:
        if hasattr(record, "to_dict"):
            return record.to_dict()
        if is_dataclass(record):
            return asdict(record)
        if isinstance(record, dict):
            return record
        raise TypeError(f"Unsupported registry record: {type(record)!r}")

    def append(self, record: Any) -> None:
        payload = self._normalize(record)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Corrupt JSONL {self.path}:{lineno}: {exc}") from exc
        return out

    def ids(self, key: str) -> set[str]:
        return {str(row[key]) for row in self.read() if key in row}

    def extend(self, records: Iterable[Any]) -> None:
        for record in records:
            self.append(record)


class SwarmRegistry:
    def __init__(self, root: str | Path):
        root = Path(root)
        self.tasks = JsonlRegistry(root / "tasks.jsonl")
        self.claims = JsonlRegistry(root / "claims.jsonl")
        self.candidates = JsonlRegistry(root / "candidates.jsonl")
        self.evaluations = JsonlRegistry(root / "evaluations.jsonl")
        self.reviews = JsonlRegistry(root / "reviews.jsonl")
        self.promotions = JsonlRegistry(root / "promotions.jsonl")

    def validate(self) -> list[str]:
        errors: list[str] = []
        task_ids = self.tasks.ids("task_id")
        claim_rows = self.claims.read()
        claim_ids = {str(row["claim_id"]) for row in claim_rows if "claim_id" in row}
        candidate_rows = self.candidates.read()
        candidate_ids = {str(row["candidate_id"]) for row in candidate_rows if "candidate_id" in row}

        for row in claim_rows:
            if row.get("task_id") not in task_ids:
                errors.append(f"claim {row.get('claim_id')} references unknown task {row.get('task_id')}")
        for row in candidate_rows:
            if row.get("claim_id") not in claim_ids:
                errors.append(f"candidate {row.get('candidate_id')} references unknown claim {row.get('claim_id')}")
        for row in self.evaluations.read():
            if row.get("candidate_id") not in candidate_ids:
                errors.append(
                    f"evaluation {row.get('evaluation_id')} references unknown candidate {row.get('candidate_id')}"
                )
        return errors
