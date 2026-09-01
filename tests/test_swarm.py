from pathlib import Path

import pytest

from swarm.builder import extract_main_py
from swarm.config_loader import validate_config
from swarm.models import EvaluationRecord
from swarm.parser import parse_claim
from swarm.promotion import promotion_decision
from swarm.safety import check_source


def test_parse_claim_contract():
    response = """
## HYPOTHESIS
Market ordering leaks value.
## MECHANISM
Shared supply changes price before later sells.
## CODE_CHANGE
Reorder existing sell slots only.
## EXPECTED_FAILURE_MODE
No benefit when prices are flat.
## SCREEN_TEST
Paired both-seat test.
## HELDOUT_TEST
New seeds and family-balanced opponents.
## PREDICTED_EFFECT
Small positive score delta.
"""
    claim = parse_claim(task_id="t1", response=response)
    assert claim.hypothesis.startswith("Market ordering")
    assert claim.validate() == []


def test_extract_main_py_requires_agent():
    source = extract_main_py("## MAIN_PY\n```python\ndef agent(obs, cfg):\n    return {}\n```")
    assert "def agent" in source
    with pytest.raises(ValueError):
        extract_main_py("## MAIN_PY\n```python\ndef helper():\n    return 1\n```")


def test_static_check_rejects_network_import():
    result = check_source("import requests\ndef agent(obs, cfg):\n    return {}\n")
    assert not result.ok
    assert any("forbidden import" in error for error in result.errors)


def test_promotion_requires_every_gate():
    evaluation = EvaluationRecord(
        evaluation_id="e1",
        candidate_id="c1",
        stage="heldout",
        mean_score=0.7,
        paired_score_delta=0.03,
        worst_family_delta=-0.01,
        passive_cash_ratio=0.99,
        invalid_games=0,
        mean_call_ms=20.0,
        physical_divergence=0.01,
    )
    thresholds = {
        "min_paired_score_delta": 0.02,
        "min_worst_family_delta": -0.03,
        "min_passive_cash_ratio": 0.97,
        "max_invalid_games": 0,
        "max_mean_call_ms": 100.0,
        "max_physical_divergence": 0.02,
    }
    assert promotion_decision(evaluation, thresholds).promote

    bad = EvaluationRecord(**{**evaluation.__dict__, "invalid_games": 1})
    assert not promotion_decision(bad, thresholds).promote


def test_config_rejects_seed_leakage():
    config = {
        "budget": {"a": 1.0},
        "roles": [{"id": "r", "count": 1}],
        "frontier": {"preserve_champion": True},
        "experiments": {
            "screen": {"seeds": [1, 2]},
            "heldout": {"seeds": [2, 3], "sealed": True},
        },
    }
    with pytest.raises(ValueError, match="overlap"):
        validate_config(config)
