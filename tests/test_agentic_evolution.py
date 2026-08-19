import numpy as np
import pandas as pd

from kagv2.agentic.interventions import intervention_grammar, mutate_market_once
from kagv2.agentic.loop import LossDrivenEvolutionLoop
from kagv2.agentic.population import population_report
from kagv2.agentic.promotion import paired_candidate_metrics, evaluate_promotion
from kagv2.agentic.regime import grouped_oof_regime_predictions
from kagv2.agentic.regret import grouped_oof_distributional_regret, residual_threshold_sweep


def test_grouped_regime_model_detects_seed_conditioned_risk():
    rng = np.random.default_rng(7)
    rows = []
    for seed in range(40):
        demand = float(rng.integers(0, 8))
        shop = "BAKERY" if demand > 3 else "PET_CAFE"
        for opp in ("adaptive", "ranker"):
            for seat in (0, 1):
                early = -2500 * demand + 500 * seat + rng.normal(0, 500)
                loss = int(demand >= 4 or early < -8000)
                rows.append({
                    "seed": seed, "opponent": opp, "seat": seat,
                    "score": 0.0 if loss else 1.0,
                    "demand_WHEAT": demand, "cash_margin_d10": early,
                    "our_weeds_d10": int(demand > 5), "opp_weeds_d10": 0,
                    "shop_1": shop,
                })
    _, metrics = grouped_oof_regime_predictions(pd.DataFrame(rows), n_splits=5)
    assert metrics.auc is not None and metrics.auc > 0.9
    assert metrics.lift_at_quartile > 1.2


def test_distributional_regret_learns_conditional_override():
    rng = np.random.default_rng(11)
    rows = []
    for seed in range(60):
        opp = "adaptive" if seed % 2 == 0 else "ranker"
        base = -18000 + rng.normal(0, 4500)
        for step, day in ((168, 7), (240, 10)):
            for mut in ("suppress", "half"):
                beneficial = mut == "suppress" and base < -19000 and day == 10
                delta = (6500 + rng.normal(0, 600)) if beneficial else (-2500 + rng.normal(0, 900))
                rows.append({
                    "opponent": opp, "seed": seed, "seat": seed % 2,
                    "base_margin": base, "base_score": 0,
                    "step": step, "index": 3, "op": "HIRE", "item": "", "qty": 1,
                    "mutation": mut, "ok": True, "activated": 1,
                    "margin_delta": delta, "day": day,
                    "day_bucket": "10-14" if day == 10 else "5-9",
                })
    oof, metrics = grouped_oof_distributional_regret(pd.DataFrame(rows), n_splits=5)
    assert metrics.auc_benefit is not None and metrics.auc_benefit > 0.8
    sweep = residual_threshold_sweep(
        oof,
        p_thresholds=(0.7, 0.8, 0.9),
        mean_thresholds=(0, 500),
        q10_floors=(-500, 0),
    )
    best = sweep[sweep.selected_events > 0].sort_values("mean_realized_delta", ascending=False).iloc[0]
    assert best.mean_realized_delta > 0
    assert best.positive_rate > 0.7


def _promotion_games():
    rows = []
    opponents = ["adaptive", "ranker", "soil", "v16", "v32_direct"]
    hard, safe = {1, 2}, {3, 4}
    for seed in range(1, 5):
        for opp in opponents:
            for seat in (0, 1):
                control = 0.0 if seed in hard and opp in {"adaptive", "ranker"} else 1.0
                rows.append({
                    "candidate": "V32", "opponent": opp, "seed": seed, "seat": seat,
                    "score": control, "margin": 1000 if control else -1000,
                    "cash": 50000, "ok": True, "changes": 0,
                })
                cand = 1.0 if seed in hard and opp in {"adaptive", "ranker"} else control
                rows.append({
                    "candidate": "GOOD", "opponent": opp, "seed": seed, "seat": seat,
                    "score": cand, "margin": 1500 if cand else -900,
                    "cash": 50200, "ok": True, "changes": 1,
                })
    return pd.DataFrame(rows), hard, safe


def test_promotion_requires_hard_seed_improvement_and_guard_safety():
    df, hard, safe = _promotion_games()
    metrics = paired_candidate_metrics(
        df, candidate="GOOD", control="V32",
        target_opponents={"adaptive", "ranker"}, guard_opponents={"soil", "v16"},
        hard_seeds=hard, safe_seeds=safe,
    )
    decision = evaluate_promotion(metrics)
    assert decision.promoted
    assert metrics["hard_delta"] > 0
    assert metrics["worst_guard_delta"] >= 0


