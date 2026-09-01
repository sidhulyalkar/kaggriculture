from __future__ import annotations

from swarm.kaggle_intelligence import _csv_rows, _select_manifest_rows, episode_fingerprint
from swarm.overnight_council import _validate_one
from swarm.overnight_slate import build_route_candidate, learn_route_map


def test_manifest_selection_keeps_top_and_diversity_without_duplicates():
    rows = [{"episode_id": str(i), "avg_score": str(4000 - i)} for i in range(100)]
    picked = _select_manifest_rows(rows, top_n=8, diverse_n=4)
    ids = [row["episode_id"] for row, _ in picked]
    reasons = [reason for _, reason in picked]
    assert len(ids) == len(set(ids)) == 12
    assert ids[:8] == [str(i) for i in range(8)]
    assert reasons.count("top") == 8
    assert reasons.count("upper_band_diverse") == 4


def test_csv_parser_handles_bom():
    rows = _csv_rows("\ufeffid,score\n12,1592.9\n")
    assert rows == [{"id": "12", "score": "1592.9"}]


def test_episode_fingerprint_captures_route_and_winner():
    observation = {
        "town": {"unlocked_shops": ["PET_CAFE", "YARN_STORE"]},
        "farms": [
            {"hands": [{}, {}], "unlocked_quadrants": [0, 1, 2], "tiles": [[{"animal": "COW"}]]},
            {"hands": [{}], "unlocked_quadrants": [0], "tiles": [[{"crop": "WHEAT"}]]},
        ],
    }
    rep = {
        "info": {"TeamNames": ["ours", "them"], "EpisodeId": 99, "seed": 7},
        "rewards": [100.0, 90.0],
        "steps": [[
            {"observation": observation, "action": {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]}},
            {"observation": observation, "action": {"farmer": ["PASS"], "hands": [], "market": []}},
        ]],
        "_meta_date": "2026-09-01",
        "_meta_avg_score": 3200.0,
    }
    fp = episode_fingerprint(rep)
    assert fp["winner_team"] == "ours"
    assert fp["signature"]["shop_prefix"] == ["PET_CAFE", "YARN_STORE"]
    assert fp["signature"]["market_counts"]["BUY_SEED"] == 1
    assert len(fp["signature_sha256"]) == 64


def test_learn_route_map_only_changes_supported_prefix():
    rows = [{
        "trace": i,
        "prefix": ["PET_CAFE", "YARN_STORE"],
        "scores": {"6c8s_3q": 0.8, "6c12s_4q_second_yarn": 0.2, "8c6s_3q": 0.0},
        "confidence": 0.6,
        "avg_score": 3300.0,
    } for i in range(3)]
    learned = learn_route_map(rows, {0, 1, 2}, min_count=2, min_advantage=0.05, min_match=0.1)
    assert learned[("PET_CAFE", "YARN_STORE")] == "6c8s_3q"


def test_route_candidate_replaces_selector_without_rewriting_controller():
    source = '''_KAWA_MILK_SUPPORT={"PIZZA_SHOP"}\ndef _get(v,k,d=None):\n    return v.get(k,d)\ndef _kawa_route_label(obs):\n    shops = list(((_get(obs, "town", {}) or {}).get("unlocked_shops", []) or []))\n    if shops[:1] == ["YARN_STORE"]:\n        return "6c12s_4q_first_yarn"\n    if "YARN_STORE" in shops[:2]:\n        if shops[:1] in (["BRUNCH_SPOT"], ["SMOOTHIE_SHOP"]):\n            return "6c8s_3q"\n        return "6c12s_4q_second_yarn"\n    if "YARN_STORE" in shops[:3]:\n        return "6c8s_3q"\n    if _KAWA_MILK_SUPPORT.intersection(shops[:3]):\n        return "10c4s_3q"\n    return "8c6s_3q"\n\n_KAWA_LAYOUT_FALLBACK={0:None,1:None}\n'''
    candidate = build_route_candidate(source, {("PIZZA_SHOP",): "8c6s_3q"}, "TEST")
    ns: dict[str, object] = {}
    exec(compile(candidate, "<candidate>", "exec"), ns)
    assert ns["_kawa_route_label"]({"town": {"unlocked_shops": ["PIZZA_SHOP"]}}) == "8c6s_3q"
    assert "_KAWA_LAYOUT_FALLBACK" in candidate


def test_council_validation_rejects_unbounded_code_and_accepts_sparse_mutations():
    route = _validate_one({"mutation_type": "route", "prefix": ["PET_CAFE", "YARN_STORE"], "route": "6c8s_3q"}, "adversary")
    param = _validate_one({"mutation_type": "parameter", "field": "_PREEMPT_START", "value": 108}, "mechanism")
    bad = _validate_one({"mutation_type": "code", "python": "import os"}, "auditor")
    assert route and route["route"] == "6c8s_3q"
    assert param and param["value"] == 108
    assert bad is None
