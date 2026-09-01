from pathlib import Path

import pytest

from swarm.builder import extract_main_py
from swarm.config_loader import validate_config
from swarm.kaggriculture_evaluator import smoke_candidate
from swarm.models import EvaluationRecord
from swarm.parser import parse_claim
from swarm.promotion import promotion_decision
from swarm.run_epoch import _read_agent_bundle
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


def test_static_check_allows_recursively_safe_embedded_parent():
    parent = "def parent(obs, cfg=None):\n    return {}\n"
    source = f"PARENT = {parent!r}\nexec(compile(PARENT, '<parent>', 'exec'))\ndef agent(obs, cfg=None):\n    return parent(obs, cfg)\n"
    assert check_source(source).ok


def test_static_check_rejects_dynamic_or_unsafe_embedded_code():
    dynamic = "code = input()\nexec(code)\ndef agent(obs, cfg=None):\n    return {}\n"
    assert not check_source(dynamic).ok

    unsafe_parent = "import subprocess\ndef parent(obs, cfg=None):\n    return {}\n"
    source = f"PARENT = {unsafe_parent!r}\nexec(PARENT)\ndef agent(obs, cfg=None):\n    return parent(obs, cfg)\n"
    result = check_source(source)
    assert not result.ok
    assert any("subprocess" in error for error in result.errors)


def test_agent_bundle_includes_dependencies(tmp_path: Path):
    root = tmp_path / "agent"
    root.mkdir()
    (root / "main.py").write_text("from helper import agent\n", encoding="utf-8")
    (root / "helper.py").write_text("def agent(obs, cfg=None): return {'farmer':['PASS'],'hands':[],'market':[]}\n", encoding="utf-8")
    bundle = _read_agent_bundle(str(root))
    assert "BUNDLED FILE: main.py" in bundle
    assert "BUNDLED FILE: helper.py" in bundle
    assert "quarantined as one main.py" in bundle


def test_runtime_smoke_accepts_minimal_passive_agent(tmp_path: Path):
    candidate = tmp_path / "main.py"
    candidate.write_text(
        "def agent(obs, configuration=None):\n    return {'farmer':['PASS'],'hands':[],'market':[]}\n",
        encoding="utf-8",
    )
    smoke = smoke_candidate(str(candidate), seed=73)
    assert smoke["ok"]
    assert smoke["invalid_games"] == 0
    assert len(smoke["rows"]) == 2


def test_promotion_requires_every_gate_and_supports_lane_override():
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
        "lane_overrides": {"architecture": {"max_physical_divergence": 1.0}},
    }
    assert promotion_decision(evaluation, thresholds).promote

    bad = EvaluationRecord(**{**evaluation.__dict__, "invalid_games": 1})
    assert not promotion_decision(bad, thresholds).promote

    architectural = EvaluationRecord(**{**evaluation.__dict__, "physical_divergence": 0.9})
    assert not promotion_decision(architectural, thresholds).promote
    assert promotion_decision(architectural, thresholds, lane="architecture").promote


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
