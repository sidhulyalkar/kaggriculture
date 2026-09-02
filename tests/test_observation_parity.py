from __future__ import annotations

from types import SimpleNamespace

from swarm.observation_parity import canonical_step, inject_parity_shim, normalize_observation_step


def _load_agent(source: str):
    patched = inject_parity_shim(source)
    ns: dict[str, object] = {}
    exec(patched, ns)
    return ns["agent"], patched


def test_canonical_step_uses_day_hour_not_missing_step():
    obs = {"day": 3, "hour": 7}
    assert canonical_step(obs) == 79
    assert normalize_observation_step(obs) == 79
    assert obs["step"] == 79


def test_canonical_step_overwrites_stale_seat_one_step():
    obs = {"day": 4, "hour": 5, "step": 0}
    assert normalize_observation_step(obs) == 101
    assert obs["step"] == 101


def test_object_observation_is_supported():
    obs = SimpleNamespace(day=2, hour=11, step=None)
    assert normalize_observation_step(obs) == 59
    assert obs.step == 59


def test_injected_agent_advances_when_step_is_missing():
    source = '''\ndef helper(obs):\n    return int(obs.get("step", 0) or 0)\n\ndef agent(obs):\n    return helper(obs)\n'''
    agent, _ = _load_agent(source)
    assert agent({"day": 1, "hour": 2}) == 26
    assert agent({"day": 1, "hour": 2, "step": 0}) == 26


def test_injected_agent_preserves_correct_clock():
    source = '''\ndef agent(obs):\n    return int(obs.get("step", 0) or 0)\n'''
    agent, _ = _load_agent(source)
    assert agent({"day": 5, "hour": 9, "step": 129}) == 129


def test_injector_uses_historical_one_space_body_indent():
    # Several public Kaggriculture agents use compact one-space indentation.
    source = '''\ndef agent(obs, configuration=None):\n step=max(0,int(obs.get("step",0) or 0))\n return step\n'''
    agent, patched = _load_agent(source)
    assert agent({"day": 2, "hour": 3}) == 51
    assert "\n _v49_normalize_observation_step(obs)\n" in patched


def test_injector_supports_multiline_signature_and_nonstandard_indent():
    source = '''\ndef agent(\n    observation,\n    configuration=None,\n):\n  value = int(observation.get("step", 0) or 0)\n  return value\n'''
    agent, patched = _load_agent(source)
    assert agent({"day": 6, "hour": 4}) == 148
    assert "_v49_normalize_observation_step(observation)" in patched


def test_injector_ignores_agent_text_inside_embedded_source():
    source = '''\n_BASE = "def agent(obs):\\n return 0\\n"\ndef agent(obs):\n    return int(obs.get("step", 0) or 0)\n'''
    agent, _ = _load_agent(source)
    assert agent({"day": 1, "hour": 11}) == 35
