from __future__ import annotations

import re
from uuid import uuid4

from .models import ExperimentClaim


SECTIONS = (
    "HYPOTHESIS",
    "MECHANISM",
    "CODE_CHANGE",
    "EXPECTED_FAILURE_MODE",
    "SCREEN_TEST",
    "HELDOUT_TEST",
    "PREDICTED_EFFECT",
)


def _extract(text: str, section: str) -> str:
    names = "|".join(re.escape(name) for name in SECTIONS)
    pattern = rf"(?ims)^\s*#+\s*{re.escape(section)}\s*$\n(.*?)(?=^\s*#+\s*(?:{names})\s*$|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def parse_claim(*, task_id: str, response: str) -> ExperimentClaim:
    claim = ExperimentClaim(
        claim_id=f"claim-{uuid4().hex[:12]}",
        task_id=task_id,
        hypothesis=_extract(response, "HYPOTHESIS"),
        mechanism=_extract(response, "MECHANISM"),
        code_change=_extract(response, "CODE_CHANGE"),
        expected_failure_mode=_extract(response, "EXPECTED_FAILURE_MODE"),
        screen_test=_extract(response, "SCREEN_TEST"),
        heldout_test=_extract(response, "HELDOUT_TEST"),
        predicted_effect=_extract(response, "PREDICTED_EFFECT"),
        raw_response=response,
    )
    missing = claim.validate()
    if missing:
        raise ValueError(f"Research response missing required sections: {', '.join(missing)}")
    return claim
