from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "v40_frontier_distillation.py"
spec = importlib.util.spec_from_file_location("v40_builder_test", SCRIPT)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


DUMMY_PARENT = '''
STRAWBERRY_MAX = 24
MAX_HANDS = 11
MAX_QUADRANTS = 2
COW_MAX = 8
SHEEP_MAX = 6

def agent(obs):
    p = int(obs.get("player", 0))
    farms = obs.get("farms", [{}])
    farm = farms[p] if p < len(farms) else {}
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in (farm.get("hands", []) or [])],
        "market": [],
    }
'''


def _obs(hands=2):
    tiles = [[None for _ in range(10)] for _ in range(10)]
    farm = {"money": 5000, "hands": [[4, 4] for _ in range(hands)], "tiles": tiles}
    return {
        "player": 0,
        "day": 10,
        "hour": 0,
        "farms": [farm, dict(farm)],
        "private": {"shed": {}, "inventories": [{} for _ in range(hands + 1)]},
        "market": {"prices": {}, "inventory": {}},
    }


def test_constant_surgery_is_exact_and_scoped():
    out = mod.replace_constant(DUMMY_PARENT, "MAX_HANDS", 12)
    assert "MAX_HANDS = 12" in out
    assert "MAX_QUADRANTS = 2" in out


def test_v40_build_is_exec_loader_safe(tmp_path):
    main = mod.build_candidate(
        DUMMY_PARENT,
        mod.CANDIDATES["V40_FERT_FLYWHEEL"],
        tmp_path / "candidate",
    )
    assert mod.exec_style_gate(main) == "v40_frontier_agent"


def test_v40_cardinality_guard_preserves_live_hand_count(tmp_path):
    main = mod.build_candidate(
        DUMMY_PARENT,
        mod.CANDIDATES["V40_FERT_FLYWHEEL"],
        tmp_path / "candidate",
    )
    fn = mod.load_agent(main, "v40_cardinality_test")
    action = fn(_obs(hands=3))
    assert len(action["hands"]) == 3
    assert len(action["market"]) <= 10
