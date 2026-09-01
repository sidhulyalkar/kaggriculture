import http.client
from pathlib import Path

import pytest

from swarm.builder import extract_main_py, materialize_candidate
from swarm.config_loader import validate_config
from swarm.kaggriculture_evaluator import smoke_candidate
from swarm.models import EvaluationRecord, ExperimentClaim
from swarm.parser import parse_claim
from swarm.promotion import promotion_decision
from swarm.providers import ProviderError, _post_json, _retryable_provider_error
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
    assert "copied byte-for-byte" in bundle


def test_materialize_candidate_preserves_trusted_parent(tmp_path: Path):
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "helper.py").write_text(
        "def parent(obs, cfg=None): return {'farmer':['PASS'],'hands':[],'market':[]}\n",
        encoding="utf-8",
    )
    (parent / "main.py").write_text("from helper import parent as agent\n", encoding="utf-8")
    claim = ExperimentClaim(
        claim_id="claim-1",
        task_id="task-1",
        hypothesis="wrapper",
        mechanism="delegate",
        code_change="root wrapper",
        expected_failure_mode="none",
        screen_test="smoke",
        heldout_test="new seeds",
        predicted_effect="parity",
    )
    response = "## MAIN_PY\n```python\nfrom helper import parent as _parent\ndef agent(obs, cfg=None):\n    return _parent(obs, cfg)\n```"
    candidate = materialize_candidate(
        response=response,
        claim=claim,
        role="residual",
        lane="frontier_improvement",
        parent_policy="control",
        output_root=tmp_path / "candidates",
        trusted_parent_root=parent,
    )
    candidate_root = Path(candidate.source_path).parent
    assert (candidate_root / "helper.py").read_text(encoding="utf-8") == (parent / "helper.py").read_text(encoding="utf-8")
    assert "_parent" in Path(candidate.source_path).read_text(encoding="utf-8")


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


def test_remote_disconnect_is_wrapped_as_retryable_provider_error(monkeypatch):
    def disconnect(*args, **kwargs):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    monkeypatch.setattr("swarm.providers.urllib.request.urlopen", disconnect)
    with pytest.raises(ProviderError) as caught:
        _post_json(
            endpoint="https://example.invalid/v1/chat",
            api_key="not-a-real-key",
            body={"hello": "world"},
            timeout_s=1,
        )
    assert caught.value.retryable
    assert _retryable_provider_error(caught.value)
    assert "RemoteDisconnected" in str(caught.value)


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


def test_cash_gates_reject_binary_win_improvement_that_loses_terminal_cash():
    evaluation = EvaluationRecord(
        evaluation_id="cash-e1",
        candidate_id="cash-c1",
        stage="heldout",
        mean_score=0.8,
        paired_score_delta=0.10,
        worst_family_delta=0.0,
        passive_cash_ratio=1.01,
        invalid_games=0,
        mean_call_ms=10.0,
        physical_divergence=0.01,
        metadata={
            "paired_cash_delta": -250.0,
            "median_paired_cash_delta": -50.0,
            "paired_cash_relative_delta": -0.004,
            "worst_family_cash_delta": -500.0,
            "worst_family_cash_relative_delta": -0.01,
            "mean_control_cash": 50000.0,
        },
    )
    thresholds = {
        "min_paired_score_delta": -0.01,
        "min_worst_family_delta": -0.05,
        "min_paired_cash_delta": 100.0,
        "min_median_paired_cash_delta": 0.0,
        "min_paired_cash_relative_delta": 0.002,
        "min_worst_family_cash_delta": -1500.0,
        "min_worst_family_cash_relative_delta": -0.03,
        "min_passive_cash_ratio": 0.97,
        "max_invalid_games": 0,
        "max_mean_call_ms": 100.0,
        "max_physical_divergence": 0.02,
    }
    decision = promotion_decision(evaluation, thresholds)
    assert not decision.promote
    assert "failed paired cash delta" in decision.reasons
    assert "failed median paired cash delta" in decision.reasons

    profitable = EvaluationRecord(
        **{
            **evaluation.__dict__,
            "metadata": {
                **evaluation.metadata,
                "paired_cash_delta": 500.0,
                "median_paired_cash_delta": 300.0,
                "paired_cash_relative_delta": 0.01,
            },
        }
    )
    assert promotion_decision(profitable, thresholds).promote


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