def test_population_mix_keeps_complementary_specialists():
    rows = []
    for _ in range(20):
        rows += [
            {"candidate": "A", "opponent": "x", "score": 1.0},
            {"candidate": "A", "opponent": "y", "score": 0.0},
            {"candidate": "B", "opponent": "x", "score": 0.0},
            {"candidate": "B", "opponent": "y", "score": 1.0},
        ]
    report = population_report(pd.DataFrame(rows), equilibrium_weight=1.0, shrink=1.0)
    assert set(report.policies) == {"A", "B"}
    assert all(w > 0.25 for w in report.policy_mixture)
    assert report.duality_gap < 0.05


def test_market_intervention_grammar_is_bounded():
    assert {x.mutation for x in intervention_grammar(["BUY_SEED", "STRAWBERRY", 8])} == {"half", "suppress"}
    assert {x.mutation for x in intervention_grammar(["SELL", "MILK", 6])} == {"half", "delay1"}


def test_mutate_market_once_does_not_touch_other_orders():
    market = [["SELL", "MILK", 6], ["HIRE"]]
    changed, pending, ok = mutate_market_once(market, 0, "half")
    assert ok and changed == [["SELL", "MILK", 3], ["HIRE"]] and pending is None
    assert market[0][2] == 6


def test_loop_emits_manifest(tmp_path):
    regime = []
    for seed in range(24):
        d = seed % 8
        for opp in ("adaptive", "ranker"):
            for seat in (0, 1):
                loss = d >= 4
                regime.append({
                    "seed": seed, "opponent": opp, "seat": seat,
                    "score": 0.0 if loss else 1.0,
                    "demand_WHEAT": d, "cash_margin_d10": -2000 * d,
                    "our_weeds_d10": int(d > 5), "opp_weeds_d10": 0,
                    "shop_1": "BAKERY" if d >= 4 else "PET_CAFE",
                })
    cf = []
    for seed in range(30):
        base = -20000 if seed % 3 == 0 else -5000
        for mut in ("suppress", "half"):
            delta = 5000 if seed % 3 == 0 and mut == "suppress" else -1000
            cf.append({
                "seed": seed, "opponent": "adaptive" if seed % 2 else "ranker", "seat": seed % 2,
                "base_margin": base, "base_score": 0, "step": 240, "day": 10,
                "index": 4, "op": "HIRE", "item": "", "qty": 1, "mutation": mut,
                "ok": True, "activated": 1, "margin_delta": delta, "day_bucket": "10-14",
            })
    manifest = LossDrivenEvolutionLoop().run(
        counterfactuals=pd.DataFrame(cf),
        regime_games=pd.DataFrame(regime),
        output_dir=tmp_path,
    )
    assert manifest["regime"]["auc"] > 0.8
    assert manifest["regret"]["auc_benefit"] > 0.7
    assert (tmp_path / "EVOLUTION_MANIFEST.json").exists()


def test_counterfactual_factory_replays_single_market_mutation():
    from kagv2.agentic.counterfactual import BranchSpec, apply_branch, economic_branch_specs
    action = {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 8], ["HIRE"]]}
    specs = economic_branch_specs(action, step=120)
    assert any(s.op == "BUY_SEED" and s.mutation == "half" for s in specs)
    spec = BranchSpec(step=120, market_index=0, mutation="half", op="BUY_SEED", item="STRAWBERRY", qty=8)
    changed, pending, hit = apply_branch(action, spec)
    assert hit and pending is None
    assert changed["market"][0] == ["BUY_SEED", "STRAWBERRY", 4]
    assert action["market"][0][2] == 8


def test_counterfactual_factory_can_generate_rows_with_fresh_agents():
    from kagv2.agentic.counterfactual import build_counterfactual_rows

    class FakeGame:
        episode_steps = 2
        def __init__(self, seed):
            self.step = 0
            self.farms = [
                {"money": 3000.0, "hands": [], "unlocked_quadrants": ["NW"], "tiles": []},
                {"money": 3000.0, "hands": [], "unlocked_quadrants": ["NW"], "tiles": []},
            ]
        def obs(self, p):
            return {
                "player": p, "step": self.step, "day": 0, "hour": self.step,
                "farms": self.farms,
                "private": {"shed": {}},
                "market": {"inventory": {}, "prices": {}},
                "town": {"unlocked_shops": []},
            }
        def step_once(self, actions):
            self.step += 1

    def champion_factory():
        def agent(obs):
            return {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 2]]}
        return agent

    def opponent_factory():
        return lambda obs: {"farmer": ["PASS"], "hands": [], "market": []}

    rows = build_counterfactual_rows(
        champion_factory, opponent_factory, seed=3, seat=0, max_events=2,
        game_factory=FakeGame,
    )
    assert rows
    assert all(r["activated"] == 1 for r in rows)
    assert {r["mutation"] for r in rows} == {"half", "suppress"}
