from __future__ import annotations

from types import SimpleNamespace

from swarm.observation_parity import canonical_step, inject_parity_shim, normalize_observation_step


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
    patched = inject_parity_shim(source)
    ns: dict[str, object] = {}
    exec(patched, ns)
    assert ns["agent"]({"day": 1, "hour": 2}) == 26
    assert ns["agent"]({"day": 1, "hour": 2, "step": 0}) == 26


def test_injected_agent_preserves_correct_clock():
    source = '''\ndef agent(obs):\n    return int(obs.get("step", 0) or 0)\n'''
    patched = inject_parity_shim(source)
    ns: dict[str, object] = {}
    exec(patched, ns)
    assert ns["agent"]({"day": 5, "hour": 9, "step": 129}) == 129
